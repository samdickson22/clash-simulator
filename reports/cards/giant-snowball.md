# Giant Snowball Implementation Audit

## Card Details
- **Card**: Giant Snowball
- **Elixir**: 2
- **Category**: Spell
- **Rarity**: Common
- **Source**: spells_other

## Official Mechanics (from Clash Royale Wiki)
- 2 Elixir spell from Frozen Peak
- Deals area damage
- Slows enemies for 3 seconds
- Knocks enemies back
- Effective as finisher and disrupting enemy pushes

## Gamedata.json Analysis
The Giant Snowball ("Snowball" in gamedata) has these capabilities:
- **Projectile-based spell**: Uses SnowballSpell projectile with speed 800
- **Area damage**: Damage 70 in radius 2500 (2.5 tiles)
- **Pushback effect**: pushback 1800 units (knockback)
- **Slow effect**: 3000ms (3 seconds) duration, -35% multiplier
- **Tower damage**: -70% crown tower damage (reduced damage to buildings)
- **Targeting**: hits air and ground units

## Implemented
- ✅ **Slow effect**: `src/clasher/spells.py:463` - SNOWBALL with slow_duration=2.5, slow_multiplier=0.65
- ✅ **Area damage**: `src/clasher/spells.py:463` - radius=250.0/1000.0 (2.5 tiles)
- ✅ **Projectile system**: `src/clasher/spells.py:41` - DirectDamageSpell class used
- ✅ **Targeting**: `src/clasher/spells.py:25-37` - Hitbox collision detection for area spells

## Missing
- ❌ **Pushback/Knockback**: Not implemented - gamedata shows pushback 1800 but no pushback logic in SNOWBALL spell
- ❌ **Projectile travel**: Currently DirectDamageSpell, should be ProjectileSpell with speed 800
- ❌ **Tower damage reduction**: gamedata shows crownTowerDamagePercent -70% but not implemented
- ❌ **Slow duration mismatch**: gamedata=3000ms (3.0s) vs implemented=2.5s
- ❌ **Slow multiplier mismatch**: gamedata=-35% vs implemented=0.65 (35% reduction)

## Notes
- Name mapping: "Giant Snowball" in wiki vs "Snowball" in gamedata.json
- Uses DirectDamageSpell instead of ProjectileSpell - lacks visual projectile travel
- Pushback/knockback system exists in entities.py for Log but not applied to Snowball
- Slow values differ between gamedata (3.0s, -35%) and implementation (2.5s, 0.65)