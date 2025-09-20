# Balloon Card Implementation Audit

## Card Details
- **Card**: Balloon
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Epic

## Implemented
- ✅ Basic troop spawning (src/clasher/battle.py:342-366)
- ✅ Air unit classification (src/clasher/battle.py:349)
- ✅ Building-only targeting (src/clasher/data.py:12)
- ✅ Death spawn bomb entity (src/clasher/battle.py:1200-1258)
- ✅ Bomb explosion damage mechanics (src/clasher/entities.py:615-633)

## Missing
- ❌ Death spawn bomb stats (BalloonBomb) not loaded from gamedata.json deathSpawnCharacterData
- ❌ Bomb explosion radius not set from gamedata (deathDamage: 94, collisionRadius: 450)
- ❌ Bomb deploy time not implemented (deployTime: 3000)
- ❌ Building-only targeting for the spawned bomb (tidTarget: "TID_TARGETS_AIR_AND_GROUND")

## Notes
- The Balloon is correctly identified as an air unit and spawns properly
- Death spawn system exists but doesn't use the specific BalloonBomb data from gamedata.json
- The bomb entity class exists but uses generic stats rather than Balloon-specific bomb stats
- Building-only targeting logic exists for troops but may not be properly applied to the Balloon
- Name mapping: "Balloon" in code matches "Balloon" in gamedata.json