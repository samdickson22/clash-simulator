# Poison Card Implementation Audit

## Card Details
- **Card**: Poison
- **Elixir**: 4
- **Category**: Spell
- **Rarity**: Epic

## Implemented
- Basic spell registration (src/clasher/spells.py:456)
- DirectDamageSpell class instantiation (src/clasher/spells.py:41-67)
- Hitbox-based collision detection (src/clasher/spells.py:25-37)
- Instant damage application in radius (src/clasher/spells.py:55-57)

## Missing
- **Area effect with duration**: Poison should create a persistent area effect for 8 seconds (gamedata.json: lifeDuration: 8000)
- **Damage over time**: Currently deals instant damage, should deal 36 damage per second over time (gamedata.json: damagePerSecond: 36)
- **Slow effect**: Should reduce enemy speed by 15% (gamedata.json: speedMultiplier: -15)
- **Hit frequency**: Should apply damage every 1 second (gamedata.json: hitFrequency: 1000)
- **Crown tower damage reduction**: Should only deal 25% damage to crown towers (gamedata.json: crownTowerDamagePercent: -75)
- **Buff system**: Poison applies a debuff buff to enemies, not implemented

## Notes
- **Name mapping**: Card is correctly named "Poison" in both code and gamedata.json
- **Radius**: Current implementation uses 3000.0 units, gamedata.json specifies 3500 units
- **Type mismatch**: Poison is implemented as DirectDamageSpell but should be an AreaEffectSpell with debuff mechanics
- **Core mechanic gap**: Poison is fundamentally a damage-over-time area effect spell, but current implementation treats it as instant damage
- **Buff system dependency**: Missing buff/debuff system required for speed reduction and damage-over-time effects