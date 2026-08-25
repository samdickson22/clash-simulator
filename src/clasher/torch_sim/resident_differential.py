"""Episode-level differential verification for the resident tensor engine.

This is verification/support code, not the production stepping path. Python
oracle battles and boundary diagnostics are intentionally allowed here. Rows
which leave resident support are reported as fallback-only and are never
counted as parity evidence. ``parity_rows`` proves only the explicitly
represented snapshot fields below, not complete ``BattleState`` parity.
Oracle events are captured at their scalar call sites. Event kinds which cannot
be represented by the verifier contract are rejected instead of reconstructed
from end-state deltas.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, cast

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import CARD_NAME_ALIASES
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.spells import SPELL_REGISTRY

from .actions import NO_OP_ACTION
from .catalog import TensorCardCatalog
from .deployment import TensorDeploymentCatalog
from .diagnostics import StateDivergence, first_divergence
from .oracle_event_capture import (
    OracleEventRecord,
    OraclePayloadKind,
    PythonOracleEventCapture,
)
from .resident_engine import (
    TensorResidentEngine,
    _resident_deployment_catalog_closure,
)
from .runtime_state import RuntimeEventOpcode, TickPhase

RESIDENT_COMPARISON_SCOPE = (
    "battle clocks/phases/outcome/allocation",
    "player elixir/refill/hand/cycle/tower values",
    "resident entity identity/card/native position/HP/target/combat/deploy/status",
    "CPython RNG state",
    "call-site event phase/opcode/order/identity/position/amount/payload kind",
)


class ResidentImplementationTopology(str, Enum):
    PYTHON_ORACLE = "python_oracle"
    PYTORCH_RESIDENT_BATCHED = "pytorch_resident_batched"


class ResidentActionProvider(Protocol):
    def __call__(
        self,
        tick: int,
        battles: Sequence[BattleState],
    ) -> Sequence[Sequence[int]] | torch.Tensor: ...


ResidentMutator = Callable[[int, TensorResidentEngine], None]


@dataclass(frozen=True)
class ResidentEventRecord:
    sequence: int
    phase: int
    opcode: int
    source_id: int
    target_id: int
    x_units: int
    y_units: int
    amount: float
    payload_kind: int
    payload: int


@dataclass(frozen=True)
class ResidentEpisodeDivergence:
    row: int
    tick: int
    action: tuple[int, int]
    state: StateDivergence | None
    expected_rng: tuple[object, ...]
    actual_rng: tuple[object, ...]
    expected_events: tuple[ResidentEventRecord, ...]
    actual_events: tuple[ResidentEventRecord, ...]

    @property
    def path(self) -> str:
        if self.state is not None:
            return self.state.path
        if self.expected_rng != self.actual_rng:
            return "battle.rng_state"
        return "battle.events"


@dataclass(frozen=True)
class ResidentEpisodeReport:
    """Episode result over :data:`RESIDENT_COMPARISON_SCOPE` only."""

    ticks_executed: int
    resident_rows: tuple[int, ...]
    preflight_rejected_rows: tuple[int, ...]
    runtime_rejected_rows: tuple[int, ...]
    fallback_only_rows: tuple[int, ...]
    completed_rows: tuple[int, ...]
    parity_rows: tuple[int, ...]
    interaction_rows: tuple[int, ...]
    interaction_entity_ids: tuple[tuple[int, ...], ...]
    diverged_rows: tuple[int, ...]
    divergences: tuple[ResidentEpisodeDivergence, ...]
    divergence: ResidentEpisodeDivergence | None
    semantic_scope: tuple[str, ...]
    oracle_topology: ResidentImplementationTopology
    candidate_topology: ResidentImplementationTopology

    @property
    def parity_passed(self) -> bool:
        """Whether at least one completed resident row matched the represented subset."""

        return self.divergence is None and bool(self.parity_rows)


def _winner(value: int) -> int | None:
    return None if value < 0 else value


def _core_card_name(engine: TensorResidentEngine, value: int) -> str | None:
    return None if value == 0 else engine.runtime.battle.card_names[value]


def _resident_snapshot(engine: TensorResidentEngine, row: int) -> dict[str, Any]:
    core = engine.runtime.battle
    player_rows: list[dict[str, Any]] = []
    for player in range(2):
        queue_length = int(core.cycle_queue_length[row, player].item())
        player_rows.append(
            {
                "elixir": float(core.elixir[row, player].item()),
                "max_elixir": float(core.max_elixir[row, player].item()),
                "refill_ms": int(core.refill_cooldown_ms[row, player].item()),
                "hand": tuple(
                    _core_card_name(engine, int(value))
                    for value in core.hand[row, player].tolist()
                ),
                "cycle": tuple(
                    _core_card_name(engine, int(value))
                    for value in core.cycle_queue[row, player, :queue_length].tolist()
                ),
                "tower_hp": tuple(
                    float(value) for value in core.tower_hp[row, player].tolist()
                ),
            }
        )

    entities: list[dict[str, Any]] = []
    for slot in range(engine.runtime.max_entities):
        if not bool(engine.runtime.entity_pool.active[row, slot].item()):
            continue
        entity_id = int(core.entity_id[row, slot].item())
        card_id = int(core.entity_card[row, slot].item())
        target_slot = int(engine.runtime.phases.target_slot[row, slot].item())
        target_id = (
            None
            if target_slot < 0
            or not bool(engine.runtime.entity_pool.active[row, target_slot].item())
            else int(core.entity_id[row, target_slot].item())
        )
        hp_value = float(core.entity_hp[row, slot].item())
        hitpoints: float | int = (
            round(hp_value)
            if bool(core.entity_hp_integer_kind[row, slot].item())
            else hp_value
        )
        entities.append(
            {
                "id": entity_id,
                "kind": int(core.entity_kind[row, slot].item()),
                "player": int(core.entity_player[row, slot].item()),
                "card": _core_card_name(engine, card_id),
                "position_units": (
                    int(core.entity_x_units[row, slot].item()),
                    int(core.entity_y_units[row, slot].item()),
                ),
                "hitpoints": hitpoints,
                "max_hitpoints": float(core.entity_max_hp[row, slot].item()),
                "target_id": target_id,
                "attack_cooldown": float(
                    engine.combat.attack_cooldown[row, slot].item()
                ),
                "last_attack_time": float(
                    core.entity_last_attack_time[row, slot].item()
                ),
                "deploy_delay": float(core.entity_deploy_delay[row, slot].item()),
                "placement_pending": bool(
                    core.entity_placement_pending[row, slot].item()
                ),
                "spawn_hook_pending": bool(
                    core.entity_spawn_hook_pending[row, slot].item()
                ),
                "spawn_hook_fired": bool(
                    core.entity_spawn_hook_fired[row, slot].item()
                ),
                "stun_timer": float(engine.runtime.status.stun_timer[row, slot].item()),
                "slow_timer": float(engine.runtime.status.slow_timer[row, slot].item()),
                "haste_timer": float(
                    engine.runtime.status.haste_timer[row, slot].item()
                ),
            }
        )
    entities.sort(key=lambda item: int(item["id"]))
    return {
        "time": float(core.time[row].item()),
        "tick": int(core.tick[row].item()),
        "double_elixir": bool(core.double_elixir[row].item()),
        "triple_elixir": bool(core.triple_elixir[row].item()),
        "overtime": bool(core.overtime[row].item()),
        "sudden_death": bool(core.sudden_death[row].item()),
        "game_over": bool(core.game_over[row].item()),
        "winner": _winner(int(core.winner[row].item())),
        "next_entity_id": int(engine.runtime.entity_pool.next_entity_id[row].item()),
        "players": tuple(player_rows),
        "entities": tuple(entities),
    }


def _oracle_snapshot(battle: BattleState) -> dict[str, Any]:
    players = tuple(
        {
            "elixir": float(player.elixir),
            "max_elixir": float(player.max_elixir),
            "refill_ms": int(player.next_card_refill_cooldown_ms),
            "hand": tuple(player.hand),
            "cycle": tuple(player.cycle_queue),
            "tower_hp": (
                float(player.left_tower_hp),
                float(player.right_tower_hp),
                float(player.king_tower_hp),
            ),
        }
        for player in battle.players
    )
    entities = []
    for entity in sorted(battle.entities.values(), key=lambda item: item.id):
        target_id = entity.target_id if entity.target_id in battle.entities else None
        entities.append(
            {
                "id": entity.id,
                "kind": entity.entity_kind,
                "player": entity.player_id,
                "card": getattr(entity.card_stats, "name", None),
                "position_units": (
                    tiles_to_logic_units(entity.position.x),
                    tiles_to_logic_units(entity.position.y),
                ),
                "hitpoints": entity.hitpoints,
                "max_hitpoints": float(entity.max_hitpoints),
                "target_id": target_id,
                "attack_cooldown": float(entity.attack_cooldown),
                "last_attack_time": float(entity.last_attack_time),
                "deploy_delay": float(entity.deploy_delay_remaining),
                "placement_pending": bool(entity.placement_pending),
                "spawn_hook_pending": bool(
                    getattr(entity, "_spawn_hook_pending", False)
                ),
                "spawn_hook_fired": bool(getattr(entity, "_spawn_hook_fired", False)),
                "stun_timer": float(entity.stun_timer),
                "slow_timer": float(entity.slow_timer),
                "haste_timer": float(entity.haste_timer),
            }
        )
    return {
        "time": float(battle.time),
        "tick": int(battle.tick),
        "double_elixir": bool(battle.double_elixir),
        "triple_elixir": bool(battle.triple_elixir),
        "overtime": bool(battle.overtime),
        "sudden_death": bool(battle.sudden_death),
        "game_over": bool(battle.game_over),
        "winner": battle.winner,
        "next_entity_id": int(battle.next_entity_id),
        "players": players,
        "entities": tuple(entities),
    }


def _normalize_oracle_payload(
    value: object,
    engine: TensorResidentEngine,
    payload_kind: OraclePayloadKind,
) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        card_to_id = engine.runtime.battle.card_to_id
        alias = next(
            (
                name
                for name, serialized in CARD_NAME_ALIASES.items()
                if serialized == value and name in card_to_id
            ),
            None,
        )
        if (
            payload_kind
            in {
                OraclePayloadKind.SPELL_EXECUTION,
                OraclePayloadKind.SPELL_PROJECTILE,
            }
            and alias is not None
        ):
            return int(card_to_id[alias])
        if value in card_to_id:
            return int(card_to_id[value])
        if alias is not None:
            return int(card_to_id[alias])
        raise ValueError(f"captured event payload is outside the card closure: {value}")
    if type(value) is int:
        return value
    raise TypeError(
        "captured event payload has no exact resident representation: "
        f"{type(value).__name__}"
    )


def _oracle_events(
    captured: Sequence[OracleEventRecord],
    engine: TensorResidentEngine,
) -> tuple[ResidentEventRecord, ...]:
    result: list[ResidentEventRecord] = []
    for sequence, event in enumerate(captured):
        try:
            oracle_payload_kind = OraclePayloadKind(event.payload_kind)
            payload_kind = int(oracle_payload_kind)
        except ValueError as exc:
            raise ValueError(
                f"uncaptured oracle event payload kind: {event.payload_kind}"
            ) from exc
        if type(event.amount) not in {int, float}:
            raise TypeError(
                "captured event amount has no exact resident representation: "
                f"{type(event.amount).__name__}"
            )
        amount = cast(int | float, event.amount)
        result.append(
            ResidentEventRecord(
                sequence=sequence,
                phase=int(event.phase),
                opcode=int(event.opcode),
                source_id=int(event.source_id),
                target_id=int(event.target_id),
                x_units=int(event.x_units),
                y_units=int(event.y_units),
                amount=float(amount),
                payload_kind=payload_kind,
                payload=_normalize_oracle_payload(
                    event.payload, engine, oracle_payload_kind
                ),
            )
        )
    return tuple(result)


def _resident_payload_kind(
    engine: TensorResidentEngine,
    *,
    phase: int,
    opcode: int,
    source_id: int,
    target_id: int,
    payload: int,
) -> int:
    if opcode == int(RuntimeEventOpcode.COMMAND):
        return int(OraclePayloadKind.SPELL_EXECUTION)
    if opcode == int(RuntimeEventOpcode.PROJECTILE):
        if phase == int(TickPhase.COMBAT):
            return int(OraclePayloadKind.COMBAT_PROJECTILE)
        if phase == int(TickPhase.COMMANDS):
            return int(OraclePayloadKind.SPELL_PROJECTILE)
        if phase == int(TickPhase.OBJECTS):
            return int(OraclePayloadKind.PROJECTILE_IMPACT)
    if opcode == int(RuntimeEventOpcode.AREA):
        return int(OraclePayloadKind.SPELL_AREA)
    if opcode == int(RuntimeEventOpcode.DAMAGE):
        return int(OraclePayloadKind.DAMAGE)
    if opcode == int(RuntimeEventOpcode.DEATH):
        return int(OraclePayloadKind.DEATH)
    if opcode == int(RuntimeEventOpcode.STATUS):
        name = (
            engine.runtime.battle.card_names[payload]
            if 0 < payload < len(engine.runtime.battle.card_names)
            else ""
        )
        spell = SPELL_REGISTRY.get(name)
        if spell is not None and float(getattr(spell, "stun_duration", 0.0)) > 0:
            return int(OraclePayloadKind.STUN)
        if spell is not None and (
            float(getattr(spell, "slow_duration", 0.0)) > 0
            or bool(getattr(spell, "freeze_effect", False))
            or float(getattr(spell, "speed_multiplier", 1.0)) < 1.0
        ):
            return int(OraclePayloadKind.SLOW)
        if 0 <= payload < engine.spawn_areas.catalog.supported.numel() and bool(
            engine.spawn_areas.catalog.supported[payload].item()
        ):
            movement = float(
                engine.spawn_areas.catalog.movement_multiplier[payload].item()
            )
            attack = float(engine.spawn_areas.catalog.attack_multiplier[payload].item())
            spawn = float(engine.spawn_areas.catalog.spawn_multiplier[payload].item())
            if movement == attack == spawn == 0.0:
                return int(OraclePayloadKind.STUN)
            if min(movement, attack, spawn) < 1.0:
                return int(OraclePayloadKind.SLOW)
    if opcode == int(RuntimeEventOpcode.MOVEMENT):
        return int(OraclePayloadKind.UNDERGROUND_MOVEMENT)
    if opcode == int(RuntimeEventOpcode.SPAWN):
        if phase == int(TickPhase.COMMANDS) and source_id > 0 and target_id == 0:
            return int(OraclePayloadKind.COMMAND_DEPLOYMENT)
        if target_id > 0:
            return int(OraclePayloadKind.OBJECT_CHARACTER)
    # STATUS cannot be losslessly classified as STUN versus SLOW from the
    # current resident planes. Keep it explicit so it fails closed instead of
    # being ignored.
    return int(OraclePayloadKind.NONE)


def _resident_events(
    engine: TensorResidentEngine,
    row: int,
    start: int,
) -> tuple[ResidentEventRecord, ...]:
    stop = int(engine.runtime.events.count[row].item())
    events = engine.runtime.events
    return tuple(
        ResidentEventRecord(
            sequence=slot - start,
            phase=int(events.phase[row, slot].item()),
            opcode=int(events.opcode[row, slot].item()),
            source_id=int(events.source_id[row, slot].item()),
            target_id=int(events.target_id[row, slot].item()),
            x_units=int(events.x_units[row, slot].item()),
            y_units=int(events.y_units[row, slot].item()),
            amount=float(events.amount[row, slot].item()),
            payload_kind=_resident_payload_kind(
                engine,
                phase=int(events.phase[row, slot].item()),
                opcode=int(events.opcode[row, slot].item()),
                source_id=int(events.source_id[row, slot].item()),
                target_id=int(events.target_id[row, slot].item()),
                payload=int(events.payload[row, slot].item()),
            ),
            payload=int(events.payload[row, slot].item()),
        )
        for slot in range(start, stop)
    )


class ResidentEpisodeDifferential:
    """Run batched resident rows beside independent Python oracle episodes."""

    def __init__(
        self,
        *,
        device: str | torch.device = "cpu",
        max_entities: int = 128,
        max_objects: int = 128,
        event_capacity: int = 512,
    ) -> None:
        self.device = torch.device(device)
        self.max_entities = max_entities
        self.max_objects = max_objects
        self.event_capacity = event_capacity

    def run(
        self,
        battles: Sequence[BattleState],
        actions: ResidentActionProvider,
        *,
        max_ticks: int,
        resident_mutator: ResidentMutator | None = None,
        stop_on_first_divergence: bool = True,
    ) -> ResidentEpisodeReport:
        if not battles:
            raise ValueError("at least one battle is required")
        if max_ticks < 1:
            raise ValueError("max_ticks must be positive")
        oracle = [battle.clone() for battle in battles]
        engine = TensorResidentEngine.from_battles(
            [battle.clone() for battle in battles],
            device=self.device,
            max_entities=self.max_entities,
            max_objects=self.max_objects,
            event_capacity=self.event_capacity,
        )
        action_space = DiscreteTileActionSpace(canonical_perspective=True)
        resident = torch.ones(len(battles), dtype=torch.bool, device=self.device)
        preflight_rejected = torch.zeros_like(resident)
        runtime_rejected = torch.zeros_like(resident)
        completed = torch.zeros_like(resident)
        interaction = torch.zeros_like(resident)
        interaction_ids: list[set[int]] = [set() for _ in battles]
        diverged = torch.zeros_like(resident)
        divergences: list[ResidentEpisodeDivergence] = []

        for tick in range(max_ticks):
            raw_actions = actions(tick, tuple(oracle))
            action_tensor = torch.as_tensor(
                raw_actions, dtype=torch.int64, device=self.device
            )
            if action_tensor.shape != (len(battles), 2):
                raise ValueError("action provider must return shape [batch, 2]")
            preflight = engine.preflight(action_tensor)
            live_resident = resident & ~completed
            newly_preflight_rejected = live_resident & ~preflight.supported
            preflight_rejected |= newly_preflight_rejected
            resident &= preflight.supported | completed

            event_start = engine.runtime.events.count.clone()
            captured_events: list[tuple[OracleEventRecord, ...]] = [() for _ in oracle]
            for row, battle in enumerate(oracle):
                if battle.game_over:
                    continue
                with PythonOracleEventCapture(battle) as capture:
                    order = [0, 1]
                    battle.rng.shuffle(order)
                    for player in order:
                        action_space.apply_action(
                            battle, player, int(action_tensor[row, player].item())
                        )
                    capture.step_logic_ticks(1)
                    captured_events[row] = tuple(capture.events)

            # An interaction is post-deployment only when that entity's
            # character component was already live at the start of the tick.
            # A delay reaching zero in the later object phase cannot make an
            # earlier collision/movement/status phase count retroactively.
            interaction_eligible = (
                engine.runtime.entity_pool.active
                & engine.runtime.battle.entity_active
                & (engine.runtime.battle.entity_deploy_delay <= 1e-9)
            )
            resident_result = engine.step(action_tensor)
            live_resident = resident & ~completed
            newly_runtime_rejected = live_resident & ~resident_result.committed
            runtime_rejected |= newly_runtime_rejected
            resident &= resident_result.committed | completed
            combat_sources = resident_result.combat.attacked & interaction_eligible
            movement_sources = (
                resident_result.movement.ordinary_moved
                | resident_result.movement.collision_only_moved
                | resident_result.movement.river_jump_moved
            ) & interaction_eligible
            status_targets = (
                (resident_result.status.lifetime_hitpoint_loss > 0)
                | (resident_result.status.periodic_hitpoint_loss > 0)
            ) & interaction_eligible
            object_targets = (resident_result.objects.damage > 0) & interaction_eligible
            interaction |= resident & (
                combat_sources.any(dim=1)
                | movement_sources.any(dim=1)
                | status_targets.any(dim=1)
                | object_targets.any(dim=1)
            )
            for row in range(len(battles)):
                if not bool(resident[row].item()):
                    continue
                for mask, identifiers in (
                    (combat_sources[row], engine.combat.entity_id[row]),
                    (movement_sources[row], engine.movement.entity_id[row]),
                    (status_targets[row], engine.combat.entity_id[row]),
                    (object_targets[row], engine.combat.entity_id[row]),
                ):
                    interaction_ids[row].update(
                        int(value)
                        for value in identifiers[mask].tolist()
                        if int(value) > 0
                    )
            if resident_mutator is not None:
                resident_mutator(tick, engine)

            completed |= torch.tensor(
                [battle.game_over for battle in oracle],
                dtype=torch.bool,
                device=self.device,
            )

            for row, battle in enumerate(oracle):
                if not bool(resident[row].item()):
                    continue
                expected_snapshot = _oracle_snapshot(battle)
                actual_snapshot = _resident_snapshot(engine, row)
                mismatch = first_divergence(
                    expected_snapshot,
                    actual_snapshot,
                    path=f"rows[{row}]",
                )
                expected_rng = battle.rng.getstate()
                actual_rng = engine.runtime.battle.rng.python_state(row)
                expected_events = _oracle_events(captured_events[row], engine)
                actual_events = _resident_events(
                    engine, row, int(event_start[row].item())
                )
                if (
                    mismatch is not None
                    or expected_rng != actual_rng
                    or expected_events != actual_events
                ):
                    divergence = ResidentEpisodeDivergence(
                        row=row,
                        tick=tick,
                        action=(
                            int(action_tensor[row, 0].item()),
                            int(action_tensor[row, 1].item()),
                        ),
                        state=mismatch,
                        expected_rng=expected_rng,
                        actual_rng=actual_rng,
                        expected_events=expected_events,
                        actual_events=actual_events,
                    )
                    divergences.append(divergence)
                    diverged[row] = True
                    resident[row] = False
                    if stop_on_first_divergence:
                        return self._report(
                            tick + 1,
                            resident,
                            preflight_rejected,
                            runtime_rejected,
                            completed,
                            interaction,
                            interaction_ids,
                            diverged,
                            tuple(divergences),
                        )
            if bool(completed.all().item()):
                return self._report(
                    tick + 1,
                    resident,
                    preflight_rejected,
                    runtime_rejected,
                    completed,
                    interaction,
                    interaction_ids,
                    diverged,
                    tuple(divergences),
                )
        return self._report(
            max_ticks,
            resident,
            preflight_rejected,
            runtime_rejected,
            completed,
            interaction,
            interaction_ids,
            diverged,
            tuple(divergences),
        )

    @staticmethod
    def _report(
        ticks: int,
        resident: torch.Tensor,
        preflight_rejected: torch.Tensor,
        runtime_rejected: torch.Tensor,
        completed: torch.Tensor,
        interaction: torch.Tensor,
        interaction_ids: Sequence[set[int]],
        diverged: torch.Tensor,
        divergences: tuple[ResidentEpisodeDivergence, ...],
    ) -> ResidentEpisodeReport:
        def rows(mask: torch.Tensor) -> tuple[int, ...]:
            return tuple(
                int(value)
                for value in torch.nonzero(mask, as_tuple=False).flatten().tolist()
            )

        fallback = preflight_rejected | runtime_rejected
        parity = resident & completed
        return ResidentEpisodeReport(
            ticks_executed=ticks,
            resident_rows=rows(resident),
            preflight_rejected_rows=rows(preflight_rejected),
            runtime_rejected_rows=rows(runtime_rejected),
            fallback_only_rows=rows(fallback),
            completed_rows=rows(completed),
            parity_rows=rows(parity),
            interaction_rows=rows(interaction),
            interaction_entity_ids=tuple(
                tuple(sorted(values)) for values in interaction_ids
            ),
            diverged_rows=rows(diverged),
            divergences=divergences,
            divergence=divergences[0] if divergences else None,
            semantic_scope=RESIDENT_COMPARISON_SCOPE,
            oracle_topology=ResidentImplementationTopology.PYTHON_ORACLE,
            candidate_topology=(
                ResidentImplementationTopology.PYTORCH_RESIDENT_BATCHED
            ),
        )


class ResidentCoverageClassification(str, Enum):
    REPRESENTED_INTERACTION_PARITY = "represented_interaction_parity"
    RESIDENT_NO_INTERACTION = "resident_no_interaction"
    PREFLIGHT_FALLBACK = "preflight_fallback"
    RUNTIME_FALLBACK = "runtime_fallback"
    DIVERGED = "diverged"
    INCOMPLETE = "incomplete"


class ResidentCoverageTopology(str, Enum):
    BATCHED_RESIDENT = "batched_resident"
    SCALAR_EXACT_RESIDENT = "scalar_exact_resident"


@dataclass(frozen=True)
class ResidentCardCoverageEntry:
    card_name: str
    card_kind: int
    mechanic_opcodes: tuple[int, ...]
    effect_opcodes: tuple[int, ...]
    classification: ResidentCoverageClassification
    interaction_observed: bool
    divergence_path: str | None

    @property
    def is_evidence(self) -> bool:
        return (
            self.classification
            is ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY
            and self.interaction_observed
        )


@dataclass(frozen=True)
class ResidentCoverageDelta:
    card_name: str
    expected: str | None
    actual: str | None
    mechanic_opcodes: tuple[int, ...]
    effect_opcodes: tuple[int, ...]


class ResidentCoverageDigestMismatch(AssertionError):
    def __init__(
        self,
        expected_digest: str,
        matrix: ResidentCoverageMatrix,
        deltas: tuple[ResidentCoverageDelta, ...],
    ) -> None:
        self.expected_digest = expected_digest
        self.actual_digest = matrix.digest
        self.deltas = deltas
        detail = "; ".join(
            f"{delta.card_name}: {delta.expected!r}->{delta.actual!r} "
            f"mechanics={delta.mechanic_opcodes} effects={delta.effect_opcodes}"
            for delta in deltas
        )
        super().__init__(
            f"resident coverage digest {matrix.digest} != {expected_digest}; {detail}"
        )


@dataclass(frozen=True)
class ResidentCoverageMatrix:
    entries: tuple[ResidentCardCoverageEntry, ...]
    digest: str
    topology: ResidentCoverageTopology

    @property
    def evidence_cards(self) -> tuple[str, ...]:
        return tuple(entry.card_name for entry in self.entries if entry.is_evidence)

    @property
    def fallback_cards(self) -> tuple[str, ...]:
        return tuple(
            entry.card_name
            for entry in self.entries
            if entry.classification
            in {
                ResidentCoverageClassification.PREFLIGHT_FALLBACK,
                ResidentCoverageClassification.RUNTIME_FALLBACK,
            }
        )

    def require_evidence(self, card_name: str) -> ResidentCardCoverageEntry:
        entry = next(
            (item for item in self.entries if item.card_name == card_name), None
        )
        if entry is None:
            raise KeyError(card_name)
        if not entry.is_evidence:
            raise ValueError(
                f"{card_name} is {entry.classification.value}, not represented "
                "post-deployment interaction parity evidence"
            )
        return entry

    def deltas(
        self,
        expected_classifications: Mapping[str, str],
    ) -> tuple[ResidentCoverageDelta, ...]:
        actual = {entry.card_name: entry for entry in self.entries}
        result: list[ResidentCoverageDelta] = []
        for name in sorted(set(expected_classifications) | set(actual)):
            entry = actual.get(name)
            expected = expected_classifications.get(name)
            current = None if entry is None else entry.classification.value
            if expected == current:
                continue
            result.append(
                ResidentCoverageDelta(
                    card_name=name,
                    expected=expected,
                    actual=current,
                    mechanic_opcodes=() if entry is None else entry.mechanic_opcodes,
                    effect_opcodes=() if entry is None else entry.effect_opcodes,
                )
            )
        return tuple(result)

    def assert_digest(
        self,
        expected_digest: str,
        expected_classifications: Mapping[str, str],
    ) -> None:
        deltas = self.deltas(expected_classifications)
        if self.digest == expected_digest and not deltas:
            return
        if not deltas:
            # A digest can change while classifications remain stable (for
            # example an opcode or divergence-path delta). Surface the current
            # per-card opcode matrix instead of emitting an unactionable hash.
            deltas = tuple(
                ResidentCoverageDelta(
                    card_name=entry.card_name,
                    expected=entry.classification.value,
                    actual=entry.classification.value,
                    mechanic_opcodes=entry.mechanic_opcodes,
                    effect_opcodes=entry.effect_opcodes,
                )
                for entry in self.entries
            )
        raise ResidentCoverageDigestMismatch(
            expected_digest,
            self,
            deltas,
        )


def _coverage_digest(entries: Sequence[ResidentCardCoverageEntry]) -> str:
    payload = [
        {
            "card": entry.card_name,
            "kind": entry.card_kind,
            "mechanics": entry.mechanic_opcodes,
            "effects": entry.effect_opcodes,
            "classification": entry.classification.value,
            "interaction": entry.interaction_observed,
            "divergence": entry.divergence_path,
        }
        for entry in entries
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def classify_resident_coverage_row(
    report: ResidentEpisodeReport,
    row: int,
    deployed_entity_ids: Sequence[int],
) -> tuple[ResidentCoverageClassification, bool]:
    """Classify one card row using only interaction attributable to its IDs."""

    deployed = {int(value) for value in deployed_entity_ids}
    attributable = bool(deployed & set(report.interaction_entity_ids[row]))
    if row in report.preflight_rejected_rows:
        return ResidentCoverageClassification.PREFLIGHT_FALLBACK, False
    if row in report.runtime_rejected_rows:
        return ResidentCoverageClassification.RUNTIME_FALLBACK, False
    if row in report.diverged_rows:
        return ResidentCoverageClassification.DIVERGED, attributable
    if row in report.parity_rows and attributable:
        return (
            ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY,
            True,
        )
    if row in report.parity_rows:
        return ResidentCoverageClassification.RESIDENT_NO_INTERACTION, False
    return ResidentCoverageClassification.INCOMPLETE, attributable


def _coverage_fixture(
    card_name: str,
    seed: int,
    *,
    episode_end_time: float = 1.05,
) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card("Knight")
    if target_stats is None:
        raise ValueError("Knight fixture target is unavailable")
    battle._spawn_unit_at_position(
        Position(14.5, 14.5),
        1,
        target_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[1]
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    fillers = [
        name
        for name in ("Knight", "Zap", "Cannon", "Fireball", "Archers")
        if name != card_name
    ]
    player = battle.players[0]
    player.hand = [card_name, *fillers[:3]]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    battle.overtime_start_time = max(0.0, episode_end_time - battle.dt)
    battle.tiebreaker_time = episode_end_time
    return battle


def _coverage_episode_tick_budget(episode_end_time: float, dt: float) -> int:
    """Count repeated logic ticks through the configured terminal boundary."""

    if not math.isfinite(episode_end_time) or episode_end_time <= 0.0:
        raise ValueError("coverage episode end time must be finite and positive")
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("coverage logic dt must be finite and positive")
    elapsed = 0.0
    ticks = 0
    # Match BattleState's repeated float addition exactly. A quotient-based
    # ceil can stop one tick early when a decimal boundary such as Xbow's
    # 3.8 seconds is represented below the mathematical value after 76 adds.
    while elapsed < episode_end_time:
        elapsed += dt
        ticks += 1
    return ticks


def enumerate_enabled_resident_coverage(
    *,
    device: str | torch.device = "cpu",
    decks_path: str = "decks.json",
    card_names: Sequence[str] | None = None,
    team_size: int = 1,
    topology: str
    | ResidentCoverageTopology = ResidentCoverageTopology.BATCHED_RESIDENT,
) -> ResidentCoverageMatrix:
    """Execute the deterministic enabled-card resident interaction matrix.

    Team-size two is explicitly unsupported; no 1v1 evidence is reused as a
    2v2 claim.
    """

    if team_size != 1:
        raise NotImplementedError("resident differential coverage does not support 2v2")
    names = tuple(
        sorted(
            set(
                card_names
                if card_names is not None
                else unique_cards_from_decks(load_deck_pool(decks_path))
            )
        )
    )
    if not names:
        raise ValueError("coverage manifest is empty")
    selected_topology = ResidentCoverageTopology(topology)
    if (
        selected_topology is ResidentCoverageTopology.SCALAR_EXACT_RESIDENT
        and len(names) > 1
    ):
        scalar_entries = tuple(
            entry
            for name in names
            for entry in enumerate_enabled_resident_coverage(
                device=device,
                decks_path=decks_path,
                card_names=(name,),
                team_size=team_size,
                topology=ResidentCoverageTopology.SCALAR_EXACT_RESIDENT,
            ).entries
        )
        return ResidentCoverageMatrix(
            entries=scalar_entries,
            digest=_coverage_digest(scalar_entries),
            topology=selected_topology,
        )
    loader = CardDataLoader()
    catalog_loader, closure_names = _resident_deployment_catalog_closure(
        loader, set(names)
    )
    catalog = TensorCardCatalog.compile(catalog_loader, closure_names)
    deployment_catalog = TensorDeploymentCatalog.compile(catalog_loader, catalog)
    executable_names = names
    post_deployment_seconds = 0.30
    episode_end_by_name: dict[str, float] = {}
    for name in executable_names:
        card_id = catalog.name_to_id[name]
        summon_count = max(1, int(deployment_catalog.summon_count[card_id].item()))
        deploy_delay = float(
            deployment_catalog.deploy_delay_seconds[card_id, :summon_count].max().item()
        )
        simple_character = (
            int(catalog.kind[card_id].item()) in {1, 2}
            and int(catalog.mechanic_count[card_id].item()) == 0
            and int(catalog.effect_count[card_id].item()) == 0
        )
        episode_end_by_name[name] = (
            max(1.05, deploy_delay + post_deployment_seconds)
            if simple_character
            else 1.05
        )
    battles = [
        _coverage_fixture(
            name,
            510_000 + index,
            episode_end_time=episode_end_by_name[name],
        )
        for index, name in enumerate(executable_names)
    ]

    def actions(tick: int, rows: Sequence[BattleState]) -> tuple[tuple[int, int], ...]:
        action = 12 * 18 + 14 if tick == 0 else NO_OP_ACTION
        return tuple((action, NO_OP_ACTION) for _ in rows)

    report = ResidentEpisodeDifferential(
        device=device,
        max_entities=64,
        max_objects=64,
        event_capacity=512,
    ).run(
        battles,
        cast(ResidentActionProvider, actions),
        max_ticks=max(
            _coverage_episode_tick_budget(end_time, battles[0].dt)
            for end_time in episode_end_by_name.values()
        ),
        stop_on_first_divergence=False,
    )
    diverged = {item.row: item for item in report.divergences}
    report_row = {name: row for row, name in enumerate(executable_names)}
    entries: list[ResidentCardCoverageEntry] = []
    for name in names:
        card_id = catalog.name_to_id[name]
        mechanics = tuple(
            int(value)
            for value in catalog.mechanic_opcode[card_id].tolist()
            if int(value) != 0
        )
        effects = tuple(
            int(value)
            for value in catalog.effect_opcode[card_id].tolist()
            if int(value) != 0
        )
        row = report_row[name]
        summon_count = int(catalog.summon_count[card_id].item())
        deployed_ids = tuple(range(2, 2 + summon_count))
        classification, attributed = classify_resident_coverage_row(
            report, row, deployed_ids
        )
        divergence_path = None if row not in diverged else diverged[row].path
        entries.append(
            ResidentCardCoverageEntry(
                card_name=name,
                card_kind=int(catalog.kind[card_id].item()),
                mechanic_opcodes=mechanics,
                effect_opcodes=effects,
                classification=classification,
                interaction_observed=attributed,
                divergence_path=divergence_path,
            )
        )
    stable_entries = tuple(entries)
    return ResidentCoverageMatrix(
        entries=stable_entries,
        digest=_coverage_digest(stable_entries),
        topology=selected_topology,
    )


@dataclass(frozen=True)
class ResidentCoverageTopologyComparison:
    batched: ResidentCoverageMatrix
    scalar_exact: ResidentCoverageMatrix

    @property
    def semantic_digest_matches(self) -> bool:
        return self.batched.digest == self.scalar_exact.digest

    @property
    def deltas(self) -> tuple[ResidentCoverageDelta, ...]:
        expected = {
            entry.card_name: entry.classification.value
            for entry in self.scalar_exact.entries
        }
        return self.batched.deltas(expected)


def compare_resident_coverage_topologies(
    card_names: Sequence[str],
    *,
    device: str | torch.device = "cpu",
) -> ResidentCoverageTopologyComparison:
    """Compare batched resident semantics with independent one-row execution."""

    batched = enumerate_enabled_resident_coverage(
        device=device,
        card_names=card_names,
        topology=ResidentCoverageTopology.BATCHED_RESIDENT,
    )
    scalar = enumerate_enabled_resident_coverage(
        device=device,
        card_names=card_names,
        topology=ResidentCoverageTopology.SCALAR_EXACT_RESIDENT,
    )
    return ResidentCoverageTopologyComparison(batched, scalar)


def no_op_actions(
    _tick: int,
    battles: Sequence[BattleState],
) -> tuple[tuple[int, int], ...]:
    return tuple((NO_OP_ACTION, NO_OP_ACTION) for _ in battles)


__all__ = [
    "RESIDENT_COMPARISON_SCOPE",
    "ResidentActionProvider",
    "ResidentCardCoverageEntry",
    "ResidentCoverageClassification",
    "ResidentCoverageDelta",
    "ResidentCoverageDigestMismatch",
    "ResidentCoverageMatrix",
    "ResidentCoverageTopology",
    "ResidentCoverageTopologyComparison",
    "ResidentEpisodeDifferential",
    "ResidentEpisodeDivergence",
    "ResidentEpisodeReport",
    "ResidentEventRecord",
    "ResidentImplementationTopology",
    "classify_resident_coverage_row",
    "compare_resident_coverage_topologies",
    "enumerate_enabled_resident_coverage",
    "no_op_actions",
]
