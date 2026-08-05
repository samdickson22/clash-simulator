"""Versioned live-balance corrections over the refreshed V5 game-data feed.

Values are base-card Level 11 stats effective after the July 6, 2026 update.
Only values absent from the public feed, or interaction-specific values that
cannot be derived from it, belong here. Keeping those deltas declarative
prevents balance history from leaking into combat code as one-off card checks.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .gamedata_normalization import normalize_entry


BALANCE_VERSION = "2026-07-06"
TOURNAMENT_LEVEL = 11

# Global combat-animation tail used after a connected target disappears.
# Character data can opt into its own AttackFinishTime, including an explicit
# zero; every ordinary combat component uses this live global value.
GLOBAL_ATTACK_FINISH_TIME_MS = 250


# Tower Troops use their own historical level curve rather than the ordinary
# Common-card multiplier. Store the live tournament snapshot explicitly so
# the fixed arena baseline is not scaled through the character-card curve.
TOURNAMENT_TOWER_STATS: dict[str, dict[str, int]] = {
    "PrincessTower": {
        "hitpoints": 3052,
        "damage": 109,
        # The compact Tower Troop payload omits visual muzzle fields. The
        # underlying PrincessTower character still launches 300 logic units
        # forward, just as the KingTower keeps its serialized 750-unit value.
        "projectile_start_radius": 300,
    },
    "KingTower": {
        "hitpoints": 4824,
        "damage": 109,
        # These native character/action fields are omitted from the compact
        # tower-support payload but control the wake-up and first-shot clocks.
        "load_time": 500,
        "activation_duration": 3300,
        # The one-time activation action has its own post-aim attack delay.
        # It is distinct from the ordinary 500 ms first-hit/retarget load.
        "activation_first_hit_delay": 700,
    },
}


TOURNAMENT_STAT_OVERRIDES: dict[str, dict[str, int]] = {
    # Ordinary troop hitpoints and damage scale directly from the refreshed
    # character/projectile payloads. Keep only values that are a distinct
    # interaction rule rather than a duplicate balance pin.
    "Miner": {"crown_tower_damage": 39},
}


# Raw character fields that changed after the bundled snapshot.  Applying
# these by spawned-character name (rather than by the parent card) keeps the
# correction consistent for Skeletons created by Graveyard, Witch, Tombstone,
# Skeleton Barrel, and every other source.
CHARACTER_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    # The bundled compact snapshot omits projectile muzzle geometry. The
    # engine launches in the target direction from this forward radius; it is
    # gameplay data because it changes flight time and the start of rolling
    # and piercing collision paths.
    "ArcherQueen": {
        "projectileStartRadius": 1350,
        # Cloak blocks target acquisition, but the native character explicitly
        # remains eligible for area damage while invisible.
        "allowAreaDmgWhenInvisible": True,
    },
    "Archer": {"projectileStartRadius": 450},
    "Assassin": {
        "dashCooldown": 800,
        # Dash travel is invulnerable by state. This separately serialized
        # tail keeps damage and status effects blocked for 100 ms after the
        # landing transition.
        "dashImmuneToDamageTime": 100,
    },
    "BabyDragon": {"projectileStartRadius": 500},
    "Bomber": {"projectileStartRadius": 350},
    "Bowler": {
        "projectileStartRadius": 1000,
        "overrideAttackFinishTime": True,
        "attackFinishTime": 150,
    },
    "BlowdartGoblin": {"projectileStartRadius": 1200},
    "ElectroDragon": {
        "projectileStartRadius": 1250,
        "overrideAttackFinishTime": True,
        "attackFinishTime": 0,
    },
    "Firecracker": {
        "projectileStartRadius": 200,
        "attackPushback": 1000,
    },
    "Ghost": {
        # Like Archer Queen, Royal Ghost cannot be acquired while invisible
        # but is still included in native area-damage target queries.
        "allowAreaDmgWhenInvisible": True,
    },
    "Giant": {
        "stopMovementAfterMS": 640,
        "waitMS": 100,
        "sightClip": 2000,
        "sightClipSide": 2000,
    },
    "Balloon": {"sightClipSide": 2000},
    "IceWizard": {"projectileStartRadius": 550},
    "InfernoDragon": {
        "projectileStartRadius": 450,
        "variableDamageTime1": 2000,
        "variableDamageTime2": 2000,
    },
    "InfernoTower": {
        "variableDamageTime1": 2000,
        "variableDamageTime2": 2000,
    },
    "LavaHound": {
        "projectileStartRadius": 1000,
        "deathSpawnRadius": 2500,
        "deathSpawnPushback": True,
    },
    "LavaPups": {"projectileStartRadius": 500},
    "EliteArcher": {"projectileStartRadius": 800},
    "MegaKnight": {
        "dashConstantTime": 800,
        "dashCooldown": 900,
        "dashLandingTime": 300,
        "dashPushBack": 1000,
        "dashRadius": 2200,
    },
    "MegaMinion": {"projectileStartRadius": 450},
    "Minion": {"projectileStartRadius": 450},
    "Miner": {"spawnPathfindSpeed": 650},
    "Musketeer": {"projectileStartRadius": 450},
    "ElectroWizard": {
        # MultipleTargets=2 normally selects distinct targets. This native
        # flag makes both bolts hit the primary when no second target exists.
        "allTargetsHit": True,
        "overrideAttackFinishTime": True,
        "attackFinishTime": 0,
    },
    "Princess": {
        "projectileStartRadius": 450,
        "overrideAttackFinishTime": True,
        "attackFinishTime": 200,
    },
    "SpearGoblin": {"projectileStartRadius": 0},
    "Witch": {
        "projectileStartRadius": 450,
        "spawnStartTime": 1000,
        "spawnRadius": 2000,
    },
    "DarkWitch": {
        "deathSpawnRadius": 500,
        "spawnStartTime": 1000,
        "spawnRadius": 1500,
        "spawnAngleShift": 90,
    },
    "Cannon": {"projectileStartRadius": 1000},
    "BombTower": {"projectileStartRadius": 0},
    "Xbow": {"projectileStartRadius": 1000},
    "Valkyrie": {
        "selfAsAoeCenter": True,
        "overrideAttackFinishTime": True,
        "attackFinishTime": 100,
    },
    # Applying these by nested character name keeps deck Bats and every
    # secondary spawn source on identical live behavior. Hit/load timings now
    # come directly from the refreshed V5 payload.
    "Bat": {
        "attackDashTime": 150,
        "spawnAngleShift": 45,
    },
    "Prince": {"chargeSpeedMultiplier": 200},
    "DarkPrince": {"chargeSpeedMultiplier": 200},
    # Death-nova displacement and split geometry are absent from the bundled
    # snapshot but remain observable combat stats.
    "Golem": {
        "deathDamageRadius": 2000,
        "deathPushback": 1800,
        "deathSpawnRadius": 1500,
        "deathSpawnPushback": True,
        "stopMovementAfterMS": 1000,
        "waitMS": 200,
        "sightClip": 2000,
        "sightClipSide": 1900,
    },
    "IceGolemite": {
        "deathDamageRadius": 2000,
        "stopMovementAfterMS": 470,
        "waitMS": 80,
        "sightClip": 2000,
        "sightClipSide": 2000,
    },
    "HogRider": {"sightClip": 4000, "sightClipSide": 4000},
    "RoyalHog": {"sightClip": 4000, "sightClipSide": 4000},
    "SkeletonBalloon": {
        "sightClipSide": 2000,
        "range": 350,
        "kamikazeTime": 500,
    },
    "Golemite": {
        "deathDamageRadius": 2000,
        "deathPushback": 900,
        "sightClip": 2000,
        "sightClipSide": 2000,
    },
    "BattleRam": {
        "chargeSpeedMultiplier": 200,
        "deathSpawnDeployTime": 1000,
        "deathSpawnRadius": 600,
        "spawnAngleShift": 180,
    },
    # Skeleton Barrel's falling container is the only enabled timed death
    # payload that pushes units.  Store the live one-tile value on the nested
    # character payload so Balloon and Bomb Tower bombs remain unaffected.
    "SkeletonContainer": {
        "deathDamageRadius": 2000,
        "deathPushback": 1000,
        "deathSpawnMinRadius": 1480,
        "deathSpawnRadius": 1480,
        "deathSpawnDeployTime": 500,
        "deathSpawnPushback": True,
    },
    "BalloonBomb": {"deathDamageRadius": 3000},
    "BombTowerBomb": {"deathDamageRadius": 3000},
}


# Runtime movement/collision columns omitted by the bundled compact export.
# These are copied from the current character tables and keyed by the nested
# character identity so card aliases and every spawn source share one value.
CHARACTER_RUNTIME_TRAITS: dict[str, dict[str, Any]] = {
    "ArcherQueen": {"mass": 6},
    "Archer": {"mass": 3},
    "BabyDragon": {"mass": 5, "flyingHeight": 3500},
    "Balloon": {"mass": 6, "flyingHeight": 3000},
    "Assassin": {"mass": 3},
    "Bat": {"mass": 1, "flyingHeight": 2000},
    "BattleRam": {"mass": 6},
    "Barbarian": {"mass": 4},
    "BlowdartGoblin": {"mass": 3},
    "Bomber": {"mass": 4},
    "Bowler": {"mass": 18, "ignorePushback": True},
    "DarkPrince": {"mass": 6, "ignorePushback": True},
    "DarkWitch": {"mass": 4},
    "DeliveryRecruit": {"mass": 5},
    "ElectroDragon": {"mass": 7, "flyingHeight": 3500},
    "ElectroSpirit": {"mass": 1},
    "ElectroWizard": {"mass": 5},
    "EliteArcher": {"mass": 3},
    "Firecracker": {"mass": 6},
    "Ghost": {"mass": 3, "hovering": True},
    "Giant": {"mass": 18, "ignorePushback": True},
    "Goblin": {"mass": 2},
    "Goblin_Stab": {"mass": 2},
    "Golem": {"mass": 20, "ignorePushback": True},
    "Golemite": {"mass": 6},
    "HogRider": {"mass": 4},
    "IceGolemite": {"mass": 6},
    "IceSpirits": {"mass": 1},
    "IceWizard": {"mass": 5},
    "InfernoDragon": {"mass": 5, "flyingHeight": 4000},
    "Knight": {"mass": 6},
    "LavaHound": {
        "mass": 5,
        "flyingHeight": 4000,
        "ignorePushback": True,
    },
    "LavaPups": {"mass": 5, "flyingHeight": 3500},
    "MegaKnight": {"mass": 18, "ignorePushback": True},
    # Mega Minion is in the six-mass class in the current character table.
    "MegaMinion": {"mass": 6, "flyingHeight": 1500},
    "Miner": {"mass": 6},
    "MiniPekka": {"mass": 4},
    "Minion": {"mass": 2, "flyingHeight": 1500},
    "Musketeer": {"mass": 5},
    "Pekka": {"mass": 18, "ignorePushback": True},
    "Prince": {"mass": 6, "ignorePushback": True},
    "Princess": {"mass": 3},
    "RageBarbarian": {"mass": 4},
    "RoyalHog": {"mass": 2},
    "Skeleton": {"mass": 1},
    "SkeletonBalloon": {"mass": 7, "flyingHeight": 3100},
    "SkeletonWarrior": {"mass": 1},
    "SpearGoblin": {"mass": 1},
    "Valkyrie": {"mass": 5},
    "Wallbreaker": {"mass": 4},
    "Witch": {"mass": 8},
}


# Projectile homing is omitted from the bundled compact snapshot. Keep it on
# the serialized projectile payload rather than branching on its parent card:
# the same projectile can be used by a troop, a tower, or a spawned unit.
PROJECTILE_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "ArcherArrow": {"homing": True},
    "ArcherQueenArrow": {"homing": True},
    "BabyDragonProjectile": {"homing": True},
    "BarbLogProjectile": {"minDistance": 3000},
    "BarbLogProjectileRolling": {
        "minDistance": 2500,
        "projectileRadius": 1300,
        "projectileRadiusY": 600,
        "spawnCharacterDeployTime": 1000,
    },
    "BombSkeletonProjectile": {"homing": False},
    "BombTowerProjectile": {"homing": False},
    "BowlerProjectile": {"homing": False, "projectileRadius": 1000},
    "BlowdartGoblinProjectile": {"homing": True},
    "ElectroDragonProjectile": {"homing": True, "chainedHitRadius": 4000},
    "ElectroSpiritProjectile": {"homing": True, "chainedHitRadius": 4000},
    "FirecrackerProjectile": {"homing": False},
    "FirecrackerExplosion": {
        "homing": False,
        "minDistance": 5000,
        "projectileRadius": 400,
        "projectileStartExtraRadius": 650,
        "spawnRadius": 80,
        "scatter": "Line",
    },
    "IceSpiritsProjectile": {"homing": True},
    "ice_wizardProjectile": {"homing": True},
    "LavaHoundProjectile": {"homing": True},
    "LavaPupProjectile": {"homing": True},
    "LogProjectile": {"minDistance": 3000},
    "LogProjectileRolling": {
        "minDistance": 2500,
        "projectileRadius": 1950,
        "projectileRadiusY": 600,
    },
    "EliteArcherArrow": {
        "homing": False,
        "projectileRadius": 250,
        "projectileStartExtraRadius": 400,
    },
    "MegaMinionSpit": {"homing": True},
    "MinionSpit": {"homing": True},
    "MusketeerProjectile": {"homing": True},
    "PrincessProjectile": {"homing": False},
    "PrincessProjectileDeco": {"homing": False},
    "SpearGoblinProjectile": {"homing": True},
    "TowerCannonball": {"homing": True},
    "TowerPrincessProjectile": {"homing": True},
    "WitchProjectile": {"homing": True},
    "xbow_projectile": {"homing": True},
}

# The compact public export drops the AreaEffectObject ``AffectsHidden``
# column. Keep it attached to the payload identity from the current client
# table: target eligibility follows the effect object, not the card name that
# happened to create it.
AREA_EFFECT_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "Earthquake": {"affectsHidden": True},
    "Freeze": {"affectsHidden": True},
    "FreezeIceGolemite": {"affectsHidden": True},
    # The compact export keeps only this ActionGroup's name. These are the
    # current native group rows, represented as resolved gameplay fields so
    # every repeated SpawnToLocation group follows the same loader path.
    "Graveyard_rework": {
        "onStartingActionData": {
            "name": "Graveyard_rework_Group",
            "source": "actions",
            "classType": "ActionGroup",
            "subActionsDelay": [
                2200,
                2700,
                3300,
                3800,
                4400,
                4900,
                5500,
                6000,
                6500,
                7100,
                7600,
                8200,
            ],
            "subActionsData": [
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": -3500,
                    "yOffset": 0,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": -2500,
                    "yOffset": -2500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 0,
                    "yOffset": 3500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 3500,
                    "yOffset": 0,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 2500,
                    "yOffset": 2500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": -3500,
                    "yOffset": 0,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 0,
                    "yOffset": 3500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": -2500,
                    "yOffset": 2500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 3500,
                    "yOffset": 0,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 0,
                    "yOffset": -3500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": 2500,
                    "yOffset": -2500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
                {
                    "classType": "ActionSpawnToLocation",
                    "spawnCharacter": "Skeleton",
                    "deployTime": 500,
                    "xOffset": -2500,
                    "yOffset": -2500,
                    "mirrorXAtArenaCenter": True,
                    "orientYByTeam": True,
                },
            ],
        },
    },
    "RageDamage": {"affectsHidden": True},
    "BarbarianRageDamage": {"affectsHidden": True},
    "RoyalDeliveryArea": {"ignoreBuildings": True},
}


def _casefold_index(
    values: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build a tolerant identity index for export-only capitalization drift."""
    return {name.casefold(): fields for name, fields in values.items()}


_CHARACTER_FIELD_OVERRIDES_CASEFOLD = _casefold_index(CHARACTER_FIELD_OVERRIDES)
_CHARACTER_RUNTIME_TRAITS_CASEFOLD = _casefold_index(CHARACTER_RUNTIME_TRAITS)
_PROJECTILE_FIELD_OVERRIDES_CASEFOLD = _casefold_index(PROJECTILE_FIELD_OVERRIDES)
_AREA_EFFECT_FIELD_OVERRIDES_CASEFOLD = _casefold_index(
    AREA_EFFECT_FIELD_OVERRIDES
)


def _identity_fields(
    exact: dict[str, dict[str, Any]],
    casefolded: dict[str, dict[str, Any]],
    name: Any,
) -> dict[str, Any]:
    identity = str(name or "")
    return exact.get(identity) or casefolded.get(identity.casefold(), {})


# Live Level 11 spell values that cannot be reproduced by scaling the refreshed
# raw payload alone. Periodic values are per damage tick; crown-tower values
# are also per tick/wave.
TOURNAMENT_SPELL_OVERRIDES: dict[str, dict[str, float]] = {
    "Arrows": {"crown_tower_damage": 25},
    "Earthquake": {
        "damage": 84,
        "building_damage": 287,
        "crown_tower_damage": 49,
    },
    "Fireball": {"crown_tower_damage": 172},
    "Freeze": {"crown_tower_damage": 37},
    "Snowball": {"crown_tower_damage": 45},
    # The separately playable Rage spell received the June 2026 Crown Tower
    # nerf. Lumberjack's distinct BarbarianRageDamage payload remains at its
    # own serialized modifier and is intentionally not routed through this.
    "Rage": {"crown_tower_damage": 45},
    "Poison": {"crown_tower_damage": 21},
    "Rocket": {"crown_tower_damage": 342},
    "Log": {"crown_tower_damage": 35},
    "Zap": {"crown_tower_damage": 48},
    # CharacterBuffData exposes Tornado's damage as DPS plus a hit frequency.
    # At Level 11 that resolves to one 84-damage hit.  Its current explicit
    # -70% Crown Tower modifier truncates that hit to 25 integer damage.
    "Tornado": {"crown_tower_damage": 25},
}


ENTRY_PATH_OVERRIDES: dict[str, dict[tuple[str, ...], Any]] = {
    "ArcherQueen": {
        # character_abilities.csv serializes the Cloaking Cape action
        # separately from the character row. The compact bundled snapshot
        # retains the buff/cooldown payload but drops this cast timing.
        ("summonCharacterData", "abilityData", "castTime"): 933,
        ("summonCharacterData", "abilityData", "triggerDelay"): 200,
    },
    "Miner": {
        ("canDeployOnEnemySide",): True,
    },
    # The compact snapshot predates the native wide-formation columns now
    # used by Royal Hogs.
    "RoyalHogs": {
        ("summonWidth",): 3500,
        ("deployWTileMargin",): 2,
    },
    "Ghost": {
        ("summonCharacterData", "buffWhenNotAttackingUseAttackRange"): True,
    },
    "Fisherman": {
        ("summonCharacterData", "projectileStartRadius"): 450,
        ("summonCharacterData", "specialMinRange"): 3500,
        ("summonCharacterData", "specialRange"): 7000,
        ("summonCharacterData", "specialLoadTime"): 1300,
        ("summonCharacterData", "projectileSpecialData", "speed"): 800,
        ("summonCharacterData", "projectileSpecialData", "dragBackSpeed"): 850,
        ("summonCharacterData", "projectileSpecialData", "dragSelfSpeed"): 450,
        ("summonCharacterData", "projectileSpecialData", "dragBackAsAttractor"): True,
        ("summonCharacterData", "projectileSpecialData", "dragMargin"): 200,
        # Removed in the April 2026 balance update. The current raw community
        # payload can still expose the obsolete slowdown buff.
        ("summonCharacterData", "projectileSpecialData", "buffTime"): 0,
    },
    "Tesla": {
        # Current hide-state timings are absent from the bundled compact
        # snapshot. They belong to the character payload, not the mechanic.
        ("summonCharacterData", "hidesWhenNotAttacking"): True,
        ("summonCharacterData", "hideTimeMS"): 800,
        ("summonCharacterData", "upTimeMS"): 800,
    },
    "Earthquake": {
        # The compact public export drops both booleans. Current native data
        # keeps the slow from outliving the field and synchronizes damage to
        # the area source rather than starting a fresh clock per target.
        ("areaEffectObjectData", "capBuffTimeToAreaEffectTime"): True,
        ("areaEffectObjectData", "buffData", "hitTickFromSource"): True,
    },
    "Tornado": {
        # Controlled damage buffs are destroyed with their parent area even
        # when their most recent refresh would otherwise outlive it.
        ("areaEffectObjectData", "buffData", "controlledByParent"): True,
        ("areaEffectObjectData", "buffData", "attractPercentage"): 360,
        ("areaEffectObjectData", "buffData", "pushSpeedFactor"): 100,
    },
    "RoyalDelivery": {
        # The falling area lives for 2000 ms, but the projectile/spawn event
        # is explicitly scheduled one native 50 ms logic frame later.
        ("areaEffectObjectData", "spawnInitialDelay"): 2050,
    },
    "GoblinBarrel": {
        ("projectileData", "spawnCharacterDeployTime"): 1100,
        ("projectileData", "spawnConstPriority"): True,
    },
    "Log": {
        # The compact public payload omits this true boolean from the rolling
        # child. Native PushbackAll bypasses the ordinary mass immunity check.
        ("projectileData", "spawnProjectileData", "pushbackAll"): True,
    },
}


def _apply_nested_data_overrides(result: dict[str, Any]) -> None:
    """Patch every embedded character and projectile payload in-place."""
    stack: list[Any] = [result]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            value.update(
                _identity_fields(
                    CHARACTER_RUNTIME_TRAITS,
                    _CHARACTER_RUNTIME_TRAITS_CASEFOLD,
                    value.get("name"),
                )
            )
            value.update(
                _identity_fields(
                    CHARACTER_FIELD_OVERRIDES,
                    _CHARACTER_FIELD_OVERRIDES_CASEFOLD,
                    value.get("name"),
                )
            )
            value.update(
                _identity_fields(
                    PROJECTILE_FIELD_OVERRIDES,
                    _PROJECTILE_FIELD_OVERRIDES_CASEFOLD,
                    value.get("name"),
                )
            )
            if str(value.get("source", "")).startswith("area_effect_objects"):
                value.update(
                    _identity_fields(
                        AREA_EFFECT_FIELD_OVERRIDES,
                        _AREA_EFFECT_FIELD_OVERRIDES_CASEFOLD,
                        value.get("name"),
                    )
                )
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def apply_entry_overrides(
    entry: dict[str, Any],
    object_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    patches = ENTRY_PATH_OVERRIDES.get(str(entry.get("name", "")))
    result = normalize_entry(entry, object_registry)

    # Character and projectile changes must reach nested payloads as well as
    # ordinary deck troops (barrels, death spawns, spawners, and mixed swarms
    # all embed raw dictionaries at different paths).
    _apply_nested_data_overrides(result)

    for path, value in (patches or {}).items():
        target = result
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = value
    return result


def apply_character_overrides(name: str, character_data: dict[str, Any]) -> dict[str, Any]:
    """Return live raw character data for any direct or nested spawn source."""
    result = deepcopy(character_data)
    result.update(
        _identity_fields(
            CHARACTER_RUNTIME_TRAITS,
            _CHARACTER_RUNTIME_TRAITS_CASEFOLD,
            name,
        )
    )
    result.update(
        _identity_fields(
            CHARACTER_FIELD_OVERRIDES,
            _CHARACTER_FIELD_OVERRIDES_CASEFOLD,
            name,
        )
    )
    _apply_nested_data_overrides(result)
    return result


def tournament_stat(card_name: str, field: str) -> int | None:
    return TOURNAMENT_STAT_OVERRIDES.get(card_name, {}).get(field)


def tournament_spell_stat(spell_name: str, field: str) -> float | None:
    return TOURNAMENT_SPELL_OVERRIDES.get(spell_name, {}).get(field)


def tournament_tower_stat(tower_name: str, field: str) -> int | None:
    return TOURNAMENT_TOWER_STATS.get(tower_name, {}).get(field)
