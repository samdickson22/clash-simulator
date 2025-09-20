# Little Prince Card Audit

## Card Details
- **Card**: Little Prince
- **Elixir**: 3
- **Category**: Troop (Champion)
- **Rarity**: Champion
- **Type**: Ranged troop with guardian spawn ability

## Implemented
- Basic troop entity structure (`src/clasher/entities.py:55`)
- Card data loading system (`src/clasher/data.py:102`)
- Projectile mechanics (base system exists)
- Basic movement and targeting (base Troop class)

## Missing
- **Champion ability system** - Guardian spawn mechanic (`ChampGuardianAbility` in gamedata.json)
- **Guardian entity** - `ChampionGuard` troop with dash mechanics (`dashMaxRange`, `jumpSpeed`)
- **Ability activation** - 3 elixir cost, 30s cooldown mechanics
- **Projectile implementation** - `LittlePrinceProjectile` with 800 speed, 39 damage
- **Push-back effect** - Guardian spawn deals 90 damage with 2000 pushback strength
- **Champion card type** handling - Currently no special champion logic

## Notes
- Card exists in gamedata.json with full ability definition
- No code implementation found for champion-specific mechanics
- Ability spawns a guardian troop that charges/dashes to target
- Guardian has separate stats: 625 HP, 79 damage, melee range (1200), ground-only targeting
- Base Little Prince: 273 HP, 39 damage via projectile, 5.5 tile range, air & ground targeting