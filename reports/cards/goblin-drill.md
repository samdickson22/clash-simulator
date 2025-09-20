# Goblin Drill - Implementation Audit

## Card Details
- **Card**: Goblin Drill
- **Elixir**: 4
- **Category**: Building
- **Rarity**: Epic
- **Type**: Structure with burrowing mechanics

## Implemented
- **Building base class**: Available in `src/clasher/entities.py:Building`
- **Death spawn system**: Available in `src/clasher/battle.py:638` - handles spawning units on death
- **Area effect system**: Available in `src/clasher/entities.py:AreaEffect` - handles area damage effects
- **Card data loading**: Available in `src/clasher/data.py` - loads spawn and death spawn character data
- **Spawn character logic**: Available in `src/clasher/entities.py:SpawnProjectile` - spawns units on impact/deployment

## Missing
- **Burrowing movement mechanics**: No code for drill moving underground to target location
- **Area damage on emergence**: No implementation of `spawnAreaObjectData` dealing 33 damage in 2-tile radius on surfacing
- **Periodic spawn mechanics**: No implementation of `spawnNumber=1` and `spawnPauseTime=3000` for spawning Goblins every 3 seconds
- **Death spawn**: No implementation of `deathSpawnCount=2` for spawning 2 Goblins on destruction
- **Morphing behavior**: No implementation of `spawnPathfindMorphData` for drill transforming from dig phase to building phase
- **Knockback on emergence**: No implementation of area knockback when surfacing
- **Collision changes**: No implementation of collision radius changes (0 during dig, 500 as building)

## Notes
- **Name mapping**: Card exists as "GoblinDrill" in gamedata.json
- **Complex mechanics**: This card has multiple phases (dig → building) that require state management
- **Area effects**: The `spawnAreaObjectData` with "GoblinDrillDamage" (33 damage, 2-tile radius, -70% crown tower damage) is not implemented
- **Spawn timing**: Periodic spawning every 3 seconds requires timer management not currently present in building logic
- **Death spawns**: Spawns 2 Goblins (`deathSpawnCount=2`) on destruction - this system exists but not used for Goblin Drill
- **No evolution support**: Evolution mechanics (`GoblinDrill_EV1`) are excluded per requirements