"""Command-exact heldout replay; complete frozen R1 W scores on common roots."""
import argparse,copy,json,os,resource,subprocess,time
from pathlib import Path
import numpy as np
BASE=4503602427370496
NATIVE_SHA='06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);ap.add_argument('--index',type=int,required=True);a=ap.parse_args();j=Path(a.job)
    from regret_admission import allowed
    from journal import record as journal
    journal(j,'regret_game',index=a.index)
    assert allowed(j) and len(os.sched_getaffinity(0))==1
    from imitation.exit_r1.rows import sha,write_json
    from imitation.exit_r1 import emitter as E
    assert sha(Path(os.environ['CLASHER_DELAY_NATIVE_DIR'])/'clasher_core.abi3.so')==NATIVE_SHA
    E.initialize();R=E.R
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from clasher.rl.action_space import DiscreteTileActionSpace
    from imitation.evaluation.events import PublicRecorder
    sources=json.loads((j/'heldout-corpus/sources.json').read_text())['games'];item=sources[a.index];g=Path(item['path'])
    if not g.exists():g=j/'heldout-games'/f'{a.index:04d}'
    assert sha(g/'manifest.json')==item['manifest_sha256']
    seal=json.loads((g/'manifest.json').read_text())
    for name,want in seal['files'].items():assert sha(g/name)==want,name
    rec=json.loads((g/'replay.json').read_text());assert rec['seed']==4503601207370496+a.index
    offset=sum(x['rows'] for x in sources[:a.index])
    arm_data={arm:np.load(j/'offline'/f'{arm}-proposals.npz') for arm in ('R3c','R3d','R3e')}
    proposals={arm:{int(row):[int(v) for v in top if v>=0] for row,top in zip(d['row_indices'],d['top8'])} for arm,d in arm_data.items()}
    t=g/'train';arrays={k:np.load(t/f'{k}.npy',mmap_mode='r') for k in ('teacher_root','teacher_wait_kind','expert_action_supervision_valid','root_offsets','root_actions','root_scores','root_valid','submitted_ticks','expert_actions')}
    ix=np.flatnonzero(arrays['teacher_root'].astype(bool)&(arrays['teacher_wait_kind']==0)&arrays['expert_action_supervision_valid'].astype(bool))
    ticks={int(arrays['submitted_ticks'][i]):int(i) for i in ix}
    assert all(offset+int(i) in proposals[arm] for arm in proposals for i in ix)
    seat=rec['seat'];b=battle(rec['episode'],R.builder.loader);channels=[CommandQueue(27,1),CommandQueue(27,1)];space=DiscreteTileActionSpace()
    cursor=sub=0;rows=[];begin=time.monotonic();cpu=time.process_time()
    with PublicRecorder(R.builder) as recorder:
        recorder.bind(b)
        while b.tick<rec['ticks']:
            if b.tick%20==0:assert allowed(j),'CPU admission/STOP changed during replay'
            for actor,ch in enumerate(channels):
                while ch.ready(b.tick):
                    action=ch.pending[0].action;ok=bool(space.apply_action(b,actor,action))
                    assert [b.tick,actor,action,ok]==rec['commands'][cursor];ch.finish(ok);cursor+=1
            if b.tick%5==0:
                if b.tick in ticks:
                    i=ticks.pop(b.tick);global_row=offset+i
                    assert 0<=global_row<65536,'fresh regret seed must stay inside the audited reservation'
                    events=[PublicEvent(**{k:e[k] for k in PublicEvent.__dataclass_fields__}) for e in recorder.public_events if e['seat']!=seat]
                    info=observe(b,R.builder,seat,events);p=E.player(BASE+global_row)
                    p.belief.update(info.tick,info.events);p.core.info,p.core.costs=info,R.costs
                    p.core.candidates(info.packet) # frozen candidate setup/elixir and RNG consumption
                    root=R.root(info,p.belief.sample(p.rng),p.rng)
                    lo,hi=map(int,arrays['root_offsets'][i:i+2]);recorded=list(map(int,arrays['root_actions'][lo:hi]))
                    sets={arm:proposals[arm][global_row] for arm in proposals}
                    union=list(dict.fromkeys(recorded+[v for top in sets.values() for v in top]+[2304,2400]))
                    plays=[v for v in union if v<2304];waits=[v for v in union if v>=2304 and v!=2305]
                    scored={}
                    # At most8 plays per call bypasses screening exclusion without changing
                    # any per-action frozen scorer, delay, horizon, rollout or score arithmetic.
                    for start in range(0,max(1,len(plays)),8):
                        candidates=waits+plays[start:start+8]
                        p.core.score_candidates(root,seat,candidates)
                        for action,value in zip(p.core.last['candidates'],p.core.last['scores']):
                            assert value is not None and np.isfinite(value),'every proposal requires a complete W score'
                            if action in scored:assert abs(scored[action]-value)<1e-12,'common root scoring changed between groups'
                            scored[int(action)]=float(value)
                    comparator=max(scored[v] for v in recorded if v in scored)
                    baseline=max(scored[2304],scored[2400]);record=dict(game=a.index,seed=rec['seed'],row=global_row,tick=b.tick,teacher_play=bool(arrays['expert_actions'][i]<2304),w_argmax_score=comparator,wait_best=baseline)
                    for arm,top in sets.items():
                        best=max([baseline]+[scored[v] for v in top]);signed=comparator-best
                        record[arm]=dict(top8=top,best_score=best,signed_regret=signed,positive_regret=max(0.,signed),play_only_regret=max(0.,comparator-max([scored[v] for v in top])) if top else None)
                    rows.append(record)
                while sub<len(rec['submissions']) and rec['submissions'][sub][0]==b.tick:
                    _,actor,action=rec['submissions'][sub];channels[actor].submit(observe(b,R.builder,actor,()),action,R.costs,R.builder);sub+=1
            b.step()
    assert not ticks and len(rows)==len(ix) and cursor==len(rec['commands']) and sub==len(rec['submissions'])
    assert b.game_over and b.tick==rec['ticks']
    out=j/'regret/games';out.mkdir(parents=True,exist_ok=True)
    path=out/f'{a.index:04d}.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    u=resource.getrusage(resource.RUSAGE_SELF)
    write_json(out/f'{a.index:04d}.json',dict(index=a.index,seed=rec['seed'],roots=len(rows),complete=True,command_exact=True,jsonl_sha256=sha(path),native_sha256=NATIVE_SHA,evaluation_freeze_sha256=sha(j/'evaluation-freeze.json'),proposals_sha256={arm:sha(j/'offline'/f'{arm}-proposals.npz') for arm in proposals},cpu_seconds=u.ru_utime+u.ru_stime,scoring_replay_cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-begin,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()))
if __name__=='__main__':main()
