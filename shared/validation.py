"""Validate stored evidence without importing private labels into observations."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from shared.io import read_jsonl


REQUIRED = {"schema_version", "run_id", "event_id", "arrival_seq", "received_at", "source", "stream_id",
            "source_seq", "source_time", "source_time_precision", "kind", "agent_id", "task_id", "call_id", "payload"}
KINDS = {"policy_published", "task_assigned", "tool_call", "tool_result", "assistant_message", "service_write", "service_record"}
FORBIDDEN = {"malicious", "attack_step", "true_author", "hidden_plan", "hidden_plans", "hidden_objective", "private_plan", "private_plans",
             "colluding_agent_ids", "prohibited_outcome", "verification_status", "scenario_condition", "private"}


def _leaks(value, path="payload"):
    errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN:
                errors.append(f"forbidden public field {path}.{key}")
            errors.extend(_leaks(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            errors.extend(_leaks(child, f"{path}[{i}]"))
    return errors


def _time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def validate_observations(events: list[dict]) -> list[str]:
    errors, seen, calls, results, streams = [], set(), {}, set(), {}
    previous_arrival, previous_time, run_id = 0, None, None
    for i, event in enumerate(events, 1):
        prefix = f"observation {i}"
        if not isinstance(event, dict):
            errors.append(f"{prefix}: expected object")
            continue
        missing = REQUIRED - event.keys()
        if missing:
            errors.append(f"{prefix}: missing fields {','.join(sorted(missing))}")
        if event.get("schema_version") != 1:
            errors.append(f"{prefix}: unsupported schema_version")
        eid = event.get("event_id")
        if not isinstance(eid, str) or not eid:
            errors.append(f"{prefix}: invalid event_id")
        elif eid in seen:
            errors.append(f"{prefix}: duplicate event_id {eid}")
        else:
            seen.add(eid)
        rid = event.get("run_id")
        if not isinstance(rid, str) or not rid:
            errors.append(f"{prefix}: invalid run_id")
        elif run_id is None:
            run_id = rid
        elif rid != run_id:
            errors.append(f"{prefix}: inconsistent run_id")
        arrival = event.get("arrival_seq")
        if type(arrival) is not int or arrival <= previous_arrival:
            errors.append(f"{prefix}: arrival_seq must be positive and strictly increasing")
        else:
            previous_arrival = arrival
        try:
            received = _time(event.get("received_at"))
            if previous_time is not None and received < previous_time:
                errors.append(f"{prefix}: received_at decreases")
            previous_time = received
        except (ValueError, TypeError):
            errors.append(f"{prefix}: invalid received_at")
        source, stream = event.get("source"), event.get("stream_id")
        if not isinstance(source, str) or not source or not isinstance(stream, str) or not stream:
            errors.append(f"{prefix}: invalid source/stream_id")
        else:
            sequence = event.get("source_seq")
            prior = streams.get((source, stream), 0)
            if type(sequence) is not int or sequence <= prior:
                errors.append(f"{prefix}: source_seq must increase within source/stream")
            else:
                streams[(source, stream)] = sequence
        precision = event.get("source_time_precision")
        if precision == "unknown" and event.get("source_time") is not None:
            errors.append(f"{prefix}: unknown source precision requires null time")
        if event.get("source_time") is not None:
            try:
                _time(event["source_time"])
            except (ValueError, TypeError):
                errors.append(f"{prefix}: invalid source_time")
        kind = event.get("kind")
        if kind not in KINDS:
            errors.append(f"{prefix}: invalid kind")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            errors.append(f"{prefix}: payload must be an object")
            payload = {}
        errors.extend(f"{prefix}: {error}" for error in _leaks(payload))
        if kind in {"tool_call", "tool_result"}:
            cid, agent = event.get("call_id"), event.get("agent_id")
            if not isinstance(cid, str) or not cid or not isinstance(agent, str) or not agent:
                errors.append(f"{prefix}: tool event requires call_id and agent_id")
                continue
            if kind == "tool_call":
                if cid in calls:
                    errors.append(f"{prefix}: duplicate call_id {cid}")
                else:
                    calls[cid] = (agent, payload.get("tool"))
                if not isinstance(payload.get("tool"), str) or not isinstance(payload.get("arguments"), dict):
                    errors.append(f"{prefix}: malformed tool call")
            else:
                if cid not in calls:
                    errors.append(f"{prefix}: result has no prior call {cid}")
                elif calls[cid][0] != agent:
                    errors.append(f"{prefix}: result agent differs from call")
                elif "tool" in payload and payload["tool"] != calls[cid][1]:
                    errors.append(f"{prefix}: result tool differs from call")
                if cid in results:
                    errors.append(f"{prefix}: duplicate tool result {cid}")
                results.add(cid)
    for cid in calls.keys() - results:
        errors.append(f"call {cid}: missing tool result")
    return errors


def validate_run(directory: str | Path) -> dict:
    directory = Path(directory)
    errors, warnings, counts = [], [], {}

    def lines(relative, required=False):
        path = directory / relative
        if not path.exists():
            if required:
                errors.append(f"missing {relative}")
            counts[relative] = 0
            return []
        try:
            records = read_jsonl(path)
        except (ValueError, OSError) as exc:
            errors.append(f"{relative}: cannot parse JSONL: {exc}")
            return []
        counts[relative] = len(records)
        if any(not isinstance(record, dict) for record in records):
            errors.append(f"{relative}: records must be objects")
        return [record for record in records if isinstance(record, dict)]

    manifest = {}
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        if not isinstance(manifest, dict):
            errors.append("manifest.json: expected object")
            manifest = {}
    except (ValueError, OSError) as exc:
        errors.append(f"manifest.json: cannot read: {exc}")
    events = lines("observations.jsonl", True)
    errors.extend(validate_observations(events))
    if not events:
        errors.append("observations.jsonl: no observations")
    expected_run = manifest.get("run_id")
    if not expected_run:
        errors.append("manifest.json: missing run_id")
    for event in events:
        if expected_run and event.get("run_id") != expected_run:
            errors.append("observation run_id differs from manifest")
    outcomes = lines("private/outcomes.jsonl", True)
    if not outcomes:
        errors.append("private/outcomes.jsonl: no outcomes")
    mode = manifest.get("generation_mode", manifest.get("mode"))
    if mode not in {"constructed", "scripted", "live"}:
        errors.append("manifest.json: unknown generation mode")
    for outcome in outcomes:
        status = outcome.get("verification_status", outcome.get("verification"))
        allowed = {"asserted", "replay_verified"} if mode == "constructed" else {"execution_verified"}
        if status not in allowed:
            errors.append(f"outcome verification {status!r} incompatible with mode {mode!r}")
        if "run_id" in outcome and outcome["run_id"] != expected_run:
            errors.append("outcome run_id differs from manifest")
    actions = lines("private/actions.jsonl")
    for i, action in enumerate(actions, 1):
        if not isinstance(action.get("role"), str) or not action["role"] or action.get("tool") not in {"read", "patch", "copy", "finish"} or not isinstance(action.get("arguments"), dict):
            errors.append(f"private action {i}: invalid role/tool/arguments")
    by_id = {e["event_id"]: e for e in events if isinstance(e.get("event_id"), str)}
    max_arrival = max((e["arrival_seq"] for e in events if type(e.get("arrival_seq")) is int), default=0)
    monitors = lines("monitor_results.jsonl")
    for i, monitor in enumerate(monitors, 1):
        prefix = f"monitor {i}"
        boundary = monitor.get("prefix_boundary", monitor.get("prefix_arrival_seq", monitor.get("prefix_end_arrival_seq")))
        if isinstance(boundary, dict):
            boundary = boundary.get("arrival_seq")
        if type(boundary) is not int or boundary < 0 or boundary > max_arrival:
            errors.append(f"{prefix}: missing or invalid prefix boundary")
        inputs = monitor.get("input_event_ids")
        support = monitor.get("supporting_event_ids", [])
        if not isinstance(inputs, list) or any(not isinstance(eid, str) for eid in inputs):
            errors.append(f"{prefix}: input_event_ids must be a list of IDs")
            inputs = []
        if not isinstance(support, list) or any(not isinstance(eid, str) for eid in support):
            errors.append(f"{prefix}: supporting_event_ids must be a list of IDs")
            support = []
        status = monitor.get("status", monitor.get("result_status"))
        score = monitor.get("score")
        if not set(support).issubset(inputs):
            rejected_citation = (isinstance(status, str) and bool(status)
                                 and status not in {"ok", "success", "complete", "completed"} and score is None)
            sink = warnings if rejected_citation else errors
            sink.append(f"{prefix}: supporting events are outside input" + ("; rejected judgment remains a missing reading" if rejected_citation else ""))
        for eid in inputs:
            if eid not in by_id:
                errors.append(f"{prefix}: unknown input event {eid}")
            elif type(boundary) is int and type(by_id[eid].get("arrival_seq")) is int and by_id[eid]["arrival_seq"] > boundary:
                errors.append(f"{prefix}: input event {eid} exceeds prefix")
        if status is None:
            errors.append(f"{prefix}: missing result status")
        elif status in {"ok", "success", "complete", "completed"}:
            probabilities = monitor.get("probabilities", monitor.get("typed_probabilities"))
            if score is None and not isinstance(probabilities, dict):
                errors.append(f"{prefix}: successful result has no score/probabilities")
            if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100):
                errors.append(f"{prefix}: score must be between zero and 100")
        elif score is not None:
            errors.append(f"{prefix}: unsuccessful result must not have a score")
    links = lines("derived_links.jsonl")
    link_ids = set()
    for i, link in enumerate(links, 1):
        lid = link.get("link_id")
        if not isinstance(lid, str) or lid in link_ids:
            errors.append(f"link {i}: missing/duplicate link_id")
        else:
            link_ids.add(lid)
        boundary = link.get("available_after_arrival_seq")
        evidence = link.get("supporting_observation_ids", link.get("supporting_event_ids", link.get("evidence_event_ids")))
        if type(boundary) is not int or boundary < 0 or not isinstance(evidence, list):
            errors.append(f"link {i}: invalid evidence boundary/list")
            continue
        for eid in evidence:
            if not isinstance(eid, str) or eid not in by_id:
                errors.append(f"link {i}: unknown supporting event {eid}")
            elif type(by_id[eid].get("arrival_seq")) is int and by_id[eid]["arrival_seq"] > boundary:
                errors.append(f"link {i}: evidence exceeds availability boundary")
    if not monitors:
        warnings.append("no monitor results; evidence validation does not establish detection")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "counts": counts}
