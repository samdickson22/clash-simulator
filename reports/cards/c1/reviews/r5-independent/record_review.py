"""Collect exact r5 identities and bounded local command/exit/scope receipts."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CANDIDATE='97171f531a31f9663f74ff95093d58053125860d'
BASE='476a747f75569040f9b137d0991691c95e6f1b29'
FOCUS='c7de06ea5a6171b4490682a7bb1be9baa825a2b4'
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
receipt=dict(candidate=CANDIDATE,base=BASE,focus=FOCUS,cwd=str(ROOT),commands=[],
    scope='LOCAL ONLY source/Git/hash/AST/pure/mock/filesystem/stdlib flags; no actual main/run_gate/worker/helper/launcher/staging/host scripts, real OS signals/masks, engine/native import, simulation/build/remote/emulator/deploy/pin; no children, production edit, commit, push, other-worktree writes. Historical defect-expecting scripts never executed.')

def sha(data):return hashlib.sha256(data).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def run(argv,name,env=None):
    start=now();p=subprocess.run(argv,cwd=ROOT,env=env,capture_output=True)
    stdout=HERE/(name+'.stdout');stderr=HERE/(name+'.stderr')
    stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
    receipt['commands'].append(dict(argv=argv,cwd=str(ROOT),environment_overrides={} if env is None else {k:env[k] for k in ('TMPDIR',) if k in env},started_utc=start,ended_utc=now(),exit_code=p.returncode,
        stdout=str(stdout.relative_to(ROOT)),stdout_sha256=sha(p.stdout),stderr=str(stderr.relative_to(ROOT)),stderr_sha256=sha(p.stderr)))
    if p.returncode:raise RuntimeError(f'command failed {name}: {p.returncode}; see preserved output')
    return p.stdout

def existing_artifacts():
    paths=[p for p in (ROOT/'reports/cards/c1/reviews').rglob('*') if p.is_file() and HERE not in p.parents and p.name!='FINAL-TOOLS-r5.md']
    paths += [ROOT/'reports/cards/c1/tools'/n for n in ('peek.py','snapcmp_probe.py')]
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)}

receipt['started_utc']=now()
preserved=existing_artifacts();receipt['preserved_before']=preserved
try:
    receipt['head']=run(['/usr/bin/git','rev-parse','HEAD'],'head').decode().strip()
    assert receipt['head']==CANDIDATE
    receipt['tree']=run(['/usr/bin/git','rev-parse',CANDIDATE+'^{tree}'],'tree').decode().strip()
    run(['/usr/bin/git','status','--short'],'status-before')
    changed=run(['/usr/bin/git','diff','--name-only',BASE,CANDIDATE],'changed-files').decode().splitlines()
    hashes={}
    for i,path in enumerate(changed):
        data=run(['/usr/bin/git','show',CANDIDATE+':'+path],f'candidate-file-{i:02d}')
        assert (ROOT/path).read_bytes()==data,path
        hashes[path]=sha(data)
    receipt['candidate_delta_file_sha256']=hashes
    for name,base in [('complete-reviewed.delta',BASE),('focused-reviewed.delta',FOCUS)]:
        data=run(['/usr/bin/git','diff','--binary',base,CANDIDATE],name)
        receipt[name+'_sha256']=sha(data)
    for name,prefix in [('git-full-tree.bin',''),('git-engine-tree.bin','engine-cards'),('git-tools-tree.bin','reports/cards/c1/tools')]:
        argv=['/usr/bin/git','--no-replace-objects','ls-tree','-r','-z',CANDIDATE]+(['--',prefix] if prefix else [])
        data=run(argv,name);receipt[name+'_sha256']=sha(data)
    run(['/usr/bin/git','diff','--check',BASE,CANDIDATE],'diff-check')
    run(['/usr/bin/git','diff','--exit-code',BASE,CANDIDATE,'--','engine-cards','reports/cards/c1/tools/probe_snapshots.py','reports/cards/c1/tools/probe_snapshot_followup.py'],'protected-no-delta')
    run(['/bin/bash','-n','reports/cards/c1/tools/final_gate.sh'],'bash-syntax')
    receipt['ast_files']=[]
    for p in sorted((ROOT/'reports/cards/c1/tools').glob('*.py')):
        if p.name in ('final_gate.py','final_gate_contract.py','gate_worker.py','gate_fixtures.py','gate_roots.py','gate_compare.py','test_final_gate_contract.py'):
            ast.parse(p.read_bytes(),filename=str(p));receipt['ast_files'].append(str(p.relative_to(ROOT)))
    readpaths=[ROOT/'reports/cards/c1/tools'/n for n in ('probe_snapshots.py','probe_snapshot_followup.py')]
    readpaths += [ROOT/p for p in ('engine-cards/differential.py','engine-cards/quickwin_resources.py','engine-cards/c56_controller.py','engine-cards/py/src/clasher/paths.py','reports/strategy_council_20260928/engine-speed/es_common.py','reports/strategy_council_20260928/engine-speed/stage5/fair_player.py')]
    bot=Path('/mpac/sdicks02/repos/clasher-bot')
    readpaths += [bot/p for p in ('bot/fidelity/fixture.py','bot/fidelity/rs_parity.py','bot/players/runtime.py','bot/live/native_parity.py','bot/search/lopp_fast.py','bot/exit/cpu_job.sh','bot/exit/cpu_room.sh')]
    readpaths += [Path('/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-final-tools-r1.md')]
    receipt['readpath_sha256']={str(p):sha(p.read_bytes()) for p in readpaths}
    env=dict(os.environ,TMPDIR=str(HERE))
    run([PY,'-I','-S','-B','reports/cards/c1/tools/test_final_gate_contract.py'],'submitted-tests',env)
    run([PY,'-I','-S','-B','reports/cards/c1/reviews/r5-independent/independent_checks.py'],'independent-tests',env)
    flag_env=dict(PATH='/usr/bin:/bin',PYTHONHASHSEED='0')
    for name,flags in [('worker-flags',['-P','-s','-S','-B']),('control-flags',['-I','-S','-B'])]:
        run([PY,*flags,'-c','import sys; print(sys.flags.hash_randomization, sys.flags.safe_path, sys.flags.no_site, sys.flags.no_user_site)'],name,flag_env)
        receipt['commands'][-1]['exact_environment']=flag_env
    receipt['preserved_after']=existing_artifacts()
    assert receipt['preserved_after']==preserved,'historical artifacts changed'
    assert run(['/usr/bin/git','rev-parse','HEAD'],'final-head').decode().strip()==CANDIDATE
    run(['/usr/bin/git','status','--short'],'status-after')
    receipt['code_sha256']={p.split('/')[-1]:h for p,h in hashes.items() if p.startswith('reports/cards/c1/tools/')}
    (HERE/'reviewed-hashes.md').write_text('\n'.join(f'- `{p}`: `{h}`' for p,h in hashes.items())+'\n')
    receipt['result']='all recorded checks passed'
finally:
    receipt['ended_utc']=now()
    receipt['review_scripts_sha256']={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')}
    with (HERE/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True)
print(json.dumps(dict(candidate=CANDIDATE,commands=len(receipt['commands']),changed_files=len(changed),preserved_artifacts=len(preserved),result=receipt['result']),indent=2))
