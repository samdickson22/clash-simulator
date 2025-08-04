#!/usr/bin/env python3
"""
Debug troop movement issues
"""

import sys
sys.path.append('src')

from clasher.engine import BattleEngine
from clasher.arena import Position
from clasher.entities import Troop
from clasher.data import CardDataLoader

def debug_troop_movement():
    """Debug why troops aren't moving"""
    
    print("🔍 TROOP MOVEMENT DEBUG")
    print("=" * 30)
    
    engine = BattleEngine()
    battle = engine.create_battle()
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    # Get Knight card
    knight_card = cards.get('Knight')
    if not knight_card:
        print("❌ Knight card not found")
        return
    
    print(f"📊 KNIGHT CARD DATA:")
    print(f"   Name: {knight_card.name}")
    print(f"   Speed: {knight_card.speed} tiles/min")
    print(f"   Range: {knight_card.range} tiles")
    print(f"   Sight Range: {knight_card.sight_range} tiles")
    
    # Deploy Knight manually
    knight = Troop(
        id=100,
        position=Position(3.5, 14.5),
        player_id=0,
        card_stats=knight_card,
        hitpoints=knight_card.hitpoints or 1000,
        max_hitpoints=knight_card.hitpoints or 1000,
        damage=knight_card.damage or 100,
        range=knight_card.range or 1.2,
        sight_range=knight_card.sight_range or 5.0,
        speed=knight_card.speed or 60.0  # Make sure speed is set
    )
    
    # Add target enemy
    target = Troop(
        id=101,
        position=Position(3.5, 18.0),
        player_id=1,
        card_stats=knight_card,
        hitpoints=500,
        max_hitpoints=500,
        damage=50,
        range=1.2,
        sight_range=5.0,
        speed=60.0
    )
    
    battle.entities[100] = knight
    battle.entities[101] = target
    
    print(f"\n🏗️ KNIGHT DEPLOYED:")
    print(f"   Position: ({knight.position.x:.2f}, {knight.position.y:.2f})")
    print(f"   Speed: {knight.speed} tiles/min = {knight.speed/60:.3f} tiles/sec")
    print(f"   Target ID: {knight.target_id}")
    print(f"   Attack cooldown: {knight.attack_cooldown}")
    
    print(f"\n🎯 TARGET:")
    print(f"   Position: ({target.position.x:.2f}, {target.position.y:.2f})")
    print(f"   Distance: {knight.position.distance_to(target.position):.2f}")
    
    # Check if knight can find target
    found_target = knight.get_nearest_target(battle.entities)
    print(f"   Can find target: {'✅ Yes' if found_target else '❌ No'}")
    if found_target:
        print(f"   Found target ID: {found_target.id}")
    
    # Run battle steps to see movement
    print(f"\n🏃 MOVEMENT SIMULATION:")
    
    for step in range(10):
        old_pos = Position(knight.position.x, knight.position.y)
        
        # Call knight update directly 
        knight.update(1.0, battle)  # 1 second timestep
        
        moved = (abs(knight.position.x - old_pos.x) > 0.001 or 
                abs(knight.position.y - old_pos.y) > 0.001)
        
        movement_x = knight.position.x - old_pos.x
        movement_y = knight.position.y - old_pos.y
        movement_distance = (movement_x**2 + movement_y**2)**0.5
        
        status = "📍 MOVED" if moved else "⏸️ STATIC"
        
        print(f"   Step {step+1}: ({knight.position.x:.3f}, {knight.position.y:.3f}) {status}")
        if moved:
            print(f"      Movement: dx={movement_x:.3f}, dy={movement_y:.3f}, dist={movement_distance:.3f}")
        
        print(f"      Target ID: {knight.target_id}")
        print(f"      Attack cooldown: {knight.attack_cooldown:.2f}")
        
        if knight.target_id:
            current_target = battle.entities.get(knight.target_id)
            if current_target:
                distance = knight.position.distance_to(current_target.position)
                print(f"      Distance to target: {distance:.3f}")
                print(f"      Should move: {distance > knight.range}")
        
        if moved and knight.position.distance_to(target.position) < 2.0:
            print(f"   ✅ Knight successfully moved toward target!")
            break
    else:
        print(f"\n⚠️ Knight didn't move significantly")
        print(f"   Final distance to target: {knight.position.distance_to(target.position):.2f}")

if __name__ == "__main__":
    debug_troop_movement()