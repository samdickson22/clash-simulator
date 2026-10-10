"""Throttle own G shard copies; verify every byte before trainer admission."""
import hashlib,json,resource,subprocess,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    start=time.monotonic();r=dict(passed=False)
    try:
        m=json.loads((J/'G-verification.json').read_text());assert m['passed']
        for i,item in enumerate(m['shards']):
            target=J/'g-corpus'/str(i);target.mkdir(parents=True,exist_ok=True)
            subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 taskset -c 39 rsync',f"127x04:{item['path']}/",str(target)+'/'],check=True)
            assert sha(target/'manifest.json')==item['manifest_sha256']
            manifest=json.loads((target/'manifest.json').read_text())
            for name,want in manifest['files'].items():
                p=target/name;assert sha(p)==want,name;p.chmod(p.stat().st_mode&~0o222)
            (target/'manifest.json').chmod((target/'manifest.json').stat().st_mode&~0o222)
        r.update(passed=True,roots=m['eligible_roots'],shards=5)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);c=resource.getrusage(resource.RUSAGE_CHILDREN)
        r.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime+c.ru_utime+c.ru_stime,note='receiver and child CPU once; read-only remote sender CPU unmetered')
        (J/'G-staging.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
