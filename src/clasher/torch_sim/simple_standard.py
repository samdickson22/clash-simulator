"""Authoritative setup boundary for the practical tensor Gym.

This module turns a public card vocabulary into the expanded, data-driven
catalogs consumed by :class:`SimpleGymRuntime`.  All name resolution happens
once during setup.  The runtime remains numeric and fail closed: a deck is
accepted only when every public root is compiled and marked training-safe by
the generalized fast-card and spawn-blueprint compilers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch

from clasher.arena import TileGrid
from clasher.balance import tournament_tower_stat
from clasher.data import CardDataLoader, load_princess_tower_character_data
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.kinematics import (
    LOGIC_TICK_MILLISECONDS,
    LOGIC_TICK_SECONDS,
    tiles_to_logic_units,
)
from clasher.unit_traits import is_knockback_immune

from .catalog import TensorCardCatalog
from .simple_abilities import FastAbilityCatalog
from .simple_catalog import FAST_CARD_EFFECT_PROJECTILE
from .simple_outcomes import FastMatchRules, FastTowerSpec
from .simple_policy_mechanics import FastPolicyMechanicCatalog
from .simple_runtime import SimpleGymRuntime
from .simple_spawn_blueprints import FastSpawnBlueprintCatalog, FastSpawnTrigger
from .simple_travel import FastTravelCatalog
from .simple_triggered_impacts import FastTriggeredImpactCatalog

# The current-client match phases expressed in the one authoritative 50 ms
# logic clock.  Keeping the source durations beside the conversion makes the
# 2400/3600/4800/6000 thresholds auditable without scattering tick literals.
STANDARD_DOUBLE_ELIXIR_TICK = 120_000 // LOGIC_TICK_MILLISECONDS
STANDARD_REGULATION_TICK = 180_000 // LOGIC_TICK_MILLISECONDS
STANDARD_TRIPLE_ELIXIR_TICK = 240_000 // LOGIC_TICK_MILLISECONDS
STANDARD_TIEBREAK_TICK = 300_000 // LOGIC_TICK_MILLISECONDS


def standard_match_rules() -> FastMatchRules:
    """Return the production regulation/overtime/tiebreak rule boundary."""

    return FastMatchRules(
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
    )


def _required_tower_stat(tower_name: str, field: str) -> int:
    value = tournament_tower_stat(tower_name, field)
    if value is None:
        raise ValueError(f"missing standard tower stat: {tower_name}.{field}")
    return int(value)


def _ceil_logic_ticks(milliseconds: int) -> int:
    if milliseconds < 0:
        raise ValueError("tower timing must be non-negative")
    return int(
        max(
            1,
            (milliseconds + LOGIC_TICK_MILLISECONDS - 1) // LOGIC_TICK_MILLISECONDS,
        )
    )


def standard_tower_spec(
    loader: CardDataLoader,
    device: str | torch.device,
) -> FastTowerSpec:
    """Compile the six fixed arena towers from shared game/balance data.

    Princess range, sight, and cadence come from the serialized support-tower
    payload.  Tournament hitpoints/damage and the native King-tower cadence
    follow the same shared sources used by the scalar verifier.  Arena
    coordinates come from :class:`TileGrid`, not a second local map snapshot.
    """

    torch_device = torch.device(device)
    if torch_device.type == "cuda" and torch_device.index is None:
        torch_device = torch.device("cuda", torch.cuda.current_device())
    princess = load_princess_tower_character_data(loader.data_file)
    princess_hp = _required_tower_stat("PrincessTower", "hitpoints")
    princess_damage = _required_tower_stat("PrincessTower", "damage")
    king_hp = _required_tower_stat("KingTower", "hitpoints")
    king_damage = _required_tower_stat("KingTower", "damage")

    positions = (
        (
            TileGrid.BLUE_LEFT_TOWER,
            TileGrid.BLUE_RIGHT_TOWER,
            TileGrid.BLUE_KING_TOWER,
        ),
        (
            TileGrid.RED_LEFT_TOWER,
            TileGrid.RED_RIGHT_TOWER,
            TileGrid.RED_KING_TOWER,
        ),
    )
    x_units = tuple(
        tuple(tiles_to_logic_units(position.x) for position in owner_positions)
        for owner_positions in positions
    )
    y_units = tuple(
        tuple(tiles_to_logic_units(position.y) for position in owner_positions)
        for owner_positions in positions
    )
    princess_range = int(princess["range"])
    princess_sight = int(princess["sightRange"])
    princess_cooldown = _ceil_logic_ticks(int(princess["hitSpeed"]))
    princess_projectile = princess.get("projectileData")
    if not isinstance(princess_projectile, dict):
        raise TypeError("standard Princess Tower is missing projectile data")
    princess_projectile_speed = int(princess_projectile.get("speed", 0) or 0)
    if princess_projectile_speed <= 0:
        raise ValueError("standard Princess Tower projectile speed must be positive")
    princess_hits_air, princess_hits_ground = serialized_hit_planes(princess)
    princess_muzzle = _required_tower_stat("PrincessTower", "projectile_start_radius")
    # BattleState's shared KingTower construction uses 7 tiles and a 1000 ms
    # hit speed. Those arena-fixture values are not present in the compact
    # support-tower payload, so they are converted here once at setup.
    king_range = tiles_to_logic_units(7)
    king_cooldown = _ceil_logic_ticks(1_000)
    king_activation = _ceil_logic_ticks(
        _required_tower_stat("KingTower", "activation_duration")
    ) + _ceil_logic_ticks(
        _required_tower_stat("KingTower", "activation_first_hit_delay")
    )

    return FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=torch_device),
        x_units=torch.tensor(x_units, dtype=torch.int32, device=torch_device),
        y_units=torch.tensor(y_units, dtype=torch.int32, device=torch_device),
        hitpoints=torch.tensor(
            ((princess_hp, princess_hp, king_hp),) * 2,
            dtype=torch.float32,
            device=torch_device,
        ),
        damage=torch.tensor(
            ((princess_damage, princess_damage, king_damage),) * 2,
            dtype=torch.float32,
            device=torch_device,
        ),
        range_units=torch.tensor(
            ((princess_range, princess_range, king_range),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        sight_range_units=torch.tensor(
            ((princess_sight, princess_sight, king_range),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        hit_cooldown_ticks=torch.tensor(
            ((princess_cooldown, princess_cooldown, king_cooldown),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        initial_cooldown_ticks=torch.tensor(
            ((princess_cooldown, princess_cooldown, 0),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        preload_cooldown_floor_ticks=torch.tensor(
            ((princess_cooldown, princess_cooldown, _ceil_logic_ticks(500)),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        effect_kind=torch.full(
            (2, 3),
            FAST_CARD_EFFECT_PROJECTILE,
            dtype=torch.int8,
            device=torch_device,
        ),
        projectile_speed_units_per_tick=torch.tensor(
            ((princess_projectile_speed, princess_projectile_speed, 1_000),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        projectile_start_radius_units=torch.tensor(
            ((princess_muzzle, princess_muzzle, 750),) * 2,
            dtype=torch.int32,
            device=torch_device,
        ),
        effect_radius_units=torch.zeros((2, 3), dtype=torch.int32, device=torch_device),
        hits_air=torch.tensor(
            ((princess_hits_air, princess_hits_air, True),) * 2,
            dtype=torch.bool,
            device=torch_device,
        ),
        hits_ground=torch.tensor(
            ((princess_hits_ground, princess_hits_ground, True),) * 2,
            dtype=torch.bool,
            device=torch_device,
        ),
        affects_hidden=torch.zeros((2, 3), dtype=torch.bool, device=torch_device),
        king_activation_ticks=torch.full(
            (2,), king_activation, dtype=torch.int32, device=torch_device
        ),
    )


def _ordered_deck_ids(
    setup: SimpleStandardSetup,
    deck_names: Sequence[Sequence[Sequence[str]]],
) -> torch.Tensor:
    if len(deck_names) < 1:
        raise ValueError("deck_names must contain at least one batch row")

    rows: list[list[list[int]]] = []
    unsupported: set[str] = set()
    unknown: set[str] = set()
    name_to_id = setup.cards.name_to_id
    for batch_row in deck_names:
        if len(batch_row) != 2:
            raise ValueError("deck_names must have shape [batch, 2, 8]")
        owners: list[list[int]] = []
        for owner_deck in batch_row:
            if len(owner_deck) != 8:
                raise ValueError("deck_names must have shape [batch, 2, 8]")
            ids: list[int] = []
            for name in owner_deck:
                card_id = name_to_id.get(name)
                if card_id is None or not bool(setup.public_root_mask[card_id]):
                    unknown.add(name)
                    continue
                ids.append(card_id)
                if not bool(setup.supported_public_root_mask[card_id]):
                    unsupported.add(name)
            owners.append(ids)
        rows.append(owners)

    if unknown:
        raise ValueError(f"deck cards are not compiled public roots: {sorted(unknown)}")
    if unsupported:
        raise ValueError(
            f"unsupported standard simple Gym deck cards: {sorted(unsupported)}"
        )
    return torch.tensor(rows, dtype=torch.int64, device=setup.device)


@dataclass(frozen=True)
class SimpleStandardSetup:
    """Compiled public vocabulary and exact standard arena fixtures."""

    cards: TensorCardCatalog
    spawn_blueprints: FastSpawnBlueprintCatalog
    policy_mechanics: FastPolicyMechanicCatalog
    ability_catalog: FastAbilityCatalog
    travel_catalog: FastTravelCatalog
    triggered_impact_catalog: FastTriggeredImpactCatalog
    knockback_immune_by_card: torch.Tensor
    tower_spec: FastTowerSpec
    rules: FastMatchRules
    public_root_mask: torch.Tensor
    supported_public_root_mask: torch.Tensor
    public_root_names: tuple[str, ...]
    supported_public_root_names: tuple[str, ...]
    canonical_lane_globals: bool

    @property
    def device(self) -> torch.device:
        return self.cards.device

    def create_runtime(
        self,
        deck_names: Sequence[Sequence[Sequence[str]]],
        *,
        entity_token_lookup: torch.Tensor,
        hand_token_lookup: torch.Tensor,
        canonical_lane_globals: bool,
        max_entities: int = 128,
        max_effects: int = 128,
        max_scheduled_casts: int = 16,
        starting_elixir: float = 6.0,
        max_elixir: float = 10.0,
        include_privileged_critic: bool = False,
    ) -> SimpleGymRuntime:
        """Create a fail-closed runtime from named, ordered player decks."""

        if canonical_lane_globals is not True:
            raise ValueError("standard simple Gym requires canonical_lane_globals=true")
        if not self.canonical_lane_globals:
            raise RuntimeError("compiled setup lost canonical_lane_globals contract")
        deck_ids = _ordered_deck_ids(self, deck_names)
        runtime_blueprints = (
            self.spawn_blueprints if self.spawn_blueprints.blueprint_count > 0 else None
        )
        return SimpleGymRuntime(
            deck_ids,
            self.spawn_blueprints.fast_cards,
            self.tower_spec,
            self.rules,
            entity_token_lookup=entity_token_lookup,
            hand_token_lookup=hand_token_lookup,
            max_entities=max_entities,
            max_effects=max_effects,
            max_scheduled_casts=max_scheduled_casts,
            starting_elixir=starting_elixir,
            max_elixir=max_elixir,
            include_privileged_critic=include_privileged_critic,
            tick_seconds=LOGIC_TICK_SECONDS,
            double_elixir_tick=STANDARD_DOUBLE_ELIXIR_TICK,
            triple_elixir_tick=STANDARD_TRIPLE_ELIXIR_TICK,
            spawn_blueprints=runtime_blueprints,
            policy_mechanics=self.policy_mechanics,
            ability_catalog=self.ability_catalog,
            travel_catalog=self.travel_catalog,
            triggered_impact_catalog=self.triggered_impact_catalog,
            knockback_immune_by_card=self.knockback_immune_by_card,
        )


def compile_standard_simple_setup(
    loader: CardDataLoader,
    public_root_names: Sequence[str],
    *,
    device: str | torch.device,
    canonical_lane_globals: bool,
) -> SimpleStandardSetup:
    """Compile standard Gym catalogs and expose truthful public support."""

    if canonical_lane_globals is not True:
        raise ValueError("standard simple Gym requires canonical_lane_globals=true")
    if not public_root_names:
        raise ValueError("public_root_names must not be empty")
    base_cards = TensorCardCatalog.compile(
        loader,
        public_root_names,
        device=device,
    )
    blueprints = FastSpawnBlueprintCatalog.compile(loader, base_cards)
    policy_mechanics = FastPolicyMechanicCatalog.compile(blueprints.cards, loader)
    ability_catalog = FastAbilityCatalog.compile(blueprints.cards, loader)
    travel_catalog = FastTravelCatalog.compile(blueprints.cards, loader)
    triggered_impact_catalog = FastTriggeredImpactCatalog.compile(
        blueprints.cards, loader
    )
    knockback_immune = torch.zeros(
        len(blueprints.cards.names),
        dtype=torch.bool,
        device=blueprints.device,
    )
    for card_id, name in enumerate(blueprints.cards.names[1:], start=1):
        card = loader.get_card(name)
        if card is not None:
            knockback_immune[card_id] = is_knockback_immune(card)
    public_mask = blueprints.public_card_mask.clone()
    supported_mask = (
        public_mask
        & blueprints.fast_cards.training_supported
        & policy_mechanics.profile_supported
        & ~ability_catalog.malformed
        & ~ability_catalog.duplicate
        & travel_catalog.profile_supported
        & ~triggered_impact_catalog.malformed
        & ~triggered_impact_catalog.duplicate
    ).clone()
    # A public action which declares multiple serialized child groups is
    # admissible only when setup compiled one complete all-or-nothing event.
    # This remains a numeric setup gate: runtime never dispatches on card names.
    action_atomic_required = torch.zeros_like(public_mask)
    deploy_events = blueprints.atomic_event_trigger == int(
        FastSpawnTrigger.DEPLOY_ACTION
    )
    action_atomic_required[blueprints.atomic_event_root_card_id[deploy_events]] = True
    supported_mask &= ~action_atomic_required | (
        blueprints.action_atomic_event_by_card >= 0
    )
    public_names = tuple(
        name
        for card_id, name in enumerate(blueprints.cards.names)
        if bool(public_mask[card_id])
    )
    supported_names = tuple(
        name
        for card_id, name in enumerate(blueprints.cards.names)
        if bool(supported_mask[card_id])
    )
    return SimpleStandardSetup(
        cards=blueprints.cards,
        spawn_blueprints=blueprints,
        policy_mechanics=policy_mechanics,
        ability_catalog=ability_catalog,
        travel_catalog=travel_catalog,
        triggered_impact_catalog=triggered_impact_catalog,
        knockback_immune_by_card=knockback_immune,
        tower_spec=standard_tower_spec(loader, device),
        rules=standard_match_rules(),
        public_root_mask=public_mask,
        supported_public_root_mask=supported_mask,
        public_root_names=public_names,
        supported_public_root_names=supported_names,
        canonical_lane_globals=True,
    )


__all__ = [
    "STANDARD_DOUBLE_ELIXIR_TICK",
    "STANDARD_REGULATION_TICK",
    "STANDARD_TIEBREAK_TICK",
    "STANDARD_TRIPLE_ELIXIR_TICK",
    "SimpleStandardSetup",
    "compile_standard_simple_setup",
    "standard_match_rules",
    "standard_tower_spec",
]
