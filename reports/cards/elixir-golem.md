# Elixir Golem Implementation Audit

## Card Details
- **Card**: Elixir Golem
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Ground troop that targets buildings only

## Implemented
- **Basic troop mechanics** (src/clasher/entities.py:240-690) - Movement, targeting, combat
- **Building-only targeting** (src/clasher/entities.py:168-171) - `targets_only_buildings` flag
- **Death spawn system** (src/clasher/battle.py:640-680) - Generic death spawn handling for all troops
- **Multi-stage death spawning** (gamedata.json:ElixirGolem) - Main golem → 2 Golemites → 4 Blobs
- **Spawn character data structure** (src/clasher/data.py:58-60) - `death_spawn_character`, `death_spawn_count`, `death_spawn_character_data`
- **Card stats loading** (src/clasher/data.py:220-225) - Death spawn data parsing from gamedata.json

## Missing
- **Elixir drop mechanics** - When any Elixir Golem stage dies, it should award elixir to the opponent:
  - Main Golem: 1 elixir
  - Each Golemite: 0.5 elixir
  - Each Blob: 0.5 elixir
- **Elixir drop implementation** - No elixir award system exists in the codebase
- **Elixir Golem card definition** - No specific card class or configuration found

## Notes
- The death spawn system is generically implemented and should handle the Elixir Golem's splitting mechanic
- gamedata.json contains complete death spawn chain: ElixirGolem1 → ElixirGolem2 (2x) → ElixirGolem4 (4x)
- All stages target buildings only (`tidTarget": "TID_TARGETS_BUILDINGS`)
- The core missing feature is the elixir drop mechanic, which is a unique gameplay element not present in other cards
- No explicit Elixir Golem class found - relies on generic troop mechanics with death spawn data