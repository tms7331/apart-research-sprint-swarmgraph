"""Prepare, calibrate and evaluate the scripted transfer baseline."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import random

from swarmgraph.initial_experiments.shared.codex_cli import CodexClient
from swarmgraph.initial_experiments.shared.io import utc_now, write_json
from swarmgraph.initial_experiments.shared.monitoring import judge_run
from swarmgraph.initial_experiments.shared.reporting import load_runs, reading
from .design import DEFAULT_ROOT, DEFAULT_REPORT, prepare, verify_source

STOP_NAMES = ("STOP", "STOP_SECURITY", "STOP_ACCESS")
TERMINAL = {"access_forbidden", "safety_restriction", "authentication", "usage_limit", "stop_file"}


class MonitorClient:
    """Only review records; never request live/adversarial actor behavior.

    The dedicated study has its own records and stop files. The earlier E06
    restriction remains untouched. Any access restriction in this task stops
    its queued calls too; no alternate model, route, or revised prompt is used.
    """
    def __init__(self, root: Path, concurrency=4):
        self.root = root
        self.client = CodexClient(root, concurrency=concurrency, timeout=180, retries=1)
        self.semaphore = asyncio.Semaphore(concurrency)

    @property
    def stopped(self):
        return any((self.root/name).exists() for name in STOP_NAMES)

    async def ask(self, prompt, schema, purpose, call_id=None):
        if purpose != "monitor":
            raise ValueError("This baseline permits monitor calls only")
        async with self.semaphore:
            if self.stopped:
                return {"status": "not_run", "call_id": call_id, "error_kind": "study_stopped"}
            result = await self.client.ask(prompt, schema, purpose, call_id)
            if result.get("error_kind") in TERMINAL or result["status"] == "usage_limit":
                write_json(self.root/"STOP_ACCESS", {"at": utc_now(), "call_id": call_id,
                    "error_kind": result.get("error_kind"), "result": result.get("output_path")})
            return result


async def monitor_partition(root: Path, partition: str, concurrency=4):
    study = verify_source(root)
    client = MonitorClient(root, concurrency)
    if client.stopped:
        raise RuntimeError("Study access/usage stop exists; no monitor calls launched")
    by_id = {r["manifest"]["run_id"]: r for r in load_runs(root)}
    jobs = []
    for case in study["cases"]:
        if case["config"]["partition"] != partition:
            continue
        run = by_id[case["run_id"]]
        if all(reading(run, view, "transcript")["complete"] for view in ("per_agent", "group")):
            continue
        jobs.append(case)
    random.Random(104 if partition == "calibration" else 205).shuffle(jobs)
    queue = asyncio.Queue()
    for job in jobs:
        queue.put_nowait(job)
    completed = 0

    async def worker():
        nonlocal completed
        while not queue.empty() and not client.stopped:
            case = queue.get_nowait()
            directory = root/"runs"/case["run_id"]
            await judge_run(client, directory, include_service=False, include_fleet=False)
            manifest = json.loads((directory/"manifest.json").read_text())
            manifest["monitored"] = True
            write_json(directory/"manifest.json", manifest)
            completed += 1
            print(json.dumps({"at": utc_now(), "partition": partition, "processed": completed,
                "scheduled": len(jobs), "run_id": case["run_id"], "stopped": client.stopped}), flush=True)
    await asyncio.gather(*(worker() for _ in range(min(4, max(1, len(jobs))))))
    if client.stopped:
        raise RuntimeError("Monitoring stopped after CLI access or usage restriction; partial records retained")


async def main(args):
    from .analysis import freeze_thresholds, report
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    if args.phase == "prepare":
        study = await prepare(root)
        print(json.dumps({"prepared": len(study["cases"]), "root": str(root)}))
    elif args.phase == "report":
        report(root, output)
    else:
        verify_source(root)
        try:
            if args.phase in {"calibrate", "all"}:
                await monitor_partition(root, "calibration", args.concurrency)
                freeze_thresholds(root)
            if args.phase in {"evaluate", "all"}:
                freeze_thresholds(root)
                await monitor_partition(root, "evaluation", args.concurrency)
        finally:
            report(root, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "calibrate", "evaluate", "all", "report"))
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--concurrency", type=int, default=4)
    asyncio.run(main(parser.parse_args()))
