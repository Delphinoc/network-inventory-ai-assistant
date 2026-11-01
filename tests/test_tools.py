import json

import pytest

from nia.evaluate import eval_retrieval
from nia.tools import validate_sql


@pytest.mark.parametrize("q", [
    "DROP TABLE cables", "select 1; drop table cables", "INSERT INTO cables VALUES (1)",
    "UPDATE cables SET status='x'", "COPY cables TO 'x.csv'", "PRAGMA version",
    "select * from cables; select 1", "SET enable_external_access=true"])
def test_write_and_multi_statements_rejected(q):
    assert validate_sql(q) is not None


def test_select_allowed_and_returns_rows(toolbox):
    out = json.loads(toolbox.run_sql("SELECT cable_type, COUNT(*) n FROM cables GROUP BY 1 ORDER BY 1"))
    assert out["row_count"] == 2 and out["rows"][0]["cable_type"] == "Copper"


def test_file_access_blocked(toolbox):
    out = json.loads(toolbox.run_sql("SELECT * FROM read_csv_auto('/etc/passwd')"))
    assert "error" in out


def test_sql_errors_returned_not_raised(toolbox):
    assert "error" in json.loads(toolbox.run_sql("SELECT nope FROM cables"))


def test_search_docs_finds_reconciliation_scope(toolbox):
    assert "nri_gis_reconciliation#Scope" in toolbox.search_docs("which cables are excluded from GIS reconciliation")


def test_retrieval_quality_floor(toolbox):
    res = eval_retrieval(toolbox.retriever)
    assert res["hit@3"] >= 0.85
