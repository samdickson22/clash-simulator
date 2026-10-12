"""X4S-4 qualification (exploration, NEVER ADOPTABLE). Runs on 127x01 before any collection. r2 after Sol r1 (F3, F10, F12).

  frozen    --corpus DIR --threads T --out R.json
      label.score_state reproduces the frozen screen8 reference action/candidates/scores on all 125
      states (the reports/explore/x4s/qualify.py equality), and the root is not mutated.
  hashes    --run-phase DIR --collect-phase DIR --config plan-qual-capture.json --out R.json
      Inventory (Sol F12): both phases ran the qualification bank, indices 0-7, both qualification arms, with this
      config (1,000 s budgets, capture.all/verify_belief/fair_check on), and every one of the 16 cases has a terminal,
      SHA-matching block proof in both phases. Then: every game's command_sha256 is identical between the unchanged
      x4s3/run.py and x4s4/collect.py (capture non-perturbation); every collect game has a capture file whose SHA
      matches its summary; features/public equality and empty input pending hold; nothing is unsampled and the
      per-reason counts sum to the game's decisions; the live belief is unchanged by every capture; the
      fair-information payload is byte-identical under every permutation (C9) AND the permutation actually moved
      cards (Sol F3): every game has >= 1 perturbed decision, and >= 50% of its early-game (tick < 600) checks were
      perturbed.
  parity    --phases DIR... --min-games N [--watch SECONDS] --out R.json
      Deadline-mode parity (PLAN r3 C7b; non-outcome timing metadata only): per arm (K4S-120 and S-200 both
      required, each with >= N block-proved games), the collection games' cutoff %, student-default % and overrun %
      lie within +-2 pp of X4S-3's R3a (K4S-120 64.2 / 22.3 / 0.16; S-200 75.3 / 0.0 / 0.14). With --watch it
      re-checks every SECONDS while the collection runs: once any arm with >= N games is outside the band it writes
      <job>/receipts/PARITY-PAUSE-<utc>.json, creates <job>/STOP (the collection supervisor, labeler and O_W
      wrapper all stop on it) and exits 1 (Sol F12). The coordinator's decision to continue or disclose must be an
      explicit <job>/data/PARITY-EXCEPTION.json (label.py checks it); the hard stop clock is unchanged.
      label.py requires a passing receipt (check 'parity', 'phases' = the resolved phase paths).
  roundtrip --phases DIR... --threads T --out R.json
      On EVERY capture of the smoke collection phases (100%, Sol F12; the phases must cover indices 0-7 x
      K4S-120/S-200 with block proofs and capture files): the C8 triple is present and hashes, pending is empty, the
      rebuilt root digest equals the captured digest, and labeling twice gives identical (action, candidates, scores).
  trainer   --packed DIR --assets FILE --out R.json      (clasher-gpu python, fit PYTHONPATH)
      A packed smoke batch loads in exit_r3.student.RootTeacherStore, every row is a root, and a
      64-row batch yields valid teacher targets.
Receipts are confined below <job>/qual/ or <job>/receipts/ and created with O_EXCL. Any failed check exits 1.
"""
import argparse, hashlib, json, os, pickle, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confine                                   # noqa: E402

QUAL_BASE, SMOKE_BASE = 4503606337370496, 4503606327370496
QUAL_ARMS, COLLECT_ARMS = ('K4S-long', 'S-long'), ('K4S-120', 'S-200')
INDICES = list(range(8))
EARLY_PERTURBED_MIN = 0.5
X4S3_R3A = {'K4S-120': dict(cutoff=64.2, student_default=22.3, overrun=0.16), 'S-200': dict(cutoff=75.3, student_default=0.0, overrun=0.14)}


class QualError(Exception):
    pass


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_receipt(path, obj, roles=('qual', 'receipts')):
    path = confine.writable(str(path), roles=roles, must_not_exist=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'w') as f:
        f.write(json.dumps(obj, indent=2)+'\n'); f.flush(); os.fsync(f.fileno())
    return path


def init_label(threads):
    sys.path.insert(0, str(HERE.parent/'x4s3'))
    import run, label
    native = run.initialize()
    import torch; torch.set_num_threads(1)
    label.run, label.THREADS = run, threads
    return run, label, native


def frozen(a):
    run, label, native = init_label(a.threads)
    rows = pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs = {r['id']: r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text())
            if r['variant'] == 'screen8' and r['repeat'] == 0}
    bad = []
    for row in rows:
        action, cands, scores = label.score_state(row['info'], row['opponent'], row['root_rng_state'],
                                                  row['candidate_rng_state'], row['seed'], row['root_digest'])
        ref = refs[row['id']]
        if not (action == ref['action'] and cands == ref['candidates'] and scores == ref['scores']):
            bad.append(row['id'])
    return dict(states=len(rows), equal=len(rows)-len(bad), mismatches=bad, threads=a.threads, native=native,
                passed=len(rows) == 125 and not bad)


def phase_inventory(phase, rng, base, arms):
    """Sol F12: the phase ran exactly indices 0-7 x arms of the named bank, each case with a terminal, SHA-matching
    block proof; returns {(index, arm): game path}."""
    phase = Path(phase)
    sched = json.loads((phase/'schedule.json').read_text())
    if sched['range'] != rng or sched['indices'] != INDICES: raise QualError(f'{phase}: range/indices must be {rng} 0-7')
    cases = {(c[0], c[2]) for c in sched['cases']}
    if cases != {(i, arm) for i in INDICES for arm in arms} or any(c[1] != base+c[0] for c in sched['cases']):
        raise QualError(f'{phase}: schedule must hold every index 0-7 x {arms} at bank base {base}')
    out = {}
    for i in INDICES:
        bp = phase/'blocks'/f'{i:04d}.json'
        if not bp.is_file(): raise QualError(f'{phase}: index {i} has no block proof')
        proof = json.loads(bp.read_text())
        if proof['index'] != i or proof['seed'] != base+i or sorted(proof['order']) != sorted(arms):
            raise QualError(f'{phase}: block proof {i} identity')
        for arm in arms:
            g = phase/'games'/f'sim-{i:04d}-d27-{arm}.json'
            if not g.is_file() or proof['games'].get(g.name) != sha_file(g): raise QualError(f'{phase}: {g.name} missing or differs from its block proof')
            out[(i, arm)] = g
    return out, sched


def check_config(path):
    cfg = json.loads(Path(path).read_text())
    ok = (sorted(cfg['arms']) == sorted(QUAL_ARMS) and all(cfg['arms'][k]['deadline_seconds'] == 1000.0 for k in QUAL_ARMS)
          and cfg['seed_ranges']['qualification'] == dict(base=QUAL_BASE, count=8)
          and all(cfg['capture'].get(k) is True for k in ('all', 'verify_belief', 'fair_check')))
    if not ok: raise QualError('qualification config must be the 1,000 s capture-all config with both checks on')
    return sha_file(path)


def hashes(a):
    cfg_sha = check_config(a.config)
    rgames, rsched = phase_inventory(a.run_phase, 'qualification', QUAL_BASE, QUAL_ARMS)
    cgames, csched = phase_inventory(a.collect_phase, 'qualification', QUAL_BASE, QUAL_ARMS)
    if not (rsched['config_sha256'] == csched['config_sha256'] == cfg_sha): raise QualError('both phases must run the given config')
    same_sched = rsched['cases'] == csched['cases']
    rows, ok = [], same_sched and len(rgames) == len(cgames) == 16
    for key in sorted(rgames):
        gr, gc = json.loads(rgames[key].read_text()), json.loads(cgames[key].read_text())
        name = cgames[key].name
        hr, hc = gr['search_ab']['command_sha256'], gc['search_ab']['command_sha256']
        pkl = Path(a.collect_phase)/'captures'/name.replace('.json', '.pkl')
        summ = json.loads(pkl.with_suffix('.json').read_text())
        sha_ok = sha_file(pkl) == summ['sha256']
        decisions = len(gc['search_ab']['deadline_stats'])
        counts = summ['counts']
        count_ok = (counts.get('not_sampled', 0) == 0 and sum(counts.values()) == decisions
                    and counts.get('captured', 0) == summ['captures'] > 0)
        chk = summ.get('checks', {})
        belief_ok = chk.get('belief_checked', 0) == summ['captures'] and chk.get('belief_unchanged', -1) == chk.get('belief_checked')
        fair_ok = chk.get('fair_checked', 0) == summ['captures'] and chk.get('fair_identical', -1) == chk.get('fair_checked')
        early = chk.get('fair_checked_early', 0)
        coverage_ok = (chk.get('fair_perturbed_decisions', 0) >= 1 and early >= 1
                       and chk.get('fair_perturbed_early', 0) >= EARLY_PERTURBED_MIN*early)
        row = dict(game=name, equal=hr == hc, capture_sha_ok=sha_ok, identity_ok=summ.get('identity_ok') is True
                   and summ['index'] == key[0] and summ['arm'] == key[1] and summ['seed'] == QUAL_BASE+key[0],
                   features_equal_all=summ['features_equal_all'], public_equal_all=summ['public_equal_all'],
                   pending_empty_all=summ['pending_empty_all'], captures=summ['captures'], decisions=decisions, counts=counts,
                   count_ok=count_ok, checks=chk, belief_unchanged=belief_ok, fair_invariant=fair_ok, fair_coverage=coverage_ok)
        ok &= all(row[k] is True for k in ('equal', 'capture_sha_ok', 'identity_ok', 'features_equal_all', 'public_equal_all',
                                           'pending_empty_all', 'count_ok', 'belief_unchanged', 'fair_invariant', 'fair_coverage'))
        rows.append(row)
    return dict(same_schedule=same_sched, config_sha256=cfg_sha, cases=len(rows), games=rows, passed=bool(ok))


def all_captures(phases, label):
    """Every capture of the smoke collection phases, which together must cover indices 0-7 x K4S-120/S-200."""
    caps, seen = [], set()
    for phase in phases:
        sched = json.loads((Path(phase)/'schedule.json').read_text())
        if sched['range'] != 'smoke': raise QualError(f'{phase}: round trip runs on the smoke collection')
        blocked = {int(p.stem) for p in (Path(phase)/'blocks').glob('*.json')}
        for c in sched['cases']:
            i, arm = c[0], c[2]
            if i not in blocked: raise QualError(f'{phase}: smoke case {i} {arm} not terminal')
            pkl = Path(phase)/'captures'/f'sim-{i:04d}-d27-{arm}.pkl'
            got, summary = label.load_captures(pkl)
            if summary['seed'] != SMOKE_BASE+i: raise QualError(f'{pkl}: seed outside the smoke bank')
            caps += got; seen.add((i, arm))
    if seen != {(i, arm) for i in INDICES for arm in COLLECT_ARMS}: raise QualError('smoke captures must cover 0-7 x K4S-120/S-200')
    return caps


def roundtrip_check(caps, score):
    """Pure check over every capture; score(*args) returns (action, candidates, scores) or raises LookupError."""
    mism, unequal, fields_missing = 0, 0, 0
    for cap in caps:
        triple = (cap.get('reserved_packet'), cap.get('opponent_elixir'), cap.get('pending'))
        fields_missing += not (triple[0] is not None and 'opponent_elixir' in cap and triple[2] == ()
                               and hashlib.sha256(pickle.dumps(triple, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest() == cap.get('c8_sha256'))
        args = (cap['info'], cap['opponent'], cap['root_rng_state'], cap['candidate_rng_state'], cap['seed'], cap['root_digest'])
        try:
            first = score(*args); second = score(*args)
        except LookupError:
            mism += 1; continue
        unequal += first != second
    return dict(checked=len(caps), digest_mismatches=mism, repeat_unequal=unequal, c8_fields_missing=fields_missing,
                passed=len(caps) > 0 and mism == 0 and unequal == 0 and fields_missing == 0)


def roundtrip(a):
    run, label, native = init_label(a.threads)
    res = roundtrip_check(all_captures(a.phases, label), label.score_state)
    return dict(res, threads=a.threads, native=native, coverage='100% of smoke captures')


def parity_once(phases, min_games):
    agg = {}
    for phase in phases:
        for p in sorted(Path(phase).glob('games/sim-*.json')):
            arm = p.stem.split('-d27-')[1]
            if not (Path(phase)/'blocks'/(p.name.split('-')[1]+'.json')).exists(): continue
            ds = json.loads(p.read_text())['search_ab']['deadline_stats']     # timing metadata only
            t = agg.setdefault(arm, dict(decisions=0, cutoff=0, student_default=0, overrun=0, games=0))
            t['games'] += 1; t['decisions'] += len(ds); t['cutoff'] += sum(bool(d['hit']) for d in ds)
            t['student_default'] += sum(bool(d.get('student_default')) for d in ds); t['overrun'] += sum(bool(d['wall_overrun']) for d in ds)
    rows = {}
    for arm, t in agg.items():
        if arm not in X4S3_R3A: raise QualError(f'unknown collection arm {arm}')
        pct = {k: 100*t[k]/max(1, t['decisions']) for k in ('cutoff', 'student_default', 'overrun')}
        ref = X4S3_R3A[arm]; within = {k: abs(pct[k]-ref[k]) <= 2.0 for k in pct}
        rows[arm] = dict(games=t['games'], decisions=t['decisions'], pct=pct, x4s3_r3a=ref, within_2pp=within,
                         evaluated=t['games'] >= min_games)
    enough = all(arm in rows and rows[arm]['evaluated'] for arm in X4S3_R3A)
    out_of_band = sorted(arm for arm, r in rows.items() if r['evaluated'] and not all(r['within_2pp'].values()))
    return dict(arms=rows, band_pp=2.0, min_games=min_games, both_arms_evaluated=enough, out_of_band=out_of_band,
                passed=bool(enough and not out_of_band))


def pause(job, res):
    """C7b: record the out-of-band reading and stop collection (STOP is honoured by every X4S-4 worker)."""
    rec = write_receipt(Path(job)/'receipts'/f"PARITY-PAUSE-{utc().replace(':', '')}.json",
                        dict(res, reason='C7b parity band exceeded; collection paused; the coordinator decides (explicit PARITY-EXCEPTION)'),
                        roles=('receipts',))
    stop = confine.writable(str(Path(job)/'STOP'), roles=('STOP',))
    if not os.path.lexists(stop):
        fd = os.open(stop, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644); os.close(fd)
    return rec


def parity(a):
    phases = [Path(p) for p in a.phases]
    while True:
        res = parity_once(phases, a.min_games)
        if res['out_of_band']:
            res['paused'] = str(pause(confine.JOB, res)); break
        if not a.watch or all((p/'supervisor-exit.json').exists() for p in phases): break
        if os.path.lexists(confine.JOB/'STOP'): res['stopped_by_STOP'] = True; break
        time.sleep(a.watch)
    res['phases'] = sorted(str(p.resolve()) for p in phases)
    res['passed'] = bool(res['passed'] and all((p/'supervisor-exit.json').exists() for p in phases)) if a.watch else res['passed']
    return res


def trainer(a):
    import numpy as np
    from exit_r3.student import RootTeacherStore, teacher_targets
    store = RootTeacherStore(a.packed, a.assets)
    n = len(store); rows = len(store.arrays['teacher_root'])
    b, y = store.batch(np.arange(min(64, n)))
    q = teacher_targets(y, .003)
    finite = bool(np.isfinite(q.numpy()).all()) and bool((abs(q.sum(-1).numpy()-1) < 1e-5).all())
    return dict(rows=rows, roots=n, all_rows_roots=n == rows, batch=int(len(y['action'])), targets_finite_normalized=finite,
                passed=n == rows and n > 0 and finite)


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('frozen'); f.add_argument('--corpus', type=Path, required=True); f.add_argument('--threads', type=int, default=1)
    h = sub.add_parser('hashes'); h.add_argument('--run-phase', type=Path, required=True); h.add_argument('--collect-phase', type=Path, required=True)
    h.add_argument('--config', type=Path, required=True)
    q = sub.add_parser('parity'); q.add_argument('--phases', type=Path, nargs='+', required=True)
    q.add_argument('--min-games', type=int, required=True); q.add_argument('--watch', type=int, default=0)
    r = sub.add_parser('roundtrip'); r.add_argument('--phases', type=Path, nargs='+', required=True); r.add_argument('--threads', type=int, default=1)
    t = sub.add_parser('trainer'); t.add_argument('--packed', type=Path, required=True); t.add_argument('--assets', type=Path, required=True)
    for p in (f, h, q, r, t): p.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(argv)
    confine.writable(str(a.out), roles=('qual', 'receipts'), must_not_exist=True)      # before any work (Sol F10)
    if a.cmd == 'parity' and a.min_games < 1: raise SystemExit('--min-games must be >= 1')
    try:
        result = dict(frozen=frozen, hashes=hashes, parity=parity, roundtrip=roundtrip, trainer=trainer)[a.cmd](a)
    except QualError as e:
        result = dict(passed=False, error=str(e))
    result.update(check=a.cmd, utc=utc(), label='X4S-4 qualification, exploration, NEVER ADOPTABLE')
    write_receipt(a.out, result); print(json.dumps({k: v for k, v in result.items() if k not in ('games',)}))
    raise SystemExit(0 if result['passed'] is True else 1)


if __name__ == '__main__':
    main()
