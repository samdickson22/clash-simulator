# Zappies Implementation Audit

## Card Details
- **Card**: Zappies
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Rare
- **Internal Name**: MiniSparkys

## Implemented
- ✅ Basic troop spawning (3 MiniZapMachine units)
- ✅ Movement and pathfinding
- ✅ Basic targeting and attack mechanics
- ✅ Health and damage scaling
- ✅ Status effect system (stun framework exists)
- ✅ Card data loading infrastructure

## Missing
- ❌ **Stun-on-attack mechanic**: Primary gimmick not implemented
  - `buffOnDamageTime: 500` (0.5s stun duration)
  - `buffOnDamageData` with "ZapFreeze" effect (hitSpeedMultiplier: -100, speedMultiplier: -100, spawnSpeedMultiplier: -100)
- ❌ **On-damage effect trigger**: No `_on_attack()` implementation for applying buffs
- ❌ **Buff application system**: Framework exists but Zappies-specific stun not applied
- ❌ **Card data mapping**: `buffOnDamageData` and `buffOnDamageTime` not loaded in CardDataLoader

## Notes
- **Name mapping**: Internal name is "MiniSparkys" but displays as "Zappies"
- **Unit type**: Spawns 3 "MiniZapMachine" units with individual stats
- **Targeting**: Can attack both air and ground units (`tidTarget: "TID_TARGETS_AIR_AND_GROUND"`)
- **Core issue**: The defining stun mechanic is completely missing despite the data being present in gamedata.json
- **Infrastructure**: The status effect system exists in `entities.py:108-140` but is not connected to Zappies' attacks