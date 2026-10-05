"""Constructed group games with accepted own history before Mirror.

This deterministic fixture controller is separate from the unchanged C56 policy.
These games cannot satisfy the final human-corpus or native-controller gates.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import time

import clasher_core
import numpy as np
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import ContractV5ObservationBuilder, ContractV5ActionMaskBuilder
from clasher.rl.public_action_mask import PublicActionMaskInput
from diagnostics import detail
from differential import battle_digest, config, snapshot
from stage2 import fingerprint
from stage2_matches import battle


def same(b, r):
    words, index = r.rng_state()
    return battle_digest(b) == r.digest() and b.rng.getstate()[1] == tuple(words)+(index,)


def game(case, cards, cfg, builder):
    rng = random.Random(660100+case)
    decks=[]
    for seat in (0, 1):
        focal=[cards[(case*3+seat+k)%len(cards)] for k in range(min(4,len(cards)))]
        deck=list(dict.fromkeys(focal+['Knight','Musketeer','Zap','Cannon','Archers','Giant','Fireball']))[:8]
        rng.shuffle(deck); decks.append(deck)
    ep=dict(seed=661000+case,decks=decks)
    b=battle(ep,builder.loader); r=clasher_core.BattleState(snapshot(b,cfg))
    masks=ContractV5ActionMaskBuilder(builder); space=DiscreteTileActionSpace()
    actions=[]; imports=[]; pcpu=rcpu=0.0; accepted=Counter()
    seat_accepted=[Counter(),Counter()]
    for t in range(6001):
        if b.game_over: break
        if t>=90 and t%20==0:
            for seat in (0,1):
                packet=builder.build_public(b,seat)
                mask=masks.build(PublicActionMaskInput.from_confidence_observation(packet))
                available=[(slot,name) for slot,name in enumerate(b.players[seat].hand) if name and (name!='Mirror' or b.resolve_card_play(seat,name) is not None)]
                desired=min(available,key=lambda row:(row[1] not in cards,seat_accepted[seat][row[1]],row[0]))[0] if available else None
                # Rotate slot priority; rank legal destinations near alternating
                # bridge lanes. Spell destinations follow the visible front troop.
                legal=np.flatnonzero(mask[:space.no_op_action])
                ranked=[]
                for action in legal:
                    decoded=space.decode_action(int(action),seat)
                    slot=decoded.slot; name=b.players[seat].hand[slot]
                    if slot!=desired:continue
                    pos=decoded.position
                    x=(4.5,13.5)[(t//160+seat+case)%2]
                    y=13.5 if seat==0 else 18.5
                    effective=b.resolve_card_play(seat,name)
                    if effective is not None and effective[2] is not None:
                        targets=[e for e in b.entities.values() if e.player_id!=seat and e.is_alive and type(e).__name__=='Troop']
                        if targets:x,y=targets[0].position.x,targets[0].position.y
                        else:y=25.5 if seat==0 else 6.5
                    ranked.append((((slot-t//20-seat)%4,(pos.x-x)**2+(pos.y-y)**2,int(action)),name,pos))
                if not ranked:continue
                key,name,pos=min(ranked,key=lambda row:row[0])
                pa=b.deploy_card(seat,name,pos); ra=r.apply_action(seat,name,pos.x,pos.y)
                actions.append([t,seat,key[2],name,pos.x,pos.y,pa])
                if pa!=ra or not same(b,r):return dict(ok=False,kind='action',episode=ep,actions=actions,**detail(b,r))
                if pa:
                    accepted[name]+=1
                    seat_accepted[seat][name]+=1
        if t>=100 and t%400==100:
            copy=b.clone(); imported=clasher_core.BattleState(snapshot(b,cfg)); parent=battle_digest(b)
            if not same(copy,imported):return dict(ok=False,kind='import',episode=ep,actions=actions,**detail(copy,imported))
            start=time.process_time()
            for _ in range(100): child=imported.clone()
            clone_us=(time.process_time()-start)*1e4
            for _ in range(80):
                copy.step();child.step()
                if not same(copy,child):return dict(ok=False,kind='continuation',root_tick=t,episode=ep,actions=actions,**detail(copy,child))
            assert parent==battle_digest(b)==imported.digest()
            imports.append(dict(tick=t,clone_us=clone_us,continuation_ticks=80))
        start=time.process_time();b.step();pcpu+=time.process_time()-start
        start=time.process_time();r.step();rcpu+=time.process_time()-start
        if not same(b,r):return dict(ok=False,kind='tick',episode=ep,actions=actions,**detail(b,r))
    return dict(ok=b.game_over,terminal=b.game_over,ticks=b.tick,episode=ep,actions=actions,
                imports=imports,accepted=dict(accepted),python_cpu=pcpu,rust_cpu=rcpu,digest=battle_digest(b))


def main():
    p=argparse.ArgumentParser();p.add_argument('--cards',nargs='+',required=True)
    p.add_argument('--games',type=int,default=12);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    pins=dict(source=fingerprint(),native=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest(),driver=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out=dict(pins=pins,cards=args.cards,games=args.games,results={})
    if args.output.exists():
        old=json.loads(args.output.read_text());assert all(old[k]==out[k] for k in ('pins','cards','games'));out=old
    builder=ContractV5ObservationBuilder()
    cfg=config(tuple(dict.fromkeys(args.cards+['Knight','Musketeer','Zap','Cannon','Archers','Giant','Fireball'])))
    for case in range(args.games):
        if out['results'].get(str(case),{}).get('ok'):continue
        result=game(case,args.cards,cfg,builder)
        assert fingerprint()==pins['source'],'source changed during gate'
        out['results'][str(case)]=result
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(args.output)
        print(case,{k:v for k,v in result.items() if k not in ('actions','python','rust','field_diff')},flush=True)
        if not result['ok']:raise SystemExit(1)
    print('PASS',args.games,flush=True)


if __name__=='__main__':main()
