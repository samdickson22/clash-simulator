# Royal Delivery Card Implementation Audit

## Card Information
- **Card**: Royal Delivery
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Common
- **Unlock Arena**: Arena 14

## Analysis from gamedata.json
Royal Delivery has the following mechanics:
- **Area Effect**: Creates an area effect object with 2000ms duration and 3000 pixel radius
- **Projectile System**: Fires projectiles that deal 171 damage in a 3000 pixel radius
- **Unit Spawning**: Spawns 1 "DeliveryRecruit" unit on impact
- **Targeting**: Hits both ground and air targets
- **Spawn Character**: "DeliveryRecruit" with:
  - Hitpoints: 214
  - Damage: 52
  - Shield Hitpoints: 94
  - Speed: 60
  - Range: 1600
  - Hit Speed: 1300ms
  - Ground targeting only
  - 1000ms deploy time

## Implementation Status

### ✅ Implemented
- **Dynamic Spell Recognition**: Royal Delivery is correctly identified by `determine_spell_type()` in `src/clasher/dynamic_spells.py:37-39` as a `SpawnProjectileSpell` due to having `projectileData` with `spawnCharacterData`
- **Dynamic Loading**: Spell loads correctly through `load_dynamic_spells()` in `src/clasher/dynamic_spells.py:191-205`
- **Projectile Mechanics**: Basic projectile travel and spawning handled by `SpawnProjectileSpell` class in `src/clasher/dynamic_spells.py:106-117`
- **Area Damage**: Projectile radius and damage properly configured from JSON data
- **Unit Spawning**: Spawn count and character data passed through from gamedata.json

### ❌ Missing
- **Area Effect Object**: The initial area effect object (`RoyalDeliveryArea`) with 2000ms duration and hit timing is not implemented
- **Spawn Time Configuration**: The 250ms spawn time delay from the area effect object is not handled
- **Delivery Recruit Stats**: The spawned unit's specific stats (shield hitpoints, deploy time, exact damage/range) may not match gamedata.json exactly
- **Hit Speed/Area Effect**: The area effect object's hit speed of 2000ms is not implemented
- **Enemy-Only Targeting**: The `onlyEnemies: true` flag from the area effect object is not enforced

### ❌ Partially Implemented
- **Spell Registry**: Fallback static implementation in `src/clasher/spells.py:464` uses `DirectDamageSpell` with wrong elixir cost (4 instead of 3) and zero damage - this should be overridden by dynamic loading
- **Unit Deployment**: SpawnProjectileSpell handles basic spawning but may not account for the exact deploy mechanics and timing

## Notes
- **Name Mapping**: Card name is consistent across all files ("RoyalDelivery")
- **Dynamic vs Static**: The card should primarily use the dynamic loading system, with the static definition serving only as a fallback
- **Complex Mechanics**: Royal Delivery has a two-stage mechanic (area effect → projectile → spawn) that may require specialized handling beyond the standard SpawnProjectileSpell
- **Elixir Cost**: Static definition has wrong elixir cost (4 vs 3), but this should be corrected by dynamic loading from gamedata.json

## Recommendations
1. Implement proper area effect object creation with timing
2. Add spawn time delay configuration
3. Ensure spawned unit matches exact DeliveryRecruit stats from gamedata.json
4. Consider adding specialized handling for the two-stage delivery mechanism
5. Remove or correct the static fallback definition with wrong elixir cost