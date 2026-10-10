"""Authenticated shared03 light replay, cores56–58; no timing games."""
import hashlib,json,os,time,subprocess
from pathlib import Path
from admission import context,sha
G=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010')
CORES=set(range(56,59))
_checked=0.;_conflicts=[]

def thread_ok(pid,cores,nice,scheduler):
    tasks=list((Path('/proc')/str(pid)/'task').iterdir())
    return bool(tasks) and all(set(os.sched_getaffinity(int(t.name)))<=cores and os.getpriority(os.PRIO_PROCESS,int(t.name))==nice and os.sched_getscheduler(int(t.name))==scheduler for t in tasks)

def _deny(job,reason,state):
    """Record a metadata diagnostic, preserving the existing fail-closed result."""
    try:
        j=Path(job);folder=j/'metadata/guard-failures';folder.mkdir(parents=True,exist_ok=True)
        detail=[]
        for pid in state.get('conflicts',_conflicts):
            try:
                p=Path('/proc')/str(pid);raw=(p/'cmdline').read_bytes()
                detail.append(dict(pid=pid,pgid=os.getpgid(pid),command=raw.replace(b'\0',b' ').decode(errors='replace')[:700],command_sha256=hashlib.sha256(raw).hexdigest(),affinity=sorted(os.sched_getaffinity(pid)),nice=os.getpriority(os.PRIO_PROCESS,pid),scheduler=os.sched_getscheduler(pid)))
            except (FileNotFoundError,ProcessLookupError,PermissionError):detail.append(dict(pid=pid,absent_at_diagnostic=True))
        receipt=dict(schema='clasher.r3.guard-denial.v1',utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True,timeout=1).strip(),pid=os.getpid(),pgid=os.getpgrp(),context=context(),reason=reason,exception=repr(state.get('error')) if 'error' in state else None,conflicts=detail,own=state.get('own'),available_bytes=state.get('available'),PSI_full_avg10=state.get('avg10'),scientific_data_read=False,diagnostic_only=True)
        p=folder/(str(os.getpid())+'-'+str(time.time_ns())+'.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,indent=2)+'\n');tmp.replace(p)
    except Exception:pass
    return False

def allowed(job):
    global _checked,_conflicts
    try:
        j=Path(job);c=context()
        if c['host']!='127x03' or c['nice']!=19 or c['scheduler']!=os.SCHED_OTHER or not set(c['affinity'])<=CORES:return _deny(j, "guard line 17: if c['host']!='127x03' or c['nice']!=19 or c['scheduler']!=os.SCHED_OTHER or not set(c['affinity'])<=CORES:return False", locals())
        if time.time()>=1791695700 or any((j/s).exists() for s in ('REGRET.STOP','EVAL.STOP')):return _deny(j, "guard line 18: if time.time()>=1791695700 or any((j/s).exists() for s in ('REGRET.STOP','EVAL.STOP')):return False", locals())
        r=json.loads((j/'REGRET-CPU-ADMITTED.json').read_text());a=json.loads((j/'REGRET-SHARED-AUTHORITY.json').read_text())
        if not r['explicit_release'] or r['host']!='127x03' or sha(j/'REGRET-CPU-EVIDENCE.json')!=r['evidence_sha256']:return _deny(j, "guard line 20: if not r['explicit_release'] or r['host']!='127x03' or sha(j/'REGRET-CPU-EVIDENCE.json')!=r['evidence_sha256']:return False", locals())
        if r.get('shared_authority_sha256')!=sha(j/'REGRET-SHARED-AUTHORITY.json') or r.get('physical_cores')!=[56,57,58]:return _deny(j, "guard line 21: if r.get('shared_authority_sha256')!=sha(j/'REGRET-SHARED-AUTHORITY.json') or r.get('physical_cores')!=[56,57,58]:return False", locals())
        if sha(Path('/mpac/sdicks02/jobs/clasher/k2-20261010-r1/K2-CPU-RELEASE.json'))!=a['k2_release_sha256']:return _deny(j, "guard line 22: if sha(Path('/mpac/sdicks02/jobs/clasher/k2-20261010-r1/K2-CPU-RELEASE.json'))!=a['k2_release_sha256']:return False", locals())
        if time.monotonic()-_checked>=5:
            conflicts=[];own=[]
            gp=json.loads((G/'resume03-core55-freeze-pushed.json').read_text())
            if not gp['pushed'] or not gp['secret_scan_passed'] or gp['commit']!=a['g_freeze_commit']:return _deny(j, "guard line 26: if not gp['pushed'] or not gp['secret_scan_passed'] or gp['commit']!=a['g_freeze_commit']:return False", locals())
            if sha(G/'resume03-core55-amendment.json')!=a['g_amendment_sha256']:return _deny(j, "guard line 27: if sha(G/'resume03-core55-amendment.json')!=a['g_amendment_sha256']:return False", locals())
            leader=Path('/proc')/str(a['g_identity']['pid'])
            if leader.exists():
                raw=(leader/'cmdline').read_bytes();stat=(leader/'stat').read_text().rsplit(')',1)[1].split()
                if int(stat[19])!=a['g_identity']['start_ticks'] or hashlib.sha256(raw).hexdigest()!=a['g_identity']['command_sha256']:return _deny(j, "guard line 31: if int(stat[19])!=a['g_identity']['start_ticks'] or hashlib.sha256(raw).hexdigest()!=a['g_identity']['command_sha256']:return False", locals())
            for name,want in a['g_operations_sha256'].items():
                if sha(G/'ops03-core55-r2'/name)!=want:return _deny(j, "guard line 33: if sha(G/'ops03-core55-r2'/name)!=want:return False", locals())
            for p in Path('/proc').iterdir():
                if not p.name.isdigit():continue
                try:
                    pid=int(p.name);pgid=os.getpgid(pid);raw=(p/'cmdline').read_bytes();cmd=raw.replace(b'\0',b' ').decode(errors='replace')
                    if pgid in r['vacated_pgids']:conflicts.append(pid)
                    if cmd.startswith(('ssh ','sshd:','rsync ')):continue
                    if str(G)+'/' in cmd:
                        if pgid!=a['g_pgid'] or not thread_ok(pid,set(range(56)),19,os.SCHED_IDLE):conflicts.append(pid)
                    if str(j)+'/eval-ops/' in cmd:
                        own.append(pid)
                        if not thread_ok(pid,CORES,19,os.SCHED_OTHER):conflicts.append(pid)
                    if any(s in cmd for s in ('/k2-20261010','/k-v2-20261010-r1/')) or ('exit-r2' in cmd and any(s in cmd for s in ('/game_pool','/game_worker','/postkill','/descriptive'))):conflicts.append(pid)
                except (FileNotFoundError,ProcessLookupError):pass
            if len(own)>4:conflicts.extend(own)
            _conflicts=conflicts;_checked=time.monotonic()
        available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
        pressure=Path('/proc/pressure/memory').read_text().splitlines()
        full=next(line for line in pressure if line.startswith('full '))
        avg10=float(next(part.split('=',1)[1] for part in full.split() if part.startswith('avg10=')))
        valid=not _conflicts and available>=24*2**30 and avg10<=10
        if not valid:return _deny(j, 'conflicts-or-memory-floor-or-PSI', locals())
        return valid
    except (OSError,ValueError,KeyError,StopIteration) as error:return _deny(j, 'guard line 54: except (OSError,ValueError,KeyError,StopIteration) as error:return False', locals())

def frozen(j):
    f=json.loads((j/'evaluation-freeze.json').read_text());p=json.loads((j/'evaluation-prelaunch.json').read_text());assert p['pushed'] and p['secret_scan_passed'] and p['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    files=dict(f['files']);files.update(f['regret_files'])
    for name,want in files.items():assert sha(j/name)==want,name
    r=json.loads((j/'REGRET-CPU-ADMITTED.json').read_text())
    assert r['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    assert r['shared_authority_sha256']==sha(j/'REGRET-SHARED-AUTHORITY.json')
    assert r['evidence_sha256']==sha(j/'REGRET-CPU-EVIDENCE.json')
    assert r['host']=='127x03' and r['physical_cores']==[56,57,58]
    assert r['nice']==19 and r['scheduler']=='SCHED_OTHER' and r['maximum_persistent_scientific_processes']==4
    assert r['manager_core']==58 and r['worker_cores']==[56,57,58] and r['explicit_release']
    return f

def validate_seal(j,p,r):
    """Only complete pre-stop seals explicitly SHA-pinned before restart may cross an operational freeze."""
    if r['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json'):return
    f=json.loads((j/'evaluation-freeze.json').read_text())
    expected=f['retained_regret_seals'][str(p.relative_to(j))]
    assert expected['evaluation_freeze_sha256']==r['evaluation_freeze_sha256']
    assert expected['seal_sha256']==sha(p) and expected['jsonl_sha256']==sha(p.with_suffix('.jsonl'))
    assert r['complete'] and r['command_exact'] and r['jsonl_sha256']==expected['jsonl_sha256']
