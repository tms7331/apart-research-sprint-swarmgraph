"""The flow graph on a tiny worked example, for the slides: three teams of three agents (an attack, an honest team
shipping shareable data, an honest team that leaves its delivery off) plus one shared read between two teams.
The labels are illustrative Jev answers, close to what Jev gave on the real fleets; the scores come from the
real simulation (swarmgraph.scaling.flow.simulate) run on this graph."""

from typing import Any

from matplotlib.patches import FancyBboxPatch

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling.flow import simulate

from .scaling_graph import GRID, HONEST, INK, MUTED, SPLIT

WORLDS = 4000  # more than the real run's 400, so the example's scores are steady to two decimals
TEAMS = {"A": "team A: attack", "S": "team S: honest, shareable data", "M": "team M: honest, delivery off"}
# call: (team, agent, column, text, source, carrier, sink)
CALLS = {
    "a1": ("A", "A-backup", 0.0, "copies private\ncheckpoint", 0.95, 0.90, 0.02),
    "a2": ("A", "A-staging", 2.0, "points entry\nat bundle", 0.30, 0.85, 0.05),
    "a3": ("A", "A-sync", 4.0, "switches\ndelivery on", 0.10, 0.20, 0.90),
    "s1": ("S", "S-backup", 0.0, "copies the\nsample", 0.05, 0.90, 0.02),
    "s0": ("S", "S-staging", 1.0, "reads a shared\nlisting", 0.05, 0.02, 0.02),
    "s2": ("S", "S-staging", 2.0, "points entry\nat bundle", 0.30, 0.85, 0.05),
    "s3": ("S", "S-sync", 4.0, "switches\ndelivery on", 0.10, 0.20, 0.90),
    "m1": ("M", "M-backup", 0.0, "copies private\ncheckpoint", 0.95, 0.90, 0.02),
    "m2": ("M", "M-staging", 2.0, "points entry\nat bundle", 0.30, 0.85, 0.05),
    "m3": ("M", "M-sync", 4.0, "leaves\ndelivery off", 0.10, 0.20, 0.03),
}
ORDER = ["a1", "m1", "s1", "a2", "m2", "s0", "s2", "a3", "m3", "s3"]  # log order: every link points forward
LINKS = [("a1", "a2"), ("a2", "a3"), ("m1", "m2"), ("m2", "m3"), ("s1", "s2"), ("s2", "s3"), ("s0", "s2"),
         ("a2", "s0")]  # the last: S's shared read names A's entry, a link that carries almost nothing
ROW = {"A": 2.0, "S": 1.0, "M": 0.0}
ROLE = {"source": "#2a78d6", "carrier": MUTED, "sink": "#8a3fb8"}


def run() -> dict:
    agent = {c: CALLS[c][1] for c in ORDER}
    scores = {c: dict(zip(("source", "carrier", "sink"), CALLS[c][4:])) for c in ORDER}
    groups = simulate(ORDER, agent, scores, [(u, v, "ref") for u, v in LINKS], worlds=WORLDS)
    return {g["sink"]: g for g in groups}


def draw_example(ax: Any, data: dict) -> None:
    """Teams as rows, steps as columns; each action shows its strongest Jev label; the attack's complete path in
    orange; each delivery's flow score at the right."""
    w, h = 0.9, 0.36
    for name, (team, _, x, text, src, car, snk) in CALLS.items():
        y = ROW[team]
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                    facecolor="white", edgecolor=SPLIT if team == "A" else MUTED,
                                    linewidth=1.4 if team == "A" else 0.9, zorder=3))
        ax.text(x, y, text, fontsize=7, color=INK, ha="center", va="center", zorder=4, linespacing=1.05)
        # the label that matters at this step of the chain: backup -> source, staging -> carrier, sync -> sink
        role, value = ("source", src) if x == 0 else ("sink", snk) if x == 4.0 else ("carrier", car)
        ax.text(x, y - h / 2 - 0.05, f"{role} {value:.2f}".replace("0.", "."), fontsize=7, color=ROLE[role],
                ha="center", va="top", zorder=4)
    for u, v in LINKS:
        (tu, _, xu, *_), (tv, _, xv, *_) = CALLS[u], CALLS[v]
        noise = (u, v) == ("a2", "s0")
        attack = tu == tv == "A"
        start, end = (xu + w / 2, ROW[tu]), (xv - w / 2, ROW[tv])
        if noise:
            start, end = (xu, ROW[tu] - h / 2 - 0.2), (xv + 0.02, ROW[tv] + h / 2 + 0.02)
        ax.annotate("", xy=end, xytext=start, zorder=2, arrowprops=dict(
            arrowstyle="-|>", mutation_scale=9, shrinkA=1, shrinkB=1,
            color=SPLIT if attack else ("#b9b8b1" if noise else MUTED), lw=2.2 if attack else 1,
            linestyle=(0, (3, 2)) if noise else "-"))
    ax.text(2.2, 1.5, "shared read: passes on almost nothing", fontsize=6.8, color=MUTED, ha="left", va="center")
    for team, y in ROW.items():
        ax.text(-0.62, y, TEAMS[team].replace(": ", ":\n"), fontsize=7.2, color=SPLIT if team == "A" else INK,
                ha="right", va="center", weight="bold" if team == "A" else "normal")
        sink = {"A": "a3", "S": "s3", "M": "m3"}[team]
        ax.text(4.62, y, f"{data[sink]:.2f}", fontsize=13, color=SPLIT if team == "A" else MUTED, ha="left",
                va="center", weight="bold")
    ax.text(4.62, 2.55, "flow score", fontsize=7.4, color=INK, ha="left", va="center")
    for x, label in ((0, "backup agent"), (2.0, "staging agent"), (4.0, "sync agent")):
        ax.text(x, 2.55, label, fontsize=7.4, color=INK, ha="center", va="center")
    ax.set_xlim(-2.0, 5.3)
    ax.set_ylim(-0.42, 2.72)
    ax.axis("off")


@source("fx")
def flow_example(ledger: Ledger) -> None:
    groups = run()
    sinks = {"A": "a3", "S": "s3", "M": "m3"}
    for team, sink in sinks.items():
        ledger.value(f"fx.score.{team.lower()}", f"{groups[sink]['score']:.2f}",
                     how=f"flow score of team {team}'s delivery in the worked example ({WORLDS} simulated worlds)")
    ledger.value("fx.worlds", f"{WORLDS:,}", how="simulated worlds in the worked example")
    ledger.figure("fx-figure", draw_example, {t: groups[s]["score"] for t, s in sinks.items()} | {
        s: groups[s]["score"] for s in sinks.values()},
        how=f"the worked example's graph, with each delivery's flow score from {WORLDS} simulated worlds",
        size=(6.2, 3.3))
