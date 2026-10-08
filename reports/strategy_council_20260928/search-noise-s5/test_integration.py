import bootstrap
import hashlib,json,unittest
from bootstrap import HERE
from cells import CELLS
from tracker_v3 import TrackerV3
from trace import snapshot
from test_tracker_v3 import PRIOR,COSTS
class Tests(unittest.TestCase):
 def test_frozen_inference(self):
  for n,h in json.loads((HERE/'frozen-s4-inputs.json').read_text()).items():self.assertEqual(hashlib.sha256((HERE/n).read_bytes()).hexdigest(),h,n)
 def test_cells(self):
  self.assertEqual(list(CELLS),['T3-N97','ELT-N97','Full-N97','R-derived','T3-N90','Full-N90'])
  for c in CELLS.values():self.assertEqual((c['arm'],c['latency'],c['failure']),('B','target',0.))
  radii=json.loads((HERE/'calibration.json').read_text())
  self.assertAlmostEqual(radii['T2-N97'],.0682);self.assertAlmostEqual(radii['T2-N90'],.1104)
 def test_snapshot_has_no_sampling_side_effects(self):
  import numpy as np
  a=TrackerV3(PRIOR,COSTS,recall=.97,precision=.97);a.advance(100)
  before=a.sample(np.random.default_rng(52))
  d=snapshot(a,100,7.78,[None]*4)
  self.assertFalse(d['hand_concentrated']);self.assertEqual(before,a.sample(np.random.default_rng(52)))
if __name__=='__main__':unittest.main()
