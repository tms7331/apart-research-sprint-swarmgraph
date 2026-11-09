"""Experiments A-C: generate the fleets, run the monitors on them, and report.

    uv run python -m swarmgraph.scaling generate [--smoke]      # A's fleets: deterministic, no model calls
    uv run python -m swarmgraph.scaling explore --run-index 0,1 # Experiment A: the missing explorations
    uv run python -m swarmgraph.scaling report [--smoke]        # Experiment A's report (reports/scaling_explorer/)
    uv run python -m swarmgraph.scaling graph-curve             # B's curve fleets: deterministic, no model calls
    uv run python -m swarmgraph.scaling explore-graph --curve --run-index 0,1,2,3  # Experiment B
    uv run python -m swarmgraph.scaling flow --run-index 0,1    # Experiment C (flow.py): fleets, Jev labels, judge
    uv run python -m swarmgraph.scaling flow-report [--smoke]   # Experiment C's flag rates
    uv run python -m swarmgraph.scaling flow-roles [--smoke]    # C's judged groups' teams and roles (no model calls)

Every model command resumes: it skips work already in its log. The raw Codex CLI archive goes to
<destination>/raw_calls/, which Git ignores.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from swarmgraph.transfer_baseline.io import read_jsonl, utc_now
from swarmgraph.transfer_baseline.run import MonitorClient

from . import explorer, graph
from .design import DESTINATION, EXPLORER_REPORT, SMOKE_DESTINATION, generate


def _stopped(client) -> None:
    if getattr(client, "stopped", False):
        raise RuntimeError("A stop marker exists in raw_calls/ (access, safety or usage restriction); "
                           "saved results are kept and the run resumes later")


async def explore(destination: Path, cases: list[str], run_indices: list[int], concurrency: int = 4,
                  min_interval: float = 2.0, retry_forbidden: bool = False) -> None:
    """Experiment A v2: explore episodes with search and read tools, one exploration per episode per run index.
    No cases named means every episode."""
    destination = Path(destination)
    episodes = [e for e in read_jsonl(destination / "episodes.jsonl") if not cases or e["case_id"] in cases]
    missing = set(cases) - {e["case_id"] for e in episodes}
    if missing:
        raise ValueError(f"unknown cases: {sorted(missing)}")
    client = MonitorClient(destination / "raw_calls", concurrency, min_interval,
                           retry_forbidden=retry_forbidden)
    _stopped(client)
    started = await explorer.run_explorations(client, destination, episodes, run_indices)
    print(json.dumps({"at": utc_now(), "started": started}), flush=True)
    for row in explorer.summary(destination):
        if cases and row["case_id"] in cases:
            print(json.dumps({k: row[k] for k in ("case_id", "agents", "score", "flagged", "calls", "saw_colluders",
                                                  "blamed_colluder", "input_tokens", "tools")}), flush=True)
    _stopped(client)


def reports(destination: Path, smoke: bool) -> None:
    if (destination / explorer.LOG).exists():
        explorer.report(destination, destination / "report_explorer" if smoke else EXPLORER_REPORT)


def graph_sandbox(curve: bool = False) -> None:
    """Experiment B: generate the sandbox (or the curve's) fleets and show how the graph splits them into chains."""
    from .design import (GRAPH_CURVE, GRAPH_CURVE_DESTINATION, GRAPH_DESTINATION, GRAPH_SANDBOX, graph_curve_cases,
                         graph_sandbox_cases)
    destination = GRAPH_CURVE_DESTINATION if curve else GRAPH_DESTINATION
    cases, spec = (graph_curve_cases(), GRAPH_CURVE) if curve else (graph_sandbox_cases(), GRAPH_SANDBOX)
    rows = generate(destination, cases=cases, design={"experiment": "B curve" if curve else "B sandbox", **spec})
    for row in rows:
        events = read_jsonl(destination / "episodes" / row["case_id"] / "observations.jsonl")
        built = graph.build(events)
        print(json.dumps({"case_id": row["case_id"], "agents": len(row["agent_ids"]),
                          **graph.describe(built, row["colluding_agent_ids"])}), flush=True)


def fallback_client(root: Path, enabled: bool, concurrency: int):
    """OpenRouter, same model, for quick runs (``--fallback``); None for full runs."""
    if not enabled:
        return None
    from swarmgraph.transfer_baseline.openrouter import OpenRouterClient, load_key
    key = load_key()
    if not key:
        raise RuntimeError("--fallback needs OPENROUTER_KEY in the environment or .env")
    return OpenRouterClient(root, key, concurrency)


async def explore_graph(cases: list[str], plain: bool, concurrency: int = 8, fallback: bool = False,
                        curve: bool = False, run_indices: tuple = (0,), retry_forbidden: bool = False) -> None:
    """Experiment B: explore the sandbox (or, with curve, the curve's) fleets with graph tools, or A's with plain."""
    from .design import GRAPH_CURVE_DESTINATION, GRAPH_DESTINATION
    GRAPH_DESTINATION = GRAPH_CURVE_DESTINATION if curve else GRAPH_DESTINATION
    mode = explorer.LOG_MODE if plain else explorer.GRAPH_MODE
    episodes = [e for e in read_jsonl(GRAPH_DESTINATION / "episodes.jsonl") if not cases or e["case_id"] in cases]
    client = MonitorClient(GRAPH_DESTINATION / "raw_calls", concurrency,
                           fallback=fallback_client(GRAPH_DESTINATION / "raw_calls", fallback, concurrency),
                           retry_forbidden=retry_forbidden)
    _stopped(client)
    await explorer.run_explorations(client, GRAPH_DESTINATION, episodes, list(run_indices), mode)
    rows = {r["case_id"]: r for r in read_jsonl(GRAPH_DESTINATION / mode.log) if r.get("status") == "ok"}
    for episode in episodes:
        r = rows.get(episode["case_id"])
        if r:
            colluders = set(episode["colluding_agent_ids"])
            print(json.dumps({"mode": mode.prompt_version, "case_id": r["case_id"], "score": r["score"],
                              "providers": sorted({t.get("provider", "codex") for t in r["turns"]}),
                              "calls": r["calls_used"], "tools": r["tools_used"],
                              "blamed_colluder": bool(set(r["suspected_agent_ids"]) & colluders)}), flush=True)
    _stopped(client)


async def flow_run(smoke: bool, run_indices: list[int], cases: list[str], concurrency: int, fallback: bool,
                   retry_forbidden: bool, jev_workers: int) -> None:
    """Experiment C: generate the missing fleets, label them with Jev (OpenRouter), simulate, then judge each pass."""
    from swarmgraph.transfer_baseline.openrouter import load_key

    from . import flow, jev
    from .design import FLOW_DESTINATION, FLOW_SMOKE_DESTINATION
    destination = FLOW_SMOKE_DESTINATION if smoke else FLOW_DESTINATION
    key = load_key()
    if not key:
        raise RuntimeError("Experiment C's labels need OPENROUTER_KEY in the environment or .env (Jev runs only on OpenRouter)")
    labeler = jev.JevClient(destination / "jev_cache", key, workers=jev_workers)
    client = MonitorClient(destination / "raw_calls", concurrency,
                           fallback=fallback_client(destination / "raw_calls", fallback, concurrency),
                           retry_forbidden=retry_forbidden)
    _stopped(client)
    await flow.run(destination, client, labeler, run_indices, smoke, cases)
    print(flow.summary(destination))
    print(json.dumps({"jev_paid_calls": labeler.paid_calls, "jev_usd": round(labeler.usd, 4)}))
    _stopped(client)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("generate", "explore", "report", "graph-sandbox",
                                            "explore-graph", "graph-curve", "flow", "flow-report", "flow-roles"))
    parser.add_argument("--curve", action="store_true", help="explore-graph: the curve's fleets, not the sandbox")
    parser.add_argument("--plain", action="store_true", help="explore-graph: A's explorer (no graph tools) on the graph fleets")
    parser.add_argument("--fallback", action="store_true",
                        help="quick runs only: on a subscription 403, switch to OpenRouter (same model)")
    parser.add_argument("--cases", default="", help="explore: comma-separated case IDs (default: every episode)")
    parser.add_argument("--run-index", default="0", help="explore: which pass(es) of the real run, e.g. 0 or 1 or 0,1")
    parser.add_argument("--retry-forbidden", action="store_true",
                        help="explore/explore-graph: retry generic HTTP 403s after a shared 60-second cooldown; explicit safety/auth/usage failures still stop")
    parser.add_argument("--smoke", action="store_true", help="A: layout 0 only; C: four small fleets (separate gitignored folders)")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--jev-workers", type=int, default=32, help="flow: parallel Jev requests")
    parser.add_argument("--min-interval", type=float, default=0.0,
                        help="seconds between call starts (2.0 = at most 30 calls a minute); 403s followed a burst of ~74/minute")
    args = parser.parse_args(argv)
    destination = SMOKE_DESTINATION if args.smoke else DESTINATION
    if args.command in ("graph-sandbox", "graph-curve"):
        graph_sandbox(curve=args.command == "graph-curve")
        return
    if args.command == "flow":
        asyncio.run(flow_run(args.smoke, [int(r) for r in args.run_index.split(",")],
                             [c for c in args.cases.split(",") if c], args.concurrency, args.fallback,
                             args.retry_forbidden, args.jev_workers))
        return
    if args.command == "flow-report":
        from . import flow
        from .design import FLOW_DESTINATION, FLOW_SMOKE_DESTINATION
        print(flow.summary(FLOW_SMOKE_DESTINATION if args.smoke else FLOW_DESTINATION))
        return
    if args.command == "flow-roles":
        from .design import FLOW_DESTINATION, FLOW_SMOKE_DESTINATION
        from .flow_roles import GROUP_ROLES_LOG, group_roles
        rows = group_roles(FLOW_SMOKE_DESTINATION if args.smoke else FLOW_DESTINATION, args.smoke)
        print(json.dumps({"fleets": len(rows), "written": GROUP_ROLES_LOG}))
        return
    if args.command == "explore-graph":
        asyncio.run(explore_graph([c for c in args.cases.split(",") if c], args.plain, args.concurrency, args.fallback,
                                  args.curve, tuple(int(r) for r in args.run_index.split(",")),
                                  retry_forbidden=args.retry_forbidden))
        return
    if args.command == "generate":
        rows = generate(destination, args.smoke)
        print(json.dumps({"episodes": len(rows), "destination": str(destination)}))
        return
    try:
        if args.command == "explore":
            asyncio.run(explore(destination, [c for c in args.cases.split(",") if c],
                                [int(r) for r in args.run_index.split(",")], args.concurrency, args.min_interval,
                                retry_forbidden=args.retry_forbidden))
            return
    finally:
        reports(destination, args.smoke)


if __name__ == "__main__":
    main()
