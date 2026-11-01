"""Load the inventory CSVs into an in-memory DuckDB database, then lock it down."""
from __future__ import annotations

import duckdb

from . import DATA_DIR

TABLES = ["manholes", "ducts", "cables", "splitters", "gis_cables", "work_orders"]


def connect(data_dir=DATA_DIR, lock: bool = True) -> duckdb.DuckDBPyConnection:
    if not (data_dir / "cables.csv").exists():
        from .generate_data import main as gen
        gen()
    con = duckdb.connect(":memory:")
    for t in TABLES:
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto(?, header=true)",
                    [str(data_dir / f"{t}.csv")])
    if lock:
        # No file / network access and no config changes once data is loaded.
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
    return con


def schema_text(con) -> str:
    lines = []
    for t in TABLES:
        cols = con.execute(f"DESCRIBE {t}").fetchall()
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        lines.append(f"{t} ({n:,} rows): " + ", ".join(f"{c[0]} {c[1]}" for c in cols))
    return "\n".join(lines)
