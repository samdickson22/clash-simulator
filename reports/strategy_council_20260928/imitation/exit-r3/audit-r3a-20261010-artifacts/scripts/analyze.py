"""Auditor analysis of R3a/K0 descriptive raw case files (read-only)."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);out={}
def load(arm,i):return json.loads((root/f'fallback-{arm}-{i:04d}.json').read_text())
rows={a:[load(a,i) for i in range(600)] for a in ('K0','R3a')}
def q(v,ps=(.5,.95)):v=np.asarray(v,float);return [round(float(np.quantile(v,p)),5) for p in ps] if len(v) else None
for arm,rs in rows.items():
    for who in ('student_seat','opp_seat'):
        S=[r['stats'][r['seat'] if who=='student_seat' else 1-r['seat']] for r in rs]
        D=[d for s in S for d in s['deadlines']]
        agg={k:int(sum(s[k] for s in S)) for k in ('polls','sampled_plays','sampled_waits','submitted_plays','accepted_plays','pending_polls','timed_wait_polls')}
        agg['search_calls']=len(D);agg['hits']=sum(d['hit'] for d in D);agg['fallbacks']=sum(d['fallback'] for d in D)
        agg['completed']=sum(d['completed'] for d in D);agg['overruns']=sum(d['wall_overrun'] for d in D)
        pre=[d for d in D if d['fallback'] and d['completed']==0 and d['candidates']>0]
        agg['cand_all_med_p95']=q([d['candidates'] for d in D])
        agg['cand_fallback_med_p95']=q([d['candidates'] for d in D if d['fallback']])
        agg['cand_nohit_med_p95']=q([d['candidates'] for d in D if not d['hit']])
        agg['mean_candidates_unpruned_fallback']=float(np.mean([d['candidates'] for d in D if d['fallback']])) if agg['fallbacks'] else None
        agg['wall_med_p95_p99']=q([d['wall_seconds'] for d in D],(.5,.95,.99))
        agg['wall_nohit_med']=q([d['wall_seconds'] for d in D if not d['hit']])
        agg['completed_per_call']=agg['completed']/len(D);agg['hit_rate']=agg['hits']/len(D);agg['fallback_rate']=agg['fallbacks']/len(D)
        agg['proposer_med_p95_ms']=[x*1000 for x in q([p for s in S for p in s['proposer_seconds']])]
        agg['overrun_gt_250ms']=sum(d['wall_seconds']>.25 for d in D)
        out[f'{arm}/{who}']=agg
    out[f'{arm}/game']=dict(loss=float(np.mean([r['loss'] for r in rs])),ticks_med=q([r['ticks'] for r in rs]),cpu_med=q([r['cpu_seconds'] for r in rs]),wall_med=q([r['wall_seconds'] for r in rs]),
        max_ticks_games=sum(r['ticks']>=6001 for r in rs),draws=sum(r['draw'] for r in rs),seat0_loss=float(np.mean([r['loss'] for r in rs if r['seat']==0])),seat1_loss=float(np.mean([r['loss'] for r in rs if r['seat']==1])),
        cores=sorted({r['context']['affinity'][0] for r in rs}).__len__(),
        checkpoint=sorted({r['checkpoint_sha256'] for r in rs}),native=sorted({r['native_sha256'] for r in rs}),runner=sorted({r['frozen_runner_sha256'] for r in rs}),
        min_timer_offset_ms=min(r['checks']['min_timer_offset_seconds'] for r in rs)*1000)
# pairing
K,R=rows['K0'],rows['R3a']
assert all((k['seed'],k['seat'],k['own_deck'],k['opponent_deck'])==(r['seed'],r['seat'],r['own_deck'],r['opponent_deck']) for k,r in zip(K,R))
same_core=sum(k['context']['affinity']==r['context']['affinity'] for k,r in zip(K,R))
dl=np.array([r['loss']-k['loss'] for k,r in zip(K,R)])
tab={f'K0={a},R3a={b}':int(sum((k['loss']==a)&(r['loss']==b) for k,r in zip(K,R))) for a in (0,1) for b in (0,1)}
rng=np.random.default_rng(80991013);ix=rng.integers(600,size=(5000,600));bs=dl[ix].mean(1)
# per-deck matchup
deck={}
for d in range(5):
    sel=[i for i in range(600) if i%5==d];deck[f'own{d}']=dict(K0=float(np.mean([K[i]['loss'] for i in sel])),R3a=float(np.mean([R[i]['loss'] for i in sel])))
# mcnemar exact
from math import comb
b_,c_=tab['K0=1,R3a=0'],tab['K0=0,R3a=1'];n=b_+c_;p=min(1,2*sum(comb(n,k) for k in range(0,min(b_,c_)+1))/2**n)
# K0 mirror: cases where whole command sequence equal between arms? (should not be)
out['pairing']=dict(same_core_pairs=same_core,table=tab,paired_mean=float(dl.mean()),ci_rerun=[float(np.quantile(bs,.025)),float(np.quantile(bs,.975))],mcnemar_p=p,per_own_deck=deck,
    order_effect=dict(K0_first=float(np.mean([dl[i] for i in range(600) if i%2==0])),R3a_first=float(np.mean([dl[i] for i in range(600) if i%2==1]))))
# time-share: fit cpu_seconds ~ a*nonsearch_polls_v1 + b*nonsearch_polls_student + sum(search wall) + c*ticks
X=[];y=[]
for arm,rs in rows.items():
    for r in rs:
        st=r['stats'];sw=sum(d['wall_seconds'] for s in st for d in s['deadlines'])
        ns=[s['polls']-len(s['deadlines']) for s in st];stu=ns[r['seat']] if arm=='R3a' else 0;v1=sum(ns)-stu
        X.append([v1,stu,r['ticks']]);y.append(r['wall_seconds']-sw)
X=np.array(X,float);y=np.array(y);coef,*_=np.linalg.lstsq(X,y,rcond=None)
out['nonsearch_cost_fit_ms']=dict(v1_poll=coef[0]*1000,student_poll=coef[1]*1000,per_tick=coef[2]*1000,r2=float(1-((X@coef-y)**2).sum()/((y-y.mean())**2).sum()))
print(json.dumps(out,indent=1))
