"""Bounded SSH metadata audit; publish only after final decisions and full drain.

No signals, scientific imports, native/model reads, or automatic retries.
Default is observation only. --publish requires the entire extension's sealed
decisions; it independently rechecks the detached/scientific groups and the
first observer's absence before atomically writing the vacancy receipt.
"""
import argparse, json, subprocess
from pathlib import Path

J = '/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2'
B = '/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1'
ROOT = Path(__file__).resolve().parents[1]
HOSTS = ('127x09', '127x16', '127x13', '127x01', '127x03')


def classify_gpu_pids(raw, owned_pids):
    """Audit our compute processes without claiming other owners' GPUs idle."""
    compute = sorted({int(line.strip()) for line in raw.splitlines() if line.strip()})
    owned = sorted(set(compute).intersection(owned_pids))
    return compute, owned


def remote(host, code):
    core = 39 if host == '127x01' else 59 if host == '127x03' else 126
    interpreter = '/usr/bin/python3' if host == '127x03' else B+'/venv/bin/python'
    result = subprocess.run(
        ['ssh', '-o', 'ConnectTimeout=10', host,
         f'nice -n {19 if host == "127x03" else 10} taskset -c {core} {interpreter} -B -'],
        input=code, text=True, capture_output=True, check=True, timeout=45)
    return json.loads(result.stdout)


def decisions_complete():
    # Read sealed JSON decisions, never reduce scientific observations on05.
    code = '''import json
from pathlib import Path
j=Path(JOB)
p=j/'stage1-results.json'
s=json.loads(p.read_text()) if p.exists() else None
print(json.dumps(dict(stage1_complete=bool(s and set(s)=={'R3c','R3d','R3e'} and all(v.get('stage1_complete') for v in s.values())),any_survivor=bool(s and any(v['survives'] for v in s.values())))))
'''.replace('JOB', repr(J))
    stage1 = remote('127x03', code)
    assert stage1['stage1_complete'], 'Final round2 Stage1 pending'
    code = '''import json
from pathlib import Path
j=Path(JOB)
values={}
for name in ('descriptive-results.json','stage2-results.json'):
 p=j/name;values[name]=json.loads(p.read_text()) if p.exists() else None
print(json.dumps(values))
'''.replace('JOB', repr(J))
    # 01 has been returned to S1; use its retained exact JSON/SHA decision.
    import hashlib
    wrapper = json.loads((ROOT/'receipts/evaluation-snapshots/127x01/descriptive-results.json').read_text())
    assert hashlib.sha256(wrapper['raw'].encode()).hexdigest() == wrapper['sha256']
    desc = json.loads(wrapper['raw'])
    assert desc == wrapper['value']
    assert desc and desc['paired_seeds'] == 600 and desc['never_adoptable'] and not desc['live_adoption']
    if stage1['any_survivor']:
        result = remote('127x03', "import json\nfrom pathlib import Path\np=Path("+repr(J+'/timing03/stage2-results.json')+")\nprint(p.read_text() if p.exists() else 'null')\n")
        assert result and result['paired_seeds'] == 600 and not result['never_adoptable']
    return dict(stage1=stage1, descriptive_complete=True,
                stage2_complete=bool(stage1['any_survivor']),
                stage2_skipped=not stage1['any_survivor'])


OBSERVE = '''import fcntl,hashlib,json,os,resource,subprocess,time
from pathlib import Path
j=Path(JOB);started=time.monotonic();sources={};pids=set();groups=set()
paths=set(j.glob('*.log.identity.json'))|set(j.glob('R3*-launch.json'))|set(j.glob('R3*-exit.json'))
for pattern in ('*STAGING*.json','VOID-ATTEMPT1-VACATED.json','EVAL-PGIDS.json'):
 paths.update(j.glob(pattern))
if HOST=='127x01':paths.add(j/'CODE-QUALIFICATION.json')
if HOST=='127x03':paths.update((j/'SHARED03-DEPLOYMENT.json',j/'SHARED03-TESTS.json',j/'SHARED03-NICE19-DEPLOYMENT.json',j/'SHARED03-REPAIR-DEPLOYMENT.json',j/'SHARED03-REPAIR-TESTS.json'))
folders=('regret',) if HOST=='127x03' else ('k0-descriptive-smoke','k0-descriptive','k0-stage2-smoke','k0-stage2') if HOST=='127x01' else ('offline',)
if HOST=='127x03':
 for pattern in ('*.log.identity.json','*STAGING*.json','EVAL-PGIDS.json'):
  paths.update((j/'timing03').glob(pattern))
 folders+=('timing03/k0-stage2-smoke','timing03/k0-stage2')
for folder in folders:
 paths.update((j/folder).glob('*meter*.json'))
def identifiers(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if (k=='pid' or k.endswith('_pid')) and isinstance(x,int) and x>0:pids.add(x)
   elif (k=='pgid' or k.endswith('_pgid')) and isinstance(x,int) and x>0:groups.add(x)
   elif k in ('pgids','recorded_pgids') and isinstance(x,list):groups.update(n for n in x if isinstance(n,int) and n>0)
   else:identifiers(x)
 elif isinstance(v,list):
  for x in v:identifiers(x)
for p in sorted(paths):
 if not p.is_file():continue
 raw=p.read_bytes();sources[str(p.relative_to(j))]=hashlib.sha256(raw).hexdigest();identifiers(json.loads(raw))
pid_paths=list(j.glob('*.log.pid'))
if HOST=='127x03':pid_paths+=list((j/'timing03').glob('*.log.pid'))
for p in pid_paths:
 raw=p.read_bytes();pid=int(raw.strip());pids.add(pid)
 sources[str(p.relative_to(j))]=hashlib.sha256(raw).hexdigest()
live=[];group_members=[];pid_members=[];self_pid=os.getpid()
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==self_pid:continue
 try:
  pid=int(p.name);pgid=os.getpgid(pid);cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  row=dict(pid=pid,pgid=pgid,command=cmd[:400])
  if pgid in groups:group_members.append(row)
  if pid in pids:pid_members.append(row)
  if not cmd.startswith(('ssh ','sshd:','rsync ')) and str(j)+'/' in cmd:live.append(row)
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
locks=[]
for folder in folders:
 p=j/folder/'POOL.lock'
 if p.exists():
  with p.open('r') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(dict(path=str(p.relative_to(j)),free=True))
   except BlockingIOError:locks.append(dict(path=str(p.relative_to(j)),free=False))
fit_clean=None
if HOST in ('127x09','127x16','127x13'):
 arm={'127x09':'R3c','127x16':'R3d','127x13':'R3e'}[HOST]
 def load(name):
  p=j/name
  if not p.exists():return None
  raw=p.read_bytes();sources[name]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
 ex=load(arm+'-exit.json');launch=load(arm+'-launch.json');c=load('fits/'+arm+'/complete.json');s=load('fits/'+arm+'/segment.json');off=load('offline/'+arm+'.json')
 fit_clean=bool(ex and launch and ex['utc']>=launch['utc'] and ex['exit_code']==0 and ex['reason'] is None and c and c['step']==(2500 if arm=='R3d' else 5000) and not c['stopped'] and s and s['status']=='returned' and off)
 gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
else:gpu=''
gpu_compute_pids,gpu_owned_pids=classify_gpu_pids(gpu,pids|{x['pid'] for x in live+group_members})
u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
result=dict(host=HOST,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),pid=self_pid,pgid=os.getpgrp(),source_sha256=sources,recorded_pids=sorted(pids),recorded_pgids=sorted(groups),live_owned=live,recorded_group_members=group_members,recorded_pid_members=pid_members,locks=locks,fit_and_offline_clean=fit_clean,gpu_compute_pids=gpu_compute_pids,gpu_owned_pids=gpu_owned_pids,parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-started)
result['all_recorded_groups_absent']=bool(not live and not group_members and not pid_members and all(x['free'] for x in locks) and fit_clean is not False and not gpu_owned_pids)
print(json.dumps(result))
'''


def audit(host, publish=False):
    if host == '127x01':
        release = ROOT/'receipts/vacancy-audits/127x01/R3-CPU-RELEASE.json'
        if release.exists():
            result = json.loads(release.read_text())
            assert result['released'] and result['no_further_R3_timing_on01']
            assert result['all_recorded_groups_absent'] and result['observer_independently_absent']
            # S1 owns01 now. Retain the final R3 release rather than auditing
            # the successor's processes or overwriting its ownership evidence.
            return dict(host=host, utc=result['utc'], publish=publish,
                        retained_final_host_release=True,
                        all_recorded_groups_absent=True,
                        recorded_pgids=len(result['pgids']), active_owned=0)
    global_complete = decisions_complete() if publish else None
    import inspect
    result = remote(host, inspect.getsource(classify_gpu_pids)+'\n'+OBSERVE.replace('JOB', repr(J)).replace('HOST', repr(host)))
    utc = result['utc'].replace(':', '').replace('-', '')
    target = ROOT/'receipts/vacancy-audits'/host
    target.mkdir(parents=True, exist_ok=True)
    (target/(utc+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    if publish:
        assert result['all_recorded_groups_absent'], 'Owned processes/groups, lock, or final fit still active; vacancy NOT published'
        # Observer has returned. The second SSH check is independent; hashes bind
        # the full journal/inventory so a new phase cannot silently reuse a receipt.
        code = '''import hashlib,json,os,subprocess
from pathlib import Path
j=Path(JOB);v=RESULT
assert not Path('/proc/'+str(v['pid'])).exists(),'First observer still present'
for name,want in v['source_sha256'].items():assert hashlib.sha256((j/name).read_bytes()).hexdigest()==want,'Inventory changed: '+name
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  assert int(p.name) not in v['recorded_pids'] and os.getpgid(int(p.name)) not in v['recorded_pgids']+[v['pgid']],'Recorded process/group present'
  cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  assert cmd.startswith(('ssh ','sshd:','rsync ')) or str(j)+'/' not in cmd,'Owned runtime present'
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
v.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),observer_independently_absent=True,global_decisions=COMPLETE,all_recorded_groups_absent=True)
tmp=j/'EVAL-VACATED.json.tmp';tmp.write_text(json.dumps(v,indent=2)+'\\n');tmp.replace(j/'EVAL-VACATED.json')
print(json.dumps(v))
'''.replace('JOB', repr(J)).replace('RESULT', repr(result)).replace('COMPLETE', repr(global_complete))
        result = remote(host, code)
        (target/'EVAL-VACATED.json').write_text(json.dumps(result, indent=2)+'\n')
    return dict(host=host, utc=result['utc'], publish=publish,
                all_recorded_groups_absent=result['all_recorded_groups_absent'],
                recorded_pgids=len(result['recorded_pgids']),
                active_owned=len(result['live_owned']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--hosts', nargs='+', choices=HOSTS, default=list(HOSTS))
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    print(json.dumps([audit(host, args.publish) for host in args.hosts], indent=2))
