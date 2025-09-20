# Minion Horde Implementation Audit

## Card Details
- **Card**: Minion Horde
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Common
- **Type**: Air Swarm Troop (Spawns 6 Minions)

## Implemented
- Basic Troop entity framework (`src/clasher/entities.py:240-690`)
- Air unit movement and pathfinding logic (`src/clasher/entities.py:429-517`)
- Projectile-based ranged attacks (`src/clasher/entities.py:317-401`)
- Air unit classification in battle systems (`src/clasher/battle.py`)
- Multi-unit summon mechanics (summonNumber: 6) (`src/clasher/data.py: summon_count`)
- Individual Minion stats from gamedata.json:
  - HP: 90, Damage: 46, Speed: 90, Range: 1.6 tiles
  - Hit Speed: 1.0s, Sight Range: 5.5 tiles
  - Air/Ground targeting (`TID_TARGETS_AIR_AND_GROUND`)
- Summon radius: 0.6 tiles, deploy delay: 0.1s

## Missing
- **Swarm Behavior**: No specific logic for coordinating the 6 Minions as a group
- **Spread Formation**: Minions likely spawn in a tight cluster rather than spread formation
- **Individual Minion Death Handling**: Each Minion should be tracked and die individually
- **Minion-Specific Projectile**: MinionSpit projectile exists in data but no unique visual/gameplay treatment
- **Swarm Targeting Priority**: No special targeting logic for the horde as a group

## Notes
- **Name Mapping**: Card uses "MinionHorde" in code, spawns individual "Minion" units
- **Architecture**: Uses standard Troop class with `is_air_unit: true` flag
- **Data Source**: All capabilities derived from gamedata.json entry, no assumptions made
- **Summon Mechanics**: Uses generic summon system with `summonNumber: 6` property
- **Status**: Core mechanics present but lacks swarm-specific behaviors that differentiate it from regular Minions (which spawn 3 units)

**Assessment**: Minion Horde is functionally implemented as 6 individual Minion troops rather than a distinct horde entity with group behaviors.