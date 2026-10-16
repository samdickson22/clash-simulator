"""Reviewed one-shot staging of a separate semantic-v1 affected validation on 08.

Usage: stage_semantic_v1.py APPROVED_REVIEW.json semv1-UTC_TAG
Requires the prior owned group3422841 terminal and lease absent. Never kills,
modifies old inputs/outputs, retries, or launches a second tag automatically.
Review keys are relative to reports/cards/b2 (including tools/ and the contract).
"""
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
SCOPE = HERE.parent
WORKTREE = HERE.parents[3]
OLD = '/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z'
FILES = ['snapshot_contract_v1.py', 'probe_dash_semantic_v1.py', 'probe_cache_descendants_v1.py',
         'validate_semantic_v1.py', 'run_semantic_v1.sh', 'stage_semantic_v1.py', 'test_r2_harness.py']

REMOTE = r'''
import hashlib,io,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
from datetime import datetime,timezone
old=Path('/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z')
tag=sys.argv[1]
assert tag.startswith('semv1-') and tag.replace('-','').isalnum()
new=old.parent/('b2-'+tag)
assert not new.exists(), 'fresh directory exists; inspect, do not retry/relaunch'
pid=3422841
proc=Path('/proc')/str(pid)
if proc.exists():
    fields=(proc/'stat').read_text().rsplit(') ',1)[1].split()
    assert fields[0]=='Z', 'old validation still alive: no competing run'
    assert os.getpgid(pid)==pid and proc.stat().st_uid==os.getuid()
members=subprocess.check_output(['ps','-eo','pid,pgid,stat,args'],text=True).splitlines()[1:]
assert not [r for r in members if r.split(None,3)[1]==str(pid) and not r.split(None,3)[2].startswith('Z')], 'old group has live work'
assert not Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-3422841').exists(), 'old CPU lease remains'
assert not (old/'fid/r2v2.pass.json').exists(), 'strict verdict unexpectedly changed; inspect'
assert all((old/f'fid/r2v2-full-{i}.exit').exists() for i in range(1,5)), 'old runner not terminal'
assert (old/'fid/r2v2-full-3.exit').read_text().strip()!='0', 'expected old config failure not present'
assert 'cannot unpack non-iterable NoneType object' in (old/'fid/r2v2-full-3.log').read_text()
# Those phases were never entered after phase1's nonzero exit. Do not duplicate useful prior evidence.
for label in ('mutA','mutB','fu-paths','clone-bounds','clone-recovery','scen-b2-root','scen-b2-stats','scen-batchA'):
    assert not (old/f'fid/r2v2-{label}.json').exists(), ('phase already exists; revise reuse plan',label)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
old_identity=json.loads((old/'fid/r2v2-identity.json').read_text())
original_inputs=dict(old_identity['inputs'])
for path,value in original_inputs.items():
    assert sha(Path(path))==value, ('strict input changed',path)
for p in list((old/'fid').glob('r2v2*'))+[old/'launch.json',old/'source-and-tools.json',old/'run.log']:
    if p.is_file(): original_inputs[str(p)]=sha(p)
new.mkdir()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    for member in archive.getmembers():
        assert member.isfile(), member.name
        (new/member.name).resolve().relative_to(new.resolve())
    archive.extractall(new)
manifest=json.loads((new/'source-and-tools.json').read_text())
for name,expected in manifest['files'].items():
    assert sha(new/name)==expected, ('tool copy changed',name)
for name,expected in manifest['engine_files'].items():
    assert sha(old/'tree'/name)==expected, ('local WIP differs from frozen native source',name)
shutil.copytree(old/'tree',new/'tree')
for name,expected in manifest['engine_files'].items():
    assert sha(new/'tree'/name)==expected
for name,expected in manifest['natives'].items():
    (new/name).mkdir()
    target=new/name/'clasher_core.abi3.so'
    shutil.copy2(old/name/'clasher_core.abi3.so',target)
    assert sha(target)==expected, ('native changed',name)
for name in ('validate_r2.py','probe_clone_bounds.py','probe_clone_recovery.py','run_scen.sh',
             'probe_native_scen.py','scenarios.py','probe_first_update_paths.py','native_entity_sites.py','probe_dash_full.py','pool.json'):
    shutil.copy2(old/'fid'/name,new/'fid'/name)
(new/'stats').mkdir(); shutil.copy2(old/'stats/gamedata.json',new/'stats/gamedata.json')
runtime=Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1')
for name,data in [('root',new/'tree/py/gamedata.json'),('rootstats',new/'stats/gamedata.json')]:
    root=new/name; root.mkdir()
    for label,target in [('engine-rs',new/'tree'),('src',new/'tree/py/src'),('gamedata.json',data),('reports',runtime/'reports')]:
        (root/label).symlink_to(target)
original=dict(strict_status='FAIL preserved',utc=datetime.now(timezone.utc).isoformat(),
              old_pid=pid,old_lease_present=False,old_live_group=[],inputs=original_inputs,
              old_phase1_exits={str(i):(old/f'fid/r2v2-full-{i}.exit').read_text().strip() for i in range(1,5)},
              unstarted_parity_phases='No original FU/Clone/scenario output; run unchanged once in the affected job')
with (new/'original-receipts.json').open('x') as out: json.dump(original,out,indent=1)
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','4',
         'bash',str(new/'fid/run_semantic_v1.sh'),str(new),tag]
with (new/'run.log').open('xb') as log:
    process=subprocess.Popen(command,cwd=new,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(new/'run.pid').write_text(str(process.pid)+'\n')
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),pid=process.pid,pgid=os.getpgid(process.pid),
             args=command,jobdir=str(new),tag=tag,cpu_bound=4,nice=15,
             source_and_tools_sha256=sha(new/'source-and-tools.json'),
             original_receipts_sha256=sha(new/'original-receipts.json'),native_sha256=manifest['natives'])
with (new/'launch.json').open('x') as out: json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


if __name__ == '__main__':
    review = json.loads(Path(sys.argv[1]).read_text())
    tag = sys.argv[2]
    assert tag.startswith('semv1-') and tag.replace('-', '').isalnum()
    assert review['verdict'] == 'APPROVED FOR BOUNDED TEST EXECUTION'
    required = ['tools/' + name for name in FILES] + ['SEMANTIC-SNAPSHOT-V1.md']
    assert set(required) <= set(review['reviewed_sha256']), 'all affected files require review'
    for name, expected in review['reviewed_sha256'].items():
        path = (SCOPE / name).resolve(); path.relative_to(SCOPE.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, ('reviewed input changed', name)
    receipt_path = SCOPE / 'evidence' / f'{tag}-launch.json'
    assert not receipt_path.exists(), 'launch receipt exists; do not retry'
    files = {'fid/' + name: HERE / name for name in FILES}
    files['SEMANTIC-SNAPSHOT-V1.md'] = SCOPE / 'SEMANTIC-SNAPSHOT-V1.md'
    files['review.json'] = Path(sys.argv[1])
    tracked = subprocess.check_output(['git', '-C', str(WORKTREE), 'ls-files', '-z', 'engine-cards'], text=True).split('\0')
    engine = {str(Path(name).relative_to('engine-cards')): hashlib.sha256((WORKTREE/name).read_bytes()).hexdigest()
              for name in tracked if name}
    # Import only the pure stdlib validator to obtain immutable library pins.
    sys.path.insert(0, str(HERE))
    from validate_semantic_v1 import NATIVES
    patch = subprocess.check_output(['git', '-C', str(WORKTREE), 'diff', '--', 'engine-cards'])
    manifest = dict(source_commit=subprocess.check_output(['git', '-C', str(WORKTREE), 'rev-parse', 'HEAD'], text=True).strip(),
                    engine_wip_diff_sha256=hashlib.sha256(patch).hexdigest(), engine_files=engine,
                    natives=NATIVES, reviewed_sha256=review['reviewed_sha256'],
                    files={name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()})
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        for name, path in files.items():
            assert path.is_file() and not path.is_symlink(), path
            archive.add(path, arcname=name, recursive=False)
        data = json.dumps(manifest, indent=1).encode()
        member = tarfile.TarInfo('source-and-tools.json'); member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    command = 'python3 -c ' + shlex.quote(REMOTE) + ' ' + shlex.quote(tag)
    result = subprocess.run(['ssh', '127x08', command], input=payload.getvalue(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        sys.stderr.write(result.stderr.decode()); raise SystemExit(result.returncode)
    launched = json.loads(result.stdout)
    with receipt_path.open('x') as out:
        json.dump(launched, out, indent=1)
    print(json.dumps(launched), flush=True)
