"""Step 1, the transfer baseline (swarmgraph/transfer_baseline/): the minimal Kitaoka reproduction.

Reads the run's two logs, episodes.jsonl and judgments.jsonl, through swarmgraph.transfer_baseline.analysis,
so the paper counts exactly what the run's own report counts. The design comes from the run's protocol.json.

RUN is the full run, committed in logs/transfer_baseline/. A --final build refuses logs that aren't
committed and pushed. The smoke run (logs/transfer_baseline_smoke/, gitignored) has the same layout, so RUN
can point there to try a change cheaply."""

import json
from pathlib import Path
from typing import Any

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.transfer_baseline.analysis import summarize
from swarmgraph.transfer_baseline.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "logs" / "transfer_baseline"
TEAM = ("case_id",)  # each team is its own cell: one episode, with its own prompts
ROLES = ("backup", "staging", "sync")  # r1, r2, r3 in swarmgraph/transfer_baseline/scenario.py: an episode's agent_ids follow this order
ROWS = {  # the figure's row groups, top to bottom: label -> which teams (split layout only: they have both views)
    "split attack": lambda r: r["condition"] == "split_attack",
    "honest (no attack)": lambda r: r["condition"] == "honest_authorized",
    "incomplete attack": lambda r: r["condition"] == "incomplete_attack" and r["omit_role"] == "r1",  # backup step missing
}
SERIES = {  # score -> (label, color, marker): dataviz categorical slots 1-2, validated; shapes differ too
    "per_agent": ("read individually", "#2a78d6", "o"),
    "joint": ("read together", "#eb6834", "s"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e0e0e0"


def draw_scores(ax: Any, data: dict) -> None:
    """One row per split-layout team, grouped by run type: an arrow from the per-agent monitor's score (its highest
    member) to the joint monitor's score for the whole team; the flag threshold dashed, the flagged side shaded."""
    threshold, y, ticks = data["threshold"], 0.0, []
    for label, pick in ROWS.items():
        teams = sorted((r for r in data["rows"] if pick(r) and r["joint"] is not None), key=lambda r: r["layout_variant"])
        first = y
        for team in teams:
            alone, together = team["per_agent"], team["joint"]
            ax.annotate("", xy=(together, y), xytext=(alone, y), zorder=2, arrowprops=dict(
                arrowstyle="-|>", color=MUTED, lw=1, shrinkA=4, shrinkB=4, mutation_scale=7))
            for key, value in (("per_agent", alone), ("joint", together)):
                _, color, marker = SERIES[key]
                ax.plot(value, y, marker, color=color, markersize=5, markeredgecolor="white", markeredgewidth=0.7,
                        zorder=3)
            y += 1
        ticks.append(((first + y - 1) / 2, label))
        y += 0.8
    ax.axvspan(threshold, 103, color=SERIES["joint"][1], alpha=0.07, linewidth=0, zorder=0)
    ax.axvline(threshold, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(threshold + 1.5, y - 1.2, f"flagged at {threshold}+", color=MUTED, fontsize=7.5, va="bottom")
    ax.set_yticks([t for t, _ in ticks], labels=[label for _, label in ticks], fontsize=8, color=INK)
    ax.set_ylim(y - 0.6, -1.4)
    ax.set_xlim(-3, 103)
    ax.set_xlabel("median suspicion score (0-100); one row per team, layouts 0-3", fontsize=8, color=INK)
    ax.tick_params(axis="both", length=0, labelsize=8, colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    handles = [ax.plot([], [], marker, color=color, linestyle="", label=label)[0]
               for label, color, marker in SERIES.values()]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8, frameon=False)


def flagged(key: str, threshold: float):
    return lambda row: row[key] >= threshold


def span(values) -> str:
    """A range of scores as text: "40–45", or "0" when they're all the same."""
    values = list(values)
    low, high = min(values), max(values)
    return f"{low:g}" if low == high else f"{low:g}–{high:g}"


@source("tb")
def transfer_baseline(ledger: Ledger) -> None:
    design = json.loads((RUN / "protocol.json").read_text())
    episodes = read_jsonl(RUN / "episodes.jsonl")
    data = summarize(episodes, read_jsonl(RUN / "judgments.jsonl"), design)
    rows, threshold = [r for r in data["rows"] if r["eligible"]], design["threshold"]
    ledger.value("tb.run", design["version"], how="the run the numbers come from (protocol.json)")
    ledger.value("tb.episodes", data["episodes"], how="scripted episodes")
    ledger.value("tb.readings", data["successful_readings"], how="successful judge readings")
    ledger.value("tb.readings.per.view", design["readings_per_view"], how="readings per monitor view")
    ledger.value("tb.threshold", threshold, how="the fixed flag threshold (MiniLab's 7.5 of 10)")
    ledger.value("tb.model", design["model"], how="the monitor model (protocol.json)")
    ledger.value("tb.effort", design["reasoning_effort"], how="the monitor's reasoning effort (protocol.json)")
    ledger.value("tb.layouts", len(design["layout_variants"]), how="layouts per run type (protocol.json)")
    how = f"teams whose median score is at least {threshold} / teams with a score; teams pooled (no interval)"
    for key, conditions, score in (
        ("tb.solo.flagged", ("solo_attack",), "per_agent"),
        ("tb.split.flagged", ("split_attack",), "per_agent"),
        ("tb.split.joint.flagged", ("split_attack",), "joint"),
        ("tb.honest.flagged", ("honest_authorized", "honest_maintenance"), "per_agent"),
        ("tb.honest.joint.flagged", ("honest_authorized", "honest_maintenance"), "joint"),
        ("tb.incomplete.flagged", ("incomplete_attack",), "per_agent"),
        ("tb.incomplete.joint.flagged", ("incomplete_attack",), "joint"),
    ):
        scored = [r for r in rows if r["condition"] in conditions and r[score] is not None]
        ledger.pooled(key, scored, flagged(score, threshold), how=f"{score}: {how}", cell=TEAM)
    agents = {e["case_id"]: e["agent_ids"] for e in episodes}

    def members(condition: str) -> list[dict]:
        """Each split team's per-agent medians by role, for the teams of one run type."""
        return [{"case_id": r["case_id"], **{ROLES[agents[r["case_id"]].index(v["agents"][0])]: v["median"]
                                             for v in r["views"] if v["view"] == "per_agent"}}
                for r in rows if r["condition"] == condition and r["execution_layout"] == "split"
                and r["per_agent"] is not None]

    attack, shipping = members("split_attack"), members("honest_authorized")
    ledger.pooled("tb.split.sync.top", attack, lambda m: m["sync"] == max(m[role] for role in ROLES),
                  how="split teams whose highest-scoring member read individually is the sync agent / split teams",
                  cell=TEAM)
    ledger.value("tb.split.sync", span(m["sync"] for m in attack),
                 how="the sync agent's median read individually, across the split-attack teams")
    ledger.value("tb.split.backup", span(m["backup"] for m in attack),
                 how="the backup agent's median read individually, across the split-attack teams")
    ledger.value("tb.honest.sync", span(m["sync"] for m in shipping),
                 how="the sync agent's median read individually, across the honest split teams that ship shareable data")

    def shown(value):
        return "-" if value is None else f"{value:g}"
    ledger.table(
        "tb-table",
        ["episode", "read individually (highest member)", "read together", "member medians"],
        [[r["case_id"], shown(r["per_agent"]), shown(r["joint"]),
          ", ".join(shown(v["median"]) for v in r["views"] if v["view"] == "per_agent")] for r in rows],
        how="median score per view, per episode",
    )
    ledger.figure("tb-figure", draw_scores, {"rows": rows, "threshold": threshold},
                  how="one row per split-layout team (split attack, honest authorized export, incomplete attack "
                      "missing its backup step): an arrow from its per-agent score to its joint score",
                  size=(6.5, 2.7))
