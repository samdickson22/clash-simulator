# Bowler Card Implementation Audit

## Card Details
- **Card**: Bowler
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Character (Ground troop)

## Implemented
- **Ground targeting**: Attacks ground units only (gamedata.json:2090)
- **Rolling projectile**: Creates RollingProjectile that travels 7.5 tiles (entities.py:360-377)
- **Area damage**: Projectile has 1800 unit radius splash damage (gamedata.json:2102)
- **Pushback mechanics**: 1000 unit pushback force (gamedata.json:2101)
- **Angled pushback**: Pushes targets along projectile's travel direction (entities.py:1093-1095)
- **Troop stats**: HP (813), damage (113), hit speed (2.5s), range (4000), speed (45) (gamedata.json:2086-2089)
- **Projectile physics**: Speed 170, range 7500 units (gamedata.json:2099-2103)

## Missing
- **Linear boulder path**: Should roll in straight line, not arc toward target (current implementation calculates target direction)
- **Building targeting**: Should prioritize buildings over troops when in range
- **Boulder collision**: Boulder should stop at first building hit rather than passing through
- **Rolling animation**: Visual rolling effect not implemented
- **Sound effects**: Rolling boulder audio not present

## Notes
- **Name mapping**: Card name matches exactly ("Bowler")
- **Core mechanics**: The essential functionality is implemented through RollingProjectile class
- **Pushback behavior**: Uses directional pushback system, which is correct for Bowler's angled knockback
- **Implementation location**: src/clasher/entities.py:341-377 (projectile creation), entities.py:1093 (pushback logic)
- **Data source**: gamedata.json:2069-2109 (card definition)