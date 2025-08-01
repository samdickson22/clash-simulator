import json
from collections import defaultdict
from typing import Dict, Any, Set


def extract_all_keys(data: Dict[str, Any], prefix: str = "") -> Set[str]:
    """Recursively extract all keys from a nested dictionary"""
    keys = set()
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)
            if isinstance(value, (dict, list)):
                keys.update(extract_all_keys(value, full_key))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            full_key = f"{prefix}[{i}]"
            keys.add(full_key)
            if isinstance(item, (dict, list)):
                keys.update(extract_all_keys(item, full_key))
    
    return keys


def main():
    """Extract all keys from spells in gamedata.json"""
    try:
        # Load the gamedata.json file
        with open("gamedata.json", "r") as f:
            gamedata = json.load(f)
        
        # Navigate to spells section
        spells = gamedata.get("items", {}).get("spells", [])
        
        if not spells:
            print("No spells found in gamedata.json")
            return
        
        print(f"Found {len(spells)} spells. Extracting all keys...")
        
        # Collect all unique keys from all spells
        all_keys = set()
        for spell in spells:
            spell_keys = extract_all_keys(spell)
            all_keys.update(spell_keys)
        
        # Sort and print all keys
        sorted_keys = sorted(all_keys)
        
        print("\\n=== ALL KEYS FOUND IN SPELLS ===")
        for key in sorted_keys:
            print(key)
        
        print(f"\\nTotal unique keys: {len(sorted_keys)}")
        
        # Also print a summary of top-level keys
        top_level_keys = set()
        for spell in spells:
            top_level_keys.update(spell.keys())
        
        print("\\n=== TOP-LEVEL KEYS ===")
        for key in sorted(top_level_keys):
            print(key)
            
    except FileNotFoundError:
        print("gamedata.json file not found")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
