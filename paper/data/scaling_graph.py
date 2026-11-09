"""Step 2, Experiment B (swarmgraph/scaling/): the same explorer given a FragBench-style provenance graph of the log
(swarmgraph/scaling/graph.py) and graph tools, on a fleet of fixed size as cross-team overlap grows.

Reads logs/scaling_graph_curve/episodes.jsonl and graph_explorations.jsonl (every successful exploration of the
prompt the code names, explorer.GRAPH_PROMPT_VERSION), and each fleet's observations.jsonl to rebuild its graph. The fleets themselves are not
committed: each is checked against its committed summary, and regenerated (deterministically, with no model calls)
when missing or stale (paper/data/fleets.py). The overlap-0 fleets are Experiment A's 100-team fleets, which is
checked here through the committed prompt hashes."""

import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullLocator, PercentFormatter

from paper.data import source
from paper.data.fleets import fleet_events
from paper.ledger import Ledger
from swarmgraph.scaling import explorer, graph
from swarmgraph.scaling.design import graph_curve_cases
from swarmgraph.transfer_baseline.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "logs" / "scaling_graph_curve"
A_RUN = ROOT / "logs" / "scaling"
SPLIT, HONEST = "#eb6834", "#1baf7a"  # the A figure's split-attack and honest colors (dataviz slots 2-3, validated)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e0e0e0"
SOME = "#f6c3ae"  # the split-attack orange, lightened: a fleet caught in some of its runs
GRAPH_TOOLS = {"list_chains", "find_chains", "read_chain", "chain_of", "who_touched"}
HOW = "runs whose final score is at least 75 / runs; every layout and pass, pooled (no interval)"


def overlap_of(case_id: str) -> float:
    match = re.search(r"_overlap([0-9.]+)_", case_id)
    return float(match.group(1)) if match else 0.0


def tag(overlap: float) -> str:
    return f"{overlap:g}".replace(".", "")  # 0.5 -> "05", 4 -> "4": ledger keys use dots as separators


def observations(case_id: str, event_count: int) -> list[dict]:
    """B's curve fleet's public log, checked against its committed summary (paper/data/fleets.py)."""
    events = fleet_events(RUN, case_id, graph_curve_cases)
    assert len(events) == event_count, case_id
    return events


TOOL_KINDS = (  # the monitor's calls by kind -> (label, color): one accent (blue) for the graph, greys for the rest
    ("graph", "graph tools", "#2a78d6"),
    ("search", "text search", "#3d3c39"),
    ("read", "reading the log", "#d3d2cc"),
)


def tool_kind(tool: str) -> str:
    return "graph" if tool in GRAPH_TOOLS else "search" if tool == "search" else "read"


def style(axis: Any, overlaps: list) -> None:
    xs = list(range(len(overlaps)))
    axis.xaxis.set_major_locator(FixedLocator(xs))
    axis.set_xticklabels([f"{o:g}" for o in overlaps])
    axis.set_xlim(-0.55, xs[-1] + 0.55)
    axis.set_xlabel("tool-call overlap between teams", fontsize=8, color=INK)
    axis.tick_params(axis="both", length=0, labelsize=8, colors=INK)
    axis.grid(axis="y", color=GRID, linewidth=0.6)
    axis.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)


def draw_tools(ax: Any, data: dict) -> None:
    """The monitor's tool calls by kind at each overlap, with the split attacks it caught above each bar."""
    xs = list(range(len(data["overlaps"])))
    bottom = [0.0] * len(xs)
    for kind, label, color in TOOL_KINDS:
        shares = data["tools"][kind]
        ax.bar(xs, shares, bottom=bottom, width=0.64, color=color, label=label, edgecolor="white", linewidth=0.6,
               zorder=3)
        bottom = [b + s for b, s in zip(bottom, shares)]
    for x, (caught, total) in zip(xs, data["caught"]):
        ax.text(x, 1.03, f"{caught}/{total}", fontsize=8, color=INK, ha="center", va="bottom")
    ax.text(-0.62, 1.03, "caught:", fontsize=7.5, color=MUTED, ha="right", va="bottom")
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylabel("share of the monitor's tool calls", fontsize=8, color=INK)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.1), ncol=3, fontsize=7, frameon=False, handlelength=1.2,
              columnspacing=1.0)
    style(ax, data["overlaps"])


def draw_chains(ax: Any, data: dict) -> None:
    """The size of the chain that holds the colluders in each attack fleet: solid where every run caught it, light
    where some did, hollow where none did."""
    for (x, y, caught, runs) in data["points"]:
        fill, edge = (SPLIT, "white") if caught == runs else (SOME, SPLIT) if caught else ("white", MUTED)
        ax.plot(x, y, linestyle="none", marker="s", markersize=5, zorder=3, markerfacecolor=fill,
                markeredgecolor=edge, markeredgewidth=0.8 if caught == runs else 1.2)
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator(data["chain_ticks"]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_yticklabels([str(t) for t in data["chain_ticks"]])
    ax.set_ylim(2.3, data["agents"] * 1.6)
    ax.axhspan(2.3, data["small_limit"], color=SPLIT, alpha=0.06, linewidth=0, zorder=0)
    for level, text in ((data["agents"], "whole fleet"), (data["small_limit"], "a tenth of the fleet")):
        ax.axhline(level, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        ax.text(-0.5, level * 1.08, text, fontsize=7, color=MUTED, ha="left", va="bottom")
    ax.set_ylabel("agents in the colluders' chain (log scale)", fontsize=8, color=INK)
    ax.legend(handles=[
        Line2D([], [], linestyle="none", marker="s", markersize=6, color=SPLIT, label="every run"),
        Line2D([], [], linestyle="none", marker="s", markersize=6, markerfacecolor=SOME, markeredgecolor=SPLIT,
               markeredgewidth=1.2, label="some runs"),
        Line2D([], [], linestyle="none", marker="s", markersize=6, color=MUTED, markerfacecolor="white",
               markeredgewidth=1.2, label="no run")], title="attack caught in", title_fontsize=7,
        loc="lower center", bbox_to_anchor=(0.5, 1.06), ncol=3, fontsize=7, frameon=False, columnspacing=1.0,
        handletextpad=0.3)
    style(ax, data["overlaps"])


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
        rows.append({"case_id": r["case_id"], "run": r["run_index"], "overlap": overlap_of(r["case_id"]),
                     "layout": e["layout_variant"],
                     "condition": e["condition"], "score": r["score"], "flagged": r["score"] >= explorer.THRESHOLD,
                     "saw_all": focal <= seen, "calls": r["calls_used"], "agents": r["agents_in_fleet"],
                     "tools": [h["call"]["tool"] for h in r["history"]],
                     "input_tokens": sum((t.get("usage") or {}).get("input_tokens") or 0 for t in r["turns"])})
    # The size of the chain holding the focal team: the colluders in an attack fleet, the same three roles (and,
    # since the overlap is seeded without the run type, the same chain) in its honest twin.
    chains, logs = {}, {}
    for row, r in zip(rows, explored):
        e = episodes[row["case_id"]]
        if row["case_id"] not in chains:  # one graph per fleet, however many times it was monitored
            events = observations(row["case_id"], e["event_count"])
            built = graph.build(events)
            chains[row["case_id"]] = graph.describe(built, e["focal_agent_ids"])["colluders_chain_agents"]
            logs[row["case_id"]] = explorer.Log(events)
        row["chain"] = chains[row["case_id"]]
        row["steps"] = explorer.found_all_four_steps(r, e, logs[row["case_id"]])
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

    ledger.value("sb.explorations", len(rows), how="successful graph runs, every pass")
    ledger.value("sb.passes", len({r["run"] for r in rows}), how="passes: each monitors every fleet once")
    ledger.value("sb.agents", agents, how="agents in every fleet of the curve")
    ledger.value("sb.teams", episodes[rows[0]["case_id"]]["honest_teams"], how="honest teams in every fleet")
    ledger.value("sb.layouts", len({r["layout"] for r in rows}), how="layouts per overlap and run type")
    ledger.value("sb.busy", graph.MAX_AGENTS_PER_RESOURCE,
                 how="a record named by more agents than this counts as busy and links nothing (graph.py)")
    ledger.value("sb.graph.tools", len(explorer.GRAPH_TOOLS) - len(explorer.TOOLS),
                 how="tools the graph monitor has beyond Experiment A's")
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
    judged = [r["score"] for r in misses if r["saw_all"]]
    ledger.value("sb.misses.saw.score", ", ".join(str(v) for v in judged) or "-",
                 how="final scores of missed runs that had seen every colluder's events")
    ledger.value("sb.misses.steps", sum(r["steps"] for r in misses),
                 how="of the missed split attacks, runs that retrieved an event (in full or as a search snippet) from "
                     "each of the attack's four steps: the private read, the copy, the prepared package, the enabled "
                     "schedule (swarmgraph.scaling.explorer.found_all_four_steps)")
    ledger.value("sb.catches.steps", sum(r["steps"] for r in catches),
                 how="of the caught split attacks, runs that retrieved an event from each of the attack's four steps")
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
        [[f"{o:g}", ", ".join(str(next(r["chain"] for r in cells[(o, "split_attack")] if r["layout"] == layout))
                              for layout in sorted({r["layout"] for r in cells[(o, "split_attack")]})),
          *(f"{sum(map(flagged, cells[(o, c)]))}/{len(cells[(o, c)])}" for c in ("split_attack", "honest_authorized")),
          f"{sum(c['tool'] in GRAPH_TOOLS for c in calls if c['overlap'] == o) / sum(c['overlap'] == o for c in calls):.0%}",
          f"{median(r['calls'] for r in rows if r['overlap'] == o):.0f}",
          f"{median(r['input_tokens'] for r in rows if r['overlap'] == o) / 1000:,.0f}K"] for o in overlaps],
        how=HOW)
    jitter = {0: -0.27, 1: -0.09, 2: 0.09, 3: 0.27}  # layouts side by side, so squares don't hide each other
    shares = {kind: [] for kind, _, _ in TOOL_KINDS}
    for o in overlaps:
        kinds = Counter(tool_kind(c["tool"]) for c in calls if c["overlap"] == o)
        for kind in shares:
            shares[kind].append(kinds[kind] / sum(kinds.values()))
    ledger.figure("sb-tools", draw_tools, {
        "overlaps": overlaps, "tools": shares,
        "caught": [(sum(map(flagged, cells[(o, "split_attack")])), len(cells[(o, "split_attack")])) for o in overlaps]},
        how=f"{HOW}; the monitor's tool calls by kind, every run, with split attacks caught above", size=(3.2, 3.0))
    ledger.figure("sb-figure", draw_chains, {
        "overlaps": overlaps, "agents": agents, "small_limit": small_limit, "chain_ticks": [3, 10, 30, 100, agents],
        "points": [(overlaps.index(fleet[0]["overlap"]) + jitter[fleet[0]["layout"]], fleet[0]["chain"],
                    sum(map(flagged, fleet)), len(fleet))
                   for fleet in (([r for r in split if r["case_id"] == c]) for c in sorted({r["case_id"] for r in split}))]},
        how=f"{HOW}; one square per attack fleet, by how many of its runs flagged it", size=(3.2, 3.0))
