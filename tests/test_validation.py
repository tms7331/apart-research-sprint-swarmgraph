from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from swarmgraph.initial_experiments.shared.io import append_jsonl, write_json
from swarmgraph.initial_experiments.shared.recorder import Recorder
from swarmgraph.initial_experiments.shared.validation import validate_observations, validate_run


def observations():
    recorder = Recorder("r_example")
    recorder.emit("policy_published", {"text": "Protected private model files require authorization; do not disable audit."})
    recorder.emit("tool_call", {"tool": "read", "arguments": {"key": "protected/file"}}, "a1", "c1")
    recorder.emit("tool_result", {"ok": True, "record": {"classification": "private"}}, "a1", "c1")
    return recorder.observations


class ValidationTests(unittest.TestCase):
    def test_valid_records_and_normal_policy_words(self):
        self.assertEqual(validate_observations(observations()), [])

    def test_required_fields_ids_sequences_and_time(self):
        for mutate in (
            lambda e: e[0].pop("source_time"),
            lambda e: e[1].update(event_id=e[0]["event_id"]),
            lambda e: e[1].update(arrival_seq=1),
            lambda e: e[2].update(source_seq=1),
            lambda e: e[2].update(received_at="2020-01-01T00:00:00Z"),
            lambda e: e[2].update(run_id="another"),
            lambda e: e[0].update(schema_version=2),
        ):
            events = observations()
            mutate(events)
            self.assertTrue(validate_observations(events))

    def test_call_result_identity_and_order(self):
        for mutate in (
            lambda e: e[2].update(call_id="future"),
            lambda e: e[2].update(agent_id="a2"),
            lambda e: e[2]["payload"].update(tool="patch"),
            lambda e: e.pop(),
        ):
            events = observations()
            mutate(events)
            self.assertTrue(validate_observations(events))

    def test_nested_labels_are_rejected(self):
        for field in ("malicious", "true_author", "attack_step", "hidden_plan", "private_plans"):
            events = observations()
            events[0]["payload"]["records"] = [{"nested": {field: "secret"}}]
            self.assertTrue(any("forbidden" in e for e in validate_observations(events)))

    def populate(self, root, mode="scripted", verification="execution_verified"):
        write_json(root / "manifest.json", {"run_id": "r_example", "generation_mode": mode})
        for event in observations():
            append_jsonl(root / "observations.jsonl", event)
        append_jsonl(root / "private/outcomes.jsonl", {"verification_status": verification})

    def test_valid_run_all_modes(self):
        for mode, status in (("scripted", "execution_verified"), ("live", "execution_verified"),
                             ("constructed", "asserted"), ("constructed", "replay_verified")):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.populate(root, mode, status)
                result = validate_run(root)
                self.assertTrue(result["valid"], result)
                self.assertEqual(result["counts"]["observations.jsonl"], 3)
                self.assertTrue(result["warnings"])

    def test_generation_verification_mismatch(self):
        for mode, status in (("constructed", "execution_verified"), ("live", "asserted")):
            with tempfile.TemporaryDirectory() as tmp:
                self.populate(Path(tmp), mode, status)
                self.assertFalse(validate_run(tmp)["valid"])

    def test_monitor_prefix_support_and_failure_scores(self):
        base = {"prefix_boundary": 2, "input_event_ids": ["e00001", "e00002"],
                "supporting_event_ids": ["e00002"], "result_status": "ok", "score": 82}
        changes = ({}, {"input_event_ids": ["e00003"]}, {"supporting_event_ids": ["e00003"]},
                   {"score": None}, {"result_status": "api_error", "score": 0},
                   {"result_status": "api_error", "score": None}, {"prefix_boundary": 5})
        for index, change in enumerate(changes):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.populate(root)
                append_jsonl(root / "monitor_results.jsonl", {**base, **change})
                result = validate_run(root)
                self.assertEqual(result["valid"], index in {0, 5}, result)

    def test_derived_links_cannot_use_future_evidence(self):
        for boundary, valid in ((2, False), (3, True)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.populate(root)
                append_jsonl(root / "derived_links.jsonl", {"link_id": "l1", "available_after_arrival_seq": boundary,
                                                           "supporting_event_ids": ["e00003"]})
                result = validate_run(root)
                self.assertEqual(result["valid"], valid, result)

    def test_rejected_citation_is_missing_judgment_not_invalid_execution(self):
        base = {"prefix_boundary": 2, "input_event_ids": ["e00001", "e00002"],
                "supporting_event_ids": ["invented_event"],
                "result_status": "invalid_evidence_citation", "score": None}
        for change, valid in (({}, True), ({"result_status": "api_error"}, True), ({"result_status": "ok", "score": 70}, False),
                              ({"score": 70}, False), ({"input_event_ids": ["e00003"]}, False)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.populate(root)
                append_jsonl(root / "monitor_results.jsonl", {**base, **change})
                result = validate_run(root)
                self.assertEqual(result["valid"], valid, result)
                if valid:
                    self.assertTrue(any("rejected judgment" in warning for warning in result["warnings"]))

    def test_missing_and_malformed_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(validate_run(tmp)["valid"])
            root = Path(tmp)
            self.populate(root)
            (root / "observations.jsonl").write_text("{bad json}\n")
            self.assertTrue(any("cannot parse" in e for e in validate_run(tmp)["errors"]))


if __name__ == "__main__":
    unittest.main()
