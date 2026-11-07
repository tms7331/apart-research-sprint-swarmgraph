"""Keep test data small: a smoke experiment is still far too large for a test."""
import pytest


@pytest.fixture(scope="session")
def generate_small_fleets():
    from swarmgraph.scaling import design

    def generate(root, smoke=False):
        cases = [case for case in design.planned_cases(smoke) if case["honest_teams"] <= 3]
        spec = {**design.protocol(smoke), "honest_teams": [0, 1, 3], "episodes": len(cases)}
        spec["planned_monitor_readings"] = len(cases) * spec["readings_per_view"]
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(design, "planned_cases", lambda smoke=False: cases)
            patch.setattr(design, "protocol", lambda smoke=False: spec)
            return design.generate(root, smoke)

    return generate


@pytest.fixture(scope="session", autouse=True)
def bound_scaling_test_fleets():
    from swarmgraph.scaling import design

    original = design.generate_fleet_episode

    def bounded(episodes, case):
        if case["honest_teams"] > 3:
            pytest.fail("Tests must use generate_small_fleets, not the full/smoke experiment (up to 543 agents)")
        return original(episodes, case)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(design, "generate_fleet_episode", bounded)
        yield
