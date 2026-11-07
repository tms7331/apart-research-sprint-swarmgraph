"""Offline adapter checks; the separately recorded smoke uses real ChatGPT auth."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from swarmgraph.initial_experiments.shared.codex_cli import CodexClient, DISABLED_FEATURES, _environment

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def events(answer='{"ok":true}', item="agent_message", completed=True):
    rows = [{"type": "thread.started", "thread_id": "test"}, {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": item, "text": answer}}]
    if completed:
        rows.append({"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 4}})
    return "\n".join(json.dumps(row) for row in rows) + "\n"


class FakeClient(CodexClient):
    def __init__(self, root, scripts=None, **kwargs):
        super().__init__(root, **kwargs)
        self.scripts = list(scripts or [{}])
        self.calls = []
        self.active = 0
        self.peak = 0

    async def _run(self, argv, cwd, stdin=b""):
        if argv[1:] == ["login", "status"]:
            return 0, "", "Logged in using ChatGPT", False
        self.calls.append((argv, cwd, stdin))
        assert not list(Path(cwd).iterdir()), "model cwd must be empty"
        self.active += 1
        self.peak = max(self.peak, self.active)
        script = self.scripts.pop(0) if self.scripts else {}
        await asyncio.sleep(script.get("delay", 0))
        self.active -= 1
        if not script.get("missing"):
            Path(argv[argv.index("--output-last-message") + 1]).write_text(script.get("answer", '{"ok":true}'))
        return script.get("rc", 0), script.get("stdout", events()), script.get("stderr", ""), script.get("timeout", False)


@pytest.fixture(autouse=True)
def installed_cli(monkeypatch):
    monkeypatch.setattr("swarmgraph.initial_experiments.shared.codex_cli.shutil.which", lambda _: "/fake/codex")


def test_success_is_audited_and_cached(tmp_path):
    async def run():
        client = FakeClient(tmp_path)
        first = await client.ask("test", SCHEMA, "smoke", "same")
        second = await client.ask("test", SCHEMA, "smoke", "same")
        assert first == second
        assert first["status"] == "ok" and first["response"] == {"ok": True}
        assert len(client.calls) == 1
        assert first["usage"] == {"input_tokens": 11, "output_tokens": 4}
        assert first["started_at"].endswith("Z") and first["completed_at"].endswith("Z")
        parent = Path(first["output_path"]).parent
        assert {"prompt.txt", "schema.json", "stdout.jsonl", "stderr.txt", "metadata.json", "response.json", "result.json"} <= {p.name for p in parent.iterdir()}
        assert len(parent.parent.name) == 64
        with pytest.raises(ValueError, match="different"):
            await client.ask("changed", SCHEMA, "smoke", "same")
        (parent / "response.json").write_text('{"ok":false}')
        with pytest.raises(ValueError, match="output"):
            await client.ask("test", SCHEMA, "smoke", "same")
    asyncio.run(run())


def test_command_and_environment_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-propagate")
    monkeypatch.setenv("CODEX_THREAD_ID", "private-thread")
    monkeypatch.setenv("HOME", "/existing-home")
    environment = _environment()
    assert "OPENAI_API_KEY" not in environment and "CODEX_THREAD_ID" not in environment
    assert environment["HOME"] == "/existing-home"
    async def run():
        client = FakeClient(tmp_path)
        await client.ask("hello", SCHEMA, "test")
        argv, cwd, stdin = client.calls[0]
        assert stdin == b"hello" and not Path(cwd).exists()
        assert "--ignore-user-config" in argv and "--ignore-rules" in argv
        assert "--ephemeral" in argv and "gpt-6.1-sol" in argv
        assert 'model_reasoning_effort="medium"' in argv
        assert 'forced_login_method="chatgpt"' in argv
        assert 'web_search="disabled"' in argv
        assert "project_doc_max_bytes=0" in argv
        assert all(argv[argv.index(feature) - 1] == "--disable" for feature in DISABLED_FEATURES)
    asyncio.run(run())


@pytest.mark.parametrize("script", [
    {"answer": "not json", "stdout": events("not json")},
    {"missing": True},
    {"answer": '{"ok":"wrong type"}', "stdout": events('{"ok":"wrong type"}')},
    {"stdout": events(completed=False)},
    {"stdout": "broken JSONL"},
])
def test_invalid_output_retried_but_not_fabricated(tmp_path, script):
    async def run():
        client = FakeClient(tmp_path, [script, script, script])
        result = await client.ask("test", SCHEMA, "bad", "invalid")
        assert result["status"] == "error" and result["response"] is None
        assert result["attempts"] == 3 and len(client.calls) == 3
        assert len(list((tmp_path / "calls").glob("*/attempt_*/result.json"))) == 3
        again = await client.ask("test", SCHEMA, "bad", "invalid")
        assert again == result and len(client.calls) == 3
    asyncio.run(run())


@pytest.mark.parametrize("item", ["command_execution", "mcp_tool_call", "web_search", "file_change", "collab_tool_call"])
def test_any_tool_event_is_rejected_without_retry(tmp_path, item):
    async def run():
        client = FakeClient(tmp_path, [{"stdout": events(item=item)}])
        result = await client.ask("test", SCHEMA, "tool")
        assert result["status"] == "error" and result["error_kind"] == "unexpected_tool_use"
        assert result["response"] is None and len(client.calls) == 1
    asyncio.run(run())


def test_usage_cap_stops_other_calls(tmp_path):
    async def run():
        client = FakeClient(tmp_path, [{"rc": 1, "missing": True,
            "stdout": json.dumps({"type": "error", "message": "You've hit your usage limit"})}])
        result = await client.ask("test", SCHEMA, "limit")
        assert result["status"] == "usage_limit" and (tmp_path / "STOP").exists()
        next_result = await client.ask("another", SCHEMA, "stopped")
        assert next_result["status"] == "usage_limit" and len(client.calls) == 1
    asyncio.run(run())


def test_auth_error_never_retries(tmp_path):
    async def run():
        client = FakeClient(tmp_path, [{"rc": 1, "stderr": "401 Unauthorized"}])
        result = await client.ask("test", SCHEMA, "auth")
        assert result["status"] == "error" and result["error_kind"] == "authentication"
        assert len(client.calls) == 1
    asyncio.run(run())


def test_error_diagnostic_is_not_a_tool(tmp_path):
    async def run():
        warning = json.dumps({"type": "item.completed", "item": {"type": "error", "message": "Code Mode is unavailable because code-mode host is disabled."}})
        client = FakeClient(tmp_path, [{"stdout": warning + "\n" + events()}])
        result = await client.ask("test", SCHEMA, "diagnostic")
        assert result["status"] == "ok"
    asyncio.run(run())


def test_two_clients_deduplicate_same_call(tmp_path):
    async def run():
        first = FakeClient(tmp_path, [{"delay": .05}])
        second = FakeClient(tmp_path)
        results = await asyncio.gather(first.ask("test", SCHEMA, "load", "shared"),
                                       second.ask("test", SCHEMA, "load", "shared"))
        assert results[0] == results[1]
        assert len(first.calls) + len(second.calls) == 1
    asyncio.run(run())


def test_failed_call_with_no_retry_cannot_be_restarted(tmp_path):
    async def run():
        client = FakeClient(tmp_path, [{"stdout": events(item="mcp_tool_call")}])
        first = await client.ask("test", SCHEMA, "tool", "blocked")
        second = await client.ask("test", SCHEMA, "tool", "blocked")
        assert first == second and len(client.calls) == 1
    asyncio.run(run())


def test_timeout_and_transient_error_retry(tmp_path):
    async def run():
        client = FakeClient(tmp_path, [{"timeout": True}, {"rc": 1, "stderr": "503 server error"}, {}])
        result = await client.ask("test", SCHEMA, "retry")
        assert result["status"] == "ok" and result["attempts"] == 3
    asyncio.run(run())


def test_concurrency_and_same_id_deduplication(tmp_path):
    async def run():
        client = FakeClient(tmp_path, [{"delay": .02}] * 8, concurrency=2)
        results = await asyncio.gather(*(client.ask("test", SCHEMA, "load", str(i)) for i in range(6)))
        assert client.peak == 2 and all(row["status"] == "ok" for row in results)
        assert any(row["queue_delay_s"] > .01 for row in results)
        results = await asyncio.gather(*(client.ask("test", SCHEMA, "load", "duplicate") for _ in range(3)))
        assert results[0] == results[1] == results[2] and len(client.calls) == 7
    asyncio.run(run())


def test_real_subprocess_timeout_kills_child(tmp_path):
    async def run():
        client = CodexClient(tmp_path, timeout=.15)
        pid_file = tmp_path / "pid"
        code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open(sys.argv[1],'w').write(str(p.pid)); time.sleep(30)"
        rc, _, _, timed_out = await client._run([sys.executable, "-c", code, str(pid_file)], str(tmp_path))
        assert timed_out and rc != 0
        pid = int(pid_file.read_text())
        # A killed descendant may briefly remain a zombie; ps distinguishes it.
        process = await asyncio.create_subprocess_exec("ps", "-o", "stat=", "-p", str(pid), stdout=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        assert not stdout.strip() or stdout.strip().startswith(b"Z")
    asyncio.run(run())


def test_explicit_safety_restriction_stops_all_future_calls_without_retry(tmp_path):
    async def run():
        message = "This content was flagged for possible cybersecurity risk. Apply for Daybreak access before retrying."
        failure = json.dumps({"type": "turn.failed", "error": {"message": message}})
        client = FakeClient(tmp_path, [{"rc": 1, "stdout": failure, "missing": True}])
        result = await client.ask("test", SCHEMA, "restricted", "restriction")
        assert result["status"] == "error" and result["error_kind"] == "safety_restriction"
        assert message in result["error"] and not result["retryable"]
        assert (tmp_path / "STOP_SECURITY").exists() and not (tmp_path / "STOP").exists()
        assert Path(result["output_path"]).with_name("stdout.jsonl").read_text() == failure
        following = await client.ask("unrelated", SCHEMA, "stopped")
        assert following["error_kind"] == "safety_restriction" and following["status"] == "error"
        assert len(client.calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("timeout", [False, True])
def test_403_is_access_failure_not_transient_or_usage(tmp_path, timeout):
    async def run():
        message = "Reconnecting... unexpected status 403 Forbidden: Unknown error, url: wss://chatgpt.com/backend-api/codex/responses"
        client = FakeClient(tmp_path, [{"rc": 1, "stderr": message, "timeout": timeout, "missing": True}])
        result = await client.ask("test", SCHEMA, "access")
        assert result["error_kind"] == "access_forbidden" and result["status"] == "error"
        assert result["error"] == message and not result["retryable"] and len(client.calls) == 1
        assert not (tmp_path / "STOP").exists()
    asyncio.run(run())


def test_manual_stop_is_not_mislabeled_usage_quota(tmp_path):
    async def run():
        (tmp_path / "STOP").write_text("Operator stopped the experiment.")
        client = FakeClient(tmp_path)
        result = await client.ask("test", SCHEMA, "stopped")
        assert result["status"] == "error" and result["error_kind"] == "stop_file"
        assert not client.calls
    asyncio.run(run())


def test_platform_restriction_words_inside_model_content_are_not_diagnostics(tmp_path):
    async def run():
        schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}
        answer = json.dumps({"text": "403 Forbidden; flagged for possible cybersecurity risk; usage_limit"})
        client = FakeClient(tmp_path, [{"answer": answer, "stdout": events(answer)}])
        result = await client.ask("test", schema, "quotation")
        assert result["status"] == "ok" and not (tmp_path / "STOP_SECURITY").exists()
        assert not (tmp_path / "STOP").exists()
    asyncio.run(run())
