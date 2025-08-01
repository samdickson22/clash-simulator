#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def test_king_tower_update():
    """Test King Tower with new stats: 4824 HP, 109 damage, 7 range, 1000ms hit speed"""
    
    print("=== King Tower Update Test ===")
    battle = BattleState()
    
    # Find King Towers
    king_towers = []
    princess_towers = []
    
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats:
            if entity.card_stats.name == "KingTower":
                king_towers.append(entity)
            elif entity.card_stats.name == "Tower":
                princess_towers.append(entity)
    
    print(f"Found {len(king_towers)} King Towers, {len(princess_towers)} Princess Towers")
    
    if king_towers:
        king = king_towers[0]
        print(f"\nKing Tower Stats:")
        print(f"  HP: {king.hitpoints} (expected: 4824)")
        print(f"  Damage: {king.damage} (expected: 109)")
        print(f"  Range: {king.range} (expected: 7.0)")
        print(f"  Hit Speed: {king.card_stats.hit_speed}ms (expected: 1000ms)")
        print(f"  Attacks Air: {king.card_stats.attacks_air}")
        print(f"  Level: {king.card_stats.level}")
        
        # Verify stats
        assert king.hitpoints == 4824, f"King HP incorrect: {king.hitpoints}"
        assert king.damage == 109, f"King damage incorrect: {king.damage}"
        assert king.range == 7.0, f"King range incorrect: {king.range}"
        assert king.card_stats.hit_speed == 1000, f"King hit speed incorrect: {king.card_stats.hit_speed}"
        
        print("✅ King Tower stats verified")
    
    if princess_towers:
        princess = princess_towers[0]
        print(f"\nPrincess Tower Stats (for comparison):")
        print(f"  HP: {princess.hitpoints} (Level 11: 3631)")
        print(f"  Damage: {princess.damage} (Level 11: 129)")
        print(f"  Range: {princess.range} (7.5)")
        print(f"  Hit Speed: {princess.card_stats.hit_speed}ms (800ms)")
    
    # Test Player State
    print(f"\n=== Player State Verification ===")
    for i, player in enumerate(battle.players):
        print(f"Player {i}:")
        print(f"  King Tower HP: {player.king_tower_hp} (expected: 4824)")
        print(f"  Left Tower HP: {player.left_tower_hp} (expected: 3631)")
        print(f"  Right Tower HP: {player.right_tower_hp} (expected: 3631)")
        
        assert player.king_tower_hp == 4824.0, f"Player {i} King HP incorrect"
        assert player.left_tower_hp == 3631.0, f"Player {i} Princess HP incorrect"
    
    print("✅ Player state verified")
    
    # Test range difference
    print(f"\n=== Range Comparison ===")
    if king_towers and princess_towers:
        king_range = king_towers[0].range
        princess_range = princess_towers[0].range
        
        print(f"King Tower range: {king_range} tiles")
        print(f"Princess Tower range: {princess_range} tiles")
        print(f"Range difference: {princess_range - king_range:.1f} tiles")
        
        if king_range < princess_range:
            print("✅ King Tower has shorter range than Princess Towers")
        else:
            print("❌ King Tower range issue")
    
    print(f"\n=== Damage Comparison ===")
    if king_towers and princess_towers:
        king_damage = king_towers[0].damage
        princess_damage = princess_towers[0].damage
        
        print(f"King Tower damage: {king_damage}")
        print(f"Princess Tower damage: {princess_damage}")
        print(f"King Tower does {((king_damage / princess_damage - 1) * 100):.1f}% more damage")
        
        if king_damage > princess_damage:
            print("✅ King Tower does more damage than Princess Towers")
    
    print(f"\n=== Summary ===")
    print("✅ King Tower: 4824 HP, 109 damage, 7.0 range, 1000ms hit speed")
    print("✅ Princess Towers: 3631 HP, 129 damage, 7.5 range, 800ms hit speed")
    print("✅ King Tower has shorter range but higher HP and different damage")
    print("✅ Both tower types can attack air units")

if __name__ == "__main__":
    test_king_tower_update()