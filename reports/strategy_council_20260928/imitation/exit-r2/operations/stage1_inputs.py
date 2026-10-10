"""Own73MiB heldout slice staging: read-only checksums and preparation meter."""
import argparse
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import time
from stage1_gpu_guard import digest,HOSTS

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True);a=p.parse_args();j=Path(a.job);start=time.monotonic();result={'passed':False}
    assert socket.gethostname().split('.')[0]==HOSTS[a.arm]
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    try:
        assert not (j/'heldout-corpus').exists(),'do not overwrite a preexisting slice'
        (j/'heldout-corpus').mkdir()
        subprocess.run(['rsync','-a','--bwlimit=153600','--rsync-path=nice -n 19 chrt --idle 0 taskset -c 63 rsync','127x03:'+str(j/'heldout-corpus')+'/',str(j/'heldout-corpus')+'/'],check=True)
        f=json.loads((j/'freeze.json').read_text());root=j/'heldout-corpus'
        assert digest(root/'manifest.json')==f['heldout_manifest_sha256']
        manifest=json.loads((root/'manifest.json').read_text())
        for name,want in manifest['files'].items():
            path=root/name;assert digest(path)==want,name;path.chmod(path.stat().st_mode & ~0o222)
        (root/'manifest.json').chmod((root/'manifest.json').stat().st_mode & ~0o222)
        result.update(passed=True,manifest_sha256=f['heldout_manifest_sha256'],verified_files=len(manifest['files']),rows=manifest['rows'])
    finally:
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        result.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),host=socket.gethostname().split('.')[0],arm=a.arm,wall_seconds=time.monotonic()-start,local_cpu_seconds=own.ru_utime+own.ru_stime+kids.ru_utime+kids.ru_stime,note='Preparation only; whole receiver process+child CPU once. Nice19/core63/IDL read-only03 sender CPU remains unmetered/disclosed. No model inference or simulation.')
        (j/f'stage1-staging-{a.arm}.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
