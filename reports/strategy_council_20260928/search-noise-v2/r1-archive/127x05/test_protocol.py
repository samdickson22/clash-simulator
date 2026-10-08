import bootstrap
from bootstrap import HERE
import json,unittest
from collections import Counter
from worker import jobs
from analyze import ci

class ProtocolTests(unittest.TestCase):
    def test_schedule_pairs_and_partition_cover(self):
        rows=jobs(json.loads((HERE/'schedule.json').read_text()))
        self.assertEqual(len(rows),4992)
        counts=Counter((ep['mode'],cell) for ep,cell,seat in rows)
        self.assertEqual(set(v for (mode,cell),v in counts.items() if mode=='scripts'),{256})
        self.assertEqual(set(v for (mode,cell),v in counts.items() if mode=='head-to-head'),{128})
        pairs=Counter((ep['pair'],cell) for ep,cell,seat in rows)
        self.assertEqual(set(pairs.values()),{2})
        assigned=[i for w in range(248) for i in range(len(rows)) if i%248==w]
        self.assertEqual(sorted(assigned),list(range(4992)))
    def test_bootstrap_cluster_constant_and_sign(self):
        self.assertEqual(ci([.5]*128),[.5,.5,.5])
        values=[-.5,0,.5,1]*32
        self.assertAlmostEqual(ci(values)[0],.25)
        a=ci(values);b=ci([-x for x in values])
        self.assertEqual(a[0],-b[0]);self.assertAlmostEqual(a[1],-b[2]);self.assertAlmostEqual(a[2],-b[1])

if __name__=='__main__':unittest.main()
