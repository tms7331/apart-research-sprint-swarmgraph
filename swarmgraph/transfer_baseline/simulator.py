"""JSON record services with role permissions and an independently graded cycle."""
from __future__ import annotations
from copy import deepcopy
from .contracts import Action, EpisodeSpec, Scenario
from .recorder import Recorder


def allowed(key: str, patterns: list[str]) -> bool:
    return any(key == p or (p.endswith("*") and key.startswith(p[:-1])) for p in patterns)


class Lab:
    def __init__(self, spec: EpisodeSpec, scenario: Scenario, recorder: Recorder | None = None):
        self.spec, self.scenario = spec, scenario
        self.state = deepcopy(spec.initial_state)
        self.recorder = recorder or Recorder("test")
        self.calls = 0
        self.actions: list[Action] = []
        self.cycled = False

    def apply(self, action: Action, agent_id: str | None = None) -> dict:
        agent_id = agent_id or action.role
        self.calls += 1
        call_id = f"c{self.calls:05d}"
        self.recorder.emit("tool_call", {"tool": action.tool, "arguments": action.arguments}, agent_id, call_id)
        self.actions.append(deepcopy(action))
        result: dict
        try:
            args = action.arguments
            perms = self.spec.permissions[action.role]
            if action.tool == "read":
                key = args["key"]
                if not allowed(key, perms["read"]):
                    raise PermissionError("read not granted")
                result = {"ok": True, "key": key, "record": deepcopy(self.state[key])}
            elif action.tool == "patch":
                key = args["key"]
                if not allowed(key, perms["write"]):
                    raise PermissionError("write not granted")
                if not isinstance(args.get("fields"), dict):
                    raise ValueError("fields must be an object")
                previous = deepcopy(self.state.get(key))
                candidate = deepcopy(self.state)
                candidate[key] = {**self.state.get(key, {}), **deepcopy(args["fields"])}
                harmful = self.scenario.check(self.spec, candidate).prohibited_outcome
                self.scenario.tick(self.spec, deepcopy(candidate))
                self.state = candidate
                self.recorder.transition(key, previous, self.state[key], agent_id, harmful)
                result = {"ok": True, "key": key, "record": deepcopy(self.state[key])}
                self.recorder.emit("service_write", {"key": key, "record": self.state[key]})
            elif action.tool == "copy":
                src, dst = args["source"], args["destination"]
                if not allowed(src, perms["read"]) or not allowed(dst, perms["write"]):
                    raise PermissionError("copy not granted")
                previous = deepcopy(self.state.get(dst))
                candidate = deepcopy(self.state)
                candidate[dst] = deepcopy(self.state[src])
                harmful = self.scenario.check(self.spec, candidate).prohibited_outcome
                self.scenario.tick(self.spec, deepcopy(candidate))
                self.state = candidate
                self.recorder.transition(dst, previous, self.state[dst], agent_id, harmful)
                result = {"ok": True, "key": dst, "record": deepcopy(self.state[dst])}
                self.recorder.emit("service_write", {"key": dst, "record": self.state[dst]})
            else:
                raise ValueError("unknown tool")
        except (KeyError, TypeError, ValueError, PermissionError, AttributeError) as exc:
            result = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
        self.recorder.emit("tool_result", result, agent_id, call_id)
        if action.public_message:
            self.recorder.emit("assistant_message", {"text": action.public_message}, agent_id)
        return result

    def run_cycle(self) -> None:
        if self.cycled:
            raise RuntimeError("standing cycle already completed")
        writes = self.scenario.tick(self.spec, deepcopy(self.state))
        preview = deepcopy(self.state)
        for write in writes:
            preview[write.key] = deepcopy(write.value)
            self.scenario.check(self.spec, preview)
        self.cycled = True
        for write in writes:
            before = deepcopy(self.state.get(write.key))
            self.state[write.key] = deepcopy(write.value)
            harmful = self.scenario.check(self.spec, self.state).prohibited_outcome
            self.recorder.transition(write.key, before, write.value, "standing_service", harmful)
            if write.public:
                self.recorder.emit("service_record", {"key": write.key, "record": write.value})
