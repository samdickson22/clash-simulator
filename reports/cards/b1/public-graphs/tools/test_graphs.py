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

    def test_incomplete_remote_wrong_owner_orphan_and_capacity_guards(self):
        base=copy.deepcopy(BOARD['rows'])
        # A transported partial graph is still explicitly unsupported.
        for bad in ('partial','owner','orphan','capacity'):
            rows=copy.deepcopy(base)
            if bad=='partial':rows=[r for r in rows if r['id']!=12]
            if bad=='owner':next(r for r in rows if r['id']==11)['owner']=0
            if bad=='orphan':rows=[r for r in rows if r['id']!=11]
            if bad=='capacity':
                r=copy.deepcopy(next(r for r in rows if r['id']==13));r['id']=99;rows.append(r)
            with self.assertRaises(p.PublicGraphError):p.repair_public_graph(rows)

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
