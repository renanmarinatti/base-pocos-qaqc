import pandas as pd

from pocos.standardize import alias_map, lithology_intervals, official_name

CATALOG = {
    "curvas": {
        "GR": {},
        "X_LOC": {},
        "LITOLOGIA": {"apelidos": ["FORCE_2020_LITHOFACIES_LITHOLOGY"]},
    }
}


def test_alias_is_case_insensitive_and_maps_to_canonical():
    aliases = alias_map(CATALOG)
    assert aliases["X_LOC"] == "X_LOC"
    assert aliases["x_loc".upper()] == "X_LOC"
    assert aliases["FORCE_2020_LITHOFACIES_LITHOLOGY"] == "LITOLOGIA"


def test_official_name_uses_exception_only_when_listed():
    exceptions = {"25/2-13 T4": {"sodir": "25/2-13"}}
    assert official_name("25/2-13 T4", exceptions) == "25/2-13"
    assert official_name("15/9-13", exceptions) == "15/9-13"


def test_lithology_runs_become_intervals_and_gaps_split_them():
    step = 0.152
    md = [100 + i * step for i in range(6)] + [110 + i * step for i in range(2)]
    samples = pd.DataFrame(
        {
            "poco": "A",
            "md": md,
            "LITOLOGIA": [65000, 65000, 65000, 30000, 30000, 30000, 30000, 30000],
            "CONFIANCA": 1.0,
            "arquivo": "x",
        }
    )
    out = lithology_intervals(samples, {65000: "folhelho", 30000: "arenito"}, step)
    # folhelho; arenito até o buraco; arenito depois do buraco
    assert out["litologia"].tolist() == ["folhelho", "arenito", "arenito"]
    assert out.loc[0, "topo_md"] == 100
    assert abs(out.loc[0, "base_md"] - (100 + 3 * step)) < 1e-9
    assert out["amostras"].tolist() == [3, 3, 2]
