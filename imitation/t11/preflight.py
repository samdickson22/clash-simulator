"""Read only T11 live-lease, resource, registration and copy launch guard."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import subprocess
from .train import frozen
from imitation.t5.guards import sha,role_guard


def main():
    host=socket.gethostname().split('.')[0];assert host in ('127x16','127x18')
    base=Path('/mpac/sdicks02/repos/clasher-lease');work=base/'t11-20261008-v1';source=work/'source'
    lease=json.loads(Path('/mpac/sdicks02/fleet-leases',host+'.json').read_text())
    assert lease['project']=='clasher' and lease['shared'] and lease['gpu'] and not lease.get('refused') and not lease.get('reclaim')
    now=datetime.now(timezone.utc);assert datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))>now
    assert now<datetime.fromisoformat('2026-10-09T04:20:00+00:00')
    assert sha(base/'lease_watch.py')=='00cdaa8ad3be41a0a85481d318ad03920b87e2564ab541e8f9a9d5bf801d246f'
    m,pins=frozen(source,source/'imitation/gate-a-v2/executable-manifest.json')
    copy=json.loads((work/'copy-receipt.json').read_text());assert copy['passed'] and copy['all_sha256_equal']
    assert copy['store_manifest_sha256']==m['store_manifest_sha256'] and copy['manifest_sha256']==pins['T11_manifest']
    for role in ('train','dev'):role_guard(base/'data/v2-store-v1'/role,role,m)
    assert sha(work/'inputs/assets.npz')==m['assets_sha256']
    assert sha(work/'inputs/T11-STORE-PASS.json')==m['store_receipt_sha256']
    console=int(subprocess.check_output([str(Path.home()/'.local/bin/fleet-console-users')],text=True).strip())
    who=subprocess.check_output(['who'],text=True);cap=min(96,lease['max_workers'],16 if console or who.strip() else 96)
    processes=[];pss=0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            if proc.stat().st_uid!=os.getuid():continue
            cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if 'clasher' not in cmd and 'imitation.t11' not in cmd:continue
            value=sum(int(l.split()[1])*1024 for l in (proc/'smaps_rollup').read_text().splitlines() if l.startswith('Pss:'))
            pss+=value;processes.append(dict(pid=int(proc.name),pss=value,command=cmd[:250]))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(processes)+8<=cap and pss<16_000_000_000
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
    free,util=map(int,gpu.split(','));assert free>=42000 and util<=5
    print(json.dumps(dict(passed=True,host=host,at=now.isoformat(),lease=lease,console=console,who=who,cap=cap,
                         existing_processes=processes,existing_pss=pss,gpu=gpu,**pins),indent=2))


if __name__=='__main__':main()
