"""Estimate per-poll inference cost difference student vs v1 from non-search wall time."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);X=[];y=[];meta=[]
for arm in ('K0','R3a'):
    for i in range(600):
        r=json.loads((root/f'fallback-{arm}-{i:04d}.json').read_text());st=r['stats']
        sw=sum(d['wall_seconds'] for s in st for d in s['deadlines'])
        ns=[s['polls']-len(s['deadlines']) for s in st]
        stu=ns[r['seat']] if arm=='R3a' else 0
        X.append([1,r['ticks'],sum(ns)-stu,stu]);y.append(r['wall_seconds']-sw);meta.append(arm)
X=np.array(X,float);y=np.array(y)
# polls are ~collinear with ticks; identify student-minus-v1 per-poll cost via contrast
A=np.column_stack([X[:,0],X[:,1],X[:,3]]);c,*_=np.linalg.lstsq(A,y,rcond=None)
res=y-A@c;boot=[]
rng=np.random.default_rng(1)
for _ in range(2000):
    ix=rng.integers(len(y),size=len(y));cc,*_=np.linalg.lstsq(A[ix],y[ix],rcond=None);boot.append(cc[2])
print(json.dumps(dict(intercept_s=c[0],per_tick_ms=c[1]*1e3,student_minus_v1_per_nonsearch_poll_ms=c[2]*1e3,ci95_ms=[float(np.quantile(boot,.025))*1e3,float(np.quantile(boot,.975))*1e3],
  nonsearch_wall_per_tick_ms={a:float(np.mean([y[k]/X[k,1] for k in range(len(y)) if meta[k]==a]))*1e3 for a in ('K0','R3a')}),indent=1))
