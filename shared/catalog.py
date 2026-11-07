from importlib import import_module

EXPERIMENTS = [
    {"experiment_id": f"E{index+1:02d}", "scenario": scenario, "generation_mode": mode,
     "folder": f"00_{scenario}_{mode}"}
    for index, (scenario, mode) in enumerate((s, m) for s in ("release", "transfer", "audit")
                                            for m in ("constructed", "scripted", "live"))
]


def scenario_for(name):
    return import_module(f"shared.scenarios.{name}").SCENARIO


def experiment_for(identifier):
    return next(e for e in EXPERIMENTS if e["experiment_id"] == identifier)
