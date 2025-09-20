# Cannon Cart Implementation Audit

## Card, Elixir, Category
- **Card**: Cannon Cart
- **Elixir**: 5
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Ground troop with ranged attack

## Implemented
- **None** - Cannon Cart is not implemented in the codebase

## Missing
- **Basic troop mechanics** - MovingCannon class not found in entities.py or other files
- **Ranged projectile attacks** - Uses MovingCannonProjectile with 83 damage, speed 1000 (gamedata.json:3705-3712)
- **Health-based transformation** - Transforms to BrokenCannon at 50% health (gamedata.json:3713-3758)
- **Transformation mechanics** - MovingCannon_trigger_at_health action with transformation effect and sound (gamedata.json:3719-3757)
- **Troop statistics** - Hitpoints: 707, Hit Speed: 900ms, Range: 5500, Speed: 60 (gamedata.json:3689-3704)
- **Ground-only targeting** - attacksGround: true, tidTarget: TID_TARGETS_GROUND (gamedata.json:3698, 3703)

## Notes
- **Name mapping**: Card is called "MovingCannon" in gamedata.json but displays as "Cannon Cart" (englishName field)
- **Transformation trigger**: Health threshold check system not implemented in current codebase
- **Action system**: onStartingActionData framework for health-based triggers not present
- **Visual effects**: Transformation effects and sounds referenced but not implemented
- **Building state**: BrokenCannon form after transformation lacks lifetime/duration mechanics in gamedata