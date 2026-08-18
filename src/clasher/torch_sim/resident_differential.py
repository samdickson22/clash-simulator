"""Episode-level differential verification for the resident tensor engine.

This is verification/support code, not the production stepping path. Python
oracle battles and boundary diagnostics are intentionally allowed here. Rows
which leave resident support are reported as fallback-only and are never
counted as parity evidence. ``parity_rows`` proves only the explicitly
represented snapshot fields below, not complete ``BattleState`` parity.
Oracle event inference is intentionally limited to the current mechanic-free
``SPAWN``/``DAMAGE``/``DEATH`` slice.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import torch

from clasher.battle import BattleState
from clasher.kinematics import tiles_to_logic_units
from clasher.rl.action_space import DiscreteTileActionSpace

from .actions import NO_OP_ACTION
from .diagnostics import StateDivergence, first_divergence
from .resident_engine import TensorResidentEngine
from .runtime_state import RuntimeEventOpcode, TickPhase

RESIDENT_COMPARISON_SCOPE = (
    "battle clocks/phases/outcome/allocation",
    "player elixir/refill/hand/cycle/tower values",
    "resident entity identity/card/native position/HP/target/combat/deploy/status",
    "CPython RNG state",
    "mechanic-free SPAWN/DAMAGE/DEATH events",
)


class ResidentActionProvider(Protocol):
    def __call__(
        self,
        tick: int,
        battles: Sequence[BattleState],
    ) -> Sequence[Sequence[int]] | torch.Tensor: ...


ResidentMutator = Callable[[int, TensorResidentEngine], None]


@dataclass(frozen=True)
class ResidentEventRecord:
    phase: int
    opcode: int
    source_id: int
    target_id: int
    amount: float
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
    divergence: ResidentEpisodeDivergence | None

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


def _oracle_events(
    before: Mapping[int, tuple[float | int, int, int]],
    battle: BattleState,
    engine: TensorResidentEngine,
) -> tuple[ResidentEventRecord, ...]:
    after = {
        entity.id: (
            entity.hitpoints,
            tiles_to_logic_units(entity.position.x),
            tiles_to_logic_units(entity.position.y),
        )
        for entity in battle.entities.values()
    }
    events: list[ResidentEventRecord] = []
    for entity_id in sorted(set(after) - set(before)):
        entity = battle.entities[entity_id]
        payload = engine.runtime.battle.card_to_id.get(
            str(getattr(entity.card_stats, "name", "")), 0
        )
        events.append(
            ResidentEventRecord(
                int(TickPhase.COMMANDS),
                int(RuntimeEventOpcode.SPAWN),
                entity_id,
                0,
                0.0,
                payload,
            )
        )
    for entity_id in sorted(set(before) & set(after)):
        old_hp = float(before[entity_id][0])
        new_hp = float(after[entity_id][0])
        if new_hp < old_hp:
            events.append(
                ResidentEventRecord(
                    int(TickPhase.COMBAT),
                    int(RuntimeEventOpcode.DAMAGE),
                    0,
                    entity_id,
                    old_hp - new_hp,
                    0,
                )
            )
    for entity_id in sorted(set(before) - set(after)):
        old_hp, _, _ = before[entity_id]
        if float(old_hp) > 0.0:
            events.extend(
                (
                    ResidentEventRecord(
                        int(TickPhase.COMBAT),
                        int(RuntimeEventOpcode.DAMAGE),
                        0,
                        entity_id,
                        float(old_hp),
                        0,
                    ),
                    ResidentEventRecord(
                        int(TickPhase.COMBAT),
                        int(RuntimeEventOpcode.DEATH),
                        0,
                        entity_id,
                        0.0,
                        0,
                    ),
                )
            )
    return tuple(events)


def _resident_events(
    engine: TensorResidentEngine,
    row: int,
    start: int,
) -> tuple[ResidentEventRecord, ...]:
    stop = int(engine.runtime.events.count[row].item())
    events = engine.runtime.events
    return tuple(
        ResidentEventRecord(
            phase=int(events.phase[row, slot].item()),
            opcode=int(events.opcode[row, slot].item()),
            source_id=int(events.source_id[row, slot].item()),
            target_id=int(events.target_id[row, slot].item()),
            amount=float(events.amount[row, slot].item()),
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

        for tick in range(max_ticks):
            raw_actions = actions(tick, tuple(oracle))
            action_tensor = torch.as_tensor(
                raw_actions, dtype=torch.int64, device=self.device
            )
            if action_tensor.shape != (len(battles), 2):
                raise ValueError("action provider must return shape [batch, 2]")
            preflight = engine.preflight(action_tensor)
            newly_preflight_rejected = resident & ~preflight.supported
            preflight_rejected |= newly_preflight_rejected
            resident &= preflight.supported

            before_entities = [
                {
                    entity.id: (
                        entity.hitpoints,
                        tiles_to_logic_units(entity.position.x),
                        tiles_to_logic_units(entity.position.y),
                    )
                    for entity in battle.entities.values()
                }
                for battle in oracle
            ]
            event_start = engine.runtime.events.count.clone()
            for row, battle in enumerate(oracle):
                if battle.game_over:
                    continue
                order = [0, 1]
                battle.rng.shuffle(order)
                for player in order:
                    action_space.apply_action(
                        battle, player, int(action_tensor[row, player].item())
                    )
                battle.step_logic_ticks(1)

            resident_result = engine.step(action_tensor)
            newly_runtime_rejected = resident & ~resident_result.committed
            runtime_rejected |= newly_runtime_rejected
            resident &= resident_result.committed
            if resident_mutator is not None:
                resident_mutator(tick, engine)

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
                expected_events = _oracle_events(before_entities[row], battle, engine)
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
                    return self._report(
                        tick + 1,
                        resident,
                        preflight_rejected,
                        runtime_rejected,
                        completed,
                        divergence,
                    )
            completed |= torch.tensor(
                [battle.game_over for battle in oracle],
                dtype=torch.bool,
                device=self.device,
            )
            if bool(completed.all().item()):
                return self._report(
                    tick + 1,
                    resident,
                    preflight_rejected,
                    runtime_rejected,
                    completed,
                    None,
                )
        return self._report(
            max_ticks,
            resident,
            preflight_rejected,
            runtime_rejected,
            completed,
            None,
        )

    @staticmethod
    def _report(
        ticks: int,
        resident: torch.Tensor,
        preflight_rejected: torch.Tensor,
        runtime_rejected: torch.Tensor,
        completed: torch.Tensor,
        divergence: ResidentEpisodeDivergence | None,
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
            divergence=divergence,
        )


def no_op_actions(
    _tick: int,
    battles: Sequence[BattleState],
) -> tuple[tuple[int, int], ...]:
    return tuple((NO_OP_ACTION, NO_OP_ACTION) for _ in battles)


__all__ = [
    "RESIDENT_COMPARISON_SCOPE",
    "ResidentActionProvider",
    "ResidentEpisodeDifferential",
    "ResidentEpisodeDivergence",
    "ResidentEpisodeReport",
    "ResidentEventRecord",
    "no_op_actions",
]
