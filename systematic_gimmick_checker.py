#!/usr/bin/env python3
"""
Systematically check each card in gamedata.json for gimmicks and test them
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader, CardStats
from src.clasher.battle import BattleState
from src.clasher.arena import Position
import json

def load_all_cards():
    """Load all cards from gamedata.json"""
    loader = CardDataLoader()
    cards = loader.load_cards()
    return cards

def check_card_for_gimmicks(card_name, card_stats):
    """Check a card for various gimmicks and return list of found gimmicks"""
    gimmicks = []
    
    # Charging mechanics
    if card_stats.charge_range is not None and card_stats.charge_range > 0:
        gimmicks.append("CHARGING")
    
    # Death spawn mechanics
    if card_stats.death_spawn_character is not None:
        gimmicks.append("DEATH_SPAWN")
    
    # Kamikaze mechanics
    if card_stats.kamikaze:
        gimmicks.append("KAMIKAZE")
    
    # Buff mechanics
    if (card_stats.buff_data is not None or 
        card_stats.hit_speed_multiplier is not None or
        card_stats.speed_multiplier is not None or
        card_stats.spawn_speed_multiplier is not None):
        gimmicks.append("BUFF")
    
    # Special timing mechanics
    if (card_stats.special_load_time is not None or
        card_stats.special_range is not None or
        card_stats.special_min_range is not None):
        gimmicks.append("SPECIAL_TIMING")
    
    # Evolution mechanics
    if card_stats.has_evolution:
        gimmicks.append("EVOLUTION")
    
    # Summon mechanics
    if card_stats.summon_count is not None and card_stats.summon_count > 0:
        gimmicks.append("SUMMON")
    
    # Area damage
    if card_stats.projectile_data and card_stats.projectile_data.get("areaDamage"):
        gimmicks.append("AREA_DAMAGE")
    
    # Projectile mechanics
    if card_stats.projectile_data is not None:
        gimmicks.append("PROJECTILE")
    
    # Building-specific gimmicks
    if card_stats.card_type == "Building":
        gimmicks.append("BUILDING")
    
    # Air/ground targeting
    if card_stats.attacks_air is not None or card_stats.attacks_ground is not None:
        gimmicks.append("TARGETING")
    
    return gimmicks

def test_charging_mechanics(card_name, card_stats):
    """Test charging mechanics for a card"""
    print(f"\\n=== Testing Charging: {card_name} ===")
    
    battle = BattleState()
    battle.players[0].hand = [card_name]
    battle.players[0].elixir = 10.0
    
    # Deploy the card
    pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, card_name, pos)
    print(f"Deployed {card_name}: {success}")
    
    if not success:
        return False
    
    # Find the entity
    entity = None
    for ent in battle.entities.values():
        if ent.card_stats.name == card_name and ent.player_id == 0:
            entity = ent
            break
    
    if not entity:
        print(f"Entity not found")
        return False
    
    print(f"Charge range: {entity.card_stats.charge_range}")
    print(f"Special damage: {entity.card_stats.damage_special}")
    print(f"Initial charging: {entity.is_charging}")
    
    # Deploy enemy target
    battle.players[1].hand = ["Knight"]
    battle.players[1].elixir = 10.0
    target_pos = Position(5.0, 25.0)
    battle.deploy_card(1, "Knight", target_pos)
    
    # Test charging behavior
    for i in range(100):
        battle.step()
        if i % 20 == 0:
            print(f"Tick {i}: is_charging={entity.is_charging}, has_charged={entity.has_charged}")
    
    return entity.is_charging or entity.has_charged

def test_death_spawn_mechanics(card_name, card_stats):
    """Test death spawn mechanics for a card"""
    print(f"\\n=== Testing Death Spawn: {card_name} ===")
    
    battle = BattleState()
    battle.players[0].hand = [card_name]
    battle.players[0].elixir = 10.0
    
    # Deploy the card
    pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, card_name, pos)
    print(f"Deployed {card_name}: {success}")
    
    if not success:
        return False
    
    # Find the entity
    entity = None
    for ent in battle.entities.values():
        if ent.card_stats.name == card_name and ent.player_id == 0:
            entity = ent
            break
    
    if not entity:
        print(f"Entity not found")
        return False
    
    print(f"Death spawn character: {entity.card_stats.death_spawn_character}")
    print(f"Death spawn count: {entity.card_stats.death_spawn_count}")
    
    # Deploy enemy target close by
    battle.players[1].hand = ["Knight"]
    battle.players[1].elixir = 10.0
    target_pos = Position(9.0, 17.0)
    battle.deploy_card(1, "Knight", target_pos)
    
    # Run until death or timeout
    for i in range(2000):
        battle.step()
        if not entity.is_alive:
            print(f"Died at tick {i}")
            break
        if i % 200 == 0:
            print(f"Tick {i}: HP={entity.hitpoints:.1f}")
    
    # Check for death spawns
    death_spawns = []
    for ent in battle.entities.values():
        if ent.card_stats.name == entity.card_stats.death_spawn_character:
            death_spawns.append(ent)
    
    print(f"Death spawns created: {len(death_spawns)}")
    return len(death_spawns) > 0

def test_kamikaze_mechanics(card_name, card_stats):
    """Test kamikaze mechanics for a card"""
    print(f"\\n=== Testing Kamikaze: {card_name} ===")
    
    battle = BattleState()
    battle.players[0].hand = [card_name]
    battle.players[0].elixir = 10.0
    
    # Deploy the card
    pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, card_name, pos)
    print(f"Deployed {card_name}: {success}")
    
    if not success:
        return False
    
    # Find the entity
    entity = None
    for ent in battle.entities.values():
        if ent.card_stats.name == card_name and ent.player_id == 0:
            entity = ent
            break
    
    if not entity:
        print(f"Entity not found")
        return False
    
    print(f"Kamikaze: {entity.card_stats.kamikaze}")
    print(f"Death spawn: {entity.card_stats.death_spawn_character}")
    
    return entity.card_stats.kamikaze

def test_summon_mechanics(card_name, card_stats):
    """Test summon mechanics for a card"""
    print(f"\\n=== Testing Summon: {card_name} ===")
    
    battle = BattleState()
    battle.players[0].hand = [card_name]
    battle.players[0].elixir = 10.0
    
    # Deploy the card
    pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, card_name, pos)
    print(f"Deployed {card_name}: {success}")
    
    if not success:
        return False
    
    # Find the entity
    entity = None
    for ent in battle.entities.values():
        if ent.card_stats.name == card_name and ent.player_id == 0:
            entity = ent
            break
    
    if not entity:
        print(f"Entity not found")
        return False
    
    print(f"Summon count: {entity.card_stats.summon_count}")
    print(f"Summon radius: {entity.card_stats.summon_radius}")
    
    initial_entities = len(battle.entities)
    
    # Run a few ticks to see if summons happen
    for i in range(50):
        battle.step()
    
    final_entities = len(battle.entities)
    print(f"Entities before: {initial_entities}, after: {final_entities}")
    
    return final_entities > initial_entities

def main():
    """Main function to systematically check all cards"""
    print("Systematic Gimmick Checker")
    print("==========================")
    
    # Load all cards
    cards = load_all_cards()
    print(f"Loaded {len(cards)} cards")
    
    # Track results
    results = {}
    
    # Check each card
    for card_name, card_stats in cards.items():
        print(f"\\n{'='*50}")
        print(f"Checking: {card_name} ({card_stats.card_type})")
        print(f"{'='*50}")
        
        # Check for gimmicks
        gimmicks = check_card_for_gimmicks(card_name, card_stats)
        
        if not gimmicks:
            print(f"No gimmicks found for {card_name}")
            results[card_name] = {"gimmicks": [], "tested": False}
            continue
        
        print(f"Gimmicks found: {', '.join(gimmicks)}")
        results[card_name] = {"gimmicks": gimmicks, "tested": True}
        
        # Test each gimmick
        for gimmick in gimmicks:
            try:
                if gimmick == "CHARGING":
                    test_charging_mechanics(card_name, card_stats)
                elif gimmick == "DEATH_SPAWN":
                    test_death_spawn_mechanics(card_name, card_stats)
                elif gimmick == "KAMIKAZE":
                    test_kamikaze_mechanics(card_name, card_stats)
                elif gimmick == "SUMMON":
                    test_summon_mechanics(card_name, card_stats)
                # Add more gimmick tests as needed
            except Exception as e:
                print(f"Error testing {gimmick}: {e}")
    
    # Summary
    print(f"\\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    
    cards_with_gimmicks = sum(1 for r in results.values() if r["gimmicks"])
    print(f"Cards with gimmicks: {cards_with_gimmicks}/{len(cards)}")
    
    for card_name, result in results.items():
        if result["gimmicks"]:
            print(f"{card_name}: {', '.join(result['gimmicks'])}")

if __name__ == "__main__":
    main()
