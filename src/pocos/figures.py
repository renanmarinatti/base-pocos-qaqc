"""Figuras das etapas, no visual da ADR 007 do portfólio (papel, grafite, ameixa).

Uso: uv run python -m pocos.figures
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pocos.inventory import BRAND, FIGURES, INK, INK_2, LINE, PAPER
from pocos.standardize import INTERIM

SOURCE_NOTE = (
    "Fontes: FORCE 2020 (Zenodo 10.5281/zenodo.4351156, CC BY 4.0) e Sodir FactPages (NLOD 2.0)."
)


def style(ax) -> None:
    ax.set_facecolor(PAPER)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(LINE)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.grid(color=LINE, linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)


def well_map(wells: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(6, 8), dpi=150)
    fig.patch.set_facecolor(PAPER)
    style(ax)
    deviated = wells["desvio_max_m"] > 50
    ax.scatter(
        wells.loc[~deviated, "lon_wgs84"],
        wells.loc[~deviated, "lat_wgs84"],
        s=22,
        color=BRAND,
        edgecolor=PAPER,
        linewidth=1,
        label="vertical",
        zorder=3,
    )
    ax.scatter(
        wells.loc[deviated, "lon_wgs84"],
        wells.loc[deviated, "lat_wgs84"],
        s=30,
        facecolor=PAPER,
        edgecolor=BRAND,
        linewidth=1.5,
        label="desviado (MD − TVD > 50 m)",
        zorder=3,
    )
    ax.set_aspect(1 / np.cos(np.radians(wells["lat_wgs84"].mean())))
    ax.set_xlabel("longitude (WGS84)", color=INK_2, fontsize=8)
    ax.set_ylabel("latitude (WGS84)", color=INK_2, fontsize=8)
    ax.set_title(
        f"{len(wells)} poços do FORCE 2020, posição oficial da Sodir",
        loc="left",
        fontsize=10,
        color=INK,
    )
    ax.legend(
        frameon=False,
        fontsize=8,
        labelcolor=INK,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.07),
        ncol=2,
    )
    fig.text(
        0.01,
        0.01,
        "Coordenada da Sodir em ED50, convertida para WGS84.\n" + SOURCE_NOTE,
        fontsize=6.5,
        color=INK_2,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def md_vs_tvd(samples: pd.DataFrame, wells: pd.DataFrame, path) -> None:
    """MD contra TVDSS: o vertical cai na diagonal; o desviado se afasta dela."""
    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=150)
    fig.patch.set_facecolor(PAPER)
    style(ax)
    deviated = set(wells.loc[wells["desvio_max_m"] > 50, "poco"])
    s = samples[["poco", "md", "tvdss"]].dropna().iloc[::20]
    for well, g in s.groupby("poco"):
        dev = well in deviated
        ax.plot(
            g["md"],
            g["tvdss"],
            color=BRAND if dev else LINE,
            linewidth=1.2 if dev else 0.8,
            zorder=3 if dev else 2,
        )
    top = s[["md", "tvdss"]].max().max()
    ax.plot([0, top], [0, top], color=INK_2, linewidth=0.8, linestyle="--")
    ax.invert_yaxis()
    ax.set_xlabel("MD — profundidade medida ao longo do poço (m)", color=INK_2, fontsize=8)
    ax.set_ylabel("TVDSS — profundidade vertical abaixo do mar (m)", color=INK_2, fontsize=8)
    ax.set_title(
        f"MD × TVDSS: {len(deviated)} dos {len(wells)} poços se afastam da vertical",
        loc="left",
        fontsize=10,
        color=INK,
    )
    ax.text(
        0.98,
        0.96,
        "roxo: desviado (MD − TVD > 50 m)\ncinza: vertical\ntracejado: MD = TVD",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7.5,
        color=INK_2,
    )
    fig.text(0.01, 0.01, SOURCE_NOTE, fontsize=6.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def run() -> None:
    wells = pd.read_parquet(INTERIM / "pocos.parquet")
    samples = pd.read_parquet(INTERIM / "amostras.parquet", columns=["poco", "md", "tvdss"])
    FIGURES.mkdir(parents=True, exist_ok=True)
    well_map(wells, FIGURES / "e2_mapa_pocos.png")
    md_vs_tvd(samples, wells, FIGURES / "e2_md_tvd.png")


if __name__ == "__main__":
    run()
