"""Own-throughput guard and pause accounting for exploration runners only."""
import argparse,json,math,os,signal,subprocess,time
from collections import deque
from pathlib import Path
from clasher.analysis.loss_review.throughput_guard import PauseClock,ThroughputComparator,gpu_task_cores,idle_and_pin,expand_smt_siblings

class StepRates:
    def __init__(self,path,field='rows_per_second_step',window=5):
        if 'including_loader' in field or 'cumulative' in field:raise ValueError('interval throughput required')
        self.path=Path(path);self.field=field
        try:self.offset=self.path.stat().st_size
        except FileNotFoundError:self.offset=0
        self.rates=deque(maxlen=window);self.last_new=0.;self.last_step=None
    def read(self):
        if self.path.stat().st_size<self.offset:self.offset=0;self.rates.clear()
        with self.path.open() as f:
            f.seek(self.offset)
            while True:
                at=f.tell();line=f.readline()
                if not line or not line.endswith('\n'):self.offset=at;break
                self.offset=f.tell()
                try:r=json.loads(line);v=float(r[self.field]);step=r.get('step',r.get('frame',self.offset))
                except (ValueError,KeyError,TypeError):continue
                if not math.isfinite(v) or v<0 or step==self.last_step:continue
                self.last_step=step;self.rates.append(v);self.last_new=time.monotonic()
        # Harmonic mean: equal-size steps, weighted by their elapsed time.
        return (0. if 0. in self.rates else len(self.rates)/sum(1/v for v in self.rates)) if len(self.rates)>=3 and time.monotonic()-self.last_new<180 else None

def gpu_pids():
    s=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=5)
    return [int(v.strip()) for v in s.splitlines() if v.strip().isdigit()]

def descendants(root):
    rows={}
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            s=p.read_text();rows[int(p.parent.name)]=int(s[s.rindex(')')+2:].split()[1])
        except (OSError,ValueError):pass
    found={root}
    while True:
        more={pid for pid,ppid in rows.items() if ppid in found}
        if more<=found:return found
        found|=more

def send(pids,sig):
    for pid in pids:
        try:os.kill(pid,sig)
        except ProcessLookupError:pass

def cpu_list(s):
    result=set()
    for part in s.strip().split(','):
        lo,_,hi=part.partition('-');result.update(range(int(lo),int(hi or lo)+1))
    return result

class Guard:
    def __init__(self,clock_path,*,log=None,baseline=None,field='rows_per_second_step',gpu_pid=None,affinity=None):
        self.clock=PauseClock(clock_path);self.clock.set_paused(False)
        self.compare=ThroughputComparator(baseline) if baseline else None
        self.reader=StepRates(log,field) if log else None
        self.gpu_pid=gpu_pid;self.paused=False;self.excluded=set();self.allowed=set(affinity or os.sched_getaffinity(0));self.last_ticks={};self.core_history=deque()
    def sample(self,pids):
        try:apps=gpu_pids();present=bool(apps) if self.gpu_pid is None else self.gpu_pid in apps
        except (OSError,ValueError,subprocess.SubprocessError):apps=[];present=None
        cores,self.last_ticks=gpu_task_cores(apps,self.last_ticks)
        now=time.monotonic();self.core_history.append((now,cores))
        while self.core_history and now-self.core_history[0][0]>30:self.core_history.popleft()
        self.excluded=expand_smt_siblings(set().union(*(v for _,v in self.core_history)))
        available=self.allowed-self.excluded
        if not available:raise RuntimeError('No CPUs remain away from observed GPU cores; drain this lane')
        tids=set(pids)
        for pid in pids:
            tids.update(int(t.name) for t in Path(f'/proc/{pid}/task').glob('[0-9]*'))
        idle_and_pin(tids,self.excluded,allowed_cpus=self.allowed)
        try:rate=self.reader.read() if self.reader else None
        except OSError:rate=None
        pause=bool(present and rate is not None and self.compare and self.compare.should_pause(rate,gpu_job_present=True))
        event='sample'
        if pause!=self.paused:
            if pause:self.clock.set_paused(True);send(pids,signal.SIGSTOP);event='pause'
            else:send(pids,signal.SIGCONT);self.clock.set_paused(False);event='resume'
            self.paused=pause
        elif pause:send(pids,signal.SIGSTOP) # children created at the boundary
        return dict(utc=time.time(),event=event,paused=self.paused,gpu_job_present=present,throughput=rate,baseline=getattr(self.compare,'baseline',None),affinity=sorted(available),excluded_cpus=sorted(self.excluded))
    def close(self,pids):
        send(pids,signal.SIGCONT);self.clock.set_paused(False);self.paused=False

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--clock',type=Path,required=True);p.add_argument('--throughput-log',required=True);p.add_argument('--baseline-rate',type=float,required=True);a=p.parse_args()
    jobs=Path('/mpac/sdicks02/jobs/clasher');pid=int((jobs/(a.label+'.pid')).read_text());assert os.getpgid(pid)==pid
    guard=Guard(a.clock,log=a.throughput_log,baseline=a.baseline_rate);a.out.parent.mkdir(parents=True,exist_ok=True)
    try:
        with a.out.open('a',buffering=1) as f:
            while not (jobs/(a.label+'.exit')).exists():
                f.write(json.dumps(guard.sample(descendants(pid)))+'\n');time.sleep(2)
    finally:guard.close(descendants(pid))
if __name__=='__main__':main()
