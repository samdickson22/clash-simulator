"""Fixed-work simulator action/winner parity with and without SIGSTOP."""
import gzip,hashlib,json,signal,subprocess,sys,time
from pathlib import Path
from gpu_guard import Guard,descendants,send
from clasher.analysis.loss_review.throughput_guard import PauseClock
root=Path(__file__).resolve().parents[3];out=root/'reports/explore/search-ab/pause-parity-v3';results=[]
for paused in (False,True):
    dest=out/('paused' if paused else 'unpaused');dest.mkdir(parents=True,exist_ok=True);clock=PauseClock(dest/'pause-clock.json');clock.set_paused(False)
    cmd=['chrt','--idle','0',sys.executable,'-B','-m','clasher.analysis.loss_review.simulate','--out',str(dest),'--workers','4','--pairs','1','--seed-base',str(2**48+70000),'--delays','27','--arms','0','C','R','CR','--reserve-weight','1','--exclusions',str(root/'reports/explore/search-ab/exclusions.json'),'--pause-clock',str(clock.path),'--full-decision-latency','--trace']
    if paused:
        costs=dest/'case-costs.json';costs.write_text(json.dumps({'C':8,'CR':5,'R':3,'0':1}));cmd+=['--case-costs',str(costs)]
    policy=Guard(dest/'pause-clock.json');policy.sample(set())
    child=subprocess.Popen(cmd);start=time.monotonic();next_pause=8;pauses=0
    while child.poll() is None:
        policy.sample(descendants(child.pid))
        if paused and pauses<3 and time.monotonic()-start>=next_pause:
            pids=descendants(child.pid);clock.set_paused(True);send(pids,signal.SIGSTOP);time.sleep(1);send(pids,signal.SIGCONT);clock.set_paused(False);pauses+=1;next_pause+=8
        time.sleep(.2)
    assert child.returncode==0
    rows={}
    for trace in (dest/'traces').glob('*.json.gz'):
        with gzip.open(trace,'rt') as f:r=json.load(f)
        encoded=json.dumps(r['actions'],separators=(',',':')).encode()
        rows[trace.name]=dict(actions_sha256=hashlib.sha256(encoded).hexdigest(),winner=r['metadata']['winner'],actions=len(r['actions']))
    results.append(dict(paused=paused,forced_pauses=pauses,clock=clock.snapshot(),games=rows))
assert results[0]['games']==results[1]['games'] and len(results[0]['games'])==4
proof=dict(matched=True,games=4,seed=2**48+70000,scope='fixed-work; all four arms; accepted/rejected actions + winner; permuted LPT dispatch',runs=results)
(root/'reports/explore/search-ab/receipts/pause-parity.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)
