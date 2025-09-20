# Lumberjack Card Implementation Audit

## Card Information
- **Card**: Lumberjack (Rage Barbarian in gamedata)
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground melee troop with death spawn effect

## Implemented
- **Basic Troop Mechanics**: Movement, targeting, and attack systems in `src/clasher/entities.py:240-690`
- **Death Spawn System**: Comprehensive death spawn handling in `src/clasher/entities.py:53-57` and `src/clasher/battle.py:638-725`
- **Area Effect Support**: Basic area effect system exists in `src/clasher/entities.py:830-926`
- **Rage Spell**: Buff spell implementation exists in `src/clasher/spells.py:182-206` with speed/damage multipliers

## Missing
- **Death Spawn Bottle**: The specific `RageBarbarianBottle` building spawn is not implemented
- **Death Area Effect**: The `BarbarianRage` area effect with rage buff mechanics is not implemented
- **Rage Effect Mechanics**: The specific rage buff (35% attack speed, 35% movement speed) from death spawn is not implemented
- **Area Effect Duration**: The 5.5 second duration with buff timing mechanics is missing
- **Rage Damage Component**: The 58 damage area effect on rage creation is not implemented

## Notes
- **Name Mapping**: The card is named "RageBarbarian" in gamedata.json but uses Lumberjack graphics
- **Death Complexity**: The card has a complex two-stage death effect: spawns a bottle building, which then creates a rage area effect
- **Buff Integration**: The rage buff system exists but needs to be integrated with the death spawn mechanics
- **Area Effect Chain**: Missing the chain reaction: death → bottle spawn → area effect → buff application

## Gamedata.json Analysis
The Lumberjack (RageBarbarian) has these key mechanics:
- `deathSpawnCharacter`: "RageBarbarianBottle" (building)
- Bottle has `deathAreaEffectData`: "BarbarianRage" (area effect)
- Area effect has `buffData`: "Rage" (35% speed/attack speed buff)
- Area effect includes `spawnAreaEffectObjectData`: "BarbarianRageDamage" (58 damage)
- Effect duration: 5500ms (5.5 seconds)
- Effect radius: 3000 game units (3 tiles)

The core issue is that while individual systems exist, the specific chain of death → bottle → rage effect is not implemented.