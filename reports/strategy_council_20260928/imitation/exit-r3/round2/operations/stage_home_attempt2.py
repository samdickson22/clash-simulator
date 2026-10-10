"""Own admitted home01 staging. No simulation or model loading."""
import hashlib,json,os,resource,socket,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
S=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
A=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def copy(src,dst,host=None):
    from admission import allowed
    assert allowed(J);Path(dst).parent.mkdir(parents=True,exist_ok=True)
    cmd=['rsync','-a','--bwlimit=153600']
    if host:cmd+=['--rsync-path=nice -n 10 taskset -c 126 rsync']
    subprocess.run(cmd+[(host+':' if host else '')+str(src),str(dst)],check=True)
    assert allowed(J)
def main():
    from admission import allowed
    assert allowed(J) and os.sched_getaffinity(0)=={39}
    result=dict(status='failed',pid=os.getpid(),pgid=os.getpgrp());start=time.monotonic()
    try:
        copy(str(S/'source')+'/',str(J/'eval-source')+'/')
        copy(str(S/'reporting-native-v1')+'/',str(J/'reporting-native')+'/')
        for name in ('main02.pt','assets.npz'):copy(S/'inputs'/name,J/'inputs'/name)
        copy(str(J/'source/exit_r3')+'/',str(J/'student-source/exit_r3')+'/','127x09')
        copy(A/'fits/R3a/step-00002500.pt',J/'fits/R3a/step-00002500.pt','127x09')
        for name in ('R3a.json','R3a-calibration.json'):copy(A/'offline'/name,J/'offline'/name,'127x09')
        stage=json.loads((S/'stage-freezes/S-mix.json').read_text());source={}
        for name,want in stage['files'].items():
            prefix=str(S/'source')+'/'
            if name.startswith(prefix):
                relative=name[len(prefix):];assert sha(J/'eval-source'/relative)==want,relative;source['eval-source/'+relative]=want
        assert source['eval-source/imitation/exit_r1/screen.py']=='17d1b4086585840f5073285c9345355b4187c8342963963360213c3a9cff176e'
        for relative in ('reports/explore/e1/run.py','reports/explore/e1/planner.py'):
            assert 'eval-source/'+relative in source,relative
        native='f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8'
        assert sha(J/'reporting-native/clasher_core.abi3.so')==native
        source['reporting-native/clasher_core.abi3.so']=native
        for p in (J/'student-source').rglob('*.py'):source[str(p.relative_to(J))]=sha(p)
        for relative in ('inputs/main02.pt','inputs/assets.npz','fits/R3a/step-00002500.pt','offline/R3a-calibration.json','offline/R3a.json'):source[relative]=sha(J/relative)
        off=json.loads((J/'offline/R3a.json').read_text());cal=json.loads((J/'offline/R3a-calibration.json').read_text())
        assert off['stage1_complete'] and not off['survives'] and off['checkpoint_sha256']==cal['checkpoint_sha256']==source['fits/R3a/step-00002500.pt']
        (J/'runtime-source-pins.json').write_text(json.dumps(source,indent=2)+'\n')
        result.update(status='complete',passed=True,pins=len(source),runtime_source_pins_sha256=sha(J/'runtime-source-pins.json'),r1_stage_freeze_sha256=sha(S/'stage-freezes/S-mix.json'),r3a_original_kill_preserved=True)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-start,accounting='Whole local staging tree once; remote sender CPU unmetered and disclosed')
        (J/'HOME-STAGING.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
