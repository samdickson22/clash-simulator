# Ram Rider Card Implementation Audit

## Card Details
- **Card**: Ram Rider
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop with spawn

## Official Mechanics (from Clash Royale Wiki)
- Ground troop that targets buildings
- After traveling 2 tiles, it charges, dealing double damage
- The Rider on its back attacks troops, slowing them by 70%

## Gamedata.json Analysis
From gamedata.json, Ram Rider has these explicit capabilities:

**Main Unit (Ram)**:
- `name`: "Ram"
- `chargeRange`: 200 (tiles)
- `damage`: 98, `damageSpecial`: 196 (double damage)
- `range`: 800, `sightRange`: 7500
- `targets`: "TID_TARGETS_BUILDINGS" (only buildings)
- `jumpHeight`: 4000, `jumpSpeed`: 160 (can jump)
- `spawnCharacterData`: spawns "RamRider" rider

**Spawned Unit (RamRider)**:
- `name`: "RamRider"
- `range`: 5500, `sightRange`: 5500
- `targets`: "TID_TARGETS_AIR_AND_GROUND" (troops)
- `projectileData`: "RamRiderBola" with 41 damage
- `targetBuffData`: "BolaSnare" with -70 speed multiplier

## Implementation Status

### Implemented
- **None** - Ram Rider is not implemented in the codebase

### Missing
- **Card definition** - No Ram Rider card found in codebase
- **Main Ram unit** - No "Ram" character implementation
- **Spawned RamRider unit** - No rider character implementation
- **Charge mechanics** - `chargeRange: 200` not implemented
- **Double damage on charge** - `damageSpecial: 196` not implemented
- **Building-only targeting** - Ram should only target buildings
- **Spawn mechanic** - Ram should spawn RamRider rider
- **Projectile attacks** - RamRider should use "RamRiderBola" projectiles
- **Slow effect** - "BolaSnare" with -70 speed multiplier not implemented
- **Jump ability** - `jumpHeight` and `jumpSpeed` not implemented

## Notes
- The Ram Rider card exists in gamedata.json with complete mechanics data
- No implementation exists in src/clasher/entities.py or related files
- This is a complex card requiring:
  1. Main Ram unit with charge mechanics and building-only targeting
  2. Spawned RamRider rider with projectile attacks and slow effects
  3. Integration between the two units
  4. Jump mechanics for river crossing
- The card uses a spawn mechanic similar to Battle Ram but with additional complexity from the ranged attacker