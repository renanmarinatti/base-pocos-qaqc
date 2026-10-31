"""Banco final (E5): carrega a base padronizada, conciliada e marcada num DuckDB.

O esquema, com chaves, restrições e comentários, está em sql/esquema.sql. Esta carga
aplica as decisões que mudam dado (D09 tira MUDWEIGHT, D10 troca códigos de nulo por NULL)
e transforma as marcas de qualidade por amostra em colunas (R08, R14). Depois gera o
dicionário de dados a partir dos comentários do próprio banco.

Saídas: data/processed/base_pocos.duckdb (fora do Git; se recria com um comando),
docs/dicionario.md e data/processed/banco.json.

Uso: uv run python -m pocos.database
"""

import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from pocos.collect import read_manifest
from pocos.inventory import PROCESSED
from pocos.reconcile import prepare_tops
from pocos.standardize import INTERIM, load_yaml

DB = PROCESSED / "base_pocos.duckdb"
SCHEMA = Path("sql/esquema.sql")
DICTIONARY = Path("docs/dicionario.md")
DECISIONS = Path("docs/decisoes.md")

CURVES = [
    "GR",
    "SGR",
    "RHOB",
    "DRHO",
    "NPHI",
    "PEF",
    "DTC",
    "DTS",
    "RDEP",
    "RMED",
    "RSHA",
    "RXO",
    "RMIC",
    "SP",
    "CALI",
    "DCAL",
    "BS",
    "ROP",
    "ROPA",
]


def sample_table(samples: pd.DataFrame, rules: dict, log: dict) -> pd.DataFrame:
    s = samples.copy()
    codes = rules["R12"]["parametros"]["codigos"]
    for curve in CURVES:
        hit = s[curve].isin(codes)
        if hit.any():
            log["nulos_trocados_D10"][curve] = int(hit.sum())
            s.loc[hit, curve] = None

    p8 = rules["R08"]["parametros"]
    washout = s["DCAL"].where(s["DCAL"].notna(), s["CALI"] - s["BS"]) > p8["arrombamento_in"]
    s["rhob_arrombado"] = s["RHOB"].notna() & (
        washout.fillna(False) | (s["DRHO"].abs() > p8["drho_max"]).fillna(False)
    )
    s["pef_baritina"] = (s["PEF"] > rules["R14"]["parametros"]["pef_max"]).fillna(False)
    s = s.rename(
        columns={
            "X_LOC": "x_utm31_ed50",
            "Y_LOC": "y_utm31_ed50",
            "LITOLOGIA": "litologia_codigo",
            "CONFIANCA": "confianca",
        }
    )
    s["litologia_codigo"] = s["litologia_codigo"].astype("Int64")
    cols = [
        "poco",
        "md",
        "tvdss",
        "x_utm31_ed50",
        "y_utm31_ed50",
        *CURVES,
        "litologia_codigo",
        "confianca",
        "rhob_arrombado",
        "pef_baritina",
        "arquivo",
    ]
    return s[cols]  # MUDWEIGHT fica de fora (D09)


def well_table(wells: pd.DataFrame, notes: pd.DataFrame, rec: pd.DataFrame) -> pd.DataFrame:
    w = wells.merge(notes[["poco", "nota"]], on="poco").merge(rec[["poco", "achados"]], on="poco")
    return pd.DataFrame(
        {
            "poco": w["poco"],
            "poco_force": w["poco_force"],
            "tipo": w["tipo"],
            "mesa_rotativa_m": w["mesa_rotativa_m"],
            "lamina_dagua_m": w["lamina_dagua_m"],
            "prof_final_md_m": w["prof_final_md_sodir"],
            "prof_final_tvd_m": w["prof_final_tvd_sodir"],
            "inclinacao_max_graus": w["inclinacao_max_sodir"],
            "x_utm31_ed50": w["x_sodir"],
            "y_utm31_ed50": w["y_sodir"],
            "lat_wgs84": w["lat_wgs84"],
            "lon_wgs84": w["lon_wgs84"],
            "md_min_perfil": w["md_min"],
            "md_max_perfil": w["md_max"],
            "desvio_max_m": w["desvio_max_m"],
            "nota_qualidade": w["nota"],
            "achados_conciliacao": w["achados"].fillna(""),
            "arquivo_las": "force/LAS_files_Force_2020_all_wells.zip",
            "arquivo_sodir": w["arquivo_sodir"],
        }
    )


def tops_table(tops: pd.DataFrame, rec: pd.DataFrame) -> pd.DataFrame:
    t = prepare_tops(tops, load_yaml("nomes_unidades.yaml"))
    t = t[t["fonte"] == "sodir"]
    key = ["poco", "base", "ocorrencia"]
    for source, suffix in (("npd_2020", "npd2020"), ("perfil_force", "perfil")):
        r = rec[rec["comparacao"] == f"{source} × sodir"][key + ["topo_md_fonte", "situacao"]]
        r = r.rename(
            columns={"topo_md_fonte": f"topo_md_{suffix}", "situacao": f"situacao_{suffix}"}
        )
        t = t.merge(r, on=key, how="left")
    return t.rename(columns={"base": "unidade_base"})[
        [
            "poco",
            "nivel",
            "unidade",
            "unidade_base",
            "ocorrencia",
            "topo_md",
            "base_md",
            "topo_md_npd2020",
            "situacao_npd2020",
            "topo_md_perfil",
            "situacao_perfil",
            "arquivo",
        ]
    ]


def decisions() -> pd.DataFrame:
    rows = re.findall(r"^## (D\d+) — (.+)$", DECISIONS.read_text(encoding="utf-8"), re.M)
    return pd.DataFrame(rows, columns=["decisao", "titulo"])


def load(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    con.register("df", df)
    cols = ", ".join(f'"{c}"' for c in df.columns)
    con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM df")
    con.unregister("df")


def dictionary(con: duckdb.DuckDBPyConnection) -> str:
    tables = con.execute(
        "SELECT table_name, comment, estimated_size FROM duckdb_tables() ORDER BY table_oid"
    ).fetchall()
    keys = con.execute(
        "SELECT table_name, constraint_type, constraint_column_names, referenced_table "
        "FROM duckdb_constraints() WHERE constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')"
    ).df()
    out = [
        "# Dicionário de dados",
        "",
        "Gerado de `sql/esquema.sql` pelo próprio banco (`uv run python -m pocos.database`). "
        "Não editar à mão.",
        "",
    ]
    for name, comment, _ in tables:
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        out += [f"## `{name}`", "", f"{comment}", "", f"Linhas: {n:,}".replace(",", "."), ""]
        k = keys[keys["table_name"] == name]
        for r in k.itertuples():
            cols = ", ".join(r.constraint_column_names)
            if r.constraint_type == "PRIMARY KEY":
                out.append(f"- Chave: `{cols}`")
            else:
                out.append(f"- `{cols}` → `{r.referenced_table}`")
        out += ["", "| Coluna | Tipo | Nulo | Descrição |", "|---|---|---|---|"]
        for col, dtype, nullable, ccomment in con.execute(
            "SELECT column_name, data_type, is_nullable, comment FROM duckdb_columns() "
            "WHERE table_name = ? ORDER BY column_index",
            [name],
        ).fetchall():
            out.append(f"| `{col}` | {dtype} | {'sim' if nullable else 'não'} | {ccomment or ''} |")
        out.append("")
    return "\n".join(out)


def run() -> dict:
    rules = load_yaml("regras.yaml")["regras"]
    catalog = load_yaml("mnemonicos.yaml")["curvas"]
    log = {"nulos_trocados_D10": {}}

    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute(SCHEMA.read_text(encoding="utf-8"))

    manifest = pd.DataFrame(read_manifest().values())
    manifest["coletado_em"] = pd.to_datetime(manifest["coletado_em"])
    manifest["bytes"] = manifest["bytes"].astype(int)
    load(con, "fonte", manifest)

    wells = pd.read_parquet(INTERIM / "pocos.parquet")
    notes = pd.read_csv(PROCESSED / "notas.csv")
    rec_wells = pd.read_csv(PROCESSED / "conciliacao_pocos.csv")
    load(con, "poco", well_table(wells, notes, rec_wells))

    load(
        con,
        "curva",
        pd.DataFrame(
            [
                {
                    "curva": c,
                    "unidade": catalog[c]["unidade"],
                    "faixa_min": catalog[c]["faixa"][0],
                    "faixa_max": catalog[c]["faixa"][1],
                    "descricao": catalog[c]["descricao"],
                }
                for c in CURVES
            ]
        ),
    )
    load(con, "amostra", sample_table(pd.read_parquet(INTERIM / "amostras.parquet"), rules, log))

    lith = pd.read_parquet(INTERIM / "litologia.parquet")
    load(con, "litologia_intervalo", lith.drop(columns=["arquivo"]))

    rec_tops = pd.read_csv(PROCESSED / "conciliacao_topos.csv")
    load(con, "topo", tops_table(pd.read_parquet(INTERIM / "topos.parquet"), rec_tops))

    cores = pd.read_csv(PROCESSED / "conciliacao_testemunhos.csv").rename(
        columns={"litologia_dominante_no_perfil": "litologia_no_perfil"}
    )
    load(
        con,
        "testemunho",
        cores[
            [
                "poco",
                "numero",
                "topo_md",
                "base_md",
                "unidade_original",
                "cobertura_perfil",
                "litologia_no_perfil",
                "situacao",
                "arquivo",
            ]
        ],
    )

    load(
        con,
        "regra",
        pd.DataFrame(
            [
                {
                    "regra": k,
                    "nome": v["nome"],
                    "gravidade": v["gravidade"],
                    "descricao": " ".join(v["descricao"].split()),
                }
                for k, v in rules.items()
            ]
        ),
    )
    problems = pd.read_csv(PROCESSED / "problemas.csv")
    problems.insert(0, "id", range(1, len(problems) + 1))
    load(
        con,
        "problema",
        problems[["id", "regra", "poco", "curva", "topo_md", "base_md", "amostras", "detalhe"]],
    )
    load(con, "decisao", decisions())

    DICTIONARY.write_text(dictionary(con), encoding="utf-8")
    counts = {
        t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for (t,) in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()
    }
    con.close()
    summary = {"tabelas": counts, "megabytes": round(DB.stat().st_size / 1e6, 1), **log}
    (PROCESSED / "banco.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))
