"""Inventário das fontes coletadas: o que cada uma traz e quais poços aparecem nas duas.

Lê só o cabeçalho dos LAS (sem as amostras) e as tabelas de poço da Sodir. É a primeira
olhada na base, antes de qualquer correção: quantos poços, que curvas, que intervalo de
profundidade, e se o nome do poço no FORCE tem par na Sodir.

Saídas: data/processed/inventario.json (pequeno, entra no Git) e a figura de presença de
curvas por poço em docs/figuras/.

Uso: uv run python -m pocos.inventory
"""

import io
import json
import re
import zipfile
from pathlib import Path

import lasio
import matplotlib.pyplot as plt
import pandas as pd

from pocos.collect import RAW, read_manifest

PROCESSED = Path("data/processed")
FIGURES = Path("docs/figuras")

# Visual da ADR 007 do portfólio: papel, grafite, ameixa.
PAPER, INK, INK_2, LINE, BRAND = "#F6F4EF", "#22252B", "#5A5D66", "#D6D1C5", "#5E3A63"


def well_name_from_file(name: str) -> str:
    """'16_1-6 A.las' -> '16/1-6 A': o arquivo troca a barra do nome oficial por '_'."""
    stem = Path(name).stem
    return re.sub(r"^(\d+)_(\d+)", r"\1/\2", stem).strip()


def las_headers(zip_path: Path) -> pd.DataFrame:
    rows = []
    with zipfile.ZipFile(zip_path) as z:
        for member in sorted(n for n in z.namelist() if n.lower().endswith(".las")):
            text = z.read(member).decode("utf-8", errors="replace")
            las = lasio.read(io.StringIO(text), ignore_data=True)
            rows.append(
                {
                    "arquivo": Path(member).name,
                    "poco_arquivo": well_name_from_file(member),
                    "poco_las": str(las.well["WELL"].value).strip(),
                    "uwi": str(las.well["UWI"].value).strip(),
                    "topo_m": float(las.well["STRT"].value),
                    "base_m": float(las.well["STOP"].value),
                    "passo_m": float(las.well["STEP"].value),
                    "nulo": float(las.well["NULL"].value),
                    "unidade_prof": las.curves[0].unit,
                    "curvas": [c.mnemonic for c in las.curves[1:]],
                    "bytes": z.getinfo(member).file_size,
                }
            )
    return pd.DataFrame(rows)


def sodir_wellbores() -> pd.DataFrame:
    tables = []
    for kind in ("exploration", "development"):
        path = max((RAW / "sodir").glob(f"wellbore_{kind}_all_*.csv"))
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        tables.append(df.assign(tipo=kind))
    return pd.concat(tables, ignore_index=True)


def presence_figure(las: pd.DataFrame, path: Path) -> None:
    """Matriz poço × curva: quais curvas cada poço traz. É a prévia da completude."""
    skip = {"DEPTH_MD", "X_LOC", "Y_LOC", "Z_LOC"}
    curves = las.explode("curvas")["curvas"]
    order = [c for c in curves.value_counts().index if c.upper() not in skip]
    wells = las.sort_values("poco_arquivo")
    matrix = [[c in set(cs) for c in order] for cs in wells["curvas"]]

    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=150)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.imshow(
        [[1 if v else 0 for v in row] for row in matrix],
        aspect="auto",
        cmap=plt.matplotlib.colors.ListedColormap(["#EDE9E0", BRAND]),
        interpolation="nearest",
    )
    short = {"FORCE_2020_LITHOFACIES_LITHOLOGY": "LITOLOGIA", "FORCE_2020_LITHOFACIES_CONFIDENCE": "CONFIANÇA"}
    ax.set_xticks(range(len(order)), [short.get(c, c) for c in order], rotation=90, fontsize=7, color=INK)
    ax.set_yticks([])
    ax.set_ylabel(f"{len(wells)} poços (ordem alfabética)", color=INK_2, fontsize=8)
    for spine in ax.spines.values():
        spine.set_color(LINE)
    share = pd.Series([sum(col) for col in zip(*matrix, strict=True)], index=order) / len(wells)
    ax.set_title(
        "Curvas declaradas no cabeçalho de cada LAS do FORCE 2020 (roxo = declarada)",
        loc="left", fontsize=10, color=INK,
    )
    fig.text(
        0.01, 0.01,
        f"GR em {share.get('GR', 0):.0%} dos poços; DTS em {share.get('DTS', 0):.0%}; "
        f"PEF em {share.get('PEF', 0):.0%}. Fonte: FORCE 2020, Zenodo 10.5281/zenodo.4351156 (CC BY 4.0).",
        fontsize=7.5, color=INK_2,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def run() -> dict:
    manifest = read_manifest()
    las = las_headers(RAW / "force/LAS_files_Force_2020_all_wells.zip")
    sodir = sodir_wellbores()
    official = set(sodir["wlbWellboreName"].str.strip())

    las["na_sodir"] = las["poco_arquivo"].isin(official)
    las["uwi_bate_arquivo"] = las["uwi"] == las["poco_arquivo"]
    curves = las.explode("curvas")["curvas"].value_counts()

    summary = {
        "fontes": [
            {"arquivo": r["arquivo"], "bytes": int(r["bytes"]), "licenca": r["licenca"]}
            for r in manifest.values()
        ],
        "force": {
            "arquivos_las": len(las),
            "megabytes": round(las["bytes"].sum() / 1e6, 1),
            "unidade_prof": sorted(las["unidade_prof"].unique().tolist()),
            "valores_nulo": sorted(las["nulo"].unique().tolist()),
            "passos_m": sorted(las["passo_m"].round(4).unique().tolist()),
            "curvas_distintas": len(curves),
            "curvas_por_poco": curves.to_dict(),
            "com_ramal": int(las["poco_arquivo"].str.contains(r"\s").sum()),
            "uwi_diferente_do_arquivo": las.loc[~las["uwi_bate_arquivo"], ["arquivo", "uwi"]]
            .to_dict("records"),
        },
        "sodir": {
            "pocos": len(sodir),
            "por_tipo": sodir["tipo"].value_counts().to_dict(),
        },
        "cruzamento": {
            "force_com_par_na_sodir": int(las["na_sodir"].sum()),
            "force_sem_par": las.loc[~las["na_sodir"], "poco_arquivo"].tolist(),
        },
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "inventario.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    las.drop(columns="curvas").to_csv(PROCESSED / "inventario_las.csv", index=False)
    presence_figure(las, FIGURES / "e1_presenca_curvas.png")
    return summary


if __name__ == "__main__":
    s = run()
    print(json.dumps({k: v for k, v in s.items() if k != "fontes"}, ensure_ascii=False, indent=1)[:3000])
