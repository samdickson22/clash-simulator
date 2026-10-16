"""Small, timestamped messages. No evaluator/native match state crosses IPC."""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Frame:
    episode: str
    sequence: int
    produced_at: float
    received_at: float
    timestamp_ms: float
    pixels: Any


@dataclass(frozen=True)
class Observation:
    frame: Frame
    public: Any
    events: tuple
    phase: str
    completed_at: float
    timings: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Snapshot:
    episode: str
    sequence: int
    produced_at: float
    received_at: float
    emitted_at: float
    tick: int
    public: Any
    own: dict
    roots: tuple
    opponent: dict
    revision: int
    pending: dict | None
    event_serial: int
    verification_serial: int


@dataclass(frozen=True)
class Command:
    command_id: int
    episode: str
    frame_sequence: int
    produced_at: float
    created_at: float
    revision: int
    card: str
    cost: float
    tile: tuple[float, float]
    expires_at: float


@dataclass(frozen=True)
class Feedback:
    command_id: int
    emitted_at: float
    revision: int
    state: str
    card: str
    cost: float
    hud: Any
    pending: dict | None
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DelayContext:
    """S6 hook: nominal delay is the selected profile's total planner delay."""
    backend: str
    acceptance_p50_ms: float
    acceptance_p99_ms: float
    nominal_command_ticks: int
    pending: dict | None
    decision_tick: int
    deadline: float
