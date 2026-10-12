"""X4S-4 offline W-screen8 labeling of captured on-policy states (exploration, NEVER ADOPTABLE). r2 after Sol r1.

  label.py plan --phases DIR... --parity RECEIPT --out <job>/data/label-plan.json
      Requires a PASSING collection-parity receipt (C7b; qualify4 parity) for the same phases, or a failed one plus an
      explicit coordinator exception <job>/data/PARITY-EXCEPTION.json bound to that receipt's SHA. For every game it
      AUTHENTICATES the terminal block proof (index, seed, order and the game JSON's SHA-256; the game JSON is hashed,
      never parsed), and BINDS identities: filename index/arm == summary index/seed/arm == every capture's
      index/seed/arm, seed == C + index, seat == index % 2, and the arm's bank-C allocation (K4S-120: O 0-1999,
      holdout 3500-3749; S-200: O 2000-3499, holdout 3750-3999). Any capture with features/public parity false or a
      non-empty pre-decision pending makes the plan FAIL. Games without a block proof are dropped (interrupted).
      Within each set, dedup on SHA-256(row bytes + root digest) keeping the first in order (arm K4S-120, S-200;
      index; tick); O is truncated per arm to the caps (K4S-120 <= 200,000; S-200 <= 250,000). Reports strata shares
      and the feature-only duplicate rate per 600-tick bucket.
  label.py run --plan <job>/data/label-plan.json --set O|holdout --workers N [--threads T]
      Labels the set's kept captures with the X4S-qualified K4 anchor kernel at no deadline (the construction of
      reports/explore/x4s/qualify.py, reserve_floor=False asserted). Per game the capture file SHA must equal the
      plan entry. Declared drops only: root-digest mismatch, and a rebuilt root with <= 1 candidate or no completed
      score; any other exception fails the run. Each game is sealed with the unchanged imitation.exit_r1.rows.seal
      into a temp dir and renamed to <job>/data/raw-<set>/<arm>/game-<index:04d>/; its receipt binds the plan SHA,
      capture SHA, kept-id SHA, teacher and thread count. Resume re-verifies an existing game's seal and receipt
      identity before skipping it. The run receipt fails, and the process exits 1, if any game is incomplete or the
      declared drop rate exceeds 0.1%.

Runs ON 127x01 at nice >= 10, cores within 0-49, one single-core worker per core. STOP (-e or -L), the study hard
stop (<job>/HARD-STOP-UTC.txt), MemAvailable < 24 GiB and the study tree's <= 70 processes (studytree.py; the run
registers its process group and starts only within the <= 100 GB disk cap) are checked before every game and every 25
states. All
writes are confined below the job root (confine.py). recorded_outcome is 0 (outcomes are never stored).
"""
import argparse, copy, datetime, hashlib, json, multiprocessing, os, pickle, shutil, socket, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confine, studytree                        # noqa: E402

JOB = confine.JOB
ARM_ORDER = ('K4S-120', 'S-200')
CAPS = {'K4S-120': 200_000, 'S-200': 250_000}
ALLOC = {'K4S-120': dict(O=(0, 2000), holdout=(3500, 3750)), 'S-200': dict(O=(2000, 3500), holdout=(3750, 4000))}
C_BASE = 4503606317370496
DROP_LIMIT = 0.001
WAIT = 2304
TEACHER = 'W-screen8 K4 anchor, no deadline, reserve_floor=False'
run = None
THREADS = 1
RAW = None
PLAN_SHA = None


class PlanError(Exception):
    pass


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())
def stop_present(): return os.path.lexists(JOB/'STOP')
def hard_stop_passed():
    t = datetime.datetime.strptime((JOB/'HARD-STOP-UTC.txt').read_text().strip(), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc) >= t
def mem_available():
    try: return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    except Exception: return 0                       # unreadable -> treated as below the floor (fail closed)
def halt_reason():
    if stop_present(): return 'stopped'
    if hard_stop_passed(): return 'hard_stop'
    if mem_available() < 24*2**30: return 'memory_guard'
    if not studytree.admission(JOB, disk=False)[0]: return 'tree_cap'      # <= 70 X4S-4 processes (Sol F9)
    return None


def durable(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_json(path, obj, roles=('data',)):
    p = confine.writable(str(path), roles=roles); tmp = confine.writable(str(p)+'.tmp', roles=roles)
    tmp.write_text(json.dumps(obj, indent=2)+'\n'); durable(tmp); tmp.replace(p); durable(p)


def row_bytes_key(row, extra=b''):
    import numpy as np
    h = hashlib.sha256()
    for k in sorted(row):
        v = np.asarray(row[k]); h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(v.shape).encode()); h.update(v.tobytes())
    h.update(extra)
    return h.hexdigest()


def load_captures(pkl):
    summary = json.loads(Path(pkl).with_suffix('.json').read_text())
    raw = Path(pkl).read_bytes()
    if sha_bytes(raw) != summary['sha256']:
        raise PlanError('capture SHA mismatch: '+str(pkl))
    caps = [pickle.loads(blob) for blob in pickle.loads(raw)]
    if len(caps) != summary['captures'] or any(c['schema'] != 'x4s4.capture.v3' for c in caps):
        raise PlanError('capture count/schema mismatch: '+str(pkl))
    return caps, summary


def which_set(arm, index):
    for name, (lo, hi) in ALLOC[arm].items():
        if lo <= index < hi: return name
    raise PlanError(f'index {index} outside the {arm} bank-C allocation')


def authenticate_block(phase, arm, index):
    proof_path = phase/'blocks'/f'{index:04d}.json'
    if not proof_path.exists(): return None
    proof = json.loads(proof_path.read_text())
    game = f'sim-{index:04d}-d27-{arm}.json'
    if not (proof.get('index') == index and proof.get('seed') == C_BASE+index and proof.get('order') == [arm]
            and set(proof.get('games', {})) == {game} and sha_file(phase/'games'/game) == proof['games'][game]):
        raise PlanError(f'block proof does not authenticate {phase}/{game}')
    return proof


def make_plan(phases, parity, out):
    out = confine.writable(str(out), roles=('data',), must_not_exist=True)
    pr = json.loads(Path(parity).read_text())
    if not (pr.get('check') == 'parity' and sorted(map(str, pr.get('phases', []))) == sorted(str(Path(p).resolve()) for p in phases)):
        raise PlanError('a C7b parity receipt for exactly these collection phases is required')
    exception = None
    if pr.get('passed') is not True:      # Sol F12: only an explicit coordinator exception bound to this receipt
        ex = JOB/'data'/'PARITY-EXCEPTION.json'
        exception = json.loads(ex.read_text()) if ex.is_file() and not ex.is_symlink() else None
        if not (exception and exception.get('parity_receipt_sha256') == sha_file(parity) and exception.get('coordinator_ruling')
                and exception.get('decision') in ('continue', 'disclose')):
            raise PlanError('C7b parity failed and there is no explicit coordinator PARITY-EXCEPTION for this receipt')
    files = []
    for phase in map(Path, phases):
        for pkl in sorted(phase.glob('captures/sim-*-d27-*.pkl')):
            index, arm = int(pkl.name.split('-')[1]), pkl.stem.split('-d27-')[1]
            if arm not in ARM_ORDER: raise PlanError('unknown arm '+arm)
            files.append((ARM_ORDER.index(arm), index, arm, pkl, phase))
    files.sort(key=lambda x: (x[0], x[1]))
    if len({(f[2], f[1]) for f in files}) != len(files): raise PlanError('duplicate (arm, index) capture files across phases')
    sets = {'O': [], 'holdout': []}
    stats = {s: dict(games=0, dropped_no_block=0, captured=0, duplicate=0, over_cap=0, kept=0,
                     kept_per_arm={a: 0 for a in ARM_ORDER}, strata={}, student_default=0, fallback=0, plays=0) for s in sets}
    seen = {s: set() for s in sets}
    feature_seen, buckets = set(), {}
    for _, index, arm, pkl, phase in files:
        which = which_set(arm, index); st = stats[which]
        if authenticate_block(phase, arm, index) is None:
            st['dropped_no_block'] += 1; continue
        caps, summary = load_captures(pkl)
        if not (summary['index'] == index and summary['arm'] == arm and summary['seed'] == C_BASE+index and summary.get('identity_ok')):
            raise PlanError(f'summary identity mismatch: {pkl}')
        st['games'] += 1; keep = []
        for c in sorted(caps, key=lambda c: c['tick']):
            if not (c['index'] == index and c['arm'] == arm and c['seed'] == C_BASE+index and c['seat'] == index % 2):
                raise PlanError(f'capture identity mismatch in {pkl}: {c["id"]}')
            if not (c['features_equal_student_input'] and c['row_equals_build_public'] and c['pending'] == ()):
                raise PlanError(f'capture parity/pending failure in {pkl}: {c["id"]}')
            st['captured'] += 1
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
            st['plays'] += c['agent_action'] < WAIT
        sets[which].append(dict(file=str(pkl), sha256=summary['sha256'], arm=arm, index=index, seed=summary['seed'], keep=keep,
                                keep_sha256=sha_bytes(json.dumps(sorted(keep)).encode())))
    dup = {b: dict(states=v[0], feature_duplicates=v[1], rate=v[1]/v[0]) for b, v in sorted(buckets.items(), key=lambda x: int(x[0]))}
    write_json(out, dict(utc=utc(), schema='x4s4.label-plan.v3', caps=CAPS, allocation=ALLOC, c_base=C_BASE, parity_receipt_sha256=sha_file(parity), parity_exception=exception,
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


class DigestMismatch(LookupError):
    pass


def score_state(info, opponent, root_rng_state, candidate_rng_state, seed, root_digest=None):
    """No-deadline W-screen8 score at one captured root. Returns (action, candidates, scores)."""
    import numpy as np
    rng = np.random.default_rng(); rng.bit_generator.state = copy.deepcopy(root_rng_state)
    root = run.R.root(copy.deepcopy(info), copy.deepcopy(opponent), rng)
    digest = root.digest()
    if root_digest is not None and digest != root_digest:
        raise DigestMismatch('root digest mismatch')
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
            raise RuntimeError('scored candidate outside gate-c mask')       # defect, never a silent drop
    move = WAIT if action >= WAIT else action
    if not mask[move]:
        raise RuntimeError('teacher selected a masked action')
    position = DiscreteTileActionSpace().decode_action(move, cap['seat']).position
    xy = [np.nan, np.nan] if position is None else [position.x, position.y]
    row = {k: np.asarray(v).copy() for k, v in cap['row'].items()}
    row.update(expert_actions=np.int16(move), expert_action_supervision_valid=np.bool_(True), submitted_ticks=np.int32(cap['tick']),
               teacher_search_action=np.int16(action), teacher_root=np.bool_(True), teacher_wait_kind=np.int8(0))
    row.update(recorded_play_ticks=np.int32(-1 if move == WAIT else cap['tick']+27),
               recorded_world_positions=np.array(xy, np.float32), submitted_world_positions=np.array(xy, np.float32),
               recorded_millitiles=np.array([-1, -1] if position is None else [round(position.x*1000), round(position.y*1000)], np.int32))
    return row


def verify_sealed(final, entry):
    """Resume: re-verify an existing labeled game's seal and receipt identity before skipping it."""
    seal = json.loads((final/'manifest.json').read_text())
    if not (seal.get('complete') is True and all(sha_file(final/k) == v for k, v in seal['files'].items())):
        raise RuntimeError(f'existing labeled game fails its seal: {final}')
    r = json.loads((final/'receipt.json').read_text())
    want = dict(capture_sha256=entry['sha256'], plan_sha256=PLAN_SHA, keep_sha256=entry['keep_sha256'], teacher=TEACHER,
                search_threads=THREADS, seed=entry['seed'], index=entry['index'], arm=entry['arm'])
    bad = {k: (r.get(k), v) for k, v in want.items() if r.get(k) != v}
    if bad: raise RuntimeError(f'existing labeled game identity differs from the plan: {final}: {bad}')
    return r


def label_game(entry):
    from imitation.exit_r1.rows import seal
    out_root = confine.writable(str(Path(RAW)/entry['arm']), roles=('data',))
    final = confine.writable(str(out_root/f"game-{entry['index']:04d}"), roles=('data',))
    base = dict(index=entry['index'], arm=entry['arm'], attempted=len(entry['keep']))
    if (final/'manifest.json').exists():
        r = verify_sealed(final, entry)
        return dict(base, status='already_sealed', rows=r['rows'], drops=r['drops'])
    why = halt_reason()
    if why: return dict(base, status=why)
    caps, summary = load_captures(Path(entry['file']))
    if summary['sha256'] != entry['sha256']: raise RuntimeError(f"capture file changed since the plan: {entry['file']}")
    keep = set(entry['keep']); rows, score_rows, drops = [], [], {}
    t0, cpu0 = time.monotonic(), time.process_time()
    for n, cap in enumerate(sorted((c for c in caps if c['id'] in keep), key=lambda c: c['tick'])):
        if n % 25 == 24:
            why = halt_reason()
            if why: return dict(base, status=why)
        try:
            action, candidates, scores = score_state(cap['info'], cap['opponent'], cap['root_rng_state'],
                                                     cap['candidate_rng_state'], cap['seed'], cap['root_digest'])
        except DigestMismatch:
            drops['digest_mismatch'] = drops.get('digest_mismatch', 0)+1; continue
        if len(candidates) <= 1 or not any(s is not None for s in scores):
            drops['no_scored_root'] = drops.get('no_scored_root', 0)+1; continue
        rows.append(label_rows(cap, action, candidates, scores)); score_rows.append(dict(candidates=candidates, scores=scores))
    if len(rows)+sum(drops.values()) != len(keep):
        raise RuntimeError(f"kept captures missing from the capture file: {entry['file']}")
    if not rows:
        return dict(base, status='no_rows', rows=0, drops=drops)
    tmp = confine.writable(str(out_root/f"game-{entry['index']:04d}.tmp"), roles=('data',))
    if tmp.exists(): shutil.rmtree(tmp)                      # confined: our own temp dir only
    if not out_root.exists(): confine.mkdirs(str(out_root), roles=('data',))
    receipt = dict(seed=entry['seed'], index=entry['index'], arm=entry['arm'], outcome=0, outcome_withheld=True,
                   rows=len(rows), root_decisions=len(rows), drops=drops, capture_sha256=entry['sha256'], plan_sha256=PLAN_SHA,
                   keep_sha256=entry['keep_sha256'], teacher=TEACHER, search_threads=THREADS,
                   cpu_seconds=time.process_time()-cpu0, wall_seconds=time.monotonic()-t0, host=socket.gethostname(),
                   label='X4S-4 on-policy labels, exploration, NEVER ADOPTABLE')
    seal(tmp, rows, score_rows, receipt)
    tmp.rename(final)
    return dict(base, status='sealed', rows=len(rows), drops=drops, cpu_seconds=receipt['cpu_seconds'])


def pin():
    ident = multiprocessing.current_process()._identity[0]
    cores = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cores[(ident-1) % len(cores)]})


def run_labels(plan_path, which, workers, threads):
    global run, RAW, THREADS, PLAN_SHA
    if socket.gethostname() != '127x01' or os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise SystemExit('label run requires 127x01 at nice >= 10')
    if not os.sched_getaffinity(0) <= set(range(50)) or not 1 <= workers <= min(50, len(os.sched_getaffinity(0))):
        raise SystemExit('label run requires cores within 0-49 and 1 <= workers <= cores')
    if halt_reason(): raise SystemExit('halted before start: '+halt_reason())
    ok, why = studytree.admission(JOB)
    if not ok: raise SystemExit('study admission: '+why)
    studytree.register(JOB, f'label-{which}')
    plan_path = Path(plan_path)
    if plan_path.resolve() != (JOB/'data'/'label-plan.json'): raise SystemExit('plan must be <job>/data/label-plan.json')
    RAW, THREADS, PLAN_SHA = str(JOB/'data'/f'raw-{which}'), threads, sha_file(plan_path)
    plan = json.loads(plan_path.read_text())
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
    finish(JOB/'data'/f'label-receipt-{which}-{int(time.time())}.json', dict(
        summarize(results, len(entries)), started=started, finished=utc(), set=which, plan_sha256=PLAN_SHA, native=native,
        native_sha256=sha_file(native), threads=threads, workers=workers, label='X4S-4 exploration, NEVER ADOPTABLE'))


def summarize(results, n_entries):
    """Run-receipt fields: complete only if every planned game is sealed/already sealed/no_rows (Sol F5)."""
    status = {}
    for r in results: status[r['status']] = status.get(r['status'], 0)+1
    done = [r for r in results if r['status'] in ('sealed', 'already_sealed', 'no_rows')]
    attempted = sum(r['attempted'] for r in done)
    drops = {k: sum(r.get('drops', {}).get(k, 0) for r in done) for k in ('digest_mismatch', 'no_scored_root')}
    complete = len(done) == n_entries == len(results)
    rate = sum(drops.values())/max(1, attempted)
    return dict(status_counts=status, complete=complete, attempted=attempted, rows=sum(r.get('rows', 0) for r in done), drops=drops,
                drop_rate=rate, digest_mismatch_rate=drops['digest_mismatch']/max(1, attempted), drop_limit=DROP_LIMIT,
                passed=bool(complete and rate <= DROP_LIMIT), games=sorted([r['arm'], r['index']] for r in done if r.get('rows')))


def finish(path, body):
    """Write the run receipt; a failed receipt exits 1 (Sol F5)."""
    write_json(path, body)
    if body['passed'] is not True: raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan'); p.add_argument('--phases', nargs='+', required=True); p.add_argument('--parity', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    r = sub.add_parser('run'); r.add_argument('--plan', type=Path, required=True); r.add_argument('--set', choices=['O', 'holdout'], required=True)
    r.add_argument('--workers', type=int, required=True); r.add_argument('--threads', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'plan': make_plan(a.phases, a.parity, a.out)
    else: run_labels(a.plan, a.set, a.workers, a.threads)


if __name__ == '__main__':
    main()
