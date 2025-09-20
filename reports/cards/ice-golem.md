# Ice Golem Card Audit

## Card Info
- **Card**: Ice Golem
- **Elixir**: 2
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Ground troop, building-targeting

## Implemented
- Basic troop movement and targeting (entities.py:14-26)
- Status effect system for slow effects (entities.py:50-55, 102-114)
- Area effect system (entities.py:81-100)
- Card data loading system (data.py:CardDataLoader)
- Death effect detection framework (entities.py:has_spawned_character)

## Missing
- **Building-only targeting**: gamedata.json shows `"tidTarget": "TID_TARGETS_BUILDINGS"` (line 468)
- **Death damage explosion**: gamedata.json shows `"deathDamage": 33` (line 468)
- **Death area slow effect**: gamedata.json shows `deathAreaEffectData` with 2000 radius and 2000ms slow duration (line 468-479)
- **Slow mechanics on death**: IceWizardSlowDown buff with -35% speed/hitSpeed/spawnSpeed multipliers (line 473-477)
- **Proper hitbox collision**: collisionRadius of 700 (line 468)
- **Melee attack range**: range of 750 (line 468)
- **Specific speed**: speed of 45 (line 468)
- **Death effect timing**: lifeDuration of 1000ms for death effect (line 470)

## Notes
- Card uses internal name "IceGolemite" in gamedata.json (line 468)
- No dedicated Ice Golem class exists in codebase
- Generic troop system exists but lacks specific Ice Golem implementation
- Death effect and area slow mechanics are core features not implemented
- Status effect system supports slow but death-triggered slow needs implementation