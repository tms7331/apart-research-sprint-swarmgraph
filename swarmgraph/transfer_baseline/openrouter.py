"""OpenRouter fallback for judge calls: the same model (openai/gpt-6.1-sol, medium effort) over HTTPS.

Used only on quick runs, and only when the Codex subscription refuses access (HTTP 403); full runs stay on the
subscription. A safety rejection never falls back. The key is read from the environment or the repository's
.env (OPENROUTER_KEY) and is never written anywhere. Each call is cached under
<root>/openrouter_calls/<sha256(call_id)>/ with its prompt, request (without the key), raw response and result.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

import jsonschema

from .io import utc_now

MODEL = "openai/gpt-6.1-sol"
EFFORT = "medium"
URL = "https://openrouter.ai/api/v1/chat/completions"
REPOSITORY = Path(__file__).resolve().parents[2]


def load_key(env_file: Path = REPOSITORY / ".env") -> str | None:
    if os.environ.get("OPENROUTER_KEY"):
        return os.environ["OPENROUTER_KEY"]
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "OPENROUTER_KEY" and value.strip():
                return value.strip().strip('"').strip("'")
    return None


class OpenRouterClient:
    provider = "openrouter"

    def __init__(self, root: Path, key: str, concurrency: int = 8, timeout: float = 300, retries: int = 1):
        self.root = Path(root) / "openrouter_calls"
        self.root.mkdir(parents=True, exist_ok=True)
        self._key, self.timeout, self.retries = key, timeout, retries
        self._semaphore = asyncio.Semaphore(concurrency)

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
            "X-Title": "swarmgraph hackathon judge"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())

    async def ask(self, prompt: str, schema: dict, purpose: str, call_id: str) -> dict:
        folder = self.root / hashlib.sha256(call_id.encode()).hexdigest()
        if (folder / "result.json").exists():
            cached = json.loads((folder / "result.json").read_text())
            if cached["status"] == "ok":
                return cached
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "prompt.txt").write_text(prompt)
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "reasoning": {"effort": EFFORT},
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": purpose, "strict": True, "schema": schema}}}
        (folder / "request.json").write_text(json.dumps(body, indent=1))
        record = {"status": "error", "response": None, "usage": {}, "call_id": call_id, "provider": self.provider,
                  "model": MODEL, "reasoning_effort": EFFORT, "output_path": str(folder / "result.json"),
                  "error_kind": None, "error": None, "started_at": utc_now()}
        async with self._semaphore:
            clock = time.monotonic()
            for attempt in range(1, self.retries + 2):
                try:
                    raw = await asyncio.to_thread(self._post, body)
                    (folder / f"raw_response_{attempt}.json").write_text(json.dumps(raw, indent=1))
                    content = raw["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    jsonschema.validate(parsed, schema)
                    usage = raw.get("usage") or {}
                    record.update(status="ok", response=parsed, error_kind=None, error=None, usage={
                        "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
                        "reasoning_output_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                        "cost": usage.get("cost")})
                    break
                except urllib.error.HTTPError as error:
                    record.update(error_kind=f"http_{error.code}", error=error.read().decode("utf-8", "replace")[:2000])
                    if error.code < 500 and error.code != 429:
                        break
                except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError,
                        jsonschema.ValidationError) as error:
                    record.update(error_kind="invalid_output" if isinstance(error, (ValueError, jsonschema.ValidationError))
                                  else "network", error=str(error)[:2000])
            record.update(completed_at=utc_now(), latency_s=time.monotonic() - clock)
        (folder / "result.json").write_text(json.dumps(record, indent=1))
        return record
