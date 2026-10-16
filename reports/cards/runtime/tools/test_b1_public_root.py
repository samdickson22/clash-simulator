"""Stdlib regressions for public-only defaults and attachment policy.

No Resources startup/native imports. Actual sensor/root/native tests run once
on the admitted combined B1 source via probe_b1_public_root.py.
"""
import copy
import ast
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'engine-cards/py/src'))
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location('public_root', REPO / 'engine-cards/public_root.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def giant(id=37, owner=0, x=5., y=12., facing=(0, 1000)):
    return dict(id=id, owner=owner, x=x, y=y, facing=list(facing), **{'class': 'Troop'},
                stats=dict(name='GoblinGiant', riders=dict(number=2, radius=900, shift=-22, max_angle=90)))


def rider(parent, rank, id):
    dx, dy = p.rider_offset(parent, rank)
    return dict(id=id, owner=parent['owner'], x=parent['x']+dx, y=parent['y']+dy,
                facing=parent['facing'][:], mount=999999, rider_rank=99,
                **{'class': 'Troop'}, stats=dict(name='SpearGoblinGiant'))


def bindings(rows):
    byid = {e['id']: e for e in rows}
    return sorted((e['x'], e['y'], byid[e['mount']]['x'], byid[e['mount']]['y'], e['rider_rank'])
                  for e in rows if 'mount' in e)


class GraphTests(unittest.TestCase):
    def test_both_seats_and_rotated_headings(self):
        for seat, facing in itertools.product((0, 1), ((0, 1000), (0, -1000), (700, 700), (-1000, 0))):
            a = giant(owner=seat, facing=facing)
            rows = [a, rider(a, 0, 1), rider(a, 1, 2)]
            out = p.repair_public_graph(rows)
            self.assertEqual((out['matched'], out['unsupported']), (2, []))
            self.assertEqual({e['rider_rank'] for e in rows[1:]}, {0, 1})
            self.assertTrue(all(e['mount'] == 37 for e in rows[1:]))

    def test_multiple_giants_reordering_and_renumbering(self):
        a, b = giant(), giant(49, x=10.)
        base = [a, b, rider(a, 0, 12), rider(a, 1, 15), rider(b, 0, 17), rider(b, 1, 22)]
        want = None
        for order in (base, base[::-1], base[2:]+base[:2]):
            rows = copy.deepcopy(order)
            for i, e in enumerate(rows):
                e['id'] = i + 1
            p.repair_public_graph(rows)
            got = bindings(rows)
            want = got if want is None else want
            self.assertEqual(got, want)

    def test_coincident_ambiguous_graph_has_bounded_distinct_slots(self):
        a, b = giant(), giant(49)
        rows = [a, b] + [rider(a, i % 2, 100+i) for i in range(4)]
        out = p.repair_public_graph(rows)
        self.assertEqual(out['ambiguous'], 4)
        self.assertEqual(len({(e['mount'], e['rider_rank']) for e in rows[2:]}), 4)

    def test_missing_rider_is_not_invented(self):
        a = giant()
        rows = [a, rider(a, 1, 10)]
        p.repair_public_graph(rows)
        self.assertEqual(len(rows), 2)

    def test_missing_parent_rejected_and_stale_link_removed(self):
        r = rider(giant(), 0, 1)
        with self.assertRaises(p.PublicGraphError) as ctx:
            p.repair_public_graph([r])
        self.assertEqual(ctx.exception.report['unsupported'], [1])
        self.assertNotIn('mount', r)
        self.assertNotIn('rider_rank', r)

    def test_wrong_owner_wrong_type_remote_and_over_capacity_negative_controls(self):
        a = giant()
        variants = []
        wrong_owner = rider(a, 0, 1); wrong_owner['owner'] = 1
        wrong_type = giant(); wrong_type['stats']['name'] = 'Giant'
        remote = rider(a, 0, 1); remote['x'] += 5
        variants += [[a, wrong_owner], [wrong_type, rider(a, 0, 1)], [a, remote]]
        variants += [[a] + [rider(a, i % 2, i+1) for i in range(3)]]
        for rows in variants:
            with self.assertRaises(p.PublicGraphError):
                p.repair_public_graph(copy.deepcopy(rows))

    def test_dead_parent_and_released_children_never_attached(self):
        # Public mask omitted the dead parent/attached rows. Only released
        # ordinary SpearGoblin rows remain; no hidden death state is needed.
        e = rider(giant(), 0, 1)
        e['stats']['name'] = 'SpearGoblin'
        e.pop('mount'); e.pop('rider_rank')
        before = copy.deepcopy(e)
        self.assertEqual(p.repair_public_graph([e])['riders'], 0)
        self.assertEqual(e, before)

    def test_projectiles_are_not_riders(self):
        a = giant()
        shot = rider(a, 0, 1); shot['class'] = 'Projectile'
        shot.pop('mount'); shot.pop('rider_rank')
        before = copy.deepcopy(shot)
        p.repair_public_graph([a, shot])
        self.assertEqual(shot, before)

    def test_legacy_projectile_template_mount_is_stripped_without_parent(self):
        shot = rider(giant(), 0, 1); shot['class'] = 'Projectile'
        p.repair_public_graph([shot])
        self.assertNotIn('mount', shot)
        self.assertNotIn('rider_rank', shot)

    def test_template_hidden_links_and_rank_do_not_affect_matching(self):
        a = giant()
        base = [a, rider(a, 0, 1), rider(a, 1, 2)]
        want = None
        for fake_id, fake_rank in ((0, -123), (37, 0), (10000000, 1234)):
            rows = copy.deepcopy(base)
            for e in rows[1:]:
                e.update(mount=fake_id, rider_rank=fake_rank)
            p.repair_public_graph(rows)
            want = bindings(rows) if want is None else want
            self.assertEqual(bindings(rows), want)

    def test_partial_turn_heading_is_an_approximation(self):
        a = giant()
        rows = [a, rider(a, 0, 1), rider(a, 1, 2)]
        a['facing'] = [0, -1000]
        self.assertEqual(p.repair_public_graph(rows)['matched'], 2)

    def test_unrelated_c56_rows_are_byte_identical(self):
        rows = [dict(id=3, owner=1, x=3., y=4., facing=[1, 0], stats=dict(name='Knight'), **{'class':'Troop'})]
        before = json.dumps(rows)
        p.repair_public_graph(rows)
        self.assertEqual(json.dumps(rows), before)


class TemplateTests(unittest.TestCase):
    def fixture(self):
        body = {'class': 'Troop', 'stats': dict(name=p.THREE_MEMBER, load=700, attack_select={'damage': 123}),
                'public_identity': [('troop_body', ['ThreeMusketeers', p.THREE_MEMBER])]}
        shot = copy.deepcopy(body)
        shot.update({'class':'Projectile', 'public_identity':[('projectile', ['ThreeMusketeers', p.THREE_MEMBER])]})
        second = copy.deepcopy(body); second['stats'].update(name='ThreeMusketeer_Rework_Character_2', load=650)
        cfg = {'cards': {'ThreeMusketeers': {'units': [[second, body], []]}}}
        return cfg, SimpleNamespace(token_id=lambda name, namespace: 326), shot

    def test_explicit_selection_overrides_wrong_first_template_only(self):
        cfg, builder, shot = self.fixture()
        templates = {(326, 'Troop'): {'wrong': True}, (200, 'Troop'): {'C56': True}}
        p.install_three_templates(cfg, builder, templates, shot)
        self.assertEqual(templates[326, 'Troop']['stats']['name'], p.THREE_MEMBER)
        self.assertEqual(templates[326, 'Troop']['stats']['load'], 700)
        self.assertEqual(templates[326, 'Projectile'], shot)
        self.assertEqual(templates[200, 'Troop'], {'C56': True})
        self.assertEqual(cfg['cards']['ThreeMusketeers']['units'][0][0]['stats']['load'], 650)

    def test_wrong_canonical_body_alias_load_projectile_and_token_rejected(self):
        for bad in ('body', 'load', 'alias', 'projectile', 'token'):
            cfg, builder, shot = self.fixture()
            if bad == 'body': cfg['cards']['ThreeMusketeers']['units'][0][1]['stats']['name'] = 'Musketeer'
            if bad == 'load': cfg['cards']['ThreeMusketeers']['units'][0][1]['stats']['load'] = 650
            if bad == 'alias': shot['public_identity'] = [('projectile', ['Musketeer'])]
            if bad == 'projectile': shot['stats']['name'] = 'Musketeer'
            if bad == 'token': builder.token_id = lambda *args, **kw: 1
            with self.assertRaises(ValueError):
                p.install_three_templates(cfg, builder, {}, shot)


class LevelConfigTests(unittest.TestCase):
    def root_class(self):
        # Execute the production methods without importing numpy or starting a
        # runtime on the light host. These methods only use stdlib operations.
        from bot.levels.configs import qkey, SIDE, base_cards
        tree = ast.parse((REPO / 'bot/levels/root.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
        ns = dict(copy=copy, qkey=qkey, SIDE=SIDE, base_cards=base_cards, TOWERS=('Tower', 'KingTower'),
                  SKIP_TOP={'mount', 'rider_rank', 'stats'})
        exec(compile(tree, '<production-level-methods>', 'exec'), ns)
        return ns['ExactLevelRoot'], ns['_templates']

    def test_healer_same_class_empty_names_have_distinct_public_delta_keys(self):
        cls, collect = self.root_class()
        pulse = lambda spell, heal: {'class':'HealPulse', 'spell_name':spell,
                                   'stats':{'name':'', 'load':0}, 'scope':{'heal_per_tick':heal}}
        a = pulse('BattleHealerSpawnHeal', 5)
        b = pulse('BattleHealerHeal', 10)
        templates = {}
        collect([a,b], templates, 'BattleHealer')
        self.assertEqual(len(templates), 2)
        root = cls.__new__(cls)
        root.R = SimpleNamespace(config={'cards': {'BattleHealer':{'units':[[{'class':'Troop', 'stats':{'name':'BattleHealer'}}],[]]}},
                                        'create_areas':{'BattleHealer':a}, 'hit_areas':{'BattleHealer':b}})
        root._producers = None
        self.assertEqual(root.body_card('', 0, 0, {'BattleHealer'}, spell='BattleHealerHeal'), 'BattleHealer')
        e11 = {'card':{}, 'tables':{'create_areas':{'BattleHealer':a}, 'hit_areas':{'BattleHealer':b}}}
        e9 = copy.deepcopy(e11)
        e9['tables']['create_areas']['BattleHealer']['scope']['heal_per_tick'] = 3
        e9['tables']['hit_areas']['BattleHealer']['scope']['heal_per_tick'] = 7
        root.lc = SimpleNamespace(entry=lambda card, lv: e11 if lv == 11 else e9)
        root._delta = {}
        self.assertEqual(root.body_delta('BattleHealer', 9, '', 'HealPulse', 'BattleHealerSpawnHeal')[1]['scope']['heal_per_tick'], 3)
        self.assertEqual(root.body_delta('BattleHealer', 9, '', 'HealPulse', 'BattleHealerHeal')[1]['scope']['heal_per_tick'], 7)

    def test_healer_pulses_qualified_and_cache_binds_config(self):
        from bot.levels.configs import SIDE, LevelConfigs, _qualify
        self.assertTrue({'create_areas', 'hit_areas'} <= set(SIDE))
        entry = {'card': {}, 'tables': {t: {'BattleHealer': {'hp': 1}} for t in ('create_areas', 'hit_areas')}}
        out = _qualify(entry, 'BattleHealer', 9)
        self.assertTrue(all('level9:BattleHealer' in table for table in out['tables'].values()))
        a = LevelConfigs(SimpleNamespace(R=SimpleNamespace(config={'cards': {}}), pins={}))
        b = LevelConfigs(SimpleNamespace(R=SimpleNamespace(config={'cards': {'BattleHealer': {}}}), pins={}))
        self.assertNotEqual(a.dir, b.dir)


if __name__ == '__main__':
    unittest.main()
