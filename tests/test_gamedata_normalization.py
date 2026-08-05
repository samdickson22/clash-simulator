import json

from clasher.balance import apply_entry_overrides
from clasher.dynamic_spells import create_spell_from_json, determine_spell_type
from clasher.gamedata_normalization import (
    build_object_registry,
    normalize_entry,
    serialized_hit_planes,
)
from clasher.factory.mechanic_detector import detect_mechanics_from_data
from clasher.paths import gamedata_path
from clasher.spells import GraveyardSpell, RoyalDeliverySpell


def test_current_gamedata_snapshot_is_the_statsroyale_v5_export():
    with gamedata_path(must_exist=True).open() as source:
        data = json.load(source)

    assert data["meta"]["fingerprint"] == "ef863332281e7c47d628d23a80881ed300d47ede"
    assert len(data["items"]["spells"]) == 148


def test_special_spell_loaders_follow_payload_shape_after_card_rename():
    with gamedata_path(must_exist=True).open() as source:
        data = json.load(source)
    registry = build_object_registry(data)
    entries = {
        entry["name"]: entry
        for entry in data["items"]["spells"]
    }

    graveyard = apply_entry_overrides(entries["Graveyard"], registry)
    graveyard["name"] = "SyntheticRepeatedSpawner"
    assert determine_spell_type(graveyard) is GraveyardSpell
    repeated_spawn = create_spell_from_json(graveyard, registry)
    assert repeated_spawn.spawn_character == "Skeleton"
    assert repeated_spawn.spawn_deadlines[0] == 1.2
    assert len(repeated_spawn.spawn_offsets) == 12

    delivery = apply_entry_overrides(entries["RoyalDelivery"], registry)
    delivery["name"] = "SyntheticDelayedAreaSpawn"
    assert determine_spell_type(delivery) is RoyalDeliverySpell

    arrows = apply_entry_overrides(entries["Arrows"], registry)
    arrows["name"] = "SyntheticGroupedVolley"
    grouped_volley = create_spell_from_json(arrows, registry)
    assert grouped_volley.projectile_pattern == "grouped_ring"


def test_compact_hit_plane_omission_means_false_when_other_plane_is_present():
    assert serialized_hit_planes({"hitsGround": True}) == (False, True)
    assert serialized_hit_planes({"hitsAir": True}) == (True, False)
    assert serialized_hit_planes({"tidTarget": "TID_TARGETS_GROUND"}) == (
        False,
        True,
    )
    assert serialized_hit_planes(
        {"tidTarget": "TID_TARGETS_AIR_AND_GROUND"}
    ) == (True, True)
    assert serialized_hit_planes(
        {},
        default_air=False,
        default_ground=True,
    ) == (False, True)
    assert serialized_hit_planes({}) == (True, True)


def test_spell_as_deploy_action_is_normalized_without_card_identity():
    entry = {
        "name": "SyntheticDeploy",
        "spellAsDeploy": True,
        "areaEffectObjectData": {
            "name": "SyntheticLanding",
            "damage": 12,
            "radius": 2500,
            "buffTime": 400,
            "onStartingActionData": {
                "subActionsData": [
                    {
                        "actionsData": [
                            {
                                "spawnDataData": {
                                    "name": "SyntheticTroop",
                                    "source": "characters",
                                    "hitpoints": 100,
                                    "deployTime": 750,
                                }
                            }
                        ]
                    }
                ]
            },
        },
    }

    normalized = normalize_entry(entry)
    character = normalized["summonCharacterData"]

    assert character["name"] == "SyntheticTroop"
    assert character["deployTime"] == 750
    assert character["spawnAreaObjectData"] == {
        "name": "SyntheticLanding",
        "damage": 12,
        "radius": 2500,
        "buffTime": 400,
    }
    assert "summonCharacterData" not in entry


def test_death_action_spawn_is_normalized_without_card_identity():
    entry = {
        "name": "SyntheticCarrier",
        "summonCharacterData": {
            "name": "SyntheticCarrierCharacter",
            "source": "characters",
            "deathAreaEffectData": {
                "onStartingActionData": {
                    "spawnDataData": {
                        "name": "SyntheticPayload",
                        "source": "buildings",
                        "deployTime": 500,
                    }
                }
            },
        },
    }

    normalized = normalize_entry(entry)
    character = normalized["summonCharacterData"]

    assert character["deathSpawnCharacter"] == "SyntheticPayload"
    assert character["deathSpawnCharacterData"]["deployTime"] == 500


def test_named_death_spawn_reference_hydrates_transitive_character_data():
    data = {
        "items": {
            "spells": [
                {
                    "summonCharacterData": {
                        "name": "SyntheticMinion",
                        "source": "characters",
                        "hitpoints": 40,
                    }
                }
            ]
        }
    }
    registry = build_object_registry(data)
    registry["SyntheticContainer"] = {
        "name": "SyntheticContainer",
        "source": "buildings",
        "deathSpawnCharacter": "SyntheticMinion",
        "deathSpawnCount": 3,
    }
    entry = {
        "name": "SyntheticBarrel",
        "summonCharacterData": {
            "name": "SyntheticBarrelCharacter",
            "source": "characters",
            "deathSpawnCharacter": "SyntheticContainer",
        },
    }

    normalized = normalize_entry(entry, registry)
    container = normalized["summonCharacterData"]["deathSpawnCharacterData"]

    assert container["name"] == "SyntheticContainer"
    assert container["deathSpawnCharacterData"]["name"] == "SyntheticMinion"
    assert container["deathSpawnCharacterData"]["hitpoints"] == 40


def test_arbitrary_character_death_area_action_uses_shared_mechanic():
    entry = {
        "name": "FutureDeathAuraUnit",
        "summonCharacterData": {
            "name": "FutureDeathAuraUnit",
            "deathAreaEffectData": {
                "name": "FutureDummy",
                "onStartingActionData": {
                    "spawnDataData": {
                        "name": "FutureBottle",
                        "deployTime": 450,
                        "deathAreaEffectData": {
                            "name": "FutureAura",
                            "radius": 2500,
                            "lifeDuration": 3000,
                            "buffTime": 500,
                            "buffData": {
                                "name": "FutureHaste",
                                "speedMultiplier": 120,
                                "hitSpeedMultiplier": 120,
                                "spawnSpeedMultiplier": 120,
                            },
                        },
                    }
                },
            },
        },
    }

    mechanics = detect_mechanics_from_data(normalize_entry(entry))

    assert [type(mechanic).__name__ for mechanic in mechanics] == [
        "DeathAreaEffect"
    ]
