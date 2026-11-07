# Exploratory graph pilot evidence

This is the compact, portable record of the original nine-cell `pilot_v2`
development study. Start with [the results](../../reports/RESULTS.md),
[the monitor audit](../../reports/DEVELOPMENT_MONITOR_AUDIT.md), or
[the execution audit](../../reports/DEVELOPMENT_EXECUTION_AUDIT.md).

The study started 128 runs: 118 have saved outcomes and 10 remain unknown.
The 267 recorded judgments include 262 successful readings and 5 errors.
There was no calibration or held-out evaluation. These exploratory results
are separate from the newer [transfer baseline](../transfer_baseline/).

## Files

| File | Contents |
|---|---|
| `episodes.jsonl` | All 128 original manifests, saved outcomes (or null), validation records, event counts, and transcript paths. `case_id` is the original run ID. |
| `judgments.jsonl` | Every saved pilot-v2 monitor judgment, including errors, scores, explanations, input event IDs, and supporting citations. Join by `run_id`. |
| `actor_calls.jsonl` | All 174 saved live actor decision records, including failed calls. Join by `run_id`. |
| `episodes/<run_id>/observations.jsonl` | Original transcript bytes for all 25 judged runs and all 17 live runs: 37 distinct runs. |
| `protocol.json` | Export scope, counts, exclusions, and limitations. |
| `inventory.json` | SHA256 hashes of the source records and exported data files. Source paths are relative to `raw/`. |
| `usage_summary.json` | Historical usage across the whole pilot archive, including pilot-v1 calls. |
| `access_status.json` | A copy of the historical stop-marker contents; the export makes no model calls. |

The transcript selection is based on recorded judgments or live generation,
not on whether a run succeeded. All unjudged outcomes are retained in the
episode index. Missing outcomes stay null; missing or failed judgments are
never converted to zero suspicion.

Records retain their original IDs, timestamps, scores, and explanations.
Only `output_path` and `call_output_path` provenance pointers are rebased to
`logs/graph_pilot/raw/`. The original paths and bytes remain in the raw archive.

## Recompute or inspect

These commands are offline and require no model calls:

```bash
# Regenerate the nine-cell summary from the portable files alone.
uv run python scripts/summarize_development.py

# Generate the detailed, explicitly uncalibrated development report.
uv run python -m swarmgraph.initial_experiments.shared.reporting \
  --root logs/graph_pilot --partition development --protocol pilot_v2 \
  --output /tmp/graph-pilot-report

# Re-export identical evidence when the local raw archive is available.
uv run python -m swarmgraph.initial_experiments.shared.archive
```

The exporter refuses to overwrite a different snapshot. The original 81
pilot-v1 runs are excluded from this snapshot; their records remain local.
Consequently, reports generated from this snapshot count only its 128 input
runs, while older archive-wide metadata also counts the excluded pilot-v1 work.

## Local raw archive

`raw/` is gitignored. It contains the complete former
`experiments/graph_pilot/` directory: all 209 run directories, CLI prompts and
responses, plans, state changes, checkpoints, and runtime logs. It was moved
without changing any original file bytes. It is needed only for full raw
inspection, not for reading or recomputing the published pilot summaries.

The historical `raw/STOP_SECURITY` remains in place. The legacy runner,
progress tool, and timing tool now default to this raw directory. No stopped
model calls were resumed. The old machine-readable audits under `reports/`
retain their original source paths and hashes as historical provenance;
replace their `experiments/graph_pilot/` prefix with `logs/graph_pilot/raw/`
when locating those original files locally.
