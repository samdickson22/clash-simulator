"""Sequential, lease-aware copies; preserve qualification fields in readiness."""
import datetime as dt
import json
from pathlib import Path
import shlex
import subprocess
import time
import traceback

from finish_data import HERE, DATA, OPS, JOBS, write
from verify_artifacts import sha

BASE = Path('/mpac/sdicks02/repos/clasher-lease')
WORK = BASE/'data/imitation-copy-v1'
COORDINATOR = '0523ae6f-baa3-4d4e-b233-b392671670db'


def run(args):
    return subprocess.check_output(list(map(str,args)), text=True)


def remote(host,args):
    return run(['ssh','-o','BatchMode=yes',host,shlex.join(list(map(str,args)))])


def check_lease(host):
    lease = json.loads(remote(host,['cat',f'/mpac/sdicks02/fleet-leases/{host}.json']))
    assert lease['project']=='clasher' and lease['coordinator_thread']==COORDINATOR
    assert not lease.get('refused') and not lease.get('reclaim')
    assert dt.datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00')) > dt.datetime.now(dt.timezone.utc)
    return lease


def main():
    cert = DATA/'receipts/T3-PASS.json'
    assert json.loads(cert.read_text())['passed']
    completed = []
    for host in ('127x11','127x13','127x14'):
        check_lease(host)
        ready_path = JOBS/f'lease-ready-{host}.json'
        ready = json.loads(ready_path.read_text()); assert ready['qualified']
        backup = OPS/f'lease-ready-{host}-before-store.json'
        if not backup.exists(): backup.write_bytes(ready_path.read_bytes())
        label = f'imitation-store-copy-{host}-v1'
        exit_path = BASE/'jobs'/f'{label}.exit.json'
        exists = remote(host,['bash','-c',f'test -e {BASE}/jobs/{label}.launch.pid && echo yes || echo no']).strip()
        if exists=='no':
            check_lease(host)
            # The existing wrapper locks the host and enforces process/RSS/lease limits.
            remote(host,['flock','-n',BASE/'jobs/host-workload.lock','true'])
            console = remote(host,['bash','-c','~/.local/bin/fleet-console-users']).strip()
            assert console.isdigit(), console
            remote(host,['mkdir','-p',WORK])
            run(['rsync','-c',HERE/'copy_leased_store.py',HERE/'verify_artifacts.py',f'{host}:{WORK}/'])
            command = f'source {BASE}/env.sh && bash {BASE}/run.sh {label} {BASE}/repo/.venv/bin/python -B {WORK}/copy_leased_store.py'
            print(remote(host,['bash','-c',command]),flush=True)
        while True:
            check_lease(host)
            status = remote(host,['bash','-c',f'if test -f {exit_path}; then cat {exit_path}; else echo null; fi'])
            value = json.loads(status)
            write(OPS/'leased-copies-status.json',dict(host=host,label=label,completed=completed,utc=time.time(),exit=value))
            if value is not None: break
            assert dt.datetime.now(dt.timezone.utc) < dt.datetime(2026,10,9,3,30,tzinfo=dt.timezone.utc)
            time.sleep(30)
        assert value['status']=='pass' and value['exit_code']==0, value
        assert value['peak_rss_bytes'] <= 64_000_000_000
        result = json.loads(remote(host,['cat',WORK/'receipt.json']))
        assert result['passed'] and result['checksum_dry_run_equal']
        assert result['certificate_sha256']==sha(cert)
        assert result['manifest_sha256']==json.loads(cert.read_text())['store_manifest_sha256']
        assert not remote(host,['cat',WORK/'checksum-dry-run.txt'])
        write(DATA/f'receipts/T3-COPY-{host}.json',dict(copy=result,execution=value))
        # Re-read at update time so no intervening qualification fields are lost.
        ready = json.loads(ready_path.read_text())
        ready.update(data_copied=True,ready_for_gpu_training_on_c56_store=True,
                     data_note='T3 certified store copied with SHA256 and empty rsync checksum dry run',
                     store_path=str(BASE/'data/c56-store-v1'),data_copy_receipt=result)
        write(ready_path,ready)
        completed.append(host)
        print(json.dumps(dict(host=host,passed=True,receipt=result)),flush=True)
    write(DATA/'receipts/T3-LEASED-COPIES.json',dict(passed=True,hosts=completed,certificate_sha256=sha(cert)))


if __name__=='__main__':
    try: main()
    except BaseException:
        write(OPS/'leased-copies-blocked.json',dict(utc=time.time(),traceback=traceback.format_exc()))
        raise
