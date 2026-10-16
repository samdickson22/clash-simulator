"""Generic affordability feasibility oracle, confidence negatives, legacy parity, and bounded real HUD cache."""
import itertools
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent));import handread
ROOT=Path('/mpac/sdicks02/scratch/live-loop');R=ROOT/'packages/handsync-identity-r7'
oldpath=ROOT/'evidence/r7-deployed-handread-20261016T113139Z/source/handread.py'
spec=importlib.util.spec_from_file_location('old_handread_reference',oldpath);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
# Independent finite oracle: enumerate assignments, then ask whether any balance in {0,..,10} explains the UI.
# Integer-cost cases suffice for this exhaustive oracle; the implementation itself also accepts finite real costs.
rng=np.random.default_rng(22)
cards=['a','b','c','d','e'];costs=dict(zip(cards,[0,1,3,4,5]));L=rng.normal(size=(5,6))
probs=np.exp(L-L.max(-1,keepdims=True));probs/=probs.sum(-1,keepdims=True)
for ui in itertools.product(('empty','greyed','coloured'),repeat=4):
    feasible=[]
    for names in itertools.permutations(cards,5):
        if any(all(u=='empty' or (costs[n]<=balance if u=='coloured' else costs[n]>balance)
                   for n,u in zip(names,ui)) for balance in range(11)):
            score=sum(np.log(probs[i,cards.index(n)]+1e-12) for i,n in enumerate(names))
            feasible.append((score,names))
    got=handread.deck_constrained(L,cards,cards,ui=list(ui),costs=costs)
    if not feasible:
        assert not got['ui_consistent'] and got['cards']==[None]*4
    else:
        expected=max(feasible,key=lambda x:x[0])[1]
        assert tuple(got['cards']+[got['next']])==expected
        for i,n in enumerate(expected):
            actual=(got['probs']+[got['next_prob']])[i]
            assert actual==round(float(probs[i,cards.index(n)]),4)
print('PASS all81 affordability masks against independent balance/assignment oracle; full probabilities unchanged')
for ui,badcost in ((['coloured','greyed','coloured','greyed'],dict.fromkeys(cards,3)),
                   (['unknown']*4,costs),(['coloured']*3,costs),(['coloured']*4,{}),
                   (['coloured']*4,[]),(['coloured']*4,dict.fromkeys(cards,float('nan')))):
    got=handread.deck_constrained(L,cards,cards,ui=ui,costs=badcost)
    assert got['ui_consistent'] is False and got['cards']==[None]*4 and got['probs']==[0.]*4
print('PASS impossible/same-cost mixed UI and malformed cost/UI inputs fail closed')
for _ in range(20):
    v=rng.normal(size=(5,6));assert handread.deck_constrained(v,cards,cards)==old.deck_constrained(v,cards,cards)
print('PASS20 random no-UI legacy byte-value parity controls')
# Force low classifier probability for every affordable alternative. Constraint must NOT manufacture confidence.
D=['Giant','Fireball','Archers','Musketeer','Minions','Valkyrie','Cannon','MiniPekka']
C=dict(Giant=5,Fireball=4,Archers=3,Musketeer=4,Minions=3,Valkyrie=4,Cannon=3,MiniPekka=4)
v=np.full((5,9),-10.)
for i,n in enumerate(['Giant','Fireball','Valkyrie','Musketeer','Minions']):v[i,D.index(n)]=8.
v[2,D.index('Archers')]=4.      # ~.018, below unchanged .1 identity gate
x=handread.deck_constrained(v,D,D,ui=['greyed','greyed','coloured','greyed'],costs=C)
assert x['cards'][2]=='Archers' and x['probs'][2]<.1
print('PASS cost constraint never boosts a low full-softmax confidence to the acceptance threshold')
cache=np.load(R/'hud-logits-s37-30.npz');meta=json.loads((R/'hud-logits-s37-30.json').read_text())
for n,L in zip(cache['indices'],cache['logits']):
    row=next(r for r in meta['rows'] if r['n']==n)
    legacy=handread.deck_constrained(L,meta['cards'],meta['deck'])
    got=handread.deck_constrained(L,meta['cards'],meta['deck'],ui=row['ui'],costs=meta['costs'])
    assert legacy==row['baseline'] and got==row['candidate']
    slot=row['slot'];assert got['cards'][slot]==row['truth']
    if n==1082:assert got['probs'][slot]<.1
    else:assert got['probs'][slot]>=.1
print('PASS30 exact-pinned model/JPEG-cache cases:14Archers candidates,1retained low confidence,15accepted-target controls')
