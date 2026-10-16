"""Small stdlib-only tests of evidence rejection; no engine import or host access."""
import ast
import importlib.util
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace, MethodType

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load('validate_r2')
scanner = load('native_entity_sites')
contract = load('snapshot_contract_v1')
semantic_validator = load('validate_semantic_v1')
differences = contract.differences
committed_projectile_aims = contract.committed_projectile_aims
native_active_speed = contract.native_active_speed
troop_speed_differences = contract.troop_speed_differences
entity_source = ast.parse((HERE.parents[3] / 'engine-cards/py/src/clasher/entities.py').read_text())
entity_class = next(n for n in entity_source.body if isinstance(n, ast.ClassDef) and n.name == 'Entity')
speed_methods = {}
exec(compile(ast.Module(body=[n for n in entity_class.body if isinstance(n, ast.FunctionDef) and
                             n.name in ('_unslowed_movement_speed', '_movement_debuff_multiplier')],
                        type_ignores=[]), 'engine-cards/py/src/clasher/entities.py', 'exec'), speed_methods)


def python_speed_entity(speed=60.0, original_speed=None, slow_multiplier=1.0, movement_mode_multiplier=1.0):
    entity = SimpleNamespace(speed=speed, original_speed=original_speed, slow_multiplier=slow_multiplier,
                             movement_mode_multiplier=movement_mode_multiplier, card_stats=SimpleNamespace(speed=60.0))
    for method in ('_unslowed_movement_speed', '_movement_debuff_multiplier'):
        setattr(entity, method, MethodType(speed_methods[method], entity))
    return entity


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


def semantic_sweep(mutation=False):
    rows = sweep(mutation)
    for summary in rows:
        summary.update(contract=contract.VERSION, raw_discrepancy_runs=40, queried_runs=40, query_count=40)
        for run in summary['rows']:
            run.update(contract=contract.VERSION, compared_ticks=45, fresh_troop_templates=['config.cards.Knight'],
                       gate_queries=[dict(method='can_receive_area_damage', source='Log', allowed=False)],
                       raw_first=0, raw_differences=[dict(field='cache', python=None, native=60)],
                       applicability=[dict(field='state.entities.7.public_speed_base', entity_class='Troop',
                                           python=None, native=60, reason='independent speed check',
                                           disposition='effective-value-compared', ticks=[0])])
            run.setdefault('differences', [])
            for delta in run['differences']:
                delta.update(tick=3, digest_equal=True, python=[], native=[7])
    return rows


def compare_fixture(cls='Troop'):
    row = dict(id=7, alive=True, **{'class': cls}, public_speed_base=None,
               stats=dict(name='Knight', speed=60, charge_speed=120), charge=0,
               shot_target=8, aim=[9.0, 26.0], hit_ids=[8], area_slows=[], hastes=[], periodic=[],
               strike_targets=[8], chain_visited=[8], launch_delay=100)
    state = dict(entities=[row], config={}, tick=9)
    actual = copy.deepcopy(state); actual['entities'][0]['public_speed_base'] = 60
    return state, actual, {7: python_speed_entity()}


class EvidenceTests(unittest.TestCase):
    def test_applicability_retains_raw_values_and_unknown_class_stays_strict(self):
        expected, actual, entities = compare_fixture('Projectile')
        delta, ledger, raw = contract.compare_states(expected, actual, entities)
        self.assertFalse(delta); self.assertTrue(raw)
        record = next(r for r in ledger if r['field'].endswith('.public_speed_base'))
        self.assertEqual((record['python'], record['native'], record['entity_class']), (None, 60, 'Projectile'))
        self.assertEqual(record['reason'], contract.CACHE_INAPPLICABLE['Projectile'])
        expected['entities'][0]['class'] = actual['entities'][0]['class'] = 'UnknownProjectileSubclass'
        self.assertTrue(contract.compare_states(expected, actual, entities)[0])

    def test_child_materialization_changes_cache_applicability(self):
        expected, actual, entities = compare_fixture('Projectile')
        actual['entities'][0]['public_speed_base'] = 137
        self.assertFalse(contract.compare_states(expected, actual, entities)[0])
        expected['entities'][0]['class'] = actual['entities'][0]['class'] = 'Troop'
        self.assertTrue(contract.compare_states(expected, actual, entities)[0])
        actual['entities'][0]['public_speed_base'] = 60
        self.assertFalse(contract.compare_states(expected, actual, entities)[0])
        # A cached pre-threshold phase stays authoritative; do not replace it from current charge.
        actual['entities'][0]['charge'] = expected['entities'][0]['charge'] = 10000
        self.assertFalse(contract.compare_states(expected, actual, entities)[0])
        actual['entities'][0]['public_speed_base'] = None
        self.assertTrue(contract.compare_states(expected, actual, entities)[0])

    def test_meaningful_projectile_state_survives_cache_applicability(self):
        expected, actual, entities = compare_fixture('Projectile')
        for key, bad in [('shot_target', 99), ('aim', [9.0, 26.5]), ('hit_ids', [8, 8]),
                         ('area_slows', [[1, .7]]), ('hastes', [[2, 10]]), ('periodic', [[3, 5]]),
                         ('strike_targets', [99]), ('chain_visited', [99]), ('launch_delay', 0)]:
            changed = copy.deepcopy(actual); changed['entities'][0][key] = bad
            self.assertTrue(contract.compare_states(expected, changed, entities)[0], key)
        changed = copy.deepcopy(actual); changed['entities'][0]['stats']['speed'] = 120
        self.assertTrue(contract.compare_states(expected, changed, entities)[0], 'projectile travel speed')

    def test_fresh_template_proof_checks_nested_child_cache(self):
        state = dict(config={'death_children': [dict(**{'class': 'Troop'}, public_speed_base=None)]}, entities=[])
        self.assertTrue(contract.fresh_troop_templates(state))
        state['config']['death_children'][0]['public_speed_base'] = 137
        with self.assertRaises(AssertionError):
            contract.fresh_troop_templates(state)
        with self.assertRaises(AssertionError):
            contract.fresh_troop_templates(dict(config={}, entities=[]))

    def test_semantic_validator_keeps_mutation_field_digest_and_both_seats_strict(self):
        semantic_validator.check_sweep(semantic_sweep(), ['log'])
        semantic_validator.check_sweep(semantic_sweep(True), ['log'], ('Log', 'RollingProjectile', True))
        for alteration in ('delta_digest', 'one_seat', 'short_run', 'missing_raw', 'missing_ledger', 'wrong_class', 'error'):
            rows = semantic_sweep(alteration in ('delta_digest', 'one_seat', 'wrong_class'))
            run = rows[0]['rows'][0]
            if alteration == 'delta_digest':
                run['digest_equal'] = True; run['differences'][0]['digest_equal'] = False
            elif alteration == 'one_seat':
                rows[1]['rows'][0]['differences'] = []
            elif alteration == 'short_run':
                run['compared_ticks'] = 44
            elif alteration == 'missing_raw':
                run['raw_differences'] = []
            elif alteration == 'missing_ledger':
                run['applicability'] = []
            elif alteration == 'wrong_class':
                run['differences'][0]['entity_class'] = 'Troop'
            else:
                run['error'] = 'collector error'
            with self.assertRaises(AssertionError, msg=alteration):
                semantic_validator.check_sweep(rows, ['log'], ('Log', 'RollingProjectile', True)
                                               if alteration in ('delta_digest', 'one_seat', 'wrong_class') else None)

    def test_semantic_fixture_cards_exist_in_frozen_data(self):
        tree = ast.parse((HERE/'probe_dash_semantic_v1.py').read_text())
        # Position constants are nonliteral; extract only the card string from each case tuple.
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'CASES' for t in n.targets))
        cards = [v.elts[0].value for v in assignment.value.values]
        loop = next(n for n in tree.body if isinstance(n, ast.For))
        cards += [pair[1] for pair in ast.literal_eval(loop.iter)]
        root = HERE.parents[3]/'engine-cards/py'
        aliases_ast = ast.parse((root/'src/clasher/card_aliases.py').read_text())
        aliases = ast.literal_eval(next(n.value for n in aliases_ast.body if isinstance(n, ast.AnnAssign)))
        available = {r['name'] for r in json.loads((root/'gamedata.json').read_text())['items']['spells']}
        self.assertEqual(len(cards), 31)
        self.assertTrue(all(c in available or aliases.get(c) in available for c in cards))
        self.assertIn('AxeMan', cards); self.assertNotIn('Executioner', cards)

    def test_descendant_validator_requires_both_seats_and_real_continuation(self):
        rows = []
        ledger = semantic_sweep()[0]['rows'][0]['applicability']
        for case, cls in [('barblog', 'RollingProjectile'), ('royal_delivery', 'SpawnProjectile')]:
            for seat in (0, 1):
                rows.append(dict(case=case, seat=seat, contract=contract.VERSION, ok=True, first=None,
                                 differences=[], source_class=cls, sentinel=137.0, child_ids=[9], continuation=20,
                                 poisoned_child_detected=True, fresh_troop_templates=['config.cards.Knight'],
                                 speed_checks=[dict(tick=t, child=9, native_cache=60) for t in range(20)],
                                 applicability=ledger))
        semantic_validator.check_descendants(rows)
        for change in ('seat', 'continuation', 'sentinel', 'poison', 'error'):
            changed = copy.deepcopy(rows)
            row = changed[0]
            if change == 'seat': row['seat'] = 1
            elif change == 'continuation': row['speed_checks'].pop()
            elif change == 'sentinel': row['speed_checks'][0]['native_cache'] = 137
            elif change == 'poison': row['poisoned_child_detected'] = False
            else: row['error'] = 'failure'
            with self.assertRaises(AssertionError, msg=change):
                semantic_validator.check_descendants(changed)

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

    def test_delayed_homing_uses_committed_endpoint_and_still_checks_aim(self):
        # Target moved during a launch delay; the projectile has not committed that new aim yet.
        source = SimpleNamespace(target_position=SimpleNamespace(x=9.0, y=26.0),
                                 primary_target=SimpleNamespace(position=SimpleNamespace(x=9.0, y=26.5)))
        state = {'entities': [dict(id=8, **{'class': 'Projectile'}, aim=[9.0, 26.5], shot_target=7)]}
        projected = committed_projectile_aims(state, {8: source})
        self.assertEqual(projected['entities'][0]['aim'], [9.0, 26.0])
        self.assertEqual(projected['entities'][0]['shot_target'], 7)
        self.assertFalse(list(differences(projected, {'entities': [dict(id=8, **{'class': 'Projectile'},
                                                                     aim=[9.0, 26.0], shot_target=7)]})))
        self.assertTrue(list(differences(projected, {'entities': [dict(id=8, **{'class': 'Projectile'},
                                                                    aim=[9.0, 26.5], shot_target=7)]})))

    def test_actual_native_speed_cache_and_exact_fallback(self):
        row = dict(public_speed_base=60.0, charge=10000, stats=dict(speed=60.0, charge_speed=120.0))
        self.assertEqual(native_active_speed(row), 60.0)  # cached before charge threshold crossed
        row['public_speed_base'] = 0.0
        self.assertEqual(native_active_speed(row), 0.0)   # initialized zero must not select fallback
        row['public_speed_base'] = None
        self.assertEqual(native_active_speed(row), 120.0)
        row['charge'] = 0
        self.assertEqual(native_active_speed(row), 60.0)

    def test_independent_python_speed_slow_recovery_and_wrong_speed_controls(self):
        entity = python_speed_entity(speed=30.0, original_speed=60.0, slow_multiplier=0.5)
        battle = SimpleNamespace(entities={7: entity})
        row = dict(**{'class': 'Troop'}, public_speed_base=60.0, charge=0,
                   stats=dict(name='Knight', speed=60.0, charge_speed=120.0))
        self.assertFalse(list(troop_speed_differences(battle, {'7': row})))
        row['public_speed_base'] = 30.0
        self.assertTrue(list(troop_speed_differences(battle, {'7': row})))
        row['public_speed_base'] = 60.0
        entity.original_speed = 120.0
        self.assertTrue(list(troop_speed_differences(battle, {'7': row})))
        entity.original_speed = None; entity.speed = 60.0; entity.slow_multiplier = 1.0
        self.assertFalse(list(troop_speed_differences(battle, {'7': row})))

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
