#!/usr/bin/env python3
"""
Analyze all cards from decks.json using the new compositional card system.
This script demonstrates the capabilities of the new system by loading
cards from deck configurations and displaying their attributes and mechanics.
"""

import json
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from clasher.data import CardDataLoader
from clasher.card_types import CardDefinition, CardStatsCompat
from clasher.paths import decks_path as resolve_decks_path


def print_card_analysis(card_name: str, card_def: CardDefinition, loader: CardDataLoader):
    """Print detailed analysis of a single card"""
    print(f"\n{'='*60}")
    print(f"🃏 {card_name.upper()}")
    print(f"{'='*60}")

    # Basic info
    print(f"Type: {card_def.kind}")
    print(f"Rarity: {card_def.rarity}")
    print(f"Elixir Cost: {card_def.elixir}")
    print(f"Card ID: {card_def.id}")

    # Tags
    if card_def.tags:
        print(f"Tags: {', '.join(sorted(card_def.tags))}")

    # Stats based on card type
    if card_def.troop_stats:
        stats = card_def.troop_stats
        print(f"\n📊 TROOP STATS:")
        if stats.hitpoints:
            print(f"  • Hitpoints: {stats.hitpoints}")
        if stats.damage:
            print(f"  • Damage: {stats.damage}")
        if stats.range_tiles:
            print(f"  • Range: {stats.range_tiles} tiles")
        if stats.hit_speed_ms:
            print(f"  • Hit Speed: {stats.hit_speed_ms}ms")
        if stats.speed_tiles_per_min:
            print(f"  • Speed: {stats.speed_tiles_per_min} tiles/min")
        if stats.sight_range_tiles:
            print(f"  • Sight Range: {stats.sight_range_tiles} tiles")
        if stats.collision_radius_tiles:
            print(f"  • Collision Radius: {stats.collision_radius_tiles} tiles")
        if stats.deploy_time_ms:
            print(f"  • Deploy Time: {stats.deploy_time_ms}ms")
        if stats.load_time_ms:
            print(f"  • Load Time: {stats.load_time_ms}ms")
        if stats.summon_count:
            print(f"  • Summon Count: {stats.summon_count}")

    elif card_def.building_stats:
        stats = card_def.building_stats
        print(f"\n🏗️  BUILDING STATS:")
        if stats.hitpoints:
            print(f"  • Hitpoints: {stats.hitpoints}")
        if stats.damage:
            print(f"  • Damage: {stats.damage}")
        if stats.range_tiles:
            print(f"  • Range: {stats.range_tiles} tiles")
        if stats.hit_speed_ms:
            print(f"  • Hit Speed: {stats.hit_speed_ms}ms")
        if stats.sight_range_tiles:
            print(f"  • Sight Range: {stats.sight_range_tiles} tiles")
        if stats.collision_radius_tiles:
            print(f"  • Collision Radius: {stats.collision_radius_tiles} tiles")
        if stats.deploy_time_ms:
            print(f"  • Deploy Time: {stats.deploy_time_ms}ms")
        if stats.lifetime_ms:
            print(f"  • Lifetime: {stats.lifetime_ms / 1000:.1f}s")

    elif card_def.spell_stats:
        stats = card_def.spell_stats
        print(f"\n✨ SPELL STATS:")
        if stats.radius_tiles:
            print(f"  • Radius: {stats.radius_tiles} tiles")
        if stats.duration_ms:
            print(f"  • Duration: {stats.duration_ms / 1000:.1f}s")
        if stats.crown_tower_damage_scale:
            print(f"  • Crown Tower Damage Scale: {stats.crown_tower_damage_scale}x")

    # Mechanics
    if card_def.mechanics:
        print(f"\n🔧 MECHANICS:")
        for i, mechanic in enumerate(card_def.mechanics, 1):
            mech_name = type(mechanic).__name__
            print(f"  {i}. {mech_name}")

            # Add specific details for known mechanics
            if mech_name == "HogRiderJump":
                print(f"     → Can jump over rivers and obstacles")
            elif mech_name == "Shield":
                print(f"     → Has protective shield that absorbs damage")
            elif mech_name == "DamageRamp":
                print(f"     → Damage increases over time on same target")
            elif mech_name == "SkeletonKingSoulCollector":
                print(f"     → Collects souls, can summon skeleton army")
            elif mech_name == "MinerTunnel":
                print(f"     → Can tunnel and appear anywhere on the map")
            elif mech_name == "KnockbackOnHit":
                print(f"     → Knocks enemies back on attack")
            elif mech_name == "FishermanHook":
                print(f"     → Can pull enemies with hook ability")

    # Effects
    if card_def.effects:
        print(f"\n💫 EFFECTS:")
        for i, effect in enumerate(card_def.effects, 1):
            effect_name = type(effect).__name__
            print(f"  {i}. {effect_name}")

            # Add specific details for known effects
            if effect_name == "DirectDamage":
                print(f"     → Deals direct damage to targets")
            elif effect_name == "ProjectileLaunch":
                print(f"     → Launches projectile with splash damage")
            elif effect_name == "PeriodicArea":
                print(f"     → Creates area effect over time")
            elif effect_name == "SpawnUnits":
                print(f"     → Spawns units at target location")
            elif effect_name == "ApplyStun":
                print(f"     → Stuns affected enemies")
            elif effect_name == "ApplySlow":
                print(f"     → Slows affected enemies")
            elif effect_name == "ApplyBuff":
                print(f"     → Applies buff to friendly units")

    # Targeting behavior
    if card_def.targeting:
        targeting = card_def.targeting
        print(f"\n🎯 TARGETING:")
        print(f"  • Can attack ground: {targeting.can_target_ground()}")
        print(f"  • Can attack air: {targeting.can_target_air()}")
        print(f"  • Targets only buildings: {targeting.buildings_only()}")

    # Legacy compatibility info
    compat = CardStatsCompat.from_card_definition(card_def)
    print(f"\n🔄 LEGACY COMPATIBILITY:")
    print(f"  • Card Type: {compat.card_type}")
    print(f"  • Mana Cost: {compat.mana_cost}")
    if compat.hitpoints:
        print(f"  • HP: {compat.hitpoints}")
    if compat.damage:
        print(f"  • Damage: {compat.damage}")


def analyze_decks():
    """Main function to analyze all cards from decks.json"""
    print("🚀 ANALYZING CARDS FROM DECKS.JSON")
    print("=" * 80)

    # Load decks
    try:
        decks_file = resolve_decks_path("decks.json", must_exist=True)
    except FileNotFoundError:
        print("❌ Error: decks.json not found")
        return

    with open(decks_file, 'r') as f:
        decks_data = json.load(f)

    # Initialize card loader
    loader = CardDataLoader()
    card_definitions = loader.load_card_definitions()

    # Collect all unique cards from all decks
    all_cards = set()
    for deck in decks_data.get("decks", []):
        all_cards.update(deck.get("cards", []))

    # Sort cards alphabetically
    sorted_cards = sorted(all_cards)

    print(f"📦 Found {len(sorted_cards)} unique cards across {len(decks_data.get('decks', []))} decks")
    print()

    # Comprehensive alias map from random_battle.py
    alias = {
        "The Log": "Log",
        "Log": "Log",
        "Hog Rider": "HogRider",
        "Hog": "HogRider",
        "X-Bow": "Xbow",
        "Mini P.E.K.K.A": "MiniPekka",
        "Mini P.E.K.K.A.": "MiniPekka",
        "Mini Pekka": "MiniPekka",
        "P.E.K.K.A": "Pekka",
        "P.E.K.K.A.": "Pekka",
        "Royal Delivery": "RoyalDelivery",
        "Royal Ghost": "RoyalGhost",
        "Skeleton Barrel": "SkeletonBarrel",
        "Giant Snowball": "GiantSnowball",
        "Wall Breakers": "Wallbreakers",
        "Electro Wizard": "ElectroWizard",
        "Ice Wizard": "IceWizard",
        "Dart Goblin": "DartGoblin",
        "Magic Archer": "MagicArcher",
        "Mega Knight": "MegaKnight",
        "Inferno Dragon": "InfernoDragon",
        "Electro Dragon": "ElectroDragon",
        "Archer Queen": "ArcherQueen",
        "Barbarian Barrel": "BarbarianBarrel",
        "Bomb Tower": "BombTower",
        "Ice Golem": "IceGolem",
        "Ice Spirit": "IceSpirit",
        "Electro Spirit": "ElectroSpirit",
        "Royal Hogs": "RoyalHogs",
        "Cannon Cart": "CannonCart",
        "Skeleton King": "SkeletonKing",
        "Tomb Stone": "Tombstone",
        # Canonical mappings to your dataset internal IDs
        "Archers": "Archer",
        "Ice Spirit": "IceSpirits",
        "IceSpirit": "IceSpirits",
        "Fire Spirit": "FireSpirits",
        "FireSpirit": "FireSpirits",
        "Ice Golem": "IceGolemite",
        "IceGolem": "IceGolemite",
        "Dart Goblin": "BlowdartGoblin",
        "DartGoblin": "BlowdartGoblin",
        "Giant Snowball": "Snowball",
        "GiantSnowball": "Snowball",
        "Barbarian Barrel": "BarbLog",
        "BarbarianBarrel": "BarbLog",
        "Skeleton Barrel": "SkeletonBalloon",
        "SkeletonBarrel": "SkeletonBalloon",
        "Royal Ghost": "Ghost",
        "RoyalGhost": "Ghost",
        # Proxy mappings
        "Bandit": "Assassin",
        "Lumberjack": "AxeMan",
        "MagicArcher": "EliteArcher",
        "Guards": "SkeletonWarriors"
    }

    # Analyze each card
    found_cards = []
    missing_cards = []

    for card_name in sorted_cards:
        # Apply alias mapping
        mapped_name = alias.get(card_name, card_name)

        # Try variations including the mapped name
        variations = [mapped_name, card_name, card_name.replace(" ", ""), card_name.replace(" ", "")]
        found = False

        for variation in variations:
            if variation in card_definitions:
                actual_name_used = variation
                print_card_analysis(actual_name_used, card_definitions[variation], loader)
                found_cards.append((card_name, actual_name_used))  # Store both original and mapped
                found = True
                break

        if not found:
            missing_cards.append(card_name)
            print(f"\n❌ CARD NOT FOUND: {card_name}")
            print(f"   → Mapped to: {mapped_name}")
            print(f"   → Not available in gamedata.json with any variation")

    # Summary
    print(f"\n{'='*80}")
    print("📊 ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successfully analyzed: {len(found_cards)} cards")
    print(f"❌ Missing from gamedata: {len(missing_cards)} cards")

    if missing_cards:
        print(f"\nMissing cards: {', '.join(missing_cards)}")

    # Show some interesting statistics
    total_mechanics = 0
    total_effects = 0
    for original_name, actual_name in found_cards:
        if actual_name in card_definitions:
            total_mechanics += len(card_definitions[actual_name].mechanics)
            total_effects += len(card_definitions[actual_name].effects)

    print(f"\n🎮 SYSTEM STATISTICS:")
    print(f"  • Total mechanics detected: {total_mechanics}")
    print(f"  • Total effects composed: {total_effects}")
    print(f"  • Average mechanics per card: {total_mechanics / len(found_cards):.2f}")
    print(f"  • Average effects per card: {total_effects / len(found_cards):.2f}")

    # Show alias mappings used
    print(f"\n🔄 ALIAS MAPPINGS USED:")
    aliases_used = []
    for original_name, actual_name in found_cards:
        if original_name != actual_name:
            aliases_used.append(f"{original_name} → {actual_name}")

    if aliases_used:
        for alias_mapping in aliases_used:
            print(f"  • {alias_mapping}")
    else:
        print(f"  • No alias mappings needed")

    print(f"\n🏆 ANALYSIS COMPLETE!")


if __name__ == "__main__":
    analyze_decks()
