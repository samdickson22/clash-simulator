# Battle Ram Audit Report

## Card, Elixir, Category
- **Card**: Battle Ram
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Rare
- **Type**: Ground unit, building-targeting

## Implemented
- Basic troop spawning and movement (`battle.py:166`)
- Ground targeting mechanics (`entities.py:240`)
- Death spawn functionality (`battle.py:680` - generic system)
- Basic damage and hitpoint systems
- Speed and range handling

## Missing
- **Building-only targeting**: Card has `tidTarget: "TID_TARGETS_BUILDINGS"` but only generic ground targeting implemented
- **Charge mechanic**: `chargeRange: 300` present in data but no charge/dash implementation
- **Kamikaze behavior**: `kamikaze: true` in data but no special death explosion logic
- **Death spawn Barbarians**: Should spawn 2 Barbarians on death (`deathSpawnCount: 2`, `deathSpawnCharacterData` with Barbarian stats)
- **Damage scaling**: `damageSpecial: 224` suggests special damage mechanic not implemented
- **Collision radius**: `collisionRadius: 750` (larger than standard troops) not fully utilized
- **Load time**: `loadTime: 50` suggests special attack timing not implemented

## Notes
- Battle Ram is mapped in `random_battle.py` but no specific class implementation exists
- Generic `Troop` class handles basic movement and combat
- Death spawn system exists but not configured for Battle Ram's Barbarian spawns
- No special charge/dash mechanics implemented despite charge range in data
- Building targeting preference not implemented - will target any ground unit currently
- Kamikaze flag suggests explosion on death but no logic implemented

**Sources**:
- gamedata.json:2369-2448 (Battle Ram definition)
- entities.py:240 (generic Troop class)
- battle.py:166,191,680 (spawn and death systems)