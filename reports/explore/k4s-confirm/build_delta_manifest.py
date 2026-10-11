"""Build DELTA-MANIFEST.json: every K4S file classified against T1 ef4c073a, and the eight r3 §4.1 deltas.

  python3 reports/explore/k4s-confirm/build_delta_manifest.py      # from a git checkout (reads ef4c073a with git show)
  python3 reports/explore/k4s-confirm/rebind.py verify              # independent re-check of the classes
"""
import hashlib, json, subprocess
from pathlib import Path
from rebind import HERE, ROOT, T1_COMMIT, T1_DIR, rebind

DELTAS = {
    1: ('cell table: 200/180/160/140/120 ms arms, speed cell, inference_scale = 1/c', ['plan.json']),
    2: ('poll-charge hook: (1/c - 1) x poll_seconds slept inside the timer in every arm (X4S-2 make_charger semantics)', ['charge.py', 'test_charge.py', 'run.py']),
    3: ('K4S kernel: SD1 seat poll (one cached forward), SD1 top-8 coarse order, full cutoff default; anchor_x stats', ['sdefault.py', 'test_sdefault.py', 'anchor_x.py', 'sd1_policy.py', 'sd1_manifest.py', 'SD1-MANIFEST.json', 'run.py']),
    4: ('10-arm schedule: rotation rho, subsample K4-140/K4-120, 10:3 dispatch, 8/10-game blocks downstream', ['schedule.py', 'test_schedule.py', 'replace.py', 'health.py', 'smoke_pass.py']),
    5: ('new populations and seeds: K4S bank 2^52+[6.18e9,6.28e9), SD1 inputs, staging from the inherited S1 runtime', ['plan.json', 'audit_seeds.py', 'seed-audit.json', 'stage_k4s.py', 'reference-files.json', 'qualify.py']),
    6: ('reducer: fixed sequence H1-H7, veto, usable cells, validity; release barrier with r3 §4.5 items; verifier by another author', ['reduce.py', 'test_reduce.py', 'synthetic.py', 'barrier.py', 'test_barrier.py', 'verifier/verify_k4s.py', 'verifier/test_verify_k4s.py']),
    7: ('per-decision and per-game fields (r3 §3.6)', ['run.py', 'check_games.py']),
    8: ('END reference cells (a)-(c) incl. SD1/v1 poll-span timing, pooling to the Mac contract', ['end_reference.py', 'end_pool.py', 'test_end_reference.py', 'END-RUNBOOK.md']),
}
SUPPORT = {
    'qualify_k4s.py': 'qualification: 125 fixed states (K4 == T1 anchor, K4 == K4S no deadline, SD1Policy == CachedPolicy, S-default cases)',
    'qualify_games.py': 'qualification: game-level driver (T1 vs K4S command hashes, charge share, zero budget)',
    'qualify.sh': 'qualification sequence (T1 batteries + K4S)',
    'rebind.py': 'mechanical T1 -> K4S path rebinding and its proof',
    'build_delta_manifest.py': 'this manifest builder',
    'qualify_games.sh': 'qualification: 11-slot game-level launcher (no-deadline, injected virtual clock, charged, zero) + check',
    'run_qualification.sh': 'qualification: per-host driver (pin, batteries, games, STOP test, receipt)',
    'stop_test.py': 'qualification: owned-STOP drain test (<= 5 min, 0 owned processes)',
    'make_qualification_receipt.py': 'qualification: per-host receipt assembler (outcome-blind)',
    'export_staging_extras.sh': 'qualification: T1 reference runtime + committed reference receipts, from git',
    'test_op7_boottime.py': 'qualification: host-independent run of a host-uptime-dependent T1 OP-7 test (T1 bytes unchanged)',
    'make_freeze_skeleton.py': 'freeze-record skeleton generator (draft only)',
    'stage_k4s.py': 'staging from the inherited S1 runtime pin f81f3655',
}
DOCS = ('.md',)


def sha(b): return hashlib.sha256(b).hexdigest()


def t1(name):
    r = subprocess.run(['git', '-C', str(ROOT), 'show', f'{T1_COMMIT}:{T1_DIR}/{name}'], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def main():
    files = {}
    tags = {}
    for k, (_, names) in DELTAS.items():
        for n in names: tags.setdefault(n, []).append(k)
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name == 'DELTA-MANIFEST.json': continue
        name = str(p.relative_to(HERE)); mine = p.read_bytes(); base = t1(name)
        if base is None:
            cls = 'new'
        elif mine == base:
            cls = 'identical'
        elif mine == rebind(base):
            cls = 'rebound'
        else:
            cls = 'delta'
        row = dict(**{'class': cls}, k4s_sha256=sha(mine))
        if base is not None: row['t1_sha256'] = sha(base)
        if name in tags: row['deltas'] = tags[name]
        if name in SUPPORT: row['support'] = SUPPORT[name]
        if p.suffix in DOCS and cls == 'new': row['role'] = 'document (not executed)'
        if name.startswith('mac/'): row['role'] = 'K4S Mac measurement (N2; separate from TIERS measure_tiers.py)'
        if name.startswith('inherited/'): row['role'] = 'T1 inherited provenance copy (not executed)'
        files[name] = row
    for name, row in files.items():
        if row['class'] == 'delta' and 'deltas' not in row and 'support' not in row:
            raise SystemExit(f'undeclared delta file: {name}')
    not_copied = sorted(set(subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', T1_COMMIT, T1_DIR + '/'], text=True).split())
                        - {f'{T1_DIR}/{n}' for n in files})
    m = dict(schema='clasher.k4s.delta-manifest.v1', prereg='reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md',
             prereg_sha256='9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a',
             t1_runtime_commit=T1_COMMIT, t1_runtime_branch='origin/worker/t1-op7-apt-20261010 (not an ancestor of main)',
             rebinding_rules='rebind.py RULES (T1_JOB, job path, FROZEN-T1.json, reports/explore/t1; committed T1 receipt prefix protected)',
             deltas={str(k): dict(description=d, files=n) for k, (d, n) in DELTAS.items()},
             files=files, t1_files_not_copied=not_copied,
             counts={c: sum(r['class'] == c for r in files.values()) for c in ('identical', 'rebound', 'delta', 'new')},
             guard_code_note='OP-1..OP-7 guard modules (host_audit, ssh_budget, ssh_transport, apt_budget, cpu_accounting, system_bus, '
                             'idle_services, owned_supervisor, perception_confirmation, parent_source_seed, pin, mirror, supervise, ssh_sensitivity) '
                             'are identical or rebound-only; see their class rows.')
    (HERE/'DELTA-MANIFEST.json').write_text(json.dumps(m, indent=2)+'\n')
    print(json.dumps(m['counts']))


if __name__ == '__main__':
    main()
