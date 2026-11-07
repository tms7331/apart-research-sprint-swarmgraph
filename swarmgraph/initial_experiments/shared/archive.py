"""Export the historical pilot's compact evidence without making model calls."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .io import canonical, read_jsonl
from .reporting import load_runs, usage_summary

FORMAT = "graph_pilot_snapshot_v1"


def portable_record(value):
    """Relocate provenance pointers; leave scores, evidence and explanations intact."""
    if isinstance(value, list):
        return [portable_record(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in {"output_path", "call_output_path"} and isinstance(item, str):
            marker = "experiments/graph_pilot/"
            if marker in item:
                item = "logs/graph_pilot/raw/" + item.split(marker, 1)[1]
        result[key] = portable_record(item)
    return result


def export_snapshot(source: Path, destination: Path) -> dict:
    source, destination = Path(source), Path(destination)
    all_runs = load_runs(source)
    runs = [run for run in all_runs if run["manifest"].get("protocol_version") == "pilot_v2"]
    if not runs:
        raise ValueError("No pilot_v2 runs found; refusing an empty export")
    if any(run["manifest"].get("partition") != "development" for run in runs):
        raise ValueError("This archive exporter is scoped to development records")
    files, sources = {}, {}

    def remember(path):
        if path.exists():
            content = path.read_bytes()
            sources[path.relative_to(source).as_posix()] = {
                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}

    def json_file(name, value):
        files[name] = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()

    def jsonl_file(name, rows):
        files[name] = "".join(canonical(row) + "\n" for row in rows).encode()

    episodes, judgments, actor_calls = [], [], []
    transcripts = 0
    for run in runs:
        manifest = run["manifest"]
        run_id = manifest["run_id"]
        directory = Path(run["directory"])
        if directory.name != run_id:
            raise ValueError(f"Run directory and manifest disagree: {directory}")
        selected = bool(run["monitors"]) or manifest["generation_mode"] == "live"
        transcript = f"episodes/{run_id}/observations.jsonl" if selected else None
        if selected:
            files[transcript] = (directory / "observations.jsonl").read_bytes()
            transcripts += 1
        episodes.append({"schema_version": 1, "case_id": run_id,
                         "manifest": manifest, "outcome": run["outcome"] or None,
                         "validation": run["validation"], "event_count": run["final_boundary"],
                         "transcript_path": transcript})
        judgments.extend(portable_record(run["monitors"]))
        actor_calls.extend(portable_record(read_jsonl(directory / "private/actor_calls.jsonl")))
        for name in ("manifest.json", "private/outcomes.jsonl", "validation.json",
                     "observations.jsonl", "monitor_results.jsonl", "private/actor_calls.jsonl"):
            remember(directory / name)
    for path in sorted((source / "calls").glob("*/attempt_*/result.json")):
        remember(path)
    jsonl_file("episodes.jsonl", episodes)
    jsonl_file("judgments.jsonl", judgments)
    jsonl_file("actor_calls.jsonl", actor_calls)
    json_file("usage_summary.json", usage_summary(source))
    stops = {}
    for name in ("STOP", "STOP_SECURITY", "STOP_ACCESS"):
        path = source / name
        if path.exists():
            remember(path)
            stops[name] = path.read_text()
    json_file("access_status.json", {"model_calls_performed_by_export": 0, "historical_stop_markers": stops})
    protocol = {"schema_version": 1, "format": FORMAT, "protocol_version": "pilot_v2",
        "partition": "development", "status": "incomplete_access_blocked" if stops else "development_only",
        "selection": "All pilot_v2 runs and judgments; transcripts for every judged or live run.",
        "runs": len(runs), "saved_outcomes": sum(bool(run["outcome"]) for run in runs),
        "unknown_outcomes": sum(not run["outcome"] for run in runs), "transcripts": transcripts,
        "judgments": len(judgments), "judgment_statuses": dict(Counter(j["result_status"] for j in judgments)),
        "actor_calls": len(actor_calls), "excluded_protocols": dict(Counter(
            run["manifest"].get("protocol_version") for run in all_runs if run not in runs)),
        "raw_archive": "raw", "original_raw_archive": "experiments/graph_pilot",
        "path_relocation": "Only output_path and call_output_path provenance pointers are rebased to logs/graph_pilot/raw/.",
        "usage_scope": "All original pilot calls, including the excluded pilot_v1 work.",
        "claims": "Uncalibrated development evidence; missing outcomes/readings remain unknown."}
    json_file("protocol.json", protocol)
    json_file("inventory.json", {"schema_version": 1, "source_root": "raw",
        "source_files": sources,
        "exported_files": {name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                           for name, content in sorted(files.items())}})
    # Refuse to replace a different snapshot; identical reruns are harmless.
    for name, content in files.items():
        target = destination / name
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Existing snapshot differs: {target}")
    for name, content in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("logs/graph_pilot/raw"))
    parser.add_argument("--output", type=Path, default=Path("logs/graph_pilot"))
    args = parser.parse_args()
    print(json.dumps(export_snapshot(args.source, args.output)))


if __name__ == "__main__":
    main()
