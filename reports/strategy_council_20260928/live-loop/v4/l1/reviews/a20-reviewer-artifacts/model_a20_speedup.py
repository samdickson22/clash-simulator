"""Reviewer throughput model for A19+A20 on 04 (time-stepped lock simulation).

Calibrated to the r4 reviewer's measured live seal child profile
(a19-reviewer-artifacts/r4/probe-04-lock-occupancy.json, 300 s, cpu 0.987):
  127x04.io.lock hold 0.534 with 157 acquisitions, 127x03 0.108 / 24, 127x08 0.026 / 6.
Serial (frozen scope) keeps all of that in-lock and uses a BLOCKING flock (served first
when the lock frees). A19 workers poll LOCK_NB every 0.2 s (a19/a20 one()).
A20 shrinks only the 04 hold to `r` of its frozen length (measured r<=0.02 on real 04
records, reviews/a20-reviewer-artifacts/real-record-split.json); 03/08 holds unchanged.
Work = serial-equivalent seconds; waiting accrues no work. Output: work rate per process.
This is a model, not a measurement; first-wave telemetry stays the ETA authority.
"""
import json,random,sys
DT=0.01
LOCKS={'04':(157,0.534),'03':(24,0.108),'08':(6,0.026)}
ACQ=sum(n for n,_ in LOCKS.values())/300.          # acquisitions per work-second
GAP=(1-sum(f for _,f in LOCKS.values()))/ACQ        # mean unlocked work between acquisitions

class Proc:
    def __init__(s,rng,serial,r):
        s.rng=rng;s.serial=serial;s.r=r;s.work=0.;s.state=None;s.next_poll=0.;s.plan()
    def plan(s):
        names=list(LOCKS);w=[LOCKS[n][0] for n in names]
        s.lock=s.rng.choices(names,w)[0];n,f=LOCKS[s.lock];hold=s.rng.expovariate(1/(f*300/n))
        if s.lock=='04' and not s.serial:s.hold,s.after=hold*s.r,hold*(1-s.r)   # parse moves outside
        else:s.hold,s.after=hold,0.
        s.state='compute';s.left=s.rng.expovariate(1/GAP)
def run(workers,r,serial=True,seconds=3600,seed=1):
    rng=random.Random(seed);ps=([Proc(rng,True,r)] if serial else [])+[Proc(rng,False,r) for _ in range(workers)]
    owner={k:None for k in LOCKS};t=0.
    while t<seconds:
        for p in ps:                                   # progress
            if p.state in('compute','hold','after'):
                p.left-=DT;p.work+=DT
                if p.left<=0:
                    if p.state=='compute':p.state='want'
                    elif p.state=='hold':
                        owner[p.lock]=None
                        if p.after>0:p.state='after';p.left=p.after
                        else:p.plan()
                    else:p.plan()
        for k in LOCKS:                                # grant: blocking serial first, then due pollers
            if owner[k] is None:
                want=[p for p in ps if p.state=='want' and p.lock==k]
                ser=[p for p in want if p.serial];due=[p for p in want if not p.serial and p.next_poll<=t]
                g=ser[0] if ser else (rng.choice(due) if due else None)
                if g:owner[k]=g;g.state='hold';g.left=g.hold
        for p in ps:
            if p.state=='want' and not p.serial and p.next_poll<=t:p.next_poll=t+0.2
        t+=DT
    s=[p.work/seconds for p in ps if p.serial];w=[p.work/seconds for p in ps if not p.serial]
    return dict(workers=workers,r=r,serial_present=serial,serial_rate=round(s[0],3) if s else None,a19_aggregate_rate=round(sum(w),3),per_worker=round(sum(w)/max(1,len(w)),3))
if __name__=='__main__':
    out=[]
    for serial in (True,False):
        for r in (1.0,0.02,0.05):
            for n in (6,12):out.append(run(n,r,serial,seconds=float(sys.argv[1]) if len(sys.argv)>1 else 1800));print(json.dumps(out[-1]),flush=True)
