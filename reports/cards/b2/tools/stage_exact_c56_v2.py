"""One fresh exact-source C56 gate on04, after the reviewed08 capture terminal.

Usage: stage_exact_c56_v2.py REVIEW.json c56v2-UTC_TAG CANDIDATE_JOBDIR CAPTURE_JOBDIR
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
TOTAL='76f873f1fcd2e1f5056ea792fe14828af2c0b60ba72579ecf28d6c1ba4fb7054'
BUILD_SHA256='adcd109b3482984c322af61fa2adbae8c8380fbc42cb3f8404603d304273daf0'
AFFECTED_SHA256='0a105fda904f4d77c157f561fe4462d53fd29f61d3a510b4c8a03ce4b2325b19'
SOURCE_COMMIT='55bac129b93a055898524b53cc350091fb65259e'
PIN='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'
FILES=['stage_exact_c56_v2.py','run_exact_c56_v2.sh','exact_c56_receipts_v2.py','test_exact_c56_receipts_v2.py','observe_c56_fixtures_v2.py']
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
assert terminal['identity_sha256']=='3995110721b39f0b5c3c705299f533db4ed60383022d853ca98b0b0a548737d5'
assert terminal['output_sha256']=='b0ecd196b9cd70a03fa358412c2c4fc8e195dd3960d9bae8689db23574d07358'
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


READ_BUILD08=r'''
import hashlib,json,subprocess,sys
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('optimized candidate read forbidden')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def validate_candidate(job):
    assert job.parent==Path('/mpac/sdicks02/jobs/clasher/cards') and job.name.startswith('b2-ragefixv1-')
    assert sha(job/'build.json')=='adcd109b3482984c322af61fa2adbae8c8380fbc42cb3f8404603d304273daf0','reviewed build identity changed'
    assert sha(job/'affected.json')=='0a105fda904f4d77c157f561fe4462d53fd29f61d3a510b4c8a03ce4b2325b19','reviewed affected receipt changed'
    build=json.loads((job/'build.json').read_text())
    affected=json.loads((job/'affected.json').read_text())
    assert build['source_commit']=='55bac129b93a055898524b53cc350091fb65259e'
    assert len(build['source_engine_files'])==504
    assert build['native_sha256']['out4']=='76f873f1fcd2e1f5056ea792fe14828af2c0b60ba72579ecf28d6c1ba4fb7054'
    assert affected['status']=='AFFECTED_CHECKS_COMPLETE' and affected['build_sha256']==sha(job/'build.json')
    assert affected['native_sha256']==build['native_sha256']
    assert affected['rage_matching_continuations']==80 and affected['rage_impact_matching_continuations']==8
    assert affected['rage_mirror_matching_continuations']==2 and affected['unchanged_critical_guard_continuations']==560
    assert affected['retained_semantic_failures']==56
    assert affected['semantic_status']=='FAIL retained; no full sweep/engine acceptance'
    assert (job/'run.exit').read_text().strip()=='0'
    launch=json.loads((job/'launch.json').read_text());assert launch['jobdir']==str(job)
    assert launch['pid']==launch['pgid'] and launch['cpu_bound']==4 and launch['nice']==15
    rows=subprocess.check_output(['ps','-eo','pid,pgid,stat'],text=True).splitlines()[1:]
    assert not [r for r in rows if r.split()[1]==str(launch['pgid']) and not r.split()[2].startswith('Z')]
    assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-'+str(launch['pgid'])).exists()
    for path,expected in build['inputs'].items():assert sha(Path(path))==expected,('changed candidate input',path)
    for name,expected in build['source_engine_files'].items():assert sha(job/'tree'/name)==expected,('candidate source drift',name)
    for name,expected in affected['outputs'].items():assert sha(job/name)==expected,('affected output drift',name)
    assert sha(job/'out4/clasher_core.abi3.so')==build['native_sha256']['out4']
    return dict(jobdir=str(job),build=build,affected=affected,build_sha256=sha(job/'build.json'),affected_sha256=sha(job/'affected.json'),launch=launch)
print(json.dumps(validate_candidate(Path(sys.argv[1]))))
'''


REMOTE=r'''
import gzip,hashlib,io,json,os,random,shutil,subprocess,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('optimized remote staging forbidden')
tag=sys.argv[1]
assert tag.startswith('c56v2-') and tag.replace('-','').isalnum()
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
sys.path.insert(0,str(job/'tools'))
from exact_c56_receipts_v2 import shared_source_inventory
shared_sources=shared_source_inventory(bot)
paths.update(bot/name for name in shared_sources)
manifest.update(shared_bot_root=str(bot),shared_bot_source_method='actual-filesystem-python-json-v1',
                shared_bot_files=shared_sources,shared_bot_commit=None)
# Cover runtime Python/search/resource sources, configuration and model inputs.
for directory in ('engine-rs','src','imitation','student-source','reports'):
    for path in (r1/directory).rglob('*'):
        if path.is_file() and path.suffix in ('.py','.json','.pt','.npz','.npy','.so'):paths.add(path)
for path in r1.iterdir():
    if path.is_file() and path.suffix in ('.py','.json','.pt','.npz','.npy'):paths.add(path)
python=Path('/mpac/sdicks02/repos/clasher-bot/.venv/bin/python')
paths.add(python);paths.add(python.parent.parent/'pyvenv.cfg')
manifest['inputs']={str(path):sha(path) for path in sorted(paths)}
with (job/'manifest.json').open('w') as out:json.dump(manifest,out,indent=1)
manifest_sha=sha(job/'manifest.json')
(job/'gate').mkdir()
env=os.environ.copy()
for key in list(env):
    if key.startswith('CLASHER_') or key in ('BASH_ENV','ENV','PYTHONHOME','PYTHONINSPECT','PYTHONSTARTUP','PYTHONPATH'):
        env.pop(key,None)
env.update(B2_C56_MANIFEST_SHA256=manifest_sha,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',PYTHONOPTIMIZE='0',
           OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','4','bash',str(job/'tools/run_exact_c56_v2.sh'),str(job)]
with (job/'run.log').open('xb') as log:
    child=subprocess.Popen(command,cwd=job,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),host='127x04',jobdir=str(job),pid=child.pid,
             pgid=os.getpgid(child.pid),args=command,cpu_bound=4,nice=15,manifest_sha256=manifest_sha,
             native_sha256=manifest['native_sha256'],source_commit=manifest['source_commit'],
             candidate_build_sha256=manifest['candidate08']['build_sha256'],
             old08_capture_terminal_sha256=manifest['capture08']['capture_terminal_sha256'])
with (job/'launch.json').open('x') as out:json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


def stage(review_path,tag,candidate_job,capture_job):
    assert tag.startswith('c56v2-') and tag.replace('-','').isalnum()
    target=SCOPE/'evidence'/f'{tag}-launch.json'
    assert not target.exists(),'receipt exists; do not retry/relaunch'
    review=json.loads(review_path.read_text())
    assert review['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    required=['tools/'+name for name in FILES]+['EXACT-C56-GATE-V2.md','evidence/gate-provenance.json','evidence/fixture-v1-review2-approved.json','evidence/c56-v2-candidate.json']
    assert set(required)<=set(review['reviewed_sha256'])
    for name,expected in review['reviewed_sha256'].items():
        path=(SCOPE/name).resolve();path.relative_to(SCOPE.resolve())
        assert sha(path)==expected,('reviewed bytes changed',name)
    declared=json.loads((SCOPE/'evidence/c56-v2-candidate.json').read_text())
    assert declared['jobdir']==candidate_job and declared['build_sha256']==BUILD_SHA256 and declared['affected_sha256']==AFFECTED_SHA256
    assert declared['native_sha256']==TOTAL and declared['source_commit']==SOURCE_COMMIT
    assert TOTAL!='0'*64 and 'PENDING' not in BUILD_SHA256 and 'PENDING' not in AFFECTED_SHA256
    capture=json.loads(subprocess.check_output(['ssh','127x08','python3 -c '+shlex.quote(READ08)+' '+shlex.quote(capture_job)]))
    capture_approval=json.loads((SCOPE/'evidence/fixture-v1-review2-approved.json').read_text())
    assert capture['capture_review']['reviewed_sha256']==capture_approval['reviewed_sha256']
    assert capture_approval['verdict']=='APPROVED FOR BOUNDED TEST EXECUTION'
    candidate=json.loads(subprocess.check_output(['ssh','127x08','python3 -c '+shlex.quote(READ_BUILD08)+' '+shlex.quote(candidate_job)]))
    assert candidate['build_sha256']==BUILD_SHA256 and candidate['affected_sha256']==AFFECTED_SHA256
    names=subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    engine={str(Path(name).relative_to('engine-cards')):sha(WORKTREE/name) for name in names if name}
    assert len(engine)==504 and engine==candidate['build']['source_engine_files'], 'full built source mismatch'
    native=subprocess.check_output(['ssh','127x08','cat '+shlex.quote(candidate_job+'/out4/clasher_core.abi3.so')])
    assert hashlib.sha256(native).hexdigest()==TOTAL
    files={'tools/'+name:HERE/name for name in FILES}
    files.update({'EXACT-C56-GATE-V2.md':SCOPE/'EXACT-C56-GATE-V2.md','review.json':review_path,
                  'gate-provenance.json':SCOPE/'evidence/gate-provenance.json',
                  'capture-review.json':SCOPE/'evidence/fixture-v1-review2-approved.json'})
    files['candidate-receipt.json']=SCOPE/'evidence/c56-v2-candidate.json'
    for name in ('parity_fixtures.py','parity_roots.py','compare.py'):
        files['canonical/'+name]=BOT/'reports/bot/learned-opponent/native-total-tools'/name
    from exact_c56_receipts_v2 import check_canonical
    check_canonical(BOT/'reports/bot/learned-opponent/native-total-tools',
                    json.loads((SCOPE/'evidence/gate-provenance.json').read_text()))
    manifest=dict(source_commit=SOURCE_COMMIT,
                  staging_commit=subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip(),
                  engine_files=engine,capture08=capture,candidate08=candidate,native_sha256=dict(pinned=PIN,total=TOTAL),
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


if __name__=='__main__':stage(Path(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4])
