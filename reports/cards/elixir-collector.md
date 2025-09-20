# Elixir Collector - Implementation Audit

## Card Details
- **Name**: Elixir Collector
- **Elixir Cost**: 6
- **Category**: Building
- **Rarity**: Rare

## Mechanics from gamedata.json
- Generates 1 elixir every 12 seconds (manaGenerateTimeMs: 12000, manaCollectAmount: 1)
- Lifetime: 86 seconds (lifeTime: 86000)
- Hitpoints: 418
- Collision radius: 1.0 tiles (1000 units)
- Deploy time: 1 second (deployTime: 1000)
- Grants 1 elixir on death (manaOnDeath: 1)

## Implemented
- ❌ **Building class exists** - No specific Elixir Collector implementation found in src/clasher/entities.py:692
- ❌ **Elixir generation** - No elixir generation mechanics found in the codebase
- ❌ **Death elixir bonus** - No death elixir mechanics found
- ❌ **Building spawning** - No building card instantiation logic found

## Missing
- Building spawning system
- Elixir generation mechanics (every 12 seconds)
- Death elixir bonus (1 elixir on destruction)
- Building lifecycle management
- Elixir Collector entity class

## Notes
- The Building base class exists in src/clasher/entities.py:692 but lacks elixir generation capabilities
- No elixir management system appears to be implemented in the codebase
- The gamedata.json contains complete stats for Elixir Collector but no corresponding implementation exists
- This appears to be a non-functional card in the current codebase state