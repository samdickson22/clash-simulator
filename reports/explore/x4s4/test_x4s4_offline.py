"""X4S-4 offline synthetic tests (exploration, NEVER ADOPTABLE). r2 after Sol script review r1 (F18). 127x05 only; no host contact.

  /dev/shm/x4s4-venv/bin/python -B reports/explore/x4s4/test_x4s4_offline.py   (and with -O, -OO)

Synthetic fixtures under a fresh temp dir in /dev/shm. torch is not installed offline, so the two torch-dependent imports
of imitation.exit_r1.rows are stubbed; seal/pack/verify, the real clasher BattleState/PlayerState/DiscreteTileActionSpace
and the scripts' own logic are exercised unchanged. Every Sol r1 probe has a discriminating fixture here (named
"F<n> probe"); each negative is paired with a positive control so a vacuous check cannot pass. The only engine-dependent
paths left to qualification §6 on 01 are real W scoring, the native frozen references, real command hashes and the trainer.
"""
import ast, contextlib, copy, datetime, hashlib, importlib, json, os, pickle, random, shutil, stat, subprocess, sys, tempfile, time, types
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO), str(REPO/'src'), str(HERE)]
RESULTS = []
C, CW, E, SMOKE, QUAL = 4503606317370496, 4503606347370496, 4503606307370496, 4503606327370496, 4503606337370496
BASELINE_RUN_SHA = 'e7f90d76f7603973b72c2e4a9ee0fc733727fddcb97b795b887f63a7b7c7a543'   # x4s3/run.py at c86d928d


def case(name, ok, **info):
    RESULTS.append(dict(case=name, ok=bool(ok), **info)); print(json.dumps(RESULTS[-1], default=str), flush=True)


def raises(fn, exc=BaseException, text=''):
    try: fn()
    except exc as e: return text in str(e) or text in repr(e)
    return False


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wjson(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj)); return p


def stub_torch_imports():
    d1 = types.ModuleType('imitation.evaluation.d1'); d1.model_packet = lambda *a, **k: None
    ft = types.ModuleType('imitation.model.features'); ft.ENTITY_COLUMNS = [0, 1, 2]; ft.build_row = lambda *a, **k: {}
    sys.modules.setdefault('imitation.evaluation.d1', d1); sys.modules.setdefault('imitation.model.features', ft)


def load_patched(name, path, replacements):
    src = Path(path).read_text()
    for a, b in replacements:
        if src.count(a) != 1: raise RuntimeError((name, a))
        src = src.replace(a, b)
    mod = types.ModuleType(name); mod.__file__ = str(path); sys.modules[name] = mod
    exec(compile(src, str(path), 'exec'), mod.__dict__)
    return mod


def use_job(job):
    """Point every module's canonical job root at a synthetic job (confine checks at call time)."""
    import confine
    confine.JOB = Path(job)
    for m in ('label', 'collect_w', 'verify_onpolicy'):
        if m in sys.modules: sys.modules[m].JOB = Path(job)
    return Path(job)


def new_job(tmp, name='job'):
    job = tmp/name
    for d in ('data', 'receipts', 'driver', 'analysis', 'qual', 'collect', 'games', 'logs'): (job/d).mkdir(parents=True, exist_ok=True)
    (job/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    return use_job(job)


class StubBelief:
    def __init__(self): self.w = [0.5, 0.5]; self._pending = None
    def sample(self, rng): return dict(hand=['h%d' % int(rng.integers(100)) for _ in range(4)])


# ================================================================ confine (F10)
def test_confine(tmp):
    import confine
    job = new_job(tmp)
    (tmp/'outside').mkdir(); os.symlink(tmp/'outside', job/'data'/'link')
    probes = {'relative path': 'data/x', 'parent traversal': str(job)+'/data/../../x', 'outside the job': str(tmp/'outside'/'x'),
              'role not allowed': str(job/'fits'/'x'), 'symlinked ancestor': str(job/'data'/'link'/'x')}
    bad = {k: raises(lambda v=v: confine.writable(v, roles=('data',)), confine.ConfinementError) for k, v in probes.items()}
    (job/'data'/'f').write_text('x'); os.symlink(job/'data'/'f', job/'data'/'lf')
    bad['symlink target'] = raises(lambda: confine.writable(str(job/'data'/'lf'), roles=('data',)), confine.ConfinementError)
    bad['must_not_exist'] = raises(lambda: confine.writable(str(job/'data'/'f'), roles=('data',), must_not_exist=True), confine.ConfinementError)
    good = confine.writable(str(job/'data'/'new'/'deep.json'), roles=('data',)) == job/'data'/'new'/'deep.json'
    made = confine.mkdirs(str(job/'data'/'a'/'b'), roles=('data',)).is_dir()
    case('F10 probe: confine rejects relative, .., outside-root, wrong role, symlink ancestor/target, existing; accepts a fresh path',
         all(bad.values()) and good and made, rejected=bad)


# ================================================================ run_collect / collect (F1, F2, F3, F13)
def test_runner_identity(tmp):
    import collect
    base = (HERE.parent/'x4s3'/'run.py').read_text()
    case('reused evaluation runner x4s3/run.py is byte-identical to c86d928d', hashlib.sha256(base.encode()).hexdigest() == BASELINE_RUN_SHA)
    import difflib
    diff = [l for l in difflib.ndiff(base.splitlines(), (HERE/'run_collect.py').read_text().splitlines()) if l[:2] in ('- ', '+ ')]
    removed = [l for l in diff if l.startswith('- ')]; added = [l[2:].strip() for l in diff if l.startswith('+ ')]
    want_calls = ['if CAPTURE is not None:', 'if CAPTURE_END is not None:', 'CAPTURE = CAPTURE_END = None', 'CAPTURE_END(pair=pair, seed=seed, arm=arm)']
    case('run_collect.py = x4s3/run.py + only the two explicit hooks (no removed line, no run_game change)',
         not removed and len(added) == 9 and all(any(a.startswith(w) for a in added) for w in want_calls)
         and all(a.startswith(('#', 'if CAPTURE', 'CAPTURE', 'policy=', 'candidates=')) for a in added), added=len(added))

    # F1 probe: the inherited nested inference_check (exact AST from run_collect.py, asserts made explicit so the probe
    # is valid under -O) must keep finding run_game's own frame after collect.install().
    tree = ast.parse((HERE/'run_collect.py').read_text())
    rg = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_game')
    guard = next(n for n in ast.walk(rg) if isinstance(n, ast.FunctionDef) and n.name == 'inference_check')

    class Explicit(ast.NodeTransformer):
        def visit_Assert(self, node):
            return ast.If(test=ast.UnaryOp(op=ast.Not(), operand=node.test), body=[ast.Raise(exc=ast.Call(
                func=ast.Name('AssertionError', ast.Load()), args=[], keywords=[]), cause=None)], orelse=[])
    guard = ast.fix_missing_locations(Explicit().visit(copy.deepcopy(guard)))
    body = [ast.parse('wall0 = time.monotonic()').body[0], guard, ast.parse("return CAPTURE_PROBE(inference_check)").body[0]]
    fn = ast.FunctionDef(name='run_game', args=ast.arguments(posonlyargs=[], args=[ast.arg('case')], kwonlyargs=[], kw_defaults=[], defaults=[]),
                         body=body, decorator_list=[], returns=None, type_params=[])
    mod_ast = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    m = types.ModuleType('runner_probe')
    m.__dict__.update(time=time, sys=sys, WINDOW=types.SimpleNamespace(active=True), CAPTURE=None, CAPTURE_END=None,
                      CAPTURE_PROBE=lambda check: (check(), 'ok')[1])
    exec(compile(mod_ast, 'runner_probe', 'exec'), m.__dict__)
    original = m.run_game
    collect.install(m)
    after = m.run_game is original and m.run_game(None) == 'ok'

    def r1_wrapper(case_):                       # the rejected r1 integration: a module-global wrapper
        t0 = time.monotonic()
        return original(case_)
    m.run_game = r1_wrapper
    control = raises(lambda: m.run_game(None), AssertionError)
    case('F1 probe: inference_check passes through the collection install (run_game identity kept); the r1 wrapper fails it',
         after and control and m.CAPTURE is collect.capture and m.CAPTURE_END is collect.capture_end)


def make_kw(tick, actor=0, belief=None, input_pending=(), submitted=(), hit=False, action=2304, candidates=(1, 2, 2304)):
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    b = BattleState(); b.players = [PlayerState(player_id=0), PlayerState(player_id=1)]; b.tick = tick; b.rng = random.Random(tick)
    return dict(seed=SMOKE, pair=0, arm='K4S-120', spec=dict(deadline_seconds=0.12, kernel='K4-anytime-sdefault'), b=b, actor=actor,
                info=dict(tick=tick), reserved=types.SimpleNamespace(packet=[1.0, 2.0, float(tick)]),
                policy=types.SimpleNamespace(player=types.SimpleNamespace(last_d1={'d': 1}), mask=np.ones(4, bool)),
                p=types.SimpleNamespace(belief=belief or StubBelief(), core=types.SimpleNamespace(pending=tuple(input_pending), opponent_elixir=5.0)),
                ch=types.SimpleNamespace(pending=list(submitted)), stats=dict(hit=hit), action=action, preparation_hit=False,
                candidates=list(candidates), opponent_events=[types.SimpleNamespace(tick=10, kind='card', name='Knight', amount=0.)])


@contextlib.contextmanager
def engine_stubs():
    """Stub engine/model modules for the REAL collect.payload: R.builder/R.root/costs and the row builders."""
    saved = {k: sys.modules.get(k) for k in ('imitation.exit_r1.rows', 'imitation.model.features', 'imitation.evaluation.d1')}
    rows = types.ModuleType('imitation.exit_r1.rows')
    rows.observation = lambda packet, mask, d1, builder: {'p': np.asarray(packet, np.float64), 'm': np.asarray(mask)}
    rows.feature_bytes = lambda row, costs: {'p': row['p']}
    ft = types.ModuleType('imitation.model.features'); ft.build_row = lambda packet, d1, costs: {'p': np.asarray(packet, np.float64)}
    d1 = types.ModuleType('imitation.evaluation.d1'); d1.model_packet = lambda packet, mask: packet
    sys.modules.update({'imitation.exit_r1.rows': rows, 'imitation.model.features': ft, 'imitation.evaluation.d1': d1})

    class Root:
        def __init__(self, info, opp, rng): self.d = hashlib.sha256(repr((info, opp, float(rng.random()))).encode()).hexdigest()
        def digest(self): return self.d
    builder = types.SimpleNamespace(token_id=lambda name, namespace=None: 3,
                                    build_public=lambda b, actor: [1.0, 2.0, float(b.tick)])
    run = types.ModuleType('run_stub')
    run.R = types.SimpleNamespace(builder=builder, costs={'Knight': 3}, root=Root)
    try: yield run
    finally:
        for k, v in saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v


def test_collect(tmp):
    import collect
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    job = new_job(tmp)
    r1 = collect.capture_rng('opponent', C, 100).random(); r2 = collect.capture_rng('opponent', C, 100).random()
    r3 = collect.capture_rng('root', C, 100).random(); r4 = collect.capture_rng('opponent', C, 110).random()
    case('capture_rng deterministic and domain-separated', r1 == r2 and len({r1, r3, r4}) == 3)
    collect.GuardedPickler.forbidden = (BattleState, PlayerState)
    case('persistent_id guard rejects a nested PlayerState and a BattleState; passes plain data',
         raises(lambda: collect.guarded_dumps(dict(a=[1, {'x': PlayerState(player_id=1)}])), collect.ForbiddenObject)
         and raises(lambda: collect.guarded_dumps(dict(s=BattleState())), collect.ForbiddenObject)
         and len(collect.guarded_dumps(dict(a=np.arange(3)))) > 0)

    # F2 probe: the runner submits the play before the hook, so ch.pending holds it; eligibility uses the INPUT pending.
    play = make_kw(100, hit=True, action=5, submitted=[object()])
    wait = make_kw(100, hit=True, action=2304)
    suspended = make_kw(100, hit=True, action=5, input_pending=[object()], submitted=[object()])
    case('F2 probe: a play whose own command is in ch.pending is eligible; WAIT eligible; a non-empty INPUT transaction is rejected',
         collect.eligible(play) is None and collect.eligible(wait) is None and collect.eligible(suspended) == 'pending_nonempty_input')
    others = [('preparation_cutoff', dict(preparation_hit=True)), ('preparation_cutoff', dict(stats=dict(hit=True, preparation_cutoff='s'))),
              ('belief_pending', dict(p=types.SimpleNamespace(belief=types.SimpleNamespace(_pending=(1,)), core=types.SimpleNamespace(pending=())))),
              ('not_search', dict(candidates=[1])), ('not_search', dict(candidates=None))]
    case('eligible(): preparation, suspended belief and single-candidate exclusions', all(collect.eligible(dict(wait, **ov)) == w for w, ov in others))

    # fair-information permutation on a real BattleState
    b = make_kw(100)['b']
    b2, moved = collect.permuted_battle(b, 0, make_kw(100)['opponent_events'])
    opp, opp2 = b.players[1], b2.players[1]
    before = [c for c in list(opp.hand)+list(opp.cycle_queue) if c != 'Knight']; after = [c for c in list(opp2.hand)+list(opp2.cycle_queue) if c != 'Knight']
    case('permutation moves only unrevealed cards, keeps the multiset and leaves the original intact',
         moved >= 2 and opp2.hand[0] == 'Knight' and after != before and sorted(after) == sorted(before)
         and b2.rng.random() != random.Random(100).random(), moved=moved)

    # F3 probe: the REAL payload, fair_check substituting kw['b'] in every path; negative controls read hidden hand,
    # cycle and future battle RNG through kw['b'] (the path the r1 harness left unperturbed).
    real_payload = collect.payload
    variants = {'real payload': real_payload,
                'reads hidden hand via kw[b]': lambda kw: dict(real_payload(kw), leak=list(kw['b'].players[1-kw['actor']].hand)),
                'reads hidden cycle via kw[b]': lambda kw: dict(real_payload(kw), leak=list(kw['b'].players[1-kw['actor']].cycle_queue)),
                'reads future battle RNG via kw[b]': lambda kw: dict(real_payload(kw), leak=kw['b'].rng.random()),
                'mutates the live belief': lambda kw: (kw['p'].belief.w.append(1.0), real_payload(kw))[1],
                'drags the battle': lambda kw: dict(real_payload(kw), battle=kw['b'])}
    out, caps_by = {}, {}
    with engine_stubs() as run_stub:
        collect.run = run_stub; collect._cfg = dict(nonhit_rate=0.25, all=True, verify_belief=True, fair_check=True)
        for name, fn in variants.items():
            collect.payload = fn; collect._captures.clear(); collect._counts.clear(); collect._checks.clear()
            try:
                for t in (100, 110):
                    collect.capture(**make_kw(t, hit=True, action=5, submitted=[object()]))
                out[name] = dict(collect._checks); caps_by[name] = list(collect._captures)
            except collect.ForbiddenObject:
                out[name] = 'ForbiddenObject'
        collect.payload = real_payload
        cap = pickle.loads(caps_by['real payload'][0]) if caps_by.get('real payload') else None
    real = out['real payload']
    case('F3 probe: the real payload is byte-identical under the permutation, with cards actually moved (early-game coverage)',
         real.get('fair_identical') == 2 and real.get('fair_checked') == 2 and real.get('fair_perturbed_decisions') == 2
         and real.get('fair_perturbed_early') == 2, checks=real)
    case('F3 probe: hidden hand, hidden cycle and future-RNG reads through kw[b] are each DETECTED',
         all(out[k].get('fair_identical') == 0 for k in ('reads hidden hand via kw[b]', 'reads hidden cycle via kw[b]', 'reads future battle RNG via kw[b]')))
    case('C7a/C9: live-belief mutation detected; a Battle reference raises the graph guard',
         out['mutates the live belief'].get('belief_unchanged') == 0 and real.get('belief_unchanged') == 2 and out['drags the battle'] == 'ForbiddenObject')
    case('real payload stores the C8 triple with its SHA, empty input pending and an explicit play (F2 play retained)',
         cap is not None and cap['pending'] == () and cap['agent_action'] == 5 and cap['opponent_elixir'] == 5.0
         and cap['c8_sha256'] == hashlib.sha256(pickle.dumps((cap['reserved_packet'], cap['opponent_elixir'], cap['pending']),
                                                             protocol=pickle.HIGHEST_PROTOCOL)).hexdigest())

    # per-game capture file through the installed hooks, confined below the job (F10)
    phase = job/'collect'/'K4S-120'/'a1'; phase.mkdir(parents=True)
    rs = types.ModuleType('run_stub2'); rs.OPTIONS = dict(out=str(phase)); rs.durable = lambda p: None; rs.run_game = lambda c: c
    rs.CAPTURE = rs.CAPTURE_END = None
    collect._cfg = dict(nonhit_rate=0.0, all=False, verify_belief=False, fair_check=False)
    with engine_stubs() as run_stub:
        rs.R = run_stub.R; collect.install(rs)
        for t, hit, act in ((100, True, 5), (110, False, 2304), (120, True, 2304)):
            kw = make_kw(t, hit=hit, action=act, submitted=[object()] if act < 2304 else []); kw['pair'] = 7; kw['seed'] = C+7
            rs.CAPTURE(**kw)
        kw = make_kw(130, candidates=[2304]); kw['pair'] = 7; kw['seed'] = C+7; rs.CAPTURE(**kw)
        rs.CAPTURE_END(pair=7, seed=C+7, arm='K4S-120')
    summ = json.loads((phase/'captures'/'sim-0007-d27-K4S-120.json').read_text())
    body = (phase/'captures'/'sim-0007-d27-K4S-120.pkl').read_bytes()
    case('per-game capture file: SHA, identity, counts (hit play and hit WAIT captured, non-hit unsampled, single-candidate excluded)',
         hashlib.sha256(body).hexdigest() == summ['sha256'] and summ['captures'] == 2 and summ['plays_captured'] == 1 and summ['identity_ok']
         and summ['counts'] == dict(captured=2, not_sampled=1, not_search=1), counts=summ['counts'])
    rs.OPTIONS = dict(out=str(tmp/'elsewhere')); (tmp/'elsewhere').mkdir()
    case('F10 probe: capture output outside the job is refused', raises(lambda: rs.CAPTURE_END(pair=8, seed=C+8, arm='K4S-120'), Exception, 'outside'))

    # F13: bank-C allocation is enforced at collection launch
    cfg = HERE/'plan-collect.json'
    def alloc(arms, idx, rng='reporting'):
        (tmp/'idx.json').write_text(json.dumps(idx))
        return lambda: collect.check_allocation(['collect.py', '--config', str(cfg), '--out', 'x', '--workers', '1', '--indices',
                                                 str(tmp/'idx.json'), '--range', rng, '--arms', *arms])
    ok = alloc(['K4S-120'], [0, 1999, 3500, 3749])() is None and alloc(['S-200'], [2000, 3499, 3750, 3999])() is None
    case('F13 probe: collection allocation: K4S-120 index 2500, S-200 index 100, two arms and K4S-120 holdout 3750 are refused',
         ok and raises(alloc(['K4S-120'], [2500]), SystemExit) and raises(alloc(['S-200'], [100]), SystemExit)
         and raises(alloc(['K4S-120', 'S-200'], [0]), SystemExit) and raises(alloc(['K4S-120'], [3750]), SystemExit)
         and alloc(['K4S-120', 'S-200'], [0], rng='smoke')() is None)


# ================================================================ label -> seal -> pack -> verify (F5, F6, F12, F13)
def synth_row(seed, tick, k=3):
    rng = np.random.default_rng([seed % 2**32, tick])
    mask = np.zeros(2306, bool); mask[[5, 600, 2304]] = True
    return dict(hand_ids=rng.integers(1, 100, 4).astype(np.int16), global_features=rng.random(8).astype(np.float32),
                entity_counts=np.int16(k), flat_entity_ids=rng.integers(1, 50, k).astype(np.int16),
                flat_entity_levels=np.ones(k, np.int8), flat_entity_features=rng.random((k, 3)).astype(np.float32),
                packed_mask=np.packbits(mask))


def write_collect_game(phase, arm, index, ticks, dup_of=None, block=True, base=C, **over):
    """A collection game exactly as run_collect + collect write it: game JSON, captures (v3) + summary, block proof."""
    seed = base+index
    (phase/'games').mkdir(parents=True, exist_ok=True); (phase/'captures').mkdir(exist_ok=True); (phase/'blocks').mkdir(exist_ok=True)
    g = phase/'games'/f'sim-{index:04d}-d27-{arm}.json'; g.write_text(json.dumps(dict(seed=seed, opaque=True)))
    caps = []
    for t in ticks:
        src = seed if dup_of is None else dup_of
        c = dict(schema='x4s4.capture.v3', id=f'{arm}/{seed}/{t}', arm=arm, index=index, seed=seed, tick=t, seat=index % 2,
                 row=synth_row(src, t), features_equal_student_input=True, row_equals_build_public=True, pending=(),
                 root_digest=f'd{src}-{t}', stratum='hit', stats=dict(student_default=t % 20 == 0, fallback=False), agent_action=5,
                 info=None, opponent=None, root_rng_state=None, candidate_rng_state=None)
        c.update(over); caps.append(pickle.dumps(c))
    body = pickle.dumps(caps)
    (phase/'captures'/f'sim-{index:04d}-d27-{arm}.pkl').write_bytes(body)
    wjson(phase/'captures'/f'sim-{index:04d}-d27-{arm}.json', dict(schema='x4s4.capture.v3', sha256=hashlib.sha256(body).hexdigest(),
          captures=len(caps), seed=seed, index=index, arm=arm, identity_ok=True))
    if block:
        wjson(phase/'blocks'/f'{index:04d}.json', dict(index=index, seed=seed, order=[arm], games={g.name: sha(g)}))


def parity_receipt(tmp, phases, passed=True):
    return wjson(tmp/f'parity-{passed}.json', dict(check='parity', passed=passed, phases=sorted(str(Path(p).resolve()) for p in phases)))


def ow_game(d, seed, n_roots, extra_rows=2):
    from imitation.exit_r1.rows import seal
    rows, scores = [], []
    for t in range(n_roots+extra_rows):
        r = synth_row(seed, t); root = t < n_roots
        r.update(expert_actions=np.int16(2304), expert_action_supervision_valid=np.bool_(True), submitted_ticks=np.int32(t),
                 teacher_search_action=np.int16(2304), teacher_root=np.bool_(root), teacher_wait_kind=np.int8(0 if root else 1),
                 recorded_play_ticks=np.int32(-1), recorded_world_positions=np.array([np.nan, np.nan], np.float32),
                 submitted_world_positions=np.array([np.nan, np.nan], np.float32), recorded_millitiles=np.array([-1, -1], np.int32))
        rows.append(r); scores.append(dict(candidates=[5, 2304] if t % 3 else [2304], scores=[.1, .2] if t % 3 else [.3]) if root
                                      else dict(candidates=[], scores=[]))
    seal(d, rows, scores, dict(seed=seed, outcome=1.0))


def test_pipeline(tmp):
    stub_torch_imports()
    import label, verify_onpolicy as V, confine
    from imitation.exit_r1 import pack as packmod
    job = new_job(tmp)
    pk, ps = job/'collect'/'K4S-120'/'a1', job/'collect'/'S-200'/'a1'
    for i in range(6): write_collect_game(pk, 'K4S-120', i, range(100, 160, 10))
    write_collect_game(pk, 'K4S-120', 6, range(100, 160, 10), dup_of=C+0)                 # exact duplicates of game 0
    for i in range(2000, 2004): write_collect_game(ps, 'S-200', i, range(100, 140, 10))
    for i in (3500, 3501): write_collect_game(pk, 'K4S-120', i, range(100, 130, 10))      # O-holdout
    write_collect_game(pk, 'K4S-120', 9, range(100, 130, 10), block=False)                # interrupted: no block proof
    label.CAPS = {'K4S-120': 30, 'S-200': 1000}
    plan_path = job/'data'/'label-plan.json'
    good_parity = parity_receipt(tmp, [pk, ps])
    label.make_plan([pk, ps], good_parity, plan_path)
    lp = json.loads(plan_path.read_text()); st = lp['stats']
    case('label plan: holdout split, interruption drop, dedup, per-arm cap, 600-tick feature duplicates',
         st['O']['dropped_no_block'] == 1 and st['O']['duplicate'] == 6 and st['O']['kept_per_arm'] == {'K4S-120': 30, 'S-200': 16}
         and st['O']['over_cap'] == 6 and st['holdout']['kept'] == 6 and lp['feature_only_duplicates_by_600_tick_bucket']['0']['feature_duplicates'] == 6)

    # F12/F13 probes on the plan: failed parity, stale block proofs, metadata mismatch, parity flags, allocation, outside out
    def plan_fails(mutate, parity=None, text=''):
        j2 = tmp/f'plan-{len(list(tmp.glob("plan-*")))}'; shutil.copytree(job/'collect', j2/'collect')
        q = parity_receipt(j2, [j2/'collect'/'K4S-120'/'a1', j2/'collect'/'S-200'/'a1']) if parity is None else parity(j2)
        mutate(j2/'collect'/'K4S-120'/'a1')
        use_job(j2); (j2/'data').mkdir(exist_ok=True)
        try: label.make_plan([j2/'collect'/'K4S-120'/'a1', j2/'collect'/'S-200'/'a1'], q, j2/'data'/'label-plan.json'); r = False
        except label.PlanError as e: r = text in str(e)
        use_job(job); return r
    stale = lambda ph: (ph/'games'/'sim-0001-d27-K4S-120.json').write_text('{"changed": 1}')
    seedmm = lambda ph: write_collect_game(ph, 'K4S-120', 2, range(100, 130, 10), seed=C+99)
    flag = lambda ph: write_collect_game(ph, 'K4S-120', 2, range(100, 130, 10), row_equals_build_public=False)
    pend = lambda ph: write_collect_game(ph, 'K4S-120', 2, range(100, 130, 10), pending=('x',))
    outside = lambda ph: write_collect_game(ph, 'K4S-120', 2600, range(100, 130, 10))
    bad_parity = lambda j2: parity_receipt(j2, [j2/'collect'/'K4S-120'/'a1', j2/'collect'/'S-200'/'a1'], passed=False)
    wrong_phases = lambda j2: parity_receipt(j2, [j2/'collect'/'K4S-120'/'a1'])
    probes = dict(stale_block=plan_fails(stale, text='authenticate'), seed_mismatch=plan_fails(seedmm, text='identity'),
                  public_parity_false=plan_fails(flag, text='parity'), pending=plan_fails(pend, text='pending'),
                  allocation=plan_fails(outside, text='allocation'), failed_parity=plan_fails(lambda ph: None, parity=bad_parity, text='EXCEPTION'),
                  parity_other_phases=plan_fails(lambda ph: None, parity=wrong_phases, text='exactly these'))
    case('F13/F12 probes: plan refuses stale block proof, seed mismatch, public-parity false, non-empty pending, out-of-allocation, failed or mismatched parity',
         all(probes.values()), probes=probes)
    j3 = tmp/'exc'; shutil.copytree(job/'collect', j3/'collect'); use_job(j3); (j3/'data').mkdir()
    q = parity_receipt(j3, [j3/'collect'/'K4S-120'/'a1', j3/'collect'/'S-200'/'a1'], passed=False)
    wjson(j3/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256=sha(q), coordinator_ruling='COORDINATOR test', decision='disclose'))
    label.make_plan([j3/'collect'/'K4S-120'/'a1', j3/'collect'/'S-200'/'a1'], q, j3/'data'/'label-plan.json')
    case('F12: an explicit coordinator PARITY-EXCEPTION bound to the failed receipt is accepted and recorded',
         json.loads((j3/'data'/'label-plan.json').read_text())['parity_exception']['decision'] == 'disclose')
    use_job(job)
    case('F10 probe: label plan output outside <job>/data is refused',
         raises(lambda: label.make_plan([pk, ps], good_parity, tmp/'plan-out.json'), confine.ConfinementError))

    # labeling: a stubbed scorer (W scoring needs the engine: qualification on 01)
    calls = []
    def score_ok(info, opponent, rrs, crs, seed, digest=None):
        calls.append(digest); return 5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None]
    label.score_state = score_ok; label.mem_available = lambda: 100*2**30
    label.RAW = str(job/'data'/'raw-O'); label.THREADS = 1; label.PLAN_SHA = sha(plan_path)
    res = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    again = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    case('labeling seals every planned game; resume re-verifies seal + identity and skips',
         all(r['status'] == 'sealed' for r in res) and all(r['status'] == 'already_sealed' for r in again))
    entry = next(e for e in lp['sets']['O'] if e['keep'])
    label.PLAN_SHA = 'f'*64
    resume_bad = raises(lambda: label.label_game(entry), RuntimeError, 'identity differs')
    label.PLAN_SHA = sha(plan_path)
    stale_entry = dict(entry, index=entry['index'], sha256='0'*64)
    shutil.rmtree(job/'data'/'raw-O'/entry['arm']/f"game-{entry['index']:04d}")
    stale_cap = raises(lambda: label.label_game(stale_entry), RuntimeError, 'changed since the plan')
    def score_bug(*a, **k): raise ValueError('engine defect')
    label.score_state = score_bug
    narrow = raises(lambda: label.label_game(entry), ValueError, 'engine defect')
    label.score_state = score_ok; label.label_game(entry)
    case('F13/F5 probes: resume with a different plan SHA, a stale capture SHA and an undeclared scorer exception all fail (no silent drop)',
         resume_bad and stale_cap and narrow)

    # F5 probe: the run receipt; a memory-guard result fails it and the process exits 1
    n = len([e for e in lp['sets']['O'] if e['keep']])
    good = label.summarize(again, n)
    bad = label.summarize(again[:-1]+[dict(again[-1], status='memory_guard')], n)
    mism = label.summarize(again[:-1]+[dict(again[-1], drops=dict(digest_mismatch=1))], n)
    exit_bad = raises(lambda: label.finish(job/'data'/'label-receipt-x.json', dict(bad, set='O', plan_sha256=sha(plan_path))), SystemExit, '1')
    case('F5 probe: label run receipt: memory_guard -> complete False, passed False and exit 1; 1 mismatch in 46 fails the 0.1% limit',
         good['passed'] and not bad['complete'] and not bad['passed'] and exit_bad and not mism['passed'] and mism['digest_mismatch_rate'] > 0.001)
    good_receipt = wjson(job/'data'/'label-receipt-O-1.json', dict(good, set='O', plan_sha256=sha(plan_path)))
    mism_receipt = wjson(tmp/'lr-mism.json', dict(mism, set='O', plan_sha256=sha(plan_path)))

    # seal -> pack -> verify O
    (job/'data'/'onpolicy').mkdir()
    plan = json.loads((HERE/'plan.json').read_text()); planf = wjson(tmp/'plan.json', plan)
    V.O_MIN, V.O_MAX, V.ARM_CAPS = 10, 100, {'K4S-120': 30, 'S-200': 1000}

    def verify(j, mode='O', receipts=(good_receipt,), selection=None):
        use_job(j)
        args = ['--mode', mode, '--plan', str(planf), '--label-receipts', *map(str, receipts)]
        if selection: args += ['--selection', str(selection)]
        rc = V.main(args); body = json.loads(next((j/'data').rglob('VERIFY-RECEIPT.json')).read_text()); use_job(job)
        return rc, body.get('error', '')

    def fresh(name, mutate=lambda j: None):
        j2 = tmp/('v-'+name); shutil.copytree(job, j2, symlinks=True)
        for p in j2.rglob('*'):
            if p.is_file() and not p.is_symlink(): p.chmod(0o644)
        for r_ in (j2/'data').rglob('VERIFY-RECEIPT.json'): r_.unlink()
        for gname in ('O-VERIFIED.json', 'OW-VERIFIED.json'):
            if (j2/'data'/gname).exists(): (j2/'data'/gname).unlink()
        shutil.rmtree(j2/'data'/'onpolicy')                      # repack: sources.json records absolute source paths
        packmod.pack([j2/'data'/'raw-O'/'K4S-120', j2/'data'/'raw-O'/'S-200'], j2/'data'/'onpolicy'/'batch-0000')
        mutate(j2); return j2
    rc, err = verify(fresh('ok'))
    case('verify O: passes and writes the O gate from real label receipts bound to the plan', rc == 0, error=err)
    neg = {}
    neg['mismatch receipt'] = verify(fresh('mm'), receipts=(mism_receipt,))
    neg['stale plan SHA'] = verify(fresh('ps', lambda j: wjson(j/'data'/'label-plan.json', dict(lp, utc='changed'))))
    def drop_one(j):
        r = json.loads(good_receipt.read_text()); r['games'] = r['games'][1:]; wjson(j/'data'/'label-receipt-O-1.json', r)
    neg['receipt game set != packed'] = verify(fresh('gs', drop_one), receipts=(tmp/'v-gs'/'data'/'label-receipt-O-1.json',))
    def relabel(j):   # a source game's receipt claims another seed (provenance)
        g = next((j/'data'/'raw-O'/'K4S-120').glob('game-*')); r = json.loads((g/'receipt.json').read_text())
        r['seed'] += 1; (g/'receipt.json').write_text(json.dumps(r))
    neg['source receipt identity'] = verify(fresh('ri', relabel))
    V.O_MIN = 1000; neg['below the O minimum'] = verify(fresh('min')); V.O_MIN = 10
    neg['symlink in batch'] = verify(fresh('sl', lambda j: os.symlink('/etc/passwd', j/'data'/'onpolicy'/'batch-0000'/'train'/'evil.npy')))
    case('F13 probes: verify O rejects a failed receipt, stale plan, receipt/packed game-set mismatch, source identity drift, small O, symlink',
         all(v[0] == 1 for v in neg.values()), errors={k: v[1][:80] for k, v in neg.items()})

    # F6 probes: O_W gate (target from the O gate; 4 games x 15 scored roots; 2 non-root rows each)
    def ow_case(name, target, games=(0, 1, 2, 3), sel=None, acc=True, seed_shift=None):
        j = tmp/('ow-'+name); new_job(j, 'job'); j = use_job(j/'job')
        for g in games:
            ow_game(j/'data'/'raw-OW'/f'game-{g:05d}', CW+g+(1 if seed_shift == g else 0), 15)
        packmod.pack([j/'data'/'raw-OW'], j/'data'/'onpolicy-w'/'batch-0000')
        wjson(j/'data'/'O-VERIFIED.json', dict(rows=target))
        wjson(j/'data'/'raw-OW-acceptance-smoke.json', dict(passed=acc))
        s = dict(reached=True, target_roots=target, selected_games=list(range(len(games))), selected_roots=15*len(games), last_game_roots=15)
        s.update(sel or {}); wjson(j/'data'/'raw-OW-selection.json', s)
        rc_ = V.main(['--mode', 'OW', '--plan', str(planf), '--selection', str(j/'data'/'raw-OW-selection.json')])
        body = json.loads((j/'data'/'onpolicy-w'/'VERIFY-RECEIPT.json').read_text()); use_job(job)
        return rc_, body
    rc, body = ow_case('ok', 46)
    case('verify OW: minimal prefix (45 < 46 <= 60), roots by the RootTeacherStore rule, single-candidate share reported',
         rc == 0 and body['roots'] == 60 and body['rows'] == 68 and 0 < body['single_candidate_root_share'] < 1, error=body.get('error'))
    owneg = dict(non_minimal=ow_case('nm', 45), short=ow_case('short', 61), gap_0124=ow_case('gap', 46, games=(0, 1, 2, 4)),
                 selection_not_range=ow_case('sel', 46, sel=dict(selected_games=[0, 1, 2, 4])),
                 seed_not_cprime_g=ow_case('seed', 46, seed_shift=2), acceptance_failed=ow_case('acc', 46, acc=False),
                 last_game_roots_claim=ow_case('lgr', 46, sel=dict(last_game_roots=14)))
    case('F6 probes: O_W gate rejects a non-minimal prefix (Sol 45-of-60), a short prefix, sources [0,1,2,4], a non-range selection, '
         'a wrong seed, a failed acceptance smoke and a wrong last-game root claim', all(v[0] == 1 for v in owneg.values()),
         errors={k: v[1].get('error', '')[:70] for k, v in owneg.items()})

    # F6 probe: collect_w resume identity
    import collect_w
    cw = new_job(tmp, 'cwjob'); collect_w.JOB = cw
    collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
    collect_w.OUT = str(cw/'data'/'raw-OW'); (cw/'data'/'raw-OW').mkdir()
    collect_w.resources_ok = lambda disk=True: True
    def sealed_game(g, **over):
        own, opp, seat, index, decks = collect_w.game_inputs(g)
        d = cw/'data'/'raw-OW'/f'game-{g:05d}'; d.mkdir()
        r = dict(seed=CW+g, index=index, opponent='v1', seat=seat, root_decisions=15,
                 episode=dict(decks=[collect_w.X[own], collect_w.X[opp]] if seat == 0 else [collect_w.X[opp], collect_w.X[own]]))
        r.update(over); (d/'replay.json').write_text(json.dumps(r))
        (d/'manifest.json').write_text(json.dumps(dict(complete=True, files={'replay.json': sha(d/'replay.json')})))
        return d
    sealed_game(3); ok = collect_w.play((3, CW)) == dict(g=3, status='already_sealed', roots=15)
    sealed_game(4, seed=CW+99); bad_seed = raises(lambda: collect_w.play((4, CW)), AssertionError, 'identity')
    sealed_game(5, opponent='script'); bad_opp = raises(lambda: collect_w.play((5, CW)), AssertionError, 'identity')
    d6 = sealed_game(6); (d6/'replay.json').write_text(json.dumps(dict(json.loads((d6/'replay.json').read_text()), root_decisions=16)))
    bad_seal = raises(lambda: collect_w.play((6, CW)), AssertionError, 'seal')
    (cw/'data'/'raw-OW'/'game-00007').mkdir(); unsealed = raises(lambda: collect_w.play((7, CW)), AssertionError, 'unsealed')
    os.symlink(cw/'nowhere', cw/'STOP'); stopped = collect_w.play((8, CW)) == dict(g=8, status='stopped')
    case('F6/F9 probes: collect_w resume re-verifies seal and realized identity (seed, opponent); unsealed dir refused; dangling STOP symlink stops',
         ok and bad_seed and bad_opp and bad_seal and unsealed and stopped)


# ================================================================ driver (F5, F8, F9)
def driver_module(tmp):
    job = new_job(tmp, 'djob')
    drv = load_patched('driver_t%d' % random.randrange(10**9), HERE/'driver.py',
                       [("J = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')", f"J = Path({str(job)!r})")])
    return drv, job


def test_driver(tmp):
    drv, job = driver_module(tmp/'a')
    state = dict(fits={'R5': 'done', 'R5-rep': 'running', 'R5W': 'pending'}, ready={'R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W'}, done={})
    drv.fit_state = lambda f: (state['fits'][f], None)
    drv.ready_students = lambda: [s for s in drv.STUDENT_ORDER if s in state['ready']]
    drv.retired_set = lambda: (set(), {})
    drv.phase_status = lambda sid, arm, r: state['done'].get((sid, arm), set())
    for f in ('R5', 'R5-rep', 'R5W'): wjson(job/f'rt-{f}'/'READY.json', {})
    none_while_fit = drv.next_phase() is None
    state['fits'] = {k: 'done' for k in state['fits']}
    order = []
    for _ in range(12):
        nx = drv.next_phase()
        if nx is None: break
        order.append(f'{nx[0]}/{nx[1]}'); state['done'][(nx[0], nx[1])] = set(range(drv.N))
    want = [f'{s}/{a}' for s in ('R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W') for a in ('K4S-120', 'S-200')]
    case('driver: no reporting phase while any fit is not done; ABBA order, all ten phases, no futility skip', none_while_fit and order == want, order=order)
    tree = ast.parse((HERE/'driver.py').read_text())
    subs = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in ('loss', 'winner', 'outcome')]
    case('driver never reads a game outcome (only the fit training loss)', subs == ["r['loss']"], subs=subs)

    # F5 probe: rc 17 with no reason -> anomaly; nothing retired; no dispatch
    drv, job = driver_module(tmp/'b')
    d = job/'games'/'R3a'/'K4S-120'/'a1'; (d/'blocks').mkdir(parents=True)
    wjson(d/'schedule.json', dict(indices=list(range(10)))); wjson(d/'launch.json', dict(workers=2))
    for i in (0, 1): wjson(d/'blocks'/f'{i:04d}.json', {})
    wjson(d/'supervisor-exit.json', dict(reason=None, returncode=17))
    (job/'REPORTING.GO').write_text('')
    launched = []; drv.launch_phase = lambda *a: launched.append(a); drv.resources_ok = lambda for_fit=False: True
    drv.next_phase = lambda: ('R3a', 'S-200', [0])
    drv.games_tick()
    case('F5 probe: a reporting exit with rc 17 and no reason is an anomaly: nothing retired, no SETTLED, no further dispatch',
         (job/'driver'/'ANOMALY-exit-games_R3a_K4S-120_a1.json').exists() and not (job/'driver'/'retired.json').exists()
         and not (d/'SETTLED.json').exists() and not launched)
    (job/'driver'/'ACK-games_R3a_K4S-120_a1').write_text('owner resolved'); drv.games_tick()
    acked = (d/'SETTLED.json').exists() and set(json.loads((job/'driver'/'retired.json').read_text())['indices']) == set(range(2, 5))
    drv2, job2 = driver_module(tmp/'c')
    d2 = job2/'games'/'R3a'/'K4S-120'/'a1'; (d2/'blocks').mkdir(parents=True)
    wjson(d2/'schedule.json', dict(indices=list(range(10)))); wjson(d2/'launch.json', dict(workers=2))
    wjson(d2/'supervisor-exit.json', dict(reason='memory_guard', returncode=-15)); drv2.settle_attempt(d2)
    case('F5 control: a permitted guard stop (memory_guard) or an owner ACK retires the started seeds and settles',
         acked and (d2/'SETTLED.json').exists() and json.loads((job2/'driver'/'retired.json').read_text())['indices'] == [0, 1, 2])

    # F5: fit completion needs a clean return AND a known zero exit (durable across a driver restart)
    drv, job = driver_module(tmp/'d')
    out = job/'fits'/'R5'; out.mkdir(parents=True)
    wjson(out/'complete.json', dict(stopped=False, step=2500)); wjson(out/'segment.json', dict(status='returned'))
    rec = wjson(job/'receipts'/'fit-R5-launch.json', dict(pid=2**22+12345, pgid=2**22+12345, launched_at_utc='2026-10-13T00:00:00Z'))
    unknown = drv.fit_state('R5')[0]
    with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='2026-10-13T01:00:00Z', kind='child_exit', pid=2**22+12345, exit_code=1))+'\n')
    failed = drv.fit_state('R5')[0]
    with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='2026-10-13T01:00:01Z', kind='child_exit', pid=2**22+12345, exit_code=0))+'\n')
    done = drv.fit_state('R5')[0]
    drv.EXIT[2**22+12345] = 3; masked = drv.fit_state('R5')[0]
    case('F5 probe: fit done only with a clean return + zero exit; unknown or nonzero exit (incl. from durable events) is failed',
         unknown == 'failed' and failed == 'failed' and done == 'done' and masked == 'failed', states=[unknown, failed, done, masked])

    # F9 probes: fail-closed admission
    drv.mem_available = lambda: 100*2**30; drv.psi_some_avg10 = lambda: 1.0; drv.disk_bytes = lambda: 10**9
    drv.tree_processes = lambda g: [1]*5; drv.gpu_used_mib = lambda: 100
    base_ok = drv.resources_ok() and drv.resources_ok(for_fit=True)
    probes = {}
    for name, attr, val, fit in (('psi unreadable', 'psi_some_avg10', lambda: None, False), ('psi > 10', 'psi_some_avg10', lambda: 10.5, False),
                                 ('mem unreadable', 'mem_available', lambda: 0, False), ('disk unreadable', 'disk_bytes', lambda: None, False),
                                 ('disk > 100 GB', 'disk_bytes', lambda: 101*10**9, False), ('> 70 processes', 'tree_processes', lambda g: [1]*71, False),
                                 ('GPU unreadable (fit)', 'gpu_used_mib', lambda: None, True)):
        old = getattr(drv, attr); setattr(drv, attr, val); probes[name] = not drv.resources_ok(for_fit=fit); setattr(drv, attr, old)
    wjson(job/'driver'/'DIAGNOSTIC.lock', dict(pid=os.getpid())); probes['live diagnostic lock'] = not drv.resources_ok()
    (job/'driver'/'DIAGNOSTIC.lock').unlink()
    os.symlink(job/'nowhere', job/'STOP'); probes['dangling STOP symlink'] = drv.stop_present(); (job/'STOP').unlink()
    case('F9 probes: admission blocks on unreadable PSI/memory/disk/GPU, PSI > 10, disk > 100 GB, > 70 processes, a live diagnostic; STOP via lexists',
         base_ok and all(probes.values()), probes=probes)

    # F9/R2-11: fit auto-resume only for wall_over_2x and only after the O_W gate
    drv, job = driver_module(tmp/'e')
    st = {'R5': 'stopped', 'R5-rep': 'pending', 'R5W': 'pending'}
    drv.fit_state = lambda f: (st[f], None); drv.live_supervisor = lambda: None; drv.resources_ok = lambda for_fit=False: True
    wjson(job/'data'/'O-VERIFIED.json', {})
    fits = drv.Fits(); calls = []; fits.launch = lambda fid, s: calls.append((fid, s))
    wjson(job/'driver'/'ANOMALY-fit-R5.json', dict(reason='wall_over_2x')); fits.tick(True); before_gate = list(calls)
    wjson(job/'data'/'OW-VERIFIED.json', {}); fits.tick(True); after_gate = list(calls)
    wjson(job/'driver'/'ANOMALY-fit-R5.json', dict(reason='nan_or_divergent')); calls.clear(); fits.tick(True)
    case('F9/R2-11: a wall_over_2x fit resumes only after the O_W gate; divergence never auto-resumes',
         before_gate == [] and after_gate == [('R5', 'stopped')] and calls == [])

    # F8 probe: reporting launches the X4S-4 supervisor, and only with a matching runtime inventory
    drv, job = driver_module(tmp/'f')
    rt = job/'rt-R3a'/'repo'
    files = ('reports/explore/x4s4/supervise.py', 'reports/explore/x4s4/confine.py', 'reports/explore/x4s3/run.py', 'reports/explore/x4s3/runtime.sh')
    for rel in files:
        (rt/rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(REPO/rel if (REPO/rel).exists() else HERE/Path(rel).name, rt/rel)
    wjson(job/'RUNTIME-INVENTORY.json', {rel: sha(rt/rel) for rel in files})
    cmds = []
    class FakePopen:
        def __init__(self, cmd, **kw): cmds.append(cmd); self.pid = 4242
    drv.subprocess = types.SimpleNamespace(Popen=FakePopen, run=subprocess.run, DEVNULL=subprocess.DEVNULL)
    drv.launch_phase('R3a', 'K4S-120', [0, 1])
    good = cmds and 'reports/explore/x4s4/supervise.py' in cmds[0] and not any('x4s3/supervise.py' in c for c in cmds[0])
    (rt/'reports/explore/x4s4/supervise.py').write_text('# tampered\n'); cmds.clear()
    drv.launch_phase('R3a', 'S-200', [0, 1])
    case('F8 probe: reporting runs reports/explore/x4s4/supervise.py; a runtime file differing from RUNTIME-INVENTORY is refused',
         good and not cmds and (job/'driver'/'ANOMALY-phase-R3a-S-200.json').exists())


# ================================================================ supervisor census (F7, F9, F10)
def test_supervise(tmp):
    import confine
    sup = load_patched('supervise_t', HERE/'supervise.py', [])
    job = new_job(tmp)
    wjson(job/'driver'/'driver.pid', dict(pid=1, pgid=424242))
    case('supervisor: X4S-4 tree groups include driver, child and own group', {424242, 12345, os.getpgrp()} <= sup.x4s4_pgids(job, 12345))
    # F7 probe: scripted /proc readings. A foreign process born inside the interval with 1,000 ticks must count.
    seq = dict(t=iter([0.0, 1.0, 2.0, 3.0, 4.0]), busy=iter([0, 1000, 1000, 1500, None]),
               own=iter([{}, {(77, 5): 50}, {(77, 5): 60, (78, 9): 40}, {}, {}]))
    sup.time = types.SimpleNamespace(monotonic=lambda: next(seq['t']))
    sup.host_busy_ticks = lambda: next(seq['busy']); sup.own_tree_ticks = lambda groups: next(seq['own'])
    hz = os.sysconf('SC_CLK_TCK')
    fc = sup.ForeignCensus(job, -1)
    v1, v2, v3, v4 = fc.sample(), fc.sample(), fc.sample(), fc.sample()
    case('F7 probe: baseline before the child; a NEW foreign process\'s first-interval CPU is counted; own births/exits handled; unreadable -> None',
         abs(v1-(1000-50)/hz) < 1e-9 and v2 == 0.0 and abs(v3-500/hz) < 1e-9 and v4 is None, values=[v1, v2, v3, v4])
    src = (HERE/'supervise.py').read_text()
    case('F9: the supervisor tests STOP with lexists only', "os.path.lexists(job/'STOP')" in src and "(job/'STOP').exists()" not in src)
    def run_main(argv):
        sys.argv = ['supervise.py', *argv]
        return lambda: sup.main()
    common = ['--rt', str(tmp), '--range', 'reporting', '--indices', str(tmp/'i.json'), '--stop-at', '2030-01-01T00:00:00Z']
    probes = dict(job_not_canonical=raises(run_main(['--job', str(tmp), '--phase', 'games/a', *common]), SystemExit, 'must be'),
                  phase_traversal=raises(run_main(['--job', str(job), '--phase', 'games/../../x', *common]), confine.ConfinementError),
                  phase_absolute=raises(run_main(['--job', str(job), '--phase', '/etc/x', *common]), confine.ConfinementError),
                  phase_role=raises(run_main(['--job', str(job), '--phase', 'fits/x', *common]), confine.ConfinementError))
    case('F10 probes: supervisor refuses a non-canonical --job and absolute/traversing/wrong-role --phase before any write', all(probes.values()), probes=probes)


# ================================================================ contention (F4, F7)
T0 = datetime.datetime(2026, 10, 13, 10, 0, tzinfo=datetime.timezone.utc).timestamp()
def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def write_phase_timing(ph, workers=10, lane=5, rows=None, launch=T0-10, exit_=None, settled=True):
    wjson(ph/'launch.json', dict(utc=iso(launch), workers=workers, lane_width=lane))
    rows = rows if rows is not None else [dict(utc=iso(T0-5+10*k), psi_some_avg10=0.5, foreign_cores_host=0.3, reduced_concurrency=False) for k in range(62)]
    (ph/'census.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    last = max([datetime.datetime.strptime(r['utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp() for r in rows] or [launch])
    wjson(ph/'supervisor-exit.json', dict(utc=iso(exit_ if exit_ is not None else last+5), reason=None, returncode=0))
    if settled: wjson(ph/'SETTLED.json', {})


def timing_game(ph, arm, i, wall=4.0, end=None):
    (ph/'games').mkdir(parents=True, exist_ok=True); (ph/'blocks').mkdir(exist_ok=True)
    g = ph/'games'/f'sim-{i:04d}-d27-{arm}.json'; g.write_text(json.dumps(dict(loss=1.0, wall_seconds=wall)))
    end = T0+10*i if end is None else end; os.utime(g, (end, end))
    wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, games={g.name: sha(g)}))


def test_contention(tmp):
    import contention
    def build(name, setup):
        job = new_job(tmp, name)
        for sid in ('R3a', 'R5'):
            ph = job/'games'/sid/'K4S-120'/'a1'
            for i in range(8): timing_game(ph, 'K4S-120', i)
            write_phase_timing(ph)
        setup(job); return contention.build(job)
    def census_edit(job, sid, k, **kw):
        ph = job/'games'/sid/'K4S-120'/'a1'; rows = [json.loads(l) for l in (ph/'census.jsonl').read_text().splitlines()]
        rows[k].update(kw); (ph/'census.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    # Each mechanism alone, in an UNCAPPED phase of a different student, flags exactly the overlapping game(s).
    # Game i occupies [T0+10i-5, T0+10i]; census row k covers (T0-5+10(k-1), T0-5+10k].
    mech = dict(clean=(lambda j: None, []),
                psi=(lambda j: census_edit(j, 'R3a', 2, psi_some_avg10=15.0), [1]),
                psi_unreadable=(lambda j: census_edit(j, 'R3a', 3, psi_some_avg10=None), [2]),
                foreign=(lambda j: census_edit(j, 'R5', 4, foreign_cores_host=3.0), [3]),
                foreign_unreadable=(lambda j: census_edit(j, 'R5', 5, foreign_cores_host=None), [4]),
                yield_window=(lambda j: census_edit(j, 'R3a', 6, reduced_concurrency=True), [5]),
                mid_gap=(lambda j: (j/'games'/'R3a'/'K4S-120'/'a1'/'census.jsonl').write_text(''.join(
                    json.dumps(dict(utc=iso(T0-5+10*k), psi_some_avg10=0.5, foreign_cores_host=0.3, reduced_concurrency=False))+'\n'
                    for k in range(62) if k not in (7, 8, 9))), [6, 7]))
    got = {k: build('m-'+k, f)['excluded_indices'] for k, (f, _) in mech.items()}
    case('F18/F7 probe: PSI, unreadable PSI, foreign, unreadable foreign, yield and a census gap each flag exactly their own games',
         all(got[k] == w for k, (_, w) in mech.items()), got=got)
    capped = build('capped', lambda j: wjson(j/'games'/'R5'/'K4S-120'/'a1'/'launch.json', dict(utc=iso(T0-10), workers=3, lane_width=5)))
    empty = build('empty', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'census.jsonl').write_text(''))
    tail = build('tail', lambda j: (wjson(j/'games'/'R3a'/'K4S-120'/'a1'/'supervisor-exit.json', dict(utc=iso(T0+60), reason=None, returncode=0)),
                 (j/'games'/'R3a'/'K4S-120'/'a1'/'census.jsonl').write_text(''.join(
                     json.dumps(dict(utc=iso(T0-5+10*k), psi_some_avg10=0.5, foreign_cores_host=0.3, reduced_concurrency=False))+'\n' for k in range(4)))))
    case('F7 probes: a capped phase flags all its games; an EMPTY census flags the whole phase; an uncovered tail is bad',
         capped['excluded_indices'] == list(range(8)) and empty['excluded_indices'] == list(range(8)) and tail['excluded_indices'] == [3, 4, 5, 6],
         got=[capped['excluded_indices'], empty['excluded_indices'], tail['excluded_indices']])
    unfinished = raises(lambda: build('unf', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'SETTLED.json').unlink()), contention.ContentionError, 'missing')
    noexit = raises(lambda: build('nx', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'supervisor-exit.json').unlink()), contention.ContentionError, 'missing')
    case('F7 probe: contention refuses unsettled or exit-less phases', unfinished and noexit)
    seen, orig = [], json.loads
    def spy(s, **kw):
        out = orig(s, **kw); seen.append(set(out)) if isinstance(out, dict) else None; return out
    contention.json.loads = spy
    w = contention.wall_only(tmp/'m-clean'/'games'/'R3a'/'K4S-120'/'a1'/'games'/'sim-0000-d27-K4S-120.json')
    contention.json.loads = orig
    case('contention parses only wall_seconds from a game JSON', w == 4.0 and seen == [{'wall_seconds'}])
    job = use_job(tmp/'m-clean')
    out, digest = contention.write_once(job, contention.build(job))
    mode = stat.S_IMODE(os.lstat(out).st_mode)
    case('contention receipt: schema v2 with per-phase inventory, written once (O_EXCL), mode 0444',
         json.loads(out.read_text())['schema'] == 'x4s4.contention.v2' and mode == 0o444 and digest == sha(out)
         and raises(lambda: contention.write_once(job, {}), Exception))


# ================================================================ reducer + report (F4, F11, F14)
def reduce_fixture(tmp, students=('R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W'), forward=5, p_loss=None):
    job = new_job(tmp, 'rjob')
    plan = json.loads((HERE/'plan.json').read_text()); plan['seed_ranges']['reporting'] = dict(base=E, count=60)
    shas = {s: hashlib.sha256(s.encode()).hexdigest() for s in students}
    plan['student']['checkpoint_sha256'] = shas['R3a']
    wjson(job/'x'/'plan.json', plan)
    wjson(job/'driver'/'retired.json', dict(indices=[3], why=[]))
    for s in students:
        if s != 'R3a': wjson(job/f'rt-{s}'/'READY.json', dict(student=dict(checkpoint_sha256=shas[s])))
    rng = random.Random(5)
    p_loss = p_loss or {'R3a': .30, 'R3a-rep': .30, 'R5': .15, 'R5-rep': .15, 'R5W': .25}
    for s in students:
        for arm in ('K4S-120', 'S-200'):
            sp = plan['arms'][arm]; ph = job/'games'/s/arm/'a1'; (ph/'games').mkdir(parents=True); (ph/'blocks').mkdir()
            idx = [i for i in range(60) if i != 3 and not (s == 'R5W' and i >= 50)]
            wjson(ph/'schedule.json', dict(range='reporting', cases=[[i, 0, arm] for i in idx]))
            width = 1 if sp['threads'] == 1 else 5
            for i in idx:
                lose = rng.random() < p_loss[s]; seat = i % 2; winner = (1-seat) if lose else seat
                ds = [dict(wall_seconds=.1, overrun_seconds=0.0, delayed_ticks=0, hit=True, fallback=False, student_default=False, action=2304, wall_overrun=False)]
                g = dict(loss=float(lose), cohort=arm, cpu_seconds=10.0, wall_seconds=5.0, metadata=dict(seed=E+i, arm=arm, terminal=True, opponent='v1-policy',
                         student_id=s, checkpoint_sha256=shas[s], study='X4S-3 exploration, NEVER ADOPTABLE', threads=sp['threads'], coarse_horizon=160,
                         budget_ms=round(sp['deadline_seconds']*1000), default_source=sp['default_source'], kernel=sp['kernel'], honest_lateness=True,
                         winner=winner, seat=seat, channel=dict(peak_pending=1), own_deck=['a'], opponent_deck=['b']),
                         search_ab=dict(worker_affinity=list(range(width)), nice=10, scheduler=0, host='127x01', worker_pid=1, gc_maintenance=[],
                                        policy_cache_counts=dict(forward=forward if (s, arm, i) == ('R5', 'S-200', 7) else 5, fallback=5),
                                        policy_polls={str(seat): 5}, latency_seconds=[.1], deadline_stats=ds))
                gp = ph/'games'/f'sim-{i:04d}-d27-{arm}.json'; gp.write_text(json.dumps(g)); os.utime(gp, (T0+10*i, T0+10*i))
                wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=E+i, order=[arm], slot_cores=list(range(width)),
                                                        worker_pid=1, games={gp.name: sha(gp)}))
            rows = [dict(utc=iso(T0-5+10*k), psi_some_avg10=(15.0 if (s, arm, k) == ('R3a', 'K4S-120', 1) else 0.5),
                         foreign_cores_host=0.3, reduced_concurrency=False) for k in range(62)]
            write_phase_timing(ph, workers=10 if width == 5 else 50, lane=width, rows=rows)
    return job


def git_repo(tmp, receipt_bytes, on_main=True):
    repo = tmp/'repo'; repo.mkdir(parents=True)
    g = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null']
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    f = repo/'reports/explore/x4s4/receipts/contention-exclusion.json'; f.parent.mkdir(parents=True); f.write_bytes(receipt_bytes)
    subprocess.run(g+['add', '-A'], check=True); subprocess.run(g+['commit', '-q', '-m', 'freeze'], check=True)
    head = subprocess.run(g+['rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    if on_main: subprocess.run(g+['update-ref', 'refs/remotes/origin/main', head], check=True)
    else:                                   # origin/main is an unrelated (orphan) history: the freeze commit is not on it
        subprocess.run(g+['checkout', '-q', '--orphan', 'main2'], check=True); subprocess.run(g+['rm', '-r', '-q', '--cached', '.'], check=True)
        (repo/'other').write_text('x'); subprocess.run(g+['add', 'other'], check=True); subprocess.run(g+['commit', '-q', '-m', 'base'], check=True)
        subprocess.run(g+['update-ref', 'refs/remotes/origin/main', 'HEAD'], check=True)
    return repo, head


def test_reduce(tmp):
    import contention, confine
    red = load_patched('reduce_t', HERE/'reduce.py', [("E_BASE, E_COUNT = 4503606307370496, 1200", "E_BASE, E_COUNT = 4503606307370496, 60")])
    job = reduce_fixture(tmp/'a')
    red.__dict__['__file__'] = str(job/'x'/'reduce.py')
    reads = []
    real_load = red.load_student
    def spy_load(*a, **k): reads.append(a[1]); return real_load(*a, **k)
    red.load_student = spy_load
    out = job/'analysis'/'results.json'
    def run(extra, sha_=None, commit=None, repo=None):
        sys.argv = ['reduce.py', '--job', str(job), '--students', 'R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W', '--out', str(out),
                    '--contention-sha', sha_ or '0'*64, '--freeze-commit', commit or '0'*40, '--repo', str(repo or tmp), *extra]
        try: red.main(); return 'ok'
        except SystemExit as e: return str(e)
    r_none = run([])
    # Sol's F4 probe: a writable receipt with only excluded_indices
    rx = job/'receipts'/'contention-exclusion.json'; rx.write_text(json.dumps(dict(excluded_indices=[0, 1])))
    r_sol = run([], sha_=sha(rx)); rx.unlink()
    body = contention.build(job); rx_path, digest = contention.write_once(job, body)
    data = rx_path.read_bytes()
    repo, head = git_repo(tmp/'g1', data)
    repo_bad, head_bad = git_repo(tmp/'g2', data+b' ')
    repo_side, head_side = git_repo(tmp/'g3', data, on_main=False)
    gate = dict(no_receipt=r_none, sol_probe_writable_minimal=r_sol, wrong_sha=run([], sha_='1'*64, commit=head, repo=repo),
                not_committed_bytes=run([], sha_=digest, commit=head_bad, repo=repo_bad),
                not_on_origin_main=run([], sha_=digest, commit=head_side, repo=repo_side))
    os.chmod(rx_path, 0o644); gate['writable'] = run([], sha_=digest, commit=head, repo=repo); os.chmod(rx_path, 0o444)
    os.link(rx_path, job/'receipts'/'hardlink'); gate['hard_linked'] = run([], sha_=digest, commit=head, repo=repo); (job/'receipts'/'hardlink').unlink()
    cen = job/'games'/'R5'/'S-200'/'a1'/'census.jsonl'; keep = cen.read_bytes(); cen.write_bytes(keep+b'\n')
    gate['inventory_changed'] = run([], sha_=digest, commit=head, repo=repo); cen.write_bytes(keep)
    (job/'games'/'R5'/'S-200'/'a2').mkdir(); gate['extra_phase'] = run([], sha_=digest, commit=head, repo=repo); (job/'games'/'R5'/'S-200'/'a2').rmdir()
    case('F4 probes: no receipt, Sol\'s writable minimal receipt, wrong SHA, uncommitted bytes, commit off origin/main, writable, '
         'hard-linked, changed inventory and an extra phase are all refused BEFORE any game read',
         all(v != 'ok' for v in gate.values()) and reads == [], refusals={k: v[:60] for k, v in gate.items()})
    case('F10 probe: reducer --out outside <job>/analysis is refused',
         raises(lambda: (setattr(sys, 'argv', ['reduce.py', '--job', str(job), '--students', 'R3a', '--out', str(tmp/'x.json'),
                                               '--contention-sha', digest, '--freeze-commit', head]), red.main()), confine.ConfinementError))
    incomplete = run([], sha_=digest, commit=head, repo=repo)
    case('reducer refuses an incomplete student without --allow-prefix (fixed N), after the freeze gate', 'fixed N' in incomplete and reads, msg=incomplete[:200])
    ok = run(['--allow-prefix'], sha_=digest, commit=head, repo=repo)
    r = json.loads(out.read_text()); ro = r['readout']; p = ro['primary']
    case('reducer: primary on the full primary prefix (R5W never cuts it); fit-inflated interval wider than the CI',
         ok == 'ok' and r['paired_seeds'] == 59 and not r['truncation']['truncated'] and r['truncation']['r5w_prefix_seeds'] == 49
         and r['truncation']['r5w_truncated'] and p['fit_inflated_interval_pp'][1]-p['fit_inflated_interval_pp'][0] > p['ci95_pp'][1]-p['ci95_pp'][0])
    case('F14: per-arm averaged primary present and averages to the pooled point (equal arm weight)',
         set(ro['primary_by_arm']) == {'K4S-120', 'S-200'}
         and abs(sum(ro['primary_by_arm'][a]['point_pp'] for a in ('K4S-120', 'S-200'))/2 - p['point_pp']) < 1e-9)
    cs = ro['contention_sensitivity']
    case('reducer: contention view excludes exactly the frozen indices [0, 1] and records the freeze SHA + commit',
         body['excluded_indices'] == [0, 1] and cs['excluded_paired_seeds'] == 2 and cs['exclusion_sha256'] == digest and cs['freeze_commit'] == head,
         excluded=body['excluded_indices'])

    # F11 probe: policy-cache parity is an explicit check (fails in every optimization mode)
    job2 = reduce_fixture(tmp/'b', forward=99)
    red.__dict__['__file__'] = str(job2/'x'/'reduce.py'); use_job(job2)
    body2 = contention.build(job2); rx2, d2 = contention.write_once(job2, body2); repo2, h2 = git_repo(tmp/'g4', rx2.read_bytes())
    sys.argv = ['reduce.py', '--job', str(job2), '--students', 'R3a', 'R5', 'R5-rep', 'R3a-rep', '--out', str(job2/'analysis'/'r.json'),
                '--contention-sha', d2, '--freeze-commit', h2, '--repo', str(repo2), '--allow-prefix']
    case('F11 probe: a policy-cache mismatch (forward=99) is refused in this optimization mode too',
         raises(lambda: red.main(), SystemExit, "pc['forward']"), optimize=sys.flags.optimize)
    use_job(job)

    # exact formulas and strict boundaries
    cl = red.classify
    pooled_neg = {'R5 minus R3a [pooled]': dict(loss_change_pp=-1.0), 'R5-rep minus R3a [pooled]': dict(loss_change_pp=-0.5)}
    pooled_zero = dict(pooled_neg, **{'R5-rep minus R3a [pooled]': dict(loss_change_pp=0.0)})
    b = [cl(dict(ci95_pp=[-3.0, -0.01]), pooled_neg), cl(dict(ci95_pp=[-3.0, 0.0]), pooled_neg), cl(dict(ci95_pp=[-3.0, -0.01]), pooled_zero),
         cl(dict(ci95_pp=[-1.99, 1.0]), pooled_neg), cl(dict(ci95_pp=[-2.0, 1.0]), pooled_neg)]
    case('classification boundaries: upper CI strictly < 0 and both pooled single-fit points < 0 for helps; lower CI strictly > -2.0',
         b == ['helps', 'inconclusive', 'inconclusive', 'no material effect', 'inconclusive'], got=b)
    def g(loss, seat=0):
        return dict(loss=float(loss), cpu_seconds=1.0, metadata=dict(own_deck=['a'], opponent_deck=['b'], seat=seat, winner=None if loss else seat),
                    search_ab=dict(deadline_stats=[dict(wall_seconds=.1, hit=True, action=2304, wall_overrun=False, fallback=False)]))
    L = {'R3a': {'K4S-120': [1, 1, 0, 0], 'S-200': [1, 0, 0, 0]}, 'R3a-rep': {'K4S-120': [1, 0, 1, 0], 'S-200': [0, 0, 0, 0]},
         'R5': {'K4S-120': [0, 0, 0, 0], 'S-200': [1, 0, 0, 0]}, 'R5-rep': {'K4S-120': [0, 1, 0, 0], 'S-200': [0, 0, 0, 0]}}
    data = {s: {a: {i: g(v[i]) for i in range(4)} for a, v in arms.items()} for s, arms in L.items()}
    plan = dict(bootstrap=dict(seed=1, reps=200), arms={'K4S-120': dict(deadline_seconds=.12), 'S-200': dict(deadline_seconds=.2)})
    res = red.analyze(data, list(L), [0, 1, 2, 3], plan)
    d = res['delta'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'])
    # by hand: K4S-120 treatment (0+1)/2/4 = 0.125 vs control (2+2)/2/4 = 0.5 -> -37.5 pp; S-200 (1+0)/2/4 vs (1+0)/2/4 -> 0; pooled -18.75
    dk = res['delta_arm'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'], 'K4S-120')['point_pp']; ds = res['delta_arm'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'], 'S-200')['point_pp']
    sigma = red.readout(res, res['contrasts'], data)
    half = 1.96*(sigma['se_boot_pp']**2+0.65**2)**.5
    case('exact formulas: per-arm and pooled primary by hand (-37.5, 0, -18.75 pp); fit-inflated half-width 1.96*sqrt(se^2+0.65^2)',
         abs(dk+37.5) < 1e-9 and abs(ds) < 1e-9 and abs(d['point_pp']+18.75) < 1e-9
         and abs(sigma['fit_inflated_interval_pp'][1]-sigma['point_pp']-half) < 1e-9, got=[dk, ds, d['point_pp']])

    # write_report renders the required readouts (render only: the real RESULTS.md is never written by tests)
    import write_report as wr
    lp = dict(stats={s: dict(games=3, dropped_no_block=1, captured=10, duplicate=1, over_cap=0, kept=9, kept_per_arm={'K4S-120': 5, 'S-200': 4},
                             strata={'hit': 7, 'nonhit_sample': 2}, student_default=1, fallback=0, plays=4) for s in ('O', 'holdout')},
              feature_only_duplicates_by_600_tick_bucket={'0': dict(states=10, feature_duplicates=2, rate=.2)})
    r_empty = copy.deepcopy(r); r_empty['readout']['contention_sensitivity'] = dict(estimate=None, exclusion_sha256=digest, freeze_commit=head,
                                                                                  excluded_paired_seeds=59, seeds=0, note='x')
    txt = wr.render(r, lp, dict(rows=400000), dict(roots=400100, rows=420000, single_candidate_root_share=.1), None, {'results': 'abc'}, [])
    txt_empty = wr.render(r_empty, lp, dict(rows=400000), dict(roots=400100, rows=420000, single_candidate_root_share=.1), None, {}, [])
    need = ['Primary Δ by arm', 'R5W secondaries 49 seeds', 'R5W prefix shorter', 'O composition and duplicates', '600-tick bucket',
            'single-candidate root share = 10.0%', 'R3a-rep differs from R3a', 'ExactFastPrior', 'anchor kernel', 'decision table']
    case('F14: report renders per-arm primary, R5W prefix disclosure, composition/dedup/600-tick tables, O_W single-candidate share, fixed disclosures, decision row',
         all(n in txt for n in need) and '**no estimate**' in txt_empty, missing=[n for n in need if n not in txt])
    rows = {o: wr.next_step(dict(outcome=o, harmful=h), dict(attribution='on-policy or deployment-matched data helps; attribution unresolved'))
            for o, h in (('helps', False), ('no material effect', True), ('inconclusive', False))}
    case('F14: decision-table follow-ups: helps -> unresolved default (matched W generation first); no effect + harmful -> label audit',
         'matched W generation first' in rows['helps'] and 'audit the O labels' in rows['no material effect']
         and 'No program decision' in rows['inconclusive'])
    sys.argv = ['write_report.py', '--out', str(tmp/'RESULTS.md')]
    case('F10 probe: write_report --out outside reports/explore/x4s4 is refused', raises(lambda: wr.main(), confine.ConfinementError))


# ================================================================ qualification (F3, F12)
def qual_phase(root, name, arms, rng, base, cmd='h', capture=True, fair_moved=True, drop_case=None, cfg_sha=None):
    ph = root/name
    cases = [[i, base+i, arm, 'own', 'opp'] for i in range(8) for arm in arms]
    wjson(ph/'schedule.json', dict(range=rng, indices=list(range(8)), cases=cases, config_sha256=cfg_sha))
    for i in range(8):
        games = {}
        for arm in arms:
            if drop_case == (i, arm): continue
            ds = [dict(hit=False, student_default=False, wall_overrun=False) for _ in range(4)]
            g = wjson(ph/'games'/f'sim-{i:04d}-d27-{arm}.json', dict(search_ab=dict(command_sha256=f'{cmd}{i}{arm}', deadline_stats=ds)))
            games[g.name] = sha(g)
            if capture:
                caps = [pickle.dumps(dict(schema='x4s4.capture.v3', id=f'{arm}/{i}/{t}', pending=(), seed=base+i)) for t in range(3)]
                body = pickle.dumps(caps); (ph/'captures').mkdir(exist_ok=True)
                (ph/'captures'/f'sim-{i:04d}-d27-{arm}.pkl').write_bytes(body)
                checks = dict(belief_checked=3, belief_unchanged=3, fair_checked=3, fair_identical=3, fair_perturbed_decisions=3 if fair_moved else 0,
                              fair_checked_early=3, fair_perturbed_early=3 if fair_moved else 0, fair_moved_cards=12)
                wjson(ph/'captures'/f'sim-{i:04d}-d27-{arm}.json', dict(schema='x4s4.capture.v3', sha256=hashlib.sha256(body).hexdigest(), captures=3,
                      index=i, seed=base+i, arm=arm, identity_ok=True, counts=dict(captured=3, not_search=1), checks=checks,
                      features_equal_all=True, public_equal_all=True, pending_empty_all=True))
        wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=base+i, order=arms, games=games))
    return ph


def test_qualify(tmp):
    stub_torch_imports()
    import qualify4 as Q, label
    job = new_job(tmp)
    cfg = HERE/'plan-qual-capture.json'; cs = sha(cfg)
    run_ph = qual_phase(job/'qual', 'run', list(Q.QUAL_ARMS), 'qualification', QUAL, capture=False, cfg_sha=cs)
    def hashes(name, **kw):
        col = qual_phase(job/'qual', name, list(Q.QUAL_ARMS), 'qualification', QUAL, cfg_sha=cs, **kw)
        out = job/'qual'/f'{name}.json'
        try: Q.main(['hashes', '--run-phase', str(run_ph), '--collect-phase', str(col), '--config', str(cfg), '--out', str(out)]); rc = 0
        except SystemExit as e: rc = e.code
        return rc, json.loads(out.read_text())
    rc, body = hashes('col-ok')
    case('qualify hashes: 16/16 cases with terminal proofs, equal command hashes, capture checks and fair coverage pass', rc == 0 and body['cases'] == 16, error=body.get('error'))
    negs = dict(missing_case=hashes('col-15', drop_case=(7, 'S-long')), unmoved_permutation=hashes('col-fair', fair_moved=False),
                command_hash_differs=hashes('col-cmd', cmd='x'))
    case('F12/F3 probes: qualification fails on 15/16 cases, a permutation that moved no card, or a command-hash difference',
         all(v[0] == 1 and v[1]['passed'] is False for v in negs.values()), errors={k: v[1].get('error', '') for k, v in negs.items()})

    # F12: 100% round trip over every smoke capture
    smoke_k = job/'collect'/'smoke'/'K4S-120'; smoke_s = job/'collect'/'smoke'/'S-200'
    for ph, arm in ((smoke_k, 'K4S-120'), (smoke_s, 'S-200')):
        for i in range(8): write_collect_game(ph, arm, i, (100, 110), base=SMOKE)
        wjson(ph/'schedule.json', dict(range='smoke', indices=list(range(8)), cases=[[i, SMOKE+i, arm] for i in range(8)]))
    caps = Q.all_captures([smoke_k, smoke_s], label)
    missing_arm = raises(lambda: Q.all_captures([smoke_k], label), Q.QualError, 'cover')
    for c in caps:
        c.update(reserved_packet=[1], opponent_elixir=5.0)
        c['c8_sha256'] = hashlib.sha256(pickle.dumps(([1], 5.0, ()), protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()
    good = Q.roundtrip_check(caps, lambda *a: (5, [5], [0.1]))
    bad_digest = Q.roundtrip_check(caps, lambda *a: (_ for _ in ()).throw(LookupError('digest')))
    caps[0]['c8_sha256'] = '0'*64; bad_c8 = Q.roundtrip_check(caps, lambda *a: (5, [5], [0.1]))
    case('F12 probes: round trip covers ALL 32 smoke captures (no sampling); a missing arm, a digest mismatch or a bad C8 hash fails',
         good['passed'] and good['checked'] == 32 and missing_arm and not bad_digest['passed'] and not bad_c8['passed'])

    # F12: parity requires both arms, and the watcher pauses collection out of band
    def parity_phase(name, arm, n, hit, sd, over):
        ph = job/'collect'/name
        for i in range(n):
            ds = [dict(hit=k < hit, student_default=k < sd, wall_overrun=k < over) for k in range(1000)]
            wjson(ph/'games'/f'sim-{i:04d}-d27-{arm}.json', dict(search_ab=dict(deadline_stats=ds))); wjson(ph/'blocks'/f'{i:04d}.json', {})
        return ph
    pk = parity_phase('pk', 'K4S-120', 3, 642, 223, 2); ps = parity_phase('ps', 'S-200', 3, 753, 0, 1)
    one = Q.parity_once([pk], 3); both = Q.parity_once([pk, ps], 3)
    pbad = parity_phase('pbad', 'S-200', 3, 700, 0, 1)
    def watch():
        try: Q.main(['parity', '--phases', str(pk), str(pbad), '--min-games', '3', '--watch', '1', '--out', str(job/'receipts'/'parity-watch.json')])
        except SystemExit as e: return e.code
    rc = watch()
    paused = list((job/'receipts').glob('PARITY-PAUSE-*.json'))
    case('F12 probes: parity with one arm does not pass; both arms in band pass; out of band the watcher writes PARITY-PAUSE, creates STOP and exits 1',
         not one['passed'] and both['passed'] and rc == 1 and paused and os.path.lexists(job/'STOP'))
    case('F10 probe: qualification receipts outside <job>/qual|receipts are refused',
         raises(lambda: Q.main(['parity', '--phases', str(pk), '--min-games', '1', '--out', str(tmp/'p.json')]), Exception, 'outside'))


# ================================================================ diagnose (F9, F15)
def test_diagnose(tmp):
    import diagnose as Dg
    rng = np.random.default_rng(7)
    n = 257
    g, c, t = rng.random(n), rng.random(n), rng.random(n); w = rng.integers(0, 2, n).astype(float); pm = rng.random(n)
    def agg(bs, order):
        acc = Dg.CEAccumulator()
        for s in range(0, n, bs):
            j = order[s:s+bs]; acc.add(g[j], c[j], t[j], w[j], pm[j])
        return acc.result()
    ref = agg(n, np.arange(n))
    inv = all(abs(agg(bs, rng.permutation(n))[k]-ref[k]) < 1e-9 for bs in (1, 7, 64) for k in ('listwise_ce', 'frozen_objective'))
    direct = (g*w).sum()/w.sum() + ((c+t)*w).sum()/(w*pm).sum()
    # Sol's counterexample: a WAIT-only batch and a play-only batch with conditional CE C
    Cc = 2.0
    acc = Dg.CEAccumulator(); acc.add([0.]*4, [0.]*4, [0.]*4, [1.]*4, [0.]*4); acc.add([0.]*4, [Cc/2]*4, [Cc/2]*4, [1.]*4, [1.]*4)
    rowmean = (0*4 + (Cc*4/4)*4)/8
    case('F15 probe: global CE is batch-size/order invariant, equals the frozen objective on all rows, and gives C (not C/2) on Sol\'s counterexample',
         inv and abs(ref['frozen_objective']-direct) < 1e-9 and abs(acc.result()['frozen_objective']-Cc) < 1e-12 and abs(rowmean-Cc/2) < 1e-12)
    job = new_job(tmp)
    lock = Dg.acquire_lock(job); ok = lock.exists() and json.loads(lock.read_text())['pid'] == os.getpid(); lock.unlink()
    wjson(job/'receipts'/'phase-R3a-K4S-120-a1-launch.json', dict(pgid=os.getpgrp()))
    refused = raises(lambda: Dg.acquire_lock(job), SystemExit, 'live') and not (job/'driver'/'DIAGNOSTIC.lock').exists()
    case('F9 probe: the diagnostic takes the driver lock, refuses (and releases) while a reporting/fit group lives', ok and refused)


# ================================================================ seed audit (F11, F16)
def test_audit(tmp):
    import audit_seeds as A
    root = tmp/'repo'; dest = root/'reports/explore/x4s4'; dest.mkdir(parents=True)
    shutil.copy(HERE/'plan.json', dest/'plan.json')
    inside = b'seed 4503606307370500 here'
    (root/'reports/explore/t1').mkdir(parents=True); (root/'reports/explore/t1/results.json').write_bytes(inside)
    (root/'reports/explore/k4s-confirm/run').mkdir(parents=True); (root/'reports/explore/k4s-confirm/run/outcome-sealed.md').write_bytes(inside)
    (root/'reports/strategy_council_20260928/live-loop/v4').mkdir(parents=True)
    (root/'reports/strategy_council_20260928/live-loop/v4/tiers-complete.json').write_bytes(inside)
    (tmp/'real.md').write_bytes(inside); os.symlink(tmp/'real.md', root/'reports/explore/alias.md')
    opened = []
    real_rb = Path.read_bytes
    def spy(self): opened.append(str(self)); return real_rb(self)
    Path.read_bytes = spy
    try:
        out = A.audit(root, dest); clean = True
    except A.AuditError as e:
        out, clean = None, str(e)
    finally:
        Path.read_bytes = real_rb
    sealed_opened = [p for p in opened if any(s in p for s in ('/t1/', '/k4s-confirm/', '/live-loop/', 'real.md', 'alias.md'))]
    case('F16 probe: sealed T1/K4S/TIERS outcome files and symlink aliases are never opened (skipped and counted)',
         clean is True and not sealed_opened and out['raw_literal_scan']['skipped_unread']['sealed_unread'] >= 3, opened_sealed=sealed_opened)
    (root/'reports/explore/notes.md').write_bytes(inside)
    case('F16 control: the same literal in an ordinary file is found (the scan is live)', raises(lambda: A.audit(root, dest), A.AuditError, 'raw literals'))
    (root/'reports/explore/notes.md').unlink()
    (root/'reports/explore/t1/PREREG.md').write_bytes(inside)
    case('F16: a seed DECLARATION inside a sealed tree is still audited', raises(lambda: A.audit(root, dest), A.AuditError, 'raw literals'))
    (root/'reports/explore/t1/PREREG.md').unlink()
    plan = json.loads((dest/'plan.json').read_text()); plan['seed_ranges']['smoke'] = dict(plan['seed_ranges']['reporting'])
    (dest/'plan.json').write_text(json.dumps(plan))
    case('F11 probe: identical bank bases fail the audit in this optimization mode too', raises(lambda: A.audit(root, dest), A.AuditError),
         optimize=sys.flags.optimize)
    shutil.copy(HERE/'plan.json', dest/'plan.json')
    wjson(root/'reports/explore/k-old/seed-audit.json', dict(prior=dict(base=E+100, count=10, name='old K bank')))
    case('F11: a prior declared range intersecting bank E fails the audit', raises(lambda: A.audit(root, dest), A.AuditError, 'intersects'))


# ================================================================ study-wide tree admission (F9)
def test_studytree(tmp):
    import studytree as S, label
    job = new_job(tmp)
    rec = S.register(job, 'label-O')
    wjson(job/'collect'/'K4S-120'/'a1'/'launch.json', dict(child_pgid=777001, supervisor_pgid=777002))
    g = S.groups(job)
    measured = S.disk_bytes(job)
    S.processes = lambda pgids: [1]*5; S.disk_bytes = lambda j: 10**9
    ok = S.admission(job)[0] and isinstance(measured, int) and measured > 0
    S.disk_bytes = lambda j: None; disk_none = not S.admission(job)[0]
    S.disk_bytes = lambda j: 101*10**9; disk_big = not S.admission(job)[0]
    S.disk_bytes = lambda j: 10**9; S.processes = lambda pgids: [1]*71; procs = not S.admission(job, disk=False)[0]
    label.mem_available = lambda: 100*2**30
    capped = label.halt_reason() == 'tree_cap'
    S.processes = lambda pgids: [1]*5; free = label.halt_reason() is None
    drv, djob = driver_module(tmp/'d')
    wjson(djob/'receipts'/'cpujob-collect-w-1.json', dict(pgid=777003)); wjson(djob/'collect'/'x'/'a1'/'launch.json', dict(child_pgid=777004, supervisor_pgid=777005))
    case('F9 probes: CPU jobs register their group; admission blocks on > 70 tree processes, unreadable or > 100 GB disk; '
         'the labeler halts on the tree cap; the driver counts registered CPU jobs and collection supervisors',
         os.getpgrp() in g and {777001, 777002} <= g and rec.exists() and ok and disk_none and disk_big and procs and capped and free
         and {777003, 777004, 777005} <= drv.tree_groups())


# ================================================================ static: asserts, configs (F11, F17), run_fit.sh (F5)
def test_static(tmp):
    owned = [p for p in sorted(HERE.glob('*.py')) if p.name not in ('run_collect.py', 'test_x4s4_offline.py')]
    asserts = {p.name: sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(p.read_text()))) for p in owned}
    case('F11: no assert statement in any X4S-4-owned script (run_collect.py keeps x4s3/run.py\'s bytes)', not any(asserts.values()), asserts=asserts)
    plan = json.loads((HERE/'plan.json').read_text())
    text = json.dumps(plan)
    drv_src = (HERE/'driver.py').read_text()
    case('F17: plan.json describes r3 (87809ae0), the ABBA order used by the driver, no futility stop, host-wide contention',
         '87809ae0' in plan['planning_doc'] and plan['students_order'] == ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']
         and "STUDENT_ORDER = ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']" in drv_src and 'skipped only' not in text
         and 'host-wide' in plan['readout']['contention'] and 'on 0-49' not in plan['readout']['contention'])
    for f in ('plan-collect.json', 'plan-qual-capture.json'):
        c = json.loads((HERE/f).read_text())
        case(f'F17/F12: {f} is a full staged runtime config (student R3a, policy v1, capture block)',
             c['student']['id'] == 'R3a' and c['student']['checkpoint_sha256'] == plan['student']['checkpoint_sha256']
             and c['policy']['checkpoint_sha256'] == plan['policy']['checkpoint_sha256'] and 'capture' in c and 'own_delay' in c)
    # F5 probe: the gate-list producer prints a valid batch then exits 17 -> run_fit.sh must fail, not list it x4
    fj = tmp/'fjob'; (fj/'data').mkdir(parents=True); (fj/'fit').mkdir()
    wjson(fj/'data'/'O-VERIFIED.json', dict(batches=[dict(name='batch-0000'), dict(name='batch-0001')]))
    src = (HERE/'run_fit.sh').read_text().replace('J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy', f'J={fj}')
    src = src.replace('exec /mpac/sdicks02/envs/clasher-gpu/bin/python -B', 'printf "%s\\n"').replace('cd "$J/fit/source"', 'true')
    src = src.replace('EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d \' \' -f 1)', 'EXIT_LOADER_AMENDMENT_SHA256=x')
    (tmp/'rf.sh').write_text(src)
    out = subprocess.run(['bash', str(tmp/'rf.sh'), 'R5'], capture_output=True, text=True)
    roots = [l for l in out.stdout.split('\n') if l.endswith(('/batch-0000', '/batch-0001'))]
    bad = subprocess.run(['bash', str(tmp/'rf.sh'), 'R5W'], capture_output=True, text=True)
    fake = tmp/'fakebin'; fake.mkdir(); (fake/'python3').write_text('#!/bin/sh\necho batch-0000\nexit 17\n'); (fake/'python3').chmod(0o755)
    prod = subprocess.run(['bash', str(tmp/'rf.sh'), 'R5'], capture_output=True, text=True, env=dict(os.environ, PATH=f'{fake}:{os.environ["PATH"]}'))
    case('F5 probe: run_fit.sh lists each O batch x4 (seed 2026101301); R5W refuses without its gate; a failing producer aborts it',
         out.returncode == 0 and len(roots) == 8 and '2026101301' in out.stdout and bad.returncode != 0
         and prod.returncode == 3 and 'batch-0000' not in prod.stdout, producer_rc=prod.returncode)
    import collect_w
    collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
    ok = True
    for g in range(200):
        own, opp, seat, index, decks = collect_w.game_inputs(g)
        ok &= (decks[index % 8] == collect_w.X[g % 5] and decks[(index//8) % 8] == collect_w.X[(g//5) % 5] and index % 2 == g % 2)
    case('collect_w: emitter-derived (own, opponent, seat) equals the X4S mapping for g in 0..199; 50 cells',
         ok and len({(g % 5, (g//5) % 5, g % 2) for g in range(50)}) == 50)


def main():
    import confine
    canonical = confine.JOB
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-test-', dir='/dev/shm'))
    try:
        for t in (test_confine, test_runner_identity, test_collect, test_pipeline, test_driver, test_supervise, test_contention,
                  test_reduce, test_qualify, test_diagnose, test_audit, test_studytree, test_static):
            d = tmp/t.__name__; d.mkdir()
            try: t(d)
            except Exception as e:
                import traceback; traceback.print_exc(); case(t.__name__+' raised', False, error=repr(e))
            finally: use_job(canonical)
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
