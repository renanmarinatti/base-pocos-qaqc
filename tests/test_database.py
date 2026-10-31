import duckdb
import numpy as np
import pandas as pd
import pytest

from pocos.database import CURVES, SCHEMA, dictionary, sample_table
from pocos.queries import QUERIES, parse
from pocos.standardize import load_yaml

RULES = load_yaml("regras.yaml")["regras"]


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute(SCHEMA.read_text(encoding="utf-8"))
    c.execute("INSERT INTO fonte VALUES ('a.zip', 'x', 'u', now(), 1, 'h', NULL, 'CC BY 4.0')")
    c.execute("INSERT INTO regra VALUES ('R01', 'n', 'media', 'd')")
    return c


def insert_well(con, nota=90):
    con.execute(
        "INSERT INTO poco (poco, poco_force, tipo, md_min_perfil, md_max_perfil, nota_qualidade, "
        "arquivo_las, arquivo_sodir) VALUES ('A', 'A', 'exploração', 0, 1, ?, 'a.zip', 'a.zip')",
        [nota],
    )


def test_schema_rejects_problem_with_unknown_rule_or_well(con):
    insert_well(con)
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO problema VALUES (1, 'R99', 'A', NULL, NULL, NULL, NULL, 'x')")
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO problema VALUES (1, 'R01', 'Z', NULL, NULL, NULL, NULL, 'x')")


def test_schema_rejects_score_out_of_range_and_inverted_interval(con):
    with pytest.raises(duckdb.ConstraintException):
        insert_well(con, nota=120)
    insert_well(con)
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO litologia_intervalo VALUES ('A', 10, 9, 65000, 'folhelho', 1, 3)")


def test_dictionary_documents_every_table_and_column(con):
    text = dictionary(con)
    tables = [t for (t,) in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()]
    assert all(f"## `{t}`" in text for t in tables)
    assert (
        con.execute("SELECT count(*) FROM duckdb_tables() WHERE comment IS NULL").fetchone()[0] == 0
    )


def test_samples_apply_decisions_and_flags():
    s = pd.DataFrame(
        {
            "poco": "A",
            "poco_force": "A",
            "md": [1.0, 2.0, 3.0],
            "tvdss": [0.0, 1, 2],
            "X_LOC": 1.0,
            "Y_LOC": 1.0,
            "LITOLOGIA": 65000.0,
            "CONFIANCA": 1.0,
            "MUDWEIGHT": 1.2,
            "arquivo": "a",
        }
    )
    for c in CURVES:
        s[c] = np.nan
    s["RXO"] = [-999.0, 2.0, 3.0]
    s["RHOB"] = 2.4
    s["CALI"] = [8.5, 12.0, 8.5]
    s["BS"] = 8.5
    s["DRHO"] = [0.0, 0.0, 0.3]
    s["PEF"] = [3.0, 50.0, 3.0]
    log = {"nulos_trocados_D10": {}}
    out = sample_table(s, RULES, log)
    assert "MUDWEIGHT" not in out.columns
    assert out["RXO"].isna().tolist() == [True, False, False]
    assert log["nulos_trocados_D10"] == {"RXO": 1}
    assert out["rhob_arrombado"].tolist() == [False, True, True]
    assert out["pef_baritina"].tolist() == [False, True, False]


def test_example_queries_are_parsed_with_titles():
    queries = parse(QUERIES.read_text(encoding="utf-8"))
    assert len(queries) >= 5
    assert all(title and sql.upper().startswith("SELECT") for title, sql in queries)
