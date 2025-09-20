# Royal Hogs Card Implementation Audit

## Card Details
- **Card**: Royal Hogs
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Character Card (summons 4 RoyalHog units)

## Implemented
- Basic Troop class inheritance (src/clasher/entities.py:~15)
- Character summoning mechanics (src/clasher/battle.py:~200-250)
- Standard movement and collision system
- Ground-only targeting (gamedata.json: `"attacksGround": true`)
- Speed: 120 (gamedata.json: `"speed": 120`)
- Health: 327 (gamedata.json: `"hitpoints": 327`)
- Damage: 29 (gamedata.json: `"damage": 29`)
- Attack speed: 1.2s (gamedata.json: `"hitSpeed": 1200`)
- Range: 750 (gamedata.json: `"range": 750`)
- Jump height: 4000 (gamedata.json: `"jumpHeight": 4000`)
- Jump speed: 160 (gamedata.json: `"jumpSpeed": 160`)
- Collision radius: 600 (gamedata.json: `"collisionRadius": 600`)
- Sight range: 9500 (gamedata.json: `"sightRange": 9500`)
- Building targeting (gamedata.json: `"tidTarget": "TID_TARGETS_BUILDINGS"`)

## Missing
- **Jump mechanics** - Royal Hogs have explicit jumpHeight and jumpSpeed parameters but no implementation detected for jumping over obstacles/structures
- **Building-specific targeting logic** - Code shows general building targeting but no Royal Hogs-specific behavior
- **Jump attack patterns** - No implementation for jump-based attack mechanics
- **Special visual effects for jumping** - No jump animation or effect handling found

## Notes
- Royal Hogs appear to be treated as a standard troop summon card
- Jump mechanics are explicitly defined in gamedata.json but no jump implementation found in codebase
- Card name mapping exists: "Royal Hogs" → "RoyalHogs" (random_battle.py)
- Uses generic Troop class with no special behavior overrides
- Targeting is set to buildings only, but no special building attack logic implemented
- Jump parameters suggest they should be able to jump over obstacles/structures, but this mechanic is not implemented in the codebase