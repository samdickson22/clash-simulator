# Skeleton Army Implementation Audit

## Card Details
- **Card**: Skeleton Army
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Character (spawns multiple units)

## Implemented
- None found

## Missing
- **Card definition**: No `SkeletonArmy` class in entities.py or spells.py
- **Spell implementation**: Missing spell definition for `TID_SPELL_SKELETON_HORDE`
- **Multi-unit spawning**: Mechanics to spawn 15 Skeletons in scatter formation
- **Individual Skeleton units**: While basic Skeleton spawning exists (used by Graveyard), no dedicated Skeleton Army implementation
- **Ground targeting**: Skeletons should only attack ground targets (`attacksGround: true`)
- **Stats integration**: 32 hitpoints, 32 damage, 90 speed, 500 range, 1000 hit speed per Skeleton

## Notes
- **Name mapping**: gamedata.json uses `"name": "SkeletonArmy"` and `"englishName": "Skeleton Army"`
- **Internal ID**: `TID_SPELL_SKELETON_HORDE` (26000012)
- **Spawn data**: Summons 15 Skeletons with `summonCharacterLevelIndex: 5`
- **Existing skeleton code**: Basic Skeleton spawning logic exists in `entities.py` for Graveyard spell but not for Skeleton Army
- **Ambiguity**: Card appears to be completely missing from codebase implementation