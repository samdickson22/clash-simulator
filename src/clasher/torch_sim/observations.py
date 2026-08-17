"""Exact batched observation projections from resident tensor battle state."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import (
    ENTITY_FEATURE_SIZE,
    EntityCapacityError,
    StructuredObservationBuilder,
)
from clasher.unit_traits import is_airborne_target

from .state import TensorBattleState


@dataclass(frozen=True)
class TensorStructuredObservation:
    """Both player perspectives for a batch of structured observations."""

    entity_ids: torch.Tensor
    entity_features: torch.Tensor
    entity_mask: torch.Tensor
    hand_ids: torch.Tensor
    global_features: torch.Tensor
    critic_entity_ids: torch.Tensor
    critic_entity_features: torch.Tensor
    critic_entity_mask: torch.Tensor
    critic_card_ids: torch.Tensor
    critic_global_features: torch.Tensor


@dataclass(frozen=True)
class TensorCvObservation:
    """Both player perspectives for a batch of channel-first CV observations."""

    board: torch.Tensor
    hud: torch.Tensor


def _visible_name(entity: object) -> str:
    stats_name = getattr(getattr(entity, "card_stats", None), "name", "")
    if stats_name:
        return str(stats_name)
    for attribute in ("spell_name", "source_name", "spawn_character"):
        value = getattr(entity, attribute, "")
        if value not in {None, "", "Unknown"}:
            return str(value)
    return ""


def _cv_visible_name(entity: object) -> str:
    """Match the CV oracle's intentionally narrower visible identity lookup."""

    stats_name = getattr(getattr(entity, "card_stats", None), "name", "")
    if stats_name:
        return str(stats_name)
    spell_name = getattr(entity, "spell_name", "")
    if spell_name:
        return str(spell_name)
    source_name = getattr(entity, "source_name", "")
    return "" if source_name in {None, "", "Unknown"} else str(source_name)


def _shield_values(entity: object) -> tuple[float, float]:
    fraction = 0.0
    for mechanic in getattr(entity, "mechanics", ()):
        candidate_max = float(getattr(mechanic, "max_shield", 0) or 0)
        if candidate_max <= 0.0:
            continue
        candidate_current = float(getattr(mechanic, "current_shield", 0) or 0)
        fraction = max(fraction, candidate_current / candidate_max)
    # Keep the unbounded fraction: structured observations clip it to one,
    # while the CV oracle preserves values above one.
    return fraction, 1.0


def _effect_values(entity: object) -> tuple[float, float]:
    elapsed = float(getattr(entity, "time_alive", 0) or 0)
    duration = float(getattr(entity, "duration", 0) or 0)
    if duration <= 0.0:
        duration = float(getattr(entity, "explosion_timer", 0) or 0)
    return elapsed, duration


class TensorObservationProjector:
    """Project public and privileged observations without rebuilding Python rows.

    The projector owns immutable or observation-only entity metadata that the
    current tensor simulator does not mutate yet. Authoritative clocks, hands,
    HP, positions, deployment state, and tower state are read directly from
    ``TensorBattleState`` on every projection. As additional resident kernels
    gain support for status and object phases, their matching metadata planes
    can move into the core state without changing the projection API.
    """

    _SHARED_TENSOR_NAMES = frozenset(
        {"structured_card_lookup", "cv_card_lookup", "terrain"}
    )

    def __init__(
        self,
        state: TensorBattleState,
        battles: Sequence[BattleState],
        *,
        structured_builder: StructuredObservationBuilder,
        cv_builder: CvObservationBuilder,
    ) -> None:
        if len(battles) != state.batch_size:
            raise ValueError("battle count does not match tensor batch")
        for index, battle in enumerate(battles):
            if not state.clocks_match(battle, index):
                raise ValueError(f"tensor state is not aligned with battle {index}")
        self.state = state
        self.structured_builder = structured_builder
        self.cv_builder = cv_builder
        self.device = state.device
        self.max_entities = structured_builder.max_entities
        self.canonical_structured = structured_builder.canonical_perspective
        self.canonical_cv = cv_builder.canonical_perspective

        batch = state.batch_size
        slots = state.max_entities

        def zeros(dtype: torch.dtype, *shape: int) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=self.device)

        self.entity_token = zeros(torch.int64, batch, slots)
        self.entity_visible = zeros(torch.bool, batch, 2, slots)
        self.entity_airborne = zeros(torch.bool, batch, slots)
        self.entity_is_building = zeros(torch.bool, batch, slots)
        self.entity_is_crown = zeros(torch.bool, batch, slots)
        self.entity_shield_current = zeros(torch.float64, batch, slots)
        self.entity_shield_max = zeros(torch.float64, batch, slots)
        self.entity_deploy_total = zeros(torch.float64, batch, slots)
        self.entity_stun = zeros(torch.float64, batch, slots)
        self.entity_slow = zeros(torch.float64, batch, slots)
        self.entity_haste = zeros(torch.float64, batch, slots)
        self.entity_special = zeros(torch.bool, batch, slots)
        self.entity_stealth_until_ms = zeros(torch.int64, batch, slots)
        self.entity_hidden_building = zeros(torch.bool, batch, slots)
        self.entity_forced_movement = zeros(torch.bool, batch, slots)
        self.entity_attack_windup = zeros(torch.bool, batch, slots)
        self.entity_charging = zeros(torch.bool, batch, slots)
        self.entity_speed = zeros(torch.float64, batch, slots)
        self.entity_range = zeros(torch.float64, batch, slots)
        self.entity_sight_range = zeros(torch.float64, batch, slots)
        self.entity_collision_radius = zeros(torch.float64, batch, slots)
        self.entity_facing_x = zeros(torch.float64, batch, slots)
        self.entity_facing_y = zeros(torch.float64, batch, slots)
        self.entity_effect_elapsed = zeros(torch.float64, batch, slots)
        self.entity_effect_duration = zeros(torch.float64, batch, slots)
        self.entity_damage = zeros(torch.float64, batch, slots)
        self.entity_identity = zeros(torch.float64, batch, slots)

        self.starting_tower_hp = zeros(torch.float64, batch, 2, 3)
        self.starting_total_tower_hp = zeros(torch.float64, batch, 2)
        self.tiebreaker_time = zeros(torch.float64, batch)
        self.ability_cooldown = zeros(torch.float64, batch, 2)
        self.ability_duration = zeros(torch.float64, batch, 2)

        structured_card_lookup = zeros(torch.int64, len(state.card_names))
        cv_card_lookup = torch.full(
            (len(state.card_names),), -1, dtype=torch.int64, device=self.device
        )
        for card_id, name in enumerate(state.card_names):
            if not name:
                continue
            structured_card_lookup[card_id] = structured_builder.token_id(name)
            cv_index = cv_builder._card_to_idx.get(name)
            if cv_index is None:
                from clasher.card_aliases import resolve_card_name

                cv_index = cv_builder._card_to_idx.get(resolve_card_name(name))
            if cv_index is not None:
                cv_card_lookup[card_id] = cv_index
        self.structured_card_lookup = structured_card_lookup
        self.cv_card_lookup = cv_card_lookup

        for batch_index, battle in enumerate(battles):
            self.tiebreaker_time[batch_index] = float(battle.tiebreaker_time)
            for player_id in range(2):
                starts = battle._starting_tower_hps.get(player_id, {})
                player = battle.players[player_id]
                for tower_index, tower_name in enumerate(("left", "right", "king")):
                    current = float(getattr(player, f"{tower_name}_tower_hp"))
                    self.starting_tower_hp[batch_index, player_id, tower_index] = float(
                        starts.get(tower_name, max(1.0, current))
                    )
                current_total = float(
                    player.left_tower_hp + player.right_tower_hp + player.king_tower_hp
                )
                self.starting_total_tower_hp[batch_index, player_id] = float(
                    battle._starting_total_tower_hp.get(
                        player_id, max(1.0, current_total)
                    )
                )
                found = battle._champion_ability_mechanic(player_id)
                if found is not None:
                    _, mechanic = found
                    ability = mechanic.ability
                    self.ability_cooldown[batch_index, player_id] = (
                        ability.get_cooldown_remaining(battle)
                        / max(1.0, float(ability.cooldown_ms))
                    )
                    self.ability_duration[batch_index, player_id] = (
                        ability.get_duration_remaining(battle)
                        / max(1.0, float(ability.duration_ms))
                    )

            for slot, entity in enumerate(
                sorted(battle.entities.values(), key=lambda value: value.id)
            ):
                name = _visible_name(entity)
                self.entity_token[batch_index, slot] = structured_builder.token_id(name)
                for perspective in range(2):
                    self.entity_visible[batch_index, perspective, slot] = (
                        entity.is_visible_to(perspective)
                    )
                self.entity_airborne[batch_index, slot] = is_airborne_target(entity)
                self.entity_is_building[batch_index, slot] = isinstance(
                    entity, Building
                )
                cv_name = _cv_visible_name(entity)
                self.entity_is_crown[batch_index, slot] = bool(
                    isinstance(entity, Building) and cv_name in {"Tower", "KingTower"}
                )
                shield_current, shield_max = _shield_values(entity)
                self.entity_shield_current[batch_index, slot] = shield_current
                self.entity_shield_max[batch_index, slot] = shield_max
                self.entity_deploy_total[batch_index, slot] = float(
                    getattr(entity, "placement_delay_total", 0) or 0
                )
                self.entity_stun[batch_index, slot] = float(
                    getattr(entity, "stun_timer", 0) or 0
                )
                self.entity_slow[batch_index, slot] = float(
                    getattr(entity, "slow_timer", 0) or 0
                )
                self.entity_haste[batch_index, slot] = float(
                    getattr(entity, "haste_timer", 0) or 0
                )
                self.entity_special[batch_index, slot] = bool(
                    getattr(entity, "_special_move_active", False)
                    or getattr(entity, "is_charging", False)
                    or getattr(entity, "_river_jump_active", False)
                )
                self.entity_stealth_until_ms[batch_index, slot] = int(
                    getattr(entity, "_stealth_until", 0) or 0
                )
                self.entity_hidden_building[batch_index, slot] = bool(
                    getattr(entity, "_hidden_building", False)
                )
                self.entity_forced_movement[batch_index, slot] = bool(
                    getattr(entity, "forced_movement_active", False)
                )
                self.entity_attack_windup[batch_index, slot] = bool(
                    getattr(entity, "_attack_windup_active", False)
                )
                self.entity_charging[batch_index, slot] = bool(
                    getattr(entity, "is_charging", False)
                )
                self.entity_speed[batch_index, slot] = float(
                    getattr(entity, "speed", getattr(entity, "travel_speed", 0)) or 0
                )
                self.entity_range[batch_index, slot] = float(
                    getattr(entity, "range", 0) or 0
                )
                self.entity_sight_range[batch_index, slot] = float(
                    getattr(entity, "sight_range", 0) or 0
                )
                self.entity_collision_radius[batch_index, slot] = float(
                    getattr(getattr(entity, "card_stats", None), "collision_radius", 0)
                    or 0
                )
                facing_x, facing_y = getattr(
                    entity, "native_facing_units", lambda: (0, 0)
                )()
                self.entity_facing_x[batch_index, slot] = float(facing_x)
                self.entity_facing_y[batch_index, slot] = float(facing_y)
                effect_elapsed, effect_duration = _effect_values(entity)
                self.entity_effect_elapsed[batch_index, slot] = effect_elapsed
                self.entity_effect_duration[batch_index, slot] = effect_duration
                self.entity_damage[batch_index, slot] = float(
                    getattr(entity, "damage", 0) or 0
                )
                identity = cv_builder._entity_name_to_value.get(cv_name)
                if identity is None:
                    from clasher.card_aliases import resolve_card_name

                    identity = cv_builder._entity_name_to_value.get(
                        resolve_card_name(cv_name), 0.0
                    )
                self.entity_identity[batch_index, slot] = float(identity)

        self.terrain = torch.stack(
            [
                torch.from_numpy(cv_builder._terrain_planes[player]).to(
                    device=self.device
                )
                for player in range(2)
            ]
        )

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        state: TensorBattleState | None = None,
        structured_builder: StructuredObservationBuilder | None = None,
        cv_builder: CvObservationBuilder | None = None,
        device: str | torch.device = "cpu",
        max_entities: int = 128,
    ) -> TensorObservationProjector:
        structured = structured_builder or StructuredObservationBuilder(
            max_entities=max_entities
        )
        cv = cv_builder or CvObservationBuilder()
        tensor_state = state or TensorBattleState.from_battles(
            battles, device=device, max_entities=max(max_entities, 128)
        )
        return cls(
            tensor_state,
            battles,
            structured_builder=structured,
            cv_builder=cv,
        )

    def fork(
        self,
        rows: Sequence[int] | torch.Tensor,
    ) -> TensorObservationProjector:
        """Fork selected resident rows with isolated observation metadata.

        Repeated rows support oracle fan-out. Card lookup tables, terrain, and
        Python builder configuration are immutable and shared; every batched
        state or metadata plane receives independent tensor storage.
        """

        row_indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        forked_state = self.state.fork(row_indices)
        forked = object.__new__(type(self))
        for name, value in vars(self).items():
            if name == "state":
                setattr(forked, name, forked_state)
                continue
            if (
                isinstance(value, torch.Tensor)
                and name not in self._SHARED_TENSOR_NAMES
            ):
                if value.ndim == 0 or int(value.shape[0]) != self.state.batch_size:
                    raise ValueError(
                        f"observation metadata tensor {name} is not batch-first"
                    )
                setattr(forked, name, value.index_select(0, row_indices))
                continue
            setattr(forked, name, value)
        return forked

    def clone(self) -> TensorObservationProjector:
        """Clone every resident projection row with isolated mutable storage."""

        return self.fork(torch.arange(self.state.batch_size, device=self.device))

    def _perspective_entity_features(self) -> torch.Tensor:
        state = self.state
        batch, slots = state.entity_id.shape
        perspectives = torch.arange(2, device=self.device).view(1, 2, 1)
        owners = state.entity_player[:, None, :]
        own = owners == perspectives
        features = torch.zeros(
            (batch, 2, slots, ENTITY_FEATURE_SIZE),
            dtype=torch.float32,
            device=self.device,
        )

        x = state.entity_x_units.to(torch.float64) / 1000.0
        y = state.entity_y_units.to(torch.float64) / 1000.0
        if self.canonical_structured:
            canonical_x = torch.where(
                perspectives == 1, BOARD_WIDTH - x[:, None], x[:, None]
            )
            canonical_y = torch.where(
                perspectives == 1, BOARD_HEIGHT - y[:, None], y[:, None]
            )
        else:
            canonical_x = x[:, None].expand(-1, 2, -1)
            canonical_y = y[:, None].expand(-1, 2, -1)
        features[..., 0] = (canonical_x / BOARD_WIDTH).clamp(0.0, 1.0).to(torch.float32)
        features[..., 1] = (
            (canonical_y / BOARD_HEIGHT).clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 2] = own
        features[..., 3] = ~own
        kind = state.entity_kind.clamp(0, 4).to(torch.int64)
        features[..., 4:9] = torch.nn.functional.one_hot(kind, 5)[:, None].to(
            torch.float32
        )
        hp_fraction = state.entity_hp / torch.clamp(state.entity_max_hp, min=1.0)
        features[..., 9] = hp_fraction[:, None].clamp(0.0, 1.0).to(torch.float32)
        shield_denominator = torch.where(
            self.entity_shield_max > 0,
            self.entity_shield_max,
            torch.ones_like(self.entity_shield_max),
        )
        shield_fraction = self.entity_shield_current / shield_denominator
        features[..., 10] = shield_fraction[:, None].clamp(0.0, 1.0).to(torch.float32)
        features[..., 11] = self.entity_airborne[:, None]
        features[..., 12] = state.entity_placement_pending[:, None]
        deploy_denominator = torch.where(
            self.entity_deploy_total > 0,
            self.entity_deploy_total,
            torch.ones_like(self.entity_deploy_total),
        )
        deploy_fraction = torch.where(
            self.entity_deploy_total > 0,
            state.entity_deploy_delay / deploy_denominator,
            torch.zeros_like(self.entity_deploy_total),
        )
        features[..., 13] = deploy_fraction[:, None].clamp(0.0, 1.0).to(torch.float32)
        features[..., 14] = (
            (self.entity_stun / 6.0)[:, None].clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 15] = (
            (self.entity_slow / 6.0)[:, None].clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 16] = (
            (self.entity_haste / 6.0)[:, None].clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 17] = self.entity_special[:, None]
        now_ms = torch.round(state.time * 1000.0).to(torch.int64)
        features[..., 18] = (self.entity_stealth_until_ms > now_ms[:, None])[:, None]
        features[..., 19] = self.entity_hidden_building[:, None]
        features[..., 20] = self.entity_forced_movement[:, None]
        features[..., 21] = self.entity_attack_windup[:, None]
        features[..., 22] = self.entity_charging[:, None]
        speed = torch.log1p(self.entity_speed.abs()) / math.log1p(1000.0)
        features[..., 23] = speed[:, None].clamp(0.0, 1.0).to(torch.float32)
        features[..., 24] = (
            (self.entity_range / 12.0)[:, None].clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 25] = (
            (self.entity_sight_range / 12.0)[:, None].clamp(0.0, 1.0).to(torch.float32)
        )
        features[..., 26] = (
            (self.entity_collision_radius / 3.0)[:, None]
            .clamp(0.0, 1.0)
            .to(torch.float32)
        )
        facing_x = self.entity_facing_x[:, None].expand(-1, 2, -1)
        facing_y = self.entity_facing_y[:, None].expand(-1, 2, -1)
        if self.canonical_structured:
            facing_x = torch.where(perspectives == 1, -facing_x, facing_x)
            facing_y = torch.where(perspectives == 1, -facing_y, facing_y)
        magnitude = torch.hypot(facing_x, facing_y).clamp(min=1.0)
        features[..., 27] = (facing_x / magnitude).clamp(-1.0, 1.0).to(torch.float32)
        features[..., 28] = (facing_y / magnitude).clamp(-1.0, 1.0).to(torch.float32)
        effect_denominator = torch.where(
            self.entity_effect_duration > 0,
            self.entity_effect_duration,
            torch.ones_like(self.entity_effect_duration),
        )
        effect = torch.where(
            self.entity_effect_duration > 0,
            self.entity_effect_elapsed / effect_denominator,
            torch.zeros_like(self.entity_effect_duration),
        )
        features[..., 29] = effect[:, None].clamp(0.0, 1.0).to(torch.float32)
        damage = torch.log1p(self.entity_damage.clamp(min=0.0)) / 8.0
        features[..., 30] = damage[:, None].clamp(0.0, 1.0).to(torch.float32)
        features[..., 31] = (self.entity_is_building & state.entity_tower_active)[
            :, None
        ]
        return features

    @staticmethod
    def _gather_rows(values: torch.Tensor, order: torch.Tensor) -> torch.Tensor:
        tail = values.shape[3:]
        expanded = order.reshape(*order.shape, *([1] * len(tail))).expand(
            *order.shape, *tail
        )
        return values.gather(2, expanded)

    def _pack_entities(
        self,
        features: torch.Tensor,
        valid: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        counts = valid.sum(dim=2)
        if bool((counts > self.max_entities).any().item()):
            maximum = int(counts.max().item())
            raise EntityCapacityError(
                f"alive entity count {maximum} exceeds configured "
                f"max_entities={self.max_entities}"
            )

        batch, perspectives, slots = valid.shape
        token = self.entity_token[:, None].expand(-1, 2, -1)
        enemy = self.state.entity_player[:, None] != torch.arange(
            2, device=self.device
        ).view(1, 2, 1)
        kind = self.state.entity_kind[:, None].expand(-1, 2, -1)
        order = (
            torch.arange(slots, device=self.device)
            .view(1, 1, -1)
            .expand(batch, perspectives, -1)
        )
        # Stable least-to-most-significant sorts reproduce the oracle's tuple
        # key while preserving entity creation order for rounded-coordinate ties.
        for key in (
            torch.round(features[..., 0] * 1e5).to(torch.int64),
            torch.round(features[..., 1] * 1e5).to(torch.int64),
            token,
            enemy.to(torch.int64),
            kind.to(torch.int64),
            (~valid).to(torch.int64),
        ):
            sorted_key = key.gather(2, order)
            local = torch.argsort(sorted_key, dim=2, stable=True)
            order = order.gather(2, local)

        order = order[..., : self.max_entities]
        packed_features = self._gather_rows(features, order)
        packed_ids = token.gather(2, order)
        packed_mask = valid.gather(2, order)
        packed_ids = torch.where(packed_mask, packed_ids, torch.zeros_like(packed_ids))
        packed_features = torch.where(
            packed_mask[..., None], packed_features, torch.zeros_like(packed_features)
        )
        return packed_ids, packed_features, packed_mask

    def _card_slots(self) -> torch.Tensor:
        hand = self.structured_card_lookup[self.state.hand]
        queue_first = self.structured_card_lookup[self.state.cycle_queue[:, :, 0]]
        queue_first = torch.where(
            self.state.cycle_queue_length > 0,
            queue_first,
            torch.zeros_like(queue_first),
        )
        return torch.cat((hand[:, :, :NUM_HAND_SLOTS], queue_first[..., None]), dim=2)

    def _crowns(self) -> torch.Tensor:
        king_dead = self.state.tower_hp[:, :, 2] <= 0
        side_lost = (self.state.tower_hp[:, :, :2] <= 0).sum(dim=2)
        lost = torch.where(king_dead, torch.full_like(side_lost, 3), side_lost)
        return torch.stack((lost[:, 1], lost[:, 0]), dim=1)

    def _structured_globals(self) -> tuple[torch.Tensor, torch.Tensor]:
        state = self.state
        player = torch.arange(2, device=self.device).view(1, 2)
        enemy = 1 - player
        progress = (state.time / torch.clamp(self.tiebreaker_time, min=1.0)).clamp(
            0.0, 1.0
        )
        own_elixir = state.elixir.gather(1, player.expand(state.batch_size, -1))
        own_max = state.max_elixir.gather(1, player.expand(state.batch_size, -1))
        crowns = self._crowns()
        own_crowns = crowns.gather(1, player.expand(state.batch_size, -1))
        enemy_crowns = crowns.gather(1, enemy.expand(state.batch_size, -1))
        own_hp = state.tower_hp.gather(
            1, player[..., None].expand(state.batch_size, 2, 3)
        )
        enemy_hp = state.tower_hp.gather(
            1, enemy[..., None].expand(state.batch_size, 2, 3)
        )
        own_start = self.starting_tower_hp.gather(
            1, player[..., None].expand(state.batch_size, 2, 3)
        )
        enemy_start = self.starting_tower_hp.gather(
            1, enemy[..., None].expand(state.batch_size, 2, 3)
        )
        tower_fractions = torch.cat(
            (
                own_hp / torch.clamp(own_start, min=1.0),
                enemy_hp / torch.clamp(enemy_start, min=1.0),
            ),
            dim=2,
        ).clamp(0.0, 1.0)
        own_cooldown = state.refill_cooldown_ms.gather(
            1, player.expand(state.batch_size, -1)
        )
        enemy_elixir = state.elixir.gather(1, enemy.expand(state.batch_size, -1))
        enemy_max = state.max_elixir.gather(1, enemy.expand(state.batch_size, -1))
        enemy_cooldown = state.refill_cooldown_ms.gather(
            1, enemy.expand(state.batch_size, -1)
        )
        enemy_king_alive = enemy_hp[..., 2] > 0

        actor = torch.cat(
            (
                progress[:, None].expand(-1, 2)[..., None],
                (1.0 - progress)[:, None].expand(-1, 2)[..., None],
                state.double_elixir[:, None, None].expand(-1, 2, -1),
                state.triple_elixir[:, None, None].expand(-1, 2, -1),
                state.overtime[:, None, None].expand(-1, 2, -1),
                (own_elixir / torch.clamp(own_max, min=1.0)).clamp(0.0, 1.0)[..., None],
                (own_crowns / 3.0)[..., None],
                (enemy_crowns / 3.0)[..., None],
                tower_fractions,
                self.ability_cooldown.clamp(0.0, 1.0)[..., None],
                self.ability_duration.clamp(0.0, 1.0)[..., None],
                (own_cooldown / 1000.0).clamp(0.0, 1.0)[..., None],
                enemy_king_alive[..., None],
            ),
            dim=2,
        ).to(torch.float32)
        critic_tail = torch.stack(
            (
                (enemy_elixir / torch.clamp(enemy_max, min=1.0)).clamp(0.0, 1.0),
                (enemy_cooldown / 1000.0).clamp(0.0, 1.0),
            ),
            dim=2,
        ).to(torch.float32)
        return actor, torch.cat((actor, critic_tail), dim=2)

    def project_structured(self) -> TensorStructuredObservation:
        features = self._perspective_entity_features()
        active = self.state.entity_active[:, None].expand(-1, 2, -1)
        actor_ids, actor_features, actor_mask = self._pack_entities(
            features, active & self.entity_visible
        )
        critic_ids, critic_features, critic_mask = self._pack_entities(features, active)
        cards = self._card_slots()
        player = torch.arange(2, device=self.device).view(1, 2)
        enemy_cards = cards.gather(
            1, (1 - player)[..., None].expand(self.state.batch_size, 2, cards.shape[2])
        )
        actor_globals, critic_globals = self._structured_globals()
        return TensorStructuredObservation(
            entity_ids=actor_ids,
            entity_features=actor_features,
            entity_mask=actor_mask,
            hand_ids=cards,
            global_features=actor_globals,
            critic_entity_ids=critic_ids,
            critic_entity_features=critic_features,
            critic_entity_mask=critic_mask,
            critic_card_ids=torch.cat((cards, enemy_cards), dim=2),
            critic_global_features=critic_globals,
        )

    def _cv_tiles(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        state = self.state
        x_units = state.entity_x_units.to(torch.int64)
        y_units = state.entity_y_units.to(torch.int64)
        in_bounds = (
            (x_units >= 0)
            & (x_units < BOARD_WIDTH * 1000)
            & (y_units >= 0)
            & (y_units < BOARD_HEIGHT * 1000)
        )
        world_x = torch.div(x_units, 1000, rounding_mode="floor")
        world_y = torch.div(y_units, 1000, rounding_mode="floor")
        x = world_x[:, None].expand(-1, 2, -1).clone()
        y = world_y[:, None].expand(-1, 2, -1).clone()
        if self.canonical_cv:
            # Rotate the continuous native point before truncation, matching
            # the oracle's integer-boundary behavior exactly.
            rotated_x = torch.div(
                BOARD_WIDTH * 1000 - x_units, 1000, rounding_mode="floor"
            ).clamp(max=BOARD_WIDTH - 1)
            rotated_y = torch.div(
                BOARD_HEIGHT * 1000 - y_units, 1000, rounding_mode="floor"
            ).clamp(max=BOARD_HEIGHT - 1)
            x[:, 1] = rotated_x
            y[:, 1] = rotated_y
        return x, y, in_bounds[:, None].expand(-1, 2, -1)

    @staticmethod
    def _scatter_add_plane(
        board: torch.Tensor,
        channel: torch.Tensor,
        tile: torch.Tensor,
        values: torch.Tensor,
        valid: torch.Tensor,
    ) -> None:
        width = BOARD_HEIGHT * BOARD_WIDTH
        index = channel * width + tile
        target = board.view(*board.shape[:2], -1)
        target.scatter_add_(
            2, index, torch.where(valid, values, torch.zeros_like(values))
        )

    @staticmethod
    def _scatter_max_plane(
        board: torch.Tensor,
        channel: torch.Tensor,
        tile: torch.Tensor,
        values: torch.Tensor,
        valid: torch.Tensor,
    ) -> None:
        width = BOARD_HEIGHT * BOARD_WIDTH
        index = channel * width + tile
        target = board.view(*board.shape[:2], -1)
        target.scatter_reduce_(
            2,
            index,
            torch.where(valid, values, torch.zeros_like(values)),
            reduce="amax",
            include_self=True,
        )

    def _cv_hud(self) -> torch.Tensor:
        state = self.state
        player = torch.arange(2, device=self.device).view(1, 2)
        enemy = 1 - player
        progress = (state.time / self.tiebreaker_time).clamp(max=1.0)
        crowns = self._crowns()
        own_hp = state.tower_hp
        enemy_hp = state.tower_hp.gather(
            1, enemy[..., None].expand(state.batch_size, 2, 3)
        )
        scalars = torch.stack(
            (
                progress[:, None].expand(-1, 2),
                state.double_elixir[:, None].expand(-1, 2),
                state.triple_elixir[:, None].expand(-1, 2),
                state.overtime[:, None].expand(-1, 2),
                state.elixir / torch.clamp(state.max_elixir, min=1.0),
                crowns / 3.0,
                crowns.gather(1, enemy.expand(state.batch_size, -1)) / 3.0,
                own_hp.sum(dim=2) / torch.clamp(self.starting_total_tower_hp, min=1.0),
                enemy_hp.sum(dim=2)
                / torch.clamp(
                    self.starting_total_tower_hp.gather(
                        1, enemy.expand(state.batch_size, -1)
                    ),
                    min=1.0,
                ),
                progress[:, None].expand(-1, 2),
                self.ability_cooldown.clamp(0.0, 1.0),
                self.ability_duration.clamp(0.0, 1.0),
            ),
            dim=2,
        ).to(torch.float32)

        vocab = len(self.cv_builder.card_vocab)
        if vocab == 0:
            return scalars
        card_values = torch.cat(
            (
                state.hand[:, :, :NUM_HAND_SLOTS],
                torch.where(
                    state.cycle_queue_length[..., None] > 0,
                    state.cycle_queue[:, :, :1],
                    torch.zeros_like(state.cycle_queue[:, :, :1]),
                ),
            ),
            dim=2,
        )
        card_indices = self.cv_card_lookup[card_values]
        one_hot = torch.nn.functional.one_hot(
            card_indices.clamp(min=0), num_classes=vocab
        ).to(torch.float32)
        one_hot *= (card_indices >= 0)[..., None]
        return torch.cat((scalars, one_hot.flatten(2)), dim=2)

    def project_cv(self) -> TensorCvObservation:
        state = self.state
        batch, slots = state.entity_id.shape
        board = torch.zeros(
            (batch, 2, self.cv_builder.BOARD_CHANNELS, BOARD_HEIGHT, BOARD_WIDTH),
            dtype=torch.float32,
            device=self.device,
        )
        board[:, :, :3] = self.terrain[None]
        perspectives = torch.arange(2, device=self.device).view(1, 2, 1)
        own = state.entity_player[:, None] == perspectives
        x, y, in_bounds = self._cv_tiles()
        tile = (y * BOARD_WIDTH + x).clamp(0, BOARD_HEIGHT * BOARD_WIDTH - 1)
        valid = state.entity_active[:, None] & self.entity_visible & in_bounds
        is_building = self.entity_is_building[:, None]
        is_crown = self.entity_is_crown[:, None]
        is_troop = state.entity_kind[:, None] == 0
        airborne = self.entity_airborne[:, None]
        channel = torch.where(
            is_building & is_crown,
            torch.where(own, 3, 4),
            torch.where(
                is_building,
                torch.where(own, 5, 6),
                torch.where(
                    is_troop & ~airborne,
                    torch.where(own, 7, 8),
                    torch.where(
                        is_troop & airborne,
                        torch.where(own, 9, 10),
                        torch.where(own, 13, 14),
                    ),
                ),
            ),
        ).to(torch.int64)
        ones = torch.ones((batch, 2, slots), dtype=torch.float32, device=self.device)
        self._scatter_add_plane(board, channel, tile, ones, valid)
        board[:, :, 3:15].clamp_(max=1.0)

        hp_channel = torch.where(own, 11, 12).to(torch.int64)
        hp_fraction = (
            (state.entity_hp / torch.clamp(state.entity_max_hp, min=1.0))
            .to(torch.float32)[:, None]
            .expand(-1, 2, -1)
        )
        self._scatter_add_plane(board, hp_channel, tile, hp_fraction, valid)
        board[:, :, 11:13].clamp_(max=3.0)

        def scatter_pair(
            own_channel: int, enemy_channel: int, values: torch.Tensor
        ) -> None:
            pair_channel = torch.where(own, own_channel, enemy_channel).to(torch.int64)
            expanded = values[:, None].expand(-1, 2, -1).to(torch.float32)
            self._scatter_max_plane(board, pair_channel, tile, expanded, valid)

        scatter_pair(15, 16, self.entity_identity)
        shield_denominator = torch.where(
            self.entity_shield_max > 0,
            self.entity_shield_max,
            torch.ones_like(self.entity_shield_max),
        )
        shield = self.entity_shield_current / shield_denominator
        scatter_pair(17, 18, shield)
        scatter_pair(19, 20, self.entity_hidden_building & self.entity_is_building)
        deploy_denominator = torch.where(
            self.entity_deploy_total > 0,
            self.entity_deploy_total,
            torch.ones_like(self.entity_deploy_total),
        )
        deploy = torch.where(
            self.entity_deploy_total > 0,
            state.entity_deploy_delay / deploy_denominator,
            torch.ones_like(self.entity_deploy_total),
        ).clamp(max=1.0)
        scatter_pair(21, 22, torch.where(state.entity_placement_pending, deploy, 0.0))
        status_seconds = self.cv_builder.MAX_VISIBLE_STATUS_SECONDS
        scatter_pair(23, 24, (self.entity_stun / status_seconds).clamp(max=1.0))
        scatter_pair(25, 26, (self.entity_slow / status_seconds).clamp(max=1.0))
        scatter_pair(27, 28, (self.entity_haste / status_seconds).clamp(max=1.0))
        scatter_pair(29, 30, self.entity_special)
        now_ms = torch.round(state.time * 1000.0).to(torch.int64)
        scatter_pair(31, 32, self.entity_stealth_until_ms > now_ms[:, None])
        return TensorCvObservation(board=board, hud=self._cv_hud())


__all__ = [
    "TensorCvObservation",
    "TensorObservationProjector",
    "TensorStructuredObservation",
]
