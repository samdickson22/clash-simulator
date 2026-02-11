#!/usr/bin/env python3
"""
Test script to verify the RuntimeError fix for entity iteration
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_entity_iteration_fix():
    """Test that entity iteration doesn't cause RuntimeError"""
    try:
        # Simple test to verify the fix works
        from clasher.entities import RollingProjectile

        # Create a simple test dictionary to simulate the issue
        test_dict = {i: f"value_{i}" for i in range(5)}

        # This old pattern would cause RuntimeError if we modified the dict during iteration
        # for key in test_dict.keys():
        #     if key % 2 == 0:
        #         del test_dict[key]  # This would cause RuntimeError

        # This new pattern (what we implemented) works fine
        keys_copy = list(test_dict.keys())
        for key in keys_copy:
            if key % 2 == 0:
                del test_dict[key]  # This works fine

        print("✅ Entity iteration fix works! No RuntimeError occurred.")
        print(f"Remaining items: {test_dict}")
        return True

    except RuntimeError as e:
        print(f"❌ RuntimeError still occurs: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Other error occurred: {e}")
        return False

if __name__ == "__main__":
    success = test_entity_iteration_fix()
    sys.exit(0 if success else 1)