"""Exercise the driver's actual world setup before starting any game."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import evaluate

class SetupCaptured(Exception): pass

class PairingTests(unittest.TestCase):
    def decks(self, mode, seat):
        captured=[]
        def battle(ep, loader):
            captured.append(ep['decks'])
            raise SetupCaptured
        ep=dict(seed=1, mode=mode, planning_deck=['A'],opponent_deck=['B'])
        resources=SimpleNamespace(builder=SimpleNamespace(loader=None))
        with patch.object(evaluate,'battle',battle), self.assertRaises(SetupCaptured):
            evaluate.game(resources,None,ep,seat)
        return captured[0]

    def test_head_to_head_keeps_world_decks_fixed_while_controller_seat_swaps(self):
        self.assertEqual(self.decks('head-to-head',0),[['A'],['B']])
        self.assertEqual(self.decks('head-to-head',1),[['A'],['B']])

    def test_continuity_retains_stage5_role_deck_pairing(self):
        self.assertEqual(self.decks('scripts',0),[['A'],['B']])
        self.assertEqual(self.decks('scripts',1),[['B'],['A']])

if __name__=='__main__':unittest.main()
