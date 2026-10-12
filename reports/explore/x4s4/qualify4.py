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
      also pins each phase's schedule/launch/supervisor-exit SHAs (final evidence), re-derived by every consumer, and
      --bank smoke runs the same check on the collection smoke (PLAN §6.2); label admission accepts only bank C.
      Running collection is
      watched inside supervise.py (parity_once every 300 s; PARITY-PAUSE + STOP when out of band).
  roundtrip --phases DIR... --threads T --out R.json
      Every capture of the smoke collection (indices 0-7 x K4S-120/S-200), each game authenticated by its block proof,
      projected terminal metadata and capture identity: C8 triple + hash, empty pending, digest rebuild and repeat
      labeling identity.
  trainer   --packed DIR --assets FILE --out R.json      (clasher-gpu python, fit PYTHONPATH)
Receipts are confined below <job>/qual/ or <job>/receipts/ and created exclusively (0444). Any failed check exits 1.
"""
import argparse, hashlib, json, pickle, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io                              # noqa: E402

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


def all_captures(phases, label):
    """Every capture of the smoke collection; each game authenticated (proof SHA, projected terminal identity) and each
    capture file bound to its game's identity; the phases must cover indices 0-7 x K4S-120/S-200."""
    caps, seen = [], set()
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


BANKS = {'collection': C_BASE, 'smoke': SMOKE_BASE}


PERMITTED_PHASE_STOPS = ('memory_guard', 'console_user', 'owned_STOP', 'hard_stop_time', 'supervisor_SIGTERM', 'study_tree_cap', 'parity_pause')
COLLECT_ALLOC = {'K4S-120': ((0, 2000), (3500, 3750)), 'S-200': ((2000, 3500), (3750, 4000))}
BANK_RANGE = {'collection': 'reporting', 'smoke': 'smoke'}


def phase_evidence(phases, bank='collection'):
    """R3-F5/R4-F5: validated execution identity of every phase. schedule.json and launch.json must exist; the schedule
    is the bank's range with seeds base+index; a bank-C phase runs exactly one arm inside its allocation; schedule and
    launch name the same config, and all phases the same config; every block proof is a scheduled index. The exit is
    classified: absent -> 'running'; reason None and returncode 0 with no live group -> 'clean'; a declared guard stop
    (PERMITTED_PHASE_STOPS: an interruption whose incomplete captures are dropped) with no live group -> 'interrupted';
    anything else (e.g. returncode 17 with no reason) is an unexpected failure and refuses. The pinned record carries
    the three file SHAs plus this classification, and every consumer re-derives it."""
    base, want = BANKS[bank], BANK_RANGE[bank]
    ev, cfgs = {}, set()
    for p in sorted(map(str, phases)):
        for n in ('schedule.json', 'launch.json'):
            if not io.lexists(f'{p}/{n}'): raise QualError(f'{p}: {n} missing (no execution identity)')
        sched, launch = io.read_json(p+'/schedule.json', 16 << 20), io.read_json(p+'/launch.json', 4 << 20)
        if sched.get('range') != want: raise QualError(f"{p}: schedule range {sched.get('range')!r} is not the {bank} bank")
        cases = sched.get('cases') or []
        if not cases or any(c[1] != base+c[0] for c in cases): raise QualError(f'{p}: schedule seeds are not bank {bank} (base+index)')
        arms = sorted({c[2] for c in cases})
        if bank == 'collection':
            if len(arms) != 1 or arms[0] not in COLLECT_ALLOC: raise QualError(f'{p}: a collection phase runs exactly one arm')
            if any(not any(lo <= c[0] < hi for lo, hi in COLLECT_ALLOC[arms[0]]) for c in cases):
                raise QualError(f'{p}: indices outside the {arms[0]} bank-C allocation')
        if not sched.get('config_sha256') or sched.get('config_sha256') != launch.get('config_sha256'):
            raise QualError(f'{p}: schedule and launch name different configs')
        cfgs.add(sched['config_sha256'])
        scheduled = {c[0] for c in cases}
        blocks = sorted(int(n[:-5]) for n in io.listdir(p+'/blocks') if n.endswith('.json')) if io.lexists(p+'/blocks') else []
        if any(i not in scheduled for i in blocks): raise QualError(f'{p}: a block proof is not a scheduled index')
        if io.lexists(p+'/supervisor-exit.json'):
            ex = io.read_json(p+'/supervisor-exit.json', 4 << 20)
            if ex.get('remaining_group_pids'): raise QualError(f'{p}: the phase exited with live group members')
            if ex.get('reason') is None and ex.get('returncode') == 0: status = 'clean'
            elif ex.get('reason') in PERMITTED_PHASE_STOPS: status = 'interrupted'
            else: raise QualError(f"{p}: unexpected phase exit (reason={ex.get('reason')!r}, returncode={ex.get('returncode')!r})")
        else:
            status = 'running'
        ev[p] = {'schedule.json': io.sha256_file(p+'/schedule.json'), 'launch.json': io.sha256_file(p+'/launch.json'),
                 'supervisor-exit.json': io.sha256_file(p+'/supervisor-exit.json') if status != 'running' else None,
                 'status': status, 'config_sha256': sched['config_sha256'], 'arms': arms, 'scheduled': len(cases), 'proved': len(blocks)}
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
    t = sub.add_parser('trainer'); t.add_argument('--packed', required=True); t.add_argument('--assets', required=True)
    for p in (f, h, q, r, t): p.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    io.check_writable(a.out, roles=('qual', 'receipts'), must_not_exist=True)       # before any work
    if a.cmd == 'parity' and a.min_games < 1: raise SystemExit('--min-games must be >= 1')
    try:
        result = dict(frozen=frozen, hashes=hashes, parity=parity, roundtrip=roundtrip, trainer=trainer)[a.cmd](a)
    except (QualError, io.Refusal) as e:
        result = dict(passed=False, error=str(e))
    result.update(check=a.cmd, utc=utc(), label='X4S-4 qualification, exploration, NEVER ADOPTABLE')
    write_receipt(a.out, result); print(json.dumps({k: v for k, v in result.items() if k not in ('games', 'inventory')}))
    raise SystemExit(0 if result['passed'] is True else 1)


if __name__ == '__main__':
    main()
