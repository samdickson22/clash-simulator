"""Independent explicit K2 release audit on03, metadata only."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
K=Path('/mpac/sdicks02/jobs/clasher/k2-20261010-r1/K2-CPU-RELEASE.json')
SHA='5eaf18f351a2a15edaf8c8cf9babacd666f78c19315b9164a67659419af1a3c7'
def main():
    assert socket.gethostname().split('.')[0]=='127x03' and os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER and os.sched_getaffinity(0)=={59}
    assert hashlib.sha256(K.read_bytes()).hexdigest()==SHA;r=json.loads(K.read_text());assert r['released'] and r['reporting_complete'] and r['host']=='127x03' and r['reporting_games']==1800
    assert r['pgids']==[2047870,2056439,2289281,2291277,2291285,2300919,2300943]
    conflicts=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            pid=int(p.name);group=os.getpgid(pid);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if group in r['pgids']:conflicts.append(dict(pid=pid,pgid=group))
            if cmd.startswith(('ssh ','sshd:','rsync ')):continue
            if any(v in cmd for v in ('/k2-20261010','/k-v2-20261010-r1/','/exit-g-topup-20261010/ops/')) or ('exit-r2' in cmd and any(v in cmd for v in ('/game_pool','/game_worker','/postkill','/descriptive'))):conflicts.append(dict(pid=pid,pgid=group,command=cmd[:600]))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    assert not conflicts,conflicts
    assert Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP-03').exists()
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024;assert available>=24*2**30
    J.mkdir(parents=True,exist_ok=True);p=J/'REGRET-CPU-EVIDENCE.json';assert not p.exists(),'version reviewed re-admission'
    evidence=dict(passed=True,host='127x03',explicit_notification='K2 user release07:00:38Z/PROGRESS07:01:18Z',release_sha256=SHA,release=r,conflicts=[],mem_available_bytes=available,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip());p.write_text(json.dumps(evidence,indent=2)+'\n')
    admitted=dict(explicit_release=True,host='127x03',regret_only=True,physical_cores=list(range(60)),nice=10,scheduler='SCHED_OTHER',manager_core=59,vacated_pgids=r['pgids'],evidence_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),utc=evidence['utc']);(J/'REGRET-CPU-ADMITTED.json').write_text(json.dumps(admitted,indent=2)+'\n');print(json.dumps(admitted))
if __name__=='__main__':main()
