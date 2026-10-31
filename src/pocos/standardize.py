"""Padronização (E2): leva as duas fontes para os mesmos nomes, unidades e referências.

Entra o bruto de data/raw/; sai Parquet em data/interim/, uma tabela por entidade:

- pocos: um registro por poço do FORCE, com o par na Sodir, a mesa rotativa, a posição nas
  duas fontes (UTM 31N ED50 e WGS84) e o desvio (MD − TVD);
- amostras: uma linha por profundidade, curvas com nome canônico, nulo como NaN, MD e
  TVDSS;
- litologia: a litologia interpretada como intervalos topo–base, como numa base de
  descrição de testemunho;
- topos: os topos de grupo e formação nas três versões (perfis do FORCE, cópia NPD 2020,
  Sodir de hoje), todos em MD a partir da mesa rotativa;
- testemunhos: os intervalos testemunhados da Sodir, em metros;
- curvas_declaradas: as curvas que o cabeçalho de cada LAS declara (a E3 confere se têm dado).

Toda tabela leva `fonte` e `arquivo` (linhagem até o manifesto). Nada é corrigido em
silêncio: cada troca de nome, conversão de unidade e nulo substituído entra em
data/processed/padronizacao.json.

Uso: uv run python -m pocos.standardize
"""

import io
import json
import zipfile
from pathlib import Path

import lasio
import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer

from pocos.collect import RAW, read_manifest
from pocos.inventory import PROCESSED, well_name_from_file

INTERIM = Path("data/interim")
LAS_ZIP = RAW / "force/LAS_files_Force_2020_all_wells.zip"
FT = 0.3048

# Sodir publica latitude e longitude em ED50; o FORCE, X e Y em UTM 31N ED50 (EPSG:23031).
ED50_TO_UTM31 = Transformer.from_crs("EPSG:4230", "EPSG:23031", always_xy=True)
ED50_TO_WGS84 = Transformer.from_crs("EPSG:4230", "EPSG:4326", always_xy=True)


def load_yaml(name: str) -> dict:
    return yaml.safe_load(Path("config", name).read_text(encoding="utf-8"))


def alias_map(catalog: dict) -> dict[str, str]:
    """Apelido (sem caixa) -> nome canônico. O próprio nome canônico também é apelido."""
    out = {}
    for name, spec in catalog["curvas"].items():
        for alias in [name, *spec.get("apelidos", [])]:
            out[alias.upper()] = name
    return out


def official_name(force_name: str, exceptions: dict) -> str:
    return exceptions.get(force_name, {}).get("sodir", force_name)


def sodir_table(stem: str) -> tuple[pd.DataFrame, str]:
    path = max((RAW / "sodir").glob(f"{stem}_*.csv"))
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    return df, path.relative_to(RAW).as_posix()


def read_las(zip_path: Path, aliases: dict, units: dict, log: dict) -> pd.DataFrame:
    frames = []
    with zipfile.ZipFile(zip_path) as z:
        for member in sorted(n for n in z.namelist() if n.lower().endswith(".las")):
            las = lasio.read(io.StringIO(z.read(member).decode("utf-8", errors="replace")))
            well = well_name_from_file(member)
            null = float(las.well["NULL"].value)
            # A profundidade é o índice do LAS (DEPT), que existe em toda amostra. A curva
            # DEPTH_MD repete o DEPT (diferença < 0,001 m) mas falta onde falta a trajetória.
            df = las.df().rename_axis("DEPT").reset_index()
            renames = {}
            for curve in las.curves[1:]:
                canonical = aliases.get(curve.mnemonic.upper())
                log["curvas_declaradas"].append(
                    {
                        "poco_force": well,
                        "curva": canonical or curve.mnemonic,
                        "unidade": curve.unit,
                    }
                )
                if canonical is None:
                    log["curvas_fora_do_catalogo"].append([well, curve.mnemonic])
                    continue
                if canonical != curve.mnemonic:
                    renames[curve.mnemonic] = canonical
                expected = units.get(canonical)
                got = curve.unit.strip()
                if expected and got not in ("", "_") and got != expected:
                    log["unidade_divergente"].append([well, canonical, got, expected])
            # lasio já troca o NULL declarado por NaN; conferimos o que sobrou com o código.
            leftover = int((df == null).sum().sum())
            log["nulo_remanescente"] += leftover
            df = df.replace(null, np.nan).rename(columns=renames)
            log["trocas_de_nome"].update(f"{a} -> {b}" for a, b in renames.items())
            log["nulos_declarados"] += int(df.isna().sum().sum())
            df.insert(0, "poco_force", well)
            df["arquivo"] = f"force/LAS_files_Force_2020_all_wells.zip:{Path(member).name}"
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns={"DEPT": "md", "Z_LOC": "tvdss"})
    out["tvdss"] = -out["tvdss"]  # positiva para baixo, como MD
    both = out["DEPTH_MD"].notna()
    log["dept_vs_depth_md_max_m"] = float(
        (out.loc[both, "md"] - out.loc[both, "DEPTH_MD"]).abs().max()
    )
    log["amostras_sem_trajetoria"] = int(out["tvdss"].isna().sum())
    out = out.drop(columns="DEPTH_MD")
    return out


def lithology_intervals(samples: pd.DataFrame, names: dict, step: float) -> pd.DataFrame:
    """Amostras consecutivas com o mesmo código viram um intervalo topo–base."""
    s = samples[["poco", "md", "LITOLOGIA", "CONFIANCA", "arquivo"]].dropna(subset=["LITOLOGIA"])
    s = s.sort_values(["poco", "md"])
    breaks = (
        (s["poco"] != s["poco"].shift())
        | (s["LITOLOGIA"] != s["LITOLOGIA"].shift())
        | (s["md"].diff() > step * 1.5)  # buraco no perfil interrompe o intervalo
    )
    s["intervalo"] = breaks.cumsum()
    # A base de um intervalo é o topo da amostra seguinte, quando ela é contígua; senão,
    # a última amostra mais um passo. Somar o passo nominal em toda base acumularia o erro
    # de arredondamento do MD (o passo real varia entre 0,1519 e 0,1521 m).
    nxt = s.groupby("poco")["md"].shift(-1)
    s["base"] = nxt.where((nxt - s["md"]) <= step * 1.5, s["md"] + step)
    out = s.groupby("intervalo").agg(
        poco=("poco", "first"),
        topo_md=("md", "min"),
        base_md=("base", "last"),
        codigo=("LITOLOGIA", "first"),
        confianca=("CONFIANCA", "median"),
        amostras=("md", "size"),
        arquivo=("arquivo", "first"),
    )
    out["codigo"] = out["codigo"].astype(int)
    out["litologia"] = out["codigo"].map(names).fillna("código desconhecido")
    return out.reset_index(drop=True)


def log_tops(exceptions: dict) -> pd.DataFrame:
    """Topos indicados nos perfis: o início de cada trecho contínuo de grupo e de formação.

    Uma unidade pode aparecer mais de uma vez no mesmo poço (falha, injeção de areia,
    repetição), então o topo é o começo de cada trecho, não a primeira amostra da unidade.
    """
    sources = {
        "force/train.zip": lambda p: pd.read_csv(zipfile.ZipFile(p).open("train.csv"), sep=";"),
        "force/leaderboard_test_features.csv": lambda p: pd.read_csv(p, sep=";"),
        "force/hidden_test.csv": lambda p: pd.read_csv(p, sep=";"),
    }
    frames = []
    for name, reader in sources.items():
        df = reader(RAW / name)[["WELL", "DEPTH_MD", "GROUP", "FORMATION"]]
        for level, col in (("GRUPO", "GROUP"), ("FORMACAO", "FORMATION")):
            d = df.dropna(subset=[col]).sort_values(["WELL", "DEPTH_MD"])
            starts = (d["WELL"] != d["WELL"].shift()) | (d[col] != d[col].shift())
            first = d.loc[starts, ["WELL", col, "DEPTH_MD"]]
            frames.append(
                pd.DataFrame(
                    {
                        "poco_force": first["WELL"].str.strip(),
                        "nivel": level,
                        "unidade": first[col],
                        "topo_md": first["DEPTH_MD"],
                        "fonte": "perfil_force",
                        "arquivo": name,
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    out["poco"] = out["poco_force"].map(lambda w: official_name(w, exceptions))
    return out


def npd2020_tops(exceptions: dict) -> pd.DataFrame:
    frames = []
    for level, name in (
        ("GRUPO", "force/NPD_Lithostratigraphy_groups_all_wells.xlsx"),
        ("FORMACAO", "force/NPD_Lithostratigraphy_member_formations_all_wells.xlsx"),
    ):
        df = pd.read_excel(RAW / name)
        frames.append(
            pd.DataFrame(
                {
                    "poco_force": df["Well identifier"].str.strip(),
                    "nivel": level,
                    "unidade": df["Surface"].str.replace(r"\s+Top$", "", regex=True),
                    "topo_md": df["MD"],
                    "tvdss_fonte": -df["Z"],
                    "fonte": "npd_2020",
                    "arquivo": name,
                }
            )
        )
    out = pd.concat(frames, ignore_index=True)
    out["poco"] = out["poco_force"].map(lambda w: official_name(w, exceptions))
    return out


def sodir_tops(wells: set[str]) -> pd.DataFrame:
    df, name = sodir_table("wellbore_formation_top")
    df = df[df["wlbName"].isin(wells)]
    level = {"GROUP": "GRUPO", "FORMATION": "FORMACAO", "MEMBER": "MEMBRO"}
    return pd.DataFrame(
        {
            "poco": df["wlbName"],
            "nivel": df["lsuLevel"].str.upper().map(level),
            "unidade": df["lsuName"],
            "topo_md": df["lsuTopDepth"],
            "base_md": df["lsuBottomDepth"],
            "fonte": "sodir",
            "arquivo": name,
        }
    )


def cores(wells: set[str], log: dict) -> pd.DataFrame:
    df, name = sodir_table("wellbore_core")
    df = df[df["wlbName"].isin(wells)].copy()
    unit = df["wlbCoreIntervalUom"].str.strip("[] ").str.lower()
    factor = np.where(unit == "ft", FT, 1.0)
    log["testemunhos_convertidos_de_pes"] = int((unit == "ft").sum())
    return pd.DataFrame(
        {
            "poco": df["wlbName"],
            "numero": df["wlbCoreNumber"],
            "topo_md": (df["wlbCoreIntervalTop"] * factor).round(2),
            "base_md": (df["wlbCoreIntervalBottom"] * factor).round(2),
            "unidade_original": unit,
            "fonte": "sodir",
            "arquivo": name,
        }
    )


def wells_table(samples: pd.DataFrame, exceptions: dict) -> pd.DataFrame:
    exp, exp_file = sodir_table("wellbore_exploration_all")
    dev, dev_file = sodir_table("wellbore_development_all")
    sodir = pd.concat(
        [
            exp.assign(tipo="exploração", arquivo_sodir=exp_file),
            dev.assign(tipo="desenvolvimento", arquivo_sodir=dev_file),
        ],
        ignore_index=True,
    )
    cols = [
        "wlbWellboreName",
        "tipo",
        "wlbKellyBushElevation",
        "wlbTotalDepth",
        "wlbFinalVerticalDepth",
        "wlbWaterDepth",
        "wlbNsDecDeg",
        "wlbEwDecDeg",
        "wlbUtmZone",
        "wlbMaxInclation",
        "arquivo_sodir",
    ]
    sodir = sodir[cols].rename(
        columns={
            "wlbWellboreName": "poco",
            "wlbKellyBushElevation": "mesa_rotativa_m",
            "wlbTotalDepth": "prof_final_md_sodir",
            "wlbFinalVerticalDepth": "prof_final_tvd_sodir",
            "wlbWaterDepth": "lamina_dagua_m",
            "wlbUtmZone": "fuso_utm_sodir",
            "wlbMaxInclation": "inclinacao_max_sodir",
        }
    )

    g = samples.groupby("poco_force")
    head = samples.dropna(subset=["X_LOC", "Y_LOC"]).sort_values("md").groupby("poco_force").first()
    force = pd.DataFrame(
        {
            "md_min": g["md"].min(),
            "md_inicio_trajetoria": head["md"],
            "md_max": g["md"].max(),
            "x_force": head["X_LOC"],
            "y_force": head["Y_LOC"],
            "md_menos_tvdss_topo": head["md"] - head["tvdss"],
            "desvio_max_m": (samples["md"] - samples["tvdss"]).groupby(samples["poco_force"]).max()
            - (head["md"] - head["tvdss"]),
            "arquivo": g["arquivo"].first(),
        }
    ).reset_index()
    force["poco"] = force["poco_force"].map(lambda w: official_name(w, exceptions))
    out = force.merge(sodir, on="poco", how="left", indicator="par_na_sodir")
    out["par_na_sodir"] = out["par_na_sodir"].eq("both")

    lon, lat = out["wlbEwDecDeg"].to_numpy(), out["wlbNsDecDeg"].to_numpy()
    out["x_sodir"], out["y_sodir"] = ED50_TO_UTM31.transform(lon, lat)
    out["lon_wgs84"], out["lat_wgs84"] = ED50_TO_WGS84.transform(lon, lat)
    out["dist_force_sodir_m"] = np.hypot(
        out["x_force"] - out["x_sodir"], out["y_force"] - out["y_sodir"]
    )
    return out.drop(columns=["wlbNsDecDeg", "wlbEwDecDeg"])


def run() -> dict:
    catalog = load_yaml("mnemonicos.yaml")
    names = {int(k): v for k, v in load_yaml("litologia.yaml")["litologia"].items()}
    exceptions = load_yaml("nomes_pocos.yaml")["excecoes"]
    units = {k: v["unidade"] for k, v in catalog["curvas"].items()}
    log = {
        "trocas_de_nome": set(),
        "curvas_fora_do_catalogo": [],
        "unidade_divergente": [],
        "nulos_declarados": 0,
        "nulo_remanescente": 0,
        "curvas_declaradas": [],
    }

    samples = read_las(LAS_ZIP, alias_map(catalog), units, log)
    samples.insert(1, "poco", samples["poco_force"].map(lambda w: official_name(w, exceptions)))
    step = float(samples.groupby("poco")["md"].diff().median())

    wells = wells_table(samples, exceptions)
    official = set(wells["poco"])
    lith = lithology_intervals(samples, names, step)
    tops = pd.concat(
        [log_tops(exceptions), npd2020_tops(exceptions), sodir_tops(official)], ignore_index=True
    )
    core = cores(official, log)
    declared = pd.DataFrame(log.pop("curvas_declaradas"))
    declared["poco"] = declared["poco_force"].map(lambda w: official_name(w, exceptions))

    INTERIM.mkdir(parents=True, exist_ok=True)
    for name, df in {
        "pocos": wells,
        "amostras": samples,
        "litologia": lith,
        "topos": tops,
        "testemunhos": core,
        "curvas_declaradas": declared,
    }.items():
        df.to_parquet(INTERIM / f"{name}.parquet", index=False)

    manifest = read_manifest()
    summary = {
        "linhagem_zip_sha256": manifest["force/LAS_files_Force_2020_all_wells.zip"]["sha256"],
        "amostras": len(samples),
        "pocos": len(wells),
        "pocos_com_par_na_sodir": int(wells["par_na_sodir"].sum()),
        "passo_md": round(step, 4),
        "trocas_de_nome": sorted(log["trocas_de_nome"]),
        "curvas_fora_do_catalogo": log["curvas_fora_do_catalogo"],
        "unidade_divergente": sorted({tuple(x[1:]) for x in log["unidade_divergente"]}),
        "unidade_divergente_pocos": len({x[0] for x in log["unidade_divergente"]}),
        "valores_nulos": log["nulos_declarados"],
        "nulo_remanescente": log["nulo_remanescente"],
        "intervalos_de_litologia": len(lith),
        "codigos_de_litologia_desconhecidos": int(
            (lith["litologia"] == "código desconhecido").sum()
        ),
        "topos_por_fonte": tops.groupby("fonte").size().to_dict(),
        "testemunhos": len(core),
        "testemunhos_convertidos_de_pes": log["testemunhos_convertidos_de_pes"],
        "dist_force_sodir_m": wells["dist_force_sodir_m"].describe().round(1).to_dict(),
        "dept_vs_depth_md_max_m": round(log["dept_vs_depth_md_max_m"], 5),
        "amostras_sem_trajetoria": log["amostras_sem_trajetoria"],
        "pocos_desviados_mais_de_50m": int((wells["desvio_max_m"] > 50).sum()),
        "md_menos_tvdss_no_topo_vs_mesa": float(
            (wells["md_menos_tvdss_topo"] - wells["mesa_rotativa_m"]).abs().median().round(2)
        ),
    }
    (PROCESSED / "padronizacao.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1, default=str))
