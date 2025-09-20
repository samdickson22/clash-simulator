# Royal Recruits Card Audit

## Card Info
- **Card**: Royal Recruits
- **Elixir**: 7
- **Category**: Troop
- **Rarity**: Common

## Implemented
- Basic troop spawning (6 units) - `src/clasher/battle.py:230-231`
- Center-only deployment restriction (x: 6-11 tiles) - `src/clasher/battle.py:143-145`
- Standard troop AI and movement - `src/clasher/entities.py:240-690`
- Ground targeting and attack mechanics - `src/clasher/entities.py:240-690`

## Missing
- **Shield mechanics**: `shieldHitpoints: 94` present in gamedata but no shield implementation found
- **Shield-specific damage absorption**: No separate shield HP tracking in `src/clasher/entities.py`
- **Shield break effects**: No implementation for when shield is destroyed

## Notes
- Royal Recruits are referenced as both "RoyalRecruits" and "RoyalRecruits_Chess" in the code
- The card uses TID `TID_SPELL_GUARD_BATTALION` in gamedata
- Standard troop behavior is implemented but the signature shield mechanic is missing
- The individual recruit character data shows they have `shieldHitpoints: 94` but this isn't handled in the entity system