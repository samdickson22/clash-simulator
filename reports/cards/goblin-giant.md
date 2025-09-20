# Goblin Giant Card Implementation Audit

## Card Information
- **Card**: Goblin Giant
- **Elixir**: 6
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Building-targeting tank with spawned Spear Goblins

## Implemented
- **Base troop spawning system**: `src/clasher/battle.py:_spawn_troop()`
- **Troop movement and pathfinding**: `src/clasher/entities.py:Troop._move_towards_target()`
- **Building-only targeting**: `src/clasher/entities.py:Entity.get_nearest_target()` (targets_only_buildings logic)
- **Projectile attacks**: `src/clasher/entities.py:Troop._create_projectile()`
- **Troop death spawning**: `src/clasher/entities.py:Battle._spawn_death_units()`

## Missing
- **Goblin Giant card registration**: No specific "GoblinGiant" card found in SPELL_REGISTRY or card loading system
- **Spawn-on-summon mechanics**: Card has `spawnNumber: 2` for SpearGoblinGiant, but no implementation for summoning troops with main troop
- **SpearGoblinGiant unit**: The spawned Spear Goblins with death spawn mechanics are not implemented
- **SpearGoblinGiant death spawn**: Should spawn regular Spear Goblins when defeated (deathSpawnCount: 1)
- **Building targeting enforcement**: While targeting logic exists, it's not specifically enforced for building-only troops like Goblin Giant

## Notes
- **Name mapping**: Card appears as "GoblinGiant" in gamedata.json but may need "Goblin Giant" mapping for user input
- **Spawn mechanics**: The game supports troop spawning (e.g., Goblin Barrel), but not the "troop carrying other troops" mechanic
- **Death spawn chain**: Missing implementation for SpearGoblinGiant → Spear Goblin death spawn sequence
- **Architecture**: Game has good foundation with CardStats data structure supporting spawn_character_data and death_spawn_character_data

## Priority Features to Implement
1. Add Goblin Giant to card registry with proper stats mapping
2. Implement summon-time troop spawning for `spawnNumber` > 0
3. Add SpearGoblinGiant as a separate troop type with death spawn mechanics
4. Test building-only targeting behavior implementation