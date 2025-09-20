# Witch Card Implementation Audit

## Card Details
- **Card**: Witch
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Epic

## Implemented
- **Basic Troop Mechanics**: Movement, targeting, and combat system (src/clasher/entities.py:168)
- **Area Damage**: Projectile-based area damage functionality (src/clasher/entities.py:72-100)
- **Single Spawn Character**: Framework for spawning one character on deployment (src/clasher/entities.py:405-440)
- **Projectile System**: Area damage projectiles with splash radius (gamedata.json: WitchProjectile)

## Missing
- **Periodic Skeleton Spawning**: Witch should spawn 4 skeletons every 7 seconds, but only single deployment spawn exists
- **Skeleton Summon Logic**: No implementation for the repeated skeleton spawning mechanic (spawnNumber: 4, spawnPauseTime: 7000ms in gamedata.json)
- **Spawn Character Data**: Skeleton spawn data exists in gamedata.json but no Witch-specific periodic spawning logic

## Notes
- The codebase has a general spawning framework but lacks Witch-specific periodic skeleton summoning
- Witch exists in gamedata.json with complete stats including spawnNumber (4) and spawnPauseTime (7000ms)
- No dedicated Witch class found - appears to be handled by generic Troop class
- Area damage projectile system exists but needs Witch-specific implementation
- Skeleton unit data exists in gamedata.json for the spawned units