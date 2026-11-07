# E05: transfer / scripted

Tests whether splitting storage, staging, and synchronization changes across three agents reduces detection. The model file is dummy data and the partner is a local record store.

The generation-specific entry point is `run.py`; the shared scenario is `shared/scenarios/transfer.py`, with generation and monitoring in `shared/generation.py` and `shared/monitoring.py`.

Run from the project root:

```bash
uv run python 00_transfer_scripted/run.py --batch e05_development --pairs 3 --benign 1 --incomplete 3
```

See root README and PROTOCOL.md for calibration, held-out evaluation, result storage, and limitations. Constructed stories require independent replay validation; scripted/live outcomes come from actual state transitions.
