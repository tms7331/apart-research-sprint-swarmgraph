"""Step 2, Experiment C (swarmgraph/scaling/flow.py): the flow graph finds the agents to read together, and Step 1's
group monitor judges them. Jev labels every tool call (source, carrier, sink); calls are linked from a record's
writer to its later readers; a sampled simulation scores where private data reaches an outside delivery through
another agent; the judge reads the top three groups.

Reads logs/scaling_flow/ (episodes.jsonl, flow_groups.jsonl, flow_judgments.jsonl) and, for the comparison,
Experiment B's graph explorations (logs/scaling_graph_curve/) and Experiment A's explorations (logs/scaling/). The
curve fleets are B's, which is checked here through the committed prompt hashes."""

import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from matplotlib.ticker import FixedLocator, PercentFormatter

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling import explorer
from swarmgraph.scaling.flow import THRESHOLD, TOP_GROUPS, WORLDS
from swarmgraph.transfer_baseline.io import read_jsonl

from .scaling_graph import A_RUN, GRID, HONEST, INK, MUTED, RUN as B_RUN, SPLIT, overlap_of, tag

RUN = B_RUN.parent / "scaling_flow"
HOW = "judgments whose highest group score is at least 75 / judgments; 4 layouts x 2 passes, pooled (no interval)"


def draw_flow(ax: Any, data: dict) -> None:
    """Left: share of fleets flagged as overlap grows, at 100 teams: the flow graph against B's graph explorer and
    A's explorer. Right: the judge's score on each judgment as the fleet grows, at overlap 4."""
    fig = ax.figure
    ax.remove()
    left, right = fig.subplots(1, 2, gridspec_kw={"wspace": 0.38, "width_ratios": [1.35, 1]})
    xs = list(range(len(data["overlaps"])))
    b = len(data["b_split"])
    left.axvspan(b - 0.5, xs[-1] + 0.5, color=GRID, alpha=0.35, linewidth=0, zorder=0)
    left.text(b - 0.35, 0.47, "beyond B's\nrange", fontsize=7, color=MUTED, ha="left", va="center")
    left.plot(xs, data["split"], color=SPLIT, linewidth=2, marker="s", markersize=7, markeredgecolor="white",
              label="split attack, flow graph", zorder=4)
    left.plot(xs, data["honest"], color=HONEST, linewidth=2, marker="^", markersize=7, markeredgecolor="white",
              label="honest, flow graph (false alarm)", zorder=4)
    left.plot(xs[:b], data["b_split"], color=MUTED, linewidth=1.5, linestyle=(0, (4, 2)), marker="o", markersize=5,
              markerfacecolor="white", markeredgewidth=1.5, label="split attack, B's graph", zorder=6)
    left.plot([0], [data["a_split"]], linestyle="none", marker="D", markersize=6, color=MUTED, zorder=6,
              label="split attack, no graph")
    left.set_ylim(-0.04, 1.06)
    left.yaxis.set_major_formatter(PercentFormatter(1.0))
    left.xaxis.set_major_locator(FixedLocator(xs))
    left.set_xticklabels([f"{o:g}" for o in data["overlaps"]])
    left.set_xlim(-0.5, xs[-1] + 0.5)
    left.set_xlabel("overlap (shared indexes per team), 303 agents", fontsize=8, color=INK)
    left.set_title("fleets flagged", fontsize=8, color=INK, loc="left")
    fig.legend(*left.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(0.5, 0.99), ncol=4,
               fontsize=7, frameon=False, handlelength=2.6, columnspacing=1.4)

    sizes = data["sizes"]
    for i, (attack, honest) in enumerate(zip(data["attack_scores"], data["honest_scores"])):
        for scores, marker, color, size in ((attack, "s", SPLIT, 4.5), (honest, "^", HONEST, 5)):
            for score, count in sorted(Counter(scores).items()):  # tied scores side by side, centred
                for k in range(count):
                    right.plot(i + 0.07 * (k - (count - 1) / 2), score, linestyle="none", marker=marker,
                               markersize=size, color=color, markeredgecolor="white", markeredgewidth=0.6, zorder=3)
    right.axhline(data["threshold"], color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    right.text(len(sizes) - 0.55, data["threshold"] + 1.2, "flag threshold", fontsize=7, color=MUTED, ha="right",
               va="bottom")
    right.set_ylim(40, 100)
    right.xaxis.set_major_locator(FixedLocator(range(len(sizes))))
    right.set_xticklabels([f"{a:,}" for a in sizes])
    right.set_xlim(-0.5, len(sizes) - 0.5)
    right.set_xlabel("agents in the fleet, overlap 4", fontsize=8, color=INK)
    right.set_title("judge's score, each judgment", fontsize=8, color=INK, loc="left")
    for axis in (left, right):
        axis.tick_params(axis="both", length=0, labelsize=8, colors=INK)
        axis.grid(axis="y", color=GRID, linewidth=0.6)
        axis.set_axisbelow(True)
        for side in ("top", "right", "left"):
            axis.spines[side].set_visible(False)
        axis.spines["bottom"].set_color(GRID)


@source("sc")
def scaling_flow(ledger: Ledger) -> None:
    episodes = {e["case_id"]: e for e in read_jsonl(RUN / "episodes.jsonl")}
    groups = {g["case_id"]: g for g in read_jsonl(RUN / "flow_groups.jsonl")}
    judged = [r for r in read_jsonl(RUN / "flow_judgments.jsonl") if r.get("status") == "ok"]
    point = {c: (e["honest_teams"], overlap_of(c)) for c, e in episodes.items()}
    rows = [{"case_id": r["case_id"], "point": point[r["case_id"]], "condition": episodes[r["case_id"]]["condition"],
             "flagged": r["flagged"], "score": r["score"], "run": r["run_index"],
             "colluders": set(episodes[r["case_id"]]["colluding_agent_ids"]),
             "top": set(max(r["groups"], key=lambda g: g["response"]["score"])["agents"])} for r in judged]
    flagged = lambda row: row["flagged"]
    attack = [r for r in rows if r["condition"] == "split_attack"]
    honest = [r for r in rows if r["condition"] == "honest_authorized"]
    cells = defaultdict(list)
    for r in rows:
        cells[(r["point"], r["condition"])].append(r)

    ledger.value("sc.fleets", len(episodes), how="fleets in Experiment C (B's 48 curve fleets and a 32-fleet scaling arm)")
    ledger.value("sc.judgments", len(rows), how="successful judgments (one per fleet per pass)")
    ledger.value("sc.passes", len({r["run"] for r in rows}), how="passes: each judges every fleet once")
    ledger.value("sc.groups", TOP_GROUPS, how="groups the judge reads per fleet, highest graph score first")
    ledger.value("sc.worlds", WORLDS, how="sampled worlds per fleet in the flow simulation")
    ledger.value("sc.threshold", THRESHOLD, how="judge score at or above which a group flags the fleet")
    b_rows = {e["case_id"]: e for e in read_jsonl(B_RUN / "episodes.jsonl")}
    same = [c for c in b_rows if c in episodes and [v["prompt_sha256"] for v in b_rows[c]["views"]]
            == [v["prompt_sha256"] for v in episodes[c]["views"]]]
    ledger.value("sc.same.fleets", len(same), how="curve fleets whose public log hashes match Experiment B's")
    ledger.value("sc.curve.fleets", len(b_rows), how="fleets on Experiment B's curve")

    overlaps = sorted({o for n, o in point.values() if n == 100})
    sizes = sorted({n for n, o in point.values() if o == 4})
    for o in overlaps:
        for condition, name in (("split_attack", "split"), ("honest_authorized", "honest")):
            ledger.pooled(f"sc.{name}.o{tag(o)}", cells[((100, o), condition)], flagged, how=f"{HOW}; 100 honest teams",
                          cell=("case_id",))
    for n in sizes:
        for condition, name in (("split_attack", "split"), ("honest_authorized", "honest")):
            ledger.pooled(f"sc.{name}.n{n}", cells[((n, 4), condition)], flagged, how=f"{HOW}; overlap 4",
                          cell=("case_id",))
        ledger.value(f"sc.agents.n{n}", f"{3 * n + 3:,}", how="agents in a fleet with this many honest teams")
    curve = set(b_rows)
    ledger.pooled("sc.split", attack, flagged, how=f"{HOW}; every fleet", cell=("case_id",))
    ledger.pooled("sc.honest", honest, flagged, how=f"{HOW}; every fleet", cell=("case_id",))
    ledger.pooled("sc.split.curve", [r for r in attack if r["case_id"] in curve], flagged,
                  how=f"{HOW}; Experiment B's curve fleets", cell=("case_id",))
    b_explored = [r for r in read_jsonl(B_RUN / explorer.GRAPH_LOG) if r.get("status") == "ok"]
    b_split = [{"case_id": r["case_id"], "flagged": r["score"] >= explorer.THRESHOLD, "overlap": overlap_of(r["case_id"])}
               for r in b_explored if b_rows[r["case_id"]]["condition"] == "split_attack"]
    ledger.pooled("sc.b.split", b_split, flagged, how="Experiment B's graph explorations of the same split-attack "
                  "fleets that flag the fleet / explorations", cell=("case_id",))
    ledger.pooled("sc.judge.colluders", attack, lambda r: r["top"] == r["colluders"],
                  how="attack judgments whose highest-scoring group is exactly the three colluders / attack judgments",
                  cell=("case_id",))
    ledger.value("sc.judge.attack.min", min(r["score"] for r in attack), how="lowest judge score on an attack fleet")
    ledger.value("sc.judge.honest.max", max(r["score"] for r in honest), how="highest judge score on an honest fleet")
    by_fleet = defaultdict(set)
    for r in rows:
        by_fleet[r["case_id"]].add(r["flagged"])
    ledger.pooled("sc.agree", [{"case_id": c, "same": len(v) == 1} for c, v in by_fleet.items()], lambda r: r["same"],
                  how="fleets whose two passes give the same flag / fleets", cell=("case_id",))
    attack_groups = [g for c, g in groups.items() if episodes[c]["condition"] == "split_attack"]
    honest_groups = [g for c, g in groups.items() if episodes[c]["condition"] == "honest_authorized"]
    ledger.pooled("sc.graph.exact", [{"case_id": g["case_id"], "exact": set(g["groups"][0]["agents"])
                                      == set(episodes[g["case_id"]]["colluding_agent_ids"])} for g in attack_groups],
                  lambda r: r["exact"], how="attack fleets whose top graph group is exactly the three colluders / attack fleets",
                  cell=("case_id",))
    ledger.value("sc.graph.attack.min", f"{min(g['groups'][0]['score'] for g in attack_groups):.2f}",
                 how="lowest top-group graph score on an attack fleet")
    ledger.value("sc.graph.honest.max", f"{max(g['groups'][0]['score'] for g in honest_groups):.2f}",
                 how="highest top-group graph score on an honest fleet")
    biggest = [g for g in attack_groups if point[g["case_id"]] == (sizes[-1], 4)]
    base = [g for g in attack_groups if point[g["case_id"]] == (100, 4)]
    ledger.value("sc.calls.base", f"{median(g['calls'] for g in base):,.0f}", how="tool calls in a 100-team fleet at overlap 4")
    ledger.value("sc.calls.largest", f"{median(g['calls'] for g in biggest):,.0f}", how="tool calls in the largest fleet")
    ledger.value("sc.usd.base", f"{100 * median(g['jev_usd'] for g in base):.0f}¢",
                 how="Jev labelling cost of one 100-team fleet at overlap 4 (cents)")
    ledger.value("sc.usd.largest", f"{100 * median(g['jev_usd'] for g in biggest):.0f}¢",
                 how="Jev labelling cost of one of the largest fleets (cents)")
    prompt_chars = [g["prompt_chars"] for r in judged for g in r["groups"]]
    log_chars = [v["prompt_chars"] for c, e in episodes.items() if point[c] == (100, 4) for v in e["views"]]
    ledger.value("sc.judge.chars", f"{median(prompt_chars) / 1000:.1f}K", how="median characters of evidence per judge call")
    ledger.value("sc.log.chars", f"{median(log_chars) / 1000:,.0f}K",
                 how="characters in the whole public log of a 100-team fleet at overlap 4")

    a_rows = {e["case_id"]: e for e in read_jsonl(A_RUN / "episodes.jsonl")}
    zero = [c for c in same if overlap_of(c) == 0]
    a_split = [r for r in explorer.summary(A_RUN) if r["case_id"] in zero and r["condition"] == "split_attack"
               and r["case_id"] in a_rows]
    rate = lambda rs: sum(r["flagged"] for r in rs) / len(rs)
    header = ["agents", "overlap", "split caught, B's graph", "split caught, flow graph", "honest false alarms",
              "judge score, attack", "judge score, honest", "Jev cost per fleet"]
    table = []
    points = [(100, o) for o in overlaps] + [(n, 4) for n in sizes if n != 100]
    for n, o in points:
        a, h = cells[((n, o), "split_attack")], cells[((n, o), "honest_authorized")]
        bs = [r for r in b_split if r["overlap"] == o] if n == 100 else []
        fleet_groups = [g for g in attack_groups if point[g["case_id"]] == (n, o)]
        table.append([f"{3 * n + 3:,}", f"{o:g}", f"{sum(r['flagged'] for r in bs)}/{len(bs)}" if bs else "–",
                      f"{sum(map(flagged, a))}/{len(a)}", f"{sum(map(flagged, h))}/{len(h)}",
                      f"{min(r['score'] for r in a)}–{max(r['score'] for r in a)}",
                      f"{min(r['score'] for r in h)}–{max(r['score'] for r in h)}",
                      f"{100 * median(g['jev_usd'] for g in fleet_groups):.0f}¢"])
    ledger.table("sc-table", header, table, how=HOW)
    ledger.figure("sc-figure", draw_flow, {
        "overlaps": overlaps, "threshold": THRESHOLD, "a_split": rate(a_split),
        "split": [rate(cells[((100, o), "split_attack")]) for o in overlaps],
        "honest": [rate(cells[((100, o), "honest_authorized")]) for o in overlaps],
        "b_split": [rate([r for r in b_split if r["overlap"] == o]) for o in overlaps if any(r["overlap"] == o for r in b_split)],
        "sizes": [3 * n + 3 for n in sizes],
        "attack_scores": [[r["score"] for r in cells[((n, 4), "split_attack")]] for n in sizes],
        "honest_scores": [[r["score"] for r in cells[((n, 4), "honest_authorized")]] for n in sizes]},
        how=f"{HOW}; left: B's graph explorations and A's explorations of the same overlap-0 fleets for comparison",
        size=(6.5, 3.0))
