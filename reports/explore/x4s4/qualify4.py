"""X4S-4 qualification (exploration, NEVER ADOPTABLE). Runs on 127x01 before any collection.

  frozen    --corpus DIR --threads T --out R.json
      label.score_state reproduces the frozen screen8 reference action/candidates/scores on all 125
      states (the reports/explore/x4s/qualify.py equality), and the root is not mutated.
  hashes    --run-phase DIR --collect-phase DIR --out R.json
      Same config and indices: every game's command_sha256 is identical between the unchanged
      x4s3/run.py and x4s4/collect.py (capture non-perturbation); every collect game has a capture
      file whose SHA matches its summary; features_equal_all and public_equal_all hold; under
      `capture.all` nothing is unsampled and the collector's per-reason counts sum to the game's decisions.
  parity    --phases DIR... --out R.json
      Deadline-mode parity (PLAN r2 C7b; non-outcome metrics only): per arm, the collection games' cutoff %,
      student-default % and overrun % lie within +-2 pp of X4S-3's R3a (K4S-120 64.2 / 22.3 / 0.16;
      S-200 75.3 / 0.0 / 0.14).
  roundtrip --phases DIR... --sample N --threads T --out R.json
      On up to N captures (seeded choice): the rebuilt root digest equals the captured digest for
      every state, and labeling twice gives identical (action, candidates, scores).
  trainer   --packed DIR --assets FILE --out R.json      (clasher-gpu python, fit PYTHONPATH)
      A packed smoke batch loads in exit_r3.student.RootTeacherStore, every row is a root, and a
      64-row batch yields valid teacher targets.
Receipts are created with O_EXCL. Any failed check exits 1.
"""
import argparse, hashlib, json, os, pickle, random, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def utc(): return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()


def write_receipt(path, obj):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as f: f.write(json.dumps(obj, indent=2)+'\n')


def init_label(threads):
    sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent/'x4s3'))
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


def hashes(a):
    def games(phase):
        out = {}
        for p in sorted((phase/'games').glob('sim-*.json')):
            g = json.loads(p.read_text()); out[p.name] = g
        return out
    r, c = games(a.run_phase), games(a.collect_phase)
    cfg = json.loads((a.collect_phase/'schedule.json').read_text())
    same_sched = json.loads((a.run_phase/'schedule.json').read_text())['cases'] == cfg['cases']
    rows, ok = [], same_sched and set(r) == set(c) and len(r) > 0
    for name in sorted(r):
        hr, hc = r[name]['search_ab']['command_sha256'], c[name]['search_ab']['command_sha256']
        pkl = a.collect_phase/'captures'/name.replace('.json', '.pkl')
        summ = json.loads(pkl.with_suffix('.json').read_text())
        sha_ok = hashlib.sha256(pkl.read_bytes()).hexdigest() == summ['sha256']
        decisions = len(c[name]['search_ab']['deadline_stats'])
        counts = summ['counts']
        count_ok = (counts.get('not_sampled', 0) == 0 and sum(counts.values()) == decisions
                    and counts.get('captured', 0) == summ['captures'] > 0)
        chk = summ.get('checks', {})
        belief_ok = chk.get('belief_checked', 0) == summ['captures'] and chk.get('belief_unchanged', -1) == chk.get('belief_checked')
        fair_ok = chk.get('fair_checked', 0) == summ['captures'] and chk.get('fair_identical', -1) == chk.get('fair_checked')
        row = dict(game=name, equal=hr == hc, capture_sha_ok=sha_ok, features_equal_all=summ['features_equal_all'],
                   public_equal_all=summ['public_equal_all'], pending_empty_all=summ['pending_empty_all'], captures=summ['captures'],
                   decisions=decisions, counts=counts, count_ok=count_ok, checks=chk, belief_unchanged=belief_ok,
                   fair_invariant=fair_ok, fair_permuted_cards=chk.get('fair_permuted_cards', 0))
        ok &= all(row[k] for k in ('equal', 'capture_sha_ok', 'features_equal_all', 'public_equal_all', 'pending_empty_all',
                                   'count_ok', 'belief_unchanged', 'fair_invariant'))
        rows.append(row)
    return dict(same_schedule=same_sched, games=rows, passed=bool(ok))


def roundtrip(a):
    run, label, native = init_label(a.threads)
    caps = []
    for phase in a.phases:
        for pkl in sorted(Path(phase).glob('captures/sim-*.pkl')):
            caps += label.load_captures(pkl)[0]
    random.Random(2026101399).shuffle(caps); caps = caps[:a.sample]
    mism, unequal, fields_missing = 0, 0, 0
    for cap in caps:
        triple = (cap.get('reserved_packet'), cap.get('opponent_elixir'), cap.get('pending'))
        fields_missing += not (triple[0] is not None and 'opponent_elixir' in cap and triple[2] == ()
                               and hashlib.sha256(pickle.dumps(triple, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest() == cap.get('c8_sha256'))
        args = (cap['info'], cap['opponent'], cap['root_rng_state'], cap['candidate_rng_state'], cap['seed'], cap['root_digest'])
        try:
            first = label.score_state(*args); second = label.score_state(*args)
        except LookupError:
            mism += 1; continue
        unequal += first != second
    return dict(sampled=len(caps), digest_mismatches=mism, repeat_unequal=unequal, c8_fields_missing=fields_missing,
                threads=a.threads, native=native, passed=len(caps) > 0 and mism == 0 and unequal == 0 and fields_missing == 0)


X4S3_R3A = {'K4S-120': dict(cutoff=64.2, student_default=22.3, overrun=0.16), 'S-200': dict(cutoff=75.3, student_default=0.0, overrun=0.14)}


def parity(a):
    agg = {}
    for phase in a.phases:
        for p in sorted(Path(phase).glob('games/sim-*.json')):
            arm = p.stem.split('-d27-')[1]
            if not (Path(phase)/'blocks'/(p.name.split('-')[1]+'.json')).exists(): continue
            ds = json.loads(p.read_text())['search_ab']['deadline_stats']     # timing metadata only
            t = agg.setdefault(arm, dict(decisions=0, cutoff=0, student_default=0, overrun=0, games=0))
            t['games'] += 1; t['decisions'] += len(ds); t['cutoff'] += sum(bool(d['hit']) for d in ds)
            t['student_default'] += sum(bool(d.get('student_default')) for d in ds); t['overrun'] += sum(bool(d['wall_overrun']) for d in ds)
    rows, ok = {}, bool(agg)
    for arm, t in agg.items():
        pct = {k: 100*t[k]/max(1, t['decisions']) for k in ('cutoff', 'student_default', 'overrun')}
        ref = X4S3_R3A[arm]; within = {k: abs(pct[k]-ref[k]) <= 2.0 for k in pct}
        rows[arm] = dict(games=t['games'], decisions=t['decisions'], pct=pct, x4s3_r3a=ref, within_2pp=within)
        ok &= all(within.values())
    return dict(arms=rows, band_pp=2.0, passed=ok)


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


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('frozen'); f.add_argument('--corpus', type=Path, required=True); f.add_argument('--threads', type=int, default=1)
    h = sub.add_parser('hashes'); h.add_argument('--run-phase', type=Path, required=True); h.add_argument('--collect-phase', type=Path, required=True)
    q = sub.add_parser('parity'); q.add_argument('--phases', type=Path, nargs='+', required=True)
    r = sub.add_parser('roundtrip'); r.add_argument('--phases', type=Path, nargs='+', required=True)
    r.add_argument('--sample', type=int, default=200); r.add_argument('--threads', type=int, default=1)
    t = sub.add_parser('trainer'); t.add_argument('--packed', type=Path, required=True); t.add_argument('--assets', type=Path, required=True)
    for p in (f, h, q, r, t): p.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if os.path.lexists(a.out): raise SystemExit('receipt exists: '+str(a.out))
    result = dict(frozen=frozen, hashes=hashes, parity=parity, roundtrip=roundtrip, trainer=trainer)[a.cmd](a)
    result.update(check=a.cmd, utc=utc(), label='X4S-4 qualification, exploration, NEVER ADOPTABLE')
    write_receipt(a.out, result); print(json.dumps({k: v for k, v in result.items() if k not in ('games',)}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
