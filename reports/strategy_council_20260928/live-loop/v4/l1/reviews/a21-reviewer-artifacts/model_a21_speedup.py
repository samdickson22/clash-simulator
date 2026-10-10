"""Reviewer throughput model for A19+A20+A21 on 04 (time-stepped flock simulation).

Recalibrated (the A20-review model used a 04-heavy seal probe with 03=0.108 and was
wrong for the 23/24 epochs whose entries route to 03). Profile for an 03-heavy
epoch, from the owner's first-wave report (epochs 3-7: held03/(held+unlocked) ~0.47-0.74):
  q   = fraction of a verifier's work done while holding 127x03.io.lock (frozen/A20 scope)
  h03 = mean A20 03 hold (median 03 record 8.3 MB: consumer CPU 0.36 s + mux 0.01 s ~0.4 s)
  08 = 0.025 of work, same hold;  04 = 0.01 (already narrowed by A20 for A19 workers).
A21 (A19 workers only) keeps r*hold locked and does (1-r)*hold as unlocked work;
r from measure_remote_split.py on real 03 records (0.10-0.14 transfer-only, plus
unchanged hashes/reads/mux), swept 0.12-0.30. Serial keeps the full scope and a
BLOCKING flock (served first); A19 polls LOCK_NB every 0.2 s. Work in serial-equivalents.
A model, not a measurement; first-wave telemetry of a fresh attempt is the ETA authority.
"""
import json,random,sys
DT=0.005
def run(workers,q,r,serial=True,seconds=1200,seed=1,h03=0.4,a21=True):
    rng=random.Random(seed)
    prof={'03':(q,h03),'08':(0.025,h03),'04':(0.01,0.4)}
    acq={k:f/h for k,(f,h) in prof.items()};tot=sum(acq.values());gap=(1-sum(f for f,_ in prof.values()))/tot
    class P:pass
    def plan(p):
        k=rng.choices(list(acq),list(acq.values()))[0];hold=rng.expovariate(1/prof[k][1])
        rr=(r if k in('03','08') and a21 else 1.0) if not p.serial else 1.0
        if k=='04' and not p.serial:rr=0.02
        p.lock=k;p.hold=hold*rr;p.after=hold*(1-rr);p.state='compute';p.left=rng.expovariate(1/gap)
    ps=[]
    for i in range(workers+(1 if serial else 0)):
        p=P();p.serial=serial and i==0;p.work=0.;p.next_poll=0.;plan(p);ps.append(p)
    owner={k:None for k in acq};t=0.;held={k:0. for k in acq}
    while t<seconds:
        for p in ps:
            if p.state in('compute','hold','after'):
                p.left-=DT;p.work+=DT
                if p.state=='hold':held[p.lock]+=DT
                if p.left<=0:
                    if p.state=='compute':p.state='want'
                    elif p.state=='hold':
                        owner[p.lock]=None
                        if p.after>0:p.state='after';p.left=p.after
                        else:plan(p)
                    else:plan(p)
        for k in acq:
            if owner[k] is None:
                want=[p for p in ps if p.state=='want' and p.lock==k]
                ser=[p for p in want if p.serial];due=[p for p in want if not p.serial and p.next_poll<=t]
                g=ser[0] if ser else (rng.choice(due) if due else None)
                if g:owner[k]=g;g.state='hold';g.left=g.hold
        for p in ps:
            if p.state=='want' and not p.serial and p.next_poll<=t:p.next_poll=t+0.2
        t+=DT
    s=[p.work/seconds for p in ps if p.serial];w=[p.work/seconds for p in ps if not p.serial]
    return dict(workers=workers,q=q,r=r if a21 else None,serial_present=serial,serial_rate=round(s[0],3) if s else None,
        a19_aggregate_rate=round(sum(w),3),lock03_utilization=round(held['03']/seconds,3))
if __name__=='__main__':
    secs=float(sys.argv[1]) if len(sys.argv)>1 else 1200
    for q in (0.5,0.63,0.75):
        print(json.dumps(run(12,q,1.0,True,secs,a21=False)),flush=True)       # current A19+A20 calibration
        for r in (0.12,0.2,0.3):print(json.dumps(run(12,q,r,True,secs)),flush=True)
        print(json.dumps(run(12,q,0.2,False,secs)),flush=True)               # after serial retirement / no serial
