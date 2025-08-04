#!/usr/bin/env python3
"""
Debug troop movement in actual battle conditions
"""

import sys
sys.path.append('src')

from clasher.engine import BattleEngine
from clasher.arena import Position

def debug_battle_movement():
    """Debug movement in actual battle simulation"""
    
    print("🔍 BATTLE MOVEMENT DEBUG")
    print("=" * 30)
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    print(f"📊 BATTLE STATE:")
    print(f"   dt: {battle.dt} seconds")
    print(f"   Entities: {len(battle.entities)}")
    
    # Deploy a Knight vs Knight scenario
    success1 = battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    success2 = battle.deploy_card(1, "Knight", Position(9.0, 20.0))
    
    print(f"\n🏗️ DEPLOYMENT:")
    print(f"   Blue Knight deployed: {'✅' if success1 else '❌'}")
    print(f"   Red Knight deployed: {'✅' if success2 else '❌'}")
    print(f"   Total entities: {len(battle.entities)}")
    
    # Find the knights
    knights = [e for e in battle.entities.values() if hasattr(e, 'card_stats') and e.card_stats and e.card_stats.name == 'Knight']
    
    if len(knights) >= 2:
        blue_knight = knights[0] if knights[0].player_id == 0 else knights[1]
        red_knight = knights[1] if knights[1].player_id == 1 else knights[0]
        
        print(f"\n👑 KNIGHTS FOUND:")
        print(f"   Blue Knight: ID={blue_knight.id}, Pos=({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f})")
        print(f"   Red Knight: ID={red_knight.id}, Pos=({red_knight.position.x:.2f}, {red_knight.position.y:.2f})")
        print(f"   Blue Speed: {blue_knight.speed} tiles/min")
        print(f"   Red Speed: {red_knight.speed} tiles/min")
        print(f"   Distance: {blue_knight.position.distance_to(red_knight.position):.2f}")
        
        # Simulate battle steps
        print(f"\n🏃 BATTLE SIMULATION:")
        
        for step in range(100):  # 100 ticks = ~3.3 seconds
            old_blue_pos = Position(blue_knight.position.x, blue_knight.position.y)
            old_red_pos = Position(red_knight.position.x, red_knight.position.y)
            
            # Step the battle
            battle.step(1.0)  # Normal speed
            
            # Check movement
            blue_moved = (abs(blue_knight.position.x - old_blue_pos.x) > 0.001 or 
                         abs(blue_knight.position.y - old_blue_pos.y) > 0.001)
            red_moved = (abs(red_knight.position.x - old_red_pos.x) > 0.001 or 
                        abs(red_knight.position.y - old_red_pos.y) > 0.001)
            
            if step % 30 == 0:  # Print every 30 ticks (~1 second)
                distance = blue_knight.position.distance_to(red_knight.position)
                print(f"   Step {step:3d}: Blue=({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) {'📍' if blue_moved else '⏸️'}")
                print(f"            Red=({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) {'📍' if red_moved else '⏸️'}")
                print(f"            Distance: {distance:.2f}")
                print(f"            Blue target: {blue_knight.target_id}, Red target: {red_knight.target_id}")
            
            if blue_moved or red_moved:
                print(f"   🎉 Movement detected at step {step}!")
                break
                
            # Check if they found each other as targets
            if blue_knight.target_id and red_knight.target_id:
                print(f"   🎯 Both knights have targets at step {step}")
                continue
        else:
            print(f"\n⚠️ No movement detected in 100 steps")
            print(f"   Blue Knight target: {blue_knight.target_id}")
            print(f"   Red Knight target: {red_knight.target_id}")
            print(f"   Blue sight range: {blue_knight.sight_range}")
            print(f"   Red sight range: {red_knight.sight_range}")
            
            # Check if they can see each other
            distance = blue_knight.position.distance_to(red_knight.position)
            print(f"   Distance: {distance:.2f}")
            print(f"   Blue can see Red: {distance <= blue_knight.sight_range}")
            print(f"   Red can see Blue: {distance <= red_knight.sight_range}")
    else:
        print(f"❌ Could not find 2 knights. Found {len(knights)} knights.")
        for knight in knights:
            print(f"   Knight ID={knight.id}, Player={knight.player_id}, Pos=({knight.position.x:.2f}, {knight.position.y:.2f})")

if __name__ == "__main__":
    debug_battle_movement()