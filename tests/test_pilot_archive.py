"""The portable pilot evidence must preserve missingness and original readings."""
import json

import pytest

from swarmgraph.initial_experiments.shared.archive import export_snapshot, portable_record
from swarmgraph.initial_experiments.shared.io import append_jsonl, read_jsonl, write_json
from swarmgraph.initial_experiments.shared.reporting import load_runs, reading, usage_summary


def episode(root, run_id, *, mode="scripted", protocol="pilot_v2", outcome=True, judged=False):
    directory = root / "runs" / run_id
    write_json(directory / "manifest.json", {
        "run_id": run_id, "protocol_version": protocol, "partition": "development",
        "generation_mode": mode, "agent_ids": ["a"], "focal_agent_ids": ["a"],
        "status": "complete" if outcome else "interrupted"})
    append_jsonl(directory / "observations.jsonl", {"event_id": "e1", "arrival_seq": 1})
    if outcome:
        append_jsonl(directory / "private/outcomes.jsonl", {"prohibited_outcome": True})
        write_json(directory / "validation.json", {"valid": True})
    if judged:
        append_jsonl(directory / "monitor_results.jsonl", {
            "run_id": run_id, "judgment_id": "j1", "result_status": "ok", "score": 95,
            "monitor_view": "per_agent", "evidence_condition": "transcript", "is_final": True,
            "prefix_boundary": 1, "candidate_agent_ids": ["a"], "supporting_event_ids": ["e1"],
            "input_event_ids": ["e1"], "call_output_path": "/old/experiments/graph_pilot/calls/c1/result.json"})
    if mode == "live":
        append_jsonl(directory / "private/actor_calls.jsonl", {
            "run_id": run_id, "status": "error", "call_id": "a1"})
    return directory


def test_export_preserves_all_v2_runs_and_readings_without_raw_archive(tmp_path):
    raw, output = tmp_path / "raw", tmp_path / "snapshot"
    episode(raw, "r_judged", judged=True)
    episode(raw, "r_unjudged")
    episode(raw, "r_live", mode="live", outcome=False)
    episode(raw, "r_old", protocol="pilot_v1", judged=True)
    (raw / "STOP_SECURITY").write_text("historical access restriction\n")
    original = [r for r in load_runs(raw) if r["manifest"]["protocol_version"] == "pilot_v2"]
    protocol = export_snapshot(raw, output)
    assert protocol["runs"] == 3 and protocol["unknown_outcomes"] == 1
    assert protocol["excluded_protocols"] == {"pilot_v1": 1}
    assert protocol["transcripts"] == 2
    assert not (output / "episodes/r_unjudged/observations.jsonl").exists()
    assert (output / "episodes/r_live/observations.jsonl").read_bytes() == (raw / "runs/r_live/observations.jsonl").read_bytes()
    expected_usage = usage_summary(raw)
    raw.rename(tmp_path / "unavailable_raw_archive")
    exported = load_runs(output)
    for before, after in zip(original, exported, strict=True):
        for field in ("manifest", "outcome", "validation", "final_boundary"):
            assert before[field] == after[field]
        assert portable_record(before["monitors"]) == after["monitors"]
        assert reading(before, "per_agent", "transcript") == reading(after, "per_agent", "transcript")
    assert usage_summary(output) == expected_usage
    live = next(row for row in read_jsonl(output / "episodes.jsonl") if row["case_id"] == "r_live")
    assert live["outcome"] is None and live["validation"] is None
    assert read_jsonl(output / "actor_calls.jsonl")[0]["status"] == "error"
    assert json.loads((output / "access_status.json").read_text())["historical_stop_markers"]["STOP_SECURITY"] == "historical access restriction\n"


def test_export_is_idempotent_and_refuses_changed_evidence(tmp_path):
    raw, output = tmp_path / "raw", tmp_path / "snapshot"
    directory = episode(raw, "r_judged", judged=True)
    export_snapshot(raw, output)
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
    export_snapshot(raw, output)
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
    append_jsonl(directory / "private/outcomes.jsonl", {"prohibited_outcome": False})
    with pytest.raises(ValueError, match="Existing snapshot differs"):
        export_snapshot(raw, output)
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}


def test_snapshot_rejects_orphan_judgments(tmp_path):
    raw, output = tmp_path / "raw", tmp_path / "snapshot"
    episode(raw, "r_judged", judged=True)
    export_snapshot(raw, output)
    append_jsonl(output / "judgments.jsonl", {"run_id": "r_missing", "score": 100})
    with pytest.raises(ValueError, match="unknown run IDs"):
        load_runs(output)
