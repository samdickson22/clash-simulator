# Flying Machine Card Implementation Audit

## Card Details
- **Name**: Flying Machine
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Rare
- **Internal Name**: DartBarrell

## Implemented
- Basic troop spawning system (battle.py:166)
- Air/Ground targeting system (entities.py:242)
- Movement mechanics (entities.py:241)
- Range-based attack system (entities.py:38)
- Projectile system (entities.py:769)
- Hitpoint and damage scaling (battle.py:201-203)
- Troop entity framework (entities.py:240)

## Missing
- **Air unit classification**: "DartBarrell" not in air_units list (battle.py:197)
- **Flying mechanics**: is_air_unit not set to True for this card
- **Special projectile handling**: "DartBarrellProjectile" not specifically implemented
- **Card registration**: No specific spell class for Flying Machine in spells.py
- **Name mapping**: Internal name "DartBarrell" doesn't match display name "Flying Machine"

## Notes
- The card exists in gamedata.json as "DartBarrell" with englishName "Flying Machine"
- Has standard troop stats: 240 HP, 67 damage, 6 range, 90 speed
- Uses single-target projectile attacks
- Missing from hardcoded air units list, so will be treated as ground unit
- No special mechanics beyond basic ranged troop behavior
- Card type is correctly identified as troop for spawning purposes

**Sources**: gamedata.json:3952-3989, battle.py:197, entities.py:240, entities.py:769