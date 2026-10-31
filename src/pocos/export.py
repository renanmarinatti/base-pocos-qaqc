"""Exportação (E5): o banco final em formatos que as ferramentas de interpretação carregam.

- LAS 2.0, um arquivo por poço, com nome oficial, mesa rotativa, curvas canônicas, as
  marcas de qualidade como curvas 0/1 e a proveniência no cabeçalho. Petrel, Techlog e
  similares importam LAS.
- Topos oficiais em tabela (poço, superfície, X, Y, Z, MD), o mesmo layout da planilha de
  topos que os organizadores do FORCE exportaram do Petrel em 2020. Z é a TVDSS do topo,
  interpolada na trajetória do perfil; fica vazia onde o perfil não tem trajetória.

Saídas: data/exports/las/*.las (fora do Git; se recriam com um comando) e
data/processed/topos_oficiais.csv.

Uso: uv run python -m pocos.export
"""

from datetime import date
from pathlib import Path

import duckdb
import lasio
import numpy as np
import pandas as pd

from pocos.database import CURVES, DB
from pocos.inventory import PROCESSED

EXPORTS = Path("data/exports/las")
PROVENANCE = (
    "Base de poços padronizada e conciliada (projeto base-pocos-qaqc). Perfis: FORCE 2020, "
    "Zenodo 10.5281/zenodo.4351156 (CC BY 4.0). Cadastro e topos: Sodir FactPages (NLOD 2.0). "
    "MUDWEIGHT removida (decisão D09); -999 tratado como nulo (D10). RHOB_ARROMB e PEF_BARIT "
    "marcam trechos de qualidade duvidosa sem alterar o valor (regras R08 e R14)."
)


def file_name(well: str) -> str:
    return well.replace("/", "_") + ".las"


def write_las(well: pd.Series, samples: pd.DataFrame, units: dict, path: Path) -> None:
    las = lasio.LASFile()
    las.well["WELL"].value = well["poco"]
    las.well["UWI"].value = well["poco"]
    las.well["COMP"].value = ""
    las.well["SRVC"].value = "FORCE 2020 / Sodir"
    las.well["DATE"].value = date.today().isoformat()
    las.well["NULL"].value = -999.25
    las.params.append(
        lasio.HeaderItem("EKB", "m", well["mesa_rotativa_m"], "Elevação da mesa rotativa (Sodir)")
    )
    las.params.append(
        lasio.HeaderItem("NOTA", "", int(well["nota_qualidade"]), "Nota de qualidade 0-100 (E3)")
    )
    las.other = PROVENANCE
    las.append_curve(
        "DEPT", samples["md"].to_numpy(), unit="m", descr="MD a partir da mesa rotativa"
    )
    las.append_curve(
        "TVDSS", samples["tvdss"].to_numpy(), unit="m", descr="Profundidade vertical abaixo do mar"
    )
    for curve in CURVES:
        values = samples[curve].to_numpy(dtype=float)
        if np.isnan(values).all():
            continue
        las.append_curve(curve, values, unit=units[curve])
    las.append_curve(
        "LITO",
        samples["litologia_codigo"].to_numpy(dtype=float),
        unit="",
        descr="Litologia interpretada (código FORCE)",
    )
    las.append_curve(
        "LITO_CONF",
        samples["confianca"].to_numpy(dtype=float),
        unit="",
        descr="Confiança da litologia: 1 alta, 3 baixa",
    )
    las.append_curve(
        "RHOB_ARROMB",
        samples["rhob_arrombado"].astype(float).to_numpy(),
        unit="",
        descr="1 = RHOB em trecho arrombado ou DRHO alto (R08)",
    )
    las.append_curve(
        "PEF_BARIT",
        samples["pef_baritina"].astype(float).to_numpy(),
        unit="",
        descr="1 = PEF afetado por baritina (R14)",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(path), version=2.0, wrap=False, fmt="%.4f")


def official_tops(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    tops = con.execute(
        "SELECT t.poco, t.unidade, t.topo_md, p.x_utm31_ed50 AS x, p.y_utm31_ed50 AS y "
        "FROM topo t JOIN poco p USING (poco) ORDER BY t.poco, t.topo_md"
    ).df()
    traj = con.execute(
        "SELECT poco, md, tvdss, x_utm31_ed50 AS x, y_utm31_ed50 AS y FROM amostra "
        "WHERE tvdss IS NOT NULL ORDER BY poco, md"
    ).df()
    out = []
    for well, t in tops.groupby("poco"):
        g = traj[traj["poco"] == well]
        t = t.copy()
        if len(g):
            inside = (t["topo_md"] >= g["md"].min()) & (t["topo_md"] <= g["md"].max())
            for col, src in (("z", "tvdss"), ("x", "x"), ("y", "y")):
                interp = np.interp(t["topo_md"], g["md"], g[src])
                t[col] = np.where(inside, interp, t[col] if col != "z" else np.nan)
            t["z"] = -t["z"]  # Z negativo abaixo do mar, como no Petrel
        else:
            t["z"] = np.nan
        out.append(t)
    t = pd.concat(out, ignore_index=True)
    return pd.DataFrame(
        {
            "Well identifier": t["poco"],
            "Surface": t["unidade"] + " Top",
            "X": t["x"].round(2),
            "Y": t["y"].round(2),
            "Z": t["z"].round(2),
            "MD": t["topo_md"],
        }
    )


def run() -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    units = dict(con.execute("SELECT curva, unidade FROM curva").fetchall())
    wells = con.execute("SELECT * FROM poco ORDER BY poco").df()
    for _, well in wells.iterrows():
        samples = con.execute(
            "SELECT * FROM amostra WHERE poco = ? ORDER BY md", [well["poco"]]
        ).df()
        write_las(well, samples, units, EXPORTS / file_name(well["poco"]))
    tops = official_tops(con)
    con.close()
    tops.to_csv(PROCESSED / "topos_oficiais.csv", index=False)
    return {"las": len(wells), "topos": len(tops), "topos_com_z": int(tops["Z"].notna().sum())}


if __name__ == "__main__":
    print(run())
