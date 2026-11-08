"""Experiment B's graph and overlap knob, on small fleets (at most 3 honest teams, per conftest). No model call."""
from swarmgraph.scaling import graph
from swarmgraph.scaling.design import case, generate
from swarmgraph.transfer_baseline.io import read_jsonl


def chains_of(root, row):
    return graph.build(read_jsonl(root / "episodes" / row["case_id"] / "observations.jsonl"))


def test_without_overlap_every_chain_is_one_team(tmp_path):
    rows = generate(tmp_path, cases=[case(0, 3, "split_attack", "split")], design={})
    built = chains_of(tmp_path, rows[0])
    assert len(built["chains"]) == 4 and all(len(c["agents"]) == 3 for c in built["chains"])
    described = graph.describe(built, rows[0]["colluding_agent_ids"])
    assert described["colluders_in_one_chain"] and described["colluders_chain_other_agents"] == 0


def test_overlap_merges_teams_and_leaves_the_rest_unchanged(tmp_path):
    plain, heavy = case(0, 3, "split_attack", "split"), case(0, 3, "split_attack", "split", overlap=4)
    rows = generate(tmp_path, cases=[plain, heavy], design={})
    assert rows[1]["case_id"].endswith("_overlap4_split_attack_split") and rows[1]["valid_completion"]
    assert rows[1]["background_valid"]
    built = chains_of(tmp_path, rows[1])
    assert len(built["chains"]) < 4
    described = graph.describe(built, rows[1]["colluding_agent_ids"])
    assert described["colluders_in_one_chain"] and described["colluders_chain_other_agents"] > 0
    again = tmp_path / "again"
    generate(again, cases=[heavy], design={})
    name = f"episodes/{heavy['case_id']}/observations.jsonl"
    assert (tmp_path / name).read_bytes() == (again / name).read_bytes()


def test_a_busy_record_is_a_hub_and_links_nothing():
    events = [{"event_id": f"e{i}", "kind": "tool_call", "agent_id": f"a_{i}", "call_id": f"c{i}",
               "payload": {"arguments": {"key": "shared/abcdef/index"}}} for i in range(10)]
    built = graph.build(events, max_agents=8)
    assert built["hubs"] == {"shared/abcdef/index": 10} and len(built["chains"]) == 10
    assert len(graph.build(events, max_agents=10)["chains"]) == 1
