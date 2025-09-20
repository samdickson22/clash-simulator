# Suspicious Bush Implementation Audit

## Card Details
- **Card**: Suspicious Bush
- **Elixir**: 2
- **Category**: Troop
- **Rarity**: Rare
- **Targets**: Buildings only

## Implemented
- Basic troop movement and targeting (entities.py:240, battle.py:638-725)
- Death spawn mechanics framework (battle.py:680-725)
- Kamikaze behavior support in data structure (data.py:56, 212)

## Missing
- **Bush Invisibility**: The `BushInvisibility` buff that makes the bush move invisibly is not implemented
- **Death Spawn Action**: The specific action `SuspiciousBush_SpawnBushGoblin` that spawns two Bush Goblins on death is not implemented
- **Bush Goblin Unit**: The `BushGoblin` character unit is not defined in the codebase
- **Building-only Targeting**: The `tidTarget": "TID_TARGETS_BUILDINGS"` restriction is not properly enforced
- **Zero Damage**: The card has 0 damage but this kamikaze behavior is not handled

## Notes
- The death spawn system exists in battle.py:680-725 but needs the specific Bush Goblin spawn data
- The invisibility buff system needs to be implemented to support the Bush's unique stealth movement
- According to gamedata.json, the Bush spawns two Bush Goblins via `SuspiciousBush_SpawnBushGoblin1` and `SuspiciousBush_SpawnBushGoblin2` actions
- The Bush has `kamikaze: true` but no death explosion damage is currently implemented