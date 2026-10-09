import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'scripts'))
from receipt_logic import (canonical, complete_reduction, perception_gate, quantiles,
    sha, summarize_decisions, verify_pins, without_availability, write_new)
import measure_mac


def row(packet, mode='deadline', w=False, threads=1, ms=100):
    return dict(packet_id=packet, mode=mode, wait_screen8=w, threads=threads,
        decision_ms=ms, frame_to_mock_ms=ms+30, searched=True, nonterminal=True,
        admission_valid=True, completed=2, candidates=2,
        candidate_ids=[12, 2304], scores=[1., 0.], action=12,
        root_scores=[[1., 0.]]*4, exact_full_budget=mode == 'exact')


def matrix():
    return [row('frame', mode, w, t) for mode in ('exact', 'deadline')
            for w in (False, True) for t in (1, 4)]


class ReceiptTests(unittest.TestCase):
    def test_quantile_interpolation_and_empty(self):
        self.assertEqual(quantiles([0, 100])['p95'], 95)
        self.assertIsNone(quantiles([])['p95'])

    def test_nonfinite_negative_and_bool_rejected(self):
        for value in (float('nan'), float('inf'), -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                quantiles([value])

    def test_partial_root_never_admitted(self):
        action, scores = complete_reduction([7, 8, 2304],
            [[100, 2, 0], [100, 2, 0], [None, 2, 0], [100, 2, 0]])
        self.assertEqual((action, scores), (8, [2, 0]))

    def test_no_complete_root_is_wait(self):
        self.assertEqual(complete_reduction([7], [[None], [1], [1], [1]]), (2304, []))

    def test_epsilon_tie_preserves_candidate_order(self):
        self.assertEqual(complete_reduction([7, 8], [[1, 1+5e-10]]*4)[0], 7)
        self.assertEqual(complete_reduction([7, 8], [[1, 1+2e-9]]*4)[0], 8)

    def test_wrong_root_count_or_shape_rejected(self):
        for scores in ([[1]]*3, [[1], [1], [1], []]):
            with self.assertRaises(ValueError):
                complete_reduction([7], scores)

    def test_nonfinite_score_rejected(self):
        with self.assertRaises(ValueError):
            complete_reduction([7], [[float('nan')]]*4)

    def test_exactness_requires_full_completion(self):
        rows = matrix()
        rows[0]['completed'] = 1
        result = summarize_decisions(rows, minimum=1)
        self.assertFalse(result['exact_pairs'][0]['equal'])
        self.assertEqual(result['exactness_gate'], 'FAIL')

    def test_exactness_detects_score_action_and_candidate_drift(self):
        for key, value in [('action', 2304), ('scores', [2, 0]), ('candidate_ids', [13, 2304])]:
            rows = matrix()
            rows[0][key] = value
            self.assertFalse(summarize_decisions(rows, minimum=1)['exact_pairs'][0]['equal'])

    def test_w_screened_candidates_are_not_deadline_truncations(self):
        rows = [row('frame', 'exact', True, t) for t in (1, 4)]
        for r in rows:
            r.update(candidates=3, candidate_ids=[12, 13, 2304], root_scores=[[1., None, 0.]]*4)
        self.assertTrue(summarize_decisions(rows)['exact_pairs'][0]['equal'])
        rows[0]['root_scores'] = [[1., 5., 0.]]*4
        self.assertFalse(summarize_decisions(rows)['exact_pairs'][0]['equal'])

    def test_finite_native_no_deadline_w_route(self):
        from types import SimpleNamespace
        class FakePlanner:
            def __init__(self, config):
                from concurrent.futures import ThreadPoolExecutor
                self.pool = ThreadPoolExecutor(max_workers=4)
                self.wait_screen8 = True
                self.resources = SimpleNamespace(costs={})
                def score_candidates(*a, deadline):
                    self.asserted_deadline = deadline
                    self.cores[0].last = {'scores': [1., None]}
                self.cores = [SimpleNamespace(score_candidates=score_candidates)] + [object()]*3
            def score(self, *args):
                raise AssertionError('Infinite budget must not reach the W native path')
        fake = ModuleType('clasher.live.decision')
        fake.RustPlanner = FakePlanner
        with patch.dict(sys.modules, {'clasher.live.decision': fake}):
            planner, _ = measure_mac.new_planner({'planner': {}, 'root_threads': 1}, SimpleNamespace(native_dir=Path('/unused')))
            try:
                planner.measurement_no_deadline = True
                info = SimpleNamespace(seat=1, packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*6)))
                values = planner.score(planner.cores[0], None, info, [12, 2304], float('inf'))
                self.assertIsNone(planner.asserted_deadline)
                self.assertEqual(values, [1., None])
            finally:
                planner.pool.shutdown()

    def test_at_least_64_exact_thread_pairs_and_all_four_cells(self):
        rows = [row(str(i), 'exact', w, t) for i in range(32) for w in (False, True) for t in (1, 4)]
        rows += [row(str(i), 'deadline', w, t) for i in range(1000) for w in (False, True) for t in (1, 4)]
        result = summarize_decisions(rows)
        self.assertEqual(result['package_decision_gate'], 'PASS')
        self.assertEqual(result['matrix_paired'], 1000)
        self.assertEqual(len(result['exact_pairs']), 64)

    def test_slow_real_search_fails_even_if_noop_samples_fast(self):
        rows = matrix()
        for r in rows:
            if r['mode'] == 'deadline':
                r['decision_ms'] = 201
        result = summarize_decisions(rows, minimum=1)
        self.assertTrue(all(v['decision_gate'] == 'FAIL' for v in result['cells'].values()))

    def test_terminal_and_skipped_searches_cannot_make_gate_pass(self):
        rows = matrix()
        for r in rows:
            r['nonterminal'] = False
        self.assertEqual(summarize_decisions(rows, minimum=1)['cells']['w0-t1']['decision_gate'], 'FAIL')
        for r in rows:
            r.update(nonterminal=True, searched=False)
        self.assertEqual(summarize_decisions(rows, minimum=1)['matrix_paired'], 0)

    def test_invalid_admission_fails_gate(self):
        rows = matrix()
        rows[-1]['admission_valid'] = False
        self.assertEqual(summarize_decisions(rows, minimum=1)['cells']['w1-t4']['decision_gate'], 'FAIL')

    def test_duplicate_and_missing_pairs_rejected_or_failed(self):
        rows = matrix()
        with self.assertRaises(ValueError):
            summarize_decisions(rows + [copy.deepcopy(rows[0])])
        result = summarize_decisions(rows[:-1], minimum=1)
        self.assertFalse(result['matrix_identical'])
        self.assertEqual(result['package_decision_gate'], 'FAIL')

    def test_only_availability_clocks_excluded(self):
        value = {'timestamp_ms': 7, 'nested': [{'available_timestamp_ms': 10, 'execution_timestamp_ms': 3}]}
        self.assertEqual(without_availability(value), {'timestamp_ms': 7, 'nested': [{'execution_timestamp_ms': 3}]})

    def test_numpy_receipt_values_keep_numeric_types(self):
        class NumericScalar:
            __module__ = 'numpy'
            def tolist(self):
                return True
        self.assertIs(json.loads(canonical({'known': NumericScalar()}))['known'], True)
        with self.assertRaises(TypeError):
            canonical({'opaque': object()})

    def test_perception_cold_retained_but_warm_gate_separate(self):
        rows = [dict(arm=arm, cold=cold, perception_ms=1000 if cold else 40, tower_ms=2)
                for arm in ('scalar', 'vectorized') for cold in (True, False)]
        result = perception_gate(rows, minimum=1)
        self.assertEqual(result['scalar']['budget_status'], 'PASS')
        self.assertEqual(result['scalar']['cold_ms']['p95'], 1000)
        rows[-1]['perception_ms'] = 40.01
        self.assertEqual(perception_gate(rows, minimum=1)['vectorized']['budget_status'], 'FAIL')

    def test_missing_perception_samples_fail(self):
        self.assertEqual(perception_gate([])['scalar']['budget_status'], 'FAIL')

    def test_hash_tamper_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'x').write_text('original')
            pins = {'x': sha(root/'x')}
            verify_pins(root, pins)
            (root/'x').write_text('changed')
            with self.assertRaises(ValueError):
                verify_pins(root, pins)
            with self.assertRaises(ValueError):
                verify_pins(root, {'../outside': '0'*64})

    def test_fresh_receipts_never_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'receipt.json'
            write_new(path, {'ok': True})
            with self.assertRaises(FileExistsError):
                write_new(path, {'ok': False})
            self.assertTrue(json.loads(path.read_text())['ok'])

    def test_mac_commands_refuse_linux_before_any_inference(self):
        with patch.object(measure_mac.sys, 'platform', 'linux'), self.assertRaises(ValueError):
            measure_mac.mac_only()
        result = subprocess.run(['bash', str(PACKAGE/'scripts/build_mac.sh')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('macOS/arm64', result.stderr)

    def test_cold_measurement_child_also_refuses_linux(self):
        with patch.object(measure_mac.sys, 'platform', 'linux'), self.assertRaises(ValueError):
            measure_mac.cold_worker(None, None, None, None)

    def test_independent_launcher_sha_checked_before_import(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'owner.py'
            path.write_text('raise RuntimeError("must not execute")')
            args = SimpleNamespace(owner_launcher=path, owner_launcher_sha256='0'*64)
            with self.assertRaisesRegex(ValueError, 'launcher SHA mismatch'):
                measure_mac.selection(args)

    def test_one_and_four_threads_keep_four_real_roots(self):
        class FakePlanner:
            def __init__(self, config):
                from concurrent.futures import ThreadPoolExecutor
                self.pool = ThreadPoolExecutor(max_workers=4)
                self.cores = [object() for _ in range(4)]
            def score(self, core):
                return [1, None]
        fake = ModuleType('clasher.live.decision')
        fake.RustPlanner = FakePlanner
        from types import SimpleNamespace
        with patch.dict(sys.modules, {'clasher.live.decision': fake}):
            for threads in (1, 4):
                planner, _ = measure_mac.new_planner({'planner': {}, 'root_threads': threads}, SimpleNamespace(native_dir=Path('/unused')))
                try:
                    self.assertEqual(planner.pool._max_workers, threads)
                    futures = [planner.pool.submit(planner.score, c) for c in planner.cores]
                    self.assertEqual([f.result() for f in futures], [[1, None]]*4)
                    self.assertEqual(planner.measurement_root_scores, [[1, None]]*4)
                finally:
                    planner.pool.shutdown()

    def test_all_configs_are_explicit_and_pinned(self):
        files = json.loads((PACKAGE/'configs/package-pins.json').read_text())['files']
        verify_pins(PACKAGE, files)
        for w in (False, True):
            for t in (1, 4):
                path = PACKAGE/f'configs/w{int(w)}-t{t}.json'
                config = json.loads(path.read_text())
                self.assertEqual(config['root_threads'], t)
                self.assertEqual(config['root_count'], 4)
                self.assertIs(config['planner']['wait_screen8'], w)
                self.assertTrue(config['planner']['public_tower_model'])
                self.assertIn(str(path.relative_to(PACKAGE)), files)


if __name__ == '__main__':
    unittest.main()
