# Clone Card Implementation Audit

## Card Information
- **Card**: Clone
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Epic

## Official Mechanics (Wiki)
The Clone is a 3-Elixir Epic spell that duplicates friendly troops in its area. Cloned units have 1 HP, retain original abilities, and cannot affect buildings.

## Gamedata.json Analysis
From gamedata.json, the Clone card has these properties:
- `radius`: 3000
- `areaEffectObjectData`: Creates "Clone" area effect with 1000ms duration
- `hitsGround`: true, `hitsAir`: true
- `onHitActionData`: "CloneAction" (action definition not found in gamedata)
- **GlobalClone variant**: Has `spawnSpeedMultiplier: -100` and other speed reduction buffs

## Implemented Features
- ✅ **Basic spell registration** - CloneSpell class defined and registered in SPELLS dict (src/clasher/spells.py:501)
- ✅ **Area-based targeting** - Finds friendly troops within 3000 unit radius (src/clasher/spells.py:248)
- ✅ **Troop duplication** - Creates new Troop entities with copied stats (src/clasher/spells.py:256-268)
- ✅ **Clone marking** - Sets `is_clone = True` flag (src/clasher/spells.py:270)
- ✅ **Building exclusion** - Only clones troops, not buildings (src/clasher/spells.py:250)
- ✅ **Dynamic spell detection** - Recognizes CloneAction in dynamic_spells.py (src/clasher/dynamic_spells.py:51)

## Missing Features
- ❌ **1 HP mechanic** - Clones copy full hitpoints instead of having 1 HP (src/clasher/spells.py:261)
- ❌ **Cannot attack buildings** - No restriction preventing clones from targeting buildings
- ❌ **is_clone attribute** - Entity/Troop classes don't define `is_clone` attribute
- ❌ **Clone visual/effects** - No special visual differentiation for clones
- ❌ **Area effect duration** - 1000ms lifeDuration from gamedata not implemented
- ❌ **Speed multipliers** - GlobalClone speed reduction buffs not implemented

## Notes
- The implementation assumes `is_clone` can be set dynamically but it's not defined in Entity class
- No handling for clone-specific behavior in battle logic (e.g., building attack restrictions)
- CloneAction referenced in gamedata but actual action definition not found
- GlobalClone variant exists in gamedata but implementation lacks the speed reduction mechanics
- Current implementation copies all troop stats exactly, missing the key "1 HP" limitation from official mechanics