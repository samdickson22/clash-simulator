# Rocket Card Implementation Audit

## Card Details
- **Card**: Rocket
- **Elixir**: 6
- **Category**: Spell
- **Rarity**: Rare

## Implemented
- Projectile spell with travel speed (350 tiles/min = 5.83 tiles/sec) - `src/clasher/spells.py:429`
- Area damage with 2.0 tile radius - `src/clasher/spells.py:429`
- Base damage of 580 - `src/clasher/spells.py:429`
- Targets both air and ground units - `src/clasher/spells.py:71-100`

## Missing
- **Pushback/knockback effect**: 1800 pushback value in gamedata.json:8425 but no implementation in ProjectileSpell class
- **Crown tower damage reduction**: -75% damage to crown towers in gamedata.json:8424 but no special handling in codebase
- **Projectile visualization**: Rocket-specific projectile sprite/animation (only generic Projectile class used)

## Notes
- Basic projectile functionality exists through ProjectileSpell class
- Values from gamedata.json are correctly mapped: radius (2000→2.0 tiles), damage (580), speed (350/60)
- No evolution mechanics to consider
- Missing the two key distinguishing features: knockback and crown tower damage reduction