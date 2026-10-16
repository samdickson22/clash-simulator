"""Deadline admission, cancellation, complete-set ordering and fallback."""
import time
import unittest
from unittest.mock import Mock
from c56_controller import CARDS, resources
from differential import config, initial
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, C56SearchConfig

class DeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder, _, cls.native, cls.bots = resources()
        cls.cfg = config(CARDS)

    def planner(self, **kwargs):
        return C56RolloutPlanner(self.builder, self.bots, backend='native',
            native=self.native, native_config=self.cfg, config=C56SearchConfig(**kwargs))

    def test_expired_returns_legal_script_fallback(self):
        p = self.planner(deadline_seconds=0, threads=2)
        b = initial(); packet = self.builder.build_public(b, 0)
        candidates, mask = p.candidates(packet)
        self.assertTrue(mask[candidates[0]])
        self.assertEqual(candidates[0], self.bots['balanced'].decide(packet).action_id)
        got = p.score_candidates(p.import_root(b), 0, candidates, deadline=time.perf_counter()-1)
        self.assertEqual(got, candidates[0])
        self.assertEqual(p.deadline_stats['completed'], 0)
        self.assertTrue(p.deadline_stats['fallback'])

    def test_inside_long_rollout_cancelled(self):
        p = self.planner(horizon=10000000, deadline_seconds=.01, threads=2)
        root = p.import_root(initial())
        start = time.perf_counter()
        p.score_candidates(root, 0, [2304, 0])
        self.assertLess(time.perf_counter()-start, .25)
        self.assertTrue(p.deadline_stats['truncated'])
        self.assertTrue(p.deadline_stats['fallback'])

    def test_partial_candidate_ignored_and_priority_ties(self):
        p = self.planner(threads=2)
        result = lambda score: (score, 0, 0, 0, [], '')
        p.native = Mock()
        p.native.search_candidates.return_value = [None, [result(1.)]*3, [result(1.)]*3]
        self.assertEqual(p.score_candidates(None, 0, [12, 23, 34]), 23)
        self.assertEqual(p.deadline_stats['completed'], 2)
        self.assertTrue(p.deadline_stats['truncated'])

    def test_complete_order_and_threads(self):
        b = initial()
        results = []
        for threads in (1,2,4):
            p = self.planner(horizon=20, deadline_seconds=30, threads=threads)
            a = p.score_candidates(p.import_root(b), 0, [2304, 0, 100], trace=True)
            self.assertFalse(p.deadline_stats['truncated'])
            results.append((a, p.last))
        self.assertEqual(results[0], results[1]); self.assertEqual(results[1], results[2])

    def test_config_rejects_bad_deadlines(self):
        for kwargs in ({'deadline_seconds': -1}, {'deadline_seconds': float('nan')}, {'threads':0}):
            with self.assertRaises(ValueError): C56SearchConfig(**kwargs)

if __name__ == '__main__': unittest.main()
