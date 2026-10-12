"""X4S-4 on-policy state collection (exploration, NEVER ADOPTABLE).

Plays deployment games with run_collect.py (a byte copy of the reviewed x4s3/run.py plus one explicit
post-timer CAPTURE(...) call) and captures student-seat decision states for offline W labeling.
The hook runs after the decision timer closed and lateness was computed, so it is never charged to a
decision; it reads its keyword arguments only and writes nothing back into the game.

Capture rule (config "capture" block; plan-collect.json):
  search decisions only: no preparation cutoff, no suspended belief transaction, more than one
  candidate after the 2305 filter, empty pending channel (else counted and skipped);
  captured if deadline hit, else with probability nonhit_rate from a domain-separated draw;
  `all: true` captures every eligible decision (qualification only).

Per capture: the gate-c training row of the student's own reserved packet, policy mask and D1 (and a
parity flag vs build_public), deep copies of info, reserved_packet and opponent_elixir, pending (empty),
one opponent hidden state sampled from a DEEP COPY of the agent's belief, root RNG state and digest, a SHA-256
of the pickled (reserved_packet, opponent_elixir, pending) triple for the round-trip test (R2-11),
candidate RNG state, and deadline stats. RNGs are seeded from SHA-256("x4s4-capture|label|seed|tick").
Captures are pickled with a persistent_id guard that raises on any BattleState/PlayerState object.

Qualification switches (capture block): verify_belief (pickle-hash of the live belief before/after
every capture must match) and fair_check (deep-copy the battle, permute the opponent's unrevealed
hand/cycle, reseed the battle RNG; the capture payload built from the altered battle must be byte-identical).
"""
import copy, hashlib, io, json, pickle, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURE_SCHEMA = 'x4s4.capture.v2'
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
    buf = io.BytesIO(); GuardedPickler(buf, protocol=pickle.HIGHEST_PROTOCOL).dump(obj); return buf.getvalue()


def capture_rng(label, seed, tick):
    import numpy as np
    digest = hashlib.sha256(f'x4s4-capture|{label}|{int(seed)}|{int(tick)}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], 'little'))


def config():
    global _cfg
    if _cfg is None:
        cfg = json.loads(Path(sys.argv[sys.argv.index('--config')+1]).read_text())
        c = cfg['capture']
        rate = float(c['nonhit_rate'])
        if not 0 <= rate <= 1:
            raise ValueError('invalid nonhit_rate')
        flags = {k: c.get(k, False) for k in ('all', 'verify_belief', 'fair_check')}
        if not all(isinstance(v, bool) for v in flags.values()):
            raise ValueError('capture flags must be booleans')
        _cfg = dict(nonhit_rate=rate, **flags)
    return _cfg


def eligible(kw):
    if kw['preparation_hit'] or kw['stats'].get('preparation_cutoff'):
        return 'preparation_cutoff'
    if getattr(kw['p'].belief, '_pending', None) is not None:
        return 'belief_pending'
    if kw['candidates'] is None or len(kw['candidates']) <= 1:
        return 'not_search'
    if tuple(kw['ch'].pending):
        return 'pending_nonempty'
    return None


def payload(kw, b):
    """Capture payload for one decision; `b` is passed separately so fair_check can substitute a copy."""
    import numpy as np
    global _costs
    from imitation.exit_r1.rows import observation, feature_bytes
    from imitation.model.features import build_row
    from imitation.evaluation.d1 import model_packet
    R = run.R
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
    public_equal = all(public[k].tobytes() == row[k].tobytes() for k in row)
    opponent = copy.deepcopy(p.belief).sample(capture_rng('opponent', seed, tick))   # deep copy: live belief untouched
    root_rng = capture_rng('root', seed, tick)
    root_rng_state = copy.deepcopy(root_rng.bit_generator.state)
    root = R.root(copy.deepcopy(info), copy.deepcopy(opponent), root_rng)
    hit = bool(stats['hit'])
    c8 = (copy.deepcopy(reserved.packet), copy.deepcopy(getattr(p.core, 'opponent_elixir', None)), tuple(kw['ch'].pending))
    return dict(c8_sha256=hashlib.sha256(pickle.dumps(c8, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest(),
        schema=CAPTURE_SCHEMA, id=f"{kw['arm']}/{seed}/{tick}", arm=kw['arm'], index=int(kw['pair']), seed=seed,
        tick=tick, seat=actor, row=row, features_equal_student_input=bool(features_equal),
        row_equals_build_public=bool(public_equal), info=copy.deepcopy(info),
        reserved_packet=copy.deepcopy(reserved.packet), opponent_elixir=copy.deepcopy(getattr(p.core, 'opponent_elixir', None)),
        pending=tuple(kw['ch'].pending), opponent=copy.deepcopy(opponent), root_rng_state=root_rng_state,
        root_digest=root.digest(), candidate_rng_state=copy.deepcopy(capture_rng('candidates', seed, tick).bit_generator.state),
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
    if len(names) > 1:
        rot = names[1:]+names[:1]             # deterministic non-identity permutation of unrevealed cards
        for (k, i), n in zip(slots, rot):
            if k == 'hand': opp.hand[i] = n
            else: cycle[i] = n
        opp.cycle_queue.clear(); opp.cycle_queue.extend(cycle)
    if hasattr(b2, 'rng'):
        b2.rng = random.Random(0x5EED)
    return b2, len(names)


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
    cap = payload(kw, kw['b'])
    blob = guarded_dumps(cap)                 # raises ForbiddenObject on any BattleState/PlayerState reference
    if cfg['verify_belief']:
        after = hashlib.sha256(pickle.dumps(kw['p'].belief, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()
        _checks['belief_unchanged'] = _checks.get('belief_unchanged', 0)+(before == after)
        _checks['belief_checked'] = _checks.get('belief_checked', 0)+1
    if cfg['fair_check']:
        b2, permuted = permuted_battle(kw['b'], int(kw['actor']), kw['opponent_events'])
        same = guarded_dumps(payload(kw, b2)) == blob
        _checks['fair_identical'] = _checks.get('fair_identical', 0)+same
        _checks['fair_checked'] = _checks.get('fair_checked', 0)+1
        _checks['fair_permuted_cards'] = _checks.get('fair_permuted_cards', 0)+permuted
    _captures.append(blob)
    _counts['captured'] = _counts.get('captured', 0)+1


def install(module):
    global run
    run = module
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    GuardedPickler.forbidden = (BattleState, PlayerState)
    original_game = run.run_game

    def run_game(case):
        _captures.clear(); _counts.clear(); _checks.clear()
        t0 = time.monotonic()
        result = original_game(case)
        pair, seed, arm = case[0], case[1], case[2]
        out = Path(run.OPTIONS['out'])/'captures'; out.mkdir(exist_ok=True)
        target = out/f'sim-{pair:04d}-d27-{arm}.pkl'
        if target.exists():
            raise FileExistsError(str(target))
        body = pickle.dumps(list(_captures), protocol=pickle.HIGHEST_PROTOCOL)   # list of guarded blobs
        tmp = target.with_suffix('.pkl.tmp'); tmp.write_bytes(body); run.durable(tmp); tmp.replace(target); run.durable(target)
        caps = [pickle.loads(x) for x in _captures]
        summary = dict(schema=CAPTURE_SCHEMA, index=pair, seed=seed, arm=arm, captures=len(caps), counts=dict(_counts),
                       checks=dict(_checks), sha256=hashlib.sha256(body).hexdigest(),
                       features_equal_all=all(c['features_equal_student_input'] for c in caps),
                       public_equal_all=all(c['row_equals_build_public'] for c in caps),
                       pending_empty_all=all(c['pending'] == () for c in caps),
                       strata={s: sum(c['stratum'] == s for c in caps) for s in ('hit', 'nonhit_sample', 'all')},
                       student_default=sum(bool(c['stats'].get('student_default')) for c in caps),
                       fallback=sum(bool(c['stats'].get('fallback')) for c in caps),
                       game_wall_seconds_incl_capture=time.monotonic()-t0)
        sj = target.with_suffix('.json'); tj = sj.with_suffix('.json.tmp')
        tj.write_text(json.dumps(summary)+'\n'); run.durable(tj); tj.replace(sj); run.durable(sj)
        _captures.clear()
        return result

    run.CAPTURE = capture
    run.run_game = run_game


def main():
    sys.path.insert(0, str(HERE))
    import run_collect                       # byte copy of x4s3/run.py + the explicit hook
    config()
    install(run_collect)
    run_collect.main()


if __name__ == '__main__':
    main()
