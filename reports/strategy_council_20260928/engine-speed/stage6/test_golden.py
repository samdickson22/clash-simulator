"""A dash speed alone does not enable the reference's river-jump route costs."""
import hashlib
import json
from pathlib import Path
import unittest

import cloudpickle
import clasher_core
from differential import config,snapshot
import test_early


class Golden(unittest.TestCase):
    same=test_early.EarlyCards.same

    def test_dash_speed_without_jump_height_keeps_ordinary_water_costs(self):
        folder=Path(__file__).resolve().parent;path=folder/'golden-route-root1808-r14.pkl'
        pins=json.loads(path.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((folder.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,cfg,_=cloudpickle.loads(path.read_bytes());cfg=config(tuple(cfg['cards']))
        self.assertEqual(b.entities[258].card_stats.jump_speed,400)
        self.assertIsNone(b.entities[258].card_stats.jump_height)
        r=clasher_core.BattleState(snapshot(b,cfg))
        for _ in range(300):b.step();r.step();self.same(b,r)


if __name__=='__main__':unittest.main()
