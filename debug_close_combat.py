#!/usr/bin/env python3
"""
Debug troop movement with close combat
"""

import sys
sys.path.append('src')

from clasher.engine import BattleEngine
from clasher.arena import Position

def debug_close_combat():
    """Debug movement with knights close enough to see each other"""
    
    print("🔍 CLOSE COMBAT DEBUG")
    print("=" * 30)
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    # Deploy knights closer together (within sight range)
    success1 = battle.deploy_card(0, "Knight", Position(9.0, 14.0))
    success2 = battle.deploy_card(1, "Knight", Position(9.0, 18.0))
    
    print(f"🏗️ DEPLOYMENT:")
    print(f"   Blue Knight deployed: {'✅' if success1 else '❌'}")
    print(f"   Red Knight deployed: {'✅' if success2 else '❌'}")
    
    # Find the knights
    knights = [e for e in battle.entities.values() if hasattr(e, 'card_stats') and e.card_stats and e.card_stats.name == 'Knight']
    
    if len(knights) >= 2:
        blue_knight = knights[0] if knights[0].player_id == 0 else knights[1]
        red_knight = knights[1] if knights[1].player_id == 1 else knights[0]
        
        distance = blue_knight.position.distance_to(red_knight.position)
        
        print(f"\n👑 KNIGHTS STATUS:")
        print(f"   Blue: ({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) Sight: {blue_knight.sight_range}")
        print(f"   Red:  ({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) Sight: {red_knight.sight_range}")
        print(f"   Distance: {distance:.2f}")
        print(f"   Blue can see Red: {distance <= blue_knight.sight_range}")
        print(f"   Red can see Blue: {distance <= red_knight.sight_range}")
        
        # Run battle simulation
        print(f"\n🏃 BATTLE SIMULATION:")
        
        for step in range(150):  # More steps to see movement
            old_blue_pos = Position(blue_knight.position.x, blue_knight.position.y)
            old_red_pos = Position(red_knight.position.x, red_knight.position.y)
            
            battle.step(1.0)
            
            blue_moved = (abs(blue_knight.position.x - old_blue_pos.x) > 0.001 or 
                         abs(blue_knight.position.y - old_blue_pos.y) > 0.001)
            red_moved = (abs(red_knight.position.x - old_red_pos.x) > 0.001 or 
                        abs(red_knight.position.y - old_red_pos.y) > 0.001)
            
            if step % 30 == 0 or blue_moved or red_moved:  # Print every second or when movement occurs
                current_distance = blue_knight.position.distance_to(red_knight.position)
                print(f"   Step {step:3d}: Blue=({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) {'📍' if blue_moved else '⏸️'}")
                print(f"            Red=({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) {'📍' if red_moved else '⏸️'}")
                print(f"            Distance: {current_distance:.2f}")
                print(f"            Targets: Blue→{blue_knight.target_id}, Red→{red_knight.target_id}")
                
                if blue_moved or red_moved:
                    print(f"   🎉 Movement detected!")
                    
                # Stop if they're very close (fighting)
                if current_distance < 2.0:
                    print(f"   ⚔️ Knights are fighting!")
                    break
        
        print(f"\nFinal distance: {blue_knight.position.distance_to(red_knight.position):.2f}")
    else:
        print(f"❌ Could not find 2 knights")

if __name__ == "__main__":
    debug_close_combat()