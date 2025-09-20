# Goblin Machine Card Audit

## Card Details
- **Card**: Goblin Machine
- **Elixir**: 5 (from gamedata.json)
- **Category**: Troop
- **Rarity**: Legendary
- **ID**: 26000096

## Implemented
- ❌ **Not implemented** - No code references found in entities.py, dynamic_spells.py, engine.py, or arena.py

## Missing (from gamedata.json)
- **Basic troop attributes**: HP (900), damage (83), range (1.2 tiles), speed (60), sight range (5.5 tiles)
- **Attack mechanics**: Hit speed (1.2s), load time (0.7s), attacks ground targets only
- **Special rocket ability**: Long-range rocket attack with 5.0 tile range, 2.5 tile minimum range
- **Rocket projectile**: Area damage (153 damage, 1.5 tile radius), reduced crown tower damage (-50%)
- **Targeting system**: Rocket has specific targeting filters and visual indicators
- **Action timing**: Rocket has 1.5s load time, 1.0s attack delay, 2.5s cooldown
- **Visual effects**: Target indication, projectile loading/hiding animations

## Notes
- **Name mapping**: Card is referenced as "GoblinMachine" in gamedata.json (camelCase)
- **Complex mechanics**: The rocket ability appears to be a special secondary attack with different range, damage, and targeting rules than the basic attack
- **Implementation gap**: This is a legendary card with unique mechanics that would require significant custom implementation
- **Elixir discrepancy**: Task specified 3 elixir but gamedata.json shows 5 elixir cost