# Royal Ghost Implementation Audit

## Card Info
- **Card**: Royal Ghost
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop (hovering)

## Implemented
- Basic troop movement and pathfinding (`src/clasher/entities.py:240-690`)
- Area damage attacks (`src/clasher/entities.py:72-107`)
- Target acquisition and priority system (`src/clasher/entities.py:159-236`)
- Basic combat mechanics (damage, hitpoints, attack speed)
- Card data loading from gamedata.json (`src/clasher/data.py:102-303`)

## Missing
- **Invisibility/Stealth mechanic**: Card has `buffWhenNotAttackingTime: 1800` (1.8s) and `buffWhenNotAttackingData` with "Invisibility" buff - NOT IMPLEMENTED
- **Hovering/River crossing**: Should be able to cross river without using bridges - NOT IMPLEMENTED (treated as regular ground unit)
- **Visibility on attack**: Should become visible when attacking - NOT IMPLEMENTED
- **Invisibility after inactivity**: Should become invisible after 1.8s of not attacking - NOT IMPLEMENTED
- **Buff system**: No general buff/invisibility system in entities (`src/clasher/entities.py`)
- **Special targeting while invisible**: No special targeting rules for invisible units

## Notes
- Card data exists in gamedata.json with complete stats (HP: 473, Damage: 102, Speed: 90, Range: 1.2 tiles, Area damage: 1.0 tile radius)
- Card loads properly through CardDataLoader system
- The unique invisibility mechanics that define Royal Ghost are completely missing from the implementation
- Current implementation treats Royal Ghost as a basic area damage troop without its signature stealth abilities
- No invisibility status effect or buff system exists in the codebase to support this mechanic