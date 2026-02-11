from typing import List, Dict, Any
from ..card_types import Mechanic
from ..mechanics.shared import (
    DeathDamage, DeathSpawn, Shield, DamageRamp, FreezeDebuff, Stun,
    CrownTowerScaling, KnockbackOnHit, PeriodicSpawner
)
from ..mechanics.champion import SkeletonKingSoulCollector, ChampionAbilityMechanic, ActiveAbility
from ..cards import CARD_MECHANICS
from ..effects import (
    DirectDamage, ApplyStun, ApplySlow, PeriodicArea, ProjectileLaunch,
    SpawnUnits, ApplyBuff
)


def detect_mechanics_from_data(entry: Dict[str, Any]) -> List[Mechanic]:
    """Detect and create mechanics based on gamedata entry"""
    mechanics = []

    # Get character data (for troops/buildings)
    char_data = entry.get("summonCharacterData", {}) or entry.get("summonSpellData", {})

    # Death effects
    # DeathDamage directly on unit
    if char_data.get("deathDamage") and char_data.get("deathRadius"):
        death_damage = char_data.get("deathDamage", 0)
        death_radius = char_data.get("deathRadius", 0)
        pass  # print(f"[Detect] DeathDamage for {entry.get('name')} radius={death_radius} dmg={death_damage}")
        mechanics.append(DeathDamage(
            radius_tiles=death_radius / 1000.0,
            damage=death_damage
        ))

    # DeathSpawn into another unit (e.g., Golem, Balloon -> Bomb unit)
    if char_data.get("deathSpawnCharacterData"):
        spawn_data = char_data["deathSpawnCharacterData"]
        unit_name = spawn_data.get("name") or char_data.get("deathSpawnCharacter")
        count = char_data.get("deathSpawnCount", 1)
        if unit_name:
            pass  # print(f"[Detect] DeathSpawn for {entry.get('name')} -> {count}x {unit_name}")
            mechanics.append(DeathSpawn(
                unit_name=unit_name,
                count=count,
                radius_tiles=0.5,
                unit_data=spawn_data,
            ))

    # Shield mechanics
    if char_data.get("shieldHitpoints"):
        pass  # print(f"[Detect] Shield for {entry.get('name')} hp={char_data['shieldHitpoints']}")
        mechanics.append(Shield(
            shield_hp=char_data["shieldHitpoints"]
        ))

    # Damage ramp (Inferno Tower/Dragon)
    if (
        char_data.get("damageRampData")
        or entry.get("name") in ["InfernoTower", "InfernoDragon"]
        or char_data.get("variableDamage2") is not None
        or char_data.get("variableDamage3") is not None
    ):
        base_damage = char_data.get("damage", 0) or 0
        stage2 = char_data.get("variableDamage2", base_damage)
        stage3 = char_data.get("variableDamage3", stage2)
        stages = [
            (0, base_damage),
            (2000, stage2),
            (4000, stage3),
        ]

        pass  # print(f"[Detect] DamageRamp for {entry.get('name')}")
        mechanics.append(DamageRamp(
            stages=stages,
            per_target=True
        ))

    # Status effect mechanics
    if char_data.get("slowData"):
        slow_data = char_data["slowData"]
        mechanics.append(FreezeDebuff(
            radius_tiles=slow_data.get("radius", 0) / 1000.0,
            slow_multiplier=slow_data.get("multiplier", 0.5),
            aura_effect=True
        ))

    if char_data.get("stunChance"):
        mechanics.append(Stun(
            stun_duration_ms=char_data.get("stunDuration", 1000),
            stun_chance=char_data["stunChance"] / 100.0
        ))

    # Crown tower scaling (mostly for spells)
    if entry.get("crownTowerDamagePercent") is not None:
        pass  # print(f"[Detect] CrownTowerScaling for {entry.get('name')} scale={entry['crownTowerDamagePercent']}")
        # crownTowerDamagePercent is negative (e.g. -70 means 35% of normal damage)
        raw = entry["crownTowerDamagePercent"]
        multiplier = (100 + raw) / 100.0 if raw < 0 else raw / 100.0
        mechanics.append(CrownTowerScaling(
            damage_multiplier=multiplier
        ))

    # Knockback mechanics (Log, Bowler)
    if char_data.get("knockbackData") or entry.get("name") in ["Log", "Bowler"]:
        knockback_distance = 1.5 if entry.get("name") == "Log" else 1.0
        pass  # print(f"[Detect] KnockbackOnHit for {entry.get('name')}")
        mechanics.append(KnockbackOnHit(
            knockback_distance=knockback_distance,
            knockback_chance=1.0
        ))

    # Periodic spawning (Witch, Night Witch) – align to common JSON keys
    # Prefer direct fields spawnNumber/spawnPauseTime/spawnCharacterData on character data
    if char_data.get("spawnPauseTime") is not None and (
        char_data.get("spawnNumber") or char_data.get("spawnCharacterData")
    ):
        unit_name = (char_data.get("spawnCharacterData") or {}).get("name", "Skeleton")
        interval_ms = char_data.get("spawnPauseTime", 3000)
        count = char_data.get("spawnNumber", 1)

        pass  # print(f"[Detect] PeriodicSpawner for {entry.get('name')} unit={unit_name} interval={interval_ms} count={count}")
        mechanics.append(PeriodicSpawner(
            unit_name=unit_name,
            spawn_interval_ms=interval_ms,
            count=count,
            spawn_radius_tiles=1.5
        ))

    # Card-specific mechanics
    card_name = entry.get("name", "")
    if card_name in CARD_MECHANICS:
        for mechanic_class in CARD_MECHANICS[card_name]:
            mechanics.append(mechanic_class())

    # Champion mechanics
    if entry.get("rarity") == "Champion":
        if card_name == "SkeletonKing":
            from ..mechanics.champion.ability import ActiveAbility
            from ..effects.spawn import SpawnUnits

            # Create the ability for Skeleton King
            ability = ActiveAbility(
                name="Summon Skeletons",
                elixir_cost=3,
                cooldown_ms=15000,
                duration_ms=1000,
                effects=[
                    SpawnUnits(
                        unit_name="Skeleton",
                        count=15,
                        radius_tiles=2.0
                    )
                ]
            )

            mechanics.append(SkeletonKingSoulCollector(ability))
        # Add other champions here as needed

    return mechanics


def detect_effects_from_data(entry: Dict[str, Any]) -> List:
    """Detect and create effects for spell cards"""
    effects = []

    # Only process spell cards
    if entry.get("tidType") != "TID_CARD_TYPE_SPELL":
        return effects

    # Direct damage
    if entry.get("damage"):
        effects.append(DirectDamage(
            damage=entry["damage"],
            radius_tiles=entry.get("radius", 0) / 1000.0
        ))

    # Stun effects
    if entry.get("stunDuration"):
        effects.append(ApplyStun(
            duration_seconds=entry["stunDuration"] / 1000.0,
            radius_tiles=entry.get("radius", 0) / 1000.0
        ))

    # Slow effects
    if entry.get("slowData"):
        slow_data = entry["slowData"]
        effects.append(ApplySlow(
            duration_seconds=slow_data.get("duration", 3000) / 1000.0,
            slow_multiplier=slow_data.get("multiplier", 0.5),
            radius_tiles=entry.get("radius", 0) / 1000.0
        ))

    # Area effects (Poison, Tornado, etc.)
    if entry.get("areaEffectObjectData"):
        area_data = entry["areaEffectObjectData"]
        effects.append(PeriodicArea(
            damage_per_second=area_data.get("damagePerSecond", 0),
            duration_seconds=area_data.get("duration", 4000) / 1000.0,
            radius_tiles=area_data.get("radius", 3000) / 1000.0,
            freeze_effect=area_data.get("freezeEffect", False),
            pull_force=area_data.get("pullForce", 0.0)
        ))

    # Projectile effects
    if entry.get("projectileData"):
        projectile_data = entry["projectileData"]
        effects.append(ProjectileLaunch(
            damage=projectile_data.get("damage", entry.get("damage", 0)),
            travel_speed=projectile_data.get("speed", 500) / 60.0,  # Convert to tiles/sec
            splash_radius_tiles=projectile_data.get("radius", 0) / 1000.0
        ))

    # Spawn effects (Goblin Barrel, etc.)
    if entry.get("summonCharacterData") and entry.get("summonNumber"):
        summon_data = entry["summonCharacterData"]
        effects.append(SpawnUnits(
            unit_name=summon_data.get("name", "Goblin"),
            count=entry["summonNumber"],
            radius_tiles=entry.get("summonRadius", 1000) / 1000.0,
            unit_data=summon_data
        ))

    # Buff effects (Rage)
    if entry.get("buffData"):
        buff_data = entry["buffData"]
        effects.append(ApplyBuff(
            duration_seconds=buff_data.get("duration", 3000) / 1000.0,
            speed_multiplier=buff_data.get("speedMultiplier", 1.5),
            damage_multiplier=buff_data.get("damageMultiplier", 1.4),
            radius_tiles=buff_data.get("radius", 3000) / 1000.0
        ))

    return effects
