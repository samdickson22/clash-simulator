# Zap Card Implementation Audit

## Card Details
- **Name**: Zap
- **Elixir**: 2
- **Category**: Spell
- **Rarity**: Common

## Implemented
- Area damage with 2.5 tile radius (src/clasher/spells.py:425)
- Stun effect for 0.5 seconds (src/clasher/spells.py:61, src/clasher/entities.py:apply_stun)
- Targets both air and ground units (gamedata.json: hitsAir=true, hitsGround=true)
- Instant damage application (DirectDamageSpell class)
- Hitbox-based collision detection (src/clasher/spells.py:25-37)
- Crown tower damage reduction (-70%) (gamedata.json)

## Missing
- Visual effects (lightning bolt animation)
- Sound effects

## Notes
- Zap is implemented as DirectDamageSpell with stun_duration=0.5
- Damage value in code (159) differs from gamedata.json (75) - potential level discrepancy
- Radius correctly mapped: 2500 in gamedata.json → 2.5 tiles in code
- Stun implemented via entity.apply_stun() method with timer system
- Only affects enemy entities (onlyEnemies: true in gamedata.json)