"""Step 2, Experiment B (swarmgraph/scaling/): the same explorer given a FragBench-style provenance graph of the log
(swarmgraph/scaling/graph.py) and graph tools, on a fleet of fixed size as cross-team overlap grows.

Reads logs/scaling_graph_curve/episodes.jsonl and graph_explorations.jsonl (every successful exploration of the
explorer_graph_v2 prompt), and each fleet's observations.jsonl to rebuild its graph. The fleets themselves are not
committed: a missing one is regenerated (deterministically, with no model calls) into a temporary directory and
checked against its committed event count. The overlap-0 fleets are Experiment A's 100-team fleets, which is
checked here through the committed prompt hashes."""

import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullLocator, PercentFormatter

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling import explorer, graph
from swarmgraph.scaling.design import graph_curve_cases
from swarmgraph.scaling.fleet import generate_fleet_episode
from swarmgraph.transfer_baseline.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "logs" / "scaling_graph_curve"
A_RUN = ROOT / "logs" / "scaling"
SPLIT, HONEST = "#eb6834", "#1baf7a"  # the A figure's split-attack and honest colors (dataviz slots 2-3, validated)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e0e0e0"
GRAPH_TOOLS = {"list_chains", "find_chains", "read_chain", "chain_of", "who_touched"}
HOW = "explorations whose final score is at least 75 / explorations; one per layout (4), pooled (no interval)"


def overlap_of(case_id: str) -> float:
    match = re.search(r"_overlap([0-9.]+)_", case_id)
    return float(match.group(1)) if match else 0.0


def tag(overlap: float) -> str:
    return f"{overlap:g}".replace(".", "")  # 0.5 -> "05", 4 -> "4": ledger keys use dots as separators


def observations(case_id: str, event_count: int) -> list[dict]:
    path = RUN / "episodes" / case_id / "observations.jsonl"
    if path.exists():
        return read_jsonl(path)
    case = next(c for c in graph_curve_cases() if c["case_id"] == case_id)
    with tempfile.TemporaryDirectory() as tmp:
        generate_fleet_episode(Path(tmp), case)
        events = read_jsonl(Path(tmp) / case_id / "observations.jsonl")
    if len(events) != event_count:
        raise ValueError(f"{case_id}: regenerated {len(events)} events, the committed row says {event_count}")
    return events


def draw_graph(ax: Any, data: dict) -> None:
    """Left: share of explorations that flag the fleet, by overlap. Right: the size of the chain that holds the
    colluders in each attack fleet, filled where the explorer caught the attack."""
    fig = ax.figure
    ax.remove()
    left, right = fig.subplots(1, 2, gridspec_kw={"wspace": 0.42})
    overlaps = data["overlaps"]
    left.plot(overlaps, data["split"], color=SPLIT, linewidth=2, marker="s", markersize=7, markeredgecolor="white",
              label="split attack", zorder=3)
    left.plot(overlaps, data["honest"], color=HONEST, linewidth=2, marker="^", markersize=7, markeredgecolor="white",
              label="honest (false alarm)", zorder=3)
    left.plot([0], [data["a_split"]], linestyle="none", marker="D", markersize=6, color=MUTED, zorder=4,
              label="split attack, no graph")
    left.set_ylim(-0.04, 1.06)
    left.yaxis.set_major_formatter(PercentFormatter(1.0))
    left.set_title("explorations that flag the fleet", fontsize=8, color=INK, loc="left")
    left.legend(loc="center right", bbox_to_anchor=(1.0, 0.72), fontsize=7, frameon=False)
    for (x, y, caught) in data["points"]:
        right.plot(x, y, linestyle="none", marker="s", markersize=5, color=SPLIT, markeredgewidth=1.5,
                   markerfacecolor=SPLIT if caught else "white", zorder=3)
    right.set_yscale("log")
    right.yaxis.set_major_locator(FixedLocator(data["chain_ticks"]))
    right.yaxis.set_minor_locator(NullLocator())
    right.set_yticklabels([str(t) for t in data["chain_ticks"]])
    right.set_ylim(2.3, data["agents"] * 1.5)
    for level, text in ((data["agents"], "whole fleet"), (data["small_limit"], "a tenth of the fleet")):
        right.axhline(level, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        right.text(overlaps[-1] + 0.45, level * 1.08, text, fontsize=7, color=MUTED, ha="right", va="bottom")
    right.set_title("agents in the colluders' chain (log scale)", fontsize=8, color=INK, loc="left")
    right.legend(handles=[
        Line2D([], [], linestyle="none", marker="s", markersize=6, color=SPLIT, label="caught"),
        Line2D([], [], linestyle="none", marker="s", markersize=6, color=SPLIT, markerfacecolor="white",
               markeredgewidth=1.5, label="missed")], loc="lower right", fontsize=7, frameon=False)
    for axis in (left, right):
        axis.xaxis.set_major_locator(FixedLocator(overlaps))
        axis.set_xticklabels([f"{o:g}" for o in overlaps])
        axis.set_xlim(-0.45, overlaps[-1] + 0.45)
        axis.set_xlabel("overlap (shared indexes per team)", fontsize=8, color=INK)
        axis.tick_params(axis="both", length=0, labelsize=8, colors=INK)
        axis.grid(axis="y", color=GRID, linewidth=0.6)
        axis.set_axisbelow(True)
        for side in ("top", "right", "left"):
            axis.spines[side].set_visible(False)
        axis.spines["bottom"].set_color(GRID)


@source("sb")
def scaling_graph(ledger: Ledger) -> None:
    episodes = {e["case_id"]: e for e in read_jsonl(RUN / "episodes.jsonl")}
    explored = [r for r in read_jsonl(RUN / explorer.GRAPH_LOG) if r.get("status") == "ok"]
    rows = []
    for r in explored:
        e = episodes[r["case_id"]]
        focal = set(e["focal_agent_ids"])
        seen = {ev["agent_id"] for h in r["history"] for key in ("events", "results")
                for ev in h["result"].get(key) or [] if isinstance(ev, dict) and ev.get("agent_id")}
        rows.append({"case_id": r["case_id"], "overlap": overlap_of(r["case_id"]), "layout": e["layout_variant"],
                     "condition": e["condition"], "score": r["score"], "flagged": r["score"] >= explorer.THRESHOLD,
                     "saw_all": focal <= seen, "calls": r["calls_used"], "agents": r["agents_in_fleet"],
                     "tools": [h["call"]["tool"] for h in r["history"]],
                     "input_tokens": sum((t.get("usage") or {}).get("input_tokens") or 0 for t in r["turns"])})
    # The size of the chain holding the focal team: the colluders in an attack fleet, the same three roles (and,
    # since the overlap is seeded without the run type, the same chain) in its honest twin.
    for row in rows:
        e = episodes[row["case_id"]]
        built = graph.build(observations(row["case_id"], e["event_count"]))
        row["chain"] = graph.describe(built, e["focal_agent_ids"])["colluders_chain_agents"]
    overlaps = sorted({r["overlap"] for r in rows})
    agents = {r["agents"] for r in rows}
    assert len(agents) == 1, agents
    agents = agents.pop()
    cells = defaultdict(list)
    for row in rows:
        cells[(row["overlap"], row["condition"])].append(row)
    flagged = lambda row: row["flagged"]
    split = [r for r in rows if r["condition"] == "split_attack"]
    honest = [r for r in rows if r["condition"] == "honest_authorized"]

    ledger.value("sb.explorations", len(rows), how="successful graph explorations, one per fleet")
    ledger.value("sb.agents", agents, how="agents in every fleet of the curve")
    ledger.value("sb.teams", episodes[rows[0]["case_id"]]["honest_teams"], how="honest teams in every fleet")
    ledger.value("sb.layouts", len({r["layout"] for r in rows}), how="layouts, one exploration each, per overlap and run type")
    a_rows = {e["case_id"]: e for e in read_jsonl(A_RUN / "episodes.jsonl")}
    zero = [c for c in episodes if overlap_of(c) == 0]
    same = [c for c in zero if c in a_rows and [v["prompt_sha256"] for v in a_rows[c]["views"]]
            == [v["prompt_sha256"] for v in episodes[c]["views"]]]
    ledger.value("sb.same.fleets", len(same), how="overlap-0 fleets whose public log hashes match Experiment A's")
    ledger.value("sb.zero.fleets", len(zero), how="overlap-0 fleets on the curve")
    for o in overlaps:
        t = tag(o)
        ledger.pooled(f"sb.split.o{t}", cells[(o, "split_attack")], flagged, how=HOW, cell=("case_id",))
        ledger.pooled(f"sb.honest.o{t}", cells[(o, "honest_authorized")], flagged, how=HOW, cell=("case_id",))
        sizes = [r["chain"] for r in cells[(o, "split_attack")]]
        ledger.value(f"sb.chain.o{t}", f"{min(sizes)}" if min(sizes) == max(sizes) else f"{min(sizes)}–{max(sizes)}",
                     how="agents in the chain that holds the colluders, smallest to largest over layouts")
    ledger.pooled("sb.honest", honest, flagged, how=f"{HOW}; every overlap", cell=("case_id",))
    ledger.value("sb.honest.max", max(r["score"] for r in honest), how="highest final score on an honest fleet")
    small_limit = agents // 10
    ledger.value("sb.small.limit", small_limit, how="a tenth of the fleet, in agents")
    ledger.pooled("sb.small.caught", [r for r in split if r["chain"] <= small_limit], flagged,
                  how="split-attack explorations that flag the fleet / those whose colluders' chain is at most a tenth "
                      "of the fleet", cell=("case_id",))
    ledger.pooled("sb.large.caught", [r for r in split if r["chain"] > small_limit], flagged,
                  how="split-attack explorations that flag the fleet / those whose colluders' chain is larger than a "
                      "tenth of the fleet", cell=("case_id",))
    misses, catches = [r for r in split if not r["flagged"]], [r for r in split if r["flagged"]]
    ledger.value("sb.misses", len(misses), how="split-attack explorations that did not flag the fleet")
    ledger.value("sb.misses.saw.all", sum(r["saw_all"] for r in misses),
                 how="of those, explorations that saw every colluder's events")
    ledger.value("sb.catches", len(catches), how="split-attack explorations that flagged the fleet")
    ledger.value("sb.catches.saw.all", sum(r["saw_all"] for r in catches),
                 how="of those, explorations that saw every colluder's events")
    calls = [{"case_id": r["case_id"], "overlap": r["overlap"], "tool": tool} for r in rows for tool in r["tools"]]
    for o in (overlaps[0], overlaps[-1]):
        at = [c for c in calls if c["overlap"] == o]
        ledger.pooled(f"sb.calls.graph.o{tag(o)}", at, lambda c: c["tool"] in GRAPH_TOOLS,
                      how=f"graph-tool calls / all calls at overlap {o:g}", cell=("case_id",))
        ledger.pooled(f"sb.calls.search.o{tag(o)}", at, lambda c: c["tool"] == "search",
                      how=f"search calls / all calls at overlap {o:g}", cell=("case_id",))
    ledger.table(
        "sb-table", ["overlap", "agents in the colluders' chain, by layout", "split attack caught",
                     "honest false alarms", "graph-tool calls", "median calls", "median input tokens"],
        [[f"{o:g}", ", ".join(str(r["chain"]) for r in sorted(cells[(o, "split_attack")], key=lambda r: r["layout"])),
          *(f"{sum(map(flagged, cells[(o, c)]))}/{len(cells[(o, c)])}" for c in ("split_attack", "honest_authorized")),
          f"{sum(c['tool'] in GRAPH_TOOLS for c in calls if c['overlap'] == o) / sum(c['overlap'] == o for c in calls):.0%}",
          f"{median(r['calls'] for r in rows if r['overlap'] == o):.0f}",
          f"{median(r['input_tokens'] for r in rows if r['overlap'] == o) / 1000:,.0f}K"] for o in overlaps],
        how=HOW)
    a_split = [r for r in explorer.summary(A_RUN) if r["case_id"] in same and r["condition"] == "split_attack"]
    jitter = {0: -0.18, 1: -0.06, 2: 0.06, 3: 0.18}  # layouts side by side, so squares don't hide each other
    ledger.figure("sb-figure", draw_graph, {
        "overlaps": overlaps, "agents": agents, "small_limit": small_limit,
        "chain_ticks": [3, 10, 30, 100, agents],
        "split": [sum(map(flagged, cells[(o, "split_attack")])) / len(cells[(o, "split_attack")]) for o in overlaps],
        "honest": [sum(map(flagged, cells[(o, "honest_authorized")])) / len(cells[(o, "honest_authorized")])
                   for o in overlaps],
        "a_split": sum(r["flagged"] for r in a_split) / len(a_split),
        "points": [(r["overlap"] + jitter[r["layout"]], r["chain"], r["flagged"]) for r in split]},
        how=f"{HOW}; right panel: one square per attack fleet, filled where it was flagged", size=(6.5, 3.0))
