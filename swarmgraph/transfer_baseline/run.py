"""Generate, judge and report the Step 1 transfer baseline.

    uv run python -m swarmgraph.transfer_baseline generate [--smoke]   # deterministic episodes, no model calls
    uv run python -m swarmgraph.transfer_baseline judge [--smoke]      # the missing judge readings
    uv run python -m swarmgraph.transfer_baseline report [--smoke]

Full run: logs/transfer_baseline/ (540 readings), report in reports/transfer_baseline/.
Smoke run (--smoke): logs/transfer_baseline_smoke/ (27 readings), report beside it.
The raw Codex CLI archive goes to <destination>/raw_calls/, which Git ignores.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import random
import time

from .codex_cli import CodexClient
from .design import DESTINATION, REPORT, SMOKE_DESTINATION, generate, protocol
from .io import read_jsonl, utc_now, write_json
from .monitoring import judge_one, planned_judgments, prompt_for, successful_judgment_ids

STOP_NAMES = ("STOP", "STOP_SECURITY", "STOP_ACCESS")
TERMINAL = {"access_forbidden", "safety_restriction", "authentication", "usage_limit", "stop_file"}


class MonitorClient:
    """Only review records; never request actor behavior.

    Any access restriction, authentication failure or usage limit writes
    STOP_ACCESS and stops queued calls. ``min_interval`` (seconds) spaces out
    the starts of calls, so a run can't burst: 2.0 caps it at 30 calls a minute.

    ``fallback`` (an OpenRouterClient; quick runs only, never full runs): on the
    first access refusal (HTTP 403) the run switches to OpenRouter with the same
    model, notes it in FALLBACK_OPENROUTER, and stays there. A safety rejection
    never falls back. Every result records the route that answered it.
    """
    def __init__(self, root: Path, concurrency=4, min_interval: float = 0.0, fallback=None):
        self.root = Path(root)
        self.fallback, self.on_fallback = fallback, False
        self.client = CodexClient(self.root, concurrency=concurrency, timeout=180, retries=1)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.min_interval = min_interval
        self._pace = asyncio.Lock()
        self._last_start = 0.0

    def _cached(self, call_id) -> bool:
        """Whether this call already has a successful saved attempt (the client replays it with no request)."""
        if not call_id:
            return False
        folder = self.root / "calls" / hashlib.sha256(call_id.encode()).hexdigest()
        return any(json.loads(p.read_text()).get("status") == "ok" for p in folder.glob("attempt_*/result.json"))

    async def _paced(self, call_id=None):
        if self.min_interval <= 0 or self._cached(call_id):
            return
        async with self._pace:
            delay = self._last_start + self.min_interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_start = time.monotonic()

    @property
    def stopped(self):
        return any((self.root / name).exists() for name in STOP_NAMES)

    async def ask(self, prompt, schema, purpose, call_id=None):
        if purpose != "monitor":
            raise ValueError("This baseline permits monitor calls only")
        async with self.semaphore:
            if self.stopped:
                return {"status": "not_run", "call_id": call_id, "error_kind": "study_stopped"}
            if self.fallback and self.on_fallback and not self._cached(call_id):
                return await self.fallback.ask(prompt, schema, purpose, call_id)
            await self._paced(call_id)
            if self.stopped:
                return {"status": "not_run", "call_id": call_id, "error_kind": "study_stopped"}
            result = await self.client.ask(prompt, schema, purpose, call_id)
            result.setdefault("provider", "codex")
            if self.fallback and result.get("error_kind") == "access_forbidden":
                self.on_fallback = True
                write_json(self.root / "FALLBACK_OPENROUTER", {"at": utc_now(), "call_id": call_id,
                           "codex_refusal": result.get("output_path")})
                answer = await self.fallback.ask(prompt, schema, purpose, call_id)
                answer["codex_refusal"] = result.get("output_path")
                return answer
            if result.get("error_kind") in TERMINAL or result["status"] == "usage_limit":
                write_json(self.root / "STOP_ACCESS", {"at": utc_now(), "call_id": call_id,
                           "error_kind": result.get("error_kind"), "result": result.get("output_path")})
            return result


def pending(destination: Path, readings: int) -> list[dict]:
    """Planned readings without a successful saved judgment, in a fixed shuffled order."""
    episodes = read_jsonl(Path(destination) / "episodes.jsonl")
    if not episodes:
        raise RuntimeError("No episodes; run generate first")
    done = successful_judgment_ids(destination)
    todo = [p for episode in episodes for p in planned_judgments(episode, readings) if p["judgment_id"] not in done]
    for planned in todo:
        prompt_for(destination, planned)  # fail before any call if episodes changed since generate
    # Interleave run types so drift over time is not confounded with condition.
    random.Random(0).shuffle(todo)
    return todo


async def judge(destination: Path, smoke: bool = False, concurrency: int = 4, client=None) -> None:
    destination = Path(destination)
    todo = pending(destination, protocol(smoke)["readings_per_view"])
    client = client or MonitorClient(destination / "raw_calls", concurrency)
    if getattr(client, "stopped", False):
        raise RuntimeError("A stop marker exists in raw_calls/; no judge calls launched")
    print(json.dumps({"at": utc_now(), "pending_readings": len(todo)}), flush=True)
    await asyncio.gather(*(judge_one(client, destination, planned) for planned in todo))
    remaining = len(pending(destination, protocol(smoke)["readings_per_view"]))
    print(json.dumps({"at": utc_now(), "taken": len(todo) - remaining, "still_missing": remaining}), flush=True)
    if getattr(client, "stopped", False):
        raise RuntimeError("Judging stopped after a CLI access or usage restriction; saved judgments are kept")


def main(argv=None) -> None:
    from .analysis import report
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("generate", "judge", "report"))
    parser.add_argument("--smoke", action="store_true", help="layout 0 only, one reading per view")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args(argv)
    destination = SMOKE_DESTINATION if args.smoke else DESTINATION
    if args.command == "generate":
        rows = generate(destination, args.smoke)
        print(json.dumps({"episodes": len(rows), "destination": str(destination)}))
    elif args.command == "judge":
        try:
            asyncio.run(judge(destination, args.smoke, args.concurrency))
        finally:
            report(destination, destination / "report" if args.smoke else REPORT, args.smoke)
    else:
        report(destination, destination / "report" if args.smoke else REPORT, args.smoke)


if __name__ == "__main__":
    main()
