"""Small, explicit contract between scenario modules and the experiment harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Action:
    role: str
    tool: str  # read, patch, copy, finish
    arguments: dict[str, Any]
    public_message: str = ""


@dataclass
class EpisodeSpec:
    scenario: str
    seed: int
    condition: str
    variant: str
    policy: str
    service_description: str
    initial_state: dict[str, dict[str, Any]]
    tasks: dict[str, str]  # exactly r1,r2,r3; background added by harness
    permissions: dict[str, dict[str, list[str]]]  # read/write exact keys or prefix*
    plans: dict[str, list[Action]]
    private: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceWrite:
    key: str
    value: dict[str, Any]
    public: bool = True


@dataclass
class Checks:
    main_tasks: dict[str, bool]
    prohibited_outcome: bool
    details: dict[str, Any] = field(default_factory=dict)


class Scenario(Protocol):
    name: str
    version: str

    def build(self, seed: int, condition: str, omit_role: str | None = None) -> EpisodeSpec: ...
    def tick(self, spec: EpisodeSpec, state: dict[str, dict[str, Any]]) -> list[ServiceWrite]: ...
    def check(self, spec: EpisodeSpec, state: dict[str, dict[str, Any]]) -> Checks: ...
    def constructed_effects(self, spec: EpisodeSpec) -> list[ServiceWrite]: ...
