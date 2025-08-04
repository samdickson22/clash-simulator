#!/usr/bin/env python3
"""
Test simple movement system
"""

import sys
sys.path.append('src')

from clasher.engine import BattleEngine
from clasher.arena import Position

def test_simple_movement():
    """Test that troops move toward enemy side when spawned"""
    
    print("🔍 SIMPLE MOVEMENT TEST")
    print("=" * 30)
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    # Deploy troops on both sides
    success1 = battle.deploy_card(0, "Knight", Position(9.0, 8.0))   # Blue side
    success2 = battle.deploy_card(1, "Knight", Position(9.0, 24.0))  # Red side
    
    print(f"🏗️ DEPLOYMENT:")
    print(f"   Blue Knight deployed: {'✅' if success1 else '❌'}")
    print(f"   Red Knight deployed: {'✅' if success2 else '❌'}")
    
    # Find the knights
    knights = [e for e in battle.entities.values() if hasattr(e, 'card_stats') and e.card_stats and e.card_stats.name == 'Knight']
    
    if len(knights) >= 2:
        blue_knight = knights[0] if knights[0].player_id == 0 else knights[1]
        red_knight = knights[1] if knights[1].player_id == 1 else knights[0]
        
        print(f"\n👑 KNIGHTS STATUS:")
        print(f"   Blue: ({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) Speed: {blue_knight.speed}")
        print(f"   Red:  ({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) Speed: {red_knight.speed}")
        
        # Run battle simulation
        print(f"\n🏃 MOVEMENT TEST:")
        
        for step in range(60):  # 2 seconds worth of steps
            old_blue_pos = Position(blue_knight.position.x, blue_knight.position.y)
            old_red_pos = Position(red_knight.position.x, red_knight.position.y)
            
            battle.step(1.0)
            
            blue_moved = (abs(blue_knight.position.x - old_blue_pos.x) > 0.001 or 
                         abs(blue_knight.position.y - old_blue_pos.y) > 0.001)
            red_moved = (abs(red_knight.position.x - old_red_pos.x) > 0.001 or 
                        abs(red_knight.position.y - old_red_pos.y) > 0.001)
            
            if step % 15 == 0 or blue_moved or red_moved:  # Print every 0.5 seconds or on movement
                print(f"   Step {step:2d}: Blue=({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) {'📍' if blue_moved else '⏸️'}")
                print(f"           Red=({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) {'📍' if red_moved else '⏸️'}")
                print(f"           Targets: Blue→{blue_knight.target_id}, Red→{red_knight.target_id}")
                
                if blue_moved or red_moved:
                    print(f"   🎉 Movement detected!")
                    # Check direction
                    blue_direction = "toward red" if blue_knight.position.y > old_blue_pos.y else "toward blue" if blue_knight.position.y < old_blue_pos.y else "sideways"
                    red_direction = "toward blue" if red_knight.position.y < old_red_pos.y else "toward red" if red_knight.position.y > old_red_pos.y else "sideways"
                    print(f"           Blue moving: {blue_direction}")
                    print(f"           Red moving: {red_direction}")
                    
                    # If both are moving toward each other, that's success
                    if blue_knight.position.y > old_blue_pos.y and red_knight.position.y < old_red_pos.y:
                        print(f"   ✅ SUCCESS! Both knights moving toward enemy side!")
                        break
        
        final_distance = blue_knight.position.distance_to(red_knight.position)
        print(f"\nFinal distance: {final_distance:.2f}")
        
        if final_distance < 16:  # They got closer
            print(f"✅ Knights moved toward each other!")
        else:
            print(f"⚠️ Knights didn't get significantly closer")
    else:
        print(f"❌ Could not find 2 knights")

if __name__ == "__main__":
    test_simple_movement()