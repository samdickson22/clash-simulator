# Skeleton King Card Audit

## Card Overview
- **Card**: Skeleton King
- **Elixir**: 4
- **Category**: Troop (Champion)
- **Rarity**: Champion

## Implemented
- **Basic Troop Mechanics**: Standard movement, targeting, and attack behaviors (`src/clasher/entities.py:240-690`)
- **Area Damage**: 1300 unit radius splash damage (`gamedata.json:areaDamageRadius`)
- **Ground Targeting**: Only attacks ground units (`attacksGround: true`)
- **Sight Range**: 5500 units for target acquisition
- **Collision Radius**: 1000 units for hitbox detection
- **Health**: 898 HP at base level
- **Damage**: 80 damage per attack at base level
- **Attack Speed**: 1600ms (1.6 seconds)
- **Movement Speed**: 60 units per minute

## Missing
- **Champion Ability System**: No implementation of champion abilities (2 elixir "Soul Summoning" ability with 20-second cooldown)
- **Ability Mechanics**: Missing soul collection from fallen troops and ability to spawn 6-16 skeletons
- **Ability Area Effect**: "SkeletonKingGraveyard" area effect object not implemented
- **Spawned Skeletons**: "SkeletonKingSkeleton" character type exists in data but no ability to spawn them
- **Champion Cooldown System**: No champion ability cooldown tracking or elixir cost for abilities
- **Ability Visual Effects**: No implementation of ability activation or area effect indicators

## Notes
- **Name Mapping**: Card exists in gamedata.json as "SkeletonKing" with matching ID 26000069
- **Data Completeness**: All base stats and ability data are present in gamedata.json
- **Architecture Gap**: The codebase has no champion-specific entity classes or ability systems
- **Implementation Status**: Skeleton King is partially implemented as a basic troop but lacks its defining champion ability
- **Ability Data**: The ability data includes:
  - `manaCost: 2` for ability activation
  - `cooldown: 20000` (20 seconds)
  - `resurrectBaseCount: 6` (minimum skeletons spawned)
  - `spawnLimit: 16` (maximum skeletons)
  - `lifeDuration: 10000` (graveyard duration)
  - `spawnInterval: 250` (skeleton spawn rate)
  - `spawnClones: true` (spawns actual units)

The Skeleton King exists in the game data and can be deployed as a basic troop, but its champion ability system is completely unimplemented in the current codebase.