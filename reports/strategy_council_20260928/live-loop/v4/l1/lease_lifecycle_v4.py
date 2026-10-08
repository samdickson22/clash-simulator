"""Formal-run lease deadline and immutable, checksum-verified checkpoint backups.

Invoke inside run.sh; all children remain attached to its supervised tree.
No training admission is granted here: formal_train.sh still checks every gate.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time

import psutil

STOP_UTC = '2026-10-09T05:00:00+00:00'
BACKUP_BASE = '/mpac/sdicks02/repos/clasher-v4-training/checkpoint-mirrors'


class CheckpointBusy(ValueError):
    pass


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def checkpoint_files(root):
    paths=[]
    if (root/'admission.json').is_file():paths.append(root/'admission.json')
    for folder in (root/'model',root/'run/model'):
        if folder.exists():
            paths.extend(p for p in folder.rglob('*') if p.is_file()
                         and p.suffix in ('.pt','.npz','.json','.jsonl','.py','.yaml'))
    for p in paths:
        if p.is_symlink() or root.resolve() not in p.resolve().parents:
            raise ValueError('Checkpoint path outside run or symlink')
    return sorted(set(paths))


def snapshot(root, destination):
    destination.mkdir(exist_ok=False)
    hashes={}
    for source in checkpoint_files(root):
        relative=source.relative_to(root);target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        # T7 replaces checkpoints atomically; T6 writes in place. Detect in-place
        # mutation through the open inode, including writes after pathname replace.
        with source.open('rb') as src,target.open('xb') as dst:
            before=os.fstat(src.fileno())
            for block in iter(lambda:src.read(1024**2),b''):dst.write(block)
            after=os.fstat(src.fileno())
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise CheckpointBusy('Checkpoint changed while copying; retained incomplete snapshot')
        hashes[str(relative)]=digest(target)
    result=dict(files_sha256=hashes,checkpoint_count=sum(n.endswith('.pt') for n in hashes),
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),heldout_payloads_opened=False)
    (destination/'backup-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def offload(root, journal, backup_host):
    if backup_host not in ('127x01','127x04'):raise ValueError('Approved checkpoint destination required')
    for attempt in range(3):
        name=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        local=journal/name
        try:
            result=snapshot(root,local);break
        except CheckpointBusy:
            if attempt==2:raise
            time.sleep(.2)
    if not result['checkpoint_count']:
        return dict(status='no-checkpoint-yet',snapshot=str(local),**result)
    target=f'{BACKUP_BASE}/{socket.gethostname().split(".")[0]}/{root.name}/{name}'
    setup='import pathlib,shutil; p=pathlib.Path('+repr(target)+'); assert shutil.disk_usage("/mpac").free>200_000_000_000; p.mkdir(parents=True,exist_ok=False)'
    subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',backup_host,
        'python3 -c '+shlex.quote(setup)],check=True,timeout=30)
    subprocess.run(['rsync','-a','--checksum','--timeout=90','--rsync-path=nice -n 10 rsync',
        str(local)+'/',backup_host+':'+target+'/'],check=True,timeout=180)
    verify='''import pathlib,json,hashlib
p=pathlib.Path(TARGET)
m=json.loads((p/'backup-manifest.json').read_text())
for name,expected in m['files_sha256'].items():
 h=hashlib.sha256()
 with (p/name).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 if h.hexdigest()!=expected:raise ValueError('Backup checksum mismatch: '+name)
print(json.dumps(dict(files=len(m['files_sha256']),verified=True)))
'''.replace('TARGET',repr(target))
    done=subprocess.run(['ssh','-o','BatchMode=yes',backup_host,'python3 -'],
        input=verify,text=True,capture_output=True,check=True,timeout=90)
    receipt=dict(status='verified',destination_host=backup_host,destination=target,
        manifest_sha256=digest(local/'backup-manifest.json'),verification=json.loads(done.stdout),**result)
    (local/'transfer-verified.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def descendants(pid,known):
    try:rows=[psutil.Process(pid),*psutil.Process(pid).children(recursive=True)]
    except psutil.NoSuchProcess:rows=[]
    for process in rows:
        try:known[process.pid]=process.create_time()
        except psutil.NoSuchProcess:pass


def signal_verified(known, sig):
    for pid,started in list(known.items()):
        try:
            process=psutil.Process(pid)
            if process.create_time()==started:process.send_signal(sig)
        except psutil.NoSuchProcess:pass


def supervise(command, journal, stop_at, backup, interval=1800, grace=120, lead=1800):
    if not 0<interval<=1800 or not 0<grace<lead:raise ValueError('Invalid backup/deadline settings')
    if time.time()>=stop_at-lead:raise ValueError('Too late to start before lease cutoff')
    journal.mkdir(exist_ok=False);known={};stop_requested=False;stopped_at=None;error=None
    def stop(*unused):
        nonlocal stop_requested
        stop_requested=True
    old={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGUSR1)}
    env=dict(os.environ,CLASHER_V4_RUN_SUPERVISED='1')
    child=subprocess.Popen(command,env=env);last_backup=time.monotonic()-interval
    try:
        while child.poll() is None:
            descendants(child.pid,known)
            if time.time()>=stop_at-lead:stop_requested=True
            if stop_requested and stopped_at is None:
                stopped_at=time.monotonic();signal_verified(known,signal.SIGTERM)
            if stopped_at is not None and time.monotonic()-stopped_at>=grace:
                signal_verified(known,signal.SIGKILL)
            if stopped_at is None and time.monotonic()-last_backup>=interval:
                try:record=backup(journal)
                except Exception as exc:
                    error=str(exc);stop_requested=True;record=dict(status='backup-failed',error=error)
                with (journal/'backups.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
                last_backup=time.monotonic()
            time.sleep(.5)
        # A terminated shell must not orphan the verified trainer/converter.
        signal_verified(known,signal.SIGTERM)
        until=time.monotonic()+grace
        while time.monotonic()<until:
            alive=[]
            for pid,created in known.items():
                try:
                    p=psutil.Process(pid)
                    if p.create_time()==created and p.status()!=psutil.STATUS_ZOMBIE:alive.append(pid)
                except psutil.NoSuchProcess:pass
            if not alive:break
            time.sleep(.5)
        signal_verified(known,signal.SIGKILL)
        try:final_backup=backup(journal)
        except Exception as exc:error=str(exc);final_backup=dict(status='backup-failed',error=error)
        result=dict(child_exit=child.returncode,stopped=stop_requested,backup_error=error,
            final_backup=final_backup,stop_at=stop_at,heldout_payloads_opened=False)
        (journal/'exit.json').write_text(json.dumps(result,indent=2)+'\n')
        return 75 if stop_requested or error else child.returncode
    finally:
        if child.poll() is None:
            descendants(child.pid,known);signal_verified(known,signal.SIGTERM)
            try:child.wait(timeout=grace)
            except subprocess.TimeoutExpired:signal_verified(known,signal.SIGKILL);child.wait()
        for sig,handler in old.items():signal.signal(sig,handler)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--arm',choices=('t6','t7'),required=True)
    for name in ('phase-state','phase-exit','output','journal'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cache-union',type=Path);p.add_argument('--backup-host',choices=('127x01','127x04'),default='127x04')
    p.add_argument('--prepared-t6',type=Path)
    a=p.parse_args();host=socket.gethostname().split('.')[0]
    if (host,a.arm) not in (('127x09','t7'),('127x15','t6')):raise ValueError('Coordinator GPU assignment required')
    root=Path('/mpac/sdicks02/repos/clasher-lease')
    for path in (a.output,a.journal):
        if root not in path.resolve().parents:raise ValueError('Run and journal must stay in lease footprint')
    command=['bash',str(Path(__file__).with_name('formal_train.sh')),a.arm,
             str(a.phase_state),str(a.phase_exit),str(a.output),str(a.cache_union or ''),str(a.prepared_t6 or '')]
    stop_at=datetime.datetime.fromisoformat(STOP_UTC).timestamp()
    raise SystemExit(supervise(command,a.journal,stop_at,lambda j:offload(a.output,j,a.backup_host)))


if __name__=='__main__':main()
