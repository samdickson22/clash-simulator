"""X4S-4 offline synthetic tests (exploration, NEVER ADOPTABLE). Runs on 127x05 only; no host contact.

  /dev/shm/x4s4-venv/bin/python -B reports/explore/x4s4/test_x4s4_offline.py   (and with -O)

Synthetic fixtures under a fresh temp dir. torch is not installed offline, so the two torch-dependent imports
of imitation.exit_r1.rows (imitation.evaluation.d1, imitation.model.features) are stubbed; seal/pack/verify,
the real clasher BattleState/PlayerState/DiscreteTileActionSpace and the scripts' own logic are exercised
unchanged. Game-engine paths (capture payload on a live game, W scoring, the trainer) are qualification §6 on 01.
"""
import copy, hashlib, importlib, importlib.util, json, os, pickle, random, shutil, subprocess, sys, tempfile, types
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO), str(REPO/'src'), str(HERE)]
RESULTS = []


def case(name, ok, **info):
    RESULTS.append(dict(case=name, ok=bool(ok), **info)); print(json.dumps(RESULTS[-1], default=str), flush=True)


def stub_torch_imports():
    d1 = types.ModuleType('imitation.evaluation.d1'); d1.model_packet = lambda *a, **k: None
    ft = types.ModuleType('imitation.model.features'); ft.ENTITY_COLUMNS = [0, 1, 2]; ft.build_row = lambda *a, **k: {}
    sys.modules.setdefault('imitation.evaluation.d1', d1); sys.modules.setdefault('imitation.model.features', ft)


def load_patched(name, path, replacements):
    src = Path(path).read_text()
    for a, b in replacements:
        assert src.count(a) == 1, (name, a); src = src.replace(a, b)
    mod = types.ModuleType(name); mod.__file__ = str(path); sys.modules[name] = mod
    exec(compile(src, str(path), 'exec'), mod.__dict__)
    return mod


class Belief:
    def __init__(self): self.w = [0.5, 0.5]; self._pending = None


# ---------------------------------------------------------------- collect.py
def test_collect(tmp):
    import collect
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    r1 = collect.capture_rng('opponent', 4503606317370496, 100).random()
    r2 = collect.capture_rng('opponent', 4503606317370496, 100).random()
    r3 = collect.capture_rng('root', 4503606317370496, 100).random()
    r4 = collect.capture_rng('opponent', 4503606317370496, 110).random()
    case('capture_rng deterministic and domain-separated', r1 == r2 and len({r1, r3, r4}) == 3)
    collect.GuardedPickler.forbidden = (BattleState, PlayerState)
    try:
        collect.guarded_dumps(dict(a=[1, 2, {'x': PlayerState(player_id=1)}])); raised = False
    except collect.ForbiddenObject: raised = True
    case('persistent_id guard rejects a nested PlayerState', raised)
    try:
        collect.guarded_dumps(dict(state=BattleState())); raised = False
    except collect.ForbiddenObject: raised = True
    case('persistent_id guard rejects a BattleState', raised)
    case('persistent_id guard passes plain data', len(collect.guarded_dumps(dict(a=np.arange(3), b='x'))) > 0)

    # eligibility
    class Ch:
        def __init__(self, pending=()): self.pending = list(pending)
    belief = types.SimpleNamespace(_pending=None)
    base = dict(preparation_hit=False, stats=dict(hit=True), p=types.SimpleNamespace(belief=belief), candidates=[1, 2], ch=Ch())
    checks = [('preparation_cutoff', dict(preparation_hit=True)), ('preparation_cutoff', dict(stats=dict(hit=True, preparation_cutoff='sample'))),
              ('belief_pending', dict(p=types.SimpleNamespace(belief=types.SimpleNamespace(_pending=(1,))))),
              ('not_search', dict(candidates=[1])), ('not_search', dict(candidates=None)), ('pending_nonempty', dict(ch=Ch([object()]))), (None, {})]
    case('eligible() reasons', all(collect.eligible(dict(base, **ov)) == want for want, ov in checks))

    # fair-information permutation on a real BattleState
    b = BattleState(); b.players = [PlayerState(player_id=0), PlayerState(player_id=1)]; b.rng = random.Random(1)
    events = [types.SimpleNamespace(tick=10, kind='card', name='Knight', amount=0.)]
    b2, n = collect.permuted_battle(b, 0, events)
    opp, opp2 = b.players[1], b2.players[1]
    unrevealed_before = [c for c in list(opp.hand)+list(opp.cycle_queue) if c != 'Knight']
    unrevealed_after = [c for c in list(opp2.hand)+list(opp2.cycle_queue) if c != 'Knight']
    case('permutation moves only unrevealed cards, keeps the multiset, leaves the original intact',
         n == 7 and opp2.hand[0] == 'Knight' and unrevealed_after != unrevealed_before and sorted(unrevealed_after) == sorted(unrevealed_before)
         and opp.hand == ['Knight', 'Archer', 'Giant', 'Minions'] and b2.rng.random() != b.rng.random(), permuted=n)

    # capture() bookkeeping with a stub payload; install() on a stub run module
    out = tmp/'phase'; out.mkdir()
    run = types.ModuleType('run_stub'); run.OPTIONS = dict(out=str(out)); run.CAPTURE = None
    run.durable = lambda p: None
    run.run_game = lambda case_: dict(game=case_[0])
    collect._cfg = dict(nonhit_rate=0.25, all=True, verify_belief=True, fair_check=True)
    collect.install(run)

    def make_kw(tick, belief):
        bb = BattleState(); bb.players = [PlayerState(player_id=0), PlayerState(player_id=1)]; bb.tick = tick; bb.rng = random.Random(tick)
        return dict(seed=4503606337370496, pair=0, arm='K4S-long', spec=dict(deadline_seconds=1000., kernel='K4-anytime-sdefault'), b=bb,
                    actor=0, info=dict(tick=tick), reserved=None, policy=None, p=types.SimpleNamespace(belief=belief, core=None),
                    ch=Ch(), stats=dict(hit=False), action=2304, preparation_hit=False, candidates=[1, 2, 2304], opponent_events=[])
    variants = {
        'clean': lambda kw, b: dict(schema=collect.CAPTURE_SCHEMA, id=str(b.tick), tick=b.tick, row={'x': np.arange(2)},
                                    features_equal_student_input=True, row_equals_build_public=True, pending=(), stratum='all',
                                    stats=dict(student_default=False, fallback=False)),
        'reads_hidden_hand': lambda kw, b: dict(schema=collect.CAPTURE_SCHEMA, id=str(b.tick), tick=b.tick, leak=list(b.players[1].hand),
                                    features_equal_student_input=True, row_equals_build_public=True, pending=(), stratum='all',
                                    stats=dict(student_default=False, fallback=False)),
        'mutates_belief': lambda kw, b: (kw['p'].belief.w.append(1.0), dict(schema=collect.CAPTURE_SCHEMA, id=str(b.tick), tick=b.tick,
                                    features_equal_student_input=True, row_equals_build_public=True, pending=(), stratum='all',
                                    stats=dict(student_default=False, fallback=False)))[1],
        'drags_battle': lambda kw, b: dict(schema=collect.CAPTURE_SCHEMA, id=str(b.tick), tick=b.tick, battle=b,
                                    features_equal_student_input=True, row_equals_build_public=True, pending=(), stratum='all',
                                    stats=dict(student_default=False, fallback=False)),
    }
    original_payload = collect.payload
    outcomes = {}
    for name, fn in variants.items():
        collect.payload = fn; collect._captures.clear(); collect._counts.clear(); collect._checks.clear()
        try:
            for t in (100, 110):
                collect.capture(**make_kw(t, Belief()))
            outcomes[name] = dict(collect._checks)
        except collect.ForbiddenObject:
            outcomes[name] = 'ForbiddenObject'
    collect.payload = original_payload
    case('fair-information check: identical when the payload ignores hidden state', outcomes['clean'].get('fair_identical') == 2)
    case('fair-information check DETECTS a payload that reads the opponent hidden hand', outcomes['reads_hidden_hand'].get('fair_identical') == 0)
    case('belief-hash check: unchanged for a read-only capture', outcomes['clean'].get('belief_unchanged') == 2)
    case('belief-hash check DETECTS a capture that mutates the live belief', outcomes['mutates_belief'].get('belief_unchanged') == 0)
    case('Battle reference in a capture raises (C9 guard)', outcomes['drags_battle'] == 'ForbiddenObject')

    # run_game wrapper output
    collect.payload = variants['clean']; collect._cfg = dict(nonhit_rate=0.0, all=False, verify_belief=False, fair_check=False)

    def game(case_):
        for t, hit in ((100, True), (110, False), (120, True)):
            kw = make_kw(t, Belief()); kw['stats'] = dict(hit=hit); run.CAPTURE(**kw)
        kw = make_kw(130, Belief()); kw['candidates'] = [2304]; run.CAPTURE(**kw)
        return dict(game=case_[0])
    run2 = types.ModuleType('run_stub2'); run2.OPTIONS = dict(out=str(out)); run2.durable = lambda p: None; run2.run_game = game; run2.CAPTURE = None
    collect.install(run2)
    run2.run_game((7, 4503606317370503, 'K4S-120', None, None))
    summ = json.loads((out/'captures'/'sim-0007-d27-K4S-120.json').read_text())
    body = (out/'captures'/'sim-0007-d27-K4S-120.pkl').read_bytes()
    case('per-game capture file: SHA, counts (hit captured, non-hit unsampled at rate 0, single-candidate excluded)',
         hashlib.sha256(body).hexdigest() == summ['sha256'] and summ['captures'] == 2 and summ['counts'] == dict(captured=2, not_sampled=1, not_search=1),
         counts=summ['counts'])
    collect.payload = original_payload


# ---------------------------------------------------------------- label -> seal -> pack -> verify
def synth_row(seed, tick, k=3):
    rng = np.random.default_rng([seed % 2**32, tick])
    mask = np.zeros(2306, bool); mask[[5, 600, 2304]] = True
    return dict(hand_ids=rng.integers(1, 100, 4).astype(np.int16), global_features=rng.random(8).astype(np.float32),
                entity_counts=np.int16(k), flat_entity_ids=rng.integers(1, 50, k).astype(np.int16),
                flat_entity_levels=np.ones(k, np.int8), flat_entity_features=rng.random((k, 3)).astype(np.float32),
                packed_mask=np.packbits(mask))


def write_captures(phase, arm, index, seed, ticks, dup_of=None):
    caps = []
    for t in ticks:
        row = synth_row(seed if dup_of is None else dup_of, t)
        caps.append(pickle.dumps(dict(schema='x4s4.capture.v2', id=f'{arm}/{seed}/{t}', arm=arm, index=index, seed=seed, tick=t, seat=index % 2,
                                      row=row, features_equal_student_input=True, row_equals_build_public=True, pending=(),
                                      root_digest=f'd{seed if dup_of is None else dup_of}-{t}', stratum='hit', stats=dict(student_default=t % 20 == 0, fallback=False),
                                      info=None, opponent=None, root_rng_state=None, candidate_rng_state=None)))
    body = pickle.dumps(caps)
    d = phase/'captures'; d.mkdir(parents=True, exist_ok=True); (phase/'blocks').mkdir(exist_ok=True)
    (d/f'sim-{index:04d}-d27-{arm}.pkl').write_bytes(body)
    (d/f'sim-{index:04d}-d27-{arm}.json').write_text(json.dumps(dict(sha256=hashlib.sha256(body).hexdigest(), captures=len(caps), seed=seed)))
    (phase/'blocks'/f'{index:04d}.json').write_text('{}')


def test_pipeline(tmp):
    stub_torch_imports()
    import label, verify_onpolicy as V
    from imitation.exit_r1 import pack as packmod
    job = tmp/'job'; (job/'data').mkdir(parents=True); (job/'receipts').mkdir()
    label.JOB = job; V.JOB = job
    C, Cw, E = 4503606317370496, 4503606347370496, 4503606307370496
    phase_k, phase_s = tmp/'collect'/'K4S-120'/'a1', tmp/'collect'/'S-200'/'a1'
    for i in range(6): write_captures(phase_k, 'K4S-120', i, C+i, range(100, 160, 10))
    write_captures(phase_k, 'K4S-120', 6, C+6, range(100, 160, 10), dup_of=C+0)            # exact duplicates of game 0
    for i in range(2000, 2004): write_captures(phase_s, 'S-200', i, C+i, range(100, 140, 10))
    for i in (3500, 3501): write_captures(phase_k, 'K4S-120', i, C+i, range(100, 130, 10))    # O-holdout
    write_captures(phase_k, 'K4S-120', 9, C+9, range(100, 130, 10)); (phase_k/'blocks'/'0009.json').unlink()  # interrupted
    label.CAPS = {'K4S-120': 30, 'S-200': 1000}
    plan_path = tmp/'label-plan.json'
    label.make_plan([phase_k, phase_s], plan_path)
    lp = json.loads(plan_path.read_text()); st = lp['stats']
    case('label plan: holdout split, interruption drop, dedup, per-arm cap',
         st['O']['dropped_no_block'] == 1 and st['O']['duplicate'] == 6 and st['O']['kept_per_arm'] == {'K4S-120': 30, 'S-200': 16}
         and st['O']['over_cap'] == 6 and st['holdout']['kept'] == 6, stats={k: st['O'][k] for k in ('kept', 'duplicate', 'over_cap', 'dropped_no_block')})
    case('feature-only duplicate report by 600-tick bucket', lp['feature_only_duplicates_by_600_tick_bucket']['0']['feature_duplicates'] == 6)

    # labeling with a stubbed scorer (W scoring needs the engine: qualification on 01)
    def fake_score(info, opponent, rrs, crs, seed, digest=None):
        if digest == f'd{C+1}-110': raise LookupError('root digest mismatch')
        return 5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None]
    label.score_state = fake_score
    raw = tmp/'raw'; label.RAW = str(raw); label.THREADS = 1
    res = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    again = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    mism = sum(r.get('digest_mismatch', 0) for r in res); rows = sum(r['rows'] for r in res)
    case('labeling: digest mismatch dropped and counted; resume skips sealed games',
         mism == 1 and rows == 45 and all(r['status'] == 'already_sealed' for r in again))
    receipt = dict(set='O', passed=True, complete=True, rows=rows, digest_mismatch_rate=0.0)   # fixture within the 0.1% limit
    (tmp/'lr-O.json').write_text(json.dumps(receipt))
    ohdir = job/'data'/'onpolicy'; ohdir.mkdir()
    packmod.pack([raw/'K4S-120', raw/'S-200'], ohdir/'batch-0000')
    plan = json.loads((HERE/'plan.json').read_text()); (tmp/'plan.json').write_text(json.dumps(plan))
    V.O_MIN, V.O_MAX, V.ARM_CAPS = 10, 100, {'K4S-120': 30, 'S-200': 1000}
    rc = V.main(['--mode', 'O', '--plan', str(tmp/'plan.json'), '--label-receipts', str(tmp/'lr-O.json')])
    gate = job/'data'/'O-VERIFIED.json'
    sealed = all(not (p.stat().st_mode & 0o222) for p in (ohdir/'batch-0000').rglob('*') if p.is_file())
    case('verify O: passes, seals, writes the O gate', rc == 0 and gate.exists() and sealed)
    if rc: print((ohdir/'VERIFY-RECEIPT.json').read_text())
    # negatives on fresh copies
    def neg(name, mutate, mode='O', receipts=(tmp/'lr-O.json',), selection=None):
        j2 = tmp/('neg-'+name); shutil.copytree(job, j2, symlinks=True)
        for p in j2.rglob('*'):
            if p.is_file(): p.chmod(0o644)
        for g in ('O-VERIFIED.json', 'OW-VERIFIED.json'):
            if (j2/'data'/g).exists() and not (mode == 'OW' and g == 'O-VERIFIED.json'): (j2/'data'/g).unlink()
        for r_ in (j2/'data').rglob('VERIFY-RECEIPT.json'): r_.unlink()
        mutate(j2); V.JOB = j2
        args = ['--mode', mode, '--plan', str(tmp/'plan.json'), '--label-receipts', *map(str, receipts)]
        if selection: args += ['--selection', str(selection)]
        rc_ = V.main(args)
        body = json.loads(next((j2/'data').rglob('VERIFY-RECEIPT.json')).read_text())
        V.JOB = job
        return rc_, body.get('error', '')
    rc_, err = neg('rows-mismatch', lambda j: None, receipts=[tmp/'lr-bad.json']) if (tmp/'lr-bad.json').write_text(json.dumps(dict(receipt, rows=rows+1))) else (0, '')
    case('verify O rejects packed rows != label receipt rows', rc_ == 1 and 'label receipts rows' in err, error=err)
    rc_, err = neg('receipt-not-passed', lambda j: None, receipts=[tmp/'lr-np.json']) if (tmp/'lr-np.json').write_text(json.dumps(dict(receipt, passed=False))) else (0, '')
    case('verify O rejects a failed label receipt', rc_ == 1 and 'not passed' in err, error=err)
    rc_, err = neg('mismatch-rate', lambda j: None, receipts=[tmp/'lr-mm.json']) if (tmp/'lr-mm.json').write_text(json.dumps(dict(receipt, digest_mismatch_rate=mism/46))) else (0, '')
    case('verify O rejects a digest-mismatch rate above 0.1% (C6)', rc_ == 1 and 'not passed' in err, rate=round(mism/46, 4), error=err)
    V.O_MIN = 1000
    rc_, err = neg('below-min', lambda j: None)
    case('verify O rejects O below the gate minimum', rc_ == 1 and 'outside' in err, error=err)
    V.O_MIN = 10
    def add_link(j): os.symlink('/etc/passwd', j/'data'/'onpolicy'/'batch-0000'/'train'/'evil.npy')
    rc_, err = neg('symlink', add_link)
    case('verify O rejects a symlink inside a batch', rc_ == 1 and 'symlink' in err, error=err)

    # OW mode: emitter-like shards with non-root rows, in C' and one bad seed
    from imitation.exit_r1.rows import seal
    def ow_game(d, seed, n_roots, extra_rows=2, seed_override=None):
        rows, scores = [], []
        for t in range(n_roots+extra_rows):
            r = synth_row(seed, t); root = t < n_roots
            r.update(expert_actions=np.int16(2304), expert_action_supervision_valid=np.bool_(True), submitted_ticks=np.int32(t),
                     teacher_search_action=np.int16(2304), teacher_root=np.bool_(root), teacher_wait_kind=np.int8(0 if root else 1),
                     recorded_play_ticks=np.int32(-1), recorded_world_positions=np.array([np.nan, np.nan], np.float32),
                     submitted_world_positions=np.array([np.nan, np.nan], np.float32), recorded_millitiles=np.array([-1, -1], np.int32))
            rows.append(r); scores.append(dict(candidates=[5, 2304], scores=[.1, .2]) if root else dict(candidates=[], scores=[]))
        seal(d, rows, scores, dict(seed=seed_override or seed, outcome=1.0))
    owraw = tmp/'owraw'; owraw.mkdir()
    for g in range(4): ow_game(owraw/f'game-{g:05d}', Cw+g, 15)
    (job/'data'/'onpolicy-w').mkdir()
    packmod.pack([owraw], job/'data'/'onpolicy-w'/'batch-0000')
    o_rows = json.loads(gate.read_text())['rows']
    sel = tmp/'onpolicy-w-selection.json'
    sel.write_text(json.dumps(dict(reached=True, target_roots=o_rows, selected_games=list(range(4)), selected_roots=60, last_game_roots=15)))
    rc = V.main(['--mode', 'OW', '--plan', str(tmp/'plan.json'), '--selection', str(sel)])
    owr = json.loads((job/'data'/'onpolicy-w'/'VERIFY-RECEIPT.json').read_text())
    case('verify OW: roots counted by the RootTeacherStore rule (non-root rows ignored), within [|O|, |O|+last game]',
         rc == 0 and owr['roots'] == 60 and owr['rows'] == 68 and (job/'data'/'OW-VERIFIED.json').exists(), roots=owr.get('roots'), error=owr.get('error'))
    sel2 = tmp/'sel-over.json'; sel2.write_text(json.dumps(dict(json.loads(sel.read_text()), target_roots=o_rows, last_game_roots=2)))
    rc_, err = neg('ow-over', lambda j: None, mode='OW', receipts=(), selection=sel2)
    case('verify OW rejects roots above |O| + last game roots', rc_ == 1 and 'outside' in err, error=err)
    def c_seed(j):
        d = j/'data'/'onpolicy-w'; shutil.rmtree(d); d.mkdir(); r2 = tmp/'owraw-c'; shutil.rmtree(r2, ignore_errors=True); r2.mkdir()
        for g in range(4): ow_game(r2/f'game-{g:05d}', Cw+g, 15, seed_override=(C+g if g == 3 else None))
        packmod.pack([r2], d/'batch-0000')
    rc_, err = neg('ow-c-seed', c_seed, mode='OW', receipts=(), selection=sel)
    case('verify OW rejects a bank-C seed in O_W', rc_ == 1 and ('outside its bank' in err or 'collection-bank C' in err), error=err)


# ---------------------------------------------------------------- driver
def test_driver(tmp):
    job = tmp/'djob'; (job/'driver').mkdir(parents=True); (job/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    drv = load_patched('driver_t', HERE/'driver.py', [("J = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')", f"J = Path({str(job)!r})")])
    state = dict(fits={'R5': 'done', 'R5-rep': 'running', 'R5W': 'pending'}, ready={'R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W'}, done={})
    drv.fit_state = lambda f: (state['fits'][f], None)
    drv.ready_students = lambda: [s for s in drv.STUDENT_ORDER if s in state['ready']]
    drv.retired_set = lambda: (set(), {})
    drv.phase_status = lambda sid, arm, r: state['done'].get((sid, arm), set())
    for f in ('R5', 'R5-rep', 'R5W'): (job/f'rt-{f}').mkdir(); (job/f'rt-{f}'/'READY.json').write_text('{}')
    none_while_fit = drv.next_phase() is None
    state['fits'] = {k: 'done' for k in state['fits']}
    order = []
    full = set(range(drv.N))
    for _ in range(12):
        nx = drv.next_phase()
        if nx is None: break
        order.append(f'{nx[0]}/{nx[1]}'); state['done'][(nx[0], nx[1])] = full
    want = [f'{s}/{a}' for s in ('R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W') for a in ('K4S-120', 'S-200')]
    case('driver: no reporting phase while any fit is not done', none_while_fit)
    case('driver: ABBA order, all ten phases, no futility skip', order == want, order=order)
    src = (HERE/'driver.py').read_text()
    case('driver never reads a game outcome', "['loss']" not in src.replace("r['loss']", 'TRAINLOSS') or src.count("['loss']") == src.count("r = json.loads(line); losses.append(r['loss'])"))


# ---------------------------------------------------------------- contention
def write_game(phase, sid, arm, i, wall, end, loss=0.0):
    (phase/'games').mkdir(parents=True, exist_ok=True); (phase/'blocks').mkdir(exist_ok=True)
    g = phase/'games'/f'sim-{i:04d}-d27-{arm}.json'
    g.write_text(json.dumps(dict(loss=loss, wall_seconds=wall, search_ab=dict(deadline_stats=[dict(wall_seconds=0.1)]))))
    os.utime(g, (end, end)); (phase/'blocks'/f'{i:04d}.json').write_text('{}')


def test_contention(tmp):
    import contention
    job = tmp/'cjob'; (job/'receipts').mkdir(parents=True)
    import datetime
    t0 = datetime.datetime(2026, 10, 13, 10, 0, tzinfo=datetime.timezone.utc).timestamp()
    def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    for sid, capped in (('R3a', False), ('R5', True)):
        ph = job/'games'/sid/'K4S-120'/'a1'; ph.mkdir(parents=True)
        (ph/'launch.json').write_text(json.dumps(dict(workers=3 if capped else 10, lane_width=5)))
        census = [dict(utc=iso(t0+10*k), psi_some_avg10=(15.0 if (sid == 'R3a' and k == 5) else 0.0),
                       foreign_cores_host=(3.0 if (sid == 'R3a' and k == 9) else 0.5), reduced_concurrency=(sid == 'R3a' and k == 13)) for k in range(20)]
        (ph/'census.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in census))
        for i, (start, wall) in enumerate([(0, 20), (60, 15), (100, 5), (150, 20), (190, 5)]):
            write_game(ph, sid, 'K4S-120', i, wall, t0+start+wall, loss=1.0)
    sys.argv = ['contention.py', '--job', str(job)]; contention.main()
    r = json.loads((job/'receipts'/'contention-exclusion.json').read_text())
    case('contention: PSI, host-wide foreign CPU, yield window and a capped phase all flag; union over students',
         r['excluded_indices'] == [0, 1, 2, 3, 4] and r['capped_phases'] == ['games/R5/K4S-120/a1']
         and {b['psi'] > 10 or (b['foreign_cores'] or 0) > 2 or b['reduced_concurrency'] for b in r['bad_periods']} == {True}, excluded=r['excluded_indices'])
    seen = []
    orig = json.loads
    def spy(s, **kw):
        out = orig(s, **kw); seen.append(set(out)) if isinstance(out, dict) else None; return out
    contention.json.loads = spy
    w = contention.wall_only(job/'games'/'R3a'/'K4S-120'/'a1'/'games'/'sim-0000-d27-K4S-120.json')
    contention.json.loads = orig
    case('contention parses only wall_seconds from a game JSON', w == 20.0 and seen == [{'wall_seconds'}])
    try:
        sys.argv = ['contention.py', '--job', str(job)]; contention.main(); again = False
    except FileExistsError: again = True
    case('contention receipt is O_EXCL (frozen once)', again)


# ---------------------------------------------------------------- reducer + report
def test_reduce(tmp):
    red = load_patched('reduce_t', HERE/'reduce.py', [("E_BASE, E_COUNT = 4503606307370496, 1200", "E_BASE, E_COUNT = 4503606307370496, 60")])
    job = tmp/'rjob'; (job/'receipts').mkdir(parents=True); (job/'driver').mkdir()
    plan = json.loads((HERE/'plan.json').read_text()); plan['seed_ranges']['reporting'] = dict(base=4503606307370496, count=60)
    (job/'plan.json').write_text(json.dumps(plan))
    red.Path = Path
    students = ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']
    shas = {s: hashlib.sha256(s.encode()).hexdigest() for s in students}
    (job/'driver'/'retired.json').write_text(json.dumps(dict(indices=[3], why=[])))
    for s in students:
        if s != 'R3a': (job/f'rt-{s}').mkdir(); (job/f'rt-{s}'/'READY.json').write_text(json.dumps(dict(student=dict(checkpoint_sha256=shas[s]))))
    plan['student']['checkpoint_sha256'] = shas['R3a']; (job/'plan.json').write_text(json.dumps(plan))
    rng = random.Random(5)
    for s in students:
        for arm in ('K4S-120', 'S-200'):
            sp = plan['arms'][arm]; ph = job/'games'/s/arm/'a1'; (ph/'games').mkdir(parents=True); (ph/'blocks').mkdir()
            idx = [i for i in range(60) if i != 3 and not (s == 'R5W' and i >= 50)]
            (ph/'schedule.json').write_text(json.dumps(dict(range='reporting', cases=[[i, 0, arm] for i in idx])))
            for i in idx:
                p_loss = {'R3a': .30, 'R3a-rep': .30, 'R5': .15, 'R5-rep': .15, 'R5W': .25}[s]
                lose = rng.random() < p_loss; seat = i % 2; winner = (1-seat) if lose else seat
                width = 1 if sp['threads'] == 1 else 5
                ds = [dict(wall_seconds=.1, overrun_seconds=0.0, delayed_ticks=0, hit=True, fallback=False, student_default=False, action=2304, wall_overrun=False)]
                g = dict(loss=float(lose), cohort=arm, cpu_seconds=10.0, metadata=dict(seed=4503606307370496+i, arm=arm, terminal=True, opponent='v1-policy',
                         student_id=s, checkpoint_sha256=shas[s], study='X4S-3 exploration, NEVER ADOPTABLE', threads=sp['threads'], coarse_horizon=160,
                         budget_ms=round(sp['deadline_seconds']*1000), default_source=sp['default_source'], kernel=sp['kernel'], honest_lateness=True,
                         winner=winner, seat=seat, channel=dict(peak_pending=1), own_deck=['a'], opponent_deck=['b']),
                         search_ab=dict(worker_affinity=list(range(width)), nice=10, scheduler=0, host='127x01', worker_pid=1, gc_maintenance=[],
                                        policy_cache_counts=dict(forward=5, fallback=5), policy_polls={str(seat): 5}, latency_seconds=[.1], deadline_stats=ds))
                gp = ph/'games'/f'sim-{i:04d}-d27-{arm}.json'; gp.write_text(json.dumps(g))
                (ph/'blocks'/f'{i:04d}.json').write_text(json.dumps(dict(index=i, seed=4503606307370496+i, order=[arm], slot_cores=list(range(width)),
                                                                          worker_pid=1, games={gp.name: hashlib.sha256(gp.read_bytes()).hexdigest()})))
    red_args = ['--job', str(job), '--students', *students, '--out', str(tmp/'results.json')]
    # job has no base/ -> reducer reads HERE/plan.json; point it at the fixture plan instead
    red.__dict__['__file__'] = str(job/'x'/'reduce.py'); (job/'x').mkdir(); shutil.copy(job/'plan.json', job/'x'/'plan.json')
    sys.argv = ['reduce.py', *red_args]
    try: red.main(); no_receipt = False
    except SystemExit as e: no_receipt = 'contention receipt' in str(e)
    case('reducer refuses to run before the C5 receipt is frozen (E1)', no_receipt)
    (job/'receipts'/'contention-exclusion.json').write_text(json.dumps(dict(excluded_indices=[0, 1])))
    sys.argv = ['reduce.py', *red_args]
    try: red.main(); incomplete = False
    except SystemExit as e: incomplete = 'fixed N' in str(e)
    case('reducer refuses an incomplete student without --allow-prefix (fixed N)', incomplete)
    sys.argv = ['reduce.py', *red_args, '--allow-prefix']; red.main()
    r = json.loads((tmp/'results.json').read_text()); ro = r['readout']
    p = ro['primary']
    case('reducer: primary on the full primary prefix (R5W never cuts it), three-way outcome, sub-labels',
         r['paired_seeds'] == 59 and not r['truncation']['truncated'] and p['outcome'] in ('helps', 'no material effect', 'inconclusive')
         and 'fit_inflated_interval_pp' in p and 'harmful' in p and p['fit_inflated_interval_pp'][1]-p['fit_inflated_interval_pp'][0] > p['ci95_pp'][1]-p['ci95_pp'][0],
         outcome=p['label'], delta=round(p['point_pp'], 2))
    sw = ro['secondary_mean_R5_minus_R5W']
    case('reducer: R5W secondaries on R5W\'s own prefix with an attribution sub-label', sw['seeds'] == 49 and 'attribution' in sw, seeds=sw['seeds'], attribution=sw['attribution'])
    case('reducer: contention view excludes the frozen indices', ro['contention_sensitivity']['excluded_paired_seeds'] == 2)
    case('reducer: parity table disclosed with no exclusion semantics', all('gap_gt_2pp_disclosed' in v for v in ro['timing_parity'].values()))
    wr = load_patched('write_report_t', HERE/'write_report.py', [("HERE = Path(__file__).resolve().parent", f"HERE = Path({str(tmp)!r})")])
    sys.argv = ['write_report.py', json.dumps(dict(disclosures=['test']))]; wr.main()
    txt = (tmp/'RESULTS.md').read_text()
    case('write_report renders the primary, sub-labels, attribution and parity', 'Primary (pre-declared' in txt and 'Fit-inflated interval' in txt
         and 'Attribution (E4' in txt and 'Timing parity' in txt)


# ---------------------------------------------------------------- collect_w mapping, supervisor census, run_fit.sh
def test_misc(tmp):
    import collect_w
    collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
    ok = True
    for g in range(200):
        own, opp, seat, index, decks = collect_w.game_inputs(g)
        ok &= (decks[index % 8] == collect_w.X[g % 5] and decks[(index//8) % 8] == collect_w.X[(g//5) % 5] and index % 2 == g % 2
               and (own, opp, seat) == (g % 5, (g//5) % 5, g % 2))
    cells = {(g % 5, (g//5) % 5, g % 2) for g in range(50)}
    case('collect_w: emitter-derived (own, opponent, seat) equals the X4S mapping for g in 0..199; 50 cells', ok and len(cells) == 50)
    sup = load_patched('supervise_t', HERE/'supervise.py', [])
    j = tmp/'sjob'; (j/'receipts').mkdir(parents=True); (j/'driver').mkdir()
    (j/'driver'/'driver.pid').write_text(json.dumps(dict(pid=1, pgid=424242)))
    groups = sup.x4s4_pgids(j, 12345)
    first = sup.foreign_cores(j, 12345); import time; t = time.time()
    while time.time()-t < 0.3: sum(range(10000))
    second = sup.foreign_cores(j, os.getpgrp())
    case('supervisor: X4S-4 tree groups include driver/child/own; host-wide foreign CPU is a number', {424242, 12345, os.getpgrp()} <= groups
         and first is None and isinstance(second, float) and second >= 0, foreign=round(second, 3))
    fj = tmp/'fjob'; (fj/'data').mkdir(parents=True); (fj/'fit').mkdir()
    (fj/'data'/'O-VERIFIED.json').write_text(json.dumps(dict(batches=[dict(name='batch-0000'), dict(name='batch-0001')])))
    src = (HERE/'run_fit.sh').read_text().replace('J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy', f'J={fj}')
    src = src.replace('exec /mpac/sdicks02/envs/clasher-gpu/bin/python -B', 'printf "%s\\n"').replace('cd "$J/fit/source"', 'true')
    src = src.replace('EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d \' \' -f 1)', 'EXIT_LOADER_AMENDMENT_SHA256=x')
    (tmp/'rf.sh').write_text(src)
    out = subprocess.run(['bash', str(tmp/'rf.sh'), 'R5'], capture_output=True, text=True)
    roots = [l for l in out.stdout.split('\n') if l.endswith('/batch-0000') or l.endswith('/batch-0001')]
    bad = subprocess.run(['bash', str(tmp/'rf.sh'), 'R5W'], capture_output=True, text=True)
    case('run_fit.sh: R5 lists each O batch x4 with seed 2026101301; R5W refuses without the O_W gate',
         out.returncode == 0 and len(roots) == 8 and '2026101301' in out.stdout and bad.returncode != 0, rc=out.returncode)


def main():
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-test-', dir='/dev/shm'))
    try:
        for t in (test_collect, test_pipeline, test_driver, test_contention, test_reduce, test_misc):
            d = tmp/t.__name__; d.mkdir()
            try: t(d)
            except Exception as e:
                import traceback; traceback.print_exc(); case(t.__name__+' raised', False, error=repr(e))
    finally:
        for p in tmp.rglob('*'):
            if not p.is_symlink():
                try: p.chmod(0o755 if p.is_dir() else 0o644)
                except OSError: pass
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(r['ok'] for r in RESULTS)
    print(json.dumps(dict(all_ok=ok, cases=len(RESULTS), failed=[r['case'] for r in RESULTS if not r['ok']], python_optimize=sys.flags.optimize)))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
