"""The explorer's tools over a public log. No model call."""
from swarmgraph.scaling.explorer import READ_LOG_MAX, SEARCH_PAGE, Log, render


def events(n_agents=30):
    out = [{"event_id": "e00001", "kind": "policy_published", "agent_id": None, "call_id": None,
            "payload": {"policy": "P", "services": "S"}}]
    for a in range(n_agents):
        for kind, payload in (("task_assigned", {"task": f"task {a}"}), ("tool_call", {"tool": "patch", "arguments": {"key": f"k/{a}", "fields": {"enabled": a % 2 == 0}}})):
            out.append({"event_id": f"e{len(out)+1:05d}", "kind": kind, "agent_id": f"a_{a:02d}", "call_id": None, "payload": payload})
    out.append({"event_id": f"e{len(out)+1:05d}", "kind": "service_write", "agent_id": None, "call_id": None, "payload": {"key": "k/0"}})
    return out


def test_tools_return_bounded_results_and_never_service_records():
    log = Log(events())
    assert len(log.events) == 60 and all(e["agent_id"] for e in log.events)
    found = log.run({"tool": "search", "query": '"ENABLED":TRUE', "start": 0})
    assert found["matches"] == 15 and len(found["results"]) == 15
    found = log.run({"tool": "search", "query": "task", "start": 0})
    assert found["matches"] == 30 and len(found["results"]) == SEARCH_PAGE
    assert len(log.run({"tool": "search", "query": "task", "start": 20})["results"]) == 10
    page = log.run({"tool": "read_log", "start": 50, "count": 99})
    assert [e["position"] for e in page["events"]] == list(range(50, 61)) and len(page["events"]) <= READ_LOG_MAX
    assert log.run({"tool": "read_events", "event_ids": ["e00002", "nope"]})["unknown"] == ["nope"]
    assert len(log.run({"tool": "read_agent", "agent_id": "a_03"})["events"]) == 2
    assert "error" in log.run({"tool": "read_agent", "agent_id": "a_99"})
    prompt = render(log, [], final=False)
    assert "service_write" not in prompt and "15 calls remain" in prompt and "P" in prompt
