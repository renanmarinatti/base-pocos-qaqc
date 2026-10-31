"""Cada regra: um dado pequeno e limpo não dispara; o mesmo dado com o erro plantado dispara.

O teste do dado limpo é tão importante quanto o do erro: regra que dispara à toa vira
ruído, e o intérprete para de ler o relatório.
"""

import numpy as np
import pandas as pd
import pytest

from pocos.quality import RULES, Base, scores
from pocos.standardize import load_yaml

STEP = 0.152
N = 50


def clean_base() -> Base:
    md = 1000 + np.arange(N) * STEP
    samples = pd.DataFrame(
        {
            "poco": "A",
            "md": md,
            "tvdss": md - 25,
            "X_LOC": 437000.0,
            "Y_LOC": 6470000.0,
            "GR": 80.0,
            "RHOB": 2.4,
            "NPHI": 0.25,
            "DTC": 90.0,
            "RDEP": 2.0,
            "CALI": 8.6,
            "BS": 8.5,
            "DCAL": np.nan,
            "DRHO": 0.02,
            "PEF": 3.0,
            "CONFIANCA": 1.0,
            "LITOLOGIA": 65000.0,
        }
    )
    wells = pd.DataFrame({"poco": ["A"], "poco_force": ["A"]})
    lithology = pd.DataFrame(
        {
            "poco": "A",
            "topo_md": [1000.0, 1003.0],
            "base_md": [1003.0, md[-1] + STEP],
            "amostras": [20, 30],
        }
    )
    tops = pd.DataFrame(
        {
            "poco": "A",
            "nivel": "GRUPO",
            "unidade": ["G1", "G2"],
            "topo_md": [900.0, 1002.0],
            "base_md": [1002.0, 1100.0],
            "fonte": "sodir",
        }
    )
    declared = pd.DataFrame(
        {"poco": "A", "curva": ["GR", "RHOB", "DEPTH_MD"], "unidade": ["gAPI", "g/cm3", "m"]}
    )
    return Base(samples, wells, lithology, tops, declared, {"GR": (0, 500), "RHOB": (1.0, 3.2)})


PARAMS = {k: v.get("parametros") or {} for k, v in load_yaml("regras.yaml")["regras"].items()}


def plant(rule: str, b: Base) -> None:
    s = b.samples
    match rule:
        case "R01":
            b.declared.loc[len(b.declared)] = ["A", "DTS", "us/ft"]  # declarada, sem coluna
        case "R02":
            s.loc[5:10, "RHOB"] = 0.5
        case "R03":
            s.loc[20, "md"] = s.loc[19, "md"]
        case "R04":
            s.loc[30:, "md"] += 5
            s.loc[30:, "tvdss"] += 5
        case "R05":
            s.loc[25:, "tvdss"] += 3
        case "R06":
            b.lithology.loc[1, "topo_md"] = 1002.0
        case "R07":
            s.loc[:40, "NPHI"] = np.nan
        case "R08":
            s.loc[:10, "CALI"] = 12.0
        case "R09":
            s.loc[:10, "CONFIANCA"] = 3.0
        case "R10":
            b.wells.loc[1] = ["A", "A T2"]
        case "R11":
            b.tops.loc[1, "topo_md"] = 990.0
        case "R12":
            s.loc[3, "GR"] = -999.0
        case "R14":
            s.loc[:5, "PEF"] = 120.0
        case "R15":
            s.loc[:10, "tvdss"] = np.nan
        case "R13":
            b.declared.loc[len(b.declared)] = ["A", "MUDWEIGHT", "_"]


@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_is_silent_on_clean_data(rule):
    assert RULES[rule](clean_base(), PARAMS[rule]).empty


@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_catches_planted_error(rule):
    b = clean_base()
    plant(rule, b)
    found = RULES[rule](b, PARAMS[rule])
    assert not found.empty
    assert set(found["poco"]) == {"A"}


def test_every_catalog_rule_has_code_and_the_reverse():
    assert set(PARAMS) == set(RULES)


def test_score_counts_each_rule_once_per_well():
    problems = pd.DataFrame(
        {
            "poco": ["A", "A", "A", "B"],
            "regra": ["R02", "R02", "R13", "R13"],
            "gravidade": ["alta", "alta", "baixa", "baixa"],
        }
    )
    out = scores(problems, pd.Series(["A", "B", "C"]), {"alta": 15, "media": 5, "baixa": 1})
    assert out.set_index("poco")["nota"].to_dict() == {"A": 84, "B": 99, "C": 100}
