"""Tools exposed to the agent: document search, schema lookup and read-only SQL."""
from __future__ import annotations

import json
import re

from .db import connect, schema_text
from .retriever import Retriever

MAX_ROWS = 300
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|pragma|"
    r"install|load|set|reset|call|checkpoint|vacuum)\b", re.I)

TOOL_SPECS = [
    {
        "name": "search_docs",
        "description": ("Search the OSP engineering documentation (data dictionary, data-quality "
                        "standards, NRI-GIS reconciliation, capacity rules, work-order SLAs, glossary). "
                        "Use it to look up business rules, thresholds and definitions before querying data."),
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look up"},
            "k": {"type": "integer", "description": "Number of sections to return (1-5)", "default": 3}},
            "required": ["query"]},
    },
    {
        "name": "get_schema",
        "description": "List the tables, row counts and column types in the inventory database.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql",
        "description": (f"Run one read-only DuckDB SQL query (SELECT or WITH) against the inventory "
                        f"database. Returns up to {MAX_ROWS} rows as JSON plus the total row count."),
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "A single SELECT/WITH statement"}},
            "required": ["query"]},
    },
]


def validate_sql(query: str) -> str | None:
    """Return an error message if the query is not a single read-only statement."""
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        return "Only one statement is allowed."
    if not re.match(r"^(select|with)\b", q, re.I):
        return "Only SELECT or WITH queries are allowed."
    if _FORBIDDEN.search(q):
        return "Query contains a forbidden keyword; only read-only queries are allowed."
    return None


class Toolbox:
    def __init__(self, con=None, retriever: Retriever | None = None):
        self.con = con or connect()
        self.retriever = retriever or Retriever()

    def search_docs(self, query: str, k: int = 3) -> str:
        k = max(1, min(int(k), 5))
        hits = self.retriever.search(query, k)
        return "\n\n".join(f"[{c.ref}] (score {s:.2f})\n{c.text}" for c, s in hits)

    def get_schema(self) -> str:
        return schema_text(self.con)

    def run_sql(self, query: str) -> str:
        err = validate_sql(query)
        if err:
            return json.dumps({"error": err})
        try:
            cur = self.con.execute(query.strip().rstrip(";"))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        except Exception as e:  # surface DB errors to the model so it can fix its SQL
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
        out = [dict(zip(cols, map(_jsonable, r))) for r in rows[:MAX_ROWS]]
        return json.dumps({"row_count": len(rows), "truncated": len(rows) > MAX_ROWS, "rows": out})

    def call(self, name: str, args: dict) -> str:
        if name == "search_docs":
            return self.search_docs(**args)
        if name == "get_schema":
            return self.get_schema()
        if name == "run_sql":
            return self.run_sql(**args)
        return json.dumps({"error": f"Unknown tool {name}"})


def _jsonable(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
