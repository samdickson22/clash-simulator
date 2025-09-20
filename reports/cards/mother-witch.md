# Mother Witch Implementation Audit

## Card Details
- **Card**: Mother Witch
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ranged attacker with curse mechanic

## Implemented
- **Basic troop mechanics** (src/clasher/entities.py:240-690)
  - Movement, targeting, attack patterns
  - Projectile-based ranged attacks
  - Standard collision detection and pathfinding
- **Death spawn system** (src/clasher/battle.py:395-451)
  - Generic framework for death-spawned units
  - Voodoo Hog spawning logic
- **Buff framework** (src/clasher/data.py:59-63)
  - Basic buff data structure in CardStats
  - Support for buff timing and effects
- **Projectile system** (src/clasher/entities.py:323-400)
  - VoodooProjectile creation and movement
  - Splash damage on projectile impact

## Missing
- **Buff-on-damage mechanic** (gamedata.json: WitchMother.buffOnDamageTime/buffOnDamageData)
  - No implementation of applying VoodooCurse buff when dealing damage
  - Missing 5-second buff duration tracking
  - No buff expiration handling in take_damage method
- **Curse death spawn** (gamedata.json: VoodooCurse.deathSpawnCount/deathSpawnData)
  - Death spawn system exists but not triggered by buffed units
  - Missing curse-to-death-spawn linkage
- **Projectile buff application** (gamedata.json: VoodooProjectile.targetBuffData)
  - No buff application when projectile hits target
  - Missing curse transfer from projectile to target

## Notes
- **Name mapping**: gamedata.json uses "WitchMother" as internal name
- **Core infrastructure present**: Death spawn and buff systems exist but lack curse-specific integration
- **Key gap**: No implementation of the "curse → death spawn" chain that defines Mother Witch's unique mechanic
- **Voodoo Hog data**: Complete stats exist in gamedata.json for the spawned unit
- **Missing integration**: Buff-on-damage and projectile-to-target buff application not implemented