"""Conciliação (E4): compara as fontes entre si e classifica cada diferença.

A Sodir é a referência oficial; as outras versões são comparadas contra ela.

- Topos: perfil do FORCE × Sodir e cópia NPD 2020 × Sodir. Cada topo é casado pelo
  nome-base da unidade (config/nomes_unidades.yaml) e pela ordem de ocorrência no poço,
  porque uma unidade pode aparecer mais de uma vez.
- Poços: posição na cabeça do poço, mesa rotativa e profundidade final, com a regra de
  quando a comparação vale (o perfil pode começar abaixo do ponto de desvio).
- Testemunhos: se o intervalo testemunhado tem perfil e cabe na profundidade final.

Classifica, não corrige. O que exige escolha vai para docs/decisoes.md.

Saídas em data/processed/: conciliacao_topos.csv, conciliacao_pocos.csv,
conciliacao_testemunhos.csv e conciliacao.json.

Uso: uv run python -m pocos.reconcile
"""

import json
import re

import numpy as np
import pandas as pd

from pocos.inventory import PROCESSED
from pocos.standardize import INTERIM, load_yaml

TOP_TOLERANCE_M = 1.0  # a Sodir arredonda o topo ao metro; o perfil tem passo de 0,152 m
POSITION_TOLERANCE_M = 25.0
KB_TOLERANCE_M = 0.5
TD_TOLERANCE_M = 5.0
SHIFT_MIN_TOPS = 3
SHIFT_MAX_STD_M = 0.5
VERTICAL_AT_TOP_M = 1.0  # MD − TVDSS − mesa rotativa abaixo disso: poço ainda vertical


def base_name(unit: str, renames: dict) -> str:
    u = unit.upper().replace("Ø", "OE").replace("Æ", "AE").replace("Å", "AA")
    u = re.sub(r"\.", "", u)
    u = re.sub(r"\s*\(INFORMAL\)", "", u)
    u = re.sub(r"\s+", " ", u).strip()
    u = re.sub(r"\s+(GP|FM|MB|SST|SS)$", "", u)
    return renames.get(u, u)


def level_suffix(unit) -> str:
    if not isinstance(unit, str):
        return ""
    m = re.search(r"\b(GP|FM|MB|SST|SS)\.?$", unit.upper().strip())
    return m.group(1) if m else ""


def prepare_tops(tops: pd.DataFrame, names: dict) -> pd.DataFrame:
    t = tops.copy()
    t["base"] = t["unidade"].map(lambda u: base_name(u, names["renomeadas"]))
    t = t[~t["base"].isin(names["marcadores_sem_nome"])]
    t = t.sort_values(["fonte", "poco", "base", "topo_md"])
    t["ocorrencia"] = t.groupby(["fonte", "poco", "base"]).cumcount() + 1
    return t


def compare_tops(t: pd.DataFrame, source: str, logged: pd.DataFrame) -> pd.DataFrame:
    """Casa os topos de `source` com os da Sodir e classifica cada par."""
    key = ["poco", "base", "ocorrencia"]
    cols = key + ["unidade", "topo_md"]
    a = t[t["fonte"] == source][cols]
    s = t[t["fonte"] == "sodir"][cols]
    m = a.merge(s, on=key, how="outer", suffixes=("_fonte", "_sodir"), indicator=True)
    m["delta_m"] = m["topo_md_fonte"] - m["topo_md_sodir"]
    m = m.merge(logged, on="poco", how="left")

    status = np.select(
        [
            m["_merge"] == "left_only",
            m["_merge"] == "right_only",
            m["delta_m"].abs() <= TOP_TOLERANCE_M,
        ],
        [f"só em {source}", "só na Sodir", "igual"],
        default="divergente",
    )
    m["situacao"] = status
    if source == "perfil_force":
        # Topo oficial fora do trecho rotulado não tem como aparecer no perfil. O trecho
        # rotulado (CSV com GROUP e FORMATION) pode começar bem abaixo do LAS; nesse caso a
        # primeira unidade do perfil "começa" onde o rótulo começa, não onde a rocha começa.
        first_label = a.groupby("poco")["topo_md"].min().rename("rotulo_min")
        m = m.merge(first_label, on="poco", how="left")
        outside = (
            (m["topo_md_sodir"] < m["rotulo_min"] - TOP_TOLERANCE_M)
            | (m["topo_md_sodir"] > m["md_max"] + TOP_TOLERANCE_M)
            | (m["topo_md_fonte"] <= m["rotulo_min"] + TOP_TOLERANCE_M)
            & (m["delta_m"] > TOP_TOLERANCE_M)
        )
        m.loc[outside & m["situacao"].isin(["só na Sodir", "divergente"]), "situacao"] = (
            "fora do trecho perfilado"
        )
    # Vários topos do mesmo poço deslocados pelo mesmo valor não são reinterpretação: é a
    # referência de profundidade que mudou. Separa um caso do outro.
    # O topo que foge do deslocamento comum continua divergente: pode ser reinterpretação
    # somada à mudança de referência.
    div = m["situacao"] == "divergente"
    median = m[div].groupby("poco")["delta_m"].transform("median")
    near = (m.loc[div, "delta_m"] - median).abs() < SHIFT_MAX_STD_M
    count = near.groupby(m.loc[div, "poco"]).transform("sum")
    m.loc[near[near & (count >= SHIFT_MIN_TOPS)].index, "situacao"] = (
        "deslocamento uniforme do poço"
    )
    renamed = (m["_merge"] == "both") & (
        m["unidade_fonte"].map(level_suffix) != m["unidade_sodir"].map(level_suffix)
    )
    m["mudou_nivel"] = renamed
    m.insert(0, "comparacao", f"{source} × sodir")
    return m.drop(columns=["_merge", "md_min", "md_max", "rotulo_min"], errors="ignore")


def wells_check(wells: pd.DataFrame) -> pd.DataFrame:
    w = wells.copy()
    implied_kb = w["md_menos_tvdss_topo"]
    w["vertical_no_inicio"] = (implied_kb - w["mesa_rotativa_m"]).abs() < VERTICAL_AT_TOP_M + 5
    # Se o perfil começa já desviado, MD − TVDSS no topo é muito maior que a mesa rotativa,
    # e nem a posição nem a referência vertical podem ser comparadas pela primeira amostra.
    w["comparavel_pela_1a_amostra"] = (implied_kb - w["mesa_rotativa_m"]) < 50
    w["delta_mesa_m"] = implied_kb - w["mesa_rotativa_m"]
    w["delta_prof_final_m"] = w["md_max"] - w["prof_final_md_sodir"]

    def status(r) -> list[str]:
        out = []
        if not r["comparavel_pela_1a_amostra"]:
            out.append("perfil começa abaixo do ponto de desvio: posição e mesa não comparáveis")
            return out
        if r["dist_force_sodir_m"] > POSITION_TOLERANCE_M:
            out.append(f"posição a {r['dist_force_sodir_m']:.0f} m da Sodir")
        if abs(r["delta_mesa_m"]) > KB_TOLERANCE_M:
            out.append(f"referência vertical {r['delta_mesa_m']:+.1f} m da mesa rotativa da Sodir")
        if r["delta_prof_final_m"] > TD_TOLERANCE_M:
            out.append(
                f"perfil {r['delta_prof_final_m']:.0f} m abaixo da profundidade final oficial"
            )
        return out

    w["achados"] = w.apply(lambda r: "; ".join(status(r)), axis=1)
    cols = [
        "poco",
        "poco_force",
        "dist_force_sodir_m",
        "mesa_rotativa_m",
        "delta_mesa_m",
        "md_min",
        "md_max",
        "prof_final_md_sodir",
        "delta_prof_final_m",
        "desvio_max_m",
        "comparavel_pela_1a_amostra",
        "achados",
    ]
    return w[cols]


def cores_check(
    cores: pd.DataFrame, samples: pd.DataFrame, wells: pd.DataFrame, lith: pd.DataFrame
) -> pd.DataFrame:
    c = cores.merge(wells[["poco", "md_min", "md_max", "prof_final_md_sodir"]], on="poco")
    covered = []
    dominant = []
    by_well = {w: g["md"].to_numpy() for w, g in samples[["poco", "md"]].groupby("poco")}
    lith_by_well = {w: g for w, g in lith.groupby("poco")}
    for r in c.itertuples():
        md = by_well.get(r.poco, np.array([]))
        inside = md[(md >= r.topo_md) & (md <= r.base_md)]
        length = max(r.base_md - r.topo_md, 0.152)
        covered.append(min(len(inside) * 0.152 / length, 1.0))
        lw = lith_by_well.get(r.poco)
        if lw is None:
            dominant.append("")
            continue
        o = lw[(lw["base_md"] > r.topo_md) & (lw["topo_md"] < r.base_md)]
        if o.empty:
            dominant.append("")
            continue
        overlap = np.minimum(o["base_md"], r.base_md) - np.maximum(o["topo_md"], r.topo_md)
        dominant.append(overlap.groupby(o["litologia"]).sum().idxmax())
    c["cobertura_perfil"] = np.round(covered, 3)
    c["litologia_dominante_no_perfil"] = dominant
    c["situacao"] = np.select(
        [
            c["base_md"] > c["prof_final_md_sodir"] + TD_TOLERANCE_M,
            c["cobertura_perfil"] >= 0.9,
            c["cobertura_perfil"] > 0,
        ],
        ["abaixo da profundidade final (unidade suspeita)", "com perfil", "perfil parcial"],
        default="sem perfil",
    )
    return c.drop(columns=["md_min", "md_max"])


def run() -> dict:
    names = load_yaml("nomes_unidades.yaml")
    wells = pd.read_parquet(INTERIM / "pocos.parquet")
    samples = pd.read_parquet(INTERIM / "amostras.parquet", columns=["poco", "md"])
    tops = prepare_tops(pd.read_parquet(INTERIM / "topos.parquet"), names)
    logged = wells[["poco", "md_min", "md_max"]]

    t = pd.concat(
        [compare_tops(tops, s, logged) for s in ("npd_2020", "perfil_force")], ignore_index=True
    )
    w = wells_check(wells)
    c = cores_check(
        pd.read_parquet(INTERIM / "testemunhos.parquet"),
        samples,
        wells,
        pd.read_parquet(INTERIM / "litologia.parquet"),
    )

    t.to_csv(PROCESSED / "conciliacao_topos.csv", index=False, float_format="%.2f")
    w.to_csv(PROCESSED / "conciliacao_pocos.csv", index=False, float_format="%.2f")
    c.to_csv(PROCESSED / "conciliacao_testemunhos.csv", index=False, float_format="%.2f")

    div = t[t["situacao"] == "divergente"]
    summary = {
        "topos": t.groupby(["comparacao", "situacao"])
        .size()
        .unstack(fill_value=0)
        .to_dict("index"),
        "topos_mudaram_de_nivel": int(t["mudou_nivel"].sum()),
        "divergencia_abs_m": div.groupby("comparacao")["delta_m"]
        .apply(lambda d: d.abs().describe().round(1).to_dict())
        .unstack()
        .to_dict("index"),
        "pocos_com_deslocamento_uniforme": t[t["situacao"] == "deslocamento uniforme do poço"]
        .groupby(["comparacao", "poco"])["delta_m"]
        .median()
        .round(1)
        .reset_index()
        .to_dict("records"),
        "pocos_com_achado": int((w["achados"] != "").sum()),
        "achados_pocos": w.loc[w["achados"] != "", ["poco", "achados"]].to_dict("records"),
        "testemunhos": c["situacao"].value_counts().to_dict(),
    }
    (PROCESSED / "conciliacao.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1, default=float))
