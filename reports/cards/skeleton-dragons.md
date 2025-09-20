# Skeleton Dragons - Implementation Audit

## Card Details
- **Name**: Skeleton Dragons
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Common
- **Type**: Air troop

## Implemented
- Basic troop spawning mechanics (src/clasher/battle.py:198,285,501)
- Air targeting capability (gamedata.json: `tidTarget": "TID_TARGETS_AIR_AND_GROUND"`)
- Projectile system (src/clasher/entities.py: PROJECTILE handling, _create_projectile methods)
- Area damage support (src/clasher/entities.py: area_damage_radius, splash_radius handling)

## Missing
- Skeleton Dragon character class not implemented (src/clasher/entities.py: no SkeletonDragon class)
- Skeleton Dragon projectile data not utilized
- Area damage mechanics not implemented for this specific card
- Dual skeleton spawning (summonNumber: 2) not implemented
- Air troop mechanics (flying units, collision rules)
- Character-specific stats not mapped (hitpoints: 219, damage: 63, speed: 90, range: 3.5)

## Notes
- Card appears in battle.py air unit lists but lacks dedicated implementation
- Projectile system exists but Skeleton Dragon projectile data (SkeletonDragonProjectile) is not used
- Area damage radius (800/1000 = 0.8 tiles) needs to be implemented for this card
- Name mapping: "SkeletonDragons" in gamedata.json vs "SkeletonDragon" character name
- Dual troop spawning (summonNumber: 2) requires special handling in troop spawning system