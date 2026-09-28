from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest
import torch

from clasher.arena import Position
from clasher.entities import (
    AreaEffect,
    ChainLightning,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


@lru_cache(maxsize=1)
def _builder() -> StructuredObservationBuilder:
    payload = torch.load(
        Path(
            "checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/"
            "candidate.pt"
        ),
        map_location="cpu",
        weights_only=False,
    )
    return StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=payload["token_names"],
        max_entities=128,
        card_semantics_version=3,
    )


def _base_kwargs(card_stats: object | None) -> dict[str, object]:
    return {
        "id": 100,
        "position": Position(9.0, 12.0),
        "player_id": 0,
        "card_stats": card_stats,
        "hitpoints": 1.0,
        "max_hitpoints": 1.0,
        "damage": 1.0,
        "range": 1.0,
        "sight_range": 1.0,
    }


@pytest.mark.parametrize(
    ("card_name", "expected"),
    [
        ("Guards", "troop_body:SkeletonWarrior"),
        ("Skeletons", "troop_body:Skeleton"),
        ("SpearGoblins", "troop_body:SpearGoblin"),
    ],
)
def test_runtime_troop_identity_uses_serialized_character_payload(
    card_name: str,
    expected: str,
) -> None:
    builder = _builder()
    entity = Troop(**_base_kwargs(builder.loader.get_card(card_name)))  # type: ignore[arg-type]

    token_id, _features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == expected


def test_runtime_projectile_identity_uses_serialized_projectile_payload() -> None:
    builder = _builder()
    entity = Projectile(
        **_base_kwargs(builder.loader.get_card("Musketeer")),  # type: ignore[arg-type]
        target_position=Position(9.0, 18.0),
    )

    token_id, _features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "projectile:MusketeerProjectile"


def test_runtime_rolling_identity_uses_nested_serialized_projectile() -> None:
    builder = _builder()
    entity = RollingProjectile(**_base_kwargs(None))  # type: ignore[arg-type]
    entity.spell_name = "Log"

    token_id, _features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "projectile:LogProjectileRolling"


def test_runtime_area_identity_uses_public_spell_identity() -> None:
    builder = _builder()
    entity = AreaEffect(**_base_kwargs(None))  # type: ignore[arg-type]
    entity.spell_name = "Rage"

    token_id, _features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "area_effect:Rage"


def test_runtime_timed_payload_uses_serialized_building_identity() -> None:
    builder = _builder()
    entity = TimedExplosive(
        **_base_kwargs(builder.loader.get_card("Balloon"))  # type: ignore[arg-type]
    )

    token_id, features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "building_body:BalloonBomb"
    assert features[7] == 1.0  # Execution kind remains area/effect.


def test_runtime_falling_troop_container_retains_source_body_identity() -> None:
    builder = _builder()
    entity = TimedExplosive(
        **_base_kwargs(builder.loader.get_card("SkeletonBalloon"))  # type: ignore[arg-type]
    )

    token_id, features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "troop_body:SkeletonBalloon"
    assert features[7] == 1.0  # Execution kind remains area/effect.


def test_runtime_spawn_carrier_walks_nested_source_projectile_payload() -> None:
    builder = _builder()
    entity = SpawnProjectile(
        **_base_kwargs(None),  # type: ignore[arg-type]
        target_position=Position(9.0, 18.0),
    )
    entity.spell_name = "RoyalDelivery"

    token_id, _features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "projectile:RoyalDeliveryProjectile"


def test_runtime_chain_controller_uses_serialized_projectile_identity() -> None:
    builder = _builder()
    entity = ChainLightning(
        **_base_kwargs(builder.loader.get_card("ElectroSpirit"))  # type: ignore[arg-type]
    )

    token_id, features = builder._entity_row(entity, 0)

    assert builder.token_names[token_id] == "projectile:ElectroSpiritProjectile"
    assert features[7] == 1.0  # Execution kind remains area/effect.
