# Hog Rider Card Implementation Audit

## Card Details
- **Card**: Hog Rider
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Ground unit

## Implemented
- Basic troop movement and pathfinding (entities.py:240-690)
- Building-only targeting (entities.py:169-171, data.py:45)
- Combat mechanics (attack, damage, hitpoints) (entities.py:294-308)
- Speed stat (120 tiles/min) (gamedata.json)
- Hit speed (1600ms) (gamedata.json)
- Range (800 game units = 0.8 tiles) (gamedata.json)
- Sight range (9500 game units = 9.5 tiles) (gamedata.json)
- Collision radius (600 game units = 0.6 tiles) (gamedata.json)

## Missing
- **Jump mechanics**: `jumpHeight: 4000` and `jumpSpeed: 160` from gamedata.json not implemented
- **Bridge jumping behavior**: No code to handle jumping over rivers/obstacles
- **Fast attack animation**: Hog Rider's signature quick attack style not specifically coded
- **Hog-specific sound/visual effects**: Not implemented in current system

## Notes
- Hog Rider data shows `TID_TARGETS_BUILDINGS` targeting - this IS implemented via `targets_only_buildings` flag
- No special gimmicks beyond jump mechanics - just a fast building-targeting troop
- Jump mechanics would require significant pathfinding changes in entities.py `_move_towards_target` method
- Current system uses generic troop behavior with building-only targeting constraint