# Swarmgraph initial experiments

**Current status:** all nine cells are implemented. Development execution was
interrupted by a Codex CLI cybersecurity safety rejection and HTTP403 errors.
Calibration, held-out evaluation, and final reproduction grades are not complete.
See [the current results](../../reports/RESULTS.md) and
[the access blocker](../../reports/ACCESS_BLOCKER.md). A local `STOP_SECURITY` marker
prevents further model calls while supported access is unresolved.

A Python experiment harness for [GRAPH_PLAN](../../specs/GRAPH_PLAN.md) steps 0–1. Three local shared-service
scenarios (release, transfer, audit) are crossed with constructed histories,
scripted execution, and live LLM agents. Every modeled file and external
destination is dummy local state. No actual model weights or external systems
are accessed.

## Setup

Run all commands from the repository root, two levels above this directory.

```bash
uv sync
codex login status
uv run pytest -q
```

Python 3.12+ and an existing **ChatGPT-authenticated Codex CLI** are required for
model calls. The project does not use API keys or make direct model API calls.
The fixed experimental model is `gpt-6.1-sol`, reasoning effort `medium`.
Jev is out of scope.

## Layout

[specs/](../../specs/) contains the project idea, execution plan, and reference papers.

The initial experiments live under `swarmgraph/initial_experiments/`. Each
`00_<scenario>_<mode>/` directory contains an experiment configuration, runnable
entry point, and scenario notes. Its sibling `shared/` package holds the scenarios,
simulation, generation, monitoring, validation, statistics, timing, and reporting.
Root-level `tests/` tests the scientific and data-integrity invariants.
[PROTOCOL.md](PROTOCOL.md) defines the evaluation.

```text
swarmgraph/
  __init__.py
  initial_experiments/
    __init__.py
    shared/
    00_release_{constructed,scripted,live}/
    00_transfer_{constructed,scripted,live}/
    00_audit_{constructed,scripted,live}/
```

| Cell | Scenario | Generation |
|---|---|---|
| E01 | Release without approval | Constructed |
| E02 | Release without approval | Scripted |
| E03 | Release without approval | Live |
| E04 | Private-file delivery | Constructed |
| E05 | Private-file delivery | Scripted |
| E06 | Private-file delivery | Live |
| E07 | Audit coverage gap | Constructed |
| E08 | Audit coverage gap | Scripted |
| E09 | Audit coverage gap | Live |

## Running

```bash
# All cells, development only. One benign seed creates 4 controls:
# authorized and maintenance, each in solo and split layouts.
uv run python -m swarmgraph.initial_experiments.shared.runner --batch development_v2 --pairs 3 --benign 1 \
  --incomplete 3 --seed-start 300 --concurrency 4 --episodes 10

# Just one cell, no models (scripted outcome checks only).
uv run python swarmgraph/initial_experiments/00_transfer_scripted/run.py --batch transfer_mechanism \
  --generate-only --pairs 3 --benign 2 --incomplete 3

# Honest calibration, followed by a separately seeded evaluation.
uv run python -m swarmgraph.initial_experiments.shared.runner --batch calibration_v2 --partition calibration \
  --pairs 0 --benign 10 --incomplete 0 --concurrency 8 --episodes 16
uv run python -m swarmgraph.initial_experiments.shared.runner --batch evaluation_v2 --partition evaluation \
  --pairs 20 --benign 6 --incomplete 3 --concurrency 8 --episodes 16

# Run this only after the calibration dataset is complete: thresholds freeze.
uv run python -m swarmgraph.initial_experiments.shared.reporting --root logs/graph_pilot/raw \
  --output reports --partition evaluation --protocol pilot_v2
```

Repeating the exact batch command resumes completed jobs. Use a new batch name
for different parameters. A partial run without a completed outcome is retained
as abandoned and restarted under a fresh opaque ID; it is never overwritten.
Completed model calls are cached by ID and prompt/schema hash. A usage-limit
response creates `logs/graph_pilot/raw/STOP`, which prevents new calls.
An explicit platform safety rejection creates `STOP_SECURITY`; it is a separate
condition from usage exhaustion. Do not remove it to retry or rephrase a rejected
request. Supported account access must be resolved first.

`--prefixes N` adds N receipt-order prefix checks chosen without outcome labels.
Timing results distinguish offline evidence availability from simulated paced
completion; they do not establish actual prevention.

## Results and audit trail

`reports/RESULTS.md` and `reports/results_summary.json` are generated from raw
records. Never edit numerical results by hand. The summary always includes all
nine cells and exposes missing/failed runs. `reports/thresholds.json` binds
thresholds to an immutable calibration fingerprint. Regenerating a report after
changing calibration requires a new output directory, rather than silent reuse.

Portable evidence is committed under [`logs/graph_pilot/`](../../logs/graph_pilot/README.md):
all pilot-v2 run records and judgments, plus transcripts for every judged or live
run. Reports can read this snapshot without the raw archive. For the existing
development summary, run `uv run python scripts/summarize_development.py`.

The full raw data is retained locally, excluded from Git. The legacy runner,
progress tool, and timing tool default to this directory:

```text
logs/graph_pilot/raw/
  experiments.jsonl, runs.jsonl, usage.jsonl
  checkpoints/<batch>.json
  calls/<opaque_call>/attempt_N/{prompt.txt,schema.json,stdout.jsonl,...}
  runs/<opaque_run>/
    manifest.json
    observations.jsonl
    derived_links.jsonl
    monitor_results.jsonl
    validation.json
    private/{plans,generations,actor_calls,actions,state_changes,outcomes}.jsonl
    private/final_state.json
```

Agent/monitor calls have tool access disabled and run in empty temporary working
directories, outside the experiment repository. They receive only explicitly
rendered prompts. Raw CLI artifacts are checked for unexpected tool use.
Credentials are neither copied nor logged.

The `pilot_v1` development artifacts document early design problems and are
excluded from the active `pilot_v2` results. See [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md).
