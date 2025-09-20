# Graveyard Implementation Audit

## Card, Elixir, Category
- **Card**: Graveyard
- **Elixir**: 5
- **Category**: Spell
- **Rarity**: Legendary

## Implemented
- Graveyard entity class with periodic skeleton spawning (`src/clasher/entities.py`)
- GraveyardSpell class for spell casting logic (`src/clasher/spells.py:GraveyardSpell`)
- Area-based spawning within radius (2.5 tiles)
- Duration-based lifecycle (10 seconds)
- Spawn interval timing (0.5 seconds)
- Maximum skeleton limit (20 skeletons)
- Skeleton stats configuration (HP: 67, Damage: 67, Speed: 60)
- Spell registration in spell mapping dictionary
- Random position spawning within radius

## Missing
- **Spawn timing accuracy**: gamedata specifies 400ms initial spawn time + 500ms intervals (9.0s duration for 13 skeletons), but code uses 0.5s intervals with 10.0s duration for 20 skeletons
- **Skeleton stats mismatch**: gamedata skeletons have 32 HP/32 damage, code uses 67 HP/67 damage
- **Speed mismatch**: gamedata skeleton speed is 90, code uses 60
- **Spawn count**: gamedata spawns exactly 13 skeletons over 9 seconds, code allows up to 20 over 10 seconds
- **Radius units**: gamedata radius is 4000 (likely in different unit system), code uses 2.5 tiles

## Notes
- Core spawning mechanic is implemented but with different balance parameters
- Entity and spell systems are properly integrated
- Skeleton troops appear to be handled by generic Troop class, not specialized Skeleton entity
- Implementation uses hardcoded stats rather than gamedata.json values
- Spell is correctly registered and available for use in battle system