"""Bounded task-only finalization after all reporting workers exit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

job=Path(sys.argv[1]);repo=job/'repo';lane=repo/'reports/explore/w-screen8'
assert os.sched_getscheduler(0)==os.SCHED_IDLE and os.getpriority(os.PRIO_PROCESS,0)>=10
limit=time.monotonic()+7200
while not (job/'reporting/exit.json').exists():
    if time.monotonic()>limit:raise TimeoutError('reporting did not finish within two hours')
    time.sleep(15)
exit_info=json.loads((job/'reporting/exit.json').read_text())
assert exit_info['returncode']==0 and not exit_info['stopping'],exit_info
cmd=[sys.executable,'-B',str(lane/'reduce.py'),'--root',str(job/'reporting'),
     '--config',str(lane/'config.json'),'--out',str(job/'results.json')]
subprocess.run(cmd,check=True,cwd=repo)
subprocess.run([sys.executable,'-B',str(lane/'compute.py'),str(job)],check=True,cwd=repo)
paths=['reports/explore/w-screen8/run.py','reports/explore/w-screen8/planner.py',
       'reports/explore/w-screen8/config.json','reports/explore/w-screen8/reduce.py',
       'reports/strategy_council_20260928/search-noise-s6/delay.py',
       'src/clasher/rl/c56_rollout_planner.py','src/clasher/analysis/loss_review/delay_fixes.py',
       'src/clasher/analysis/loss_review/search_ab.py',
       'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json']
receipt=dict(freeze_commit='d0e9dc2f',baseline_commit='f9d3b454',production_commit='59454e1a',
    reporting_adapter='frozen w-confirm screen8 reference, independent of production tree',
    reporting_native=str(job/'native/clasher_core.abi3.so'),
    reporting_native_sha256=hashlib.sha256((job/'native/clasher_core.abi3.so').read_bytes()).hexdigest(),
    files={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths})
(job/'runtime-pin.json').write_text(json.dumps(receipt,indent=2)+'\n')
# Only summary aggregates enter the report output directory.
report=job/'report';report.mkdir(exist_ok=True)
(report/'results.json').write_bytes((job/'results.json').read_bytes())
subprocess.run([sys.executable,'-B',str(lane/'write_report.py'),str(report)],check=True,cwd=repo)
(job/'FINISHED').write_text('PASS\n')
print('Finalization complete',flush=True)
