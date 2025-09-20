# Rascals Card Implementation Audit

## Card Details
- **Card**: Rascals
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Common
- **Type**: Multi-unit summon (1 Rascal Boy + 2 Rascal Girls)

## Implemented
- **None** - The Rascals card is not implemented in the codebase

## Missing
Based on gamedata.json analysis:
- **Multi-unit summon mechanics**: Card spawns 1 RascalBoy and 2 RascalGirl units (gamedata.json:26000053)
- **RascalBoy mechanics**:
  - Melee troop with 758 HP, 52 damage, 800 range, 60 speed
  - Targets ground only (TID_TARGETS_GROUND)
  - 1.5s hit speed, 1.1s load time
  - 750 collision radius
- **RascalGirl mechanics**:
  - Ranged troop with 102 HP, 52 damage, 5000 range, 60 speed
  - Targets air and ground (TID_TARGETS_AIR_AND_GROUND)
  - 1.0s hit speed, 0.5s load time
  - 500 collision radius
  - Uses projectiles (RascalGirlProjectile with 800 speed)
- **Summon radius**: 3000 unit radius for spawning the three units
- **Deploy timing**: 1000ms deploy time for both unit types

## Notes
- **Name mapping**: Card uses "Rascals" internally but gamedata shows "Hooded Gang" as TID reference
- **Implementation gap**: No code found for Rascals, RascalBoy, RascalGirl, or Hooded Gang entities in the codebase
- **Architecture fit**: Would need to extend the Troop class and implement multi-unit spawning logic similar to other swarm cards
- **Projectile system**: RascalGirl requires projectile implementation which exists in the codebase (entities.py:769-826)