"""s37 exact original r6/5361 timeline, symbolic own-packet projection, and later isolated decoder branches."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=HERE/'field_reservation_test.py';nodes=[]
for n in ast.parse(p.read_text()).body:
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='results' for t in n.targets):break
    nodes.append(n)
ns={'__file__':str(p),'__name__':'fixture_only'}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
ROOT=ns['ROOT'];WAIT=ns['WAIT'];Decision=ns['Decision']
pin=ROOT/'parity/tree-15117b86b/bot/live/translate.py'
assert hashlib.sha256(pin.read_bytes()).hexdigest()=='5361deb0dbe166fd751bbb3ed3d7a710acc23cc6cbd36cb8eaaee5eb1d9458d8'
assert Path(ns['LiveTranslator'].step.__code__.co_filename if hasattr(ns['LiveTranslator'],'step') else
            ns['LiveTranslator'].hud.__code__.co_filename).resolve()==pin.resolve()
base=ROOT/'packages/handsync-availability-r6/live/loop/handsync.py'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='b89c76a17c8ea9789dd4240d352ed151a3d8c483a66ac2f4bb2a7527385cbe34'
spec=importlib.util.spec_from_file_location('released_r6_reference',base)
r6=importlib.util.module_from_spec(spec);spec.loader.exec_module(r6)
D=[json.loads(x) for x in (ROOT/'runs/s37/decisions.jsonl').read_text().splitlines()]
REF={d['poll']:d for d in D if (d.get('stats')or{}).get('tap_guard')}
observed=[]
original_make=ns['make_session']
def observe(module,actions):
    st,t=original_make(module,actions)
    st.rt.R.builder.token_id=lambda name,namespace=None: st.own_deck.index(name)+1
    original=st.tr.information
    def information(record):
        info=original(record)
        # Execute the deployed observation's exact own-hand projection using named test tokens; no board claim.
        names=list(info.own['hand'][:4])+[None]*(4-len(info.own['hand'][:4]))
        names.append(info.own['cycle'][0] if info.own['cycle'] else None)
        info.packet.observation.hand_ids[:]=[0 if n is None else st.rt.R.builder.token_id(n) for n in names]
        return info
    st.tr.information=information
    old=st.player.inner.act
    def act(view):
        if view.tick in REF:
            d=REF[view.tick];slot=d['stats']['action']//576;tr=st.tr.own_tracker
            ids=view.reserved.packet.observation.hand_ids.tolist()
            decode=lambda i:st.own_deck[i-1] if i else None
            named=[decode(i) for i in ids]
            assert named[:4]==view.reserved.own['hand']
            observed.append(dict(n=d['n'],poll=view.tick,original_action=d['stats']['action'],slot=slot,
             emitted=d['action'],reason=d['stats']['tap_guard'],can_act=view.can_act,
             model_hand=copy.deepcopy(st._rec['hand']),tracker_hand=tr.hand,
             tracker_queue=list(tr.hyps[tr.best].queue),recent_play_lru=list(tr.played),
             sync_evidence={str(k):v for k,v in tr._sync.items()},busy=list(tr.busy),
             pending=[c.__dict__ for c in view.pending],physical_own=copy.deepcopy(view.info.own),
             reserved_own=copy.deepcopy(view.reserved.own),packet_names=named,
             packet_scope='exact own-hand name projection with test token IDs; full board packet was not persisted'))
        return old(view)
    st.player.inner.act=act
    return st,t
ns['make_session']=observe
baseline=ns['replay'](r6,ROOT/'runs/s37')
assert not baseline['errors'] and baseline['guard_count']==15, (baseline['errors'][:3],baseline['guard_count'])
assert len(baseline['inputs'])==baseline['diagnostics']['executed']==27
assert len(observed)==15
for r in observed:
    assert not r['pending'] and r['can_act'] and r['slot']==2
    assert r['packet_names'][2]==r['tracker_hand'][2]
    if r['n']==1082:
        assert r['reason']=='coloured_unverified' and r['tracker_hand'][2]=='Valkyrie'
    else:
        assert r['reason']=='coloured_mismatch' and r['tracker_hand'][2]=='Archers'
        assert r['model_hand']['cards'][2]=='Valkyrie' and r['model_hand']['ui'][2]=='coloured'
    print('PASS original identity refusal',r['n'],r['original_action'],r['tracker_hand'][2],
          r['model_hand']['cards'][2],r['model_hand']['probs'][2],r['reason'])
out=ROOT/'packages/handsync-identity-r7/original-identity-timeline.json'
out.write_text(json.dumps(dict(baseline=baseline,refusal_timeline=observed,
    deployed_translate_sha256=hashlib.sha256(pin.read_bytes()).hexdigest(),
    frozen_r6_sha256=hashlib.sha256(base.read_bytes()).hexdigest()),indent=2)+'\n')
print('receipt:',out)
