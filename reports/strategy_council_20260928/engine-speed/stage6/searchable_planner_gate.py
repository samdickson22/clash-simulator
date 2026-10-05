"""100 searchable calls: ten focal cards, both seats, five live threat ages.

Actor waits with ten elixir while the opponent's Knight and Musketeer advance.
The existing policy-proposal input guarantees one legal focal-card candidate.
This is a constructed core-parity gate, not fair-state reconstruction admission.
"""
import hashlib
import json
from pathlib import Path

import cloudpickle
import numpy as np
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, trace_digest
from clasher.rl.public_action_mask import PublicActionMaskInput
from c56_controller import CARDS, verify
from controller import EARLY, resources
from differential import Position, config, initial
from stage2 import fingerprint
import clasher_core

FOLDER=Path(__file__).resolve().parent
OUTPUT=FOLDER/'planner-search100-r4.json'


def native_candidates(planner, root, packet, seat, proposal):
    mask=planner.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
    ranked=planner.native.ranked_actions(root,seat,'balanced')
    pool=np.flatnonzero(mask[:2304])
    samples=planner.rng.choice(pool,min(planner.config.samples,len(pool)),replace=False).tolist()
    proposals=[ranked[0][0],2304]+[r[0] for r in ranked[:planner.config.script_top]]
    if mask[2305]:proposals.append(2305)
    proposals += [proposal]+samples
    return list(dict.fromkeys(int(a) for a in proposals if mask[int(a)])),mask


def main():
    native_path=Path(clasher_core.__file__).resolve()
    assert native_path.parent==FOLDER/'native'
    pins=dict(source=fingerprint(),native=hashlib.sha256(native_path.read_bytes()).hexdigest(),
              drivers={n:hashlib.sha256((FOLDER/n).read_bytes()).hexdigest()
                       for n in ('searchable_planner_gate.py','controller.py')})
    out=dict(pins=pins,required_calls=100,results={})
    if OUTPUT.exists():
        old=json.loads(OUTPUT.read_text());assert old['pins']==pins;out=old
    builder,meta,scripts,bots=resources();cfg=config(tuple(dict.fromkeys((*CARDS,*EARLY))))
    for index,card in enumerate(EARLY):
        for seat in (0,1):
            cards=(card,'Knight','Archers','Musketeer','Zap','Cannon','Giant','Fireball')
            b=initial(663000+index*2+seat,cards=cards)
            for player in b.players:player.elixir=10
            foe=1-seat;y=18.5 if seat==0 else 13.5
            assert b.deploy_card(foe,'Knight',Position(4.5,y))
            assert b.deploy_card(foe,'Musketeer',Position(5.5,y))
            for tick in (100,180,260,340,420):
                while b.tick<tick:b.step()
                key=f'{card}-{seat}-{tick}'
                if out['results'].get(key,{}).get('ok'):continue
                py=C56RolloutPlanner(builder,bots,seed=664000+index*1000+seat*500+tick)
                native=C56RolloutPlanner(builder,bots,seed=664000+index*1000+seat*500+tick,
                                        backend='native',native=scripts,native_config=cfg)
                root=native.import_root(b);parent=trace_digest(b)
                packet=builder.build_public(b,seat)
                mask=bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                slot=b.players[seat].hand.index(card)
                legal=np.flatnonzero(mask[slot*576:(slot+1)*576])+slot*576
                assert len(legal)>0,(key,'no focal legal action')
                proposal=int(legal[len(legal)//2])
                copy=b.clone();decoded=py.space.decode_action(proposal,seat)
                assert copy.deploy_card(seat,card,decoded.position),(key,'focal proposal rejected')
                try:
                    public=verify(b,root,builder,scripts,bots,seat);assert public['ok'],public
                    pc,pm=py.candidates(packet,policy_proposals=[proposal])
                    nc,nm=native_candidates(native,root,packet,seat,proposal)
                    assert pc==nc and np.array_equal(pm,nm),('candidate order',pc,nc)
                    assert len(pc)>1 and proposal in pc
                    pa=py.score_candidates(b,seat,pc,trace=True)
                    na=native.score_candidates(root,seat,nc,trace=True)
                    assert (pa,py.last)==(na,native.last),'planner action/score/trace mismatch'
                    assert trace_digest(b)==parent,'planner mutated Python root'
                    result=dict(ok=True,card=card,seat=seat,tick=tick,candidates=pc,action=pa,
                                focal_proposal=proposal,scores=py.last['scores'],root=parent,
                                trace_sha256=hashlib.sha256(json.dumps(py.last['traces']).encode()).hexdigest())
                except BaseException as exc:
                    OUTPUT.with_suffix('.failure.pkl').write_bytes(cloudpickle.dumps((b,seat)))
                    OUTPUT.with_suffix('.failure.json').write_text(json.dumps(dict(key=key,error=repr(exc),python=py.last,native=native.last),indent=2)+'\n')
                    raise
                assert fingerprint()==pins['source'],'source changed during gate'
                assert all(hashlib.sha256((FOLDER/n).read_bytes()).hexdigest()==h for n,h in pins['drivers'].items())
                out['results'][key]=result
                tmp=OUTPUT.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(OUTPUT)
                print('PASS',len(out['results']),key,'candidates',len(pc),flush=True)
    assert len(out['results'])==100
    print('PASS 100 searchable planner calls, every early card both seats',flush=True)


if __name__=='__main__':main()
