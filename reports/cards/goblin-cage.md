# Goblin Cage Implementation Audit

## Card Details
- **Card**: Goblin Cage
- **Elixir**: 4
- **Category**: Building
- **Rarity**: Rare
- **Type**: Building with death spawn

## Implemented
- Building entity class (src/clasher/entities.py:693)
- Death spawn system (src/clasher/battle.py:644-725)
- Card stats loading system (src/clasher/data.py:54-57, 210-213)
- Generic projectile support for buildings (src/clasher/entities.py:728-739)
- Building lifecycle management (src/clasher/entities.py:696-726)

## Missing
- **Lifetime system**: Building despawns after 20 seconds (lifeTime: 20000 in gamedata.json:7946)
- **GoblinBrawler spawn**: Death spawns GoblinBrawler with specific stats (gamedata.json:7951-7968)
- **Specific Goblin Cage implementation**: No dedicated class or configuration found
- **Hit speed**: 10 second attack cycle (hitSpeed: 10000 in gamedata.json:7945)
- **Collision radius**: 1000 unit radius (gamedata.json:7947)
- **Death spawn count**: Spawns exactly 1 GoblinBrawler (deathSpawnCount: 1 in gamedata.json:7948)

## Notes
- Goblin Cage appears to be completely missing from the codebase despite having full gamedata.json entry
- No references to "GoblinCage", "GoblinBrawler", or card ID 27000012 found in source files
- Building foundation exists but Goblin Cage-specific implementation is absent
- Death spawn system is implemented and ready for Goblin Cage's GoblinBrawler spawn mechanic
- Card data mapping supports all necessary fields (death_spawn_character, death_spawn_count, death_spawn_character_data)