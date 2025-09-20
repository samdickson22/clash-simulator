# Mega Knight Card Implementation Audit

## Card Info
- **Card**: Mega Knight
- **Elixir**: 7
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop

## Implemented
- Basic troop movement and pathfinding (`src/clasher/entities.py:101-150`)
- Area damage on attacks (`src/clasher/entities.py:81-100`)
- Basic combat system (targeting, attacking, taking damage) (`src/clasher/entities.py:62-180`)
- Ground-only targeting (from gamedata: `tidTarget": "TID_TARGETS_GROUND"`)
- Health, damage, speed, range, sight range stats (`gamedata.json:3868-3877`)

## Missing
**Core Mechanics:**
- Spawn damage - Area damage and knockback on deployment (gamedata: `projectileData` with `damage: 168`, `pushback: 1000`, `radius: 2200`)
- Jump/Dash ability - Teleport to targets with area damage (gamedata: `dashDamage: 210`, `dashMinRange: 3500`, `dashMaxRange: 5000`, `jumpSpeed: 250`)
- Jump height visualization (gamedata: `jumpHeight: 3000`)
- Area damage radius on attacks (gamedata: `areaDamageRadius: 1300`)
- Special knockback mechanics

**Animation/Visual Effects:**
- Spawn landing effect
- Jump/dash visual effects
- Impact effects

## Notes
- Card name mapping: "MegaKnight" in code matches gamedata.json entry
- Only references found are in `decks.json` (card list) and `random_battle.py` (name mapping)
- No specific Mega Knight implementation found - relies on generic Troop class
- Evolution data exists but was excluded per requirements
- Key missing features are the signature spawn impact and jump mechanics that define the card