# Tombstone Card Implementation Audit

## Card Details
- **Card**: Tombstone
- **Elixir**: 3
- **Category**: Building
- **Rarity**: Rare
- **Type**: Building (Spawner)

## Implemented
- **Death spawn**: Spawns 4 Skeletons when destroyed (battle.py:644-725)
- **Basic building mechanics**: Uses Building class for stationary structure (entities.py:693-742)
- **Building stats**: HP (207), lifetime (30s), collision radius (1000 units) (gamedata.json:27000009)

## Missing
- **Periodic spawning**: Should spawn 2 Skeletons every 0.5s with 3.5s initial pause (gamedata.json:spawnInterval=500, spawnNumber=2, spawnPauseTime=3500)
- **Spawned Skeleton stats**: Spawns Skeletons with 32 HP, 32 damage, 90 speed, 500 range (gamedata.json:spawnCharacterData)
- **No attack capability**: Building should not attack - only spawn (currently uses generic Building attack logic)
- **Spawn timing mechanics**: Missing spawn interval tracking and timing system
- **Skeleton spawning radius**: Should spawn Skeletons at building location with proper positioning

## Notes
- **Name mapping**: Card name matches exactly ("Tombstone")
- **Core spawner logic**: No dedicated SpawnerBuilding class exists - would need to be created
- **Death spawn system**: Already implemented in battle.py and works for Tombstone
- **Implementation gap**: Missing periodic spawning functionality which is Tombstone's primary mechanic
- **Data source**: gamedata.json:27000009 (card definition with spawnCharacterData, deathSpawnCharacterData, spawnInterval, spawnNumber, spawnPauseTime)