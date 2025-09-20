## Clash Royale Card Data Model (Compositional, Flag-less)

### Goals
- Avoid boolean hasX flags; presence of components implies capability
- Reuse common mechanics across cards; isolate unique mechanics per card
- Single-use mechanics live inside that card’s class/module; only promote to shared when used by 2+ cards
- Separate Troop / Building / Spell concerns cleanly
- Data-driven from gamedata (tiles preferred; convert from game units)

### Conventions
- Distances in tiles (1 tile = 1000 game units)
- Times in milliseconds unless stated otherwise
- Ranges are attack ranges; sight ranges are separate

### Core Types (Python, data-oriented)
```python
from dataclasses import dataclass, field
from typing import Optional, Sequence, Protocol, Literal, Callable, Any

CardKind = Literal["troop", "building", "spell", "champion"]
Rarity = Literal["Common", "Rare", "Epic", "Legendary", "Champion"]

@dataclass(frozen=True)
class BaseStats:
    # Common numeric stats (used where applicable)
    hitpoints: Optional[int] = None
    damage: Optional[int] = None
    range_tiles: Optional[float] = None
    hit_speed_ms: Optional[int] = None
    sight_range_tiles: Optional[float] = None
    collision_radius_tiles: Optional[float] = None

@dataclass(frozen=True)
class TroopStats(BaseStats):
    # Movement and targeting for troops only
    speed_tiles_per_min: Optional[int] = None
    deploy_time_ms: Optional[int] = 1000
    load_time_ms: Optional[int] = None
    summon_count: Optional[int] = None

@dataclass(frozen=True)
class BuildingStats(BaseStats):
    # Buildings can have finite lifetime
    lifetime_ms: Optional[int] = None
    deploy_time_ms: Optional[int] = 1000
    load_time_ms: Optional[int] = None

@dataclass(frozen=True)
class SpellStats:
    # Spells have no HP; durations are on effects, not card-level lifetime
    radius_tiles: Optional[float] = None
    duration_ms: Optional[int] = None
    crown_tower_damage_scale: Optional[float] = None  # e.g., 0.27 for 27%

# Behavior contracts (implemented by pluggable strategies)
class TargetingBehavior(Protocol):
    def can_target_air(self) -> bool: ...
    def can_target_ground(self) -> bool: ...
    def buildings_only(self) -> bool: ...

class MovementBehavior(Protocol):
    def update(self, entity: Any, dt_ms: int) -> None: ...

class AttackBehavior(Protocol):
    def maybe_attack(self, entity: Any, dt_ms: int) -> None: ...

# Mechanics are modular components attached to entities (troops/buildings) with lifecycle hooks
class Mechanic(Protocol):
    def on_attach(self, entity: Any) -> None: ...
    def on_spawn(self, entity: Any) -> None: ...
    def on_tick(self, entity: Any, dt_ms: int) -> None: ...
    def on_attack_start(self, entity: Any, target: Any) -> None: ...
    def on_attack_hit(self, entity: Any, target: Any) -> None: ...
    def on_death(self, entity: Any) -> None: ...

# Spell effects are actions executed at cast-time or over time
class Effect(Protocol):
    def apply(self, context: Any) -> None: ...

@dataclass(frozen=True)
class CardDefinition:
    id: int
    name: str
    kind: CardKind
    rarity: Rarity
    elixir: int
    
    # Exactly one of these is populated based on kind
    troop_stats: Optional[TroopStats] = None
    building_stats: Optional[BuildingStats] = None
    spell_stats: Optional[SpellStats] = None

    # Composition
    targeting: Optional[TargetingBehavior] = None
    movement: Optional[MovementBehavior] = None
    attack: Optional[AttackBehavior] = None
    mechanics: Sequence[Mechanic] = field(default_factory=tuple)

    # Spells only: list of Effects executed at cast-time or via area objects
    effects: Sequence[Effect] = field(default_factory=tuple)

    # Lightweight classification for queries/filters (e.g., {"air_unit", "ranged"})
    tags: frozenset[str] = frozenset()
```

### Reusable Mechanics Library (shared-only; promote only when reused ≥ 2 cards)
- DeathDamage(radius_tiles, damage)
- DeathSpawn(unit_name, count, formation: Callable[..., list[tuple[float,float]]])
- KnockbackOnHit(pushback_units)
- CrownTowerScaling(scale: float)
- DamageRamp(stages: list[tuple[int, int]], per_target: bool)  // Inferno Tower, Inferno Dragon
- Shield(shield_hp)                                            // Dark Prince, Guards
- PeriodicSpawner(unit_name, interval_ms, count)               // Huts, Furnace
- FreezeDebuff(duration_ms)                                    // Freeze
- Stun(duration_ms)                                            // Zap / Lightning

### Card-Specific Mechanics Pattern (single-use)
Single-use mechanics are implemented in the card’s own module and not added to the shared library. Examples:
- SparkyChargeUp(charge_ms, reset_on_stun)
- HogRiderJump(jump_speed, jump_height, bridge_only)
- PrincessVolleyPattern(count, first_proj, deco_proj)
- MagicArcherPierce(max_pierce, falloff)
- SkeletonKingSoulCollector()
- LightningTargetPicker(max_targets=3, priority="highest_hitpoints")
- ElixirCollectorProduction(interval_ms, amount, death_bonus)
- WallBreakersKamikaze(radius_tiles, damage)                    # suicide on hit
- IceSpiritFreeze(duration_ms, radius_tiles)                    # self-detonate + freeze
- RocketPushback(pushback_units)                                # heavy pushback on impact
- GoblinCageOnDeathSpawn(unit_name="GoblinBrawler")            # building → troop spawn
- SkeletonArmyScatter(count=15, formation="scatter")            # large swarm scatter
- MinionHordeFormation(count=6, formation="cluster")           # multi-unit formation offsets
- SkeletonDragonsDuoSpawn(count=2)                              # dual air spawn
- MagicArcherPierceLine(max_pierce, falloff)                    # line pierce logic
- SpiritEmpressDualForm(elixir_thresholds=(3,6))                # form based on elixir

Pattern:
```python
# cards/sparky.py
class SparkyChargeUp(Mechanic):
    def on_tick(self, entity, dt_ms: int) -> None: ...
    def on_attack_start(self, entity, target) -> None: ...

def build_sparky(entry: dict) -> list[Mechanic]:
    return [SparkyChargeUp(charge_ms=entry.get("loadTime", 3000), reset_on_stun=True)]
```

### Spell Effect Primitives
- DirectDamage(radius_tiles, damage)
- ApplyStun(duration_ms)
- ApplySlow(percent, duration_ms)
- PeriodicArea(duration_ms, tick_ms, radius_tiles, on_tick: Effect)
- ProjectileLaunch(name, speed_tiles_per_s, on_impact: Effect)
- SpawnUnits(unit_name, count, formation)
- ApplyBuff(buff_name, params)

### Mechanics Taxonomy (from reports/cards)
- Targeting:
  - Buildings-only, Air+Ground, Ground-only, Priorities (troop > building)
- Movement:
  - Ground, Air (bridge ignoring), Jumping (river-only), Charge, Dash (with i-frames), Teleport, Hover (river ignore for ground-like units)
  - Burrow/Underground travel and anywhere deployment (Miner, Goblin Drill)
- Attacks:
  - Melee, Projectile, Beam, Pierce line, Chain lightning, Multi-projectile volley, Boomerang (out-and-back), Shotgun spread with distance falloff
  - Rolling projectile with two-phase behavior (Log/Barbarian Barrel/Bowler)
- On-death/On-hit:
  - DeathDamage, DeathSpawn, Kamikaze explode, Freeze on hit, Rage-on-death aura, Deploy-on-death bombs, Death chains (multi-stage spawns)
- Temporal scaling/buffs:
  - Damage ramp (per-target), Charge-up, Stun/Freeze/Slow, Aura debuff
  - Snare (severe speed reduction), Reflect/Deflect projectiles (temporary), Invisibility-after-idle
- Spawners/Periodic:
  - PeriodicSpawner (huts), Troop periodic spawns (Witch/Night Witch), Elixir generation (collector)
- Multi-summon formations:
  - Triangle/cluster/line/scatter/hexagon (Minions/Minion Horde/Skeleton Army/Skeleton Dragons/Goblin Gang)
- Champion abilities:
  - Active ability with cost+cooldown (AQ, GK, Monk, SK, Little Prince, Boss Bandit), per-card logic
  
### Additional Shared Effects/Utilities
- Knockback(pushback_units) with directional control
- Pull(towards_point, strength) for Tornado-like effects
- HookPull(towards_unit, min_range, max_range, cooldown_ms) for Fisherman
- TopNTargetSelection(n, priority) for Lightning
- MultiWaveProjectile(waves, interval_ms, projectiles_per_wave) for Arrows
- RecoilMovement(distance_tiles) for Firecracker
- Transformation(health_threshold_percent, into_entity) for Cannon Cart, Goblin Demolisher
- RebirthChain([entity1, entity2, ...], timings_ms) for Phoenix
- MixedSummon(primary, secondary, counts, formation) for Goblin Gang, Rascals
- CarryingCompanions(spawn_on_summon) for Goblin Giant

### Factory: From gamedata to CardDefinition (sketch)
```python
def card_from_gamedata(entry: dict) -> CardDefinition:
    name = entry["name"]
    kind: CardKind = entry["kind"]  # "troop"|"building"|"spell"|"champion"
    rarity: Rarity = entry["rarity"]
    elixir = entry["manaCost"]

    mechanics: list[Mechanic] = []
    effects: list[Effect] = []

    # Stats
    troop_stats = building_stats = spell_stats = None
    if kind in ("troop", "champion"):
        troop_stats = TroopStats(
            hitpoints=entry.get("hitpoints"),
            damage=entry.get("damage"),
            range_tiles=(entry.get("range", 0) / 1000) if entry.get("range") else None,
            hit_speed_ms=entry.get("hitSpeed"),
            sight_range_tiles=(entry.get("sightRange", 0) / 1000) if entry.get("sightRange") else None,
            collision_radius_tiles=(entry.get("collisionRadius", 0) / 1000) if entry.get("collisionRadius") else None,
            speed_tiles_per_min=entry.get("speed"),
            deploy_time_ms=entry.get("deployTime", 1000),
            load_time_ms=entry.get("loadTime"),
            summon_count=entry.get("summonNumber"),
        )
    elif kind == "building":
        building_stats = BuildingStats(
            hitpoints=entry.get("hitpoints"),
            damage=entry.get("damage"),
            range_tiles=(entry.get("range", 0) / 1000) if entry.get("range") else None,
            hit_speed_ms=entry.get("hitSpeed"),
            sight_range_tiles=(entry.get("sightRange", 0) / 1000) if entry.get("sightRange") else None,
            collision_radius_tiles=(entry.get("collisionRadius", 0) / 1000) if entry.get("collisionRadius") else None,
            lifetime_ms=entry.get("lifeTime"),
            deploy_time_ms=entry.get("deployTime", 1000),
            load_time_ms=entry.get("loadTime"),
        )
    elif kind == "spell":
        spell_stats = SpellStats(
            radius_tiles=(entry.get("radius", 0) / 1000) if entry.get("radius") else None,
            duration_ms=entry.get("lifeDuration"),
            crown_tower_damage_scale=(1.0 + (entry.get("crownTowerDamagePercent", 0) / 100.0)) if entry.get("crownTowerDamagePercent") else None,
        )

    # Mechanics driven by fields
    if entry.get("deathDamage"):
        mechanics.append(DeathDamage(radius_tiles=(entry.get("deathRadius", 0)/1000),
                                     damage=entry["deathDamage"]))
    if entry.get("deathSpawnCount"):
        mechanics.append(DeathSpawn(unit_name=entry["deathSpawnCharacter"],
                                    count=entry["deathSpawnCount"],
                                    formation=lambda c: [(0,0)]*c))
    if entry.get("variableDamage3"):
        mechanics.append(DamageRamp(stages=[(0, entry.get("variableDamage1", 0)),
                                            (1000, entry.get("variableDamage2", 0)),
                                            (3000, entry.get("variableDamage3", 0))],
                                    per_target=True))
    if entry.get("jumpSpeed"):
        mechanics.append(JumpMovement(jump_speed=entry["jumpSpeed"],
                                      jump_height=entry.get("jumpHeight", 0),
                                      bridge_only=True))
    if entry.get("shieldHitpoints"):
        mechanics.append(Shield(shield_hp=entry["shieldHitpoints"]))

    # Spells
    proj = entry.get("projectileData")
    if kind == "spell" and proj:
        # Projectile spell with on-impact damage
        effects.append(ProjectileLaunch(
            name=proj["name"],
            speed_tiles_per_s=proj["speed"]/100.0,  # if speed in tiles/min or units, adapt
            on_impact=DirectDamage(radius_tiles=(proj.get("radius", 0)/1000) if proj.get("radius") else 0,
                                   damage=proj.get("damage", 0)),
        ))
    if kind == "spell" and entry.get("lifeDuration"):
        # Periodic area spell (e.g., Poison/Freeze)
        tick = entry.get("hitFrequency", 1000)
        per_tick_damage = entry.get("damagePerSecond", 0)
        on_tick = DirectDamage(radius_tiles=(entry.get("radius", 0)/1000) if entry.get("radius") else 0,
                               damage=per_tick_damage)
        effects.append(PeriodicArea(duration_ms=entry["lifeDuration"],
                                    tick_ms=tick,
                                    radius_tiles=(entry.get("radius", 0)/1000) if entry.get("radius") else 0,
                                    on_tick=on_tick))

    # Card-specific (single-use) mechanics, attached by card name/id
    mechanics.extend(apply_card_specific_mechanics(entry))

    # Targeting / movement / attack behaviors are selected based on flags
    targeting = build_targeting(entry)  # e.g., BuildingsOnlyTargeting if tidTarget == buildings
    movement = build_movement(entry)    # GroundMovement / AirMovement / JumpMovement already in mechanics
    attack = build_attack(entry)        # MeleeAttack / ProjectileAttack

    return CardDefinition(
        id=entry["id"],
        name=name,
        kind=kind,
        rarity=rarity,
        elixir=elixir,
        troop_stats=troop_stats,
        building_stats=building_stats,
        spell_stats=spell_stats,
        targeting=targeting,
        movement=movement,
        attack=attack,
        mechanics=tuple(mechanics),
        effects=tuple(effects),
        tags=frozenset(derive_tags(entry)),
    )
```

### Example Mappings

#### Giant (Troop)
```python
CardDefinition(
    id=26000001,
    name="Giant",
    kind="troop",
    rarity="Rare",
    elixir=5,
    troop_stats=TroopStats(hitpoints=1598, damage=99, range_tiles=1.2, hit_speed_ms=1500,
                           sight_range_tiles=7.5, speed_tiles_per_min=45,
                           collision_radius_tiles=0.75),
    targeting=BuildingsOnlyTargeting(),
    movement=GroundMovement(),
    attack=MeleeAttack(),
    mechanics=(),
    tags=frozenset({"ground", "melee", "building_target"}),
)
```

#### Poison (Spell – periodic area)
```python
CardDefinition(
    id=28000003,
    name="Poison",
    kind="spell",
    rarity="Epic",
    elixir=4,
    spell_stats=SpellStats(radius_tiles=3.5, duration_ms=8000, crown_tower_damage_scale=0.25),
    effects=(
        PeriodicArea(duration_ms=8000, tick_ms=1000, radius_tiles=3.5,
                      on_tick=DirectDamage(radius_tiles=3.5, damage=36)),
        PoisonDebuff(radius_tiles=3.5, speed_mult=0.85, hit_speed_mult=0.85),  # card-specific
    ),
    tags=frozenset({"area", "damage_over_time"}),
)
```

#### Inferno Tower (Building – per-target damage ramp)
```python
CardDefinition(
    id=27000003,
    name="Inferno Tower",
    kind="building",
    rarity="Rare",
    elixir=5,
    building_stats=BuildingStats(hitpoints=683, range_tiles=6.0, hit_speed_ms=400, lifetime_ms=30000),
    targeting=AirAndGroundTargeting(),
    attack=BeamAttack(),
    mechanics=(DamageRamp(stages=[(0, 20), (1000, 62), (3000, 331)], per_target=True),),
    tags=frozenset({"defense", "ramp_damage"}),
)
```

#### Hog Rider (Troop – jumping)
```python
CardDefinition(
    id=26000021,
    name="Hog Rider",
    kind="troop",
    rarity="Rare",
    elixir=4,
    troop_stats=TroopStats(hitpoints=800, damage=148, range_tiles=0.8, hit_speed_ms=1600,
                           sight_range_tiles=9.5, speed_tiles_per_min=120,
                           collision_radius_tiles=0.6),
    targeting=BuildingsOnlyTargeting(),
    movement=GroundMovement(),
    attack=MeleeAttack(),
    mechanics=(HogRiderJump(jump_speed=160, jump_height=4.0, bridge_only=True),),  # card-specific
    tags=frozenset({"ground", "melee", "jump"}),
)
```

#### Sparky (Troop – charge-up, reset on stun)
```python
CardDefinition(
    id=26000033,
    name="Sparky",
    kind="troop",
    rarity="Legendary",
    elixir=6,
    troop_stats=TroopStats(hitpoints=567, damage=520, range_tiles=5.0, hit_speed_ms=4000,
                           sight_range_tiles=5.0, speed_tiles_per_min=45,
                           collision_radius_tiles=0.8),
    targeting=GroundOnlyTargeting(),
    movement=GroundMovement(),
    attack=ProjectileAttack(projectile_name="ZapMachineProjectile", splash_radius_tiles=1.8),
    mechanics=(SparkyChargeUp(charge_ms=3000, reset_on_stun=True),),  # card-specific
    tags=frozenset({"ranged", "charge_up"}),
)
```

#### Skeleton King (Champion – active ability + soul collection)
```python
CardDefinition(
    id=26000069,
    name="Skeleton King",
    kind="champion",
    rarity="Champion",
    elixir=4,
    troop_stats=TroopStats(hitpoints=898, damage=80, range_tiles=1.2, hit_speed_ms=1600,
                           sight_range_tiles=5.5, speed_tiles_per_min=60,
                           collision_radius_tiles=1.0),
    targeting=GroundOnlyTargeting(),
    movement=GroundMovement(),
    attack=MeleeAttack(),
    mechanics=(
        SkeletonKingSoulCollector(),  # card-specific
        ActiveAbility(
            name="Soul Summoning",
            elixir_cost=2,
            cooldown_ms=20000,
            effect=SpawnUnits("Skeleton", count=6, formation=lambda c: [(0,0)]*c),
        ),
    ),
    tags=frozenset({"champion", "active_ability"}),
)
```

### Design Notes
- No booleans are required; attach Mechanics/Effects as needed
- Lifetime is exclusive to buildings; spells use effect.duration; troops persist until death
- Targeting, Movement, Attack behaviors remain small, swappable strategies
- Champion abilities reuse the same Effect primitives via an ActiveAbility mechanic; the ability’s unique logic stays card-specific
- Use tags only for coarse classification; do not infer behavior from tags
- Promotion rule: implement mechanics card-locally first; when another card needs the same mechanic, extract into the shared library

### Suggested Module Layout
- cards/<card_name>.py: card-specific builders and single-use mechanics
- mechanics/shared/: reusable mechanics (DeathDamage, DamageRamp, Shield, etc.)
- effects/: spell effect primitives (DirectDamage, PeriodicArea, Stun, Freeze)
- factory/card_factory.py: reads gamedata and assembles CardDefinition, calling per-card builders

### Integration Hooks (engine-facing)
- Entities own: targeting, movement, attack, mechanics[]
- Engine calls: on_spawn → per-tick on_tick → on_attack_start/on_attack_hit → on_death
- Spell cast creates either immediate Effects or persistent area objects that tick
- Factory converts gamedata units → tiles/ms and assembles components

### Testing Checklist
- Validate DamageRamp per-target tracking (Inferno Tower switching)
- Verify JumpMovement clears path constraints (Hog over river)
- Ensure ChargeUp resets on stun/knockback (Sparky)
- Confirm CrownTowerScaling applies only to towers
- PeriodicArea tick accuracy and stacking rules (Poison vs Freeze)

### Mechanics: Detection and Card Mapping (from gamedata.json)

Shared mechanics (cards → detection keys):
- Building-only targeting: Giant, Golem, Royal Giant, Hog Rider, Ram Rider (Ram), Royal Hogs, Lava Hound, Battle Ram, Ice Golem
  - Detect: tidTarget == "TID_TARGETS_BUILDINGS"
- Jumping: Hog Rider, Prince, Dark Prince, Ram Rider, Royal Hogs, Mega Knight
  - Detect: jumpHeight, jumpSpeed
- Charge/Dash: Prince, Dark Prince, Battle Ram, Ram Rider (Ram), Bandit, Golden Knight, Mega Knight, Elite Barbarians
  - Detect: chargeRange + damageSpecial and/or dashMinRange, dashMaxRange, jumpSpeed
- Kamikaze: Wall Breakers, Fire Spirit, Ice Spirit, Skeleton Barrel (barrel), Goblin Demolisher (kamikaze form)
  - Detect: kamikaze: true; often paired with deathDamage
- Death spawn: Goblin Cage, Lava Hound, Golem, Tombstone, Night Witch, Witch, Royal Delivery, Goblin Drill, Balloon, Giant Skeleton, Elixir Golem, Skeleton Barrel, Barbarian Hut
  - Detect: deathSpawnCount, deathSpawnCharacterData (chains for multi-stage)
- Death area damage/bomb: Giant Skeleton, Balloon, Bomb Tower, Ice Golem, Phoenix
  - Detect: deathDamage, deathAreaEffectData, collisionRadius
- Crown tower scaling: Fireball, Rocket, Poison, Giant Snowball, The Log, Lightning, Phoenix fireball, others
  - Detect: crownTowerDamagePercent
- Knockback/Pushback: Fireball, Rocket, The Log, Giant Snowball, Bowler, Mega Knight, Goblin Demolisher
  - Detect: pushback (projectile/area), radiusY for log-shaped hitboxes
- Stun/ZapFreeze: Zappies, Electro Wizard, Electro Dragon, Zap, Lightning
  - Detect: buffOnDamageTime, targetBuffData.name == "ZapFreeze" (and -100% multipliers)
- Slow debuff: Ice Wizard, Giant Snowball, Fisherman (bola), Poison (-15%), Earthquake
  - Detect: buffData.speedMultiplier (and hitSpeedMultiplier/spawnSpeedMultiplier)
- Chain/multi-target: Electro Dragon (chainedHitCount=3), Electro Spirit (9), Electro Wizard (multipleTargets=2)
  - Detect: chainedHitCount, multipleTargets
- Persistent AOE: Poison, Freeze, Tornado, Earthquake, Goblin Curse
  - Detect: lifeDuration, hitFrequency, damagePerSecond, onlyEnemies, buffData
- Periodic spawners: Furnace, Tombstone, Witch, Night Witch
  - Detect: spawnInterval, spawnPauseTime, spawnNumber, spawnCharacterData
- Multi-summon formations: Skeletons, Skeleton Army, Minions, Minion Horde, Spear Goblins, Goblins, Royal Recruits, Three Musketeers
  - Detect: summonNumber, summonDeployDelay, summonRadius
- Mixed-unit summon: Goblin Gang (3+3), Rascals (1+2)
  - Detect: summonCharacterSecondCount, summonCharacterSecondData
- Beam with damage ramp: Inferno Tower, Inferno Dragon
  - Detect: variableDamage1/2/3, loadTime
- Rolling projectile (two-phase): The Log, Barbarian Barrel, Bowler
  - Detect: spawnChain, projectileRange, radius/radiusY on rolling projectile
- Pierce line: Magic Archer
  - Detect: long projectileRange, small radius (pierce handled in logic)
- Boomerang projectile: Executioner
  - Detect: projectileData.pingpongVisualTime
- Shotgun spread: Hunter
  - Detect: multipleProjectiles, small areaDamageRadius
- Pull/Hook: Fisherman
  - Detect: projectileSpecialData (hook), specialRange, specialMinRange, specialLoadTime
- Snare: Ram Rider (Rider)
  - Detect: targetBuffData.name == "BolaSnare", speedMultiplier around -70%
- Transformation on health: Cannon Cart, Goblin Demolisher
  - Detect: healthPercentages, onStartingActionData with transform/morph
- Rebirth chain: Phoenix
  - Detect: death projectile (PhoenixFireball), deathSpawnCharacterData PhoenixEgg, timed respawn
- Invisibility-after-idle: Royal Ghost
  - Detect: buffWhenNotAttackingTime, buffWhenNotAttackingData (Invisibility)
- Elixir generation: Elixir Collector
  - Detect: manaGenerateTimeMs, manaCollectAmount, manaOnDeath
- Multi-wave projectiles: Arrows
  - Detect: projectileWaves, projectileWaveInterval, multipleProjectiles
- Deploy/activation AOE: Battle Healer (spawn/heal on hit), Electro Wizard (deploy zap), Royal Delivery (area→spawn), Goblin Drill (emerge), Mega Knight (landing)
  - Detect: spawnAreaEffectObjectData, areaEffectOnHitData, deathAreaEffectData, projectiles tied to deploy
- Champion abilities (cost/cooldown/duration): Archer Queen, Golden Knight, Skeleton King, Mighty Miner, Little Prince, Boss Bandit
  - Detect: abilityData.manaCost, abilityData.cooldown, abilityData.duration, ability name
- Damage reflection: Electro Giant
  - Detect: reflectedAttackRadius, reflectedAttackDamage, reflectedAttackBuffData

Single-use mechanics (examples → detection keys):
- Ram Rider: Ram (chargeRange, damageSpecial, jumpHeight/jumpSpeed, tidTarget buildings, spawnCharacterData RamRider); Rider (projectileData RamRiderBola, targetBuffData BolaSnare)
- Bandit: dashMinRange, dashMaxRange, jumpSpeed, dashDamage (immunity handled in logic)
- Golden Knight: abilityData GoldenKnightChain, dashMinRange/dashMaxRange, dashCount, jumpSpeed
- Mega Knight: deploy projectileData (damage/pushback/radius), dash ranges, jumpHeight/jumpSpeed
- Electro Wizard: multipleTargets, buffOnDamageTime + ZapFreeze, spawnAreaEffectObjectData ElectroWizardZap
- Electro Dragon: chainedHitCount, projectile targetBuffData ZapFreeze
- Zappies: buffOnDamageTime, buffOnDamageData ZapFreeze
- Fisherman: projectileSpecialData FishermanProjectile, specialRange/minRange/loadTime
- Firecracker: projectileData with spawnProjectileData (explosion shrapnel), recoil handled in logic
- Executioner: projectileData.pingpongVisualTime
- Hunter: multipleProjectiles (spread behavior in logic)
- Magic Archer: long projectileRange, small radius (pierce in logic)
- Cannon Cart: healthPercentages, transform action
- Goblin Demolisher: healthPercentages, transform to _kamikaze_form, death projectile with pushback
- Phoenix: death projectile (PhoenixFireball), deathSpawnCharacterData PhoenixEgg, timed respawn to PhoenixNoRespawn
- Royal Ghost: buffWhenNotAttackingTime, buffWhenNotAttackingData Invisibility
- Battle Healer: spawnAreaEffectObjectData (heal), areaEffectOnHitData (heal), buffData with heal tick
- Goblin Drill: spawnPathfindMorphData, spawnAreaObjectData (emerge AoE), spawnNumber/spawnPauseTime, deathSpawnCount
- Miner: special deployment rule (card-level logic; not a single field)
- Elixir Golem: death spawn chain across stages; elixir reward handled in game rules
- Electro Giant: reflectedAttack* fields

