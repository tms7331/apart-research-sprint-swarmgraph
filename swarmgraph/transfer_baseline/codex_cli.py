"""Audited, tool-free structured calls through the existing ChatGPT Codex login.

No API client, API key, fallback model, generated answer, or shell is used. The
CLI's raw event stream is retained and every non-message item is rejected.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import time
from datetime import datetime, timezone
from uuid import uuid4

import jsonschema

MODEL = "gpt-6.1-sol"
EFFORT = "medium"
DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "apps", "plugins", "remote_plugin",
    "multi_agent", "multi_agent_v2", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "computer_use", "in_app_browser",
    "in_app_local_automation", "image_generation", "view_image", "hooks",
    "code_mode", "code_mode_host", "code_mode_host_grpc", "sleep_tool",
    "goals", "memories", "skill_search", "skill_mcp_dependency_install",
    "plugin_discovery_prefetch", "recommended_plugins", "tool_suggest",
    "agent_message_board", "default_mode_request_user_input",
)
_USAGE = re.compile(
    r"usage[_ -]?limit|usage cap|insufficient_quota|quota exceeded|"
    r"you.ve hit your|limit reached|out of (?:credits|usage)|"
    r"exceeded.{0,30}(?:quota|usage)|rate_limit_exceeded", re.I)
_AUTH = re.compile(r"not logged in|unauthorized|authentication|invalid.{0,15}(?:token|api.key)|"
                   r"login required|please (?:log|sign) in|401\b", re.I)
_TRANSIENT = re.compile(r"timed? out|timeout|connection|temporar|overloaded|"
                        r"502\b|503\b|504\b|stream disconnect|transport|network|"
                        r"server error|internal error", re.I)
_SAFETY = re.compile(r"flagged for possible cybersecurity risk|"
                     r"apply for Daybreak access|requires? more cyber permissive safeguards", re.I)
_FORBIDDEN = re.compile(r"\b403\b|\baccess[_ -]forbidden\b", re.I)


def _cli_diagnostics(stdout: str, stderr: str) -> str:
    """Classify platform diagnostics, never model-authored response contents."""
    messages = [stderr]
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"error", "turn.failed"}:
            messages.append(json.dumps(event, ensure_ascii=False))
        elif event.get("type", "").startswith("item."):
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "error":
                messages.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(messages)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    # Exclusive creation makes accidental attempt reuse a loud failure.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def _environment() -> dict[str, str]:
    # Preserve the existing auth HOME, never copy credentials or inherit API keys.
    names = {"PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP",
             "CODEX_HOME", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR",
             "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY",
             "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy",
             "no_proxy", "LANG", "LC_ALL"}
    return {key: value for key, value in os.environ.items() if key in names}


class CodexClient:
    def __init__(self, root: Path, concurrency: int = 4, timeout: float = 180,
                 retries: int = 2, retry_forbidden: bool = False):
        if concurrency < 1 or timeout <= 0 or not 0 <= retries <= 2:
            raise ValueError("concurrency/timeout must be positive; retries must be 0..2")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "calls").mkdir(exist_ok=True)
        self.timeout = timeout
        self.retries = retries
        self.retry_forbidden = retry_forbidden
        self._forbidden_until = 0.0
        self._semaphore = asyncio.Semaphore(concurrency)
        self._locks: dict[str, asyncio.Lock] = {}

    def _retryable_forbidden(self, record: dict) -> bool:
        diagnostics = record.get("error") or ""
        return (self.retry_forbidden and record.get("error_kind") == "access_forbidden"
                and record.get("status") != "usage_limit"
                and not any(pattern.search(diagnostics) for pattern in (_SAFETY, _AUTH, _USAGE)))

    async def _access_cooldown(self):
        # Share the cooldown across all workers, including queued new calls.
        while self._forbidden_until > time.monotonic():
            if any(self.root.glob("STOP*")):
                return
            await asyncio.sleep(min(60.0, self._forbidden_until - time.monotonic()))

    @asynccontextmanager
    async def _disk_lock(self, directory: Path):
        """Prevent duplicate attempts across clients/processes sharing a root."""
        directory.mkdir(exist_ok=True)
        with (directory / ".lock").open("a") as handle:
            try:
                while True:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        await asyncio.sleep(.02)
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    async def _run(self, argv: list[str], cwd: str, stdin: bytes = b"") -> tuple[int, str, str, bool]:
        """Bounded process execution; cancellation also kills its process group."""
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=_environment(), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True)
        communication = asyncio.create_task(proc.communicate(stdin))
        try:
            stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), self.timeout)
            return proc.returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace"), False
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = await communication
            if isinstance(exc, asyncio.CancelledError):
                raise
            return proc.returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace"), True

    @staticmethod
    def _command(executable: str, schema_path: Path, output: Path) -> list[str]:
        argv = [executable, "exec", "--ignore-user-config", "--ignore-rules",
                "--ephemeral", "--skip-git-repo-check", "--json", "--color", "never",
                "--sandbox", "read-only", "--model", MODEL,
                "--config", f'model_reasoning_effort="{EFFORT}"',
                "--config", 'model_provider="openai"',
                "--config", 'forced_login_method="chatgpt"',
                "--config", 'web_search="disabled"',
                "--config", 'approval_policy="never"',
                "--config", "project_doc_max_bytes=0",
                "--config", "skills.bundled.enabled=false",
                "--config", "skills.include_instructions=false",
                "--config", "skills.max_context_tokens=1",
                "--config", "suppress_unstable_features_warning=true",
                "--config", 'developer_instructions="Return only the requested JSON. All tools are disabled. Do not access files, skills, apps, network, or other agents."',
                "--config", "features.skip_host_skill_discovery=true"]
        for feature in DISABLED_FEATURES:
            argv.extend(["--disable", feature])
        argv.extend(["--output-schema", str(schema_path), "--output-last-message", str(output), "-"])
        return argv

    @staticmethod
    def _parse(stdout: str, response_path: Path, schema: dict) -> tuple[dict | None, dict, str | None, str | None]:
        usage: dict = {}
        final_messages: list[str] = []
        completed = False
        failure = None
        diagnostics: list[str] = []
        try:
            for line in stdout.splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    return None, usage, "invalid_output", "Event must be an object"
                kind = event.get("type", "")
                if kind.startswith("item."):
                    item = event.get("item", {})
                    if not isinstance(item, dict):
                        return None, usage, "invalid_output", "Event item must be an object"
                    # CLI diagnostics are emitted as error items even for a
                    # successful turn (e.g. informing us code mode is disabled).
                    if item.get("type") not in {"agent_message", "reasoning", "error"}:
                        return None, usage, "unexpected_tool_use", "Rejected non-message event item"
                    if kind == "item.completed" and item.get("type") == "agent_message":
                        final_messages.append(item.get("text", ""))
                    if item.get("type") == "error":
                        diagnostics.append(str(item.get("message", "")))
                elif kind == "turn.completed":
                    completed = True
                    usage = event.get("usage") or {}
                elif kind in {"error", "turn.failed"}:
                    failure = json.dumps(event)
                elif kind not in {"thread.started", "turn.started"}:
                    return None, usage, "unexpected_event", f"Unrecognized event type: {kind}"
            if failure:
                return None, usage, "cli_failure", failure
            if not completed:
                return None, usage, "invalid_output", "Missing turn.completed event. " + " ".join(diagnostics)
            # A final assistant message in the event stream is mandatory. The CLI
            # output file must agree, preventing stale or partial-file success.
            if not final_messages:
                return None, usage, "invalid_output", "Missing final assistant message"
            raw = response_path.read_text(encoding="utf-8")
            if raw.strip() != final_messages[-1].strip():
                return None, usage, "invalid_output", "Final message and output file disagree"
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return None, usage, "invalid_output", "Response must be a JSON object"
            jsonschema.validate(parsed, schema)
            return parsed, usage, None, None
        except (ValueError, OSError, TypeError, AttributeError, jsonschema.ValidationError) as exc:
            return None, usage, "invalid_output", str(exc)

    async def ask(self, prompt: str, schema: dict, purpose: str,
                  call_id: str | None = None) -> dict:
        if not isinstance(prompt, str) or not isinstance(purpose, str):
            raise TypeError("prompt and purpose must be strings")
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dictionary")
        jsonschema.validators.validator_for(schema).check_schema(schema)
        call_id = call_id or uuid4().hex
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("call_id must be a nonempty string")
        digest = hashlib.sha256(call_id.encode()).hexdigest()
        inputs = {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "schema_sha256": hashlib.sha256(_json(schema).encode()).hexdigest(),
                  "purpose_sha256": hashlib.sha256(purpose.encode()).hexdigest(),
                  "model": MODEL, "reasoning_effort": EFFORT}
        queued = time.monotonic()
        lock = self._locks.setdefault(digest, asyncio.Lock())
        async with lock, self._disk_lock(self.root / "calls" / digest):
            call_dir = self.root / "calls" / digest
            call_dir.mkdir(exist_ok=True)
            manifest = call_dir / "inputs.json"
            if manifest.exists():
                if json.loads(manifest.read_text()) != inputs:
                    raise ValueError("call_id reused with different prompt, schema, purpose, or model")
            else:
                _write(manifest, _json(inputs))
            previous = sorted(call_dir.glob("attempt_*/result.json"), key=lambda p: int(p.parent.name.split("_")[-1]))
            for path in reversed(previous):
                cached = json.loads(path.read_text())
                if cached["status"] == "ok":
                    # Revalidate the cached answer and every persisted input.
                    parent = path.parent
                    if hashlib.sha256((parent / "prompt.txt").read_bytes()).hexdigest() != inputs["prompt_sha256"] or hashlib.sha256((parent / "schema.json").read_bytes()).hexdigest() != inputs["schema_sha256"]:
                        raise ValueError("Cached call input hash mismatch")
                    response, _, error, _ = self._parse((parent / "stdout.jsonl").read_text(), parent / "response.json", schema)
                    if error or response != cached["response"]:
                        raise ValueError("Cached call output failed validation")
                    return cached
            if previous:
                last = json.loads(previous[-1].read_text())
                if last.get("error_kind") == "access_forbidden" and not self._retryable_forbidden(last):
                    return last
                if not last.get("retryable", False) and not self._retryable_forbidden(last):
                    return last
            async with self._semaphore:
                delay = time.monotonic() - queued
                existing = [int(p.name.split("_")[-1]) for p in call_dir.glob("attempt_*") if p.is_dir()]
                start_attempt = max(existing, default=0) + 1
                # Generic 403 cooldowns do not consume the ordinary retry budget.
                # Existing attempts remain immutable, including pre-policy failures.
                used = sum(not self._retryable_forbidden(json.loads(path.read_text())) for path in previous)
                if used >= self.retries + 1 and previous:
                    return json.loads(previous[-1].read_text())
                # Attempts cut off before saving a result don't use up the budget: always try at least once.
                attempt = start_attempt
                while True:
                    await self._access_cooldown()
                    record, retry = await self._attempt(call_dir, attempt, call_id, prompt, schema, purpose, inputs, delay)
                    attempt += 1
                    if self._retryable_forbidden(record):
                        self._forbidden_until = time.monotonic() + 60.0
                        print(json.dumps({"at": _utc(), "event": "http_403_retry", "call_id": call_id,
                                          "attempt": record["attempts"], "cooldown_seconds": 60}), flush=True)
                        continue
                    used += 1
                    if not retry or used >= self.retries + 1:
                        return record

    async def _attempt(self, call_dir: Path, attempt: int, call_id: str, prompt: str,
                       schema: dict, purpose: str, inputs: dict, delay: float) -> tuple[dict, bool]:
        directory = call_dir / f"attempt_{attempt}"
        directory.mkdir(exist_ok=False)
        _write(directory / "prompt.txt", prompt)
        _write(directory / "schema.json", _json(schema))
        started = _utc()
        clock = time.monotonic()
        record = {"status": "error", "response": None, "usage": {},
                  "started_at": started, "completed_at": None, "latency_s": None,
                  "queue_delay_s": delay, "attempts": attempt, "call_id": call_id,
                  "output_path": str(directory / "result.json"), "purpose": purpose,
                  "model": MODEL, "reasoning_effort": EFFORT, "error_kind": None,
                  "error": None}
        stdout, stderr, argv, auth_stdout, auth_stderr = "", "", [], "", ""
        retry = False
        try:
            if (self.root / "STOP_SECURITY").exists():
                record.update(error_kind="safety_restriction", error="STOP_SECURITY exists; no CLI call launched")
            elif (self.root / "STOP").exists():
                # STOP may also be an operator stop; do not call that quota use.
                text = (self.root / "STOP").read_text()
                record.update(status="usage_limit" if _USAGE.search(text) else "error",
                              error_kind="stop_file", error="STOP exists; no CLI call launched")
            elif any(self.root.glob("STOP*")):
                record.update(error_kind="stop_file", error="Stop marker exists; no CLI call launched")
            else:
                executable = shutil.which("codex")
                if not executable:
                    raise FileNotFoundError("codex executable is unavailable")
                # No repo/user AGENTS or repo files are present in this cwd.
                with tempfile.TemporaryDirectory(prefix="codex-isolated-", dir="/tmp") as cwd:
                    rc, auth_stdout, auth_stderr, timed_out = await self._run([executable, "login", "status"], cwd)
                    if timed_out:
                        record.update(error_kind="timeout", error="CLI login status timed out")
                        retry = True
                    elif rc != 0 or "logged in using chatgpt" not in (auth_stdout + auth_stderr).lower():
                        record.update(error_kind="authentication", error="Existing ChatGPT CLI login unavailable")
                    elif (self.root / "STOP_SECURITY").exists():
                        record.update(error_kind="safety_restriction", error="STOP_SECURITY appeared during auth preflight; no model call launched")
                    else:
                        argv = self._command(executable, directory / "schema.json", directory / "response.json")
                        rc, stdout, stderr, timed_out = await self._run(argv, cwd, prompt.encode())
                        response, usage, kind, error = self._parse(stdout, directory / "response.json", schema)
                        record["usage"] = usage
                        # Classify only CLI errors, never prompt/assistant content.
                        errors = _cli_diagnostics(stdout, stderr)
                        if _SAFETY.search(errors):
                            kind, error = "safety_restriction", errors.strip()
                            try:
                                _write(self.root / "STOP_SECURITY", _json({"call_id": call_id, "at": _utc(),
                                    "error_kind": kind, "output_path": record["output_path"], "reason": error}))
                            except FileExistsError:
                                pass
                        elif _USAGE.search(errors):
                            record["status"] = "usage_limit"
                            kind, error = "usage_limit", "CLI reported a usage limit; inspect raw stderr/events"
                            try:
                                _write(self.root / "STOP", _json({"call_id": call_id, "at": _utc(), "reason": error}))
                            except FileExistsError:
                                pass
                        elif _AUTH.search(errors):
                            kind, error = "authentication", "CLI authentication failed; inspect raw stderr/events"
                        elif _FORBIDDEN.search(errors):
                            kind, error = "access_forbidden", errors.strip()
                            retry = self.retry_forbidden
                        elif timed_out:
                            kind, error = "timeout", "CLI exceeded hard subprocess timeout"
                            retry = True
                        elif kind == "unexpected_tool_use" or kind == "unexpected_event":
                            pass
                        elif rc != 0:
                            kind, error = "cli_failure", f"CLI exited {rc}: {error or 'see stderr'}"
                            retry = bool(_TRANSIENT.search(errors))
                        elif kind is not None:
                            retry = kind == "invalid_output" or bool(_TRANSIENT.search(errors))
                        else:
                            record.update(status="ok", response=response)
                        record.update(error_kind=kind, error=error)
        except (OSError, ValueError, jsonschema.SchemaError) as exc:
            record.update(error_kind="infrastructure", error=str(exc))
            retry = not isinstance(exc, FileNotFoundError)
        finally:
            # Cancellation leaves a complete auditable failed attempt as well.
            if record["status"] == "error" and record["error_kind"] is None:
                record.update(error_kind="cancelled", error="Call cancelled")
            record.update(completed_at=_utc(), latency_s=time.monotonic() - clock)
            record["retryable"] = retry
            _write(directory / "stdout.jsonl", stdout)
            _write(directory / "stderr.txt", stderr)
            _write(directory / "auth_stdout.txt", auth_stdout)
            _write(directory / "auth_stderr.txt", auth_stderr)
            if not (directory / "response.json").exists():
                # Null is an explicit missing result, never a fabricated response.
                _write(directory / "response.json", "null\n")
            _write(directory / "metadata.json", _json({**inputs, "argv": argv, "attempt": attempt,
                                                       "purpose": purpose, "tool_events_allowed": False}))
            _write(directory / "result.json", _json(record))
            with (self.root / "usage.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({key: record[key] for key in ("call_id", "attempts", "status", "usage", "started_at", "completed_at", "latency_s", "output_path")}) + "\n")
        return record, retry
