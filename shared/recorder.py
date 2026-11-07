"""Operator observations and evaluator ground truth have separate sinks."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from shared.io import append_jsonl, utc_now


class Recorder:
    def __init__(self, run_id: str, directory: Path | None = None):
        self.run_id = run_id
        self.directory = directory
        self.observations: list[dict] = []
        self.transitions: list[dict] = []
        self.sequence = defaultdict(int)
        self.first_harm = None

    def emit(self, kind: str, payload: dict, agent_id: str | None = None,
             call_id: str | None = None, task_id: str | None = None) -> dict:
        source = "agent_transcript" if agent_id else "shared_service"
        if kind in ("policy_published", "task_assigned"):
            source = "public_context"
        stream = agent_id or source
        self.sequence[stream] += 1
        now = utc_now()
        event = {"schema_version": 1, "run_id": self.run_id,
                 "event_id": f"e{len(self.observations)+1:05d}",
                 "arrival_seq": len(self.observations)+1, "received_at": now,
                 "source": source, "stream_id": stream, "source_seq": self.sequence[stream],
                 "source_time": now[:19] + "+00:00" if source == "shared_service" else None,
                 "source_time_precision": "second" if source == "shared_service" else "unknown",
                 "kind": kind, "agent_id": agent_id, "task_id": task_id,
                 "call_id": call_id, "payload": deepcopy(payload)}
        self.observations.append(event)
        if self.directory:
            append_jsonl(self.directory / "observations.jsonl", event)
        return event

    def transition(self, key: str, before: dict | None, after: dict, actor: str,
                   harmful: bool, generated: bool = False) -> dict:
        record = {"schema_version": 1, "run_id": self.run_id,
                  "transition_id": f"s{len(self.transitions)+1:05d}",
                  "executed_at": utc_now(), "after_arrival_seq": len(self.observations),
                  "key": key, "before": deepcopy(before), "after": deepcopy(after),
                  "actor": actor, "prohibited_outcome_present": harmful,
                  "generated": generated}
        self.transitions.append(record)
        if harmful and self.first_harm is None:
            self.first_harm = record
        if self.directory:
            append_jsonl(self.directory / "private/state_changes.jsonl", record)
        return record
