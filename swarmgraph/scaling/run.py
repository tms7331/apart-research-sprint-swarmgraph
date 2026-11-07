"""Step 2: generate the fleets, then run the all-logs reference and Experiment A's investigator on them.

    uv run python -m swarmgraph.scaling generate [--smoke]      # deterministic fleets, no model calls
    uv run python -m swarmgraph.scaling investigate [--smoke]   # Experiment A: the missing investigations, then its report
    uv run python -m swarmgraph.scaling judge [--smoke]         # all-logs reference: the missing readings, then its report
    uv run python -m swarmgraph.scaling report [--smoke]        # both reports

Full run: logs/scaling/ (84 episodes; 3 investigations each), reports in reports/scaling_investigator/ and
reports/scaling_all_logs/. Smoke run (--smoke): logs/scaling_smoke/ (21 episodes; 1 investigation each),
reports beside it. The raw Codex CLI archive goes to <destination>/raw_calls/, which Git ignores.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from swarmgraph.transfer_baseline.io import read_jsonl, utc_now
from swarmgraph.transfer_baseline.monitoring import judge_one
from swarmgraph.transfer_baseline.run import MonitorClient, pending

from . import explorer, investigator
from .design import DESTINATION, INVESTIGATOR_REPORT, REPORT, SMOKE_DESTINATION, generate, protocol


def _stopped(client) -> None:
    if getattr(client, "stopped", False):
        raise RuntimeError("A stop marker exists in raw_calls/ (access, safety or usage restriction); "
                           "saved results are kept and the run resumes later")


async def judge(destination: Path, smoke: bool = False, concurrency: int = 2, client=None,
                min_interval: float = 2.0) -> None:
    """All-logs reference: one all-logs view per episode, judged readings_per_view times."""
    destination = Path(destination)
    readings = protocol(smoke)["readings_per_view"]
    todo = pending(destination, readings)
    client = client or MonitorClient(destination / "raw_calls", concurrency, min_interval)
    _stopped(client)
    print(json.dumps({"at": utc_now(), "pending_readings": len(todo)}), flush=True)
    await asyncio.gather(*(judge_one(client, destination, planned) for planned in todo))
    remaining = len(pending(destination, readings))
    print(json.dumps({"at": utc_now(), "taken": len(todo) - remaining, "still_missing": remaining}), flush=True)
    _stopped(client)


async def investigate(destination: Path, smoke: bool = False, concurrency: int = 2, client=None,
                      min_interval: float = 2.0) -> None:
    """Experiment A: the investigations not yet finished."""
    destination = Path(destination)
    runs = investigator.SMOKE_RUNS if smoke else investigator.RUNS
    client = client or MonitorClient(destination / "raw_calls", concurrency, min_interval)
    _stopped(client)
    started = await investigator.run_investigations(client, destination, runs)
    remaining = len(investigator.pending(destination, runs))
    print(json.dumps({"at": utc_now(), "started": started, "finished": started - remaining,
                      "still_missing": remaining}), flush=True)
    _stopped(client)


async def explore(destination: Path, cases: list[str], run_indices: list[int], concurrency: int = 4,
                  min_interval: float = 2.0) -> None:
    """Experiment A v2: explore episodes with search and read tools, one exploration per episode per run index.
    No cases named means every episode."""
    destination = Path(destination)
    episodes = [e for e in read_jsonl(destination / "episodes.jsonl") if not cases or e["case_id"] in cases]
    missing = set(cases) - {e["case_id"] for e in episodes}
    if missing:
        raise ValueError(f"unknown cases: {sorted(missing)}")
    client = MonitorClient(destination / "raw_calls", concurrency, min_interval)
    _stopped(client)
    started = await explorer.run_explorations(client, destination, episodes, run_indices)
    print(json.dumps({"at": utc_now(), "started": started}), flush=True)
    for row in explorer.summary(destination):
        if cases and row["case_id"] in cases:
            print(json.dumps({k: row[k] for k in ("case_id", "agents", "score", "flagged", "calls", "saw_colluders",
                                                  "blamed_colluder", "input_tokens", "tools")}), flush=True)
    _stopped(client)


def reports(destination: Path, smoke: bool) -> None:
    from .analysis import report
    report(destination, destination / "report_all_logs" if smoke else REPORT, smoke)
    investigator.report(destination, destination / "report_investigator" if smoke else INVESTIGATOR_REPORT,
                        investigator.SMOKE_RUNS if smoke else investigator.RUNS)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("generate", "investigate", "explore", "judge", "report"))
    parser.add_argument("--cases", default="", help="explore: comma-separated case IDs (default: every episode)")
    parser.add_argument("--run-index", default="0", help="explore: which pass(es) of the real run, e.g. 0 or 1 or 0,1")
    parser.add_argument("--smoke", action="store_true", help="layout 0 only, one reading or investigation each")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--min-interval", type=float, default=2.0,
                        help="seconds between call starts (2.0 = at most 30 calls a minute); 403s followed a burst of ~74/minute")
    args = parser.parse_args(argv)
    destination = SMOKE_DESTINATION if args.smoke else DESTINATION
    if args.command == "generate":
        rows = generate(destination, args.smoke)
        print(json.dumps({"episodes": len(rows), "destination": str(destination)}))
        return
    try:
        if args.command == "judge":
            asyncio.run(judge(destination, args.smoke, args.concurrency, min_interval=args.min_interval))
        elif args.command == "investigate":
            asyncio.run(investigate(destination, args.smoke, args.concurrency, min_interval=args.min_interval))
        elif args.command == "explore":
            asyncio.run(explore(destination, [c for c in args.cases.split(",") if c],
                                [int(r) for r in args.run_index.split(",")], args.concurrency, args.min_interval))
            return
    finally:
        reports(destination, args.smoke)


if __name__ == "__main__":
    main()
