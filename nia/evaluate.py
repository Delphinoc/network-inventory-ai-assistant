"""Evaluation harness.

  python -m nia.evaluate checks     # SQL checks vs injected anomalies (offline)
  python -m nia.evaluate retrieval  # doc retrieval hit@k / MRR (offline)
  python -m nia.evaluate agent      # Claude agent vs SQL answer key (needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import json
from statistics import mean

import pandas as pd

from . import DATA_DIR, RESULTS_DIR
from .checks import run_check

# Plain-language ops questions. Thresholds and scope rules are deliberately NOT given:
# the agent has to find them in the docs.
AGENT_EVAL = {
    "missing_coordinates": "Which manholes can't be located on the map because their coordinates are incomplete?",
    "duplicate_record": "Are there any duplicate cable records in the NRI? List the affected cable IDs.",
    "orphan_cable_duct": "Which cables reference a duct that doesn't exist in the inventory?",
    "orphan_duct_manhole": "Which ducts are linked to a manhole that isn't in the inventory?",
    "cable_over_capacity": "Which cables show more fibres or pairs in use than they physically have?",
    "subduct_over_capacity": "Which ducts have more sub-ducts occupied than installed?",
    "splitter_over_capacity": "Which splitters have more ports in use than their split ratio allows?",
    "decommissioned_in_use": "Which cables have a status that conflicts with their service assignments?",
    "missing_in_gis": "Which NRI cables are missing from GIS and should be raised as reconciliation exceptions?",
    "missing_in_nri": "Are there cable routes in GIS with no matching NRI record? List them.",
    "duct_mismatch": "Which cables are recorded in a different duct in NRI than in GIS?",
    "length_mismatch": "Which cables have a GIS route length that is out of tolerance against the recorded duct length?",
    "underutilised_cable": "Which cables should be flagged as underutilised under our planning standards?",
    "aged_open_work_orders": "Which open work orders are past their SLA as of the reporting date?",
}

# Question -> section that contains the answer.
RETRIEVAL_EVAL = [
    ("Which cables are out of scope for NRI-GIS reconciliation?", "nri_gis_reconciliation#Scope"),
    ("What tolerance is allowed between GIS route length and duct length?", "nri_gis_reconciliation#Route length tolerance"),
    ("What is a ghost route in GIS?", "nri_gis_reconciliation#Missing in NRI"),
    ("How many days does a repair job have before it breaches SLA?", "field_work_orders#SLA targets by job type"),
    ("When is an open work order considered overdue?", "field_work_orders#Aged (overdue) work orders"),
    ("What aging buckets are used for overdue field work?", "field_work_orders#Aging buckets"),
    ("How many output ports does a 1:16 splitter have?", "capacity_and_utilisation#Splitter over capacity"),
    ("What makes a cable underutilised for investment planning?", "capacity_and_utilisation#Underutilised cables"),
    ("How is cable utilisation calculated?", "capacity_and_utilisation#Cable utilisation"),
    ("Can a decommissioned cable still have fibres in use?", "data_quality_standards#Status consistency: decommissioned cables"),
    ("What date should be used for as-of calculations?", "data_quality_standards#Reporting date"),
    ("Is a cable ID appearing twice a problem?", "data_quality_standards#Uniqueness: duplicate records"),
    ("What does a manhole need to be located on the map?", "data_quality_standards#Completeness: manhole coordinates"),
    ("What columns are in the gis_cables table?", "data_dictionary#gis_cables (GIS)"),
    ("What does the capacity column mean for copper cables?", "data_dictionary#cables (NRI)"),
    ("What is a sub-duct?", "glossary#Duct and sub-duct"),
    ("What is the DFF system used for?", "glossary#NRI, GIS and DFF"),
]


def prf(pred: set, truth: set) -> dict:
    tp = len(pred & truth)
    p = tp / len(pred) if pred else (1.0 if not truth else 0.0)
    r = tp / len(truth) if truth else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3), "exact_match": pred == truth}


def eval_checks(con) -> dict:
    inj = pd.read_csv(DATA_DIR / "injected_anomalies.csv")
    rows = {k: prf(set(run_check(con, k)), set(g["record_id"])) for k, g in inj.groupby("anomaly_type")}
    return {"per_check": rows, "mean_recall": mean(r["recall"] for r in rows.values()),
            "mean_precision": mean(r["precision"] for r in rows.values()), "anomalies": len(inj)}


def eval_retrieval(retriever, ks=(1, 3)) -> dict:
    hits = {k: 0 for k in ks}
    rr = []
    for q, target in RETRIEVAL_EVAL:
        refs = [c.ref for c, _ in retriever.search(q, k=max(5, *ks))]
        for k in ks:
            hits[k] += target in refs[:k]
        rr.append(1 / (refs.index(target) + 1) if target in refs else 0.0)
    n = len(RETRIEVAL_EVAL)
    return {"questions": n, **{f"hit@{k}": round(hits[k] / n, 3) for k in ks}, "mrr": round(mean(rr), 3)}


def eval_agent(client, toolbox, model, only=None, verbose=False) -> dict:
    from .agent import run_agent
    per = {}
    for cid, q in AGENT_EVAL.items():
        if only and cid not in only:
            continue
        truth = set(run_check(toolbox.con, cid))
        res = run_agent(q, client, toolbox, model=model, verbose=verbose)
        pred = set(res.record_ids or [])
        used_docs = any(c["tool"] == "search_docs" for c in res.tool_calls)
        per[cid] = {**prf(pred, truth), "truth_n": len(truth), "pred_n": len(pred),
                    "parsed_ids": res.record_ids is not None, "searched_docs": used_docs,
                    "tool_calls": len(res.tool_calls), "input_tokens": res.input_tokens,
                    "output_tokens": res.output_tokens, "seconds": round(res.seconds, 1)}
        print(f"{cid:24s} P={per[cid]['precision']:.2f} R={per[cid]['recall']:.2f} "
              f"exact={per[cid]['exact_match']} tools={per[cid]['tool_calls']}")
    vals = list(per.values())
    return {"model": model, "questions": len(vals), "per_question": per,
            "mean_precision": round(mean(v["precision"] for v in vals), 3),
            "mean_recall": round(mean(v["recall"] for v in vals), 3),
            "mean_f1": round(mean(v["f1"] for v in vals), 3),
            "exact_match_rate": round(mean(v["exact_match"] for v in vals), 3),
            "doc_search_rate": round(mean(v["searched_docs"] for v in vals), 3),
            "mean_tool_calls": round(mean(v["tool_calls"] for v in vals), 1),
            "total_tokens": sum(v["input_tokens"] + v["output_tokens"] for v in vals)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suite", choices=["checks", "retrieval", "agent"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--only", nargs="*", help="agent suite: run only these check IDs")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    RESULTS_DIR.mkdir(exist_ok=True)
    if args.suite == "checks":
        from .db import connect
        out = eval_checks(connect())
    elif args.suite == "retrieval":
        from .retriever import Retriever
        out = eval_retrieval(Retriever())
    else:
        from .agent import DEFAULT_MODEL, make_client
        from .tools import Toolbox
        out = eval_agent(make_client(), Toolbox(), args.model or DEFAULT_MODEL, args.only, args.verbose)
    (RESULTS_DIR / f"{args.suite}_eval.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("per_")}, indent=2))


if __name__ == "__main__":
    main()
