# Royal Giant Card Audit

## Card Details
- **Card**: Royal Giant
- **Elixir**: 6
- **Category**: Troop
- **Rarity**: Epic (based on gamedata.json structure)

## Implemented
- **Basic troop mechanics** - Movement, health, damage (entities.py:240-690)
- **Building-only targeting** - `targets_only_buildings` flag implemented (entities.py:169-171, data.py:45)
- **Projectile attacks** - RoyalGiantProjectile with ranged damage (entities.py:298-400)
- **Speed stat** - Movement speed of 45 tiles/min (gamedata.json)
- **Hitpoints** - 1236 HP at level 1 (gamedata.json)
- **Attack range** - 5000 game units (5 tiles) (gamedata.json)
- **Hit speed** - 1700ms (1.7 seconds) (gamedata.json)
- **Load time** - 800ms attack windup (gamedata.json)
- **Collision radius** - 750 game units (gamedata.json)
- **Ground-only attacks** - `attacksGround: true` (gamedata.json)

## Missing
- **Card instantiation** - No specific Royal Giant class or spawn logic found
- **Projectile specifics** - RoyalGiantProjectile class not implemented
- **Stat scaling** - Level-based damage/HP scaling not applied to Royal Giant
- **Visual assets** - No sprite/icon references found

## Notes
- Core targeting logic exists in `entities.py:169-171` with `targets_only_buildings` flag
- Generic troop framework supports all required mechanics (projectiles, building targeting, movement)
- Royal Giant appears to be a "ready to implement" card - all base systems exist
- Name mapping: "Royal Giant" in gamedata.json matches expected naming convention
- No evolution mechanics found (consistent with task requirements)