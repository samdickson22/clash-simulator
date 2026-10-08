"""Own two SSH tunnels during a formal T7 fit, inside the09 lease wrapper.

Home services are separately bounded/fleet-supervised. Their exact labels and
inventory/manifest hashes must be provided. No service or producer is fabricated.
Connection tokens never enter fit/backup artifacts or compact mirrored receipts.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time

from formal_guard import admit
from pixel_cache import sha
from cache_union_v4 import partition


def runtime_spec(admission, admission_sha, source, shards):
    rows=[]
    for name,digest in sorted(admission['receipts'].items()):
        p=Path(name)
        if p.parent.parent.resolve()!=source.resolve() or sha(p)!=digest:
            raise ValueError('Producer-admitted receipt changed')
        r=json.loads(p.read_text())
        if r['split'] in ('train','validation'):rows.append(dict(r,receipt_sha256=digest))
    evidence=[]
    for shard in shards:
        inv=Path(shard['inventory']);m=Path(shard['manifest'])
        evidence.append(dict(inventory=json.loads(inv.read_text()),manifest=json.loads(m.read_text()),
                             inventory_sha256=sha(inv),manifest_sha256=sha(m)))
    partition(rows,evidence)  # No missing/overlapping/extra match, before training.
    return dict(schema='clasher.v4.formal-union.v1',admission_sha256=admission_sha,
                receipt_sha256={r['episode']:r['receipt_sha256'] for r in rows},shards=shards)


def main():
    p=argparse.ArgumentParser()
    for name in ('phase-state','phase-exit','output','control','services'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease');code=Path(__file__).parent
    if socket.gethostname().split('.')[0]!='127x09' or os.environ.get('CLASHER_LEASE_ROOT')!=str(root):
        raise ValueError('Assigned09 lease wrapper required')
    for q in (a.output,a.control):
        if root not in q.resolve().parents or q.exists():raise ValueError('Fresh lease-local paths required')
    source=root/'data/v4-matches';split=code.parent/'split.json'
    admission=admit(a.phase_state,a.phase_exit,source,split,code)
    plan=json.loads(a.services.read_text())
    if {r['host'] for r in plan['remote']}!={'127x01','127x03'} or len(plan['remote'])!=2:
        raise ValueError('Only the two pinned home services allowed')
    a.control.mkdir();proof=a.control/'admission.json'
    proof.write_text(json.dumps(admission,indent=2)+'\n')
    tunnels=[];child=None;stopped=False
    def stop(*unused):
        nonlocal stopped
        stopped=True
        if child is not None and child.poll() is None:child.send_signal(signal.SIGTERM)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
    shards=[plan['local']]
    try:
        for remote in plan['remote']:
            host=remote['host'];label=remote['label']
            if not re.fullmatch('v4-cache-transport-server-[a-zA-Z0-9-]+',label):raise ValueError('Invalid service label')
            folder=a.control/host;folder.mkdir();jobs=Path('/mpac/sdicks02/jobs/clasher')
            for suffix in ('ready.json','token'):
                dst=folder/suffix
                if suffix=='token':dst.touch(mode=0o600)
                subprocess.run(['scp','-q','-o','ConnectTimeout=10',host+':'+str(jobs/(label+'.'+suffix)),str(dst)],check=True,timeout=30)
            for key in ('inventory','manifest'):
                path=Path(remote[key]);expected=remote[key+'_sha256']
                if not (str(path).startswith('/mpac/sdicks02/jobs/clasher/') or str(path).startswith('/mpac/sdicks02/repos/clasher/reports/')):
                    raise ValueError('Home evidence path outside owned footprint')
                dst=folder/(key+'.json')
                subprocess.run(['scp','-q','-o','ConnectTimeout=10',host+':'+str(path),str(dst)],check=True,timeout=30)
                if sha(dst)!=expected:raise ValueError('Service evidence changed')
            ready=json.loads((folder/'ready.json').read_text())
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            tunnel=subprocess.Popen(['ssh','-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
                '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',
                '-L',f'127.0.0.1:{port}:127.0.0.1:{int(ready["port"])}',host])
            tunnels.append(tunnel)
            for _ in range(100):
                if stopped:raise SystemExit(75)
                if tunnel.poll() is not None:raise RuntimeError('Owned tunnel exited')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Owned tunnel unavailable')
            shards.append(dict(kind='remote',inventory=str(folder/'inventory.json'),manifest=str(folder/'manifest.json'),
                ready=str(folder/'ready.json'),token_file=str(folder/'token'),endpoint=f'http://127.0.0.1:{port}/'))
        runtime=a.control/'runtime.json'
        runtime.write_text(json.dumps(runtime_spec(admission,sha(proof),source,shards),indent=2)+'\n')
        command=[sys.executable,'-B',str(code/'lease_lifecycle_v4.py'),'--arm','t7',
            '--phase-state',str(a.phase_state),'--phase-exit',str(a.phase_exit),'--output',str(a.output),
            '--journal',str(a.control/'backups'),'--backup-host','127x04','--cache-union',str(runtime)]
        if stopped:raise SystemExit(75)
        child=subprocess.Popen(command);rc=child.wait()
        (a.control/'client-exit.json').write_text(json.dumps(dict(code=rc,stopped=stopped,
            admission_sha256=sha(proof),runtime_sha256=sha(runtime),heldout_payloads_opened=False))+'\n')
        raise SystemExit(rc)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=180)
            except subprocess.TimeoutExpired:
                # Lease supervisor remains responsible for descendant cleanup.
                child.kill();child.wait()
        for tunnel in tunnels:
            if tunnel.poll() is None:
                tunnel.terminate()
                try:tunnel.wait(timeout=10)
                except subprocess.TimeoutExpired:tunnel.kill();tunnel.wait()
        for remote in plan['remote']:
            label=remote['label']
            if re.fullmatch('v4-cache-transport-server-[a-zA-Z0-9-]+',label):
                subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',remote['host'],
                    'touch','/mpac/sdicks02/jobs/clasher/'+label+'.stop'],timeout=20,check=False)


if __name__=='__main__':main()
