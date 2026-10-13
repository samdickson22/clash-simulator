"""X4S-4 offline synthetic tests (exploration, NEVER ADOPTABLE). r3 after Sol script review r2. 127x05 only; no host contact.

  /dev/shm/x4s4-venv/bin/python -B reports/explore/x4s4/test_x4s4_offline.py   (and with -O, -OO; any umask)

Synthetic fixtures under a fresh temp dir in /dev/shm (and disposable git repositories there). torch is not installed
offline, so the two torch-dependent imports of imitation.exit_r1.rows are stubbed; seal/pack/verify, the real clasher
BattleState/PlayerState/DiscreteTileActionSpace and the scripts' own logic run unchanged. Every Sol r1 and r2 probe has
a discriminating fixture ("F<n> probe" / "R2-F<n> probe"); write-safety negatives assert that the outside sentinel is
unchanged. Real engine paths (W scoring, native references, command hashes, trainer, GPU) remain qualification §6.
"""
import ast, contextlib, copy, datetime, errno, threading, hashlib, json, os, pickle, random, shutil, signal, stat, subprocess, sys, tempfile, time, types
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO), str(REPO/'src'), str(HERE)]
import x4s4io as io                                  # noqa: E402
RESULTS = []
C, CW, E, SMOKE, QUAL = 4503606317370496, 4503606347370496, 4503606307370496, 4503606327370496, 4503606337370496
BASELINE_RUN_SHA = 'e7f90d76f7603973b72c2e4a9ee0fc733727fddcb97b795b887f63a7b7c7a543'   # x4s3/run.py at c86d928d
PY = sys.executable


def case(name, ok, **info):
    RESULTS.append(dict(case=name, ok=bool(ok), **info)); print(json.dumps(RESULTS[-1], default=str), flush=True)


def raises(fn, exc=BaseException, text=''):
    try: fn()
    except exc as e: return text in str(e) or text in repr(e)
    return False


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wjson(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj)); return p
def readonly(p): return not (os.lstat(p).st_mode & 0o222)


def stub_torch_imports():
    d1 = types.ModuleType('imitation.evaluation.d1'); d1.model_packet = lambda *a, **k: None
    ft = types.ModuleType('imitation.model.features'); ft.ENTITY_COLUMNS = [0, 1, 2]; ft.build_row = lambda *a, **k: {}
    sys.modules.setdefault('imitation.evaluation.d1', d1); sys.modules.setdefault('imitation.model.features', ft)


def load_fresh(name, path):
    src = Path(path).read_text()
    mod = types.ModuleType(name); mod.__file__ = str(path); sys.modules[name] = mod
    exec(compile(src, str(path), 'exec'), mod.__dict__)
    return mod


def use_job(job):
    io.JOB = str(job)
    for m in ('label', 'collect_w', 'verify_onpolicy'):
        if m in sys.modules: sys.modules[m].JOB = str(job)
    return Path(job)


def new_job(tmp, name='job', hard_stop='2030-01-01T00:00:00Z'):
    job = Path(tmp)/name
    for d in ('data', 'receipts', 'driver', 'analysis', 'qual', 'collect', 'games', 'logs', 'smoke', 'inputs', 'calibration', 'fits', 'fit'):
        (job/d).mkdir(parents=True, exist_ok=True)
    (job/'HARD-STOP-UTC.txt').write_text(hard_stop+'\n')
    fake_watchdog(job)
    return use_job(job)


def fake_watchdog(job):
    """r9 fixture: a recorded watchdog (this live test process) with a heartbeat, so watchdog_ok() holds; the real
    watchdog.py is exercised separately in test_r9. The heartbeat age limit is relaxed for the suite in main()."""
    (Path(job)/'watchdog').mkdir(exist_ok=True)
    wjson(Path(job)/'watchdog'/'pid.json', dict(pid=os.getpid(), starttime=io.proc_stat(os.getpid())['starttime']))
    wjson(Path(job)/'watchdog'/'heartbeat.json', dict(pid=os.getpid(), epoch=time.time(), halted=None))
    hist = Path(job)/'watchdog'/'stop-periods.jsonl'
    if not hist.exists(): hist.write_text('')                   # r10 (R9-F5): the durable STOP history the watchdog creates


def git(repo, *args, check=True):
    g = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null']
    return subprocess.run(g+list(args), capture_output=True, text=True, check=check).stdout.strip()


def git_repo(path, files, on_main=True):
    """Disposable repository with `files` committed; origin/main at that commit (or an unrelated orphan)."""
    repo = Path(path); repo.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    for rel, data in files.items():
        f = repo/rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(data)
    git(repo, 'add', '-A'); git(repo, 'commit', '-q', '-m', 'fixture')
    head = git(repo, 'rev-parse', 'HEAD')
    if on_main: git(repo, 'update-ref', 'refs/remotes/origin/main', head)
    else:
        git(repo, 'checkout', '-q', '--orphan', 'main2'); git(repo, 'rm', '-r', '-q', '--cached', '.')
        (repo/'other').write_text('x'); git(repo, 'add', 'other'); git(repo, 'commit', '-q', '-m', 'base')
        git(repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    return str(repo), head


class StubBelief:
    def __init__(self): self.w = [0.5, 0.5]; self._pending = None
    def sample(self, rng): return dict(hand=['h%d' % int(rng.integers(100)) for _ in range(4)])


# ================================================================ the I/O gate (R2-F1, F10)
def test_io(tmp):
    job = new_job(tmp)
    outside = Path(tmp)/'outside'; outside.mkdir(); sentinel = outside/'sentinel'; sentinel.write_bytes(b'SENTINEL')
    os.symlink(outside, job/'data'/'link')
    probes = {'relative path': 'data/x', 'parent traversal': f'{job}/data/../../x', 'outside the job': str(outside/'x'),
              'role not allowed': f'{job}/nope/x', 'symlinked ancestor': f'{job}/data/link/x'}
    bad = {k: raises(lambda v=v: io.create_excl(v, b'x', roles=('data',)), io.Refusal) for k, v in probes.items()}
    os.link(sentinel, job/'data'/'hard.json'); os.symlink(sentinel, job/'data'/'soft.json')
    bad['replace over hard link'] = raises(lambda: io.replace_bytes(f'{job}/data/hard.json', b'EVIL'), io.Refusal, 'nlink')
    bad['replace over symlink'] = raises(lambda: io.replace_bytes(f'{job}/data/soft.json', b'EVIL'), io.Refusal, 'symlink')
    bad['create over hard link'] = raises(lambda: io.create_excl(f'{job}/data/hard.json', b'EVIL'), io.Refusal, 'exists')
    bad['append to hard link'] = raises(lambda: io.append_bytes(f'{job}/data/hard.json', b'EVIL'), io.Refusal, 'nlink')
    bad['append to symlink'] = raises(lambda: io.append_bytes(f'{job}/data/soft.json', b'EVIL'), io.Refusal)
    case('R2-F1/F10 probes: the gate refuses relative/traversing/outside/wrong-role/symlinked-ancestor targets and never '
         'writes through a hard link or symlink (outside sentinel unchanged)', all(bad.values()) and sentinel.read_bytes() == b'SENTINEL', refused=bad)
    # Sol's exact probe: hard-link <data>/receipt.json.tmp to an outside sentinel, then the real label.write_json
    stub_torch_imports()
    import label
    use_job(job)
    os.link(sentinel, job/'data'/'receipt.json.tmp')
    label.write_json(f'{job}/data/receipt.json', dict(ok=True))
    case('R2-F1 probe (Sol): label.write_json beside a hard-linked receipt.json.tmp leaves the outside sentinel unchanged',
         sentinel.read_bytes() == b'SENTINEL' and json.loads((job/'data'/'receipt.json').read_text()) == dict(ok=True))
    good = io.create_excl(f'{job}/data/new/deep.json', b'{}', roles=('data',)) and readonly(job/'data'/'new'/'deep.json')
    d = job/'data'/'tree'; d.mkdir(); (d/'f').write_text('x'); os.symlink(outside, d/'out')
    io.remove_tree(str(d))
    case('fd-based removal never follows a link; exclusive creation makes read-only files; replace is atomic',
         good and not d.exists() and sentinel.exists() and io.replace_json(f'{job}/data/r.json', dict(a=1)) and json.loads((job/'data'/'r.json').read_text()) == dict(a=1))
    src = Path(tmp)/'base'; (src/'repo').mkdir(parents=True); (src/'repo'/'plan.json').write_text('{}'); os.symlink('plan.json', src/'repo'/'alias')
    io.copy_tree_fresh(str(src), f'{job}/rt-R5')
    case('runtime overlay: fresh copy with links copied as links; an existing destination refuses',
         os.path.islink(job/'rt-R5'/'repo'/'alias') and (job/'rt-R5'/'repo'/'plan.json').read_text() == '{}'
         and raises(lambda: io.copy_tree_fresh(str(src), f'{job}/rt-R5'), io.Refusal, 'exists'))
    os.mkfifo(job/'data'/'fifo')
    reads = dict(symlink_leaf=raises(lambda: io.read_bytes(f'{job}/data/soft.json'), io.Refusal, 'symlink'),
                 hard_link_leaf=raises(lambda: io.read_bytes(f'{job}/data/hard.json'), io.Refusal, 'nlink'),
                 symlink_ancestor=raises(lambda: io.read_bytes(f'{job}/data/link/sentinel'), io.Refusal),
                 fifo_not_opened=raises(lambda: io.read_bytes(f'{job}/data/fifo'), io.Refusal, 'not-regular'),
                 nan_json=raises(lambda: io.loads_strict(b'{"a": NaN}'), io.Refusal, 'non-finite'),
                 dup_key=raises(lambda: io.loads_strict(b'{"a": 1, "a": 2}'), io.Refusal, 'duplicate'))
    (job/'data'/'g.json').write_text(json.dumps(dict(metadata=dict(terminal=True, winner=1), loss=1.0)))
    proj = io.project_json(f'{job}/data/g.json', ('metadata', 'terminal'))
    case('reads: symlink/hard-link/ancestor/FIFO refuse before reading; strict JSON; projections drop outcome keys',
         all(reads.values()) and proj == dict(metadata=dict(terminal=True)), reads=reads)
    sub = dict(rc_nonzero=raises(lambda: io.run_checked(['/bin/sh', '-c', 'echo ok; exit 3'], 10, 100), io.Refusal, 'exited 3'),
               relative_argv=raises(lambda: io.run_checked(['sh', '-c', 'true'], 10, 100), io.Refusal, 'absolute'),
               timeout=raises(lambda: io.run_checked(['/bin/sleep', '5'], 0.5, 100), io.Refusal, 'timed out'))
    case('run_checked: nonzero rc (with valid stdout), relative argv and timeout all refuse', all(sub.values()), sub=sub)
    # R3-F7: append classifies the leaf BEFORE opening; a FIFO with no reader is refused promptly (never a blocking open)
    os.mkfifo(job/'data'/'events.fifo')
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError('blocked'))); signal.alarm(5)
    try: fifo = raises(lambda: io.append_bytes(f'{job}/data/events.fifo', b'x'), io.Refusal, 'not-regular')
    except TimeoutError: fifo = False
    finally: signal.alarm(0)
    strict = dict(exponent_overflow=raises(lambda: io.loads_strict(b'{"x": 1e999}'), io.Refusal, 'non-finite'),
                  negative_overflow=raises(lambda: io.loads_strict(b'[-1e400]'), io.Refusal, 'non-finite'),
                  finite_ok=io.loads_strict(b'{"x": 1.5e3}') == dict(x=1500.0))
    (job/'data'/'dup.json').write_text('{"metadata": {"terminal": true}, "loss": 1, "loss": 0}')
    strict['projected_duplicate_of_dropped_key'] = raises(lambda: io.project_json(f'{job}/data/dup.json', ('metadata', 'terminal')), io.Refusal, 'duplicate')
    case('R3-F7 probes (Sol): append to a FIFO is refused without a blocking open; 1e999-style overflow and projected duplicate keys refuse',
         fifo and all(strict.values()), strict=strict)
    t0 = time.monotonic()
    marker = '31.%d' % random.randrange(10**8, 10**9)              # unique sleep argument of this run's helper only
    helper = raises(lambda: io.run_checked(['/bin/sh', '-c', f'/bin/sleep {marker} & /bin/sleep {marker}'], 0.5, 100), io.Refusal)
    time.sleep(0.5)
    def argv(pid):
        try: return open(f'/proc/{pid}/cmdline', 'rb').read().split(b'\x00')
        except OSError: return []
    left = [pid for pid in io.all_pids() if argv(pid)[:2] == [b'/bin/sleep', marker.encode()]]
    ctl = io.spawn(['/bin/sleep', marker], f'{job}/logs/ctl.log', dict(PATH='/usr/bin:/bin'))      # control: the matcher sees a live one
    seen = [pid for pid in io.all_pids() if argv(pid)[:2] == [b'/bin/sleep', marker.encode()]] == [ctl['pid']]
    io.stop_owned(ctl['pgid'], ctl['starttime'], term_grace=5, kill_grace=5, poll=0.1); ctl['popen'].wait()
    src = (HERE/'x4s4io.py').read_text()
    case('R3-F8: run_checked stops a timed-out helper AND its grandchild by verified individual PIDs (no group signal anywhere)',
         helper and not left and seen and time.monotonic()-t0 < 30 and 'killpg' not in src, left=left)
    child = io.spawn(['/bin/sleep', '30'], f'{job}/logs/sleep.log', dict(PATH='/usr/bin:/bin'))
    pids = io.owned_pids(child['pgid'], child['starttime'])
    wrong = io.owned_pids(child['pgid'], child['starttime']+1)
    io.stop_owned(child['pgid'], child['starttime'], term_grace=5, kill_grace=5, poll=0.1); child['popen'].wait()
    case('owned processes: (pgid, starttime) identity; a wrong starttime owns nothing; PID-only stop',
         pids == [child['pid']] and wrong == [] and io.owned_pids(child['pgid'], child['starttime']) == [])


# ================================================================ run_collect / collect (F1, F2, F3, F13, R2-F1, R2-F8)
def test_runner_identity(tmp):
    import collect
    base = (HERE.parent/'x4s3'/'run.py').read_text()
    case('reused evaluation runner x4s3/run.py is byte-identical to c86d928d', hashlib.sha256(base.encode()).hexdigest() == BASELINE_RUN_SHA)
    import difflib
    diff = [l for l in difflib.ndiff(base.splitlines(), (HERE/'run_collect.py').read_text().splitlines()) if l[:2] in ('- ', '+ ')]
    removed = [l for l in diff if l.startswith('- ')]; added = [l[2:].strip() for l in diff if l.startswith('+ ')]
    case('run_collect.py = x4s3/run.py + only the two explicit hooks (9 added lines, none removed)',
         not removed and len(added) == 9 and all(a.startswith(('#', 'if CAPTURE', 'CAPTURE', 'policy=', 'candidates=')) for a in added))
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
    m = types.ModuleType('runner_probe')
    m.__dict__.update(time=time, sys=sys, WINDOW=types.SimpleNamespace(active=True), CAPTURE=None, CAPTURE_END=None,
                      CAPTURE_PROBE=lambda check: (check(), 'ok')[1])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), 'runner_probe', 'exec'), m.__dict__)
    original = m.run_game
    collect.install(m)
    after = m.run_game is original and m.run_game(None) == 'ok'
    def r1_wrapper(case_):
        t0 = time.monotonic(); return original(case_)
    m.run_game = r1_wrapper
    case('F1 probe: inference_check passes through the collection install; the r1 wrapper fails it',
         after and raises(lambda: m.run_game(None), AssertionError))


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
    run = types.ModuleType('run_stub')
    run.R = types.SimpleNamespace(builder=types.SimpleNamespace(token_id=lambda name, namespace=None: 3,
                                                                build_public=lambda b, actor: [1.0, 2.0, float(b.tick)]),
                                  costs={'Knight': 3}, root=Root)
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
    case('capture_rng deterministic and domain-separated', r1 == r2 and len({r1, collect.capture_rng('root', C, 100).random(), collect.capture_rng('opponent', C, 110).random()}) == 3)
    collect.GuardedPickler.forbidden = (BattleState, PlayerState)
    case('persistent_id guard rejects PlayerState/BattleState; passes plain data',
         raises(lambda: collect.guarded_dumps(dict(a=[1, {'x': PlayerState(player_id=1)}])), collect.ForbiddenObject)
         and raises(lambda: collect.guarded_dumps(dict(s=BattleState())), collect.ForbiddenObject) and len(collect.guarded_dumps(dict(a=np.arange(3)))) > 0)
    play = make_kw(100, hit=True, action=5, submitted=[object()]); wait = make_kw(100, hit=True)
    suspended = make_kw(100, hit=True, action=5, input_pending=[object()], submitted=[object()])
    case('F2 probe: a play with its own command in ch.pending is eligible; WAIT eligible; a non-empty INPUT transaction rejected',
         collect.eligible(play) is None and collect.eligible(wait) is None and collect.eligible(suspended) == 'pending_nonempty_input')
    real_payload = collect.payload
    variants = {'real': real_payload,
                'hand': lambda kw: dict(real_payload(kw), leak=list(kw['b'].players[1-kw['actor']].hand)),
                'cycle': lambda kw: dict(real_payload(kw), leak=list(kw['b'].players[1-kw['actor']].cycle_queue)),
                'rng': lambda kw: dict(real_payload(kw), leak=kw['b'].rng.random()),
                'belief': lambda kw: (kw['p'].belief.w.append(1.0), real_payload(kw))[1],
                'battle': lambda kw: dict(real_payload(kw), battle=kw['b'])}
    out, caps_by = {}, {}
    with engine_stubs() as run_stub:
        collect.run = run_stub; collect._cfg = dict(nonhit_rate=0.25, all=True, verify_belief=True, fair_check=True)
        for name, fn in variants.items():
            collect.payload = fn; collect._captures.clear(); collect._counts.clear(); collect._checks.clear()
            try:
                for t in (100, 110): collect.capture(**make_kw(t, hit=True, action=5, submitted=[object()]))
                out[name] = dict(collect._checks); caps_by[name] = list(collect._captures)
            except collect.ForbiddenObject:
                out[name] = 'ForbiddenObject'
        collect.payload = real_payload
    real = out['real']
    case('F3 probe: the real payload is byte-identical under the permutation with cards moved; hand/cycle/RNG reads via kw[b] are detected',
         real.get('fair_identical') == 2 and real.get('fair_perturbed_decisions') == 2 and real.get('fair_perturbed_early') == 2
         and all(out[k].get('fair_identical') == 0 for k in ('hand', 'cycle', 'rng')))
    case('C7a/C9: belief mutation detected; a Battle reference raises the graph guard',
         out['belief'].get('belief_unchanged') == 0 and out['battle'] == 'ForbiddenObject')
    cap = pickle.loads(caps_by['real'][0])
    case('real payload stores the C8 triple with its SHA, empty input pending and the submitted play',
         cap['pending'] == () and cap['agent_action'] == 5 and cap['c8_sha256'] == hashlib.sha256(pickle.dumps(
             (cap['reserved_packet'], cap['opponent_elixir'], cap['pending']), protocol=pickle.HIGHEST_PROTOCOL)).hexdigest())
    phase = job/'collect'/'K4S-120'/'a1'; phase.mkdir(parents=True)
    rs = types.ModuleType('run_stub2'); rs.OPTIONS = dict(out=str(phase)); rs.run_game = lambda c: c; rs.CAPTURE = rs.CAPTURE_END = None
    collect._cfg = dict(nonhit_rate=0.0, all=False, verify_belief=False, fair_check=False)
    with engine_stubs() as run_stub:
        rs.R = run_stub.R; collect.install(rs)
        for t, hit, act in ((100, True, 5), (110, False, 2304), (120, True, 2304)):
            kw = make_kw(t, hit=hit, action=act, submitted=[object()] if act < 2304 else []); kw['pair'] = 7; kw['seed'] = C+7; rs.CAPTURE(**kw)
        kw = make_kw(130, candidates=[2304]); kw['pair'] = 7; kw['seed'] = C+7; rs.CAPTURE(**kw)
        rs.CAPTURE_END(pair=7, seed=C+7, arm='K4S-120')
    summ = json.loads((phase/'captures'/'sim-0007-d27-K4S-120.json').read_text())
    body = (phase/'captures'/'sim-0007-d27-K4S-120.pkl').read_bytes()
    case('per-game capture file through the gate: SHA, identity, counts; exclusive and read-only',
         hashlib.sha256(body).hexdigest() == summ['sha256'] and summ['captures'] == 2 and summ['plays_captured'] == 1
         and summ['counts'] == dict(captured=2, not_sampled=1, not_search=1) and readonly(phase/'captures'/'sim-0007-d27-K4S-120.pkl'))
    # R2-F1 probe (Sol): the collection ENTRY validates --out before the inherited runner creates anything
    outside = Path(tmp)/'outside-out'
    entry_outside = raises(lambda: collect.check_out(['x', '--out', str(outside)]), io.Refusal) and not outside.exists()
    stale = job/'collect'/'S-200'/'a1'; (stale/'games').mkdir(parents=True)
    entry_stale = raises(lambda: collect.check_out(['x', '--out', str(stale)]), SystemExit, 'already holds')
    fresh = job/'collect'/'S-200'/'a2'; fresh.mkdir(parents=True); (fresh/'launch.json').write_text('{}')
    entry_ok = collect.check_out(['x', '--out', str(fresh)]) == str(fresh)
    new = job/'collect'/'S-200'/'a3'; collect.check_out(['x', '--out', str(new)])
    os.symlink(outside.parent, job/'collect'/'lnk')
    case('R2-F1 probe (Sol): collection entry refuses an outside --out WITHOUT creating it, a used phase dir, and a symlinked ancestor',
         entry_outside and entry_stale and entry_ok and new.is_dir()
         and raises(lambda: collect.check_out(['x', '--out', str(job/'collect'/'lnk'/'p')]), io.Refusal) and not (outside.parent/'p').exists())
    cfg = HERE/'plan-collect.json'
    def alloc(arms, idx, rng='reporting'):
        (Path(tmp)/'idx.json').write_text(json.dumps(idx))
        return lambda: collect.check_allocation(['collect.py', '--config', str(cfg), '--out', 'x', '--workers', '1', '--indices',
                                                 str(Path(tmp)/'idx.json'), '--range', rng, '--arms', *arms])
    ok = alloc(['K4S-120'], [0, 1999, 3500, 3749])() is None and alloc(['S-200'], [2000, 3499, 3750, 3999])() is None
    case('F13 probe: collection allocation refuses out-of-allocation indices and two arms',
         ok and raises(alloc(['K4S-120'], [2500]), SystemExit) and raises(alloc(['S-200'], [100]), SystemExit)
         and raises(alloc(['K4S-120', 'S-200'], [0]), SystemExit) and raises(alloc(['K4S-120'], [3750]), SystemExit))
    # R2-F8 monitor death: the collection runner stops its own group when its supervisor disappears
    sleeper = subprocess.Popen(['/bin/sleep', '60']); st = io.proc_stat(sleeper.pid)
    out_dir = job/'collect'/'K4S-120'/'a9'; out_dir.mkdir(parents=True)
    script = Path(tmp)/'watch.py'
    script.write_text(f"import sys, time\nsys.path[:0] = {[str(REPO), str(REPO/'src'), str(HERE)]!r}\nimport x4s4io as io\nio.JOB = {str(job)!r}\n"
                      f"import collect\ncollect.supervisor_watchdog({str(out_dir)!r}, period=0.2)\ntime.sleep(30)\nsys.exit(0)\n")
    child = subprocess.Popen([PY, '-B', str(script)], env=dict(os.environ, X4S4_SUPERVISOR=f"{sleeper.pid}:{st['starttime']}"), start_new_session=True)
    time.sleep(1.0); sleeper.kill(); sleeper.wait()
    try: rc = child.wait(timeout=20)
    except subprocess.TimeoutExpired: child.kill(); rc = None
    noenv = subprocess.run([PY, '-B', str(script)], env={k: v for k, v in os.environ.items() if k != 'X4S4_SUPERVISOR'}, capture_output=True, text=True, timeout=30)
    case('R2-F8 probe: monitor death - the runner refuses to start without its supervisor and exits 70 with a receipt when it dies',
         rc == 70 and (out_dir/'supervisor-lost.json').exists() and noenv.returncode != 0 and 'supervisor' in noenv.stderr, rc=rc)


# ================================================================ label -> seal -> pack -> verify (F5, F6, F13, R2-F5, R2-F8)
def synth_row(seed, tick, k=3):
    rng = np.random.default_rng([seed % 2**32, tick])
    mask = np.zeros(2306, bool); mask[[5, 600, 2304]] = True
    return dict(hand_ids=rng.integers(1, 100, 4).astype(np.int16), global_features=rng.random(8).astype(np.float32),
                entity_counts=np.int16(k), flat_entity_ids=rng.integers(1, 50, k).astype(np.int16),
                flat_entity_levels=np.ones(k, np.int8), flat_entity_features=rng.random((k, 3)).astype(np.float32),
                packed_mask=np.packbits(mask))


def write_game(phase, arm, index, base, terminal=True, hit=0, n=4, sd=0, **meta):
    g = Path(phase)/'games'/f'sim-{index:04d}-d27-{arm}.json'; g.parent.mkdir(parents=True, exist_ok=True)
    m = dict(terminal=terminal, seed=base+index, arm=arm, seat=index % 2, winner=0, budget_ms=meta.pop('budget_ms', 120)); m.update(meta)
    ds = [dict(hit=k < hit, student_default=k < sd, wall_overrun=False) for k in range(n)]
    g.write_text(json.dumps(dict(metadata=m, loss=1.0, search_ab=dict(command_sha256=meta.get('cmd', 'h'), deadline_stats=ds))))
    return g


def write_collect_game(phase, arm, index, ticks, dup_of=None, block=True, base=C, terminal=True, **over):
    seed = base+index; phase = Path(phase)
    g = write_game(phase, arm, index, base, terminal=terminal)
    (phase/'captures').mkdir(parents=True, exist_ok=True); (phase/'blocks').mkdir(exist_ok=True)
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
    if block: wjson(phase/'blocks'/f'{index:04d}.json', dict(index=index, seed=seed, order=[arm], games={g.name: sha(g)}))


ALLOC_T = {'K4S-120': list(range(0, 2000))+list(range(3500, 3750)), 'S-200': list(range(2000, 3500))+list(range(3750, 4000))}


def finish_phase(ph, arm=None, rng='reporting', base=C, cfg='c'*64, reason='auto', rc=0, exit_=True, indices=None):
    """Complete phase execution evidence as the supervisor/runner write it: schedule (range, seeded cases of one arm),
    launch (same config), supervisor-exit (status, no live group). r6 (Sol R5-F3): by default the schedule holds
    exactly the cases the phase attempted (its games); a phase with an unproved attempted case cannot have exited clean,
    so reason='auto' gives it the guard interruption the supervisor would record (memory_guard, SIGTERM)."""
    ph = Path(ph)
    if arm is None: arm = next(n[:-5].split('-d27-')[1] for n in sorted(os.listdir(ph/'games')))
    games = sorted(int(n.split('-')[1]) for n in os.listdir(ph/'games')) if (ph/'games').is_dir() else []
    proved = sorted(int(n[:-5]) for n in os.listdir(ph/'blocks')) if (ph/'blocks').is_dir() else []
    idx = indices if indices is not None else sorted(set(games) | set(proved))
    if reason == 'auto': reason, rc = (None, rc) if set(idx) <= set(proved) else ('memory_guard', -15)
    wjson(ph/'schedule.json', dict(range=rng, indices=idx, cases=[[i, base+i, arm] for i in idx], config_sha256=cfg))
    wjson(ph/'launch.json', dict(workers=10, lane_width=5, config_sha256=cfg))
    if exit_: wjson(ph/'supervisor-exit.json', dict(reason=reason, returncode=rc, remaining_group_pids=[], complete_blocks=len(proved)))


def job_of(path):
    """The job directory containing `path` (the nearest ancestor holding receipts/, collect/ or HARD-STOP-UTC.txt)."""
    for d in [Path(path)]+list(Path(path).parents):
        if (d/'receipts').is_dir() or (d/'collect').is_dir() or (d/'HARD-STOP-UTC.txt').exists(): return d
    raise AssertionError(f'no job above {path}')


def refuse_failed_bless(paths):
    """SA-5: a fixture may never bless a FAILED receipt (a JSON whose top-level `passed` is not True). A real guard.py run
    exits 1 on a failed verdict and never yields a passed guard receipt, so blessing one would test an impossible state."""
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix == '.json':
            try: d = json.loads(p.read_text())
            except ValueError: continue
            if isinstance(d, dict) and 'passed' in d and d['passed'] is not True:
                raise AssertionError(f'fixture tried to bless a failed receipt: {p}')


def bless_into(job, *paths, allow_failed=False):
    """bless() for outputs that live outside the job tree (fixture receipts under tmp), recorded in `job`'s receipts.
    allow_failed=True only for a NEGATIVE that must still be refused downstream (defence in depth)."""
    import studytree as ST
    if not allow_failed: refuse_failed_bless(paths)
    n = f'test-{random.randrange(16**10):010x}'; (Path(job)/'receipts').mkdir(exist_ok=True)
    return wjson(Path(job)/'receipts'/f'guard-{n}.json', dict(schema='x4s4.guard.v1', name=n, passed=True,
                                                              outputs={str(p): ST.output_identity(str(p)) for p in paths}, new_files={}))


def bless(*paths, name=None, allow_failed=False):
    """r8 fixture: exactly what a PASSED guard.py run records for its declared outputs (receipts/guard-*.json naming each
    output with its current identity) - stands in for the guarded producer of a fixture file."""
    import studytree as ST
    if not paths: return None
    if not allow_failed: refuse_failed_bless(paths)
    job = job_of(paths[0]); outs = {}; (job/'receipts').mkdir(exist_ok=True)
    for p in paths:
        try: outs[str(p)] = ST.output_identity(str(p))
        except io.Refusal: pass
    n = name or f'test-{random.randrange(16**10):010x}'
    return wjson(job/'receipts'/f'guard-{n}.json', dict(schema='x4s4.guard.v1', name=n, passed=True, outputs=outs, new_files={}))


def parity_doc(tmp, phases, passed=True, final=True, name=None, bank='collection'):
    import qualify4
    for ph in phases:
        if not (Path(ph)/'supervisor-exit.json').exists(): finish_phase(ph)
    inv = qualify4.parity_inventory([str(p) for p in phases])
    doc = wjson(Path(tmp)/(name or f'parity-{passed}-{final}-{len(inv)}-{bank}.json'), dict(check='parity', passed=passed, final=final, bank=bank,
                phases=sorted(str(p) for p in phases), inventory=inv, evidence=qualify4.phase_evidence([str(p) for p in phases], 'collection')))
    if passed is True:                                         # SA-5: a FAILED receipt is never blessed; failed receipts
        bless_into(job_of(phases[0]), doc)                     # come only from the real guarded `qualify4 parity --final` run
    return doc


def guarded_parity(job, phases, name, final=True, min_games=1, extra=(), code=None):
    """SA-5: run the REAL qualify4 parity (in a child, io.JOB = job) under the REAL guard.py Runner, exactly as P3 does.
    Returns (receipt path, guard body, runner exits). `code` selects the x4s4 directory (mutation check)."""
    import guard as G
    code = Path(code or HERE); fake_watchdog(job); (Path(job)/'receipts').mkdir(exist_ok=True)
    out = Path(job)/'receipts'/f'parity-{name}.json'
    argv = ['parity', '--phases', *[str(p) for p in phases], '--bank', 'collection', '--min-games', str(min_games),
            *(['--final'] if final else []), *extra, '--out', str(out)]
    src = (f"import sys; sys.path[:0] = {[str(code), str(REPO), str(REPO/'src')]!r}; import x4s4io as io; io.JOB = {str(job)!r}; "
           f"import qualify4; qualify4.main({argv!r})")
    saved_job = io.JOB; use_job(job)
    try:
        with FastGuards():
            r = G.Runner(str(job), f'p3-{name}', [PY, '-B', '-c', src], outputs=[str(out)]); exits = []; r.exit = exits.append
            body = r.run()
    finally:
        use_job(saved_job)
    if body is None and (Path(job)/'receipts'/f'guard-p3-{name}.json').exists():      # a failing run returns no body: read the receipt
        body = json.loads((Path(job)/'receipts'/f'guard-p3-{name}.json').read_text())
    return out, body, exits


def ow_game(d, seed, n_roots, index=None, extra_rows=2, replay_exact=None):
    from imitation.exit_r1.rows import seal, write_json
    d = Path(d); g_index = 56+(seed % 2) if index is None else index
    rows, scores = [], []
    for t in range(n_roots+extra_rows):
        r = synth_row(seed, t); root = t < n_roots
        r.update(expert_actions=np.int16(2304), expert_action_supervision_valid=np.bool_(True), submitted_ticks=np.int32(t),
                 teacher_search_action=np.int16(2304), teacher_root=np.bool_(root), teacher_wait_kind=np.int8(0 if root else 1),
                 recorded_play_ticks=np.int32(-1), recorded_world_positions=np.array([np.nan, np.nan], np.float32),
                 submitted_world_positions=np.array([np.nan, np.nan], np.float32), recorded_millitiles=np.array([-1, -1], np.int32))
        rows.append(r); scores.append(dict(candidates=[5, 2304] if t % 3 else [2304], scores=[.1, .2] if t % 3 else [.3]) if root
                                      else dict(candidates=[], scores=[]))
    receipt = dict(seed=seed, index=g_index, seat=g_index % 2, opponent='v1', episode=dict(seed=seed, decks=[['a'], ['b']]),
                   outcome=1.0, root_decisions=n_roots)
    write_json(d/'replay.json', receipt)
    if replay_exact is not None: receipt = dict(receipt, replay_exact=replay_exact)
    seal(d, rows, scores, receipt)
    return io.verify_sealed_dir(str(d))[1]


def reseal_batch(bdir, key, mutate):
    """Forge a packed batch's own seal after mutating one array (so only the source binding can catch it)."""
    bdir = Path(bdir); f = bdir/'train'/f'{key}.npy'
    for p in bdir.rglob('*'):
        if p.is_file(): p.chmod(0o644)
    a = np.load(f); a = mutate(a); np.save(f, a, allow_pickle=False)
    tm = json.loads((bdir/'train'/'manifest.json').read_text()); tm['arrays'][key]['sha256'] = sha(f)
    (bdir/'train'/'manifest.json').write_text(json.dumps(tm))
    m = json.loads((bdir/'manifest.json').read_text())
    for rel in (f'train/{key}.npy', 'train/manifest.json'): m['files'][rel] = sha(bdir/rel)
    (bdir/'manifest.json').write_text(json.dumps(m))


def test_pipeline(tmp):
    stub_torch_imports()
    import label, verify_onpolicy as V, qualify4
    from imitation.exit_r1 import pack as packmod
    job = new_job(tmp)
    pk, ps = job/'collect'/'K4S-120'/'a1', job/'collect'/'S-200'/'a1'
    for i in range(6): write_collect_game(pk, 'K4S-120', i, range(100, 160, 10))
    write_collect_game(pk, 'K4S-120', 6, range(100, 160, 10), dup_of=C+0)
    for i in range(2000, 2004): write_collect_game(ps, 'S-200', i, range(100, 140, 10))
    for i in (3500, 3501): write_collect_game(pk, 'K4S-120', i, range(100, 130, 10))
    write_collect_game(pk, 'K4S-120', 9, range(100, 130, 10), block=False)
    label.CAPS = {'K4S-120': 30, 'S-200': 1000}
    plan_path = job/'data'/'label-plan.json'
    good_parity = parity_doc(tmp, [pk, ps])
    label.make_plan([str(pk), str(ps)], str(good_parity), str(plan_path))
    lp = json.loads(plan_path.read_text()); st = lp['stats']
    case('label plan: holdout split, interruption drop, dedup, per-arm cap, 600-tick duplicates; bound to the parity inventory',
         st['O']['dropped_no_block'] == 1 and st['O']['duplicate'] == 6 and st['O']['kept_per_arm'] == {'K4S-120': 30, 'S-200': 16}
         and st['O']['over_cap'] == 6 and st['holdout']['kept'] == 6 and lp['feature_only_duplicates_by_600_tick_bucket']['0']['feature_duplicates'] == 6
         and lp['parity_receipt_sha256'] == sha(good_parity))
    def plan_fails(mutate, parity=None, text=''):
        j2 = Path(tmp)/f'plan-{len(list(Path(tmp).glob("plan-*")))}'; shutil.copytree(job/'collect', j2/'collect'); (j2/'data').mkdir(); (j2/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n'); (j2/'watchdog').mkdir(); (j2/'watchdog'/'stop-periods.jsonl').write_text('')   # H-1 evidence
        phases = [j2/'collect'/'K4S-120'/'a1', j2/'collect'/'S-200'/'a1']
        q = parity_doc(j2, phases) if parity is None else parity(j2, phases)
        mutate(phases[0]); use_job(j2)
        try: label.make_plan([str(p) for p in phases], str(q), str(j2/'data'/'label-plan.json')); r = 'accepted'
        except label.PlanError as e: r = str(e)
        use_job(job); return text in r and r != 'accepted', r
    probes = dict(
        stale_block=plan_fails(lambda ph: (ph/'games'/'sim-0001-d27-K4S-120.json').write_text('{"changed": 1}'), text='block proof'),
        nonterminal=plan_fails(lambda ph: None, parity=lambda j2, phs: (write_collect_game(phs[0], 'K4S-120', 2, range(100, 130, 10), terminal=False),
                                                                        parity_doc_raw(j2, phs))[1], text='terminal'),
        seed_mismatch=plan_fails(lambda ph: write_collect_game(ph, 'K4S-120', 2, range(100, 130, 10), seed=C+99), text='identity'),
        public_parity_false=plan_fails(lambda ph: None, parity=lambda j2, phs: (write_collect_game(phs[0], 'K4S-120', 2, range(100, 130, 10), row_equals_build_public=False),
                                                                                parity_doc(j2, phs))[1], text='parity/pending'),
        failed_parity_no_exception=plan_fails(lambda ph: None, parity=lambda j2, phs: guarded_parity(j2, phs, 'noexc')[0], text='authentic'),
        failed_parity_unguarded=plan_fails(lambda ph: None, parity=lambda j2, phs: parity_doc(j2, phs, passed=False), text='guard receipt'),
        not_final=plan_fails(lambda ph: None, parity=lambda j2, phs: parity_doc(j2, phs, final=False), text='not final'),
        stale_parity=plan_fails(lambda ph: write_collect_game(ph, 'K4S-120', 7, range(100, 130, 10)), text='not a scheduled index'),   # r6: case binding refuses first
        final_evidence_deleted=plan_fails(lambda ph: (ph/'supervisor-exit.json').unlink(), text='supervisor-exit'),
        final_evidence_changed=plan_fails(lambda ph: wjson(ph/'supervisor-exit.json', dict(reason='memory_guard', returncode=-15, remaining_group_pids=[])),
                                          text='evidence changed'),
        smoke_bank_receipt=plan_fails(lambda ph: None, parity=lambda j2, phs: parity_doc(j2, phs, bank='smoke'), text='bank-C'))
    case('R2-F8/F13/R3-F5 probes: the plan refuses a stale block proof, a NON-TERMINAL game, a STALE parity receipt (games added after '
         'it), deleted or changed final phase evidence (Sol R3-F5), a smoke-bank receipt, a non-final receipt, public-parity false and a '
         'failed parity without an authentic exception',
         all(v[0] for v in probes.values()), probes={k: v[1][:70] for k, v in probes.items()})
    # authentic coordinator exception: a commit on origin/main whose COORDINATOR.md names the failed receipt's SHA
    j3 = Path(tmp)/'exc'; shutil.copytree(job/'collect', j3/'collect'); (j3/'data').mkdir(); (j3/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n'); (j3/'watchdog').mkdir(); (j3/'watchdog'/'stop-periods.jsonl').write_text('')   # H-1 evidence
    phases3 = [j3/'collect'/'K4S-120'/'a1', j3/'collect'/'S-200'/'a1']
    q3, g3, _ = guarded_parity(j3, phases3, 'exc')              # SA-5: real guard.py + qualify4 parity --final (no bless)
    assert g3 and g3['passed'] is True and json.loads(q3.read_text())['passed'] is False, (g3, q3)
    repo, head = git_repo(Path(tmp)/'coord', {'reports/strategy_council_20260928/COORDINATOR.md': f'C7b ruling: continue; receipt {sha(q3)}\n'.encode()})
    saved_repo = io.REPO; io.REPO = repo; use_job(j3)
    wjson(j3/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256=sha(q3), coordinator_ruling='x', decision='disclose'))
    bare = raises(lambda: label.make_plan([str(p) for p in phases3], str(q3), str(j3/'data'/'p1.json')), label.PlanError, 'authentic')
    (j3/'data'/'PARITY-EXCEPTION.json').unlink()
    wjson(j3/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256=sha(q3), coordinator_commit=head, decision='disclose'))
    label.make_plan([str(p) for p in phases3], str(q3), str(j3/'data'/'label-plan.json'))
    io.REPO = saved_repo; use_job(job)
    case('R2-F8: a bare exception string is refused; an exception bound to a coordinator commit on origin/main naming the receipt SHA is accepted',
         bare and json.loads((j3/'data'/'label-plan.json').read_text())['parity_exception']['coordinator_commit'] == head)
    # labeling
    def score_ok(info, opponent, rrs, crs, seed, digest=None): return 5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None]
    label.score_state = score_ok
    label.RAW = f'{job}/data/raw-O'; label.THREADS = 1; label.PLAN_SHA = sha(plan_path)
    res = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    first_receipt = wjson(job/'data'/'label-receipt-O-0.json', dict(label.summarize(res, len(res)), set='O', plan_sha256=sha(plan_path)))
    bless(first_receipt)                                            # r10 (R9-F6/F7): reuse needs the passed producer receipt
    again = [label.label_game(e) for e in lp['sets']['O'] if e['keep']]
    case('labeling seals every planned game; resume re-verifies the complete seal + identity and skips',
         all(r['status'] == 'sealed' for r in res) and all(r['status'] == 'already_sealed' for r in again))
    entry = next(e for e in lp['sets']['O'] if e['keep'])
    label.PLAN_SHA = 'f'*64; resume_bad = raises(lambda: label.label_game(entry), RuntimeError, 'identity differs'); label.PLAN_SHA = sha(plan_path)
    gdir = job/'data'/'raw-O'/entry['arm']/f"game-{entry['index']:04d}"
    (gdir/'extra.txt').write_text('x'); extra_bad = raises(lambda: label.label_game(entry), RuntimeError, 'seal'); (gdir/'extra.txt').unlink()
    io.remove_tree(str(gdir))
    stale_cap = raises(lambda: label.label_game(dict(entry, sha256='0'*64)), RuntimeError, 'changed since the plan')
    label.score_state = lambda *a, **k: (_ for _ in ()).throw(ValueError('engine defect'))
    narrow = raises(lambda: label.label_game(entry), ValueError, 'engine defect')
    label.score_state = score_ok; label.label_game(entry)
    case('F13/F5 probes: resume with another plan SHA or an extra file in the seal, a stale capture and an undeclared scorer exception all fail',
         resume_bad and extra_bad and stale_cap and narrow)
    n = len([e for e in lp['sets']['O'] if e['keep']])
    good = label.summarize(again, n)
    bad = label.summarize(again[:-1]+[dict(again[-1], status='memory_guard')], n)
    mism = label.summarize(again[:-1]+[dict(again[-1], drops=dict(digest_mismatch=1))], n)
    case('F5 probe: memory_guard -> incomplete + exit 1; 1 mismatch in 46 fails the 0.1% limit',
         good['passed'] and not bad['passed'] and raises(lambda: label.finish(f'{job}/data/lr-x.json', dict(bad, set='O')), SystemExit, '1')
         and not mism['passed'])
    good_receipt = job/'data'/'label-receipt-O-1.json'; io.write_json_once(str(good_receipt), dict(good, set='O', plan_sha256=sha(plan_path), threads=1))
    mism_receipt = Path(tmp)/'lr-mism.json'; wjson(mism_receipt, dict(mism, set='O', plan_sha256=sha(plan_path), threads=1))
    (job/'data'/'onpolicy').mkdir()
    planf = wjson(Path(tmp)/'plan.json', json.loads((HERE/'plan.json').read_text()))
    V.O_MIN, V.O_MAX, V.ARM_CAPS = 10, 100, {'K4S-120': 30, 'S-200': 1000}
    def verify(j, mode='O', receipts=None, selection=None, negative=False):
        use_job(j)
        rec = [str(j/'data'/'label-receipt-O-1.json')] if receipts is None else [str(r) for r in receipts]
        args = ['--mode', mode, '--plan', str(planf), '--label-receipts', *rec]
        if selection: args += ['--selection', str(selection)]
        root = j/'data'/V.MODES[mode][0]                          # r8: what the guarded producers would have recorded
        bless_into(j, *[d for d in sorted(root.glob('batch-*')) if (d/'manifest.json').exists()], *[Path(r) for r in rec if Path(r).exists()],
                   *[x for x in (j/'data'/'label-plan.json',) if x.exists()],
                   *[x for x in (Path(selection) if selection else None, j/'data'/'raw-OW-acceptance-smoke.json') if x and x.exists()],
                   allow_failed=negative)                  # SA-5: a failed receipt is blessed only for a negative (must be refused)
        rc = V.main(args); body = json.loads(next((j/'data').rglob('VERIFY-RECEIPT.json')).read_text())
        gate = j/'data'/V.MODES[mode][1]
        if gate.exists(): bless_into(j, gate)                      # the guarded verifier run's declared output
        use_job(job)
        return rc, body.get('error', '')
    def fresh(name, mutate=lambda j: None, pre=lambda j: None):
        j2 = Path(tmp)/('v-'+name); shutil.copytree(job, j2, symlinks=True)
        for p in j2.rglob('*'):
            if p.is_file() and not p.is_symlink(): p.chmod(0o644)
        pre(j2)
        use_job(j2); packmod.pack([j2/'data'/'raw-O'/'K4S-120', j2/'data'/'raw-O'/'S-200'], j2/'data'/'onpolicy'/'batch-0000'); use_job(job)
        mutate(j2); return j2
    jok = fresh('ok'); rc, err = verify(jok)
    case('verify O: passes with complete source re-verification and packed-byte binding', rc == 0, error=err)
    # R4-F1 (Sol): the gate must agree with the genuine verifier receipt it pins
    import studytree as ST
    use_job(jok); gate_ok = ST.authenticate_gate(str(jok), 'O')[1] == sha(jok/'data'/'O-VERIFIED.json')
    gp = jok/'data'/'O-VERIFIED.json'; gkeep = gp.read_bytes(); gp.chmod(0o644)
    def gate_probe(mutate, rec_mutate=None):
        g = json.loads(gkeep); mutate(g)
        rp_ = jok/'data'/'onpolicy'/'VERIFY-RECEIPT.json'; rkeep = rp_.read_bytes()
        if rec_mutate:
            rr = json.loads(rkeep); rec_mutate(rr); rp_.chmod(0o644); rp_.write_text(json.dumps(rr)); g['receipt_sha256'] = sha(rp_)
        gp.write_text(json.dumps(g)); bless_into(jok, gp)          # as if written by a guarded run: the field checks decide
        r_ = raises(lambda: ST.authenticate_gate(str(jok), 'O'), io.Refusal, 'gate')
        gp.write_bytes(gkeep); rp_.chmod(0o644); rp_.write_bytes(rkeep); return r_
    bdir = jok/'data'/'onpolicy'/'batch-0000'; train = Path(tmp)/'train-corpus'
    ow_game(Path(tmp)/'traw0'/'game-00000', C+0, 4, index=56); packmod.pack([Path(tmp)/'traw0'], train)
    shutil.move(str(bdir), str(Path(tmp)/'o-orig')); shutil.copytree(train, bdir)
    tmanifest = hashlib.sha256((bdir/'manifest.json').read_bytes()).hexdigest()
    gprobe = {"Sol R4-F1: training corpus + gate re-pinned, authentic receipt unchanged":
              gate_probe(lambda g: g['batches'][0].update(manifest_sha256=tmanifest))}
    shutil.rmtree(bdir); shutil.move(str(Path(tmp)/'o-orig'), str(bdir))
    gprobe['gate rows differ from the receipt'] = gate_probe(lambda g: g.update(rows=g['rows']+1))
    gprobe['gate source list differs'] = gate_probe(lambda g: g.update(sources_sha256='0'*64))
    gprobe['gate names another label plan'] = gate_probe(lambda g: g.update(label_plan_sha256='0'*64))
    gprobe['incomplete receipt body (passed/mode only)'] = gate_probe(lambda g: None, rec_mutate=lambda r: [r.pop(k) for k in list(r) if k not in ('passed', 'mode')])
    gprobe['receipt not sealed'] = gate_probe(lambda g: None, rec_mutate=lambda r: r.update(sealed=False))
    use_job(job)
    case('R4-F1 probes (Sol): authenticate_gate accepts the genuine gate+receipt pair and refuses a gate re-pinned to a training corpus '
         'beside its unchanged authentic receipt, changed counts/sources/plan identity, and an incomplete or unsealed receipt body',
         gate_ok and all(gprobe.values()), probes=gprobe)
    neg = {}
    neg['mismatch receipt'] = verify(fresh('mm'), receipts=[mism_receipt], negative=True)
    def teacher(j):        # Sol R2-F5 probe: raw-O receipt teacher changed, manifest and packed corpus unchanged
        g = next((j/'data'/'raw-O'/'K4S-120').glob('game-*')); r = json.loads((g/'receipt.json').read_text())
        r['teacher'] = 'UNREVIEWED_TEACHER'; (g/'receipt.json').write_text(json.dumps(r))
    neg['R2-F5 Sol probe: unreviewed teacher in a raw receipt'] = verify(fresh('teacher', mutate=teacher))
    def bump(a):
        a = a.copy(); a.flat[0] = a.flat[0]+1; return a
    neg['packed bytes forged (own seal resealed)'] = verify(fresh('forge', mutate=lambda j: reseal_batch(j/'data'/'onpolicy'/'batch-0000', 'hand_ids', bump)))
    neg['stale plan SHA'] = verify(fresh('ps', mutate=lambda j: wjson(j/'data'/'label-plan.json', dict(lp, utc='changed'))))
    V.O_MIN = 1000; neg['below the O minimum'] = verify(fresh('min')); V.O_MIN = 10
    neg['symlink in batch'] = verify(fresh('sl', mutate=lambda j: os.symlink('/etc/passwd', j/'data'/'onpolicy'/'batch-0000'/'train'/'evil.npy')))
    case('R2-F5/F13 probes: verify O rejects a broken raw seal (teacher edit), forged packed bytes, a failed receipt, a stale plan, small O, a symlink',
         all(v[0] == 1 for v in neg.values()), errors={k: v[1][:80] for k, v in neg.items()})
    # O_W gate
    def ow_case(name, target, games=(0, 1, 2, 3), sel=None, acc=None, seed_shift=None):
        j = Path(tmp)/('ow-'+name); new_job(j, 'job'); j = use_job(j/'job')
        rows = []
        for g in games:
            msha = ow_game(j/'data'/'raw-OW'/f'game-{g:05d}', CW+g+(1 if seed_shift == g else 0), 15, index=56+g % 2)
            rows.append(dict(g=g, seed=CW+g, index=56+g % 2, seat=g % 2, own=g % 5, opponent=(g//5) % 5, roots=15, manifest_sha256=msha))
        packmod.pack([j/'data'/'raw-OW'], j/'data'/'onpolicy-w'/'batch-0000')
        og = wjson(j/'data'/'O-VERIFIED.json', dict(rows=target))
        arows = []
        for g in (0, 1):
            m = ow_game(j/'data'/'raw-OW-acceptance'/f'game-{g:05d}', QUAL+g, 5, index=56+g % 2, replay_exact=True)
            arows.append(dict(g=g, seed=QUAL+g, index=56+g % 2, seat=g % 2, roots=5, manifest_sha256=m, replay_exact=True, status='sealed'))
        accd = dict(schema='x4s4.ow-acceptance.v2', bank='qualification', base=QUAL, games=arows, passed=True, v1_sha256=V.V1_SHA, emitter_sha256=V.EMITTER_SHA)
        wjson(j/'data'/'raw-OW-acceptance-smoke.json', acc(accd) if acc else accd)
        s = dict(reached=True, target_roots=target, selected_games=list(range(len(games))), selected_roots=15*len(games), last_game_roots=15,
                 games=rows, v1_sha256=V.V1_SHA, emitter_sha256=V.EMITTER_SHA)
        s.update(sel or {}); wjson(j/'data'/'raw-OW-selection.json', s)
        bless_into(j, *[d for d in sorted((j/'data'/'onpolicy-w').glob('batch-*')) if (d/'manifest.json').exists()],
                   j/'data'/'raw-OW-selection.json', j/'data'/'raw-OW-acceptance-smoke.json', og)   # r8: the guarded producers
        import studytree as _st
        real_ag = _st.authenticate_gate
        def synthetic_o_gate(job_, mode):                       # r9 (R8-F4): verify OW authenticates the O gate; the
            if mode != 'O': return real_ag(job_, mode)          # synthetic O gate here has no corpus, so only its
            if _st.guarded_output(job_, str(og)) is None: raise io.Refusal('gate', 'O gate has no passed guard receipt')
            return [], sha(og), json.loads(og.read_text())      # guard is real; the corpus checks are tested elsewhere
        _st.authenticate_gate = synthetic_o_gate
        try: rc_ = V.main(['--mode', 'OW', '--plan', str(planf), '--selection', str(j/'data'/'raw-OW-selection.json')])
        finally: _st.authenticate_gate = real_ag
        body = json.loads((j/'data'/'onpolicy-w'/'VERIFY-RECEIPT.json').read_text()); use_job(job)
        return rc_, body
    rc, body = ow_case('ok', 46)
    case('verify OW: minimal prefix (45 < 46 <= 60), selection identity rows, authenticated acceptance, single-candidate share',
         rc == 0 and body['roots'] == 60 and body['rows'] == 68 and 0 < body['single_candidate_root_share'] < 1, error=body.get('error'))
    owneg = dict(non_minimal=ow_case('nm', 45), short=ow_case('short', 61), gap_0124=ow_case('gap', 46, games=(0, 1, 2, 4)),
                 seed_not_cprime_g=ow_case('seed', 46, seed_shift=2), last_game_roots_claim=ow_case('lgr', 46, sel=dict(last_game_roots=14)),
                 acceptance_boolean_only=ow_case('acc1', 46, acc=lambda a: {'passed': True}),
                 acceptance_one_game=ow_case('acc2', 46, acc=lambda a: dict(a, games=a['games'][:1])),
                 acceptance_on_cprime=ow_case('acc3', 46, acc=lambda a: dict(a, base=CW)),
                 selection_row_manifest=ow_case('selm', 46, sel=dict(games=[dict(r, manifest_sha256='0'*64) for r in []])))
    case("F6/R2-F5 probes: O_W gate rejects a non-minimal prefix, a short prefix, sources [0,1,2,4], a wrong seed, a wrong last-game claim, "
         "Sol's Boolean-only acceptance receipt, a one-game or C'-bank acceptance, and a selection without identity rows",
         all(v[0] == 1 for v in owneg.values()), errors={k: v[1].get('error', '')[:70] for k, v in owneg.items()})
    # collect_w: resume identity and the in-flight hard-stop path
    import collect_w
    cw = new_job(tmp, 'cwjob'); collect_w.JOB = str(cw)
    collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
    collect_w.OUT = f'{cw}/data/raw-OW'; (cw/'data'/'raw-OW').mkdir()
    collect_w.resources_ok = lambda disk=True: True
    def sealed_game(g, **over):
        own, opp, seat, index, decks = collect_w.game_inputs(g)
        from imitation.exit_r1.rows import seal, write_json
        d = cw/'data'/'raw-OW'/f'game-{g:05d}'
        r = dict(seed=CW+g, index=index, opponent='v1', seat=seat, root_decisions=3, outcome=1.0,
                 episode=dict(decks=[collect_w.X[own], collect_w.X[opp]] if seat == 0 else [collect_w.X[opp], collect_w.X[own]]))
        r.update(over); write_json(d/'replay.json', r)
        rows, scores = [], []
        for t in range(3):
            row = synth_row(CW+g, t); row.update(expert_actions=np.int16(2304), expert_action_supervision_valid=np.bool_(True),
                submitted_ticks=np.int32(t), teacher_search_action=np.int16(2304), teacher_root=np.bool_(True), teacher_wait_kind=np.int8(0),
                recorded_play_ticks=np.int32(-1), recorded_world_positions=np.array([np.nan, np.nan], np.float32),
                submitted_world_positions=np.array([np.nan, np.nan], np.float32), recorded_millitiles=np.array([-1, -1], np.int32))
            rows.append(row); scores.append(dict(candidates=[5, 2304], scores=[.1, .2]))
        seal(d, rows, scores, r); return d
    d3 = sealed_game(3)
    saved_em = collect_w.emitter; collect_w.emitter = types.SimpleNamespace(run_game=lambda *a, **k: None)   # a replay would stop at once
    no_ev = collect_w.play((3, CW))['status'] == 'stopped' and not d3.exists() and list(d3.parent.glob('unaccepted-game-00003-*'))
    d3 = sealed_game(3); m3 = hashlib.sha256((d3/'manifest.json').read_bytes()).hexdigest()   # r10: reuse needs the guarded selection
    bless(wjson(cw/'data'/'raw-OW-selection.json', dict(games=[dict(g=3, manifest_sha256=m3)])))
    ok = collect_w.play((3, CW))['status'] == 'already_sealed' and bool(no_ev); collect_w.emitter = saved_em
    sealed_game(4, seed=CW+99); bad_seed = raises(lambda: collect_w.play((4, CW)), AssertionError, 'identity')
    sealed_game(5, opponent='script'); bad_opp = raises(lambda: collect_w.play((5, CW)), AssertionError, 'identity')
    d6 = sealed_game(6); (d6/'replay.json').write_text((d6/'replay.json').read_text().replace('"root_decisions": 3', '"root_decisions": 4'))
    bad_seal = raises(lambda: collect_w.play((6, CW)), AssertionError, 'seal')
    (cw/'data'/'raw-OW'/'game-00007').mkdir(); unsealed = raises(lambda: collect_w.play((7, CW)), AssertionError, 'unsealed')
    def crossing(seed, index, directory, opponent, stop):      # the emitter call straddles the hard stop
        (cw/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n'); return dict(root_decisions=3, cpu_seconds=1.0)
    collect_w.emitter = types.SimpleNamespace(run_game=crossing)
    past = collect_w.play((8, CW))['status'] == 'past_hard_stop'
    (cw/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    os.symlink(cw/'nowhere', cw/'STOP'); stopped = collect_w.play((9, CW)) == dict(g=9, status='stopped')
    import studytree
    mon = studytree.monitor(str(cw))
    case('R2-F3/F6 probes: collect_w resume re-verifies the complete seal and realized identity; a game straddling the hard stop is '
         'NOT counted; a dangling STOP stops dispatch and the parent monitor (which stops in-flight workers) sees it',
         ok and bad_seed and bad_opp and bad_seal and unsealed and past and stopped and mon == 'owned_STOP')


def parity_doc_raw(j2, phs):
    """Parity receipt WITHOUT re-proving games (used to plant a receipt over a non-terminal game)."""
    inv = [[str(p), n, sha(Path(p)/'games'/n)] for p in sorted(map(str, phs)) for n in sorted(os.listdir(Path(p)/'games'))
           if (Path(p)/'blocks'/f"{n.split('-')[1]}.json").exists()]
    import qualify4
    for ph in phs:
        if not (Path(ph)/'supervisor-exit.json').exists(): finish_phase(ph)
    doc = wjson(Path(j2)/'parity-raw.json', dict(check='parity', passed=True, final=True, bank='collection', phases=sorted(str(p) for p in phs),
                                                 inventory=inv, evidence=qualify4.phase_evidence([str(p) for p in phs], 'collection')))
    bless_into(job_of(phs[0]), doc)
    return doc


# ================================================================ driver (R2-F1, R2-F2, R2-F3)
def driver_module(tmp):
    job = new_job(tmp, 'djob')
    drv = load_fresh('driver_t%d' % random.randrange(10**9), HERE/'driver.py')
    return drv, job


def phase_fixture(drv, job, sid='R3a', arm='K4S-120', a='a1', reason=None, rc=0, blocks=10, indices=10, workers=2, child_exit=None):
    d = job/'games'/sid/arm/a; (d/'blocks').mkdir(parents=True)
    wjson(d/'schedule.json', dict(indices=list(range(indices)))); wjson(d/'launch.json', dict(workers=workers))
    for i in range(blocks): wjson(d/'blocks'/f'{i:04d}.json', {})
    wjson(d/'supervisor-exit.json', dict(reason=reason, returncode=rc))
    rec = dict(launched_at_utc='2026-10-13T00:00:00Z', launch_id='L-'+a+sid+arm, pid=2**22+7, pgid=2**22+7, starttime=12345)
    rp = job/'receipts'/f'phase-{sid}-{arm}-{a}-launch.json'; wjson(rp, rec)
    if child_exit is not None:
        with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='2026-10-13T01:00:00Z', kind='child_exit', pid=rec['pid'], launch_id=rec['launch_id'], exit_code=child_exit))+'\n')
    return d, rec, rp


def test_driver(tmp):
    drv, job = driver_module(tmp/'a')
    state = dict(fits={'R5': 'done', 'R5-rep': 'running', 'R5W': 'pending'}, done={})
    drv.fit_state = lambda f: (state['fits'][f], None)
    drv.ready_students = lambda: list(drv.STUDENT_ORDER)
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
    case('driver: no reporting phase while any fit is not done; ABBA order, all ten phases, no futility skip',
         none_while_fit and order == [f'{s}/{a}' for s in ('R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W') for a in ('K4S-120', 'S-200')])
    tree = ast.parse((HERE/'driver.py').read_text())
    subs = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in ('loss', 'winner', 'outcome')]
    case('driver never reads a game outcome (only the fit training loss)', subs == ["json.loads(line)['loss']"], subs=subs)
    # R2-F1 probe (Sol): driver/events.jsonl symlinked to an outside sentinel
    drv, job = driver_module(tmp/'b')
    sentinel = Path(tmp)/'sentinel'; sentinel.write_bytes(b'SENTINEL'); os.symlink(sentinel, job/'driver'/'events.jsonl')
    case('R2-F1 probe (Sol): driver event() refuses a symlinked events.jsonl; the outside sentinel is unchanged',
         raises(lambda: drv.event(kind='x'), io.Refusal) and sentinel.read_bytes() == b'SENTINEL')
    # R2-F2 probes
    drv, job = driver_module(tmp/'c')
    launched = []; drv.launch_phase = lambda *a: launched.append(a); drv.resources_ok = lambda for_fit=False: True
    drv.next_phase = lambda: ('R3a', 'S-200', [0]); (job/'REPORTING.GO').write_text('')
    d, rec, rp = phase_fixture(drv, job, child_exit=17)
    drv.games_tick()
    sol = (job/'driver'/'ANOMALY-exit-games_R3a_K4S-120_a1.json').exists() and not (d/'SETTLED.json').exists() and not launched
    drv2, job2 = driver_module(tmp/'d'); d2, rec2, rp2 = phase_fixture(drv2, job2, child_exit=None)
    drv2.settle_attempt(str(d2).replace(str(job2), drv2.J))
    unknown = (job2/'driver'/'ANOMALY-exit-games_R3a_K4S-120_a1.json').exists() and not (d2/'SETTLED.json').exists()
    wjson(job2/'driver'/'ACK-exit-games_R3a_K4S-120_a1.json', dict(launch_id='WRONG', pid=rec2['pid'], starttime=rec2['starttime'],
          receipt_sha256=sha(rp2), disposition='retire', owner='sam'))
    drv2.settle_attempt(str(d2)); stale_ack = (job2/'driver'/'ANOMALY-stale-ack-exit-games_R3a_K4S-120_a1.json').exists() and not (d2/'SETTLED.json').exists()
    (job2/'driver'/'ACK-exit-games_R3a_K4S-120_a1.json').unlink()
    wjson(job2/'driver'/'ACK-exit-games_R3a_K4S-120_a1.json', dict(launch_id=rec2['launch_id'], pid=rec2['pid'], starttime=rec2['starttime'],
          receipt_sha256=sha(rp2), disposition='retire', owner='sam'))
    drv2.settle_attempt(str(d2))
    settled = json.loads((d2/'SETTLED.json').read_text()) if (d2/'SETTLED.json').exists() else {}
    consumed = not (job2/'driver'/'ACK-exit-games_R3a_K4S-120_a1.json').exists() and list((job2/'driver').glob('ACK-exit-*.consumed-*.json'))
    case("R2-F2 probes: Sol's child-17 + clean receipt is an anomaly with no SETTLED and no dispatch; an unknown child status needs an ACK "
         "bound to the exact attempt (a wrong launch_id is a stale-ACK anomaly); the right ACK settles, keeps the evidence and is consumed",
         sol and unknown and stale_ack and settled.get('disposition') == 'owner_ack' and settled.get('ack', {}).get('launch_id') == rec2['launch_id']
         and bool(consumed) and not (job2/'driver'/'ANOMALY-exit-games_R3a_K4S-120_a1.json').exists())
    drv3, job3 = driver_module(tmp/'e')
    d3, _, _ = phase_fixture(drv3, job3, reason='memory_guard', rc=-15, blocks=0, child_exit=1); drv3.settle_attempt(str(d3))
    d4, _, _ = phase_fixture(drv3, job3, a='a2', blocks=10, child_exit=0); drv3.settle_attempt(str(d4))
    case('R2-F2 controls: a permitted guard stop with child status 1 retires started seeds; a clean receipt with child 0 settles clean',
         json.loads((d3/'SETTLED.json').read_text())['disposition'] == 'guard_stop'
         and json.loads((job3/'driver'/'retired.json').read_text())['indices'] == [0, 1, 2]
         and json.loads((d4/'SETTLED.json').read_text())['disposition'] == 'clean')
    # fit completion: clean return + known zero exit of THIS launch; unknown exit needs an exact-attempt ACK
    drv, job = driver_module(tmp/'f')
    out = job/'fits'/'R5'; out.mkdir(parents=True, exist_ok=True)
    wjson(out/'complete.json', dict(stopped=False, step=2500)); wjson(out/'segment.json', dict(status='returned'))
    rec = dict(pid=2**22+12345, pgid=2**22+12345, starttime=99, launch_id='FITL', launched_at_utc='2026-10-13T00:00:00Z')
    rp = wjson(job/'receipts'/'fit-R5-launch.json', rec)
    states = [drv.fit_state('R5')[0]]
    with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='x', kind='child_exit', pid=rec['pid'], launch_id='OTHER', exit_code=0))+'\n')
    states.append(drv.fit_state('R5')[0])
    wjson(job/'driver'/'ACK-fit-R5-exit.json', dict(launch_id='FITL', pid=rec['pid'], starttime=99, receipt_sha256=sha(rp), disposition='success', owner='sam'))
    states.append(drv.fit_state('R5')[0]); states.append(drv.fit_state('R5')[0])
    drv.EXIT[rec['pid']] = 3; drv.LAUNCHED[rec['pid']] = 'FITL'; states.append(drv.fit_state('R5')[0])
    case('R2-F2/decision-2: fit done only with a clean return and a zero exit of THIS launch; an exit event of another launch does not count; '
         'an exact-attempt ACK resolves an unknown exit once (consumed, durable resolution); a known nonzero exit stays failed',
         states == ['failed', 'failed', 'done', 'done', 'failed'] and not (job/'driver'/'ACK-fit-R5-exit.json').exists(), states=states)
    # R2-F3 probes: live fit guard and admission
    drv, job = driver_module(tmp/'g')
    rec = dict(pid=os.getpid(), pgid=os.getpgrp(), starttime=io.proc_stat(os.getpgrp())['starttime'], launch_id='G', launched_at_utc=drv.utc())
    drv.fit_state = lambda fid: ('running', rec)
    sent = []; drv.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
    drv.io.signal_pid = lambda pid, pgid, st, sig: sent.append(('pid', sig)) or True
    drv.io.stop_owned = lambda *a, **k: sent.append(('group',)) or True
    drv.io.group_alive = lambda *a: False
    drv.mem_available = lambda: 100*2**30; drv.gpu_used_mib = lambda: 1000
    drv.studytree = types.SimpleNamespace(**{k: getattr(drv.studytree, k) for k in dir(drv.studytree) if not k.startswith('__')})
    drv.studytree.pss_bytes = lambda pids: 1 << 30
    def guard(**over):
        sent.clear()
        for f in (job/'driver').glob('ANOMALY-*'): f.unlink()
        saved = {k: getattr(drv, k) if k != 'pss' else drv.studytree.pss_bytes for k in over}
        for k, v in over.items():
            if k == 'pss': drv.studytree.pss_bytes = v
            else: setattr(drv, k, v)
        drv.Fits().guard('R5')
        an = json.loads((job/'driver'/'ANOMALY-fit-R5.json').read_text())['reason'] if (job/'driver'/'ANOMALY-fit-R5.json').exists() else None
        for k, v in saved.items():
            if k == 'pss': drv.studytree.pss_bytes = v
            else: setattr(drv, k, v)
        return bool(sent), an
    g = dict(clean=guard(), memory_zero=guard(mem_available=lambda: 0), memory_unreadable=guard(mem_available=lambda: None),
             gpu_unreadable=guard(gpu_used_mib=lambda: None), gpu_over=guard(gpu_used_mib=lambda: 45000),
             pss_over_50=guard(pss=lambda pids: 51*2**30), pss_unreadable=guard(pss=lambda pids: None))
    case("R2-F3 probes (Sol): a running fit is stopped (signal sent + blocking ANOMALY-fit) on MemAvailable 0 or unreadable, GPU unreadable "
         "or > 40 GB, and PSS > 50 GiB (frozen rule restored) or unreadable; a healthy fit is left alone",
         g['clean'] == (False, None) and all(v[0] and v[1] for k, v in g.items() if k != 'clean') and drv.studytree.PSS_LIMIT == 50*2**30,
         guards={k: v[1] for k, v in g.items()})
    drv, job = driver_module(tmp/'h')
    drv.mem_available = lambda: 100*2**30; drv.psi_some_avg10 = lambda: 1.0; drv.gpu_used_mib = lambda: 100
    drv.studytree = types.SimpleNamespace(admission=lambda job, add=0, disk=True: (add+5 <= 70, None), MEM_FLOOR=24*2**30)
    base_ok = drv.resources_ok() and drv.resources_ok(for_fit=True)
    adm = {}
    for name, attr, val, fit in (('psi unreadable', 'psi_some_avg10', lambda: None, False), ('psi > 10', 'psi_some_avg10', lambda: 10.5, False),
                                 ('mem unreadable', 'mem_available', lambda: None, False), ("Sol's 50,000 MiB GPU", 'gpu_used_mib', lambda: 50000, True),
                                 ('GPU unreadable', 'gpu_used_mib', lambda: None, True)):
        old = getattr(drv, attr); setattr(drv, attr, val); adm[name] = not drv.resources_ok(for_fit=fit); setattr(drv, attr, old)
    drv.studytree = types.SimpleNamespace(admission=lambda job, add=0, disk=True: (add+20 <= 70, None), MEM_FLOOR=24*2**30)
    adm['reporting reservation (20 live + 53 new > 70)'] = not drv.resources_ok()
    me = io.own_identity(); wjson(job/'driver'/'DIAGNOSTIC.lock', dict(pid=me['pid'], starttime=me['starttime']))
    drv.studytree = types.SimpleNamespace(admission=lambda job, add=0, disk=True: (True, None), MEM_FLOOR=24*2**30)
    adm['live diagnostic lock'] = not drv.resources_ok()
    case('R2-F3 probes: admission fails closed on unreadable PSI/memory/GPU, PSI > 10, GPU already 50,000 MiB, a reservation that would '
         'exceed 70 processes, and a live diagnostic lock', base_ok and all(adm.values()), adm=adm)
    # R4-F3 probes (Sol): a STOPPED completion gets the same exit reconciliation as a final one
    def stopped_case(sub, seg_status, exit_code):
        drv, job = driver_module(tmp/sub)
        out = job/'fits'/'R5'; out.mkdir(parents=True, exist_ok=True)
        wjson(out/'complete.json', dict(stopped=True, step=250)); wjson(out/'segment.json', dict(status=seg_status))
        rec = dict(pid=2**22+999, pgid=2**22+999, starttime=7, launch_id='SL', launched_at_utc='2026-10-13T00:00:00Z')
        wjson(job/'receipts'/'fit-R5-launch.json', rec)
        if exit_code is not None:
            with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='x', kind='child_exit', pid=rec['pid'], launch_id='SL', exit_code=exit_code))+'\n')
        wjson(job/'data'/'O-VERIFIED.json', {})
        calls = []; drv.live_supervisor = lambda: None; drv.resources_ok = lambda for_fit=False: True
        fits = drv.Fits(); fits.launch = lambda fid, st: calls.append((fid, st)); fits.tick()
        return drv.fit_state('R5')[0], calls, (job/'driver'/'ANOMALY-fit-R5-exit.json').exists()
    sol = stopped_case('s1', 'failed', 17); unknown = stopped_case('s2', 'returned', None); clean = stopped_case('s3', 'returned', 0)
    case("R4-F3 probes (Sol): stopped completion + failed segment + exit 17 is 'failed' with a blocking anomaly and NO resume; an "
         "unknown exit also blocks; a clean authorized stop (segment returned, exit 0) resumes",
         sol == ('failed', [], True) and unknown == ('failed', [], True) and clean == ('stopped', [('R5', 'stopped')], False),
         got=[sol, unknown, clean])
    # R4-F2 probes (Sol): calibration admission, live monitoring and late results; nothing new after STOP/deadline
    def cal_driver(sub):
        drv, job = driver_module(tmp/sub)
        drv.resources_ok = lambda for_fit=False: True; drv.CALIBRATION_POLL = 0.1
        started = []
        def fake_launch(name, argv, log, receipt, env, cwd=None, extra_rec=None, cmd='sleep 60'):
            started.append(name)
            child = io.spawn(['/bin/sh', '-c', drv._cmd], log, dict(PATH='/usr/bin:/bin'))
            drv.POPEN[child['pid']] = child['popen']; drv.LAUNCHED[child['pid']] = 'CAL'
            return dict(launch_id='CAL', pid=child['pid'], pgid=child['pgid'], starttime=child['starttime'])
        drv.launch = fake_launch; drv._cmd = 'sleep 60'
        return drv, job, started
    drv, job, started = cal_driver('c1'); cal = f'{job}/calibration/R5.json'; (job/'calibration').mkdir(exist_ok=True)
    os.symlink(job/'nowhere', job/'STOP'); stop_adm = drv.run_calibration('R5', 'x', cal) == 'not_admitted' and not started; (job/'STOP').unlink()
    drv.STOP_AT = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc); dl_adm = drv.run_calibration('R5', 'x', cal) == 'not_admitted' and not started
    drv.STOP_AT = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
    seq = iter([None, 'memory_floor']); drv.calibration_breach = lambda rec: next(seq, 'memory_floor')
    t0 = time.monotonic(); inflight = drv.run_calibration('R5', 'x', cal); el = time.monotonic()-t0
    inflight_ok = inflight == 'stopped' and el < 30 and (job/'driver'/'ANOMALY-calibration-R5.json').exists()
    drv, job, started = cal_driver('c2'); cal = f'{job}/calibration/R5.json'; (job/'calibration').mkdir(exist_ok=True)
    drv.calibration_breach = lambda rec: None; drv._cmd = f'sleep 0.6; echo {{}} > {cal}'
    drv.STOP_AT = datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=0.3)
    late = drv.run_calibration('R5', 'x', cal) == 'stopped' and not os.path.exists(cal) and list((job/'calibration').glob('R5.json.rejected-*'))
    drv.STOP_AT = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc); good = drv.run_calibration('R5', 'x', cal) == 'ok' and os.path.exists(cal)
    drv3, job3, _ = cal_driver('c3'); spy = []
    drv3.fit_state = lambda f: ('done', None); drv3.run_calibration = lambda *a: spy.append(a) or 'ok'
    os.symlink(job3/'nowhere', job3/'STOP'); drv3.prepare_students(); (job3/'STOP').unlink()
    drv3.STOP_AT = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc); drv3.prepare_students()
    case("R4-F2 probes (Sol): with STOP or a past deadline neither prepare_students nor calibration reaches a child; a running "
         "calibration is stopped by PID on a live breach (anomaly); a success returned after the deadline is rejected; a clean one is accepted",
         stop_adm and dl_adm and inflight_ok and bool(late) and good and spy == [], got=dict(stop=stop_adm, deadline=dl_adm, inflight=inflight, late=bool(late), good=good))
    # R3-F2 probes (Sol): live study caps on a running fit and the guard through teardown
    drv, job = driver_module(tmp/'g2')
    rec = dict(pid=os.getpid(), pgid=os.getpgrp(), starttime=io.proc_stat(os.getpgrp())['starttime'], launch_id='G', launched_at_utc=drv.utc())
    drv.fit_state = lambda fid: ('running', rec)
    sent2 = []; drv.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
    drv.io.signal_pid = lambda *a: sent2.append('pid') or True; drv.io.stop_owned = lambda *a, **k: True; drv.io.group_alive = lambda *a: False
    drv.mem_available = lambda: 100*2**30; drv.gpu_used_mib = lambda: 1000
    drv.studytree = types.SimpleNamespace(**{k: getattr(drv.studytree, k) for k in dir(drv.studytree) if not k.startswith('__')})
    drv.studytree.pss_bytes = lambda pids: 1 << 30
    drv.studytree.admission = lambda job, add=0, disk=True: (False, '71 X4S-4 processes')
    drv.Fits().guard('R5')
    cap = bool(sent2) and json.loads((job/'driver'/'ANOMALY-fit-R5.json').read_text())['reason'] == 'study_tree_cap'
    (job/'driver'/'ANOMALY-fit-R5.json').unlink(); sent2.clear()
    drv.studytree.admission = lambda job, add=0, disk=True: (True, None)
    wjson(job/'fits'/'R5'/'complete.json', dict(stopped=False, step=2500)); drv.mem_available = lambda: 0
    drv.Fits().guard('R5')
    teardown = bool(sent2) and json.loads((job/'driver'/'ANOMALY-fit-R5.json').read_text())['reason'] == 'memory_floor'
    case('R3-F2 probes (Sol): a live fit is stopped by the study process/disk cap, and MemAvailable 0 during teardown still stops it',
         cap and teardown)
    # R3-F6 probes (Sol): generic ACKs
    drv, job = driver_module(tmp/'g3')
    drv.anomaly('driver-exception', error='x')
    (job/'driver'/'ACK-driver-exception.json').write_text('NOT JSON OR AN ATTEMPT ACK')
    malformed = drv.unresolved_anomalies() == ['driver-exception'] and (job/'driver'/'ACK-driver-exception.json').exists()
    (job/'driver'/'ACK-driver-exception.json').unlink(); os.symlink(job/'nowhere', job/'driver'/'ACK-driver-exception.json')
    dangling = drv.unresolved_anomalies() == ['driver-exception']; (job/'driver'/'ACK-driver-exception.json').unlink()
    wjson(job/'driver'/'ACK-driver-exception.json', dict(anomaly_sha256='0'*64, disposition='continue', owner='sam'))
    stale = drv.unresolved_anomalies() == ['driver-exception']; (job/'driver'/'ACK-driver-exception.json').unlink()
    wjson(job/'driver'/'ACK-driver-exception.json', dict(anomaly_sha256=sha(job/'driver'/'ANOMALY-driver-exception.json'), disposition='continue', owner='sam'))
    resolved = drv.unresolved_anomalies() == [] and not (job/'driver'/'ACK-driver-exception.json').exists() and list((job/'driver').glob('RESOLVED-driver-exception-*.json'))
    drv.anomaly('exit-games_R3a_K4S-120_a1', reason='x'); wjson(job/'driver'/'ACK-exit-games_R3a_K4S-120_a1.json', dict(anomaly_sha256=sha(job/'driver'/'ANOMALY-exit-games_R3a_K4S-120_a1.json'), disposition='continue', owner='sam'))
    attempt_needs_attempt_ack = drv.unresolved_anomalies() == ['exit-games_R3a_K4S-120_a1']
    case("R3-F6 probes (Sol): a malformed, dangling or stale generic ACK keeps blocking; a valid one (anomaly SHA + 'continue' + owner) is "
         'consumed and archived; an attempt anomaly cannot be cleared by a generic ACK', malformed and dangling and stale and bool(resolved) and attempt_needs_attempt_ack)
    # R3-F1 probes (Sol): the frozen fit writer's existing tree is validated before every (resumed) launch
    drv, job = driver_module(tmp/'g4')
    sentinel = Path(tmp)/'fit-sentinel'; sentinel.write_bytes(b'SENTINEL')
    (job/'fits'/'R5').mkdir(parents=True, exist_ok=True); os.symlink(sentinel, job/'fits'/'R5'/'runtime.json')
    fit_probes = dict(symlinked_runtime_json=raises(lambda: drv.prepare_fit_dirs('R5'), io.Refusal, 'symlink'))
    (job/'fits'/'R5'/'runtime.json').unlink(); os.link(sentinel, job/'fits'/'R5'/'train.jsonl')
    fit_probes['hard_linked_train_jsonl'] = raises(lambda: drv.prepare_fit_dirs('R5'), io.Refusal, 'hard-linked')
    (job/'fits'/'R5'/'train.jsonl').unlink(); (job/'cache'/'fit'/'tmp').mkdir(parents=True, exist_ok=True); os.symlink(sentinel, job/'cache'/'fit'/'tmp'/'x')
    fit_probes['symlink_in_cache'] = raises(lambda: drv.prepare_fit_dirs('R5'), io.Refusal, 'symlink')
    (job/'cache'/'fit'/'tmp'/'x').unlink()
    (job/'fit').mkdir(exist_ok=True); (job/'fit'/'run_fit.sh').write_text('#'); (job/'fit'/'loader6.json').write_text('{}')
    wjson(job/'RUNTIME-INVENTORY.json', {'fit/run_fit.sh': sha(job/'fit'/'run_fit.sh'), 'fit/loader6.json': '0'*64})
    fit_probes['loader_not_pinned'] = raises(lambda: drv.prepare_fit_dirs('R5'), io.Refusal, 'loader6')
    wjson(job/'RUNTIME-INVENTORY.json', {'fit/run_fit.sh': sha(job/'fit'/'run_fit.sh'), 'fit/loader6.json': sha(job/'fit'/'loader6.json')})
    fit_probes['gate_not_authenticated'] = raises(lambda: drv.prepare_fit_dirs('R5'), io.Refusal)
    drv.studytree = types.SimpleNamespace(**{k: getattr(drv.studytree, k) for k in dir(drv.studytree) if not k.startswith('__')})
    drv.studytree.authenticate_gate = lambda j, mode: ([f'{j}/data/onpolicy/batch-0000', f'{j}/data/onpolicy/batch-0001'], 'G'*64, {})
    spawned = []; drv.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
    drv.io.spawn = lambda argv, log, env, roles=('logs',), cwd=None: spawned.append(argv) or dict(pid=4243, pgid=4243, starttime=1, popen=None)
    drv.Fits().launch('R5', 'pending')
    launched_ok = spawned and spawned[0][-3:] == ['-', 'batch-0000', 'batch-0001'] and json.loads((job/'receipts'/'fit-R5-launch.json').read_text())['gate_sha256'] == 'G'*64
    case('R3-F1 probes (Sol): before a fit launch the driver refuses a symlinked runtime.json (the frozen writer target), a hard-linked '
         'train.jsonl, a link inside cache/fit, an unpinned loader amendment and an unauthenticated gate; the launch passes the '
         'authenticated batch names (no JSON read by the shell) and records the gate SHA; the outside sentinel is unchanged',
         all(fit_probes.values()) and bool(launched_ok) and sentinel.read_bytes() == b'SENTINEL', probes=fit_probes)
    drv, job = driver_module(tmp/'i')
    st = {'R5': 'stopped', 'R5-rep': 'pending', 'R5W': 'pending'}
    drv.fit_state = lambda f: (st[f], None); drv.live_supervisor = lambda: None; drv.resources_ok = lambda for_fit=False: True
    wjson(job/'data'/'O-VERIFIED.json', {})
    fits = drv.Fits(); calls = []; fits.launch = lambda fid, s: calls.append((fid, s))
    wjson(job/'driver'/'ANOMALY-fit-R5.json', dict(reason='wall_over_2x')); fits.tick(); before = list(calls)
    wjson(job/'data'/'OW-VERIFIED.json', {}); fits.tick(); after = list(calls)
    wjson(job/'driver'/'ANOMALY-fit-R5.json', dict(reason='nan_or_divergent')); calls.clear(); fits.tick()
    case('R2-11: a wall_over_2x fit resumes only after the O_W gate; divergence never auto-resumes', before == [] and after == [('R5', 'stopped')] and calls == [])
    drv, job = driver_module(tmp/'j')
    rt = job/'rt-R3a'/'repo'
    for rel in drv.RUNTIME_FILES:
        (rt/rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(REPO/rel if (REPO/rel).exists() else HERE/Path(rel).name, rt/rel)
    wjson(job/'RUNTIME-INVENTORY.json', {rel: sha(rt/rel) for rel in drv.RUNTIME_FILES})
    spawned = []
    drv.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
    drv.io.spawn = lambda argv, log, env, roles=('logs',), cwd=None: spawned.append(argv) or dict(pid=4242, pgid=4242, starttime=1, popen=None)
    drv.launch_phase('R3a', 'K4S-120', [0, 1])
    good = spawned and 'reports/explore/x4s4/supervise.py' in spawned[0] and spawned[0][0] == '/usr/bin/taskset' and readonly(job/'receipts'/'phase-R3a-K4S-120-a1-launch.json')
    (rt/'reports/explore/x4s4/x4s4io.py').write_text('# tampered\n'); spawned.clear()
    drv.launch_phase('R3a', 'S-200', [0, 1])
    case('F8: reporting runs the X4S-4 supervisor with an absolute argv and a read-only launch receipt; a runtime file (here x4s4io.py) '
         'differing from RUNTIME-INVENTORY is refused', good and not spawned and (job/'driver'/'ANOMALY-phase-R3a-S-200.json').exists())


# ================================================================ supervisor (F7, R2-F1, R2-F7, R2-F8)
def test_supervise(tmp):
    sup = load_fresh('supervise_t', HERE/'supervise.py')
    job = new_job(tmp)
    seq = dict(t=iter([0.0, 1.0, 2.0, 3.0, 4.0]), busy=iter([0, 1000, 1000, 1500, None]),
               own=iter([{}, {(77, 5): 50}, {(77, 5): 60, (78, 9): 40}, {}, {}]))
    sup.time = types.SimpleNamespace(monotonic=lambda: next(seq['t']))
    sup.host_busy_ticks = lambda: next(seq['busy']); sup.own_tree_ticks = lambda j: next(seq['own'])
    hz = os.sysconf('SC_CLK_TCK'); fc = sup.ForeignCensus(str(job))
    v = [fc.sample() for _ in range(4)]
    case("F7 probe: a NEW foreign process's first-interval CPU is counted; own births/exits handled; unreadable -> None",
         abs(v[0]-(1000-50)/hz) < 1e-9 and v[1] == 0.0 and abs(v[2]-500/hz) < 1e-9 and v[3] is None, values=v)
    src = (HERE/'supervise.py').read_text()
    case('supervisor: STOP via lexists; no bare group signal (verified-PID stop only); hard stop bound to HARD-STOP-UTC.txt; 24 h',
         "io.lexists(job+'/STOP')" in src and 'killpg' not in src and 'os.kill(' not in src and 'HARD-STOP-UTC.txt' in src and '12 h' not in src)
    def run_main(argv):
        sys.argv = ['supervise.py', *argv]; return lambda: sup.main()
    common = ['--rt', str(tmp), '--range', 'reporting', '--indices', str(Path(tmp)/'i.json'), '--stop-at', '2030-01-01T00:00:00Z']
    probes = dict(job_not_canonical=raises(run_main(['--job', str(tmp), '--phase', 'games/a', *common]), SystemExit, 'must be'),
                  phase_traversal=raises(run_main(['--job', str(job), '--phase', 'games/../../x', *common]), io.Refusal),
                  phase_absolute=raises(run_main(['--job', str(job), '--phase', '/etc/x', *common]), io.Refusal),
                  phase_role=raises(run_main(['--job', str(job), '--phase', 'fits/x', *common]), io.Refusal))
    case('R2-F1: the supervisor refuses a non-canonical --job and absolute/traversing/wrong-role --phase before any write', all(probes.values()) and not (job/'fits'/'x').exists())
    # R3-F2 probe (Sol): a direct collection launch with MemAvailable 0 / PSI 90 is refused BEFORE the child is spawned
    import studytree as ST
    saved = (ST.mem_available, ST.psi_some_avg10, ST.admission)
    ST.admission = lambda job, add=0, disk=True: (True, None)
    ST.mem_available = lambda: 0; low_mem = sup.admit_phase(str(job), 51)
    ST.mem_available = lambda: 100*2**30; ST.psi_some_avg10 = lambda: 90.0; high_psi = sup.admit_phase(str(job), 51)
    ST.psi_some_avg10 = lambda: 1.0; fine = sup.admit_phase(str(job), 51)
    ST.admission = lambda job, add=0, disk=True: (add <= 10, 'reservation'); reserve = sup.admit_phase(str(job), 51)
    ST.admission = lambda job, add=0, disk=True: (True, None)
    os.symlink(job/'nowhere', job/'STOP'); stop_pre = sup.admit_phase(str(job), 51); (job/'STOP').unlink()
    past = sup.admit_phase(str(job), 51, datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc))
    (job/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n'); past_file = sup.admit_phase(str(job), 51)
    (job/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    ST.mem_available, ST.psi_some_avg10, ST.admission = saved
    order = src.index('admit_phase(job, workers*width+3, stop_at)') < src.index('io.spawn(cmd')
    case('R3-F2/R4-F2 probes (Sol): before io.spawn the supervisor refuses MemAvailable 0, PSI 90, an over-reservation, a STOP link and '
         'an expired deadline (--stop-at or HARD-STOP-UTC.txt); it admits a healthy phase',
         'MemAvailable' in (low_mem or '') and 'PSI' in (high_psi or '') and fine is None and 'reservation' in (reserve or '') and order
         and 'STOP' in (stop_pre or '') and 'hard stop' in (past or '') and 'hard stop' in (past_file or ''))
    # R2-F8: the in-supervisor parity watch pauses out of band (SA-4: high side) and fails closed on a broken phase
    ph = job/'collect'/'S-200'/'a1'
    for i in range(2000, 2100): write_game(ph, 'S-200', i, C, hit=80, n=100); wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=C+i, order=['S-200'], games={f'sim-{i:04d}-d27-S-200.json': sha(ph/'games'/f'sim-{i:04d}-d27-S-200.json')}))
    why = sup.parity_watch(str(job), str(ph))
    paused = why == 'parity_pause' and os.path.lexists(job/'STOP') and list((job/'receipts').glob('PARITY-PAUSE-*.json'))
    (job/'STOP').unlink()
    (ph/'games'/'sim-2000-d27-S-200.json').write_text('{"tampered": 1}')
    failed = (sup.parity_watch(str(job), str(ph)) or '').startswith('parity_monitor_failed')
    case('R2-F8 probes: the in-supervisor C7b watch pauses (PARITY-PAUSE + STOP) out of band above X4S-3 (SA-4), and a failing watch is a stop reason',
         bool(paused) and failed, why=why)


# ================================================================ HR-2: slow-but-healthy readings never HALT; stuck ones still do
def hr2_bigjob(tmp, name, n_dirs=150, n_files=1000):
    """A job whose walk is slow but healthy (n_dirs * n_files entries; ~1 s on /dev/shm), like J with 564,490 entries."""
    j = Path(tmp)/name/'job'; (j/'watchdog').mkdir(parents=True); (j/'receipts').mkdir()
    (j/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    for d_ in range(n_dirs):
        bd = j/'data'/f'd{d_:04d}'; bd.mkdir(parents=True)
        for f_ in range(n_files): (bd/f'f{f_:04d}').touch()
    ctl = Path(tmp)/name/'ctl'; ctl.mkdir(); (ctl/'gpu').write_text('100')
    (ctl/'psi').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
    (ctl/'gpu.sh').write_text(f'#!/bin/sh\ncat {ctl}/gpu\n'); os.chmod(ctl/'gpu.sh', 0o755)
    return j, ctl


def hr2_run(code, j, ctl, opts=(), secs=6.0):
    """The real watchdog (from `code`) over `j` with a marked study process; returns (halt reason or None, heartbeats)."""
    env = {k: v for k, v in os.environ.items() if k not in ('X4S4_STUDY', 'X4S4_READOUT')}
    m = subprocess.Popen(['/bin/sleep', '60'], env={'X4S4_STUDY': str(j), 'PATH': '/usr/bin:/bin'}, start_new_session=True)
    w = subprocess.Popen([sys.executable, '-B', str(Path(code)/'watchdog.py'), 'run', '--job', str(j), '--cycle', '0.5', '--measure-budget', '0.3',
                          '--stall', '3', '--stop-grace', '1.5', '--kill-grace', '1', '--nvidia-smi', str(ctl/'gpu.sh'), '--gpu-timeout', '0.3',
                          '--mem-floor', '1', '--psi', str(ctl/'psi'), '--slow-cycle', '0.5', '--slow-budget', '5', '--slow-max-age', '8', *opts],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    beats = {}
    try:
        t0 = time.monotonic()
        while time.monotonic()-t0 < secs and not (j/'HALT.json').exists():
            try: hb = json.loads((j/'watchdog'/'heartbeat.json').read_text()); beats[hb['epoch']] = hb.get('readings') or {}
            except (OSError, ValueError, KeyError): pass
            time.sleep(0.05)
        t1 = time.monotonic()
        while time.monotonic()-t1 < 3 and (j/'HALT.json').exists() and m.poll() is None: time.sleep(0.05)
        reason = json.loads((j/'HALT.json').read_text()).get('reason') if (j/'HALT.json').exists() else None
        return reason, beats, m.poll() is not None
    finally:
        for p in (w, m):
            if p.poll() is None: p.kill()
            p.wait()


def hr2_scenarios(tmp, code=None):
    """Each HR-2 rule as one discriminating scenario -> {name: passed}. Used by test_hr2 and by the mutation check."""
    code = Path(code or HERE); W = load_fresh('watchdog_hr2', code/'watchdog.py')
    out = {}
    def run(name, fn):
        try: out[name] = bool(fn())
        except Exception as e: out[name] = False; print('hr2 scenario', name, 'raised', repr(e), flush=True)
    big = {}
    def bigjob():
        if 'j' not in big: big['j'], big['ctl'] = hr2_bigjob(tmp, 'hr2-big')
        return big['j'], big['ctl']
    def slow_positive():      # the incident: a walk slower than the FAST budget (0.3 s) is healthy -> no HALT, heartbeats continue
        j, ctl = bigjob(); reason, beats, _ = hr2_run(code, j, ctl)
        disk_s = [b['slow_timing']['disk'] for b in beats.values() if b.get('slow_timing')]
        print('hr2 slow walk seconds', disk_s[:5], 'beats', len(beats), 'reason', reason, flush=True)
        return reason is None and len(beats) >= 8 and disk_s and max(disk_s) > 0.3 and all(b.get('slow_age', 0) <= 8 for b in beats.values())
    def slow_bounded():       # a walk slower than the SLOW budget (0.2 s here) is bounded -> HALT, tree stopped
        j, ctl = hr2_bigjob(tmp, 'hr2-bound', n_dirs=150)
        reason, _, stopped = hr2_run(code, j, ctl, opts=('--slow-budget', '0.2', '--slow-max-age', '8'))
        return reason is not None and ('measurement failed' in reason or 'overdue' in reason) and stopped
    def slow_breach():        # slow-lane limits still HALT: disk over and PSS over
        j, ctl = hr2_bigjob(tmp, 'hr2-disk', n_dirs=2, n_files=10); r1, _, s1 = hr2_run(code, j, ctl, opts=('--max-disk', '1'))
        j2, ctl2 = hr2_bigjob(tmp, 'hr2-pss', n_dirs=2, n_files=10); r2, _, s2 = hr2_run(code, j2, ctl2, opts=('--tree-pss', '1'))
        return r1 and r1.startswith('disk') and s1 and r2 and 'study PSS' in r2 and s2
    def slow_failed():        # a failed slow reading (unreadable dir) still HALTs
        j, ctl = hr2_bigjob(tmp, 'hr2-fail', n_dirs=2, n_files=10); (j/'locked').mkdir(); os.chmod(j/'locked', 0)
        try: reason, _, stopped = hr2_run(code, j, ctl)
        finally: os.chmod(j/'locked', 0o755)
        return reason and 'measurement failed' in reason and stopped
    def unit_due():           # a STUCK slow pass (no return) HALTs after SLOW_BUDGET; a finished one does not; the fast rule is unchanged
        dog = W.Watchdog.__new__(W.Watchdog); dog.a = types.SimpleNamespace(cycle=1.0, measure_budget=0.8, stall=3.0, slow_budget=2.0, slow_max_age=3.0)
        dog.breach = None; now = time.monotonic(); dog.progress = now; dog.m_start = dog.last_start = now-0.1; dog.m_done = now-0.05
        dog.s_start, dog.s_done = now-2.5, None; stuck = 'slow measurement (PSS/disk) overdue' in (dog.due(now)[0] or '')
        dog.s_start, dog.s_done = now-2.5, now-0.5; done = dog.due(now)[0] is None
        dog.s_start, dog.s_done = now-1.0, None; running = dog.due(now)[0] is None
        dog.m_start, dog.m_done = now-0.9, None; fast = 'measurement overdue' in (dog.due(now)[0] or '')
        return stuck and done and running and fast
    def unit_verdict():       # stale / missing slow results HALT; a fresh one is copied into the readings
        dog = W.Watchdog.__new__(W.Watchdog); dog.a = types.SimpleNamespace(slow_max_age=3.0); mono = time.monotonic(); now = time.time()
        res = lambda age: dict(epoch=now-age, tree_pss=5, disk=7, disk_vanished=0, timing=dict(pss=0.1, disk=0.2))
        dog.started = mono-1.0; dog.slow = None; r = {}; startup = dog.slow_verdict(now, mono, r) is None
        dog.started = mono-4.0; missing = 'no slow measurement' in (dog.slow_verdict(now, mono, {}) or '')
        dog.slow = res(4.0); stale = 'older than' in (dog.slow_verdict(now, mono, {}) or '')
        dog.slow = res(1.0); r = {}; fresh = dog.slow_verdict(now, mono, r) is None and r.get('disk') == 7 and r.get('tree_pss') == 5
        return startup and missing and stale and fresh
    def args_check():         # SLOW_MAX_AGE must exceed SLOW_CYCLE + SLOW_BUDGET (a healthy pass can never look stale)
        r = subprocess.run([sys.executable, '-B', str(code/'watchdog.py'), 'status', '--job', str(Path(tmp)/'nojob'), '--slow-cycle', '30',
                            '--slow-budget', '120', '--slow-max-age', '150'], capture_output=True, text=True)
        return r.returncode != 0 and 'slow-max-age' in r.stderr
    for name, fn in (('unit_due', unit_due), ('unit_verdict', unit_verdict), ('args_check', args_check), ('slow_positive', slow_positive),
                     ('slow_bounded', slow_bounded), ('slow_breach', slow_breach), ('slow_failed', slow_failed)):
        run(name, fn)
    return out


def test_hr2(tmp):
    r = hr2_scenarios(tmp)
    case('HR-2 regression (the 14:32:50Z HALT): the real watchdog over a 150k-entry job whose walk exceeds the FAST budget '
         '(0.3 s) runs without HALT, heartbeats continue, and the slow result stays within its age bound', r['slow_positive'], scenarios=r)
    case('HR-2: a slow pass beyond its own budget HALTs (bounded; tree stopped); a stuck slow pass (no return) HALTs after '
         'SLOW_BUDGET in the main thread; a finished or still-in-budget pass does not; the fast overdue rule is unchanged',
         r['slow_bounded'] and r['unit_due'])
    case('HR-2: a stale slow result or none within SLOW_MAX_AGE of start HALTs; a fresh one feeds the readings; SLOW_MAX_AGE must '
         'exceed SLOW_CYCLE + SLOW_BUDGET', r['unit_verdict'] and r['args_check'])
    case('HR-2: slow-lane limits and failures still HALT and stop the tree (disk over, PSS over, an unreadable directory)',
         r['slow_breach'] and r['slow_failed'])


# ================================================================ HR-1 (COORDINATOR 77a01d88): the disk walk vs benign concurrent writers
def hr1_churn(root, stop, kind='rename'):
    """A benign concurrent writer like label.py's 48 workers: build game-N.tmp/ trees, rename them to game-N/, remove old ones."""
    root = Path(root); n = 0
    while not stop.is_set():
        t = root/f'game-{n:05d}.tmp'; t.mkdir(parents=True, exist_ok=True)
        for k in range(4): (t/f'f{k}').write_bytes(b'x'*100); (t/'train').mkdir(exist_ok=True); (t/'train'/f'r{k}').write_bytes(b'y'*50)
        os.rename(t, root/f'game-{n:05d}')
        old = root/f'game-{n-3:05d}'
        if old.exists(): shutil.rmtree(old, ignore_errors=True)
        n += 1


class FakeEntry:
    def __init__(self, path, err=None, real=None): self.path, self.err, self.real = path, err, real
    def stat(self, follow_symlinks=True):
        if self.err: raise OSError(self.err, os.strerror(self.err), self.path)
        return os.lstat(self.real)


class FakeScandir:
    """Deterministic vanishing: entries whose lstat fails with errno, and directories whose scandir fails with errno."""
    def __init__(self, dir_errs, entry_errs, iter_errs=()): self.dir_errs, self.entry_errs, self.iter_errs = dir_errs, entry_errs, set(iter_errs)
    def __call__(self, d):
        if d in self.dir_errs: raise OSError(self.dir_errs[d], os.strerror(self.dir_errs[d]), d)
        real = sorted(os.scandir(d), key=lambda e: e.name)
        out = [FakeEntry(e.path, self.entry_errs.get(e.path), e.path) for e in real]
        fs = self
        class It:
            def __init__(self): self.i = 0
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def __iter__(self): return self
            def __next__(self):
                if d in fs.iter_errs: raise OSError(errno.ENOENT, 'gone', d)
                if self.i >= len(out): raise StopIteration
                self.i += 1; return out[self.i-1]
        return It()


def hr1_scenarios(tmp, code=None):
    """Each HR-1 rule as one discriminating scenario -> {name: passed}. Used by test_hr1 and by the mutation check."""
    import errno as E
    code = Path(code or HERE); ST = load_fresh('studytree_hr1', code/'studytree.py')
    out = {}
    def run(name, fn):
        try: out[name] = bool(fn())
        except Exception as e: out[name] = False; print('hr1 scenario', name, 'raised', repr(e), flush=True)
    def tree(name):
        r = Path(tmp)/name; (r/'a'/'b').mkdir(parents=True); (r/'a'/'f1').write_bytes(b'1'*1000); (r/'a'/'b'/'f2').write_bytes(b'2'*333)
        os.link(r/'a'/'f1', r/'a'/'hard'); os.symlink('a/f1', r/'link'); return r
    def du_parity():          # quiescent tree: equals `du -sb` (root, dirs, symlink, a hard link once)
        r = tree('parity'); du = int(subprocess.run(['/usr/bin/du', '-sb', '--', str(r)], capture_output=True, text=True, check=True).stdout.split()[0])
        b, v = ST.tree_bytes(str(r), 5); return b == du and v == 0
    def det_vanish():         # deterministic: an entry ENOENT, a subdir ENOENT at scandir, a parent ENOTDIR, a dir gone mid-iteration
        r = tree('det'); (r/'c').mkdir(); (r/'c'/'x').write_bytes(b'z'*10); (r/'d').mkdir(); (r/'d'/'y').write_bytes(b'w')
        fake = FakeScandir({str(r/'a'/'b'): E.ENOENT, str(r/'c'): E.ENOTDIR}, {str(r/'a'/'f1'): E.ENOENT}, iter_errs=[str(r/'d')])
        b, v = ST.tree_bytes(str(r), 5, scandir=fake); return v == 4 and b > 0
    def det_errors():         # every other error raises: EACCES/EIO at a subdir or entry, any error at the root, a missing root, a file root, timeout
        r = tree('err'); res = []
        for dirs, ents in (({str(r/'a'): E.EACCES}, {}), ({str(r/'a'): E.EIO}, {}), ({}, {str(r/'a'/'f1'): E.EACCES}), ({}, {str(r/'a'/'f1'): E.EIO}),
                           ({str(r): E.ENOENT}, {}), ({str(r): E.ENOTDIR}, {})):
            res.append(raises(lambda: ST.tree_bytes(str(r), 5, scandir=FakeScandir(dirs, ents)), OSError))
        res.append(raises(lambda: ST.tree_bytes(str(r/'missing'), 5), FileNotFoundError))
        res.append(raises(lambda: ST.tree_bytes(str(r/'a'/'f1'), 5), NotADirectoryError))
        res.append(raises(lambda: ST.tree_bytes(str(r), 0), TimeoutError))
        locked = r/'locked'; locked.mkdir(); os.chmod(locked, 0)
        try: res.append(raises(lambda: ST.tree_bytes(str(r), 5), PermissionError))
        finally: os.chmod(locked, 0o755)
        return all(res)
    def churn_walk():         # real concurrent writer: 150 walks never raise; vanishing was actually exercised
        r = Path(tmp)/'churn'; r.mkdir(); stop = threading.Event(); ths = [threading.Thread(target=hr1_churn, args=(r/f'w{i}', stop)) for i in range(4)]
        for t in ths: t.start()
        gone, ok = 0, True
        try:
            for _ in range(150):
                b, v = ST.tree_bytes(str(r), 5); gone += v; ok = ok and b > 0
        finally:
            stop.set(); [t.join() for t in ths]
        print('hr1 churn vanished', gone, flush=True)
        return ok and gone > 0
    def churn_disk_bytes():   # the in-process reading (admission / monitors): never None under the same writer
        r = Path(tmp)/'churn2'; r.mkdir(); stop = threading.Event(); ths = [threading.Thread(target=hr1_churn, args=(r/f'w{i}', stop)) for i in range(4)]
        for t in ths: t.start()
        vals = []
        try:
            for _ in range(60): ST._disk['bytes'] = None; vals.append(ST.disk_bytes(str(r)))
        finally:
            stop.set(); [t.join() for t in ths]
        locked = r/'locked'; locked.mkdir(); os.chmod(locked, 0); ST._disk['bytes'] = None
        try: unreadable = ST.disk_bytes(str(r))
        finally: os.chmod(locked, 0o755)
        return all(isinstance(v, int) and v > 0 for v in vals) and unreadable is None
    def static():             # no du anywhere in the measurement code; the watchdog uses the shared walk
        w, st_ = (code/'watchdog.py').read_text(), (code/'studytree.py').read_text()
        return '/usr/bin/du' not in w and '/usr/bin/du' not in st_ and "'du'" not in w and 'tree_bytes(self.job' in w and 'tree_bytes(job' in st_
    for name, fn in (('du_parity', du_parity), ('det_vanish', det_vanish), ('det_errors', det_errors), ('churn_walk', churn_walk),
                     ('churn_disk_bytes', churn_disk_bytes), ('static', static)):
        run(name, fn)
    return out


def hr1_live(tmp, code=None):
    """The HALT's regression test, on the real watchdog process (from `code`): a marked study process plus (a) label-like
    rename/remove churn inside the job and (b) a churn of short-lived marked processes (exits, zombies) for 6 s -> no HALT,
    heartbeats keep coming and some walk counted vanished entries."""
    code = Path(code or HERE); j = Path(tmp)/'hr1-live'/'job'; (j/'watchdog').mkdir(parents=True); (j/'receipts').mkdir(); (j/'data').mkdir()
    (j/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    for d_ in range(100):                                   # a realistic bulk (the real job had 62,655 entries): each walk takes
        bd = j/'data'/'bulk'/f'd{d_:03d}'; bd.mkdir(parents=True)          # long enough to overlap the writers' renames
        for f_ in range(100): (bd/f'f{f_:03d}').write_bytes(b'b')
    ctl = Path(tmp)/'hr1-live'/'ctl'; ctl.mkdir(); (ctl/'gpu').write_text('100')
    (ctl/'psi').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
    (ctl/'gpu.sh').write_text(f'#!/bin/sh\ncat {ctl}/gpu\n'); os.chmod(ctl/'gpu.sh', 0o755)
    env = {k: v for k, v in os.environ.items() if k not in ('X4S4_STUDY', 'X4S4_READOUT')}
    menv = {'X4S4_STUDY': str(j), 'PATH': '/usr/bin:/bin'}
    m = subprocess.Popen(['/bin/sleep', '60'], env=menv, start_new_session=True)
    w = subprocess.Popen([sys.executable, '-B', str(code/'watchdog.py'), 'run', '--job', str(j), '--cycle', '0.5', '--measure-budget', '0.45',
                          '--stall', '3', '--stop-grace', '1.5', '--kill-grace', '1', '--nvidia-smi', str(ctl/'gpu.sh'), '--slow-cycle', '0.5', '--slow-budget', '2', '--slow-max-age', '3',
                          '--gpu-timeout', '0.5', '--mem-floor', '1', '--psi', str(ctl/'psi')],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    stop = threading.Event(); ths = [threading.Thread(target=hr1_churn, args=(j/'data'/'raw-O'/f'w{i}', stop)) for i in range(8)]
    def proc_churn():
        while not stop.is_set():
            p = subprocess.Popen(['/bin/sh', '-c', 'exit 0'], env=menv); time.sleep(0.02); p.wait()
    ths.append(threading.Thread(target=proc_churn))
    per_beat = {}
    try:
        t0 = time.monotonic()
        while not (j/'watchdog'/'heartbeat.json').exists() and time.monotonic()-t0 < 10: time.sleep(0.05)
        for t in ths: t.start()
        t0 = time.monotonic()
        while time.monotonic()-t0 < 6.0 and not (j/'HALT.json').exists():
            try:
                hb = json.loads((j/'watchdog'/'heartbeat.json').read_text())
                per_beat[hb['epoch']] = (hb.get('readings') or {}).get('disk_vanished') or 0
            except (OSError, ValueError, KeyError): pass
            time.sleep(0.02)
        halted = (j/'HALT.json').exists(); reason = json.loads((j/'HALT.json').read_text()).get('reason') if halted else None
    finally:
        stop.set(); [t.join() for t in ths if t.is_alive() or True]
        for p in (w, m):
            if p.poll() is None: p.kill()
            p.wait()
    return dict(no_halt=not halted, reason=reason, beats=len(per_beat), vanished_seen=sum(per_beat.values()), marked_alive_until_end=True)


def test_hr1(tmp):
    r = hr1_scenarios(tmp)
    case('HR-1: tree_bytes equals `du -sb` on a quiescent tree (root, dirs, symlink, hard link once)', r['du_parity'], scenarios=r)
    case('HR-1: entries vanishing mid-walk (ENOENT at lstat, ENOENT/ENOTDIR at a subdir scandir, gone mid-iteration) are skipped '
         'and counted', r['det_vanish'])
    case('HR-1: every other error raises - EACCES/EIO at a subdir or an entry, any error at the root, a missing or non-directory '
         'root, a real unreadable directory, and the timeout', r['det_errors'])
    case('HR-1: under a real label-like writer (4 threads renaming .tmp trees and removing old ones), 150 walks never fail and '
         'vanished entries were exercised; studytree.disk_bytes never returns None under it, and is None for an unreadable dir',
         r['churn_walk'] and r['churn_disk_bytes'])
    case('HR-1: no du in watchdog.py or studytree.py; both use the shared tree_bytes walk', r['static'])
    live = hr1_live(tmp)
    case('HR-1 regression (the 11:57:58Z HALT): the real watchdog over a 10k-entry job under rename/remove churn (8 writers) AND a '
         'churn of short-lived marked processes (exits, zombies) for 6 s does not HALT and heartbeats continue (the vanished count '
         'it saw is reported; vanishing itself is asserted deterministically and under churn above)',
         live['no_halt'] and live['beats'] >= 6, live=live)


# ================================================================ SA-5 (COORDINATOR 5483e9d6): qualify4 parity --final (P3)
def sa5_job(tmp, name):
    """A finished bank-C collection (both arms, 1 game each, cutoff 0 %: out of band on the LOW side at --min-games 1)."""
    j = new_job(Path(tmp)/name)
    pk, ps = j/'collect'/'K4S-120'/'a1', j/'collect'/'S-200'/'a1'
    write_collect_game(pk, 'K4S-120', 0, range(100, 130, 10)); write_collect_game(ps, 'S-200', 2000, range(100, 130, 10))
    import qualify4; qualify4.parity_inventory([str(pk), str(ps)])          # the fixture is block-proved and terminal
    for ph in (pk, ps): finish_phase(ph)
    return j, [pk, ps]


def sa5_scenarios(tmp, code=None):
    """Each SA-5 rule as one discriminating scenario -> {name: passed}. Used by test_sa5 and by the mutation check."""
    stub_torch_imports()
    import label
    out = {}
    def run(name, fn):
        try: out[name] = bool(fn())
        except Exception as e: out[name] = False; print('sa5 scenario', name, 'raised', repr(e), flush=True)
    def stopped(j): return os.path.lexists(Path(j)/'STOP') or bool(list((Path(j)/'receipts').glob('PARITY-PAUSE-*.json')))
    def final_low():      # --final, low side: guard PASSED, receipt passed=false/final/final_mode, no STOP, no PARITY-PAUSE
        j, phs = sa5_job(tmp, 'final_low'); q, body, exits = guarded_parity(j, phs, 'fl', code=code); d = json.loads(q.read_text())
        return (body['passed'] is True and d['passed'] is False and d['final'] is True and d.get('final_mode') is True
                and d['out_of_band'] == ['K4S-120', 'S-200'] and not stopped(j))
    def default_unchanged():   # without --final: exit 1 (guard failed), PARITY-PAUSE + STOP, exactly as before
        j, phs = sa5_job(tmp, 'default'); q, body, exits = guarded_parity(j, phs, 'df', final=False, code=code)
        d = json.loads(q.read_text())
        return body['passed'] is False and d['passed'] is False and 'final_mode' not in d and os.path.lexists(j/'STOP') and stopped(j)
    def not_final():      # --final over a phase without supervisor-exit: not a completed final check -> exit 1
        j, phs = sa5_job(tmp, 'not_final'); (phs[1]/'supervisor-exit.json').unlink()
        q, body, exits = guarded_parity(j, phs, 'nf', code=code)
        return body['passed'] is False and not stopped(j)
    def watch_refused():  # --final --watch: refused (error) -> exit 1
        j, phs = sa5_job(tmp, 'watch'); q, body, exits = guarded_parity(j, phs, 'wt', extra=('--watch', '5'), code=code)
        return body['passed'] is False and 'final' in json.loads(q.read_text()).get('error', '')
    def halted():         # --final whose final fresh verdict halts (finalize sets `halted`, passed stays false): exit 1
        j, phs = sa5_job(tmp, 'halted'); use_job(j); fake_watchdog(j)
        Q = load_fresh('qualify4_sa5', Path(code or HERE)/'qualify4.py')
        import studytree as ST
        saved = ST.fresh_verdict; ST.fresh_verdict = lambda *a, **k: 'memory_guard'
        q = j/'receipts'/'parity-ht.json'; rc = None
        try: Q.main(['parity', '--phases', *map(str, phs), '--bank', 'collection', '--min-games', '1', '--final', '--out', str(q)])
        except SystemExit as e: rc = e.code
        finally: ST.fresh_verdict = saved
        d = json.loads(q.read_text())
        return rc == 1 and d.get('halted') == 'memory_guard' and d['final'] is True and not stopped(j)
    def error_exit():     # --final whose check raises (a tampered game): an error receipt -> exit 1
        j, phs = sa5_job(tmp, 'error'); (phs[0]/'games'/'sim-0000-d27-K4S-120.json').write_text('{"tampered": 1}')
        q, body, exits = guarded_parity(j, phs, 'er', code=code)
        return body['passed'] is False and json.loads(q.read_text()).get('error')
    def plan_e2e():       # end to end: guarded --final receipt + authentic exception -> label.make_plan accepts; wrong SHA refused
        j, phs = sa5_job(tmp, 'e2e'); q, body, exits = guarded_parity(j, phs, 'e2e', code=code)
        if not (body['passed'] is True and json.loads(q.read_text())['passed'] is False): return False
        repo, head = git_repo(Path(tmp)/'sa5coord', {'reports/strategy_council_20260928/COORDINATOR.md': f'PE: disclose {sha(q)}\n'.encode()})
        saved_repo = io.REPO; io.REPO = repo; use_job(j)
        try:
            wjson(j/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256='0'*64, coordinator_commit=head, decision='disclose'))
            wrong = raises(lambda: label.make_plan([str(p) for p in phs], str(q), str(j/'data'/'p-wrong.json')), label.PlanError, 'authentic')
            (j/'data'/'PARITY-EXCEPTION.json').unlink()
            none = raises(lambda: label.make_plan([str(p) for p in phs], str(q), str(j/'data'/'p-none.json')), label.PlanError, 'authentic')
            wjson(j/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256=sha(q), coordinator_commit=head, decision='disclose'))
            label.make_plan([str(p) for p in phs], str(q), str(j/'data'/'label-plan.json'))
            ok = json.loads((j/'data'/'label-plan.json').read_text())['parity_exception']['parity_receipt_sha256'] == sha(q)
        finally:
            io.REPO = saved_repo
        return wrong and none and ok
    def plan_default_blocked():   # the pre-SA-5 blocker, demonstrated: a default (non --final) failed receipt is refused even WITH
        j, phs = sa5_job(tmp, 'blocked'); q, body, exits = guarded_parity(j, phs, 'bk', final=False, code=code)   # an exception
        repo, head = git_repo(Path(tmp)/'sa5coord2', {'reports/strategy_council_20260928/COORDINATOR.md': f'PE: disclose {sha(q)}\n'.encode()})
        saved_repo = io.REPO; io.REPO = repo; use_job(j)
        try:
            wjson(j/'data'/'PARITY-EXCEPTION.json', dict(parity_receipt_sha256=sha(q), coordinator_commit=head, decision='disclose'))
            return raises(lambda: label.make_plan([str(p) for p in phs], str(q), str(j/'data'/'p.json')), label.PlanError, 'guard receipt')
        finally:
            io.REPO = saved_repo
    def rule_unit():      # the exit rule itself: only final + arms + no error + no halt completes
        Q = load_fresh('qualify4_sa5r', Path(code or HERE)/'qualify4.py'); base = dict(final=True, arms={}, passed=False)
        f = Q.final_check_completed
        return (f(base) and f(dict(base, passed=True)) and not f(dict(base, final=False)) and not f({k: v for k, v in base.items() if k != 'arms'})
                and not f(dict(base, error='x')) and not f(dict(base, halted='owned_STOP')))
    for name, fn in (('rule_unit', rule_unit), ('final_low', final_low), ('default_unchanged', default_unchanged), ('not_final', not_final),
                     ('watch_refused', watch_refused), ('halted', halted), ('error_exit', error_exit), ('plan_e2e', plan_e2e), ('plan_default_blocked', plan_default_blocked)):
        run(name, fn)
    return out


def test_sa5(tmp):
    canonical_job = io.JOB
    try: r = sa5_scenarios(tmp)
    finally: use_job(canonical_job)
    case('SA-5: P3 `qualify4 parity --final` under the real guard.py: low side -> guard PASSED, receipt passed=false (final, '
         'final_mode), no STOP and no PARITY-PAUSE', r['final_low'], scenarios=r)
    case('SA-5: without --final the behaviour is unchanged (exit 1, guard failed, PARITY-PAUSE + STOP)', r['default_unchanged'])
    case('SA-5: --final exits 1 (no passed guard) for a non-final phase set, with --watch, on a check error, and when the final fresh '
         'verdict halts; the exit rule completes only for final + per-arm reading + no error + no halt',
         r['not_final'] and r['watch_refused'] and r['error_exit'] and r['halted'] and r['rule_unit'])
    probe = Path(tmp)/'failed-probe.json'; probe.write_text(json.dumps(dict(passed=False)))
    case('SA-5: the bless fixtures refuse a failed receipt (no test can pass a failed receipt by blessing it)',
         raises(lambda: bless_into(Path(tmp)/'bj', probe), AssertionError, 'failed receipt') and raises(lambda: bless(probe), AssertionError, 'failed receipt'))
    case('SA-5 end to end: real guard.py -> qualify4 parity --final -> label.make_plan accepts the failed receipt only with an '
         'authentic exact-receipt exception (none or a wrong SHA is refused); a default-mode failed receipt stays refused (guard)',
         r['plan_e2e'] and r['plan_default_blocked'])


# ================================================================ SA-4 (COORDINATOR 08723c23): one-sided in-loop C7b watch
def sa4_phase(job, arm, hit, sd=0, ov=0, n=1000, count=100, k=1):
    """A collection phase of `count` block-proved games, each with n decisions: hit cutoffs, sd student-defaults, ov overruns."""
    ph = Path(job)/'collect'/arm/f'a{k}'; first = 2000 if arm == 'S-200' else 0
    for i in range(first, first+count):
        g = ph/'games'/f'sim-{i:04d}-d27-{arm}.json'; g.parent.mkdir(parents=True, exist_ok=True)
        ds = [dict(hit=j < hit, student_default=j < sd, wall_overrun=j < ov) for j in range(n)]
        g.write_text(json.dumps(dict(metadata=dict(terminal=True, seed=C+i, arm=arm, seat=i % 2, winner=0, budget_ms=120), loss=1.0,
                                     search_ab=dict(command_sha256='h', deadline_stats=ds))))
        wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=C+i, order=[arm], games={g.name: sha(g)}))
    return ph


def sa4_scenarios(sup, tmp):
    """Each SA-4 rule as one discriminating scenario -> {name: passed}. Used by test_sa4 and by the mutation check."""
    out = {}
    def fresh(name):
        return new_job(Path(tmp)/name)
    def pauses(job): return sorted((Path(job)/'receipts').glob('PARITY-PAUSE-*.json'))
    def lowside(job):
        p = Path(job)/'receipts'/'parity-lowside.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    def run(name, fn):
        try: out[name] = bool(fn())
        except Exception as e: out[name] = False; print('sa4 scenario', name, 'raised', repr(e), flush=True)
    def low():          # S-200 cutoff 70.0 < 75.3 - 2: low side only -> no pause, appended record (twice = two lines)
        job = fresh('low'); ph = sa4_phase(job, 'S-200', hit=700)
        w1, w2 = sup.parity_watch(str(job), str(ph)), sup.parity_watch(str(job), str(ph)); recs = lowside(job)
        return (w1 is None and w2 is None and not os.path.lexists(job/'STOP') and not pauses(job) and len(recs) == 2
                and all(r['out_of_band'] == ['S-200'] and 'inventory' not in r and len(r['inventory_sha256']) == 64
                        and r['phase'] == str(ph) and abs(r['arms']['S-200']['pct']['cutoff']-70.0) < 1e-9 for r in recs))
    def high():         # S-200 cutoff 80.0 > 75.3 + 2 -> PARITY-PAUSE + STOP, no low-side record
        job = fresh('high'); ph = sa4_phase(job, 'S-200', hit=800)
        why = sup.parity_watch(str(job), str(ph)); p = pauses(job)
        return (why == 'parity_pause' and os.path.lexists(job/'STOP') and len(p) == 1
                and json.loads(p[0].read_text()).get('high_side') == ['S-200'] and not lowside(job))
    def just_high():    # cutoff 77.4 (> 77.3) pauses; cutoff 77.2 is in band: neither pause nor record
        job = fresh('just_high'); ph = sa4_phase(job, 'S-200', hit=774)
        a = sup.parity_watch(str(job), str(ph)) == 'parity_pause'
        job2 = fresh('in_band_top'); ph2 = sa4_phase(job2, 'S-200', hit=772)
        b = sup.parity_watch(str(job2), str(ph2)) is None and not pauses(job2) and not lowside(job2) and not os.path.lexists(job2/'STOP')
        return a and b
    def in_band_low():  # cutoff 73.4 (>= 73.3) is in band: no record
        job = fresh('in_band_low'); ph = sa4_phase(job, 'S-200', hit=734)
        return sup.parity_watch(str(job), str(ph)) is None and not lowside(job) and not pauses(job)
    def low_small_above():  # low cutoff (70.0) with overrun 0.3 % (above 0.14 but within +2 pp) -> still low side: record, no pause
        job = fresh('low_small_above'); ph = sa4_phase(job, 'S-200', hit=700, ov=3)
        recs = lowside(job) if sup.parity_watch(str(job), str(ph)) is None else None
        return recs is not None and len(recs) == 1 and not pauses(job) and not os.path.lexists(job/'STOP')
    def mixed_sd():     # S-200 cutoff low (70.0) but student-default 5.0 % > 0.0 + 2 -> pause
        job = fresh('mixed_sd'); ph = sa4_phase(job, 'S-200', hit=700, sd=50)
        return sup.parity_watch(str(job), str(ph)) == 'parity_pause' and os.path.lexists(job/'STOP') and not lowside(job)
    def mixed_overrun():  # K4S-120 cutoff low (50.0), student-default in band (22.3), overrun 3.0 % > 0.16 + 2 -> pause
        job = fresh('mixed_ov'); ph = sa4_phase(job, 'K4S-120', hit=500, sd=223, ov=30)
        return sup.parity_watch(str(job), str(ph)) == 'parity_pause' and not lowside(job)
    def not_evaluated():  # 99 games far above: below PARITY_MIN_GAMES -> neither pause nor record
        job = fresh('not_eval'); ph = sa4_phase(job, 'S-200', hit=950, count=99)
        return sup.parity_watch(str(job), str(ph)) is None and not pauses(job) and not lowside(job) and not os.path.lexists(job/'STOP')
    def monitor_failure():  # a tampered game: the watch fails closed (stop reason), creating neither STOP nor a record
        job = fresh('mon_fail'); ph = sa4_phase(job, 'S-200', hit=700)
        (ph/'games'/'sim-2000-d27-S-200.json').write_text('{"tampered": 1}')
        why = sup.parity_watch(str(job), str(ph)) or ''
        return why.startswith('parity_monitor_failed') and not lowside(job) and not os.path.lexists(job/'STOP')
    def record_failure():   # the low-side record cannot be written (symlink): stop reason; the outside target untouched
        job = fresh('rec_fail'); ph = sa4_phase(job, 'S-200', hit=700)
        outside = Path(tmp)/'outside-sa4.txt'; outside.write_text('sentinel\n')
        os.symlink(outside, job/'receipts'/'parity-lowside.jsonl')
        why = sup.parity_watch(str(job), str(ph)) or ''
        return why.startswith('parity_monitor_failed') and outside.read_text() == 'sentinel\n' and not pauses(job)
    def helper_two_arms():  # high_side() itself: an unevaluated high arm never pauses; an evaluated one does (any metric)
        ref = dict(cutoff=75.3, student_default=0.0, overrun=0.14)
        def arm(cut, ev, sd=0.0): return dict(evaluated=ev, pct=dict(cutoff=cut, student_default=sd, overrun=0.1), x4s3_r3a=ref)
        return (sup.high_side(dict(arms={'A': arm(70.0, True), 'B': arm(90.0, False)})) == []
                and sup.high_side(dict(arms={'A': arm(70.0, True), 'B': arm(90.0, True)})) == ['B']
                and sup.high_side(dict(arms={'A': arm(70.0, True, sd=2.5)})) == ['A'])
    for name, fn in (('low', low), ('high', high), ('helper_two_arms', helper_two_arms), ('just_high', just_high), ('in_band_low', in_band_low), ('low_small_above', low_small_above), ('mixed_sd', mixed_sd),
                     ('mixed_overrun', mixed_overrun), ('not_evaluated', not_evaluated), ('monitor_failure', monitor_failure),
                     ('record_failure', record_failure)):
        run(name, fn)
    return out


def test_sa4(tmp):
    sup = load_fresh('supervise_sa4', HERE/'supervise.py')
    r = sa4_scenarios(sup, tmp)
    case('SA-4: low side only (cutoff 70.0 vs 75.3) -> no pause, no STOP; each watch appends one record (no inventory) to '
         'receipts/parity-lowside.jsonl', r['low'], scenarios=r)
    case('SA-4: high side (cutoff 80.0) -> PARITY-PAUSE (high_side recorded) + STOP, no low-side record', r['high'])
    case('SA-4: threshold is strict +2 pp: 77.4 pauses; 77.2 and 73.4 are in band (no pause, no record); a low cutoff with a metric '
         'above its reference by less than 2 pp is low side (record, no pause)', r['just_high'] and r['in_band_low'] and r['low_small_above'])
    case('SA-4: mixed low cutoff with a high student-default (S-200) or a high overrun (K4S-120) -> pause, no record',
         r['mixed_sd'] and r['mixed_overrun'])
    case('SA-4: an arm below PARITY_MIN_GAMES is not evaluated (no pause, no record); high_side() ignores unevaluated arms',
         r['not_evaluated'] and r['helper_two_arms'])
    case('SA-4: a monitor exception, or a failed low-side record (symlink; outside sentinel unchanged), is parity_monitor_failed',
         r['monitor_failure'] and r['record_failure'])


# ================================================================ contention (F7, R2-F4, R2-F7)
T0 = datetime.datetime(2026, 10, 13, 10, 0, tzinfo=datetime.timezone.utc).timestamp()
def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def write_phase_timing(ph, workers=10, lane=5, rows=None, launch=T0-10, exit_=None, settled=True, raw_lines=None):
    wjson(ph/'launch.json', dict(utc=iso(launch), workers=workers, lane_width=lane))
    rows = rows if rows is not None else [dict(utc=iso(T0-5+10*k), psi_some_avg10=0.5, foreign_cores_host=0.3, reduced_concurrency=False) for k in range(62)]
    text = ''.join(json.dumps(r)+'\n' for r in rows) if raw_lines is None else raw_lines
    (ph/'census.jsonl').write_text(text)
    last = max([datetime.datetime.strptime(r['utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp() for r in rows] or [launch])
    wjson(ph/'supervisor-exit.json', dict(utc=iso(exit_ if exit_ is not None else last+5), reason=None, returncode=0))
    if settled: wjson(ph/'SETTLED.json', {})


def timing_game(ph, arm, i, wall=4.0, end=None):
    (ph/'games').mkdir(parents=True, exist_ok=True); (ph/'blocks').mkdir(exist_ok=True)
    g = ph/'games'/f'sim-{i:04d}-d27-{arm}.json'; g.write_text(json.dumps(dict(loss=1.0, wall_seconds=wall)))
    end = T0+10*i if end is None else end; os.utime(g, (end, end))
    wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, games={g.name: sha(g)}))


def census_rows(**edits):
    rows = [dict(utc=iso(T0-5+10*k), psi_some_avg10=0.5, foreign_cores_host=0.3, reduced_concurrency=False) for k in range(62)]
    for k, kv in edits.items(): rows[int(k[1:])].update(kv)
    return rows


def test_contention(tmp):
    import contention
    def build(name, setup):
        job = new_job(tmp, name)
        for sid in ('R3a', 'R5'):
            ph = job/'games'/sid/'K4S-120'/'a1'
            for i in range(8): timing_game(ph, 'K4S-120', i)
            write_phase_timing(ph)
        setup(job); return contention.build(str(job))
    def edit(sid, **kw):
        return lambda j: write_phase_timing(j/'games'/sid/'K4S-120'/'a1', rows=census_rows(**kw))
    mech = dict(clean=(lambda j: None, []), psi=(edit('R3a', k2=dict(psi_some_avg10=15.0)), [1]),
                psi_unreadable=(edit('R3a', k3=dict(psi_some_avg10=None)), [2]), foreign=(edit('R5', k4=dict(foreign_cores_host=3.0)), [3]),
                foreign_unreadable=(edit('R5', k5=dict(foreign_cores_host=None)), [4]), yield_window=(edit('R3a', k6=dict(reduced_concurrency=True)), [5]),
                mid_gap=(lambda j: write_phase_timing(j/'games'/'R3a'/'K4S-120'/'a1', rows=[r for k, r in enumerate(census_rows()) if k not in (7, 8, 9)]), [6, 7]))
    got = {k: build('m-'+k, f)['excluded_indices'] for k, (f, _) in mech.items()}
    case('F7 probes: PSI, unreadable PSI, foreign, unreadable foreign, yield and a census gap each flag exactly their own games',
         all(got[k] == w for k, (_, w) in mech.items()), got=got)
    def raw(**kw):     # census text with literal non-JSON numbers
        def f(j):
            rows = census_rows(); lines = [json.dumps(r) for r in rows]
            for k, val in kw.items(): lines[int(k[1:])] = lines[int(k[1:])].replace('"psi_some_avg10": 0.5', '"psi_some_avg10": '+val)
            write_phase_timing(j/'games'/'R5'/'K4S-120'/'a1', rows=rows, raw_lines='\n'.join(lines)+'\n')
        return f
    invalid = dict(nan=(raw(k2='NaN'), [1]), infinity=(raw(k3='Infinity'), [2]), negative=(edit('R5', k4=dict(psi_some_avg10=-1.0)), [3]),
                   foreign_nan_value=(edit('R5', k5=dict(foreign_cores_host=1e400)), [4]),
                   chronology=(edit('R5', k6=dict(utc=iso(T0-500))), [4]), reduced_not_bool=(edit('R5', k7=dict(reduced_concurrency='no')), [6]))
    got2 = {k: build('i-'+k, f)['excluded_indices'] for k, (f, _) in invalid.items()}
    case("R2-F7 probes (Sol): NaN, Infinity, negative and overflowing readings, out-of-chronology times and a non-boolean yield flag are BAD "
         "(each isolated in an uncapped phase) - never clean", all(set(w) <= set(got2[k]) and got2[k] for k, (_, w) in invalid.items()), got=got2)
    capped = build('capped', lambda j: wjson(j/'games'/'R5'/'K4S-120'/'a1'/'launch.json', dict(utc=iso(T0-10), workers=3, lane_width=5)))
    empty = build('empty', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'census.jsonl').write_text(''))
    tail = build('tail', lambda j: write_phase_timing(j/'games'/'R3a'/'K4S-120'/'a1', rows=census_rows()[:4], exit_=T0+60))
    case('F7: a capped phase flags all its games; an EMPTY census flags the whole phase; an uncovered tail is bad',
         capped['excluded_indices'] == list(range(8)) and empty['excluded_indices'] == list(range(8)) and tail['excluded_indices'] == [3, 4, 5, 6])
    case('contention refuses unsettled or exit-less phases',
         raises(lambda: build('unf', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'SETTLED.json').unlink()), contention.ContentionError, 'missing')
         and raises(lambda: build('nx', lambda j: (j/'games'/'R5'/'K4S-120'/'a1'/'supervisor-exit.json').unlink()), contention.ContentionError, 'missing'))
    w = contention.wall_only(f'{tmp}/m-clean/games/R3a/K4S-120/a1/games/sim-0000-d27-K4S-120.json')
    job = use_job(Path(tmp)/'m-clean')
    out, digest = contention.write_once(str(job), contention.build(str(job)))
    body = json.loads(Path(out).read_text())
    case('contention: wall_seconds projection only; schema v3 with per-game SHA/size/st_mtime_ns and the retired SHA; written once, read-only',
         w == 4.0 and body['schema'] == 'x4s4.contention.v3' and len(body['coverage']['games/R3a/K4S-120/a1']['games'][0]) == 5
         and readonly(out) and digest == sha(out) and raises(lambda: contention.write_once(str(job), {}), io.Refusal))


# ================================================================ reducer + report (R2-F4, R2-F9, F11, F14)
def reduce_fixture(tmp, students=('R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W'), forward=5):
    job = new_job(tmp, 'rjob')
    plan = json.loads((HERE/'plan.json').read_text()); plan['seed_ranges']['reporting'] = dict(base=E, count=60)
    shas = {s: hashlib.sha256(s.encode()).hexdigest() for s in students}
    plan['student']['checkpoint_sha256'] = shas['R3a']
    wjson(job/'x'/'plan.json', plan)
    wjson(job/'driver'/'retired.json', dict(indices=[3], why=[]))
    for s in students:
        if s != 'R3a': wjson(job/f'rt-{s}'/'READY.json', dict(student=dict(checkpoint_sha256=shas[s])))
    rng = random.Random(5)
    p_loss = {'R3a': .30, 'R3a-rep': .30, 'R5': .15, 'R5-rep': .15, 'R5W': .25}
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
                wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=E+i, order=[arm], slot_cores=list(range(width)), worker_pid=1, games={gp.name: sha(gp)}))
            write_phase_timing(ph, workers=10 if width == 5 else 50, lane=width,
                               rows=census_rows(**({'k1': dict(psi_some_avg10=15.0)} if (s, arm) == ('R3a', 'K4S-120') else {})))
    return job


FREEZE = 'reports/explore/x4s4/receipts/contention-exclusion.json'


def test_reduce(tmp):
    import contention
    red = load_fresh('reduce_t', HERE/'reduce.py'); red.E_COUNT = 60
    job = reduce_fixture(Path(tmp)/'a')
    red.__dict__['__file__'] = str(job/'x'/'reduce.py')
    reads = []; real_load = red.load_student
    red.load_student = lambda *a, **k: (reads.append(a[1]), real_load(*a, **k))[1]
    out = job/'analysis'/'results.json'
    def run(extra, sha_=None, commit=None, repo=None):
        sys.argv = ['reduce.py', '--job', str(job), '--students', 'R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W', '--out', str(out),
                    '--contention-sha', sha_ or '0'*64, '--freeze-commit', commit or '0'*40, '--repo', str(repo or tmp), *extra]
        try: red.main(); return 'ok'
        except SystemExit as e: return str(e)
    gate = dict(no_receipt=run([]))
    rx = job/'receipts'/'contention-exclusion.json'; rx.write_text(json.dumps(dict(excluded_indices=[0, 1])))
    gate['sol_r1_writable_minimal'] = run([], sha_=sha(rx)); rx.unlink()
    body = contention.build(str(job)); rx_path, digest = contention.write_once(str(job), body)
    bless(rx_path)                                                  # r8: the guarded contention.py run's output
    data = Path(rx_path).read_bytes()
    repo, head = git_repo(Path(tmp)/'g1', {FREEZE: data})
    repo_bad, head_bad = git_repo(Path(tmp)/'g2', {FREEZE: data+b' '})
    repo_side, head_side = git_repo(Path(tmp)/'g3', {FREEZE: data}, on_main=False)
    gate.update(wrong_sha=run([], sha_='1'*64, commit=head, repo=repo), not_committed_bytes=run([], sha_=digest, commit=head_bad, repo=repo_bad),
                not_on_origin_main=run([], sha_=digest, commit=head_side, repo=repo_side))
    # R2-F4 Sol probe: git replace substitutes the committed blob with the declared bytes
    old_blob = git(repo_bad, 'rev-parse', f'{head_bad}:{FREEZE}')
    new_blob = subprocess.run(['git', '-C', repo_bad, 'hash-object', '-w', '--stdin'], input=data, capture_output=True, check=True).stdout.decode().strip()
    git(repo_bad, 'replace', old_blob, new_blob)
    plain_git_fooled = hashlib.sha256(subprocess.run(['git', '-C', repo_bad, 'cat-file', 'blob', f'{head_bad}:{FREEZE}'], capture_output=True).stdout).hexdigest() == digest
    gate['git_replace_substitution'] = run([], sha_=digest, commit=head_bad, repo=repo_bad)
    os.chmod(rx_path, 0o644); gate['writable'] = run([], sha_=digest, commit=head, repo=repo); os.chmod(rx_path, 0o444)
    os.link(rx_path, job/'receipts'/'hardlink'); gate['hard_linked'] = run([], sha_=digest, commit=head, repo=repo); (job/'receipts'/'hardlink').unlink()
    moved = [g for g in (job/'games').glob('*/*/a1/games/sim-000[01]-d27-*.json')]
    stamps = {g: os.stat(g) for g in moved}
    for g, st0 in stamps.items(): os.utime(g, ns=(st0.st_atime_ns, st0.st_mtime_ns+500*10**9))
    rebuilt = contention.build(str(job))['excluded_indices']
    gate['R2-F4 Sol probe: game mtimes changed, bytes unchanged'] = run([], sha_=digest, commit=head, repo=repo)
    for g, st0 in stamps.items(): os.utime(g, ns=(st0.st_atime_ns, st0.st_mtime_ns))
    rj = job/'driver'/'retired.json'; keep = rj.read_bytes(); rj.write_text(json.dumps(dict(indices=[3, 4], why=[])))
    gate['retired.json changed'] = run([], sha_=digest, commit=head, repo=repo); rj.write_bytes(keep)
    cen = job/'games'/'R5'/'S-200'/'a1'/'census.jsonl'; ck = cen.read_bytes(); cen.write_bytes(ck+b'\n')
    gate['census changed'] = run([], sha_=digest, commit=head, repo=repo); cen.write_bytes(ck)
    (job/'games'/'R5'/'S-200'/'a2').mkdir(); gate['extra phase'] = run([], sha_=digest, commit=head, repo=repo); (job/'games'/'R5'/'S-200'/'a2').rmdir()
    case("R2-F4/F4 probes: refused before any game load - no receipt, Sol's r1 writable receipt, wrong SHA, uncommitted bytes, a commit "
         "off origin/main, a GIT-REPLACE substitution (which fools plain git), writable/hard-linked receipts, changed game mtimes "
         "(whose rebuild changes the exclusion), a changed retired.json, census or phase set",
         all(v != 'ok' for v in gate.values()) and reads == [] and plain_git_fooled and body['excluded_indices'] == [0, 1] and rebuilt != [0, 1],
         refusals={k: v[:60] for k, v in gate.items()}, rebuilt=rebuilt)
    case('F10: reducer --out outside <job>/analysis is refused',
         raises(lambda: (setattr(sys, 'argv', ['reduce.py', '--job', str(job), '--students', 'R3a', '--out', str(Path(tmp)/'x.json'),
                                               '--contention-sha', digest, '--freeze-commit', head]), red.main()), io.Refusal))
    incomplete = run([], sha_=digest, commit=head, repo=repo)
    case('reducer refuses an incomplete student without --allow-prefix (fixed N), after the freeze gate', 'fixed N' in incomplete and reads)
    lp = dict(stats={s: dict(games=3, dropped_no_block=1, captured=10, duplicate=1, over_cap=0, kept=400000, kept_per_arm={'K4S-120': 5, 'S-200': 4},
                             strata={'hit': 7}, student_default=1, fallback=0, plays=4) for s in ('O', 'holdout')},
              feature_only_duplicates_by_600_tick_bucket={'0': dict(states=10, feature_duplicates=2, rate=.2)})
    lpp = wjson(job/'data'/'label-plan.json', lp); bless(lpp)           # r9 (R8-F4): the guarded label plan run
    og = wjson(job/'data'/'O-VERIFIED.json', dict(rows=399900, label_plan_sha256=sha(lpp)))
    ogw = wjson(job/'data'/'OW-VERIFIED.json', dict(roots=400100, rows=420000, single_candidate_root_share=.1, o_gate_sha256=sha(og)))
    ok = run(['--allow-prefix'], sha_=digest, commit=head, repo=repo)
    bless(out)                                                      # r8: the guarded reduce.py run's output
    r = json.loads(out.read_text()); ro = r['readout']; p = ro['primary']
    case('reducer: primary on the full primary prefix (R5W never cuts it); per-arm mean equals pooled; contention view [0,1] with SHA + commit',
         ok == 'ok' and r['paired_seeds'] == 59 and r['truncation']['r5w_prefix_seeds'] == 49 and r['truncation']['r5w_truncated']
         and abs(sum(ro['primary_by_arm'][a]['point_pp'] for a in ('K4S-120', 'S-200'))/2 - p['point_pp']) < 1e-9
         and ro['contention_sensitivity']['excluded_paired_seeds'] == 2 and ro['contention_sensitivity']['exclusion_sha256'] == digest
         and ro['contention_sensitivity']['freeze_commit'] == head)
    job2 = reduce_fixture(Path(tmp)/'b', forward=99)
    red.__dict__['__file__'] = str(job2/'x'/'reduce.py'); use_job(job2)
    rx2, d2 = contention.write_once(str(job2), contention.build(str(job2))); bless(rx2); repo2, h2 = git_repo(Path(tmp)/'g4', {FREEZE: Path(rx2).read_bytes()})
    sys.argv = ['reduce.py', '--job', str(job2), '--students', 'R3a', 'R5', 'R5-rep', 'R3a-rep', '--out', str(job2/'analysis'/'r.json'),
                '--contention-sha', d2, '--freeze-commit', h2, '--repo', repo2, '--allow-prefix']
    case('F11 probe: a policy-cache mismatch is refused in this optimization mode too', raises(lambda: red.main(), SystemExit, "pc['forward']"), optimize=sys.flags.optimize)
    use_job(job)
    cl = red.classify
    neg = {'R5 minus R3a [pooled]': dict(loss_change_pp=-1.0), 'R5-rep minus R3a [pooled]': dict(loss_change_pp=-0.5)}
    zero = dict(neg, **{'R5-rep minus R3a [pooled]': dict(loss_change_pp=0.0)})
    b = [cl(dict(ci95_pp=[-3.0, -0.01]), neg), cl(dict(ci95_pp=[-3.0, 0.0]), neg), cl(dict(ci95_pp=[-3.0, -0.01]), zero),
         cl(dict(ci95_pp=[-1.99, 1.0]), neg), cl(dict(ci95_pp=[-2.0, 1.0]), neg)]
    case('classification boundaries are strict', b == ['helps', 'inconclusive', 'inconclusive', 'no material effect', 'inconclusive'], got=b)
    def gm(loss, seat=0):
        return dict(loss=float(loss), cpu_seconds=1.0, metadata=dict(own_deck=['a'], opponent_deck=['b'], seat=seat, winner=None if loss else seat),
                    search_ab=dict(deadline_stats=[dict(wall_seconds=.1, hit=True, action=2304, wall_overrun=False, fallback=False)]))
    L = {'R3a': {'K4S-120': [1, 1, 0, 0], 'S-200': [1, 0, 0, 0]}, 'R3a-rep': {'K4S-120': [1, 0, 1, 0], 'S-200': [0, 0, 0, 0]},
         'R5': {'K4S-120': [0, 0, 0, 0], 'S-200': [1, 0, 0, 0]}, 'R5-rep': {'K4S-120': [0, 1, 0, 0], 'S-200': [0, 0, 0, 0]}}
    data = {s: {a: {i: gm(v[i]) for i in range(4)} for a, v in arms.items()} for s, arms in L.items()}
    res = red.analyze(data, list(L), [0, 1, 2, 3], dict(bootstrap=dict(seed=1, reps=200), arms={'K4S-120': dict(deadline_seconds=.12), 'S-200': dict(deadline_seconds=.2)}))
    d = res['delta'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'])
    dk = res['delta_arm'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'], 'K4S-120')['point_pp']; ds = res['delta_arm'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'], 'S-200')['point_pp']
    rd = red.readout(res, res['contrasts'], data); half = 1.96*(rd['se_boot_pp']**2+0.65**2)**.5
    case('exact formulas by hand (-37.5, 0, -18.75 pp) and fit-inflated half-width', abs(dk+37.5) < 1e-9 and abs(ds) < 1e-9
         and abs(d['point_pp']+18.75) < 1e-9 and abs(rd['fit_inflated_interval_pp'][1]-rd['point_pp']-half) < 1e-9)
    # R2-F9/R3-F4: report inputs must chain to the current study evidence
    import write_report as wr, studytree
    saved = (io.REPO, studytree.authenticate_gate)
    io.REPO = repo
    studytree.authenticate_gate = lambda j, mode: ([], sha(Path(j)/'data'/{'O': 'O-VERIFIED.json', 'OW': 'OW-VERIFIED.json', 'holdout': 'HOLDOUT-VERIFIED.json'}[mode]), {})
    try:
        docs, shas = wr.authenticate(str(job), digest, head)
        txt = wr.render(docs['results'], docs['label_plan'], docs['o_gate'], docs['ow_gate'], docs.get('diagnostic'), shas, [])
        need = ['Primary Δ by arm', 'R5W secondaries 49 seeds', 'O composition and duplicates', 'single-candidate root share = 10.0%',
                'R3a-rep differs from R3a', 'decision table', 'unavailable (not completed before the hard stop, or its guarded run did not pass)', '| R5W | — | unavailable']
        bind = {}
        def tamper_results(**ch):
            rr = json.loads(out.read_text()); keep_r = out.read_bytes()
            for k, v in ch.items():
                tgt = rr
                for part in k.split('.')[:-1]: tgt = tgt[part]
                tgt[k.split('.')[-1]] = v
            out.chmod(0o644); out.write_text(json.dumps(rr)); bless(out)   # guarded, so the binding checks decide
            res_ = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit); out.write_bytes(keep_r); return res_
        bind["Sol R3-F4: fake C5 identity strings"] = tamper_results(**{'identities.contention_receipt_sha256': 'not-a-sha', 'identities.freeze_commit': 'not-a-commit',
                                                                        'readout.contention_sensitivity.exclusion_sha256': 'not-a-sha'})
        bind['results reduced under other gates'] = tamper_results(**{'identities.gates': dict(O='0'*64, OW='0'*64)})
        bind['results reduced with other checkpoints'] = tamper_results(**{'identities.students': dict(r['identities']['students'], R5=dict(checkpoint_sha256='WRONG', threshold=None))})
        bind['results without identities (pre-r4 reducer)'] = tamper_results(identities=None)
        bind['Sol R4-F4: identities.students empty'] = tamper_results(**{'identities.students': {}})
        for sid in wr.STUDENTS:
            bind[f'R4-F4: identities omit {sid}'] = tamper_results(**{'identities.students': {k: v for k, v in r['identities']['students'].items() if k != sid}})
        bind['R4-F4: duplicate reduced student'] = tamper_results(students=r['students']+['R5'])
        # R4-F6 (Sol): the full freeze runs before results are opened; post-reduction census change refused
        opened = []; real_rb = io.read_bytes
        def spy_rb(path, *a, **k): opened.append(str(path)); return real_rb(path, *a, **k)
        rx = job/'receipts'/'contention-exclusion.json'; rkeep = rx.read_bytes(); rx.chmod(0o644); rx.unlink()
        io.read_bytes = spy_rb
        try: no_c5 = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'C5')
        finally: io.read_bytes = real_rb
        rx.write_bytes(rkeep); rx.chmod(0o444)
        bind['Sol R4-F6: missing C5 receipt refused and results.json never opened'] = no_c5 and not any(o.endswith('results.json') for o in opened)
        cen = job/'games'/'R5'/'S-200'/'a1'/'census.jsonl'; ck = cen.read_bytes(); cen.write_bytes(ck+b'\n')
        bind['Sol R4-F6: census changed after reduction'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'changed since the freeze'); cen.write_bytes(ck)
        bind['wrong declared C5 SHA'] = raises(lambda: wr.authenticate(str(job), '1'*64, head), SystemExit, 'C5')
        ogw_keep = ogw.read_bytes()
        wjson(job/'data'/'OW-VERIFIED.json', dict(roots=1, rows=1, single_candidate_root_share=.1, o_gate_sha256='0'*64))
        bind['O_W gate not built on this O gate'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'O_W gate'); ogw.write_bytes(ogw_keep)
        wjson(job/'data'/'label-plan.json', dict(lp, utc='other')); bless(job/'data'/'label-plan.json')
        bind['stale label plan'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'O gate was not verified against this label plan')
        wjson(job/'data'/'label-plan.json', lp)
        hg = wjson(job/'data'/'HOLDOUT-VERIFIED.json', dict(mode='holdout'))
        staged = {k: v for k, v in r['identities']['students'].items()}
        good_diag = dict(holdout_gate_sha256=sha(hg), heldout64_sha256=wr.HELDOUT64_SHA, students={k: {} for k in wr.STUDENTS}, student_checkpoints=staged)
        wjson(job/'analysis'/'diagnostic.json', good_diag); bless(job/'analysis'/'diagnostic.json'); diag_ok = wr.authenticate(str(job), digest, head)[0].get('diagnostic') is not None
        wjson(job/'analysis'/'diagnostic.json', dict(good_diag, student_checkpoints={k: dict(checkpoint_sha256='WRONG', threshold=None) for k in staged})); bless(job/'analysis'/'diagnostic.json')
        bind["Sol R3-F4: diagnostic with WRONG checkpoints"] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'checkpoints')
        wjson(job/'analysis'/'diagnostic.json', dict(good_diag, student_checkpoints={k: v for k, v in staged.items() if k != 'R5W'})); bless(job/'analysis'/'diagnostic.json')
        bind['R4-F4: diagnostic omits R5W checkpoints'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'checkpoints')
        wjson(job/'analysis'/'diagnostic.json', dict(good_diag, heldout64_sha256='0'*64)); bless(job/'analysis'/'diagnostic.json')
        bind['diagnostic without the fixed held-out64'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'held-out64')
        wjson(job/'analysis'/'diagnostic.json', dict(good_diag, holdout_gate_sha256='0'*64)); bless(job/'analysis'/'diagnostic.json')
        bind['diagnostic not on the verified holdout'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'holdout')
        (job/'analysis'/'diagnostic.json').unlink()
        io.REPO = repo_side
        bind['C5 commit not on this repository\'s origin/main'] = raises(lambda: wr.authenticate(str(job), digest, head), SystemExit, 'C5')
    finally:
        io.REPO, studytree.authenticate_gate = saved
    sys.argv = ['write_report.py', '--contention-sha', digest, '--freeze-commit', head, '--out', str(Path(tmp)/'RESULTS.md')]
    case('R2-F9/R3-F4/R4-F4/R4-F6: the report renders every section and an explicit unavailable diagnostic; it refuses fake C5 identities, results '
         'reduced under other gates or checkpoints, unchained gates, a stale plan, diagnostics with wrong checkpoints/held-out64/holdout, '
         'an off-main C5 commit, empty or partial model identities (each student), a duplicate student, a diagnostic missing R5W, a '
         'missing C5 receipt WITHOUT opening results.json, a post-reduction census change and an out-of-root --out', all(n in txt for n in need) and diag_ok and all(bind.values()) and raises(lambda: wr.main(), io.Refusal),
         missing=[n for n in need if n not in txt], bind=bind)


# ================================================================ qualification (F3, F12, R2-F8)
def qual_phase(root, name, arms, rng, base, cmd='h', capture=True, fair_moved=True, drop_case=None, cfg_sha=None, terminal=True, ck=None):
    ph = Path(root)/name
    wjson(ph/'schedule.json', dict(range=rng, indices=list(range(8)), cases=[[i, base+i, arm, 'own', 'opp'] for i in range(8) for arm in arms], config_sha256=cfg_sha))
    for i in range(8):
        games = {}
        for arm in arms:
            if drop_case == (i, arm): continue
            g = write_game(ph, arm, i, base, terminal=terminal, budget_ms=1000000, checkpoint_sha256=ck, cmd=f'{cmd}{i}{arm}')
            games[g.name] = sha(g)
            if capture:
                caps = [pickle.dumps(dict(schema='x4s4.capture.v3', id=f'{arm}/{i}/{t}', pending=(), seed=base+i, index=i, arm=arm)) for t in range(3)]
                body = pickle.dumps(caps); (ph/'captures').mkdir(exist_ok=True)
                (ph/'captures'/f'sim-{i:04d}-d27-{arm}.pkl').write_bytes(body)
                checks = dict(belief_checked=3, belief_unchanged=3, fair_checked=3, fair_identical=3, fair_perturbed_decisions=3 if fair_moved else 0,
                              fair_checked_early=3, fair_perturbed_early=3 if fair_moved else 0)
                wjson(ph/'captures'/f'sim-{i:04d}-d27-{arm}.json', dict(schema='x4s4.capture.v3', sha256=hashlib.sha256(body).hexdigest(), captures=3,
                      index=i, seed=base+i, arm=arm, identity_ok=True, counts=dict(captured=3, not_search=1), checks=checks,
                      features_equal_all=True, public_equal_all=True, pending_empty_all=True))
        wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=base+i, order=arms, games=games))
    return ph


def healthy_host(fn):
    """r7: qualify4 subcommands now run study admission (QualGuard); offline the host measurements are stubbed healthy
    (MemAvailable 100 GiB, PSI 1.0) and restored afterwards."""
    def wrapped(tmp):
        import studytree as ST
        saved = (ST.mem_available, ST.psi_some_avg10)
        ST.mem_available, ST.psi_some_avg10 = (lambda: 100*2**30), (lambda: 1.0)
        try: return fn(tmp)
        finally: ST.mem_available, ST.psi_some_avg10 = saved
    wrapped.__name__ = fn.__name__
    return wrapped


@healthy_host
def test_qualify(tmp):
    stub_torch_imports()
    import qualify4 as Q, label
    job = new_job(tmp)
    cfg = HERE/'plan-qual-capture.json'; cs = sha(cfg); ck = json.loads(cfg.read_text())['student']['checkpoint_sha256']
    run_ph = qual_phase(job/'qual', 'run', list(Q.QUAL_ARMS), 'qualification', QUAL, capture=False, cfg_sha=cs, ck=ck)
    def hashes(name, **kw):
        col = qual_phase(job/'qual', name, list(Q.QUAL_ARMS), 'qualification', QUAL, cfg_sha=cs, ck=kw.pop('ck', ck), **kw)
        out = job/'qual'/f'{name}.json'
        try: Q.main(['hashes', '--run-phase', str(run_ph), '--collect-phase', str(col), '--config', str(cfg), '--out', str(out)]); rc = 0
        except SystemExit as e: rc = e.code
        return rc, json.loads(out.read_text())
    rc, body = hashes('col-ok')
    case('qualify hashes: 16/16 proved, projected-terminal cases with equal command hashes, capture checks and fair coverage pass',
         rc == 0 and body['cases'] == 16 and readonly(job/'qual'/'col-ok.json'), error=body.get('error'))
    negs = dict(nonterminal_16=hashes('col-nt', terminal=False), missing_case=hashes('col-15', drop_case=(7, 'S-long')),
                unmoved_permutation=hashes('col-fair', fair_moved=False), command_hash_differs=hashes('col-cmd', cmd='x'),
                wrong_student=hashes('col-ck', ck='f'*64))
    case("R2-F8 probes (Sol): qualification FAILS on 16 non-terminal games with valid proofs, and on 15/16 cases, an unmoved permutation, "
         "a command-hash difference or another student checkpoint", all(v[0] == 1 and v[1]['passed'] is False for v in negs.values()),
         errors={k: v[1].get('error', '')[:60] for k, v in negs.items()})
    sk, ss = job/'collect'/'smoke'/'K4S-120', job/'collect'/'smoke'/'S-200'
    for ph, arm in ((sk, 'K4S-120'), (ss, 'S-200')):
        for i in range(8): write_collect_game(ph, arm, i, (100, 110), base=SMOKE)
        wjson(ph/'schedule.json', dict(range='smoke', indices=list(range(8)), cases=[[i, SMOKE+i, arm] for i in range(8)]))
    caps = Q.all_captures([sk, ss], label)
    missing_arm = raises(lambda: Q.all_captures([sk], label), Q.QualError, 'cover')
    for c in caps:
        c.update(reserved_packet=[1], opponent_elixir=5.0)
        c['c8_sha256'] = hashlib.sha256(pickle.dumps(([1], 5.0, ()), protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()
    good = Q.roundtrip_check(caps, lambda *a: (5, [5], [0.1]))
    bad_digest = Q.roundtrip_check(caps, lambda *a: (_ for _ in ()).throw(LookupError('digest')))
    (sk/'games'/'sim-0003-d27-K4S-120.json').write_text('{"forged": 1}')
    forged = raises(lambda: Q.all_captures([sk, ss], label), Q.QualError, 'block proof')
    case('F12/R2-F8: round trip covers ALL 32 smoke captures, each smoke game proof-authenticated; a missing arm, a digest error or a forged '
         'smoke game fails', good['passed'] and good['checked'] == 32 and missing_arm and not bad_digest['passed'] and forged)
    def parity_phase(name, arm, n, hit, base_i):
        ph = job/'collect'/name
        for i in range(base_i, base_i+n):
            g = write_game(ph, arm, i, C, hit=hit, n=1000, sd=223 if arm == 'K4S-120' else 0); wjson(ph/'blocks'/f'{i:04d}.json', dict(index=i, seed=C+i, order=[arm], games={g.name: sha(g)}))
        finish_phase(ph, arm, exit_=False)
        return ph
    pk = parity_phase('pk', 'K4S-120', 3, 642, 0); ps = parity_phase('ps', 'S-200', 3, 753, 2000)
    for ph in (pk, ps): finish_phase(ph)
    case('parity: one arm does not pass; both arms in band pass with an inventory', not Q.parity_once([pk], 3)['passed'] and Q.parity_once([pk, ps], 3)['passed'])
    pbad = parity_phase('pbad', 'S-200', 3, 700, 2100); finish_phase(pbad)
    def run_parity(phases, out, watch='0'):
        try: Q.main(['parity', '--phases', *map(str, phases), '--min-games', '3', '--watch', watch, '--out', str(out)])
        except SystemExit as e: return e.code
    def run_parity_bank(phases, out, bank):
        try: Q.main(['parity', '--phases', *map(str, phases), '--min-games', '3', '--bank', bank, '--out', str(out)])
        except SystemExit as e: return e.code
    rc = run_parity([pk, pbad], job/'receipts'/'pw.json', '1')
    case('C7b: out of band the parity command writes PARITY-PAUSE, creates STOP and exits 1',
         rc == 1 and list((job/'receipts').glob('PARITY-PAUSE-*.json')) and os.path.lexists(job/'STOP'))
    (job/'STOP').unlink()
    smp = []
    for arm, idx in (('K4S-120', (0, 1, 2)), ('S-200', (3, 4, 5))):
        sm = job/'collect'/f'smoke-par-{arm}'; smp.append(sm)
        for i in idx:
            g = write_game(sm, arm, i, SMOKE, hit=642 if arm == 'K4S-120' else 753, n=1000, sd=223 if arm == 'K4S-120' else 0)
            wjson(sm/'blocks'/f'{i:04d}.json', dict(index=i, seed=SMOKE+i, order=[arm], games={g.name: sha(g)}))
        finish_phase(sm, arm, rng='smoke', base=SMOKE)
    rc_s = run_parity_bank(smp, job/'receipts'/'smoke-par.json', 'smoke'); rc_c = run_parity_bank(smp, job/'receipts'/'smoke-as-c.json', 'collection')
    case('R3-F5 probe (Sol): --bank smoke runs PLAN §6.2 deadline parity on block-proved smoke-bank games (passes); the same games are '
         'refused as bank C', rc_s == 0 and json.loads((job/'receipts'/'smoke-par.json').read_text())['bank'] == 'smoke' and rc_c == 1)
    # R4-F5 probes (Sol): the producer refuses deficient execution evidence; a declared guard stop is an allowed interruption
    def parity_probe(name, edit):
        a = parity_phase(name+'-k', 'K4S-120', 3, 642, 0); b = parity_phase(name+'-s', 'S-200', 3, 753, 2000)
        finish_phase(a); finish_phase(b); edit(a, b)
        out = job/'receipts'/f'{name}.json'; rc_ = run_parity([a, b], out)
        return rc_, json.loads(out.read_text())
    pr = dict(failed_exit=parity_probe('fx', lambda a, b: [finish_phase(x, reason=None, rc=17) for x in (a, b)]),
              missing_schedule_launch=parity_probe('ms', lambda a, b: [((x/'schedule.json').unlink(), (x/'launch.json').unlink()) for x in (a, b)]),
              config_mismatch=parity_probe('cm', lambda a, b: wjson(a/'launch.json', dict(workers=10, config_sha256='d'*64))),
              phases_on_two_configs=parity_probe('c2', lambda a, b: finish_phase(b, cfg='e'*64)),
              live_group_at_exit=parity_probe('lg', lambda a, b: wjson(a/'supervisor-exit.json', dict(reason=None, returncode=0, remaining_group_pids=[123]))))
    allowed = parity_probe('gs', lambda a, b: finish_phase(a, reason='memory_guard', rc=1))
    case("R4-F5 probes (Sol): parity refuses a returncode-17 exit, missing schedule/launch, mismatched or two configs and a live group "
         "at exit; a declared guard stop (memory_guard) passes as an 'interrupted' phase",
         all(v[0] == 1 and v[1]['passed'] is False for v in pr.values()) and allowed[0] == 0
         and sorted(e['status'] for e in allowed[1]['evidence'].values()) == ['clean', 'interrupted'],
         errors={k: v[1].get('error', '')[:60] for k, v in pr.items()})
    pnf = parity_phase('pnf', 'S-200', 3, 753, 2200)
    rc2 = run_parity([pk, pnf], job/'receipts'/'pnf.json')
    case('R2-F8: a parity receipt over a phase without supervisor-exit is not final and does not pass',
         rc2 == 1 and json.loads((job/'receipts'/'pnf.json').read_text())['final'] is False)


# ================================================================ diagnose (F15, R2-F3, R2-F9)
def test_diagnose(tmp):
    import diagnose as Dg
    rng = np.random.default_rng(7); n = 257
    g, c, t = rng.random(n), rng.random(n), rng.random(n); w = rng.integers(0, 2, n).astype(float); pm = rng.random(n)
    def agg(bs, order):
        acc = Dg.CEAccumulator()
        for s in range(0, n, bs): j = order[s:s+bs]; acc.add(g[j], c[j], t[j], w[j], pm[j])
        return acc.result()
    ref = agg(n, np.arange(n))
    inv = all(abs(agg(bs, rng.permutation(n))[k]-ref[k]) < 1e-9 for bs in (1, 7, 64) for k in ('listwise_ce', 'frozen_objective'))
    acc = Dg.CEAccumulator(); acc.add([0.]*4, [0.]*4, [0.]*4, [1.]*4, [0.]*4); acc.add([0.]*4, [1.]*4, [1.]*4, [1.]*4, [1.]*4)
    case("F15: global CE is batch-size/order invariant and gives C (not C/2) on Sol's counterexample (formula algebra; GPU path is qualification)",
         inv and abs(ref['frozen_objective']-((g*w).sum()/w.sum()+((c+t)*w).sum()/(w*pm).sum())) < 1e-9 and abs(acc.result()['frozen_objective']-2.0) < 1e-12)
    job = new_job(tmp)
    lock = Dg.acquire_lock(str(job)); body = json.loads(Path(lock).read_text())
    ok = body['pid'] == os.getpid() and body['starttime'] == io.own_identity()['starttime'] and (job/'driver'/'DISPATCH.lock').exists()
    Path(lock).unlink()
    me = io.own_identity(); lead = io.proc_stat(me['pgid'])
    wjson(job/'receipts'/'phase-R3a-K4S-120-a1-launch.json', dict(pgid=me['pgid'], starttime=lead['starttime']))
    refused = raises(lambda: Dg.acquire_lock(str(job)), SystemExit, 'live') and not (job/'driver'/'DIAGNOSTIC.lock').exists()
    (job/'receipts'/'phase-R3a-K4S-120-a1-launch.json').unlink()
    guard = Dg.guard_factory(str(job)); os.symlink(job/'nowhere', job/'STOP')
    stops = raises(guard, Dg.Abort, 'owned_STOP')
    (job/'STOP').unlink(); (job/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n'); hard = raises(guard, Dg.Abort, 'hard_stop')
    (job/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    unauth = raises(lambda: Dg.students_of(str(job)), io.Refusal) and raises(lambda: Dg.holdout_of(str(job)), io.Refusal)
    wjson(job/'data'/'HOLDOUT-VERIFIED.json', dict(mode='O', batches=[dict(name='batch-0000')])); bless(job/'data'/'HOLDOUT-VERIFIED.json')
    wrong_gate = raises(lambda: Dg.holdout_of(str(job)), io.Refusal, 'holdout gate')
    # R3-F3 probe (Sol): a fully sealed TRAINING corpus (seed C+0) swapped into the holdout path is refused before any loader
    stub_torch_imports()
    from imitation.exit_r1 import pack as packmod
    hroot = job/'data'/'onpolicy-holdout'
    ow_game(Path(tmp)/'hraw'/'game-00000', C+3500, 4, index=56); ow_game(Path(tmp)/'traw'/'game-00000', C+0, 4, index=56)
    packmod.pack([Path(tmp)/'hraw'], hroot/'batch-0000')
    mh = hashlib.sha256((hroot/'batch-0000'/'manifest.json').read_bytes()).hexdigest()
    shared = dict(batches=[dict(name='batch-0000', manifest_sha256=mh, rows=6, roots=4, games=1)], rows=6, roots=4, rows_per_arm={'K4S-120': 6},
                  single_candidate_root_share=0.25, sources_sha256='5'*64, label_plan_sha256='6'*64, label_receipts_sha256=['7'*64],
                  parity_receipt_sha256='8'*64)
    rc = wjson(hroot/'VERIFY-RECEIPT.json', dict(shared, passed=True, sealed=True, mode='holdout'))
    wjson(job/'data'/'HOLDOUT-VERIFIED.json', dict(shared, mode='holdout', receipt_sha256=sha(rc))); bless(job/'data'/'HOLDOUT-VERIFIED.json')
    authentic = Dg.holdout_of(str(job))[0] == [str(hroot/'batch-0000')]
    shutil.move(str(hroot/'batch-0000'), str(Path(tmp)/'orig-batch')); packmod.pack([Path(tmp)/'traw'], hroot/'batch-0000')
    substituted = raises(lambda: Dg.holdout_of(str(job)), io.Refusal, 'manifest pin')
    shutil.rmtree(hroot/'batch-0000'); shutil.move(str(Path(tmp)/'orig-batch'), str(hroot/'batch-0000'))
    (hroot/'batch-0001').mkdir(); extra_batch = raises(lambda: Dg.holdout_of(str(job)), io.Refusal, 'inventory'); (hroot/'batch-0001').rmdir()
    rc.write_text(json.dumps(dict(shared, passed=True, sealed=True, mode='holdout', note='edited'))); receipt_changed = raises(lambda: Dg.holdout_of(str(job)), io.Refusal, 'receipt')
    case('R3-F3 probes (Sol): the holdout selector authenticates the current corpus - a substituted sealed training corpus, an extra batch '
         'and an edited verifier receipt are refused; the authentic gate passes', authentic and substituted and extra_batch and receipt_changed)
    case('R2-F3/F9 probes: the diagnostic lock (pid + starttime) is taken under the DISPATCH flock and refused while reporting/fit work lives; '
         'live guards abort on STOP and the hard stop; inputs come only from the verified holdout gate and the staged students',
         ok and refused and stops and hard and unauth and wrong_gate)


# ================================================================ seed audit (R2-F6, F11)
def test_audit(tmp):
    import audit_seeds as A
    inside = b'seed 4503606307370500 here'
    plan = (HERE/'plan.json').read_bytes()
    files = {'reports/explore/x4s4/plan.json': plan,
             'reports/explore/t1/RESULTS.json': inside+b' T1-OUTCOME',
             'reports/explore/ordinary.json': inside+b' T1-OUTCOME',            # content alias of the sealed outcome (hard-link twin)
             'reports/explore/t1/outcomes/plan.json': inside,                   # declaration name under an outcome-bearing ancestor
             'reports/explore/t1/seed-audit.json': json.dumps(dict(r=dict(base=4503601407370496, count=600))).encode(),
             'reports/strategy_council_20260928/live-loop/v4/tiers-complete.json': inside,
             'reports/explore/k-old/seed-audit.json': json.dumps(dict(r=dict(base=4503601007370496, count=10))).encode(),
             'reports/explore/k-old/notes.md': b'nothing here'}
    repo, head = git_repo(Path(tmp)/'r', files)
    entries = io.git_ls_tree(repo, head)
    sources, omitted, decls = A.derive_inventory(entries)
    paths = {s[0] for s in sources}
    excluded = {'reports/explore/t1/RESULTS.json', 'reports/explore/ordinary.json', 'reports/explore/t1/outcomes/plan.json',
                'reports/strategy_council_20260928/live-loop/v4/tiers-complete.json'}
    inv = dict(schema=A.RULE, commit=head, sources_sha256=A.list_sha(sources), omitted=omitted, sealed_declarations=decls)
    requested = []
    real = io.git_blobs
    def spy(r, oids, **k): requested.extend(oids); return real(r, oids, **k)
    io.git_blobs = spy
    try: out = A.audit(repo, inv, json.loads(plan)); clean = True
    except A.AuditError as e: out, clean = None, str(e)
    finally: io.git_blobs = real
    bad_oids = {e[2] for e in entries if e[4] in excluded}
    case("R2-F6 probes (Sol): an outcome file, its content alias elsewhere (hard-link twin) and a declaration name under an outcome-bearing "
         "ancestor (t1/outcomes/plan.json) are never read; the sealed seed declaration is; omissions are counted per reason",
         clean is True and not (paths & excluded) and not (set(requested) & bad_oids) and 'reports/explore/t1/seed-audit.json' in paths
         and omitted.get('alias_of_excluded') == 1 and omitted.get('outcome_path', 0) >= 2, omitted=omitted, err=clean)
    case('R2-F6: the audit refuses a source list that differs from the reviewed inventory',
         raises(lambda: A.audit(repo, dict(inv, sources_sha256='0'*64), json.loads(plan)), A.AuditError, 'differs'))
    files2 = dict(files, **{'reports/explore/k-old/notes.md': inside+b' notes'})
    repo2, head2 = git_repo(Path(tmp)/'r2', files2)
    s2, o2, d2 = A.derive_inventory(io.git_ls_tree(repo2, head2))
    case('R2-F6 control: the same literal in an ordinary scan source fails the audit (the scan is live)',
         raises(lambda: A.audit(repo2, dict(schema=A.RULE, commit=head2, sources_sha256=A.list_sha(s2), omitted=o2, sealed_declarations=d2),
                                json.loads(plan)), A.AuditError, 'raw literals'))
    p2 = json.loads(plan); p2['seed_ranges']['smoke'] = dict(p2['seed_ranges']['reporting'])
    case('F11 probe: identical bank bases fail in this optimization mode too', raises(lambda: A.audit(repo, inv, p2), A.AuditError), optimize=sys.flags.optimize)
    files3 = dict(files, **{'reports/explore/k-old/seed-audit.json': json.dumps(dict(r=dict(base=E+100, count=10))).encode()})
    repo3, head3 = git_repo(Path(tmp)/'r3', files3)
    s3, o3, d3 = A.derive_inventory(io.git_ls_tree(repo3, head3))
    case('F11: a declared prior range intersecting bank E fails the audit',
         raises(lambda: A.audit(repo3, dict(schema=A.RULE, commit=head3, sources_sha256=A.list_sha(s3), omitted=o3, sealed_declarations=d3),
                                json.loads(plan)), A.AuditError, 'intersects'))
    committed = json.loads((HERE/'seed-sources.json').read_text())
    case('the committed seed-sources.json pins a commit, the rule version, the derived list SHA and the explicit sealed declarations',
         committed['schema'] == A.RULE and len(committed['commit']) == 40 and len(committed['sources_sha256']) == 64
         and all(s[2] == 'sealed_declaration' for s in committed['sealed_declarations']))


# ================================================================ study tree (R2-F3)
def test_studytree(tmp):
    import studytree as S, label
    job = new_job(tmp)
    rec = S.register(str(job), 'label-O')
    wjson(job/'collect'/'K4S-120'/'a1'/'launch.json', dict(child_pgid=777001, child_starttime=5, supervisor_pgid=777002, supervisor_starttime=6))
    g = S.groups(str(job))
    case('CPU jobs register (pgid, starttime); phase supervisors and children are tree groups', (777001, 5) in g and (777002, 6) in g and Path(rec).exists())
    saved = (S.processes, S.disk_bytes)
    S.processes = lambda grps: [1]*20; S.disk_bytes = lambda j=None: 10**9
    res = dict(add_50=not S.admission(str(job), add=51)[0], add_50_ok=S.admission(str(job), add=50)[0])
    S.disk_bytes = lambda j=None: None; res['disk_unreadable'] = not S.admission(str(job))[0]
    S.disk_bytes = lambda j=None: 101*10**9; res['disk_over'] = not S.admission(str(job))[0]
    S.processes, S.disk_bytes = saved[0], lambda j=None: 10**9
    sm, sp = S.mem_available, S.pss_bytes
    S.mem_available = lambda: None; res['mem_unreadable'] = S.monitor(str(job)) == 'memory_guard'
    S.mem_available = lambda: 100*2**30; S.pss_bytes = lambda pids: None; me = io.own_identity()
    res['pss_unreadable'] = S.monitor(str(job), own=(me['pgid'], io.proc_stat(me['pgid'])['starttime']), check_psi=False) == 'pss_guard'
    S.pss_bytes = lambda pids: 51*2**30; res['pss_over_50'] = S.monitor(str(job), own=(me['pgid'], io.proc_stat(me['pgid'])['starttime']), check_psi=False) == 'pss_guard'
    S.pss_bytes = sp
    os.symlink(job/'nowhere', job/'STOP'); res['dangling_STOP'] = S.monitor(str(job)) == 'owned_STOP'; (job/'STOP').unlink()
    (job/'HARD-STOP-UTC.txt').unlink(); res['deadline_unreadable'] = S.hard_stop_passed(str(job)) is True
    S.mem_available = sm; S.disk_bytes = saved[1]
    case('R2-F3 probes: admission RESERVES new workers (20 live + 51 > 70); disk unreadable/over; monitor stops on unreadable memory, '
         'unreadable or > 50 GiB PSS, a dangling STOP and an unreadable deadline', all(res.values()), res=res)


# ================================================================ live dispatch / acceptance paths (R3-F2)
def _echo(e): return dict(status='sealed', e=e)


def emitter_game(d, seed, index, own_deck, opp_deck, replay_exact=True):
    from imitation.exit_r1.rows import seal, write_json
    d = Path(d); seat = index % 2
    r = dict(seed=seed, index=index, opponent='v1', seat=seat, root_decisions=3, outcome=1.0, cpu_seconds=1.0,
             episode=dict(decks=[own_deck, opp_deck] if seat == 0 else [opp_deck, own_deck]))
    write_json(d/'replay.json', r)
    rows, scores = [], []
    for t in range(3):
        row = synth_row(seed, t); row.update(expert_actions=np.int16(2304), expert_action_supervision_valid=np.bool_(True),
            submitted_ticks=np.int32(t), teacher_search_action=np.int16(2304), teacher_root=np.bool_(True), teacher_wait_kind=np.int8(0),
            recorded_play_ticks=np.int32(-1), recorded_world_positions=np.array([np.nan, np.nan], np.float32),
            submitted_world_positions=np.array([np.nan, np.nan], np.float32), recorded_millitiles=np.array([-1, -1], np.int32))
        rows.append(row); scores.append(dict(candidates=[5, 2304], scores=[.1, .2]))
    r = dict(r, replay_exact=replay_exact); seal(d, rows, scores, r)
    return r


def test_live_paths(tmp):
    stub_torch_imports()
    import label, collect_w, studytree as ST
    saved = (ST.mem_available, ST.psi_some_avg10)
    ST.mem_available = lambda: 100*2**30; ST.psi_some_avg10 = lambda: 1.0
    fake_me = dict(pid=os.getpid(), pgid=2**22+77, leader_start=1)       # an empty group: stop_workers can signal nothing here
    try:
        # Sol R3-F2 probe 3: valid PSI 90 must DELAY label dispatch (no work runs), while the live monitor keeps running
        calls = dict(n=0)
        def monitor():
            calls['n'] += 1; return 'owned_STOP' if calls['n'] >= 4 else None
        res, halted = label.dispatch([1, 2], 1, _echo, fake_me, monitor=monitor, admit=lambda: (False, 'memory PSI > 10'), poll=0.05)
        gated = res == [] and halted == 'owned_STOP' and calls['n'] >= 4
        res2, halted2 = label.dispatch([1, 2], 1, _echo, fake_me, monitor=lambda: None, admit=lambda: (True, None), poll=0.05)
        ST.psi_some_avg10 = lambda: 90.0; real_admit = ST.dispatch_ok(); ST.psi_some_avg10 = lambda: 1.0
        case('R3-F2 probe (Sol): with valid PSI 90 label dispatch submits nothing (the real dispatch admission refuses) and the live monitor '
             'still runs; with admission it dispatches normally', gated and sorted(r['e'] for r in res2) == [1, 2] and halted2 is None
             and real_admit == (False, 'memory PSI unreadable or > 10'))
        # Sol R3-F2 probe 1: an acceptance game straddling the hard stop is rejected and the smoke does not pass
        job = new_job(tmp); collect_w.JOB = str(job)
        collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
        def straddle(seed, index, directory, opponent, stop, acceptance):
            g = seed-QUAL
            r = emitter_game(directory, seed, index, collect_w.X[g % 5], collect_w.X[(g//5) % 5])
            if g == 1: (job/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
            return r
        collect_w.emitter = types.SimpleNamespace(run_game=straddle)
        passed = collect_w.acceptance_smoke(fake_me, monitor=lambda: None, poll=0.1)
        rows = json.loads((job/'data'/'raw-OW-acceptance-smoke.json').read_text())['games']
        case('R3-F2 probe (Sol): an acceptance game finishing after the hard stop is rejected; the smoke receipt says passed=false',
             passed is False and [r['status'] for r in rows] == ['sealed', 'past_hard_stop'])
    finally:
        ST.mem_available, ST.psi_some_avg10 = saved
    # in-flight STOP during an acceptance game: an isolated session (its own group), the parent stops the worker by PID
    job2 = new_job(tmp, 'inflight')
    script = Path(tmp)/'acc.py'
    script.write_text(f"""import sys, json, time, types, threading, os
sys.path[:0] = {[str(REPO), str(REPO/'src'), str(HERE)]!r}
import x4s4io as io
io.JOB = {str(job2)!r}
import collect_w, studytree as ST
collect_w.JOB = io.JOB
ST.mem_available = lambda: 100*2**30; ST.psi_some_avg10 = lambda: 1.0
collect_w.X = [['d%d-%d' % (d, c) for c in range(8)] for d in range(5)]
def slow(seed, index, directory, opponent, stop, acceptance):
    open('/proc/self/comm', 'w').write('x4s4accslow'); time.sleep(60)
collect_w.emitter = types.SimpleNamespace(run_game=slow)
threading.Timer(1.0, lambda: os.symlink(io.JOB+'/nowhere', io.JOB+'/STOP')).start()
t0 = time.monotonic()
ok = collect_w.acceptance_smoke(collect_w.identity(), poll=0.2)
print(json.dumps(dict(passed=ok, seconds=time.monotonic()-t0)))
""")
    r = subprocess.run([PY, '-B', str(script)], capture_output=True, text=True, timeout=120, start_new_session=True)
    try: info = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: info = dict(raw=r.stdout[-300:], err=r.stderr[-500:])
    rows = json.loads((job2/'data'/'raw-OW-acceptance-smoke.json').read_text())['games'] if (job2/'data'/'raw-OW-acceptance-smoke.json').exists() else []
    def comm(pid):
        try: return open(f'/proc/{pid}/comm').read().strip()
        except OSError: return ''
    leftover = [p for p in io.all_pids() if comm(p) == 'x4s4accslow']
    case('R3-F2 probe (Sol): a STOP (dangling link) during an in-flight acceptance game makes the parent stop the worker by PID within '
         'seconds; passed=false with a halted row', info.get('passed') is False and info.get('seconds', 99) < 30 and rows and rows[0]['status'] == 'halted'
         and not leftover, info=info, rows=rows)


# ================================================================ r6: Sol r5 findings R5-F1..F4 and the Q-D2(a) smoke-pack
@healthy_host
def test_r6(tmp):
    import studytree as ST
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    def stop_link(job): time.sleep(0.1); os.symlink(Path(job)/'nowhere', Path(job)/'STOP')   # strictly after prior outputs (H-1 margin)
    def r6_driver(sub):
        """A driver over a fresh job with healthy measurements; io.spawn is a spy that records any child creation."""
        drv, job = driver_module(tmp/sub)
        spawned = []
        ns = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
        def spy(argv, *a, **k):
            spawned.append(argv); raise RuntimeError('spawn reached')
        ns.spawn = spy; drv.io = ns
        drv.mem_available = lambda: 100*2**30; drv.psi_some_avg10 = lambda: 0.0; drv.gpu_used_mib = lambda: 0
        drv.studytree = types.SimpleNamespace(**{k: getattr(ST, k) for k in dir(ST) if not k.startswith('__')})
        drv.studytree.admission = lambda job, add=0, disk=True: (True, None)
        return drv, job, spawned
    def lock_hook(drv, hook):
        class Lock:
            def __enter__(self): hook(); return self
            def __exit__(self, *e): return False
        drv.DispatchLock = Lock
    def refused(job): return [e for e in map(json.loads, (Path(job)/'driver'/'events.jsonl').read_text().splitlines()) if e['kind'] == 'launch_refused'] \
        if (Path(job)/'driver'/'events.jsonl').exists() else []
    def attempt(fn):
        try: return fn()
        except RuntimeError as e: return 'SPAWNED' if 'spawn reached' in str(e) else repr(e)

    # ---- R5-F1: STOP / deadline crossing during the lock wait, resource admission and corpus preparation
    def fit_case(sub, where, kind):
        drv, job, spawned = r6_driver(sub)
        drv.fit_state = lambda f: ('pending', None); drv.live_supervisor = lambda: None
        wjson(job/'data'/'O-VERIFIED.json', {})
        cross = (lambda: stop_link(job)) if kind == 'STOP' else (lambda: setattr(drv, 'STOP_AT', past))
        lock_hook(drv, cross if where == 'lock' else (lambda: None))
        real_ok = drv.resources_ok
        drv.resources_ok = (lambda for_fit=False: (cross(), real_ok(for_fit))[1]) if where == 'resources' else real_ok
        drv.prepare_fit_dirs = (lambda fid: (cross(), (['batch-0000'], 'g'*64))[1]) if where == 'corpus' else (lambda fid: (['batch-0000'], 'g'*64))
        r = attempt(lambda: drv.Fits().tick())
        return r != 'SPAWNED' and not spawned and not (job/'receipts'/'fit-R5-launch.json').exists()
    fits_cross = {f'{w}/{k}': fit_case(f'f1-{w}-{k}', w, k) for w in ('lock', 'corpus') for k in ('STOP', 'deadline')}
    # a STOP after the resume renames: the in-launch gate refuses and the attempt state is restored (no spawn)
    drv, job, spawned = r6_driver('f1-resume')
    out = job/'fits'/'R5'; out.mkdir(parents=True, exist_ok=True)
    wjson(out/'complete.json', dict(stopped=True, step=250)); wjson(out/'segment.json', dict(status='returned')); (out/'step-00000250.pt').write_bytes(b'ck')
    wjson(job/'receipts'/'fit-R5-launch.json', dict(launch_id='OLD', pid=2**22+3, pgid=2**22+3, starttime=1))
    drv.fit_state = lambda f: ('pending', None); drv.prepare_fit_dirs = lambda fid: (['batch-0000'], 'g'*64)
    real_rename = io.rename_path
    def rn(src, dst, roles=None):
        real_rename(src, dst, roles=roles)
        if '/fit-R5-launch-' in dst: stop_link(job)
    drv.io.rename_path = rn
    r = attempt(lambda: drv.Fits().launch('R5', 'stopped'))
    rollback = (r != 'SPAWNED' and not spawned and (out/'segment.json').exists() and (out/'complete.json').exists()
                and (job/'receipts'/'fit-R5-launch.json').exists() and not list(out.glob('*-attempt*')) and not list((job/'receipts').glob('fit-R5-launch-*')))
    case("R5-F1 (Sol): a fit launch crossing STOP or the hard stop while it waits for DISPATCH.lock or re-verifies the corpus never "
         "reaches a child; a STOP after the resume renames is refused inside launch() and the attempt state is restored",
         all(fits_cross.values()) and rollback, fits=fits_cross, rollback=rollback)

    def phase_case(sub, where, kind):
        drv, job, spawned = r6_driver(sub)
        (job/'REPORTING.GO').write_text('go'); drv.live_supervisor = lambda: None
        drv.next_phase = lambda: ('R3a', 'K4S-120', [0, 1]); drv.fit_state = lambda f: ('done', None)
        inv = {}
        for rel in drv.RUNTIME_FILES:
            f = job/'rt-R3a'/'repo'/rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(rel); inv[rel] = sha(f)
        wjson(job/'RUNTIME-INVENTORY.json', inv); (job/'games'/'R3a'/'K4S-120').mkdir(parents=True)
        cross = (lambda: stop_link(job)) if kind == 'STOP' else (lambda: setattr(drv, 'STOP_AT', past))
        lock_hook(drv, cross if where == 'lock' else (lambda: None))
        real_ok = drv.resources_ok
        drv.resources_ok = (lambda for_fit=False: (cross(), real_ok(for_fit))[1]) if where == 'resources' else real_ok
        r = attempt(drv.games_tick)
        return r != 'SPAWNED' and not spawned and not list((job/'games'/'R3a'/'K4S-120').glob('indices-*')) and bool(refused(job))
    phase_cross = {f'{w}/{k}': phase_case(f'p1-{w}-{k}', w, k) for w in ('lock', 'resources') for k in ('STOP', 'deadline')}
    case("R5-F1 (Sol): a reporting launch crossing STOP or the hard stop while it waits for DISPATCH.lock or for resource admission is "
         "refused at the final gate: no indices file, no supervisor child", all(phase_case_v for phase_case_v in phase_cross.values()), phases=phase_cross)

    def cal_case(sub, kind):
        drv, job, spawned = r6_driver(sub); (job/'calibration').mkdir(exist_ok=True)
        drv.live_supervisor = lambda: None; drv.fit_state = lambda f: ('done', None)
        cross = (lambda: stop_link(job)) if kind == 'STOP' else (lambda: setattr(drv, 'STOP_AT', past))
        real_ok = drv.resources_ok
        drv.resources_ok = lambda for_fit=False: (cross(), real_ok(for_fit))[1]
        r = attempt(lambda: drv.run_calibration('R5', str(job/'inputs'/'R5.pt'), str(job/'calibration'/'R5.json')))
        return r == 'not_admitted' and not spawned
    cal_cross = {k: cal_case(f'c1-{k}', k) for k in ('STOP', 'deadline')}
    # post-return STOP control (Sol): the calibrator creates STOP, writes its output and exits 0 between two parent polls
    drv, job = driver_module(tmp/'c1-post'); (job/'calibration').mkdir(exist_ok=True); cal = f'{job}/calibration/R5.json'
    drv.resources_ok = lambda for_fit=False: True; drv.CALIBRATION_POLL = 0.2; drv.calibration_breach = lambda rec: None
    drv.live_supervisor = lambda: None; drv.fit_state = lambda f: ('done', None)
    def fake_launch(name, argv, log, receipt, env, cwd=None, extra_rec=None):
        child = io.spawn(['/bin/sh', '-c', f'ln -s nowhere {job}/STOP; echo {{}} > {cal}'], log, dict(PATH='/usr/bin:/bin'))
        drv.POPEN[child['pid']] = child['popen']; drv.LAUNCHED[child['pid']] = 'POST'
        return dict(launch_id='POST', pid=child['pid'], pgid=child['pgid'], starttime=child['starttime'])
    drv.launch = fake_launch
    post = drv.run_calibration('R5', 'x', cal)
    post_ok = (post == 'stopped' and not os.path.exists(cal) and list((job/'calibration').glob('R5.json.rejected-*'))
               and not list((job/'receipts').glob('calibration-R5-accepted-*')))
    # READY is never published after STOP, even with an accepted calibration in hand
    def ready_case(sub, stop):
        drv, job = driver_module(tmp/sub)
        drv.fit_state = lambda f: ('done', None) if f == 'R5' else ('pending', None)
        ck = job/'fits'/'R5'/'step-00002500.pt'; ck.parent.mkdir(parents=True, exist_ok=True); ck.write_bytes(b'checkpoint')
        pj = job/'base'/'repo'/'reports'/'explore'/'x4s3'/'plan.json'; pj.parent.mkdir(parents=True); wjson(pj, {})
        def fake_cal(fid, dest, cal):
            wjson(cal, dict(checkpoint_sha256=sha(dest), threshold=0.5))
            wjson(job/'receipts'/f'calibration-{fid}-accepted-X.json', dict(launch_id='X', calibration_sha256=sha(cal)))
            if stop: stop_link(job)
            return 'ok'
        drv.run_calibration = fake_cal; drv.prepare_students()
        return (job/'rt-R5'/'READY.json').exists()
    ready_stop, ready_ok = ready_case('c1-ready-stop', True), ready_case('c1-ready-ok', False)
    case("R5-F1 (Sol): calibration admission crossing STOP or the hard stop during resource admission never reaches a child; a "
         "calibrator that creates STOP and exits 0 between polls is rejected (stopped, output set aside, no acceptance); READY is not "
         "published after STOP (control: published without STOP)",
         all(cal_cross.values()) and bool(post_ok) and not ready_stop and ready_ok, cal=cal_cross, post=post, ready=[ready_stop, ready_ok])
    sup_src = (HERE/'supervise.py').read_text()
    sup = load_fresh('supervise_r6', HERE/'supervise.py'); sj = new_job(tmp/'s1')
    future = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
    healthy = sup.final_check(str(sj), future); stop_link(sj); st_ = sup.final_check(str(sj), future); (sj/'STOP').unlink()
    dl = sup.final_check(str(sj), past)
    order = (sup_src.index('admit_phase(job, workers*width+3, stop_at)') < sup_src.index('census_cpu = ForeignCensus(job)')
             < sup_src.index('late = final_check(job, stop_at)') < sup_src.index('child = io.spawn(cmd'))
    case('R5-F1 (Sol): the supervisor repeats the STOP/deadline check after admission and the census, immediately before io.spawn',
         healthy is None and 'STOP' in (st_ or '') and 'hard stop' in (dl or '') and order)

    # ---- R5-F2: calibration is owned, counted and excluding study work; a restarted driver reconciles a live old one
    import diagnose
    drv, job, spawned = r6_driver('c2')
    old = io.spawn(['/bin/sleep', '60'], f'{job}/logs/old-cal.log', dict(PATH='/usr/bin:/bin'))
    try:
        wjson(job/'receipts'/'calibrate-R5-launch-100.json', dict(launch_id='OLD', pid=old['pid'], pgid=old['pgid'], starttime=old['starttime'], name='calibrate-R5'))
        (job/'calibration').mkdir(exist_ok=True); wjson(job/'calibration'/'R5.json', dict(partial=True))
        census = (old['pgid'], old['starttime']) in ST.groups(str(job)) and old['pid'] in ST.processes(ST.groups(str(job)))
        diag_live = any('calibrate-R5' in n for n in diagnose.live_study_work(str(job)))
        diag_refused = raises(lambda: diagnose.acquire_lock(str(job)), SystemExit, 'calibration') and not (job/'driver'/'DIAGNOSTIC.lock').exists()
        drv.live_supervisor = lambda: None; drv.fit_state = lambda f: ('pending', None)
        excl = dict(resources=drv.resources_ok(for_fit=True) is False, final_gate=drv.final_gate() == 'calibration live',
                    second_calibration=attempt(lambda: drv.run_calibration('R5', 'x', str(job/'calibration'/'R6.json'))) == 'not_admitted')
        wjson(job/'data'/'O-VERIFIED.json', {}); drv.prepare_fit_dirs = lambda fid: (['batch-0000'], 'g'*64)
        excl['fit'] = attempt(lambda: drv.Fits().tick()) != 'SPAWNED'
        excl['no_spawn'] = not spawned
        found = drv.reconcile_calibrations()
        try: old['popen'].wait(timeout=30)
        except subprocess.TimeoutExpired: found = False                # not stopped: the reconciliation failed
        recon = (found and not io.group_alive(old['pgid'], old['starttime']) and (job/'receipts'/'calibration-R5-orphan-OLD.json').exists()
                 and not (job/'calibration'/'R5.json').exists() and list((job/'calibration').glob('R5.json.orphaned-*'))
                 and drv.reconcile_calibrations() is False)
    finally:
        if old['popen'].poll() is None: io.stop_owned(old['pgid'], old['starttime'], term_grace=5, kill_grace=5); old['popen'].wait()
    # the other direction: a live diagnostic lock excludes calibration
    drv2, job2, spawned2 = r6_driver('c2-diag'); drv2.live_supervisor = lambda: None; drv2.fit_state = lambda f: ('pending', None)
    me = io.own_identity(); wjson(job2/'driver'/'DIAGNOSTIC.lock', dict(pid=me['pid'], starttime=me['starttime']))
    diag_excl = attempt(lambda: drv2.run_calibration('R5', 'x', str(job2/'calibration'/'R5.json'))) == 'not_admitted' and not spawned2
    # an output without an acceptance receipt (an earlier incarnation's unknown exit) is set aside, never used
    drv3, job3 = driver_module(tmp/'c2-unacc'); (job3/'calibration').mkdir(exist_ok=True); wjson(job3/'calibration'/'R5.json', dict(threshold=0.5))
    drv3.reconcile_calibrations(); unacc = not (job3/'calibration'/'R5.json').exists()
    main_src = (HERE/'driver.py').read_text()
    gated = main_src.index('if not reconcile_calibrations():') < main_src.index('fits.tick(); prepare_students(); games_tick()')
    case("R5-F2 (Sol): a live calibration group is in studytree.groups and the process census, refuses the diagnostic lock, and "
         "blocks fit/calibration admission and the final gate; a live diagnostic blocks calibration; a restarted driver stops the "
         "old calibration by verified PID, sets its output aside and records the disposition before any other dispatch; an "
         "unaccepted output is set aside", census and diag_live and diag_refused and all(excl.values()) and bool(recon) and diag_excl
         and unacc and gated, excl=excl, census=census, diag=[diag_live, diag_refused], recon=bool(recon), diag_excl=diag_excl)

    # ---- R5-F4: two resumed attempts with unknown exits, each reconciled by its own ACK
    drv, job = driver_module(tmp/'f4'); out = job/'fits'/'R5'; out.mkdir(parents=True, exist_ok=True)
    rp = job/'receipts'/'fit-R5-launch.json'
    def fs():
        try: return drv.fit_state('R5')[0]
        except io.Refusal as e: return 'refused: '+str(e)[-60:]          # Sol's r5 failure mode
    def attempt_files(lid, pid):
        wjson(out/'complete.json', dict(stopped=True, step=250)); wjson(out/'segment.json', dict(status='returned'))
        rec = dict(pid=pid, pgid=pid, starttime=7, launch_id=lid, launched_at_utc='2026-10-13T00:00:00Z'); wjson(rp, rec); return rec
    def ack(rec, receipt): wjson(job/'driver'/'ACK-fit-R5-exit.json', dict(launch_id=rec['launch_id'], pid=rec['pid'], starttime=rec['starttime'],
                                                                           receipt_sha256=sha(receipt), disposition='success', owner='sam'))
    r1 = attempt_files('A1', 2**22+501)
    s1_before = fs(); ack(r1, rp); s1 = fs()
    first = s1_before == 'failed' and s1 == 'stopped' and (job/'receipts'/'fit-R5-exit-resolution-A1.json').exists() and not (job/'driver'/'ACK-fit-R5-exit.json').exists()
    os.rename(out/'segment.json', out/'segment-attempt1.json'); os.rename(out/'complete.json', out/'complete-attempt1.json')
    os.rename(rp, job/'receipts'/'fit-R5-launch-1.json')
    r2 = attempt_files('A2', 2**22+502)
    s2_before = fs()                                   # the first resolution does not authorize the second
    ack(r1, job/'receipts'/'fit-R5-launch-1.json'); s2_stale = fs()
    stale = s2_stale == 'failed' and (job/'driver'/'ANOMALY-stale-ack-fit-R5-exit.json').exists()
    (job/'driver'/'ACK-fit-R5-exit.json').unlink(); ack(r2, rp); s2 = fs()
    second = (s2_before == 'failed' and s2 == 'stopped' and (job/'receipts'/'fit-R5-exit-resolution-A2.json').exists()
              and json.loads((job/'receipts'/'fit-R5-exit-resolution-A1.json').read_text())['launch_id'] == 'A1'
              and len(list((job/'driver').glob('ACK-fit-R5-exit.consumed-*.json'))) == 2)
    case("R5-F4 (Sol): a second resumed attempt with an unknown exit is reconciled by its own exact-attempt ACK into a launch-specific "
         "resolution; the first resolution neither authorizes nor obstructs it, a first-attempt ACK is stale, both ACKs are kept consumed",
         first and stale and second, got=[s1_before, s1, s2_before, s2_stale, s2])

    # ---- R5-F3: case-level schedule/proof binding, clean-exit coverage, typed exit status (Sol's four cases + controls)
    import qualify4 as Q
    job = new_job(tmp/'q'); base = job/'collect'
    def ph(name, arm, idx):
        p = base/name
        for i in idx:
            g = write_game(p, arm, i, C, hit=642 if arm == 'K4S-120' else 753, n=1000, sd=223 if arm == 'K4S-120' else 0)
            wjson(p/'blocks'/f'{i:04d}.json', dict(index=i, seed=C+i, order=[arm], games={g.name: sha(g)}))
        return p
    def run_parity(phases, name):
        out = job/'receipts'/f'{name}.json'
        try: Q.main(['parity', '--phases', *map(str, phases), '--min-games', '3', '--out', str(out)]); rc = 0
        except SystemExit as e: rc = e.code
        return rc, json.loads(out.read_text())
    def probe(name, edit):
        a, b = ph(name+'-k', 'K4S-120', (0, 1, 2)), ph(name+'-s', 'S-200', (2000, 2001, 2002))
        finish_phase(a); finish_phase(b); edit(a, b); return run_parity([a, b], name)
    sol = dict(
        scheduled4_proved3_clean=probe('c4', lambda a, b: finish_phase(a, indices=[0, 1, 2, 3], reason=None, rc=0)),
        reason_only_exit=probe('ro', lambda a, b: wjson(a/'supervisor-exit.json', dict(reason='memory_guard'))),
        permitted_reason_rc17=probe('r17', lambda a, b: finish_phase(a, reason='memory_guard', rc=17)),
        k4s_schedule_s200_proofs=(lambda: (lambda x, y: (finish_phase(x), finish_phase(y, 'K4S-120'), run_parity([x, y], 'xs'))[2])(
            ph('xs-k', 'K4S-120', (0, 1, 2)), ph('xs-s', 'S-200', (3500, 3501, 3502))))(),
        duplicate_case=probe('dc', lambda a, b: wjson(a/'schedule.json', dict(json.loads((a/'schedule.json').read_text()),
                                                       cases=[[0, C, 'K4S-120'], [0, C, 'K4S-120'], [1, C+1, 'K4S-120'], [2, C+2, 'K4S-120']]))),
        proof_game_not_scheduled=probe('pg', lambda a, b: wjson(a/'blocks'/'0000.json', dict(json.loads((a/'blocks'/'0000.json').read_text()),
                                                            games={'sim-0000-d27-K4S-120.json': sha(a/'games'/'sim-0000-d27-K4S-120.json'), 'sim-0000-d27-S-200.json': '0'*64}))),
        exit_without_pid_list=probe('np', lambda a, b: wjson(a/'supervisor-exit.json', dict(reason=None, returncode=0))),
        unknown_returncode=probe('ur', lambda a, b: wjson(a/'supervisor-exit.json', dict(reason=None, returncode=None, remaining_group_pids=[]))))
    def interrupted(a, b):
        finish_phase(a, indices=[0, 1, 2, 3], reason='memory_guard', rc=-15)
    ok_int = probe('oi', interrupted)
    healthy = probe('hc', lambda a, b: None)
    ev_int = sorted((e['status'], e['dropped']) for e in ok_int[1].get('evidence', {}).values())
    case("R5-F3 (Sol): parity refuses a clean exit with 4 scheduled / 3 proved, a reason-only exit, a permitted reason beside "
         "returncode 17, a K4S schedule whose proofs are S-200 cases, a duplicate case, a proof naming an unscheduled game, an exit "
         "without its process list and an unknown returncode; a SIGTERM guard interruption passes with its dropped case recorded; "
         "the complete healthy control passes",
         all(v[0] == 1 and v[1]['passed'] is False for v in sol.values()) and ok_int[0] == 0 and ev_int == [('clean', 0), ('interrupted', 1)]
         and healthy[0] == 0, errors={k: v[1].get('error', '')[-70:] for k, v in sol.items()}, interrupted=ev_int)
    import label
    good_k, good_s = base/'hc-k', base/'hc-s'
    pr = job/'receipts'/'hc.json'; bless(pr)                       # r8: what the guarded parity run records
    adm_ok = label.check_parity([str(good_k), str(good_s)], str(pr))[0]['passed'] is True
    finish_phase(good_k, indices=[0, 1, 2, 3], reason=None, rc=0)                # evidence changed after the receipt
    adm_bad = raises(lambda: label.check_parity([str(good_k), str(good_s)], str(pr)), label.PlanError, 'evidence')
    case("R5-F3: label admission re-derives the strengthened evidence: the healthy receipt is admitted; after the schedule is widened "
         "to an uncovered clean case the same receipt is refused", adm_ok and adm_bad)

    # ---- Q-D2(a): smoke-pack labels, seals and packs the smoke collection into <job>/qual/smoke-pack/batch-0000
    stub_torch_imports()
    from imitation.exit_r1 import pack as packmod
    def smoke_job(sub):
        j = new_job(tmp/sub); phases = []
        for arm in Q.COLLECT_ARMS:
            p = j/'collect'/'smoke'/arm; phases.append(p)
            for i in range(8): write_collect_game(p, arm, i, (100, 110, 120), base=SMOKE)
            wjson(p/'schedule.json', dict(range='smoke', indices=list(range(8)), cases=[[i, SMOKE+i, arm] for i in range(8)]))
        return j, [str(p) for p in phases]
    saved = (label.score_state, label.THREADS, label.RAW, label.PLAN_SHA, label.DATA_ROLE)
    try:
        label.score_state = lambda *a, **k: (5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None]); label.THREADS = 1
        sj, phases = smoke_job('sp')
        body = Q.smoke_pack_into(phases, label, packmod.pack)
        batch = sj/'qual'/'smoke-pack'/'batch-0000'
        sealed_ok = body['passed'] and batch.is_dir() and io.verify_sealed_dir(str(batch))[1] == body['packed_manifest_sha256']
        shape = (body['games'] == 16 and body['statuses'] == {'sealed': 16} and body['rows'] == 48 and body['captures'] == 48
                 and str(batch).startswith(io.JOB+'/qual/') and readonly(sj/'qual'/'smoke-plan.json')
                 and not list((sj/'data').iterdir()))
        label.DATA_ROLE = 'data'
        again = raises(lambda: Q.smoke_pack_into(phases, label, packmod.pack), io.Refusal, 'exists')
        label.DATA_ROLE = 'data'
        sj2, phases2 = smoke_job('sp-stop'); stop_link(sj2)
        stopped = Q.smoke_pack_into(phases2, label, packmod.pack)
        stop_ok = stopped['passed'] is False and not (sj2/'qual'/'smoke-pack').exists() and 'stopped' in stopped['statuses']
        label.DATA_ROLE = 'data'
        sj3, phases3 = smoke_job('sp-forged')
        (Path(phases3[0])/'games'/'sim-0003-d27-K4S-120.json').write_text('{"forged": 1}')
        forged = raises(lambda: Q.smoke_pack_into(phases3, label, packmod.pack), Q.QualError, 'block proof') and not (sj3/'qual'/'smoke-plan.json').exists()
    finally:
        label.score_state, label.THREADS, label.RAW, label.PLAN_SHA, label.DATA_ROLE = saved
    q_src = (HERE/'qualify4.py').read_text()
    case("Q-D2(a) smoke-pack: all 16 authenticated smoke games (48 captures) are labelled by the unchanged label_game under <job>/qual, "
         "sealed and packed once by the frozen pack() into a seal-verified <job>/qual/smoke-pack/batch-0000 that the trainer check "
         "accepts by location; nothing is written under <job>/data; a rerun refuses (no overwrite), STOP halts labelling with no pack, "
         "and a forged smoke game is refused before any write",
         sealed_ok and shape and again and stop_ok and forged and "'smoke-pack': smoke_pack" in q_src,
         body={k: body.get(k) for k in ('games', 'statuses', 'rows', 'captures', 'passed')}, stop=stopped.get('statuses'))


# ================================================================ r7: Sol r6 findings R6-F1..F3
@healthy_host
def test_r7(tmp):
    import studytree as ST, qualify4 as Q, label
    stub_torch_imports()
    from imitation.exit_r1 import pack as packmod
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    def stop_link(job):
        if not os.path.lexists(Path(job)/'STOP'): os.symlink(Path(job)/'nowhere', Path(job)/'STOP')

    # ---- R6-F1: STOP / deadline crossing during the final gate's own events-log scan never reaches io.spawn
    def gate_case(sub, kind):
        drv, job = driver_module(tmp/sub)
        out = job/'fits'/'R5'; out.mkdir(parents=True, exist_ok=True)
        wjson(out/'complete.json', dict(stopped=False, step=2500)); wjson(out/'segment.json', dict(status='returned'))
        os.utime(out/'complete.json', (time.time()-100, time.time()-100))   # completed well before the STOP (H-1)
        rec = dict(launch_id='DONE', pid=2**22+77, pgid=2**22+77, starttime=5, launched_at_utc='2026-10-13T00:00:00Z')
        wjson(job/'receipts'/'fit-R5-launch.json', rec)
        with (job/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='x', kind='child_exit', pid=rec['pid'], launch_id='DONE', exit_code=0))+'\n')
        spawned = []
        ns = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')})
        def spy(argv, *a, **k): spawned.append(argv); raise RuntimeError('spawn reached')
        def slow_read(path, *a, **k):
            text = io.read_text(path, *a, **k)
            if str(path).endswith('/events.jsonl'):                     # the gate's own exit-log scan
                if kind == 'STOP': stop_link(job)
                else: drv.STOP_AT = past
            return text
        ns.spawn, ns.read_text = spy, slow_read; drv.io = ns
        drv.live_supervisor = lambda: None
        try: r = drv.launch('fit-R5-rep', ['/bin/true'], f'{job}/logs/x.log', f'{job}/receipts/x.json', {})
        except RuntimeError as e: r = 'SPAWNED' if 'spawn reached' in str(e) else repr(e)
        return r is None and not spawned and drv.fit_state('R5')[0] == 'done'
    g = {k: gate_case(f'g-{k}', k) for k in ('STOP', 'deadline')}
    src = (HERE/'driver.py').read_text(); fg = src[src.index('def final_gate():'):src.index('def launch(')]
    order = fg.index("fit_state(f)[0] == 'running'") < fg.index('if stop_present()') < fg.index('if now() >= STOP_AT')
    case("R6-F1 (Sol): STOP or the hard stop crossing during the final gate's own events-log/fit-status scan is caught: launch() "
         "returns None and io.spawn is never reached; the cheap checks are statically last", all(g.values()) and order, gate=g, order=order)

    # ---- R6-F2 (child side since r8): STOP/deadline/breach halts every qualification item; a receipt never passes after one
    def guard_for(job, name, out='g.json'):
        return Q.QualGuard(str(job), name, str(Path(job)/'qual'/out))
    def smoke_job(sub):
        j = new_job(tmp/sub); phases = []
        for arm in Q.COLLECT_ARMS:
            p = j/'collect'/'smoke'/arm; phases.append(p)
            for i in range(8): write_collect_game(p, arm, i, (100, 110, 120), base=SMOKE)
            wjson(p/'schedule.json', dict(range='smoke', indices=list(range(8)), cases=[[i, SMOKE+i, arm] for i in range(8)]))
        return j, [str(p) for p in phases]
    saved = (label.score_state, label.THREADS, label.RAW, label.PLAN_SHA, label.DATA_ROLE, label.halt_reason)
    def restore(): label.score_state, label.THREADS, label.RAW, label.PLAN_SHA, label.DATA_ROLE, label.halt_reason = saved
    ok_score = (5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None])
    batch = lambda j: Path(j)/'qual'/'smoke-pack'/'batch-0000'
    def run_smoke(sub, fire_at=None, fire=None, pk=None):
        j, phases = smoke_job(sub); calls = []
        def score(*a, **k):
            calls.append(1)
            if fire_at is not None and len(calls) == fire_at: fire(j)
            return ok_score
        Q.GUARD = guard_for(j, 'smoke-pack'); label.score_state, label.THREADS = score, 1
        try:
            try: out = Q.smoke_pack_into(phases, label, pk(j) if pk else packmod.pack)
            except Q.QualHalt as e: out = 'halt: '+str(e)
        finally: Q.GUARD = None; restore()
        return out, j, calls
    def sealed(j):
        if not batch(j).exists(): return False
        try: io.verify_sealed_dir(str(batch(j))); return True
        except io.Refusal: return False
    res = {}
    for kind, fire in (('STOP', stop_link), ('deadline', lambda j: (Path(j)/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n'))):
        out, j, calls = run_smoke(f'r7-late-{kind}', 48, fire)
        res[f'late_score_{kind}'] = isinstance(out, str) and out.startswith('halt') and len(calls) == 48 and not batch(j).exists()
    def pack_with(when):
        def make(j):
            def pk(roots, output, memory_guard=None):
                n = []
                def mg():
                    n.append(1)
                    if when == 'in_pack' and len(n) == 3: stop_link(j)
                    memory_guard()
                r = packmod.pack(roots, output, memory_guard=mg)
                if when == 'after_pack': stop_link(j)
                return r
            return pk
        return make
    for when in ('in_pack', 'after_pack'):
        out, j, _ = run_smoke(f'r7-{when}', pk=pack_with(when))
        res[when] = isinstance(out, str) and out.startswith('halt') and (when == 'after_pack' or not sealed(j))
    # the round-trip loop halts at the next capture after STOP (Sol r6: 96 scoring calls, passed, exit 0)
    j, _ = smoke_job('r7-rt'); Q.GUARD = guard_for(j, 'roundtrip', 'g4.json'); calls = []
    def rscore(*a):
        calls.append(1); stop_link(j); return (5, [5], [0.1])
    caps = [dict(info=None, opponent=None, root_rng_state=None, candidate_rng_state=None, seed=0, root_digest=None) for _ in range(48)]
    try: rt_halt = raises(lambda: Q.roundtrip_check(caps, rscore), Q.QualHalt, 'owned_STOP')
    finally: Q.GUARD = None
    res['roundtrip_halts'] = rt_halt and len(calls) == 2
    # finalize: a result computed as passed is written passed=false under STOP / the deadline
    fin = guard_for(j, 'roundtrip', 'g4.json').finalize(dict(passed=True, check='roundtrip'))
    res['finalize_STOP'] = fin['passed'] is False and json.loads((j/'qual'/'g4.json').read_text())['passed'] is False
    (j/'STOP').unlink(); (j/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
    res['finalize_deadline'] = guard_for(j, 'hashes', 'g5.json').finalize(dict(passed=True))['passed'] is False
    (j/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    # CLI: the real main() halts before any work with STOP present and writes a failed receipt (exit 1)
    stop_link(j)
    try: Q.main(['parity', '--phases', str(j/'collect'/'smoke'/'K4S-120'), '--min-games', '1', '--bank', 'smoke', '--out', str(j/'qual'/'cli.json')]); rc = 0
    except SystemExit as e: rc = e.code
    cli = json.loads((j/'qual'/'cli.json').read_text())
    res['cli_STOP'] = rc == 1 and cli['passed'] is False and 'owned_STOP' in cli['error']
    (j/'STOP').unlink()
    case("R6-F2 (Sol, child side): a STOP or the deadline at the last (48th) score, a STOP inside the frozen packer and a STOP right "
         "after it all halt smoke-pack with no accepted batch; the round-trip loop halts at the next capture; finalize writes "
         "passed=false under STOP or the deadline; the real CLI halts before any work under STOP", all(res.values()), res=res)

    # ---- R6-F3: digest failures fail smoke-pack; legitimate no-scored-root games are allowed
    def drops_case(sub, score):
        j, phases = smoke_job(sub); label.score_state, label.THREADS = score, 1
        try: return Q.smoke_pack_into(phases, label, packmod.pack), j
        finally: restore()
    ok_score = (5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None])
    def by_seed(bad_seed, kind, only_tick=None):
        def score(info, opponent, rrs, crs, seed, digest=None):
            tick = int(str(digest).rsplit('-', 1)[1]) if digest else None
            if seed == bad_seed and (only_tick is None or tick == only_tick):
                if kind == 'digest': raise label.DigestMismatch('root digest mismatch')
                return 5, [5], [0.3]                                        # one candidate: no scored root
            return ok_score
        return score
    d1, j1 = drops_case('r7-digest-only', by_seed(SMOKE+7, 'digest'))       # all roots of one game (both arms' index 7)
    d2, j2 = drops_case('r7-digest-mixed', by_seed(SMOKE+3, 'digest', only_tick=110))
    h1, j3 = drops_case('r7-noroot-game', by_seed(SMOKE+5, 'noroot'))
    h2, j4 = drops_case('r7-noroot-mixed', by_seed(SMOKE+2, 'noroot', only_tick=120))
    f3 = dict(digest_only=d1['passed'] is False and 'digest' in d1.get('error', '') and not batch(j1).exists(),
              digest_mixed=d2['passed'] is False and 'digest' in d2.get('error', '') and not batch(j2).exists(),
              noroot_game=h1['passed'] is True and h1['statuses'].get('no_rows') == 2 and h1['drops'] == {'no_scored_root': 6}
                          and h1['attempted'] == 48 and h1['rows'] == 42,
              noroot_mixed=h2['passed'] is True and h2['drops'] == {'no_scored_root': 2} and h2['rows'] == 46 and h2['attempted'] == 48)
    case("R6-F3 (Sol): smoke-pack fails on digest mismatches - a game whose roots all fail (no_rows) and a single failed root in a "
         "sealed game - with no packed batch; legitimate no-scored-root games and roots pass with complete attempted/row/drop accounting",
         all(f3.values()), f3=f3, d1=d1.get('error'), h1={k: h1.get(k) for k in ('statuses', 'drops', 'rows', 'attempted', 'error')})


# ================================================================ r8: Sol r7 R7-F1..F3 - the guard audit, one case per row
class FastGuards:
    """Shrinks only the guard timing constants (tick/period/stale/measurement deadline) and stubs healthy host readings;
    restores everything on exit. The mechanisms under test are unchanged."""
    def __enter__(self):
        import studytree as ST
        self.ST = ST
        self.saved = {k: getattr(ST, k) for k in ('ENFORCER_TICK', 'MONITOR_PERIOD', 'MONITOR_STALE', 'MEASURE_TIMEOUT',
                                                 'mem_available', 'psi_some_avg10', 'disk_bytes', 'pss_bytes')}
        ST.ENFORCER_TICK, ST.MONITOR_PERIOD, ST.MONITOR_STALE, ST.MEASURE_TIMEOUT = 0.05, 0.05, 0.6, 0.5
        ST.mem_available, ST.psi_some_avg10, ST.disk_bytes = (lambda: 100*2**30), (lambda: 1.0), (lambda j=None: 10**9)
        return ST
    def __exit__(self, *e):
        for k, v in self.saved.items(): setattr(self.ST, k, v)
        return False


def test_r8(tmp):
    import guard as G, threading
    def stop_link(job):
        if not os.path.lexists(Path(job)/'STOP'): os.symlink(Path(job)/'nowhere', Path(job)/'STOP')
    def mk(sub):
        j = new_job(tmp/sub); return j
    def runner(j, name, argv, **kw):
        r = G.Runner(str(j), name, argv, **kw); exits = []; r.exit = exits.append; return r, exits
    def receipt(j, name): return json.loads((Path(j)/'receipts'/f'guard-{name}.json').read_text())
    def gone(r): return r.child is not None and not io.group_alive(r.child['pgid'], r.child['starttime'])
    def spawn_spy(r):
        calls = []; real = io.spawn
        def spy(*a, **k): calls.append(a[0]); return real(*a, **k)
        G.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')}); G.io.spawn = spy
        return calls
    rows = {}

    # ---- row 1: guard.py runner - admission (bounded, STOP/deadline LAST before spawn)
    with FastGuards() as ST:
        adm = {}
        for kind in ('STOP', 'deadline', 'psi_11', 'blocked_measurement', 'stop_during_measurement'):
            j = mk(f'g1-{kind}'); r, exits = runner(j, 'adm', ['/bin/sleep', '30']); calls = spawn_spy(r)
            if kind == 'STOP': stop_link(j)
            if kind == 'deadline': (j/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
            if kind == 'psi_11': ST.psi_some_avg10 = lambda: 11.0
            gate = threading.Event()
            if kind == 'blocked_measurement': ST.disk_bytes = lambda j_=None: (gate.wait(5), 10**9)[1]
            if kind == 'stop_during_measurement': ST.disk_bytes = lambda j_=None, j=j: (stop_link(j), 10**9)[1]
            try: body = r.run()
            finally: gate.set(); G.io = io; ST.psi_some_avg10 = lambda: 1.0; ST.disk_bytes = lambda j_=None: 10**9
            adm[kind] = body is not None and body['passed'] is False and 'admission' in body['error'] and not calls and exits == [3]
        rows['runner_admission'] = adm
        # live monitor + independent expiry: the monitor is BLOCKED in a measurement when STOP / the deadline appears,
        # or simply stays blocked (no completed verdict -> monitor_stale); the child is stopped by verified PIDs
        live = {}
        for kind in ('STOP_while_blocked', 'deadline_while_blocked', 'stale_while_blocked', 'memory_breach'):
            j = mk(f'g1-live-{kind}'); r, exits = runner(j, 'live', ['/bin/sleep', '30'])
            gate, entered = threading.Event(), threading.Event()
            n = []
            def disk(j_=None, gate=gate, entered=entered, n=n):
                n.append(1)
                if len(n) > 1: entered.set(); gate.wait(20)               # admission passes; the live monitor blocks
                return 10**9
            if kind != 'memory_breach': ST.disk_bytes = disk
            def trigger(j=j, kind=kind, entered=entered):
                if kind == 'memory_breach':
                    time.sleep(0.2); ST.mem_available = lambda: 0; return
                entered.wait(5)
                if kind == 'STOP_while_blocked': stop_link(j)
                if kind == 'deadline_while_blocked': (j/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
            t = threading.Thread(target=trigger, daemon=True); t.start()
            t0 = time.monotonic()
            try: r.run()
            finally: gate.set(); ST.disk_bytes = lambda j_=None: 10**9; ST.mem_available = lambda: 100*2**30
            el = time.monotonic()-t0; rc_ = receipt(j, 'live')
            want = {'STOP_while_blocked': 'owned_STOP', 'deadline_while_blocked': 'hard_stop_time', 'stale_while_blocked': 'monitor_stale',
                    'memory_breach': 'memory_guard'}[kind]
            live[kind] = rc_['passed'] is False and rc_['breach'] == want and gone(r) and el < 10 and exits and exits[0] == 3
        rows['runner_live_expiry'] = live
        # acceptance: fresh guards after the child exits 0; STOP/deadline LAST; outputs verified
        acc = {}
        def accept_case(kind):
            j = mk(f'g1-acc-{kind}'); out = j/'qual'/'out.json'
            cmd = ['/bin/sh', '-c', f'echo {{}} > {out}' + ('; exit 7' if kind == 'nonzero' else '')]
            if kind == 'missing_output': cmd = ['/bin/true']
            r, exits = runner(j, 'acc', cmd, outputs=[str(out)], new_files=[str(j/'qual'/'new-')])
            real_wait = None
            if kind in ('memory_at_end', 'stop_at_end'):
                orig = r.run
                def hooked_spawn(*a, **k):
                    ch = io.spawn(*a, **k); real = ch['popen'].wait
                    def w(*aa, **kk):
                        rc = real(*aa, **kk)
                        r.done.set(); time.sleep(4*ST.MONITOR_PERIOD)   # the live monitor has finished: only acceptance sees it
                        if kind == 'memory_at_end': ST.mem_available = lambda: 0
                        else: stop_link(j)
                        return rc
                    ch['popen'].wait = w; return ch
                G.io = types.SimpleNamespace(**{k: getattr(io, k) for k in dir(io) if not k.startswith('__')}); G.io.spawn = hooked_spawn
            try: body = r.run()
            finally: G.io = io; ST.mem_available = lambda: 100*2**30
            rc_ = receipt(j, 'acc')
            if kind == 'healthy':
                return body['passed'] is True and rc_['outputs'] == {str(out): sha(out)} and rc_['returncode'] == 0 and \
                    ST.guarded_output(str(j), str(out))['name'] == 'acc'
            return rc_['passed'] is False and ST.guarded_output(str(j), str(out)) is None
        for kind in ('healthy', 'nonzero', 'missing_output', 'memory_at_end', 'stop_at_end'): acc[kind] = accept_case(kind)
        rows['runner_acceptance'] = acc
        # --readout: the deadline does not apply to the readout scripts only; STOP still refuses
        j = mk('g1-readout'); (j/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
        rr = Path(tmp)/'fakerepo'; (rr/'reports'/'explore'/'x4s3').mkdir(parents=True, exist_ok=True)
        (rr/'reports'/'explore'/'x4s3'/'runtime.sh').write_text('exit 0\n')          # r10: the exact readout invocation form
        ro_argv = ['/bin/bash', str(rr/'reports'/'explore'/'x4s3'/'runtime.sh'), str(rr/'reports'/'explore'/'x4s4'/'reduce.py')]
        r, exits = runner(j, 'ro', ro_argv, readout=True)
        ro_ok = r.run()['passed'] is True
        stop_link(j); r2, _ = runner(j, 'ro2', ro_argv, readout=True)
        ro_stop = r2.run()['passed'] is False
        rows['runner_readout'] = dict(deadline_exempt=ro_ok, stop_refuses=ro_stop,
                                      other_scripts_refused=raises(lambda: G.Runner(str(j), 'x', ['/bin/true'], readout=True), SystemExit, 'readout'))
    case("r8 guard audit row 1 - guard.py runner (Q1, Q2 hashes, Q3, Q4 round trip/parity, Q5, Q6, P3-P9 non-supervisor steps, P11, "
         "P13-P15): bounded admission refuses STOP, the deadline, PSI 11, a blocked measurement and STOP during the measurement with no "
         "spawn; with the live monitor BLOCKED in a measurement, STOP, the deadline and staleness (and a memory breach) stop the child "
         "by verified PIDs with a failed receipt; acceptance needs exit 0, the declared outputs, a fresh verdict and STOP/deadline last; "
         "--readout is deadline-exempt only for the readout scripts",
         all(all(v.values()) for v in rows.values()), rows=rows)

    # ---- row: the shared Enforcer itself (supervise.py, driver.py, guard.py) - cheap checks only, re-armable
    with FastGuards() as ST:
        j = mk('enf'); fired = []
        e = ST.Enforcer(str(j), fired.append).start()
        blocked = threading.Event()
        def stuck(): ST.disk_bytes(); blocked.wait(5)
        ST.disk_bytes = lambda j_=None: (blocked.wait(5), 1)[1]
        threading.Thread(target=lambda: ST.monitor(str(j)), daemon=True).start()          # a measurement stuck in du
        time.sleep(0.1); stop_link(j); t0 = time.monotonic()
        while not fired and time.monotonic()-t0 < 3: time.sleep(0.02)
        enf_stop = fired == ['owned_STOP']; blocked.set(); e.stop(); (j/'STOP').unlink()
        fired2 = []; e2 = ST.Enforcer(str(j), fired2.append, active=lambda: True).start()
        t0 = time.monotonic()
        while not fired2 and time.monotonic()-t0 < 3: time.sleep(0.02)
        enf_stale = fired2 == ['monitor_stale']
        e2.arm(); fired2.clear(); e2.verdict(None); time.sleep(0.2); rearm_quiet = fired2 == []
        e2.stop()
        fired3 = []; e3 = ST.Enforcer(str(j), fired3.append, active=lambda: False).start(); time.sleep(1.0); idle_quiet = fired3 == []; e3.stop()
        timeout = ST.fresh_verdict(str(j), extra=lambda: (time.sleep(2), None)[1]) == 'measurement_timeout'
    case("r8 guard audit - shared Enforcer: STOP fires within ticks while a measurement is stuck in du; no verdict for MONITOR_STALE "
         "while active fires monitor_stale; re-armed it stays quiet with fresh verdicts; inactive it never goes stale; a measurement past "
         "its deadline is a breach (fresh_verdict -> measurement_timeout)", enf_stop and enf_stale and rearm_quiet and idle_quiet and timeout,
         got=[enf_stop, enf_stale, rearm_quiet, idle_quiet, timeout])

    # ---- row: supervise.py (Q2, Q4 smoke collection, Q7, Q8, P1, P2, driver-launched reporting phases)
    sup = load_fresh('supervise_r8', HERE/'supervise.py'); src = (HERE/'supervise.py').read_text()
    with FastGuards() as ST:
        j = mk('sup'); gate = threading.Event()
        ST.disk_bytes = lambda j_=None: (gate.wait(5), 1)[1]
        blocked_adm = (sup.admit_phase(str(j), 51) or '').startswith('admission: admission measurement missed')
        gate.set(); ST.disk_bytes = lambda j_=None: 10**9
        healthy = sup.final_reason(str(j)) is None
        ST.mem_available = lambda: 0; mem_end = sup.final_reason(str(j)) == 'memory_guard'; ST.mem_available = lambda: 100*2**30
        stop_link(j); stop_end = sup.final_reason(str(j)) == 'owned_STOP'; (j/'STOP').unlink()
        maps = [sup.guard_reason(x) for x in ('owned_STOP', 'hard_stop_time', 'monitor_stale', 'study_tree_cap: 71', 'measurement_timeout', 'pss_guard', 'psi_unreadable')]
    m = src[src.index('def main():'):]
    wired = (m.index('child = io.spawn(cmd') < m.index('enforcer = studytree.Enforcer(') < m.index('while True:') < m.index('enforcer.verdict(None)')
             < m.index('enforcer.stop()') < m.index('reason = final_reason(job)') < m.index("write_json_once(out+'/supervisor-exit.json'")
             and 'with stop_lock:' in m and 'if reason is not None: break' in m)
    import qualify4 as Q
    permitted = 'monitor_stale' in Q.PERMITTED_PHASE_STOPS
    case("r8 guard audit row - supervise.py: admission is one bounded measurement (a blocked du refuses), the Enforcer is started "
         "after the spawn with a heartbeat per complete loop iteration and stops the child (thread-safe stop) on STOP, the deadline or "
         "staleness; a clean exit is recorded only after a fresh verdict (memory 0 or STOP at the end -> a declared guard reason); "
         "monitor_stale is a permitted phase stop", blocked_adm and healthy and mem_end and stop_end and wired and permitted
         and maps == ['owned_STOP', 'hard_stop_time', 'monitor_stale', 'study_tree_cap', 'monitor_stale', 'memory_guard', 'memory_guard'],
         got=dict(blocked_adm=blocked_adm, healthy=healthy, mem_end=mem_end, stop_end=stop_end, wired=wired, maps=maps))

    # ---- row: driver.py (P10/P12) - fits and calibration under the Enforcer; acceptance after fresh guards
    with FastGuards() as ST:
        drv, job = driver_module(tmp/'drv8'); events = lambda: [json.loads(l) for l in (job/'driver'/'events.jsonl').read_text().splitlines()] if (job/'driver'/'events.jsonl').exists() else []
        out = {}
        for kind in ('STOP', 'stale'):
            ch = io.spawn(['/bin/sleep', '30'], f'{job}/logs/fit-{kind}.log', dict(PATH='/usr/bin:/bin'))
            rec = dict(launch_id=f'F-{kind}', pid=ch['pid'], pgid=ch['pgid'], starttime=ch['starttime'])
            drv.ENFORCER = ST.Enforcer(drv.J, drv.on_gpu_breach, active=lambda: bool(drv.LIVE)).start()
            drv.gpu_live('fit', 'R5', rec)
            if kind == 'STOP': stop_link(job)
            t0 = time.monotonic()
            while ch['popen'].poll() is None and time.monotonic()-t0 < 10: time.sleep(0.05)
            dead = ch['popen'].poll() is not None
            ev = []
            while not ev and time.monotonic()-t0 < 10:              # the callback records after the verified-PID stop
                ev = [e for e in events() if e['kind'] == 'gpu_enforcer_stop' and e['launch_id'] == rec['launch_id']]; time.sleep(0.05)
            time.sleep(0.1); drv.ENFORCER.stop()
            out[kind] = dead and ev and ev[0]['reason'] == ('owned_STOP' if kind == 'STOP' else 'monitor_stale') and \
                ((job/'driver'/'ANOMALY-fit-R5.json').exists() == (kind == 'stale'))
            if (job/'STOP').exists() or os.path.lexists(job/'STOP'): (job/'STOP').unlink()
            if (job/'driver'/'ANOMALY-fit-R5.json').exists(): (job/'driver'/'ANOMALY-fit-R5.json').unlink()
            drv.gpu_done()
        # calibration acceptance: a calibrator that exits 0 while memory is breached at the end is rejected (fresh verdict)
        (job/'calibration').mkdir(exist_ok=True); cal = f'{job}/calibration/R5.json'
        drv.resources_ok = lambda for_fit=False: True; drv.CALIBRATION_POLL = 0.05; drv.calibration_breach = lambda rec: None
        drv.live_supervisor = lambda: None; drv.fit_state = lambda f: ('done', None); drv.ENFORCER = None
        def fake_launch(name, argv, log, receipt_, env, cwd=None, extra_rec=None):
            ch = io.spawn(['/bin/sh', '-c', f'echo {{}} > {cal}'], log, dict(PATH='/usr/bin:/bin'))
            drv.POPEN[ch['pid']] = ch['popen']; drv.LAUNCHED[ch['pid']] = 'CALM'
            return dict(launch_id='CALM', pid=ch['pid'], pgid=ch['pgid'], starttime=ch['starttime'])
        drv.launch = fake_launch
        ST.mem_available = lambda: 0                    # breached when the calibrator returns (in-flight guards stubbed healthy)
        try: cal_res = drv.run_calibration('R5', 'x', cal)
        finally: ST.mem_available = lambda: 100*2**30
        out['calibration_final_guard'] = cal_res == 'stopped' and not os.path.exists(cal) and not list((job/'receipts').glob('calibration-R5-accepted-*')) \
            and (job/'driver'/'ANOMALY-calibration-R5.json').exists()
        dsrc = (HERE/'driver.py').read_text()
        ps = dsrc[dsrc.index('def prepare_students():'):dsrc.index('# ---------------- games')]
        out['ready_after_fresh'] = ps.index('if studytree.fresh_verdict(J): return') < ps.index("io.write_json_once(rt+'/READY.json'")
        out['enforcer_in_main'] = 'ENFORCER = studytree.Enforcer(J, on_gpu_breach, active=lambda: bool(LIVE)).start()' in dsrc
    case("r8 guard audit row - driver.py: a live fit (verified trainer PID) is stopped by the Enforcer on STOP and on a stale guard "
         "(anomaly), even with the main loop not ticking; a calibration that exits 0 while memory is breached at the end is rejected by "
         "the fresh verdict (anomaly, no acceptance receipt); READY is published only after a fresh verdict", all(out.values()), got=out)

    # ---- rows: guarded acceptance by every consumer (a failed or stale guard receipt never counts)
    import studytree as ST, label, verify_onpolicy as V, write_report as wr, reduce as rdc
    j = mk('acc8'); f = wjson(j/'qual'/'x.json', dict(a=1))
    none = ST.guarded_output(str(j), str(f)) is None
    wjson(j/'receipts'/'guard-failed.json', dict(schema='x4s4.guard.v1', passed=False, outputs={str(f): sha(f)}))
    failed_no = ST.guarded_output(str(j), str(f)) is None
    bless(f); ok_ = ST.guarded_output(str(j), str(f)) is not None
    wjson(f, dict(a=2)); stale_no = ST.guarded_output(str(j), str(f)) is None
    cons = dict(none=none, failed_receipt=failed_no, passed=ok_, changed_output=stale_no)
    use_job(j)
    pr = wjson(j/'receipts'/'p.json', dict(check='parity'))
    cons['label_parity'] = raises(lambda: label.check_parity([], str(pr)), label.PlanError, 'guard receipt')
    wjson(j/'data'/'label-plan.json', {})
    cons['label_run_plan'] = raises(lambda: label.run_labels(str(j/'data'/'label-plan.json'), 'O', 1, 1), SystemExit, 'guard receipt')
    wjson(j/'data'/'O-VERIFIED.json', dict(mode='O'))
    cons['gate'] = raises(lambda: ST.authenticate_gate(str(j), 'O'), io.Refusal, 'guard receipt')
    (j/'data'/'onpolicy'/'batch-0000').mkdir(parents=True); wjson(j/'data'/'onpolicy'/'batch-0000'/'manifest.json', {})
    V.JOB = str(j)
    try: V.verify('O', str(j/'data'/'onpolicy'), json.loads((HERE/'plan.json').read_text()), [], None, None, None, {}); vb = False
    except Exception as e: vb = 'guard receipt' in str(e)
    cons['verify_batch'] = vb
    (j/'data'/'O-VERIFIED.json').chmod(0o644); (j/'data'/'O-VERIFIED.json').unlink()
    rc_ = V.main(['--mode', 'O', '--plan', str(HERE/'plan.json'), '--label-receipts', str(f)])
    vr = json.loads((j/'data'/'onpolicy'/'VERIFY-RECEIPT.json').read_text())
    cons['verify_label_receipt'] = rc_ == 1 and 'guard receipt' in vr['error']
    rx = j/'receipts'/'contention-exclusion.json'; rx.write_text('{}'); rx.chmod(0o444)
    cons['reduce_contention'] = raises(lambda: rdc.verify_freeze(str(j), sha(rx), '0'*40, str(tmp)), SystemExit, 'guard receipt')
    wjson(j/'analysis'/'results.json', {})
    saved_vf = rdc.verify_freeze; rdc.verify_freeze = lambda *a, **k: None
    try: cons['report_results'] = raises(lambda: wr.authenticate(str(j), '0'*64, '0'*40), BaseException, 'results.json has no passed guard')
    finally: rdc.verify_freeze = saved_vf
    use_job(job)
    case("r8 guard audit rows - guarded acceptance: an output counts only through a PASSED guard receipt naming its CURRENT identity "
         "(a failed receipt or a changed output never counts); label plan admission (parity receipt), label run (plan), every gate "
         "consumer (authenticate_gate), verify_onpolicy (packed batches = R7-F3's pack, label receipts), reduce (C5 receipt) and "
         "write_report (results.json; an unguarded diagnostic is rendered unavailable) refuse unguarded inputs", all(cons.values()), got=cons)

    # ---- rows: every owned long-running entry point refuses to run outside guard.py (and with a dead runner)
    saved_env = os.environ.pop('X4S4_GUARD')
    ent = {}
    try:
        def entry(name, fn, argv=None):
            if argv is not None: sys.argv = argv
            ent[name] = raises(fn, BaseException, 'guard.py')       # a mutant that runs on is recorded, not fatal
        jj = mk('ent8')
        entry('qualify4', lambda: Q.main(['parity', '--phases', str(jj), '--min-games', '1', '--out', str(jj/'qual'/'e.json')]))
        entry('label', lambda: label.main(), ['label.py', 'plan', '--phases', 'x', '--parity', 'y', '--out', str(jj/'data'/'p.json')])
        entry('verify_onpolicy', lambda: V.main(['--mode', 'O', '--plan', 'x']))
        import collect_w, diagnose, contention
        entry('collect_w', lambda: collect_w.main(), ['collect_w.py', '--checkpoint', 'x', '--count', '1', '--workers', '1'])
        entry('diagnose', lambda: diagnose.main(), ['diagnose.py'])
        entry('contention', lambda: contention.main(), ['contention.py', '--job', str(jj)])
        entry('reduce', lambda: rdc.main(), ['reduce.py', '--job', str(jj), '--students', 'R3a', '--out', 'x', '--contention-sha', '0', '--freeze-commit', '0'])
        entry('write_report', lambda: wr.main(), ['write_report.py', '--contention-sha', '0', '--freeze-commit', '0'])
        os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']+987654}:dead"   # wrong start time
        ent['dead_runner'] = raises(lambda: ST.require_guard('x'), SystemExit, 'not alive')
    finally:
        os.environ['X4S4_GUARD'] = saved_env
    case("r8 guard audit rows - child binding: qualify4, label, verify_onpolicy, collect_w, diagnose, contention, reduce and "
         "write_report refuse to run outside guard.py, and a runner that is not alive is refused", all(ent.values()), got=ent)

    # ---- process-exit paths: SIGTERM to a runner stops its child; a driver leaving its loop stops a live fit
    with FastGuards() as ST:
        j = mk('sigterm'); r, exits = runner(j, 'sig', ['/bin/sleep', '30'])
        threading.Timer(0.4, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
        t0 = time.monotonic(); r.run(); el = time.monotonic()-t0
        sig_ok = receipt(j, 'sig')['breach'] == 'runner_SIGTERM' and gone(r) and el < 10 and signal.getsignal(signal.SIGTERM) is not None
        drv, djob = driver_module(tmp/'drvexit')
        ch = io.spawn(['/bin/sleep', '30'], f'{djob}/logs/fx.log', dict(PATH='/usr/bin:/bin'))
        rec = dict(launch_id='FX', pid=ch['pid'], pgid=ch['pgid'], starttime=ch['starttime'])
        drv.fit_state = lambda f: ('running', rec) if f == 'R5' else ('pending', None)
        drv.stop_live_fits('SIGTERM')
        try: ch['popen'].wait(timeout=10)
        except subprocess.TimeoutExpired:                          # not stopped: record, then clean up by verified PID
            io.stop_owned(ch['pgid'], ch['starttime'], term_grace=5, kill_grace=5); ch['popen'].wait()
        evs = (djob/'driver'/'events.jsonl').read_text().splitlines() if (djob/'driver'/'events.jsonl').exists() else []
        exit_ok = ch['popen'].returncode == -signal.SIGTERM and any(json.loads(l).get('reason') == 'driver exit: SIGTERM' for l in evs)
        msrc = (HERE/'driver.py').read_text(); mm = msrc[msrc.index('def main():'):]
        exit_wired = mm.index('try:') < mm.index('loop(fits, stop)') < mm.index('finally:') < mm.index('stop_live_fits(')
    case("r8 guard audit - process exits: SIGTERM to a guard.py runner stops its child by verified PIDs (breach runner_SIGTERM, "
         "failed receipt) and the runner restores the previous handler; a driver leaving its loop for any reason (finally) stops "
         "every live fit through its verified trainer PID", sig_ok and exit_ok and exit_wired, got=[sig_ok, exit_ok, exit_wired])

    # ---- row: the runbook invokes every long-running step through its guard (static)
    rb = (HERE/'QUALIFY-RUNBOOK.md').read_text().replace('\\\n', ' ')        # join continued shell lines
    cmds = [l for l in rb.splitlines() if 'qualify4.py ' in l or 'label.py ' in l or 'verify_onpolicy.py ' in l or 'collect_w.py ' in l
            or 'imitation.exit_r1.pack' in l or 'packw.py' in l or 'diagnose.py' in l or 'contention.py' in l or 'reduce.py ' in l or 'write_report.py ' in l
            or 'pytest' in l]
    unguarded = [l.strip()[:90] for l in cmds if l.lstrip().startswith(('cd ', '| P', '$', 'test ', '/')) and '$GRD' not in l and 'guard.py' not in l
                 and not l.lstrip().startswith(('| P8', '| P10', '| P12'))]
    packs = [l for l in rb.splitlines() if 'packw.py --set' in l]          # r10 (R9-F7): production packs through packw
    case("r8 guard audit row - runbook: every qualify4/label/verify/collect_w/pack/diagnose/readout/pytest command runs under $GRD "
         "(guard.py); both production packs (P6, P9) declare their batch as a guarded --output",
         not unguarded and len(packs) >= 2 and all('--output $J/data/' in l for l in packs), unguarded=unguarded)


# ================================================================ r9: SR-1 external watchdog, R8-F4 edges, rule H-1
def test_r9(tmp):
    import studytree as ST, guard as G, qualify4 as Q, label, verify_onpolicy as V, write_report as wr, collect_w
    WD = HERE/'watchdog.py'; PYX = sys.executable
    def fake(path, body):
        Path(path).write_text('#!/bin/sh\n'+body+'\n'); os.chmod(path, 0o755); return str(path)
    def wjob(sub, deadline='2030-01-01T00:00:00Z'):
        j = Path(tmp)/sub/'job'; (j/'watchdog').mkdir(parents=True); (j/'receipts').mkdir(); (j/'qual').mkdir()
        if deadline: (j/'HARD-STOP-UTC.txt').write_text(deadline+'\n')
        ctl = Path(tmp)/sub/'ctl'; ctl.mkdir(); (ctl/'du').write_text('1000'); (ctl/'gpu').write_text('100')
        (ctl/'psi').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
        du = fake(ctl/'du.sh', f'[ -f {ctl}/du-sleep ] && sleep $(cat {ctl}/du-sleep); [ -f {ctl}/du-fail ] && exit 1; echo "$(cat {ctl}/du)\t$3"')
        gpu = fake(ctl/'gpu.sh', f'[ -f {ctl}/gpu-sleep ] && sleep $(cat {ctl}/gpu-sleep); [ -f {ctl}/gpu-fail ] && exit 1; cat {ctl}/gpu')
        return j, ctl, du, gpu
    def marker(j, extra_sh=None, readout=False):
        cmd = ['/bin/sh', '-c', extra_sh] if extra_sh else ['/bin/sleep', '60']
        if readout: cmd = [PYX, '-c', 'import time; time.sleep(60)', '/x/reports/explore/x4s4/guard.py', '--readout']   # a readout root
        env = {'X4S4_STUDY': str(j), 'PATH': '/usr/bin:/bin', **({'X4S4_READOUT': '1'} if readout else {})}
        return subprocess.Popen(cmd, env=env, start_new_session=True)
    def wd_run(j, du, gpu, *opts):
        env = {k: v for k, v in os.environ.items() if k not in ('X4S4_STUDY',)}
        return subprocess.Popen([PYX, '-B', str(WD), 'run', '--job', str(j), '--cycle', '1.0', '--measure-budget', '0.8', '--stall', '3',
                                 '--stop-grace', '1.5', '--kill-grace', '1', '--nvidia-smi', gpu, '--slow-cycle', '0.5', '--slow-budget', '2', '--slow-max-age', '3', '--gpu-timeout', '0.5',
                                 '--mem-floor', '1', '--psi', str(Path(du).parent/'psi'), *opts],     # host-independent defaults
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    def until(cond, limit=15):
        t0 = time.monotonic()
        while time.monotonic()-t0 < limit:
            if cond(): return True
            time.sleep(0.1)
        return False
    def halt_doc(j): return json.loads((j/'HALT.json').read_text()) if (j/'HALT.json').exists() else {}
    def cleanup(*ps):
        for p in ps:
            if p.poll() is None: p.kill()                                # our own direct children (by PID)
            p.wait()
    old_age = ST.WATCHDOG_MAX_AGE; ST.WATCHDOG_MAX_AGE = 30.0
    res = {}
    try:
        # ---- healthy: heartbeat, no HALT, study processes untouched; watchdog_ok holds
        j, ctl, du, gpu = wjob('w-ok'); m = marker(j); w = wd_run(j, du, gpu)
        ok_hb = until(lambda: (j/'watchdog'/'heartbeat.json').exists()); time.sleep(1.5)
        res['healthy'] = ok_hb and m.poll() is None and not (j/'HALT.json').exists() and ST.watchdog_ok(str(j)) is None \
            and json.loads((j/'watchdog'/'heartbeat.json').read_text())['readings']['processes'] == 1
        # STOP honoured: STOP appears, the study process exits by itself before the grace -> no HALT; STOP period logged
        (j/'STOP').symlink_to(j/'nowhere'); time.sleep(0.4); m.terminate(); m.wait(); time.sleep(2.2)
        res['stop_honoured_no_halt'] = not (j/'HALT.json').exists()
        (j/'STOP').unlink()
        until(lambda: '"end"' in (j/'watchdog'/'stop-periods.jsonl').read_text())    # the next cycle records the end
        sp = [k for k in (json.loads(l)['kind'] for l in (j/'watchdog'/'stop-periods.jsonl').read_text().splitlines()) if k in ('start', 'end')]
        res['stop_period_logged'] = sp == ['start', 'end'] and len(ST.stop_periods(str(j))) == 1
        cleanup(w)
        # ---- every breach -> HALT.json + STOP, the study tree stopped one PID at a time, other jobs untouched
        def breach(sub, setup, want, opts=(), deadline='2030-01-01T00:00:00Z', stubborn=False):
            j, ctl, du, gpu = wjob(sub, deadline)
            ms = [marker(j), marker(j, 'trap "" TERM; sleep 60 & wait') if stubborn else marker(j)]; late = None
            other = marker(Path(tmp)/'other-job')                      # a different study marker: never touched
            setup(j, ctl)
            w = wd_run(j, du, gpu, *opts)
            try:
                halted = until(lambda: (j/'HALT.json').exists())
                emptied = until(lambda: all(p.poll() is not None for p in ms))
                late = marker(j); late_killed = until(lambda: late.poll() is not None)       # HALT is a hard stop
                h = halt_doc(j)
                ok = halted and emptied and late_killed and want in h.get('reason', '') and os.path.lexists(j/'STOP') \
                    and other.poll() is None and oct((j/'HALT.json').stat().st_mode & 0o777) == '0o444'
                return ok, h.get('reason')
            finally:
                cleanup(*[x for x in (w, other, *ms, late) if x is not None])
        cases = dict(
            deadline=breach('w-dl', lambda j, c: None, 'after the deadline', deadline='2000-01-01T00:00:00Z'),
            no_deadline=breach('w-nodl', lambda j, c: None, 'before the deadline file', deadline=None),
            deadline_changed=breach('w-dlc', lambda j, c: threading.Timer(1.0, lambda: (j/'HARD-STOP-UTC.txt').write_text('2031-01-01T00:00:00Z\n')).start(), 'deadline file changed'),
            memory=breach('w-mem', lambda j, c: None, 'MemAvailable', opts=('--mem-floor', str(10**15))),
            psi_unreadable=breach('w-psi', lambda j, c: None, 'PSI unreadable', opts=('--psi', '/nonexistent/psi')),
            processes=breach('w-procs', lambda j, c: None, 'study processes > 1', opts=('--max-procs', '1')),
            pss=breach('w-pss', lambda j, c: None, 'study PSS', opts=('--tree-pss', '1')),
            disk=breach('w-disk', lambda j, c: None, 'disk', opts=('--max-disk', '1')),                  # HR-1: the real walk of the job
            du_failed=breach('w-duf', lambda j, c: ((j/'locked').mkdir(), os.chmod(j/'locked', 0)), 'measurement failed'),   # unreadable dir
            du_timeout=breach('w-dut', lambda j, c: None, 'measurement failed', opts=('--slow-budget', '0')),   # HR-2: the walk's bound = the slow pass budget
            gpu_over=breach('w-gpu', lambda j, c: (c/'gpu').write_text('50000'), 'GPU'),
            gpu_failed=breach('w-gpuf', lambda j, c: (c/'gpu-fail').write_text('1'), 'measurement failed'),
            stop_not_honoured=breach('w-stop', lambda j, c: (j/'STOP').symlink_to(j/'nowhere'), 'STOP not honoured', stubborn=True),
            measurement_overdue=breach('w-over', lambda j, c: (c/'gpu-sleep').write_text('6'), 'measurement overdue', opts=('--gpu-timeout', '30')))
        res['breaches'] = {k: v[0] for k, v in cases.items()}
        # the E8 readout may run after the deadline: readout-marked processes alone never HALT; a production one does
        j, ctl, du, gpu = wjob('w-ro', '2000-01-01T00:00:00Z'); ro = marker(j, readout=True); w = wd_run(j, du, gpu)
        fake_halts = until(lambda: (j/'HALT.json').exists()) and 'after the deadline' in halt_doc(j).get('reason', '')
        cleanup(w, ro)
        res['deadline_inert_readout_tokens_halt'] = fake_halts       # SR-3: a real Runner subtree is the positive (test_r10)
        # ---- after HALT: watchdog_ok refuses, and every entry point refuses new work
        j = Path(tmp)/'w-dl'/'job'
        res['after_halt_watchdog_ok'] = ST.watchdog_ok(str(j)) is not None
        jj = new_job(tmp/'w-entry'); wjson(jj/'HALT.json', dict(epoch=time.time())); wjson(jj/'watchdog'/'heartbeat.json', dict(pid=os.getpid(), epoch=time.time(), halted='x'))
        r = G.Runner(str(jj), 'after-halt', ['/bin/true']); r.exit = lambda c: None
        res['runner_refuses'] = 'watchdog' in (r.run() or {}).get('error', '')
        sup = load_fresh('supervise_r9', HERE/'supervise.py')
        res['supervisor_refuses'] = 'watchdog' in (sup.admit_phase(str(jj), 1) or '')
        drv, djob = driver_module(tmp/'w-drv'); wjson(djob/'watchdog'/'heartbeat.json', dict(pid=os.getpid(), epoch=time.time(), halted='HALT'))
        res['driver_final_gate_refuses'] = 'watchdog' in (drv.final_gate() or '')
        # ---- launcher: detached, own session, outside the study tree even when launched from a marked shell
        j, ctl, du, gpu = wjob('w-start')
        env = dict(os.environ, X4S4_STUDY=str(j))
        st = subprocess.run([PYX, '-B', str(WD), 'start', '--job', str(j), '--cycle', '1.0', '--measure-budget', '0.8', '--slow-cycle', '0.5', '--slow-budget', '2', '--slow-max-age', '3', '--nvidia-smi', gpu,
                             '--mem-floor', '1', '--psi', str(ctl/'psi')],
                            env=env, capture_output=True, text=True, timeout=30)
        pidrec = json.loads((j/'watchdog'/'pid.json').read_text()); wpid = pidrec['pid']
        with open(f'/proc/{wpid}/environ', 'rb') as f: wenv = f.read()
        res['launcher'] = st.returncode == 0 and b'X4S4_STUDY' not in wenv and os.getsid(wpid) == wpid and \
            subprocess.run([PYX, '-B', str(WD), 'status', '--job', str(j)], capture_output=True).returncode == 0 and \
            subprocess.run([PYX, '-B', str(WD), 'start', '--job', str(j)], capture_output=True).returncode != 0
        if io.proc_stat(wpid) and io.proc_stat(wpid)['starttime'] == pidrec['starttime']: os.kill(wpid, signal.SIGTERM)   # verified PID
        until(lambda: io.proc_stat(wpid) is None or io.proc_stat(wpid)['state'] == 'Z', 10)
        # ---- static: one stdlib-only file; verified one-by-one PID signals; never results
        src = WD.read_text(); tree_ = ast.parse(src)
        imports = {a.name.split('.')[0] for n in ast.walk(tree_) if isinstance(n, ast.Import) for a in n.names} | \
                  {n.module.split('.')[0] for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom)}
        kt = src[src.index('def kill_tree'):src.index('# ---------------------------------------------------------------- status / control')]
        res['static'] = imports <= {'argparse', 'calendar', 'json', 'math', 'os', 'queue', 'secrets', 'signal', 'stat', 'subprocess', 'sys',
                                    'threading', 'time', 'studytree'} \
            and [ast.unparse(n) for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom)] == ['from studytree import readout_invocation', 'from studytree import tree_bytes'] \
            and 'killpg' not in src and 'os.kill(-' not in src and kt.index('self.tree.still(pid, start)') < kt.index('os.kill(pid, sig)') \
            and not any(w in c.value for c in ast.walk(tree_) if isinstance(c, ast.Constant) and isinstance(c.value, str) and len(c.value) < 80
                        for w in ('/games', '/analysis', '/data', '/collect', '/qual', '/fits', 'results', 'outcome', 'loss'))
    finally:
        ST.WATCHDOG_MAX_AGE = old_age
    case("r9 SR-1 watchdog (real process, real disk walk, fake nvidia-smi): healthy -> heartbeat, no HALT, study processes untouched; STOP "
         "honoured within the grace -> no HALT, STOP period logged; each breach (deadline reached / missing / changed, memory, "
         "unreadable PSI, process count, PSS, disk, disk-walk failure (unreadable dir)/timeout, GPU over/failure, STOP not honoured, a stalled cycle) -> "
         "read-only HALT.json + STOP, every study process stopped one by one (a TERM-ignoring one by KILL), a later study process "
         "stopped too, another job's process untouched; after HALT the runner, supervisor and driver refuse new work; the launcher "
         "detaches the watchdog outside the study tree; stdlib-only, verified PID signals, no result paths",
         all(v for k, v in res.items() if k != 'breaches') and all(res['breaches'].values()), res=res,
         reasons={k: v[1] for k, v in cases.items()})

    # ---- R8-F4: every producer -> consumer edge needs the producer's matching passed receipt
    f4 = {}
    j = new_job(tmp/'f4')
    stub_torch_imports(); from imitation.exit_r1 import pack as packmod
    ow_game(Path(tmp)/'f4raw'/'game-00000', C+0, 4, index=56); batch = j/'qual'/'smoke-pack'/'batch-0000'
    packmod.pack([Path(tmp)/'f4raw'], batch)
    ta = types.SimpleNamespace(packed=str(batch), assets=str(j/'inputs'/'assets.npz'))
    f4['trainer_unguarded'] = raises(lambda: Q.trainer(ta), BaseException, 'R8-F4')
    wjson(j/'receipts'/'guard-failed-sp.json', dict(schema='x4s4.guard.v1', passed=False, outputs={str(batch): ST.output_identity(str(batch))}))
    f4['trainer_failed_receipt'] = raises(lambda: Q.trainer(ta), BaseException, 'R8-F4')
    bless(batch); f4['trainer_guarded_proceeds'] = not raises(lambda: Q.trainer(ta), BaseException, 'R8-F4')   # then offline imports fail
    wjson(j/'data'/'O-VERIFIED.json', dict(mode='O', rows=5)); collect_w.JOB = str(j)
    f4['collect_w_o_gate'] = raises(collect_w.o_target, io.Refusal, 'guard receipt')
    collect_w.JOB = io.JOB
    wjson(j/'data'/'label-plan.json', {}); (j/'data'/'onpolicy').mkdir(); V.JOB = str(j)
    V.main(['--mode', 'O', '--plan', str(HERE/'plan.json')]) if not (j/'data'/'O-VERIFIED.json').unlink() else None
    f4['verify_label_plan'] = 'label plan has no passed guard' in json.loads((j/'data'/'onpolicy'/'VERIFY-RECEIPT.json').read_text())['error']
    wjson(j/'data'/'O-VERIFIED.json', dict(mode='O', rows=5)); (j/'data'/'onpolicy-w').mkdir()
    sel = wjson(j/'data'/'raw-OW-selection.json', {}); acc = wjson(j/'data'/'raw-OW-acceptance-smoke.json', {}); bless(sel, acc)
    V.main(['--mode', 'OW', '--plan', str(HERE/'plan.json'), '--selection', str(sel)])
    f4['verify_ow_o_gate'] = 'O-VERIFIED.json has no passed guard receipt' in json.loads((j/'data'/'onpolicy-w'/'VERIFY-RECEIPT.json').read_text())['error']
    vsrc = (HERE/'verify_onpolicy.py').read_text(); wsrc = (HERE/'write_report.py').read_text()
    f4['write_report_label_plan'] = "guarded_output(J, paths['label_plan'])" in wsrc
    use_job(j)
    case("r9 R8-F4: the trainer refuses a smoke batch without its passed smoke-pack receipt (missing or failed) before opening it, and "
         "proceeds past the check with one; O_W generation and O_W verification authenticate the guarded O gate; O/holdout verification "
         "and the report require the guarded label plan", all(f4.values()), f4=f4)

    # ---- H-1: outputs completing at/after HALT, at/after the deadline or during STOP are never counted
    h1 = {}
    j = new_job(tmp/'h1'); out = wjson(j/'qual'/'o.json', dict(a=1)); rec = bless(out)
    t_rec = os.stat(rec).st_mtime
    h1['counted'] = ST.guarded_output(str(j), str(out)) is not None
    wjson(j/'HALT.json', dict(epoch=t_rec-1)); h1['after_halt'] = ST.guarded_output(str(j), str(out)) is None and ST.h1_reason(str(j), t_rec) == 'after HALT'
    wjson(j/'HALT.json', dict(epoch=t_rec+1)); h1['before_halt'] = ST.guarded_output(str(j), str(out)) is not None
    (j/'HALT.json').write_text('not json'); h1['halt_unreadable'] = ST.guarded_output(str(j), str(out)) is None
    (j/'HALT.json').unlink()
    (j/'watchdog'/'stop-periods.jsonl').write_text(json.dumps(dict(kind='start', epoch=t_rec-5))+'\n'+json.dumps(dict(kind='end', epoch=t_rec+5))+'\n')
    h1['during_stop'] = ST.guarded_output(str(j), str(out)) is None and ST.h1_reason(str(j), t_rec) == 'during STOP'
    (j/'watchdog'/'stop-periods.jsonl').write_text(json.dumps(dict(kind='start', epoch=t_rec-9))+'\n'+json.dumps(dict(kind='end', epoch=t_rec-5))+'\n')
    h1['after_stop_period'] = ST.guarded_output(str(j), str(out)) is not None
    (j/'HARD-STOP-UTC.txt').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t_rec-1))+'\n')
    h1['after_deadline'] = ST.guarded_output(str(j), str(out)) is None and ST.h1_reason(str(j), t_rec) == 'after deadline'
    rro = wjson(j/'receipts'/'guard-readout-x.json', dict(json.loads(Path(rec).read_text()), readout=True))   # a --readout run
    h1['readout_flag_alone_not_exempt'] = ST.guarded_output(str(j), str(out)) is None      # r10 (R9-F3): invocation + output bound
    rro.unlink()
    (j/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    os.symlink(j/'nowhere', j/'STOP'); h1['stop_present_now'] = ST.h1_reason(str(j), time.time()+1) == 'during STOP'; (j/'STOP').unlink()
    # block level: a game pair whose proof completed after HALT is not counted by label admission, parity or the reducer
    pk = j/'collect'/'K4S-120'/'a1'
    for i in range(3): write_collect_game(pk, 'K4S-120', i, (100, 110))
    late = pk/'blocks'/'0002.json'; tl = os.stat(late).st_mtime
    for n in ('0000.json', '0001.json'): os.utime(pk/'blocks'/n, (tl-100, tl-100))
    wjson(j/'HALT.json', dict(epoch=tl-50))
    h1['label_block'] = label.authenticate_block(str(pk), 'K4S-120', 2) is None and label.authenticate_block(str(pk), 'K4S-120', 1) is not None
    h1['parity_inventory'] = sorted(int(x[1].split('-')[1]) for x in Q.parity_inventory([str(pk)])) == [0, 1]
    h1['proved_game'] = raises(lambda: Q.proved_game(str(pk), 2, 'K4S-120', C), Q.QualError, 'H-1')
    (j/'HALT.json').unlink()
    # reducer: a reporting block completed after HALT is excluded and counted in checks
    import reduce as rdc
    rj = reduce_fixture(Path(tmp)/'h1-red'); fake_watchdog(rj); use_job(rj)
    plan = json.loads((rj/'x'/'plan.json').read_text())
    d = sorted((rj/'games'/'R5'/'K4S-120').glob('a*'))[0]; blocks = sorted((d/'blocks').glob('*.json'))
    tb = time.time()
    for b in (rj/'games'/'R5').rglob('blocks/*.json'): os.utime(b, (tb-100, tb-100))     # every R5 block in time ...
    for rd_ in rj.glob('rt-*/READY.json'): os.utime(rd_, (tb-100, tb-100))                 # (and its READY: R9-F6)
    os.utime(blocks[-1], (tb, tb)); wjson(rj/'HALT.json', dict(epoch=tb-50))              # ... except this one
    chk = __import__('collections').Counter()
    rows, _complete = rdc.load_student(str(rj), 'R5', plan, set(), chk)
    h1['reducer'] = chk['h1_excluded'] == 1 and int(blocks[-1].name[:-5]) not in rows['K4S-120']
    # driver: a READY written during STOP does not make the student ready (R8-F7's late READY)
    drv, djob = driver_module(tmp/'h1-drv'); rd = djob/'rt-R5'/'READY.json'; rd.parent.mkdir(parents=True)
    os.symlink(djob/'nowhere', djob/'STOP'); time.sleep(0.02); wjson(rd, dict(utc='x'))
    h1['late_READY'] = drv.ready('R5') is False and 'R5' not in drv.ready_students()
    (djob/'STOP').unlink(); (djob/'watchdog'/'stop-periods.jsonl').write_text('')
    h1['READY_in_time'] = (wjson(rd, dict(utc='y')) and drv.ready('R5')) is True
    use_job(io.JOB)
    case("r9 rule H-1: a guarded output counts only if its receipt completed before any HALT (unreadable HALT fails closed), before "
         "the deadline and outside every STOP period (watchdog log, or a STOP present now); a game block completed after HALT is "
         "not counted by label admission, parity or proved_game, and the reducer excludes it (counted in checks); a READY written "
         "during STOP does not make a student ready", all(h1.values()), h1=h1)

    # ---- markers and STOP exit (static): every study entry point requires X4S4_STUDY=<job>; calibration env carries it;
    # the driver leaves its loop under STOP/HALT once nothing lives, so the watchdog's stop grace can be met
    gs, ss, ds = (HERE/'guard.py').read_text(), (HERE/'supervise.py').read_text(), (HERE/'driver.py').read_text()
    case("r9 study marker and STOP exit: guard.py, supervise.py and driver.py require X4S4_STUDY=<job>; the calibration child's "
         "explicit environment carries it; the driver exits under STOP/HALT when no supervisor, calibration or fit lives",
         "os.environ.get('X4S4_STUDY') != io.JOB" in gs and "(os.environ.get('X4S4_READOUT') == '1') != bool(a.readout)" in gs
         and "os.environ.get('X4S4_STUDY') != job or 'X4S4_READOUT' in os.environ" in ss
         and "os.environ.get('X4S4_STUDY') != J or 'X4S4_READOUT' in os.environ" in ds and "X4S4_STUDY=J," in ds and "reason='STOP/HALT; nothing live" in ds)


# ================================================================ r10: Sol r9 R9-F1..F8 (ruling SR-2), one case each
def test_r10(tmp):
    import studytree as ST, guard as G, label
    WD = HERE/'watchdog.py'; PYX = sys.executable
    sys.path.insert(0, str(HERE)); import watchdog as W, packw
    def fake(path, body):
        Path(path).write_text('#!/bin/sh\n'+body+'\n'); os.chmod(path, 0o755); return str(path)
    def wjob(sub, deadline='2030-01-01T00:00:00Z'):
        j = Path(tmp)/sub/'job'; (j/'watchdog').mkdir(parents=True); (j/'receipts').mkdir()
        if deadline: (j/'HARD-STOP-UTC.txt').write_text(deadline+'\n')
        ctl = Path(tmp)/sub/'ctl'; ctl.mkdir(); (ctl/'du').write_text('1000'); (ctl/'gpu').write_text('100')
        (ctl/'psi').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
        du = fake(ctl/'du.sh', f'[ -f {ctl}/du-raw ] && {{ cat {ctl}/du-raw; exit 0; }}; echo "$(cat {ctl}/du)\t$3"')
        gpu = fake(ctl/'gpu.sh', f'cat {ctl}/gpu')
        return j, ctl, du, gpu
    def wd(j, ctl, du, gpu, *opts):
        env = {k: v for k, v in os.environ.items() if k not in ('X4S4_STUDY', 'X4S4_READOUT')}
        return subprocess.Popen([PYX, '-B', str(WD), 'run', '--job', str(j), '--cycle', '1.0', '--measure-budget', '0.8', '--stall', '3',
                                 '--stop-grace', '1.5', '--kill-grace', '1', '--nvidia-smi', gpu, '--slow-cycle', '0.5', '--slow-budget', '2', '--slow-max-age', '3',
                                 '--gpu-timeout', '0.5', '--mem-floor', '1', '--psi', str(ctl/'psi'), *opts],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    def marked(j, cmd, readout=False):
        env = {'X4S4_STUDY': str(j), 'PATH': '/usr/bin:/bin', **({'X4S4_READOUT': '1'} if readout else {})}
        return subprocess.Popen(cmd, env=env, start_new_session=True)
    def until(cond, limit=15):
        t0 = time.monotonic()
        while time.monotonic()-t0 < limit:
            if cond(): return True
            time.sleep(0.1)
        return False
    def reason(j): return json.loads((j/'HALT.json').read_text()).get('reason', '') if (j/'HALT.json').exists() else ''
    def alive_pid(pid): s_ = io.proc_stat(pid); return bool(s_ and s_['state'] != 'Z')
    def cleanup(*ps):
        for p in ps:
            if p is not None and p.poll() is None: p.kill()
            if p is not None: p.wait()
    def ident(pid): s_ = io.proc_stat(pid); return (pid, s_['starttime']) if s_ else None
    def kill_pid(pid_start):                                        # stray test descendants, by verified (pid, starttime)
        if pid_start and ident(pid_start[0]) == pid_start and alive_pid(pid_start[0]): os.kill(pid_start[0], signal.SIGKILL)
    def halted_with(sub, setup, want, opts=(), extra=None):
        j, ctl, du, gpu = wjob(sub); m = marked(j, ['/bin/sleep', '60']); setup(j, ctl)
        w = wd(j, ctl, du, gpu, *opts)
        try:
            ok = until(lambda: (j/'HALT.json').exists()) and until(lambda: m.poll() is not None) and want in reason(j)
            return ok and (extra(j) if extra else True), reason(j)
        finally: cleanup(w, m)

    # ---- R9-F1: stalls and failures in the watchdog's OWN writes HALT, and teardown never depends on its log
    f1 = {}
    f1['heartbeat_fifo'] = halted_with('f1-hb', lambda j, c: os.mkfifo(j/'watchdog'/'heartbeat.json'), 'watchdog write failed')
    f1['log_fifo_teardown'] = halted_with('f1-log', lambda j, c: os.mkfifo(j/'watchdog'/'watchdog.log'), 'MemAvailable',
                                          opts=('--mem-floor', str(10**15)))
    a = types.SimpleNamespace(cycle=1.0, measure_budget=0.8, stall=3.0, slow_budget=2.0, slow_max_age=3.0)
    dog = W.Watchdog.__new__(W.Watchdog); dog.a = a; dog.breach = None; dog.m_start = dog.m_done = dog.last_start = None
    dog.s_start = dog.s_done = None
    now = time.monotonic(); dog.progress = now-4.0
    f1['stall_unit'] = 'stalled' in (dog.due(now)[0] or '')
    case("R9-F1 (Sol): a FIFO at heartbeat.json (a stuck or failed watchdog write) HALTs and stops the tree; with a FIFO at "
         "watchdog.log, a memory breach still HALTs and stops the tree (teardown never waits on its log); no worker progress "
         "for STALL is a HALT", all(v[0] if isinstance(v, tuple) else v for v in f1.values()), f1={k: (v[1] if isinstance(v, tuple) else v) for k, v in f1.items()})

    # ---- R9-F2: checks every <= cycle+0.5 s; an overdue measurement or a late start HALTs
    j, ctl, du, gpu = wjob('f2'); w = wd(j, ctl, du, gpu); seen = []
    try:
        t0 = time.monotonic()
        while time.monotonic()-t0 < 5.0:
            try: e = json.loads((j/'watchdog'/'heartbeat.json').read_text())['epoch']
            except (OSError, ValueError, KeyError): e = None
            if e and (not seen or e != seen[-1]): seen.append(e)
            time.sleep(0.05)
    finally: cleanup(w)
    gaps = [b-a_ for a_, b in zip(seen, seen[1:])]
    dog.progress = now; dog.m_start = now-0.9; dog.m_done = None; dog.last_start = now-0.9
    over = 'overdue' in (dog.due(now)[0] or '')
    dog.m_done = now-0.1; dog.last_start = now-1.6
    late = 'no measurement started' in (dog.due(now)[0] or '')
    ov = halted_with('f2-over', lambda j, c: (c/'gpu.sh').write_text('#!/bin/sh\nsleep 3; echo 1\n'), 'measurement overdue', opts=('--gpu-timeout', '30'))
    case("R9-F2 (Sol): healthy heartbeats are <= cycle+0.5 s apart (cycle 1.0 s here, 9.5 s by default so <= 10 s); a "
         "measurement longer than its budget HALTs (real process), and so does a late measurement start (unit)",
         len(gaps) >= 3 and max(gaps) <= 1.5 and over and late and ov[0], gaps=[round(g, 3) for g in gaps], overdue=ov[1])

    # ---- R9-F3: membership closed over launched work (cleaned-env exec, exact-env helpers); the readout exemption is
    # bound to a readout runner's subtree, the exact invocation and its declared output
    j, ctl, du, gpu = wjob('f3'); w = wd(j, ctl, du, gpu)
    m = marked(j, ['/bin/sh', '-c', 'env -i /bin/sleep 60 & sleep 2; exec env -i /bin/sleep 61'])
    helper_pid = None
    try:
        time.sleep(3.0)
        kids = [ident(int(p)) for p in os.listdir('/proc') if p.isdigit() and (io.proc_stat(int(p)) or {}).get('ppid') == m.pid]
        helper_pid = kids[0] if kids else None
        with open(f'/proc/{m.pid}/environ', 'rb') as f: cleaned = b'X4S4_STUDY' not in f.read()
        hb = json.loads((j/'watchdog'/'heartbeat.json').read_text())['readings']
        counted = hb.get('processes') == 2                             # the exec'd process and its unmarked helper
        (ctl/'gpu').write_text('50000')                                 # breach (GPU over) -> both are stopped
        stopped = until(lambda: m.poll() is not None) and until(lambda: helper_pid is None or ident(helper_pid[0]) != helper_pid
                                                                  or not alive_pid(helper_pid[0]))
    finally:
        cleanup(w, m)
        if helper_pid: kill_pid(helper_pid)
    rr = Path(tmp)/'f3repo'; (rr/'reports'/'explore'/'x4s3').mkdir(parents=True); (rr/'reports'/'explore'/'x4s3'/'runtime.sh').write_text('exit 0\n')
    good = ['/bin/bash', str(rr/'reports/explore/x4s3/runtime.sh'), str(rr/'reports/explore/x4s4/reduce.py')]
    inert = raises(lambda: G.Runner(str(j), 'x', ['/bin/sh', '-c', 'printf "{}" > "$1"', 'reports/explore/x4s4/reduce.py', 'o'], readout=True), SystemExit, 'readout')
    jj = new_job(tmp/'f3-h1'); res_ = wjson(jj/'analysis'/'results.json', {}); other = wjson(jj/'qual'/'other.json', {})
    (jj/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
    def rec_for(path, argv):
        return wjson(jj/'receipts'/f'guard-ro-{random.randrange(10**9)}.json', dict(schema='x4s4.guard.v1', passed=True, readout=True, argv=argv,
                                                                                   outputs={str(path): sha(path)}, new_files={}))
    r1 = rec_for(res_, good); exempt_ok = ST.guarded_output(str(jj), str(res_)) is not None; r1.unlink()
    r2 = rec_for(res_, ['/bin/sh', '-c', 'x', str(rr/'reports/explore/x4s4/reduce.py')]); inert_no = ST.guarded_output(str(jj), str(res_)) is None; r2.unlink()
    r3 = rec_for(other, good); undeclared_no = ST.guarded_output(str(jj), str(other)) is None; r3.unlink()
    # SR-3: the readout root is a real guard.py Runner. Unit: the argv predicate. Negative: Python -c with inert guard.py /
    # --readout tokens HALTs after the deadline. Positive: a real Runner subtree (a test copy of watchdog/guard/studytree
    # whose x4s4io.JOB names the temp job; byte-identical otherwise) keeps running after the deadline.
    GP, gcmd = W.GUARD_PATH, ['/bin/bash', '/r/reports/explore/x4s3/runtime.sh', '/r/reports/explore/x4s4/reduce.py']
    argv_cases = dict(
        real=W.readout_argv([PYX, '-B', GP, '--name', 'x', '--readout', '--', *gcmd]) is True,
        dash_c=W.readout_argv([PYX, '-c', 'x', GP, '--readout', '--', *gcmd]) is False,
        dash_m=W.readout_argv([PYX, '-m', 'guard', '--readout', '--', *gcmd]) is False,
        other_guard_path=W.readout_argv([PYX, '-B', '/x/reports/explore/x4s4/guard.py', '--readout', '--', *gcmd]) is False,
        no_readout_flag=W.readout_argv([PYX, '-B', GP, '--name', 'x', '--', *gcmd]) is False,
        readout_only_after_dashdash=W.readout_argv([PYX, '-B', GP, '--name', 'x', '--', *gcmd, '--readout']) is False,
        wrapped_not_allowlisted=W.readout_argv([PYX, '-B', GP, '--readout', '--', '/bin/sh', '-c', 'x', '/r/reports/explore/x4s4/reduce.py']) is False,
        not_python=W.readout_argv(['/bin/bash', GP, '--readout', '--', *gcmd]) is False)
    j2, ctl2, du2, gpu2 = wjob('f3-ro', '2000-01-01T00:00:00Z')
    inert_proc = marked(j2, [PYX, '-c', 'import time; time.sleep(60)', '/x/reports/explore/x4s4/guard.py', '--readout', '--', *gcmd], readout=True)
    w2 = wd(j2, ctl2, du2, gpu2)
    try: inert_halts = until(lambda: (j2/'HALT.json').exists()) and 'after the deadline' in reason(j2)
    finally: cleanup(w2, inert_proc)
    cr = Path(tmp)/'f3-copy'; xd = cr/'reports'/'explore'/'x4s4'; xd.mkdir(parents=True); jx = cr/'job'
    for f_ in ('watchdog.py', 'guard.py', 'studytree.py'): shutil.copy(HERE/f_, xd/f_)
    src_io = (HERE/'x4s4io.py').read_text(); line = "JOB = '/mpac/sdicks02/jobs/clasher/x4s4-onpolicy'"; assert src_io.count(line) == 1
    (xd/'x4s4io.py').write_text(src_io.replace(line, f"JOB = '{jx}'"))                       # test copy only
    (cr/'reports'/'explore'/'x4s3').mkdir(parents=True); (cr/'reports'/'explore'/'x4s3'/'runtime.sh').write_text('exec /bin/sleep 60\n')
    for d_ in ('watchdog', 'receipts', 'logs'): (jx/d_).mkdir(parents=True)
    (jx/'HARD-STOP-UTC.txt').write_text('2000-01-01T00:00:00Z\n')
    env_w = {k: v for k, v in os.environ.items() if k not in ('X4S4_STUDY', 'X4S4_READOUT')}
    w3 = subprocess.Popen([PYX, '-B', str(xd/'watchdog.py'), 'run', '--job', str(jx), '--cycle', '1.0', '--measure-budget', '0.8', '--stall', '3',
                           '--stop-grace', '1.5', '--kill-grace', '1', '--nvidia-smi', gpu2, '--slow-cycle', '0.5', '--slow-budget', '2', '--slow-max-age', '3', '--gpu-timeout', '0.5',
                           '--mem-floor', '1', '--psi', str(ctl2/'psi')], env=env_w, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    runner, kids, bare = None, [], None
    try:
        until(lambda: (jx/'watchdog'/'heartbeat.json').exists())
        runner = subprocess.Popen([PYX, '-B', str(xd/'guard.py'), '--name', 'ro', '--readout', '--', '/bin/bash',
                                   str(cr/'reports'/'explore'/'x4s3'/'runtime.sh'), str(xd/'reduce.py')],
                                  env={'X4S4_STUDY': str(jx), 'X4S4_READOUT': '1', 'PATH': '/usr/bin:/bin'}, preexec_fn=lambda: os.nice(10),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        until(lambda: any((io.proc_stat(int(p)) or {}).get('ppid') == runner.pid for p in os.listdir('/proc') if p.isdigit()), 20)
        kids = [ident(int(p)) for p in os.listdir('/proc') if p.isdigit() and (io.proc_stat(int(p)) or {}).get('ppid') == runner.pid]
        time.sleep(3.0)                                                      # past deadline + grace, several cycles
        runner_ok = bool(kids) and runner.poll() is None and all(k and ident(k[0]) == k for k in kids) and not (jx/'HALT.json').exists()
        bare = marked(jx, ['/bin/sleep', '60'], readout=True)               # a READOUT-marked process outside the Runner
        bare_halts = until(lambda: (jx/'HALT.json').exists()) and 'after the deadline' in reason(jx)
        until(lambda: runner.poll() is not None and not any(k and ident(k[0]) == k for k in kids))   # HALT stops the Runner tree
    finally:
        cleanup(w3, runner, bare)
        for k in kids: kill_pid(k)
    f3 = dict(cleaned_env_exec_counted=cleaned and counted, stopped=stopped, inert_token_refused=inert, exempt_ok=exempt_ok,
              inert_receipt_not_exempt=inert_no, undeclared_output_not_exempt=undeclared_no, **{f'argv_{k}': v for k, v in argv_cases.items()},
              inert_tokens_halt=inert_halts, real_runner_subtree_exempt=runner_ok, bare_readout_marker_halts=bare_halts)
    case("R9-F3 (Sol): a process that execs with a cleaned environment and its exact-environment helper stay members (counted, "
         "stopped on HALT); guard.py refuses an inert script token as --readout; the deadline H-1 exemption needs the exact "
         "invocation AND the script's declared output; SR-3: a readout root must be Python running exactly the adjacent guard.py "
         "in --readout mode with an allowlisted wrapped command (argv unit cases); Python -c with inert guard.py/--readout tokens "
         "HALTs after the deadline, while a real guard.py Runner's subtree keeps running and a bare READOUT-marked process HALTs",
         all(f3.values()), f3=f3)

    # ---- R9-F4: malformed measurements are failures (valid high PSI is still not a breach)
    psi = lambda v: (lambda j, c: (c/'psi').write_text(f'some avg10={v} avg60=0 avg300=0 total=0\n'))
    f4 = dict(psi_nan=halted_with('f4-nan', psi('nan'), 'malformed'), psi_inf=halted_with('f4-inf', psi('inf'), 'malformed'),
              psi_neg=halted_with('f4-neg', psi('-1'), 'malformed'), psi_101=halted_with('f4-101', psi('101'), 'malformed'),
              psi_no_some=halted_with('f4-nosome', lambda j, c: (c/'psi').write_text('full avg10=0\n'), 'malformed'),
              meminfo_no_kb=halted_with('f4-mem', lambda j, c: (c/'meminfo').write_text('MemAvailable: 999\n'), 'MemAvailable malformed',
                                        opts=('--meminfo', str(Path(tmp)/'f4-mem'/'ctl'/'meminfo'))),
              disk_unreadable=halted_with('f4-du', lambda j, c: ((j/'locked').mkdir(), os.chmod(j/'locked', 0)), 'measurement failed'),
              gpu_empty=halted_with('f4-gpu0', lambda j, c: (c/'gpu').write_text(''), 'nvidia-smi printed nothing'),
              gpu_negative=halted_with('f4-gpun', lambda j, c: (c/'gpu').write_text('-3'), 'measurement failed'))
    j, ctl, du, gpu = wjob('f4-high'); (ctl/'psi').write_text('some avg10=99.50 avg60=0 avg300=0 total=0\n'); m = marked(j, ['/bin/sleep', '60'])
    w = wd(j, ctl, du, gpu)
    try: time.sleep(2.5); high_ok = not (j/'HALT.json').exists() and m.poll() is None
    finally: cleanup(w, m)
    case("R9-F4 (Sol): PSI nan/inf/-1/101 or without a 'some' line, MemAvailable without its unit, an unreadable job directory (HR-1 walk), and an empty "
         "or negative nvidia-smi reading are measurement failures (HALT); a valid high PSI (99.5) is not a breach (frozen rule)",
         all(v[0] for v in f4.values()) and high_ok, f4={k: v[1][:50] for k, v in f4.items()}, high_ok=high_ok)

    # ---- R9-F5: STOP history is durable before STOP goes; missing history fails closed
    j, ctl, du, gpu = wjob('f5'); w = wd(j, ctl, du, gpu, '--cycle', '5.0', '--measure-budget', '0.8')
    try:
        until(lambda: (j/'watchdog'/'heartbeat.json').exists()); time.sleep(0.3)
        t_stop = time.time()
        subprocess.run([PYX, '-B', str(WD), 'stop', '--job', str(j)], check=True, capture_output=True)
        out = j/'receipts'/'late.json'; out.write_text('{}'); t_mid = os.stat(out).st_mtime
        subprocess.run([PYX, '-B', str(WD), 'resume', '--job', str(j)], check=True, capture_output=True)   # before the next cycle
        hist = [json.loads(l) for l in (j/'watchdog'/'stop-periods.jsonl').read_text().splitlines()]
    finally: cleanup(w)
    kinds = [h['kind'] for h in hist if h['kind'] in ('start', 'end')]
    (j/'HARD-STOP-UTC.txt').write_text('2030-01-01T00:00:00Z\n')
    t_start = next(h['epoch'] for h in hist if h['kind'] == 'start')
    pulse = kinds[:2] == ['start', 'end'] and ST.h1_reason(str(j), t_mid) == 'during STOP' and ST.h1_reason(str(j), t_stop-5) is None \
        and ST.h1_reason(str(j), t_start-0.01) == 'during STOP'                # coarse-clock mtimes: the boundary is widened
    os.symlink('nowhere', j/'STOP'); time.sleep(0.02)
    subprocess.run([PYX, '-B', str(WD), 'resume', '--job', str(j)], check=True, capture_output=True)   # a raw STOP: recorded first
    raw_rec = [json.loads(l) for l in (j/'watchdog'/'stop-periods.jsonl').read_text().splitlines()][-2:]
    raw_ok = [r['kind'] for r in raw_rec] == ['start', 'end'] and raw_rec[0]['source'] == 'resume' and not os.path.lexists(j/'STOP')
    (j/'watchdog'/'stop-periods.jsonl').rename(j/'watchdog'/'gone.jsonl')
    missing_closed = (ST.h1_reason(str(j), time.time()) or '').startswith('STOP periods unreadable')
    (j/'watchdog'/'gone.jsonl').rename(j/'watchdog'/'stop-periods.jsonl')
    wjson(j/'HALT.json', dict(epoch=time.time())); os.symlink('nowhere', j/'STOP')
    no_resume_after_halt = subprocess.run([PYX, '-B', str(WD), 'resume', '--job', str(j)], capture_output=True).returncode != 0
    case("R9-F5 (Sol): a STOP pulse made and removed through `watchdog.py stop/resume` before the next watchdog cycle leaves a durable "
         "start+end, and an output completed inside it is excluded by H-1 while an earlier one counts; resuming a raw STOP records "
         "its start before removal; a missing STOP history fails H-1 closed; resume is refused after HALT",
         pulse and raw_ok and missing_closed and no_resume_after_halt, kinds=kinds, raw=[r['kind'] for r in raw_rec])

    # ---- R9-F6: H-1 on reused dependencies: fit completions/checkpoints, calibrations, raw seals, READY at every consumer
    f6 = {}
    drv, djob = driver_module(tmp/'f6'); out = djob/'fits'/'R5'; out.mkdir(parents=True)
    hist = djob/'watchdog'/'stop-periods.jsonl'
    for st_ in (250, 2500): (out/f'step-{st_:08d}.pt').write_bytes(b'ck')
    t = time.time(); os.utime(out/'step-00000250.pt', (t-200, t-200))
    hist.write_text(json.dumps(dict(kind='start', epoch=t-100))+'\n'+json.dumps(dict(kind='end', epoch=t+100))+'\n')   # STOP covers "now"
    wjson(out/'complete.json', dict(stopped=False, step=2500)); wjson(out/'segment.json', dict(status='returned'))
    rec = dict(pid=2**22+901, pgid=2**22+901, starttime=7, launch_id='F6', launched_at_utc='2026-10-13T00:00:00Z'); wjson(djob/'receipts'/'fit-R5-launch.json', rec)
    with (djob/'driver'/'events.jsonl').open('a') as f: f.write(json.dumps(dict(utc='x', kind='child_exit', pid=rec['pid'], launch_id='F6', exit_code=0))+'\n')
    f6['late_final_not_done'] = drv.fit_state('R5')[0] == 'stopped'
    f6['resume_from_admissible'] = drv.admissible_checkpoint(str(out)) == str(out/'step-00000250.pt')
    os.utime(out/'step-00000250.pt', (t, t)); f6['no_admissible_none'] = drv.admissible_checkpoint(str(out)) is None
    drv.prepare_fit_dirs = lambda fid: (['batch-0000'], 'g'*64); drv.final_gate = lambda: None
    drv.Fits().launch('R5', 'stopped'); f6['no_admissible_anomaly'] = (djob/'driver'/'ANOMALY-fit-R5-resume.json').exists()
    cal = djob/'calibration'/'R5.json'; wjson(cal, dict(threshold=.5)); acc = wjson(djob/'receipts'/'calibration-R5-accepted-X.json', dict(calibration_sha256=sha(cal)))
    f6['late_calibration_refused'] = drv.accepted_calibration('R5', str(cal)) is None
    hist.write_text(''); f6['in_time_calibration_ok'] = drv.accepted_calibration('R5', str(cal)) is not None
    for sid_ in ('R3a-rep', 'R5', 'R5-rep', 'R5W'):
        rd = djob/f'rt-{sid_}'/'READY.json'; rd.parent.mkdir(exist_ok=True); wjson(rd, dict(student=dict(checkpoint='x', checkpoint_sha256='c', threshold=.5)))
    bp = djob/'base'/'repo'/'reports'/'explore'/'x4s3'/'plan.json'; bp.parent.mkdir(parents=True)
    wjson(bp, dict(student=dict(id='R3a', checkpoint='x', checkpoint_sha256='c', threshold=.5)))
    wjson(djob/'HALT.json', dict(epoch=time.time()-50))
    import reduce as rdc, diagnose as dg, write_report as wr
    f6['ready_reduce'] = raises(lambda: rdc.load_student(str(djob), 'R5', json.loads((HERE/'plan.json').read_text()), set(), __import__('collections').Counter()), io.Refusal, 'H-1')
    f6['ready_diagnose'] = raises(lambda: dg.students_of(str(djob)), io.Refusal, 'H-1')
    f6['ready_report'] = raises(lambda: wr.staged_students(str(djob), str(HERE/'plan.json')), io.Refusal, 'H-1')
    f6['ready_studytree'] = raises(lambda: ST.ready_student(str(djob), 'R5'), io.Refusal, 'H-1')
    (djob/'HALT.json').unlink()
    # raw label seal completed during STOP: reuse refused even with a guarded receipt listing it -> set aside, relabelled
    use_job(djob); lj = djob
    stub_torch_imports()
    caps_dir = lj/'collect'/'K4S-120'/'a1'; write_collect_game(caps_dir, 'K4S-120', 0, (100, 110))
    pkl = caps_dir/'captures'/'sim-0000-d27-K4S-120.pkl'; summ = json.loads(pkl.with_suffix('.json').read_text())
    keep = sorted(pickle.loads(c)['id'] for c in pickle.loads(pkl.read_bytes()))
    entry = dict(file=str(pkl), sha256=summ['sha256'], arm='K4S-120', index=0, seed=C, keep=keep, keep_sha256=hashlib.sha256(json.dumps(keep).encode()).hexdigest())
    saved = (label.score_state, label.RAW, label.PLAN_SHA, label.THREADS, label.DATA_ROLE)
    label.score_state = lambda *a, **k: (5, [5, 600, 2304, 2401], [0.3, 0.1, 0.2, None]); label.RAW = f'{lj}/data/raw-O'; label.PLAN_SHA = 'p'*64; label.THREADS = 1; label.DATA_ROLE = 'data'
    try:
        first = label.label_game(entry); gdir = lj/'data'/'raw-O'/'K4S-120'/'game-0000'
        bless(wjson(lj/'data'/'label-receipt-O-9.json', dict(label.summarize([first], 1), set='O')))
        ok_reuse = label.label_game(entry)['status'] == 'already_sealed'
        tm = os.stat(gdir/'manifest.json').st_mtime
        hist.write_text(json.dumps(dict(kind='start', epoch=tm-1))+'\n'+json.dumps(dict(kind='end', epoch=tm+1))+'\n')
        late_seal = label.label_game(entry)['status'] == 'sealed' and list(gdir.parent.glob('unaccepted-game-0000-*'))
    finally:
        label.score_state, label.RAW, label.PLAN_SHA, label.THREADS, label.DATA_ROLE = saved; hist.write_text(''); use_job(io.JOB)
    f6['raw_seal_reuse_in_time'] = ok_reuse; f6['raw_seal_during_stop_set_aside'] = bool(late_seal)
    case("R9-F6 (Sol): a final fit completion inside a STOP period is not 'done' (resumed from the newest H-1-admissible checkpoint; "
         "none -> a blocking anomaly); a calibration accepted during STOP is refused; a READY after HALT is refused by the reducer, "
         "the diagnostic, the report and studytree; a raw label seal completed during STOP is not reused even with a passed receipt "
         "(set aside, relabelled), while an in-time one with its receipt is", all(f6.values()), f6=f6)

    # ---- R9-F7: the packer's inputs need producer evidence (missing / failed / changed identity refused)
    pj = new_job(tmp/'f7'); from imitation.exit_r1 import pack as packmod
    g0 = pj/'data'/'raw-O'/'K4S-120'/'game-0000'; ow_game(g0, C+0, 4, index=56)
    m0 = hashlib.sha256((g0/'manifest.json').read_bytes()).hexdigest()
    f7 = dict(missing=raises(lambda: packw.authenticate_inputs(str(pj), 'O'), io.Refusal, 'provenance'))
    lr = wjson(pj/'data'/'label-receipt-O-1.json', dict(game_manifests=[['K4S-120', 0, m0]]))
    wjson(pj/'receipts'/'guard-failed-lr.json', dict(schema='x4s4.guard.v1', passed=False, outputs={str(lr): sha(lr)}))
    f7['failed_receipt'] = raises(lambda: packw.authenticate_inputs(str(pj), 'O'), io.Refusal, 'provenance')
    lr2 = wjson(pj/'data'/'label-receipt-O-2.json', dict(game_manifests=[['K4S-120', 0, '0'*64]])); bless(lr2)
    f7['changed_identity'] = raises(lambda: packw.authenticate_inputs(str(pj), 'O'), io.Refusal, 'provenance')
    bless(lr); roots, n, authed = packw.authenticate_inputs(str(pj), 'O')
    packw.check_inventory(roots, authed)
    packmod.pack(roots, pj/'data'/'onpolicy'/'batch-0000'); f7['with_evidence_packs'] = n == 1 and (pj/'data'/'onpolicy'/'batch-0000'/'manifest.json').exists()
    # SR-3: one authenticated real game + one game-* symlink to a sealed game WITHOUT evidence -> refused before the packer runs
    unauth = Path(tmp)/'f7-unauth'/'game-0009'; ow_game(unauth, C+9, 4, index=56)
    link = pj/'data'/'raw-O'/'K4S-120'/'game-0001'; os.symlink(unauth, link)
    packed_calls = []; real_pack = packmod.pack; packmod.pack = lambda *a_, **k_: packed_calls.append(a_)
    use_job(pj)
    try: link_refused = raises(lambda: packw.main(['--set', 'O', '--output', f'{pj}/data/onpolicy/batch-0001']), io.Refusal, 'not a real directory')
    finally: packmod.pack = real_pack; use_job(io.JOB)
    f7['symlinked_game_refused_before_pack'] = link_refused and not packed_calls and not (pj/'data'/'onpolicy'/'batch-0001').exists()
    link.unlink()
    # SR-3: the packer's glob must equal the authenticated inventory right before packing (a game appearing afterwards)
    roots, n, authed = packw.authenticate_inputs(str(pj), 'O')
    ow_game(pj/'data'/'raw-O'/'K4S-120'/'game-0002', C+2, 4, index=56)
    f7['inventory_changed_refused'] = raises(lambda: packw.check_inventory(roots, authed), io.Refusal, 'inventory')
    shutil.rmtree(pj/'data'/'raw-O'/'K4S-120'/'game-0002'); f7['inventory_equal_ok'] = packw.check_inventory(roots, authed) is None
    ow = pj/'data'/'raw-OW'/'game-00000'; ow_game(ow, CW+0, 4, index=56)
    f7['ow_without_selection'] = raises(lambda: packw.authenticate_inputs(str(pj), 'OW'), io.Refusal, 'provenance')
    bless(wjson(pj/'data'/'raw-OW-selection.json', dict(games=[dict(g=0, manifest_sha256=hashlib.sha256((ow/'manifest.json').read_bytes()).hexdigest())])))
    f7['ow_with_selection'] = packw.authenticate_inputs(str(pj), 'OW')[1] == 1
    rb = (HERE/'QUALIFY-RUNBOOK.md').read_text()
    f7['runbook_packs_via_packw'] = rb.count('packw.py --set') >= 3 and 'imitation.exit_r1.pack' not in rb
    case("R9-F7 (Sol): packw refuses raw label games without a passed receipt, with only a failed one, or listed with another "
         "manifest; with their evidence the unchanged packer packs them; SR-3: a game-* symlink to an unevidenced sealed game "
         "beside an authenticated one is refused before the packer runs, and the packer's glob must equal the authenticated "
         "inventory; O_W games need the guarded selection; the runbook's production packs go through packw", all(f7.values()), f7=f7)

    # ---- R9-F8: the watchdog's own I/O is confined (sentinels preserved; no symlink/hard link/FIFO/ancestor redirect)
    cj = new_job(tmp/'f8'); sentinel = Path(tmp)/'f8-sentinel.txt'; sentinel.write_text('KEEP')
    jfd, wfd = W.dirs(str(cj))
    f8 = {}
    try:
        (cj/'watchdog'/'heartbeat.json').unlink(); os.symlink(sentinel, cj/'watchdog'/'heartbeat.json')
        f8['symlink_target_refused'] = raises(lambda: W.write_atomic(wfd, 'heartbeat.json', dict(x=1)), OSError) and sentinel.read_text() == 'KEEP'
        (cj/'watchdog'/'heartbeat.json').unlink()
        hl = cj/'watchdog'/'stop-periods.jsonl'; hl.unlink(); os.link(sentinel, hl)
        f8['hardlink_append_refused'] = raises(lambda: W.append(wfd, 'stop-periods.jsonl', dict(x=1)), OSError) and sentinel.read_text() == 'KEEP'
        hl.unlink(); os.mkfifo(cj/'watchdog'/'watchdog.log'); t0 = time.monotonic()
        f8['fifo_append_refused_fast'] = raises(lambda: W.append(wfd, 'watchdog.log', dict(x=1)), OSError) and time.monotonic()-t0 < 1.0
        (cj/'watchdog'/'pid.json').unlink(); os.symlink(sentinel, cj/'watchdog'/'pid.json')
        f8['symlink_read_refused'] = raises(lambda: W.read_small(wfd, 'pid.json'), OSError)
        W.write_atomic(wfd, 'heartbeat.json', dict(x=2))
        f8['no_temp_left'] = not [n for n in os.listdir(cj/'watchdog') if '.tmp-' in n]
    finally:
        os.close(wfd); os.close(jfd)
    link_job = Path(tmp)/'f8-linkjob'; os.symlink(cj, link_job)
    f8['symlinked_job_refused'] = raises(lambda: W.dirs(str(link_job)), OSError)
    cj2 = new_job(tmp/'f8b'); shutil.rmtree(cj2/'watchdog'); os.symlink(Path(tmp), cj2/'watchdog')
    f8['symlinked_watchdog_dir_refused'] = raises(lambda: W.dirs(str(cj2)), OSError)
    src = WD.read_text(); tree_ = ast.parse(src)
    opens = [ast.unparse(n.args[0]) for n in ast.walk(tree_) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'open']
    f8['builtin_open_only_proc_and_host_files'] = all(o.startswith("f'/proc/") or o in ('a.meminfo', 'a.psi') for o in opens)
    osopens = [n for n in ast.walk(tree_) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'os.open']
    f8['os_open_nofollow'] = all('NF' in ast.unparse(n) or ast.unparse(n.args[0]) == "'/'" for n in osopens)
    case("R9-F8 (Sol): the watchdog's own writer refuses a symlinked heartbeat target, a hard-linked history, a FIFO log (without "
         "blocking) and a symlinked pid file, leaving outside sentinels unchanged; a symlinked job path or watchdog directory is "
         "refused; temps are exclusive and cleaned; builtin open() is used only for /proc and the host's meminfo/PSI; every os.open "
         "is O_NOFOLLOW", all(f8.values()), f8=f8)


# ================================================================ static (F11, F17, R2-F10), run_fit.sh (F5)
def test_static(tmp):
    owned = [p for p in sorted(HERE.glob('*.py')) if p.name not in ('run_collect.py', 'test_x4s4_offline.py')]
    routed = [p for p in owned if p.name != 'watchdog.py']        # SR-1: the watchdog is deliberately stdlib-only (test_r9)
    asserts = {p.name: sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(p.read_text()))) for p in owned}
    case('F11: no assert statement in any X4S-4-owned script', not any(asserts.values()), asserts=asserts)
    bypass = {}
    for p in routed:
        if p.name in ('x4s4io.py',): continue
        src = p.read_text(); tree = ast.parse(src)
        fs_attrs = ('write_text', 'write_bytes', 'read_text', 'read_bytes', 'mkdir', 'unlink', 'rmdir', 'rename', 'symlink_to', 'chmod',
                    'rmtree', 'copyfile', 'copytree', 'killpg', 'kill', 'Popen', 'check_output', 'system', 'open')
        def flagged(n):
            if isinstance(n.func, ast.Name): return n.func.id == 'open'
            if not isinstance(n.func, ast.Attribute): return False
            owner = ast.unparse(n.func.value)
            if owner in ('io', 'np', 'json', 'pickle', 'fcntl'): return False
            if n.func.attr in ('replace', 'run'): return owner in ('subprocess', 'os', 'shutil') or owner.startswith('Path')
            return n.func.attr in fs_attrs
        bad = [ast.unparse(n)[:60] for n in ast.walk(tree) if isinstance(n, ast.Call) and flagged(n)]
        bad = [b for b in bad if not b.startswith(("open('/proc", 'open(\'/proc', 'open("/proc'))]
        if bad: bypass[p.name] = bad
    case('R2-F1: no owned script reads, writes, renames, removes, spawns or group-signals outside x4s4io (only /proc is read directly)',
         not bypass, bypass=bypass)
    plan = json.loads((HERE/'plan.json').read_text())
    drv_src = (HERE/'driver.py').read_text()
    case('F17/R2-F10: plan.json describes r3: ABBA order, no futility, host-wide contention, the prefix rule for interruptions',
         '87809ae0' in plan['planning_doc'] and plan['students_order'] == ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']
         and "STUDENT_ORDER = ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']" in drv_src and 'host-wide' in plan['readout']['contention']
         and 'largest seed-index prefix' in plan['ordering']['interrupted'] and 'terminal in every reduced' not in plan['ordering']['interrupted'])
    for f in ('plan-collect.json', 'plan-qual-capture.json'):
        c = json.loads((HERE/f).read_text())
        case(f'{f} is a full staged runtime config (student R3a, policy v1, capture block)',
             c['student']['checkpoint_sha256'] == plan['student']['checkpoint_sha256'] and c['policy']['checkpoint_sha256'] == plan['policy']['checkpoint_sha256'] and 'capture' in c)
    fj = Path(tmp)/'fjob'; (fj/'data').mkdir(parents=True); (fj/'fit').mkdir(); (fj/'cache'/'fit'/'tmp').mkdir(parents=True)
    wjson(fj/'data'/'O-VERIFIED.json', dict(batches=[dict(name='batch-0000'), dict(name='batch-0001')]))
    src = (HERE/'run_fit.sh').read_text().replace('J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy', f'J={fj}')
    src = src.replace('exec /mpac/sdicks02/envs/clasher-gpu/bin/python -B', 'printf "%s\\n"').replace('cd "$J/fit/source"', 'true')
    src = src.replace('EXIT_LOADER_AMENDMENT_SHA256=$(sha256sum "$EXIT_LOADER_AMENDMENT" | cut -d \' \' -f 1)', 'EXIT_LOADER_AMENDMENT_SHA256=x')
    (Path(tmp)/'rf.sh').write_text(src)
    rf = lambda *a, env=None: subprocess.run(['bash', str(Path(tmp)/'rf.sh'), *a], capture_output=True, text=True, env=env)
    out = rf('R5', '-', 'batch-0000', 'batch-0001')
    roots = [l for l in out.stdout.split('\n') if l.endswith(('/batch-0000', '/batch-0001'))]
    shell = dict(ok=out.returncode == 0 and len(roots) == 8 and '2026101301' in out.stdout and '--resume' not in out.stdout,
                 resume=('--resume' in rf('R5', '/x/ck.pt', 'batch-0000').stdout), r5w_without_gate=rf('R5W', '-', 'batch-0000').returncode != 0,
                 no_batches=rf('R5', '-').returncode == 3, bad_name=rf('R5', '-', '../evil').returncode != 0,
                 reads_no_json='json.load' not in (HERE/'run_fit.sh').read_text() and 'mkdir' not in (HERE/'run_fit.sh').read_text())
    shutil.rmtree(fj/'cache'/'fit'/'tmp'); os.symlink(Path(tmp), fj/'cache'/'fit'/'tmp')
    shell['tmpdir_symlink'] = rf('R5', '-', 'batch-0000').returncode == 3
    case('R3-F1: run_fit.sh takes the driver-authenticated batch names (x4, seed 2026101301), reads no JSON and creates no directory, '
         'refuses no/bad batch names, R5W without its gate, and a TMPDIR the driver did not prepare', all(shell.values()), shell=shell)
    import collect_w
    collect_w.X = [[f'deck{d}-{c}' for c in range(8)] for d in range(5)]
    ok = all(collect_w.game_inputs(g)[4][collect_w.game_inputs(g)[3] % 8] == collect_w.X[g % 5] and collect_w.game_inputs(g)[4][7] == collect_w.X[(g//5) % 5] for g in range(200))
    case('collect_w: emitter-derived (own, opponent, seat) equals the X4S mapping for g in 0..199; acceptance on the qualification bank',
         ok and collect_w.QUAL_BASE == QUAL and collect_w.ACCEPTANCE_GAMES == 2)


UMASK = os.umask(0); os.umask(UMASK)


def main():
    # r8: owned entry points run only under guard.py (studytree.require_guard); in-process test calls run as the child of
    # this live process. Negative tests unset/forge X4S4_GUARD explicitly.
    os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']}:offline-tests"
    import studytree as _st; _st.WATCHDOG_MAX_AGE = 1e9          # r9: fixture heartbeats do not age; test_r9 restores 30 s
    canonical, canonical_repo = io.JOB, io.REPO
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-test-', dir='/dev/shm'))
    try:
        for t in (test_io, test_runner_identity, test_collect, test_pipeline, test_driver, test_supervise, test_sa4, test_sa5, test_hr1, test_hr2, test_contention,
                  test_reduce, test_qualify, test_diagnose, test_audit, test_studytree, test_live_paths, test_r6, test_r7, test_r8, test_r9, test_r10, test_static):
            d = tmp/t.__name__; d.mkdir()
            try: t(d)
            except Exception as e:
                import traceback; traceback.print_exc(); case(t.__name__+' raised', False, error=repr(e))
            finally: use_job(canonical); io.REPO = canonical_repo
    finally:
        for p in tmp.rglob('*'):
            if not p.is_symlink():
                try: p.chmod(0o755 if p.is_dir() else 0o644)
                except OSError: pass
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(r['ok'] for r in RESULTS)
    print(json.dumps(dict(all_ok=ok, cases=len(RESULTS), failed=[r['case'] for r in RESULTS if not r['ok']], python_optimize=sys.flags.optimize,
                          umask=oct(UMASK))))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
