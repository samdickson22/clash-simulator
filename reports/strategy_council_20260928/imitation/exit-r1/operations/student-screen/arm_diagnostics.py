"""Run the unchanged frozen diagnostics for one arm after the common case gate."""
import argparse,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--freeze-sha256',required=True);p.add_argument('--arm',required=True,choices=('S-mix','S-teacher','S-human'));a=p.parse_args();j=Path(a.job)
assert json.loads((j/'controller.json').read_text())['stage']=='parallel frozen agreement diagnostics; all cases complete'
assert os.sched_getscheduler(0)==os.SCHED_IDLE and len(os.sched_getaffinity(0))==1
assert len(list((j/'cases').glob('*.json')))==3168
for command in [
 ['-m','imitation.exit_r1.screen','--freeze',str(j/'execution-freeze.json'),'--freeze-sha256',a.freeze_sha256,'--mode','agreement','--arm',a.arm,'--teacher-store',str(j/'heldout-corpus'),'--assets',str(j/'inputs/assets.npz'),'--output',str(j/'agreement'),'--stop',str(j/'REPORTING.STOP')],
 [str(j/'ops/supplement.py'),'--job',str(j),'--freeze-sha256',a.freeze_sha256,'--arm',a.arm]]:
 subprocess.run([sys.executable,'-B',*command],check=True)
