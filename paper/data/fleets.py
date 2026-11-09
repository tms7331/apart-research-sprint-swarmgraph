"""A fleet's event log, checked against its committed summary.

Each fleet's observations.jsonl is gitignored: `generate` and `graph-curve` rebuild it deterministically, with no model
calls. So the paper never takes one on trust. It uses the local copy when that copy matches, regenerates the fleet
otherwise, and checks the result against the committed episodes.jsonl row: its event count, and the SHA-256 of the
fleet's whole-log monitor prompt (the policy and every agent's events), which the row recorded when the fleet was
made. Reading the fleet isn't recorded as one of a number's logs, since the number rests on that committed row."""

import hashlib
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from swarmgraph.scaling.fleet import VIEW, generate_fleet_episode
from swarmgraph.transfer_baseline.io import read_jsonl
from swarmgraph.transfer_baseline.monitoring import build_prompt


@contextmanager
def unrecorded() -> Iterator[None]:
    """Files read inside this block aren't recorded as the running data source's logs."""
    from paper import build  # the build records each source's reads on this stack (paper/build.py)
    build._reading.append(set())
    try:
        yield
    finally:
        build._reading.pop()


def _rows(run: Path) -> dict[str, dict]:
    return {r["case_id"]: r for r in read_jsonl(run / "episodes.jsonl")}


def _matches(events: list[dict], row: dict) -> bool:
    view = next(v for v in row["views"] if v["view"] == VIEW)
    _, prompt = build_prompt(events, VIEW, view["agents"])
    return len(events) == row["event_count"] and hashlib.sha256(prompt.encode()).hexdigest() == view["prompt_sha256"]


def fleet_events(run: Path, case_id: str, cases: Callable[[], list[dict]]) -> list[dict]:
    """The events of fleet `case_id` in run directory `run`, whose planned cases `cases()` lists."""
    row = _rows(run)[case_id]
    path = run / "episodes" / case_id / "observations.jsonl"
    with unrecorded():
        events = read_jsonl(path) if path.exists() else []
        if not _matches(events, row):
            case = next(c for c in cases() if c["case_id"] == case_id)
            with tempfile.TemporaryDirectory() as tmp:
                generate_fleet_episode(Path(tmp), case)
                events = read_jsonl(Path(tmp) / case_id / "observations.jsonl")
    if not _matches(events, row):
        raise ValueError(f"{case_id}: the regenerated fleet doesn't match its row in {run / 'episodes.jsonl'}")
    return events
