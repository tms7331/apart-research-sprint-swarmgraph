"""The OpenRouter fallback: only on an access refusal, sticky for the run, never on a safety rejection. No network."""
import asyncio
import json

from swarmgraph.transfer_baseline.run import MonitorClient


class Fake:
    def __init__(self, status, error_kind=None, provider=None):
        self.status, self.error_kind, self.provider, self.calls = status, error_kind, provider, []

    async def ask(self, prompt, schema, purpose, call_id=None):
        self.calls.append(call_id)
        result = {"status": self.status, "error_kind": self.error_kind, "call_id": call_id, "output_path": "x",
                  "response": {"ok": True} if self.status == "ok" else None}
        if self.provider:
            result["provider"] = self.provider
        return result


def test_a_403_switches_the_run_to_openrouter_and_stays_there(tmp_path):
    openrouter = Fake("ok", provider="openrouter")
    client = MonitorClient(tmp_path, concurrency=1, fallback=openrouter)
    client.client = Fake("error", "access_forbidden")
    first = asyncio.run(client.ask("p", {}, "monitor", "c1"))
    second = asyncio.run(client.ask("p", {}, "monitor", "c2"))
    assert first["provider"] == second["provider"] == "openrouter" and first["codex_refusal"] == "x"
    assert client.client.calls == ["c1"] and openrouter.calls == ["c1", "c2"]
    assert (tmp_path / "FALLBACK_OPENROUTER").exists() and not client.stopped


def test_a_safety_rejection_stops_and_never_falls_back(tmp_path):
    openrouter = Fake("ok", provider="openrouter")
    client = MonitorClient(tmp_path, concurrency=1, fallback=openrouter)
    client.client = Fake("error", "safety_restriction")
    result = asyncio.run(client.ask("p", {}, "monitor", "c1"))
    assert result["error_kind"] == "safety_restriction" and openrouter.calls == []
    assert json.loads((tmp_path / "STOP_ACCESS").read_text())["error_kind"] == "safety_restriction"


def test_without_a_fallback_a_403_stops_the_run(tmp_path):
    client = MonitorClient(tmp_path, concurrency=1)
    client.client = Fake("error", "access_forbidden")
    asyncio.run(client.ask("p", {}, "monitor", "c1"))
    assert client.stopped
