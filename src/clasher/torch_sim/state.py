"""Dense, batched tensor representation of mutable battle state."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from typing import Any

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.kinematics import tiles_to_logic_units

WINNER_IN_PROGRESS = -2
WINNER_DRAW = -1
TOWER_SLOTS = {"left": 0, "right": 1, "king": 2}


@dataclass
class TensorBattleState:
    """Structure-of-arrays state retained across batched simulation ticks.

    Integer native coordinates and stable card/entity IDs avoid lossy float
    geometry and Python identity dependence.  Float64 is used for the oracle's
    externally visible clocks and elixir until those values are migrated to a
    proven fixed-point representation.
    """

    device: torch.device
    card_names: tuple[str, ...]
    card_to_id: dict[str, int]
    time: torch.Tensor
    tick: torch.Tensor
    active: torch.Tensor
    double_elixir: torch.Tensor
    triple_elixir: torch.Tensor
    overtime: torch.Tensor
    sudden_death: torch.Tensor
    game_over: torch.Tensor
    winner: torch.Tensor
    sudden_death_crowns: torch.Tensor
    elixir: torch.Tensor
    max_elixir: torch.Tensor
    refill_cooldown_ms: torch.Tensor
    hand: torch.Tensor
    deck: torch.Tensor
    cycle_queue: torch.Tensor
    cycle_queue_length: torch.Tensor
    tower_hp: torch.Tensor
    entity_active: torch.Tensor
    entity_id: torch.Tensor
    entity_kind: torch.Tensor
    entity_player: torch.Tensor
    entity_card: torch.Tensor
    entity_x_units: torch.Tensor
    entity_y_units: torch.Tensor
    entity_hp: torch.Tensor
    entity_hp_integer_kind: torch.Tensor
    entity_max_hp: torch.Tensor
    entity_last_attack_time: torch.Tensor
    entity_deploy_delay: torch.Tensor
    entity_placement_pending: torch.Tensor
    entity_spawn_hook_pending: torch.Tensor
    entity_spawn_hook_fired: torch.Tensor
    entity_lifetime_ms: torch.Tensor
    entity_lifetime_decay_rate: torch.Tensor
    entity_lifetime_elapsed: torch.Tensor
    entity_lifetime_decay_work: torch.Tensor
    entity_lifetime_tick_carry_ms: torch.Tensor
    entity_tower_slot: torch.Tensor
    entity_tower_active: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.tick.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.entity_id.shape[1])

    def fork(
        self,
        batch_indices: Sequence[int] | torch.Tensor | None = None,
    ) -> TensorBattleState:
        """Return an independent tensor state containing selected batch rows.

        Every mutable tensor gets its own storage.  Repeated indices are
        allowed, which lets tree-search callers fan one exact root state out
        into multiple branches without re-encoding Python battle objects.
        """

        if batch_indices is None:
            indices = torch.arange(self.batch_size, device=self.device)
        else:
            indices = torch.as_tensor(
                batch_indices,
                dtype=torch.int64,
                device=self.device,
            )
        if indices.ndim != 1 or indices.numel() == 0:
            raise ValueError("batch_indices must be a non-empty 1D sequence")
        if bool(((indices < 0) | (indices >= self.batch_size)).any().item()):
            raise IndexError("tensor battle fork index is out of range")

        values: dict[str, Any] = {}
        for state_field in fields(self):
            value = getattr(self, state_field.name)
            if isinstance(value, torch.Tensor):
                values[state_field.name] = value.index_select(0, indices).clone()
            elif isinstance(value, dict):
                values[state_field.name] = value.copy()
            else:
                values[state_field.name] = value
        return type(self)(**values)

    def clone(self) -> TensorBattleState:
        """Return an independent exact copy of the full tensor batch."""

        return self.fork()

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        device: str | torch.device = "cpu",
        max_entities: int = 128,
        max_cards: int = 16,
    ) -> TensorBattleState:
        if not battles:
            raise ValueError("at least one battle is required")
        if max_entities < max(len(battle.entities) for battle in battles):
            raise ValueError("max_entities is smaller than the live entity count")
        if max_cards < max(
            max(len(player.deck), len(player.cycle_queue))
            for battle in battles
            for player in battle.players
        ):
            raise ValueError("max_cards is smaller than a deck or cycle queue")

        torch_device = torch.device(device)
        names = sorted(
            {
                str(name)
                for battle in battles
                for player in battle.players
                for name in (*player.deck, *player.hand, *player.cycle_queue)
                if name is not None
            }
            | {
                str(getattr(entity.card_stats, "name", ""))
                for battle in battles
                for entity in battle.entities.values()
            }
        )
        card_names = ("", *names)
        card_to_id = {name: index for index, name in enumerate(card_names)}
        batch = len(battles)

        def zeros(*shape: int, dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        state = cls(
            device=torch_device,
            card_names=card_names,
            card_to_id=card_to_id,
            time=zeros(batch, dtype=torch.float64),
            tick=zeros(batch, dtype=torch.int64),
            active=torch.ones(batch, dtype=torch.bool, device=torch_device),
            double_elixir=zeros(batch, dtype=torch.bool),
            triple_elixir=zeros(batch, dtype=torch.bool),
            overtime=zeros(batch, dtype=torch.bool),
            sudden_death=zeros(batch, dtype=torch.bool),
            game_over=zeros(batch, dtype=torch.bool),
            winner=torch.full(
                (batch,), WINNER_IN_PROGRESS, dtype=torch.int8, device=torch_device
            ),
            sudden_death_crowns=zeros(batch, 2, dtype=torch.int8),
            elixir=zeros(batch, 2, dtype=torch.float64),
            max_elixir=zeros(batch, 2, dtype=torch.float64),
            refill_cooldown_ms=zeros(batch, 2, dtype=torch.int32),
            hand=zeros(batch, 2, 4, dtype=torch.int64),
            deck=zeros(batch, 2, max_cards, dtype=torch.int64),
            cycle_queue=zeros(batch, 2, max_cards, dtype=torch.int64),
            cycle_queue_length=zeros(batch, 2, dtype=torch.int16),
            tower_hp=zeros(batch, 2, 3, dtype=torch.float64),
            entity_active=zeros(batch, max_entities, dtype=torch.bool),
            entity_id=zeros(batch, max_entities, dtype=torch.int64),
            entity_kind=zeros(batch, max_entities, dtype=torch.int8),
            entity_player=zeros(batch, max_entities, dtype=torch.int8),
            entity_card=zeros(batch, max_entities, dtype=torch.int64),
            entity_x_units=zeros(batch, max_entities, dtype=torch.int32),
            entity_y_units=zeros(batch, max_entities, dtype=torch.int32),
            entity_hp=zeros(batch, max_entities, dtype=torch.float64),
            entity_hp_integer_kind=zeros(batch, max_entities, dtype=torch.bool),
            entity_max_hp=zeros(batch, max_entities, dtype=torch.float64),
            entity_last_attack_time=zeros(batch, max_entities, dtype=torch.float64),
            entity_deploy_delay=zeros(batch, max_entities, dtype=torch.float64),
            entity_placement_pending=zeros(batch, max_entities, dtype=torch.bool),
            entity_spawn_hook_pending=zeros(batch, max_entities, dtype=torch.bool),
            entity_spawn_hook_fired=zeros(batch, max_entities, dtype=torch.bool),
            entity_lifetime_ms=zeros(batch, max_entities, dtype=torch.int64),
            entity_lifetime_decay_rate=zeros(batch, max_entities, dtype=torch.int64),
            entity_lifetime_elapsed=zeros(batch, max_entities, dtype=torch.float64),
            entity_lifetime_decay_work=zeros(batch, max_entities, dtype=torch.int64),
            entity_lifetime_tick_carry_ms=zeros(
                batch, max_entities, dtype=torch.float64
            ),
            entity_tower_slot=torch.full(
                (batch, max_entities), -1, dtype=torch.int8, device=torch_device
            ),
            entity_tower_active=zeros(batch, max_entities, dtype=torch.bool),
        )
        state.load_battles(battles)
        return state

    def _card_id(self, name: str | None) -> int:
        if name is None:
            return 0
        try:
            return self.card_to_id[str(name)]
        except KeyError as exc:
            raise ValueError(f"card {name!r} is absent from tensor catalog") from exc

    def load_battles(self, battles: Sequence[BattleState]) -> None:
        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match tensor batch")
        self.entity_active.zero_()
        self.entity_id.zero_()
        self.entity_kind.zero_()
        self.entity_player.zero_()
        self.entity_card.zero_()
        self.entity_x_units.zero_()
        self.entity_y_units.zero_()
        self.entity_hp.zero_()
        self.entity_hp_integer_kind.zero_()
        self.entity_max_hp.zero_()
        self.entity_last_attack_time.zero_()
        self.entity_deploy_delay.zero_()
        self.entity_placement_pending.zero_()
        self.entity_spawn_hook_pending.zero_()
        self.entity_spawn_hook_fired.zero_()
        self.entity_lifetime_ms.zero_()
        self.entity_lifetime_decay_rate.zero_()
        self.entity_lifetime_elapsed.zero_()
        self.entity_lifetime_decay_work.zero_()
        self.entity_lifetime_tick_carry_ms.zero_()
        self.entity_tower_slot.fill_(-1)
        self.entity_tower_active.zero_()
        self.hand.zero_()
        self.deck.zero_()
        self.cycle_queue.zero_()
        self.cycle_queue_length.zero_()

        for batch_index, battle in enumerate(battles):
            self.time[batch_index] = battle.time
            self.tick[batch_index] = battle.tick
            self.active[batch_index] = not battle.game_over
            self.double_elixir[batch_index] = battle.double_elixir
            self.triple_elixir[batch_index] = battle.triple_elixir
            self.overtime[batch_index] = battle.overtime
            self.sudden_death[batch_index] = battle.sudden_death
            self.game_over[batch_index] = battle.game_over
            self.winner[batch_index] = (
                WINNER_IN_PROGRESS
                if not battle.game_over
                else WINNER_DRAW
                if battle.winner is None
                else battle.winner
            )
            self.sudden_death_crowns[batch_index] = torch.tensor(
                battle._sudden_death_crowns,
                dtype=torch.int8,
                device=self.device,
            )
            for player_index, player in enumerate(battle.players):
                self.elixir[batch_index, player_index] = player.elixir
                self.max_elixir[batch_index, player_index] = player.max_elixir
                self.refill_cooldown_ms[batch_index, player_index] = (
                    player.next_card_refill_cooldown_ms
                )
                for slot, name in enumerate(player.hand):
                    self.hand[batch_index, player_index, slot] = self._card_id(name)
                for slot, name in enumerate(player.deck):
                    self.deck[batch_index, player_index, slot] = self._card_id(name)
                queue = tuple(player.cycle_queue)
                self.cycle_queue_length[batch_index, player_index] = len(queue)
                for slot, name in enumerate(queue):
                    self.cycle_queue[batch_index, player_index, slot] = self._card_id(
                        name
                    )
                self.tower_hp[batch_index, player_index] = torch.tensor(
                    (
                        player.left_tower_hp,
                        player.right_tower_hp,
                        player.king_tower_hp,
                    ),
                    dtype=torch.float64,
                    device=self.device,
                )
            for entity_index, entity in enumerate(
                sorted(battle.entities.values(), key=lambda value: value.id)
            ):
                self.entity_active[batch_index, entity_index] = entity.is_alive
                self.entity_id[batch_index, entity_index] = entity.id
                self.entity_kind[batch_index, entity_index] = entity.entity_kind
                self.entity_player[batch_index, entity_index] = entity.player_id
                self.entity_card[batch_index, entity_index] = self._card_id(
                    getattr(entity.card_stats, "name", None)
                )
                self.entity_x_units[batch_index, entity_index] = tiles_to_logic_units(
                    entity.position.x
                )
                self.entity_y_units[batch_index, entity_index] = tiles_to_logic_units(
                    entity.position.y
                )
                self.entity_hp[batch_index, entity_index] = entity.hitpoints
                self.entity_hp_integer_kind[batch_index, entity_index] = (
                    type(entity.hitpoints) is int
                )
                self.entity_max_hp[batch_index, entity_index] = entity.max_hitpoints
                self.entity_last_attack_time[batch_index, entity_index] = (
                    entity.last_attack_time
                )
                self.entity_deploy_delay[batch_index, entity_index] = (
                    entity.deploy_delay_remaining
                )
                self.entity_placement_pending[batch_index, entity_index] = (
                    entity.placement_pending
                )
                self.entity_spawn_hook_pending[batch_index, entity_index] = bool(
                    getattr(entity, "_spawn_hook_pending", False)
                )
                self.entity_spawn_hook_fired[batch_index, entity_index] = bool(
                    getattr(entity, "_spawn_hook_fired", False)
                )
                lifetime_ms = getattr(entity.card_stats, "lifetime_ms", None)
                if entity.entity_kind == 1 and lifetime_ms and lifetime_ms > 0:
                    self.entity_lifetime_ms[batch_index, entity_index] = int(
                        lifetime_ms
                    )
                    self.entity_lifetime_decay_rate[batch_index, entity_index] = (
                        5000
                        * round(entity.max_hitpoints)
                        // int(lifetime_ms)
                    )
                    self.entity_lifetime_elapsed[batch_index, entity_index] = float(
                        getattr(entity, "lifetime_elapsed", 0.0)
                    )
                    self.entity_lifetime_decay_work[batch_index, entity_index] = int(
                        getattr(entity, "lifetime_decay_work", 0)
                    )
                    self.entity_lifetime_tick_carry_ms[
                        batch_index, entity_index
                    ] = float(getattr(entity, "lifetime_tick_carry_ms", 0.0))
                tower_slot = getattr(entity, "_crown_tower_slot", None)
                self.entity_tower_slot[batch_index, entity_index] = (
                    TOWER_SLOTS.get(tower_slot, -1)
                    if isinstance(tower_slot, str)
                    else -1
                )
                self.entity_tower_active[batch_index, entity_index] = bool(
                    getattr(entity, "_tower_active", False)
                )

    def clocks_match(self, battle: BattleState, batch_index: int = 0) -> bool:
        return (
            int(self.tick[batch_index].item()) == battle.tick
            and float(self.time[batch_index].item()) == battle.time
            and tuple(
                int(value)
                for value in self.entity_id[batch_index][
                    self.entity_id[batch_index] != 0
                ].tolist()
            )
            == tuple(sorted(battle.entities))
        )

    def sync_to_battles(self, battles: Sequence[BattleState]) -> None:
        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match tensor batch")
        for batch_index, battle in enumerate(battles):
            battle.time = float(self.time[batch_index].item())
            battle.tick = int(self.tick[batch_index].item())
            battle.double_elixir = bool(self.double_elixir[batch_index].item())
            battle.triple_elixir = bool(self.triple_elixir[batch_index].item())
            battle.overtime = bool(self.overtime[batch_index].item())
            battle.sudden_death = bool(self.sudden_death[batch_index].item())
            battle.game_over = bool(self.game_over[batch_index].item())
            winner = int(self.winner[batch_index].item())
            battle.winner = None if winner < 0 else winner
            battle._sudden_death_crowns = (
                int(self.sudden_death_crowns[batch_index, 0].item()),
                int(self.sudden_death_crowns[batch_index, 1].item()),
            )
            for player_index, player in enumerate(battle.players):
                player.elixir = float(self.elixir[batch_index, player_index].item())
                player.max_elixir = float(
                    self.max_elixir[batch_index, player_index].item()
                )
                player.next_card_refill_cooldown_ms = int(
                    self.refill_cooldown_ms[batch_index, player_index].item()
                )
                player.hand = [
                    None if value == 0 else self.card_names[value]
                    for value in self.hand[batch_index, player_index].tolist()
                ]
                queue_length = int(
                    self.cycle_queue_length[batch_index, player_index].item()
                )
                player.cycle_queue = deque(
                    self.card_names[value]
                    for value in self.cycle_queue[
                        batch_index, player_index, :queue_length
                    ].tolist()
                )
                # The idle vertical slice cannot mutate tower HP.  Preserve
                # the oracle's original scalar kinds (currently integer for
                # untouched towers) instead of round-tripping through float64.
            entities_by_id = battle.entities
            for entity_index in range(self.max_entities):
                entity_id = int(self.entity_id[batch_index, entity_index].item())
                if entity_id == 0:
                    continue
                entity = entities_by_id[entity_id]
                entity.last_attack_time = float(
                    self.entity_last_attack_time[batch_index, entity_index].item()
                )
                entity.deploy_delay_remaining = float(
                    self.entity_deploy_delay[batch_index, entity_index].item()
                )
                entity.placement_pending = bool(
                    self.entity_placement_pending[
                        batch_index, entity_index
                    ].item()
                )
                entity._spawn_hook_pending = bool(
                    self.entity_spawn_hook_pending[
                        batch_index, entity_index
                    ].item()
                )
                entity._spawn_hook_fired = bool(
                    self.entity_spawn_hook_fired[
                        batch_index, entity_index
                    ].item()
                )
                if (
                    isinstance(entity, Building)
                    and int(
                        self.entity_lifetime_ms[
                            batch_index, entity_index
                        ].item()
                    )
                    > 0
                ):
                    hp = float(self.entity_hp[batch_index, entity_index].item())
                    entity.hitpoints = (
                        int(hp)
                        if bool(
                            self.entity_hp_integer_kind[
                                batch_index, entity_index
                            ].item()
                        )
                        else hp
                    )
                    entity.lifetime_elapsed = float(
                        self.entity_lifetime_elapsed[
                            batch_index, entity_index
                        ].item()
                    )
                    entity.lifetime_decay_work = int(
                        self.entity_lifetime_decay_work[
                            batch_index, entity_index
                        ].item()
                    )
                    entity.lifetime_tick_carry_ms = float(
                        self.entity_lifetime_tick_carry_ms[
                            batch_index, entity_index
                        ].item()
                    )


@dataclass(frozen=True)
class TensorBattleFork:
    """Tensor root plus an exact scalar guard for safe search-tree forking.

    ``TensorBattleState`` intentionally contains only the fields implemented
    by tensor kernels.  The scalar snapshots prevent a caller from binding a
    tensor root to a behaviorally different ``BattleState`` merely because its
    clock and entity IDs happen to match.
    """

    _state: TensorBattleState = field(repr=False)
    scalar_snapshots: tuple[dict[str, Any], ...]

    @property
    def state(self) -> TensorBattleState:
        """Return an independent, caller-owned copy of the tensor root."""

        return self._state.clone()

    def _materialize_state(self) -> TensorBattleState:
        """Return mutable storage for an executor without exposing the root."""

        return self._state.clone()

    @classmethod
    def capture(
        cls,
        battles: Sequence[BattleState],
        *,
        device: str | torch.device = "cpu",
        max_entities: int | None = None,
        max_cards: int | None = None,
    ) -> TensorBattleFork:
        if not battles:
            raise ValueError("at least one battle is required")
        from .diagnostics import battle_snapshot

        entity_capacity = max(
            128 if max_entities is None else int(max_entities),
            max(len(battle.entities) for battle in battles),
        )
        card_capacity = max(
            16 if max_cards is None else int(max_cards),
            max(
                max(len(player.deck), len(player.cycle_queue))
                for battle in battles
                for player in battle.players
            ),
        )
        return cls(
            _state=TensorBattleState.from_battles(
                battles,
                device=device,
                max_entities=entity_capacity,
                max_cards=card_capacity,
            ),
            scalar_snapshots=tuple(battle_snapshot(battle) for battle in battles),
        )

    @property
    def batch_size(self) -> int:
        return self._state.batch_size

    def fork(
        self,
        batch_indices: Sequence[int] | torch.Tensor | None = None,
    ) -> TensorBattleFork:
        if batch_indices is None:
            selected = tuple(range(self.batch_size))
        elif isinstance(batch_indices, torch.Tensor):
            selected = tuple(int(value) for value in batch_indices.cpu().tolist())
        else:
            selected = tuple(int(value) for value in batch_indices)
        forked_state = self._state.fork(selected)
        return type(self)(
            _state=forked_state,
            scalar_snapshots=tuple(self.scalar_snapshots[index] for index in selected),
        )

    def matches_battles(self, battles: Sequence[BattleState]) -> bool:
        if len(battles) != self.batch_size:
            return False
        from .diagnostics import battle_snapshot, first_divergence

        return all(
            first_divergence(expected, battle_snapshot(battle)) is None
            for expected, battle in zip(self.scalar_snapshots, battles)
        )
