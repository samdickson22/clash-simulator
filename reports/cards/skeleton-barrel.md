# Skeleton Barrel Audit Report

## Card Details
- **Card**: Skeleton Barrel
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Common
- **Type**: Air unit

## Official Mechanics (Clash Royale Wiki)
- Fast, building-targeting air troop
- When destroyed or reaching a building, deals area damage and spawns 7 Skeletons in a circle
- Inflicts knockback on impact

## Gamedata.json Analysis
Based on gamedata.json entry (lines 3880-3949):

**Key Capabilities:**
- Air troop (`is_air_unit: true`)
- Building-targeting only (`tidTarget": "TID_TARGETS_BUILDINGS"`)
- Kamikaze mechanic (`kamikaze: true`)
- Death spawn system (`deathSpawnCount: 1`)
- Multi-layered death spawn: spawns SkeletonContainer → spawns 7 Skeletons
- Death damage on impact (`deathDamage: 57`)

## Implementation Status

### Implemented
- ✅ Basic air troop movement (entities.py:48, 430-431)
- ✅ Building-only targeting (entities.py:169-171)
- ✅ Death spawn system (battle.py:830-872, `_spawn_death_units`)
- ✅ Multi-unit spawning mechanics (battle.py:518-596)
- ✅ Skeleton troop entity exists (gamedata.json lines 3930-3946)

### Missing
- ❌ **Kamikaze mechanic** - Not implemented in troop behavior
- ❌ **Death damage on impact** - Death spawn system doesn't apply damage
- ❌ **Area damage/knockback on death** - No death explosion mechanics
- ❌ **SkeletonContainer intermediate entity** - Code spawns Skeletons directly, not via Container
- ❌ **Specific death positioning** - Spawns randomly rather than in circle formation

## Notes
- **Name mapping**: Card uses "SkeletonBalloon" in code, "Skeleton Barrel" in display name
- **Air unit classification**: Properly recognized in air_units list (battle.py:197, 284, 500)
- **Death spawn structure**: gamedata shows 2-layer spawn (Barrel → Container → 7 Skeletons), but implementation likely skips Container step
- **Core gap**: Missing the "barrel explodes" mechanic that defines the card's unique gameplay

## Priority Implementation Order
1. Add kamikaze/death damage to troop death mechanics
2. Implement death explosion area damage and knockback
3. Add SkeletonContainer as intermediate death spawn entity
4. Implement circular spawn formation for death spawns