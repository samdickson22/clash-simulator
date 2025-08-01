#!/usr/bin/env python3
"""
Debug red knight attack behavior
"""

from src.clasher.engine import BattleEngine
from src.clasher.arena import Position

def debug_red_knight_attack():
    """Debug red knight reaching target and attacking"""
    print("=== Red Knight Attack Debug ===")
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    # Deploy red knight
    battle.players[1].elixir = 10.0
    battle.deploy_card(1, 'Knight', Position(9, 20))
    
    # Find the red knight and target
    red_knight = None
    for entity in battle.entities.values():
        if (hasattr(entity, 'card_stats') and entity.card_stats and 
            entity.card_stats.name == 'Knight' and entity.player_id == 1):
            red_knight = entity
            break
    
    # Run until near target
    print("Running simulation until near target...")
    for step in range(30):
        battle.step(speed_factor=1.0)
        
        if red_knight.target_id:
            target = battle.entities.get(red_knight.target_id)
            if target:
                distance = red_knight.position.distance_to(target.position)
                if distance <= red_knight.range:
                    print(f"Knight reached attack range at step {step+1}")
                    print(f"  Position: ({red_knight.position.x:.2f}, {red_knight.position.y:.2f})")
                    print(f"  Distance: {distance:.2f}")
                    print(f"  Range: {red_knight.range:.2f}")
                    print(f"  Target HP: {target.hitpoints}")
                    break
    
    # Continue simulation to see attacks
    print("\nContinuing to monitor attacks...")
    for step in range(10):
        old_hp = 0
        if red_knight.target_id:
            target = battle.entities.get(red_knight.target_id)
            if target:
                old_hp = target.hitpoints
        
        battle.step(speed_factor=1.0)
        
        new_hp = 0
        attacked = False
        if red_knight.target_id:
            target = battle.entities.get(red_knight.target_id)
            if target:
                new_hp = target.hitpoints
                attacked = old_hp != new_hp
                distance = red_knight.position.distance_to(target.position)
        
        print(f"  Step {step+1}: HP {new_hp:.0f} CD {red_knight.attack_cooldown:.2f} "
              f"Dist {distance:.2f} {'ATTACKED' if attacked else ''}")
        
        if attacked:
            print(f"    >>> Attack successful! Damage: {old_hp - new_hp}")

if __name__ == "__main__":
    debug_red_knight_attack()