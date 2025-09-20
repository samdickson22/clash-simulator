# Spear Goblins - Implementation Audit

## Card Details
- **Card**: Spear Goblins
- **Elixir**: 2
- **Category**: Troop
- **Rarity**: Common
- **Type**: Ranged troop (spawns 3 units)

## Official Mechanics (Wiki)
- Fast, single-target, ranged troops
- Deploy 3 units per card
- Low hitpoints and damage
- Medium range (5 tiles)
- Target both air and ground units

## Gamedata.json Analysis
Based on the Spear Goblins entry in gamedata.json:

**Core Properties:**
- `summonNumber`: 3 (deploys 3 units)
- `summonDeployDelay`: 100ms (staggered deployment)
- `manaCost`: 2 elixir
- `rarity`: "Common"
- `unlockArena`: "Arena1"

**Individual Spear Goblin Unit Stats:**
- `hitpoints`: 52
- `damage`: 32 (via projectile)
- `range`: 5500 game units (5.5 tiles)
- `speed`: 120 tiles/min (fast movement)
- `hitSpeed`: 1700ms
- `loadTime`: 1300ms
- `sightRange`: 5500 game units (5.5 tiles)
- `collisionRadius`: 500 game units (0.5 tiles)
- `attacksGround`: true
- `targetType`: "TID_TARGETS_AIR_AND_GROUND"

**Projectile System:**
- Uses `SpearGoblinProjectile` with:
  - `speed`: 500
  - `damage`: 32
  - Source: "projectiles"

## Implementation Status

### ✅ Implemented
- **Troop base functionality**: Complete troop system in `src/clasher/entities.py:240-690`
- **Ranged projectile attacks**: Generic projectile system in `src/clasher/entities.py:769-826` handles Spear Goblins projectiles
- **Multi-unit deployment**: `summonNumber` and `summonDeployDelay` properties supported in `src/clasher/data.py:189-191`
- **Air/ground targeting**: `TargetType.BOTH` and targeting logic in `src/clasher/entities.py:22-24, 158-214`
- **Movement and pathfinding**: Complete troop movement system in `src/clasher/entities.py:427-690`
- **Basic combat**: Damage dealing, hitpoints, attack cooldowns in `src/clasher/entities.py:251-308`

### ❌ Missing
- **No specific Spear Goblins class**: No dedicated implementation for Spear Goblins
- **No projectile damage handling**: The comment in `src/clasher/battle.py:585` mentions projectile damage but no specific implementation for Spear Goblins
- **No visual representation**: No sprite or model definitions found
- **No sound effects**: No audio implementation
- **No level scaling**: Level 11 stats hardcoded, no dynamic leveling

### ⚠️  Ambiguities
- **Name mapping**: Gamedata uses "SpearGoblins" but codebase may use different naming
- **Projectile integration**: While projectile system exists, specific integration for Spear Goblins is unclear
- **Deployment positioning**: How the 3 goblins are positioned relative to each other when spawned

## Notes
The Spear Goblins card data is properly defined in gamedata.json with all necessary stats and properties. The core game engine has all the required systems (troops, projectiles, targeting, movement) to support Spear Goblins functionality. However, there appears to be no specific implementation class or dedicated code for Spear Goblins - they would rely on the generic troop and projectile systems.

The implementation likely works through the generic systems but lacks card-specific optimizations or special behaviors that might be needed for authentic Spear Goblins gameplay.