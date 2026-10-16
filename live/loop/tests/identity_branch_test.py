"""Original field prefixes with ONE corrected-decoder branch, then stop: no counterfactual full-battle claim."""
import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import numpy as np
HERE=Path(__file__).resolve().parent
p=HERE/'field_reservation_test.py';nodes=[]
for n in ast.parse(p.read_text()).body:
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='results' for t in n.targets):break
    nodes.append(n)
ns={'__file__':str(p),'__name__':'fixture_only'}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
import handread
ROOT=ns['ROOT'];R=ROOT/'packages/handsync-identity-r7'
base=ROOT/'packages/handsync-availability-r6/live/loop/handsync.py'
spec=importlib.util.spec_from_file_location('branch_frozen_r6',base);r6=importlib.util.module_from_spec(spec);spec.loader.exec_module(r6)
D=list(map(json.loads,(ROOT/'runs/s37/decisions.jsonl').read_text().splitlines()))
P=list(map(json.loads,(ROOT/'runs/s37/perception.jsonl').read_text().splitlines()))
E=list(map(json.loads,(ROOT/'runs/s37/events.jsonl').read_text().splitlines()))
REF={d['n']:d for d in D if (d.get('stats')or{}).get('tap_guard')}
A={d['poll']:(d.get('stats')or{}).get('action',d['action']) for d in D}
meta=json.loads((R/'hud-logits-s37-30.json').read_text());cache=np.load(R/'hud-logits-s37-30.npz')
LG={int(n):L for n,L in zip(cache['indices'],cache['logits'])}

def branch(n,correction=None):
    s,t=ns['make_session'](r6,A)
    s.tr.clock.anchor(0,next(e['ts_ms'] for e in E if e.get('ev')=='match_start'))
    for original in P:
        r=copy.deepcopy(original);r.pop('tick',None)
        ns['ownplay'].dedupe_own_events(r,s)
        if r['n']==n and correction is not None:
            r['hand'].update({k:correction[k] for k in ('cards','probs','next','next_prob','raw')})
        before=s.ch.submitted
        d=s.step(r)
        if original['n']==n:return s,d,before
    raise AssertionError('missing branch frame')

rows=[]
for n,ref in REF.items():
    original_action=ref['stats']['action'];slot=original_action//576
    old,d,before=branch(n)
    assert d.action==ns['WAIT'] and d.stats['tap_guard']==ref['stats']['tap_guard']
    assert old.ch.submitted==before
    ui=next(r['hand']['ui'] for r in P if r['n']==n)
    correction=handread.deck_constrained(LG[n],meta['cards'],meta['deck'],ui=ui,costs=meta['costs'])
    s,d,before=branch(n,correction)
    if n==1082:
        assert d.action==ns['WAIT'] and d.stats['tap_guard']=='coloured_unverified' and s.ch.submitted==before
        assert correction['cards'][slot]=='Valkyrie' and correction['probs'][slot]<.1
        print('PASS original true-Valkyrie uncertainty still refused',n)
    else:
        assert correction['cards'][slot]=='Archers' and correction['probs'][slot]>=.1
        assert d.action==original_action and s.ch.submitted==before+1
        assert s.ch.pending[-1].card=='Archers' and s.ch.pending[-1].action==original_action
        assert not (d.stats or {}).get('tap_guard')
        Tap=ns['m']['tap_ns']['AdbTaps'];tap=Tap.__new__(Tap);tap.n=0;tap.sent={};tap.p=types.SimpleNamespace(stdin=io.StringIO())
        _,xy,target=ns['m']['C'].action_target(d.action);tap.play(xy,target)
        expected=f'input tap {xy[0]} {xy[1]}; input tap {target[0]} {target[1]}; echo __ack 1\n'
        assert tap.n==1 and tap.p.stdin.getvalue()==expected
        print('PASS one-stop original prefix branch',n,original_action,'verifiedArchers',correction['probs'][slot])
    rows.append(dict(n=n,original_action=original_action,original_reason=ref['stats']['tap_guard'],
                     correction=correction,emitted=d.action,new_submissions=s.ch.submitted-before,
                     pending=[c.__dict__ for c in s.ch.pending]))
(R/'identity-branch-receipt.json').write_text(json.dumps(dict(rows=rows,
 limitation='Each independent branch stops immediately after the prospective action. Prefix uses original logs; correction uses exact-model retained-JPEG re-decode, NOT original uncompressed logits. Original15/42gate remainsFAILED.'),indent=2)+'\n')
print('15 independent original-input negatives + candidate branches passed; no continuation after new action')
