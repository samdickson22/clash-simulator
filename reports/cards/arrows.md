# Arrows Implementation Audit

## Card Details
- **Card**: Arrows
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Common

## Implemented
- **DirectDamageSpell base functionality** (src/clasher/spells.py:48-55)
- **Area damage with radius** (radius=400.0)
- **Instant damage application** (damage=144)
- **Spell registration** (src/clasher/spells.py:68)

## Missing
- **Three volley projectile system** - gamedata.json specifies `projectileWaves: 3` with `projectileWaveInterval: 200`
- **Multiple projectiles per volley** - gamedata.json specifies `multipleProjectiles: 10`
- **Projectile travel mechanics** - gamedata.json projectileData shows `speed: 1100` and `radius: 1400`
- **Reduced crown tower damage** - gamedata.json specifies `crownTowerDamagePercent: -75`
- **Proper hitbox scaling** - gamedata.json spell radius is 3500 vs code radius 400.0 (likely units mismatch)

## Notes
- Current implementation treats Arrows as instant area damage spell
- gamedata.json shows Arrows should behave as a multi-wave projectile spell
- Name mapping: gamedata.json "Arrows" → code "Arrows"
- Damage values: gamedata.json shows 48 damage per projectile × multiple projectiles × 3 waves = 144 total (matches code)
- Unit mismatch: gamedata uses coordinate units (3500) vs code uses tile units (400.0)