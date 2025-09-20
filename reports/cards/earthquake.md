# Earthquake Card Audit Report

## Card Details
- **Name**: Earthquake
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Rare

## Implemented
- **Basic area damage spell** (`src/clasher/spells.py:460`)
  - Instant damage in 3.0 tile radius
  - 332 damage value
  - Uses `DirectDamageSpell` class

- **Slow effect** (`src/clasher/spells.py:460`)
  - 3.0 second slow duration
  - 0.5x speed multiplier (50% slow)

- **Dynamic spell loading** (`src/clasher/dynamic_spells.py:59`)
  - Correctly classified as `DirectDamageSpell` based on areaEffectObjectData with lifeDuration <= 1000ms

## Missing
- **Building damage multiplier** (from gamedata.json)
  - `buildingDamagePercent: 350` (350% damage to buildings)
  - Currently deals same damage to all targets

- **Crown tower damage reduction** (from gamedata.json)
  - `crownTowerDamagePercent: -35` (35% reduced damage to crown towers)
  - Currently deals full damage to all targets

- **Damage over time** (from gamedata.json)
  - `damagePerSecond: 32` with `hitFrequency: 1000`
  - Currently implemented as instant damage only

- **Ground targeting restriction** (from gamedata.json)
  - `hitsGround: true` and `hitsAir: false`
  - Currently affects both ground and air targets

- **Area effect duration** (from gamedata.json)
  - `lifeDuration: 3000` (3 seconds)
  - `buffTime: 1000` (1 second buff duration)
  - Currently implemented as instant effect

## Notes
- The spell is registered in the static spell registry and will be loaded dynamically
- Current implementation treats Earthquake as a simple direct damage spell with slow
- gamedata.json indicates Earthquake should have complex damage scaling (different for buildings vs crown towers) and damage over time mechanics
- The spell should only affect ground units, not air units
- Name mapping: "Earthquake" in code matches "Earthquake" in gamedata.json