# Bats Card Implementation Audit

## Card Details
- **Card**: Bats
- **Elixir**: 2
- **Category**: Troop (Swarm)
- **Rarity**: Common
- **Type**: Air & Ground Targeting (Fast flying melee troop)

## Gamedata.json Analysis
Based on the Bats card data from gamedata.json:

### Core Properties
- **summonNumber**: 5 (spawns 5 individual Bat units)
- **summonRadius**: 750 (0.75 tiles deployment radius)
- **summonDeployDelay**: 100ms
- **unlockArena**: Arena5
- **source**: spells_characters (treated as character card)

### Individual Bat Unit Properties
- **name**: Bat
- **hitpoints**: 32
- **damage**: 32
- **range**: 1200 (1.2 tiles - melee range)
- **sightRange**: 5500 (5.5 tiles)
- **speed**: 120 (very fast movement)
- **hitSpeed**: 1300ms
- **loadTime**: 700ms
- **deployTime**: 1000ms
- **collisionRadius**: 500 (0.5 tiles)
- **attacksGround**: true
- **tidTarget**: "TID_TARGETS_AIR_AND_GROUND"
- **tidSpeed**: "TID_SPEED_5" (Very Fast)

## Implementation Status

### ✅ Implemented
- **Basic troop spawning mechanism**: The `_spawn_swarm_troops()` function in `src/clasher/battle.py:222` handles multi-unit spawning with circular formation
- **Swarm deployment logic**: Cards with `summonCount > 1` are properly detected and spawned in formation
- **Individual unit stats**: Each Bat unit gets proper hitpoints, damage, range, sight, and speed from card data
- **Air/Ground targeting**: Bat units inherit targeting capabilities from their data
- **Collision detection**: Individual collision radius is respected for each Bat unit
- **Formation spawning**: Units spawn in a circle with randomness around deployment point

### ✅ Core Mechanics Present
- **Very fast movement**: Speed 120 tiles/minute is correctly loaded and applied
- **Melee attacks**: 1.2 tile range indicates melee combat behavior
- **Single-target damage**: Each Bat deals 32 damage per attack
- **Air unit classification**: Bats should be classified as air units for targeting purposes
- **5-unit swarm**: Correctly spawns 5 individual Bat entities

### ❓ Missing/Potentially Missing
- **Air unit classification**: Bats are not included in the hardcoded air units list in `src/clasher/battle.py:197-198`
  - Current list: `['Minions', 'MinionHorde', 'Balloon', 'SkeletonBalloon', 'BabyDragon', 'InfernoDragon', 'ElectroDragon', 'SkeletonDragons', 'MegaMinion']`
  - **Recommendation**: Add 'Bats' to this list

## Notes

### Name Mapping
- **Card name**: "Bats" (spell that summons units)
- **Unit name**: "Bat" (individual unit spawned)
- This follows the pattern where swarm cards have plural names but spawn singular units

### Implementation Architecture
- Bats are handled as a "character" type card (`TID_CARD_TYPE_CHARACTER`) rather than a spell
- The swarm spawning system correctly handles the 5-unit deployment
- Each Bat unit inherits stats from the `summonCharacterData` section

### Key Code References
- `src/clasher/battle.py:166-189`: Swarm troop detection and spawning
- `src/clasher/battle.py:222-255`: Multi-unit circular formation spawning
- `src/clasher/data.py:176-196`: Summon count and radius data loading
- `src/clasher/data.py:121-149`: Individual unit stats extraction

### Summary
The Bats card appears to be **largely implemented** with the core swarm spawning mechanism working correctly. The only missing piece appears to be air unit classification, which would affect pathfinding and targeting interactions. All other mechanics (5-unit spawn, fast movement, melee attacks, individual unit stats) are properly supported by the existing codebase.