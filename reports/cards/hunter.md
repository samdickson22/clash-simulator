# Hunter Card Implementation Audit

## Card Details
- **Card**: Hunter
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Epic
- **Type**: Ground troop

## Implemented
- Basic troop movement and pathfinding (entities.py:240-690)
- Target acquisition and priority system (entities.py:159-236)
- Health and damage mechanics (entities.py:66-70)
- Projectile creation and movement (entities.py:323-400, 768-825)
- Status effects (stun, slow) (entities.py:108-135)
- Attack cooldown and timing (entities.py:267-306)

## Missing
- **Multiple projectiles (shotgun pellets)**: gamedata.json shows `multipleProjectiles: 10` but entities.py doesn't implement multi-projectile attacks
- **Area damage radius**: gamedata.json shows `areaDamageRadius: 70` but projectiles only handle single-target damage
- **Shotgun spread pattern**: No implementation of Hunter's signature shotgun spread that deals more damage up close
- **Projectile-specific mechanics**: HunterProjectile named in gamedata.json but no special handling for shotgun projectiles

## Notes
- Hunter is referenced in gamedata.json with ID 26000044 and basic troop stats
- Core troop framework exists but lacks Hunter-specific multi-projectile mechanics
- The card exists in game data but has no unique implementation beyond basic troop behavior
- Projectile system supports splash damage but not multi-projectile shotgun attacks
- No special class or handling for Hunter's unique shotgun mechanics