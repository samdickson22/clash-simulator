"""30-minute host-local control/treatment check; GPU-job processes are read-only."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from gpu_guard import Guard,descendants,send

def harmonic(xs):return len(xs)/sum(1/x for x in xs)

def main():
    p=argparse.ArgumentParser();p.add_argument('--log',type=Path,required=True);p.add_argument('--gpu-pid',type=int,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--period',type=int,default=900);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[3];baseline=[];treatment=[];samples=[];offset=a.log.stat().st_size;started=time.time();phase='baseline';phase_start=time.monotonic();last_step=None;child=None;guard=None;batch=0
    def collect():
        nonlocal offset,last_step
        new=[]
        with a.log.open() as f:
            f.seek(offset)
            while True:
                at=f.tell();line=f.readline()
                if not line or not line.endswith('\n'):offset=at;break
                offset=f.tell()
                try:r=json.loads(line)
                except ValueError:continue
                if r.get('event')!='step' or 'rows_per_second_step' not in r or r['step']==last_step:continue
                last_step=r['step'];new.append(dict(utc=time.time(),phase=phase,step=r['step'],rate=r['rows_per_second_step']))
        return new
    try:
        with (a.out/'monitor.jsonl').open('a',buffering=1) as f:
            while True:
                new=collect();samples.extend(new)
                (baseline if phase=='baseline' else treatment).extend(s['rate'] for s in new)
                for s in new:f.write(json.dumps(s)+'\n')
                elapsed=time.monotonic()-phase_start
                if phase=='baseline' and elapsed>=a.period:
                    if len(baseline)<10:raise RuntimeError('insufficient measured baseline steps')
                    rate=harmonic(baseline);phase='treatment';phase_start=time.monotonic();guard=Guard(a.out/'pause-clock.json',log=a.log,baseline=rate,gpu_pid=a.gpu_pid)
                    f.write(json.dumps(dict(event='treatment-start',utc=time.time(),baseline=rate,workers=16))+'\n')
                elif phase=='treatment' and elapsed>=a.period:break
                if phase=='treatment':
                    if child is None or child.poll() is not None:
                        batch+=1;dest=a.out/f'batch{batch:02d}'
                        cmd=[sys.executable,'-B',str(root/'reports/explore/search-ab/home_worker.py'),'--offset',str((batch-1)*100),'--seed-offset','60000','--pairs','100','--arms','0','--workers','16','--max-seconds','840','--gpu-guard','--throughput-log',str(a.log),'--baseline-rate',str(rate),'--gpu-pid',str(a.gpu_pid),'--out',str(dest),'--full-decision-latency']
                        costs=root/'reports/explore/search-ab/case-costs.json'
                        if costs.exists():cmd+=['--case-costs',str(costs)]
                        child=subprocess.Popen(cmd)
                    # Inner worker owns its clock and guard. Monitor records only.
                    f.write(json.dumps(dict(event='treatment-sample',utc=time.time(),batch=batch,pid=child.pid))+'\n')
                (a.out/'progress.json').write_text(json.dumps(dict(start_utc=started,phase=phase,phase_seconds=elapsed,baseline_steps=len(baseline),treatment_steps=len(treatment),baseline=harmonic(baseline) if baseline else None,batches=batch))+'\n')
                time.sleep(2)
    finally:
        if child is not None and child.poll() is None:
            pids=descendants(child.pid);send(pids,signal.SIGCONT);send(pids,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:send(pids,signal.SIGKILL);child.wait()
    result=dict(start_utc=started,end_utc=time.time(),period_seconds=a.period,host=os.uname().nodename,workers=16,metric='fresh rows_per_second_step',baseline=baseline,treatment=treatment,samples=samples,baseline_rate=harmonic(baseline),treatment_rate=harmonic(treatment),ratio=harmonic(treatment)/harmonic(baseline),batches=batch)
    (a.out/'coexistence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','treatment','samples')}),flush=True)
if __name__=='__main__':main()
