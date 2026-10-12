"""X4S-4 offline W-screen8 labeling of captured on-policy states (exploration, NEVER ADOPTABLE).

  label.py plan --phases DIR... --out LABEL_PLAN.json
      Verifies each capture file against its summary SHA (games without a block proof are dropped:
      interrupted or non-terminal). Splits by index: < 3500 -> set O, >= 3500 -> set holdout (bank-C
      O-holdout, never trained on). Within each set, dedup on SHA-256(row bytes + root digest) keeping
      the first in order (arm K4S-120, S-200; index; tick); O is then truncated per arm to the caps
      (K4S-120 <= 200,000; S-200 <= 250,000). Reports strata shares and the feature-only duplicate rate
      (row bytes only) per 600-tick bucket.
  label.py run --plan LABEL_PLAN.json --set O|holdout --out RAW_DIR --workers N [--threads T]
      Labels the set's kept captures with the X4S-qualified K4 anchor kernel at no deadline (the
      construction of reports/explore/x4s/qualify.py, reserve_floor=False asserted): rebuild the root
      from (info, opponent, root RNG state) and require the captured digest (mismatch -> state dropped
      and counted); regenerate candidates from the captured candidate RNG state; score. Rows get the
      G-emitter teacher fields; each game is sealed with the unchanged imitation.exit_r1.rows.seal into
      a temp dir, then renamed to RAW_DIR/<arm>/game-<index:04d>/ (pack.py layout). The final receipt
      records the digest-mismatch rate; > 0.1% marks the run failed (the O gate refuses it).

Runs ON 127x01 at nice >= 10, cores within 0-49, one single-core worker per core. STOP (<job>/STOP,
-e or -L) and MemAvailable < 24 GiB are checked before every game; a rerun skips sealed games.
recorded_outcome is 0 (outcomes are never stored).
"""
import argparse, copy, hashlib, json, multiprocessing, os, pickle, shutil, socket, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOB = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')
ARM_ORDER = ('K4S-120', 'S-200')
CAPS = {'K4S-120': 200_000, 'S-200': 250_000}
HOLDOUT_MIN_INDEX = 3500
MISMATCH_LIMIT = 0.001
WAIT = 2304
run = None
THREADS = 1
RAW = None


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def stop_present(): return os.path.lexists(JOB/'STOP')
def mem_available():
    return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024


def durable(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_json(path, obj):
    tmp = Path(str(path)+'.tmp'); tmp.write_text(json.dumps(obj, indent=2)+'\n'); durable(tmp); tmp.replace(path); durable(path)


def row_bytes_key(row, extra=b''):
    import numpy as np
    h = hashlib.sha256()
    for k in sorted(row):
        v = np.asarray(row[k]); h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(v.shape).encode()); h.update(v.tobytes())
    h.update(extra)
    return h.hexdigest()


def load_captures(pkl):
    summary = json.loads(pkl.with_suffix('.json').read_text())
    raw = pkl.read_bytes()
    if sha_bytes(raw) != summary['sha256']:
        raise ValueError('capture SHA mismatch: '+str(pkl))
    caps = [pickle.loads(blob) for blob in pickle.loads(raw)]
    if len(caps) != summary['captures'] or any(c['schema'] != 'x4s4.capture.v2' for c in caps):
        raise ValueError('capture count/schema mismatch: '+str(pkl))
    return caps, summary


def make_plan(phases, out):
    files = []
    for phase in phases:
        for pkl in sorted(Path(phase).glob('captures/sim-*-d27-*.pkl')):
            index, arm = int(pkl.name.split('-')[1]), pkl.stem.split('-d27-')[1]
            if arm not in ARM_ORDER: raise ValueError('unknown arm '+arm)
            files.append((ARM_ORDER.index(arm), index, arm, pkl, Path(phase)))
    files.sort(key=lambda x: (x[0], x[1]))
    sets = {'O': [], 'holdout': []}
    stats = {s: dict(games=0, dropped_no_block=0, captured=0, features_unequal=0, duplicate=0, over_cap=0, kept=0,
                     kept_per_arm={a: 0 for a in ARM_ORDER}, strata={}, student_default=0, fallback=0) for s in sets}
    seen = {s: set() for s in sets}
    feature_seen, buckets = set(), {}
    for _, index, arm, pkl, phase in files:
        which = 'holdout' if index >= HOLDOUT_MIN_INDEX else 'O'
        st = stats[which]
        if not (phase/'blocks'/f'{index:04d}.json').exists():
            st['dropped_no_block'] += 1; continue
        caps, summary = load_captures(pkl)
        st['games'] += 1; keep = []
        for c in sorted(caps, key=lambda c: c['tick']):
            st['captured'] += 1
            if not c['features_equal_student_input'] or c['pending'] != ():
                st['features_unequal'] += 1; continue
            if which == 'O':
                fkey = row_bytes_key(c['row']); b = str(c['tick']//600*600)
                d = buckets.setdefault(b, [0, 0]); d[0] += 1; d[1] += fkey in feature_seen; feature_seen.add(fkey)
            k = row_bytes_key(c['row'], str(c['root_digest']).encode())
            if k in seen[which]: st['duplicate'] += 1; continue
            seen[which].add(k)
            if which == 'O' and st['kept_per_arm'][arm] >= CAPS[arm]: st['over_cap'] += 1; continue
            keep.append(c['id']); st['kept'] += 1; st['kept_per_arm'][arm] += 1
            st['strata'][c['stratum']] = st['strata'].get(c['stratum'], 0)+1
            st['student_default'] += bool(c['stats'].get('student_default')); st['fallback'] += bool(c['stats'].get('fallback'))
        sets[which].append(dict(file=str(pkl), sha256=summary['sha256'], arm=arm, index=index, seed=summary['seed'], keep=keep))
    dup = {b: dict(states=v[0], feature_duplicates=v[1], rate=v[1]/v[0]) for b, v in sorted(buckets.items(), key=lambda x: int(x[0]))}
    write_json(out, dict(utc=utc(), schema='x4s4.label-plan.v2', caps=CAPS, holdout_min_index=HOLDOUT_MIN_INDEX,
                         order='arm K4S-120,S-200; index; tick', dedup='sha256(row bytes)+root_digest (multiple determinizations kept)',
                         feature_only_duplicates_by_600_tick_bucket=dup, stats=stats, sets=sets))
    print(json.dumps({s: {k: stats[s][k] for k in ('games', 'kept', 'duplicate', 'over_cap')} for s in stats}), flush=True)


def make_teacher(seed):
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    import anchor
    c = anchor.planner_class(DelayAwarePlanner)(run.R.builder, run.R.bots, backend='native', native=run.R.native,
        native_config=run.R.config, catalog=run.CAT, config=C56SearchConfig(threads=1, wait_screen8=False), seed=seed+100001,
        command_delay=27, delay_aware=True, symmetric_opponent=True, opponent_delay=27, opponent_interval=10,
        opponent_capacity=1, max_outstanding=1, arm='W', variant='screen8', reserve_floor=False,
        search_threads=THREADS, coarse_horizon=160)
    if getattr(c, 'reserve_floor', False) is not False:
        raise RuntimeError('labeler W config must have reserve_floor=False')
    return c


def score_state(info, opponent, root_rng_state, candidate_rng_state, seed, root_digest=None):
    """No-deadline W-screen8 score at one captured root. Returns (action, candidates, scores)."""
    import numpy as np
    rng = np.random.default_rng(); rng.bit_generator.state = copy.deepcopy(root_rng_state)
    root = run.R.root(copy.deepcopy(info), copy.deepcopy(opponent), rng)
    digest = root.digest()
    if root_digest is not None and digest != root_digest:
        raise LookupError('root digest mismatch')
    c = make_teacher(seed)
    c.rng.bit_generator.state = copy.deepcopy(candidate_rng_state); c.info = copy.deepcopy(info); c.costs = run.R.costs
    candidates, _ = c.candidates(c.info.packet, []); candidates = [x for x in candidates if x != 2305]
    try:
        action = c.score_candidates(root, c.info.seat, candidates, fallback=WAIT)
        last = dict(candidates=[int(x) for x in c.last['candidates']], scores=list(c.last['scores']))
    finally:
        c.close()
    if root.digest() != digest:
        raise RuntimeError('root mutated by scoring')
    return int(action), last['candidates'], last['scores']


def label_rows(cap, action, candidates, scores):
    import numpy as np
    from clasher.rl.action_space import DiscreteTileActionSpace
    mask = np.unpackbits(cap['row']['packed_mask'])[:2306].astype(bool)
    for a, v in zip(candidates, scores):
        if v is not None and a < 2400 and not mask[a]:
            raise ValueError('scored candidate outside gate-c mask')
    move = WAIT if action >= WAIT else action
    if not mask[move]:
        raise ValueError('teacher selected a masked action')
    position = DiscreteTileActionSpace().decode_action(move, cap['seat']).position
    xy = [np.nan, np.nan] if position is None else [position.x, position.y]
    row = {k: np.asarray(v).copy() for k, v in cap['row'].items()}
    row.update(expert_actions=np.int16(move), expert_action_supervision_valid=np.bool_(True), submitted_ticks=np.int32(cap['tick']),
               teacher_search_action=np.int16(action), teacher_root=np.bool_(True), teacher_wait_kind=np.int8(0))
    row.update(recorded_play_ticks=np.int32(-1 if move == WAIT else cap['tick']+27),
               recorded_world_positions=np.array(xy, np.float32), submitted_world_positions=np.array(xy, np.float32),
               recorded_millitiles=np.array([-1, -1] if position is None else [round(position.x*1000), round(position.y*1000)], np.int32))
    return row


def label_game(entry):
    from imitation.exit_r1.rows import seal
    out_root = Path(RAW)/entry['arm']
    final = out_root/f"game-{entry['index']:04d}"
    base = dict(index=entry['index'], arm=entry['arm'], attempted=len(entry['keep']))
    if (final/'manifest.json').exists():
        prior = json.loads((final/'receipt.json').read_text())
        return dict(base, status='already_sealed', rows=prior['rows'], digest_mismatch=prior['skipped'].get('LookupError: root digest mismatch', 0))
    if stop_present(): return dict(base, status='stopped')
    if mem_available() < 24*2**30: return dict(base, status='memory_guard')
    caps, _ = load_captures(Path(entry['file']))
    keep = set(entry['keep']); rows, score_rows, skipped = [], [], {}
    t0, cpu0 = time.monotonic(), time.process_time()
    for cap in sorted((c for c in caps if c['id'] in keep), key=lambda c: c['tick']):
        try:
            action, candidates, scores = score_state(cap['info'], cap['opponent'], cap['root_rng_state'],
                                                     cap['candidate_rng_state'], cap['seed'], cap['root_digest'])
            if len(candidates) <= 1 or not any(s is not None for s in scores):
                skipped['no_scored_root'] = skipped.get('no_scored_root', 0)+1; continue
            rows.append(label_rows(cap, action, candidates, scores)); score_rows.append(dict(candidates=candidates, scores=scores))
        except (LookupError, ValueError) as e:
            key = type(e).__name__+': '+str(e); skipped[key] = skipped.get(key, 0)+1
    mism = skipped.get('LookupError: root digest mismatch', 0)
    if not rows:
        return dict(base, status='no_rows', skipped=skipped, digest_mismatch=mism)
    tmp = out_root/f"game-{entry['index']:04d}.tmp"
    if tmp.exists(): shutil.rmtree(tmp)
    out_root.mkdir(parents=True, exist_ok=True)
    receipt = dict(seed=entry['seed'], index=entry['index'], arm=entry['arm'], outcome=0, outcome_withheld=True,
                   rows=len(rows), root_decisions=len(rows), skipped=skipped, capture_sha256=entry['sha256'],
                   teacher='W-screen8 K4 anchor, no deadline, reserve_floor=False, search_threads=%d' % THREADS,
                   cpu_seconds=time.process_time()-cpu0, wall_seconds=time.monotonic()-t0, host=socket.gethostname(),
                   label='X4S-4 on-policy labels, exploration, NEVER ADOPTABLE')
    seal(tmp, rows, score_rows, receipt)
    tmp.rename(final)
    return dict(base, status='sealed', rows=len(rows), skipped=skipped, digest_mismatch=mism, cpu_seconds=receipt['cpu_seconds'])


def pin():
    ident = multiprocessing.current_process()._identity[0]
    cores = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cores[(ident-1) % len(cores)]})


def run_labels(plan_path, which, raw, workers, threads):
    global run, RAW, THREADS
    if socket.gethostname() != '127x01' or os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise SystemExit('label run requires 127x01 at nice >= 10')
    if not os.sched_getaffinity(0) <= set(range(50)) or not 1 <= workers <= min(50, len(os.sched_getaffinity(0))):
        raise SystemExit('label run requires cores within 0-49 and 1 <= workers <= cores')
    if stop_present():
        raise SystemExit('STOP present')
    RAW, THREADS = str(raw), threads
    plan = json.loads(Path(plan_path).read_text())
    sys.path.insert(0, str(HERE.parent/'x4s3'))
    import run as run_module
    run = run_module
    native = run.initialize()
    import torch; torch.set_num_threads(1)
    entries = [g for g in plan['sets'][which] if g['keep']]
    started = utc(); results = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('fork'), initializer=pin) as pool:
        for r in pool.map(label_game, entries, chunksize=1):
            results.append(r); print(json.dumps(r), flush=True)
    status = {}
    for r in results: status[r['status']] = status.get(r['status'], 0)+1
    attempted = sum(r['attempted'] for r in results if r['status'] in ('sealed', 'already_sealed', 'no_rows'))
    mismatches = sum(r.get('digest_mismatch', 0) for r in results)
    complete = all(r['status'] in ('sealed', 'already_sealed', 'no_rows') for r in results) and len(results) == len(entries)
    rate = mismatches/max(1, attempted)
    write_json(Path(raw)/f'label-receipt-{which}-{int(time.time())}.json', dict(
        started=started, finished=utc(), set=which, plan_sha256=sha_bytes(Path(plan_path).read_bytes()), native=native,
        native_sha256=sha_bytes(Path(native).read_bytes()), threads=threads, workers=workers, status_counts=status,
        complete=complete, attempted=attempted, rows=sum(r.get('rows', 0) for r in results),
        digest_mismatches=mismatches, digest_mismatch_rate=rate, mismatch_limit=MISMATCH_LIMIT,
        passed=complete and rate <= MISMATCH_LIMIT,
        skipped={k: sum(r.get('skipped', {}).get(k, 0) for r in results) for k in {k for r in results for k in r.get('skipped', {})}},
        label='X4S-4 exploration, NEVER ADOPTABLE'))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan'); p.add_argument('--phases', nargs='+', required=True); p.add_argument('--out', type=Path, required=True)
    r = sub.add_parser('run'); r.add_argument('--plan', type=Path, required=True); r.add_argument('--set', choices=['O', 'holdout'], required=True)
    r.add_argument('--out', type=Path, required=True); r.add_argument('--workers', type=int, required=True)
    r.add_argument('--threads', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'plan': make_plan(a.phases, a.out)
    else: run_labels(a.plan, a.set, a.out, a.workers, a.threads)


if __name__ == '__main__':
    main()
