"""Qualified complete paired terminal blocks only; original R3a never adoptable."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
import numpy as np
from admission import allowed,frozen,sha
from protocol import BASES,stage,arm_list,order,decision
from journal import record
from imitation.exit_r1.rows import write_json
def bootstrap(v):
    v=np.asarray(v,float);rng=np.random.default_rng(80991013);ix=rng.integers(len(v),size=(5000,len(v)));samples=v[ix].mean(1)
    return dict(value=float(v.mean()),ci95=list(map(float,np.quantile(samples,[.025,.975]))))
def run(j,lane,smoke):
    assert allowed(j) and os.sched_getaffinity(0)=={55};f=frozen(j);record(j,'reducer',lane=lane,smoke=smoke)
    folder=j/stage(lane,smoke);done=json.loads((folder/'POOL-DONE.json').read_text());assert done['status']=='complete'
    arms=arm_list(lane,json.loads((j/'stage1-results.json').read_text()) if lane=='stage2' else None);assert done['arms']==arms
    losses={a:[] for a in arms};diagnostics={a:dict(wins=0,draws=0,deadline_calls=0,deadline_hits=0,fallback_uses=0,wall_overruns=0,completed_roots=0,proposer_seconds=[]) for a in arms};proofs=[]
    for i in range(2 if smoke else 600):
        assert allowed(j)
        p=folder/'blocks'/f'{i:04d}.json';b=json.loads(p.read_text());assert b['complete'] and b['lane']==lane and b['smoke']==smoke and b['index']==i and b['arms']==arms and b['arm_order']==order(arms,i)
        assert b['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json') and [v['arm'] for v in b['cases']]==b['arm_order']
        assert b['context']['host']=='127x03' and b['context']['nice']==10 and b['context']['scheduler']==0 and len(b['context']['affinity'])==1
        keys=[]
        for item in b['cases']:
            a=item['arm'];case=folder/'cases'/f'fallback-{a}-{i:04d}.json';assert sha(case)==item['sha256'];v=json.loads(case.read_text())
            assert v['terminal'] and v['loss'] in (0,1) and (v['mode'],v['arm'],v['index'],v['seat'],v['seed'])==('fallback',a,i,i%2,BASES[lane][int(smoke)]+i)
            assert v['smoke']==smoke and v['freeze_sha256']==sha(j/'evaluation-freeze.json') and v['context']==b['context']
            assert v['protocol']==f['protocol'] and v['threads']==1 and v['horizon']==160 and v['deadline_seconds']==.2 and v['return_reserve_seconds']==.008
            assert v['native_sha256']==f['files']['reporting-native/clasher_core.abi3.so'] and v['frozen_runner_sha256']==f['files']['eval-source/imitation/exit_r1/screen.py']
            assert v['checks']['fallback_calls']>0 and v['checks']['proposer_calls']>0 and not v['adoption_eligible']
            if a!='K0':
                off=json.loads((j/'offline'/f'{a}.json').read_text());assert v['checkpoint_sha256']==off['checkpoint_sha256'] and v['calibration_sha256']==sha(j/'offline'/f'{a}-calibration.json')
                assert v['checks']['student_fallback_calls']>0 and v['checks']['student_proposer_calls']>0
                if lane=='stage2':assert off['stage1_complete'] and off['survives']
                else:assert a=='R3a' and not off['survives'] and v['never_adoptable']
            else:assert v['checkpoint_sha256']==f['files']['inputs/main02.pt']
            keys.append((v['seed'],v['seat'],v['own_deck'],v['opponent_deck']));losses[a].append(v['loss']);d=diagnostics[a];d['wins']+=v['win'];d['draws']+=v['draw'];s=v['stats'][i%2];d['proposer_seconds'].extend(s['proposer_seconds'])
            for stats in s['deadlines']:
                d['deadline_calls']+=1;d['deadline_hits']+=bool(stats['hit']);d['fallback_uses']+=bool(stats['fallback']);d['wall_overruns']+=bool(stats['wall_overrun']);d['completed_roots']+=stats['completed']
        assert all(k==keys[0] for k in keys),'paired seed/seat/deck mismatch'
        proofs.append(dict(index=i,block_sha256=sha(p),cases=b['cases']))
    if smoke:
        write_json(j/('qualification-'+lane+'.json'),dict(passed=True,lane=lane,excluded_smoke=True,blocks=proofs,evaluation_freeze_sha256=sha(j/'evaluation-freeze.json')));return
    result={}
    for a in arms:
        d=diagnostics[a];v=np.asarray(d.pop('proposer_seconds'));d['proposer_latency_median_seconds']=float(np.median(v));d['proposer_latency_p95_seconds']=float(np.quantile(v,.95))
        r=dict(arm=a,cases=600,terminal=600,loss=bootstrap(losses[a]),diagnostics=d)
        if a!='K0':
            paired=bootstrap(np.asarray(losses[a])-np.asarray(losses['K0']));r.update(paired_loss_change_vs_K0=paired,**decision(lane,paired['ci95'][1]))
        result[a]=r
    write_json(j/('descriptive-results.json' if lane=='descriptive' else 'stage2-results.json'),dict(lane=lane,protocol=f['protocol'],never_adoptable=lane=='descriptive',arms=result,paired_seeds=600,seed_base=BASES[lane][0],bootstrap_seed=80991013,bootstrap_resamples=5000,evaluation_freeze_sha256=sha(j/'evaluation-freeze.json'),block_proofs=proofs,exploration_no_multiplicity_adjustment=True,live_adoption=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--lane',choices=tuple(BASES),required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job);t=time.monotonic();status='failed'
    try:run(j,a.lane,a.smoke);status='complete'
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);write_json(j/f'reduce-{a.lane}-{int(a.smoke)}-meter-{os.getpid()}.json',dict(status=status,pid=os.getpid(),pgid=os.getpgrp(),parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()))
