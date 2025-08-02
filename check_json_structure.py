#!/usr/bin/env python3
"""
Check gamedata.json structure
"""

import json

def main():
    """Check JSON structure"""
    with open('gamedata.json', 'r') as f:
        data = json.load(f)
    
    print("Top level keys:", list(data.keys()))
    if 'items' in data:
        print("Items keys:", list(data['items'].keys()))
    
    # Check if there are characters or other sections
    for key in data.keys():
        if key != 'items':
            print(f"Other section '{key}':", type(data[key]))

if __name__ == "__main__":
    main()
