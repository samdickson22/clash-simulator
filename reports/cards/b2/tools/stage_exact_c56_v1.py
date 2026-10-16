"""One fresh exact-source C56 gate on04, after the reviewed08 capture terminal.

Usage: stage_exact_c56_v1.py REVIEW.json c56v1-UTC_TAG CAPTURE_JOBDIR
No old gate restart, build, pin/runtime write, process stop or automatic retry.
"""
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized staging forbidden')

HERE=Path(__file__).resolve().parent
SCOPE=HERE.parent
WORKTREE=HERE.parents[3]
TOTAL='7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff'
PIN='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'
FILES=['stage_exact_c56_v1.py','run_exact_c56_v1.sh','exact_c56_receipts_v1.py','test_exact_c56_receipts_v1.py','observe_c56_fixtures_v1.py']
BOT=Path('/mpac/sdicks02/repos/clasher-bot')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


READ08=r'''
import hashlib,json,os,subprocess,sys
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('optimized remote read forbidden')
job=Path(sys.argv[1]); old=Path('/mpac/sdicks02/jobs/clasher/cards/b2-semv1-20261016T1052Z')
assert job.parent==old.parent and job.name.startswith('b2-fixturev1-')
launch=json.loads((job/'launch.json').read_text()); terminal=json.loads((job/'terminal.json').read_text())
assert launch['jobdir']==str(job) and terminal['status']=='CAPTURE_COMPLETE'
assert terminal['collection_status']=='COMPLETE' and not terminal['changed_inputs']
assert terminal['exit_code']==0 and (job/'probe.exit').read_text().strip()=='0'
assert launch['pid']==launch['pgid'] and launch['cpu_bound']==1 and launch['nice']==15
for pid in (3586969,launch['pgid']):
    rows=subprocess.check_output(['ps','-eo','pid,pgid,stat'],text=True).splitlines()[1:]
    assert not [r for r in rows if r.split()[1]==str(pid) and not r.split()[2].startswith('Z')], ('active',pid)
    assert not Path(f'/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-{pid}').exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
identity=json.loads((old/'fid/semv1-20261016T1052Z-identity.json').read_text())
for path,expected in identity['inputs'].items():assert sha(Path(path))==expected,('changed old input',path)
assert sha(job/'fid/fixtures.json')==terminal['output_sha256']
assert sha(job/'identity.json')==terminal['identity_sha256']
for path,expected in json.loads((job/'identity.json').read_text())['inputs'].items():
    assert sha(Path(path))==expected,('changed capture input',path)
manifest=json.loads((job/'source-and-tools.json').read_text())
assert sha(job/'source-and-tools.json')==launch['source_and_tools_sha256']
review=json.loads((job/'review.json').read_text())
assert review['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
assert manifest['reviewed_sha256']==review['reviewed_sha256']
for name,expected in review['reviewed_sha256'].items():
    path=job/('fid/'+name[6:] if name.startswith('tools/') else name)
    assert sha(path)==expected,('capture reviewed file',name)
results=json.loads((job/'fid/fixtures.json').read_text())
assert results['collection_status']=='COMPLETE' and results['collection_error'] is None
natural={(name,lead,seat) for name,lead in [('zap',1),('zap',-4),('freeze',1),('log',-4),('ice_spirit',0),('electro_dragon',6),('magic_archer',10),('executioner',10)] for seat in (0,1)}
legacy={(name,lead,seat) for name,lead in [('zap',1),('electro_dragon',6),('ice_spirit',0)] for seat in (0,1)}
assert len(results['rows'])==16 and {(r['case'],r['lead'],r['seat']) for r in results['rows']}==natural
assert len(results['legacy'])==6 and {(r['case'],r['lead'],r['seat']) for r in results['legacy']}==legacy
source_manifest=json.loads((old/'source-and-tools.json').read_text())
assert sha(old/'source-and-tools.json')==identity['inputs'][str(old/'source-and-tools.json')]
assert len(source_manifest['engine_files'])==504
for name,expected in source_manifest['engine_files'].items():assert sha(old/'tree'/name)==expected,('frozen complete source',name)
print(json.dumps(dict(identity=identity,old_job=str(old),capture_job=str(job),capture_terminal=terminal,
                     capture_terminal_sha256=sha(job/'terminal.json'),capture_launch=launch,
                     capture_review=review,source_manifest=source_manifest)))
'''


REMOTE=r'''
import gzip,hashlib,io,json,os,random,shutil,subprocess,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('optimized remote staging forbidden')
tag=sys.argv[1]
assert tag.startswith('c56v1-') and tag.replace('-','').isalnum()
job=Path('/mpac/sdicks02/jobs/clasher/cards')/('b2-'+tag)
assert not job.exists(),'fresh job exists; inspect without retry'
job.mkdir()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    for member in archive.getmembers():
        assert member.isfile(),member.name
        (job/member.name).resolve().relative_to(job.resolve())
    archive.extractall(job)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''):h.update(block)
    return h.hexdigest()
manifest=json.loads((job/'manifest.json').read_text())
for path,expected in manifest['files'].items():assert sha(job/path)==expected,('staged bytes',path)
assert len(manifest['engine_files'])==504
for path,expected in manifest['engine_files'].items():assert sha(job/'tree'/path)==expected,('engine bytes',path)
r1=Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1')
baseline=Path('/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1/clasher_core.abi3.so')
assert sha(baseline)==manifest['native_sha256']['pinned']
(job/'pinned-native').mkdir();shutil.copy2(baseline,job/'pinned-native/clasher_core.abi3.so')
assert sha(job/'total-native/clasher_core.abi3.so')==manifest['native_sha256']['total']
rt=job/'rt';rt.mkdir()
for child in r1.iterdir():
    if child.name not in ('engine-rs','src','gamedata.json'):(rt/child.name).symlink_to(child)
for name,target in [('engine-rs',job/'tree'),('src',job/'tree/py/src'),('gamedata.json',job/'tree/py/gamedata.json')]:
    (rt/name).symlink_to(target)
original_roots=Path('/mpac/sdicks02/jobs/clasher/cards/b2/roots')
shutil.copytree(original_roots,job/'roots')
corpus=json.loads((job/'gate-provenance.json').read_text())['roots']
canonical=json.loads((job/'gate-provenance.json').read_text())['gate_tools']
for name in ('parity_fixtures.py','parity_roots.py','compare.py'):
    assert sha(job/'canonical'/name)==canonical[name],('historical canonical source',name)
assert {p.name for p in (job/'roots').iterdir()}==set(corpus)
for name,expected in corpus.items():assert sha(job/'roots'/name)==expected,('historical root corpus',name)
data=Path('/mpac/sdicks02/repos/clasher-bot-data')
split=json.loads((data/'t1-split.json').read_text())
episodes=sorted(r['episode'] for r in split['matches'] if r['split'] in ('train','validation') and (data/'t1-trainval'/r['episode']).exists())
assert len(episodes)==len(set(episodes))==577
manifest['episodes']=episodes
paths=set(job/name for name in manifest['files'])
paths.update(job/'tree'/name for name in manifest['engine_files'])
paths.update((job/'roots').iterdir())
paths.add(job/'pinned-native/clasher_core.abi3.so')
paths.add(data/'t1-split.json')
for episode in episodes:
    for name in ('setup.json','evaluation-only.jsonl.gz','events.jsonl','objects.jsonl.gz'):
        paths.add(data/'t1-trainval'/episode/name)
bot=Path('/mpac/sdicks02/repos/clasher-bot')
tracked=subprocess.check_output(['git','-C',str(bot),'ls-files','-z'],text=True).split('\0')
paths.update(bot/name for name in tracked if name and Path(name).suffix in ('.py','.json'))
# Cover runtime Python/search/resource sources, configuration and model inputs.
for directory in ('engine-rs','src','imitation','student-source','reports'):
    for path in (r1/directory).rglob('*'):
        if path.is_file() and path.suffix in ('.py','.json','.pt','.npz','.npy','.so'):paths.add(path)
for path in r1.iterdir():
    if path.is_file() and path.suffix in ('.py','.json','.pt','.npz','.npy'):paths.add(path)
python=Path('/mpac/sdicks02/repos/clasher-bot/.venv/bin/python')
paths.add(python);paths.add(python.parent.parent/'pyvenv.cfg')
manifest['shared_bot_commit']=subprocess.check_output(['git','-C',str(bot),'rev-parse','HEAD'],text=True).strip()
manifest['inputs']={str(path):sha(path) for path in sorted(paths)}
with (job/'manifest.json').open('w') as out:json.dump(manifest,out,indent=1)
manifest_sha=sha(job/'manifest.json')
(job/'gate').mkdir()
env=os.environ.copy()
for key in ('BASH_ENV','ENV','PYTHONHOME','PYTHONINSPECT','PYTHONSTARTUP','PYTHONPATH',
            'CLASHER_ROOT','CLASHER_EVAL_RUNTIME_ROOT','CLASHER_DELAY_NATIVE_DIR','CLASHER_BOT_RUNTIME','CLASHER_BOT_RUNTIME_PINS'):
    env.pop(key,None)
env.update(B2_C56_MANIFEST_SHA256=manifest_sha,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',PYTHONOPTIMIZE='0',
           OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','4','bash',str(job/'tools/run_exact_c56_v1.sh'),str(job)]
with (job/'run.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=job,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),host='127x04',jobdir=str(job),pid=child.pid,
             pgid=os.getpgid(child.pid),args=command,cpu_bound=4,nice=15,manifest_sha256=manifest_sha,
             native_sha256=manifest['native_sha256'],source_commit=manifest['source_commit'],
             old08_capture_terminal_sha256=manifest['capture08']['capture_terminal_sha256'])
with (job/'launch.json').open('x') as out:json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


def stage(review_path,tag,capture_job):
    assert tag.startswith('c56v1-') and tag.replace('-','').isalnum()
    target=SCOPE/'evidence'/f'{tag}-launch.json'
    assert not target.exists(),'receipt exists; do not retry/relaunch'
    review=json.loads(review_path.read_text())
    assert review['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    required=['tools/'+name for name in FILES]+['EXACT-C56-GATE-V1.md','evidence/gate-provenance.json','evidence/fixture-v1-review2-approved.json']
    assert set(required)<=set(review['reviewed_sha256'])
    for name,expected in review['reviewed_sha256'].items():
        path=(SCOPE/name).resolve();path.relative_to(SCOPE.resolve())
        assert sha(path)==expected,('reviewed bytes changed',name)
    capture=json.loads(subprocess.check_output(['ssh','127x08','python3 -c '+shlex.quote(READ08)+' '+shlex.quote(capture_job)]))
    capture_approval=json.loads((SCOPE/'evidence/fixture-v1-review2-approved.json').read_text())
    assert capture['capture_review']['reviewed_sha256']==capture_approval['reviewed_sha256']
    assert capture_approval['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    names=subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    engine={str(Path(name).relative_to('engine-cards')):sha(WORKTREE/name) for name in names if name}
    assert len(engine)==504 and engine==capture['source_manifest']['engine_files'], 'full frozen source mismatch'
    native=subprocess.check_output(['ssh','127x08','cat '+shlex.quote(capture['old_job']+'/out4/clasher_core.abi3.so')])
    assert hashlib.sha256(native).hexdigest()==TOTAL
    files={'tools/'+name:HERE/name for name in FILES}
    files.update({'EXACT-C56-GATE-V1.md':SCOPE/'EXACT-C56-GATE-V1.md','review.json':review_path,
                  'gate-provenance.json':SCOPE/'evidence/gate-provenance.json',
                  'capture-review.json':SCOPE/'evidence/fixture-v1-review2-approved.json'})
    for name in ('parity_fixtures.py','parity_roots.py','compare.py'):
        files['canonical/'+name]=BOT/'reports/bot/learned-opponent/native-total-tools'/name
    from exact_c56_receipts_v1 import check_canonical
    check_canonical(BOT/'reports/bot/learned-opponent/native-total-tools',
                    json.loads((SCOPE/'evidence/gate-provenance.json').read_text()))
    manifest=dict(source_commit=subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip(),
                  engine_files=engine,capture08=capture,native_sha256=dict(pinned=PIN,total=TOTAL),
                  files={name:sha(path) for name,path in files.items()})
    manifest['files']['total-native/clasher_core.abi3.so']=TOTAL
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for name,path in files.items():
            assert path.is_file() and not path.is_symlink()
            archive.add(path,arcname=name,recursive=False)
        for name in engine:
            archive.add(WORKTREE/'engine-cards'/name,arcname='tree/'+name,recursive=False)
        for name,data in [('manifest.json',json.dumps(manifest,indent=1).encode()),('total-native/clasher_core.abi3.so',native)]:
            item=tarfile.TarInfo(name);item.size=len(data);archive.addfile(item,io.BytesIO(data))
    result=subprocess.run(['ssh','127x04','python3 -c '+shlex.quote(REMOTE)+' '+shlex.quote(tag)],input=payload.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        sys.stderr.write(result.stderr.decode());raise SystemExit(result.returncode)
    receipt=json.loads(result.stdout)
    with target.open('x') as out:json.dump(receipt,out,indent=1)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':stage(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
