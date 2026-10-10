"""Raw GPU staging first, then merged complete03 Stage1 decisions to01."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
from admission import allowed,frozen,sha
from journal import record
from imitation.exit_r1.rows import write_json
def main(j):
    assert allowed(j) and os.sched_getaffinity(0)=={39};f=frozen(j);record(j,'stage_survivors');r=dict(passed=False,pid=os.getpid(),pgid=os.getpgrp());t=time.monotonic()
    def copy(host,path,target):
        assert allowed(j);Path(target).parent.mkdir(parents=True,exist_ok=True);core=59 if host=='127x03' else 126
        subprocess.run(['rsync','-a','--rsync-path=nice -n 10 taskset -c '+str(core)+' rsync',host+':'+str(path),str(target)],check=True)
    try:
        for arm in ('R3c','R3d','R3e'):
            host=f['arms'][arm]['host'];steps=f['arms'][arm]['steps']
            for name in (arm+'.json',arm+'-calibration.json'):copy(host,j/'offline'/name,j/'offline'/name)
            path=j/'fits'/arm/f'step-{steps:08d}.pt';copy(host,path,path);off=json.loads((j/'offline'/f'{arm}.json').read_text());assert sha(path)==off['checkpoint_sha256']
        # This final merge order is required; raw GPU metrics must never overwrite kills.
        for arm in ('R3c','R3d','R3e'):copy('127x03',j/'offline'/f'{arm}.json',j/'offline'/f'{arm}.json')
        copy('127x03',j/'stage1-results.json',j/'stage1-results.json');stage1=json.loads((j/'stage1-results.json').read_text())
        copy('127x03',str(j/'regret')+'/',str(j/'regret')+'/')
        assert all(v['stage1_complete'] and v==json.loads((j/'offline'/f'{a}.json').read_text()) for a,v in stage1.items())
        r.update(passed=True,stage1_results_sha256=sha(j/'stage1-results.json'),survivors=[a for a,v in stage1.items() if v['survives']],regret_proofs_and_whole_pool_meters_copied=True)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);r.update(parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,accounting='Whole survivor receiver tree once; remote sender CPU unmetered/disclosed');write_json(j/'STAGE2-ARMS-STAGING.json',r)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();main(Path(a.job))
