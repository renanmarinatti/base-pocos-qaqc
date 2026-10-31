"""Regras de qualidade (E3): aplica o catálogo de config/regras.yaml à base padronizada.

Cada regra é uma função que recebe a base (`Base`) e os parâmetros do catálogo e devolve os
problemas encontrados, um por linha: poço, curva, trecho de profundidade, quantas amostras
e um detalhe legível. O motor junta tudo no registro de problemas e calcula a nota de cada
poço. A regra **marca**; não corrige nem apaga dado. Corrigir é decisão, e decisão vai
para docs/decisoes.md.

Saídas em data/processed/: problemas.csv (o registro) e notas.csv (a nota por poço).

Uso: uv run python -m pocos.quality
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pocos.inventory import PROCESSED
from pocos.standardize import INTERIM, load_yaml

COLUMNS = ["poco", "curva", "topo_md", "base_md", "amostras", "detalhe"]


@dataclass
class Base:
    samples: pd.DataFrame
    wells: pd.DataFrame
    lithology: pd.DataFrame
    tops: pd.DataFrame
    declared: pd.DataFrame
    ranges: dict[str, tuple[float, float]]

    @classmethod
    def load(cls, folder: Path = INTERIM) -> Base:
        catalog = load_yaml("mnemonicos.yaml")["curvas"]
        return cls(
            samples=pd.read_parquet(folder / "amostras.parquet"),
            wells=pd.read_parquet(folder / "pocos.parquet"),
            lithology=pd.read_parquet(folder / "litologia.parquet"),
            tops=pd.read_parquet(folder / "topos.parquet"),
            declared=pd.read_parquet(folder / "curvas_declaradas.parquet"),
            ranges={k: tuple(v["faixa"]) for k, v in catalog.items() if "faixa" in v},
        )


def issues(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=COLUMNS)


def by_well(samples: pd.DataFrame) -> pd.DataFrame:
    return samples.sort_values(["poco", "md"], kind="stable")


# Curvas que a padronização renomeou para colunas da base.
RENAMED = {"DEPTH_MD": "md", "Z_LOC": "tvdss"}


def r01_declared_but_empty(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples
    declared = base.declared.assign(coluna=base.declared["curva"].replace(RENAMED))
    curves = [c for c in declared["coluna"].unique() if c in s.columns]
    valid = s.groupby("poco")[curves].count().div(s.groupby("poco").size(), axis=0)
    rows = []
    for well, curve, column in declared[["poco", "curva", "coluna"]].itertuples(index=False):
        frac = valid.at[well, column] if column in valid.columns else 0.0
        if frac < p["fracao_minima_valida"]:
            rows.append(
                {
                    "poco": well,
                    "curva": curve,
                    "amostras": 0,
                    "detalhe": f"declarada no cabeçalho; {frac:.2%} das amostras com dado",
                }
            )
    return issues(rows)


def r02_out_of_range(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples
    rows = []
    for curve, (lo, hi) in base.ranges.items():
        if curve not in s.columns:
            continue
        v = s[curve].where(~s[curve].isin(p["ignorar_codigos"]))
        bad = v.notna() & ((v < lo) | (v > hi))
        if not bad.any():
            continue
        g = s.loc[bad].groupby("poco")
        stats = pd.DataFrame(
            {
                "n": g.size(),
                "topo": g["md"].min(),
                "base": g["md"].max(),
                "vmin": g[curve].min(),
                "vmax": g[curve].max(),
            }
        )
        stats["valid"] = s.loc[v.notna()].groupby("poco").size().reindex(stats.index)
        for well, r in stats.iterrows():
            frac = r["n"] / r["valid"]
            if frac >= p["fracao_minima_para_disparar"]:
                rows.append(
                    {
                        "poco": well,
                        "curva": curve,
                        "topo_md": r["topo"],
                        "base_md": r["base"],
                        "amostras": int(r["n"]),
                        "detalhe": f"{frac:.1%} fora de [{lo}, {hi}]; "
                        f"mín. {r['vmin']:.3g}, máx. {r['vmax']:.3g}",
                    }
                )
    return issues(rows)


def r03_depth_order(base: Base, p: dict) -> pd.DataFrame:
    rows = []
    for well, g in base.samples.groupby("poco", sort=False):
        d = g["md"].diff()
        bad = d.le(0)
        if bad.any():
            rows.append(
                {
                    "poco": well,
                    "curva": "MD",
                    "topo_md": g.loc[bad, "md"].min(),
                    "base_md": g.loc[bad, "md"].max(),
                    "amostras": int(bad.sum()),
                    "detalhe": "MD repetida ou decrescente",
                }
            )
    return issues(rows)


def r04_gaps(base: Base, p: dict) -> pd.DataFrame:
    s = by_well(base.samples)[["poco", "md"]]
    prev = s.groupby("poco")["md"].shift()
    gap = (s["md"] - prev) > p["lacuna_minima_m"]
    out = pd.DataFrame(
        {"poco": s.loc[gap, "poco"], "topo_md": prev[gap], "base_md": s.loc[gap, "md"]}
    )
    out["curva"] = "MD"
    out["amostras"] = 0
    out["detalhe"] = [
        f"{b - t:.1f} m sem amostra" for t, b in zip(out["topo_md"], out["base_md"], strict=True)
    ]
    return out[COLUMNS].reset_index(drop=True)


def r05_geometry(base: Base, p: dict) -> pd.DataFrame:
    s = by_well(base.samples.dropna(subset=["tvdss"]))[["poco", "md", "tvdss"]]
    excess = s["md"] - s["tvdss"]
    drop = excess.groupby(s["poco"]).diff() < -p["tolerancia_m"]
    rows = []
    for well, g in s.loc[drop].groupby("poco"):
        rows.append(
            {
                "poco": well,
                "curva": "Z_LOC",
                "topo_md": g["md"].min(),
                "base_md": g["md"].max(),
                "amostras": len(g),
                "detalhe": "MD − TVD diminui ao descer o poço",
            }
        )
    return issues(rows)


def r06_lithology_overlap(base: Base, p: dict) -> pd.DataFrame:
    lith = base.lithology.sort_values(["poco", "topo_md"])
    prev_base = lith.groupby("poco")["base_md"].shift()
    over = lith["topo_md"] < prev_base - 1e-6
    rows = [
        {
            "poco": r.poco,
            "curva": "LITOLOGIA",
            "topo_md": r.topo_md,
            "base_md": pb,
            "amostras": int(r.amostras),
            "detalhe": "intervalo começa antes do fim do anterior",
        }
        for r, pb in zip(lith.loc[over].itertuples(), prev_base[over], strict=True)
    ]
    return issues(rows)


def r07_basic_completeness(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples
    curves = [c for c in p["curvas"] if c in s.columns]
    valid = s.groupby("poco")[curves].count().div(s.groupby("poco").size(), axis=0)
    long = valid.stack().rename("frac").reset_index()
    long.columns = ["poco", "curva", "frac"]
    low = long[long["frac"] < p["fracao_minima_valida"]]
    return issues(
        [
            {
                "poco": r.poco,
                "curva": r.curva,
                "amostras": 0,
                "detalhe": f"{r.frac:.0%} do trecho perfilado com dado",
            }
            for r in low.itertuples()
        ]
    )


def r08_washout(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples
    has_rhob = s["RHOB"].notna()
    washout = s["DCAL"].where(s["DCAL"].notna(), s["CALI"] - s["BS"]) > p["arrombamento_in"]
    bad = has_rhob & (washout.fillna(False) | (s["DRHO"].abs() > p["drho_max"]).fillna(False))
    stats = pd.DataFrame(
        {
            "n": bad.groupby(s["poco"]).sum(),
            "valid": has_rhob.groupby(s["poco"]).sum(),
            "topo": s.loc[bad].groupby("poco")["md"].min(),
            "base": s.loc[bad].groupby("poco")["md"].max(),
        }
    )
    stats = stats[stats["valid"] > 0]
    stats["frac"] = stats["n"] / stats["valid"]
    hit = stats[stats["frac"] >= p["fracao_minima_para_disparar"]]
    return issues(
        [
            {
                "poco": w,
                "curva": "RHOB",
                "topo_md": r.topo,
                "base_md": r.base,
                "amostras": int(r.n),
                "detalhe": f"{r.frac:.0%} do RHOB em trecho arrombado ou com DRHO alto",
            }
            for w, r in hit.iterrows()
        ]
    )


def r09_low_confidence(base: Base, p: dict) -> pd.DataFrame:
    c = base.samples[["poco", "CONFIANCA"]].dropna()
    frac = c["CONFIANCA"].eq(3).groupby(c["poco"]).mean()
    hit = frac[frac > p["fracao_maxima"]]
    return issues(
        [
            {
                "poco": w,
                "curva": "CONFIANCA",
                "amostras": 0,
                "detalhe": f"{f:.0%} da litologia com confiança 3 (baixa)",
            }
            for w, f in hit.items()
        ]
    )


def r10_duplicate_well(base: Base, p: dict) -> pd.DataFrame:
    w = base.wells
    dup = w[w.duplicated("poco", keep=False)]
    return issues(
        [
            {
                "poco": well,
                "curva": "",
                "amostras": 0,
                "detalhe": "arquivos de perfil: " + ", ".join(g["poco_force"]),
            }
            for well, g in dup.groupby("poco")
        ]
    )


def r11_official_tops(base: Base, p: dict) -> pd.DataFrame:
    t = base.tops[base.tops["fonte"] == "sodir"].sort_values(["poco", "nivel", "topo_md"])
    tol = p["tolerancia_m"]
    rows = []
    inverted = t[t["topo_md"] > t["base_md"] + tol]
    rows += [
        {
            "poco": r.poco,
            "curva": r.unidade,
            "topo_md": r.topo_md,
            "base_md": r.base_md,
            "amostras": 0,
            "detalhe": f"{r.nivel}: topo abaixo da base",
        }
        for r in inverted.itertuples()
    ]
    prev_base = t.groupby(["poco", "nivel"])["base_md"].shift()
    prev_name = t.groupby(["poco", "nivel"])["unidade"].shift()
    over = t["topo_md"] < prev_base - tol
    rows += [
        {
            "poco": r.poco,
            "curva": r.unidade,
            "topo_md": r.topo_md,
            "base_md": pb,
            "amostras": 0,
            "detalhe": f"{r.nivel}: começa {pb - r.topo_md:.1f} m antes do fim de {pn}",
        }
        for r, pb, pn in zip(
            t.loc[over].itertuples(), prev_base[over], prev_name[over], strict=True
        )
    ]
    return issues(rows)


def r12_alternative_null(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples
    skip = {"md", "tvdss", "X_LOC", "Y_LOC"}
    curves = [c for c in s.columns if s[c].dtype.kind == "f" and c not in skip]
    rows = []
    for code in p["codigos"]:
        hit = s[curves] == code
        for curve in hit.columns[hit.any()]:
            g = s.loc[hit[curve]].groupby("poco")["md"]
            for well, md in g:
                rows.append(
                    {
                        "poco": well,
                        "curva": curve,
                        "topo_md": md.min(),
                        "base_md": md.max(),
                        "amostras": len(md),
                        "detalhe": f"valor {code} é código de nulo, não medida",
                    }
                )
    return issues(rows)


def r13_undeclared_unit(base: Base, p: dict) -> pd.DataFrame:
    d = base.declared
    blank = d["unidade"].str.strip().isin(["", "_"]) & ~d["curva"].isin(p["ignorar"])
    return issues(
        [
            {"poco": r.poco, "curva": r.curva, "amostras": 0, "detalhe": "cabeçalho sem unidade"}
            for r in d[blank].itertuples()
        ]
    )


def r14_barite_pef(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples[["poco", "md", "PEF"]].dropna()
    high = s["PEF"] > p["pef_max"]
    g = s.groupby("poco")
    stats = pd.DataFrame(
        {
            "frac": high.groupby(s["poco"]).mean(),
            "n": high.groupby(s["poco"]).sum(),
            "topo": s.loc[high].groupby("poco")["md"].min(),
            "base": s.loc[high].groupby("poco")["md"].max(),
            "pmax": g["PEF"].max(),
        }
    )
    hit = stats[stats["frac"] >= p["fracao_minima_para_disparar"]]
    return issues(
        [
            {
                "poco": w,
                "curva": "PEF",
                "topo_md": r.topo,
                "base_md": r.base,
                "amostras": int(r.n),
                "detalhe": f"{r.frac:.1%} das leituras acima de {p['pef_max']} "
                f"(máx. {r.pmax:.0f}): baritina da lama",
            }
            for w, r in hit.iterrows()
        ]
    )


def r15_missing_trajectory(base: Base, p: dict) -> pd.DataFrame:
    s = base.samples[["poco", "md", "tvdss"]]
    missing = s["tvdss"].isna()
    frac = missing.groupby(s["poco"]).mean()
    rows = []
    for well, f in frac[frac >= p["fracao_minima_para_disparar"]].items():
        md = s.loc[missing & (s["poco"] == well), "md"]
        rows.append(
            {
                "poco": well,
                "curva": "Z_LOC",
                "topo_md": md.min(),
                "base_md": md.max(),
                "amostras": len(md),
                "detalhe": f"{f:.0%} das amostras sem X, Y e Z",
            }
        )
    return issues(rows)


RULES: dict[str, Callable[[Base, dict], pd.DataFrame]] = {
    "R01": r01_declared_but_empty,
    "R02": r02_out_of_range,
    "R03": r03_depth_order,
    "R04": r04_gaps,
    "R05": r05_geometry,
    "R06": r06_lithology_overlap,
    "R07": r07_basic_completeness,
    "R08": r08_washout,
    "R09": r09_low_confidence,
    "R10": r10_duplicate_well,
    "R11": r11_official_tops,
    "R12": r12_alternative_null,
    "R13": r13_undeclared_unit,
    "R14": r14_barite_pef,
    "R15": r15_missing_trajectory,
}


def apply(base: Base, catalog: dict) -> pd.DataFrame:
    frames = []
    for rule_id, spec in catalog["regras"].items():
        found = RULES[rule_id](base, spec.get("parametros") or {})
        found.insert(0, "regra", rule_id)
        found.insert(1, "nome", spec["nome"])
        found.insert(2, "gravidade", spec["gravidade"])
        frames.append(found)
    return pd.concat([f for f in frames if not f.empty], ignore_index=True)


def scores(problems: pd.DataFrame, wells: pd.Series, penalty: dict) -> pd.DataFrame:
    """100 menos a penalidade de cada regra disparada no poço (uma vez por regra)."""
    hit = problems[["poco", "regra", "gravidade"]].drop_duplicates(["poco", "regra"])
    hit = hit[hit["poco"].isin(set(wells))]
    lost = hit["gravidade"].map(penalty).groupby(hit["poco"]).sum()
    out = pd.DataFrame({"poco": sorted(wells)})
    out["nota"] = (100 - out["poco"].map(lost).fillna(0)).clip(lower=0).astype(int)
    for level in ("alta", "media", "baixa"):
        n = hit[hit["gravidade"] == level].groupby("poco").size()
        out[f"regras_{level}"] = out["poco"].map(n).fillna(0).astype(int)
    out["regras"] = out["poco"].map(
        hit.groupby("poco")["regra"].apply(lambda r: " ".join(sorted(r)))
    )
    return out.fillna({"regras": ""})


def run() -> dict:
    catalog = load_yaml("regras.yaml")
    base = Base.load()
    problems = apply(base, catalog)
    notes = scores(problems, base.wells["poco"], catalog["penalidade"])
    problems.to_csv(PROCESSED / "problemas.csv", index=False, float_format="%.2f")
    notes.to_csv(PROCESSED / "notas.csv", index=False)
    summary = {
        "problemas": len(problems),
        "por_regra": problems.groupby("regra").size().to_dict(),
        "pocos_por_regra": problems.groupby("regra")["poco"].nunique().to_dict(),
        "por_gravidade": problems.groupby("gravidade").size().to_dict(),
        "nota": notes["nota"].describe().round(1).to_dict(),
        "pocos_sem_problema": int((notes["regras"] == "").sum()),
    }
    (PROCESSED / "qualidade.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1, default=float))
