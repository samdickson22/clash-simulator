# Lightning Card Audit Report

## Card Details
- **Card**: Lightning
- **Elixir**: 6
- **Category**: Spell
- **Rarity**: Epic

## Implemented
- Direct damage in area radius (3500 units / 3.5 tiles) - `src/clasher/spells.py:426`
- Stun effect (0.5 seconds) on hit targets - `src/clasher/spells.py:61`
- Area effect collision detection with hitbox overlap - `src/clasher/spells.py:56`
- Projectile creation with "LighningSpell" projectile - `gamedata.json:8587`
- Tower damage reduction (-73%) - `gamedata.json:8591`
- Speed/attack slowdown (100% reduction) - `gamedata.json:8595-8602`
- Hit both air and ground targets - `gamedata.json:8583-8584`

## Missing
- Multi-target targeting system (Lightning should hit up to 3 targets with priority system)
- Area of effect object duration (1500ms lifetime from gamedata) - current implementation is instant
- Hit speed mechanics (460ms from gamedata) - not implemented in current DirectDamageSpell
- Buff/debuff application system for the ZapFreeze effect - gamedata shows complex buff structure
- Projectile travel mechanics - Lightning should travel from source to target with speed 500

## Notes
- Current implementation uses DirectDamageSpell class, but gamedata suggests Lightning should have area effect object with projectiles
- Name mapping: gamedata shows "LighningSpell" (typo) projectile name
- Gamedata reveals Lightning has complex mechanics: area effect object + projectiles + buff system
- Static LIGHTNING definition in spells.py uses simplified DirectDamageSpell (damage: 864) vs gamedata projectile damage: 413
- Missing the area effect object's hitSpeed (460ms) which suggests periodic damage application
- No implementation of the multi-target priority system that Lightning typically has in Clash Royale