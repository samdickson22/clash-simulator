"""Small stdlib-only tests of evidence rejection; no engine import or host access."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load('validate_r2')
scanner = load('native_entity_sites')
# Load only the actual pure comparison functions, without importing the engine.
source = ast.parse((HERE / 'probe_dash_full.py').read_text())
namespace = {}
exec(compile(ast.Module(body=[n for n in source.body if isinstance(n, ast.FunctionDef) and
                             n.name in ('norm', 'differences')], type_ignores=[]), str(HERE / 'probe_dash_full.py'), 'exec'), namespace)
differences = namespace['differences']


def sweep(mutation=False):
    rows = []
    for seat in ('blue', 'red'):
        runs = [dict(lead=n, first=None, cast=dict(python=True, native=True, before_export=False))
                for n in range(-4, 36)]
        if mutation:
            runs[0].update(first=3, digest_equal=True, differences=[dict(
                field='state.entities.8.hit_ids', spell_name='Log', entity_class='RollingProjectile')])
        rows.append(dict(case='log', seat=seat, rows=runs, runs=40, cast_successes=40,
                         mismatches=int(mutation), query_count=1))
    return rows


class EvidenceTests(unittest.TestCase):
    def test_full_comparison_detects_native_only_optional_state(self):
        self.assertTrue(list(differences({'frozen_stop': None}, {'frozen_stop': {'target_id': 7}})))
        self.assertTrue(list(differences({}, {'frozen_stop': {'target_id': 7}})))

    def test_full_comparison_detects_buffs_and_pending_casts(self):
        for key in ('periodic', 'area_slows', 'hastes', 'pending_casts'):
            self.assertTrue(list(differences({key: []}, {key: [{'id': 7}]})))

    def test_hit_sets_ordered_but_duplicates_and_extra_hits_fail(self):
        self.assertFalse(list(differences({'hit_ids': [2, 7]}, {'hit_ids': [7, 2]})))
        self.assertTrue(list(differences({'hit_ids': []}, {'hit_ids': [7]})))
        self.assertTrue(list(differences({'hit_ids': [7]}, {'hit_ids': [7, 7]})))

    def test_baseline_and_intended_mutation(self):
        validator.check_sweep(sweep(), ['log'])
        validator.check_sweep(sweep(True), ['log'], ('Log', 'RollingProjectile', True))

    def test_rejected_action_and_swallowed_exception_rejected(self):
        for alteration in ('rejected', 'error', 'duplicate_offset'):
            rows = sweep()
            run = rows[0]['rows'][0]
            if alteration == 'rejected':
                run['cast']['native'] = False
            elif alteration == 'error':
                run['error'] = 'probe exception'
            else:
                run['lead'] = -3
            with self.assertRaises(AssertionError):
                validator.check_sweep(rows, ['log'])

    def test_only_declared_setup_only_fixtures_allow_zero_actions(self):
        zero = [name for name, count in validator.FIRST_UPDATE_ACTIONS.items() if count == 0]
        self.assertEqual(len(zero), 6)
        self.assertEqual(len(validator.FIRST_UPDATE_ACTIONS), 21)
        validator.check_actions([], 0)
        with self.assertRaises(AssertionError):
            validator.check_actions([], 1)
        with self.assertRaises(AssertionError):
            validator.check_actions([])

    def test_unrelated_mutation_difference_rejected(self):
        for alteration in ('field', 'spell', 'class', 'digest', 'seat'):
            rows = sweep(True)
            run = rows[0]['rows'][0]
            delta = run['differences'][0]
            if alteration == 'field':
                delta['field'] = 'state.entities.7.hp'
            elif alteration == 'spell':
                delta['spell_name'] = 'Tower'
            elif alteration == 'class':
                delta['entity_class'] = 'Troop'
            elif alteration == 'digest':
                run['digest_equal'] = False
            else:
                rows[1]['rows'][0]['differences'] = []
            with self.assertRaises(AssertionError):
                validator.check_sweep(rows, ['log'], ('Log', 'RollingProjectile', True))

    def test_scanner_multiline_length_loop_hit_extend_and_no_files(self):
        with tempfile.TemporaryDirectory(prefix='b2-r2-scanner-') as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                list(scanner.scan(root))
            (root / 'fixture.rs').write_text('''fn targets() {
for i in 0..self.entities.len() { }
self\n.entities\n.iter().filter(|e| e.alive);
self.entities[..n].iter();
e.hit_ids.extend(&ids);
}
''')
            found = list(scanner.scan(root))
            self.assertEqual(len(found), 4)
            self.assertEqual({row[1] for row in found}, {'targets'})


if __name__ == '__main__':
    unittest.main()
