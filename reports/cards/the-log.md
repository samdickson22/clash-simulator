# The Log - Implementation Audit

## Card, Elixir, Category
- **Card**: The Log
- **Elixir**: 2
- **Category**: Spell
- **Rarity**: Legendary

## Implemented
- **RollingProjectile entity class** (`src/clasher/entities.py:915-972`) - Handles rolling projectiles with spawn chains
- **RollingProjectileSpell detection** (`src/clasher/dynamic_spells.py:25-27`) - Detects spells with spawnProjectileData
- **Basic ProjectileSpell definition** (`src/clasher/spells.py:289`) - Defined as basic projectile (incorrect implementation)
- **Knockback mechanics** (`src/clasher/entities.py:953-972`) - Physical knockback and attack reset
- **Ground-only targeting** (`src/clasher/entities.py:946`) - Skips air units

## Missing
- **LogProjectile spawn chain** - gamedata shows spawnChain:1 with LogProjectileRolling projectile
- **Dual-phase damage** - gamedata defines both initial LogProjectile (360 speed) and LogProjectileRolling (200 speed, 113 damage)
- **Reduced crown tower damage** - gamedata specifies crownTowerDamagePercent: -85 (15% damage to towers)
- **Elliptical hitbox** - gamedata defines radius:1950 and radiusY:600 for tall elliptical shape
- **Proper projectile range** - gamedata specifies projectileRange:10100 (10.1 tiles)
- **Pushback value** - gamedata defines pushback:700 for knockback distance

## Notes
- Current implementation uses generic ProjectileSpell instead of RollingProjectileSpell
- Name mapping: gamedata uses "TID_SPELL_LOG" but codebase references "Log"
- Damage values mismatch: gamedata shows 113 damage vs spells.py shows 240 damage
- RollingProjectile class exists and supports the mechanics but isn't being used for The Log
- The Log has a unique two-phase behavior: initial projectile spawn followed by rolling projectile