# Furnace Card Implementation Audit

## Card Details
- **Card**: Furnace
- **Elixir**: 4
- **Category**: Building
- **Rarity**: Rare
- **Internal Name**: FirespiritHut

## Implemented
- ❌ **Basic building structure** - Building entity class exists but lacks spawn mechanics
- ❌ **Fire Spirits spawning** - No spawn timer or unit generation logic
- ❌ **Periodic spawn mechanics** - Missing spawnPauseTime (5s) and spawnNumber (1) handling
- ❌ **Building lifetime** - Missing lifeTime (28s) implementation
- ❌ **Death spawn** - Missing deathSpawnCharacterData logic for spawning on destruction
- ❌ **Fire Spirits behavior** - No implementation of Fire Spirits troops (kamikaze, splash damage)

## Missing (from gamedata.json)
Based on FirespiritHut data in gamedata.json:
- **Building stats**: hitpoints (331), collisionRadius (1000)
- **Spawn mechanics**: spawnPauseTime (5000ms), spawnNumber (1), lifeTime (28000ms)
- **Spawn unit**: FireSpirits with kamikaze behavior and splash damage projectiles
- **Death spawn**: deathSpawnCount (1) - spawns 1 Fire Spirit when destroyed
- **Fire Spirits stats**: hitpoints (90), damage (81), speed (120), range (2500), kamikaze (true)
- **Projectile mechanics**: FireSpiritsProjectile with area damage (radius 2300)

## Notes
- The card exists in gamedata.json as "FirespiritHut" with englishName "Furnace"
- Building entity framework exists but lacks spawner building functionality
- No spawn timer logic for periodic unit generation
- Missing death spawn mechanics for building destruction
- Fire Spirits troops not implemented with their kamikaze behavior
- Data loading in CardDataLoader missing key building spawn properties
- No SpawnerBuilding class or periodic spawn system in entities.py
- Core game architecture needs spawner building support before Furnace can be implemented