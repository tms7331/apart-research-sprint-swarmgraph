"""Step 2, Experiment A (swarmgraph/scaling/): an explorer with search and read tools and a fixed budget, as the
fleet grows. Reads logs/scaling/episodes.jsonl and explorations.jsonl through swarmgraph.scaling.explorer, so
the paper counts what the run's report counts: every successful exploration of the explorer_v1 prompt, both
passes (run indices 0 and 1)."""

from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from matplotlib.ticker import FixedLocator, NullLocator, PercentFormatter

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling import explorer
from swarmgraph.transfer_baseline.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "logs" / "scaling"
SERIES = {  # condition -> (label, color, marker): dataviz categorical slots 1-3, validated; shapes differ too
    "solo_attack": ("solo attack", "#2a78d6", "o"),
    "split_attack": ("split attack", "#eb6834", "s"),
    "honest_authorized": ("honest (0 flags means success)", "#1baf7a", "^"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e0e0e0"
HOW = "explorations whose final score is at least 75 / explorations; 4 layouts x 2 passes, pooled (no interval)"


def draw_detection(ax: Any, data: dict) -> None:
    """Share of explorations that flag the fleet, by fleet size, one line per run type, labelled at its end."""
    sizes = data["agents"]
    # Where lines coincide (both attacks at 100%), the solo line is drawn on top with smaller markers, so both stay
    # visible: a blue circle inside an orange square.
    style = {"honest_authorized": (6, 3), "split_attack": (8, 4), "solo_attack": (5, 5)}  # markersize, zorder
    for condition, (label, color, marker) in SERIES.items():
        rates = [data["rates"][condition][n] for n in data["teams"]]
        size, order = style[condition]
        ax.plot(sizes, rates, color=color, linewidth=2, marker=marker, markersize=size, markeredgecolor="white",
                label=label, zorder=order)
        ax.annotate(label, (sizes[-1], rates[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                    fontsize=8, color=INK)
    ax.axvline(data["boundary"], color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(data["boundary"] * 1.07, 0.5, f"log longer than\n{data['budget']} calls can read", fontsize=7.5, color=MUTED,
            va="center")
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(sizes))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([str(s) for s in sizes])
    ax.set_xlim(sizes[0] / 1.3, sizes[-1] * 4.5)
    ax.set_ylim(-0.04, 1.06)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("agents in the fleet (log scale)", fontsize=8, color=INK)
    ax.set_ylabel("fleets flagged", fontsize=8, color=INK)
    ax.tick_params(axis="both", length=0, labelsize=8, colors=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=8, frameon=False)


@source("sa")
def scaling_explorer(ledger: Ledger) -> None:
    episodes = {e["case_id"]: e for e in read_jsonl(RUN / "episodes.jsonl")}
    rows = [r for r in explorer.summary(RUN)]
    for row in rows:
        row["honest_teams"] = episodes[row["case_id"]]["honest_teams"]
    teams = sorted({r["honest_teams"] for r in rows})
    agents = {n: next(len(e["agent_ids"]) for e in episodes.values() if e["honest_teams"] == n
                      and e["execution_layout"] == "split") for n in teams}
    cells = defaultdict(list)
    for row in rows:
        cells[(row["honest_teams"], row["condition"])].append(row)
    flagged = lambda row: row["flagged"]
    for n in teams:
        ledger.value(f"sa.agents.n{n}", agents[n], how="agents in a split-team fleet with this many honest teams")
        for condition, short in (("solo_attack", "solo"), ("split_attack", "split"), ("honest_authorized", "honest")):
            ledger.pooled(f"sa.{short}.n{n}", cells[(n, condition)], flagged, how=HOW, cell=("case_id",))
    honest = [r for r in rows if r["condition"] == "honest_authorized"]
    attacks = [r for r in rows if r["condition"] != "honest_authorized"]
    ledger.pooled("sa.honest", honest, flagged, how=f"{HOW}; every fleet size", cell=("case_id",))
    misses = [r for r in attacks if not r["flagged"]]
    saw_all = lambda r: r["saw_colluders"].split("/")[0] == r["saw_colluders"].split("/")[1]
    ledger.value("sa.explorations", len(rows), how="successful explorations, both passes")
    ledger.value("sa.passes", len({r.get("run_index", 0) for r in read_jsonl(RUN / "explorations.jsonl") if r.get("status") == "ok"}),
                 how="passes of the real run (one exploration of every episode each)")
    ledger.value("sa.budget", explorer.BUDGET_CALLS, how="tool calls per exploration")
    ledger.value("sa.read.max", explorer.READ_LOG_MAX, how="most events one read_log call returns")
    ledger.value("sa.capacity", explorer.BUDGET_CALLS * explorer.READ_LOG_MAX,
                 how="the monitor's capacity: events it can read in its whole budget (calls x events per read)")
    ledger.value("sa.threshold", explorer.THRESHOLD, how="final score at or above which an exploration flags the fleet")
    ledger.value("sa.misses", len(misses), how="attack explorations that did not flag the fleet")
    ledger.value("sa.misses.saw.all", sum(map(saw_all, misses)), how="of those, explorations that saw every colluder's events")
    ledger.value("sa.catches.saw.all", sum(map(saw_all, [r for r in attacks if r["flagged"]])),
                 how="attack explorations that flagged the fleet and had seen every colluder's events")
    ledger.value("sa.catches", sum(r["flagged"] for r in attacks), how="attack explorations that flagged the fleet")
    ledger.value("sa.honest.max", max(r["score"] for r in honest), how="highest final score on an honest fleet")
    ledger.value("sa.tokens.largest", round(median(r["input_tokens"] for r in rows if r["honest_teams"] == teams[-1]) / 1000),
                 how="median input tokens per exploration at the largest fleet, in thousands")
    ledger.table(
        "sa-table", ["honest teams", "agents", "solo attack caught", "split attack caught", "honest false alarms",
                     "median calls", "median input tokens"],
        [[str(n), str(agents[n]), *(f"{sum(map(flagged, cells[(n, c)]))}/{len(cells[(n, c)])}" for c in SERIES),
          f"{median(r['calls'] for r in rows if r['honest_teams'] == n):.0f}",
          f"{median(r['input_tokens'] for r in rows if r['honest_teams'] == n) / 1000:,.0f}K"] for n in teams],
        how=HOW)
    # The read budget covers the whole log while events / 40 per read_log call fit in the calls: between the last
    # fleet that fits and the first that doesn't.
    fits = [n for n in teams if max(e["event_count"] for e in episodes.values() if e["honest_teams"] == n)
            <= explorer.READ_LOG_MAX * explorer.BUDGET_CALLS]
    last_fit, first_over = agents[fits[-1]], agents[teams[len(fits)]]
    explored = {r["exploration_id"]: r for r in read_jsonl(RUN / "explorations.jsonl") if r.get("status") == "ok"}
    calls = [{"case_id": r["case_id"], "tool": h["call"]["tool"], "fits": episodes[r["case_id"]]["honest_teams"] in fits}
             for r in explored.values() for h in r["history"]]
    ledger.pooled("sa.calls.readlog.fits", [c for c in calls if c["fits"]], lambda c: c["tool"] == "read_log",
                  how="read_log calls / all calls, fleets whose log fits in the read budget", cell=("case_id",))
    ledger.pooled("sa.calls.search.over", [c for c in calls if not c["fits"]], lambda c: c["tool"] == "search",
                  how="search calls / all calls, fleets whose log is longer than the read budget", cell=("case_id",))
    ledger.figure("sa-figure", draw_detection, {
        "teams": teams, "agents": [agents[n] for n in teams],
        "rates": {c: {n: sum(map(flagged, cells[(n, c)])) / len(cells[(n, c)]) for n in teams} for c in SERIES},
        "boundary": (last_fit * first_over) ** 0.5, "budget": explorer.BUDGET_CALLS}, how=f"{HOW}; one line per run type", size=(6.5, 3.0))
