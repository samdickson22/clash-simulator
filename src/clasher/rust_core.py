from __future__ import annotations

import hashlib
import json
import struct
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from .balance import DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS
from .differential import (
    SNAPSHOT_SCHEMA_VERSION,
    canonical_battle_snapshot,
    snapshot_bytes,
)
from .entities import Building

try:
    from _clasher_rust import (  # type: ignore[import-untyped]
        ResidentBattle as _ResidentBattle,
    )
    from _clasher_rust import (  # type: ignore[import-untyped]
        consume_state_bytes as _consume_state_bytes,
    )
    from _clasher_rust import noop_ticks as _noop_ticks  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - depends on optional compiled artifact
    _consume_state_bytes = None
    _noop_ticks = None
    _ResidentBattle = None


FNV_OFFSET_BASIS: Final = 0xCBF29CE484222325
FNV_PRIME: Final = 0x100000001B3
U64_MASK: Final = (1 << 64) - 1


def rust_core_available() -> bool:
    return (
        _noop_ticks is not None
        and _consume_state_bytes is not None
        and _ResidentBattle is not None
    )


def require_rust_core() -> None:
    if not rust_core_available():
        raise RuntimeError(
            "optional Rust core is not installed; run "
            "`maturin develop --manifest-path rust/clasher-core/Cargo.toml`"
        )


def rust_noop_ticks(ticks: int) -> int:
    require_rust_core()
    if ticks < 0 or ticks > (1 << 32) - 1:
        raise ValueError("ticks must fit in u32")
    assert _noop_ticks is not None
    return int(_noop_ticks(ticks))


def python_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    hash_value = FNV_OFFSET_BASIS
    for byte in payload:
        hash_value = ((hash_value ^ byte) * FNV_PRIME) & U64_MASK
    return len(payload), hash_value


def rust_consume_state_bytes(payload: bytes) -> tuple[int, int]:
    require_rust_core()
    assert _consume_state_bytes is not None
    size, hash_value = _consume_state_bytes(payload)
    return int(size), int(hash_value)


class RustBattleMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    ON = "on"


@dataclass(frozen=True)
class BattleClockState:
    tick: int
    time: float
    dt: float
    double_elixir: bool
    triple_elixir: bool
    overtime: bool
    game_over: bool

    def sha256(self) -> str:
        payload = struct.pack(
            "<qdd????",
            self.tick,
            self.time,
            self.dt,
            self.double_elixir,
            self.triple_elixir,
            self.overtime,
            self.game_over,
        )
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ResidentPlayerState:
    player_id: int
    elixir: float
    max_elixir: float
    next_card_refill_cooldown_ms: int
    hand: tuple[str | None, ...]
    cycle_queue: tuple[str, ...]
    king_tower_hp: float
    left_tower_hp: float
    right_tower_hp: float

    def append_hash_payload(self, payload: bytearray) -> None:
        payload.extend(struct.pack("<qddqQ", self.player_id, self.elixir, self.max_elixir, self.next_card_refill_cooldown_ms, len(self.hand)))
        for card in self.hand:
            if card is None:
                payload.append(0)
            else:
                payload.append(1)
                _append_string(payload, card)
        payload.extend(struct.pack("<Q", len(self.cycle_queue)))
        for card in self.cycle_queue:
            _append_string(payload, card)
        payload.extend(
            struct.pack(
                "<ddd",
                self.king_tower_hp,
                self.left_tower_hp,
                self.right_tower_hp,
            )
        )


@dataclass(frozen=True)
class ResidentTowerState:
    id: int
    player_id: int
    slot: str
    hp: float
    hp_milli: int
    is_alive: bool
    is_active: bool
    last_attack_time: float

    def append_hash_payload(self, payload: bytearray) -> None:
        payload.extend(struct.pack("<qq", self.id, self.player_id))
        _append_string(payload, self.slot)
        payload.extend(
            struct.pack(
                "<dq??d",
                self.hp,
                self.hp_milli,
                self.is_alive,
                self.is_active,
                self.last_attack_time,
            )
        )


@dataclass(frozen=True)
class ResidentOutcomeState:
    sudden_death: bool
    game_over: bool
    winner: int | None
    sudden_death_crowns: tuple[int, int]


def _append_string(payload: bytearray, value: str) -> None:
    encoded = value.encode("utf-8")
    payload.extend(struct.pack("<Q", len(encoded)))
    payload.extend(encoded)


class ResidentRustBattle:
    """Python owner for one long-lived native battle allocation.

    A complete canonical checkpoint crosses the boundary only at construction
    or an explicit checkpoint replacement. Ordinary phase methods operate on
    resident Rust fields. Complete-tick ``on`` mode remains fail-closed until
    every phase has been ported and the extension advertises that capability.
    """

    def __init__(self, native: Any) -> None:
        self._native = native

    @classmethod
    def from_battle(cls, battle: Any) -> ResidentRustBattle:
        require_rust_core()
        checkpoint = snapshot_bytes(canonical_battle_snapshot(battle))
        assert _ResidentBattle is not None
        native = _ResidentBattle(
            checkpoint,
            tick=int(battle.tick),
            time=float(battle.time),
            dt=float(battle.dt),
            double_elixir=bool(battle.double_elixir),
            triple_elixir=bool(battle.triple_elixir),
            overtime=bool(battle.overtime),
            game_over=bool(battle.game_over),
            double_elixir_start_time=float(battle.double_elixir_start_time),
            overtime_start_time=float(battle.overtime_start_time),
            triple_elixir_start_time=float(battle.triple_elixir_start_time),
            player_tick_ms=round(float(battle.dt) * 1000.0),
            refill_schedule=list(
                DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS
            ),
            players=[
                (
                    int(player.player_id),
                    float(player.elixir),
                    float(player.max_elixir),
                    int(player.next_card_refill_cooldown_ms),
                    list(player.hand),
                    list(player.cycle_queue),
                    float(player.king_tower_hp),
                    float(player.left_tower_hp),
                    float(player.right_tower_hp),
                )
                for player in battle.players
            ],
            towers=[
                (
                    int(entity.id),
                    int(entity.player_id),
                    str(entity._crown_tower_slot),
                    float(entity.hitpoints),
                    round(float(entity.hitpoints) * 1000.0),
                    bool(entity.is_alive),
                    bool(getattr(entity, "_tower_active", True)),
                    float(entity.last_attack_time),
                )
                for entity in battle.entities.values()
                if isinstance(entity, Building)
                and entity._crown_tower_slot in {"left", "right", "king"}
            ],
            idle_eligible=bool(battle.can_fast_forward_idle()),
            sparse_idle_win_checks=True,
            sudden_death=bool(battle.sudden_death),
            sudden_death_crowns=tuple(battle._sudden_death_crowns),
            tiebreaker_time=float(battle.tiebreaker_time),
            winner=battle.winner,
        )
        return cls(native)

    @property
    def supports_complete_tick(self) -> bool:
        return bool(self._native.supports_complete_tick())

    def require_complete_tick(self, mode: RustBattleMode | str) -> None:
        parsed_mode = RustBattleMode(mode)
        if parsed_mode is RustBattleMode.ON and not self.supports_complete_tick:
            raise RuntimeError(
                "Rust battle mode 'on' is unavailable: the resident core does "
                "not yet implement every native tick phase"
            )

    def advance_clock_phase(self) -> bool:
        return bool(self._native.advance_clock_phase())

    def clock_state(self) -> BattleClockState:
        values = self._native.clock_state()
        return BattleClockState(*values)

    def clock_sha256(self) -> str:
        return str(self._native.clock_sha256())

    def advance_player_phase(self) -> None:
        self._native.advance_player_phase()

    def player_states(self) -> tuple[ResidentPlayerState, ...]:
        return tuple(
            ResidentPlayerState(
                player_id=int(values[0]),
                elixir=float(values[1]),
                max_elixir=float(values[2]),
                next_card_refill_cooldown_ms=int(values[3]),
                hand=tuple(values[4]),
                cycle_queue=tuple(values[5]),
                king_tower_hp=float(values[6]),
                left_tower_hp=float(values[7]),
                right_tower_hp=float(values[8]),
            )
            for values in self._native.player_states()
        )

    def player_sha256(self) -> str:
        return str(self._native.player_sha256())

    @property
    def supports_idle_ticks(self) -> bool:
        return bool(self._native.supports_idle_ticks())

    def advance_idle_ticks(self, ticks: int) -> int:
        return int(self._native.advance_idle_ticks(ticks))

    def tower_states(self) -> tuple[ResidentTowerState, ...]:
        return tuple(
            ResidentTowerState(
                id=int(values[0]),
                player_id=int(values[1]),
                slot=str(values[2]),
                hp=float(values[3]),
                hp_milli=int(values[4]),
                is_alive=bool(values[5]),
                is_active=bool(values[6]),
                last_attack_time=float(values[7]),
            )
            for values in self._native.tower_states()
        )

    def outcome_state(self) -> ResidentOutcomeState:
        sudden_death, game_over, winner, crowns = self._native.outcome_state()
        return ResidentOutcomeState(
            sudden_death=bool(sudden_death),
            game_over=bool(game_over),
            winner=None if winner is None else int(winner),
            sudden_death_crowns=(int(crowns[0]), int(crowns[1])),
        )

    def idle_sha256(self) -> str:
        return str(self._native.idle_sha256())

    def entity_state_bytes(self) -> bytes:
        return bytes(self._native.entity_state_bytes())

    def entity_sha256(self) -> str:
        return str(self._native.entity_sha256())

    def checkpoint_bytes(self) -> bytes:
        return bytes(self._native.checkpoint_bytes())

    @property
    def checkpoint_sha256(self) -> str:
        return str(self._native.checkpoint_sha256())

    @property
    def checkpoint_size(self) -> int:
        return int(self._native.checkpoint_size())

    @property
    def checkpoint_generation(self) -> int:
        return int(self._native.checkpoint_generation())

    @property
    def checkpoint_is_current(self) -> bool:
        return bool(self._native.checkpoint_is_current())

    @property
    def schema_version(self) -> int:
        return int(self._native.schema_version())

    def replace_checkpoint(self, payload: bytes) -> None:
        self._native.replace_checkpoint(payload)


def compare_clock_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = BattleClockState(
        tick=int(battle.tick),
        time=float(battle.time),
        dt=float(battle.dt),
        double_elixir=bool(battle.double_elixir),
        triple_elixir=bool(battle.triple_elixir),
        overtime=bool(battle.overtime),
        game_over=bool(battle.game_over),
    )
    actual = resident.clock_state()
    if actual == expected and resident.clock_sha256() == expected.sha256():
        return
    for field_name in BattleClockState.__dataclass_fields__:
        expected_value = getattr(expected, field_name)
        actual_value = getattr(actual, field_name)
        if type(expected_value) is not type(actual_value) or expected_value != actual_value:
            raise AssertionError(
                "resident Rust clock parity mismatch "
                f"field={field_name} expected={expected_value!r} "
                f"actual={actual_value!r}"
            )
    raise AssertionError(
        "resident Rust clock hash mismatch "
        f"expected={expected.sha256()} actual={resident.clock_sha256()}"
    )


def python_player_states(battle: Any) -> tuple[ResidentPlayerState, ...]:
    return tuple(
        ResidentPlayerState(
            player_id=int(player.player_id),
            elixir=float(player.elixir),
            max_elixir=float(player.max_elixir),
            next_card_refill_cooldown_ms=int(
                player.next_card_refill_cooldown_ms
            ),
            hand=tuple(player.hand),
            cycle_queue=tuple(player.cycle_queue),
            king_tower_hp=float(player.king_tower_hp),
            left_tower_hp=float(player.left_tower_hp),
            right_tower_hp=float(player.right_tower_hp),
        )
        for player in battle.players
    )


def player_states_sha256(states: tuple[ResidentPlayerState, ...]) -> str:
    payload = bytearray(struct.pack("<Q", len(states)))
    for player in states:
        player.append_hash_payload(payload)
    return hashlib.sha256(payload).hexdigest()


def compare_player_phase(battle: Any, resident: ResidentRustBattle) -> None:
    expected = python_player_states(battle)
    actual = resident.player_states()
    if actual == expected and resident.player_sha256() == player_states_sha256(expected):
        return
    if len(actual) != len(expected):
        raise AssertionError(
            "resident Rust player parity mismatch "
            f"field=count expected={len(expected)} actual={len(actual)}"
        )
    for player_index, (expected_player, actual_player) in enumerate(
        zip(expected, actual, strict=True)
    ):
        for field_name in ResidentPlayerState.__dataclass_fields__:
            expected_value = getattr(expected_player, field_name)
            actual_value = getattr(actual_player, field_name)
            if type(expected_value) is not type(actual_value) or expected_value != actual_value:
                raise AssertionError(
                    "resident Rust player parity mismatch "
                    f"player={player_index} field={field_name} "
                    f"expected={expected_value!r} actual={actual_value!r}"
                )
    raise AssertionError(
        "resident Rust player hash mismatch "
        f"expected={player_states_sha256(expected)} "
        f"actual={resident.player_sha256()}"
    )


def python_tower_states(battle: Any) -> tuple[ResidentTowerState, ...]:
    return tuple(
        ResidentTowerState(
            id=int(entity.id),
            player_id=int(entity.player_id),
            slot=str(entity._crown_tower_slot),
            hp=float(entity.hitpoints),
            hp_milli=round(float(entity.hitpoints) * 1000.0),
            is_alive=bool(entity.is_alive),
            is_active=bool(getattr(entity, "_tower_active", True)),
            last_attack_time=float(entity.last_attack_time),
        )
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity._crown_tower_slot in {"left", "right", "king"}
    )


def python_outcome_state(battle: Any) -> ResidentOutcomeState:
    return ResidentOutcomeState(
        sudden_death=bool(battle.sudden_death),
        game_over=bool(battle.game_over),
        winner=battle.winner,
        sudden_death_crowns=tuple(battle._sudden_death_crowns),
    )


def idle_state_sha256(battle: Any) -> str:
    clock = BattleClockState(
        tick=int(battle.tick),
        time=float(battle.time),
        dt=float(battle.dt),
        double_elixir=bool(battle.double_elixir),
        triple_elixir=bool(battle.triple_elixir),
        overtime=bool(battle.overtime),
        game_over=bool(battle.game_over),
    )
    outcome = python_outcome_state(battle)
    players = python_player_states(battle)
    towers = python_tower_states(battle)
    payload = bytearray(struct.pack("<qd", clock.tick, clock.time))
    payload.extend(
        bytes(
            (
                clock.double_elixir,
                clock.triple_elixir,
                clock.overtime,
                outcome.sudden_death,
                outcome.game_over,
            )
        )
    )
    if outcome.winner is None:
        payload.append(0)
    else:
        payload.append(1)
        payload.extend(struct.pack("<q", outcome.winner))
    payload.extend(struct.pack("<qq", *outcome.sudden_death_crowns))
    payload.extend(struct.pack("<Q", len(players)))
    for player in players:
        player.append_hash_payload(payload)
    payload.extend(struct.pack("<Q", len(towers)))
    for tower in towers:
        tower.append_hash_payload(payload)
    return hashlib.sha256(payload).hexdigest()


def compare_idle_state(battle: Any, resident: ResidentRustBattle) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    expected_towers = python_tower_states(battle)
    actual_towers = resident.tower_states()
    if expected_towers != actual_towers:
        raise AssertionError(
            "resident Rust idle parity mismatch field=towers "
            f"expected={expected_towers!r} actual={actual_towers!r}"
        )
    expected_outcome = python_outcome_state(battle)
    actual_outcome = resident.outcome_state()
    if expected_outcome != actual_outcome:
        raise AssertionError(
            "resident Rust idle parity mismatch field=outcome "
            f"expected={expected_outcome!r} actual={actual_outcome!r}"
        )
    expected_hash = idle_state_sha256(battle)
    actual_hash = resident.idle_sha256()
    if expected_hash != actual_hash:
        raise AssertionError(
            "resident Rust idle parity mismatch field=hash "
            f"expected={expected_hash} actual={actual_hash}"
        )


def _exact_scalar(value: Any) -> dict[str, str | int]:
    if type(value) is int:
        return {"kind": "int", "value": int(value)}
    return {"bits": f"{struct.unpack('<Q', struct.pack('<d', float(value)))[0]:016x}", "kind": "float"}


def resident_entity_rows(battle: Any) -> list[dict[str, Any]]:
    return [
        {
            "card_name": str(getattr(entity.card_stats, "name", "")),
            "encounter_index": encounter_index,
            "entity_kind": int(entity.entity_kind),
            "hitpoints": _exact_scalar(entity.hitpoints),
            "id": int(entity.id),
            "is_alive": bool(entity.is_alive),
            "max_hitpoints": _exact_scalar(entity.max_hitpoints),
            "mechanics": [
                f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                for mechanic in entity.mechanics
            ],
            "player_id": int(entity.player_id),
            "position_x": _exact_scalar(entity.position.x),
            "position_y": _exact_scalar(entity.position.y),
            "python_type": (
                f"{type(entity).__module__}.{type(entity).__qualname__}"
            ),
            "target_id": (
                None if entity.target_id is None else int(entity.target_id)
            ),
        }
        for encounter_index, entity in enumerate(battle.entities.values())
    ]


def resident_entity_bytes(battle: Any) -> bytes:
    return json.dumps(
        resident_entity_rows(battle),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def compare_resident_entities(
    battle: Any,
    resident: ResidentRustBattle,
) -> None:
    expected = resident_entity_rows(battle)
    actual = json.loads(resident.entity_state_bytes())
    if expected == actual:
        expected_hash = hashlib.sha256(resident_entity_bytes(battle)).hexdigest()
        actual_hash = resident.entity_sha256()
        if expected_hash == actual_hash:
            return
        raise AssertionError(
            "resident Rust entity hash mismatch "
            f"expected={expected_hash} actual={actual_hash}"
        )
    from .differential import first_snapshot_difference

    difference = first_snapshot_difference(expected, actual)
    if difference is None:  # pragma: no cover - defensive
        raise AssertionError("resident Rust entity state mismatch")
    raise AssertionError(
        "resident Rust entity parity mismatch "
        f"path={difference.path} reason={difference.reason} "
        f"expected={difference.expected!r} actual={difference.actual!r}"
    )


def apply_idle_state(battle: Any, resident: ResidentRustBattle) -> None:
    """Publish resident idle state at one explicit Python boundary."""
    clock = resident.clock_state()
    battle.tick = clock.tick
    battle.time = clock.time
    battle.dt = clock.dt
    battle.double_elixir = clock.double_elixir
    battle.triple_elixir = clock.triple_elixir
    battle.overtime = clock.overtime
    battle.game_over = clock.game_over

    player_states = resident.player_states()
    if len(player_states) != len(battle.players):
        raise RuntimeError(
            "resident idle export has a different player count: "
            f"rust={len(player_states)} python={len(battle.players)}"
        )
    for player, player_state in zip(battle.players, player_states, strict=True):
        if int(player.player_id) != player_state.player_id:
            raise RuntimeError(
                "resident idle export changed player order: "
                f"rust={player_state.player_id} python={player.player_id}"
            )
        player.elixir = player_state.elixir
        player.max_elixir = player_state.max_elixir
        player.next_card_refill_cooldown_ms = (
            player_state.next_card_refill_cooldown_ms
        )
        player.hand[:] = player_state.hand
        player.cycle_queue = deque(player_state.cycle_queue)
        # Idle ticks never change tower HP. Keeping the Python values avoids
        # turning exact integer tower snapshots into binary64 at publication.

    towers_by_id = {
        entity.id: entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity._crown_tower_slot in {"left", "right", "king"}
    }
    tower_states = resident.tower_states()
    if set(towers_by_id) != {state.id for state in tower_states}:
        raise RuntimeError("resident idle export changed Crown Tower membership")
    for tower_state in tower_states:
        tower = towers_by_id[tower_state.id]
        if (
            tower.player_id != tower_state.player_id
            or tower._crown_tower_slot != tower_state.slot
        ):
            raise RuntimeError(
                "resident idle export changed Crown Tower identity "
                f"id={tower_state.id}"
            )
        # The idle path never mutates tower HP/liveness/activation. Preserve
        # their original Python scalar types and instance/class field layout;
        # only the visualization clock advances in this coherent phase.
        tower.last_attack_time = tower_state.last_attack_time

    outcome = resident.outcome_state()
    battle.sudden_death = outcome.sudden_death
    battle.game_over = outcome.game_over
    battle.winner = outcome.winner
    if (
        "_sudden_death_crowns" in battle.__dict__
        or outcome.sudden_death_crowns != (0, 0)
    ):
        battle._sudden_death_crowns = outcome.sudden_death_crowns


assert SNAPSHOT_SCHEMA_VERSION == 1
