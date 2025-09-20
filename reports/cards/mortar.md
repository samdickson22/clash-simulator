# Mortar Card Implementation Audit

## Card Details
- **Card**: Mortar
- **Elixir**: 4
- **Category**: Building
- **Rarity**: Common
- **Target Type**: Ground only (TID_TARGETS_GROUND)

## Implemented
- ✅ Building entity system (`src/clasher/entities.py:693-766`)
- ✅ General building mechanics (stationary, attacks with cooldown)
- ✅ Projectile system for area damage (`src/clasher/entities.py:768-826`)
- ✅ Splash damage radius support (2000 units = 2.0 tiles)
- ✅ Building deployment system (`src/clasher/battle.py:159-160`)
- ✅ Hitbox-based collision detection for splash damage
- ✅ Lifetime system (30 seconds from gamedata)
- ✅ Load time and hit speed mechanics

## Missing
- ❌ **Long-range building behavior**: Mortar has 11.5 tile range (11500 units) but standard targeting logic may not properly handle extreme-range buildings
- ❌ **Ground-only targeting enforcement**: Code has targeting logic but may not properly restrict Mortar to ground targets only
- ❌ **Deploy time validation**: Mortar has 3.5s deploy time but building spawn system doesn't account for deployment delays
- ❌ **Sight range vs attack range**: Mortar has 11.5 tile sight range but standard buildings may have different sight/attack range relationships

## Notes
- **Name mapping**: Card name matches exactly between gamedata.json ("Mortar") and implementation expectations
- **Architecture**: Buildings use the same base `Building` class as towers, with projectile support for area damage
- **Projectile data**: Mortar projectile has speed 300, damage 104, radius 2000 (2.0 tiles) - all supported by existing projectile system
- **Lifetime**: 30 second lifetime is handled by standard entity lifecycle, no special implementation needed
- **Targeting**: Building targeting system exists but may need validation for ground-only restriction at extreme ranges
- **Deployment**: Building deployment system exists but deploy time delays are not currently implemented

## Recommendations
1. Verify ground-only targeting works correctly at 11.5 tile range
2. Consider implementing deploy time delays for buildings that have them
3. Test sight range vs attack range behavior for long-range buildings
4. Validate that Mortar's area damage radius (2.0 tiles) works correctly with hitbox collision system