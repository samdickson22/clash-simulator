"""Preserve Python's membership-keyed mask after a building changes position."""
import hashlib
import json
from pathlib import Path
import unittest

import cloudpickle
import clasher_core
from differential import Position,config,snapshot
import test_early


class PlacementCache(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_moved_drill_keeps_cached_mask_until_membership_changes(self):
        folder=Path(__file__).resolve().parent;path=folder/'repaired-r12-root5040.pkl'
        pins=json.loads(path.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((folder.parents[3]/name).read_bytes()).hexdigest(),expected)
        for clear in (False,True):
            with self.subTest(clear=clear):
                b,cfg,_=cloudpickle.loads(path.read_bytes());cfg=config(tuple(cfg['cards']))
                if clear:b._building_placement_blocked_masks.clear()
                r=clasher_core.BattleState(snapshot(b,cfg))
                new=b.next_entity_id
                self.assertTrue(b.deploy_card(0,'Musketeer',Position(13.5,13.5)))
                self.assertTrue(r.apply_action(0,'Musketeer',13.5,13.5))
                self.same(b,r)
                self.assertEqual(b.entities[new].position.y,14.5 if clear else 13.5)
                self.continuation(b,cfg,160)


if __name__=='__main__':unittest.main()
