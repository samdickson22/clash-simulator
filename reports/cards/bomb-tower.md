# Bomb Tower Implementation Audit

## Card Details
- **Card**: Bomb Tower
- **Elixir**: 4
- **Category**: Building
- **Rarity**: Common

## Official Mechanics (Wiki Reference)
- Area damage, ground-targeting, long-ranged building
- When defeated, drops a bomb which explodes after 3 seconds dealing damage
- Range: 6 tiles
- Attack Speed: 1.8 seconds
- Death damage equivalent to normal attack damage

## gamedata.json Analysis
From gamedata.json, Bomb Tower has these capabilities:
- **Building Type**: Ground-targeting building (TID_TARGETS_GROUND)
- **Hitpoints**: 530
- **Hit Speed**: 1800ms (1.8 seconds)
- **Range**: 6000 units (6 tiles)
- **Lifetime**: 30000ms (30 seconds)
- **Projectile**: BombTowerProjectile with area damage (radius: 1500 units)
- **Death Spawn**: BombTowerBomb with 87 damage, 3000ms deploy delay, area damage
- **Death Spawn Count**: 1
- **Collision Radius**: 600 units

## Implemented
- ✅ Building entity system (src/clasher/entities.py: Building class)
- ✅ Ground targeting only (TID_TARGETS_GROUND)
- ✅ Projectile system with area damage (entities.py: _create_projectile, _uses_projectiles)
- ✅ Building lifetime management (30 seconds)
- ✅ Attack cooldown system (1.8 second hit speed)
- ✅ Range-based targeting (6 tiles)
- ✅ Death spawn system (battle.py: _handle_death_spawns)
- ✅ Card data loading (data.py: CardStats with death_spawn_character_data)

## Missing
- ❌ Specific Bomb Tower card registration in SPELL_REGISTRY
- ❌ 3-second delay on death bomb explosion (currently immediate spawn)
- ❌ Building-specific visual/sound effects for death bomb
- ❌ Area damage radius scaling for death bomb

## Notes
- Bomb Tower uses the generic Building class which handles most mechanics
- Death spawn system exists but Bomb Tower's 3-second bomb delay isn't implemented
- All core stats (HP, damage, range, attack speed) are loaded from gamedata.json
- Projectile system supports area damage as required
- Card ID 27000004 exists in gamedata.json but needs to be mapped to usable card name