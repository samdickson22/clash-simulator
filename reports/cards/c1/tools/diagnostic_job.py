"""Bounded B2-first diagnostic only. Independent review precedes stage/host execution.

No engine imports in staging/driver. Reuses the approved signal/child controller,
never its full-gate admission or execution entry points. All output is one-use.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import traceback

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = '9fa2ea993f5d0d26109b2fc2201db3c83dbf6089'
HOST = '127x08'
JOBS = Path('/mpac/sdicks02/jobs/clasher/cards/c1')
PY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
CPU = '/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh'
EXTRAS = [
    'reports/cards/c1/tools/'+name for name in (
        'diagnostic_job.py','diagnostic_worker.py','diagnostic_recover.py','final_gate.py','final_gate_contract.py',
        'probe_shared_troop.py','probe_review_r2.py','probe_snapshots.py',
        'probe_snapshot_followup.py','probe_c1_cases.py','probe_integration_selectors.py',
        'probe_first_update_diagnostic.py','probe_dash_clock.py')]
EXTRAS += ['reports/cards/b2/tools/'+name for name in ('snapshot_contract_v1.py','probe_clone_bounds.py','probe_clone_recovery.py')]
EXTRAS += ['reports/cards/batchA/tools/'+name for name in (
    'probe_native_scen.py','scenarios.py','probe_first_update_paths.py')]
EXTRAS += ['reports/strategy_council_20260928/engine-speed/es_common.py']


def utc(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def private_directory(path, create=False):
    if create:
        path.mkdir(mode=0o700)
        # Shared job parents carry setgid: mkdir(0700) alone inherits 02000.
        path.chmod(0o700)
    info=path.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and path.resolve()==path
    assert stat.S_IMODE(info.st_mode)==0o700, 'private directory must be exactly 0700: '+str(path)


def finish(children, failures, controller, output, commit):
    cleanup_ok=True
    try:
        children.stop()
    except BaseException:
        cleanup_ok=False
        failures.append(dict(phase='cleanup',error=traceback.format_exc()))
    try: controller.check_cancelled()
    except BaseException: failures.append(dict(phase='stop',error=traceback.format_exc()))
    save(output/'terminal.json',dict(utc=utc(),status='DIAGNOSTIC_FAIL' if failures else 'DIAGNOSTIC_PASS',
        cleanup_complete=cleanup_ok and not children.live,failures=failures,children=children.rows,
        commit=commit,engine_acceptance=False,final_C56='WITHHELD'))
    return int(bool(failures))


def clean_environment():
    account=pwd.getpwuid(os.getuid())
    return dict(PATH='/mpac/sdicks02/tools/cargo/bin:/usr/bin:/bin',
        USER=account.pw_name,LOGNAME=account.pw_name,HOME=account.pw_dir,
        LANG='C.UTF-8',LC_ALL='C.UTF-8',PYTHONHASHSEED='0',PYTHONOPTIMIZE='0',
        PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',
        OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',
        CUDA_VISIBLE_DEVICES='',CARGO_HOME='/mpac/sdicks02/tools/cargo',
        RUSTUP_HOME='/mpac/sdicks02/tools/rustup',CARGO_INCREMENTAL='0',CARGO_BUILD_JOBS='4',PYO3_PYTHON=PY)


def job_environment(job):
    env=clean_environment()
    env['CARGO_TARGET_DIR']=str(job/'target')
    # njit(cache=True) ignores PYTHONDONTWRITEBYTECODE. Never write or
    # exempt generated code under the authenticated source inventory.
    env['NUMBA_CACHE_DIR']=str(job/'numba-cache')
    return env


def validate(job):
    manifest=json.loads((job/'manifest.json').read_text())
    review=json.loads((job/'review.json').read_text())
    assert review['verdict']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION'
    assert review['commit']==manifest['commit'] and review['base']==BASE
    assert review['reviewed_sha256']==manifest['files']
    assert sha(job/'review.json')==manifest['review_sha256']
    actual={str(path.relative_to(job/'src')):sha(path) for path in (job/'src').rglob('*') if path.is_file()}
    assert actual==manifest['files'], 'source/tool inventory differs'
    assert all(not path.is_symlink() for path in (job/'src').rglob('*')), 'source symlink'
    for path,expected in manifest.get('external',{}).items(): assert sha(path)==expected, path
    return manifest


BOOTSTRAP = r'''
import fcntl,io,json,os,re,subprocess,sys,tarfile
from pathlib import Path
tag=sys.argv[1]
assert re.fullmatch(r'c1diag-\d{8}T\d{6}Z-r[1-9]\d*',tag)
parent=Path('/mpac/sdicks02/jobs/clasher/cards/c1')
assert parent.resolve()==parent and parent.is_dir()
lock=(parent/'diagnostic-stage.lock').open('a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
job=parent/tag
assert not job.exists(),'fresh job already exists; preserve and inspect'
for old in parent.glob('c1diag-*'):
    assert old.is_dir() and not old.is_symlink()
    assert (old/'output/terminal.json').is_file(),('prior diagnostic not terminal',str(old))
    terminal=json.loads((old/'output/terminal.json').read_text())
    assert terminal.get('cleanup_complete') is True,('prior cleanup incomplete',str(old))
    launch=json.loads((old/'launch.json').read_text())
    rows=subprocess.check_output(['ps','-eo','pid,pgid,stat'],text=True).splitlines()[1:]
    assert not [row for row in rows if row.split()[1]==str(launch['pgid']) and not row.split()[2].startswith('Z')],('old group active',str(old))
    assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims',f"lease-{launch['pid']}").exists()
job.mkdir(mode=0o700)
job.chmod(0o700)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    seen=set()
    for member in archive.getmembers():
        path=Path(member.name)
        assert member.isfile() and member.name not in seen
        assert not path.is_absolute() and path.as_posix()==member.name and '..' not in path.parts
        assert member.name in ('manifest.json','review.json') or member.name.startswith('src/')
        seen.add(member.name)
        target=job/path; target.resolve().relative_to(job)
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with target.open('xb') as stream: stream.write(archive.extractfile(member).read())
        target.chmod(0o600)
command=['python3','-B',str(job/'src/reports/cards/c1/tools/diagnostic_job.py'),'admit',str(job)]
raise SystemExit(subprocess.call(command))
'''


def stage(review_path,tag):
    assert re.fullmatch(r'c1diag-\d{8}T\d{6}Z-r[1-9]\d*',tag)
    assert REPO==Path('/mpac/sdicks02/repos/clasher-cards-b2-c1-integration-20261016')
    assert not subprocess.check_output(['git','-C',str(REPO),'status','--porcelain','--untracked-files=no'])
    commit=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    subprocess.run(['git','-C',str(REPO),'merge-base','--is-ancestor',BASE,commit],check=True)
    files=subprocess.check_output(['git','-C',str(REPO),'ls-files','-z','engine-cards'],text=True).split('\0')
    names=sorted(set(filter(None,files))|set(EXTRAS))
    sources={name:REPO/name for name in names}
    for name,path in sources.items():
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(REPO)
        assert not name.endswith(('.so','.dylib','.pyc')), 'compiled input forbidden'
        assert path.read_bytes()==subprocess.check_output(['git','-C',str(REPO),'show',commit+':'+name]),name
    manifest=dict(commit=commit,base=BASE,files={name:sha(path) for name,path in sources.items()},
                  review_sha256=sha(review_path),utc=utc())
    review=json.loads(review_path.read_text())
    assert review['verdict']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION' and review['commit']==commit and review['base']==BASE
    assert review['reviewed_sha256']==manifest['files']
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:') as archive:
        for name,path in sources.items(): archive.add(path,arcname='src/'+name,recursive=False)
        archive.add(review_path,arcname='review.json',recursive=False)
        encoded=json.dumps(manifest,indent=2).encode(); info=tarfile.TarInfo('manifest.json'); info.size=len(encoded)
        archive.addfile(info,io.BytesIO(encoded))
    receipt=REPO/'reports/cards/c1/integration'/(tag+'-launch.json')
    assert not receipt.exists(), 'local launch receipt exists; do not duplicate'
    run=subprocess.run(['ssh',HOST,'python3 -B -c '+shlex.quote(BOOTSTRAP)+' '+shlex.quote(tag)],
        input=payload.getvalue(),capture_output=True)
    if run.returncode:
        save(receipt.with_name(tag+'-stage-failure.json'),dict(utc=utc(),exit=run.returncode,
            stdout=run.stdout.decode(errors='replace'),stderr=run.stderr.decode(errors='replace'),manifest=manifest))
        raise RuntimeError('remote staging failed; preserve partial job and inspect, do not retry')
    launch=json.loads(run.stdout)
    save(receipt,launch); print(json.dumps(launch),flush=True)


def admit(job):
    assert socket.gethostname().split('.')[0]==HOST and job.parent==JOBS and job.resolve()==job
    manifest=validate(job)
    external=[CPU,str(Path(CPU).with_name('cpu_room.sh')),str(Path(PY).resolve())]
    external += ['/mpac/sdicks02/tools/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin/'+name for name in ('cargo','rustc')]
    platform=dict(utc=utc(),external={path:sha(path) for path in external},
        inherited=subprocess.run(['ps','-p','1042473,940202,3586969','-o','pid,ppid,pgid,lstart,stat,args'],capture_output=True,text=True).stdout)
    save(job/'platform.json',platform)
    private_directory(job)
    for name in ('output','native','root','numba-cache'): private_directory(job/name,create=True)
    shutil.copyfile(job/'src/engine-cards/py/gamedata.json',job/'root/gamedata.json')
    env=clean_environment()
    admission=dict(commit=manifest['commit'],manifest_sha256=sha(job/'manifest.json'),
        review_sha256=sha(job/'review.json'),platform_sha256=sha(job/'platform.json'))
    save(job/'admission.json',admission)
    for name in ('manifest.json','review.json','platform.json','admission.json'):
        (job/name).chmod(0o400)
    command=['nice','-n','15','bash',CPU,'4',PY,'-P','-s','-B',str(HERE/'diagnostic_job.py'),'run',str(job),sha(job/'admission.json')]
    with (job/'run.log').open('xb') as log:
        child=subprocess.Popen(command,cwd=job,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    launch=dict(utc=utc(),pid=child.pid,pgid=os.getpgid(child.pid),command=command,
        commit=manifest['commit'],manifest_sha256=sha(job/'manifest.json'),review_sha256=sha(job/'review.json'),
        platform_sha256=sha(job/'platform.json'),cpu=4,nice=15,job=str(job),host=HOST)
    save(job/'launch.json',launch); print(json.dumps(launch),flush=True)


def run(job,admission_sha):
    assert socket.gethostname().split('.')[0]==HOST and job.parent==JOBS
    sys.path.insert(0,str(HERE))
    import final_gate as G
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,G.interrupted)
    output=job/'output'; children=G.Children(output); failures=[]; manifest=None
    try:
        for path in (job,output,job/'native',job/'root',job/'numba-cache'): private_directory(path)
        assert re.fullmatch('[0-9a-f]{64}',admission_sha) and sha(job/'admission.json')==admission_sha
        admission=json.loads((job/'admission.json').read_text())
        for name in ('manifest','review','platform'):
            assert sha(job/(name+'.json'))==admission[name+'_sha256']
        lease=Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims')/('lease-'+str(os.getppid()))
        assert lease.read_text().split()==['4',str(os.getpgrp())], 'direct admitted CPU lease4 required'
        assert os.getpriority(os.PRIO_PROCESS,0)>=15
        manifest=validate(job)
        assert manifest['commit']==admission['commit']
        platform=json.loads((job/'platform.json').read_text())
        assert all(sha(path)==value for path,value in platform['external'].items())
        assert not any((job/'numba-cache').iterdir()), 'fresh generated cache required'
        env=job_environment(job)
        save(output/'before.json',dict(utc=utc(),manifest_sha256=sha(job/'manifest.json'),
            files=manifest['files'],platform=platform,lease=lease.read_text(),pid=os.getpid(),pgid=os.getpgrp(),
            child_environment=env))
        command=['/mpac/sdicks02/tools/cargo/bin/cargo','+1.97.1','build','--offline',
            '--manifest-path',str(job/'src/engine-cards/Cargo.toml'),'--release',
            '--features','extension-module,gil-release','-j','4']
        children.start('build',command,env); children.wait('build',['build'])
        library=job/'target/release/libclasher_core.so'
        assert library.read_bytes()[:4]==b'\x7fELF'
        shutil.copyfile(library,job/'native/clasher_core.abi3.so')
        native_sha=sha(library)
        assert sha(job/'native/clasher_core.abi3.so')==native_sha
        save(output/'build.json',dict(utc=utc(),commit=manifest['commit'],native_sha256=native_sha,
            command=command,platform_sha256=sha(job/'platform.json'),manifest_sha256=sha(job/'manifest.json')))
        tasks=[('shared',job/'src/reports/cards/c1/tools/probe_shared_troop.py',
            ['--contract',str(job/'src/reports/cards/b2/tools/snapshot_contract_v1.py'),'--native-sha256',native_sha]),
            ('dash-clock',job/'src/reports/cards/c1/tools/probe_dash_clock.py',
                ['--contract',str(job/'src/reports/cards/b2/tools/snapshot_contract_v1.py'),'--native-sha256',native_sha]),
            ('review',job/'src/reports/cards/c1/tools/probe_review_r2.py',[]),
            ('selectors',job/'src/reports/cards/c1/tools/probe_integration_selectors.py',
                ['--contract',str(job/'src/reports/cards/b2/tools/snapshot_contract_v1.py'),'--native-sha256',native_sha]),
            ('followup',job/'src/reports/cards/c1/tools/probe_snapshot_followup.py',[]),
            ('first-update',job/'src/reports/cards/c1/tools/probe_first_update_diagnostic.py',[]),
            ('clone-bounds',job/'src/reports/cards/b2/tools/probe_clone_bounds.py',[]),
            ('clone-recovery',job/'src/reports/cards/b2/tools/probe_clone_recovery.py',[]),
            ('terrain',job/'src/reports/cards/c1/tools/probe_c1_cases.py',
                ['bandit_water_end','bandit_water_end_red','mk_vs_giant','mk_vs_giant_red'])]
        for label,probe,args in tasks:
            G.check_cancelled(); validate(job)
            command=[PY,'-P','-s','-B',str(HERE/'diagnostic_worker.py'),str(job),label,str(probe),*args]
            paths=['native','src/engine-cards','src/engine-cards/py/src','src/reports/cards/c1/tools',
                   'src/reports/cards/batchA/tools','src/reports/strategy_council_20260928/engine-speed']
            paths.append('src/reports/cards/b2/tools')
            probe_env=dict(env,PYTHONPATH=os.pathsep.join(str(job/path) for path in paths),CLASHER_ROOT=str(job/'root'),
                C1_DIAG_MANIFEST_SHA256=admission['manifest_sha256'],C1_DIAG_BUILD_SHA256=sha(output/'build.json'))
            children.start(label,command,probe_env)
            try: children.wait(label,[label])
            except Exception as error:
                G.check_cancelled(); failures.append(dict(phase=label,error=repr(error)))
        validate(job)
        assert sha(job/'admission.json')==admission_sha
        for name in ('manifest','review','platform'):
            assert sha(job/(name+'.json'))==admission[name+'_sha256']
        assert sha(job/'native/clasher_core.abi3.so')==native_sha
        assert sha(job/'root/gamedata.json')==manifest['files']['engine-cards/py/gamedata.json']
        assert all(sha(path)==value for path,value in platform['external'].items())
        cache={}
        for path in (job/'numba-cache').rglob('*'):
            assert not path.is_symlink(), 'generated cache symlink'
            if path.is_dir(): continue
            assert path.is_file(), 'nonregular generated cache'
            cache[str(path.relative_to(job/'numba-cache'))]=sha(path)
        save(output/'after.json',dict(utc=utc(),files=manifest['files'],native_sha256=native_sha,
            platform=platform,generated_numba_cache=cache))
    except BaseException:
        failures.append(dict(phase='driver',error=traceback.format_exc()))
    return finish(children,failures,G,output,None if manifest is None else manifest['commit'])


if __name__=='__main__':
    if sys.flags.optimize: raise RuntimeError('unoptimized execution required')
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=('stage','admit','run'))
    parser.add_argument('path',type=Path); parser.add_argument('tag',nargs='?'); args=parser.parse_args()
    if args.mode=='stage': stage(args.path,args.tag)
    elif args.mode=='admit': admit(args.path)
    else: raise SystemExit(run(args.path,args.tag))
