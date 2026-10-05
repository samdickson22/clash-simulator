"""Truth is used only by this verifier, never by the posterior."""
import json
from pathlib import Path
import time
import numpy as np
from c56_controller import resources
from stage2_matches import battle
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import champion_ability_cost
from derived_public_state import DerivedPublicState, PublicEvent
from decks import catalogs
from qualify import write

HERE=Path(__file__).resolve().parent


def assert_truth(tracker,b,seat):
    p=b.players[seat]
    assert tracker.elixir==p.elixir, ('elixir',b.tick,seat,tracker.elixir,p.elixir)
    assert tracker.refill==p.next_card_refill_cooldown_ms, ('refill',b.tick,tracker.refill,p.next_card_refill_cooldown_ms)
    d=tracker.derived()
    key=lambda n:n or ''
    if d['hand'] is not None:
        assert sorted(d['hand'],key=key)==sorted(p.hand,key=key),('hand',b.tick,d,p.hand)
    if d['cycle'] is not None:
        assert d['cycle']==tuple(p.cycle_queue),('queue',b.tick,d,list(p.cycle_queue))
    truth_hand=sorted(tracker.ids[n] if n else 0 for n in p.hand)
    truth_queue=[tracker.ids[n] for n in p.cycle_queue]
    assert np.any(np.all(tracker.states[:,:4]==truth_hand,axis=1)&np.all(tracker.states[:,4:4+len(truth_queue)]==truth_queue,axis=1)),('lost truth',b.tick)
    return int(d['hand'] is not None),int(d['cycle'] is not None)


def full_games():
    builder,_,_,bots=resources();cats=catalogs();prior=cats['train']
    costs={n:float(builder.loader.get_card(n).mana_cost) for d in prior['decks'] for n in d['cards']}
    decks=prior['decks']
    chosen=[]
    for champion in ('ArcherQueen','MightyMiner','Goblinstein'):
        chosen.extend(sorted((d for d in decks if champion in d['cards']),key=lambda d:-d['frequency'])[:2])
    chosen+=sorted(decks,key=lambda d:-d['frequency'])[:2]
    out=dict(complete=False,prior_decks=len(decks),prior_frequency=sum(d['frequency'] for d in decks),games=[])
    space=DiscreteTileActionSpace()
    for i,deck in enumerate(chosen):
        rng=np.random.default_rng(880100+i)
        ep=dict(seed=880200+i,decks=[rng.permutation(deck['cards']).tolist(),rng.permutation(chosen[(i+3)%len(chosen)]['cards']).tolist()])
        b=battle(ep,builder.loader);trackers=[DerivedPublicState(prior,costs) for _ in (0,1)];events=[[],[]]
        counts=[0,0];abilities=0;checks=0;start=time.perf_counter()
        while not b.game_over:
            if b.tick>=90 and b.tick%5==0:
                for seat in (0,1):
                    a=bots[('balanced','pressure','defense')[(i+seat)%3]].select_action(builder.build_public(b,seat))
                    if b.can_activate_champion_ability(seat):
                        champ=next(n for n in ep['decks'][seat] if n in ('ArcherQueen','MightyMiner','Goblinstein'))
                        assert space.apply_action(b,seat,2305)
                        events[seat].append(PublicEvent(b.tick,'ability',champ,champion_ability_cost(champ,loader=builder.loader)));abilities+=1
                    if a<2304:
                        n=b.players[seat].hand[a//576]
                        if space.apply_action(b,seat,a):events[seat].append(PublicEvent(b.tick,'card',n))
            # Public input ends at timestamped visible events. Truth never enters update.
            for seat in (0,1):
                trackers[seat].update(b.tick,events[seat])
                h,c=assert_truth(trackers[seat],b,seat);counts[0]+=h;counts[1]+=c;checks+=1
            b.step()
        for seat in (0,1):
            trackers[seat].update(b.tick,events[seat]);assert_truth(trackers[seat],b,seat)
        out['games'].append(dict(seed=ep['seed'],ticks=b.tick,checks=checks,hand_determined=counts[0],cycle_determined=counts[1],abilities=abilities,wall=time.perf_counter()-start,elixir_error=0))
        write(HERE/'derived-games.json',out);print(out['games'][-1],flush=True)
    out['complete']=True;write(HERE/'derived-games.json',out)


if __name__=='__main__':full_games()
