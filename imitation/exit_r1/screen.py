"""Fresh paired student games using the qualified gate(c) and E1 deadline kernel.

One process per assigned core; an external owned supervisor sets resource caps.
Reporting requires explicit plan/checkpoint/runtime/seed-audit SHA bindings.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import socket
import sys
import time
import numpy as np
import torch
from .rows import sha, write_json
from . import emitter
from .screen_metrics import diagnostics, paired_interval, decide

ARMS=('S-mix','S-teacher','S-human')
BASES=dict(h2h=4503601007370496,fallback=4503601107370496,teacher=4503601207370496,smoke=4503601307370496)
COUNTS=dict(h2h=256,fallback=600,teacher=64)


def load_student(path):
    from imitation.model.inference import Policy
    from imitation.model.network import ModelConfig, SetPolicy
    ck=torch.load(path,map_location='cpu',weights_only=True);s=ck['ema']
    model=SetPolicy(ModelConfig(**ck['config']),s['descriptors'],s['tile_features'],s['costs'])
    # Value is a training auxiliary only; portable proposer has the original API.
    model.load_state_dict({k:v for k,v in s.items() if not k.startswith('value_head.')})
    model.temperatures.fill_(1.)
    return Policy(model)


def verify_freeze(path,digest):
    path=Path(path)
    if sha(path)!=digest:raise ValueError('execution freeze SHA mismatch')
    freeze=json.loads(path.read_text())
    for name,expected in freeze['files'].items():
        if sha(name)!=expected:raise ValueError('frozen input changed: '+name)
    audit=json.loads(Path(freeze['seed_audit']).read_text())
    if audit.get('passed') is not True:raise ValueError('seed audit did not pass')
    seeds=set(audit['proposed'])
    if not all(BASES[k]+i in seeds for k in COUNTS for i in range(COUNTS[k])):
        raise ValueError('seed audit does not cover the entire screen')
    return freeze


def freeze_inputs(plan,plan_sha,audit,checkpoints,native,output):
    if sha(plan)!=plan_sha:raise ValueError('coordinator-frozen draft SHA mismatch')
    root=Path(__file__).resolve().parents[2]
    paths=[Path(plan),Path(audit),Path(native),*(Path(p) for p in checkpoints.values())]
    for directory in ('imitation/model','imitation/evaluation','imitation/exit_r1','src',
                      'engine-rs','reports/explore/e1','reports/explore/w-screen8',
                      'reports/strategy_council_20260928/search-noise-s6',
                      'reports/strategy_council_20260928/engine-speed'):
        paths.extend(p for p in (root/directory).rglob('*') if p.suffix in ('.py','.json') and p.is_file())
    paths.extend(root/p for p in ('decks.json','reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json'))
    f=dict(schema='clasher.exit-r1.screen-freeze.v1',plan_sha256=plan_sha,plan=str(Path(plan).resolve()),
           seed_audit=str(Path(audit).resolve()),checkpoints={k:str(Path(v).resolve()) for k,v in checkpoints.items()},
           native=str(Path(native).resolve()),seed_bases=BASES,counts=COUNTS,
           files={str(p.resolve()):sha(p) for p in paths})
    if Path(output).exists():raise ValueError('freeze output must be fresh')
    write_json(output,f)
    try:verify_freeze(output,sha(output))
    except Exception:Path(output).unlink();raise
    return sha(output)


def execution_guard(stop):
    host=socket.gethostname().split('.')[0]
    if host not in ('127x01','127x02','127x03','127x04','127x08'):raise ValueError('no leased CPU simulations')
    if os.sched_getscheduler(0)!=os.SCHED_IDLE or os.getpriority(os.PRIO_PROCESS,0)<(19 if host=='127x08' else 10):
        raise ValueError('screen requires nice/SCHED_IDLE')
    if len(os.sched_getaffinity(0))!=1:raise ValueError('pin each game worker to one core')
    if host=='127x08' and not stop:raise ValueError('08 needs an owned stop file')
    from .pack import check_memory
    check_memory()
    if stop and Path(stop).exists():raise InterruptedError('screen STOP')


def initialize(freeze):
    os.environ['CLASHER_DELAY_NATIVE_DIR']=str(Path(freeze['native']).parent)
    r=emitter.initialize()
    import clasher_core
    if sha(clasher_core.__file__)!=sha(freeze['native']) or not hasattr(r.native,'rollout_e1'):
        raise ValueError('E1 native deadline kernel required')
    from imitation.evaluation.paths import ROOT
    directory=ROOT/'reports/explore/e1';sys.path.insert(0,str(directory))
    spec=importlib.util.spec_from_file_location('exit_r1_e1_runner',directory/'run.py')
    e1=importlib.util.module_from_spec(spec);spec.loader.exec_module(e1)
    from clasher.analysis.loss_review.human import make_catalog
    e1.R=r;e1.PRIOR=emitter.PRIOR;e1.CAT=make_catalog(r.builder)
    return e1,{k:load_student(p) for k,p in freeze['checkpoints'].items()}


def run_case(e1,policies,mode,arm,index,seed,output,stop=None,max_ticks=6001,freeze_sha256=None):
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from imitation.evaluation.standalone import StandalonePlayer
    from imitation.evaluation.d1 import model_packet
    from imitation.evaluation.events import PublicRecorder
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from clasher.rl.action_space import DiscreteTileActionSpace
    r=e1.R;seat=index%2;decks=emitter.decks()[:5]
    own,other=list(decks[index%5]),list(decks[(index//5)%5]);rng=random.Random(seed)
    rng.shuffle(own);rng.shuffle(other);orders=[own,other] if seat==0 else [other,own]
    b=battle(dict(seed=seed,decks=orders),r.builder.loader)
    assigned={seat:policies[arm],1-seat:policies['init']}
    adapters={a:StandalonePlayer(assigned[a],r.builder,r.costs,a,orders[a],seed+271828+a) for a in (0,1)}
    players={a:e1.make_player(seed+100000+2*(a!=seat),'W') for a in (0,1)} if mode=='fallback' else {}
    channels=[CommandQueue(27,1),CommandQueue(27,1)];waits=[0,0];space=DiscreteTileActionSpace()
    stats=[dict(polls=0,sampled_plays=0,sampled_waits=0,submitted_plays=0,accepted_plays=0,
                pending_polls=0,timed_wait_polls=0,deadlines=[],proposer_seconds=[]) for _ in (0,1)]
    commands=hashlib.sha256();cpu0=time.process_time();wall0=time.monotonic()
    with PublicRecorder(r.builder) as recorder:
        recorder.bind(b)
        while not b.game_over and b.tick<max_ticks:
            if b.tick%20==0:execution_guard(stop)
            for actor,ch in enumerate(channels):
                while ch.ready(b.tick):
                    command=ch.pending[0]
                    if b.players[actor].hand[command.action//576]!=command.card:raise AssertionError('delayed hand slot changed')
                    ok=bool(space.apply_action(b,actor,command.action));ch.finish(ok)
                    stats[actor]['accepted_plays']+=int(ok)
                    commands.update(f'{b.tick},{actor},{command.action},{int(ok)};'.encode())
            if b.tick>=90 and b.tick%5==0:
                for actor,ch in enumerate(channels):
                    begin=time.monotonic()
                    events=[PublicEvent(**{k:v[k] for k in PublicEvent.__dataclass_fields__})
                            for v in recorder.public_events if v['seat']!=actor]
                    info=observe(b,r.builder,actor,events);reserved=ch.own_packet(info,r.builder)
                    fallback,mask=adapters[actor].decide(b.tick,reserved.packet,recorder.public_events)
                    if fallback>=2304:fallback=2304  # Abilities disabled symmetrically.
                    s=stats[actor];s['polls']+=1;s['sampled_plays']+=int(fallback<2304);s['sampled_waits']+=int(fallback==2304)
                    if not ch.available:s['pending_polls']+=1;continue
                    if b.tick<waits[actor]:s['timed_wait_polls']+=1;continue
                    action=fallback
                    if actor in players:
                        if b.tick%10:continue
                        p=players[actor];cutoff=begin+.2-.008
                        proposal_start=time.monotonic()
                        proposals=assigned[actor].propose(model_packet(reserved.packet,mask),adapters[actor].last_d1,k=8)
                        s['proposer_seconds'].append(time.monotonic()-proposal_start)
                        p.belief.update(info.tick,info.events)
                        p.core.info,p.core.costs,p.core.pending=info,r.costs,tuple(ch.pending)
                        p.core.opponent_elixir=float(adapters[actor].last_d1['opp_elixir'])
                        candidates,_=p.core.candidates(reserved.packet,[v['action'] for v in proposals])
                        candidates=[a for a in candidates if a!=2305]
                        if time.monotonic()>=cutoff:
                            p.core.selected_wait_ticks=0
                            p.core.deadline_stats=dict(hit=True,fallback=True,completed=0,candidates=len(candidates))
                        else:
                            root=r.root(info,p.belief.sample(p.rng),p.rng)
                            action=p.core.score_candidates(root,actor,candidates,deadline=cutoff,fallback=fallback)
                        waits[actor]=b.tick+p.core.selected_wait_ticks
                    if action<2304:
                        if not mask[action]:raise AssertionError('illegal public action')
                        ch.submit(info,int(action),r.costs,r.builder);s['submitted_plays']+=1
                    if actor in players:
                        elapsed=time.monotonic()-begin
                        s['deadlines'].append(dict(players[actor].core.deadline_stats,wall_seconds=elapsed,wall_overrun=elapsed>.2))
            b.step()
    if not b.game_over:raise RuntimeError('nonterminal screen game')
    record=dict(mode=mode,arm=arm,index=index,seed=seed,seat=seat,terminal=True,winner=b.winner,freeze_sha256=freeze_sha256,
                loss=float(b.winner is not None and b.winner!=seat),win=float(b.winner==seat),draw=b.winner is None,
                ticks=b.tick,cpu_seconds=time.process_time()-cpu0,wall_seconds=time.monotonic()-wall0,
                stats=stats,command_sha256=commands.hexdigest(),fair_information='public packet + own HUD + public events; independent belief/RNG')
    write_json(Path(output)/f'{mode}-{arm}-{index:04d}.json',record)
    return record


@torch.inference_mode()
def agreement(policy,store,batch_size=64,root_only=True):
    keep=store.arrays['expert_action_supervision_valid'] & (store.arrays['teacher_wait_kind']!=3)
    if root_only:keep &= store.arrays['teacher_root']
    selected=np.flatnonzero(keep)
    values=[];actions=[];games=[];top8=[];hard=[]
    for start in range(0,len(selected),batch_size):
        ix=selected[start:start+batch_size];b,y=store.batch(ix)
        lp=policy.model.log_policy(b);values.append(lp['gate'].exp().numpy())
        actions.append(y['action'].numpy());games.append(np.asarray(store.arrays['episode_ids'][ix]))
        joint=(lp['card'][:,:,None]+lp['tile']).flatten(1)
        candidates=joint.topk(8,dim=1).indices.numpy()
        top8.extend((candidates==y['action'].numpy()[:,None]).any(1).tolist())
        predicted=np.where(lp['gate'].argmax(1).numpy()==1,joint.argmax(1).numpy(),2304)
        hard.extend((predicted==y['action'].numpy()).tolist())
    probabilities=np.concatenate(values);chosen=np.concatenate(actions)
    d=diagnostics(chosen,probabilities[:,1],probabilities[:,0])
    positive=chosen<2304;d['top8_action_recall']=float(np.asarray(top8)[positive].mean())
    d['hard_action_agreement']=float(np.mean(hard));d['scope']='teacher roots' if root_only else 'eligible poll rows'
    raw=dict(actions=chosen,play=probabilities[:,1],wait=probabilities[:,0],episodes=np.concatenate(games))
    # Cluster by whole teacher game, preserving each game's positive denominator.
    units=np.unique(raw['episodes']);sums=[]
    for game in units:
        ix=raw['episodes']==game;plays=(chosen[ix]<2304)
        sums.append([ix.sum(),plays.sum(),(chosen[ix]==2304).sum(),raw['play'][ix][plays].sum(),raw['wait'][ix].sum()])
    rng=np.random.default_rng(80991010);a=np.asarray(sums)
    samples=a[rng.integers(len(a),size=(5000,len(a)))].sum(1)
    if (samples[:,1]==0).any():raise ValueError('bootstrap teacher sample has no plays')
    d['ci95']={k:np.quantile(v,[.025,.975]).tolist() for k,v in
               (('play_recall',samples[:,3]/samples[:,1]),('teacher_wait_rate',samples[:,2]/samples[:,0]),
                ('student_wait_rate',samples[:,4]/samples[:,0]))}
    d['games']=len(units)
    return d,raw


def reduce_games(directory,agreement_metrics,counts=COUNTS,freeze_sha256=None):
    root=Path(directory);results={}
    def records(mode,arm):
        result=[]
        for i in range(counts[mode]):
            r=json.loads((root/f'{mode}-{arm}-{i:04d}.json').read_text())
            if (r['mode'],r['arm'],r['index'],r['seed'],r['terminal'])!=(mode,arm,i,BASES[mode]+i,True):
                raise ValueError('case identity/terminal mismatch')
            if freeze_sha256 and r.get('freeze_sha256')!=freeze_sha256:raise ValueError('case execution freeze differs')
            result.append(r)
        return result
    reference=records('fallback','init')
    for arm in ARMS:
        if freeze_sha256 and agreement_metrics[arm].get('freeze_sha256')!=freeze_sha256:
            raise ValueError('diagnostic execution freeze differs')
        h2h=records('h2h',arm);paired=records('fallback',arm)
        ci=paired_interval([r['loss'] for r in paired],[r['loss'] for r in reference])
        h2h_ci=paired_interval([r['loss'] for r in h2h],np.zeros(len(h2h)))
        results[arm]=dict(h2h_games=len(h2h),h2h_loss=float(np.mean([r['loss'] for r in h2h])),
                         h2h_ci95=h2h_ci['ci95'],h2h_wins=sum(r['win'] for r in h2h),h2h_draws=sum(r['draw'] for r in h2h),
                         fallback=ci,teacher=agreement_metrics[arm],**decide(agreement_metrics[arm],ci))
    return results


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True);p.add_argument('--freeze-sha256',required=True)
    p.add_argument('--mode',choices=('h2h','fallback','teacher','agreement','reduce'),required=True)
    p.add_argument('--arm',choices=(*ARMS,'init'),required=True)
    p.add_argument('--offset',type=int,default=0);p.add_argument('--count',type=int,default=1)
    p.add_argument('--output',required=True);p.add_argument('--stop');p.add_argument('--smoke',action='store_true')
    p.add_argument('--teacher-store');p.add_argument('--assets');p.add_argument('--games');p.add_argument('--diagnostics')
    a=p.parse_args();execution_guard(a.stop);f=verify_freeze(a.freeze,a.freeze_sha256)
    if a.mode=='reduce':
        results=reduce_games(a.games,json.loads(Path(a.diagnostics).read_text()),freeze_sha256=a.freeze_sha256)
        write_json(a.output,dict(freeze_sha256=a.freeze_sha256,arms=results));return
    e1,policies=initialize(f);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    if a.mode=='agreement':
        from .student import TeacherStore
        store=TeacherStore(a.teacher_store,a.assets)
        if not json.loads((Path(a.teacher_store)/'manifest.json').read_text()).get('packed'):
            raise ValueError('pack the complete held-out teacher slice first')
        seeds=set(map(int,np.unique(store.arrays['perspective_ids'])))
        if seeds!={BASES['teacher']+i for i in range(COUNTS['teacher'])}:raise ValueError('held-out teacher seed slice mismatch')
        metrics,_=agreement(policies[a.arm],store)
        metrics['all_poll_rows'],_=agreement(policies[a.arm],store,root_only=False)
        write_json(out/f'{a.arm}.json',dict(freeze_sha256=a.freeze_sha256,teacher_manifest_sha256=sha(Path(a.teacher_store)/'manifest.json'),**metrics));return
    if a.offset<0 or a.count<1 or a.offset+a.count>(32 if a.smoke else COUNTS[a.mode]):p.error('case range out of bounds')
    for i in range(a.offset,a.offset+a.count):
        if a.mode=='teacher':
            emitter.POLICY=policies['init']
            r=emitter.run_game((BASES['smoke'] if a.smoke else BASES['teacher'])+i,i,out/f'game-{i:09d}',
                               opponent=('W','v1','baseline','script')[i%4],stop=a.stop)
            if r is None:raise InterruptedError('held-out teacher generation STOP')
            continue
        if (out/f'{a.mode}-{a.arm}-{i:04d}.json').exists():raise ValueError('case already exists; use a separate smoke output')
        r=run_case(e1,policies,a.mode,a.arm,i,(BASES['smoke'] if a.smoke else BASES[a.mode])+i,out,a.stop,
                   freeze_sha256=a.freeze_sha256)
        print(json.dumps({k:r[k] for k in ('mode','arm','index','seed','loss','wall_seconds')}),flush=True)


if __name__=='__main__':main()
