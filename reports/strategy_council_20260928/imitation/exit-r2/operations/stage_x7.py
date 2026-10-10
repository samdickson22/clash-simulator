"""Throttled read-only corpus pull, exact SHA check, and preparation meter."""
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time

JOB=Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1<<20),b''):h.update(data)
    return h.hexdigest()

def main():
    start=time.monotonic();result={'passed':False}
    try:
        subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 10 rsync',
            '127x16:'+str(JOB/'corpus')+'/',str(JOB/'corpus')+'/'],check=True)
        frozen=json.loads((JOB/'freeze.json').read_text())
        assert sha(JOB/'corpus/manifest.json')==frozen['files']['corpus/manifest.json']
        corpus=json.loads((JOB/'corpus/manifest.json').read_text())
        for relative,expected in corpus['files'].items():
            assert sha(JOB/'corpus'/relative)==expected,relative
            (JOB/'corpus'/relative).chmod((JOB/'corpus'/relative).stat().st_mode & ~0o222)
        (JOB/'corpus/manifest.json').chmod((JOB/'corpus/manifest.json').stat().st_mode & ~0o222)
        for relative in ('inputs/main02.pt','inputs/assets.npz','human/train/manifest.json'):
            assert sha(JOB/relative)==frozen['files'][relative],relative
        assert sha(JOB/'inputs/assets.npz.json')=='31c4ddbc2a01c3d826ab67eca9a7f80b847c2fa770cef1c828e51d4ff285faa2'
        result.update(passed=True,verified_corpus_files=len(corpus['files']),
            corpus_manifest_sha256=sha(JOB/'corpus/manifest.json'),
            human_manifest_sha256=sha(JOB/'human/train/manifest.json'))
    finally:
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
            wall_seconds=time.monotonic()-start,local_cpu_seconds=own.ru_utime+own.ru_stime+kids.ru_utime+kids.ru_stime,
            note='Preparation only; read-only remote sender CPU not included in local meter; no fit or game attempt.')
        (JOB/'X7-staging.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
