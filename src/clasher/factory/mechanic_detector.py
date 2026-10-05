from typing import List, Dict, Any
from ..card_types import Mechanic
from ..mechanics.shared import (
    DeathDamage, DeathSpawn, Shield, DamageRamp, FreezeDebuff, Stun,
    CrownTowerScaling, KnockbackOnHit, PeriodicSpawner, SpawnAreaEffect,
    DeathAreaEffect, MultipleTargetAttack, SerializedOnHitBuff, SpawnPushback,
)
from ..mechanics.champion import SkeletonKingSoulCollector, ChampionAbilityMechanic, ActiveAbility
from ..cards import (
    AttackRecoil,
    ArcherQueenCloak,
    BanditDash,
    BattleRamCharge,
    CARD_MECHANICS,
    ElectroDragonChainLightning,
    ElectroSpiritChain,
    HideWhenIdle,
    IceSpiritFreeze,
    InvisibilityWhenNotAttacking,
    MegaKnightSlam,
    UndergroundDeployment,
    WallBreakersDemolition,
)
from ..effects import (
    DirectDamage, ApplyStun, ApplySlow, PeriodicArea, ProjectileLaunch,
    SpawnUnits, ApplyBuff
)
from ..kinematics import logic_speed_to_tiles_per_second
from ..gamedata_normalization import serialized_hit_planes

DEBUG_DETECT = False


def detect_mechanics_from_data(entry: Dict[str, Any]) -> List[Mechanic]:
    """Detect and create mechanics based on gamedata entry"""
    mechanics = []

    # Get character data (for troops/buildings)
    char_data = entry.get("summonCharacterData", {}) or entry.get("summonSpellData", {})

    if char_data.get("spawnAreaObjectData"):
        mechanics.append(SpawnAreaEffect(area_data=char_data["spawnAreaObjectData"]))

    # Death effects
    # DeathDamage directly on unit
    if char_data.get("deathDamage"):
        death_damage = char_data.get("deathDamage", 0)
        death_area = char_data.get("deathAreaEffectData") or {}
        hits_air, hits_ground = serialized_hit_planes(death_area)
        # The game client uses a 2-tile character death-nova default when the
        # serialized character omits an explicit radius (Golem/Golemite).
        death_radius = (
            char_data.get("deathDamageRadius")
            or char_data.get("deathRadius")
            or death_area.get("radius")
            or 2000
        )
        if DEBUG_DETECT:
            print(f"[Detect] DeathDamage for {entry.get('name')} radius={death_radius} dmg={death_damage}")
        mechanics.append(DeathDamage(
            radius_tiles=death_radius / 1000.0,
            damage=death_damage,
            knockback_distance=float(char_data.get("deathPushback", 0) or 0) / 1000.0,
            hits_air=hits_air,
            hits_ground=hits_ground,
        ))

    # DeathSpawn into another unit (e.g., Golem, Balloon -> Bomb unit)
    if char_data.get("deathSpawnCharacterData"):
        spawn_data = char_data["deathSpawnCharacterData"]
        unit_name = spawn_data.get("name") or char_data.get("deathSpawnCharacter")
        count = char_data.get("deathSpawnCount", 1)
        # Some serialized "characters" are only delayed effect containers.
        # They have no hitpoints and resolve a death-area payload (for example
        # Lumberjack's Rage bottle), so materializing them as combat troops is
        # invalid. Their owning card/effect mechanic handles the payload.
        effect_only_container = bool(
            not spawn_data.get("hitpoints")
            and spawn_data.get("deathAreaEffectData")
            and spawn_data.get("deathDamage") is None
        )
        if unit_name and not effect_only_container:
            if DEBUG_DETECT:
                print(f"[Detect] DeathSpawn for {entry.get('name')} -> {count}x {unit_name}")
            mechanics.append(DeathSpawn(
                unit_name=unit_name,
                count=count,
                radius_tiles=float(char_data.get("deathSpawnRadius", 0) or 0) / 1000.0,
                min_radius_tiles=float(
                    char_data.get("deathSpawnMinRadius", 0) or 0
                ) / 1000.0,
                radial_pushback=bool(char_data.get("deathSpawnPushback", False)),
                spawn_const_priority=bool(
                    char_data.get("spawnConstPriority", False)
                ),
                deploy_time_ms=int(char_data.get("deathSpawnDeployTime", 0) or 0),
                unit_data=spawn_data,
            ))

    # DeathAreaEffect is a separate native object path. It may be a direct
    # field (Ice Golem) or a dummy action that creates a delayed container
    # whose own death creates the real field (Lumberjack).
    if char_data.get("deathAreaEffectData"):
        mechanics.append(
            DeathAreaEffect(area_data=char_data["deathAreaEffectData"])
        )

    # Shield mechanics
    if char_data.get("shieldHitpoints"):
        if DEBUG_DETECT:
            print(f"[Detect] Shield for {entry.get('name')} hp={char_data['shieldHitpoints']}")
        mechanics.append(Shield(
            shield_hp=char_data["shieldHitpoints"]
        ))

    # Serialized multi-stage damage ramp.
    if (
        char_data.get("damageRampData")
        or char_data.get("variableDamage2") is not None
        or char_data.get("variableDamage3") is not None
    ):
        base_damage = char_data.get("damage", 0) or 0
        stage2 = char_data.get("variableDamage2", base_damage)
        stage3 = char_data.get("variableDamage3", stage2)
        stage2_time = int(char_data.get("variableDamageTime1", 2000) or 0)
        stage3_time = stage2_time + int(
            char_data.get("variableDamageTime2", 2000) or 0
        )
        stages = [
            (0, base_damage),
            (stage2_time, stage2),
            (stage3_time, stage3),
        ]

        if DEBUG_DETECT:
            print(f"[Detect] DamageRamp for {entry.get('name')}")
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

    if int(char_data.get("multipleTargets", 0) or 0) > 1:
        mechanics.append(MultipleTargetAttack())

    if char_data.get("buffOnDamageData") and int(
        char_data.get("buffOnDamageTime", 0) or 0
    ) > 0:
        mechanics.append(SerializedOnHitBuff())

    # Crown tower scaling can live on either the card or its character payload.
    crown_tower_damage_percent = entry.get("crownTowerDamagePercent")
    if crown_tower_damage_percent is None:
        crown_tower_damage_percent = char_data.get("crownTowerDamagePercent")
    if crown_tower_damage_percent is not None:
        if DEBUG_DETECT:
            print(f"[Detect] CrownTowerScaling for {entry.get('name')} scale={crown_tower_damage_percent}")
        from ..balance import tournament_stat

        mechanics.append(CrownTowerScaling(
            damage_multiplier=max(0.0, 1.0 + crown_tower_damage_percent / 100.0),
            crown_tower_damage=tournament_stat(
                str(entry.get("name", "")), "crown_tower_damage"
            ),
        ))

    # Direct character knockback actions. Projectile pushback is decoded from
    # its own payload when the projectile is created, including PushbackAll.
    knockback_data = char_data.get("knockbackData") or {}
    if knockback_data:
        knockback_distance = float(
            knockback_data.get("pushback", 1000) or 0
        ) / 1000.0
        if DEBUG_DETECT:
            print(f"[Detect] KnockbackOnHit for {entry.get('name')}")
        mechanics.append(KnockbackOnHit(
            knockback_distance=knockback_distance,
            knockback_chance=1.0,
            ignores_mass=bool(knockback_data.get("pushbackAll", False)),
        ))

    # Periodic spawning (Witch, Night Witch) – align to common JSON keys
    # Prefer direct fields spawnNumber/spawnPauseTime/spawnCharacterData on character data
    if char_data.get("spawnPauseTime") is not None and (
        char_data.get("spawnNumber") or char_data.get("spawnCharacterData")
    ):
        spawn_data = char_data.get("spawnCharacterData") or {}
        unit_name = spawn_data.get("name", "Skeleton")
        interval_ms = char_data.get("spawnPauseTime", 3000)
        count = char_data.get("spawnNumber", 1)
        configured_start_ms = int(char_data.get("spawnStartTime", 0) or 0)
        raw_spawn_radius = char_data.get("spawnRadius")
        spawn_radius_tiles = (
            0.0
            if raw_spawn_radius is None
            else float(raw_spawn_radius) / 1000.0
        )

        if DEBUG_DETECT:
            print(f"[Detect] PeriodicSpawner for {entry.get('name')} unit={unit_name} interval={interval_ms} count={count}")
        mechanics.append(PeriodicSpawner(
            unit_name=unit_name,
            spawn_interval_ms=interval_ms,
            # Character spawners have the standard one-second first wave.
            # Buildings use their serialized production cadence for the first
            # wave as well: deployment and production are separate clocks
            # (notably Tombstone deploys for 1 s, then takes 3.5 s to produce
            # its first pair).
            first_spawn_delay_ms=(
                configured_start_ms
                or (
                    interval_ms
                    if entry.get("tidType") == "TID_CARD_TYPE_BUILDING"
                    else 1000
                )
            ),
            # The native spawner emits at most one member per 50 ms logic
            # frame even when SpawnInterval is zero.
            intra_spawn_interval_ms=(
                max(50, int(char_data.get("spawnInterval", 0) or 0))
                if count > 1
                else 0
            ),
            count=count,
            spawn_with_deploy=bool(char_data.get("spawnCharacterWithDeploy", False)),
            spawn_angle_shift_degrees=float(char_data.get("spawnAngleShift", 0) or 0),
            spawn_radius_tiles=spawn_radius_tiles,
            unit_data=spawn_data or None,
        ))

    if char_data.get("manaGenerateTimeMs"):
        from ..cards.elixir_collector import ElixirProduction

        mechanics.append(ElixirProduction())

    if bool(char_data.get("hidesWhenNotAttacking", False)):
        mechanics.append(HideWhenIdle())

    if float(char_data.get("attackPushback", 0) or 0) > 0:
        mechanics.append(AttackRecoil())

    inactivity_buff = char_data.get("buffWhenNotAttackingData", {}) or {}
    if (
        "invisibility"
        in str(inactivity_buff.get("name", "")).casefold()
        and int(char_data.get("buffWhenNotAttackingTime", 0) or 0) > 0
    ):
        mechanics.append(InvisibilityWhenNotAttacking())

    if (
        float(char_data.get("dashMinRange", 0) or 0) > 0
        and float(char_data.get("dashMaxRange", 0) or 0) > 0
    ):
        if (
            int(char_data.get("dashConstantTime", 0) or 0) > 0
            or float(char_data.get("dashRadius", 0) or 0) > 0
        ):
            mechanics.append(MegaKnightSlam())
        else:
            mechanics.append(BanditDash())

    spawn_pushback = float(char_data.get("spawnPushback", 0) or 0)
    spawn_pushback_radius = float(
        char_data.get("spawnPushbackRadius", 0) or 0
    )
    if spawn_pushback > 0 and spawn_pushback_radius > 0:
        mechanics.append(
            SpawnPushback(
                distance_tiles=spawn_pushback / 1000.0,
                radius_tiles=spawn_pushback_radius / 1000.0,
                hits_air=bool(char_data.get("attacksAir", False)),
                hits_ground=bool(char_data.get("attacksGround", True)),
            )
        )

    projectile_data = char_data.get("projectileData", {}) or {}
    chained_hit_count = int(
        projectile_data.get("chainedHitCount", 0) or 0
    )
    is_kamikaze = bool(char_data.get("kamikaze", False))
    if chained_hit_count > 1:
        mechanics.append(
            ElectroSpiritChain()
            if is_kamikaze
            else ElectroDragonChainLightning()
        )
    elif is_kamikaze:
        target_buff = projectile_data.get("targetBuffData", {}) or {}
        target_buff_name = str(target_buff.get("name", "")).casefold()
        if (
            "freeze" in target_buff_name
            and float(projectile_data.get("radius", 0) or 0) > 0
        ):
            mechanics.append(IceSpiritFreeze())
        elif (
            int(char_data.get("deathSpawnCount", 0) or 0) > 0
            and char_data.get("deathSpawnCharacterData")
        ):
            mechanics.append(BattleRamCharge())
        elif (
            float(char_data.get("areaDamageRadius", 0) or 0) > 0
            and float(projectile_data.get("radius", 0) or 0) > 0
        ):
            mechanics.append(WallBreakersDemolition())
        elif (
            (projectile_data.get("spawnAreaEffectObjectData", {}) or {})
            .get("buffData", {}) or {}
        ).get("healPerSecond"):
            # Heal Spirit: splash on impact, then heals own troops.
            from ..cards.kamikaze_spirits import HealSpiritBurst

            mechanics.append(HealSpiritBurst())
        elif float(projectile_data.get("radius", 0) or 0) > 0:
            # Fire Spirit: a kamikaze self-projectile with plain splash.
            from ..cards.kamikaze_spirits import KamikazeSplash

            mechanics.append(KamikazeSplash())

    ability_data = char_data.get("abilityData", {}) or {}
    ability_name = str(ability_data.get("name", "")).casefold()
    if ability_name == "mightyminerlaneswitch":
        from ..cards.c56_champions import MightyMinerSwitch

        mechanics.append(MightyMinerSwitch())
    elif ability_name == "goblinstein_ability":
        from ..cards.c56_champions import GoblinsteinTether

        mechanics.append(GoblinsteinTether())
    if (
        "invisibility"
        in str(ability_data.get("tid", "")).casefold()
        and ability_data.get("buffData")
    ):
        mechanics.append(ArcherQueenCloak())

    if float(char_data.get("spawnPathfindSpeed", 0) or 0) > 0:
        mechanics.append(UndergroundDeployment())

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
            attract_percentage=area_data.get("attractPercentage", 0.0),
            push_speed_factor=area_data.get("pushSpeedFactor", 0.0),
        ))

    # Projectile effects
    if entry.get("projectileData"):
        projectile_data = entry["projectileData"]
        effects.append(ProjectileLaunch(
            damage=projectile_data.get("damage", entry.get("damage", 0)),
            travel_speed=logic_speed_to_tiles_per_second(
                projectile_data.get("speed", 500)
            ),
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
