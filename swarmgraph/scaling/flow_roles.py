"""After Experiment C: each judged group's agents, with their teams and roles. No model calls.

The roles are ground truth from each fleet's private plans, read after the run to describe the groups the flow
graph found; the method itself never sees them. The fleets are gitignored, so this reads them once (generating any
that are missing, deterministically) and writes a small log the paper reads:

    uv run python -m swarmgraph.scaling flow-roles    # writes logs/scaling_flow/flow_group_roles.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

from swarmgraph.transfer_baseline.io import read_jsonl, write_jsonl

from . import flow
from .design import flow_cases

GROUP_ROLES_LOG = "flow_group_roles.jsonl"


def roles(fleet: Path) -> dict[str, tuple[str, str]]:
    """Each agent's (team, role) from the fleet's private plans: ground truth, for describing results only."""
    plans = json.loads((Path(fleet) / "private" / "plans.jsonl").read_text().splitlines()[0])
    return {agent: tuple(key.rsplit("_", 1)) for key, agent in plans["role_to_agent"].items()}


def group_roles(destination: Path, smoke: bool = False) -> list[dict]:
    """Each fleet's judged groups (the top flow.TOP_GROUPS of flow_groups.jsonl), with each agent's team and role.
    Generates any missing fleet first (no model calls). Writes GROUP_ROLES_LOG."""
    destination = Path(destination)
    # flow.generate rewrites protocol.json from the code's design; keep the one the run recorded.
    recorded = (destination / "protocol.json").read_text() if (destination / "protocol.json").exists() else None
    flow.generate(destination, flow_cases(smoke))
    if recorded is not None:
        (destination / "protocol.json").write_text(recorded)
    rows = []
    for built in read_jsonl(destination / flow.GROUPS_LOG):
        role = roles(destination / "episodes" / built["case_id"])
        rows.append({"schema_version": 1, "case_id": built["case_id"], "groups": [
            {"agents": g["agents"], "roles": [list(role[a]) for a in g["agents"]]}
            for g in built["groups"][:flow.TOP_GROUPS]]})
    write_jsonl(destination / GROUP_ROLES_LOG, rows)
    return rows
