"""Step 1, the transfer baseline (swarmgraph/transfer_baseline/): the minimal Kitaoka reproduction.

Reads the run's two logs, episodes.jsonl and judgments.jsonl, through swarmgraph.transfer_baseline.analysis,
so the paper counts exactly what the run's own report counts. The design comes from the run's protocol.json.

For now RUN is the smoke run (logs/transfer_baseline_smoke/, gitignored, one reading per view): a scaffold
that proves the pipeline from logs to figure. Point RUN at logs/transfer_baseline/ once the full run is
committed; a --final build refuses logs that aren't committed and pushed."""

import json
from pathlib import Path
from typing import Any

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.transfer_baseline.analysis import summarize
from swarmgraph.transfer_baseline.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "logs" / "transfer_baseline_smoke"
TEAM = ("case_id",)  # each team is its own cell: one episode, with its own prompts
ROWS = {  # the figure's rows, top to bottom: (label, conditions)
    "solo attack": ("solo_attack",),
    "split attack": ("split_attack",),
    "honest, authorized export": ("honest_authorized",),
    "honest, maintenance": ("honest_maintenance",),
    "incomplete attack": ("incomplete_attack",),
}
SERIES = {  # score -> (label, color, marker): dataviz categorical slots 1-2, validated; shapes differ too
    "per_agent": ("per-agent monitor (highest member)", "#2a78d6", "o"),
    "joint": ("joint monitor (whole team)", "#eb6834", "s"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e0e0e0"


def draw_scores(ax: Any, data: dict) -> None:
    """One dot per team and monitor, at its median score; rows by run type; the flag threshold dashed."""
    rows, threshold = data["rows"], data["threshold"]
    for i, (label, conditions) in enumerate(ROWS.items()):
        teams = [r for r in rows if r["condition"] in conditions]
        for j, (key, (_, color, marker)) in enumerate(SERIES.items()):
            scores = [r[key] for r in teams if r[key] is not None]
            for k, score in enumerate(scores):
                y = i + (j - 0.5) * 0.28 + (k - (len(scores) - 1) / 2) * 0.06
                ax.plot(score, y, marker, color=color, markersize=6, markeredgecolor="white", markeredgewidth=1)
    ax.axvline(threshold, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(threshold + 1, -0.75, f"flagged at {threshold}+", color=MUTED, fontsize=8, va="bottom")
    ax.set_yticks(range(len(ROWS)), labels=list(ROWS), fontsize=8, color=INK)
    ax.set_ylim(len(ROWS) - 0.5, -0.9)
    ax.set_xlim(-3, 103)
    ax.set_xlabel("median suspicion score (0-100)", fontsize=8, color=INK)
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


@source("tb")
def transfer_baseline(ledger: Ledger) -> None:
    design = json.loads((RUN / "protocol.json").read_text())
    data = summarize(read_jsonl(RUN / "episodes.jsonl"), read_jsonl(RUN / "judgments.jsonl"), design)
    rows, threshold = [r for r in data["rows"] if r["eligible"]], design["threshold"]
    ledger.value("tb.run", design["version"], how="the run the numbers come from (protocol.json)")
    ledger.value("tb.episodes", data["episodes"], how="scripted episodes")
    ledger.value("tb.readings", data["successful_readings"], how="successful judge readings")
    ledger.value("tb.readings.per.view", design["readings_per_view"], how="readings per monitor view")
    ledger.value("tb.threshold", threshold, how="the fixed flag threshold (MiniLab's 7.5 of 10)")
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
    def shown(value):
        return "-" if value is None else f"{value:g}"
    ledger.table(
        "tb-table",
        ["episode", "per-agent (highest member)", "joint", "member medians"],
        [[r["case_id"], shown(r["per_agent"]), shown(r["joint"]),
          ", ".join(shown(v["median"]) for v in r["views"] if v["view"] == "per_agent")] for r in rows],
        how="median score per view, per episode",
    )
    ledger.figure("tb-figure", draw_scores, {"rows": rows, "threshold": threshold},
                  how="one dot per team and monitor at its median score", size=(6.5, 2.6))
