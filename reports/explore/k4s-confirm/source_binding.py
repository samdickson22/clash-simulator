"""PREREG-K4S qualification source binding (Sol core r2 finding 9).

  build  (on a git checkout): writes t1-reference-expected.json from git ef4c073a: sha256 of every T1 file that
         export_staging_extras.sh stages, plus the committed reference receipts (reference-files.json).
  record --job J   (on the host, before the first battery): J/source-binding-start.json
  verify --job J   (after games and STOP test): recomputes, requires equality with the start record, and writes
                   J/source-binding-end.json.

Covers every file of the staged K4S overlay (repo/reports/explore/k4s-confirm, recursive) and the staged T1 reference
tree (repo/reports/explore/t1). The T1 tree must equal the expected manifest exactly: no missing or extra file.
Only plan.json may differ, and only by the job-path rebinding; it is compared after reversing that substitution.
The driver receipts of qualify_games.py must name the staged run.py/plan.json of their runtime, and every listed
game hash must match its file.
"""
import argparse, glob, hashlib, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T1_COMMIT = 'ef4c073a4c69e85aea0b6f9af9c1118ca8888a59'
T1_JOB = '/mpac/sdicks02/jobs/clasher/t1-20261010-r1'
EXPECTED = HERE/'t1-reference-expected.json'
REMOVED = ('receipts/', 'corpora/', 'verifier/', 'FROZEN-T1.json', 'seed-audit.json')
# Immutable qualified inputs (job-relative): native module, SD1/v1 checkpoints, calibration, 125-state corpus, pins.
INPUTS = ('native/clasher_core.abi3.so', 'inputs/R3a.pt', 'inputs/R3a-calibration.json', 'inputs/main02.pt',
          'corpus/states-ready.pkl', 'corpus/symmetric-screen-samples.json', 'runtime-pin.json', 'inherited-runtime-pin.json', 'staging.json')
# Battery/check/STOP artifacts bound by `verify` and re-checked by the receipt assembler.
ARTIFACTS = ('tests.log', 'k4s-qualification.json', 'qualification.json', 'belief-qualification.json', 'guard-support-qualification.json',
             'sd1-manifest-check.txt', 'qualification-source-before.json', 'qualification-source-binding.json', 'out/check-games.json',
             'out/stoptest.json')


def sha(b): return hashlib.sha256(b).hexdigest()


def tree(root):
    root = Path(root)
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def build():
    top = subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', '--show-toplevel'], text=True).strip()
    names = subprocess.check_output(['git', '-C', top, 'ls-tree', '-r', '--name-only', T1_COMMIT, 'reports/explore/t1/'], text=True).split()
    files = {}
    for n in names:
        rel = n[len('reports/explore/t1/'):]
        if rel.startswith(REMOVED) or (rel.endswith('.md') and '/' not in rel): continue
        files[rel] = sha(subprocess.check_output(['git', '-C', top, 'show', f'{T1_COMMIT}:{n}']))
    refs = json.loads((HERE/'reference-files.json').read_text())['files']
    for f in refs:
        if f['path'].startswith('reports/explore/t1/'): files[f['path'][len('reports/explore/t1/'):]] = f['sha256']
    EXPECTED.write_text(json.dumps(dict(schema='clasher.k4s.t1-reference-expected.v1', t1_commit=T1_COMMIT,
        rule='plan.json is compared after replacing the staged job path with ' + T1_JOB, files=files,
        other_reference_files={f['path']: f['sha256'] for f in refs if not f['path'].startswith('reports/explore/t1/')}), indent=2)+'\n')
    print(len(files))


def snapshot(job):
    repo = Path(job)/'repo'
    expected = json.loads((repo/'reports/explore/k4s-confirm/t1-reference-expected.json').read_text())
    t1 = tree(repo/'reports/explore/t1')
    plan_raw = (repo/'reports/explore/t1/plan.json').read_bytes().decode()
    errors = sorted(set(t1) ^ set(expected['files']))
    for rel, h in expected['files'].items():
        got = sha(plan_raw.replace(str(job), T1_JOB).encode()) if rel == 'plan.json' else t1.get(rel)
        if got != h: errors.append('t1 mismatch: '+rel)
    for p, h in expected['other_reference_files'].items():
        if sha((repo/p).read_bytes()) != h: errors.append('reference file: '+p)
    inputs = {n: sha((Path(job)/n).read_bytes()) for n in INPUTS}
    plan = json.loads((repo/'reports/explore/k4s-confirm/plan.json').read_text())
    pinned = {'native/clasher_core.abi3.so': plan['source_reference']['native_sha256'], 'inputs/R3a.pt': plan['student']['checkpoint_sha256'],
              'inputs/R3a-calibration.json': plan['student']['calibration_sha256'], 'inputs/main02.pt': plan['policy']['checkpoint_sha256']}
    errors += [f'input pin: {n}' for n, h in pinned.items() if inputs[n] != h]
    pin = json.loads((Path(job)/'runtime-pin.json').read_text())
    errors += [f'runtime-pin input: {n}' for n, h in pin['inputs'].items() if inputs.get(n) != h]
    return dict(k4s=tree(repo/'reports/explore/k4s-confirm'), t1=t1, t1_expected_sha256=sha(json.dumps(expected, sort_keys=True).encode()),
                inputs=inputs, t1_matches_ef4c073a=not errors, t1_errors=errors)


def verify_receipts(job, snap):
    """Exactly the canonical qual_tasks receipts, each naming the staged runtime bytes of its side, with exactly its
    games and their hashes (Sol core r3 finding 15)."""
    sys.path.insert(0, str(Path(job)/'repo/reports/explore/k4s-confirm'))
    from qual_tasks import validate_receipts, TASKS
    G = Path(job)/'out/games'
    errors, bound = validate_receipts(G, lambda p: json.loads(Path(p).read_text()), lambda p: sha(Path(p).read_bytes()))
    n = 0
    for p in sorted(glob.glob(str(G/'*'/'receipt-*.json'))):
        r = json.loads(Path(p).read_text()); n += 1
        side = 'k4s' if r.get('runtime') == 'k4s' else 't1'
        if r.get('run_py_sha256') != snap[side]['run.py'] or r.get('plan_sha256') != snap[side]['plan.json']: errors.append('runtime identity: '+p)
    if n != len(TASKS): errors.append(f'receipts {n} != {len(TASKS)}')
    return n, errors, {f'{g}/{f}': h for (g, f), h in sorted(bound.items())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['build', 'record', 'verify']); ap.add_argument('--job', type=Path)
    a = ap.parse_args()
    if a.mode == 'build': return build()
    snap = snapshot(a.job)
    if a.mode == 'record':
        (a.job/'source-binding-start.json').write_text(json.dumps(snap, indent=2)+'\n')
        ok = snap['t1_matches_ef4c073a']
    else:
        start = json.loads((a.job/'source-binding-start.json').read_text())
        n, rerr, bound = verify_receipts(a.job, snap)
        end = dict(snap, unchanged_since_start=start == snap, driver_receipts=n, receipt_errors=rerr, bound_game_sha256=bound,
                   artifact_sha256={c: sha((a.job/c).read_bytes()) for c in ARTIFACTS},
                   start_sha256=sha((a.job/'source-binding-start.json').read_bytes()))
        ok = end['unchanged_since_start'] and snap['t1_matches_ef4c073a'] and n == 11 and not rerr
        end['passed'] = ok
        (a.job/'source-binding-end.json').write_text(json.dumps(end, indent=2)+'\n')
    print(json.dumps(dict(mode=a.mode, ok=ok, t1_errors=snap['t1_errors'][:5])))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
