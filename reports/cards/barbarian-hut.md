# Barbarian Hut Implementation Audit

## Card Information
- **Card**: Barbarian Hut
- **Elixir**: 6 (gamedata shows 6, user mentioned 7)
- **Category**: Building
- **Rarity**: Rare

## Implemented
- Building base class (`src/clasher/entities.py:Building`)
- Death spawn mechanics (`src/clasher/battle.py:_spawn_death_units`)
- CardStats loading with death spawn support (`src/clasher/data.py:CardStats`)
- Health system (455 HP)
- Collision radius (1000 units)
- Lifetime system (30000ms / 30 seconds)

## Missing
- **Periodic spawning**: `spawnInterval: 500ms`, `spawnNumber: 3`, `spawnPauseTime: 14000ms` - spawns 3 Barbarians every 14 seconds
- **Spawn character data**: `spawnCharacterData: Barbarian` - data for spawned Barbarians
- **Spawn mechanics in Building class**: No `time_since_spawn` tracking or periodic spawn logic
- **CardStats fields**: Missing `spawn_interval`, `spawn_number`, `spawn_pause_time`, `spawn_character_data` properties
- **Building spawn capability**: Building class only handles attacks, not unit spawning

## Notes
- **Elixir cost discrepancy**: User said 7 elixir, but gamedata.json shows 6 elixir (matches wiki)
- **Death spawn implemented**: Spawns 1 Barbarian on death (correctly implemented)
- **No evolution data**: Card has no evolution mechanics
- **Name mapping**: Uses "BarbarianHut" in code vs "Barbarian Hut" in display
- **Spawn pattern**: Should spawn 3 Barbarians every 14 seconds (14s pause + 0.5s interval)
- **Building lifetime**: 30 seconds duration correctly mapped to CardStats