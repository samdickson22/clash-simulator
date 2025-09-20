# Miner Card Implementation Audit

## Card Details
- **Card**: Miner
- **Elixir**: 3
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground troop

## Implemented
- **Basic troop mechanics** (src/clasher/entities.py:240-690) - Standard movement, targeting, and combat
- **Ground-only targeting** - TID_TARGETS_GROUND in gamedata.json
- **Standard deployment** (src/clasher/battle.py:129-164) - Regular troop deployment rules
- **Melee combat** - 1.2 tile range attacks
- **Hitbox collision** - 0.5 tile collision radius (hitboxes.json)
- **Basic stats** - HP: 473, Damage: 76, Speed: 90, Hit Speed: 1.2s

## Missing
- **Underground/burrowing deployment** - Core signature mechanic allowing deployment anywhere on battlefield
- **Anywhere deployment system** - No "canDeployAnywhere" attribute or deployment zone override
- **Burrowing state management** - No underground entity states or visual effects
- **Special movement mechanics** - No underground pathfinding or burrow speed modifiers
- **Emergence effects** - No surfacing animations or feedback
- **Special deployment validation** - Currently restricted to standard deployment zones

## Notes
- **Current status**: ~30% complete - functions as generic ground troop without signature ability
- **Name mapping**: "Miner" in gamedata.json matches expected card name
- **Mechanic assumption**: Underground burrowing/deployment is Miner's defining feature based on Clash Royale lore
- **Infrastructure gap**: Missing special deployment systems, underground states, and teleport mechanics
- **Comparison**: Similar to Bandit's partial dash implementation - codebase has some special movement infrastructure but incomplete