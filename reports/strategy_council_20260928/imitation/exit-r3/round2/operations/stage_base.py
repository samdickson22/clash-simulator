"""GPU-focused owned source/input staging, before any round2 optimizer fit."""
import hashlib,json,os,resource,socket,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
OLD=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1')
BASE=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getaffinity(0)=={126}
    assert not (J/'BASE-STAGING.json').exists(),'review and version any repeated staging'
    start=time.monotonic();r=dict(passed=False,host=socket.gethostname(),pid=os.getpid(),pgid=os.getpgrp())
    try:
        for n in ('source','inputs','g-corpus','provenance','pilot'):
            target=J/n;target.mkdir(exist_ok=True)
            source=(str(OLD/n)+'/' if (OLD/n).exists() else '127x09:'+str(OLD/n)+'/')
            subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 10 taskset -c 126 rsync',source,str(target)+'/'],check=True)
        for n in ('cache','tmp','ops','fits'): (J/n).mkdir(exist_ok=True)
        old=json.loads((J/'inherited-freeze.json').read_text())
        assert sha(J/'inputs/main02.pt')==old['files']['inputs/main02.pt']
        assert sha(J/'inputs/assets.npz')==old['files']['inputs/assets.npz']
        assert sha(BASE/'corpus/manifest.json')==old['corpus_manifest_sha256']
        for i in range(5):
            p=J/'g-corpus'/str(i)/'manifest.json';assert sha(p)==old['files'][f'g-corpus/{i}/manifest.json']
            for n,want in json.loads(p.read_text())['files'].items():assert sha(p.parent/n)==want,n
        r.update(passed=True,g_shards=5,g_files=355,r1_roots=old['r1_roots'],g_roots=old['g_roots'],corpus_manifest_sha256=old['corpus_manifest_sha256'],init_sha256=sha(J/'inputs/main02.pt'),assets_sha256=sha(J/'inputs/assets.npz'))
    finally:
        utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        r.update(utc=utc,cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-start,accounting='whole receiver process/child tree once; remote read-only sender CPU unmetered')
        (J/'BASE-STAGING.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
