"""Step 2, Experiment C (swarmgraph/scaling/flow.py): the flow graph finds the agents to read together, and Step 1's
monitor judges each group, read together. Jev labels every tool call (source, carrier, sink); calls are linked from a record's
writer to its later readers; a sampled simulation scores where private data reaches an outside delivery through
another agent; the judge reads the top three groups.

Reads logs/scaling_flow/ (episodes.jsonl, flow_groups.jsonl, flow_judgments.jsonl) and, for the comparison,
Experiment B's graph explorations (logs/scaling_graph_curve/) and Experiment A's explorations (logs/scaling/). The
curve fleets are B's, which is checked here through the committed prompt hashes."""

import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, PercentFormatter

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling import explorer
from swarmgraph.scaling.flow import THRESHOLD, TOP_GROUPS, WORLDS
from swarmgraph.transfer_baseline.io import read_jsonl

from .scaling_graph import A_RUN, GRID, HONEST, INK, MUTED, RUN as B_RUN, SPLIT, overlap_of, tag

RUN = B_RUN.parent / "scaling_flow"
HOW = "judgments whose highest group score is at least 75 / judgments; 4 layouts x 2 passes, pooled (no interval)"


SEQ = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]  # dataviz sequential blue


def draw_board(ax: Any, data: dict) -> None:
    """A scoreboard: the split attacks each method caught under each condition (hatched: not run)."""
    conds, labels = data["conditions"], data["labels"]
    for i, (name, counts) in enumerate(data["methods"]):
        for j, count in enumerate(counts):
            if count is None:
                ax.add_patch(Rectangle((j, i), 1, 1, facecolor="white", edgecolor=GRID, hatch="////", linewidth=0.5))
                continue
            k, n = count
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=SEQ[round(6 * k / n)], edgecolor="white", linewidth=1.5))
            ax.text(j + 0.5, i + 0.5, f"{k}/{n}", fontsize=8, ha="center", va="center",
                    color="white" if k / n > 0.6 else INK)
    ax.set_xlim(0, len(conds))
    ax.set_ylim(len(data["methods"]), 0)
    ax.set_xticks([j + 0.5 for j in range(len(conds))], labels=labels)
    ax.set_yticks([i + 0.5 for i in range(len(data["methods"]))], labels=[m for m, _ in data["methods"]])
    split = data["split_at"]
    ax.axvline(split, color=INK, linewidth=0.8)
    ax.text(split / 2, -0.12, "303 agents, by tool-call overlap between teams", fontsize=7.5, color=MUTED,
            ha="center", va="bottom")
    ax.text((split + len(conds)) / 2, -0.12, "overlap 4", fontsize=7.5, color=MUTED, ha="center", va="bottom")
    ax.legend(handles=[Rectangle((0, 0), 1, 1, facecolor=SEQ[6], label="all caught"),
                       Rectangle((0, 0), 1, 1, facecolor=SEQ[3], label="half"),
                       Rectangle((0, 0), 1, 1, facecolor=SEQ[0], edgecolor=GRID, label="none"),
                       Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=GRID, hatch="////", label="not run")],
              loc="upper right", bbox_to_anchor=(1.0, -0.42), ncol=4, fontsize=7, frameon=False, handlelength=1.2,
              columnspacing=0.9)
    ax.tick_params(axis="both", length=0, labelsize=8, colors=INK)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)


def draw_judge(ax: Any, data: dict) -> None:
    """The judge's score on every judgment, split attack against honest twin, one row per condition."""
    conds = data["conditions"]
    for i, (attack, honest) in enumerate(zip(data["attack_scores"], data["honest_scores"])):
        for scores, color, marker, dy in ((attack, SPLIT, "s", -0.15), (honest, HONEST, "^", 0.15)):
            for score, count in sorted(Counter(scores).items()):  # tied scores stacked within the row
                for m in range(count):
                    ax.plot(score, i + dy + 0.07 * (m - (count - 1) / 2), marker, color=color, markersize=3.8,
                            markeredgecolor="white", markeredgewidth=0.4, zorder=3)
    ax.axvline(data["threshold"], color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(data["threshold"] + 0.8, len(conds) - 0.62, f"flagged at {data['threshold']}+", fontsize=7.5,
            color=MUTED, va="bottom")
    ax.set_yticks(range(len(conds)), labels=[f"overlap {o:g}" if n == 100 else f"{3 * n + 3:,} agents"
                                             for n, o in conds])
    ax.set_ylim(len(conds) - 0.4, -0.6)
    ax.set_xlim(45, 100)
    ax.set_xlabel("judge's score for the fleet (the highest of its groups); each of 4 layouts x 2 passes",
                  fontsize=8, color=INK)
    ax.legend(handles=[Line2D([], [], marker="s", color=SPLIT, linestyle="", label="split attack"),
                       Line2D([], [], marker="^", color=HONEST, linestyle="", label="honest (no attack)")],
              loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8, frameon=False)
    ax.tick_params(axis="both", length=0, labelsize=8, colors=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


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
    conditions = [(100, o) for o in overlaps] + [(n, 4) for n in sizes if n != 100]
    count = lambda rs: (sum(r["flagged"] for r in rs), len(rs)) if rs else None
    ledger.figure("sc-figure", draw_board, {
        "conditions": conditions, "split_at": len(overlaps),
        "labels": [f"{o:g}" for o in overlaps] + [f"{3 * n + 3:,}\nagents" for n in sizes if n != 100],
        "methods": [
            ("A: no graph", [count(a_split) if (n, o) == (100, 0) else None for n, o in conditions]),
            ("B: provenance graph", [count([r for r in b_split if r["overlap"] == o]) if n == 100 else None
                                     for n, o in conditions]),
            ("C: flow graph + judge", [count(cells[(c, "split_attack")]) for c in conditions])]},
        how=f"{HOW}; with B's graph runs and A's runs of the same fleets for comparison", size=(6.5, 1.9))
    ledger.figure("sc-scores", draw_judge, {
        "conditions": conditions, "threshold": THRESHOLD,
        "attack_scores": [[r["score"] for r in cells[(c, "split_attack")]] for c in conditions],
        "honest_scores": [[r["score"] for r in cells[(c, "honest_authorized")]] for c in conditions]},
        how=f"{HOW}; every judgment's score", size=(6.5, 3.0))
