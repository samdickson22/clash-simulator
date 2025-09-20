# Sparky Card Implementation Audit

## Card Overview
- **Card**: Sparky
- **Elixir**: 6
- **Category**: Troop
- **Rarity**: Legendary
- **Internal Name**: ZapMachine

## Game Data Analysis (gamedata.json)
- **Hitpoints**: 567
- **Damage**: 520 (per shot)
- **Hit Speed**: 4000ms (4.0 seconds)
- **Load Time**: 3000ms (3.0 seconds charge-up)
- **Range**: 5000 (5.0 tiles)
- **Sight Range**: 5000 (5.0 tiles)
- **Speed**: 45 (very slow movement)
- **Target Type**: Ground only
- **Projectile**: ZapMachineProjectile (1400 speed, 1800 radius splash damage)

### Key Mechanics from Game Data:
1. **Slow Movement**: Speed of 45 (one of the slowest troops)
2. **Long Charge-up**: 3000ms load time before firing
3. **Area Damage**: Projectile has 1800 radius splash damage
4. **Ground Target Only**: Cannot attack air units
5. **Projectile-based**: Uses projectiles instead of direct attacks

## Implementation Status

### ✅ Implemented:
- **Basic Troop Entity**: All core troop mechanics (movement, targeting, attacking) - `src/clasher/entities.py:240-690`
- **Projectile System**: General projectile handling for area damage - `src/clasher/entities.py:769-826`
- **Area Damage**: Splash damage mechanics using hitbox collision detection - `src/clasher/entities.py:803-825`
- **Status Effects**: Stun vulnerability system - `src/clasher/entities.py:108-140`
- **Target Priority**: Ground-only targeting, troop vs building priority - `src/clasher/entities.py:159-236`
- **Bridge Pathfinding**: Ground unit navigation - `src/clasher/entities.py:427-690`

### ❌ Missing:
- **Charge-up Mechanics**: No implementation of 3000ms load time before attacks
- **Stun Reset**: When stunned, charge-up should reset (no current implementation)
- **Slow Movement**: Speed of 45 not specifically implemented (uses generic speed)
- **Custom Projectile**: ZapMachineProjectile not specifically coded
- **Sparky-specific Behavior**: No unique handling for this legendary troop

## Notes
- **Name Mapping**: Internal name is "ZapMachine" but displays as "Sparky"
- **Data Source**: All mechanics derived from gamedata.json entry at ID 26000033
- **Implementation Gap**: While basic troop/projectile systems exist, Sparky's unique charge-up and stun-reset mechanics are not implemented
- **Assumptions**: Current implementation would treat Sparky as a standard projectile troop without its signature charge-up behavior