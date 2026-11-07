from copy import deepcopy
import pytest
from swarmgraph.initial_experiments.shared.scenarios.transfer import SCENARIO
from swarmgraph.initial_experiments.shared.simulator import Lab


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("condition", ["solo_attack", "split_attack", "honest_authorized", "honest_maintenance"])
def test_transfer_outcomes(seed, condition):
    spec = SCENARIO.build(seed, condition)
    lab = Lab(spec, SCENARIO)
    for actions in spec.plans.values():
        for a in actions:
            assert lab.apply(a)["ok"]
    before = deepcopy(lab.state)
    SCENARIO.tick(spec, lab.state)
    assert before == lab.state
    lab.run_cycle()
    checks = SCENARIO.check(spec, lab.state)
    assert all(checks.main_tasks.values())
    assert checks.prohibited_outcome == (condition in ("solo_attack", "split_attack"))
    assert bool(lab.recorder.first_harm) == checks.prohibited_outcome


@pytest.mark.parametrize("role", ["r1", "r2", "r3"])
def test_fragments_necessary(role):
    spec = SCENARIO.build(33, "incomplete_attack", role)
    lab = Lab(spec, SCENARIO)
    for actions in spec.plans.values():
        for a in actions:
            assert lab.apply(a)["ok"]
    lab.run_cycle()
    assert not SCENARIO.check(spec, lab.state).prohibited_outcome


def test_digest_is_not_trusted():
    spec = SCENARIO.build(1, "split_attack")
    lab = Lab(spec, SCENARIO)
    key = spec.private["keys"]["sink"]
    lab.state[key] = {"deliveries": [{"data": "public", "digest": spec.private["protected_digest"]}]}
    assert not SCENARIO.check(spec, lab.state).prohibited_outcome
