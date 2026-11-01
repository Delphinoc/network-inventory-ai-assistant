"""Rule-based SQL data-quality checks: the answer key the agent is scored against.

Each check returns the IDs of the records that break a rule in docs/data_quality_standards.md,
docs/nri_gis_reconciliation.md, docs/capacity_and_utilisation.md or docs/field_work_orders.md.
"""
from __future__ import annotations

import argparse

import pandas as pd

from . import REPORTING_DATE

CHECKS: dict[str, dict] = {
    "missing_coordinates": {
        "category": "Completeness",
        "sql": "SELECT manhole_id AS record_id FROM manholes WHERE lat IS NULL OR lon IS NULL",
    },
    "duplicate_record": {
        "category": "Uniqueness",
        "sql": "SELECT cable_id AS record_id FROM cables GROUP BY cable_id HAVING COUNT(*) > 1",
    },
    "orphan_cable_duct": {
        "category": "Referential integrity",
        "sql": """SELECT DISTINCT c.cable_id AS record_id FROM cables c
                  ANTI JOIN ducts d ON c.duct_id = d.duct_id""",
    },
    "orphan_duct_manhole": {
        "category": "Referential integrity",
        "sql": """SELECT duct_id AS record_id FROM ducts
                  WHERE from_manhole NOT IN (SELECT manhole_id FROM manholes)
                     OR to_manhole NOT IN (SELECT manhole_id FROM manholes)""",
    },
    "cable_over_capacity": {
        "category": "Capacity",
        "sql": "SELECT DISTINCT cable_id AS record_id FROM cables WHERE used_count > capacity",
    },
    "subduct_over_capacity": {
        "category": "Capacity",
        "sql": "SELECT duct_id AS record_id FROM ducts WHERE sub_ducts_used > sub_duct_count",
    },
    "splitter_over_capacity": {
        "category": "Capacity",
        "sql": """SELECT splitter_id AS record_id FROM splitters
                  WHERE ports_used > CAST(split_part(split_ratio, ':', 2) AS INTEGER)""",
    },
    "decommissioned_in_use": {
        "category": "Status consistency",
        "sql": """SELECT DISTINCT cable_id AS record_id FROM cables
                  WHERE status = 'Decommissioned' AND used_count > 0""",
    },
    "missing_in_gis": {
        "category": "Reconciliation",
        "sql": """SELECT DISTINCT c.cable_id AS record_id FROM cables c
                  ANTI JOIN gis_cables g ON c.cable_id = g.cable_id
                  WHERE c.status <> 'Planned'""",
    },
    "missing_in_nri": {
        "category": "Reconciliation",
        "sql": """SELECT DISTINCT g.cable_id AS record_id FROM gis_cables g
                  ANTI JOIN cables c ON c.cable_id = g.cable_id""",
    },
    "duct_mismatch": {
        "category": "Reconciliation",
        "sql": """SELECT DISTINCT c.cable_id AS record_id FROM cables c
                  JOIN gis_cables g ON c.cable_id = g.cable_id
                  WHERE c.duct_id <> g.duct_id""",
    },
    "length_mismatch": {
        "category": "Reconciliation",
        "sql": """SELECT DISTINCT c.cable_id AS record_id FROM cables c
                  JOIN gis_cables g ON c.cable_id = g.cable_id AND c.duct_id = g.duct_id
                  JOIN ducts d ON d.duct_id = c.duct_id
                  WHERE ABS(g.route_length_m - d.length_m) / d.length_m > 0.10""",
    },
    "underutilised_cable": {
        "category": "Utilisation insight",
        "sql": """SELECT DISTINCT cable_id AS record_id FROM cables
                  WHERE status = 'In Service' AND install_year <= 2015
                    AND used_count * 1.0 / capacity < 0.10""",
    },
    "aged_open_work_orders": {
        "category": "Aging",
        "sql": f"""SELECT work_order_id AS record_id FROM work_orders
                   WHERE status = 'Open'
                     AND DATE '{REPORTING_DATE}' - opened_date > CASE job_type
                         WHEN 'Repair' THEN 7 WHEN 'Re-termination' THEN 14
                         WHEN 'Duct Clearing' THEN 21 WHEN 'Inspection' THEN 30 END""",
    },
}


def run_check(con, check_id: str) -> list[str]:
    return sorted(r[0] for r in con.execute(CHECKS[check_id]["sql"]).fetchall())


def run_all(con) -> pd.DataFrame:
    rows = [{"check_id": cid, "category": c["category"], "record_id": rid}
            for cid, c in CHECKS.items() for rid in run_check(con, cid)]
    return pd.DataFrame(rows)


def main() -> None:
    from .db import connect
    argparse.ArgumentParser(description="Run all SQL data-quality checks").parse_args()
    con = connect()
    issues = run_all(con)
    summary = issues.groupby(["category", "check_id"]).size().rename("records").reset_index()
    print(summary.to_string(index=False))
    print(f"\nTotal flagged: {len(issues)}")


if __name__ == "__main__":
    main()
