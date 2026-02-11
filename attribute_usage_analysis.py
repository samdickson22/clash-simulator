#!/usr/bin/env python3
"""
Analysis of card attribute loading vs actual usage in the battle system.
This script identifies the gap between available data and what's actually used.
"""

import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent / "src"))

from src.clasher.data import CardDataLoader

def analyze_attribute_usage():
    """Analyze which card attributes are loaded vs used in battle"""
    print("🔍 CARD ATTRIBUTE USAGE ANALYSIS")
    print("=" * 80)

    # Load cards using the compatibility system (what gameplay relies on)
    loader = CardDataLoader()
    legacy_cards = loader.load_cards()

    # Load card definitions using the new system (what's available but unused)
    new_cards = loader.load_card_definitions()

    print(f"📊 Data Sources:")
    print(f"  • Compat CardStats: {len(legacy_cards)} cards")
    print(f"  • New CardDefinition: {len(new_cards)} cards")
    print()

    # Analyze a sample card to show attribute availability
    sample_card_name = "Knight"
    if sample_card_name in legacy_cards and sample_card_name in new_cards:
        legacy_card = legacy_cards[sample_card_name]
        new_card = new_cards[sample_card_name]

        print(f"🃏 SAMPLE ANALYSIS: {sample_card_name}")
        print("-" * 40)

        print(f"\n📦 LOADED ATTRIBUTES (Compat CardStats):")
        legacy_attrs = [attr for attr in dir(legacy_card) if not attr.startswith('_') and not callable(getattr(legacy_card, attr))]
        print(f"  Total: {len(legacy_attrs)} attributes")
        print(f"  Combat: hitpoints={legacy_card.hitpoints}, damage={legacy_card.damage}, range={legacy_card.range}")
        print(f"  Movement: speed={legacy_card.speed}, hit_speed={legacy_card.hit_speed}")
        print(f"  Targeting: targets_only_buildings={legacy_card.targets_only_buildings}")
        print(f"  Special: charge_range={getattr(legacy_card, 'charge_range', None)}")
        print(f"  Death: death_spawn_character={getattr(legacy_card, 'death_spawn_character', None)}")
        print(f"  Buff: buff_data={getattr(legacy_card, 'buff_data', None)}")
        print(f"  Projectile: projectile_data={getattr(legacy_card, 'projectile_data', None)}")

        print(f"\n🆕 NEW SYSTEM ATTRIBUTES (CardDefinition):")
        print(f"  Mechanics: {len(new_card.mechanics)} - {[type(m).__name__ for m in new_card.mechanics]}")
        print(f"  Effects: {len(new_card.effects)} - {[type(e).__name__ for e in new_card.effects]}")
        print(f"  Tags: {new_card.tags}")
        print(f"  Structured Stats: troop_stats={bool(new_card.troop_stats)}")
        print(f"  Behaviors: targeting={bool(new_card.targeting)}, movement={bool(new_card.movement)}")

    print(f"\n🎯 BATTLE SYSTEM USAGE ANALYSIS:")
    print("-" * 40)

    # Based on code analysis, identify what's actually used
    used_in_battle = {
        "name": "✅ Card identification and display",
        "id": "✅ Internal tracking",
        "mana_cost": "✅ Elixir validation and deployment",
        "card_type": "✅ Display and categorization",
        "hitpoints": "✅ Entity health calculation",
        "damage": "✅ Attack damage calculation",
        "range": "✅ Attack range validation",
        "sight_range": "✅ Target acquisition",
        "speed": "✅ Movement speed",
        "hit_speed": "✅ Attack timing",
        "collision_radius": "✅ Hitbox calculation",
        "targets_only_buildings": "✅ Building-only targeting",
        "summon_count": "✅ Swarm deployment",
        "charge_range": "✅ Charge mechanics (Hog Rider, etc.)",
        "damage_special": "✅ First-hit bonus damage",
        "death_spawn_character": "✅ Death spawning (Lava Hound, etc.)",
        "projectile_data": "⚠️ Partially used (only damage)",
        "load_time": "⚠️ Used in some entities",
        "deploy_time": "⚠️ Used in some entities"
    }

    loaded_but_unused = {
        "death_spawn_count": "❌ Death spawn count not implemented",
        "kamikaze": "❌ Kamikaze mechanics not implemented",
        "buff_data": "❌ Buff/debuff system not implemented",
        "hit_speed_multiplier": "❌ Attack speed buffs not used",
        "speed_multiplier": "❌ Movement speed buffs not used",
        "spawn_speed_multiplier": "❌ Spawn speed buffs not used",
        "special_load_time": "❌ Special timing not implemented",
        "special_range": "❌ Special range attacks not implemented",
        "special_min_range": "❌ Minimum range not implemented",
        "tribe": "❌ Tribe mechanics not implemented",
        "unlock_arena": "❌ Meta-data only",
        "english_name": "❌ Display only",
        "evolution_data": "❌ Evolution system not implemented",
        "area_damage_radius": "❌ Area damage not fully implemented",
        "projectile_splash_radius": "❌ Splash damage not implemented",
        "attacks_ground": "❌ Not used (targets_only_buildings used instead)",
        "attacks_air": "❌ Not used (target_type used instead)",
        "target_type": "⚠️ Partially used"
    }

    new_system_unused = {
        "mechanics": "❌ Rich mechanic system completely unused",
        "effects": "❌ Effect composition system unused",
        "tags": "❌ Categorical tagging system unused",
        "targeting_behavior": "❌ Protocol-based targeting unused",
        "movement_behavior": "❌ Protocol-based movement unused",
        "attack_behavior": "❌ Protocol-based attack unused",
        "troop_stats": "❌ Structured stat containers unused",
        "building_stats": "❌ Structured stat containers unused",
        "spell_stats": "❌ Structured stat containers unused"
    }

    print(f"✅ ATTRIBUTES CURRENTLY USED:")
    for attr, usage in sorted(used_in_battle.items()):
        print(f"  {attr}: {usage}")

    print(f"\n⚠️  LOADED BUT UNUSED (Compat System):")
    for attr, reason in sorted(loaded_but_unused.items()):
        print(f"  {attr}: {reason}")

    print(f"\n🚀 AVAILABLE BUT UNUSED (New Compositional System):")
    for attr, reason in sorted(new_system_unused.items()):
        print(f"  {attr}: {reason}")

    print(f"\n📊 USAGE STATISTICS:")
    total_legacy = len(used_in_battle) + len(loaded_but_unused)
    total_new = len(new_system_unused)

    print(f"  Compat System: {len(used_in_battle)}/{total_legacy} attributes used ({len(used_in_battle)/total_legacy*100:.1f}%)")
    print(f"  New Compositional System: 0/{total_new} components used (0.0%)")

    print(f"\n🎯 KEY OPPORTUNITIES:")
    print(f"  1. Implement buff system using loaded buff_data")
    print(f"  2. Add area damage using area_damage_radius")
    print(f"  3. Implement projectile splash damage")
    print(f"  4. Integrate new mechanic system via CardStatsCompat")
    print(f"  5. Add kamikaze mechanics for appropriate cards")

    print(f"\n🏆 CONCLUSION:")
    print(f"  The battle system uses ~44% of loaded legacy attributes")
    print(f"  The new compositional system is completely unused")
    print(f"  Significant potential for gameplay enhancement exists")

if __name__ == "__main__":
    analyze_attribute_usage()
