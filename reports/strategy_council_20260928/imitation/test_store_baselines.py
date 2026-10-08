"""Data-path smoke checks against the real one-unit store and metric arithmetic."""
import json
import math
from pathlib import Path
import unittest
import numpy as np
from packed_store import PackedStore
from baselines import Metrics, buckets

HERE=Path(__file__).resolve().parent


class StoreTests(unittest.TestCase):
    def test_smoke_roundtrip_and_batch(self):
        root=HERE/'data/store-smoke-v2'
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertTrue(manifest['smoke_passed'])
        self.assertFalse(manifest['passed'])
        self.assertEqual(manifest['roundtrip_perspectives'],45)
        for role in ('train','dev','eval','eval_ood'):
            store=PackedStore(root,role)
            ix=np.array([0,len(store)//2,len(store)-1,0])
            batch=store.batch(ix)
            self.assertEqual(batch['action_masks'].shape,(4,2306))
            for i,row in enumerate(ix):
                count=int(store.arrays['entity_counts'][row])
                offset=int(store.arrays['entity_offsets'][row])
                np.testing.assert_array_equal(batch['entity_ids'][i,:count],store.arrays['flat_entity_ids'][offset:offset+count])
                self.assertEqual(int(batch['entity_mask'][i].sum()),count)
            valid=batch['expert_action_supervision_valid']
            self.assertTrue(batch['action_masks'][np.arange(4)[valid],batch['expert_actions'][valid]].all())

    def test_metric_factorization_and_ability(self):
        metric=Metrics()
        metric.add(np.array([2304,577,2305]),np.array([[.8,.1,.1],[.1,.6,.3],[.1,.2,.7]]),
                   np.array([[.2,.5,.2,.1]]),np.array([.25]),np.array([1]),np.array([1]),np.array([1]))
        r=metric.result()
        self.assertAlmostEqual(r['joint_nll'],(-math.log(.8)-math.log(.6*.5*.25)-math.log(.7))/3)
        self.assertAlmostEqual(r['card_nll'],-math.log(.5))
        self.assertAlmostEqual(r['tile_nll'],-math.log(.25))
        self.assertAlmostEqual(r['ability_nll'],-math.log(.7))
        self.assertEqual(r['median_tile_error'],0)

    def test_phase_boundaries(self):
        features=np.zeros((4,18));features[:,5]=[.6,.1,.9,1.]
        np.testing.assert_array_equal(buckets(np.array([2399,2400,3599,3600]),features),[6,12,20,32])

    def test_playable_timing_denominator(self):
        metric=Metrics()
        metric.add(np.array([2304,0]),np.array([[1.,0.,0.],[.5,.5,0.]]),
                   np.array([[1.,0.,0.,0.]]),np.array([1.]),np.array([0]),np.array([0]),np.array([0]),
                   np.array([False,True]))
        r=metric.result()
        self.assertEqual(r['playable_rows'],1)
        self.assertAlmostEqual(r['play_wait_nll'],math.log(2)/2)
        self.assertAlmostEqual(r['play_wait_nll_playable'],math.log(2))
        self.assertAlmostEqual(r['play_wait_brier_playable'],.25)
        self.assertEqual(sum(b['rows'] for b in r['hazard_calibration_playable']),1)


if __name__=='__main__': unittest.main()
