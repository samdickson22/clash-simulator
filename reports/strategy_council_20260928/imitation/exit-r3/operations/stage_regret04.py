"""Guarded own04 staging: scorer/heldout only, then offline proposals after fits."""
import argparse,json,os,resource,signal,subprocess,time
from pathlib import Path
from exit_r3.rows import sha,write_json
from guard_regret04 import allowed
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1');B=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')

def main():
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');a=p.parse_args();start=time.monotonic();result=dict(passed=False,base_passed=False);child=None
    assert allowed(J,manager=True)
    receipt=json.loads((J/'REGRET04-ADMITTED.json').read_text())
    authority=json.loads((J/'REGRET04-AUTHORITY.json').read_text())
    freeze=json.loads((J/'evaluation-freeze.json').read_text())
    assert sha(J/'REGRET04-AUTHORITY.json')==freeze['regret04_authority_sha256']
    assert authority['progress_sha_changes_are_bookkeeping'] and authority['absolute_vacate_utc']=='2026-10-10T07:30:00Z'
    def live():
        assert allowed(J,manager=True),'04 PSI/A19/deadline/stop admission changed'
        r=subprocess.run(['ssh','-o','ConnectTimeout=2','127x05','sha256sum '+' '.join(receipt['a19_progress_sha256'])],capture_output=True,text=True,check=True,timeout=3)
        actual={l.split()[1]:l.split()[0] for l in r.stdout.splitlines()}
        assert set(actual)==set(receipt['a19_progress_sha256']),'A19 progress availability check incomplete'
        result['a19_observed_progress_sha256']=actual
    def run(command):
        nonlocal child
        live();child=subprocess.Popen(command,start_new_session=True)
        while child.poll() is None:
            assert allowed(J,manager=True),'04 PSI/A19/deadline/stop admission changed';time.sleep(.2)
        assert child.wait()==0;child=None;live()
    try:
        if not (J/'REGRET04-STAGING.json').exists() or not json.loads((J/'REGRET04-STAGING.json').read_text()).get('base_passed'):
            for source,target in ((B/'source',J/'source'),(B/'heldout-corpus',J/'heldout-corpus'),(B/'inputs',J/'inputs'),(Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/source'),J/'scorer-source'),(Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/native'),J/'scorer-native')):
                target.mkdir(parents=True,exist_ok=True);run(['rsync','-a',str(source)+'/',str(target)+'/'])
            sources=json.loads((J/'heldout-corpus/sources.json').read_text())['games']
            for i,item in enumerate(sources):
                if not Path(item['path']).exists():
                    target=J/'heldout-games'/f'{i:04d}';target.mkdir(parents=True,exist_ok=True)
                    run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 taskset -c 63 rsync','127x03:'+item['path']+'/',str(target)+'/']);assert sha(target/'manifest.json')==item['manifest_sha256']
            expected=json.loads((J/'source-manifests.json').read_text())['scorer-source']
            for name,want in expected.items():assert sha(J/'scorer-source'/name)==want,name
            assert sha(J/'scorer-native/clasher_core.abi3.so')=='06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10'
            f=json.loads((J/'freeze.json').read_text());assert sha(J/'heldout-corpus/manifest.json')==f['heldout_manifest_sha256']
            for name,want in json.loads((J/'heldout-corpus/manifest.json').read_text())['files'].items():assert sha(J/'heldout-corpus'/name)==want
        result['base_passed']=True
        if a.offline:
            (J/'offline').mkdir(exist_ok=True)
            for arm,host in (('R3a','127x09'),('R3b','127x16')):
                for name in (arm+'.json',arm+'-calibration.json',arm+'-proposals.npz'):
                    run(['rsync','-a','--rsync-path=nice -n 10 taskset -c 126 rsync',host+':'+str(J/'offline'/name),str(J/'offline')+'/'])
                off=json.loads((J/'offline'/f'{arm}.json').read_text());assert off['calibration']['rows']==8088 and not off['stage1_complete']
            result['passed']=True
    finally:
        if child is not None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,host='127x04',nice=19,affinity=sorted(os.sched_getaffinity(0)),note='Whole local staging process tree once; remote sender CPU unmetered')
        write_json(J/f'regret04-staging-meter-{os.getpid()}.json',result);write_json(J/'REGRET04-STAGING.json',result);print(json.dumps(result))
if __name__=='__main__':main()
