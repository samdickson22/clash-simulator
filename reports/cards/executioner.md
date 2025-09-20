# Executioner Card Audit Report

## Card Information
- **Card**: Executioner (AxeMan)
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Ground Troop (Air & Ground targeting)

## Implemented
- ✅ Basic troop spawning and movement (src/clasher/entities.py:240-690)
- ✅ Health and damage systems (src/clasher/entities.py:35-71, 72-107)
- ✅ Area damage/splash damage support (src/clasher/entities.py:80-86, 90-107)
- ✅ Projectile system with splash radius (src/clasher/entities.py:317-399, 769-826)
- ✅ Ground troop targeting (air and ground) (src/clasher/entities.py:174-176, 188-191)
- ✅ Hitbox-based collision detection (src/clasher/entities.py:101-106, 813-825)
- ✅ Status effect system (stun, slow) (src/clasher/entities.py:108-135)

## Missing
- ❌ **Boomerang projectile mechanic** - The core mechanic where axe travels out AND returns, dealing area damage both ways (gamedata.json: `pingpongVisualTime: 1500`)
- ❌ **Special projectile type** - No `BoomerangProjectile` or similar class exists in entities.py
- ❌ **Double-hit area damage** - Current Projectile class only deals damage once at target location, not on both outbound and return paths
- ❌ **Visual ping-pong timing** - The `pingpongVisualTime` property in gamedata.json is not implemented
- ❌ **Executioner-specific entity class** - No dedicated class for the Executioner troop type
- ❌ **AxeManProjectile specific handling** - The projectile exists in gamedata.json but has no special implementation for its unique behavior

## Notes
- **Name mapping**: Card is named "AxeMan" in gamedata.json but displays as "Executioner" (englishName field)
- **Core mechanic missing**: The defining feature of Executioner - the boomerang axe that hits enemies both going out and coming back - is completely unimplemented
- **Current fallback**: If spawned, would likely function as a standard projectile troop with single-hit area damage, missing the unique double-hit mechanic
- **Projectile range**: Has extended projectile range (7500 units vs typical 4500-5500) to accommodate the out-and-back travel pattern
- **Area damage radius**: Has significant area damage (1000 radius) that should apply on both outbound and return paths

## Gamedata.json Key Properties
```json
{
  "projectileData": {
    "name": "AxeManProjectile",
    "pingpongVisualTime": 1500,  // ❌ NOT IMPLEMENTED
    "projectileRange": 7500,     // Extended for out-and-back
    "radius": 1000,             // Large area damage radius
    "tid": "TID_SPELL_ATTRIBUTE_AREA_DAMAGE"
  }
}
```