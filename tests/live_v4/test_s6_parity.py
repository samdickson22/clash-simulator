"""Real native scorer parity on recorded train-only pixel/belief inputs."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import time
import unittest

from clasher.live.contracts import Snapshot
from clasher.live.decision import RustPlanner, DecisionInfo
from clasher.live.loading import delay_module
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, C56SearchConfig
from clasher.rl.live_inference_contract import parse_public_vision_frame, LIVE_VISION_SCHEMA_VERSION

FIXTURE = Path(__file__).parent/'fixtures/s6-train-inputs.json'


def snapshot(row):
    public = copy.deepcopy(row['public'])
    outer = {key: public.pop(key) for key in ('episode_id', 'frame_id', 'timestamp_ms')}
    public = parse_public_vision_frame(dict(outer, schema_version=LIVE_VISION_SCHEMA_VERSION, public=public))
    return Snapshot(public.episode_id, row['sequence'], 0., 0., 0., row['tick'], public,
                    copy.deepcopy(row['own']), tuple(row['roots']), row['opponent'],
                    row['revision'], row['pending'], 0, 0)


def nonterminal_variant(row):
    """Explicit synthetic tower variant; hand and opponent roots stay recorded."""
    from clasher.rl.live_inference_contract import VisionEntity
    s = snapshot(row)
    towers = tuple(VisionEntity(f'fixture-{seat}-{i}', card, 'building', seat, x, y,
                               1., 1., 1.)
                   for seat in (0, 1) for i, (card, x, y) in enumerate(
                       [('KingTower', 9., 3. if seat == 0 else 29.),
                        ('Tower', 3., 7. if seat == 0 else 25.),
                        ('Tower', 15., 7. if seat == 0 else 25.)]))
    return replace(s, public=replace(s.public, entities=towers))


class S6RecordedParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(1)
        cls.planner = RustPlanner({'seed': 6108})
        cls.constructed_delays = (cls.planner.delay_ticks,
                                  [core.command_delay for core in cls.planner.cores])
        cls.fixture = json.loads(FIXTURE.read_text())
        if cls.fixture['split'] != 'train':
            raise ValueError('Recorded parity fixture must be train-only')

    @classmethod
    def tearDownClass(cls):
        cls.planner.close()

    def test_constructor_uses_total_delay_for_all_four_roots(self):
        from clasher.live.timing import planner_timing
        delay = planner_timing({})[3]
        self.assertEqual(self.constructed_delays, (delay, [delay]*4))

    def reset(self, delay=None, aware=True):
        import numpy as np
        p = self.planner
        p.rng = np.random.default_rng(6108)
        p.packets = type(p.packets)(p.resources.builder)
        p.delay_aware = aware
        if delay is not None:
            p.delay_ticks = delay
        for i, core in enumerate(p.cores):
            core.rng = np.random.default_rng(6108+i)
            core.command_delay, core.delay_aware = p.delay_ticks, aware
        return p

    def reference(self, s, delay, aware=True):
        """Direct unmodified S6 full-list scoring, independent of runtime adapter."""
        import numpy as np
        p = self.planner
        r = p.resources
        packets = type(p.packets)(r.builder)
        packet, _ = packets.build(s.public, s.tick)
        info = DecisionInfo(s.tick, 1, p.model_hypothesis(packet),
                            {k: s.own[k] for k in ('hand', 'cycle', 'refill', 'elixir')})
        cls = delay_module().DelayAwarePlanner if aware else C56RolloutPlanner
        extra = dict(command_delay=delay, delay_aware=True) if aware else {}
        core = cls(r.builder, r.bots, backend='native', native=r.native, native_config=r.config,
                   config=C56SearchConfig(horizon=160, interval=10, threads=1), seed=6108, **extra)
        core.info, core.costs = info, r.costs
        candidates, _ = core.candidates(info.packet)
        rng = np.random.default_rng(6108)
        values = np.zeros(len(candidates))
        for hypothesis in s.roots:
            root = r.root(info, hypothesis, rng)
            core.score_candidates(root, info.seat, candidates)
            values += np.array(core.last['scores'])/4
        best = 0
        for i in range(1, len(candidates)):
            if values[i] > values[best]+1e-9:
                best = i
        return candidates[best], candidates, values.tolist()

    def test_runtime_equals_s6_on_recorded_inputs(self):
        import numpy as np
        from clasher.live.timing import planner_timing
        delay = planner_timing({})[3]
        results = []
        for row in self.fixture['inputs']:
            with self.subTest(frame=row['sequence']):
                s = snapshot(row)
                p = self.reset(delay)
                before = copy.deepcopy(s.own)
                expected, candidates, scores = self.reference(s, delay)
                action, diagnostic = p.decide(s, time.monotonic()+30.)
                self.assertGreater(len(candidates), 1)
                self.assertEqual(diagnostic['completed'], len(candidates))
                self.assertEqual(diagnostic['candidate_ids'], candidates)
                np.testing.assert_allclose(diagnostic['scores'], scores, rtol=0, atol=1e-10)
                self.assertEqual(action, expected)
                self.assertEqual(s.own, before)
                results.append(dict(sequence=s.sequence, action=action, candidates=len(candidates),
                                    command_delay_ticks=delay, search_ms=diagnostic['search_ms']))
        print('S6_RECORDED_PARITY '+json.dumps(results), flush=True)

    def test_zero_delay_equals_original_on_recorded_input(self):
        import numpy as np
        s = snapshot(self.fixture['inputs'][0])
        expected, candidates, scores = self.reference(s, 0, aware=False)
        outputs = []
        for aware in (True, False):
            p = self.reset(0, aware)
            action, diagnostic = p.decide(s, time.monotonic()+30.)
            self.assertEqual(action, expected)
            self.assertEqual(diagnostic['completed'], len(candidates))
            np.testing.assert_allclose(diagnostic['scores'], scores, rtol=0, atol=1e-9)
            outputs.append(diagnostic['scores'])
        self.assertEqual(*outputs)

    def test_nonterminal_variant_matches_s6_and_changes_delay_scores(self):
        import numpy as np
        from clasher.live.timing import planner_timing
        s = nonterminal_variant(self.fixture['inputs'][-1])
        delay = planner_timing({})[3]
        expected, candidates, scores = self.reference(s, delay)
        _, immediate_candidates, immediate_scores = self.reference(s, 0)
        self.assertEqual(candidates, immediate_candidates)
        self.assertGreater(max(scores)-min(scores), 1e-6)
        self.assertFalse(np.allclose(scores, immediate_scores))
        p = self.reset(delay)
        action, diagnostic = p.decide(s, time.monotonic()+30.)
        self.assertEqual(action, expected)
        self.assertEqual(diagnostic['completed'], len(candidates))
        np.testing.assert_allclose(diagnostic['scores'], scores, rtol=0, atol=1e-10)
        print('S6_NONTERMINAL_PARITY '+json.dumps(dict(action=action,
              candidates=len(candidates), score_range=[min(scores), max(scores)],
              search_ms=diagnostic['search_ms'])), flush=True)

    def test_deadline_selects_only_complete_s6_candidates(self):
        from clasher.live.timing import planner_timing
        s = nonterminal_variant(self.fixture['inputs'][-1])
        delay = planner_timing({})[3]
        _, candidates, scores = self.reference(s, delay)
        p = self.reset(delay)
        start = time.monotonic()
        action, diagnostic = p.decide(s, start+.2)
        elapsed = time.monotonic()-start
        n = diagnostic['completed']
        if n:
            best = 0
            for i in range(1, n):
                if scores[i] > scores[best]+1e-9:
                    best = i
            self.assertEqual(action, candidates[best])
        else:
            self.assertEqual(action, 2304)
        self.assertLess(elapsed, .23)  # Includes OS scheduling and result collection.
        print('S6_DEADLINE '+json.dumps(dict(ms=elapsed*1000, completed=n,
              candidates=len(candidates), deadline_overrun=diagnostic['deadline_overrun'])), flush=True)


if __name__ == '__main__':
    unittest.main()
