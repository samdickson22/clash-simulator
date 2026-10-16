"""Stdlib regressions for public-only defaults and attachment policy.

No Resources startup/native imports. Actual sensor/root/native tests run once
on the admitted combined B1 source via probe_b1_public_root.py.
"""
import copy
import ast
import importlib.util
import itertools
import json
import struct
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
    def test_spawn_and_sensor_clamped_walls_corners_both_seats(self):
        points = ((.499,.499), (17.501,.499), (.499,31.501), (17.501,31.501),
                  (.499,10.5), (17.501,10.5), (8.5,.499), (8.5,31.501))
        for owner, seat, margin, point in itertools.product((0,1), (0,1), (0.,.25), points):
            a = giant(owner=owner, x=point[0], y=point[1], facing=(0,1000 if owner == 0 else -1000))
            rows = [a, rider(a,0,1), rider(a,1,2)]
            for e in rows[1:]:
                e['x'], e['y'] = p._clamp_position(e['x'], e['y'], margin)
            # Exact public normalization/float32 storage/seat inverse.
            for e in rows:
                for axis, extent in (('x',18.),('y',32.)):
                    v = e[axis] if seat == 0 else extent-e[axis]
                    v = max(0., min(1., v/extent))
                    v = struct.unpack('f',struct.pack('f',v))[0]*extent
                    e[axis] = v if seat == 0 else extent-v
            self.assertEqual(p.repair_public_graph(rows)['matched'], 2)
            self.assertEqual({e['rider_rank'] for e in rows[1:]}, {0,1})

    def test_compressed_interior_radius_still_rejected(self):
        a = giant(x=.499, y=.499)
        r = rider(a,0,1); r.update(x=.499,y=.499)
        with self.assertRaises(p.PublicGraphError):
            p.repair_public_graph([a,r])

    def test_future_clone_capability_oriented_by_public_owner_only(self):
        proto = giant(id=501,x=9.,y=10.5)
        children = [rider(proto,0,502),rider(proto,1,503)]
        for rank,c in enumerate(children):
            c.update(mount=501,rider_rank=rank)
        proto['clone_children'] = children
        before = copy.deepcopy(proto)
        for owner in (0,1):
            parent = giant(owner=owner)
            parent['clone_template'] = copy.deepcopy(proto)
            rows = [parent,rider(parent,0,1),rider(parent,1,2)]
            p.repair_public_graph(rows)
            cap = parent['clone_template']
            self.assertEqual(cap['owner'],owner)
            self.assertEqual(cap['id'],501)
            for c in cap['clone_children']:
                dx,dy = p.rider_offset(cap,c['rider_rank'])
                self.assertEqual((round((c['x']-cap['x'])*1000),round((c['y']-cap['y'])*1000)),
                                 (round(dx*1000),round(dy*1000)))
                self.assertEqual((c['mount'],c['owner']),(501,owner))
            self.assertEqual(len(rows),3)
        self.assertEqual(proto,before)

    def test_future_clone_capability_rejects_wrong_static_parent_rank(self):
        parent = giant()
        proto = giant(id=501,x=9.,y=10.5)
        children = [rider(proto,0,502),rider(proto,1,503)]
        for rank,c in enumerate(children): c.update(mount=501,rider_rank=rank)
        proto['clone_children'] = children
        for bad in ('mount','rank'):
            parent['clone_template'] = copy.deepcopy(proto)
            if bad == 'mount': parent['clone_template']['clone_children'][0]['mount'] = 999
            if bad == 'rank': parent['clone_template']['clone_children'][1]['rider_rank'] = 0
            with self.assertRaises(ValueError): p.repair_public_graph([parent])

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
        body = {'class': 'Troop', 'stats': dict(name=p.THREE_MEMBER, load=700, projectile_speed=1000, attack_select={'damage': 123}),
                'public_identity': [('troop_body', ['ThreeMusketeers', p.THREE_MEMBER])]}
        shot = copy.deepcopy(body)
        shot.update({'class':'Projectile', 'public_identity':[('projectile', ['ThreeMusketeers', p.THREE_MEMBER])]})
        shot['stats']['speed'] = 1000
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
        for bad in ('body', 'load', 'alias', 'projectile', 'token', 'zero_speed', 'wrong_speed'):
            cfg, builder, shot = self.fixture()
            if bad == 'body': cfg['cards']['ThreeMusketeers']['units'][0][1]['stats']['name'] = 'Musketeer'
            if bad == 'load': cfg['cards']['ThreeMusketeers']['units'][0][1]['stats']['load'] = 650
            if bad == 'alias': shot['public_identity'] = [('projectile', ['Musketeer'])]
            if bad == 'projectile': shot['stats']['name'] = 'Musketeer'
            if bad == 'token': builder.token_id = lambda *args, **kw: 1
            if bad == 'zero_speed': shot['stats']['speed'] = 0
            if bad == 'wrong_speed': shot['stats']['speed'] = 20
            with self.assertRaises(ValueError):
                p.install_three_templates(cfg, builder, {}, shot)


class LevelConfigTests(unittest.TestCase):
    def root_class(self):
        # Execute the production methods without importing numpy or starting a
        # runtime on the light host. These methods only use stdlib operations.
        from bot.levels.configs import qkey, SIDE, base_cards
        tree = ast.parse((REPO / 'bot/levels/root.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.Assign))]
        ns = dict(copy=copy, qkey=qkey, SIDE=SIDE, base_cards=base_cards, TOWERS=('Tower', 'KingTower'),
                  SKIP_TOP={'mount', 'rider_rank', 'stats'})
        exec(compile(tree, '<production-level-methods>', 'exec'), ns)
        return ns['ExactLevelRoot'], ns['_templates']

    def test_clone_capabilities_change_only_for_scoped_b1_producers(self):
        cls, _ = self.root_class()
        for name in ('GoblinGiant', 'ThreeMusketeers', 'BattleHealer', 'Knight', 'Musketeer'):
            root = cls.__new__(cls)
            body = {'class':'Troop', 'stats':{'name':name,'damage':100},
                    'clone_template':{'stats':{'name':name,'damage':100}}}
            e11 = {'card':{'units':[[body],[]]},'tables':{}}
            e9 = copy.deepcopy(e11)
            e9['card']['units'][0][0]['stats']['damage'] = 80
            e9['card']['units'][0][0]['clone_template']['stats']['damage'] = 80
            root.lc = SimpleNamespace(entry=lambda card, lv: e11 if lv == 11 else e9)
            root._delta = {}
            sd,td = root.body_delta(name,9,name,'Troop')
            self.assertEqual(sd['damage'],80)
            if name in ('Knight','Musketeer'):
                self.assertNotIn('clone_template',td)
                self.assertEqual(json.dumps(body['clone_template']),json.dumps({'stats':{'name':name,'damage':100}}))
            else:
                self.assertEqual(td['clone_template']['stats']['damage'],80)

    def test_building_projectile_level_fallback_preserved(self):
        cls, _ = self.root_class()
        for name in ('Cannon', 'Tesla', 'Xbow'):
            root = cls.__new__(cls)
            body = {'class':'Building', 'stats':{'name':name, 'damage':100, 'max_hp':1000}}
            e11 = {'card':{'units':[[body],[]]}, 'tables':{}}
            e9 = copy.deepcopy(e11)
            e9['card']['units'][0][0]['stats'].update(damage=80,max_hp=800)
            root.lc = SimpleNamespace(entry=lambda card, lv: e11 if lv == 11 else e9)
            root._delta = {}
            self.assertEqual(root.body_delta(name,9,name,'Projectile')[0]['damage'], 80)

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


class NativeSnapshotOracleTests(unittest.TestCase):
    def test_native_omitted_zero_rank_default_and_bad_graph_negative_controls(self):
        tree = ast.parse((REPO / 'reports/cards/runtime/tools/probe_b1_public_root.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('require','graph')]
        ns = {}
        exec(compile(tree,'<production-native-snapshot-oracle>','exec'),ns)
        a = giant()
        r0,r1 = rider(a,0,1),rider(a,1,2)
        r0.update(mount=a['id']); r0.pop('rider_rank')
        r1.update(mount=a['id'],rider_rank=1)
        self.assertEqual(len(ns['graph']({'entities':[a,r0,r1]})),2)
        for bad in ('mount','rank','owner'):
            rows = copy.deepcopy([a,r0,r1])
            if bad == 'mount': rows[1]['mount'] = 99999
            if bad == 'rank': rows[2]['rider_rank'] = 0
            if bad == 'owner': rows[1]['owner'] = 1
            with self.assertRaises(AssertionError):
                ns['graph']({'entities':rows})


if __name__ == '__main__':
    unittest.main()
