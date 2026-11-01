"""Claude tool-calling agent that answers OSP inventory questions using RAG + read-only SQL."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass, field

from . import REPORTING_DATE
from .tools import TOOL_SPECS, Toolbox

DEFAULT_MODEL = os.environ.get("NIA_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = f"""You are an analytics assistant for an Outside Plant (OSP) Engineering team.
You answer questions about network inventory data (manholes, ducts, cables, splitters, GIS routes,
field work orders) and flag data-quality exceptions.

How to work:
- Look up the relevant rule with search_docs BEFORE writing SQL for any data-quality, reconciliation,
  capacity, utilisation or SLA question. Never assume a threshold, scope or definition.
- Use get_schema if you are unsure of table or column names, then run_sql (DuckDB, read-only).
- The reporting date is {REPORTING_DATE} unless the user says otherwise.
- Check your result makes sense (e.g. count rows, look for duplicates) before answering.
- Answer concisely: the finding, the rule you applied with its source as [doc#section], and the count.
- If the question asks which records are affected, end with a fenced json block listing EVERY
  matching ID once (not a sample), e.g.
```json
{{"record_ids": ["CB-000123", "CB-000456"]}}
```"""


@dataclass
class AgentResult:
    answer: str
    record_ids: list[str] | None
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    completed: bool = True


def extract_record_ids(text: str) -> list[str] | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    for b in reversed(blocks):
        try:
            ids = json.loads(b).get("record_ids")
        except json.JSONDecodeError:
            continue
        if isinstance(ids, list):
            return sorted({str(i) for i in ids})
    return None


def run_agent(question: str, client, toolbox: Toolbox, model: str = DEFAULT_MODEL,
              max_turns: int = 12, verbose: bool = False) -> AgentResult:
    messages = [{"role": "user", "content": question}]
    calls, tin, tout, t0 = [], 0, 0, time.time()
    for _ in range(max_turns):
        resp = client.messages.create(model=model, max_tokens=4096, system=SYSTEM_PROMPT,
                                      tools=TOOL_SPECS, messages=messages)
        usage = getattr(resp, "usage", None)
        tin += getattr(usage, "input_tokens", 0) or 0
        tout += getattr(usage, "output_tokens", 0) or 0
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return AgentResult(text, extract_record_ids(text), calls, tin, tout, time.time() - t0)
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            out = toolbox.call(b.name, dict(b.input))
            calls.append({"tool": b.name, "input": dict(b.input)})
            if verbose:
                print(f"  -> {b.name}({json.dumps(dict(b.input))[:200]})")
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        messages.append({"role": "user", "content": results})
    return AgentResult("Stopped: reached max turns.", None, calls, tin, tout, time.time() - t0, False)


def make_client():
    import anthropic  # imported lazily so tests run without the SDK configured
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY (see .env.example) to run the agent.")
    return anthropic.Anthropic()


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask the OSP inventory assistant a question")
    ap.add_argument("question")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("-v", "--verbose", action="store_true", help="print tool calls")
    args = ap.parse_args()
    res = run_agent(args.question, make_client(), Toolbox(), args.model, verbose=args.verbose)
    print(res.answer)
    print(f"\n[{len(res.tool_calls)} tool calls, {res.input_tokens:,} in / {res.output_tokens:,} out tokens, "
          f"{res.seconds:.1f}s]")


if __name__ == "__main__":
    main()
