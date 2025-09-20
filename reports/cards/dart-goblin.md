# Dart Goblin Implementation Audit

## Card Details
- **Card**: Dart Goblin
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Ranged ground troop

## Implemented
- **Basic troop mechanics** (entities.py:240-690)
  - Movement, pathfinding, targeting
  - Attack cooldown and damage dealing
  - Status effects (stun, slow)
- **Projectile system** (entities.py:323-400, 769-826)
  - Projectile creation and movement
  - Hitbox-based collision detection
  - Splash damage support
- **Targeting system** (entities.py:159-236)
  - Air and ground targeting
  - Target priority (troops > buildings)
  - Sight range mechanics
- **Card data structure** (data.py:7-100)
  - Full stat support (HP, damage, speed, range, etc.)
  - Projectile data integration
  - Level scaling system

## Missing
- **Dart Goblin specific entity class** - No dedicated BlowdartGoblin/DartGoblin class found
- **Card registration** - No spell/class registration in dynamic_spells.py or spells.py
- **BlowdartGoblinProjectile** - Specific projectile type not implemented
- **Character stats mapping** - Game data exists but not connected to codebase

## Notes
- **Name mapping**: Game data uses "BlowdartGoblin" internally, card is called "Dart Goblin" in English
- **Core mechanics supported**: The base projectile troop system is fully implemented and would support Dart Goblin
- **Integration needed**: Card needs to be registered in the spell system and connected to game data
- **No special mechanics**: Dart Goblin has no unique gimmicks (charge, spawn, death effects, etc.) beyond standard projectile behavior

**Source: gamedata.json:2691-2786 (BlowdartGoblin card definition)**