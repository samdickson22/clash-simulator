# Wall Breakers Implementation Audit

## Card Details
- **Card**: Wall Breakers
- **Elixir**: 2
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Building-targeting, Area damage, Kamikaze

## Implemented
- **Basic Troop Framework**: Found in `src/clasher/entities.py:240-689` - Troop class handles movement, targeting, and basic combat
- **Building Targeting**: `src/clasher/entities.py:169-171` - `targets_only_buildings` property supported
- **Area Damage**: `src/clasher/entities.py:81-107` - Area damage mechanics with splash radius support
- **Kamikaze Detection**: `src/clasher/data.py:56` - `kamikaze` boolean property in CardStats
- **Projectile System**: `src/clasher/entities.py:769-826` - Projectile handling for ranged attacks
- **Entity Status Effects**: `src/clasher/entities.py:108-136` - Stun, slow, and other status effects
- **Collision Detection**: `src/clasher/entities.py:28-37` - Hitbox-based collision system

## Missing
- **Kamikaze/Suicide Attack Logic**: No implementation of self-destruct on attack/impact
- **On-Kill Explosion Effects**: No handling of death explosions or spawn-on-death mechanics
- **Wall Breaker-Specific Behavior**: No card-specific logic for Wall Breakers found in codebase
- **Projectile Integration**: Wall Breakers should create projectiles but no code connects them to projectile system
- **Area Damage on Death**: Kamikaze units should deal area damage when destroyed, not implemented

## Notes
- **Name Mapping**: Card is named "Wallbreakers" in gamedata.json but "Wall Breakers" in official sources
- **Mechanics Source**: Based on gamedata.json, Wall Breakers have:
  - `kamikaze: true` - should destroy themselves on attack
  - `areaDamageRadius: 1500` - deals area damage (1.5 tile radius)
  - `tidTarget: "TID_TARGETS_BUILDINGS"` - only targets buildings
  - `summonNumber: 2` - spawns 2 units
  - High speed (120) but low HP (129)
- **Implementation Gap**: While the framework exists for area damage and targeting, the kamikaze suicide mechanic is completely missing
- **No Spell Registry Entry**: No mention of Wall Breakers in spell registry or dynamic loading system