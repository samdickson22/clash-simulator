# Guards Card Implementation Audit

## Card Details
- **Card**: Guards
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Epic
- **Type**: SkeletonWarrior (summonCharacterData)

## Implemented
- ✅ **Basic Troop Mechanics**: Movement, pathfinding, targeting (src/clasher/entities.py:240-690)
- ✅ **Damage System**: Basic damage dealing and hitpoint tracking (src/clasher/entities.py:66-70)
- ✅ **Attack Cooldown**: Hit speed timing (1000ms = 1.0s) (src/clasher/entities.py:306)
- ✅ **Shield System**: shieldHitpoints attribute handling (entities.py:66-70)
- ✅ **Ground Targeting**: tidTarget: "TID_TARGETS_GROUND" (gamedata.json)
- ✅ **Summon Mechanics**: summonNumber: 3 units with 100ms deploy delay (gamedata.json)
- ✅ **Speed Movement**: speed: 90 tiles/minute (gamedata.json)
- ✅ **Sight Range**: 5500 units = 5.5 tiles for targeting (gamedata.json)
- ✅ **Combat Range**: 1600 units = 1.6 tiles melee range (gamedata.json)
- ✅ **Status Effects**: Stun and slow mechanics (entities.py:108-135)

## Missing
- ❌ **Specific Shield Mechanics**: No visual or functional distinction between shield HP and main HP beyond basic damage absorption
- ❌ **Death Spawn Effects**: No special behavior on death (skeleton-specific mechanics)
- ❌ **Shield Break Effects**: No special effects when shield is destroyed
- ❌ **Character-Specific Animations**: No visual distinction for skeleton warriors
- ❌ **Sound Effects**: No audio feedback for attacks or shield breaks

## Notes
- Guards are implemented under the internal name "SkeletonWarriors" (gamedata.json)
- Uses generic Troop class with no specialized subclass for unique behaviors
- Shield mechanics are handled through basic damage absorption rather than layered HP system
- Summon mechanics use standard multi-unit deployment (3 units, 100ms delay)
- Range of 1.6 tiles indicates melee combat despite being listed as "ranged" in some wikis
- Speed of 90 tiles/minute = 1.5 tiles/second movement speed
- No evolution mechanics considered (EVOS excluded per requirements)

## Implementation Status: PARTIAL (70%)
Core functionality exists but lacks card-specific visual/audio polish and advanced mechanics.