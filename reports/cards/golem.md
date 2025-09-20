# Golem Card Implementation Audit

## Card Info
- **Card**: Golem
- **Elixir**: 8
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Ground troop, Targets buildings only

## Implemented
- Basic troop stats (HP, damage, speed, attack range) - `src/clasher/entities.py:240`
- Building-only targeting - `src/clasher/entities.py:168-171`
- Movement and pathfinding - `src/clasher/entities.py:427-494`
- Basic attack mechanics - `src/clasher/entities.py:292-308`
- Data loading from gamedata.json - `src/clasher/data.py`

## Missing
- **Death spawn mechanic**: Golem should spawn 2 Golemites when killed (deathSpawnCount: 2)
- **Death damage**: Golem should deal area damage on death (deathDamage: 88)
- **Golemite spawning**: Death spawn character "Golemite" with appropriate stats not implemented
- **Death area effect**: Splash damage from Golem's death not implemented in `take_damage` method

## Notes
- Golem data is present in gamedata.json with all required fields including deathSpawnCount, deathDamage, and deathSpawnCharacterData
- The Entity.take_damage method (`src/clasher/entities.py:66-70`) simply marks the entity as dead but doesn't handle death spawns or effects
- No special mechanics found - Golem is a straightforward tank troop with death effects
- Codebase has death spawn data structures in CardStats but no implementation logic for death effects