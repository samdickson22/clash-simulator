"""Read-only Git/source/hash and stdlib flag checks; writes receipts only beside this script."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
CANDIDATE='c7de06ea5a6171b4490682a7bb1be9baa825a2b4'
BASE='476a747f75569040f9b137d0991691c95e6f1b29'
FOCUSED='4bfae6b0844b4620d9482cc996a74bf86f1a1887'
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
commands=[]


def sha(data): return hashlib.sha256(data).hexdigest()


def call(argv, artifact=None, env=None):
    started=datetime.now(timezone.utc).isoformat()
    p=subprocess.run(argv,cwd=REPO,env=env,capture_output=True)
    row=dict(argv=argv,cwd=str(REPO),exit_code=p.returncode,started_utc=started,
             ended_utc=datetime.now(timezone.utc).isoformat(),stdout_sha256=sha(p.stdout),
             stdout_bytes=len(p.stdout),stderr=p.stderr.decode(errors='replace'))
    if env is not None: row['environment']=env
    if artifact:
        path=HERE/artifact
        with path.open('xb') as f: f.write(p.stdout)
        row['stdout_artifact']=str(path.relative_to(REPO))
    elif len(p.stdout)<1000: row['stdout']=p.stdout.decode(errors='replace')
    commands.append(row)
    if p.returncode: raise RuntimeError(row)
    return p.stdout


identity=call(['git','rev-parse','HEAD','HEAD^{tree}']).decode().splitlines()
assert identity[0]==CANDIDATE
call(['git','status','--short'],'status-before-report.txt')
call(['git','diff','--exit-code'])
call(['bash','-n','reports/cards/c1/tools/final_gate.sh'])
call(['git','diff','--check',BASE,CANDIDATE])
call(['git','diff','--exit-code',BASE,CANDIDATE,'--','engine-cards',
      'reports/cards/c1/tools/probe_snapshots.py','reports/cards/c1/tools/probe_snapshot_followup.py'])
full=call(['git','diff','--binary',BASE,CANDIDATE],'complete-reviewed.delta')
focused=call(['git','diff','--binary',FOCUSED,CANDIDATE],'focused-reviewed.delta')
listing=call(['/usr/bin/git','--no-replace-objects','ls-tree','-r','-z',CANDIDATE],'git-full-tree.bin')
for prefix,artifact in [('engine-cards','git-engine-tree.bin'),('reports/cards/c1/tools','git-tools-tree.bin')]:
    call(['/usr/bin/git','--no-replace-objects','ls-tree','-r','-z',CANDIDATE,'--',prefix],artifact)
changed=call(['git','diff','--name-only',BASE,CANDIDATE]).decode().splitlines()
hashes={}
for name in changed:
    data=call(['git','show',f'{CANDIDATE}:{name}'])
    assert (REPO/name).read_bytes()==data,name
    hashes[name]=sha(data)
tools={p.name:sha(p.read_bytes()) for p in (REPO/'reports/cards/c1/tools').iterdir()
       if p.name in ('final_gate.py','final_gate.sh','final_gate_contract.py','gate_worker.py',
                     'gate_fixtures.py','gate_roots.py','gate_compare.py','test_final_gate_contract.py')}
readpaths=[
    REPO/'reports/cards/c1/PROGRESS.md',REPO/'reports/cards/c1/FINAL-GATE-PLAN.md',
    REPO/'reports/cards/c1/RESULTS.md',REPO/'reports/cards/c1/SNAPSHOT-DIAGNOSTICS.md',
    REPO/'reports/cards/c1/tools/probe_snapshots.py',REPO/'reports/cards/c1/tools/probe_snapshot_followup.py',
    REPO/'engine-cards/differential.py',REPO/'engine-cards/py/src/clasher/paths.py',
    REPO/'engine-cards/c56_controller.py',REPO/'engine-cards/quickwin_resources.py',
    REPO/'reports/strategy_council_20260928/engine-speed/es_common.py',
    REPO/'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py',
    REPO/'reports/bot/learned-opponent/native-total-tools/parity_fixtures.py',
    REPO/'reports/bot/learned-opponent/native-total-tools/parity_roots.py',
    REPO/'reports/bot/learned-opponent/native-total-tools/compare.py',
    Path('/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-final-tools-r1.md')]
bot=Path('/mpac/sdicks02/repos/clasher-bot')
readpaths += [bot/x for x in ('bot/exit/cpu_job.sh','bot/exit/cpu_room.sh','bot/fidelity/fixture.py',
    'bot/fidelity/rs_parity.py','bot/players/runtime.py','bot/live/native_parity.py','bot/search/lopp_fast.py')]
old=REPO/'reports/cards/c1/reviews/r3-independent'
old_receipt=json.loads((old/'receipt.json').read_text())
preserved={}
for name,expected in old_receipt['artifacts'].items():
    observed=sha((old/name).read_bytes()); assert observed==expected,name
    preserved[str((old/name).relative_to(REPO))]=observed
for name in ('tools/peek.py','tools/snapcmp_probe.py'):
    p=REPO/'reports/cards/c1'/name
    preserved[str(p.relative_to(REPO))]=sha(p.read_bytes())
flag_env=dict(PATH='/usr/bin:/bin',PYTHONHASHSEED='0')
probe='import sys; print(sys.flags.hash_randomization, sys.flags.safe_path, sys.flags.no_site, sys.flags.no_user_site)'
for flags,expected in [(['-P','-s','-S','-B'],b'0 True 1 1\n'),(['-I','-S','-B'],b'1 True 1 1\n')]:
    assert call([PY,*flags,'-c',probe],env=flag_env)==expected
call(['git','rev-parse','HEAD','HEAD^{tree}'])
assert (REPO/'.git').exists()
test_history=[
    dict(command='TMPDIR='+str(HERE)+' '+PY+' -I -S -B reports/cards/c1/tools/test_final_gate_contract.py > reports/cards/c1/reviews/r4-independent/submitted-tests.log 2>&1',
         exit_code=0,groups=16,source_sha256=tools['test_final_gate_contract.py'],log='submitted-tests.log'),
    dict(command='TMPDIR='+str(HERE)+' '+PY+' -I -S -B reports/cards/c1/reviews/r4-independent/independent_checks.py > reports/cards/c1/reviews/r4-independent/independent-tests.log 2>&1',
         exit_code=1,groups=16,passed=15,errors=1,source='independent_checks-first-attempt.py',log='independent-tests-first-attempt.log',
         error='Review harness omitted SIGKILL in inert signal namespace; timeout control errored. Production source untouched. First source/log/reproduction preserved.'),
    dict(command='TMPDIR='+str(HERE)+' '+PY+' -I -S -B reports/cards/c1/reviews/r4-independent/independent_checks.py > reports/cards/c1/reviews/r4-independent/independent-tests.log 2>&1',
         exit_code=0,groups=16,source='independent_checks.py',log='independent-tests.log',
         caveat='One group deliberately reproduces R4-1; test success is not launcher approval.')]
artifact_hashes={p.name:sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file() and p.name not in ('record-review.log',)}
receipt=dict(candidate=CANDIDATE,candidate_tree=identity[1],base=BASE,focused_base=FOCUSED,
    full_delta_sha256=sha(full),focused_delta_sha256=sha(focused),git_full_tree_sha256=sha(listing),
    git_full_tree_entries=listing.count(b'\0'),candidate_delta_file_sha256=hashes,tool_sha256=tools,
    readpath_sha256={str(p):sha(p.read_bytes()) for p in readpaths},preserved_r3_and_untracked_sha256=preserved,
    commands=commands,test_history=test_history,artifacts=artifact_hashes,
    exploratory_read_errors=[dict(exit_code=2,reason='rg searched nonexistent bot/players/fair_player.py and bot reports/perf-audit/quickwins/quickwin_resources.py. Correct readpaths found with rg --files: engine-speed/stage5/fair_player.py, engine-cards/quickwin_resources.py. Only reads, no source run.')],
    scope='LOCAL ONLY. Read-only Git/hash/source/AST, pure contract, synthetic files under r4-independent, stdlib flag subprocess only. Driver Popen, killpg, signal installation/masks all inert/mocked. No actual driver main/run_gate/worker/helper/launcher/staging/host script, engine/native imports, simulation/build/remote/emulator/deploy/pin operation, delegates, commit/push, or other-worktree writes. Old defect-expecting review scripts read as history only, never rerun.')
with (HERE/'receipt.json').open('x') as f: json.dump(receipt,f,indent=2,sort_keys=True)
with (HERE/'reviewed-hashes.md').open('x') as f:
    f.write(f'Candidate `{CANDIDATE}`, tree `{identity[1]}`.\n\n')
    for name,value in hashes.items(): f.write(f'- `{name}`: `{value}`\n')
print(json.dumps(dict(candidate=CANDIDATE,tree=identity[1],delta_files=len(hashes),commands=len(commands),
    full_delta_sha256=sha(full),focused_delta_sha256=sha(focused),tool_hashes=tools,preserved_r3=True),indent=2))
