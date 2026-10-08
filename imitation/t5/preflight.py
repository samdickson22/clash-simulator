"""Read-only fleet launch audit, limited to authorized T5 target hosts."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
from .guards import frozen, role_guard, sha


def main():
    p = argparse.ArgumentParser(); p.add_argument('--freeze', required=True)
    p.add_argument('--store', required=True); p.add_argument('--assets', required=True)
    p.add_argument('--expected-new-processes', type=int, default=10)
    a = p.parse_args(); host = socket.gethostname().split('.')[0]
    if host not in ('127x04', '127x08', '127x11', '127x13', '127x14'):
        raise ValueError('not a registered initial run host')
    who = subprocess.check_output(['who'], text=True)
    root = Path(__file__).resolve().parents[2]
    manifest, pins = frozen(root, a.freeze)
    for role in ('train', 'dev'):
        role_guard(Path(a.store)/role, role, manifest)
    if sha(a.assets) != manifest['assets_sha256']:
        raise ValueError('asset mismatch')
    borrowed = host in ('127x11', '127x13', '127x14')
    cap = {'127x13': 64, '127x14': 64}.get(host, 96)
    lease = None
    if borrowed:
        lease = json.loads(Path('/mpac/sdicks02/fleet-leases/'+host+'.json').read_text())
        now = datetime.now(timezone.utc)
        if (lease.get('project')!='clasher' or lease.get('gpu') is not True or lease.get('refused')
                or lease.get('reclaim') or datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))<=now
                or now>=datetime.fromisoformat('2026-10-09T04:20:00+00:00')):
            raise ValueError('lease missing/refused/reclaimed/expired or planned stop reached')
        cap = min(cap, lease['max_workers'])
        if not str(root).startswith('/mpac/sdicks02/repos/clasher-lease/'):
            raise ValueError('borrowed code escapes footprint')
    if who.strip(): cap = min(cap, 16)
    processes = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            if proc.stat().st_uid != os.getuid(): continue
            command = (proc/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if not any(s in command for s in ('clasher', 'imitation.', '/t5-20261008', '/t4-')): continue
            rss = 0
            for line in (proc/'status').read_text().splitlines():
                if line.startswith('VmRSS:'): rss = int(line.split()[1])*1024
            processes.append({'pid': int(proc.name), 'rss_bytes': rss, 'command': command[:350]})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if len(processes)+a.expected_new_processes+2 > cap:
        raise ValueError('all-Clasher process budget exhausted')
    if borrowed and sum(r['rss_bytes'] for r in processes) > 64000000000-8000000000:
        raise ValueError('insufficient shared RSS budget')
    gpu = subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'], text=True).strip()
    free = int(gpu.split(',')[0])
    if free < 42000:
        raise ValueError('insufficient idle GPU headroom for qualified microbatch')
    print(json.dumps({'host': host, 'at': datetime.now(timezone.utc).isoformat(), 'who': who,
                      'cap': cap, 'reserved_new_processes': a.expected_new_processes+2,
                      'existing_clasher_processes': processes, 'gpu': gpu, 'lease': lease, **pins,
                      'passed': True}, indent=2))


if __name__ == '__main__':
    main()
