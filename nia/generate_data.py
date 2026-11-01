"""Generate a synthetic Outside Plant (OSP) inventory with known, injected data-quality issues.

Tables mimic two source systems:
  * NRI (Network Resource Inventory): manholes, ducts, cables, splitters
  * GIS: gis_cables (cable routes as drawn on the map)
  * DFF (Digital Field Force): work_orders

All data is synthetic. Every injected anomaly is logged to data/injected_anomalies.csv
so the SQL checks (and the agent) can be scored against a known answer key.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import DATA_DIR, REPORTING_DATE

EXCHANGES = {
    "Ayer Rajah": "West", "Jurong": "West", "Tampines": "East", "Bedok": "East",
    "Ang Mo Kio": "North-East", "Serangoon": "North-East", "Woodlands": "North",
    "Yishun": "North", "Orchard": "Central", "Toa Payoh": "Central",
}
FIBRE_CAPACITY = [12, 24, 48, 96, 144, 288]
COPPER_CAPACITY = [50, 100, 200, 400, 800]
SPLIT_RATIOS = {"1:8": 8, "1:16": 16, "1:32": 32}
JOB_SLA_DAYS = {"Inspection": 30, "Repair": 7, "Re-termination": 14, "Duct Clearing": 21}


def _ids(prefix: str, n: int, width: int) -> list[str]:
    return [f"{prefix}-{i:0{width}d}" for i in range(1, n + 1)]


def generate(seed: int = 42, n_manholes: int = 400, n_ducts: int = 600,
             n_cables: int = 1500, n_splitters: int = 300, n_work_orders: int = 800):
    rng = np.random.default_rng(seed)
    as_of = pd.Timestamp(REPORTING_DATE)
    anomalies: list[dict] = []

    def log(kind: str, table: str, ids) -> None:
        anomalies.extend({"anomaly_type": kind, "table": table, "record_id": i} for i in ids)

    # ---- Manholes -------------------------------------------------------
    ex_names = list(EXCHANGES)
    manholes = pd.DataFrame({
        "manhole_id": _ids("MH", n_manholes, 5),
        "exchange": rng.choice(ex_names, n_manholes),
        "lat": np.round(rng.uniform(1.27, 1.44, n_manholes), 6),
        "lon": np.round(rng.uniform(103.65, 103.98, n_manholes), 6),
        "status": rng.choice(["In Service", "Abandoned"], n_manholes, p=[0.97, 0.03]),
        "install_year": rng.integers(1985, 2025, n_manholes),
    })
    manholes["region"] = manholes["exchange"].map(EXCHANGES)
    manholes = manholes[["manhole_id", "exchange", "region", "lat", "lon", "status", "install_year"]]

    # ---- Ducts ----------------------------------------------------------
    sub_count = rng.choice([1, 2, 3, 4], n_ducts)
    ducts = pd.DataFrame({
        "duct_id": _ids("DU", n_ducts, 5),
        "from_manhole": rng.choice(manholes["manhole_id"], n_ducts),
        "to_manhole": rng.choice(manholes["manhole_id"], n_ducts),
        "length_m": np.round(rng.uniform(30, 450, n_ducts), 1),
        "sub_duct_count": sub_count,
        "sub_ducts_used": [int(rng.integers(0, c + 1)) for c in sub_count],
        "status": rng.choice(["In Service", "Blocked"], n_ducts, p=[0.96, 0.04]),
    })

    # ---- Cables (NRI) ---------------------------------------------------
    ctype = rng.choice(["Fibre", "Copper"], n_cables, p=[0.7, 0.3])
    capacity = np.array([rng.choice(FIBRE_CAPACITY) if t == "Fibre" else rng.choice(COPPER_CAPACITY)
                         for t in ctype])
    status = rng.choice(["In Service", "Planned", "Decommissioned"], n_cables, p=[0.92, 0.03, 0.05])
    used = np.floor(capacity * rng.beta(2, 3, n_cables)).astype(int)
    used[status != "In Service"] = 0
    cables = pd.DataFrame({
        "cable_id": _ids("CB", n_cables, 6),
        "cable_type": ctype,
        "duct_id": rng.choice(ducts["duct_id"], n_cables),
        "capacity": capacity,
        "used_count": used,
        "install_year": rng.integers(1990, 2026, n_cables),
        "status": status,
    })

    # ---- Splitters ------------------------------------------------------
    ratio = rng.choice(list(SPLIT_RATIOS), n_splitters)
    splitters = pd.DataFrame({
        "splitter_id": _ids("SP", n_splitters, 4),
        "manhole_id": rng.choice(manholes["manhole_id"], n_splitters),
        "split_ratio": ratio,
        "ports_used": [int(rng.integers(0, SPLIT_RATIOS[r] + 1)) for r in ratio],
        "status": "In Service",
    })

    # ---- GIS cable routes (not expected for Planned cables) -------------
    in_gis = cables[cables["status"] != "Planned"].merge(ducts[["duct_id", "length_m"]], on="duct_id")
    gis = pd.DataFrame({
        "cable_id": in_gis["cable_id"],
        "duct_id": in_gis["duct_id"],
        "route_length_m": np.round(in_gis["length_m"] * rng.uniform(0.97, 1.03, len(in_gis)), 1),
    })

    # ---- Work orders (DFF) ----------------------------------------------
    asset_pool = np.concatenate([cables["cable_id"], ducts["duct_id"], manholes["manhole_id"]])
    job = rng.choice(list(JOB_SLA_DAYS), n_work_orders, p=[0.4, 0.3, 0.15, 0.15])
    opened = as_of - pd.to_timedelta(rng.integers(0, 365, n_work_orders), unit="D")
    duration = rng.gamma(2.0, 6.0, n_work_orders).round().astype(int)
    closed = opened + pd.to_timedelta(duration, unit="D")
    wo_open = (closed > as_of) | (rng.random(n_work_orders) < 0.04)
    work_orders = pd.DataFrame({
        "work_order_id": _ids("WO", n_work_orders, 5),
        "asset_id": rng.choice(asset_pool, n_work_orders),
        "job_type": job,
        "opened_date": opened.date,
        "closed_date": pd.Series(closed.date).where(~wo_open, None),
        "status": np.where(wo_open, "Open", "Closed"),
    })

    # ================= Inject anomalies (disjoint record sets) ============
    pick = lambda pool, k: list(rng.choice(pool, k, replace=False))  # noqa: E731

    mh = pick(manholes["manhole_id"], 12)
    manholes.loc[manholes["manhole_id"].isin(mh), ["lat", "lon"]] = np.nan
    log("missing_coordinates", "manholes", mh)

    duct_pool = list(ducts["duct_id"])
    orphan_d = pick(duct_pool, 6)
    ducts.loc[ducts["duct_id"].isin(orphan_d), "to_manhole"] = [f"MH-9{i:04d}" for i in range(6)]
    log("orphan_duct_manhole", "ducts", orphan_d)
    sub_over = pick([d for d in duct_pool if d not in orphan_d], 6)
    m = ducts["duct_id"].isin(sub_over)
    ducts.loc[m, "sub_ducts_used"] = ducts.loc[m, "sub_duct_count"] + 1
    log("subduct_over_capacity", "ducts", sub_over)

    in_service = list(cables.loc[cables["status"] == "In Service", "cable_id"])
    decom = list(cables.loc[cables["status"] == "Decommissioned", "cable_id"])
    rng.shuffle(in_service)
    groups = {"cable_over_capacity": 10, "orphan_cable_duct": 8, "duplicate_record": 10,
              "missing_in_gis": 10, "duct_mismatch": 8, "length_mismatch": 8}
    chosen, pos = {}, 0
    for k, n in groups.items():
        chosen[k] = in_service[pos:pos + n]
        pos += n

    m = cables["cable_id"].isin(chosen["cable_over_capacity"])
    cables.loc[m, "used_count"] = cables.loc[m, "capacity"] + rng.integers(1, 20, m.sum())
    log("cable_over_capacity", "cables", chosen["cable_over_capacity"])

    for i, cid in enumerate(chosen["orphan_cable_duct"]):
        bogus = f"DU-9{i:04d}"
        cables.loc[cables["cable_id"] == cid, "duct_id"] = bogus
        gis.loc[gis["cable_id"] == cid, "duct_id"] = bogus  # both systems agree on the bad ref
    log("orphan_cable_duct", "cables", chosen["orphan_cable_duct"])

    dec_in_use = pick(decom, 8)
    m = cables["cable_id"].isin(dec_in_use)
    cables.loc[m, "used_count"] = rng.integers(1, 12, m.sum())
    log("decommissioned_in_use", "cables", dec_in_use)

    cables = pd.concat([cables, cables[cables["cable_id"].isin(chosen["duplicate_record"])]],
                       ignore_index=True)
    log("duplicate_record", "cables", chosen["duplicate_record"])

    gis = gis[~gis["cable_id"].isin(chosen["missing_in_gis"])]
    log("missing_in_gis", "cables", chosen["missing_in_gis"])

    for cid in chosen["duct_mismatch"]:
        cur = gis.loc[gis["cable_id"] == cid, "duct_id"].iloc[0]
        gis.loc[gis["cable_id"] == cid, "duct_id"] = rng.choice([d for d in duct_pool if d != cur])
    log("duct_mismatch", "cables", chosen["duct_mismatch"])

    m = gis["cable_id"].isin(chosen["length_mismatch"])
    gis.loc[m, "route_length_m"] = np.round(gis.loc[m, "route_length_m"] * rng.choice([0.6, 1.4, 1.6], m.sum()), 1)
    log("length_mismatch", "cables", chosen["length_mismatch"])

    ghost = [f"CB-9{i:05d}" for i in range(6)]
    gis = pd.concat([gis, pd.DataFrame({"cable_id": ghost, "duct_id": rng.choice(duct_pool, 6),
                                        "route_length_m": np.round(rng.uniform(30, 450, 6), 1)})],
                    ignore_index=True)
    log("missing_in_nri", "gis_cables", ghost)

    sp = pick(splitters["splitter_id"], 6)
    m = splitters["splitter_id"].isin(sp)
    splitters.loc[m, "ports_used"] = splitters.loc[m, "split_ratio"].map(SPLIT_RATIOS) + rng.integers(1, 5, m.sum())
    log("splitter_over_capacity", "splitters", sp)

    tables = {"manholes": manholes, "ducts": ducts, "cables": cables, "splitters": splitters,
              "gis_cables": gis.reset_index(drop=True), "work_orders": work_orders}
    return tables, pd.DataFrame(anomalies)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    tables, anomalies = generate(args.seed)
    DATA_DIR.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(DATA_DIR / f"{name}.csv", index=False)
        print(f"{name:12s} {len(df):>6,} rows")
    anomalies.to_csv(DATA_DIR / "injected_anomalies.csv", index=False)
    print(f"injected anomalies: {len(anomalies)} across {anomalies['anomaly_type'].nunique()} types")


if __name__ == "__main__":
    main()
