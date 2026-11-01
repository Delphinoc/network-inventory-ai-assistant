import pandas as pd

from nia import DATA_DIR
from nia.checks import CHECKS, run_check
from nia.generate_data import generate


def test_generator_is_deterministic():
    a, inj_a = generate(seed=7)
    b, inj_b = generate(seed=7)
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])
    pd.testing.assert_frame_equal(inj_a, inj_b)


def test_injected_sets_are_disjoint_within_cables():
    _, inj = generate()
    cab = inj[inj["table"] == "cables"]
    assert cab["record_id"].is_unique


def test_sql_checks_recover_every_injected_anomaly(con):
    inj = pd.read_csv(DATA_DIR / "injected_anomalies.csv")
    for kind, grp in inj.groupby("anomaly_type"):
        assert set(run_check(con, kind)) == set(grp["record_id"]), kind


def test_every_check_runs(con):
    for cid in CHECKS:
        assert isinstance(run_check(con, cid), list)
