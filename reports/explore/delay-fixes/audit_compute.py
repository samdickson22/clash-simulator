"""Compact task-only compute/GPU audit. Does not inspect any owner paths."""
import argparse,json
from datetime import datetime
from pathlib import Path
import numpy as np


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();hosts={};shards=[];incomplete=[];stops=[]
 def aggregate_for(host):
  return hosts.setdefault(host,dict(shards=0,games=0,worker_cpu_seconds=0.,shard_wall_seconds=0.,max_workers=0,
   worker_capacity_seconds=0.,stopped_attempts=0,gpu_samples=0,below80_samples=0,
   paused_worker_sample_seconds=0.,below80_unpaused_samples=0,throughput_guard_samples=0,throughput_measured_samples=0,throughput_below95_samples=0,throughput_ratios=[],gpu=[]))
 paths=sorted((a.root/'shards').glob('p*'))+sorted((a.root/'lag-only/shards').glob('p*'))
 for path in paths:
  receipt=path/'receipt.json'
  if not receipt.exists():incomplete.append(str(path.relative_to(a.root)));continue
  row=json.loads(receipt.read_text());host=row['host']
  aggregate=aggregate_for(host)
  # Resume receipts count fresh game CPU only; prior attempt CPU is added below.
  aggregate['shards']+=1;aggregate['games']+=row['games'];aggregate['worker_cpu_seconds']+=row['worker_cpu_seconds']
  aggregate['shard_wall_seconds']+=row['wall_seconds'];aggregate['max_workers']=max(aggregate['max_workers'],row['workers'])
  aggregate['worker_capacity_seconds']+=row['workers']*row['wall_seconds']
  gpu_path=path/'gpu.jsonl';records=[json.loads(line) for line in gpu_path.read_text().splitlines()] if gpu_path.exists() else []
  for i,sample in enumerate(records):
   if sample['gpu'] is None:continue
   aggregate['gpu_samples']+=1;aggregate['below80_samples']+=sample['gpu']<80
   aggregate['throughput_guard_samples']+=sample.get('policy')=='own-throughput-below95-v1'
   aggregate['throughput_below95_samples']+=any(m.get('below95',False) for m in sample.get('throughput',[]))
   measured=[m['sample']['rate']/m['baseline'] for m in sample.get('throughput',[]) if m.get('sample') and m.get('baseline')]
   aggregate['throughput_measured_samples']+=bool(measured)
   aggregate['throughput_ratios'].extend(measured)
   aggregate['below80_unpaused_samples']+=sample['gpu']<80 and sample.get('gpu_compute_job_present',True) and sample['workers']>sample['paused']
   aggregate['gpu'].append(sample['gpu'])
   if i+1<len(records):
    dt=records[i+1]['utc']-sample['utc']
    if 0<dt<10:aggregate['paused_worker_sample_seconds']+=sample['paused']*dt
  shards.append(dict(shard=str(path.relative_to(a.root)),host=host,games=row['games'],wall_seconds=row['wall_seconds'],worker_cpu_seconds=row['worker_cpu_seconds'],workers=row['workers']))
 snapshots=list((a.root/'receipts').glob('*.technical-stop.json'))
 evidence=a.root/'receipts/unreachable11-stop-evidence.json'
 if evidence.exists():snapshots.append(evidence)
 seen=set()
 for path in snapshots:
  stop=json.loads(path.read_text());label=stop['label']
  if label in seen:continue
  seen.add(label);wrapper=a.root/'receipts'/f'{label}.exit.json'
  if wrapper.exists():
   entry=json.loads(wrapper.read_text());host=entry['host'];start=datetime.fromisoformat(entry['started_utc']).timestamp()
   timing='wrapper receipt'
  elif label=='cpu-delay-fixes-p0025-primary-v1':
   host='127x11';launch=json.loads((a.root/'launch.json').read_text())
   start=min(r['started'] for r in launch['results']+launch['failed']);timing='initial six-host dispatch batch; own wrapper unavailable'
  else:raise ValueError('missing stopped-attempt timing/host receipt')
  workers=len(stop.get('verified_descendants',[])) or stop.get('verified_descendant_count',26)
  wall=stop['utc']-start;cpu=stop['observed_process_cpu_seconds'];aggregate=aggregate_for(host)
  aggregate['worker_cpu_seconds']+=cpu;aggregate['shard_wall_seconds']+=wall
  aggregate['worker_capacity_seconds']+=workers*wall;aggregate['max_workers']=max(aggregate['max_workers'],workers)
  aggregate['stopped_attempts']+=1
  stops.append(dict(label=label,host=host,workers=workers,wall_seconds=wall,observed_process_cpu_seconds=cpu,timing=timing))
 for host,row in hosts.items():
  row['mean_active_cores_over_shard_wall']=row['worker_cpu_seconds']/row['shard_wall_seconds']
  row['pool_utilization_over_shard_wall']=row['worker_cpu_seconds']/row['worker_capacity_seconds']
  row['gpu_p10_p50_p90']=np.quantile(row.pop('gpu'),[.1,.5,.9]).tolist() if row['gpu_samples'] else None
  ratios=row.pop('throughput_ratios')
  row['throughput_ratio_p10_p50_p90']=np.quantile(ratios,[.1,.5,.9]).tolist() if ratios else None
  row['observed_below80_fraction']=row['below80_samples']/row['gpu_samples'] if row['gpu_samples'] else None
  # Startup/tails and GPU pauses remain in the wall denominator.
 out=dict(hosts=hosts,shards=shards,incomplete_shards=incomplete,stopped_attempts=stops,
    unknown_cpu_attempts=['cpu-delay-fixes-p0025-resource-r2: host11 down; CPU unavailable'],
    worker_cpu_seconds=sum(r['worker_cpu_seconds'] for r in hosts.values()),
    note='Fresh game CPU plus verified stopped-attempt process CPU (includes stopped main initialization); successful main initialization/build/tests excluded. Down11 second-attempt CPU unavailable, so total is a lower bound. Utilization uses summed workers×attempt wall, retaining changed caps, startup/tails and GPU pauses. Pause counts are monitor-reported: brief verified idle-GPU drains on13/15 can overstate paused time; log gaps>=10s excluded. Below80 device samples include idle GPUs and baseline stalls while our workers pause. No continuous GPU>=80 claim.')
 a.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['hosts'],indent=2))


if __name__=='__main__':main()
