"""Drain only a verified owned shard already backing off below its GPU baseline."""
import argparse,json,os,signal,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--host',required=True);a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo')
sample=json.loads((root/'early-reporting/gpu-guard.jsonl').read_text().splitlines()[-1]);assert sample['paused'] and sample['throughput']<.95*sample['baseline'] and time.time()-sample['utc']<10
state=json.loads(Path('/mpac/sdicks02/repos/clasher-lease/jobs/tempo-early-'+a.host+'-v1.state.json').read_text());pid=state['pid'];args=Path('/proc/'+str(pid)+'/cmdline').read_bytes().split(b'\0')
assert args[0].endswith(b'/python') and str(root/'worker_runtime.py').encode() in args and str(root/'early-reporting').encode() in args
(root/'receipts'/('early-drain-'+a.host+'.json')).write_text(json.dumps(dict(pid=pid,host=a.host,sample=sample,utc=time.time(),reason='already-paused shard drains; original outputs preserved, no change to GPU processes'),indent=2)+'\n')
os.kill(pid,signal.SIGINT);print(json.dumps(dict(pid=pid,host=a.host,signal='SIGINT',reason='drain already GPU-paused own shard')))
