# Tornado Card Implementation Audit

## Card Details
- **Card**: Tornado
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Epic
- **Type**: Area Effect

## Implemented
- **Spell class structure**: `TornadoSpell` class in `src/clasher/spells.py:95`
- **Area effect creation**: Creates `AreaEffect` entity with tornado properties
- **Pull mechanics**: `_apply_tornado_pull()` method in `src/clasher/entities.py:415` pulls entities toward center
- **Damage over time**: Applies damage per second to affected entities
- **Duration handling**: 3-second lifetime with automatic cleanup
- **Hitbox collision**: Proper radius-based collision detection for affected entities
- **Entity filtering**: Only affects enemy entities, not caster's own units

## Missing
- **Incorrect damage values**: Game data shows 60 damage per second, implementation uses 35
- **Incorrect duration**: Game data shows 1.05 seconds, implementation uses 3.0 seconds
- **Incorrect radius**: Game data shows 5500 units (5.5 tiles), implementation uses 3000 units (3 tiles)
- **Missing crown tower damage reduction**: Game data specifies -83% damage to crown towers
- **Missing hit frequency**: Game data shows 550ms hit frequency, not implemented
- **Missing air targeting**: Game data specifies `hitsAir: true`, implementation unclear
- **Missing buff time**: Game data shows 500ms buff time, not implemented
- **Missing hit speed**: Game data shows 50ms hit speed, not implemented

## Notes
- **Name mapping**: Card name matches exactly between game data and implementation
- **Core mechanics**: Pulling mechanic is implemented but with incorrect parameters
- **Area effect**: Uses generic `AreaEffect` class with tornado-specific properties
- **Source of truth**: All missing mechanics verified from `gamedata.json` Tornado entry
- **Implementation status**: Basic functionality exists but needs parameter tuning to match official game data