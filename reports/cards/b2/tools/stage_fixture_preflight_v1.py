"""Reviewed one-shot CPU1 root/normal-acquisition diagnosis, after3586969 terminal.

Usage: stage_fixture_preflight_v1.py REVIEW.json fixturev1-UTC_TAG
Internal --run JOB mode is launched only by the staged normal CPU wrapper.
No kills, retries, full sweeps, builds, gates, runtime writes or engine acceptance.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import runpy
import shlex
import subprocess
import sys
import tarfile
import traceback

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized execution invalidates staging assertions')

HERE = Path(__file__).resolve().parent
SCOPE = HERE.parent
WORKTREE = HERE.parents[3]
NATIVE = '7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff'
FILES = ['probe_dash_natural_v1.py', 'probe_fixture_preflight_v1.py',
         'stage_fixture_preflight_v1.py', 'test_fixture_preflight_v1.py']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(job):
    manifest=json.loads((job/'source-and-tools.json').read_text())
    inputs=dict(manifest['inputs'])
    inputs[str(job/'source-and-tools.json')]=os.environ['B2_PREFLIGHT_MANIFEST_SHA256']
    for path,expected in inputs.items():
        assert sha(Path(path))==expected, ('input changed before collection',path)
    with (job/'identity.json').open('x') as out:
        json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),pgid=os.getpgid(0),
                       inputs=inputs,scope='22 bounded continuations; no full sweep/gate/acceptance'),out,indent=1)
    probe=job/'fid/probe_fixture_preflight_v1.py'
    command=[str(probe),str(job/'fid/fixtures.json')]
    started=datetime.now(timezone.utc).isoformat()
    with (job/'probe.pid.json').open('x') as pid:
        json.dump(dict(pid=os.getpid(),pgid=os.getpgid(0),mode='same-process runpy, no child',args=command),pid)
    saved_argv=sys.argv[:]
    try:
        with (job/'probe.log').open('x') as log, redirect_stdout(log), redirect_stderr(log):
            sys.argv=command
            try:
                runpy.run_path(str(probe),run_name='__main__')
                code=0
            except SystemExit as ex:
                code=ex.code if isinstance(ex.code,int) else (0 if ex.code is None else 1)
            except BaseException:
                traceback.print_exc(); code=1
    finally:
        sys.argv=saved_argv
    with (job/'probe.exit').open('x') as out:
        out.write(str(code)+'\n')
    changed=[path for path,expected in inputs.items() if sha(Path(path))!=expected]
    result=json.loads((job/'fid/fixtures.json').read_text()) if (job/'fid/fixtures.json').is_file() else None
    complete=(code==0 and not changed and result is not None and result.get('status')=='CAPTURE_COMPLETE'
            and result.get('collection_status')=='COMPLETE' and len(result.get('rows',[]))==16
            and len(result.get('legacy',[]))==6 and result.get('collection_error') is None)
    receipt=dict(status='CAPTURE_COMPLETE' if complete else 'CAPTURE_INVALID',exit_code=code,
                 semantic_status=result.get('semantic_status') if result else 'NO_RESULT',
                 natural_comparison_status=result.get('natural_comparison_status') if result else 'NO_RESULT',
                 started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),
                 identity_sha256=sha(job/'identity.json'),changed_inputs=changed,
                 collection_status=result.get('collection_status') if result else 'NO_RESULT',
                 output_sha256=sha(job/'fid/fixtures.json') if result else None,
                 scope='16 natural plus six legacy continuations; retained legacy FAILs; no engine acceptance')
    with (job/'terminal.tmp').open('x') as out:
        json.dump(receipt,out,indent=1)
    os.rename(job/'terminal.tmp',job/'terminal.json')
    print(json.dumps(receipt),flush=True)
    return 0 if complete else 1


REMOTE = r'''
import hashlib,io,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
from datetime import datetime,timezone
if not __debug__ or sys.flags.optimize: raise SystemExit('optimized remote staging forbidden')
old=Path('/mpac/sdicks02/jobs/clasher/cards/b2-semv1-20261016T1052Z'); pid=3586969
tag=sys.argv[1]
assert tag.startswith('fixturev1-') and tag.replace('-','').isalnum()
new=old.parent/('b2-'+tag)
assert not new.exists(), 'destination exists; inspect without retry/relaunch'
proc=Path('/proc')/str(pid)
if proc.exists():
    fields=(proc/'stat').read_text().rsplit(') ',1)[1].split()
    assert fields[0]=='Z' and os.getpgid(pid)==pid and proc.stat().st_uid==os.getuid(), 'old launcher not terminal'
rows=subprocess.check_output(['ps','-eo','pid,pgid,stat,args'],text=True).splitlines()[1:]
assert not [r for r in rows if r.split(None,3)[1]==str(pid) and not r.split(None,3)[2].startswith('Z')], 'old group active'
assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-3586969').exists(), 'old lease remains'
assert all((old/f'fid/semv1-20261016T1052Z-semantic-{i}.exit').is_file() for i in range(1,5)), 'old phase not terminal'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
identity=json.loads((old/'fid/semv1-20261016T1052Z-identity.json').read_text())
inputs=dict(identity['inputs'])
for path,expected in inputs.items(): assert sha(Path(path))==expected, ('old input changed',path)
for p in list((old/'fid').glob('semv1-20261016T1052Z*'))+[old/'launch.json',old/'source-and-tools.json',old/'run.log']:
    if p.is_file(): inputs[str(p)]=sha(p)
new.mkdir()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    for member in archive.getmembers():
        assert member.isfile(), member.name
        (new/member.name).resolve().relative_to(new.resolve())
    archive.extractall(new)
manifest=json.loads((new/'source-and-tools.json').read_text())
for name,expected in manifest['files'].items(): assert sha(new/name)==expected, ('tool copy changed',name)
for name,expected in manifest['engine_files'].items(): assert sha(old/'tree'/name)==expected, ('source changed',name)
for name in ('probe_dash_semantic_v1.py','snapshot_contract_v1.py'):
    shutil.copy2(old/'fid'/name,new/'fid'/name)
    inputs[str(new/'fid'/name)]=sha(new/'fid'/name)
(new/'native').mkdir()
shutil.copy2(old/'out4/clasher_core.abi3.so',new/'native/clasher_core.abi3.so')
assert sha(new/'native/clasher_core.abi3.so')==manifest['native_sha256']
inputs[str(new/'native/clasher_core.abi3.so')]=manifest['native_sha256']
root=new/'root'; root.mkdir()
for name,target in [('engine-rs',old/'tree'),('src',old/'tree/py/src'),('gamedata.json',old/'tree/py/gamedata.json'),('reports',old/'root/reports')]:
    (root/name).symlink_to(target)
for name,expected in manifest['files'].items(): inputs[str(new/name)]=expected
manifest['inputs']=inputs
with (new/'source-and-tools.json').open('w') as out: json.dump(manifest,out,indent=1)
# The runner checks the exact stage-final manifest too; identity is not a mutable self-hash.
manifest_sha=sha(new/'source-and-tools.json')
env=os.environ.copy()
for key in ('BASH_ENV','ENV','PYTHONHOME','PYTHONINSPECT','PYTHONSTARTUP'):
    env.pop(key,None)
env.update(CLASHER_ROOT=str(root),PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',PYTHONOPTIMIZE='0',
           OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='',
           B2_PREFLIGHT_MANIFEST_SHA256=manifest_sha,
           PYTHONPATH=':'.join([str(new/'native'),str(root/'engine-rs'),str(root/'src'),'/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed']))
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','1',
         '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python','-B',str(new/'fid/stage_fixture_preflight_v1.py'),'--run',str(new)]
with (new/'run.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),pid=child.pid,pgid=os.getpgid(child.pid),args=command,
             jobdir=str(new),tag=tag,cpu_bound=1,nice=15,source_and_tools_sha256=manifest_sha,
             native_sha256=manifest['native_sha256'],old_pid=pid,old_live_group=[],old_lease_present=False)
with (new/'launch.json').open('x') as out: json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


def stage(review_path,tag):
    review=json.loads(review_path.read_text())
    assert review['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    assert tag.startswith('fixturev1-') and tag.replace('-','').isalnum()
    required=['tools/'+n for n in FILES]+['NATURAL-DASH-FIXTURE-V1.md']
    assert set(required)<=set(review['reviewed_sha256'])
    for name,expected in review['reviewed_sha256'].items():
        path=(SCOPE/name).resolve(); path.relative_to(SCOPE.resolve())
        assert sha(path)==expected, ('reviewed bytes changed',name)
    target=SCOPE/'evidence'/f'{tag}-launch.json'
    assert not target.exists(), 'local receipt exists; do not retry'
    files={'fid/'+name:HERE/name for name in FILES}
    files.update({'NATURAL-DASH-FIXTURE-V1.md':SCOPE/'NATURAL-DASH-FIXTURE-V1.md','review.json':review_path})
    names=subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    manifest=dict(source_commit=subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip(),
                  native_sha256=NATIVE,reviewed_sha256=review['reviewed_sha256'],
                  engine_files={str(Path(n).relative_to('engine-cards')):sha(WORKTREE/n) for n in names if n},
                  files={name:sha(path) for name,path in files.items()})
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for name,path in files.items():
            assert path.is_file() and not path.is_symlink(), path
            archive.add(path,arcname=name,recursive=False)
        data=json.dumps(manifest,indent=1).encode(); item=tarfile.TarInfo('source-and-tools.json'); item.size=len(data)
        archive.addfile(item,io.BytesIO(data))
    result=subprocess.run(['ssh','127x08','python3 -c '+shlex.quote(REMOTE)+' '+shlex.quote(tag)],
                          input=payload.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if result.returncode:
        sys.stderr.write(result.stderr.decode()); raise SystemExit(result.returncode)
    launched=json.loads(result.stdout)
    with target.open('x') as out: json.dump(launched,out,indent=1)
    print(json.dumps(launched),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='--run':
        job=Path(sys.argv[2])
        assert sha(job/'source-and-tools.json')==os.environ['B2_PREFLIGHT_MANIFEST_SHA256']
        raise SystemExit(run(job))
    stage(Path(sys.argv[1]),sys.argv[2])
