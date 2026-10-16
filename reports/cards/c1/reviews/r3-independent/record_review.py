"""Read-only Git/source checks plus serial stdlib flag probes; writes receipts here only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BASE = '476a747f75569040f9b137d0991691c95e6f1b29'
OLD = 'c45854febf93352284dd9f76b02651d989d906a7'
CANDIDATE = '4bfae6b0844b4620d9482cc996a74bf86f1a1887'
PYTHON = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
def sha(data): return hashlib.sha256(data).hexdigest()
commands = []
def run(args, output=None, env=None):
    start = datetime.now(timezone.utc).isoformat()
    p = subprocess.run(args, cwd=REPO, env=env, capture_output=True)
    item = dict(argv=args, cwd=str(REPO), started_utc=start,
                ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=p.returncode,
                stdout_sha256=sha(p.stdout), stdout_bytes=len(p.stdout),
                stderr=p.stderr.decode(errors='replace'))
    if env is not None: item['explicit_environment'] = env
    if output:
        (HERE/output).write_bytes(p.stdout); item['stdout_artifact'] = output
    elif len(p.stdout) < 4000: item['stdout'] = p.stdout.decode(errors='replace')
    commands.append(item)
    return p

head = run(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}']).stdout.decode().splitlines()
assert head[0] == CANDIDATE
run(['git', 'status', '--short'], 'status-before-report.txt')
files = run(['git', 'diff', '--name-only', BASE, CANDIDATE]).stdout.decode().splitlines()
hashes = {}
for name in files:
    data = run(['git', 'show', f'{CANDIDATE}:{name}']).stdout
    assert data == (REPO/name).read_bytes(), name
    hashes[name] = sha(data)
full = run(['git', 'diff', '--binary', BASE, CANDIDATE], 'complete-reviewed.delta').stdout
focused = run(['git', 'diff', '--binary', OLD, CANDIDATE], 'focused-reviewed.delta').stdout
run(['bash', '-n', 'reports/cards/c1/tools/final_gate.sh'])
run(['git', 'diff', '--check', BASE, CANDIDATE])
run(['git', 'diff', '--exit-code', BASE, CANDIDATE, '--', 'engine-cards',
     'reports/cards/c1/tools/probe_snapshots.py', 'reports/cards/c1/tools/probe_snapshot_followup.py'])
for prefix in (None, 'reports/cards/c1/tools'):
    cmd = ['/usr/bin/git', '--no-replace-objects', 'ls-tree', '-r', '-z', CANDIDATE]
    if prefix: cmd += ['--', prefix]
    result = run(cmd, 'git-prefixed-tree.bin' if prefix else 'git-full-tree.bin')
    assert result.returncode == 0 and result.stdout
    commands[-1]['entries'] = result.stdout.count(b'\0')
flag_code = 'import sys; print(sys.flags.hash_randomization, sys.flags.safe_path, sys.flags.no_site, sys.flags.no_user_site)'
for flags in (['-P', '-s', '-S', '-B'], ['-I', '-S', '-B']):
    run([PYTHON, *flags, '-c', flag_code], env=dict(PATH='/usr/bin:/bin', PYTHONHASHSEED='0'))
paths = [REPO/'reports/cards/c1/tools'/n for n in ('probe_snapshots.py', 'probe_snapshot_followup.py', 'peek.py', 'snapcmp_probe.py')]
paths += [Path('/mpac/sdicks02/repos/clasher-bot')/n for n in
          ('bot/exit/cpu_job.sh', 'bot/exit/cpu_room.sh', 'bot/players/runtime.py', 'bot/fidelity/fixture.py',
           'bot/fidelity/rs_parity.py', 'bot/live/native_parity.py', 'bot/search/lopp_fast.py')]
paths += [REPO/n for n in ('engine-cards/differential.py', 'engine-cards/py/src/clasher/paths.py',
          'reports/strategy_council_20260928/engine-speed/es_common.py',
          'reports/strategy_council_20260928/engine-speed/stage5/fair_player.py')]
paths += [Path('/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-final-tools-r1.md')]
readpaths = {str(p): sha(p.read_bytes()) for p in paths}
temp = str(HERE)
tests = [dict(command=f'TMPDIR={temp} {PYTHON} -I -S -B reports/cards/c1/tools/test_final_gate_contract.py > reports/cards/c1/reviews/r3-independent/submitted-tests.log 2>&1',
              exit_code=0, result='13 submitted groups PASS; includes real stdlib-only interpreter flag probe'),
         dict(command=f'TMPDIR={temp} {PYTHON} -I -S -B reports/cards/c1/reviews/r3-independent/independent_checks.py > reports/cards/c1/reviews/r3-independent/independent-tests.log 2>&1',
              exit_code=1, artifact_at_attempt='independent_checks-first-attempt.py / independent-tests-first-attempt.log',
              result='9 groups passed; filesystem test harness expected FileExistsError but inherited setgid bit caused earlier correct mode rejection; no production defect'),
         dict(command=f'TMPDIR={temp} {PYTHON} -I -S -B reports/cards/c1/reviews/r3-independent/independent_checks.py > reports/cards/c1/reviews/r3-independent/independent-tests.log 2>&1',
              exit_code=0, result='10 independent groups PASS after explicitly chmod700 scratch directory; one group intentionally reproduces the new interrupted-wait finding')]
receipt = dict(candidate=CANDIDATE, candidate_tree=head[1], base=BASE, focused_base=OLD,
               full_delta_sha256=sha(full), focused_delta_sha256=sha(focused),
               candidate_delta_file_sha256=hashes, readpath_and_preserved_sha256=readpaths,
               verification=tests, readonly_commands=commands,
               scope='Local serial read-only source/Git/hash/AST, pure contract validators, mocked bootstrap/publication/wait helpers, scratch filesystem and stdlib-only interpreter flag probes. No driver main/run_gate, actual worker/helper/launcher/staging/host script, engine/native import, simulation, build, remote, emulator, deployment, pin action, delegation, production edit, commit or push.',
               artifacts={p.name: sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file()})
with (HERE/'receipt.json').open('x') as f:
    json.dump(receipt, f, indent=2, sort_keys=True); f.write('\n')
with (HERE/'reviewed-hashes.md').open('x') as f:
    for name, h in hashes.items(): f.write(f'- `{name}`: `{h}`.\n')
print(json.dumps(dict(candidate=CANDIDATE, tree=head[1], full_delta_sha256=sha(full),
                     focused_delta_sha256=sha(focused), commands=len(commands),
                     command_exits=[x['exit_code'] for x in commands], files=len(files)), indent=2))
