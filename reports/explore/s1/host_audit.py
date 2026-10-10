"""Independent admission/vacancy census; no signals or other-owner changes."""
import argparse,hashlib,json,os,socket,subprocess,time
from pathlib import Path

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def memory():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024

def processes():
    rows=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split()
            cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').strip()
            rows.append(dict(pid=int(d.name),ppid=int(stat[1]),pgid=int(stat[2]),start_ticks=int(stat[19]),cpu_ticks=int(stat[11])+int(stat[12]),uid=d.stat().st_uid,cmd=cmd,affinity=sorted(os.sched_getaffinity(int(d.name)))))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return rows

def release_gate(job):
    receipt=json.loads((job/'R3-RELEASE-ADMITTED.json').read_text())
    assert receipt['explicit_final_release'] and receipt['fully_vacated'] and receipt['stage2_priority_resolved']
    assert sha(job/'R3-release-evidence.json')==receipt['evidence_sha256']
    old=set(receipt['all_recorded_pgids'])
    census=processes();assert not [r for r in census if r['pgid'] in old]
    assert not [r for r in census if r['cmd'] and 'python' in Path(r['cmd'].split()[0]).name.lower() and '/exit-r3-' in r['cmd']] if census else True
    assert Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP').exists()
    assert Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP-01').exists()
    return receipt

def foreign_compute(job,rows):
    forbidden=[]
    for r in rows:
        if not r['cmd']:continue
        first=Path(r['cmd'].split()[0]).name.lower()
        if str(job) in r['cmd']:continue
        if any(x in first for x in ('python','raylet','cargo','rustc','gcc','clang','node','java','ffmpeg')):
            forbidden.append(r)
    return forbidden

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--final',action='store_true');a=ap.parse_args()
    assert socket.gethostname()=='127x01'
    console=subprocess.check_output(['who'],text=True)
    release=release_gate(a.job)
    before=processes();time.sleep(1);after=processes()
    bypid={r['pid']:r for r in before};hz=os.sysconf('SC_CLK_TCK')
    foreign=foreign_compute(a.job,after)
    active=[r for r in after if r['uid']==os.getuid() and r['pid'] in bypid and r['cmd'] and str(a.job) not in r['cmd'] and (r['cpu_ticks']-bypid[r['pid']]['cpu_ticks'])/hz>.1 and Path(r['cmd'].split()[0]).name not in ('sshd','tailscaled')]
    own=[r for r in after if str(a.job) in r['cmd'] and r['pid']!=os.getpid() and 'python' in Path(r['cmd'].split()[0]).name]
    result=dict(utc=utc(),host=socket.gethostname(),who=console,memavailable_GiB=memory()/2**30,foreign_compute=foreign,foreign_active=active,own_compute=own,release=release,processes=after,final=a.final)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    assert not foreign and not active,(foreign,active)
    assert memory()>=24*2**30
    if a.final:assert not own,own
    print(json.dumps({k:v for k,v in result.items() if k!='processes'}))
if __name__=='__main__':main()
