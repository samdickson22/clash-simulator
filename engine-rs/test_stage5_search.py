"""Native search regression discovered by the prospective C56 root gate."""
import cloudpickle
import unittest
from pathlib import Path
from c56_controller import CARDS,resources
from differential import config
from clasher.rl.c56_rollout_planner import C56RolloutPlanner

FIXTURE=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/engine-speed/stage5/failure19.pkl'

class SearchRegression(unittest.TestCase):
    def test_stunned_push_services_route_before_thaw(self):
        b,seat=cloudpickle.loads(FIXTURE.read_bytes())
        builder,_,scripts,bots=resources();cfg=config(CARDS)
        p=C56RolloutPlanner(builder,bots)
        n=C56RolloutPlanner(builder,bots,backend='native',native=scripts,native_config=cfg)
        pa=p.score_candidates(b,seat,[714],trace=True)
        na=n.score_candidates(n.import_root(b),seat,[714],trace=True)
        self.assertEqual((pa,p.last),(na,n.last))

if __name__=='__main__':unittest.main()
