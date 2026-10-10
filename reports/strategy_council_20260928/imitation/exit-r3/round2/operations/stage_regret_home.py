"""Stage frozen-W replay inputs on admitted03; no scoring or model loading."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
B=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')
R=Path('/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def copy(src,dst,host=None):
    from regret_admission import allowed
    assert allowed(J);Path(dst).parent.mkdir(parents=True,exist_ok=True)
    cmd=['rsync','-a','--bwlimit=153600']
    if host:cmd+=['--rsync-path=nice -n 10 taskset -c 126 rsync']
    subprocess.run(cmd+[(host+':' if host else '')+str(src),str(dst)],check=True);assert allowed(J)
def main():
    from regret_admission import allowed
    assert allowed(J) and os.sched_getaffinity(0)=={59};r=dict(passed=False,pid=os.getpid(),pgid=os.getpgrp());t=time.monotonic()
    try:
        for src,dst in ((R/'source',J/'scorer-source'),(R/'native',J/'scorer-native'),(B/'heldout-corpus',J/'heldout-corpus')):copy(str(src)+'/',str(dst)+'/')
        copy(str(J/'source/exit_r3')+'/',str(J/'student-source/exit_r3')+'/','127x09')
        for name in ('main02.pt','assets.npz'):copy(B/'inputs'/name,J/'inputs'/name)
        snapshot=json.loads((J/'inherited-source-manifests.json').read_text());pins={}
        for name,want in snapshot['scorer-source'].items():assert sha(J/'scorer-source'/name)==want,name;pins['scorer-source/'+name]=want
        native='06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10';assert sha(J/'scorer-native/clasher_core.abi3.so')==native;pins['scorer-native/clasher_core.abi3.so']=native
        manifest=json.loads((J/'heldout-corpus/manifest.json').read_text())
        for name,want in manifest['files'].items():assert sha(J/'heldout-corpus'/name)==want,name
        for name in ('manifest.json','sources.json'):pins['heldout-corpus/'+name]=sha(J/'heldout-corpus'/name)
        sources=json.loads((J/'heldout-corpus/sources.json').read_text())['games'];assert len(sources)==64
        for i,item in enumerate(sources):
            p=Path(item['path'])
            assert p.exists(),'heldout source unavailable; review before any remote source copy'
            assert sha(p/'manifest.json')==item['manifest_sha256']
        for p in (J/'student-source').rglob('*.py'):pins[str(p.relative_to(J))]=sha(p)
        for name in ('main02.pt','assets.npz'):pins['inputs/'+name]=sha(J/'inputs'/name)
        (J/'regret-runtime-pins.json').write_text(json.dumps(pins,indent=2)+'\n');r.update(passed=True,pins=len(pins),regret_runtime_pins_sha256=sha(J/'regret-runtime-pins.json'),heldout_games=64)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);r.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,accounting='Whole base staging tree once; remote read-only sender CPU unmetered/disclosed');(J/'REGRET-BASE-STAGING.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
