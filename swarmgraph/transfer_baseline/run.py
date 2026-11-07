"""Prepare, monitor and report the Step 1 transfer baseline.

    uv run python -m swarmgraph.transfer_baseline.run prepare            # 36 scripted episodes, no model calls
    uv run python -m swarmgraph.transfer_baseline.run monitor --concurrency 8   # 540 judge calls
    uv run python -m swarmgraph.transfer_baseline.run report
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import random

from .codex_cli import CodexClient
from .design import DEFAULT_REPORT, DEFAULT_ROOT, PROTOCOL, prepare, verify_source
from .io import utc_now, write_json
from .monitoring import judge_episode, missing_judgments
from .validation import validate_run

STOP_NAMES = ("STOP", "STOP_SECURITY", "STOP_ACCESS")
TERMINAL = {"access_forbidden", "safety_restriction", "authentication", "usage_limit", "stop_file"}


class MonitorClient:
    """Only review records; never request actor behavior.

    Any access restriction, authentication failure or usage limit writes
    STOP_ACCESS and stops queued calls. No alternate model, route, or revised
    prompt is used.
    """
    def __init__(self, root: Path, concurrency=4):
        self.root = Path(root)
        self.client = CodexClient(self.root, concurrency=concurrency, timeout=180, retries=1)
        self.semaphore = asyncio.Semaphore(concurrency)

    @property
    def stopped(self):
        return any((self.root / name).exists() for name in STOP_NAMES)

    async def ask(self, prompt, schema, purpose, call_id=None):
        if purpose != "monitor":
            raise ValueError("This baseline permits monitor calls only")
        async with self.semaphore:
            if self.stopped:
                return {"status": "not_run", "call_id": call_id, "error_kind": "study_stopped"}
            result = await self.client.ask(prompt, schema, purpose, call_id)
            if result.get("error_kind") in TERMINAL or result["status"] == "usage_limit":
                write_json(self.root / "STOP_ACCESS", {"at": utc_now(), "call_id": call_id,
                           "error_kind": result.get("error_kind"), "result": result.get("output_path")})
            return result


async def monitor(root: Path, concurrency: int = 4) -> None:
    """Take every planned reading that is not yet saved; resumable."""
    study = verify_source(root)
    readings = PROTOCOL["readings_per_view"]
    client = MonitorClient(root, concurrency)
    if client.stopped:
        raise RuntimeError("Study access/usage stop exists; no monitor calls launched")
    pending = []
    for case in study["cases"]:
        directory = root / "runs" / case["run_id"]
        if not (directory / "private/outcomes.jsonl").exists():
            raise RuntimeError("Episodes are missing; run the prepare phase first")
        if missing_judgments(directory, readings):
            pending.append(directory)
    # Interleave conditions so any drift over time is not confounded with run type.
    random.Random(PROTOCOL["version"]).shuffle(pending)
    queue = asyncio.Queue()
    for directory in pending:
        queue.put_nowait(directory)
    processed = 0

    async def worker():
        nonlocal processed
        while not queue.empty() and not client.stopped:
            directory = queue.get_nowait()
            await judge_episode(client, directory, readings)
            write_json(directory / "validation.json", validate_run(directory))
            manifest = json.loads((directory / "manifest.json").read_text())
            manifest["monitored"] = not missing_judgments(directory, readings)
            write_json(directory / "manifest.json", manifest)
            processed += 1
            print(json.dumps({"at": utc_now(), "processed": processed, "scheduled": len(pending),
                              "run_id": directory.name, "stopped": client.stopped}), flush=True)
    await asyncio.gather(*(worker() for _ in range(max(1, min(concurrency, len(pending))))))
    if client.stopped:
        raise RuntimeError("Monitoring stopped after CLI access or usage restriction; partial records retained")


async def main(args):
    from .analysis import report
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    if args.phase in {"prepare", "all"}:
        study = prepare(root)
        print(json.dumps({"prepared": len(study["cases"]), "root": str(root)}))
    if args.phase in {"monitor", "all"}:
        try:
            await monitor(root, args.concurrency)
        finally:
            report(root, output)
    elif args.phase == "report":
        report(root, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=("prepare", "monitor", "report", "all"))
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--concurrency", type=int, default=4)
    asyncio.run(main(parser.parse_args()))
