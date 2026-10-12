"""X4S-4 offline W-screen8 labeling of captured on-policy states (exploration, NEVER ADOPTABLE). r3 after Sol r2.

Every read and write goes through x4s4io (R2-F1); game JSONs are only projected to non-outcome metadata.

  label.py plan --phases DIR... --parity RECEIPT --out <job>/data/label-plan.json
      C7b admission (R2-F8): the parity receipt must be FINAL (every phase exited), name exactly these phases, and its
      game inventory must equal the phases' CURRENT block-proved inventory (a receipt from earlier, smaller phases is
      stale and refused). It must pass, or a failed receipt needs <job>/data/PARITY-EXCEPTION.json bound to the
      receipt's SHA AND to a coordinator commit on origin/main whose COORDINATOR.md names that SHA (verified through
      the self-verifying git walker); the exception is recorded in the plan and the hard stop is never reset.
      For every game it AUTHENTICATES the block proof (index, seed, order, game SHA-256) and the projected game
      metadata (terminal, seed, arm), and BINDS identities: filename index/arm == summary index/seed/arm == every
      capture's index/seed/arm, seed == C + index, seat == index % 2, and the arm's bank-C allocation (K4S-120: O
      0-1999, holdout 3500-3749; S-200: O 2000-3499, holdout 3750-3999). Any capture with features/public parity false
      or a non-empty pre-decision pending makes the plan FAIL. Games without a block proof are dropped (interrupted).
      Within each set, dedup on SHA-256(row bytes + root digest) keeping the first in order (arm K4S-120, S-200;
      index; tick); O is truncated per arm to the caps (K4S-120 <= 200,000; S-200 <= 250,000). Reports strata shares
      and the feature-only duplicate rate per 600-tick bucket.
  label.py run --plan <job>/data/label-plan.json --set O|holdout --workers N [--threads T]
      Labels the set's kept captures with the X4S-qualified K4 anchor kernel at no deadline (reserve_floor=False
      asserted). Per game the capture file SHA must equal the plan entry. Declared drops only: root-digest mismatch,
      and a rebuilt root with <= 1 candidate or no completed score; any other exception fails the run. Each game is
      sealed with the unchanged imitation.exit_r1.rows.seal into a validated fresh temp dir and renamed to
      <job>/data/raw-<set>/<arm>/game-<index:04d>/; its receipt binds the plan SHA, capture SHA, kept-id SHA, teacher
      and thread count. Resume re-verifies the existing game's complete seal inventory and receipt identity.
      The parent dispatches one game at a time per free worker and runs the live guards (studytree.monitor) between
      dispatches: STOP, the hard stop, MemAvailable, PSI readability, the labeler's PSS (<= 50 GiB), the tree's
      <= 70 processes and the job's <= 100 GB; on a breach it stops dispatch, TERM/KILLs its own verified worker PIDs
      and fails. Admission reserves workers + 1 processes. The run receipt fails, and the process exits 1, if any game
      is incomplete or the declared drop rate exceeds 0.1%.

Runs ON 127x01 at nice >= 10, cores within 0-49, one single-core worker per core. recorded_outcome is 0.
"""
import argparse, copy, hashlib, json, multiprocessing, os, pickle, socket, sys, time
from concurrent.futures import ProcessPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io, studytree, qualify4         # noqa: E402

JOB = io.JOB
ARM_ORDER = ('K4S-120', 'S-200')
CAPS = {'K4S-120': 200_000, 'S-200': 250_000}
ALLOC = {'K4S-120': dict(O=(0, 2000), holdout=(3500, 3750)), 'S-200': dict(O=(2000, 3500), holdout=(3750, 4000))}
C_BASE = 4503606317370496
DROP_LIMIT = 0.001
WAIT = 2304
TEACHER = 'W-screen8 K4 anchor, no deadline, reserve_floor=False'
COORDINATOR_MD = 'reports/strategy_council_20260928/COORDINATOR.md'
run = None
THREADS = 1
RAW = None
PLAN_SHA = None


class PlanError(Exception):
    pass


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return io.sha256_file(str(p))


def halt_reason():
    """Worker-side checks between states (the parent runs the full live guards)."""
    if io.lexists(JOB+'/STOP'): return 'stopped'
    if studytree.hard_stop_passed(JOB): return 'hard_stop'
    return None


def write_json(path, obj, roles=('data',)):
    io.replace_json(str(path), obj, roles=roles)


def row_bytes_key(row, extra=b''):
    import numpy as np
    h = hashlib.sha256()
    for k in sorted(row):
        v = np.asarray(row[k]); h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(v.shape).encode()); h.update(v.tobytes())
    h.update(extra)
    return h.hexdigest()


def load_captures(pkl):
    pkl = str(pkl)
    summary = io.read_json(pkl[:-4]+'.json', 16 << 20)
    raw = io.read_bytes(pkl, 8 << 30)
    if sha_bytes(raw) != summary['sha256']:
        raise PlanError('capture SHA mismatch: '+pkl)
    caps = [pickle.loads(blob) for blob in pickle.loads(raw)]
    if len(caps) != summary['captures'] or any(c['schema'] != 'x4s4.capture.v3' for c in caps):
        raise PlanError('capture count/schema mismatch: '+pkl)
    return caps, summary


def which_set(arm, index):
    for name, (lo, hi) in ALLOC[arm].items():
        if lo <= index < hi: return name
    raise PlanError(f'index {index} outside the {arm} bank-C allocation')


def authenticate_block(phase, arm, index):
    """None if the game has no block proof (interrupted); otherwise the proof, game SHA and projected terminal
    identity must all hold (R2-F8), else PlanError."""
    if not io.lexists(f'{phase}/blocks/{index:04d}.json'): return None
    try:
        g, digest = qualify4.proved_game(str(phase), index, arm, C_BASE)
    except (qualify4.QualError, io.Refusal) as e:
        raise PlanError(f'block proof does not authenticate {phase} {index} {arm}: {e}')
    m = qualify4.game_meta(g).get('metadata', {})
    if m.get('seat') != index % 2: raise PlanError(f'{phase} {index} {arm}: seat differs')
    return digest


def check_parity(phases, parity):
    """R2-F8: final, exact-phase, current-inventory parity receipt; failed parity needs an authentic exception."""
    pr = io.read_json(str(parity), 256 << 20)
    names = sorted(str(p) for p in phases)
    if not (pr.get('check') == 'parity' and sorted(map(str, pr.get('phases', []))) == names):
        raise PlanError('a C7b parity receipt for exactly these collection phases is required')
    if pr.get('bank') != 'collection': raise PlanError('label admission accepts only a bank-C collection parity receipt')
    evidence = qualify4.phase_evidence(names)                 # R3-F5: re-derive the final phase evidence NOW
    if pr.get('final') is not True or any(e['supervisor-exit.json'] is None for e in evidence.values()):
        raise PlanError('the parity receipt is not final, or a phase no longer has its supervisor-exit evidence')
    if pr.get('evidence') != evidence: raise PlanError('stale parity receipt: phase schedule/launch/exit evidence changed')
    try: current = qualify4.parity_inventory(names)
    except (qualify4.QualError, io.Refusal) as e: raise PlanError(f'parity inventory cannot be re-derived: {e}')
    if pr.get('inventory') != current:
        raise PlanError('stale parity receipt: its game inventory differs from the current phases')
    exception = None
    if pr.get('passed') is not True:
        ex = JOB+'/data/PARITY-EXCEPTION.json'
        exception = io.read_json(ex, 1 << 20) if io.lexists(ex) else None
        receipt_sha = sha_file(parity)
        ok = bool(exception and exception.get('parity_receipt_sha256') == receipt_sha and exception.get('decision') in ('continue', 'disclose')
                  and isinstance(exception.get('coordinator_commit'), str))
        if ok:
            try:
                text = io.git_committed_blob(io.REPO, exception['coordinator_commit'], COORDINATOR_MD).decode('utf-8', 'replace')
                ok = receipt_sha in text and io.git_is_ancestor(io.REPO, exception['coordinator_commit'])
            except io.Refusal:
                ok = False
        if not ok:
            raise PlanError('C7b parity failed and there is no authentic coordinator PARITY-EXCEPTION for this receipt')
    return pr, exception


def recheck_parity(plan):
    """Later consumers (label run, O/holdout verification) re-run the full parity admission on the plan's receipt."""
    if sha_file(plan['parity_receipt']) != plan['parity_receipt_sha256']: raise PlanError('parity receipt changed since the plan')
    check_parity(plan['parity_phases'], plan['parity_receipt'])


def make_plan(phases, parity, out):
    io.check_writable(str(out), roles=('data',), must_not_exist=True)
    phases = [str(p) for p in phases]
    pr, exception = check_parity(phases, parity)
    files = []
    for phase in phases:
        cdir = phase+'/captures'
        for name in (io.listdir(cdir) if io.lexists(cdir) else []):
            if not (name.startswith('sim-') and name.endswith('.pkl')): continue
            index, arm = int(name.split('-')[1]), name[:-4].split('-d27-')[1]
            if arm not in ARM_ORDER: raise PlanError('unknown arm '+arm)
            files.append((ARM_ORDER.index(arm), index, arm, f'{cdir}/{name}', phase))
    files.sort(key=lambda x: (x[0], x[1]))
    if len({(f[2], f[1]) for f in files}) != len(files): raise PlanError('duplicate (arm, index) capture files across phases')
    sets = {'O': [], 'holdout': []}
    stats = {s: dict(games=0, dropped_no_block=0, captured=0, duplicate=0, over_cap=0, kept=0,
                     kept_per_arm={a: 0 for a in ARM_ORDER}, strata={}, student_default=0, fallback=0, plays=0) for s in sets}
    seen = {s: set() for s in sets}
    feature_seen, buckets = set(), {}
    for _, index, arm, pkl, phase in files:
        which = which_set(arm, index); st = stats[which]
        game_sha = authenticate_block(phase, arm, index)
        if game_sha is None:
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
        sets[which].append(dict(file=pkl, sha256=summary['sha256'], arm=arm, index=index, seed=summary['seed'], keep=keep,
                                game_sha256=game_sha, keep_sha256=sha_bytes(json.dumps(sorted(keep)).encode())))
    dup = {b: dict(states=v[0], feature_duplicates=v[1], rate=v[1]/v[0]) for b, v in sorted(buckets.items(), key=lambda x: int(x[0]))}
    io.write_json_once(str(out), dict(utc=utc(), schema='x4s4.label-plan.v4', caps=CAPS, allocation=ALLOC, c_base=C_BASE,
                       parity_receipt_sha256=sha_file(parity), parity_receipt=str(parity), parity_phases=phases,
                       parity_inventory_sha256=pr.get('inventory_sha256'), parity_passed=pr.get('passed'),
                       parity_exception=exception, order='arm K4S-120,S-200; index; tick',
                       dedup='sha256(row bytes)+root_digest (multiple determinizations kept)',
                       feature_only_duplicates_by_600_tick_bucket=dup, stats=stats, sets=sets), roles=('data',), mode=0o444)
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
    """Resume: re-verify an existing labeled game's complete seal inventory and receipt identity before skipping it."""
    try: seal, _ = io.verify_sealed_dir(final)
    except io.Refusal as e: raise RuntimeError(f'existing labeled game fails its seal: {final}: {e}')
    r = io.read_json(final+'/receipt.json', 16 << 20)
    want = dict(capture_sha256=entry['sha256'], plan_sha256=PLAN_SHA, keep_sha256=entry['keep_sha256'], teacher=TEACHER,
                search_threads=THREADS, seed=entry['seed'], index=entry['index'], arm=entry['arm'])
    bad = {k: (r.get(k), v) for k, v in want.items() if r.get(k) != v}
    if bad: raise RuntimeError(f'existing labeled game identity differs from the plan: {final}: {bad}')
    return r


def label_game(entry):
    from imitation.exit_r1.rows import seal
    out_root = f"{RAW}/{entry['arm']}"
    final = f"{out_root}/game-{entry['index']:04d}"
    io.check_writable(final, roles=('data',))
    base = dict(index=entry['index'], arm=entry['arm'], attempted=len(entry['keep']))
    if io.lexists(final+'/manifest.json'):
        r = verify_sealed(final, entry)
        return dict(base, status='already_sealed', rows=r['rows'], drops=r['drops'])
    if io.lexists(final): raise RuntimeError(f'unsealed labeled game directory present: {final}')
    why = halt_reason()
    if why: return dict(base, status=why)
    caps, summary = load_captures(entry['file'])
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
    io.mkdirs(out_root, roles=('data',))
    tmp = f"{out_root}/game-{entry['index']:04d}.tmp"
    if io.lexists(tmp): io.remove_tree(tmp, roles=('data',))          # our own confined temp; links never followed
    io.check_writable(tmp, roles=('data',), must_not_exist=True)
    receipt = dict(seed=entry['seed'], index=entry['index'], arm=entry['arm'], outcome=0, outcome_withheld=True,
                   rows=len(rows), root_decisions=len(rows), drops=drops, capture_sha256=entry['sha256'], plan_sha256=PLAN_SHA,
                   keep_sha256=entry['keep_sha256'], teacher=TEACHER, search_threads=THREADS,
                   cpu_seconds=time.process_time()-cpu0, wall_seconds=time.monotonic()-t0, host=socket.gethostname(),
                   label='X4S-4 on-policy labels, exploration, NEVER ADOPTABLE')
    seal(tmp, rows, score_rows, receipt)                                   # frozen writer into the validated fresh dir
    io.verify_sealed_dir(tmp)
    io.rename_path(tmp, final, roles=('data',))
    return dict(base, status='sealed', rows=len(rows), drops=drops, cpu_seconds=receipt['cpu_seconds'])


def pin():
    ident = multiprocessing.current_process()._identity[0]
    cores = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cores[(ident-1) % len(cores)]})


def stop_workers(me):
    """TERM then KILL this run's own verified worker PIDs (never the parent, never a pattern)."""
    io.stop_owned(me['pgid'], me['leader_start'], term_grace=30, kill_grace=30, exclude=(me['pid'],))


def dispatch(entries, workers, work, me, monitor=None, admit=None, poll=10.0):
    """Submit one entry per free worker. Before every submission the dispatch admission must hold (R3-F2: MemAvailable
    >= 24 GiB and PSI readable and <= 10 - this only DELAYS new work); between dispatches the parent runs the live
    guards (STOP, hard stop, memory, PSS, tree, disk), whose breach stops the workers. Returns (results, halted)."""
    monitor = monitor or (lambda: studytree.monitor(JOB, own=(me['pgid'], me['leader_start'])))
    admit = admit or studytree.dispatch_ok
    results, halted, inflight, todo = [], None, {}, list(entries)
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('fork'), initializer=pin) as pool:
        while todo or inflight:
            why = monitor()
            if why and not halted:
                halted = why; stop_workers(me); break
            while todo and len(inflight) < workers and admit()[0]:
                e = todo.pop(0); inflight[pool.submit(work, e)] = e
            if not inflight:
                time.sleep(poll); continue                         # gated: wait, keep monitoring
            done, _ = wait(list(inflight), timeout=poll, return_when=FIRST_COMPLETED)
            for f in done:
                inflight.pop(f)
                r = f.result()                                             # undeclared exceptions propagate
                results.append(r); print(json.dumps(r), flush=True)
    return results, halted


def run_labels(plan_path, which, workers, threads):
    global run, RAW, THREADS, PLAN_SHA
    if socket.gethostname() != '127x01' or os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise SystemExit('label run requires 127x01 at nice >= 10')
    if not os.sched_getaffinity(0) <= set(range(50)) or not 1 <= workers <= min(50, len(os.sched_getaffinity(0))):
        raise SystemExit('label run requires cores within 0-49 and 1 <= workers <= cores')
    if halt_reason(): raise SystemExit('halted before start: '+halt_reason())
    plan_path = str(plan_path)
    if plan_path != JOB+'/data/label-plan.json': raise SystemExit('plan must be <job>/data/label-plan.json')
    ok, why = studytree.admission(JOB, add=workers+1)
    if not ok: raise SystemExit('study admission: '+why)
    studytree.register(JOB, f'label-{which}')
    lead = io.proc_stat(os.getpgrp()); ident = io.own_identity()
    me = dict(pid=ident['pid'], pgid=ident['pgid'], leader_start=lead['starttime'] if lead else ident['starttime'])
    RAW, THREADS, PLAN_SHA = JOB+f'/data/raw-{which}', threads, sha_file(plan_path)
    plan = io.read_json(plan_path, 1 << 30)
    recheck_parity(plan)                                     # R3-F5: the parity chain still holds at labeling time
    sys.path.insert(0, str(HERE.parent/'x4s3'))
    import run as run_module
    run = run_module
    native = run.initialize()
    import torch; torch.set_num_threads(1)
    entries = [g for g in plan['sets'][which] if g['keep']]
    started = utc()
    results, halted = dispatch(entries, workers, label_game, me)
    finish(JOB+f'/data/label-receipt-{which}-{int(time.time())}.json', dict(
        summarize(results, len(entries)), started=started, finished=utc(), set=which, plan_sha256=PLAN_SHA, native=native,
        native_sha256=sha_file(native), threads=threads, workers=workers, halted=halted, label='X4S-4 exploration, NEVER ADOPTABLE'))


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
    """Write the run receipt (exclusive); a failed receipt exits 1 (Sol F5)."""
    io.write_json_once(str(path), body, roles=('data',), mode=0o444)
    if body['passed'] is not True: raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan'); p.add_argument('--phases', nargs='+', required=True); p.add_argument('--parity', required=True)
    p.add_argument('--out', required=True)
    r = sub.add_parser('run'); r.add_argument('--plan', required=True); r.add_argument('--set', choices=['O', 'holdout'], required=True)
    r.add_argument('--workers', type=int, required=True); r.add_argument('--threads', type=int, default=1)
    a = ap.parse_args()
    if a.cmd == 'plan': make_plan(a.phases, a.parity, a.out)
    else: run_labels(a.plan, a.set, a.workers, a.threads)


if __name__ == '__main__':
    main()
