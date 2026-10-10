"""Final GPU proposals to admitted03, JSON and file SHA checks only."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
from regret_admission import allowed,frozen
from admission import sha
from imitation.exit_r1.rows import write_json
from journal import record
def main(j):
    assert allowed(j) and os.sched_getaffinity(0)=={59};f=frozen(j);record(j,'stage_proposals');r=dict(passed=False,pid=os.getpid(),pgid=os.getpgrp());t=time.monotonic()
    try:
        files={};(j/'offline').mkdir(exist_ok=True)
        for arm in ('R3c','R3d','R3e'):
            host=f['arms'][arm]['host']
            for name in (arm+'.json',arm+'-calibration.json',arm+'-proposals.npz'):
                assert allowed(j);target=j/'offline'/name;subprocess.run(['rsync','-a','--rsync-path=nice -n 10 taskset -c 126 rsync',host+':'+str(target),str(target)],check=True);files[name]=sha(target)
            off=json.loads((j/'offline'/f'{arm}.json').read_text());cal=json.loads((j/'offline'/f'{arm}-calibration.json').read_text());assert off['checkpoint_sha256']==cal['checkpoint_sha256'] and not off['stage1_complete'] and off['freeze_sha256']==f['training_freeze_sha256']
        r.update(passed=True,files=files)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);r.update(parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,accounting='Whole proposal receiver tree once; remote sender CPU unmetered/disclosed');write_json(j/'REGRET-PROPOSALS-STAGING.json',r)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();main(Path(a.job))
