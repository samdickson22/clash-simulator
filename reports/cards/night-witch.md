# Night Witch Implementation Audit

## Card Details
- **Card**: Night Witch
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop

## Implemented
- **Basic troop deployment** - Troop spawning system exists in `src/clasher/battle.py:432`
- **Ground targeting** - Ground troop targeting logic in `src/clasher/entities.py:85`
- **Movement and pathfinding** - Base troop movement in `src/clasher/entities.py:140`
- **Basic combat** - Attack mechanics in `src/clasher/entities.py:130`

## Missing
- **Periodic bat spawning** - `spawnNumber: 2` bats every `spawnPauseTime: 5000`ms (5 seconds) - No periodic spawn mechanic exists in Troop class
- **Death spawn** - `deathSpawnCount: 1` bat on death - No death spawn mechanic in `src/clasher/entities.py:19`
- **Bat entity** - "Bat" character exists in gamedata but no corresponding implementation found
- **Air targeting for bats** - Bats should target both air and ground (`tidTarget: "TID_TARGETS_AIR_AND_GROUND"`)
- **Spawn radius and positioning** - Proper bat spawn positioning around Night Witch

## Notes
- The Night Witch is mapped to ID `26000048` in gamedata.json
- Character name in gamedata is "DarkWitch" but English name is "Night Witch"
- Bat character data exists but no Bat entity implementation found in codebase
- No periodic spawn timer or death spawn hook exists in current Troop implementation
- Current spawn mechanics are limited to projectiles and area effects, not troop-based spawning