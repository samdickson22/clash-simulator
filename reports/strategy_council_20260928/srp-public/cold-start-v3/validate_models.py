"""Synthetic public-template coverage and policy-input parity, no scored games."""
import json
import numpy as np
from pathlib import Path
from support import Context, TRAIN_DECKS, cl_eval, maybe_silence_stdio
from public_planner import Resources, PublicPlanner, DeckBelief, observe
from clasher.arena import Position
from clasher.rl.public_action_mask import PublicActionMaskInput


def main():
    c=Context(); r=Resources(c)
    prior=json.loads(TRAIN_DECKS.read_text())
    env=c.envs('holdout',193001)[0]
    identities=set(); count=0
    for card in r.costs:
        with maybe_silence_stdio(True):
            env.reset(seed=193001)
        b=env.battle
        for seat in (0,1):
            b.players[seat].elixir=10
            b.players[seat].hand[0]=card
            b.deploy_card(seat,card,Position(4.5,12.5 if seat==0 else 19.5))
        for tick in range(250):
            if tick==25:
                for e in list(b.entities.values()):
                    if getattr(e.card_stats, 'name', '')=='IceGolemite':
                        e.take_damage(e.hitpoints)
                    elif getattr(e.card_stats, 'name', '')=='DarkPrince':
                        e.take_damage(2000)
            b.step()
            if tick%5:
                continue
            for seat in (0,1):
                info=observe(env,seat)
                root,payload=r.root(info,dict(elixir=6,hand=['Knight','Archers','Giant','Musketeer'],
                                             cycle=['Log','Cannon','Zap','Skeletons'],refill=0),
                                    np.random.default_rng(tick))
                identities.update((c.loaded.builder.token_names[int(t)],int(np.argmax(f[4:9])))
                    for t,f in zip(info.packet.observation.entity_ids[info.packet.observation.entity_mask],
                                   info.packet.observation.entity_features[info.packet.observation.entity_mask]))
                for e in json.loads(payload)['entities']:
                    if e['hp'] < e['stats']['max_hp']:
                        assert e['shield']==0
                count+=1
            if tick==50:
                info=observe(env,0)
                mask=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
                planner=PublicPlanner(r,prior,policy=True)
                got=planner.policy_top(info,mask)
                _,_,original_mask,output=cl_eval._policy_step(c.loaded,env,0,
                    state=c.loaded.model.initial_state(1,device=c.device),
                    previous_action=r.no_op,previous_reward=0.,episode_start=False,
                    deterministic=True,device=c.device)
                legal=np.flatnonzero(original_mask)
                probs=output.distribution().probs.detach().numpy().reshape(-1)
                expected=legal[np.argsort(-probs[legal],kind='stable')[:8]].tolist()
                assert got==expected,(card,got,expected)
    # Check the complete public resource timeline independently of combat.
    from clasher.player import PlayerState
    from collections import deque
    deck=prior['decks'][0]['cards']
    player=PlayerState(1,deck=deck,hand=deck[:4],cycle_queue=deque(deck[4:]))
    belief=DeckBelief(prior,r.costs)
    stats={name:stats for name,stats in r.bot.cards.values()}
    history=[]
    for tick in range(6002):
        if tick:
            player.regenerate_elixir(.05,.93 if tick>4800 else 1.4 if tick>2400 else 2.8)
            player.tick_card_refill(1000 if tick<2400 else 500 if tick<4800 else 350)
        if tick%5==0:
            card=next((x for x in player.hand if x and player.can_play_card(x,stats[x])),None)
            if card:
                assert player.play_card(card,stats[card])
                history.append((tick,card))
        belief.update(tick,tuple(history))
        assert abs(belief.elixir_units/10000-player.elixir)<1e-8
        assert belief.refill==player.next_card_refill_cooldown_ms
        actual=np.zeros(12,dtype=np.int16)
        actual[:4]=[belief.ids[x] if x else 0 for x in player.hand]
        actual[4:4+len(player.cycle_queue)]=[belief.ids[x] for x in player.cycle_queue]
        assert np.any(np.all(belief.states==actual,axis=1))
    result=dict(public_roots=count,policy_top8_parity_cases=len(r.costs),resource_timeline_ticks=6002,
                public_identities=sorted(identities),shield_consistency=True)
    (Path(__file__).resolve().parent/'results/model-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MODEL VALIDATION PASS',result,flush=True)


if __name__=='__main__':
    main()
