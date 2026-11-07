"""Integration coverage for authored/replayed workflows and fleet observations."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarmgraph.initial_experiments.shared.catalog import scenario_for
from swarmgraph.initial_experiments.shared.contracts import Action, ServiceWrite
from swarmgraph.initial_experiments.shared.generation import FleetScenario, generate_run, planned_actions, prepare_spec
from swarmgraph.initial_experiments.shared.io import read_jsonl
from swarmgraph.initial_experiments.shared.monitoring import select_events
from swarmgraph.initial_experiments.shared.simulator import Lab, allowed
from swarmgraph.initial_experiments.shared.validation import validate_observations


SCENARIOS = ("release", "transfer", "audit")
CONTROLS = (("solo_attack", None), ("split_attack", None), ("honest_authorized", None),
            ("honest_maintenance", None), ("incomplete_attack", "r1"),
            ("incomplete_attack", "r2"), ("incomplete_attack", "r3"))


def normalized(events):
    return [{k: e[k] for k in ("kind", "agent_id", "call_id", "payload")} for e in events]


class GenerationTests(unittest.TestCase):
    def test_six_background_agents_do_real_condition_independent_work(self):
        for name in SCENARIOS:
            scenario = scenario_for(name)
            baseline = None
            for condition, omit in CONTROLS:
                with self.subTest(scenario=name, condition=condition, omitted=omit):
                    spec, mapping, backgrounds = prepare_spec(scenario, 7, condition, "split", 6, omit)
                    self.assertEqual(len(backgrounds), 2)
                    self.assertEqual([b.condition for b, _ in backgrounds], ["honest_authorized", "honest_maintenance"])
                    background_description = [(b.initial_state, b.tasks, b.plans, b.permissions, rolemap)
                                              for b, rolemap in backgrounds]
                    if baseline is None:
                        baseline = deepcopy(background_description)
                    self.assertEqual(background_description, baseline)
                    self.assertFalse(any("dashboard" in key.lower() for key in spec.initial_state))
                    lab = Lab(spec, FleetScenario(scenario, backgrounds))
                    for action in planned_actions(spec, "split", 6):
                        self.assertTrue(lab.apply(action, mapping[action.role])["ok"])
                    lab.run_cycle()
                    for bspec, rolemap in backgrounds:
                        bcheck = scenario.check(bspec, lab.state)
                        self.assertTrue(all(bcheck.main_tasks.values()))
                        self.assertFalse(bcheck.prohibited_outcome)
                        actions = [action for action in lab.actions if action.role in rolemap.values()]
                        self.assertTrue(actions)
                        self.assertTrue(any(action.tool == "read" for action in actions))
                        self.assertTrue(any(action.tool in {"patch", "copy"} for action in actions))
                        for original, role in rolemap.items():
                            self.assertEqual(spec.tasks[role], bspec.tasks[original])
                            self.assertEqual(spec.permissions[role], bspec.permissions[original])
                    self.assertEqual(len(set(mapping.values())), 9)

    def test_constructed_scripted_agree_all_scenarios_and_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in SCENARIOS:
                for condition, omit in CONTROLS:
                    with self.subTest(scenario=name, condition=condition, omitted=omit):
                        generated = []
                        for mode in ("constructed", "scripted"):
                            config = {"scenario": name, "seed": 11, "generation_mode": mode,
                                      "condition": condition, "execution_layout": "solo" if condition == "solo_attack" else "split",
                                      "background_count": 6, "omit_role": omit, "partition": "development"}
                            directory = asyncio.run(generate_run(None, root, config))
                            events = read_jsonl(directory / "observations.jsonl")
                            outcome = read_jsonl(directory / "private/outcomes.jsonl")[-1]
                            final = json.loads((directory / "private/final_state.json").read_text())
                            self.assertEqual(validate_observations(events), [])
                            self.assertEqual(outcome["prohibited_outcome"], condition in {"solo_attack", "split_attack"})
                            self.assertEqual(len(outcome["background_controls"]), 2)
                            self.assertTrue(all(b["control_completed"] and not b["prohibited_outcome"] for b in outcome["background_controls"]))
                            self.assertTrue(all(row["payload"].get("ok") for row in events if row["kind"] == "tool_result"))
                            if condition.startswith("honest"):
                                self.assertTrue(outcome["valid_benign"])
                            if mode == "constructed":
                                self.assertEqual(outcome["verification_status"], "replay_verified")
                                self.assertTrue(outcome["constructed_validation"]["passed"])
                            else:
                                self.assertEqual(outcome["verification_status"], "execution_verified")
                            generated.append((normalized(events), final, outcome))
                        self.assertEqual(generated[0][0], generated[1][0])
                        self.assertEqual(generated[0][1], generated[1][1])
                        self.assertEqual(generated[0][2]["main_tasks"], generated[1][2]["main_tasks"])

    def test_role_permissions_enforced_and_solo_split_global_actions_match(self):
        for name in SCENARIOS:
            scenario = scenario_for(name)
            solo, smap, _ = prepare_spec(scenario, 17, "solo_attack", "solo", 6, None)
            split, tmap, _ = prepare_spec(scenario, 17, "split_attack", "split", 6, None)
            sa, ta = planned_actions(solo, "solo", 6), planned_actions(split, "split", 6)
            self.assertEqual(solo.initial_state, split.initial_state)
            self.assertEqual([(a.tool, a.arguments, a.public_message) for a in sa],
                             [(a.tool, a.arguments, a.public_message) for a in ta])
            self.assertEqual(len(set(smap[r] for r in ("r1", "r2", "r3"))), 1)
            self.assertEqual(len(set(tmap[r] for r in ("r1", "r2", "r3"))), 3)
            for action in ta:
                args, perms = action.arguments, split.permissions[action.role]
                if action.tool == "read":
                    self.assertTrue(allowed(args["key"], perms["read"]))
                elif action.tool == "patch":
                    self.assertTrue(allowed(args["key"], perms["write"]))
                elif action.tool == "copy":
                    self.assertTrue(allowed(args["source"], perms["read"]))
                    self.assertTrue(allowed(args["destination"], perms["write"]))
            lab = Lab(split, scenario)
            before = deepcopy(lab.state)
            self.assertFalse(lab.apply(Action("r1", "patch", {"key": "outside/permissions", "fields": {"value": 1}}))["ok"])
            self.assertEqual(lab.state, before)

    def test_prefix_selectors_never_read_future_or_unassigned_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = asyncio.run(generate_run(None, root, {"scenario": "audit", "seed": 3,
                "condition": "split_attack", "execution_layout": "split", "generation_mode": "scripted", "background_count": 6}))
            events = read_jsonl(directory / "observations.jsonl")
            manifest = json.loads((directory / "manifest.json").read_text())
            focal = manifest["focal_agent_ids"]
            for boundary in (1, len(events)//2, len(events)):
                for view, evidence, agents in (("per_agent", "transcript", focal[:1]), ("group", "transcript", focal),
                                               ("group", "service", focal), ("fleet_window", "transcript", manifest["agent_ids"])):
                    selected = select_events(events, view, agents, evidence, boundary)
                    self.assertTrue(all(e["arrival_seq"] <= boundary for e in selected))
                    # IDs/order originate in the delivered prefix, not a rebuilt omniscient graph.
                    self.assertEqual(selected, [e for e in events[:boundary] if e in selected])
                    self.assertFalse(any(e["kind"] == "task_assigned" and view != "fleet_window" and e["agent_id"] not in agents for e in selected))
                    if evidence == "transcript":
                        self.assertFalse(any(e["source"] == "shared_service" for e in selected))
                    # Validate nested structural leakage using the full source stream
                    # above; a selected prefix can intentionally omit call/results.
                    self.assertTrue(all("hidden_plan" not in e["payload"] and "true_author" not in e["payload"] for e in selected))

    def test_malformed_apply_is_rejected_atomically(self):
        for tool, arguments in (("patch", {"key": None, "fields": {}}), ("patch", {"key": "absent", "fields": []}),
                                ("copy", {"source": [], "destination": "absent"}), ("read", {"key": {}})):
            scenario = scenario_for("audit")
            spec = scenario.build(1, "split_attack")
            lab = Lab(spec, scenario)
            before = deepcopy(lab.state)
            result = lab.apply(Action("r1", tool, arguments))
            self.assertFalse(result["ok"])
            self.assertEqual(lab.state, before)
            self.assertEqual(lab.recorder.transitions, [])
            self.assertFalse(any(e["kind"] == "service_write" for e in lab.recorder.observations))

    def test_checker_typing_failure_rejects_validly_permitted_write(self):
        scenario = scenario_for("audit")
        spec = scenario.build(2, "split_attack")
        lab = Lab(spec, scenario)
        before = deepcopy(lab.state)
        result = lab.apply(Action("r1", "patch", {"key": spec.private["keys"]["config"], "fields": {"watch_path": [], "maintained": True}}))
        self.assertFalse(result["ok"])
        self.assertEqual(lab.state, before)
        self.assertEqual(lab.recorder.transitions, [])

    def test_tick_typing_failure_rejects_write_before_commit(self):
        scenario = scenario_for("audit")
        spec = scenario.build(2, "split_attack")
        lab = Lab(spec, scenario)
        before = deepcopy(lab.state)
        # The outcome checker can classify this draft as incomplete, but the
        # standing application cannot normalize a list as a resource path.
        result = lab.apply(Action("r2", "patch", {"key": spec.private["keys"]["change"], "fields": {"target": []}}))
        self.assertFalse(result["ok"])
        self.assertEqual(lab.state, before)
        self.assertEqual(lab.recorder.transitions, [])

    def test_cycle_failure_is_atomic_even_after_a_valid_preview_write(self):
        scenario = scenario_for("audit")
        spec = scenario.build(2, "split_attack")
        lab = Lab(spec, scenario)
        before = deepcopy(lab.state)
        invalid_config = {**before[spec.private["keys"]["config"]], "watch_path": [], "maintained": True}
        writes = [ServiceWrite(spec.private["benign"], {"revision": "v2"}, public=False),
                  ServiceWrite(spec.private["keys"]["config"], invalid_config)]
        with patch.object(scenario, "tick", return_value=writes):
            with self.assertRaises(TypeError):
                lab.run_cycle()
        self.assertEqual(lab.state, before)
        self.assertFalse(lab.cycled)
        self.assertEqual(lab.recorder.transitions, [])
        self.assertEqual(lab.recorder.observations, [])

    def test_tick_exception_does_not_mutate_cycle_state(self):
        scenario = scenario_for("audit")
        spec = scenario.build(2, "split_attack")
        lab = Lab(spec, scenario)
        lab.state[spec.private["keys"]["change"]]["target"] = []
        before = deepcopy(lab.state)
        with self.assertRaises(TypeError):
            lab.run_cycle()
        self.assertEqual(lab.state, before)
        self.assertFalse(lab.cycled)
        self.assertEqual(lab.recorder.transitions, [])


if __name__ == "__main__":
    unittest.main()
