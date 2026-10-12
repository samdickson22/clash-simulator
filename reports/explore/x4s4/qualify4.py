"""X4S-4 qualification (exploration, NEVER ADOPTABLE). Runs on 127x01 before any collection. r3 after Sol r2 (R2-F1, R2-F8).

Every read and write goes through x4s4io. Game JSONs are only ever PROJECTED to non-outcome fields (metadata.terminal/
seed/arm/budget_ms/checkpoint_sha256/opponent/seat, search_ab.command_sha256/deadline_stats hit/student_default/
wall_overrun); loss/winner/outcome are dropped while parsing.

  frozen    --corpus DIR --threads T --out R.json
      label.score_state reproduces the frozen screen8 reference action/candidates/scores on all 125 states.
  hashes    --run-phase DIR --collect-phase DIR --config plan-qual-capture.json --out R.json
      Inventory: both phases ran the qualification bank, indices 0-7, both qualification arms, with this config
      (1,000 s budgets, capture.all/verify_belief/fair_check on); every one of the 16 cases has a SHA-matching block
      proof AND its projected game metadata says terminal, the case's seed and arm, the 1,000 s budget and the
      config's student checkpoint (R2-F8: a proof alone is not a terminal guarantee under -O). Then command-hash
      equality, capture SHA/identity, parity flags, empty input pending, complete counts, unchanged live belief, fair
      invariance and fair coverage (>= 1 perturbed decision per game, >= 50% of early checks perturbed).
  parity    --phases DIR... --min-games N [--watch SECONDS] --out R.json
      C7b deadline-mode parity over the block-proved, SHA-verified, projected-terminal games of the phases. The receipt
      carries the exact game inventory (phase, game, SHA-256) and final = every phase has its supervisor-exit.json;
      passed requires final, both arms evaluated (>= N games each) and both in the +-2 pp band. label.py recomputes
      the inventory and refuses a receipt that no longer matches the phases (stale parity). r4 (R3-F5): the receipt
      also pins each phase's schedule/launch/supervisor-exit SHAs (final evidence), re-derived by every consumer (r6,
      R5-F3: case-level schedule/proof binding, full coverage for a clean exit, typed exit status), and
      --bank smoke runs the same check on the collection smoke (PLAN §6.2); label admission accepts only bank C.
      Running collection is
      watched inside supervise.py (parity_once every 300 s; PARITY-PAUSE + STOP when out of band).
  roundtrip --phases DIR... --threads T --out R.json
      Every capture of the smoke collection (indices 0-7 x K4S-120/S-200), each game authenticated by its block proof,
      projected terminal metadata and capture identity: C8 triple + hash, empty pending, digest rebuild and repeat
      labeling identity.
  smoke-pack --phases DIR... --threads T --out R.json      (r6, coordinator Q-D2(a))
      PLAN §6.5 input: every authenticated smoke capture is labelled by the unchanged label.label_game (frozen teacher,
      label thread count) under <job>/qual/smoke-raw, sealed, and packed once by the frozen pack() into the fresh
      <job>/qual/smoke-pack/batch-0000 (plan <job>/qual/smoke-plan.json); smoke bank only, never production data.
  trainer   --packed DIR --assets FILE --out R.json      (clasher-gpu python, fit PYTHONPATH)
r7 (Sol r6, R6-F2): every subcommand runs under QualGuard - study admission and registration before any work, the
frozen live rules on a watcher thread, halt checks between items, and a final STOP/deadline/breach check before the
receipt; a receipt never passes after a STOP, the deadline or a breach. R6-F3: smoke-pack fails on any digest mismatch.
Receipts are confined below <job>/qual/ or <job>/receipts/ and created exclusively (0444). Any failed check exits 1.
"""
import argparse, hashlib, json, os, pickle, secrets, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io                              # noqa: E402
import studytree                                 # noqa: E402

QUAL_BASE, SMOKE_BASE, C_BASE = 4503606337370496, 4503606327370496, 4503606317370496
QUAL_ARMS, COLLECT_ARMS = ('K4S-long', 'S-long'), ('K4S-120', 'S-200')
INDICES = list(range(8))
EARLY_PERTURBED_MIN = 0.5
X4S3_R3A = {'K4S-120': dict(cutoff=64.2, student_default=22.3, overrun=0.16), 'S-200': dict(cutoff=75.3, student_default=0.0, overrun=0.14)}
GAME_KEEP = ('metadata', 'terminal', 'seed', 'arm', 'budget_ms', 'checkpoint_sha256', 'opponent', 'seat', 'search_ab',
             'command_sha256', 'deadline_stats', 'hit', 'student_default', 'wall_overrun')


class QualError(Exception):
    pass


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def write_receipt(path, obj, roles=('qual', 'receipts')):
    io.write_json_once(str(path), obj, roles=roles, mode=0o444)
    return str(path)


GUARD_PERIOD, GUARD_GRACE = 5.0, 60.0
QUAL_PROCESSES = 2
GPU_ADMIT_MIB, GPU_LIMIT_MIB = 8*1024, 40*1024                # the fit rules (driver.py), for the trainer check


def gpu_used_mib():
    try:
        r = io.run_checked(['/usr/bin/nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], 20, 4096,
                           env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
        v = int(r.stdout.split()[0]); return v if v >= 0 else None
    except (io.Refusal, ValueError, IndexError):
        return None


class QualHalt(Exception):
    pass


class QualGuard:
    """R6-F2: every qualification subcommand is owned, admitted and live-guarded like production work.
    * admit(): no STOP (lexists), the immutable hard stop not reached, MemAvailable >= 24 GiB with memory PSI readable
      and <= 10 (studytree.dispatch_ok - dispatch inhibition only), the study tree + this job <= 70 processes and the
      job <= 100 GB (studytree.admission); then the process group is registered (receipts/cpujob-qual-*) so every other
      admission counts it.
    * A watcher thread applies the frozen running-work rules every GUARD_PERIOD s (studytree.monitor: STOP, hard stop,
      MemAvailable < 24 GiB or unreadable, PSI unreadable, own PSS > 50 GiB or unreadable, study process/disk caps; high
      PSI is NOT a kill rule). A breach is latched; the work checks check() between items and stops with QualHalt. If
      the work does not reach a check within GUARD_GRACE s (a long native call), the watcher itself writes the failed
      receipt and ends the process (os._exit(3)).
    * finalize(): STOP, deadline and the latched breach are checked once more immediately before the receipt is
      written; any of them turns the result into passed=false. A qualification receipt therefore never passes after a
      STOP, the deadline or a breach.
    The GPU step (trainer) additionally uses the fit rules: admitted only with the GPU readable and <= 8 GiB used;
    stopped if it becomes unreadable or exceeds 40 GB."""
    def __init__(self, job, name, out, gpu=False):
        self.job, self.name, self.out, self.gpu = job, name, str(out), gpu
        self.halt, self.halt_at, self.finalized = None, None, False
        self.lock, self.done = threading.Lock(), threading.Event()
        self.exit = os._exit
        self.thread = None

    def quick(self):
        if io.lexists(self.job+'/STOP'): return 'owned_STOP'
        if studytree.hard_stop_passed(self.job): return 'hard_stop_time'
        return None

    def admit(self):
        why = self.quick()
        if why: raise QualHalt('admission: '+why)
        ok, why = studytree.dispatch_ok()
        if not ok: raise QualHalt('admission: '+why)
        ok, why = studytree.admission(self.job, QUAL_PROCESSES)
        if not ok: raise QualHalt('admission: '+why)
        if self.gpu:
            g = gpu_used_mib()
            if g is None or g > GPU_ADMIT_MIB: raise QualHalt(f'admission: GPU unreadable or {g} MiB already used')
        studytree.register(self.job, f'qual-{self.name}-{secrets.token_hex(3)}')
        me = io.own_identity(); lead = io.proc_stat(me['pgid'])
        self.own = (me['pgid'], lead['starttime'] if lead else me['starttime'])
        self.thread = threading.Thread(target=self._watch, daemon=True); self.thread.start()

    def poll(self):
        """One live-guard evaluation (the watcher's step); latches and returns the breach."""
        if self.halt is None:
            why = studytree.monitor(self.job, own=self.own)
            if why is None and self.gpu:
                g = gpu_used_mib()
                if g is None or g > GPU_LIMIT_MIB: why = 'gpu_unreadable_or_over_40GB'
            if why: self.halt, self.halt_at = why, time.monotonic()
        return self.halt

    def _watch(self):
        while not self.done.wait(GUARD_PERIOD):
            try: self.poll()
            except Exception as exc:                                      # a failing monitor is itself a breach
                if self.halt is None: self.halt, self.halt_at = f'monitor_failed: {exc!r}', time.monotonic()
            if self.halt is not None and time.monotonic()-self.halt_at >= GUARD_GRACE: self.expire()

    def expire(self):
        """The work did not acknowledge a breach in time: record the failure and end this process."""
        with self.lock:
            if self.finalized: return
            self.finalized = True
            try: write_receipt(self.out, dict(passed=False, check=self.name, utc=utc(), error=f'qualification halted: {self.halt} '
                                              f'(no acknowledgement within {GUARD_GRACE:.0f} s)', label='X4S-4 qualification, exploration, NEVER ADOPTABLE'))
            finally: self.exit(3)

    def reason(self):
        return self.halt or self.quick()

    def check(self):
        why = self.reason()
        if why: raise QualHalt(f'qualification halted: {why}')

    def finalize(self, result):
        """Final STOP/deadline/breach check immediately before the receipt is written; returns the receipt body."""
        with self.lock:
            if self.finalized: return None
            self.finalized = True; self.done.set()
            why = self.reason()
            if why and result.get('passed') is True:
                result = dict(result, passed=False, error=f'qualification halted: {why}')
            if why: result['halted'] = why
            write_receipt(self.out, result)
            return result


GUARD = None                                         # the running subcommand's QualGuard (main)


def guard_check():
    if GUARD is not None: GUARD.check()


def game_meta(path):
    """Projected, outcome-free view of a runner game JSON."""
    return io.project_json(str(path), GAME_KEEP)


def proved_game(phase, i, arm, base, budget_ms=None, checkpoint=None):
    """(path, sha256) of a block-proved game whose projected metadata is terminal with the case's identity."""
    phase = str(phase)
    bp = f'{phase}/blocks/{i:04d}.json'
    if not io.lexists(bp): raise QualError(f'{phase}: index {i} has no block proof')
    proof = io.read_json(bp, 1 << 20)
    if proof.get('index') != i or proof.get('seed') != base+i or arm not in proof.get('order', []):
        raise QualError(f'{phase}: block proof {i} identity')
    g = f'{phase}/games/sim-{i:04d}-d27-{arm}.json'
    if not io.lexists(g): raise QualError(f'{phase}: {i} {arm} game missing')
    digest = io.sha256_file(g)
    if proof.get('games', {}).get(f'sim-{i:04d}-d27-{arm}.json') != digest: raise QualError(f'{phase}: {i} {arm} differs from its block proof')
    m = game_meta(g).get('metadata', {})
    if not (m.get('terminal') is True and m.get('seed') == base+i and m.get('arm') == arm):
        raise QualError(f'{phase}: {i} {arm} is not a terminal game of this case (terminal={m.get("terminal")!r})')
    if budget_ms is not None and m.get('budget_ms') != budget_ms: raise QualError(f'{phase}: {i} {arm} budget {m.get("budget_ms")}')
    if checkpoint is not None and m.get('checkpoint_sha256') != checkpoint: raise QualError(f'{phase}: {i} {arm} student checkpoint differs')
    return g, digest


def init_label(threads):
    sys.path.insert(0, str(HERE.parent/'x4s3'))
    import run, label
    native = run.initialize()
    import torch; torch.set_num_threads(1)
    label.run, label.THREADS = run, threads
    return run, label, native


def frozen(a):
    run, label, native = init_label(a.threads)
    rows = pickle.loads(io.read_bytes(str(a.corpus)+'/states-ready.pkl', 1 << 30))
    refs = {r['id']: r for r in io.read_json(str(a.corpus)+'/symmetric-screen-samples.json', 1 << 30)
            if r['variant'] == 'screen8' and r['repeat'] == 0}
    bad = []
    for row in rows:
        guard_check()                                                    # R6-F2: halts between states
        action, cands, scores = label.score_state(row['info'], row['opponent'], row['root_rng_state'],
                                                  row['candidate_rng_state'], row['seed'], row['root_digest'])
        ref = refs[row['id']]
        if not (action == ref['action'] and cands == ref['candidates'] and scores == ref['scores']): bad.append(row['id'])
    return dict(states=len(rows), equal=len(rows)-len(bad), mismatches=bad, threads=a.threads, native=native,
                passed=len(rows) == 125 and not bad)


def phase_inventory(phase, rng, base, arms, budget_ms=None, checkpoint=None):
    """The phase ran exactly indices 0-7 x arms of the named bank; every case proved, terminal and of its identity."""
    sched = io.read_json(f'{phase}/schedule.json', 16 << 20)
    if sched['range'] != rng or sched['indices'] != INDICES: raise QualError(f'{phase}: range/indices must be {rng} 0-7')
    cases = {(c[0], c[2]) for c in sched['cases']}
    if cases != {(i, arm) for i in INDICES for arm in arms} or any(c[1] != base+c[0] for c in sched['cases']):
        raise QualError(f'{phase}: schedule must hold every index 0-7 x {arms} at bank base {base}')
    return {(i, arm): proved_game(phase, i, arm, base, budget_ms, checkpoint)[0] for i in INDICES for arm in arms}, sched


def check_config(path):
    cfg = io.read_json(str(path), 4 << 20)
    ok = (sorted(cfg['arms']) == sorted(QUAL_ARMS) and all(cfg['arms'][k]['deadline_seconds'] == 1000.0 for k in QUAL_ARMS)
          and cfg['seed_ranges']['qualification'] == dict(base=QUAL_BASE, count=8)
          and all(cfg['capture'].get(k) is True for k in ('all', 'verify_belief', 'fair_check')))
    if not ok: raise QualError('qualification config must be the 1,000 s capture-all config with both checks on')
    return io.sha256_file(str(path)), cfg['student']['checkpoint_sha256']


def hashes(a):
    cfg_sha, ck = check_config(a.config)
    rgames, rsched = phase_inventory(a.run_phase, 'qualification', QUAL_BASE, QUAL_ARMS, 1000000, ck)
    cgames, csched = phase_inventory(a.collect_phase, 'qualification', QUAL_BASE, QUAL_ARMS, 1000000, ck)
    if not (rsched['config_sha256'] == csched['config_sha256'] == cfg_sha): raise QualError('both phases must run the given config')
    same_sched = rsched['cases'] == csched['cases']
    rows, ok = [], same_sched and len(rgames) == len(cgames) == 16
    for key in sorted(rgames):
        gr, gc = game_meta(rgames[key]), game_meta(cgames[key])
        name = Path(cgames[key]).name
        pkl = f'{a.collect_phase}/captures/{name[:-5]}.pkl'
        summ = io.read_json(pkl[:-4]+'.json', 16 << 20)
        sha_ok = io.sha256_file(pkl) == summ['sha256']
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
        row = dict(game=name, equal=gr['search_ab']['command_sha256'] == gc['search_ab']['command_sha256'], capture_sha_ok=sha_ok,
                   identity_ok=summ.get('identity_ok') is True and summ['index'] == key[0] and summ['arm'] == key[1] and summ['seed'] == QUAL_BASE+key[0],
                   features_equal_all=summ['features_equal_all'], public_equal_all=summ['public_equal_all'],
                   pending_empty_all=summ['pending_empty_all'], captures=summ['captures'], decisions=decisions, counts=counts,
                   count_ok=count_ok, checks=chk, belief_unchanged=belief_ok, fair_invariant=fair_ok, fair_coverage=coverage_ok)
        ok &= all(row[k] is True for k in ('equal', 'capture_sha_ok', 'identity_ok', 'features_equal_all', 'public_equal_all',
                                           'pending_empty_all', 'count_ok', 'belief_unchanged', 'fair_invariant', 'fair_coverage'))
        rows.append(row)
    return dict(same_schedule=same_sched, config_sha256=cfg_sha, cases=len(rows), games=rows, passed=bool(ok))


def smoke_games(phases, label):
    """[(phase, index, arm, capture file, captures, summary)] of the smoke collection: each game authenticated (proof
    SHA, projected terminal identity) and each capture file bound to its game's identity; the phases must cover
    indices 0-7 x K4S-120/S-200 exactly once."""
    games, seen = [], set()
    for phase in map(str, phases):
        sched = io.read_json(f'{phase}/schedule.json', 16 << 20)
        if sched['range'] != 'smoke': raise QualError(f'{phase}: round trip runs on the smoke collection')
        for c in sched['cases']:
            i, arm = c[0], c[2]
            if c[1] != SMOKE_BASE+i: raise QualError(f'{phase}: case {i} seed outside the smoke bank')
            proved_game(phase, i, arm, SMOKE_BASE)
            got, summary = label.load_captures(f'{phase}/captures/sim-{i:04d}-d27-{arm}.pkl')
            if not (summary['seed'] == SMOKE_BASE+i and summary['index'] == i and summary['arm'] == arm and summary.get('identity_ok') is True
                    and all(x['seed'] == SMOKE_BASE+i and x['index'] == i and x['arm'] == arm for x in got)):
                raise QualError(f'{phase}: capture identity of {i} {arm}')
            if (i, arm) in seen: raise QualError(f'{phase}: smoke case {i} {arm} appears twice')
            games.append((phase, i, arm, f'{phase}/captures/sim-{i:04d}-d27-{arm}.pkl', got, summary)); seen.add((i, arm))
    if seen != {(i, arm) for i in INDICES for arm in COLLECT_ARMS}: raise QualError('smoke captures must cover 0-7 x K4S-120/S-200')
    return games


def all_captures(phases, label):
    """Every capture of the authenticated smoke collection (smoke_games)."""
    return [c for g in smoke_games(phases, label) for c in g[4]]


SMOKE_RAW, SMOKE_PLAN, SMOKE_BATCH = 'qual/smoke-raw', 'qual/smoke-plan.json', 'qual/smoke-pack/batch-0000'


def smoke_pack_into(phases, label, pack):
    """Q-D2(a), PLAN §6.5 input: label EVERY authenticated smoke capture (smoke bank only; never production data) with
    the unchanged label.label_game (frozen teacher at label.THREADS), seal each game under <job>/qual/smoke-raw, and
    pack once with the frozen pack() into the fresh <job>/qual/smoke-pack/batch-0000, which `trainer` then re-verifies
    and opens. All three destinations must not exist (no resume).
    r7 (R6-F2): the labeler's halt hook is the qualification guard (STOP, hard stop, latched live breach); the guard is
    checked before and after every game, immediately before the pack, by the packer's per-source guard callback, and
    after the pack; any halt fails the check (a batch packed before a halt is never accepted).
    r7 (R6-F3): strict accounting - every game attempted == rows + drops; any digest mismatch fails; `no_rows` passes
    only when its captures were all dropped for having no scored root. Returns the receipt body."""
    J = io.JOB
    raw, plan_path, batch = f'{J}/{SMOKE_RAW}', f'{J}/{SMOKE_PLAN}', f'{J}/{SMOKE_BATCH}'
    for p in (raw, plan_path, batch): io.check_writable(p, roles=('qual',), must_not_exist=True)
    entries = []
    for phase, i, arm, pkl, got, summary in smoke_games(phases, label):
        keep = sorted(c['id'] for c in got)
        entries.append(dict(file=pkl, sha256=summary['sha256'], arm=arm, index=i, seed=summary['seed'], keep=keep, phase=phase,
                            keep_sha256=hashlib.sha256(json.dumps(keep).encode()).hexdigest()))
    guard_check()
    io.write_json_once(plan_path, dict(utc=utc(), schema='x4s4.smoke-label-plan.v1', phases=sorted(map(str, phases)),
                                       threads=label.THREADS, entries=entries,
                                       label='X4S-4 smoke trainer-compatibility labels, exploration, NEVER ADOPTABLE'),
                       roles=('qual',), mode=0o444)
    label.RAW, label.PLAN_SHA, label.DATA_ROLE = raw, io.sha256_file(plan_path), 'qual'
    if GUARD is not None: label.halt_reason = GUARD.reason       # the worker's halt hook = the qualification guard
    body = dict(phases=sorted(map(str, phases)), games=len(entries), captures=sum(len(e['keep']) for e in entries),
                threads=label.THREADS, plan=plan_path, plan_sha256=label.PLAN_SHA, raw=raw, packed=batch, passed=False)
    results = []
    for e in entries:
        guard_check()
        r = label.label_game(e); results.append(r)
        if r['status'] not in ('sealed', 'no_rows'): break          # stopped / hard stop / breach: no further game
        guard_check()                                               # after every final label result
    statuses, drops = {}, {}
    for r in results:
        statuses[r['status']] = statuses.get(r['status'], 0)+1
        for k, v in (r.get('drops') or {}).items(): drops[k] = drops.get(k, 0)+v
    rows = sum(r.get('rows', 0) for r in results)
    body.update(statuses=statuses, rows=rows, drops=drops, attempted=sum(r.get('attempted', 0) for r in results))
    bad = [f"{r['arm']}/{r['index']}" for r in results if r.get('rows', 0)+sum((r.get('drops') or {}).values()) != r.get('attempted')]
    if len(results) != len(entries) or set(statuses) - {'sealed', 'no_rows'}:
        body['error'] = f'labelling did not finish every smoke game: {statuses}'; return body
    if bad: body['error'] = f'incomplete attempted/row/drop accounting: {bad}'; return body
    if drops.get('digest_mismatch'):
        body['error'] = f"{drops['digest_mismatch']} digest mismatches (smoke reconstruction must be 100%)"; return body
    if set(drops) - {'no_scored_root'}: body['error'] = f'undeclared drop reasons {sorted(drops)}'; return body
    if not statuses.get('sealed') or body['attempted'] != body['captures']:
        body['error'] = 'no sealed smoke game, or not every capture attempted'; return body
    guard_check()                                                    # immediately before the pack
    def pack_guard():
        from imitation.exit_r1.pack import check_memory
        check_memory(); guard_check()                                # frozen floor + the qualification guard, per source
    pack([f'{raw}/{arm}' for arm in COLLECT_ARMS], batch, memory_guard=pack_guard)
    guard_check()                                                    # a batch packed across a halt is not accepted
    _, manifest_sha = io.verify_sealed_dir(batch)
    body.update(packed_manifest_sha256=manifest_sha, passed=True)
    return body


def smoke_pack(a):
    run, label, native = init_label(a.threads)
    from imitation.exit_r1.pack import pack
    return dict(smoke_pack_into(a.phases, label, pack), native=native)


def roundtrip_check(caps, score):
    """Pure check over every capture; score(*args) returns (action, candidates, scores) or raises LookupError."""
    mism, unequal, fields_missing = 0, 0, 0
    for cap in caps:
        guard_check()                                                    # R6-F2: halts between captures
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


BANKS = {'collection': C_BASE, 'smoke': SMOKE_BASE}


# R5-F3: the child statuses a declared guard stop can produce: 0 (the runner finished as the guard fired), -SIGTERM /
# -SIGKILL (the supervisor's verified-PID teardown) and 1 (Python's exit after its pool workers were stopped first).
INTERRUPTED_RETURNCODES = (0, 1, -15, -9)
PERMITTED_PHASE_STOPS = ('memory_guard', 'console_user', 'owned_STOP', 'hard_stop_time', 'supervisor_SIGTERM', 'study_tree_cap', 'parity_pause')
COLLECT_ALLOC = {'K4S-120': ((0, 2000), (3500, 3750)), 'S-200': ((2000, 3500), (3750, 4000))}
BANK_RANGE = {'collection': 'reporting', 'smoke': 'smoke'}


def phase_evidence(phases, bank='collection'):
    """R3-F5/R4-F5/R5-F3: validated execution identity of every phase.
    * schedule.json and launch.json must exist and name the same config (all phases one config);
    * the schedule is the bank's range; its cases are unique (index, seed, arm) triples with seed base+index, the
      case indices are exactly the declared sorted unique `indices`, and every index has the same arm set (a bank-C
      phase: exactly one arm, inside its allocation);
    * every block proof is bound to one scheduled index: proof index/seed equal the case, its `order` is exactly that
      index's scheduled arms and its `games` names exactly those cases;
    * the exit is typed: `reason`, `returncode` and `remaining_group_pids` (a list) must all be present, the list empty.
      'clean' = reason None, returncode 0 and FULL coverage (every scheduled index proved, complete_blocks equal);
      'interrupted' = a declared guard stop (PERMITTED_PHASE_STOPS) with a returncode in INTERRUPTED_RETURNCODES, whose
      unproved indices are recorded as dropped; no exit -> 'running'; anything else refuses (e.g. returncode 17, a
      reason-only exit, a clean exit with missing cases).
    The pinned record carries the three file SHAs plus this classification, and every consumer re-derives it."""
    base, want = BANKS[bank], BANK_RANGE[bank]
    ev, cfgs = {}, set()
    for p in sorted(map(str, phases)):
        for n in ('schedule.json', 'launch.json'):
            if not io.lexists(f'{p}/{n}'): raise QualError(f'{p}: {n} missing (no execution identity)')
        sched, launch = io.read_json(p+'/schedule.json', 16 << 20), io.read_json(p+'/launch.json', 4 << 20)
        if sched.get('range') != want: raise QualError(f"{p}: schedule range {sched.get('range')!r} is not the {bank} bank")
        cases, indices = sched.get('cases') or [], sched.get('indices')
        if not (isinstance(indices, list) and indices and all(type(i) is int and i >= 0 for i in indices) and indices == sorted(set(indices))):
            raise QualError(f'{p}: schedule indices are not a sorted unique list')
        if any(not isinstance(c, list) or len(c) < 3 or type(c[0]) is not int or type(c[1]) is not int or not isinstance(c[2], str) for c in cases):
            raise QualError(f'{p}: malformed schedule case')
        if not cases or any(c[1] != base+c[0] for c in cases): raise QualError(f'{p}: schedule seeds are not bank {bank} (base+index)')
        keys = [(c[0], c[2]) for c in cases]
        if len(set(keys)) != len(keys): raise QualError(f'{p}: duplicate scheduled case')
        by_index = {}
        for i, arm in keys: by_index.setdefault(i, set()).add(arm)
        if sorted(by_index) != indices: raise QualError(f'{p}: scheduled cases do not cover exactly the declared indices')
        arms = sorted({arm for _, arm in keys})
        if any(v != set(arms) for v in by_index.values()): raise QualError(f'{p}: indices scheduled with different arm sets')
        if bank == 'collection':
            if len(arms) != 1 or arms[0] not in COLLECT_ALLOC: raise QualError(f'{p}: a collection phase runs exactly one arm')
            if any(not any(lo <= i < hi for lo, hi in COLLECT_ALLOC[arms[0]]) for i in indices):
                raise QualError(f'{p}: indices outside the {arms[0]} bank-C allocation')
        if not sched.get('config_sha256') or sched.get('config_sha256') != launch.get('config_sha256'):
            raise QualError(f'{p}: schedule and launch name different configs')
        cfgs.add(sched['config_sha256'])
        names = sorted(n for n in io.listdir(p+'/blocks') if n.endswith('.json')) if io.lexists(p+'/blocks') else []
        proved = []
        for n in names:
            try: i = int(n[:-5])
            except ValueError: raise QualError(f'{p}: block proof name {n!r}')
            if n != f'{i:04d}.json' or i not in by_index: raise QualError(f'{p}: block proof {n} is not a scheduled index')
            proof = io.read_json(f'{p}/blocks/{n}', 1 << 20)
            order = proof.get('order')
            if proof.get('index') != i or proof.get('seed') != base+i: raise QualError(f'{p}: block proof {n} identity is not its scheduled case')
            if not isinstance(order, list) or len(order) != len(set(order)) or set(order) != by_index[i]:
                raise QualError(f'{p}: block proof {n} arms {order!r} are not the scheduled arms {sorted(by_index[i])}')
            if set(proof.get('games') or {}) != {f'sim-{i:04d}-d27-{arm}.json' for arm in order}:
                raise QualError(f'{p}: block proof {n} games are not exactly its scheduled cases')
            proved.append(i)
        dropped = sorted(set(indices)-set(proved))
        if io.lexists(p+'/supervisor-exit.json'):
            ex = io.read_json(p+'/supervisor-exit.json', 4 << 20)
            if not all(k in ex for k in ('reason', 'returncode', 'remaining_group_pids')) or not isinstance(ex['remaining_group_pids'], list):
                raise QualError(f'{p}: incomplete exit evidence (reason, returncode and remaining_group_pids are required)')
            rc, reason = ex['returncode'], ex['reason']
            if ex['remaining_group_pids']: raise QualError(f'{p}: the phase exited with live group members')
            if reason is None and rc == 0 and type(rc) is int:
                if dropped or ex.get('complete_blocks', len(proved)) != len(proved):
                    raise QualError(f'{p}: clean exit but {len(dropped)} scheduled indices have no block proof')
                status = 'clean'
            elif reason in PERMITTED_PHASE_STOPS and type(rc) is int and rc in INTERRUPTED_RETURNCODES:
                status = 'interrupted'
            else: raise QualError(f"{p}: unexpected phase exit (reason={reason!r}, returncode={rc!r})")
        else:
            status = 'running'
        ev[p] = {'schedule.json': io.sha256_file(p+'/schedule.json'), 'launch.json': io.sha256_file(p+'/launch.json'),
                 'supervisor-exit.json': io.sha256_file(p+'/supervisor-exit.json') if status != 'running' else None,
                 'status': status, 'config_sha256': sched['config_sha256'], 'arms': arms, 'scheduled': len(indices),
                 'proved': len(proved), 'dropped': len(dropped)}
    if len(cfgs) > 1: raise QualError('the phases ran different configs')
    return ev


def parity_inventory(phases, base=C_BASE):
    """[(phase, game name, sha256)] of every block-proved, SHA-verified, projected-terminal game of the bank."""
    inv = []
    for phase in sorted(map(str, phases)):
        bdir = phase+'/blocks'
        if not io.lexists(bdir): continue
        for n in io.listdir(bdir):
            if not n.endswith('.json'): continue
            i = int(n[:-5])
            proof = io.read_json(f'{bdir}/{n}', 1 << 20)
            for arm in proof.get('order', []):
                g, digest = proved_game(phase, i, arm, base)
                inv.append([phase, Path(g).name, digest])
    return inv


def parity_once(phases, min_games, require_both=True, bank='collection'):
    agg = {}
    inv = parity_inventory(phases, BANKS[bank])
    for phase, name, digest in inv:
        arm = name[:-5].split('-d27-')[1]
        ds = game_meta(f'{phase}/games/{name}')['search_ab']['deadline_stats']      # timing metadata only
        t = agg.setdefault(arm, dict(decisions=0, cutoff=0, student_default=0, overrun=0, games=0))
        t['games'] += 1; t['decisions'] += len(ds); t['cutoff'] += sum(bool(d.get('hit')) for d in ds)
        t['student_default'] += sum(bool(d.get('student_default')) for d in ds); t['overrun'] += sum(bool(d.get('wall_overrun')) for d in ds)
    rows = {}
    for arm, t in agg.items():
        if arm not in X4S3_R3A: raise QualError(f'unknown collection arm {arm}')
        pct = {k: 100*t[k]/max(1, t['decisions']) for k in ('cutoff', 'student_default', 'overrun')}
        ref = X4S3_R3A[arm]; within = {k: abs(pct[k]-ref[k]) <= 2.0 for k in pct}
        rows[arm] = dict(games=t['games'], decisions=t['decisions'], pct=pct, x4s3_r3a=ref, within_2pp=within, evaluated=t['games'] >= min_games)
    enough = all(arm in rows and rows[arm]['evaluated'] for arm in X4S3_R3A)
    out_of_band = sorted(arm for arm, r in rows.items() if r['evaluated'] and not all(r['within_2pp'].values()))
    return dict(arms=rows, band_pp=2.0, min_games=min_games, both_arms_evaluated=enough, out_of_band=out_of_band,
                bank=bank, inventory=inv, inventory_sha256=hashlib.sha256(json.dumps(inv).encode()).hexdigest(),
                passed=bool((enough or not require_both) and not out_of_band))


def pause(job, res):
    """C7b: record the out-of-band reading and stop collection (STOP is honoured by every X4S-4 worker)."""
    rec = write_receipt(f"{job}/receipts/PARITY-PAUSE-{utc().replace(':', '')}.json",
                        dict({k: v for k, v in res.items() if k != 'inventory'}, utc=utc(),
                             reason='C7b parity band exceeded; collection paused; the coordinator decides (explicit PARITY-EXCEPTION)'),
                        roles=('receipts',))
    io.create_stop(job)
    return rec


def parity(a):
    phases = [str(p) for p in a.phases]
    while True:
        res = parity_once(phases, a.min_games, bank=a.bank)
        if res['out_of_band']:
            res['paused'] = pause(io.JOB, res); break
        final = all(io.lexists(p+'/supervisor-exit.json') for p in phases)
        if not a.watch or final: break
        if io.lexists(io.JOB+'/STOP'): res['stopped_by_STOP'] = True; break
        guard_check()
        time.sleep(a.watch)
    res['phases'] = sorted(phases)
    res['evidence'] = phase_evidence(phases, a.bank)
    res['final'] = all(e['status'] != 'running' for e in res['evidence'].values())
    res['passed'] = bool(res['passed'] and res['final'])
    return res


def trainer(a):
    """R3-F3: the packed smoke batch must lie under <job>/qual and re-verify completely; the assets must match the
    RUNTIME-INVENTORY pin; only then does the frozen loader open them."""
    import numpy as np
    from exit_r3.student import RootTeacherStore, teacher_targets
    packed = str(a.packed)
    if not packed.startswith(io.JOB+'/qual/'): raise QualError('the packed smoke batch must lie under <job>/qual/')
    _, manifest_sha = io.verify_sealed_dir(packed)
    inv = io.read_json(io.JOB+'/RUNTIME-INVENTORY.json', 4 << 20)
    if io.sha256_file(str(a.assets)) != inv.get('inputs/assets.npz'): raise QualError('assets differ from RUNTIME-INVENTORY')
    guard_check()
    store = RootTeacherStore(packed, a.assets)
    n = len(store); rows = len(store.arrays['teacher_root'])
    b, y = store.batch(np.arange(min(64, n)))
    q = teacher_targets(y, .003)
    finite = bool(np.isfinite(q.numpy()).all()) and bool((abs(q.sum(-1).numpy()-1) < 1e-5).all())
    return dict(rows=rows, roots=n, all_rows_roots=n == rows, batch=int(len(y['action'])), targets_finite_normalized=finite,
                packed_manifest_sha256=manifest_sha, passed=n == rows and n > 0 and finite)


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('frozen'); f.add_argument('--corpus', required=True); f.add_argument('--threads', type=int, default=1)
    h = sub.add_parser('hashes'); h.add_argument('--run-phase', required=True); h.add_argument('--collect-phase', required=True)
    h.add_argument('--config', required=True)
    q = sub.add_parser('parity'); q.add_argument('--phases', nargs='+', required=True)
    q.add_argument('--min-games', type=int, required=True); q.add_argument('--watch', type=int, default=0)
    q.add_argument('--bank', choices=sorted(BANKS), default='collection', help='smoke: PLAN §6.2 deadline parity on the collection smoke')
    r = sub.add_parser('roundtrip'); r.add_argument('--phases', nargs='+', required=True); r.add_argument('--threads', type=int, default=1)
    s = sub.add_parser('smoke-pack', help='Q-D2(a): label + seal + pack the smoke captures into <job>/qual/smoke-pack/batch-0000')
    s.add_argument('--phases', nargs='+', required=True); s.add_argument('--threads', type=int, default=1)
    t = sub.add_parser('trainer'); t.add_argument('--packed', required=True); t.add_argument('--assets', required=True)
    for p in (f, h, q, r, s, t): p.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    io.check_writable(a.out, roles=('qual', 'receipts'), must_not_exist=True)       # before any work
    if a.cmd == 'parity' and a.min_games < 1: raise SystemExit('--min-games must be >= 1')
    global GUARD
    GUARD = QualGuard(io.JOB, a.cmd, a.out, gpu=a.cmd == 'trainer')                                          # R6-F2: owned, admitted, guarded
    try:
        GUARD.admit()
        result = {'frozen': frozen, 'hashes': hashes, 'parity': parity, 'roundtrip': roundtrip, 'smoke-pack': smoke_pack,
                  'trainer': trainer}[a.cmd](a)
    except (QualError, QualHalt, io.Refusal) as e:
        result = dict(passed=False, error=str(e))
    result.update(check=a.cmd, utc=utc(), label='X4S-4 qualification, exploration, NEVER ADOPTABLE')
    try:
        final = GUARD.finalize(result)
    finally:
        GUARD = None
    if final is None: raise SystemExit(3)                             # the watcher already failed this check
    print(json.dumps({k: v for k, v in final.items() if k not in ('games', 'inventory')}))
    raise SystemExit(0 if final['passed'] is True else 1)


if __name__ == '__main__':
    main()
