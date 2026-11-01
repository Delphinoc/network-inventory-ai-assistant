"""Network Inventory AI Assistant: RAG + tool-calling agent for OSP inventory data quality."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
RESULTS_DIR = ROOT / "results"
REPORTING_DATE = "2026-10-31"
