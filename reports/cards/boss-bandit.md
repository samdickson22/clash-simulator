# Boss Bandit Card Audit Report

## Card Details
- **Card**: Boss Bandit
- **Elixir**: 6
- **Category**: Troop (Champion)
- **Rarity**: Champion
- **Type**: Ground troop

## Implemented
- **Basic troop mechanics**: Movement, targeting, attack (`src/clasher/entities.py:240-690`)
- **Combat stats**: HP (1063 → 2757 scaled), Damage (105 → 272 scaled), Range (0.8 tiles), Speed (90 tiles/min) (`src/clasher/data.py:CardStats`)
- **Dash mechanics data**: Raw dash parameters exist in gamedata (DashMinRange: 3500, DashMaxRange: 6000, DashDamage: 210, JumpSpeed: 500)
- **Card loading**: Successfully loads as "BossBandit" with ID 26000103 (`src/clasher/data.py:CardDataLoader`)

## Missing
- **Dash/Charge mechanics**: Despite having dash parameters in gamedata, no actual dash implementation in Troop class - dash mechanics are mapped to charging system but Boss Bandit doesn't use standard charging
- **Getaway Grenade ability**: 1-elixir teleport/warp ability completely missing from codebase
- **Ability system**: No champion ability system implemented in entities.py
- **Teleport mechanics**: No teleportation or warping functionality in movement system
- **Special targeting**: "Rascals only check" mentioned in gamedata but not implemented
- **Buff spawning**: Ability should spawn a buff after 1000ms delay - not implemented
- **One-time ability use**: 999999 cooldown suggests single use - not enforced

## Notes
- **Name mapping**: Card is stored as "BossBandit" (camelCase) in codebase, displays as "Boss Bandit"
- **Gamedata vs implementation**: Dash parameters exist in gamedata.json but Troop class uses generic charging mechanics instead
- **Ability complexity**: Boss Bandit's ability system is referenced in gamedata but completely absent from codebase
- **Champion status**: Recognized as Champion rarity but no special champion mechanics implemented