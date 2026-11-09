"""Step 2, Experiment A: fleet generation, the all-logs view, judging plumbing and the analysis.

No test makes a model call.
"""
from collections import Counter
from pathlib import Path

import pytest

from swarmgraph.scaling import design as scaling
from swarmgraph.scaling.design import HONEST_TEAMS, PROTOCOL, SMOKE, planned_cases
from swarmgraph.transfer_baseline import design as step1
from swarmgraph.transfer_baseline.io import read_jsonl

PACKAGE = Path(scaling.__file__).resolve().parent
GENERATED = ("episodes", "episodes.jsonl", "protocol.json")


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and p.relative_to(root).parts[0] in GENERATED}


def test_package_is_independent_of_initial_experiments():
    for path in PACKAGE.glob("*.py"):
        assert "initial_experiments" not in path.read_text(), path.name


def test_design_is_three_run_types_by_four_layouts_by_seven_fleet_sizes():
    full, smoke = planned_cases(), planned_cases(True)
    assert len(full) == PROTOCOL["episodes"] == 84 and len(smoke) == SMOKE["episodes"] == 21
    assert len({c["case_id"] for c in full}) == 84
    assert Counter((c["condition"], c["execution_layout"]) for c in full) == {
        ("solo_attack", "solo"): 28, ("split_attack", "split"): 28, ("honest_authorized", "split"): 28}
    assert sorted({c["honest_teams"] for c in full}) == list(HONEST_TEAMS) == [0, 1, 3, 10, 30, 100, 180]
    assert {c["seed"] % 4 for c in full} == {0, 1, 2, 3} and all(c["seed"] % 4 == c["layout_variant"] for c in full)
    assert PROTOCOL["planned_monitor_readings"] == 84 * PROTOCOL["readings_per_view"]
    assert SMOKE["planned_monitor_readings"] == 21 * SMOKE["readings_per_view"]


@pytest.fixture(scope="module")
def full(tmp_path_factory, generate_small_fleets):
    root = tmp_path_factory.mktemp("scaling")
    return root, generate_small_fleets(root)


def test_generation_is_byte_identical(full, tmp_path, generate_small_fleets):
    root, _ = full
    generate_small_fleets(tmp_path)
    first, second = tree(root), tree(tmp_path)
    assert first and first == second


def test_every_episode_runs_as_designed(full):
    root, rows = full
    assert [r["case_id"] for r in rows] == [c["case_id"] for c in planned_cases() if c["honest_teams"] <= 3]
    for row in rows:
        focal = 1 if row["execution_layout"] == "solo" else 3
        assert len(row["agent_ids"]) == 3 * row["honest_teams"] + focal == len(set(row["agent_ids"]))
        assert row["background_valid"]
        if row["condition"] == "honest_authorized":
            assert row["valid_benign"] and not row["prohibited_outcome"]
        else:
            assert row["valid_completion"] and row["prohibited_outcome"]
        assert [v["view"] for v in row["views"]] == ["all_logs"] and row["views"][0]["agents"] == row["agent_ids"]
        events = read_jsonl(root / "episodes" / row["case_id"] / "observations.jsonl")
        assert len(events) == row["event_count"]
        assert {e["agent_id"] for e in events if e["agent_id"]} == set(row["agent_ids"])


def test_backgrounds_are_matched_across_run_types_and_nested_across_fleet_sizes(full):
    _, rows = full
    background = {(r["layout_variant"], r["honest_teams"], r["condition"]):
                  set(r["agent_ids"]) - set(r["focal_agent_ids"]) for r in rows}
    for variant in range(4):
        for n in (0, 1, 3):
            same = [background[(variant, n, c)] for c in ("solo_attack", "split_attack", "honest_authorized")]
            assert same[0] == same[1] == same[2] and len(same[0]) == 3 * n
        for small, large in zip((0, 1, 3), (1, 3)):
            assert background[(variant, small, "split_attack")] <= background[(variant, large, "split_attack")]


def test_with_no_honest_teams_the_split_attack_prompt_is_step_1s_group_view(full, tmp_path):
    _, rows = full
    group = {r["layout_variant"]: next(v["prompt_sha256"] for v in r["views"] if v["view"] == "group")
             for r in step1.generate(tmp_path) if r["condition"] == "split_attack"}
    zero = [r for r in rows if r["honest_teams"] == 0 and r["condition"] == "split_attack"]
    assert len(zero) == 4
    assert all(r["views"][0]["prompt_sha256"] == group[r["layout_variant"]] for r in zero)
