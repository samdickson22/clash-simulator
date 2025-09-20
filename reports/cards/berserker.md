# Berserker Implementation Audit

**Card:** Berserker
**Elixir:** 2
**Category:** Troop
**Rarity:** Common

## Implemented
- Basic troop framework (src/clasher/entities.py:108 - Troop class)
- Health and damage system (src/clasher/entities.py:35-36)
- Ground targeting (src/clasher/entities.py:22)
- Movement and pathfinding (src/clasher/entities.py:110-120)
- Attack cooldown and timing (src/clasher/entities.py:42-43)
- Combat state management (src/clasher/entities.py:46-48)

## Missing
- Berserker-specific implementation - No specific class or instantiation found in codebase
- Fast attack speed mechanic (hitSpeed: 500ms from gamedata.json)
- Specific stats: 350 HP, 40 damage, 5500 sight range (gamedata.json)
- Ground-only targeting implementation (attacksGround: true from gamedata.json)
- Deploy time: 1000ms (gamedata.json)
- Speed: 90 (gamedata.json)
- Load time: 300ms (gamedata.json)

## Notes
- Berserker appears to be completely unimplemented in the current codebase
- Only generic troop framework exists that could support Berserker implementation
- No name mapping found between "Berserker" and any implemented classes
- Gamedata.json shows standard melee troop stats with no special abilities
- Card ID: 26000102, source: "spells_characters" in gamedata.json