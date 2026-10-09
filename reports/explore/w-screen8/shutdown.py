"""Read-only check that this lane's simulation processes have exited."""
import json
from pathlib import Path
import sys
import time

job=Path(sys.argv[1]);processes=[]
for phase in ('smoke','reporting'):
    pids=json.loads((job/phase/'pid.json').read_text())
    for role,pid in pids.items():
        path=Path('/proc')/str(pid)/'cmdline'
        command=path.read_bytes().replace(b'\0',b' ').decode(errors='replace') if path.exists() else ''
        alive=bool(command and str(job) in command)
        processes.append(dict(phase=phase,role=role,pid=pid,alive=alive))
assert not any(p['alive'] for p in processes),processes
workers=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        command=path.read_bytes().replace(b'\0',b' ').decode(errors='replace')
        # Exact worker script prefixes, not inspection/helper command strings.
        if command.startswith(str(Path(sys.executable))) and any(
            str(job/'repo/reports/explore/w-screen8'/name) in command
            for name in ('run.py','supervise.py')):
            workers.append(dict(pid=int(path.parent.name),command=command))
    except OSError:pass
assert not workers,workers
result=dict(time=time.time(),processes=processes,leftover_simulation_workers=workers,all_lane_jobs_exited=True)
(job/'shutdown.json').write_text(json.dumps(result,indent=2)+'\n');print('Simulation shutdown PASS',flush=True)
