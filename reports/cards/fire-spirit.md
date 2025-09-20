# Fire Spirit Card Implementation Audit

## Card Information
- **Card**: Fire Spirit
- **Elixir**: 1
- **Category**: Troop
- **Rarity**: Common
- **Type**: Air troop (kamikaze)

## Implemented
- ✅ Basic troop infrastructure (`src/clasher/entities.py`)
- ✅ Data loading from gamedata.json (`src/clasher/data.py`)
- ✅ Card deployment system (`src/clasher/battle.py`)
- ✅ Name mapping and card recognition
- ✅ Hitbox collision data (`hitboxes.json`)
- ✅ Standard movement and targeting mechanics
- ✅ General projectile system (exists but not Fire Spirit specific)

## Missing
- ❌ **Kamikaze death explosion** - Core mechanic not implemented despite `kamikaze: true` flag
- ❌ **Projectile area damage** - 2.3 tile splash radius from projectileData not utilized
- ❌ **Death spawn area damage** - Explosion on death dealing 81 damage in 2.3 tile radius
- ❌ **Air unit classification** - Should be marked as air unit (flying troop)
- ❌ **Swarm behavior** - Coordinated movement for multiple Fire Spirits

## Notes
- The gamedata.json properly defines Fire Spirit with `kamikaze: true` and projectile splash radius of 2300 (2.3 tiles)
- Infrastructure exists for projectiles and area damage, but Fire Spirit-specific implementation is missing
- Card is deployable but lacks its signature explosive death mechanic
- Missing the visual/audio feedback for explosion effects
- No special handling for air unit pathfinding (Fire Spirits should fly over river)