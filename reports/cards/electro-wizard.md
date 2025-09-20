# CR Audit - Electro Wizard

## Card Overview
- **Name**: Electro Wizard
- **Elixir**: 4
- **Category**: Troop
- **Rarity**: Legendary
- **Type**: Ground unit

## Implemented
- Basic troop movement and targeting system (src/clasher/entities.py:240-309)
- Stun mechanics system (src/clasher/entities.py:108-139)
- General damage dealing (src/clasher/entities.py:72-101)
- Hitbox-based collision detection (src/clasher/entities.py:97-101)
- Air/ground targeting support (src/clasher/entities.py:21-24)

## Missing
- **Multiple targets attack**: `multipleTargets: 2` mechanic from gamedata.json:2873
- **Chain lightning**: Electro Wizard attacks should jump to 2 targets
- **Zap freeze effect on damage**: `buffOnDamageTime: 500` with `ZapFreeze` buff (gamedata.json:2876-2890)
- **Deployment area effect**: `ElectroWizardZap` AOE on spawn (gamedata.json:2892-2913)
- **Stun application**: The `ZapFreeze` buff should stun targets (gamedata.json:2882-2889)
- **Hit speed/speed reduction**: -100% multiplier for 0.5s duration (gamedata.json:2886-2888)

## Notes
- Electro Wizard is not specifically implemented in the codebase
- Basic troop functionality exists but lacks the unique multi-target chain lightning mechanic
- The zap/stun debuff system exists in the engine but is not applied by Electro Wizard attacks
- Deployment zap effect is completely missing
- Card data shows the Electro Wizard should apply a stun effect on both attack and deployment

## Gamedata.json Key Mechanics
- `multipleTargets: 2` - attacks chain to 2 targets
- `buffOnDamageTime: 500` - applies debuff for 0.5 seconds
- `ZapFreeze` buff: -100% hit speed, -100% speed, -100% spawn speed
- `ElectroWizardZap` area effect on deployment: 75 damage + 0.5s stun