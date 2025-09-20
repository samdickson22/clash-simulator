# Void Card Implementation Audit

## Card Details
- **Card**: Void (DarkMagic in gamedata.json)
- **Elixir**: 3
- **Category**: Spell
- **Rarity**: Epic
- **Type**: Area Effect Spell

## Implemented
- Basic spell registration in `src/clasher/spells.py:22` as `DARK_MAGIC = DirectDamageSpell("DarkMagic", 4, radius=3000.0, damage=0)`
- Spell registry inclusion in `src/clasher/spells.py:42` with mapping `"DarkMagic": DARK_MAGIC`
- Area damage framework through `DirectDamageSpell` base class
- Hitbox-based collision detection in `src/clasher/spells.py:58`
- Basic spell casting infrastructure

## Missing
- **Dynamic damage scaling**: Card uses `ActionLaserBall` with `maxUnitPerActionList: [1, 4]` - deals more damage to fewer targets (core mechanic)
- **Area of Effect**: Should have radius of 2500 (currently set to 3000 in code)
- **Elixir cost**: Currently set to 4 in code, should be 3
- **Laser beam effect**: Uses `ActionLaserBall` with `detectionRadius: 2500` and `hitFrequency: 1000`
- **Visual effects**: Missing `PaoloFirstEffectEverIntro` and `PaoloFirstEffectEver` effects
- **Damage application**: Current implementation has damage=0, but should deal damage based on target count
- **Life duration**: Area effect should persist for 4000ms (not implemented)
- **Target filtering**: Should use `ForcedCharacterTargets` hit filter

## Notes
- **Name mapping**: Card is named "DarkMagic" in gamedata.json but displayed as "Void" in englishName field
- **Core mechanic**: The "deals more damage to fewer targets" behavior is completely missing - this is the defining feature of Void
- **Effect timing**: Spell has delayed effects with `subActionsDelay: [0, 500]` and `firstHitDelay: 1000`
- **Stats tags**: Has complex damage scaling with `targets_mid_lower`, `targets_mid_upper`, `targets_more_lower`, and `damage_more_targets` tags
- **Special damage**: Uses `DarkMagicAOE_Damage_lv1` with `damagePerSecond: 297` and special crown tower damage handling