# Firecracker Card Implementation Audit

## Card Details
- **Card**: Firecracker
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Common

## GameData.json Analysis
From gamedata.json, Firecracker has these key capabilities:
- **Hitpoints**: 119
- **Speed**: 90 (Fast speed - TID_SPEED_4)
- **Range**: 6000 (6.0 tiles - long range)
- **Hit Speed**: 3000ms (3.0 seconds)
- **Sight Range**: 8500 (8.5 tiles)
- **Collision Radius**: 500 (0.5 tiles)
- **Targeting**: Air and Ground (TID_TARGETS_AIR_AND_GROUND)
- **Projectile**: FirecrackerProjectile with spawnProjectileData
  - **Main Damage**: From projectile itself
  - **Explosion**: FirecrackerExplosion with 25 damage, 400 radius, spawns 5 projectiles
  - **Explosion Projectiles**: 5 projectiles with area damage targeting air and ground

## Key Mechanics (From gamedata.json)
1. **Projectile Attack**: Shoots FirecrackerProjectile that creates explosion
2. **Multi-Shrapnel Explosion**: On impact, spawns 5 area damage projectiles
3. **Area Damage**: Explosion projectiles have radius for splash damage
4. **Air/Ground Targeting**: Can attack both air and ground units

## Implemented
- ✅ **Basic Troop Mechanics**: Movement, targeting, attack cooldown (entities.py:240-690)
- ✅ **Projectile System**: General projectile creation and movement (entities.py:769-826)
- ✅ **Area Damage**: Splash damage with hitbox collision detection (entities.py:803-825)
- ✅ **Multi-Projectile Spawning**: spawnProjectileData support (dynamic_spells.py:32-34)
- ✅ **Air/Ground Targeting**: TargetType.BOTH with air unit detection (entities.py:22-24, 174-192)

## Missing
- ❌ **Firecracker-Specific Implementation**: No dedicated Firecracker class or logic
- ❌ **5-Shrapnel Explosion**: While multi-projectile system exists, Firecracker's specific 5-projectile explosion pattern not implemented
- ❌ **Recoil Mechanics**: Post-attack backward movement (1 tile) not implemented
- ❌ **Firecracker Projectile**: Specific projectile class with explosion behavior
- ❌ **Card Registration**: Firecracker not found in codebase searches

## Notes
- **Name Mapping**: Card name matches exactly ("Firecracker" in gamedata.json)
- **Architecture**: Codebase has solid foundation with projectile, area damage, and multi-spawn systems
- **Implementation Gap**: Firecracker appears to be completely unimplemented despite supporting systems existing
- **Priority**: Medium - requires creating specific projectile logic and recoil mechanics, but core systems are in place

**Key Files for Implementation**:
- `src/clasher/entities.py` - Troop and projectile base classes
- `src/clasher/dynamic_spells.py` - Multi-projectile spell type detection
- Need to add Firecracker-specific projectile explosion behavior and recoil mechanics