"""Planner total delay must not alter backend acceptance or verification timing."""
import json
from pathlib import Path
import tempfile
import unittest
from clasher.live.actuation import Actuation, MockInput
from clasher.live.timing import planner_timing


class TimingTests(unittest.TestCase):
    def test_default_total_delay_matches_measured_components(self):
        _, _, row, ticks = planner_timing({})
        self.assertEqual(ticks, round((row['planner_frame_to_submission_p50_ms']
                                      + row['p50_ms']) / row['tick_ms']))

    def test_total_planner_delay_is_separate_from_backend_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'timing.json'
            row = dict(p50_ticks=23.03, p50_ms=1151.5, p99_ms=1187.3,
                       planner_total_delay_ticks=28)
            path.write_text(json.dumps({'backends': {'test': row}}))
            cfg = dict(backend='test', timing_path=str(path))
            self.assertEqual(planner_timing(cfg)[3], 28)
            actor = Actuation(MockInput(0), 'test', path)
            self.assertEqual(actor.delay_ticks, 23)
            self.assertAlmostEqual(actor.machine.verify_seconds, 1.7873)
            for invalid in (None, True, -1, 28.5, '28', float('nan')):
                row['planner_total_delay_ticks'] = invalid
                path.write_text(json.dumps({'backends': {'test': row}}))
                with self.assertRaisesRegex(ValueError, 'planner_total_delay_ticks'):
                    planner_timing(cfg)
            del row['planner_total_delay_ticks']
            path.write_text(json.dumps({'backends': {'test': row}}))
            with self.assertRaisesRegex(ValueError, 'planner_total_delay_ticks'):
                planner_timing(cfg)


if __name__ == '__main__':
    unittest.main()
