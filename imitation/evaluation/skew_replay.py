"""Replay eight Stage 5 seeded C56 script worlds through the serving boundary.

The deadline player is called on its non-search cadence to obtain its actual D1
row without requiring any trained model. Scripts drive the recorded game; rows
are compared to independent SidecarObserver output, including dtype/shape/bytes.
A second pass replays the recorded public stream and checks the same row hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .paths import setup, COUNCIL
setup()
from .search import ImitationDeadlinePlayer
from .d1 import D1Tracker, model_packet
from fair_player import Resources, observe
from derived_public_state import PublicEvent as SearchEvent
from sidecar_observer import SidecarObserver
from stage2_matches import battle
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskInput


def digest(row):
    h=hashlib.sha256()
    for key in sorted(row):
        a=np.asarray(row[key])
        h.update(key.encode());h.update(a.dtype.str.encode());h.update(str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    r=Resources();prior=json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())
    decks=prior['decks'];chosen=[]
    for champion in ('ArcherQueen','MightyMiner','Goblinstein'):
        chosen.extend(sorted((d for d in decks if champion in d['cards']),key=lambda d:-d['frequency'])[:2])
    chosen+=sorted(decks,key=lambda d:-d['frequency'])[:2]
    space=DiscreteTileActionSpace()
    for i,deck in enumerate(chosen):
        target=args.output/f'game-{i}.json'
        if target.exists(): continue
        rng=np.random.default_rng(880100+i)
        ep=dict(seed=880200+i,decks=[rng.permutation(deck['cards']).tolist(),
                                   rng.permutation(chosen[(i+3)%8]['cards']).tolist()])
        b=battle(ep,r.builder.loader);seat=i%2
        player=ImitationDeadlinePlayer(r,prior,ep['seed'],None,seat,ep['decks'][seat])
        hashes=[];actions=[]; tensor_rows=[]
        with SidecarObserver(r.builder) as side:
            side.audit_counters={'opponent_elixir_topup_total':0.};side(b,seat,None)
            while not b.game_over:
                if b.tick>=90 and b.tick%5==0:
                    side(b,seat,None)
                    enemy=[SearchEvent(e['tick'],e['kind'],e['name'],e['amount'])
                           for e in side.public_events if e['seat']!=seat]
                    player.decide(observe(b,r.builder,seat,enemy),1,public_events=side.public_events)
                    actual,expected=player.last_d1,side.rows[-1]
                    assert actual.keys()==expected.keys()
                    for key in actual:
                        aa,bb=np.asarray(actual[key]),np.asarray(expected[key])
                        assert aa.dtype==bb.dtype and aa.shape==bb.shape and aa.tobytes()==bb.tobytes(),(i,b.tick,key)
                    hashes.append([b.tick,digest(actual)])
                    packet=r.builder.build_public(b,seat)
                    mask=r.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                    packed=model_packet(packet,mask)
                    tensor_rows.append({**{'packet_'+k:v for k,v in packed.items()},
                                        **{'serve_'+k:v for k,v in actual.items()},
                                        **{'train_'+k:v for k,v in expected.items()}})
                    for actor in (0,1):
                        a=int(r.bots[('balanced','pressure','defense')[(i+actor)%3]].select_action(r.builder.build_public(b,actor)))
                        if b.can_activate_champion_ability(actor):
                            ok=space.apply_action(b,actor,2305);assert ok
                            actions.append([b.tick,actor,2305,True])
                        if a<2304:
                            ok=space.apply_action(b,actor,a);actions.append([b.tick,actor,a,bool(ok)])
                b.step()
            events=list(side.public_events)
        # Replay recorded immutable stream, not simulator truth, at each decision.
        replay=D1Tracker(r.builder,r.costs,seat,ep['decks'][seat]);offset=0
        for tick,want in hashes:
            # Same-tick actions occur after the row. Include only events before row.
            while offset<len(events) and events[offset]['tick']<tick: offset+=1
            got=replay.update(tick,events[:offset])
            assert digest(got)==want,(i,tick,'recorded stream replay')
        tensors=args.output/f'game-{i}-tensors.npz'
        assert not tensors.exists()
        np.savez_compressed(tensors,costs=r.builder.card_stat_features[:,0]*10,
                            **{k:np.asarray([row[k] for row in tensor_rows]) for k in tensor_rows[0]})
        value=dict(tensor_file=tensors.name,tensor_sha256=hashlib.sha256(tensors.read_bytes()).hexdigest(),plumbing_only=True,seed=ep['seed'],decks=ep['decks'],seat=seat,terminal=b.game_over,
                   ticks=b.tick,rows=len(hashes),fields=sorted(player.last_d1),row_hashes=hashes,
                   public_events=events,actions=actions,sidecar_bytes_equal=True,recorded_stream_equal=True,
                   note='D1 row equality only; model feature-tensor equality separately required')
        with open(target,'x') as f: json.dump(value,f)
        print(json.dumps({k:value[k] for k in ('seed','ticks','rows','sidecar_bytes_equal','recorded_stream_equal')}),flush=True)
    with open(args.output/'done.json','x') as f:json.dump({'complete':True,'games':8},f)


if __name__=='__main__': main()
