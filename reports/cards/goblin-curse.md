# Goblin Curse - Implementation Audit

## Card, Elixir, Category
- **Card**: Goblin Curse
- **Elixir**: 2
- **Category**: Spell
- **Rarity**: Epic
- **Unlock Arena**: Arena 14

## Implemented
- Basic spell registration in `src/clasher/spells.py:265` as `GOBLIN_CURSE`
- Listed in `SPELL_REGISTRY` with other spells
- Uses `DirectDamageSpell` base class (incorrect implementation - should be area effect)

## Missing
Based on gamedata.json analysis, Goblin Curse should have these mechanics:

### Core Mechanics
- **Area Effect Object**: 6-second duration with 3.0 tile radius
- **Hit Frequency**: Every 0.83 seconds (50 game ticks)
- **Damage**: 100 damage on impact

### Buff System
- **Amplification Buff**: +20% damage taken by affected enemies (`GoblinCurseAmplify`)
- **Damage Over Time**: 12 damage per second (`GoblinCurseDamage`)
- **Tower Damage Reduction**: -80% crown tower damage

### Goblin Spawning
- **Death Spawn**: Spawns goblin when buffed unit dies
- **Spawn Data**: Goblin with 79 HP, 47 damage, 1.1s hit speed, 1.2 speed
- **Spawn Mechanics**: `deathSpawnCount: 1` with `GoblinCurseGoblin` data

### Action System
- **Intro Action**: `GoblinCurseIntro` on cast
- **Core Action**: `GoblinCurseCore` with main functionality
- **Outro Action**: `GoblinCurseOutro` on expiration
- **Hit Action**: `GoblinCurseCreateBuffs` when hitting enemies

## Notes
- Current implementation uses `DirectDamageSpell` which is incorrect - this should be a persistent area effect
- Complex buff system with damage amplification and DOT is not implemented
- Goblin spawning on death of buffed enemies is completely missing
- Multi-phase action system (intro/core/outro) not implemented
- Tower damage reduction mechanic not present
- Missing all spell visualization and timing mechanics
- No area effect object persistence or duration tracking

**Name Mapping**: `GoblinCurse` (gamedata) → `GOBLIN_CURSE` (code)

**Implementation Gap**: Currently registered as a basic damage spell, but should be a complex area effect with buff/debuff system and conditional spawning.