"""Fresh, fair-information diagnostic games with complete public telemetry.

The existing Stage 5 public reconstruction and S6 delay rollout implementation
are imported read-only. Opponent hand/order and live RNG never reach a planner.
"""
import argparse,gzip,hashlib,json,multiprocessing,os,random,socket,sys,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from .human import make_catalog,write
from .metrics import Game,archetype,extract
ROOT=Path(__file__).resolve().parents[4]
COUNCIL=ROOT/'reports/strategy_council_20260928'
RES=None;CAT=None;PRIOR=None;OPTIONS=None


def initialize():
    global RES,CAT,PRIOR
    sys.path[:0]=[str(ROOT/'engine-rs'),str(COUNCIL/'engine-speed/stage5')]
    import torch
    torch.set_num_threads(1)
    from fair_player import Resources
    RES=Resources();CAT=make_catalog(RES.builder)
    PRIOR=json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())


def run_game(case):
    from fair_player import PublicPlanner,observe
    from derived_public_state import PublicEvent
    from stage2_matches import battle
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    sys.path.insert(0,str(COUNCIL/'search-noise-s6'))
    import delay as dm
    from clasher.rl.public_observation import REAL_PLAY_ENTITY_FEATURE_INDICES
    start=time.monotonic();cpu=time.process_time()
    pair,seed,delay,own,other,style=case;seat=pair%2
    rng=random.Random(seed);own=list(own);other=list(other);rng.shuffle(own);rng.shuffle(other)
    decks=[own,other] if seat==0 else [other,own]
    b=battle(dict(seed=seed,decks=decks),RES.builder.loader)
    p=PublicPlanner(RES,PRIOR,seed+100000)
    channel=dm.CommandChannel(delay)
    p.core=dm.DelayAwarePlanner(RES.builder,RES.bots,backend='native',seed=seed+100001,
        native=RES.native,native_config=RES.config,config=C56SearchConfig(threads=1),
        command_delay=delay,delay_aware=bool(delay))
    ticks=[];globals_=[];hands=[];queues=[];entities=[];ids=[];offsets=[0];plays=[];events=[];actions=[]
    cols=sorted(REAL_PLAY_ENTITY_FEATURE_INDICES)
    def act(actor,action):
        if action>=2304:return False
        name=b.players[actor].hand[action//576];elixir=b.players[actor].elixir
        choice=p.core.space.decode_action(action,actor)
        ok=p.core.space.apply_action(b,actor,action)
        actions.append([b.tick,actor,int(action),name,bool(ok)])
        if actor==seat:
            x,y=choice.position.x,choice.position.y
            if seat==1:x,y=18-x,32-y
            plays.append(dict(tick=b.tick,card=name,x=x,y=y,accepted=bool(ok),elixir_before=elixir))
        elif ok: events.append(PublicEvent(b.tick,'card',name))
        return ok
    while not b.game_over and b.tick<OPTIONS['max_ticks']:
        if b.tick%5==0:
            ob=RES.builder.build_public(b,seat).observation
            ticks.append(b.tick);globals_.append(ob.global_features.copy());hands.append(ob.hand_ids.copy())
            q=list(b.players[seat].cycle_queue)
            queues.append([RES.builder.token_id(n,namespace='card_action') for n in q]+[0]*(8-len(q)))
            ef=ob.entity_features[ob.entity_mask][:,cols].copy();entities.append(ef)
            ids.append(ob.entity_ids[ob.entity_mask].copy());offsets.append(offsets[-1]+len(ef))
        if channel.ready(b.tick):channel.finish(act(seat,channel.pending.action))
        if b.tick>=90 and b.tick%10==0:
            info=observe(b,RES.builder,seat,events)
            p.belief.update(info.tick,info.events)
            if channel.pending is None:
                p.core.info=info;p.core.costs=RES.costs
                candidates,_=p.core.candidates(info.packet)
                # Abilities are excluded from this diagnostic arm on both sides.
                candidates=[a for a in candidates if a!=2305]
                if len(candidates)>1:
                    opponent=p.belief.sample(p.rng)
                    root=RES.root(info,opponent,p.rng)
                    action=p.core.score_candidates(root,seat,candidates)
                    if action<2304:
                        channel.submit(info,action,RES.costs,RES.builder)
                        if channel.ready(b.tick):channel.finish(act(seat,action))
            else:channel.blocked+=1
            other_action=int(RES.bots[style].select_action(RES.builder.build_public(b,1-seat)))
            if other_action<2304:act(1-seat,other_action)
        b.step()
    terminal=b.game_over
    loss=None if not terminal else float(b.winner is not None and b.winner!=seat)
    ident=f'sim-{pair:04d}-d{delay}'
    game=Game(ident,f'sim-{pair:04d}',f'search_d{delay}','exploration',
        archetype(own)+' vs '+archetype(other),own,loss,np.asarray(ticks),np.asarray(globals_),np.asarray(hands),
        np.asarray(offsets),np.concatenate(entities),np.concatenate(ids),plays,
        dict(seed=seed,seat=seat,style=style,terminal=terminal,winner=b.winner,delay_ticks=delay,
             own_deck=own,opponent_deck=other,channel=channel.diagnostics(),
             fair_information='public observation + own HUD + accepted enemy events; sampled hidden state and independent RNG',
             planner='Stage5 public reconstruction / S6 fixed-budget delay rollout',abilities='disabled both sides'),np.asarray(queues))
    result=extract(game,CAT)
    result.update(wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu)
    dest=Path(OPTIONS['out'])
    write(dest/'games'/f'{ident}.json',result)
    if OPTIONS['trace']:
        # Full analysis telemetry is separate from the player input boundary.
        with gzip.open(dest/'traces'/f'{ident}.json.gz','wt') as f:
            json.dump(dict(metadata=game.metadata,ticks=ticks,globals=np.asarray(globals_).tolist(),
                hands=np.asarray(hands).tolist(),queues=queues,offsets=offsets,entities=game.entities.tolist(),
                entity_ids=game.entity_ids.tolist(),plays=plays,actions=actions),f,separators=(',',':'))
    print(json.dumps(dict(game=ident,ticks=b.tick,wall=result['wall_seconds'],loss=loss)),flush=True)
    return dict(game=ident,wall=result['wall_seconds'],cpu=result['cpu_seconds'],terminal=terminal)


def main():
    global OPTIONS
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,required=True)
    ap.add_argument('--pairs',type=int,default=96);ap.add_argument('--max-ticks',type=int,default=6001)
    ap.add_argument('--seed-base',type=int,default=281474976710656);ap.add_argument('--exclusions',type=Path,required=True)
    ap.add_argument('--trace',action='store_true');ap.add_argument('--delays',type=int,nargs='+',default=[0,27])
    args=ap.parse_args();start=time.monotonic()
    if (args.out/'schedule.json').exists():raise ValueError('use a fresh output directory')
    exclude=json.loads(args.exclusions.read_text());denied=set(exclude['proposed'])|set(exclude['explicit'])
    # All game, shuffle and player generator seeds are checked. Resource template
    # demonstrations use the existing fixed 880601 seed; they never enter results.
    seeds={args.seed_base+i+off for i in range(args.pairs) for off in (0,100000,100001,100002)}
    if seeds & denied:raise ValueError('seed exclusion collision')
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'traces').mkdir(exist_ok=True)
    OPTIONS=dict(out=str(args.out),trace=args.trace,max_ticks=args.max_ticks)
    initialize()
    # Train-only prior. Five common strategic archetypes, top-frequency deck per
    # family; no human outcomes or eval deck rows enter schedule selection.
    selected=[]
    for family in ('bridge_wincon','siege','beatdown','bait','chip'):
        eligible=[d for d in PRIOR['decks'] if archetype(d['cards'])==family]
        if eligible:selected.append(max(eligible,key=lambda d:d['frequency'])['cards'])
    cases=[]
    for i in range(args.pairs):
        for delay in args.delays:
            cases.append((i,args.seed_base+i,delay,selected[i%len(selected)],selected[(i//len(selected))%len(selected)],('balanced','pressure','defense')[(i//25)%3]))
    write(args.out/'schedule.json',dict(cases=cases,seed_exclusions_sha256=hashlib.sha256(args.exclusions.read_bytes()).hexdigest(),
          checked_seeds=sorted(seeds),intersections=[],purpose='exploration only',selected_decks=selected))
    write(args.out/'catalog.json',CAT)
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('fork')) as pool:
        results=list(pool.map(run_game,cases,chunksize=1))
    write(args.out/'receipt.json',dict(games=len(results),terminal=sum(r['terminal'] for r in results),workers=args.workers,
        wall_seconds=time.monotonic()-start,worker_cpu_seconds=sum(r['cpu'] for r in results),host=socket.gethostname(),
        affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),results=results))

if __name__=='__main__':main()
