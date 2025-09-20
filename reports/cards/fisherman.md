# Fisherman Card Audit Report

## Card Information
- **Card**: Fisherman
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop with ranged pull attack

## Gamedata.json Analysis
Based on gamedata.json, Fisherman has these specific capabilities:

### Core Stats
- **Hitpoints**: 340
- **Damage**: 76
- **Range**: 1200 (1.2 tiles)
- **Speed**: 60 (medium speed)
- **Hit Speed**: 1300ms (1.3 seconds)
- **Sight Range**: 7500 (7.5 tiles)
- **Target**: Ground only

### Special Mechanics
- **Special Range**: 7000 (7.0 tiles) - range for pull ability
- **Special Min Range**: 3500 (3.5 tiles) - minimum range for pull ability
- **Special Load Time**: 1300ms - cooldown for pull attack
- **Pull Projectile**: "FishermanProjectile" with speed 800, buff time 1500ms
- **Slow Effect**: "IceWizardSlowDown" -35% hit speed, -35% movement speed, -35% spawn speed

## Implemented

### ✅ Basic Troop Mechanics
- Ground troop spawning and movement (`src/clasher/battle.py:515`)
- Basic attack system (`src/clasher/entities.py:415`)
- Target selection and pathfinding (`src/clasher/entities.py:380`)
- Health and damage system (`src/clasher/entities.py:200`)

### ✅ Projectile System
- Ranged projectile attacks (`src/clasher/entities.py:420`)
- Projectile travel and impact (`src/clasher/entities.py:425`)

### ✅ Slow Effect System
- Slow debuff application (`src/clasher/entities.py:180`)
- Speed modification mechanics (`src/clasher/entities.py:185`)

## Missing

### ❌ Pull Hook Mechanism
- **Source**: gamedata.json shows `projectileSpecialData` with "FishermanProjectile"
- **Issue**: No implementation of the unique pull/tether mechanic that pulls enemies toward Fisherman
- **Expected**: Special attack that pulls target enemy closer (similar to Tornado but targeted)

### ❌ Dual Range System
- **Source**: gamedata.json defines both normal range (1200) and special range (7000)
- **Issue**: Codebase only handles single range values
- **Expected**: Fisherman should use different ranges for normal attacks vs pull attacks

### ❌ Special Attack Cooldown
- **Source**: gamedata.json has `specialLoadTime`: 1300ms separate from normal `hitSpeed`
- **Issue**: No special attack cooldown system implemented
- **Expected**: Separate cooldown timer for pull ability vs normal attacks

### ❌ Special Min Range
- **Source**: gamedata.json has `specialMinRange`: 3500
- **Issue**: No minimum range validation for special attacks
- **Expected**: Pull attack should only work at distances > 3.5 tiles

## Notes

- **Name Mapping**: Card is correctly named "Fisherman" in both gamedata.json and would be loaded dynamically
- **Card Type**: Classified as character/troop, so would use Troop class (`src/clasher/entities.py:284`)
- **Evolution**: No evolution data present (correct for audit scope)
- **Ambiguity**: The pull mechanic implementation is unclear - would require new entity behavior or special projectile type
- **Assumption**: Fisherman would be handled by dynamic spell loading but lack unique pull mechanics makes it function as basic ranged troop with slow