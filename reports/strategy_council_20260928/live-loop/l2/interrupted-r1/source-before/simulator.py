"""Clean-state pairs with the registered seeds, deck multisets and native opening order."""
import argparse,json,time,hashlib,os,traceback
from pathlib import Path
from types import SimpleNamespace
from bootstrap import setup,HERE,COUNCIL
from offline_loop import progress,write,append,storage_guard

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['p16','c56'],required=True);ap.add_argument('--wait',action='store_true');ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    r,_=setup(a.mode)
    import numpy as np
    from stage2_matches import battle
    from clasher.rl.action_space import DiscreteTileActionSpace
    space=DiscreteTileActionSpace();bld=r.builder if a.mode=='c56' else r.loaded.builder
    schedule=json.loads((HERE/'schedule.json').read_text())['matches'];matches=[m for m in schedule if m['mode']==a.mode]
    prior=dict(decks=[dict(cards=list(d)) for d in sorted({tuple(sorted(deck)) for ep in schedule for deck in ep['decks']})])
    if a.mode=='c56':
        from deadline_player import DeadlinePublicPlanner
        from fair_player import observe
        from derived_public_state import PublicEvent
        bots=r.bots
    else:
        from public_planner import observe
        from tuning import Config
        from clean_p16 import CleanP16 as Planner
        from clasher.rl.contract_v5 import ContractV5ObservationBuilder
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
        ob=ContractV5ObservationBuilder(card_loader=bld.loader)
        bots={s:PublicScriptedOpponent(ob,style=s,card_scope='c56') for s in ('balanced','pressure','defense')}
        prior=dict(decks=sum([json.loads(p.read_text())['decks'] for p in [COUNCIL/'m0/data/roles_v2/training.json',COUNCIL/'m0/data/roles_v2/development.json',COUNCIL/'pilot/hog26-deployment.json']],[]))
    folder=HERE/('simulator-smoke-'+a.mode if a.smoke else 'simulator');folder.mkdir(exist_ok=True)
    if a.smoke:matches=[dict(matches[0],pair=-1,seed=1967040401)]
    for ep in matches:
        path=folder/f"pair-{ep['pair']:02d}.json"
        if path.exists():continue
        origin=(HERE/'smoke'/'pair--1'/'setup-evaluation-only.json') if a.smoke else HERE/'native'/f"pair-{ep['pair']:02d}"/'setup-evaluation-only.json'
        while not origin.exists():
            if not a.wait:raise RuntimeError('Native opening order unavailable')
            time.sleep(5)
        setup_state=json.loads(origin.read_text())['initial']
        names={bld.loader.get_card(c)._raw_entry['id']:c for d in ep['decks'] for c in d}
        decks=[]
        for side in (0,1):
            p=next(p for p in setup_state['players'] if p['owner']==side)
            hand=[None]*4
            for c in p['hand']:hand[c['handIndex']]=names[c['cardId']]
            decks.append(hand+[names[c['cardId']] for c in p['cycle']])
            assert sorted(decks[-1])==sorted(ep['decks'][side])
        b=battle(dict(seed=ep['seed'],decks=decks),bld.loader)
        while b.tick<setup_state['tick']:b.step()
        # Initial public elixir/hand alignment is evaluator setup, never a pixel-player input.
        if a.mode=='c56':p=DeadlinePublicPlanner(r,prior,ep['seed']+31)
        else:p=Planner(r,prior,Config('mixture',opponent='mixture'),seed=ep['seed']+31)
        events=[];rows=[];actions=[];reject=[0,0];start=time.perf_counter();decision=0
        while not b.game_over:
            if b.tick%10==0:
                t=time.perf_counter()
                if a.mode=='c56':act,searched=p.decide(observe(b,bld,1,events),decision*2,deadline=t+.2)
                else:act,_=p.decide(observe(SimpleNamespace(battle=b,structured_obs_builder=bld),1),decision*2)
                elapsed=time.perf_counter()-t
                bot=bots[ep['style']]
                packet=bot.builder.build_public(b,0)
                other=int(bot.select_action(packet))
                rows.append([b.tick,elapsed]);decision+=1
                for seat,action in [(0,other),(1,int(act))]:
                    if action>=2304:continue
                    card=b.players[seat].hand[action//576];ok=space.apply_action(b,seat,action);reject[seat]+=not ok
                    actions.append([b.tick,seat,action,card,bool(ok)])
                    if ok and seat==0 and a.mode=='c56':events.append(PublicEvent(b.tick,'card',card))
            b.step()
        write(path,dict(**ep,opening_decks=decks,terminal=True,tick=b.tick,winner=b.winner,win=int(b.winner==1),
            score=.5 if b.winner is None else float(b.winner==1),rejected=reject,timings=rows,actions=actions,seconds=time.perf_counter()-start,
            source_manifest=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest() if (HERE/'manifest.json').exists() else None))
        storage_guard();progress(f"Simulator pair {ep['pair']} complete, terminal tick {b.tick}; no interim aggregate strength inspection.")
    progress(f'Simulator {a.mode} worker finished.')
if __name__=='__main__':
    try:main()
    except BaseException:progress('Simulator exception: '+traceback.format_exc());raise
