"""Stage one reviewed Rage build/affected job after940202 terminal, on08 only."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

if not __debug__ or sys.flags.optimize:raise SystemExit('optimized staging forbidden')
HERE=Path(__file__).resolve().parent;SCOPE=HERE.parent;WORKTREE=HERE.parents[3]
FILES=['stage_rage_fix_v1.py','run_rage_fix_v1.sh','validate_rage_fix_v1.py','test_rage_fix_v1.py','probe_rage_impact_v1.py']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


REMOTE=r'''
import hashlib,io,json,os,shutil,subprocess,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('optimized remote staging forbidden')
tag=sys.argv[1]
assert tag.startswith('ragefixv1-') and tag.replace('-','').isalnum()
old=Path('/mpac/sdicks02/jobs/clasher/cards/b2-semv1-20261016T1052Z')
capture=old.parent/'b2-fixturev1-20261016T1226Z'
new=old.parent/('b2-'+tag)
assert not new.exists(),'fresh path exists; inspect without retry'
for pid in (3586969,940202):
    rows=subprocess.check_output(['ps','-eo','pid,pgid,stat'],text=True).splitlines()[1:]
    assert not [r for r in rows if r.split()[1]==str(pid) and not r.split()[2].startswith('Z')],('old group active',pid)
    assert not Path(f'/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-{pid}').exists()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''):h.update(block)
    return h.hexdigest()
CAPTURE_IDENTITY_SHA256='3995110721b39f0b5c3c705299f533db4ed60383022d853ca98b0b0a548737d5'
def validate_capture_reference(capture,old):
    terminal=json.loads((capture/'terminal.json').read_text())
    assert terminal['status']=='CAPTURE_COMPLETE' and terminal['exit_code']==0 and not terminal['changed_inputs']
    assert terminal['output_sha256']=='b0ecd196b9cd70a03fa358412c2c4fc8e195dd3960d9bae8689db23574d07358'
    assert sha(capture/'fid/fixtures.json')==terminal['output_sha256']
    assert terminal['identity_sha256']==CAPTURE_IDENTITY_SHA256,'historical identity receipt changed'
    assert sha(capture/'identity.json')==CAPTURE_IDENTITY_SHA256,'historical identity bytes changed'
    old_inputs=json.loads((capture/'identity.json').read_text())['inputs']
    required=[old/'source-and-tools.json']+[old/'fid'/('semv1-20261016T1052Z-semantic-'+str(i)+'.json') for i in range(1,5)]
    assert all(str(path) in old_inputs for path in required),'historical reference missing from pinned identity'
    for path,expected in old_inputs.items():assert sha(Path(path))==expected,('old input changed',path)
    return old_inputs,json.loads((old/'source-and-tools.json').read_text())
old_inputs,old_manifest=validate_capture_reference(capture,old)
new.mkdir()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    for member in archive.getmembers():
        assert member.isfile(),member.name
        (new/member.name).resolve().relative_to(new.resolve())
    archive.extractall(new)
manifest=json.loads((new/'source-and-tools.json').read_text())
for name,expected in manifest['files'].items():assert sha(new/name)==expected,('new tool copy',name)
assert len(manifest['engine_files'])==504
assert set(manifest['engine_files'])==set(old_manifest['engine_files'])
changed={name for name in manifest['engine_files'] if manifest['engine_files'][name]!=old_manifest['engine_files'][name]}
assert changed=={'differential.py','live_snapshot.py','src/lib.rs','src/scope.rs'},('Rage-only source drift',changed)
for name,expected in manifest['engine_files'].items():assert sha(new/'tree'/name)==expected,('new engine copy',name)
reuse=['snapshot_contract_v1.py','probe_dash_semantic_v1.py','probe_cache_descendants_v1.py',
       'validate_semantic_v1.py','validate_r2.py','probe_first_update_paths.py','probe_clone_bounds.py',
       'probe_clone_recovery.py','probe_native_scen.py','scenarios.py','pool.json']
for name in reuse:shutil.copy2(old/'fid'/name,new/'fid'/name)
(new/'stats').mkdir();shutil.copy2(old/'stats/gamedata.json',new/'stats/gamedata.json')
r1=Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1')
for name,data in [('root',new/'tree/py/gamedata.json'),('rootstats',new/'stats/gamedata.json')]:
    root=new/name;root.mkdir()
    for label,target in [('engine-rs',new/'tree'),('src',new/'tree/py/src'),('gamedata.json',data),('reports',r1/'reports')]:
        (root/label).symlink_to(target)
inputs=dict(old_inputs)
for name in manifest['files']:inputs[str(new/name)]=sha(new/name)
for name in manifest['engine_files']:inputs[str(new/'tree'/name)]=sha(new/'tree'/name)
for name in reuse:inputs[str(new/'fid'/name)]=sha(new/'fid'/name)
inputs[str(new/'stats/gamedata.json')]=sha(new/'stats/gamedata.json')
for path in (capture/'terminal.json',capture/'launch.json',capture/'source-and-tools.json',capture/'identity.json',capture/'fid/fixtures.json'):
    inputs[str(path)]=sha(path)
for path in (Path('/mpac/sdicks02/tools/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin')/name for name in ('cargo','rustc')):
    inputs[str(path)]=sha(path)
manifest.update(inputs=inputs,source_delta_from_captured=sorted(changed),old_source_manifest_sha256=sha(old/'source-and-tools.json'),capture_terminal_sha256=sha(capture/'terminal.json'))
with (new/'source-and-tools.json').open('w') as out:json.dump(manifest,out,indent=1)
manifest_sha=sha(new/'source-and-tools.json')
env=os.environ.copy()
for key in list(env):
    if key.startswith('CLASHER_') or key in ('BASH_ENV','ENV','PYTHONHOME','PYTHONINSPECT','PYTHONSTARTUP','PYTHONPATH','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS'):
        env.pop(key,None)
env.update(PYTHONOPTIMIZE='0',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',B2_RAGE_MANIFEST_SHA256=manifest_sha,
           OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','4',
         'bash',str(new/'fid/run_rage_fix_v1.sh'),str(new),tag]
with (new/'run.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=new,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),jobdir=str(new),tag=tag,pid=child.pid,pgid=os.getpgid(child.pid),
             args=command,cpu_bound=4,nice=15,source_and_tools_sha256=manifest_sha,
             source_commit=manifest['source_commit'],old_live_groups=[],old_leases_present=False)
with (new/'launch.json').open('x') as out:json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


def stage(review_path,tag):
    assert tag.startswith('ragefixv1-') and tag.replace('-','').isalnum()
    review=json.loads(review_path.read_text());assert review['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    required=['tools/'+name for name in FILES]+['RAGE-STATE-FIX.md','evidence/ragefix-source-review-inputs.json']
    assert set(required)<=set(review['reviewed_sha256'])
    for name,expected in review['reviewed_sha256'].items():
        path=(SCOPE/name).resolve();path.relative_to(SCOPE.resolve());assert sha(path)==expected,('reviewed input changed',name)
    receipt=SCOPE/'evidence'/f'{tag}-launch.json';assert not receipt.exists(),'receipt exists; do not retry'
    names=subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    engine={str(Path(name).relative_to('engine-cards')):sha(WORKTREE/name) for name in names if name}
    source_review=json.loads((SCOPE/'evidence/ragefix-source-review-inputs.json').read_text())
    assert engine==source_review['engine_files'] and len(engine)==504,'source differs from reviewed candidate'
    files={'fid/'+name:HERE/name for name in FILES}
    files.update({'RAGE-STATE-FIX.md':SCOPE/'RAGE-STATE-FIX.md','source-review.json':SCOPE/'evidence/ragefix-source-review-inputs.json','review.json':review_path})
    manifest=dict(source_commit=subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip(),
                  engine_files=engine,engine_wip_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(WORKTREE),'diff','--','engine-cards'])).hexdigest(),
                  files={name:sha(path) for name,path in files.items()},reviewed_sha256=review['reviewed_sha256'])
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for name,path in files.items():
            assert path.is_file() and not path.is_symlink();archive.add(path,arcname=name,recursive=False)
        for name in engine:
            path=WORKTREE/'engine-cards'/name;assert path.is_file() and not path.is_symlink()
            archive.add(path,arcname='tree/'+name,recursive=False)
        data=json.dumps(manifest,indent=1).encode();member=tarfile.TarInfo('source-and-tools.json');member.size=len(data);archive.addfile(member,io.BytesIO(data))
    result=subprocess.run(['ssh','127x08','python3 -c '+shlex.quote(REMOTE)+' '+shlex.quote(tag)],input=payload.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        sys.stderr.write(result.stderr.decode());raise SystemExit(result.returncode)
    launched=json.loads(result.stdout)
    with receipt.open('x') as out:json.dump(launched,out,indent=1)
    print(json.dumps(launched),flush=True)


if __name__=='__main__':stage(Path(sys.argv[1]),sys.argv[2])
