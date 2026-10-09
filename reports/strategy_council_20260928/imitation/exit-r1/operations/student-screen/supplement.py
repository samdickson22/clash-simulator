"""Whole-game CIs and execution diagnostics required by the frozen reporting plan."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from imitation.exit_r1 import screen
from imitation.exit_r1.student import TeacherStore
from imitation.exit_r1.rows import sha,write_json

def clustered(sums,names,ratios):
    a=np.asarray(sums,dtype=np.float64)
    rng=np.random.default_rng(80991010)
    b=a[rng.integers(len(a),size=(5000,len(a)))].sum(1)
    total=a.sum(0);result={}
    for key,(numerator,denominator) in ratios.items():
        ni=names.index(numerator);di=names.index(denominator)
        if not total[di] or (b[:,di]==0).any():raise ValueError('zero diagnostic denominator: '+key)
        result[key]=dict(value=float(total[ni]/total[di]),
            ci95=np.quantile(b[:,ni]/b[:,di],[.025,.975]).tolist(),
            numerator=float(total[ni]),denominator=float(total[di]))
    return result

@torch.inference_mode()
def teacher(policy,store,root_only):
    keep=store.arrays['expert_action_supervision_valid'] & (store.arrays['teacher_wait_kind']!=3)
    if root_only:keep &= store.arrays['teacher_root']
    ix=np.flatnonzero(keep);rows=[]
    for begin in range(0,len(ix),64):
        take=ix[begin:begin+64];b,y=store.batch(take);lp=policy.model.log_policy(b)
        gate=lp['gate'].exp().numpy();actions=y['action'].numpy();positive=actions<2304
        joint=(lp['card'][:,:,None]+lp['tile']).flatten(1)
        top8=(joint.topk(8,dim=1).indices.numpy()==actions[:,None]).any(1)&positive
        predicted=np.where(lp['gate'].argmax(1).numpy()==1,joint.argmax(1).numpy(),2304)
        ep=store.arrays['episode_ids'][take]
        rows.append(np.column_stack((ep,np.ones(len(take)),positive,actions==2304,
            gate[:,1],gate[:,0],gate[:,1]*positive,top8,predicted==actions)))
    a=np.concatenate(rows);units=np.unique(a[:,0]);assert len(units)==64
    sums=[a[a[:,0]==u,1:].sum(0) for u in units]
    names=['rows','teacher_play','teacher_wait','student_play','student_wait','recall','top8','hard']
    ratios={'teacher_play_rate':('teacher_play','rows'),'teacher_wait_rate':('teacher_wait','rows'),
        'student_play_rate':('student_play','rows'),'student_wait_rate':('student_wait','rows'),
        'play_recall':('recall','teacher_play'),'play_prevalence_ratio':('student_play','teacher_play'),
        'top8_action_recall':('top8','teacher_play'),'hard_action_agreement':('hard','rows')}
    return dict(games=64,rows=len(a),scope='teacher roots' if root_only else 'eligible poll rows',
        metrics=clustered(sums,names,ratios),teacher_self_recall=1.0)

def games(records,side):
    names=['games','loss','win','draw','polls','plays','waits','submitted','pending','timed',
           'decisions','hits','fallback','overruns','roots','proposer_seconds','proposals']
    sums=[];latencies=[];walls=[]
    for r in records:
        s=r['stats'][r['seat'] if side=='student' else 1-r['seat']]
        d=s['deadlines'];p=s['proposer_seconds'];latencies.extend(p)
        walls.extend(x['wall_seconds'] for x in d)
        loss=r['loss'] if side=='student' else r['win'];win=r['win'] if side=='student' else r['loss']
        sums.append([1,loss,win,int(r['draw']),s['polls'],s['sampled_plays'],s['sampled_waits'],
            s['submitted_plays'],s['pending_polls'],s['timed_wait_polls'],len(d),
            sum(x.get('hit',x.get('truncated',False)) for x in d),
            sum(x['fallback'] for x in d),sum(x['wall_overrun'] for x in d),
            sum(x['completed'] for x in d),sum(p),len(p)])
    ratios={key:(key,'games') for key in ('loss','win','draw')}
    ratios.update({key:(value,'polls') for key,value in
        [('play_rate','plays'),('WAIT_rate','waits'),('submitted_play_rate','submitted'),
         ('pending_poll_rate','pending'),('timed_wait_poll_rate','timed')]})
    if sum(x[10] for x in sums):
        ratios.update({key:(value,'decisions') for key,value in
            [('deadline_hit_rate','hits'),('fallback_rate','fallback'),
             ('wall_overrun_rate','overruns'),('completed_roots_per_decision','roots')]})
        ratios['mean_proposer_seconds']=('proposer_seconds','proposals')
    result=dict(games=len(records),terminal_games=sum(r['terminal'] for r in records),
        metrics=clustered(sums,names,ratios),
        cpu_seconds=sum(r['cpu_seconds'] for r in records),
        wall_seconds=sum(r['wall_seconds'] for r in records),
        command_hashes_sha256=__import__('hashlib').sha256(''.join(r['command_sha256'] for r in records).encode()).hexdigest())
    if latencies:
        result['proposer_seconds_p50_p95_p99']=np.quantile(latencies,[.5,.95,.99]).tolist()
        result['decision_wall_seconds_p50_p95_p99']=np.quantile(walls,[.5,.95,.99]).tolist()
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True)
    p.add_argument('--freeze-sha256',required=True);p.add_argument('--arm',choices=screen.ARMS)
    a=p.parse_args();job=Path(a.job);screen.execution_guard(str(job/'REPORTING.STOP'))
    f=screen.verify_freeze(job/'execution-freeze.json',a.freeze_sha256);torch.set_num_threads(1)
    if a.arm:
        store=TeacherStore(job/'heldout-corpus',job/'inputs/assets.npz')
        assert set(map(int,np.unique(store.arrays['perspective_ids'])))=={
            screen.BASES['teacher']+i for i in range(64)}
        policy=screen.load_student(f['checkpoints'][a.arm])
        result=dict(teacher=teacher(policy,store,True),all_poll_rows=teacher(policy,store,False),
            freeze_sha256=a.freeze_sha256,teacher_manifest_sha256=sha(job/'heldout-corpus/manifest.json'))
        # Compare supplemental rates to the frozen implementation's decisions.
        original,_=screen.agreement(policy,store)
        for key in ('play_recall','student_wait_rate','teacher_wait_rate'):
            assert abs(original[key]-result['teacher']['metrics'][key]['value'])<1e-6,key
        write_json(job/'supplement'/f'{a.arm}.json',result)
    else:
        d=json.loads((job/'diagnostics.json').read_text())
        reduced=screen.reduce_games(job/'cases',d,freeze_sha256=a.freeze_sha256)
        results={}
        for mode in ('h2h','fallback'):
            arms=screen.ARMS if mode=='h2h' else ('init',*screen.ARMS)
            results[mode]={}
            for arm in arms:
                records=[json.loads((job/'cases'/f'{mode}-{arm}-{i:04d}.json').read_text())
                         for i in range(screen.COUNTS[mode])]
                results[mode][arm]={side:games(records,side) for side in ('student','opponent')}
        write_json(job/'aggregate.json',dict(lane='exploration; no multiplicity adjustment',
            freeze_sha256=a.freeze_sha256,arms=reduced,game_diagnostics=results,
            bootstrap=dict(resamples=5000,seed=80991010,unit='whole game seed',ci='percentile 95%')))
if __name__=='__main__':main()
