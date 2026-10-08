"""Execute on 127x01 after qualification; read each lease host and publish atomic receipts."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import socket
import subprocess

assert socket.gethostname().split('.')[0] == '127x01'
HOSTS = ('127x11','127x13','127x14','127x16','127x18','127x09','127x15')
BASE = '/mpac/sdicks02/repos/clasher-lease'
remote = r'''
import hashlib,json,socket
from pathlib import Path
b=Path('/mpac/sdicks02/repos/clasher-lease');h=socket.gethostname().split('.')[0]
def read(p):
 return json.loads(p.read_text()) if p.exists() else None
r={'host':h,'lease':read(Path('/mpac/sdicks02/fleet-leases')/(h+'.json')),'p16':read(b/'jobs/p16.json'),'gpu':read(b/'tmp/gpu-check.json'),'source':read(b/'jobs/source-verified.json'),'data':read(b/'jobs/data-copy.json'),'audit':read(b/'jobs/final-audit.json')}
r['setup_runs']=[read(p) for p in sorted((b/'jobs').glob('setup-*.exit.json'))]
r['native_sha256']=(b/'jobs/native.sha256').read_text().strip() if (b/'jobs/native.sha256').exists() else None
r['source_manifest_sha256']=hashlib.sha256((b/'source-sha256.json').read_bytes()).hexdigest() if (b/'source-sha256.json').exists() else None
r['historical_pin_drift']=read(b/'historical-pin-drift.json')
r['script_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file() and p.suffix in ('.py','.sh')}
print(json.dumps(r))
'''
output = Path('/mpac/sdicks02/jobs/clasher')
dataset_root=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data')
t3_paths=[p for p in (dataset_root/'receipts/T3-PASS.json',dataset_root/'c56-store-v1/T3-PASS.json') if p.is_file()]
for host in HOSTS:
    prior=output/f'lease-ready-{host}.json'
    if prior.exists() and json.loads(prior.read_text()).get('cpu_upgrade'):
        print(host, 'Preserving CPU-upgrade receipt; use publish_cpu_upgrade.py for a targeted refresh')
        continue
    result = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,'nice -n 10 python3 -'], input=remote, text=True, capture_output=True)
    if result.returncode:
        print(host, 'COLLECTION FAILED', result.stderr);continue
    r=json.loads(result.stdout); lease=r['lease']; cpu=bool(lease.get('cpu',host not in ('127x09','127x15'))) if lease else False
    smoke=r['p16']; gpu=r['gpu']; data=r['data']
    cpu_ok=bool(smoke and smoke.get('checked_episodes')==12 and smoke.get('mismatches')==[])
    gpu_ok=bool(gpu and gpu.get('full_required_suite_passed'))
    finished=bool(r['setup_runs'] and r['setup_runs'][-1].get('status')=='pass')
    lease_ok=bool(lease and lease.get('project')=='clasher' and not lease.get('reclaim') and not lease.get('refused') and dt.datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))>dt.datetime.now(dt.timezone.utc))
    copied=bool(data and data.get('status')=='pass')
    receipt={
      'host':host,'updated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'lease_path':f'/mpac/sdicks02/fleet-leases/{host}.json','lease':lease,'lease_valid':lease_ok,
      'footprint_path':BASE,'env_sh':BASE+'/env.sh','repo':BASE+'/repo','uv':BASE+'/tools/uv/uv',
      'python_version':'3.12.13','cpu_env':BASE+'/repo/.venv' if cpu else None,'gpu_env':BASE+'/envs/clasher-gpu',
      'rust_version':'1.97.1' if cpu else None,'launch_wrapper':BASE+'/run.sh',
      'smoke_result':{'status':'PASS' if cpu_ok else ('PENDING_OR_FAILED' if cpu else 'NOT_APPLICABLE_GPU_ONLY'),'result':smoke,'log':BASE+'/jobs/p16.log' if cpu else None},
      'gpu_check_result':{'status':'PASS' if gpu_ok else 'PENDING_OR_FAILED','required_probes':{k:v.get('status') for k,v in (gpu or {}).get('checks',{}).items()},'receipt':BASE+'/tmp/gpu-check.json','compile_required':False},
      'data_copied':copied,'data_path':BASE+'/data/c56-store-v1','data_receipt':data,
      'data_note':None if copied else ('T3-PASS.json present; checksum-verified staging pending.' if t3_paths else 'T3-PASS.json absent on hub at collection; training store not copied or qualified.'),
      'hub_t3_certificates':[str(p) for p in t3_paths],
      'caps':{'processes':lease.get('max_workers') if lease else None,'console_user_process_cap':16,'shared_resident_memory_bytes':64_000_000_000 if lease and lease.get('shared') else None,'minimum_gpu_free_mib':8192,'nice_minimum':10,'gpu_only':not cpu,'one_supervised_job_at_a_time':True},
      'qualified':lease_ok and finished and gpu_ok and (cpu_ok or not cpu) and bool(r['audit'] and r['audit']['status']=='pass'),
      'ready_for_cpu_evaluation':lease_ok and finished and cpu_ok,
      'ready_for_gpu_training_on_c56_store':lease_ok and finished and gpu_ok and copied,
      'source_snapshot':'127x01:/mpac/sdicks02/jobs/clasher/lease-source-20261008',
      'native_build':'rebuilt from snapshot; historical hub native source pins had drifted' if cpu else None,
      'adaptations':['lease-local paths and host allowlist','Python 3.12.13','GPU DataLoader and YOLO workers=1; torch/BLAS threads=1','12 GiB GPU pre-probe minimum to preserve 8 GiB headroom'],
      'evidence':r,
    }
    p=output/f'lease-ready-{host}.json';tmp=p.with_suffix('.json.tmp');tmp.write_text(json.dumps(receipt,indent=2)+'\n');tmp.replace(p)
    print(json.dumps({k:receipt[k] for k in ('host','qualified','data_copied','ready_for_cpu_evaluation','ready_for_gpu_training_on_c56_store')}))
