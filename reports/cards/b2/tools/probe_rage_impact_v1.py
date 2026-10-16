"""Eight RageDamage-vs-dash continuations, unchanged semantic-v1 comparison.

Observe the real impact source label; friendly haste remains governed separately.
This is a bounded guard witness, not a new broad sweep or applicability rule.
"""
import json
from pathlib import Path
import sys
import traceback

if not __debug__ or sys.flags.optimize:raise SystemExit('optimized probe forbidden')

from differential import config,initial,Position,clasher_core,battle_digest
import probe_dash_semantic_v1 as probe
from snapshot_contract_v1 import VERSION,fresh_troop_templates

LEADS=(6,8,9,10)


def collect():
    cards=tuple(dict.fromkeys(('Bandit','Rage')+probe.FILL));cfg=config(cards)
    original=probe.observe_effect_queries
    def observe(bandit,card,events):return original(bandit,'RageDamage',events)
    rows=[]
    try:
        probe.observe_effect_queries=observe
        for seat in (0,1):
            for lead in LEADS:
                try:row=dict(probe.one('Rage',probe.ENEMY,probe.P,lead,seat,cfg,cards),seat=seat)
                except Exception:row=dict(lead=lead,seat=seat,error=traceback.format_exc(limit=5))
                rows.append(row)
    finally:
        probe.observe_effect_queries=original
    return rows


def mirror_one(seat):
    cards=('Mirror','Rage')+probe.FILL;cfg=config(cards);b=initial(7,cards=cards)
    for player in b.players:
        player.elixir=10.0;player.hand=['Rage','Mirror','Knight','Giant']
        player.cycle_queue.clear();player.cycle_queue.extend(['Archers','Musketeer'])
    native=clasher_core.BattleState(probe.probe_snapshot(b,cfg))
    templates=fresh_troop_templates(json.loads(native.snapshot()))
    actions=[];ledger={};deltas={};first=None
    for tick in range(140):
        if tick in (0,4):
            card='Rage' if tick==0 else 'Mirror'
            point=probe.mirror((4.5,10.5) if tick==0 else (7.5,11.5),seat)
            py=bool(b.deploy_card(seat,card,Position(*point)));rs=bool(native.apply_action(seat,card,*point))
            actions.append([tick,seat,card,py,rs]);assert py and rs
        b.step();native.step(1)
        delta,applicability,raw=probe.full_compare(b,native,cfg)
        equal=native.digest()==battle_digest(b)
        for item in applicability:
            key=json.dumps(item,sort_keys=True)
            if key not in ledger:ledger[key]=dict(item,ticks=[])
            ledger[key]['ticks'].append(tick)
        for item in delta:
            key=json.dumps(item,sort_keys=True)
            if key not in deltas:deltas[key]=dict(item,tick=tick,digest_equal=equal)
        if (delta or not equal) and first is None:first=tick
    final=json.loads(native.snapshot())
    expired=(not any(e.is_alive and getattr(e.card_stats,'name',None)=='Rage' for e in b.entities.values())
             and not any(e['alive'] and e['stats']['name']=='Rage' for e in final['entities']))
    return dict(contract=VERSION,case='rage_mirror',seat=seat,ticks=140,actions=actions,
                first=first,differences=list(deltas.values()),applicability=list(ledger.values()),
                fresh_troop_templates=templates,expired=expired)


if __name__=='__main__':
    rows=[]
    if sys.argv[2:]==['--mirror']:
        for seat in (0,1):
            try:rows.append(mirror_one(seat))
            except Exception:rows.append(dict(case='rage_mirror',seat=seat,error=traceback.format_exc(limit=5)))
    else:
        assert len(sys.argv)==2
        rows=collect()
    with Path(sys.argv[1]).open('x') as out:json.dump(rows,out,indent=1)
    print(json.dumps([dict(seat=r['seat'],lead=r.get('lead'),first=r.get('first'),error=r.get('error'),
                           queries=r.get('gate_queries',[])) for r in rows]),flush=True)
