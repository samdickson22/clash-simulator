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
RES=None;CAT=None;PRIOR=None;OPTIONS=None;POLICY=None


def initialize():
    global RES,CAT,PRIOR,POLICY
    if os.environ.get('CLASHER_DELAY_NATIVE_DIR'):
        sys.path.insert(0,os.environ['CLASHER_DELAY_NATIVE_DIR'])
        import clasher_core  # pin the task-owned extension before support path insertion
    sys.path[:0]=[str(ROOT),str(ROOT/'engine-rs'),str(COUNCIL/'engine-speed/stage5')]
    import torch
    torch.set_num_threads(1)
    from fair_player import Resources
    RES=Resources();CAT=make_catalog(RES.builder)
    PRIOR=json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())
    if OPTIONS.get('checkpoint'):
        from imitation.model import load_policy
        POLICY=load_policy(OPTIONS['checkpoint'])
        assert all(p.dtype == torch.float32 for p in POLICY.model.parameters())
        POLICY.model.temperatures.fill_(1.)


def run_game(case):
    from fair_player import PublicPlanner,observe
    from derived_public_state import PublicEvent
    from stage2_matches import battle
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    sys.path.insert(0,str(COUNCIL/'search-noise-s6'))
    import delay as dm
    from clasher.rl.public_observation import REAL_PLAY_ENTITY_FEATURE_INDICES
    start=time.monotonic();cpu=time.process_time()
    from .delay_fixes import CommandQueue, planner_class, imitation_candidates
    pair,seed,arm,own,other,style=case;seat=pair%2
    delay=0 if arm in ('U0','S0') else 27
    symmetric=arm not in ('U0','U27')
    capacity=int(arm[1:]) if arm.startswith('N') else 1
    rng=random.Random(seed);own=list(own);other=list(other);rng.shuffle(own);rng.shuffle(other)
    decks=[own,other] if seat==0 else [other,own]
    b=battle(dict(seed=seed,decks=decks),RES.builder.loader)
    p=PublicPlanner(RES,PRIOR,seed+100000)
    channel=CommandQueue(delay,capacity)
    opponent_channel=CommandQueue(OPTIONS['opponent_delay'] if symmetric else 0,4 if symmetric else 1)
    p.core=planner_class(dm.DelayAwarePlanner)(RES.builder,RES.bots,backend='native',seed=seed+100001,
        native=RES.native,native_config=RES.config,config=C56SearchConfig(threads=1),
        command_delay=delay,delay_aware=bool(delay),symmetric_opponent=symmetric,
        max_outstanding=capacity,opponent_delay=OPTIONS['opponent_delay'],
        opponent_interval=OPTIONS['opponent_interval'],forward_prior=arm=='IF')
    d1=None
    if arm in ('I0','IF'):
        from imitation.evaluation.d1 import D1Tracker
        d1=D1Tracker(RES.builder,RES.costs,seat,own)
    public_events=[];submissions=[];proposal_audit=[];decision_polls=0
    latencies=[];cpu_latencies=[]
    raw_latencies=[]
    from .throughput_guard import PauseClock
    clock=PauseClock(Path(OPTIONS['out'])/'pause-clock.json')
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
        if ok:
            public_events.append(dict(tick=b.tick,seat=actor,kind='card',name=name,amount=0.,
                x=choice.position.x,y=choice.position.y))
        return ok
    while not b.game_over and b.tick<OPTIONS['max_ticks']:
        if b.tick%5==0:
            ob=RES.builder.build_public(b,seat).observation
            ticks.append(b.tick);globals_.append(ob.global_features.copy());hands.append(ob.hand_ids.copy())
            q=list(b.players[seat].cycle_queue)
            queues.append([RES.builder.token_id(n,namespace='card_action') for n in q]+[0]*(8-len(q)))
            ef=ob.entity_features[ob.entity_mask][:,cols].copy();entities.append(ef)
            ids.append(ob.entity_ids[ob.entity_mask].copy());offsets.append(offsets[-1]+len(ef))
        def complete(ch,actor):
            while ch.ready(b.tick):
                command=ch.pending[0]
                if b.players[actor].hand[command.action//576] != command.card:
                    raise AssertionError('pending card changed')
                ch.finish(act(actor,command.action))
        complete(channel,seat);complete(opponent_channel,1-seat)
        if b.tick>=90 and b.tick%10==0:
            decision_polls+=1
            info=observe(b,RES.builder,seat,events)
            p.belief.update(info.tick,info.events)
            if channel.available:
                decision_start=clock.now();decision_wall=time.perf_counter();decision_cpu=time.process_time()
                reserved=channel.own_packet(info,RES.builder)
                p.core.info=info;p.core.costs=RES.costs;p.core.pending=tuple(channel.pending)
                if d1 is not None:
                    d1.update(b.tick,public_events);d1._exploration_events=public_events
                if arm in ('I0','IF'):
                    opponent=p.belief.sample(p.rng)
                    root=RES.root(info,opponent,p.rng)
                    candidates,audit=imitation_candidates(p.core,RES,root,reserved,d1,POLICY,forward=arm=='IF')
                    proposal_audit.append(audit)
                else:
                    candidates,_=p.core.candidates(reserved.packet)
                    candidates=[a for a in candidates if a!=2305]
                    if len(candidates)>1:
                        opponent=p.belief.sample(p.rng)
                        root=RES.root(info,opponent,p.rng)
                if len(candidates)>1:
                    action=p.core.score_candidates(root,seat,candidates)
                    if action<2304:
                        channel.submit(info,int(action),RES.costs,RES.builder)
                        submissions.append(b.tick)
                        complete(channel,seat)
                latencies.append(max(0.,clock.now()-decision_start))
                raw_latencies.append(time.perf_counter()-decision_wall)
                cpu_latencies.append(time.process_time()-decision_cpu)
            else:channel.blocked+=1
        if b.tick>=90 and b.tick%OPTIONS['opponent_interval']==0:
            if opponent_channel.available:
                enemy_info=observe(b,RES.builder,1-seat,())
                reserved=opponent_channel.own_packet(enemy_info,RES.builder)
                other_action=int(RES.bots[style].select_action(reserved.packet))
                if other_action<2304:
                    opponent_channel.submit(enemy_info,other_action,RES.costs,RES.builder)
                    complete(opponent_channel,1-seat)
            else:opponent_channel.blocked+=1
        b.step()
    terminal=b.game_over
    loss=None if not terminal else float(b.winner is not None and b.winner!=seat)
    win=None if not terminal else float(b.winner==seat)
    ident=f'sim-{pair:04d}-d{delay}'
    if arm is not None:ident+=f'-{arm}'
    game=Game(ident,f'sim-{pair:04d}',f'search_d{delay}','exploration',
        archetype(own)+' vs '+archetype(other),own,loss,np.asarray(ticks),np.asarray(globals_),np.asarray(hands),
        np.asarray(offsets),np.concatenate(entities),np.concatenate(ids),plays,
        dict(seed=seed,seat=seat,style=style,terminal=terminal,winner=b.winner,delay_ticks=delay,
             own_deck=own,opponent_deck=other,channel=channel.diagnostics(),opponent_channel=opponent_channel.diagnostics(),
             opponent_delay=opponent_channel.delay,opponent_interval=OPTIONS['opponent_interval'],max_outstanding=capacity,arm=arm,win=win,
             fair_information='public observation + own HUD + accepted enemy events; sampled hidden state and independent RNG',
             planner='Stage5 public reconstruction / S6 fixed-budget delay rollout',abilities='disabled both sides'),np.asarray(queues))
    result=extract(game,CAT)
    result['cohort']=arm
    result['delay_fixes']=dict(arm=arm,latency_seconds=latencies,cpu_latency_seconds=cpu_latencies,
        raw_wall_latency_seconds=raw_latencies,latency_clock='active-wall-v1',
        submission_ticks=submissions,proposal_audit=proposal_audit)
    # Loss-review-style pooled behavior metrics; complete post-play windows.
    accepted=[q['tick'] for q in plays if q['accepted']]
    gaps=[(v-u)/20 for u,v in zip(accepted,accepted[1:])]
    silence=[not any(t < q <= t+27 for q in submissions) for t in accepted if t+27<=b.tick]
    stats=result['stats']['all']
    stats['post_play_no_submission_27ticks_fraction']=[sum(silence),len(silence)]
    stats['interplay_gap_seconds']=[sum(gaps),len(gaps)]
    submitted_silence=[not any(t<q<=t+27 for q in submissions) for t in submissions if t+27<=b.tick]
    execution_silence=[not any(t<q<=t+27 for q in accepted) for t in accepted if t+27<=b.tick]
    stats['post_submission_no_followup_27ticks_fraction']=[sum(submitted_silence),len(submitted_silence)]
    stats['post_execution_no_followup_27ticks_fraction']=[sum(execution_silence),len(execution_silence)]
    stats['pending_blocked_decision_fraction']=[channel.blocked,decision_polls]
    stats['win_fraction']=[win or 0,int(terminal)]
    stats['loss_fraction']=[loss or 0,int(terminal)]
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
    from datetime import datetime, timezone
    from .delay_runtime import GPUWatch
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,required=True)
    ap.add_argument('--pairs',type=int,default=50);ap.add_argument('--pair-offset',type=int,default=0)
    ap.add_argument('--arms',nargs='+',default=['U0','U27','S0','S27','N2','N4','I0','IF'],choices=['U0','U27','S0','S27','N2','N4','I0','IF'])
    ap.add_argument('--checkpoint',type=Path);ap.add_argument('--exclusions',type=Path,required=True)
    ap.add_argument('--opponent-delay',type=int,default=22);ap.add_argument('--opponent-interval',type=int,default=10)
    ap.add_argument('--trace',action='store_true');ap.add_argument('--max-ticks',type=int,default=6001)
    ap.add_argument('--gpu-guard',action='store_true');ap.add_argument('--resume',action='store_true')
    args=ap.parse_args();start=time.monotonic()
    if not 1<=args.workers<=26:raise ValueError('lease pool limit 26 plus parent, supervisor, and monitoring')
    if set(args.arms)&{'I0','IF'} and not args.checkpoint:raise ValueError('released checkpoint required')
    checkpoint_sha=None
    if args.checkpoint:
        checkpoint_sha=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        if checkpoint_sha!='d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed':
            raise ValueError('released v1 checkpoint mismatch')
    if datetime.now(timezone.utc)>=datetime(2026,10,9,4,15,tzinfo=timezone.utc):
        raise RuntimeError('no shards start after 04:15Z')
    OPTIONS=dict(out=str(args.out),trace=args.trace,max_ticks=args.max_ticks,
        checkpoint=str(args.checkpoint) if args.checkpoint else None,
        opponent_delay=args.opponent_delay,opponent_interval=args.opponent_interval)
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'traces').mkdir(exist_ok=True)
    guard=GPUWatch(args.out/'gpu.jsonl',args.gpu_guard)
    if args.gpu_guard:guard.prepare()
    exclude=json.loads(args.exclusions.read_text());denied=set(exclude['proposed'])|set(exclude['explicit'])
    initialize()
    selected=[]
    for family in ('bridge_wincon','siege','beatdown','bait','chip'):
        eligible=[d for d in PRIOR['decks'] if archetype(d['cards'])==family]
        selected.append(max(eligible,key=lambda d:d['frequency'])['cards'])
    cases=[];checked=set()
    for pair in range(args.pair_offset,args.pair_offset+args.pairs):
        seed=2**48+50000+pair
        checked.update(seed+off for off in (0,100000,100001,100002))
        for arm in args.arms:
            cases.append((pair,seed,arm,selected[pair%5],selected[(pair//5)%5],('balanced','pressure','defense')[(pair//25)%3]))
    if checked&denied:raise ValueError('seed exclusion collision')
    schedule=dict(cases=cases,checked_seeds=sorted(checked),seed_exclusions_sha256=hashlib.sha256(args.exclusions.read_bytes()).hexdigest(),
        checkpoint_sha256=checkpoint_sha,purpose='non-confirmatory exploration; no eval data',options=OPTIONS,
        workers=args.workers)
    if (args.out/'schedule.json').exists():
        old=json.loads((args.out/'schedule.json').read_text())
        semantic=lambda row:{k:v for k,v in row.items() if k not in ('out','checkpoint')}
        if (not args.resume or old['cases']!=json.loads(json.dumps(cases))
                or semantic(old['options'])!=semantic(OPTIONS)
                or old['checkpoint_sha256']!=checkpoint_sha):
            raise ValueError('resume configuration mismatch')
        if old['options']!=OPTIONS:
            write(args.out/'migration.json',dict(old_options=old['options'],new_options=OPTIONS,
                checkpoint_sha256=checkpoint_sha,reason='technical resource migration; same paired schedule'))
    else:write(args.out/'schedule.json',schedule)
    write(args.out/'catalog.json',CAT)
    pending=[];reused=[]
    for case in cases:
        pair,seed,arm=case[:3];d=0 if arm in ('U0','S0') else 27
        path=args.out/'games'/f'sim-{pair:04d}-d{d}-{arm}.json'
        if path.exists() and args.resume:
            row=json.loads(path.read_text())
            if row['metadata']['seed']!=seed or row['cohort']!=arm or not row['metadata']['terminal']:
                raise ValueError('invalid completed game')
            reused.append(dict(game=row['identity'],wall=row['wall_seconds'],cpu=row['cpu_seconds'],terminal=True))
        else:pending.append(case)
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('fork')) as pool:
        futures=[pool.submit(run_game,case) for case in pending]
        with guard:
            fresh=[future.result() for future in futures]
    results=reused+fresh
    write(args.out/'receipt.json',dict(games=len(results),terminal=sum(r['terminal'] for r in results),workers=args.workers,
        wall_seconds=time.monotonic()-start,worker_cpu_seconds=sum(r['cpu'] for r in fresh),host=socket.gethostname(),
        resumed_games=len(reused),new_games=len(fresh),checkpoint_sha256=checkpoint_sha,results=results))


if __name__=='__main__':main()
