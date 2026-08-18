from __future__ import annotations

from collections import defaultdict

import pytest
import torch

from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.projectile_coverage import (
    enumerate_enabled_projectile_bridge_coverage,
)

EXPECTED_DIGEST = "6f0a56d4be288fb944cb09c72c3e050fb2166e71ee92de2f9f17cb39da6a8783"
EXPECTED_SUPPORTED = {
    "ArcherQueen",
    "Archers",
    "Arrows",
    "BabyDragon",
    "Bomber",
    "BombTower",
    "Bowler",
    "Cannon",
    "DartGoblin",
    "Fireball",
    "GiantSnowball",
    "GoblinBarrel",
    "IceWizard",
    "LavaHound",
    "MegaMinion",
    "Minions",
    "Musketeer",
    "Princess",
    "Rocket",
    "SpearGoblins",
    "Xbow",
    "Zap",
    "Witch",
}
EXPECTED_UNSUPPORTED_BY_REASON = {
    "card has no projectile payload": {
        "Balloon",
        "Bandit",
        "Bats",
        "BattleRam",
        "DarkPrince",
        "ElectroWizard",
        "Giant",
        "GoblinGang",
        "Golem",
        "Guards",
        "HogRider",
        "IceGolem",
        "InfernoDragon",
        "InfernoTower",
        "Knight",
        "Lumberjack",
        "MegaKnight",
        "Miner",
        "MiniPekka",
        "NightWitch",
        "Pekka",
        "Prince",
        "RoyalGhost",
        "RoyalHogs",
        "SkeletonBarrel",
        "Skeletons",
        "Tesla",
        "Tombstone",
        "Valkyrie",
    },
    "continuous freeze/slow area is not retained": {
        "Earthquake",
        "Freeze",
        "Poison",
    },
    "impact child projectile is not retained": {"Firecracker"},
    "piercing/start collision projectile is not retained": {"MagicArcher"},
    "projectile impact callbacks are not retained: ElectroDragonChainLightning": {
        "ElectroDragon"
    },
    "projectile impact callbacks are not retained: ElectroSpiritChain": {
        "ElectroSpirit"
    },
    "projectile impact callbacks are not retained: IceSpiritFreeze": {"IceSpirit"},
    "projectile impact callbacks are not retained: WallBreakersDemolition": {
        "Wallbreakers"
    },
    "spell family GraveyardSpell is not retained": {"Graveyard"},
    "spell family RollingProjectileSpell is not retained": {
        "BarbarianBarrel",
        "Log",
    },
    "spell family RoyalDeliverySpell is not retained": {"RoyalDelivery"},
    "spell family TornadoSpell is not retained": {"Tornado"},
}


@pytest.fixture(scope="module")
def enabled_matrix():
    return enumerate_enabled_projectile_bridge_coverage()


def test_enabled_manifest_has_reviewed_standalone_bridge_matrix(enabled_matrix) -> None:
    enabled = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    assert tuple(entry.card_name for entry in enabled_matrix.entries) == enabled
    assert len(enabled_matrix.entries) == 66
    assert enabled_matrix.digest == EXPECTED_DIGEST
    assert set(enabled_matrix.supported_cards) == EXPECTED_SUPPORTED

    actual_by_reason: dict[str, set[str]] = defaultdict(set)
    for entry in enabled_matrix.entries:
        if not entry.bridge_supported:
            assert entry.unsupported_reason is not None
            actual_by_reason[entry.unsupported_reason].add(entry.card_name)
    assert dict(actual_by_reason) == EXPECTED_UNSUPPORTED_BY_REASON


def test_serialized_feature_rows_cover_each_retained_payload_family(
    enabled_matrix,
) -> None:
    entries = {entry.card_name: entry for entry in enabled_matrix.entries}

    zap = entries["Zap"]
    assert zap.payload_kind == "direct_spell"
    assert zap.feature_map["damage"] == 192.0
    assert zap.feature_map["stun_ms"] == 500

    fireball = entries["Fireball"]
    assert fireball.payload_kind == "projectile_spell"
    assert fireball.feature_map["projectile_speed_units"] == 600
    assert fireball.feature_map["knockback_units"] == 1_000

    arrows = entries["Arrows"]
    assert arrows.feature_map["multiple_projectiles"] == 10
    assert arrows.feature_map["damage_waves"] == 3
    assert arrows.feature_map["projectile_pattern"] == 1

    barrel = entries["GoblinBarrel"]
    assert barrel.payload_kind == "spawn_projectile"
    assert barrel.feature_map["spawn_card_name"] == "Goblin"
    assert barrel.feature_map["spawn_count"] == 3
    assert barrel.feature_map["spawn_deploy_delay_ms"] == 1_100
    assert barrel.feature_map["spawn_offsets_units"] == (
        (
            ((0, 577), (499, -288), (-499, -288)),
            ((0, 577), (-499, -288), (499, -288)),
        ),
        (
            ((0, -577), (499, 288), (-499, 288)),
            ((0, -577), (-499, 288), (499, 288)),
        ),
    )

    cannon = entries["Cannon"]
    assert cannon.payload_kind == "combat_projectile"
    assert cannon.feature_map["tracks_target"] is True
    assert cannon.feature_map["projectile_start_radius_units"] == 1_000


def test_standalone_support_is_never_resident_engine_parity_evidence(
    enabled_matrix,
) -> None:
    assert not enabled_matrix.resident_engine_parity_claimed
    assert all(
        not entry.resident_engine_parity_evidence for entry in enabled_matrix.entries
    )
    assert (
        enabled_matrix.require_standalone_support("Fireball").payload_kind
        == "projectile_spell"
    )
    with pytest.raises(ValueError, match="standalone projectile bridge"):
        enabled_matrix.require_standalone_support("Knight")


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_representative_feature_digest_is_device_stable(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    matrix = enumerate_enabled_projectile_bridge_coverage(
        device=device,
        card_names=("Arrows", "Cannon", "Fireball", "GoblinBarrel", "Zap"),
    )
    assert matrix.digest == (
        "c418e00ec86015fa2cdef72501e97db6119887fd75a5515c00b69d66ca0e6496"
    )
