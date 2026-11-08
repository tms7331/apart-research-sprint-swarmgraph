"""The flow graph on a tiny worked example, for the slides: an attack team and an honest team that ships shareable
data, linked by one shared read (the honest team's staging agent reads an index that lists the attack team's
package). The labels are illustrative Jev answers, close to what Jev gave on the real fleets; the flow comes from
the real simulation's sampling (swarmgraph.scaling.flow.uniforms and simulate) run on this graph.

The figure has two panels on the same calls: the graph as it's built (each action with Jev's three answers, each
link with the record that makes it) and the flow found on it (each link with the share of worlds in which private
data passes along it, each delivery with its flow score)."""

from typing import Any

import numpy as np
from matplotlib.patches import FancyBboxPatch

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling.flow import simulate, uniforms

from .scaling_graph import INK, MUTED, SPLIT

WORLDS = 4000  # more than the real run's 400, so the example's numbers are steady
SOURCE, SINK, LIGHT, FADED = "#2a78d6", "#8a3fb8", "#c9c8c2", "#a9a8a2"
# call: (team, agent, x, y, name, source, carrier, sink); x and y in inches on the figure
CALLS = {
    "a1": ("A", "A-backup", 0.0, 1.0, "copy\ncheckpoint", 0.95, 0.90, 0.02),
    "a2": ("A", "A-staging", 1.8, 1.0, "point\npackage", 0.30, 0.85, 0.05),
    "a3": ("A", "A-sync", 2.9, 1.0, "delivery\non", 0.10, 0.20, 0.90),
    "s1": ("S", "S-backup", 0.0, 0.0, "copy\nsample", 0.05, 0.90, 0.02),
    "s0": ("S", "S-staging", 0.9, 0.0, "read\nindex", 0.05, 0.02, 0.02),
    "s2": ("S", "S-staging", 1.8, 0.0, "point\npackage", 0.30, 0.85, 0.05),
    "s3": ("S", "S-sync", 2.9, 0.0, "delivery\non", 0.10, 0.20, 0.90),
}
ORDER = ["a1", "s1", "a2", "s0", "s2", "a3", "s3"]  # log order: every link points forward
# (from, to, the record that makes the link)
LINKS = [("a1", "a2", "bundle"), ("a2", "a3", "package"), ("s1", "s2", "bundle"), ("s0", "s2", "same\nagent"),
         ("s2", "s3", "package"), ("a2", "s0", "the index lists\nA's package")]
SINKS = {"A": "a3", "S": "s3"}
BW, BH, RIGHT = 0.54, 0.62, 4.15  # box width and height; where the second panel starts


def labels(c: str) -> dict:
    return dict(zip(("source", "carrier", "sink"), CALLS[c][5:]))


def sample(worlds: int = WORLDS) -> dict:
    """The simulation's rounds on the example, kept per call (the same rule and the same random numbers as
    flow.simulate): each call's source and carrier answers, whether it holds private data, and whether it's hit."""
    agent = {c: CALLS[c][1] for c in ORDER}
    preds = {c: [u for u, v, _ in LINKS if v == c] for c in ORDER}
    out = {k: {} for k in ("source", "carrier", "holds", "carried", "hit")}
    for v in ORDER:
        received, through = np.zeros(worlds, bool), np.zeros(worlds, bool)
        for u in preds[v]:
            received |= out["holds"][u]
            through |= out["holds"][u] if agent[u] != agent[v] else (out["carrier"][u] & out["hit"][u])
        out["source"][v] = uniforms(f"src|{v}", worlds) < labels(v)["source"]
        out["carrier"][v] = uniforms(f"car|{v}", worlds) < labels(v)["carrier"]
        out["carried"][v] = out["carrier"][v] & received
        out["holds"][v] = out["source"][v] | out["carried"][v]
        out["hit"][v] = through
    return out


def run() -> dict:
    """Each delivery's flow score and group (simulate), each call's hit rate, and each link's share of rounds in
    which private data passes along it and on (for the picture only: the method scores calls, not links)."""
    agent = {c: CALLS[c][1] for c in ORDER}
    groups = simulate(ORDER, agent, {c: labels(c) for c in ORDER}, [(u, v, "ref") for u, v, _ in LINKS],
                      worlds=WORLDS)
    by_sink = {g["sink"]: g for g in groups}
    rounds = sample()
    onward = {u for u, _, _ in LINKS}
    link = {(u, v): float((rounds["holds"][u] & (rounds["carried"][v] if v in onward else True)).mean())
            for u, v, _ in LINKS}
    hit = {c: float(rounds["hit"][c].mean()) for c in ORDER}
    return {"score": {t: by_sink[s]["score"] for t, s in SINKS.items()}, "link": link, "hit": hit,
            "group": by_sink[SINKS["A"]]["agents"]}


def box(ax: Any, x0: float, c: str, numbers: bool, dim: bool = False) -> None:
    team, _, x, y, name, *_ = CALLS[c]
    ax.add_patch(FancyBboxPatch((x0 + x - BW / 2, y - BH / 2), BW, BH, boxstyle="round,pad=0.0,rounding_size=0.04",
                                facecolor="white", edgecolor=LIGHT if dim else (SPLIT if team == "A" else MUTED),
                                linewidth=1.0, zorder=3))
    if not numbers:
        ax.text(x0 + x, y, name, fontsize=5.8, ha="center", va="center", color=LIGHT if dim else INK, zorder=4,
                linespacing=0.95, weight="normal" if dim else "bold")
        return
    ax.text(x0 + x, y + BH / 2 - 0.04, name, fontsize=5.8, ha="center", va="top", color=INK, zorder=4,
            linespacing=0.95, weight="bold")
    for i, (question, color) in enumerate((("source", SOURCE), ("carrier", MUTED), ("sink", SINK))):
        p, yy = labels(c)[question], y - 0.03 - 0.1 * i
        ax.text(x0 + x - BW / 2 + 0.04, yy, question, fontsize=5.3, color=color, ha="left", va="center", zorder=4)
        ax.text(x0 + x + BW / 2 - 0.04, yy, f"{p:.2f}".replace("0.", "."), fontsize=5.3, zorder=4, ha="right",
                va="center", color=INK if p >= 0.5 else MUTED, weight="bold" if p >= 0.5 else "normal")


def arrow(ax: Any, x0: float, u: str, v: str, label: str, width: float = 0.9, color: str = MUTED,
          label_color: str = MUTED) -> None:
    (tu, _, xu, yu, *_), (tv, _, xv, yv, *_) = CALLS[u], CALLS[v]
    xu, xv = x0 + xu, x0 + xv
    arc = (u, v) == ("s1", "s2")  # passes under the index read, which sits between them
    if arc:
        start, end = (xu, yu - BH / 2), (xv, yv - BH / 2)
    elif tu == tv:
        start, end = (xu + BW / 2, yu), (xv - BW / 2, yv)
    else:  # the shared read: from the bottom of A's package step down to the top of S's index read
        start, end = (xu - 0.1, yu - BH / 2), (xv + 0.1, yv + BH / 2)
    ax.annotate("", xy=end, xytext=start, zorder=2, arrowprops=dict(
        arrowstyle="-|>", mutation_scale=7 + 1.5 * width, shrinkA=0, shrinkB=0.5, color=color, lw=width,
        connectionstyle="arc3,rad=0.3" if arc else "arc3"))
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    style = dict(fontsize=5.4, style="italic", color=label_color, zorder=5, linespacing=1.0)
    if arc:
        ax.text(mx, my - 0.3, label, ha="center", va="top", **style)
    elif tu != tv:
        ax.text(mx + 0.1, my, label, ha="left", va="center", **style)
    else:
        ax.text(mx, my + 0.04, label, ha="center", va="bottom", **style)


def draw_example(ax: Any, data: dict) -> None:
    """Left, the graph as it's built; right, the flow found on it; the same calls in the same places."""
    link = {tuple(k.split(">")): p for k, p in data["link"].items()}
    for u, v, record in LINKS:
        arrow(ax, 0.0, u, v, record)
    for c in CALLS:
        box(ax, 0.0, c, numbers=True)
    for u, v, _ in LINKS:
        p, attack = link[(u, v)], CALLS[u][0] == CALLS[v][0] == "A"
        arrow(ax, RIGHT, u, v, f"{p:.0%}", width=0.6 + 3.5 * p, color=SPLIT if attack else FADED,
              label_color=SPLIT if attack else MUTED)
    for c in CALLS:
        box(ax, RIGHT, c, numbers=False, dim=not any(link[(u, v)] >= 0.1 for u, v, _ in LINKS if c in (u, v)))
    for team, sink in SINKS.items():
        _, _, x, y, *_ = CALLS[sink]
        ax.text(RIGHT + x + BW / 2 + 0.08, y, f"{data['score'][team]:.2f}", fontsize=11, weight="bold",
                color=SPLIT if team == "A" else MUTED, ha="left", va="center")
    _, _, x, y, *_ = CALLS["a3"]
    ax.text(RIGHT + x + BW / 2 + 0.08, y - BH / 2 - 0.02, "flow score", fontsize=5.6, color=MUTED, ha="left", va="top")
    for team, name, y in (("A", "team A\nattack", 1.0), ("S", "team S\nhonest", 0.0)):
        ax.text(-BW / 2 - 0.08, y, name, fontsize=6.4, ha="right", va="center", linespacing=1.05,
                color=SPLIT if team == "A" else INK, weight="bold" if team == "A" else "normal")
    top = 1.0 + BH / 2
    for x0, title, note in (
            (0.0, "1. The graph we build",
             "box: one action, with Jev's three answers\narrow: one action writes a record that a later one names"),
            (RIGHT, "2. The flow we find",
             f"arrow: % of the simulated worlds where private data passes along it\n"
             f"flow score: % where it arrives through another agent, × P(sink)")):
        ax.text(x0 + 1.45, top + 0.42, title, fontsize=8, weight="bold", ha="center")
        ax.text(x0 + 1.45, top + 0.33, note, fontsize=5.6, color=MUTED, ha="center", va="top", linespacing=1.15)
    ax.annotate("", xy=(RIGHT - BW / 2 - 0.1, 0.5), xytext=(2.9 + BW / 2 + 0.12, 0.5),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1))
    ax.text((RIGHT - BW / 2 + 2.9 + BW / 2) / 2, 0.56, "simulate", fontsize=5.8, ha="center", va="bottom")
    ax.set_xlim(-0.85, RIGHT + 3.55)
    ax.set_ylim(-0.75, top + 0.55)
    ax.set_aspect("equal")
    ax.axis("off")


@source("fx")
def flow_example(ledger: Ledger) -> None:
    result = run()
    # one round, step by step: the first round's random numbers for the attack's first two actions
    first = sample(worlds=1)
    yes = lambda b: "yes" if b else "no"
    rows = []
    for c, question in (("a1", "source"), ("a2", "source"), ("a2", "carrier")):
        p, r = labels(c)[question], float(uniforms(f"{dict(source='src', carrier='car')[question]}|{c}", 1)[0])
        rows.append([CALLS[c][4].replace("\n", " "), f"{question}?", f"{p:.2f}", f"{r:.2f}", yes(r < p)])
    ledger.table("fx-round", ["action", "question", "probability", "random", "answer"], rows,
                 how="the worked example's first round: each answer is yes when the random number is below the "
                     "probability")
    for c in ("a1", "a2", "a3"):
        ledger.value(f"fx.r0.{c}.holds", yes(first["holds"][c][0]), how=f"first round: does {c} hold private data")
        ledger.value(f"fx.r0.{c}.hit", yes(first["hit"][c][0]),
                     how=f"first round: did private data reach {c} from another agent")
    names = {"a3": "delivery on (team A)", "s3": "delivery on (team S)", "s0": "read index (team S)",
             "a2": "point package (team A)"}
    ledger.table("fx-scores", ["action", "hit rate", "P(sink)", "flow score"],
                 [[names[c], f"{result['hit'][c]:.2f}", f"{labels(c)['sink']:.2f}",
                   f"{result['hit'][c] * labels(c)['sink']:.2f}"] for c in ("a3", "s3", "a2", "s0")],
                 how=f"the worked example after {WORLDS} rounds: flow score = hit rate x P(sink)")
    ledger.value("fx.group.a", ", ".join(a.split("-")[1] for a in result["group"][:-1]) + " and "
                 + result["group"][-1].split("-")[1] + f" agents of team {result['group'][0][0]}",
                 how="the agents in the group behind team A's delivery")
    for team, score in result["score"].items():
        ledger.value(f"fx.score.{team.lower()}", f"{score:.2f}",
                     how=f"flow score of team {team}'s delivery in the worked example ({WORLDS} simulated worlds)")
    ledger.value("fx.worlds", f"{WORLDS:,}", how="rounds simulated in the worked example")
    ledger.figure("fx-figure", draw_example,
                  {"score": result["score"], "link": {f"{u}>{v}": p for (u, v), p in result["link"].items()}},
                  how=f"the worked example: the graph as built, then the flow found on it over {WORLDS} simulated "
                      "worlds", size=(7.6, 2.7))
