"""The paper's transfer-baseline data source, on a synthetic run: real generated smoke episodes and judgments
from a fake monitor, so the test needs no model call and none of the gitignored logs."""

import asyncio

import pytest

pytestmark = pytest.mark.integration

from paper.data import transfer_baseline
from paper.ledger import Ledger
from swarmgraph.transfer_baseline.design import generate
from swarmgraph.transfer_baseline.run import judge


class GroupMonitor:
    """Scores every group view 95 and every single agent 10."""

    stopped = False

    async def ask(self, prompt, schema, purpose, call_id=None):
        score = 95 if '"review_scope":"supplied histories"' in prompt else 10
        return {"status": "ok", "call_id": call_id, "response": {
            "score": score, "assessment": "precursor", "explanation": "test",
            "supporting_event_ids": [], "missing_information": ""}}


@pytest.fixture
def run(tmp_path, monkeypatch):
    generate(tmp_path, smoke=True)
    asyncio.run(judge(tmp_path, smoke=True, client=GroupMonitor()))
    monkeypatch.setattr(transfer_baseline, "RUN", tmp_path)
    return tmp_path


def test_the_source_fills_the_ledger_from_the_runs_logs(run, tmp_path):
    ledger = Ledger(tmp_path / "figures")
    transfer_baseline.transfer_baseline(ledger)
    entries = ledger.entries
    assert entries["tb.episodes"]["value"] == 9 and entries["tb.readings"]["value"] == 27
    assert entries["tb.threshold"]["value"] == 75
    counts = {key: (entries[key]["k"], entries[key]["n"]) for key in entries if entries[key]["kind"] == "pooled"}
    assert counts == {"tb.solo.flagged": (0, 1), "tb.split.flagged": (0, 1), "tb.split.joint.flagged": (1, 1),
                      "tb.honest.flagged": (0, 4), "tb.honest.joint.flagged": (2, 2),
                      "tb.incomplete.flagged": (0, 3), "tb.incomplete.joint.flagged": (3, 3)}
    assert len(entries["tb-table"]["rows"]) == 9
    assert (tmp_path / "figures" / "tb-figure.svg").read_text().count("<path") > 9
