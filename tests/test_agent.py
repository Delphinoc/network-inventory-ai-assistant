"""Agent loop tests with a scripted fake Claude client (no API key needed)."""
from types import SimpleNamespace as NS

from nia.agent import extract_record_ids, run_agent
from nia.evaluate import prf


def text(t):
    return NS(type="text", text=t)


def tool_use(i, name, inp):
    return NS(type="tool_use", id=i, name=name, input=inp)


class FakeClient:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        content, stop = self.responses.pop(0)
        return NS(content=content, stop_reason=stop, usage=NS(input_tokens=100, output_tokens=20))


def test_agent_runs_tools_then_answers(toolbox):
    client = FakeClient([
        ([tool_use("t1", "search_docs", {"query": "splitter port capacity"})], "tool_use"),
        ([tool_use("t2", "run_sql", {"query": "SELECT splitter_id FROM splitters WHERE ports_used > "
                                              "CAST(split_part(split_ratio, ':', 2) AS INT)"})], "tool_use"),
        ([text('Found 2.\n```json\n{"record_ids": ["SP-0002", "SP-0001"]}\n```')], "end_turn"),
    ])
    res = run_agent("Which splitters are over capacity?", client, toolbox)
    assert [c["tool"] for c in res.tool_calls] == ["search_docs", "run_sql"]
    assert res.record_ids == ["SP-0001", "SP-0002"]
    assert res.input_tokens == 300 and res.completed
    # tool results are fed back to the model with matching ids
    last_user = client.calls[-1]["messages"][-2]  # list is shared; final assistant turn appended after
    assert last_user["content"][0]["tool_use_id"] == "t2"
    assert '"row_count": 6' in last_user["content"][0]["content"]


def test_agent_stops_at_max_turns(toolbox):
    loop = [([tool_use(f"t{i}", "get_schema", {})], "tool_use") for i in range(3)]
    res = run_agent("q", FakeClient(loop), toolbox, max_turns=3)
    assert not res.completed and res.record_ids is None


def test_extract_record_ids_uses_last_valid_block():
    t = '```json\n{"record_ids": ["A"]}\n```\nfix:\n```json\n{"record_ids": ["B","B","C"]}\n```'
    assert extract_record_ids(t) == ["B", "C"]
    assert extract_record_ids("no ids here") is None


def test_prf():
    assert prf({"a", "b"}, {"a", "c"}) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "exact_match": False}
    assert prf(set(), set())["exact_match"]
