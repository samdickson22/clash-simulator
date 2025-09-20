# Spirit Empress Implementation Audit

## Card Info
- **Card**: Spirit Empress
- **Elixir**: Variable (3 for Ground form, 6 for Air/Mounted form)
- **Category**: Troop
- **Rarity**: Legendary

## Implemented
- Basic spell registry entry as DirectDamageSpell with 0 damage (placeholder)
- Location: `src/clasher/spells.py:471, 508`

## Missing
- **Variable Elixir Form Mechanic**: Core mechanic where form depends on player's Elixir count (3 elixir = Ground melee form, 6 elixir = Air ranged form)
- **Ground Form**: Melee combat, ground targeting only
- **Air Form**: Medium ranged combat, air & ground targeting
- **Troop Summoning**: Actual troop deployment with character data (`MergeMaiden_Normal`, `MergeMaiden_Mounted`)
- **Form Switching Logic**: Dynamic form change based on Elixir availability
- **Movement & Pathfinding**: Basic troop movement and AI
- **Combat System**: Attack targeting, damage dealing, hit speed
- **Visual Forms**: Separate sprites/models for ground vs air forms

## Notes
- Current implementation is a placeholder spell with 0 damage, not a functional troop
- Name mapping: `MergeMaiden` in codebase = `Spirit Empress` in game
- Gamedata shows two separate cards: `MergeMaiden_Normal` (3 elixir ground) and `MergeMaiden_Mounted` (6 elixir air)
- The variable elixir mechanic appears completely unimplemented
- No troop entity classes or combat logic found in the codebase