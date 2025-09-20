# Battle Healer - Implementation Audit

## Card Details
- **Card**: Battle Healer
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Rare
- **Arena**: Arena 8

## Implemented Mechanics
- **Basic troop spawning**: Troop entity creation (src/clasher/battle.py:698)
- **Movement and pathfinding**: Standard ground troop movement with bridge navigation (src/clasher/entities.py:427-690)
- **Basic attack system**: Melee attacks with hit speed, damage, and targeting (src/clasher/entities.py:292-308)
- **Target acquisition**: Priority targeting system (troops > buildings) (src/clasher/entities.py:159-214)
- **Health and damage**: Basic combat mechanics (src/clasher/entities.py:66-70, 72-106)

## Missing Mechanics
Based on gamedata.json analysis, Battle Healer has these **critical unimplemented mechanics**:

### 1. Spawn Area Healing (spawnAreaObjectData)
- **Heal on spawn**: Creates healing area when deployed (79 HP/sec)
- **Radius**: 2.5 tiles around spawn point
- **Duration**: 1 second
- **Frequency**: 250ms tick rate
- **Source**: gamedata.json:5038-5054

### 2. Attack-Triggered Healing (areaEffectOnHitData)
- **Heal on attack**: Creates healing area when attacking (40 HP/sec)
- **Radius**: 4.0 tiles around attack target
- **Duration**: 50ms (instant effect)
- **Frequency**: 250ms tick rate
- **Source**: gamedata.json:5056-5073

### 3. "When Not Attacking" Buff System
- **buffWhenNotAttackingTime**: 5-second timer
- **Mechanism**: Special behavior when not actively attacking
- **Source**: gamedata.json:5034

### 4. Area Effect Object System
- **Area effect creation**: No system for spawnable area effects
- **Buff application**: No healing buff mechanics for troops
- **Hit frequency**: No timed buff application system
- **Source**: Missing in entities.py, battle.py, data.py

## Notes
- **Name mapping**: Card name "BattleHealer" in gamedata.json vs "Battle Healer" display name
- **Architecture gap**: Codebase has HealSpell for spells but NO troop-based healing system
- **Entity types**: AURA entity type defined (entities.py:18) but not implemented for healing
- **Data structure**: CardStats class supports buff_data but troop spawning ignores spawn/area effect data
- **Core issue**: Troop deployment only handles basic stats, completely ignores complex mechanics like spawnAreaObjectData and areaEffectOnHitData

## Implementation Priority
1. **HIGH**: Spawn area healing on deployment (defines the card's unique purpose)
2. **HIGH**: Attack-triggered healing (core combat mechanic)
3. **MEDIUM**: "When not attacking" behavior (secondary characteristic)
4. **LOW**: Visual effects for healing auras