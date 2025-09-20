# Minions Card Audit Report

## Card Details
- **Card**: Minions
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Common

## Implemented
- **Basic troop mechanics** - `src/clasher/entities.py:240` (Troop class)
- **Air unit status** - `src/clasher/entities.py:48` (is_air_unit flag)
- **Projectile attacks** - `src/clasher/entities.py:317-322` (projectile detection and creation)
- **Air targeting** - `src/clasher/entities.py:174-176` (can attack air and ground)
- **Movement and pathfinding** - `src/clasher/entities.py:427-533` (air units bypass bridges)
- **Target acquisition** - `src/clasher/entities.py:159-214` (nearest target with priority rules)
- **Damage dealing** - `src/clasher/entities.py:72-106` (damage and splash damage systems)
- **Status effects** - `src/clasher/entities.py:108-135` (stun, slow, etc.)
- **Card data structure** - `gamedata.json` (complete Minions card entry)

## Missing
- **Triangle spawn formation** - gamedata.json shows summonNumber: 3 but code spawns in random positions
- **Summon deploy delay** - gamedata.json shows summonDeployDelay: 100ms but not implemented in spawn logic
- **MinionSpit projectile** - gamedata.json defines projectileData but code uses generic projectile system
- **Air unit collision rules** - No special collision handling for air-to-air interactions
- **Specific spawn offsets** - No implementation of triangle formation offsets for the 3 spawned Minions

## Notes
- **Name mapping**: Code uses "Minions" (plural) while gamedata.json shows individual unit as "Minion" (singular)
- **Air unit behavior**: Properly implemented as air units that bypass bridge pathfinding and can attack both air/ground targets
- **Projectile system**: Uses generic projectile system rather than specific "MinionSpit" projectile type
- **Spawn mechanics**: Basic spawn implemented but lacks the authentic triangle formation mentioned in official sources
- **No special gimmicks**: Minions have no charge, chain, retarget, death effects, or other complex mechanics according to gamedata.json