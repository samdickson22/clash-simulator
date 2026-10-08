"""Home04 checkpoint puller. Checksum verified, versioned, never deletes data."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time

ROOT = Path('/mpac/sdicks02/repos/clasher-checkpoints/v2')
RUNS = {'127x16': 2026100821, '127x18': 2026100822}
STATE = ROOT/'backup-state.json'
DEADLINE = datetime.fromisoformat('2026-10-09T05:00:00+00:00')

PROBE = r'''
import hashlib,json,os,socket,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
request=json.load(sys.stdin);host=socket.gethostname().split('.')[0]
assert host==request['host'] and host in ('127x16','127x18')
lease=json.loads(Path('/mpac/sdicks02/fleet-leases',host+'.json').read_text())
now=datetime.now(timezone.utc)
assert lease['project']=='clasher' and not lease.get('reclaim') and not lease.get('refused')
assert now<datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))
assert now<datetime.fromisoformat('2026-10-09T05:00:00+00:00')
console=int(subprocess.check_output([str(Path.home()/'.local/bin/fleet-console-users')],text=True))
processes={}
for p in Path('/proc').iterdir():
 try:
  if not p.name.isdigit() or p.stat().st_uid!=os.getuid():continue
  stat=(p/'stat').read_text().split(') ',1)[1].split()
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  processes[int(p.name)]=(int(stat[1]),int(stat[16]),cmd)
 except (FileNotFoundError,ProcessLookupError):pass
owned={pid for pid,(_,_,cmd) in processes.items() if '/repos/clasher' in cmd or '/jobs/clasher' in cmd or 'imitation.t11' in cmd}
while True:
 new={pid for pid,(parent,_,_) in processes.items() if parent in owned}-owned
 if not new:break
 owned.update(new)
pss=0
for pid in owned:
 try:
  pss+=sum(int(l.split()[1])*1024 for l in Path('/proc',str(pid),'smaps_rollup').read_text().splitlines() if l.startswith('Pss:'))
  assert processes[pid][1]>=10
 except (FileNotFoundError,ProcessLookupError):pass
assert len(owned)+4<=min(lease['max_workers'],16 if console else 96) and pss<64000000000
free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
assert free>=8192
run=Path('/mpac/sdicks02/repos/clasher-lease/t11-20261008-v1/runs')/('main-'+str(request['seed']))
files=[]
for p in sorted(run.glob('*.pt')):
 s=p.stat();old=request['known'].get(p.name)
 if old and old['bytes']==s.st_size and old['mtime_ns']==s.st_mtime_ns:continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 after=p.stat()
 if (s.st_size,s.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):continue
 files.append(dict(name=p.name,source=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,sha256=h.hexdigest()))
print(json.dumps(dict(host=host,at=now.isoformat(),files=files,source_pss_bytes=pss,source_processes=len(owned),gpu_free_mib=free,console=console)))
'''


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n'); temporary.replace(path)


def run(argv, **kwargs):
    return subprocess.check_output(argv, text=True, timeout=120, **kwargs)


def poll(state):
    for host, seed in RUNS.items():
        h = state['hosts'].setdefault(host, dict(seed=seed, known={}))
        try:
            assert datetime.now(timezone.utc) < DEADLINE
            console = int(run([str(Path.home()/'.local/bin/fleet-console-users')]).strip())
            own_count = len(run(['ps', '-u', str(os.getuid()), '--no-headers', '-o', 'pid']).splitlines())
            assert own_count+5 <= (16 if console else 96), 'home04 process headroom'
            assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize > 20_000_000_000
            command = 'nice -n 10 python3 -c '+shlex.quote(PROBE)
            snapshot = json.loads(run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, command],
                input=json.dumps(dict(host=host, seed=seed, known=h['known']))))
            for item in snapshot['files']:
                assert Path(item['name']).name == item['name'] and len(item['sha256']) == 64
                destination = ROOT/('main-'+str(seed))/item['sha256']/item['name']
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    run(['rsync', '-c', '--partial', '--timeout=60', '--rsync-path=nice -n 10 rsync',
                         '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=10', host+':'+item['source'], str(destination)])
                assert destination.stat().st_size == item['bytes'] and sha(destination) == item['sha256']
                receipt = dict(**item, destination=str(destination), verified_at=datetime.now(timezone.utc).isoformat(), host=host, seed=seed)
                # Every content version is retained; no overwrite of earlier checkpoints.
                if not destination.with_suffix('.receipt.json').exists():
                    write(destination.with_suffix('.receipt.json'), receipt)
                h['known'][item['name']] = receipt
                print(json.dumps(dict(event='backup_verified', **receipt)), flush=True)
                write(STATE, state)
            h.update(last_success=datetime.now(timezone.utc).isoformat(), last_probe={k:v for k,v in snapshot.items() if k!='files'}, error=None)
            latest = max(h['known'].values(), key=lambda v:v['mtime_ns'], default=None)
            h['latest'] = latest
            h['checkpoint_age_seconds'] = time.time()-latest['mtime_ns']/1e9 if latest else None
        except Exception as error:
            h.update(error=repr(error), last_error=datetime.now(timezone.utc).isoformat())
            print(json.dumps(dict(event='backup_error', host=host, error=repr(error))), flush=True)
        state['checked_at'] = datetime.now(timezone.utc).isoformat(); write(STATE, state)
    # Only the small receipt reaches05/01; checkpoint bytes stay on04.
    for host in ('127x01','127x05'):
        try:
            run(['rsync','-c','--rsync-path=nice -n 10 rsync',str(STATE),host+':/mpac/sdicks02/repos/clasher/imitation/t11/receipts/backup-state.json'])
        except Exception as error:
            print(json.dumps(dict(event='receipt_mirror_error',host=host,error=repr(error))),flush=True)


def main():
    assert socket.gethostname().split('.')[0] == '127x04'
    os.nice(max(0,10-os.getpriority(os.PRIO_PROCESS,0)))
    ROOT.mkdir(parents=True,exist_ok=True)
    lock=(ROOT/'backup.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=json.loads(STATE.read_text()) if STATE.exists() else dict(started_at=datetime.now(timezone.utc).isoformat(),hosts={})
    state.update(pid=os.getpid(),poll_seconds=60,destination=str(ROOT),source_deadline=DEADLINE.isoformat(),backup_code_sha256=sha(__file__))
    while datetime.now(timezone.utc)<DEADLINE:
        poll(state)
        time.sleep(min(60,max(0,(DEADLINE-datetime.now(timezone.utc)).total_seconds())))
    state['stopped_at']=datetime.now(timezone.utc).isoformat();state['stop_reason']='leased source cutoff';write(STATE,state)


if __name__ == '__main__':
    main()
