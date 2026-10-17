"""Public-only graph controls, including the actual complete mixed-game board."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO/'engine-cards/py/src'))
spec = importlib.util.spec_from_file_location('new_public_graph', REPO/'engine-cards/public_root.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
old = types.ModuleType('old_public_graph')
exec(subprocess.check_output(['git','show','a156cf5b1:engine-cards/public_root.py'],cwd=REPO,text=True),old.__dict__)
BOARD = json.loads((Path(__file__).resolve().parents[1]/'failing-public-board.json').read_text())


def bindings(rows):
    ids = {r['id']: r for r in rows}
    return sorted((r['owner'],r['x'],r['y'],ids[r['mount']]['x'],ids[r['mount']]['y'],r['rider_rank'])
                  for r in rows if r.get('mount') is not None)


def reflect(rows):
    for e in rows:
        e.update(owner=1-e['owner'], x=18-e['x'], y=32-e['y'], facing=[-x for x in e['facing']])
    return rows


class MixedGraphTests(unittest.TestCase):
    def test_actual_baseline_counterexample_is_reproduced(self):
        with self.assertRaises(old.PublicGraphError) as ex:
            old.repair_public_graph(copy.deepcopy(BOARD['rows']))
        self.assertEqual(ex.exception.report['unsupported'], [13])
        self.assertEqual(ex.exception.report['matched'], 1)
        self.assertEqual((BOARD['tick'],BOARD['seat']), (350,0))

    def test_actual_full_board_both_owners_and_row_orders(self):
        for flip, reverse in itertools.product((False,True), repeat=2):
            rows = copy.deepcopy(BOARD['rows'])
            if flip: reflect(rows)
            if reverse: rows.reverse()
            out = p.repair_public_graph(rows)
            self.assertEqual(out['matched'],2)
            self.assertEqual(out['structural_fallback'], [0 if flip else 1])
            self.assertEqual(out['structural_riders'],2)
            self.assertEqual(len({(r['mount'],r['rider_rank']) for r in rows if r.get('mount') is not None}),2)

    def test_source_visibility_or_private_template_links_do_not_gate_complete_graph(self):
        want = None
        for source_visible, fake_link in itertools.product((True,False),(1,999999)):
            rows=copy.deepcopy(BOARD['rows'])
            if not source_visible: rows=[r for r in rows if r['stats']['name']!='Fisherman']
            for r in rows:
                if r['stats']['name']=='SpearGoblinGiant':r.update(mount=fake_link,rider_rank=99)
            p.repair_public_graph(rows)
            got=bindings(rows); want=got if want is None else want
            self.assertEqual(got,want)

    def test_multiple_transported_parents_recompute_whole_owner(self):
        rows=copy.deepcopy(BOARD['rows'])
        extra=copy.deepcopy(next(r for r in rows if r['id']==11));extra.update(id=90,x=11.,y=18.)
        extra_children=[]
        for rank,id in enumerate((91,92)):
            r=copy.deepcopy(next(r for r in rows if r['id']==12+rank))
            r.update(id=id,x=r['x']+7,y=r['y']+4); extra_children.append(r)
        rows += [extra]+extra_children
        want=None
        for reverse in (False,True):
            trial=copy.deepcopy(rows[::-1] if reverse else rows)
            out=p.repair_public_graph(trial)
            self.assertEqual(out['matched'],4);self.assertEqual(out['structural_riders'],4)
            self.assertEqual(len({(r['mount'],r['rider_rank']) for r in trial if r.get('mount') is not None}),4)
            got=bindings(trial);want=got if want is None else want
            self.assertEqual(got,want)

    def test_wrong_owner_orphan_and_capacity_guards(self):
        base=copy.deepcopy(BOARD['rows'])
        for bad in ('owner','orphan','capacity'):
            rows=copy.deepcopy(base)
            if bad=='owner':next(r for r in rows if r['id']==11)['owner']=0
            if bad=='orphan':rows=[r for r in rows if r['id']!=11]
            if bad=='capacity':
                r=copy.deepcopy(next(r for r in rows if r['id']==13));r['id']=99;rows.append(r)
            with self.assertRaises(p.PublicGraphError):p.repair_public_graph(rows)

    def test_transported_partial_population_reconstructs(self):
        # Only the displaced rider is observed (its sibling row is missing):
        # the old helper rejects it, the capacity-feasible policy attaches it.
        rows=[r for r in copy.deepcopy(BOARD['rows']) if r['id']!=12]
        with self.assertRaises(old.PublicGraphError):old.repair_public_graph(copy.deepcopy(rows))
        for flip, reverse in itertools.product((False,True), repeat=2):
            trial=copy.deepcopy(rows)
            if flip: reflect(trial)
            if reverse: trial.reverse()
            out=p.repair_public_graph(trial)
            self.assertEqual((out['matched'],out['structural_riders'],out['unsupported']),(1,1,[]))
            self.assertEqual([r['mount'] for r in trial if r.get('mount') is not None],
                             [next(r['id'] for r in trial if r['stats']['name']=='GoblinGiant')])


def _gg(owner, id, x, y, facing, spec):
    return dict(id=id, owner=owner, **{'class': 'Troop'}, x=x, y=y, facing=list(facing),
                stats=dict(name='GoblinGiant', riders=spec))


def _rider(owner, id, x, y):
    return dict(id=id, owner=owner, **{'class': 'Troop'}, x=x, y=y, facing=[0, 1000],
                stats=dict(name='SpearGoblinGiant'))


class PropertyTests(unittest.TestCase):
    SPEC = next(r for r in BOARD['rows'] if r['stats']['name'] == 'GoblinGiant')['stats']['riders']

    def board(self, rng, parents, displaced, drop, extra=0):
        rows, n = [], 1
        for owner in (0, 1):
            for _ in range(parents[owner]):
                x, y = rng.uniform(2, 16), rng.uniform(3, 29)
                facing = rng.choice(([0, 1000], [0, -1000], [707, 707], [-600, 800]))
                gg = _gg(owner, n, x, y, facing, self.SPEC); n += 1
                kids = []
                for rank in range(2):
                    dx, dy = p.rider_offset(gg, rank)
                    kids.append(_rider(owner, n, x + dx, y + dy)); n += 1
                if displaced:  # post-carry parent movement of up to ~1.5 tiles
                    gg.update(x=x + rng.uniform(-1.5, 1.5), y=y + rng.uniform(-1.5, 1.5))
                rows.append(gg)
                rows += [k for k in kids if rng.random() >= drop]
            for _ in range(extra):
                rows.append(_rider(owner, n, rng.uniform(2, 16), rng.uniform(3, 29))); n += 1
        rng.shuffle(rows)
        return rows

    def test_feasible_populations_always_reconstruct(self):
        import random
        rng = random.Random(20261017)
        for trial in range(3000):
            rows = self.board(rng, (rng.randint(0, 3), rng.randint(0, 3)), True, rng.choice((0, .3, .6)))
            out = p.repair_public_graph(rows)
            riders = [r for r in rows if r['stats']['name'] == 'SpearGoblinGiant']
            ids = {r['id']: r for r in rows}
            self.assertEqual((out['matched'], out['unsupported']), (len(riders), []))
            slots = {(r['mount'], r['rider_rank']) for r in riders}
            self.assertEqual(len(slots), len(riders))
            for r in riders:
                m = ids[r['mount']]
                self.assertEqual((m['stats']['name'], m['owner'], r['rider_rank'] in (0, 1)),
                                 ('GoblinGiant', r['owner'], True))

    def test_over_capacity_always_rejected(self):
        import random
        rng = random.Random(7)
        for trial in range(500):
            rows = self.board(rng, (rng.randint(0, 2), rng.randint(0, 2)), rng.random() < .5, 0, extra=1)
            with self.assertRaises(p.PublicGraphError):
                p.repair_public_graph(rows)

    def test_undisplaced_boards_match_old_helper_exactly(self):
        import random
        rng = random.Random(11)
        for trial in range(2000):
            rows = self.board(rng, (rng.randint(0, 3), rng.randint(0, 3)), False, rng.choice((0, .3)))
            a, b = copy.deepcopy(rows), copy.deepcopy(rows)
            ra = old.repair_public_graph(a)
            rb = p.repair_public_graph(b)
            self.assertEqual(rb['structural_fallback'], [])
            self.assertEqual(a, b)
            self.assertEqual({k: ra[k] for k in ra}, {k: rb[k] for k in ra})

    def test_balanced_remote_pair_is_explicit_public_default(self):
        # Position alone cannot prove the private transport history. The new
        # complete-population policy deliberately accepts capacity-feasible rows.
        rows=copy.deepcopy(BOARD['rows'])
        for r in rows:
            if r['stats']['name']=='GoblinGiant':r.update(x=17.,y=29.)
        out=p.repair_public_graph(rows)
        self.assertEqual(out['matched'],2);self.assertEqual(out['structural_fallback'],[1])

    def test_duplicate_ids_rejected_and_unrelated_rows_unchanged(self):
        rows=copy.deepcopy(BOARD['rows']);rows[0]['id']=rows[1]['id']
        with self.assertRaises(ValueError):p.repair_public_graph(rows)
        rows=copy.deepcopy(BOARD['rows'])
        before=[copy.deepcopy(r) for r in rows if r['stats']['name'] not in ('GoblinGiant','SpearGoblinGiant')]
        p.repair_public_graph(rows)
        self.assertEqual(before,[r for r in rows if r['stats']['name'] not in ('GoblinGiant','SpearGoblinGiant')])


if __name__=='__main__':unittest.main()
