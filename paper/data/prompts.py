"""The prompts and questions each experiment used, verbatim, for the paper's appendix.

Each text is taken from the code, and only after a check against the logs: a prompt rebuilt from today's code must
hash to the one the run recorded (or, for Jev's questions, match the digest in the run's protocol.json). If the code
has changed since the run, the check raises and the keys go missing, so the appendix can't show a prompt the run
didn't use."""

import hashlib
import json

from paper.data import source
from paper.ledger import Ledger
from swarmgraph.scaling import explorer, flow
from swarmgraph.transfer_baseline import monitoring
from swarmgraph.transfer_baseline.io import digest, read_jsonl

from .scaling_flow import EXAMPLE
from .scaling import observations as a_observations
from .scaling_graph import A_RUN, RUN as B_RUN, observations
from .transfer_baseline import RUN as TB_RUN

C_RUN = B_RUN.parent / "scaling_flow"
STEP1 = "layout0_split_attack_split"  # Step 1's split attack in layout 0: the three agents' tasks, policy and services


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def check(rebuilt: str, recorded: str, what: str) -> None:
    if sha(rebuilt) != recorded:
        raise ValueError(f"{what}: the prompt rebuilt from the code doesn't match the one the run recorded")


def first_ok(rows: list[dict]) -> dict:
    return next(r for r in rows if r["status"] == "ok" and r["turns"])


def questions_text(questions: dict) -> str:
    """Jev's three questions as the request carries them: the instructions, then what yes and no mean."""
    return "\n\n".join(f"{name}:\n{q['instructions']}\n  yes: {q['criteria']['true']}\n  no: {q['criteria']['false']}"
                       for name, q in questions.items())


@source("pr")
def prompts(ledger: Ledger) -> None:
    # Step 1: the monitor. Rebuild the split attack's group view and compare it with the hash in episodes.jsonl.
    episode = next(e for e in read_jsonl(TB_RUN / "episodes.jsonl") if e["case_id"] == STEP1)
    view = next(v for v in episode["views"] if v["view"] == "group")
    events = read_jsonl(TB_RUN / "episodes" / episode["case_id"] / "observations.jsonl")
    _, prompt = monitoring.build_prompt(events, view["view"], view["agents"])
    check(prompt, view["prompt_sha256"], f"Step 1, {episode['case_id']}")
    ledger.text("pr.monitor", monitoring.JUDGE_INSTRUCTIONS,
                how=f"the monitor's instructions ({monitoring.PROMPT_VERSION}), before the evidence; checked against "
                    f"{episode['case_id']}'s recorded prompt")
    published = next(e["payload"] for e in events if e["kind"] == "policy_published")
    ledger.text("pr.policy", published["policy"], how=f"the public policy of {episode['case_id']} (layout 0)")
    ledger.text("pr.services", published["services"], how=f"the services text of {episode['case_id']} (layout 0)")
    ledger.text("pr.tasks", "\n\n".join(f"{e['payload']['task']}\n  read: {', '.join(e['payload']['permissions']['read'])}"
                                         f"\n  write: {', '.join(e['payload']['permissions']['write'])}"
                                         for e in events if e["kind"] == "task_assigned"),
                how=f"the three agents' tasks and permissions in {episode['case_id']} (layout 0)")

    # Experiment A: the explorer. Rebuild the first turn of the first successful exploration.
    row = first_ok(read_jsonl(A_RUN / "explorations.jsonl"))
    a_episode = next(e for e in read_jsonl(A_RUN / "episodes.jsonl") if e["case_id"] == row["case_id"])
    log = explorer.Log(a_observations(row["case_id"], a_episode["event_count"]))
    check(explorer.render(log, [], False), row["turns"][0]["prompt_sha256"], f"Experiment A, {row['case_id']}")
    if row["prompt_version"] != explorer.PROMPT_VERSION:
        raise ValueError(f"Experiment A ran {row['prompt_version']}, the code is {explorer.PROMPT_VERSION}")
    ledger.text("pr.explorer", explorer.INSTRUCTIONS,
                how=f"the explorer's instructions ({explorer.PROMPT_VERSION}); braces are filled in per fleet; checked "
                    f"against {row['case_id']}'s first turn")

    # Experiment B: the graph explorer's instructions add the graph tools in place of A's finish line.
    rows = read_jsonl(B_RUN / "graph_explorations.jsonl")
    row = first_ok(rows)
    episode = next(e for e in read_jsonl(B_RUN / "episodes.jsonl") if e["case_id"] == row["case_id"])
    log = explorer.GraphLog(observations(row["case_id"], episode["event_count"]))
    check(explorer.render_graph(log, [], False), row["turns"][0]["prompt_sha256"], f"Experiment B, {row['case_id']}")
    start = explorer.GRAPH_INSTRUCTIONS.index("The operator also has")
    added = explorer.GRAPH_INSTRUCTIONS[start:explorer.GRAPH_INSTRUCTIONS.index("\n- finish:", start)]
    ledger.text("pr.graph", added,
                how=f"what the graph explorer's instructions ({explorer.GRAPH_PROMPT_VERSION}) add to the explorer's, "
                    f"before its finish line; checked against {row['case_id']}'s first turn")

    # Experiment C: Jev's questions (the digest in protocol.json) and the judge (one recorded group prompt).
    protocol = json.loads((C_RUN / "protocol.json").read_text())
    if digest([flow.QUESTIONS]) != protocol["labeler"]["questions_sha256"]:
        raise ValueError("Experiment C: Jev's questions in the code aren't the ones the run recorded")
    ledger.value("pr.jev.model", protocol["labeler"]["model"], how="the Jev model (logs/scaling_flow/protocol.json)")
    ledger.text("pr.jev", questions_text(flow.QUESTIONS),
                how=f"Jev's three yes/no questions ({flow.LABEL_VERSION}), each with what yes and no mean; checked "
                    "against the digest in logs/scaling_flow/protocol.json")
    judgment = next(j for j in read_jsonl(C_RUN / "flow_judgments.jsonl")
                    if j["case_id"] == EXAMPLE and j["status"] == "ok")
    episode = next(e for e in read_jsonl(B_RUN / "episodes.jsonl") if e["case_id"] == EXAMPLE)
    events = observations(EXAMPLE, episode["event_count"])
    group = judgment["groups"][0]
    check(flow.judge_prompt(events, group["agents"]), group["prompt_sha256"], f"Experiment C, {EXAMPLE}")
    requests = dict(flow.label_requests(explorer.Log(events)))
    top = [g for g in read_jsonl(C_RUN / "flow_groups.jsonl") if g["case_id"] == EXAMPLE][-1]["groups"][0]
    call = max(top["calls"], key=lambda c: top["labels"][c]["source"])
    ledger.text("pr.jev.request", "\n\n".join(requests[call]),
                how=f"{EXAMPLE}: Jev's request for the top group's most likely source call ({call}), as sent")
