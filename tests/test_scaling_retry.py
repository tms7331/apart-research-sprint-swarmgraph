"""Offline checks for the explicitly enabled 403 cooldown; no real sleeps or calls."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from swarmgraph.transfer_baseline import codex_cli


@pytest.fixture
def fake_cli(monkeypatch):
    clock = SimpleNamespace(now=0.0, sleeps=[], requests=[], errors=[])
    monkeypatch.setattr(codex_cli, "time", SimpleNamespace(monotonic=lambda: clock.now))
    monkeypatch.setattr(codex_cli.shutil, "which", lambda _: "/fake/codex")

    async def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += seconds

    async def run(self, argv, cwd, stdin=b""):
        if argv[1:] == ["login", "status"]:
            return 0, "", "Logged in using ChatGPT", False
        clock.requests.append((clock.now, stdin))
        error = clock.errors.pop(0) if clock.errors else None
        if error:
            return 1, json.dumps({"type": "error", "message": error}), "", False
        Path(argv[argv.index("--output-last-message") + 1]).write_text("{}")
        events = [{"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
                  {"type": "turn.completed", "usage": {}}]
        return 0, "\n".join(map(json.dumps, events)), "", False

    monkeypatch.setattr(codex_cli.asyncio, "sleep", sleep)
    monkeypatch.setattr(codex_cli.CodexClient, "_run", run)
    return clock


def test_resumes_saved_403_and_waits_each_minute_without_spending_normal_retries(tmp_path, fake_cli):
    async def exercise():
        fake_cli.errors = ["403 Forbidden: Unknown error"]
        first = await codex_cli.CodexClient(tmp_path, retries=0).ask("same", {}, "monitor", "call")
        saved = Path(first["output_path"]).read_bytes()
        assert first["error_kind"] == "access_forbidden"
        fake_cli.errors = ["403 Forbidden: Unknown error"] * 3
        client = codex_cli.CodexClient(tmp_path, retries=0, retry_forbidden=True)
        result = await client.ask("same", {}, "monitor", "call")
        assert result["status"] == "ok" and result["attempts"] == 5
        assert fake_cli.sleeps == [60.0] * 3
        assert [t for t, _ in fake_cli.requests] == [0, 0, 60, 120, 180]
        assert all(prompt == b"same" for _, prompt in fake_cli.requests)
        assert Path(first["output_path"]).read_bytes() == saved
        assert await client.ask("same", {}, "monitor", "call") == result
        assert len(fake_cli.requests) == 5
    asyncio.run(exercise())


@pytest.mark.parametrize("message,kind", [
    ("403 flagged for possible cybersecurity risk", "safety_restriction"),
    ("403 authentication failed", "authentication"),
    ("403 usage_limit", "usage_limit"),
])
def test_explicit_restrictions_still_stop(tmp_path, fake_cli, message, kind):
    fake_cli.errors = [message]
    client = codex_cli.CodexClient(tmp_path, retry_forbidden=True)
    result = asyncio.run(client.ask("same", {}, "monitor", "call"))
    assert result["error_kind"] == kind
    assert len(fake_cli.requests) == 1 and not fake_cli.sleeps


def test_cooldown_also_applies_to_new_calls_and_honors_stop_markers(tmp_path, fake_cli):
    async def exercise():
        client = codex_cli.CodexClient(tmp_path, retry_forbidden=True)
        client._forbidden_until = 60
        assert (await client.ask("new", {}, "monitor", "new"))["status"] == "ok"
        assert fake_cli.requests[0][0] == 60
        client._forbidden_until = 120
        (tmp_path / "STOP_OPERATOR").write_text("stop")
        assert (await client.ask("stop", {}, "monitor", "stop"))["error_kind"] == "stop_file"
        assert len(fake_cli.requests) == 1
    asyncio.run(exercise())


def test_saved_403_still_requires_explicit_retry_opt_in(tmp_path, fake_cli, monkeypatch):
    async def interrupt_cooldown(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(codex_cli.asyncio, "sleep", interrupt_cooldown)
    fake_cli.errors = ["403 Forbidden: Unknown error"]
    enabled = codex_cli.CodexClient(tmp_path, retry_forbidden=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(enabled.ask("same", {}, "monitor", "call"))
    disabled = codex_cli.CodexClient(tmp_path)
    result = asyncio.run(disabled.ask("same", {}, "monitor", "call"))
    assert result["error_kind"] == "access_forbidden" and result["attempts"] == 1
    assert len(fake_cli.requests) == 1
