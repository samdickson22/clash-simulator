# Phoenix Card Implementation Audit

## Card Details
- **Name**: Phoenix
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Legendary
- **ID**: 26000087

## Implemented
- Basic troop spawning system (src/clasher/battle.py:166, src/clasher/entities.py:240)
- Health/damage mechanics (src/clasher/entities.py:66)
- Movement and pathfinding (src/clasher/entities.py:427)
- Basic targeting (src/clasher/entities.py:159)
- Death spawn projectile system (src/clasher/battle.py:644)

## Missing
Based on gamedata.json analysis (lines 6112-6185):

- **Death spawn fireball**: PhoenixFireball projectile with area damage (radius: 2.5 tiles, damage: 64, pushback: 2000)
- **Phoenix Egg**: Death-spawned character with 94 HP that spawns after 4.3 seconds
- **Phoenix rebirth**: PhoenixNoRespawn character (329 HP) spawned from egg
- **Air unit status**: Phoenix should be classified as air unit (is_air_unit: true)
- **Flying movement**: Air units bypass bridge pathfinding and fly directly to targets
- **Death spawn chain**: Phoenix → PhoenixFireball → PhoenixEgg → PhoenixNoRespawn
- **Projectile mechanics**: PhoenixFireball speed (600), crown tower damage (-70%), area damage radius

## Notes
- Phoenix is classified as a "spell" in gamedata.json but summons a character troop
- The death spawn system exists in code but Phoenix-specific projectile and character chain not implemented
- Air unit mechanics exist in codebase (entities.py:48, 430) but Phoenix not marked as air unit
- Multi-stage death mechanic (fireball → egg → reborn phoenix) is complex and not implemented
- No specific Phoenix class or handling found in codebase
- Name mapping: "Phoenix" in gamedata.json corresponds to card ID 26000087