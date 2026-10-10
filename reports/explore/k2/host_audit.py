"""Read-only PID/thread/physical-core and source census for the owned run."""
import argparse,hashlib,json,os,socket,subprocess
from pathlib import Path

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def audit(job):
    owned=[];contenders=[];groups=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            pid=int(d.name);stat=(d/'stat').read_text().rsplit(')',1)[1].split();pgid=int(stat[2])
            if pgid==1575208:groups.append(pid)
            if not cmd:continue
            affinity=sorted(os.sched_getaffinity(pid));nice=os.getpriority(os.PRIO_PROCESS,pid);scheduler=os.sched_getscheduler(pid)
            if str(job) in cmd and ('python' in cmd or 'supervise' in cmd) and pid!=os.getpid() and not cmd.startswith(('bash -c','ssh','scp')):
                threads=[]
                for t in (d/'task').iterdir():
                    tid=int(t.name);a=sorted(os.sched_getaffinity(tid));n=os.getpriority(os.PRIO_PROCESS,tid);s=os.sched_getscheduler(tid)
                    assert n==10 and s==os.SCHED_OTHER,(pid,tid,n,s)
                    assert set(a)<=set(range(60)),(pid,tid,a)
                    threads.append(dict(tid=tid,affinity=a,nice=n,scheduler=s))
                owned.append(dict(pid=pid,pgid=pgid,cmd=cmd,affinity=affinity,nice=nice,scheduler=scheduler,threads=threads))
            elif set(affinity)&set(range(55)) and 'python' in cmd:
                contenders.append(dict(pid=pid,cmd=cmd,affinity=affinity,cpu_ticks=int(stat[11])+int(stat[12])))
        except (FileNotFoundError,ProcessLookupError):continue
    assert not groups,('G not vacated',groups)
    topology={}
    for i in range(60):
        base=Path(f'/sys/devices/system/cpu/cpu{i}/topology')
        topology[i]={n:(base/n).read_text().strip() for n in ('physical_package_id','core_id','thread_siblings_list')}
    assert len({(v['physical_package_id'],v['core_id']) for v in topology.values()})==60
    cache=Path('/proc/1655741');assert cache.exists()
    result=dict(utc=utc(),host=socket.gethostname(),who=subprocess.check_output(['who'],text=True),G_pgid_absent=1575208,owned=owned,other_python_candidates=contenders,topology=topology,cache_pid=1655741,cache_pgid=os.getpgid(1655741),cache_affinity=sorted(os.sched_getaffinity(1655741)),memavailable_bytes=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.write_text(json.dumps(audit(a.job),indent=2)+'\n')
if __name__=='__main__':main()
