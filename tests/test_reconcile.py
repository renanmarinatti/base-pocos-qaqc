import pandas as pd

from pocos.reconcile import base_name, compare_tops, prepare_tops, wells_check

NAMES = {"renomeadas": {"BAAT": "BRENT"}, "marcadores_sem_nome": ["NO FORMAL NAME"]}


def test_base_name_ignores_case_dots_suffix_and_norwegian_letters():
    assert base_name("Blodoeks Fm.", {}) == base_name("BLODØKS FM", {}) == "BLODOEKS"
    assert base_name("Statfjord Fm.", {}) == base_name("STATFJORD GP", {})
    assert base_name("BAAT GP.", NAMES["renomeadas"]) == "BRENT"
    assert base_name("EGGA FM (INFORMAL)", {}) == "EGGA"


def tops(rows):
    return pd.DataFrame(rows, columns=["fonte", "poco", "unidade", "topo_md"])


def classify(rows, source="npd_2020"):
    t = prepare_tops(tops(rows), NAMES)
    logged = pd.DataFrame({"poco": ["A"], "md_min": [0.0], "md_max": [5000.0]})
    out = compare_tops(t, source, logged)
    return dict(
        zip(out["base"] + "#" + out["ocorrencia"].astype(str), out["situacao"], strict=True)
    )


def test_equal_divergent_and_only_in_one_source():
    got = classify(
        [
            ("npd_2020", "A", "Utsira Fm.", 800.0),
            ("sodir", "A", "UTSIRA FM", 800.4),
            ("npd_2020", "A", "Lista Fm.", 2000.0),
            ("sodir", "A", "LISTA FM", 2100.0),
            ("sodir", "A", "SELE FM", 2050.0),
            ("sodir", "A", "NO FORMAL NAME", 2500.0),
        ]
    )
    assert got == {"UTSIRA#1": "igual", "LISTA#1": "divergente", "SELE#1": "só na Sodir"}


def test_repeated_unit_is_matched_by_occurrence_not_crossed():
    got = classify(
        [
            ("npd_2020", "A", "Lista Fm.", 2000.0),
            ("npd_2020", "A", "Lista Fm.", 2200.0),
            ("sodir", "A", "LISTA FM", 2000.0),
            ("sodir", "A", "LISTA FM", 2200.0),
        ]
    )
    assert got == {"LISTA#1": "igual", "LISTA#2": "igual"}


def test_same_offset_in_many_tops_is_a_reference_shift():
    rows = []
    for i, unit in enumerate(["U1", "U2", "U3", "U4"]):
        rows += [
            ("npd_2020", "A", f"{unit} Fm.", 1000.0 + 100 * i),
            ("sodir", "A", f"{unit} FM", 1003.0 + 100 * i),
        ]
    rows += [("npd_2020", "A", "U5 Fm.", 1500.0), ("sodir", "A", "U5 FM", 1650.0)]
    got = classify(rows)
    assert {got[f"U{i}#1"] for i in range(1, 5)} == {"deslocamento uniforme do poço"}
    assert got["U5#1"] == "divergente"


def test_official_top_above_labelled_log_is_not_a_divergence():
    got = classify(
        [
            ("perfil_force", "A", "NORDLAND GP.", 494.5),
            ("sodir", "A", "NORDLAND GP", 106.0),
            ("perfil_force", "A", "HORDALAND GP.", 1143.1),
            ("sodir", "A", "HORDALAND GP", 1143.0),
        ],
        source="perfil_force",
    )
    assert got == {"NORDLAND#1": "fora do trecho perfilado", "HORDALAND#1": "igual"}


def test_well_logged_only_below_kickoff_is_not_compared_by_first_sample():
    wells = pd.DataFrame(
        {
            "poco": ["V", "D"],
            "poco_force": ["V", "D"],
            "dist_force_sodir_m": [1.0, 2444.0],
            "mesa_rotativa_m": [25.0, 25.0],
            "md_menos_tvdss_topo": [25.0, 1082.0],
            "md_min": [100.0, 3900.0],
            "md_max": [3000.0, 4700.0],
            "prof_final_md_sodir": [3000.0, 4724.0],
            "desvio_max_m": [1.0, 315.0],
        }
    )
    out = wells_check(wells).set_index("poco")["achados"]
    assert out["V"] == ""
    assert out["D"].startswith("perfil começa abaixo do ponto de desvio")
