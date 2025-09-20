# Heal Spirit Implementation Audit

## Card Details
- **Card**: Heal Spirit
- **Elixir**: 1
- **Category**: Spell (Troop-summoning spell)
- **Rarity**: Rare
- **Type**: Area healing with damage

## Gamedata.json Analysis
Based on gamedata.json analysis, the Heal Spirit has these mechanics:
- **summonCharacterData**: Spawns a "HealSpirit" character troop
- **projectileData**: The spirit launches a projectile ("HealSpiritProjectile")
- **spawnAreaEffectObjectData**: Creates a healing area effect on impact
- **buffData**: Heals 157 HP per second with 250ms frequency
- **kamikaze**: The troop dies after attacking (suicide unit)
- **Life Duration**: 1000ms (1 second) for the healing area
- **Radius**: 2500 (2.5 tiles) for healing area
- **Damage**: 43 damage from projectile explosion
- **Speed**: 120 (slow movement speed)

## Implemented Features
- ✅ **Spell Type Detection**: Correctly identified as HealSpell in `dynamic_spells.py:65-71`
- ✅ **Dynamic Loading**: Automatically loaded from gamedata.json via `dynamic_spells.py:191-205`
- ✅ **Heal Amount Calculation**: Approximates total heal from healPerSecond in `dynamic_spells.py:177`
- ✅ **HealSpell Class**: Basic healing functionality in `spells.py:278-298`
- ✅ **Area-based Healing**: Heals friendly units within radius using distance check

## Missing Features
- ❌ **Troop Summoning**: The actual Heal Spirit troop is not spawned/implemented
- ❌ **Troop Movement**: No AI for the spawned spirit to move toward targets
- ❌ **Projectile Launch**: Spirit doesn't launch healing projectile
- ❌ **Kamikaze Behavior**: Troop doesn't die after attacking/launching projectile
- ❌ **Area Effect Duration**: Healing area should persist for 1 second, not instant
- ❌ **Damage Component**: Projectile should deal 43 damage on impact
- ❌ **Specific Healing Rate**: Should heal 157 HP/sec at 250ms intervals, not lump sum

## Notes
- The implementation treats Heal Spirit as a direct healing spell, but it should spawn a troop that then creates the healing effect
- Name mapping: JSON uses "Heal" as the spell name, not "HealSpirit"
- The heal amount calculation (`healPerSecond * 4`) is an approximation rather than implementing the actual timing-based healing
- Current implementation only provides instant area healing, missing the troop mechanics and projectile system that define the card's unique behavior
- Card is categorized as a spell but should function as a troop-summoning spell with complex behavior