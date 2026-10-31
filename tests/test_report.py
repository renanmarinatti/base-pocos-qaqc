import pandas as pd
import pytest

from pocos.report import (
    decision_sections,
    decisions_for,
    fill_block,
    fmt,
    name_matches,
    well_sheet,
    well_slug,
)


def test_numbers_use_brazilian_format():
    assert fmt(2337639) == "2.337.639"
    assert fmt(-104.0, 1) == "-104,0"
    assert fmt(float("nan")) == "—"


def test_slug_is_a_valid_file_name():
    assert well_slug("34/11-2 S") == "34_11-2_S"


def test_fill_block_replaces_only_between_markers_and_requires_them():
    text = "a\n<!-- numeros:inicio -->\nvelho\n<!-- numeros:fim -->\nb"
    out = fill_block(text, "novo\n")
    assert out == "a\n<!-- numeros:inicio -->\nnovo\n<!-- numeros:fim -->\nb"
    assert fill_block(out, "novo\n") == out
    with pytest.raises(ValueError):
        fill_block("sem marcador", "x")


def test_decisions_are_found_by_well_name_in_backticks():
    sections = decision_sections("## D01 — a\nfala de `25/2-13`\n## D02 — b\nfala de 25/2-13\n")
    assert decisions_for("25/2-13", sections) == ["D01"]


def test_name_matches_counts_exact_and_trivial_cleanup():
    tops = pd.DataFrame(
        {
            "fonte": ["npd_2020", "npd_2020", "sodir", "sodir"],
            "poco": ["A", "A", "A", "A"],
            "unidade": ["BALDER FM", "Sele Fm.", "BALDER FM", "SELE FM"],
        }
    )
    assert name_matches(tops) == (1, 2)


def sheet(problems, tops, cores):
    well = pd.Series(
        {
            "poco": "A",
            "poco_force": "A T2",
            "tipo": "exploração",
            "nota_qualidade": 70,
            "md_min_perfil": 100.0,
            "md_max_perfil": 2000.0,
            "prof_final_md_m": 1990.0,
            "mesa_rotativa_m": 25.0,
            "lamina_dagua_m": 100.0,
            "arquivo_las": "a.zip",
            "arquivo_sodir": "s.csv",
            "achados_conciliacao": "perfil 10 m abaixo da profundidade final oficial",
        }
    )
    return well_sheet(well, problems, tops, cores, ["D02"], {"D02": "`A T2` é `A`"})


def test_sheet_separates_decisions_missing_data_and_treated():
    problems = pd.DataFrame(
        [
            ("R08", "densidade em poço arrombado", "RHOB", 500.0, 900.0, "40% arrombado"),
            ("R07", "curvas básicas incompletas", "NPHI", None, None, "20% com dado"),
            ("R13", "curva sem unidade no cabeçalho", "X_LOC", None, None, "sem unidade"),
            ("R13", "curva sem unidade no cabeçalho", "Y_LOC", None, None, "sem unidade"),
            ("R12", "código de nulo", "RXO", 1.0, 2.0, "-999 é nulo"),
        ],
        columns=["regra", "nome", "curva", "topo_md", "base_md", "detalhe"],
    )
    tops = pd.DataFrame(
        {
            "unidade": ["UTSIRA FM", "BALDER FM"],
            "topo_md": [1034.0, 1500.0],
            "topo_md_perfil": [930.0, 1500.0],
            "situacao_perfil": ["divergente", "igual"],
            "topo_md_npd2020": [1034.0, 1500.0],
            "situacao_npd2020": ["igual", "igual"],
        }
    )
    cores = pd.DataFrame(
        {
            "numero": [1],
            "topo_md": [2010.0],
            "base_md": [2020.0],
            "situacao": ["sem perfil"],
            "cobertura_perfil": [0.0],
        }
    )
    text = sheet(problems, tops, cores)
    decide = text.split("## Para decidir")[1].split("## Falta no dado")[0]
    missing = text.split("## Falta no dado")[1].split("## Já tratado")[0]
    done = text.split("## Já tratado na base")[1]
    assert "# A (no FORCE: `A T2`)" in text
    assert "perfil 10 m abaixo" in decide
    assert "R08" in decide and "rhob_arrombado" in decide
    assert "UTSIRA FM" in decide and "-104,0 m" in decide and "BALDER" not in decide
    assert "Testemunho 1" in decide
    assert "R07" in missing and missing.count("R13") == 1 and "X_LOC, Y_LOC" in missing
    assert "R12" not in decide + missing and "D10" in done and "D02" in done
