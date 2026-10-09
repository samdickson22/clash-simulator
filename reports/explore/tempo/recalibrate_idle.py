"""Measured unloaded baseline refresh after owned simulation workloads exited."""
import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=180);a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo');path=root/'receipts/perception-rate.jsonl';begin=time.time()
def verify_idle():
 for f in Path('/proc').glob('[0-9]*/cmdline'):
  try:args=f.read_bytes().split(b'\0')
  except OSError:continue
  if args and args[0].endswith(b'/python') and any(x.endswith(b'/tempo/worker_runtime.py') for x in args):raise ValueError('own tempo runtime still active')
verify_idle();old=json.loads(path.with_suffix('.baseline.json').read_text())
while time.time()-begin<a.seconds:verify_idle();time.sleep(10)
end=time.time();rows=[json.loads(x) for x in path.read_text().splitlines()];samples=[r for r in rows if begin<r['utc']<=end];assert len(samples)>=a.seconds/12 and all(r['frames_per_second_step']>0 for r in samples)
rate=sum(r['frames_per_second_step'] for r in samples)/len(samples);receipt=dict(old=old,new_baseline=rate,seconds=end-begin,rate_samples=samples,control='own tempo simulation runtimes absent at every10s check',utc=end)
(root/'receipts/baseline-idle-refresh.json').write_text(json.dumps(receipt,indent=2)+'\n');path.with_suffix('.baseline.json').write_text(json.dumps(dict(old,baseline=rate,refresh_utc=end,control_seconds=end-begin,refresh_receipt=str(root/'receipts/baseline-idle-refresh.json')))+'\n');print(json.dumps(dict(baseline=rate,seconds=end-begin)))
