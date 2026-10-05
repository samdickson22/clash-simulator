"""Canonical-data regression: movement rechecks pending lethal damage."""
import unittest
from differential import config
from stage2_matches import PILOT, match, resources


class CanonicalDataParity(unittest.TestCase):
    def test_later_combat_damage_cancels_ranged_movement(self):
        # At 5369 an Archer chooses Knight 718 before later combat reduces its
        # HP 490 -> 406. Four existing arrows reserve 448 damage. Python then
        # cancels the Archer's travel in the movement phase.
        result = match(1, config(PILOT), resources(), until=5370)
        self.assertTrue(result['ok'], f"{result.get('tick')}: {result.get('field_diff')}")


if __name__ == '__main__':
    unittest.main()
