"""X4S-4 on-policy state collection (exploration, NEVER ADOPTABLE). r3 after Sol script review r2.

r3 (R2-F1, R2-F8): every read and write goes through x4s4io; the entry validates --out (a confined collect/qual/smoke
path of real directories, fresh or holding only the supervisor's files) BEFORE the inherited runner touches the
filesystem; the runner only runs under its supervisor (X4S4_SUPERVISOR=pid:starttime) and, if that process disappears,
records supervisor-lost.json, TERMs its own group's verified PIDs and exits 70.

Plays deployment games with run_collect.py, a byte copy of the reviewed x4s3/run.py plus two explicit hooks:
CAPTURE(...) right after apply_lateness (the decision timer has closed) and CAPTURE_END(pair, seed, arm) right
after the game JSON is durable and before the block proof. run_game is NEVER replaced (Sol F1: its nested
inference_check locates its own frame through the module-global run_game).

Eligibility (Sol F2: the pending test uses the PRE-decision input transaction p.core.pending, which run.py sets
from the channel before candidates are generated; a play submitted by this decision is not "pending input"):
  search decisions only: no preparation cutoff, no suspended belief transaction, more than one candidate after the
  2305 filter, empty pre-decision pending (else counted and skipped); captured if deadline hit, else with
  probability nonhit_rate from a domain-separated draw; `all: true` captures every eligible decision (qualification).

Per capture: the gate-c training row of the student's own reserved packet, policy mask and D1 (and a parity flag
vs build_public of the battle passed in kw['b']), deep copies of info, reserved_packet, opponent_elixir and the
pre-decision pending tuple (with a SHA-256 of that triple), one opponent hidden state sampled from a DEEP COPY of
the agent's belief, root RNG state and digest, candidate RNG state, and deadline stats. RNGs are seeded from
SHA-256("x4s4-capture|label|seed|tick"). Captures are pickled with a persistent_id guard that raises on any
BattleState/PlayerState object.

Qualification switches (capture block): verify_belief (pickle hash of the live belief before/after every capture
must match) and fair_check (Sol F3: the payload is rebuilt from kw with kw['b'] REPLACED by a deep copy whose
opponent never-revealed hand/cycle cards are permuted and whose battle RNG is reseeded; the payload must be
byte-identical; the number of decisions with an actual card permutation is counted for coverage).
"""
import copy, hashlib, io as _stdio, json, os, pickle, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io                              # noqa: E402  (every read/write goes through the gate)

CAPTURE_SCHEMA = 'x4s4.capture.v3'
CAPTURE_ROLES = ('collect', 'qual', 'smoke')
EARLY_TICKS = 600                                 # first 30 s of game time (fair-check coverage counters)
_captures, _counts, _checks = [], {}, {}
_cfg = None
_costs = None
run = None


class ForbiddenObject(Exception):
    pass


class GuardedPickler(pickle.Pickler):
    """Refuses to serialize any battle or true player state reachable from a capture (C9)."""
    forbidden = ()

    def persistent_id(self, obj):
        if self.forbidden and isinstance(obj, self.forbidden):
            raise ForbiddenObject(f'capture graph references {type(obj).__name__}')
        return None


def guarded_dumps(obj):
    buf = _stdio.BytesIO(); GuardedPickler(buf, protocol=pickle.HIGHEST_PROTOCOL).dump(obj); return buf.getvalue()


def capture_rng(label, seed, tick):
    import numpy as np
    digest = hashlib.sha256(f'x4s4-capture|{label}|{int(seed)}|{int(tick)}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], 'little'))


def config():
    global _cfg
    if _cfg is None:
        cfg = io.read_json(sys.argv[sys.argv.index('--config')+1], 4 << 20)
        c = cfg['capture']
        rate = float(c['nonhit_rate'])
        if not 0 <= rate <= 1:
            raise ValueError('invalid nonhit_rate')
        flags = {k: c.get(k, False) for k in ('all', 'verify_belief', 'fair_check')}
        if not all(isinstance(v, bool) for v in flags.values()):
            raise ValueError('capture flags must be booleans')
        _cfg = dict(nonhit_rate=rate, **flags)
    return _cfg


def input_pending(kw):
    """The decision's INPUT transaction: run.py sets p.core.pending = tuple(ch.pending) before candidates."""
    return tuple(getattr(kw['p'].core, 'pending', ()) or ())


def eligible(kw):
    if kw['preparation_hit'] or kw['stats'].get('preparation_cutoff'):
        return 'preparation_cutoff'
    if getattr(kw['p'].belief, '_pending', None) is not None:
        return 'belief_pending'
    if kw['candidates'] is None or len(kw['candidates']) <= 1:
        return 'not_search'
    if input_pending(kw):
        return 'pending_nonempty_input'
    return None


def payload(kw):
    """Capture payload for one decision. Every battle read goes through kw['b'] (so fair_check can substitute it)."""
    import numpy as np
    global _costs
    from imitation.exit_r1.rows import observation, feature_bytes
    from imitation.model.features import build_row
    from imitation.evaluation.d1 import model_packet
    R = run.R
    b = kw['b']
    seed, actor, tick = int(kw['seed']), int(kw['actor']), int(b.tick)
    policy, reserved, info, p, stats, spec = kw['policy'], kw['reserved'], kw['info'], kw['p'], kw['stats'], kw['spec']
    d1 = copy.deepcopy(policy.player.last_d1)
    mask = np.asarray(policy.mask).copy()
    row = observation(reserved.packet, mask, d1, R.builder)
    if _costs is None:
        _costs = np.zeros(360, np.float32)
        for name, cost in R.costs.items():
            _costs[R.builder.token_id(name, namespace='card_action')] = cost
    student_input = build_row(model_packet(reserved.packet, mask), d1, _costs)
    rebuilt = feature_bytes(row, _costs)
    features_equal = all(np.asarray(v).tobytes() == np.asarray(student_input[k]).tobytes() for k, v in rebuilt.items())
    public = observation(R.builder.build_public(b, actor), mask, d1, R.builder)
    public_equal = all(np.asarray(public[k]).tobytes() == np.asarray(row[k]).tobytes() for k in row)
    opponent = copy.deepcopy(p.belief).sample(capture_rng('opponent', seed, tick))   # deep copy: live belief untouched
    root_rng = capture_rng('root', seed, tick)
    root_rng_state = copy.deepcopy(root_rng.bit_generator.state)
    root = R.root(copy.deepcopy(info), copy.deepcopy(opponent), root_rng)
    hit = bool(stats['hit'])
    pending = input_pending(kw)
    c8 = (copy.deepcopy(reserved.packet), copy.deepcopy(getattr(p.core, 'opponent_elixir', None)), pending)
    return dict(
        schema=CAPTURE_SCHEMA, id=f"{kw['arm']}/{seed}/{tick}", arm=kw['arm'], index=int(kw['pair']), seed=seed,
        tick=tick, seat=actor, row=row, features_equal_student_input=bool(features_equal),
        row_equals_build_public=bool(public_equal), info=copy.deepcopy(info),
        reserved_packet=c8[0], opponent_elixir=c8[1], pending=pending,
        c8_sha256=hashlib.sha256(pickle.dumps(c8, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest(),
        opponent=copy.deepcopy(opponent), root_rng_state=root_rng_state, root_digest=root.digest(),
        candidate_rng_state=copy.deepcopy(capture_rng('candidates', seed, tick).bit_generator.state),
        candidates_at_decision=[int(a) for a in kw['candidates']], agent_action=int(kw['action']),
        budget_ms=round(spec['deadline_seconds']*1000), kernel=spec['kernel'],
        stats={k: (v if isinstance(v, (bool, int, float, str, type(None))) else repr(v)) for k, v in stats.items()},
        stratum='hit' if hit else ('all' if config()['all'] else 'nonhit_sample'))


def permuted_battle(b, actor, opponent_events):
    """Deep copy with the opponent's never-revealed cards permuted in hand+cycle and a reseeded battle RNG."""
    b2 = copy.deepcopy(b)
    opp = b2.players[1-actor]
    revealed = {e.name for e in opponent_events if getattr(e, 'kind', None) == 'card'}   # PublicEvent(tick, kind, name, amount)
    slots = [('hand', i) for i, c in enumerate(opp.hand) if c is not None and c not in revealed]
    cycle = list(opp.cycle_queue)
    slots += [('cycle', i) for i, c in enumerate(cycle) if c not in revealed]
    names = [opp.hand[i] if k == 'hand' else cycle[i] for k, i in slots]
    moved = 0
    if len(set(names)) > 1:
        rot = names[1:]+names[:1]             # deterministic non-identity permutation of unrevealed cards
        for (k, i), n in zip(slots, rot):
            if k == 'hand': opp.hand[i] = n
            else: cycle[i] = n
        opp.cycle_queue.clear(); opp.cycle_queue.extend(cycle)
        moved = sum(a != c for a, c in zip(names, rot))
    if hasattr(b2, 'rng'):
        b2.rng = random.Random(0x5EED)
    return b2, moved


def capture(**kw):
    why = eligible(kw)
    seed, tick = int(kw['seed']), int(kw['b'].tick)
    cfg = config()
    if why is None:
        hit = bool(kw['stats']['hit'])
        if not (cfg['all'] or hit or capture_rng('nonhit', seed, tick).random() < cfg['nonhit_rate']):
            why = 'not_sampled'
    if why is not None:
        _counts[why] = _counts.get(why, 0)+1
        return
    before = hashlib.sha256(pickle.dumps(kw['p'].belief, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest() if cfg['verify_belief'] else None
    blob = guarded_dumps(payload(kw))         # raises ForbiddenObject on any BattleState/PlayerState reference
    if cfg['verify_belief']:
        after = hashlib.sha256(pickle.dumps(kw['p'].belief, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()
        _checks['belief_unchanged'] = _checks.get('belief_unchanged', 0)+(before == after)
        _checks['belief_checked'] = _checks.get('belief_checked', 0)+1
    if cfg['fair_check']:
        b2, moved = permuted_battle(kw['b'], int(kw['actor']), kw['opponent_events'])
        same = guarded_dumps(payload(dict(kw, b=b2))) == blob      # altered battle in EVERY path (kw['b'])
        _checks['fair_identical'] = _checks.get('fair_identical', 0)+same
        _checks['fair_checked'] = _checks.get('fair_checked', 0)+1
        _checks['fair_perturbed_decisions'] = _checks.get('fair_perturbed_decisions', 0)+(moved >= 2)
        _checks['fair_moved_cards'] = _checks.get('fair_moved_cards', 0)+moved
        if tick < EARLY_TICKS:                # early game: most opponent cards unrevealed (qualification coverage)
            _checks['fair_checked_early'] = _checks.get('fair_checked_early', 0)+1
            _checks['fair_perturbed_early'] = _checks.get('fair_perturbed_early', 0)+(moved >= 2)
    _captures.append(blob)
    _counts['captured'] = _counts.get('captured', 0)+1


def capture_end(pair, seed, arm):
    """Write this game's captures durably (before run.py writes the block proof); reset per-game state."""
    caps_blobs = list(_captures)
    out = str(run.OPTIONS['out'])+'/captures'
    io.mkdirs(out, roles=CAPTURE_ROLES)
    target = f'{out}/sim-{pair:04d}-d27-{arm}.pkl'
    body = pickle.dumps(caps_blobs, protocol=pickle.HIGHEST_PROTOCOL)
    io.create_excl(target, body, roles=CAPTURE_ROLES, mode=0o444)           # exclusive, fsynced, no-follow
    caps = [pickle.loads(x) for x in caps_blobs]
    summary = dict(schema=CAPTURE_SCHEMA, index=int(pair), seed=int(seed), arm=arm, captures=len(caps), counts=dict(_counts),
                   checks=dict(_checks), sha256=hashlib.sha256(body).hexdigest(),
                   features_equal_all=all(c['features_equal_student_input'] for c in caps),
                   public_equal_all=all(c['row_equals_build_public'] for c in caps),
                   pending_empty_all=all(c['pending'] == () for c in caps),
                   identity_ok=all(c['index'] == pair and c['seed'] == seed and c['arm'] == arm for c in caps),
                   strata={s: sum(c['stratum'] == s for c in caps) for s in ('hit', 'nonhit_sample', 'all')},
                   student_default=sum(bool(c['stats'].get('student_default')) for c in caps),
                   fallback=sum(bool(c['stats'].get('fallback')) for c in caps),
                   plays_captured=sum(c['agent_action'] < 2304 for c in caps))
    io.write_json_once(target[:-4]+'.json', summary, roles=CAPTURE_ROLES, mode=0o444)
    _captures.clear(); _counts.clear(); _checks.clear()


def install(module):
    global run
    run = module
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    GuardedPickler.forbidden = (BattleState, PlayerState)
    before = module.run_game
    module.CAPTURE = capture
    module.CAPTURE_END = capture_end
    if module.run_game is not before:
        raise RuntimeError('run_game identity must be preserved (inference_check)')


C_BASE = 4503606317370496
ALLOC = {'K4S-120': ((0, 2000), (3500, 3750)), 'S-200': ((2000, 3500), (3750, 4000))}   # O, O-holdout (PLAN r3 §2)


def check_allocation(argv):
    """Sol F13: a bank-C ('reporting' range of the collection config) run names one arm, and every index lies in that
    arm's O or O-holdout allocation; smoke/qualification banks are checked by run.py's own range bound."""
    def arg(k, n=1):
        i = argv.index(k); return argv[i+1:i+1+n]
    rng = arg('--range')[0]
    if rng != 'reporting': return
    cfg = io.read_json(arg('--config')[0], 4 << 20)
    if cfg['seed_ranges']['reporting'] != dict(base=C_BASE, count=4000): raise SystemExit('collection must use bank C')
    arms = []
    for x in (argv[argv.index('--arms')+1:] if '--arms' in argv else []):
        if x.startswith('--'): break
        arms.append(x)
    if len(arms) != 1 or arms[0] not in ALLOC:
        raise SystemExit('a bank-C collection phase runs exactly one arm (--arms K4S-120 or S-200)')
    idx = io.read_json(arg('--indices')[0], 1 << 20)
    bad = [i for i in idx if not any(lo <= i < hi for lo, hi in ALLOC[arms[0]])]
    if bad: raise SystemExit(f'indices outside the {arms[0]} bank-C allocation: {bad[:5]}')


SUPERVISOR_FILES = {'launch.json', 'worker.log', 'census.jsonl', 'progress.json', 'stop-reason.json'}


def check_out(argv):
    """Sol r2 R2-F1: the inherited runner creates and writes --out with ordinary path calls, so the entry validates it
    FIRST: a confined collect/qual/smoke path whose every component is a real directory, either created here or the
    supervisor's fresh phase directory (only supervisor files present)."""
    out = argv[argv.index('--out')+1]
    if not out.startswith('/'): raise SystemExit('--out must be absolute')
    io.check_writable(out, roles=CAPTURE_ROLES)
    if io.lexists(out):
        if not io.is_real_dir(out): raise SystemExit(f'--out is not a real directory: {out}')
        extra = set(io.listdir(out))-SUPERVISOR_FILES
        if extra: raise SystemExit(f'--out already holds {sorted(extra)[:5]} (one schedule per directory)')
    else:
        io.mkdirs(out, roles=CAPTURE_ROLES)
    return out


def supervisor_watchdog(out, period=5.0):
    """R2-F8 monitor death: the collection runner is only allowed to run under its live supervisor (pid:starttime in
    X4S4_SUPERVISOR). If that process is gone or replaced, the runner records it and stops its own group's PIDs."""
    import threading, signal
    spec = os.environ.get('X4S4_SUPERVISOR', '')
    try: spid, sstart = (int(x) for x in spec.split(':'))
    except ValueError: raise SystemExit('collection runs only under the X4S-4 supervisor (X4S4_SUPERVISOR=pid:starttime)')
    me = io.own_identity()
    def alive():
        st = io.proc_stat(spid); return st is not None and st['starttime'] == sstart and st['state'] != 'Z'
    if not alive(): raise SystemExit('supervisor not alive at start')
    def loop():
        while alive(): time.sleep(period)
        try: io.write_json_once(out+'/supervisor-lost.json', dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                                  supervisor=spec), roles=CAPTURE_ROLES)
        except io.Refusal: pass
        lead = io.proc_stat(me['pgid'])
        io.signal_owned(me['pgid'], lead['starttime'] if lead else me['starttime'], signal.SIGTERM, exclude=(me['pid'],))
        os._exit(70)
    t = threading.Thread(target=loop, daemon=True); t.start()
    return t


def main():
    import run_collect                       # byte copy of x4s3/run.py + the two explicit hooks
    check_allocation(sys.argv)
    out = check_out(sys.argv)                # before the inherited runner touches the filesystem
    supervisor_watchdog(out)
    config()
    install(run_collect)
    run_collect.main()


if __name__ == '__main__':
    main()
