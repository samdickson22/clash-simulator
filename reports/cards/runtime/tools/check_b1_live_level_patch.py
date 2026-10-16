"""Read-only stdlib check of the LIVE-owned proposed consumer patch.

Applies a unified patch IN MEMORY and executes only the source-extracted public
payload method on fixtures. No numpy/Resources/native import or file mutation.
LIVE owner still owns actual consumer integration and admitted native tests.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import sys
from types import SimpleNamespace as NS

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO / 'engine-cards/py/src'))
spec = importlib.util.spec_from_file_location('public_root',REPO / 'engine-cards/public_root.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def patched(source, patch):
    base, lines = source.splitlines(True), patch.splitlines(True)
    i = next(i for i,l in enumerate(lines) if l.startswith('@@ '))
    index = int(re.match(r'@@ -(\d+)',lines[i]).group(1))-1
    out = base[:index]
    for line in lines[i+1:]:
        if line[0] in ' -':
            assert base[index] == line[1:]
            index += 1
        if line[0] in ' +':
            out.append(line[1:])
    return ''.join(out+base[index:])


def payload(source):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'LevelRoot')
    fn = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name == 'payload')
    # The local import only supplies champion indices, unused in these fixtures.
    fn.body = [n for n in fn.body if not isinstance(n,ast.ImportFrom)]
    ns = dict(copy=copy, json=json, random=random, ratio=lambda _:1., scale=lambda e,r:e,
              np=NS(argmax=lambda values: list(values).index(max(values))))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual-LIVE-payload-method>','exec'),ns)
    return ns['payload']


class Masked(list):
    def __getitem__(self, key):
        return [v for v,ok in zip(self,key) if ok] if isinstance(key,list) else super().__getitem__(key)


def fixture(R, board=False):
    obs = NS(entity_ids=Masked(),entity_features=Masked(),entity_mask=[],global_features=[0]*32)
    if board:
        templates = []
        for token,name,x,y in ((2,'GoblinGiant',5.,12.),(3,'SpearGoblinGiant',5.,12.),(3,'SpearGoblinGiant',5.,12.)):
            e = dict(id=999,owner=0,x=x,y=y,facing=[0,1000],king=False,champion=None,shield=0.,
                     **{'class':'Troop'},stats=dict(name=name,max_hp=100.,interval=1300,load=700))
            if name == 'GoblinGiant':
                e['stats']['riders'] = dict(number=2,radius=900,shift=-22,max_angle=90)
            else:
                rank = len(templates)-1
                dx,dy = p.rider_offset(templates[0],rank)
                e.update(x=x+dx,y=y+dy,mount=99999,rider_rank=99)
            templates.append(e)
            R.templates[token,'Troop'] = copy.deepcopy(e)
            row = [0.]*33; row[0]=e['x']/18; row[1]=e['y']/32; row[2]=1; row[4]=1; row[9]=1; row[28]=1
            obs.entity_ids.append(token); obs.entity_features.append(row); obs.entity_mask.append(True)
    return NS(R=R,levels=NS(level=lambda *args:11)), NS(seat=0,tick=5,own={},packet=NS(observation=obs))


def main():
    source = (REPO / 'bot/live/levels.py').read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == '822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5'
    patch = (REPO / 'reports/cards/runtime/patches/B1-live-level-public-graph.patch').read_text()
    fixed = patched(source,patch)
    assert hashlib.sha256(fixed.encode()).hexdigest() == 'a3289daf71ef7f1e4270e2b4f56542a31f07c00a86b645ab94c7fbadd3d032bf'
    old,new = payload(source),payload(fixed)
    rng = NS(integers=lambda _:123)
    for modern in (False,True):
        R = NS(builder=NS(token_names=['pad','unknown','GoblinGiant','SpearGoblinGiant']),templates={},config={})
        if modern: R.repair_public_graph = p.repair_public_graph
        root,info = fixture(R)
        assert old(root,info,{},rng) == new(root,info,{},rng)
    R = NS(builder=NS(token_names=['pad','unknown','GoblinGiant','SpearGoblinGiant']),templates={},config={},
           repair_public_graph=p.repair_public_graph)
    root,info = fixture(R,True)
    before = json.loads(old(root,info,{},rng))['entities']
    assert all(e['mount'] == 99999 for e in before[1:])
    after = json.loads(new(root,info,{},rng))['entities']
    assert all(e['mount'] == after[0]['id'] for e in after[1:])
    assert {e['rider_rank'] for e in after[1:]} == {0,1}
    assert hashlib.sha256((REPO/'bot/live/levels.py').read_bytes()).hexdigest() == hashlib.sha256(source.encode()).hexdigest()
    print('PASS: legacy/new C56 payload bytes preserved; old stale GG graph reproduced; proposed consumer repairs valid distinct ranks; protected source unchanged')


if __name__ == '__main__': main()
