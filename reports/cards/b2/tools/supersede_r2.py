"""One-shot, reviewed B2 scheduling transition; no retries/requeues or broad kills.

Usage: supersede_r2.py APPROVED_REVIEW_RECEIPT.json
The review receipt must contain reviewed_sha256 for this script and every corrected
harness script. The existing queued 561530 group is stopped briefly, rechecked for
admission, then either resumed unchanged or terminated as explicitly authorized.
Only after a successful supersede receipt is ONE fresh isolated cpu_job4 queued.
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
WORKTREE = HERE.parents[3]
HOST = '127x08'
OLD = '/mpac/sdicks02/jobs/clasher/cards/b2m'
NEW = '/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0925Z'
TAG = 'r2v2'

SUPERSEDE = r'''
import json,os,signal,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
old=Path('/mpac/sdicks02/jobs/clasher/cards/b2m'); pid=561530
lease=Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-561530')
expected=['bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','8','bash',str(old/'fid/run_r2.sh'),str(old),str(old/'out4'),str(old/'mutA'),str(old/'mutB')]
def utc(): return datetime.now(timezone.utc).isoformat()
def args(p): return Path(f'/proc/{p}/cmdline').read_bytes().decode().rstrip('\0').split('\0')
def identity():
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()
    assert fields[19]=='193963347', 'PID start identity changed'
    assert os.getpgid(pid)==pid and Path(f'/proc/{pid}').stat().st_uid==os.getuid(), 'PGID/owner changed'
    assert args(pid)==expected, ('launcher args changed',args(pid))
def members():
    rows=subprocess.check_output(['ps','-eo','pid,ppid,pgid,stat,args'],text=True).splitlines()[1:]
    return [line for line in rows if line.split(None,4)[2]==str(pid)]
def queued():
    assert not lease.exists(), 'lease acquired: leave existing work intact'
    assert not list((old/'fid').glob('r2*')), 'r2 outputs exist: leave existing work intact'
    assert (old/'r2.log').stat().st_size==0, 'launcher output exists: leave intact'
    children=[int(line.split()[0]) for line in members() if line.split()[1]==str(pid)]
    assert len(children)==1 and args(children[0])==['bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh','8'], 'not solely waiting for cpu_room8'
    return children[0]
assert not (old/'r2.superseded.json').exists(), 'already superseded; do not relaunch'
identity(); child=queued(); before=dict(utc=utc(),pid=pid,start_ticks=193963347,args=args(pid),members=members(),cpu_room_child=child)
# Freeze only this owned group to close the admission race. If it already admitted, finally resumes it unchanged.
stopped=False
try:
    os.killpg(pid,signal.SIGSTOP); stopped=True
    time.sleep(0.05)
    identity(); assert queued()==child
    os.killpg(pid,signal.SIGTERM)
finally:
    if stopped:
        try: os.killpg(pid,signal.SIGCONT)
        except ProcessLookupError: pass
for _ in range(50):
    live=[line for line in members() if not line.split()[3].startswith('Z')]
    if not live: break
    time.sleep(0.1)
assert not live and not lease.exists(), ('group/lease remains',live)
assert not Path(f'/mpac/sdicks02/jobs/clasher/bot-cpu-claims/claim-{child}').exists(), 'cpu_room claim remains; report without deleting'
receipt=dict(status='superseded-not-evidence',before=before,utc=utc(),live_group_members=live,lease_present=False,
             command='SIGSTOP group561530; repeat identity/queued checks; TERM exact group561530; SIGCONT group561530')
with (old/'r2.superseded.json').open('x') as out: json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''

PREPARE_AND_LAUNCH = r'''
import hashlib,io,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
from datetime import datetime,timezone
old=Path('/mpac/sdicks02/jobs/clasher/cards/b2m')
new=Path('/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0925Z'); tag='r2v2'
assert json.loads((old/'r2.superseded.json').read_text())['status']=='superseded-not-evidence'
assert not new.exists(), 'fresh job directory already exists; inspect before any retry'
new.mkdir()
# Archive is produced from tracked engine files and explicitly selected scoped tools, never runtime state.
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    for member in archive.getmembers():
        assert member.isfile() and (new/member.name).resolve().is_relative_to(new.resolve()), member.name
    archive.extractall(new)
manifest=json.loads((new/'source-and-tools.json').read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for name,expected in manifest['files'].items():
    assert sha(new/name)==expected, ('copied input hash mismatch',name)
    if name.startswith('tree/'):
        assert sha(old/name)==expected, ('source differs from already-built out4 tree',name)
natives={'out4':'7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff',
         'mutA':'ff74a2fc8cfb7e78c60d0c1eb9e0880aebab8fb010939b2fa9d0eb6cfe01ee33',
         'mutB':'2964dec34f8a0a29c9352e249e7e87e77adfce7bcdc908bdbb1443fb8b4265f3'}
for name,expected in natives.items():
    (new/name).mkdir()
    target=new/name/'clasher_core.abi3.so'
    shutil.copy2(old/name/'clasher_core.abi3.so',target)
    assert sha(target)==expected, ('native hash mismatch',name)
(new/'stats').mkdir()
shutil.copy2(old/'stats/gamedata.json',new/'stats/gamedata.json')
shutil.copy2(old/'fid/pool.json',new/'fid/pool.json')
runtime=Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1')
for rootname,data in [('root',new/'tree/py/gamedata.json'),('rootstats',new/'stats/gamedata.json')]:
    root=new/rootname; root.mkdir()
    for name,target in [('engine-rs',new/'tree'),('src',new/'tree/py/src'),('gamedata.json',data),('reports',runtime/'reports')]:
        (root/name).symlink_to(target)
command=['nice','-n','15','bash','/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh','4','bash',
         str(new/'fid/run_r2.sh'),str(new),str(new/'out4'),str(new/'mutA'),str(new/'mutB'),tag]
with (new/'run.log').open('xb') as log:
    process=subprocess.Popen(command,cwd=new,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(new/'run.pid').write_text(str(process.pid)+'\n')
receipt=dict(utc=datetime.now(timezone.utc).isoformat(),pid=process.pid,pgid=os.getpgid(process.pid),args=command,
             jobdir=str(new),tag=tag,source_and_tools_sha256=sha(new/'source-and-tools.json'),native_sha256=natives,
             reviewed_sha256=manifest['reviewed_sha256'],cpu_bound=4,nice=15,
             superseded_receipt_sha256=sha(old/'r2.superseded.json'))
with (new/'launch.json').open('x') as out: json.dump(receipt,out,indent=1)
print(json.dumps(receipt),flush=True)
'''


def remote(script, payload=b''):
    result = subprocess.run(['ssh', HOST, 'python3 -c ' + shlex.quote(script)], input=payload,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        sys.stderr.write(result.stderr.decode())
        raise SystemExit(result.returncode)
    print(result.stdout.decode(), flush=True)
    return json.loads(result.stdout)


if __name__ == '__main__':
    review = json.loads(Path(sys.argv[1]).read_text())
    assert review['verdict'] == 'APPROVED FOR BOUNDED TEST EXECUTION'
    for name, expected in review['reviewed_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, ('reviewed tool changed', name)
    assert Path(__file__).name in review['reviewed_sha256'], 'scheduler must be independently reviewed too'
    names = subprocess.check_output(['git','-C',str(WORKTREE),'ls-files','-z','engine-cards'],text=True).split('\0')
    files = {str(Path('tree')/Path(name).relative_to('engine-cards')): WORKTREE/name for name in names if name}
    for name in ['probe_dash_full.py','probe_clone_recovery.py','probe_clone_bounds.py','run_r2.sh',
                 'validate_r2.py','test_r2_harness.py','native_entity_sites.py','run_scen.sh','probe_native_scen.py','scenarios.py']:
        files[f'fid/{name}'] = HERE/name
    files['fid/probe_first_update_paths.py'] = WORKTREE/'reports/cards/batchA/tools/probe_first_update_paths.py'
    source_commit = subprocess.check_output(['git','-C',str(WORKTREE),'rev-parse','HEAD'],text=True).strip()
    patch = subprocess.check_output(['git','-C',str(WORKTREE),'diff','--','engine-cards'])
    manifest = dict(source_commit=source_commit,engine_wip_diff_sha256=hashlib.sha256(patch).hexdigest(),
                    files={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()},
                    reviewed_sha256=review['reviewed_sha256'])
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for name,path in files.items():
            assert path.is_file() and not path.is_symlink(), path
            archive.add(path,arcname=name,recursive=False)
        data=json.dumps(manifest,indent=1).encode()
        member=tarfile.TarInfo('source-and-tools.json'); member.size=len(data)
        archive.addfile(member,io.BytesIO(data))
    # No host mutation occurs until all local source/tool/review checks and archive preparation succeed.
    superseded = remote(SUPERSEDE)
    launched = remote(PREPARE_AND_LAUNCH,payload.getvalue())
    evidence = HERE.parent/'evidence'
    (evidence/'r2-superseded-20261016.json').write_text(json.dumps(superseded,indent=1)+'\n')
    (evidence/'r2v2-launch-20261016.json').write_text(json.dumps(launched,indent=1)+'\n')
