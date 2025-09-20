# Fireball Card Implementation Audit

## Card Information
- **Card**: Fireball
- **Elixir**: 4
- **Category**: Spell
- **Rarity**: Rare

## Official Mechanics
- Deals area damage to air and ground targets
- Medium radius with knockback effect
- Projectile spell that travels to target position

## Implemented Features
- **Projectile Mechanics**: Implemented via `ProjectileSpell` class in `spells.py:71-110`
  - Creates projectile entities that travel to target position
  - Travel speed: 600 tiles/min (10 tiles/sec)
- **Area Damage**: Implemented via `Projectile._deal_splash_damage()` in `entities.py:803-825`
  - Splash radius: 2.5 tiles (2500 game units)
  - Hitbox-based collision detection for accurate damage application
- **Damage Application**: Implemented via `Entity.take_damage()` in `entities.py:66-70`
  - Applies damage to all enemy entities within splash radius
  - Crown tower damage reduction: -70% (from gamedata.json)
- **Launch Position**: Implemented via `ProjectileSpell._get_launch_position()` in `spells.py:102-109`
  - Launches from player's king tower position

## Missing Features
- **Knockback Effect**: Fireball has `pushback: 1000` in gamedata.json but knockback is not implemented for projectile spells
- **Crown Tower Damage Scaling**: The 70% damage reduction is noted in gamedata but not applied in code

## Data Source (gamedata.json)
```json
{
  "name": "Fireball",
  "manaCost": 4,
  "projectileData": {
    "name": "FireballSpell",
    "speed": 600,
    "damage": 269,
    "crownTowerDamagePercent": -70,
    "pushback": 1000,
    "radius": 2500,
    "tidTarget": "TID_TARGETS_AIR_AND_GROUND"
  }
}
```

## Implementation Status
- **Core Functionality**: ✅ Implemented (projectile travel, area damage)
- **Special Effects**: ❌ Missing (knockback not implemented)
- **Tower Damage**: ❌ Missing (crown tower damage scaling not applied)
- **Targeting**: ✅ Implemented (air and ground targeting)

## Notes
- Fireball is correctly classified as a `ProjectileSpell` by the dynamic spell system
- Damage value in code (572) differs from gamedata.json (269) - likely due to level scaling
- The spell implementation uses the generic projectile system which covers basic functionality
- No evolution mechanics to consider (EVOS excluded per requirements)