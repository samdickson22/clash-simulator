# Bandit Card Implementation Audit

## Card Details
- **Card**: Bandit
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop (targets ground only)

## Official Mechanics (Wiki)
- Dashes for double damage if ground units are 3.5-6 tiles away
- Becomes immune during the dash

## Gamedata.json Capabilities
Based on gamedata.json entry (name: "Assassin", englishName: "Bandit"):
- **Basic stats**: HP: 354, Damage: 76, Speed: 90, Range: 0.75 tiles, Hit Speed: 1.0s
- **Dash mechanics**: `dashDamage: 152` (2x normal damage), `dashMinRange: 3500` (3.5 tiles), `dashMaxRange: 6000` (6 tiles), `jumpSpeed: 500`
- **Targeting**: `attacksGround: true`, `tidTarget: "TID_TARGETS_GROUND"`
- **Other**: Deploy time: 1.0s, Sight range: 6.0 tiles, Collision radius: 0.6 tiles

## Implemented
- ✅ Basic troop movement and targeting (entities.py:240-690)
- ✅ Ground-only targeting system (entities.py:174-176)
- ✅ Generic charging mechanics framework (entities.py:244-425) - *but not dash-specific*
- ✅ Damage modification system for charge attacks (entities.py:310-315)
- ✅ Speed modification system for charge state (entities.py:422-425)

## Missing
- ❌ **Dash-specific mechanics**: No implementation of Bandit's unique dash behavior
- ❌ **Range-based dash triggering**: Current charge system uses distance traveled, not target distance range (3.5-6 tiles)
- ❌ **Instant dash movement**: No jump/teleport to target during dash
- ❌ **Immunity during dash**: No invulnerability frames during dash
- ❌ **Dash-specific damage scaling**: System exists but not wired to Bandit's dashDamage parameter
- ❌ **Visual dash effects**: No jump animation or dash visual feedback

## Notes
- **Name mapping**: Card is named "Assassin" in gamedata.json but displays as "Bandit"
- **Mechanic mismatch**: Current charge system is distance-based from spawn position, but Bandit needs target-distance-based dash triggering (3.5-6 tile range)
- **Core framework exists**: The charging/damage modification infrastructure is present but needs dash-specific implementation
- **Immunity system**: No general immunity system exists in codebase, would need to be implemented for dash invulnerability
- **Jump mechanics**: No jump/teleport movement system exists for the dash movement