"""Light checks for the refit failure modes; no model, runtime, or corpus needed."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from bot.exit import train


class Store:
    def __len__(self):
        return 1000

    def batch(self, positions):
        return positions


class RefitInputsTest(unittest.TestCase):
    def test_export_gate_rejects_corruption_and_nonfinite_logits(self):
        from bot.search.lopp_train import check_export_head
        logits = np.array([[1., 2., 3.]], np.float32)
        self.assertEqual(check_export_head(logits, logits.copy()), 0.)
        for bad in (logits + .1, np.full_like(logits, np.nan), np.full_like(logits, np.inf)):
            with self.assertRaises((AssertionError, ValueError)):
                check_export_head(logits, bad)

    def test_mixed_batches_include_both_stores_deterministically(self):
        for fraction, counts in ((.5, (2048, 2048)), (2 / 3, (2731, 1365))):
            data = train.StepBatches(Store(), Store(), 4096, fraction, 123, 0, 2)
            with patch.object(train, 'concat', side_effect=lambda parts: parts):
                _, parts = data[0]
                _, again = data[0]
            self.assertEqual(tuple(map(len, parts)), counts)
            self.assertTrue(all((a == b).all() for a, b in zip(parts, again)))

    def test_misconfigured_ratio_fails_before_runtime_or_output_creation(self):
        base = ['--init', 'unused', '--assets', 'unused', '--new', 'unused', '--out', 'unused']
        for extra in (['--old', 'unused'], ['--new-ratio', '2'],
                      ['--new-ratio', 'nan'], ['--new-ratio', '0'],
                      ['--new-ratio', '.5'], ['--loader-workers', '-1']):
            with self.subTest(extra=extra), patch.object(train, 'bootstrap') as bootstrap:
                with self.assertRaises(SystemExit) as result:
                    train.main(base + extra)
                self.assertEqual(result.exception.code, 2)
                bootstrap.assert_not_called()

    def test_kf1_export_args_convert_every_path(self):
        # Exercise the actual export expression without loading torch or starting a fit.
        import ast
        from types import SimpleNamespace
        tree = ast.parse((Path(__file__).parents[1] / 'search/lopp_train.py').read_text())
        assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'serial_args' for t in n.targets))
        scope = dict(Path=Path, a=SimpleNamespace(init=Path('poolfp.npz'), out=Path('out'), epochs=8))
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<export args>', 'exec'), scope)
        self.assertEqual(json.loads(json.dumps(scope['serial_args'])),
                         dict(init='poolfp.npz', out='out', epochs=8))


if __name__ == '__main__':
    unittest.main()
