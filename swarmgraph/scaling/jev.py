"""Jev, TypeSafe's decision model, on OpenRouter: typed questions about a state, answered with probabilities.

Experiment C's labeler (flow.py) asks it three yes/no ("noul") questions about each tool call. Jev runs only on
OpenRouter, not on the Codex subscription, so its calls are the one deliberate exception to "full runs stay on the
subscription". The key is read from OPENROUTER_KEY (environment or .env) and never written anywhere.

Every answer is cached on disk by its full request (model, state, questions), so a rerun makes no paid calls, and
each paid call's usage and cost are kept with it. Requests are retried on rate limits and server errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.14"
LONG_CONTEXT_BYTES = 32_000  # larger states run in Jev's slower, less accurate long-context mode
RETRYABLE = (408, 429, 500, 502, 503, 504)


class JevClient:
    def __init__(self, cache: Path, key: str, workers: int = 32, attempts: int = 8):
        self.cache, self._key, self.workers, self.attempts = Path(cache), key, workers, attempts
        self.paid_calls, self.usd, self._lock = 0, 0.0, threading.Lock()

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
            "X-Title": "swarmgraph flow labels"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())

    def ask(self, state: list[str], questions: dict) -> dict:
        """{"answers": {name: answer}, "usage": ..., "model": the version that answered}, from the cache if present."""
        body = {"model": MODEL, "state": state, "questions": questions}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        path = self.cache / digest[:2] / f"{digest}.json"
        if path.exists():
            return json.loads(path.read_text())
        for attempt in range(self.attempts):
            try:
                raw = self._post(body)
                break
            except urllib.error.HTTPError as error:
                detail = error.read()[:300].decode(errors="replace")
                if error.code not in RETRYABLE or attempt == self.attempts - 1:
                    raise RuntimeError(f"Jev HTTP {error.code}: {detail}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == self.attempts - 1:
                    raise
            time.sleep(min(60, 2 ** attempt))
        record = {"answers": raw.get("answers") or {}, "usage": raw.get("usage") or {}, "model": raw.get("model"),
                  "state_bytes": len(json.dumps(state).encode())}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        temporary.write_text(json.dumps(record))
        os.replace(temporary, path)
        with self._lock:
            self.paid_calls += 1
            self.usd += record["usage"].get("cost") or 0.0
        return record

    def ask_many(self, items: list[tuple[list[str], dict]]) -> list[dict]:
        with ThreadPoolExecutor(self.workers) as pool:
            return list(pool.map(lambda item: self.ask(*item), items))
