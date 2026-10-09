"""Refresh drifting capture baseline only after verified own-sim-free control."""
import argparse,json,os,signal,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo')
rate_path=root/'receipts/perception-rate.jsonl';baseline_path=rate_path.with_suffix('.baseline.json');old=json.loads(baseline_path.read_text());original=root/'receipts'/('baseline-recalibration-'+a.host+'.json')
if original.exists():old=json.loads(original.read_text())['old']
samples=[json.loads(x) for x in (root/'early-reporting/gpu-guard.jsonl').read_text().splitlines()];now=time.time();control=[r for r in samples if r['utc']>=now-120]
assert len(control)>=40 and now-control[0]['utc']>=110 and all(r['paused'] for r in control),'require continuous own-sim pause control'
label='tempo-early-'+a.host+'-v1';state=json.loads(Path('/mpac/sdicks02/repos/clasher-lease/jobs/'+label+'.state.json').read_text())
# Guard owns all simulation descendants; verify every simulator PID is stopped.
pids=[];cpu=0.
for path in Path('/proc').glob('[0-9]*/cmdline'):
 try:args=path.read_bytes().split(b'\0');stat=(path.parent/'stat').read_text();parts=stat[stat.rindex(')')+2:].split()
 except OSError:continue
 if b'clasher.analysis.loss_review.simulate' in args and str(root/'early-reporting').encode() in args:
  assert parts[0]=='T',f'simulator not stopped: {path.parent.name}';pids.append(int(path.parent.name));cpu+=(int(parts[11])+int(parts[12]))/os.sysconf('SC_CLK_TCK')
assert pids,'no owned stopped simulators'
rates=[json.loads(x) for x in rate_path.read_text().splitlines()];window=[r for r in rates if r['utc']>=now-120];assert len(window)>=11
# Same interval-frame-count metric as initial calibration, while our sims are stopped.
new_rate=sum(r['frames_per_second_step'] for r in window)/len(window)
receipt=dict(host=a.host,old=old,new_baseline=new_rate,control_seconds=now-control[0]['utc'],control_samples=len(control),own_stopped_sim_pids=pids,stopped_sim_cpu_seconds=cpu,rate_samples=window,reason='GPU capture rate remains below initial baseline with own simulations continuously stopped; measured phase drift, remeasure unloaded current rate',utc=now)
if a.apply:
 updated=dict(old,baseline=new_rate,recalibration=receipt['reason'],recalibration_utc=now,control_seconds=receipt['control_seconds']);baseline_path.write_text(json.dumps(updated)+'\n')
 # Interrupt only the verified own runtime supervisor; it resumes then terminates
 # its descendants in its existing BaseException cleanup, preserving game files.
 runtimes=[]
 for path in Path('/proc').glob('[0-9]*/cmdline'):
  try:args=path.read_bytes().split(b'\0')
  except OSError:continue
  if args and args[0].endswith(b'/python') and str(root/'worker_runtime.py').encode() in args and str(root/'early-reporting').encode() in args:runtimes.append(int(path.parent.name))
 assert len(runtimes)==1,runtimes;receipt['interrupted_runtime_pid']=runtimes[0];os.kill(runtimes[0],signal.SIGINT)
(root/'receipts'/('baseline-recalibration-'+a.host+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('rate_samples','old','own_stopped_sim_pids')}))
