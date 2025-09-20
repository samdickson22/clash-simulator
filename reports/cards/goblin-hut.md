# Goblin Hut Card Implementation Audit

## Card Details
- **Card**: Goblin Hut
- **Elixir**: 4 (not 5 as specified in task - gamedata shows 4)
- **Category**: Building
- **Rarity**: Rare
- **Type**: Defensive building

## Official Mechanics (Wiki)
- Defensive building that spawns Spear Goblins when enemies are in range
- Rare building costing 4 Elixir

## Gamedata.json Analysis
Based on gamedata.json lines 7146-7197, the Goblin Hut has these specific capabilities:

### Core Properties
- **Lifetime**: 30 seconds (30000ms)
- **Hitpoints**: 480
- **Collision Radius**: 1000 (1 tile)
- **Death Spawn**: Yes, spawns 1 Spear Goblin on destruction
- **Deploy Time**: 1000ms (1 second)

### Death Spawn Mechanics
- **Spawn Count**: 1 Spear Goblin when destroyed
- **Spawn Character**: SpearGoblin
- **Spear Goblin Stats**:
  - Hitpoints: 52
  - Damage: 32
  - Range: 5500 (5.5 tiles)
  - Sight Range: 5500 (5.5 tiles)
  - Speed: 120 (tiles/minute)
  - Hit Speed: 1700ms (1.7 seconds)
  - Load Time: 1300ms (1.3 seconds)
  - Target Type: TID_TARGETS_AIR_AND_GROUND
  - Projectile Data: SpearGoblinProjectile (damage: 32)

### Missing from Gamedata
- No active spawning while alive (spawnInterval: 0, spawnNumber: 0, spawnPauseTime: 0)
- No attack capabilities (no hitSpeed, damage, or projectileData for the hut itself)
- Only spawns Spear Goblins on death, not during lifetime

## Implementation Status

### ✅ Implemented
- **Building entity system**: Core Building class exists in `src/clasher/entities.py:693-766`
- **Building spawning**: Buildings can be spawned via `battle.py` based on card_type
- **Death spawn system**: Death spawn mechanics exist for troops in `src/clasher/battle.py:760-815`
- **Spear Goblin unit**: Spear Goblin character data exists in gamedata and can be spawned

### ❌ Missing
- **Building death spawn**: Death spawn logic only applies to Troop entities, not Building entities (`battle.py:760`)
- **Goblin Hut card**: No specific card implementation found in spell registry or data loader
- **Active spawning**: No implementation for periodic spawning during building lifetime
- **Building-specific mechanics**: No special handling for building death spawns

### 🔍 Ambiguities
- **Wiki vs Gamedata conflict**: Wiki mentions spawning Spear Goblins "when enemies are in range" but gamedata only shows death spawn
- **Elixir cost**: Task specified 5 elixir but gamedata shows 4 elixir
- **Name mapping**: gamedata uses "GoblinHut" internally but wiki uses "Goblin Hut"

## Required Implementation

### Critical Missing Features
1. **Building death spawn support**: Extend death spawn logic to include Building entities
2. **Goblin Hut card registration**: Add Goblin Hut to the card registry with proper stats
3. **Death spawn data mapping**: Ensure deathSpawnCharacterData is properly mapped from gamedata

### Implementation Notes
- The Spear Goblin unit that should spawn on death already has complete data
- Core building mechanics exist, just need to enable death spawn for buildings
- No active spawning during lifetime needed based on gamedata (spawnInterval: 0)