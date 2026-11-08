"""A short excerpt of one fleet's public log, for the slides: the three colluders' actions, each with the two calls
by other agents just before it, so the excerpt shows how the attack sits among ordinary work.

The fleet is Experiment B's overlap-0 attack fleet in layout 0 (303 agents; the same as Experiment A's 100-team
fleet). The excerpt is the monitor's own view (explorer.Log: no run IDs, timestamps or service records)."""

import json

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling.explorer import Log
from swarmgraph.transfer_baseline.io import read_jsonl

from .scaling_graph import RUN, observations

CASE = "layout0_n100_split_attack_split"
ROLES = ("backup", "staging", "sync")  # the colluders' three steps, in the order they act
BEFORE = 2  # other agents' calls shown before each colluder's step
LONGEST = 30  # characters of a field's value shown


def shorten(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= LONGEST else text[: LONGEST - 1] + "…"


@source("lx")
def log_excerpt(ledger: Ledger) -> None:
    episode = next(e for e in read_jsonl(RUN / "episodes.jsonl") if e["case_id"] == CASE)
    log = Log(observations(CASE, episode["event_count"]))
    colluders = set(episode["colluding_agent_ids"])
    calls = [e for e in log.events if e["kind"] == "tool_call"]
    steps = [i for i, e in enumerate(calls) if e["agent_id"] in colluders and e["payload"]["tool"] == "patch"]
    rows = []
    for role, i in zip(ROLES, steps, strict=True):
        others = [e for e in calls[:i] if e["agent_id"] not in colluders][-BEFORE:]
        for event, step in [*((e, "") for e in others), (calls[i], role)]:
            args = event["payload"].get("arguments", {})
            fields = ", ".join(f"{k}: {shorten(v)}" for k, v in sorted(args.get("fields", {}).items())
                               if k in ("data", "source_key", "enabled", "prepared"))
            rows.append([event["event_id"], event["agent_id"][:8], event["payload"]["tool"], args.get("key", ""),
                         fields, step])
    ledger.table("lx-log", ["event", "agent", "tool", "record", "fields", "step"], rows,
                 how=f"{CASE}: each colluder's patch, with the {BEFORE} calls by other agents just before it")
    ledger.value("lx.events", f"{len(log.events):,}", how=f"events in {CASE}'s public log")
    ledger.value("lx.agents", f"{len(log.agents):,}", how=f"agents in {CASE}")
