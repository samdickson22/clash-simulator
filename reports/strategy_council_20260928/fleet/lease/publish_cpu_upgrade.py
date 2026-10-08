"""Publish only 09/15 CPU upgrade receipts on the hub, preserving GPU/data history."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

assert socket.gethostname().split('.')[0] == '127x01'
BASE = '/mpac/sdicks02/repos/clasher-lease'
remote = r'''
import hashlib,json,socket,subprocess
from pathlib import Path
b=Path('/mpac/sdicks02/repos/clasher-lease');h=socket.gethostname().split('.')[0]
def read(p):return json.loads(p.read_text())
r={'host':h,'lease':read(Path('/mpac/sdicks02/fleet-leases')/(h+'.json')),'p16':read(b/'jobs/p16.json'),'audit':read(b/'jobs/final-audit.json'),'run':read(b/'jobs/cpu-upgrade-20261008-r1.exit.json'),'peer_native':read(b/'jobs/cpu-upgrade-peer-native.json'),'gpu':read(b/'tmp/gpu-check.json')}
r['native_sha256']=hashlib.sha256((b/'repo/engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest()
r['source_manifest_sha256']=hashlib.sha256((b/'source-sha256.json').read_bytes()).hexdigest()
r['script_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file() and p.suffix in ('.py','.sh')}
r['console_users']=int(subprocess.check_output([str(Path.home()/'.local/bin/fleet-console-users')],text=True).strip())
r['who']=subprocess.check_output(['who'],text=True)
r['python']=subprocess.check_output([str(b/'repo/.venv/bin/python'),'-B','-c','import platform;print(platform.python_version())'],text=True).strip()
r['gpu_free_mib']=[int(x) for x in subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).split()]
print(json.dumps(r))
'''
output=Path('/mpac/sdicks02/jobs/clasher')
for host in ('127x09','127x15'):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,'nice -n 10 python3 -'],input=remote,text=True,capture_output=True,check=True)
    r=json.loads(result.stdout);lease=r['lease'];run=r['run'];p16=r['p16']
    assert lease['project']=='clasher' and lease['coordinator_thread']=='0523ae6f-baa3-4d4e-b233-b392671670db'
    assert lease['cpu'] and not lease['gpu_only'] and lease['shared'] and lease['max_workers']==96
    assert not lease.get('refused') and not lease.get('reclaim')
    assert dt.datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))>dt.datetime.now(dt.timezone.utc)
    assert run['status']=='pass' and run['exit_code']==0 and run['memory_metric']=='pss'
    assert run['peak_processes']<=16 and run['peak_sampled_pss_bytes']<=64_000_000_000
    assert p16['checked_episodes']==12 and not p16['mismatches'] and r['audit']['status']=='pass'
    assert r['native_sha256']==r['peer_native']['native_sha256']
    assert r['gpu']['full_required_suite_passed'] and min(r['gpu_free_mib'])>=8192
    assert r['python']=='3.12.13'
    p=output/f'lease-ready-{host}.json'
    original=p.read_bytes();receipt=json.loads(original)
    assert receipt['evidence']['source_manifest_sha256']==r['source_manifest_sha256']
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=output/(p.name+'.pre-cpu-upgrade-'+stamp)
    with backup.open('xb') as f:f.write(original)
    shutil.copystat(p,backup)
    prior_checked=receipt['updated_utc']
    receipt['gpu_evidence_reused_without_rerun']=True
    receipt['data_status_last_checked_utc']=receipt.get('data_status_last_checked_utc',prior_checked)
    receipt['data_note']='Preserved from pre-CPU-upgrade receipt ('+prior_checked+'): '+(receipt.get('data_note') or 'See data receipt.')
    receipt.update(updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),lease=lease,lease_valid=True,cpu_env=BASE+'/repo/.venv',rust_version=None,qualified=True,ready_for_cpu_evaluation=True,
      smoke_result={'status':'PASS','result':p16,'log':BASE+'/jobs/p16.log'},
      native_build='Copied from qualified 127x11 lease footprint after matching all 137 engine source pins and native SHA-256; no local Rust build needed',
      previous_receipt_backup=str(backup),previous_receipt_sha256=hashlib.sha256(original).hexdigest(),cpu_upgrade=r)
    caps=receipt['caps'];caps.pop('shared_resident_memory_bytes',None)
    caps.update(processes=96,gpu_only=False,console_user_process_cap=16,
      console_user_detector='~/.local/bin/fleet-console-users',console_users_at_upgrade=r['console_users'],
      effective_process_cap_at_upgrade=16 if r['console_users']>0 or r['who'].strip() else 96,
      shared_pss_memory_bytes=64_000_000_000,memory_metric='sum of PSS across verified Clasher process tree',minimum_gpu_free_mib=8192)
    e=receipt['evidence'];e.update(lease=lease,p16=p16,audit=r['audit'],native_sha256=r['native_sha256'],script_sha256=r['script_sha256'])
    e['setup_runs'].append(run)
    temporary=p.with_suffix('.json.tmp-cpu-upgrade');temporary.write_text(json.dumps(receipt,indent=2)+'\n')
    assert p.read_bytes()==original,'Receipt changed concurrently; original and candidate preserved'
    temporary.replace(p)
    print(json.dumps({'host':host,'smoke':p16,'backup':str(backup),'peak_processes':run['peak_processes'],'peak_sampled_pss_bytes':run['peak_sampled_pss_bytes'],'effective_cap':caps['effective_process_cap_at_upgrade']}))
