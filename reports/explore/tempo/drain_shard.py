"""Only an owned, already GPU-paused shard may be retired and resumed elsewhere."""
import argparse,json,os,signal,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sample=json.loads((a.out/'gpu-guard.jsonl').read_text().splitlines()[-1]);assert sample['paused'] and sample['throughput']<.95*sample['baseline'] and time.time()-sample['utc']<10
state=json.loads(Path('/mpac/sdicks02/repos/clasher-lease/jobs/'+a.label+'.state.json').read_text());pid=state['pid'];args=Path('/proc/'+str(pid)+'/cmdline').read_bytes().split(b'\0')
assert args[0].endswith(b'/python') and str(a.out).encode() in args and any(x.endswith(b'/tempo/worker_runtime.py') for x in args)
os.kill(pid,signal.SIGINT);print(json.dumps(dict(pid=pid,label=a.label,out=str(a.out),signal='SIGINT',sample=sample)))
