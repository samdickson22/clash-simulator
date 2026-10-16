"""One exact pre-build failed-job closure, only after independent review.

Does not launch, signal, change permissions, remove leases or alter old evidence.
The only remote write is an exclusive DIAGNOSTIC_FAIL terminal receipt.
"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import stat
import subprocess
import sys

RELATIVE='reports/cards/c1/tools/diagnostic_recover.py'
JOBS=Path('/mpac/sdicks02/jobs/clasher/cards/c1')
SPEC=dict(job=str(JOBS/'c1diag-20261016T152715Z-r1'),
    commit='18d6f9e05c3e662c8558287b659018ba92d272e1',pid=3502954,pgid=3502954,driver_pid=3503110,
    files={
        'admission.json':'ba0af63ef7d5372ed01fe851223c18701f3536e6d2bfda2cf5fc87c601ffb519',
        'output/before.json':'93a797fe5c49820623bf597f35f3ab531ca9880b424c98fb553d3795111c6b2e',
        'launch.json':'3e6b49978a2222425209cc0d9003437b812b2b9e45f73f849afead4ecf01639c',
        'manifest.json':'15433b0209b49562a2e53ab8a861d46c0f784b9fcdbd5a85b20ed4bfc3ca8707',
        'platform.json':'8d94589ff1a1be9b4b578274dab97ab8e17732e2fcf6102ac3f55adadb75c14e',
        'review.json':'167f6f8232ad6783efd0bb12ca67dd59c635c4e7b18a9356269de7c8749b2405',
        'run.log':'a6d4a36f4d217fb896739fd18dee72d4a4c89a5c52d38c508210d1ee6eb62c33'})


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_failed(job, spec):
    assert job.resolve()==job and not job.is_symlink()
    manifest=json.loads((job/'manifest.json').read_text())
    expected=dict(spec['files'])
    expected.update({'src/'+name:value for name,value in manifest['files'].items()})
    expected['root/gamedata.json']=manifest['files']['engine-cards/py/gamedata.json']
    actual={}; modes={}
    for path in [job,*job.rglob('*')]:
        info=path.lstat()
        assert info.st_uid==os.getuid() and not path.is_symlink(), str(path)
        if stat.S_ISDIR(info.st_mode): modes[str(path.relative_to(job))]=stat.S_IMODE(info.st_mode)
        else:
            assert stat.S_ISREG(info.st_mode), str(path)
            actual[str(path.relative_to(job))]=sha(path)
    assert actual==expected, 'failed job changed or contains build/child/terminal artifacts'
    expected_dirs={'.','native'}
    for name in expected:
        expected_dirs.update(str(parent) for parent in Path(name).parents)
    assert set(modes)==expected_dirs, 'unexpected build/output directories'
    assert modes['.']==modes['output']==0o2700, 'original permission failure differs'
    assert manifest['commit']==spec['commit']
    launch=json.loads((job/'launch.json').read_text())
    before=json.loads((job/'output/before.json').read_text())
    assert (launch['pid'],launch['pgid'])==(spec['pid'],spec['pgid'])
    assert (before['pid'],before['pgid'])==(spec['driver_pid'],spec['pgid'])
    assert 'run/output must be mode 0700' in (job/'run.log').read_text()
    return dict(files=actual,directory_modes=modes)


def absent_owned_job(spec, claims):
    rows=subprocess.check_output(['ps','-eo','pid=,ppid=,pgid=,sid=,stat='],text=True).splitlines()
    matches=[row for row in rows if (lambda fields:
        int(fields[0]) in (spec['pid'],spec['driver_pid']) or
        int(fields[2])==spec['pgid'] or int(fields[3])==spec['pgid'])(row.split())]
    assert not matches, 'recorded job process/group/session still present: '+repr(matches)
    for pid in (spec['pid'],spec['driver_pid']):
        for prefix in ('claim-','lease-'):
            assert not (claims/(prefix+str(pid))).exists(), 'recorded accounting file remains'
    for path in claims.glob('lease-*'):
        try: fields=path.read_text().split()
        except FileNotFoundError: continue  # Unrelated job may finish during inspection.
        assert len(fields)!=2 or fields[1]!=str(spec['pgid']), 'recorded group lease remains'
    return dict(utc=datetime.now(timezone.utc).isoformat(),matches=[],
        process_inventory_sha256=hashlib.sha256('\n'.join(rows).encode()).hexdigest(),
        recorded_claims_and_leases_absent=True)


def recover(review, review_sha):
    if sys.flags.optimize: raise RuntimeError('unoptimized execution required')
    assert socket.gethostname().split('.')[0]=='127x08'
    assert review['verdict']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION' and review['recovery']==SPEC
    job=Path(SPEC['job'])
    assert job.parent==JOBS and JOBS.resolve()==JOBS
    with (JOBS/'diagnostic-stage.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        evidence=inspect_failed(job,SPEC)
        liveness=absent_owned_job(SPEC,Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims'))
        assert inspect_failed(job,SPEC)==evidence, 'evidence changed during inspection'
        receipt=dict(utc=datetime.now(timezone.utc).isoformat(),status='DIAGNOSTIC_FAIL',
            cleanup_complete=True,commit=SPEC['commit'],engine_acceptance=False,final_C56='WITHHELD',
            children=[],failures=[dict(phase='driver-before-build',error=(job/'run.log').read_text())],
            recovery=dict(kind='exact-prebuild-failure-no-processes-or-build',spec=SPEC,
                review_commit=review['commit'],review_sha256=review_sha,
                script_sha256=review['reviewed_sha256'][RELATIVE],evidence=evidence,liveness=liveness))
        # Preserve the original 2700 modes. No chmod, deletion or fake child exit.
        parent=os.open(job/'output',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: fd=os.open('terminal.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        finally: os.close(parent)
        with os.fdopen(fd,'w') as stream:
            json.dump(receipt,stream,indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        print(json.dumps(dict(job=str(job),terminal_sha256=sha(job/'output/terminal.json'),status='DIAGNOSTIC_FAIL')))


BOOTSTRAP=r'''
import hashlib,json,sys
if sys.flags.optimize: raise RuntimeError('unoptimized execution required')
payload=json.loads(sys.stdin.buffer.read())
review_bytes=payload['review'].encode(); source=payload['source'].encode()
assert hashlib.sha256(review_bytes).hexdigest()==sys.argv[1]
review=json.loads(review_bytes)
assert review['verdict']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION'
assert hashlib.sha256(source).hexdigest()==review['reviewed_sha256']['reports/cards/c1/tools/diagnostic_recover.py']
scope={'__name__':'reviewed_recovery'}
exec(compile(source,'<reviewed-diagnostic-recovery>','exec'),scope)
scope['recover'](review,sys.argv[1])
'''


def stage(review_path):
    import diagnostic_job as J
    receipt=J.REPO/'reports/cards/c1/integration/recovery-152715Z-execution.json'
    assert not receipt.exists(), 'local recovery receipt already exists; do not duplicate'
    review=json.loads(review_path.read_text())
    assert review['verdict']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION' and review['recovery']==SPEC
    assert review['base']==J.BASE
    assert not subprocess.check_output(['git','-C',str(J.REPO),'status','--porcelain','--untracked-files=no'])
    commit=subprocess.check_output(['git','-C',str(J.REPO),'rev-parse','HEAD'],text=True).strip()
    assert review['commit']==commit
    names=set(filter(None,subprocess.check_output(['git','-C',str(J.REPO),'ls-files','-z','engine-cards'],text=True).split('\0')))|set(J.EXTRAS)
    assert review['reviewed_sha256']=={name:J.sha(J.REPO/name) for name in names}
    for name in names:
        path=J.REPO/name
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(J.REPO)
        assert path.read_bytes()==subprocess.check_output(['git','-C',str(J.REPO),'show',commit+':'+name])
    payload=json.dumps(dict(review=review_path.read_text(),source=Path(__file__).read_text())).encode()
    result=subprocess.run(['ssh',J.HOST,'python3 -B -c '+shlex.quote(BOOTSTRAP)+' '+sha(review_path)],input=payload,capture_output=True)
    J.save(receipt,dict(utc=J.utc(),exit=result.returncode,review_sha256=sha(review_path),
        stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
    print(receipt)
    if result.returncode: raise RuntimeError('recovery rejected; preserve and inspect, do not retry')


if __name__=='__main__':
    if sys.flags.optimize: raise RuntimeError('unoptimized execution required')
    assert len(sys.argv)==2
    stage(Path(sys.argv[1]))
