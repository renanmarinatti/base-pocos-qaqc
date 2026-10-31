"""Figuras das etapas, no visual da ADR 007 do portfólio (papel, grafite, ameixa).

Uso: uv run python -m pocos.figures
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pocos.inventory import BRAND, FIGURES, INK, INK_2, LINE, PAPER, PROCESSED
from pocos.standardize import INTERIM, load_yaml

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


def rule_matrix(problems: pd.DataFrame, notes: pd.DataFrame, rules: dict, path) -> None:
    """Poço × regra, ordenado pela nota: onde cada regra disparou e com que gravidade."""
    level = {"baixa": 1, "media": 2, "alta": 3}
    ids = list(rules)
    order = notes.sort_values(["nota", "poco"])["poco"].tolist()
    grid = (
        problems.assign(v=problems["gravidade"].map(level))
        .pivot_table(index="poco", columns="regra", values="v", aggfunc="max")
        .reindex(index=order, columns=ids)
        .fillna(0)
    )
    cmap = plt.matplotlib.colors.ListedColormap(["#EDE9E0", "#D9C8DB", "#A27FA6", BRAND])
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(11, 7.5), dpi=150, gridspec_kw={"width_ratios": [4, 1.3]}
    )
    fig.patch.set_facecolor(PAPER)
    ax.imshow(grid.to_numpy(), aspect="auto", cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
    hits = problems.groupby("regra")["poco"].nunique().reindex(ids).fillna(0).astype(int)
    labels = [f"{r}\n{rules[r]['gravidade']}\n{hits[r]} poços" for r in ids]
    ax.set_xticks(range(len(ids)), labels, fontsize=6.5, color=INK)
    ax.set_yticks([])
    ax.set_ylabel(f"{len(order)} poços, da pior para a melhor nota", color=INK_2, fontsize=8)
    for spine in ax.spines.values():
        spine.set_color(LINE)
    ax.set_title("Onde cada regra de qualidade disparou", loc="left", fontsize=10, color=INK)
    handles = [
        plt.matplotlib.patches.Patch(color=c, label=t)
        for c, t in ((BRAND, "alta"), ("#A27FA6", "média"), ("#D9C8DB", "baixa"))
    ]
    ax.legend(
        handles=handles,
        frameon=False,
        fontsize=7.5,
        labelcolor=INK,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.1),
    )

    style(bx)
    scores = notes.set_index("poco").reindex(order)["nota"]
    bx.barh(range(len(scores)), scores.to_numpy(), color=BRAND, height=0.8)
    bx.set_ylim(len(scores) - 0.5, -0.5)
    bx.set_yticks([])
    bx.set_xlim(0, 100)
    bx.set_title("Nota (0–100)", loc="left", fontsize=10, color=INK)
    fig.text(
        0.01,
        0.01,
        "Nota: 100 menos 15 por regra alta, 5 por média e 1 por baixa, "
        "uma vez por regra. " + SOURCE_NOTE,
        fontsize=6.5,
        color=INK_2,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def tops_reconciliation(tops: pd.DataFrame, path) -> None:
    """Como os topos se comparam com a Sodir, e quanto mudaram os que foram reinterpretados."""
    order = [
        "igual",
        "deslocamento uniforme do poço",
        "divergente",
        "fora do trecho perfilado",
        "só na Sodir",
    ]
    comps = [
        ("npd_2020 × sodir", "cópia NPD 2020", "#A27FA6"),
        ("perfil_force × sodir", "rótulos do perfil FORCE", BRAND),
    ]
    counts = tops.groupby(["comparacao", "situacao"]).size()

    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(12, 6.5), dpi=150, gridspec_kw={"width_ratios": [1, 1.1]}
    )
    fig.patch.set_facecolor(PAPER)
    style(ax)
    y = np.arange(len(order))
    for i, (comp, label, color) in enumerate(comps):
        vals = [counts.get((comp, o), 0) for o in order]
        bars = ax.barh(y + (i - 0.5) * 0.38, vals, height=0.36, color=color, label=label)
        for bar, v in zip(bars, vals, strict=True):
            ax.text(
                bar.get_width() + 20,
                bar.get_y() + bar.get_height() / 2,
                f"{v:,}".replace(",", "."),
                va="center",
                fontsize=7,
                color=INK_2,
            )
    ax.set_yticks(y, order, fontsize=8, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("topos", color=INK_2, fontsize=8)
    ax.set_title("Topos comparados com a Sodir de hoje", loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")

    style(bx)
    d = tops[(tops["comparacao"] == "npd_2020 × sodir") & (tops["situacao"] == "divergente")]
    d = d.assign(delta=-d["delta_m"]).sort_values("delta")  # Sodir − 2020
    labels = [f"{p} · {u.title()}" for p, u in zip(d["poco"], d["base"], strict=True)]
    yy = np.arange(len(d))
    bx.hlines(yy, 0, d["delta"], color=LINE, linewidth=1)
    bx.scatter(d["delta"], yy, s=26, color=BRAND, zorder=3)
    bx.axvline(0, color=INK_2, linewidth=0.8)
    bx.set_yticks(yy, labels, fontsize=6.5, color=INK)
    bx.set_xlabel(
        "Sodir hoje − cópia de 2020 (m); positivo = topo mais fundo hoje", color=INK_2, fontsize=8
    )
    bx.set_title(f"{len(d)} topos reinterpretados desde 2020", loc="left", fontsize=10, color=INK)
    fig.text(
        0.01,
        0.01,
        "Igual: até 1 m. Deslocamento uniforme: vários topos do mesmo poço "
        "movidos pelo mesmo valor (34/10-16 R, 3 m). " + SOURCE_NOTE,
        fontsize=6.5,
        color=INK_2,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)


def run() -> None:
    wells = pd.read_parquet(INTERIM / "pocos.parquet")
    samples = pd.read_parquet(INTERIM / "amostras.parquet", columns=["poco", "md", "tvdss"])
    FIGURES.mkdir(parents=True, exist_ok=True)
    well_map(wells, FIGURES / "e2_mapa_pocos.png")
    md_vs_tvd(samples, wells, FIGURES / "e2_md_tvd.png")
    problems_path = PROCESSED / "problemas.csv"
    if problems_path.exists():
        rule_matrix(
            pd.read_csv(problems_path),
            pd.read_csv(PROCESSED / "notas.csv"),
            load_yaml("regras.yaml")["regras"],
            FIGURES / "e3_matriz_regras.png",
        )
    tops_path = PROCESSED / "conciliacao_topos.csv"
    if tops_path.exists():
        tops_reconciliation(pd.read_csv(tops_path), FIGURES / "e4_topos.png")


if __name__ == "__main__":
    run()
