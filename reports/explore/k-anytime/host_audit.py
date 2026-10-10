"""Read-only owned-process/core and cache liveness census."""
import json,os,socket,subprocess,sys
from pathlib import Path
job=Path(sys.argv[1]);host=socket.gethostname();cpus=set(range(60 if host=='127x03' else 40))
physical={c:((Path(f'/sys/devices/system/cpu/cpu{c}/topology/physical_package_id').read_text().strip()),(Path(f'/sys/devices/system/cpu/cpu{c}/topology/core_id').read_text().strip())) for c in cpus}
assert len(set(physical.values()))==len(cpus)
rows=[];cache=[]
for p in Path('/proc').glob('[0-9]*'):
    try:
        cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');pid=int(p.name)
        if str(job) in cmd and (p/'comm').read_text().strip() in ('python','python3','python3.12'):
            affinity=sorted(os.sched_getaffinity(pid));nice=os.getpriority(os.PRIO_PROCESS,pid);scheduler=os.sched_getscheduler(pid)
            assert set(affinity)<=cpus and nice>=10 and scheduler==os.SCHED_IDLE,(pid,affinity,nice,scheduler)
            rows.append(dict(pid=pid,pgid=os.getpgid(pid),nice=nice,scheduler=scheduler,affinity=affinity))
        if host=='127x03' and 'validation_cache_service_renewal_v4.py' in cmd and (p/'comm').read_text().strip()=='python':
            cache.append(dict(pid=pid,pgid=os.getpgid(pid),affinity=sorted(os.sched_getaffinity(pid)),alive=True))
    except (OSError,ProcessLookupError):pass
result=dict(at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),host=host,load=os.getloadavg(),physical_unique=True,physical_cpu_count=len(cpus),owned_python_processes=rows,cache_services=cache,who=subprocess.check_output(['who'],text=True))
print(json.dumps(result,indent=2))
