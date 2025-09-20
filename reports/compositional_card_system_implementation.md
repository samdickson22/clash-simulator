# Compositional Card System Implementation Plan

## Overview

Implement a compositional, flag-less Clash Royale card system that replaces boolean feature flags with attached Mechanics/Effects components. Single-use mechanics will live in per-card modules, with promotion to shared mechanics only when reused by 2+ cards. The system will be data-driven from gamedata.json with proper unit conversions (1 tile = 1000 game units, times in ms).

## Current State Analysis

The existing codebase uses a traditional object-oriented approach with inheritance and conditional logic:

### Key Discoveries:
- **Entity lifecycle**: entities.py:57-70 `__post_init__`, :251-309 `Troop.update()`, :696-726 `Building.update()` 
- **Death handling**: battle.py:637-678 `_cleanup_dead_entities()` handles death spawns before entity removal
- **Attack system**: entities.py:72-106 `_deal_attack_damage()` checks for area damage via card_stats attributes
- **Spell system**: spells.py and dynamic_spells.py use class-based spell types with limited composition
- **Status effects**: entities.py:108-140 simple stun/slow timers without compositional mechanics
- **Targeting**: entities.py:159-214 `get_nearest_target()` uses conditionals for building-only targeting
- **Movement**: entities.py:427-689 pathfinding hardcoded in `Troop` class with charging mechanics

### Key Constraints:
- Entities created via `_spawn_entity()` (battle.py:615-635) and `_spawn_troop()` (battle.py:166-221)
- Update loop calls `entity.update(dt, self)` for all entities (battle.py:120-121)
- Death cleanup happens after all entity updates (battle.py:124)
- Projectiles are separate entities, not integrated with attack behaviors (entities.py:769-826)

## Desired End State

A fully compositional card system where:
- Cards are assembled from reusable Mechanics and Effects
- No boolean hasX flags - presence implies behavior
- Lifecycle hooks enable modular behavior injection
- Factory automatically detects and attaches mechanics from gamedata.json
- Representative cards function with signature mechanics:
  - Giant (baseline building-only targeting)
  - Poison (DoT AOE with debuff)
  - Inferno Tower (per-target damage ramp)
  - Hog Rider (river jumping)
  - Sparky (charge-up with reset on stun)
  - Skeleton King (champion ability with soul collection)

### Verification Points:
- Factory correctly maps gamedata fields to mechanics (see card_data_model.md:449-534)
- Mechanics fire at correct lifecycle moments (spawn/tick/attack/death)
- Champion abilities work with elixir cost/cooldown/duration
- Spells compose from Effect primitives
- No regression in existing card behaviors

## What We're NOT Doing

- Visual/sound effects integration
- Balance changes to card stats
- Card evolutions (EV1 variants)
- Arena/map modifications
- Network/multiplayer systems
- UI/frontend changes
- Performance optimizations beyond basic efficiency

## Implementation Approach

Use composition over inheritance with Protocol-based behaviors and lifecycle hooks. Mechanics attach to entities and respond to lifecycle events. Effects compose for spell behaviors. Factory reads gamedata.json and assembles CardDefinitions with appropriate components.

## Phase 1: Core Types & Lifecycle Infrastructure

### Overview
Establish the foundational type system and lifecycle hook infrastructure that all mechanics will use.

### Changes Required:

#### 1. Core Types Module
**File**: `src/clasher/card_types.py` (new)
**Changes**: Create core types from card_data_model.md

```python
from dataclasses import dataclass, field
from typing import Optional, Sequence, Protocol, Literal, Callable, Any

CardKind = Literal["troop", "building", "spell", "champion"]
Rarity = Literal["Common", "Rare", "Epic", "Legendary", "Champion"]

@dataclass(frozen=True)
class BaseStats:
    hitpoints: Optional[int] = None
    damage: Optional[int] = None
    range_tiles: Optional[float] = None
    hit_speed_ms: Optional[int] = None
    sight_range_tiles: Optional[float] = None
    collision_radius_tiles: Optional[float] = None

@dataclass(frozen=True)
class TroopStats(BaseStats):
    speed_tiles_per_min: Optional[int] = None
    deploy_time_ms: Optional[int] = 1000
    load_time_ms: Optional[int] = None
    summon_count: Optional[int] = None

@dataclass(frozen=True)
class BuildingStats(BaseStats):
    lifetime_ms: Optional[int] = None
    deploy_time_ms: Optional[int] = 1000

@dataclass(frozen=True)
class SpellStats:
    radius_tiles: Optional[float] = None
    duration_ms: Optional[int] = None
    crown_tower_damage_scale: Optional[float] = None

class TargetingBehavior(Protocol):
    def can_target_air(self) -> bool: ...
    def can_target_ground(self) -> bool: ...
    def buildings_only(self) -> bool: ...

class MovementBehavior(Protocol):
    def update(self, entity: Any, dt_ms: int) -> None: ...

class AttackBehavior(Protocol):
    def maybe_attack(self, entity: Any, dt_ms: int) -> None: ...

class Mechanic(Protocol):
    def on_attach(self, entity: Any) -> None: ...
    def on_spawn(self, entity: Any) -> None: ...
    def on_tick(self, entity: Any, dt_ms: int) -> None: ...
    def on_attack_start(self, entity: Any, target: Any) -> None: ...
    def on_attack_hit(self, entity: Any, target: Any) -> None: ...
    def on_death(self, entity: Any) -> None: ...

class Effect(Protocol):
    def apply(self, context: Any) -> None: ...

@dataclass(frozen=True)
class CardDefinition:
    id: int
    name: str
    kind: CardKind
    rarity: Rarity
    elixir: int
    troop_stats: Optional[TroopStats] = None
    building_stats: Optional[BuildingStats] = None
    spell_stats: Optional[SpellStats] = None
    targeting: Optional[TargetingBehavior] = None
    movement: Optional[MovementBehavior] = None
    attack: Optional[AttackBehavior] = None
    mechanics: Sequence[Mechanic] = field(default_factory=tuple)
    effects: Sequence[Effect] = field(default_factory=tuple)
    tags: frozenset[str] = frozenset()
```

#### 2. Entity Lifecycle Hooks
**File**: `src/clasher/entities.py`
**Changes**: Add mechanic storage and lifecycle calls to Entity base class (lines 27-70)

```python
# Add to Entity class after line 55:
mechanics: List[Mechanic] = field(default_factory=list)

# Modify __post_init__ (line 57):
def __post_init__(self) -> None:
    if self.max_hitpoints == 0:
        self.max_hitpoints = self.hitpoints
    # Call on_attach for all mechanics
    for mechanic in self.mechanics:
        mechanic.on_attach(self)

# Add new method after take_damage (line 71):
def on_spawn(self) -> None:
    """Called when entity is spawned in battle"""
    for mechanic in self.mechanics:
        mechanic.on_spawn(self)

def on_death(self) -> None:
    """Called when entity dies"""
    for mechanic in self.mechanics:
        mechanic.on_death(self)
        
# Modify take_damage to trigger on_death (line 66):
def take_damage(self, amount: float) -> None:
    self.hitpoints = max(0, self.hitpoints - amount)
    if self.hitpoints <= 0 and self.is_alive:
        self.is_alive = False
        self.on_death()  # Trigger death mechanics
```

#### 3. Update Loop Integration
**File**: `src/clasher/entities.py`
**Changes**: Call on_tick in Troop and Building update methods

```python
# In Troop.update() after line 257 (status effects):
# Call on_tick for all mechanics
for mechanic in self.mechanics:
    mechanic.on_tick(self, dt * 1000)  # Convert to ms

# In Building.update() after line 702 (status effects):
# Call on_tick for all mechanics  
for mechanic in self.mechanics:
    mechanic.on_tick(self, dt * 1000)  # Convert to ms
```

#### 4. Attack Hook Integration
**File**: `src/clasher/entities.py`
**Changes**: Add on_attack_start and on_attack_hit hooks (lines 298-308 for Troop, 717-726 for Building)

```python
# In Troop before attack (line 298):
for mechanic in self.mechanics:
    mechanic.on_attack_start(self, current_target)

# After damage dealt (line 304/305):
for mechanic in self.mechanics:
    mechanic.on_attack_hit(self, current_target)
    
# Similar changes in Building.update() lines 720/723
```

#### 5. Spawn Hook Integration
**File**: `src/clasher/battle.py`
**Changes**: Call on_spawn after entity creation (lines 615-635, 191-220)

```python
# In _spawn_entity after line 633:
entity.on_spawn()

# In _spawn_single_troop after line 220:
troop.on_spawn()
```

### Success Criteria:

#### Automated Verification:
- [ ] Core types module imports without errors: `python -c "from src.clasher.card_types import *"`
- [ ] Existing tests still pass: `python -m pytest tests/`
- [ ] Lifecycle hooks called in correct order (add test)

#### Manual Verification:
- [ ] Entities can have mechanics attached
- [ ] Mechanics receive all lifecycle events
- [ ] No performance regression in battle simulation

---

## Phase 2: Shared Mechanics Implementation

### Overview
Implement the core shared mechanics that are reused across multiple cards.

### Changes Required:

#### 1. Shared Mechanics Module Structure
**File**: `src/clasher/mechanics/shared/__init__.py` (new)
**Changes**: Create shared mechanics module structure

```python
from .death_effects import DeathDamage, DeathSpawn
from .shield import Shield
from .damage_ramp import DamageRamp
from .status_effects import FreezeDebuff, Stun
from .scaling import CrownTowerScaling
from .knockback import KnockbackOnHit
from .spawner import PeriodicSpawner

__all__ = [
    'DeathDamage', 'DeathSpawn', 'Shield', 'DamageRamp',
    'FreezeDebuff', 'Stun', 'CrownTowerScaling', 
    'KnockbackOnHit', 'PeriodicSpawner'
]
```

#### 2. Death Effects Mechanics
**File**: `src/clasher/mechanics/shared/death_effects.py` (new)
**Changes**: Implement death damage and spawn mechanics

```python
@dataclass
class DeathDamage:
    radius_tiles: float
    damage: int
    
    def on_attach(self, entity): pass
    def on_spawn(self, entity): pass
    def on_tick(self, entity, dt_ms): pass
    def on_attack_start(self, entity, target): pass
    def on_attack_hit(self, entity, target): pass
    
    def on_death(self, entity):
        from ...battle import BattleState
        battle_state = entity.battle_state  # Need to add reference
        # Deal area damage at death position
        for target in battle_state.entities.values():
            if target.player_id == entity.player_id or not target.is_alive:
                continue
            distance = entity.position.distance_to(target.position)
            if distance <= self.radius_tiles:
                target.take_damage(self.damage)

@dataclass
class DeathSpawn:
    unit_name: str
    count: int
    formation: Callable[[int], list[tuple[float, float]]]
    
    def on_death(self, entity):
        # Spawn units using battle_state._spawn_death_units pattern
        # Implementation based on battle.py:680-717
        pass
```

#### 3. Shield Mechanic
**File**: `src/clasher/mechanics/shared/shield.py` (new)
**Changes**: Implement shield that absorbs damage

```python
@dataclass
class Shield:
    shield_hp: int
    current_shield: int = field(init=False)
    
    def on_attach(self, entity):
        self.current_shield = self.shield_hp
        # Hook into entity's take_damage method
        entity._original_take_damage = entity.take_damage
        entity.take_damage = lambda amount: self._shielded_take_damage(entity, amount)
    
    def _shielded_take_damage(self, entity, amount):
        if self.current_shield > 0:
            absorbed = min(amount, self.current_shield)
            self.current_shield -= absorbed
            remaining = amount - absorbed
            if remaining > 0:
                entity._original_take_damage(remaining)
        else:
            entity._original_take_damage(amount)
```

#### 4. Damage Ramp Mechanic
**File**: `src/clasher/mechanics/shared/damage_ramp.py` (new)
**Changes**: Implement per-target damage ramping (Inferno Tower/Dragon)

```python
@dataclass
class DamageRamp:
    stages: list[tuple[int, int]]  # [(time_ms, damage)]
    per_target: bool
    target_timers: dict = field(default_factory=dict)
    
    def on_tick(self, entity, dt_ms):
        # Track time on current target
        if entity.target_id:
            self.target_timers[entity.target_id] = \
                self.target_timers.get(entity.target_id, 0) + dt_ms
                
    def on_attack_start(self, entity, target):
        # Apply ramped damage based on time on target
        time_on_target = self.target_timers.get(target.id, 0)
        damage = self._get_damage_for_time(time_on_target)
        entity.damage = damage  # Override entity damage
        
    def _get_damage_for_time(self, time_ms):
        for stage_time, stage_damage in reversed(self.stages):
            if time_ms >= stage_time:
                return stage_damage
        return self.stages[0][1] if self.stages else 0
```

### Success Criteria:

#### Automated Verification:
- [ ] Mechanics module imports successfully: `python -c "from src.clasher.mechanics.shared import *"`
- [ ] Unit tests for each mechanic pass: `python -m pytest tests/test_mechanics.py`
- [ ] Death spawn creates correct number of units
- [ ] Shield blocks damage correctly
- [ ] Damage ramp increases over time

#### Manual Verification:
- [ ] Dark Prince shield absorbs damage before HP loss
- [ ] Golem death spawns 2 Golemites
- [ ] Inferno Tower damage ramps up on single target
- [ ] Shield visual indicator updates correctly

---

## Phase 3: Spell Effects Composition

### Overview
Refactor spell system to use composable Effects instead of inheritance.

### Changes Required:

#### 1. Effect Primitives
**File**: `src/clasher/effects/__init__.py` (new)
**Changes**: Create effect primitives module

```python
from .damage import DirectDamage
from .status import ApplyStun, ApplySlow, ApplyFreeze
from .area import PeriodicArea
from .projectile import ProjectileLaunch
from .spawn import SpawnUnits
from .buff import ApplyBuff

@dataclass
class EffectContext:
    battle_state: 'BattleState'
    caster_id: int
    target_position: Position
    affected_entities: list[Entity] = field(default_factory=list)
```

#### 2. Spell Refactor
**File**: `src/clasher/spells.py`
**Changes**: Refactor to use Effect composition (replace lines 13-511)

```python
@dataclass
class ComposedSpell:
    name: str
    mana_cost: int
    effects: list[Effect]
    
    def cast(self, battle_state, player_id, target_pos):
        context = EffectContext(battle_state, player_id, target_pos)
        for effect in self.effects:
            effect.apply(context)
```

#### 3. Dynamic Spell Loading
**File**: `src/clasher/dynamic_spells.py`
**Changes**: Update to build Effect chains (lines 89-189)

```python
def create_spell_from_json(spell_data):
    effects = []
    
    # Build effect chain based on spell data
    if 'projectileData' in spell_data:
        effects.append(build_projectile_effect(spell_data['projectileData']))
    
    if 'areaEffectObjectData' in spell_data:
        effects.append(build_area_effect(spell_data['areaEffectObjectData']))
        
    # Apply modifiers
    if spell_data.get('crownTowerDamagePercent'):
        effects = [CrownTowerScaling(spell_data['crownTowerDamagePercent'])] + effects
    
    return ComposedSpell(
        name=spell_data['name'],
        mana_cost=spell_data['manaCost'],
        effects=effects
    )
```

### Success Criteria:

#### Automated Verification:
- [ ] All spell tests still pass: `python -m pytest tests/test_spells.py`
- [ ] Effect composition creates correct spell behavior
- [ ] Crown tower scaling applies correctly

#### Manual Verification:
- [ ] Fireball: projectile + damage + knockback + tower scaling
- [ ] Poison: periodic area + DoT + slow debuff
- [ ] Lightning: top-3 targeting + stun + chain timing
- [ ] Arrows: multi-wave projectiles with travel time

---

## Phase 4: Card-Specific Mechanics

### Overview
Implement single-use mechanics in per-card modules.

### Changes Required:

#### 1. Card Module Structure
**File**: `src/clasher/cards/__init__.py` (new)
**Changes**: Create card-specific mechanics structure

```python
from .hog_rider import HogRiderJump
from .sparky import SparkyChargeUp
from .bandit import BanditDash
from .fisherman import FishermanHook
# ... etc

CARD_MECHANICS = {
    'HogRider': [HogRiderJump],
    'Sparky': [SparkyChargeUp],
    'Bandit': [BanditDash],
    'Fisherman': [FishermanHook],
}
```

#### 2. Hog Rider Jump
**File**: `src/clasher/cards/hog_rider.py` (new)
**Changes**: Implement river jumping mechanic

```python
@dataclass
class HogRiderJump:
    jump_height: int
    jump_speed: int
    
    def on_tick(self, entity, dt_ms):
        # Check if approaching river
        if self._approaching_river(entity):
            # Override pathfinding to jump over
            entity.can_cross_river = True
```

#### 3. Sparky Charge-Up
**File**: `src/clasher/cards/sparky.py` (new)
**Changes**: Implement charge-up with stun reset

```python
@dataclass
class SparkyChargeUp:
    charge_ms: int
    reset_on_stun: bool
    charge_time: int = 0
    
    def on_tick(self, entity, dt_ms):
        if entity.target_id:
            self.charge_time += dt_ms
            
    def on_attack_start(self, entity, target):
        if self.charge_time >= self.charge_ms:
            entity.damage *= 3  # Charged attack
            self.charge_time = 0
            
    def on_stun(self, entity):
        if self.reset_on_stun:
            self.charge_time = 0
```

### Success Criteria:

#### Automated Verification:
- [ ] Card mechanics load correctly: `python -c "from src.clasher.cards import CARD_MECHANICS"`
- [ ] Unit tests for card mechanics pass

#### Manual Verification:
- [ ] Hog Rider jumps over river correctly
- [ ] Sparky charge-up resets on stun
- [ ] Bandit dash grants invincibility frames
- [ ] Fisherman hook pulls enemies

---

## Phase 5: Champion Ability System  

### Overview
Implement champion abilities with elixir cost and cooldown.

### Changes Required:

#### 1. Champion Ability Framework
**File**: `src/clasher/mechanics/champion.py` (new)
**Changes**: Create champion ability system

```python
@dataclass
class ActiveAbility:
    name: str
    elixir_cost: int
    cooldown_ms: int
    duration_ms: int
    effects: list[Effect]
    last_use_time: int = 0
    is_active: bool = False
    
    def can_activate(self, entity, battle_state):
        player = battle_state.players[entity.player_id]
        time_since_use = battle_state.time * 1000 - self.last_use_time
        return (player.elixir >= self.elixir_cost and 
                time_since_use >= self.cooldown_ms and
                not self.is_active)
    
    def activate(self, entity, battle_state):
        if self.can_activate(entity, battle_state):
            player = battle_state.players[entity.player_id]
            player.elixir -= self.elixir_cost
            self.last_use_time = battle_state.time * 1000
            self.is_active = True
            # Apply ability effects
            for effect in self.effects:
                effect.apply(EffectContext(battle_state, entity.player_id, entity.position))
```

#### 2. Skeleton King Soul Collector
**File**: `src/clasher/cards/skeleton_king.py` (new)
**Changes**: Implement soul collection mechanic

```python
@dataclass
class SkeletonKingSoulCollector:
    souls_collected: int = 0
    souls_per_activation: int = 20
    
    def on_tick(self, entity, dt_ms):
        # Check for nearby deaths and collect souls
        for other in entity.battle_state.entities.values():
            if not other.is_alive and other.just_died:  # Need to add flag
                distance = entity.position.distance_to(other.position)
                if distance <= 5.0:  # 5 tile soul collection radius
                    self.souls_collected += 1
```

### Success Criteria:

#### Automated Verification:
- [ ] Champion abilities consume elixir correctly
- [ ] Cooldown prevents rapid activation
- [ ] Duration-based effects expire properly

#### Manual Verification:
- [ ] Archer Queen invisibility and attack speed buff work
- [ ] Golden Knight chain dash hits multiple targets
- [ ] Skeleton King spawns skeletons from souls
- [ ] Mighty Miner switches lanes and drops bomb

---

## Phase 6: Card Factory Implementation

### Overview
Build the factory that assembles CardDefinitions from gamedata.json.

### Changes Required:

#### 1. Factory Core
**File**: `src/clasher/factory/card_factory.py` (new)
**Changes**: Implement factory with mechanic detection

```python
def card_from_gamedata(entry: dict) -> CardDefinition:
    mechanics = []
    
    # Detect and attach mechanics based on gamedata fields
    if entry.get('deathDamage'):
        mechanics.append(DeathDamage(
            radius_tiles=entry.get('deathRadius', 0)/1000,
            damage=entry['deathDamage']
        ))
    
    if entry.get('shieldHitpoints'):
        mechanics.append(Shield(shield_hp=entry['shieldHitpoints']))
        
    if entry.get('chargeRange'):
        # Check if it's a shared charge mechanic or card-specific
        card_name = entry['name']
        if card_name in CARD_MECHANICS:
            mechanics.extend([m() for m in CARD_MECHANICS[card_name]])
            
    # ... detection for all mechanics per card_data_model.md:449-534
    
    return CardDefinition(
        id=entry['id'],
        name=entry['name'],
        kind=_determine_card_kind(entry),
        rarity=entry['rarity'],
        elixir=entry['manaCost'],
        mechanics=tuple(mechanics),
        # ... other fields
    )
```

#### 2. Integration with Data Loader
**File**: `src/clasher/data.py`
**Changes**: Update CardDataLoader to use factory (lines 102-237)

```python
def load_cards(self):
    # After loading JSON at line 110
    from ..factory.card_factory import card_from_gamedata
    
    for spell_data in spells:
        card_def = card_from_gamedata(spell_data)
        # Convert CardDefinition to CardStats for compatibility
        self._cards[card_def.name] = self._card_def_to_stats(card_def)
```

### Success Criteria:

#### Automated Verification:
- [ ] Factory detects all mechanics from gamedata: `python tests/test_factory.py`
- [ ] Cards load with correct mechanics attached
- [ ] Unit conversions applied correctly (tiles/ms)

#### Manual Verification:
- [ ] Giant has building-only targeting
- [ ] Dark Prince has shield and charge
- [ ] Golem has death spawn
- [ ] Inferno Tower has damage ramp

---

## Phase 7: System Integration & Polish

### Overview
Final integration, testing, and polish.

### Changes Required:

#### 1. Battle State Integration
**File**: `src/clasher/battle.py`
**Changes**: Add battle_state reference to entities (needed for mechanics)

```python
# In _spawn_entity line 615-635, add:
entity.battle_state = self  # Add reference for mechanics

# In _spawn_single_troop line 191-220, add:
troop.battle_state = self
```

#### 2. Comprehensive Tests
**File**: `tests/test_compositional_system.py` (new)
**Changes**: Add integration tests for the compositional system

```python
def test_giant_targets_buildings_only():
    battle = create_test_battle()
    giant = spawn_card(battle, 'Giant', Position(9, 10))
    assert giant.mechanics  # Has mechanics attached
    # Verify targeting behavior
    
def test_inferno_damage_ramp():
    # Test damage increases over time on same target
    
def test_poison_dot_and_slow():
    # Test area effect with damage over time and slow
    
def test_skeleton_king_ability():
    # Test champion ability activation
```

### Success Criteria:

#### Automated Verification:
- [ ] All existing tests pass: `python -m pytest tests/`
- [ ] Integration tests pass: `python -m pytest tests/test_compositional_system.py`
- [ ] No memory leaks or performance regression
- [ ] Type checking passes: `mypy src/clasher/`

#### Manual Verification:
- [ ] Representative cards work end-to-end:
  - Giant targets only buildings
  - Poison applies DoT and slow in area
  - Inferno Tower ramps damage per target
  - Hog Rider jumps river
  - Sparky charges and resets on stun
  - Skeleton King collects souls and spawns skeletons
- [ ] Spells compose correctly:
  - Fireball: knockback + tower scaling
  - Log: two-phase roll with knockback
  - Lightning: top-3 targeting with stun
  - Arrows: multi-wave projectiles
- [ ] Champions work:
  - Abilities cost elixir
  - Cooldowns enforced
  - Effects apply correctly

---

## Testing Strategy

### Unit Tests:
- Test each Mechanic in isolation
- Test each Effect in isolation  
- Test factory detection logic
- Test lifecycle hook ordering

### Integration Tests:
- Test complete cards with multiple mechanics
- Test spell effect composition
- Test champion ability system
- Test death spawn chains

### Manual Testing Steps:
1. Spawn Giant near enemy troops and buildings - verify it ignores troops
2. Cast Poison - verify DoT ticks and units slow
3. Place Inferno Tower - verify damage increases on same target, resets on retarget
4. Deploy Hog Rider on opposite side of river - verify jump
5. Place Sparky, let it charge, stun it - verify charge reset
6. Deploy Skeleton King, activate ability - verify soul spawning

## Performance Considerations

- Mechanics are lightweight objects with minimal state
- Lifecycle hooks add minimal overhead (simple iteration)
- Effect composition may be slightly slower than inheritance but more flexible
- Consider pooling Effect objects to reduce allocation

## Migration Notes

- Existing CardStats remains for compatibility during migration
- Factory creates CardDefinition, then converts to CardStats
- Gradually migrate systems to use CardDefinition directly
- Entities can work with both old stats and new mechanics during transition

## References

- Original specification: `reports/card_data_model.md`
- Gamedata format: `gamedata.json`  
- Current entity system: `src/clasher/entities.py:27-1280`
- Current spell system: `src/clasher/spells.py:13-511`
- Current battle logic: `src/clasher/battle.py:14-814`
- Mechanics mapping: `reports/card_data_model.md:449-534`
