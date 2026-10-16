"""True-deck full-pool adapter and smoke; keeps deployed planning unchanged."""
from contextlib import contextmanager
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import time

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
JOB = ROOT / 'fullpool'
MODEL_ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-fullpool')
FAST = f'student:{MODEL_ROOT}/fits/f1a2/step-001200.pt'
OLD_FAST = 'student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375'
BELIEF = 'fullpool:11433651:freq=b53b02a1fde4'
LIVE = 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1'
EXTRA = ('Barbarians', 'BattleRam', 'Bomber', 'GoblinCage', 'MegaMinion', 'SpearGoblins', 'Tombstone')


def utc():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.' + str(os.getpid()))
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def runtime(belief):
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)
    rt.belief_prior = belief
    return rt


def install_placement(rt):
    from bot.levels.placement import install_runtime, _wrap
    install_runtime(rt)
    from policy import V1Policy
    if getattr(V1Policy, '_deckopt_fp_placement', False):
        return
    original = V1Policy.__init__
    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        builder = args[1] if len(args) > 1 else kwargs['builder']
        _wrap(self.player, builder)
    V1Policy.__init__ = init
    V1Policy._deckopt_fp_placement = True


def empirical_vocab(rt):
    """Reuse the public empirical builder for the seven observed extra cards."""
    import c56_controller
    from bot.players import royalesim_vocab as rv
    measured = rv.load(rt)
    path = JOB / 'vocab-seven-extra.json'
    if path.exists():
        extra = json.loads(path.read_text())
        assert extra['meta']['cards'] == list(EXTRA)
        assert extra['meta']['token_sha256'] == measured['meta']['token_sha256']
    else:
        cards = c56_controller.CARDS
        try:
            c56_controller.CARDS = EXTRA
            extra = rv.build(rt, '16.402')
        finally:
            c56_controller.CARDS = cards
        dump(path, extra)
    assert not extra['unresolved_units'], extra['unresolved_units']
    unresolved = set(extra['unresolved_projectiles']) - set(measured['projectiles']) - set(measured.get('no_counterpart_firers', ()))
    assert not unresolved, sorted(unresolved)
    assert not extra['unresolved_spells'], extra['unresolved_spells']
    assert not extra['no_template'], extra['no_template']
    # C56 statics/mappings keep their original measured values. Extra-card
    # empirical rows replace only dynamic template defaults absent from C56.
    base_raw = json.loads(rv.VOCAB_PATH.read_text())
    for field in ('units', 'spells', 'projectiles', 'statics'):
        for key, value in extra[field].items():
            if key not in base_raw[field]:
                measured[field][key] = value
    measured['meta']['deckopt_extra_cards'] = list(EXTRA)
    measured['meta']['extra_probe_sha256'] = sha(path)
    from bot.players.royalesim_translate import complete_vocab
    measured = complete_vocab(rt, measured)
    required = [tuple(value) for value in extra['units'].values()]
    assert all(f'{token}/{kind}' in measured['statics'] for token, kind in required)
    dump(JOB / 'vocab-combined.json', measured)
    return measured


class Observed:
    """Passive diagnostics plus assertions of each side's actual start config."""
    def __init__(self, inner, role, expected_belief=None, expected_fast=None):
        from bot.livediag.sim_diag import Recorder
        self.rec = Recorder(inner, 0)
        self.role = role
        self.expected_belief, self.expected_fast = expected_belief, expected_fast
        self.start_config = None
        self.last_info = None
    def __getattr__(self, name):
        return getattr(self.rec, name) if hasattr(self.rec, name) else getattr(self.rec.inner, name)
    def bind_rsim(self, match):
        return self.rec.bind_rsim(match)
    def start(self, ctx):
        self.rec.seat = ctx.seat
        self.rec.start(ctx)
        player = self.rec.inner
        search = getattr(player, 'search', None)
        belief = getattr(getattr(search, 'p', None), 'belief', None)
        fast = getattr(player, 'fast', None)
        got_belief = None if belief is None else type(belief).__name__
        got_fast = None if fast is None else str(fast.path)
        if self.expected_belief is not None:
            assert got_belief == self.expected_belief, (self.role, got_belief)
        if self.expected_fast is not None:
            assert Path(got_fast).resolve() == Path(self.expected_fast).resolve(), (self.role, got_fast)
        self.start_config = dict(role=self.role, seat=ctx.seat, name=player.name,
                                 belief_class=got_belief, fast_path=got_fast,
                                 fast_threshold=getattr(fast, 'threshold', None),
                                 runtime_belief=getattr(player.rt, 'belief_prior', None),
                                 source=getattr(player, 'source', None),
                                 deadline_seconds=player.deadline_seconds, effective_deadline_seconds=self.deadline_seconds, search_deadline_seconds=getattr(search, 'deadline_seconds', None),
                                 native_threads=getattr(search, 'native_threads', None), pool_size=getattr(search, 'pool_size', None),
                                 chunks=getattr(search, 'chunks', None))
        print('START_CONFIG', json.dumps(self.start_config), flush=True)
    def act(self, view):
        self.last_info = view.info
        return self.rec.act(view)
    def close(self):
        return self.rec.close()


def players(rt, name, opponent, seat, strong_rt=None):
    from bot.eval.headline import make_player
    from bot.live.player import LivePlayer, load_fast, make_live_player
    assert 'BOT_BELIEF_PRIOR' not in os.environ and 'CLASHER_LIVE_FAST' not in os.environ
    own = make_live_player(rt, name)
    # Equivalent to the bundle's CLASHER_LIVE_FAST override, scoped to this
    # instance so the opponent cannot inherit the bundle's fast tier.
    own.fast = load_fast(rt, FAST)
    assert abs(own.deadline_seconds - .2) < 1e-9
    own = Observed(own, 'our full-pool bundle', 'FullPoolBelief', FAST.split(':', 1)[1])
    if opponent == 'LIVE-K4CW-r16':
        other_rt = strong_rt or runtime('c56')
        install_placement(other_rt)
        other = LivePlayer(other_rt, tier='search', wall_ms=None, threads=1, r3a=16,
                           fast_spec=OLD_FAST, cutoff_default='it5s2', name=opponent)
        other = Observed(other, 'strong opponent', 'LiveBelief', OLD_FAST.split(':', 1)[1].split('@')[0])
    else:
        assert opponent in ('R3a', 'v1')
        other = Observed(make_player(rt, opponent), f'full-pool {opponent}')
    return {seat: own, 1-seat: other}


def diagnostics(player, result=None):
    from bot.livediag.live_metrics import analyse
    import bisect
    stats = analyse(player.rec.perc, player.rec.dec, {})
    decisions = [d['stats'] for d in player.rec.dec if d.get('stats')]
    searched = [d for d in decisions if 'hit' in d or 'completed' in d or
                'preparation_cutoff' in d or d.get('source', '').startswith('default-')]
    hits = sum(bool(d.get('hit')) for d in searched)
    defaults = sum(d.get('source', '').startswith('default-') for d in searched)
    pushes = stats['giant_pushes']
    reactions=[];giant_reactions=[]
    if result is not None:
        own=sorted(d['tick'] for d in player.rec.dec if d['submitted'])
        for tick,card,action,accepted in result['play_log'][1-player.rec.seat]:
            if not accepted:continue
            i=bisect.bisect_left(own,tick)
            if i==len(own):continue
            seconds=(own[i]-tick)/20
            reactions.append(seconds)
            if card=='Giant':giant_reactions.append(seconds)
    return dict(reaction_s=reactions,reaction_giant_s=giant_reactions,start_config=player.start_config, search_decisions=len(searched),
                cutoff_hits=hits, cutoff_hit_rate=hits / len(searched) if searched else None,
                defaults=defaults, default_rate=defaults / len(searched) if searched else None,
                giant_pushes=len(pushes), undefended_before_contact=sum(p['no_def_before_contact'] for p in pushes),
                giant_push_details=pushes, search_wall_ms=stats['search_wall_ms'],
                source=stats['source'], cut=stats['cut'])


def smoke():
    from bot.players.royalesim_match import play_match
    from bot.fullpool.cards import C56, engine_name
    from bot.fullpool.packet_check import check_information
    from bot.search.lopp import FAILURES
    JOB.mkdir(exist_ok=True)
    rt = runtime(BELIEF)
    install_placement(rt)
    print('RUNTIME', json.dumps(rt.pins), flush=True)
    vocab = empirical_vocab(rt)
    variant = json.loads((ROOT / 'variant-B-full-budget.json').read_text())
    collection = variant['plans']['baseline']['levels']
    raw = [json.loads(line) for line in (ROOT / 'opponent-decks.jsonl').read_text().splitlines()]
    source = max(enumerate(raw), key=lambda item: sum(engine_name(c) not in C56 for c in item[1]['opp_deck']))
    other = [engine_name(card) for card in source[1]['opp_deck']]
    case_seed = int.from_bytes(os.urandom(6), 'little')
    own = list(variant['candidates']['baseline'])
    rng = random.Random(case_seed)
    rng.shuffle(own); rng.shuffle(other)
    from bot.levels.profile import rarity, clamp, RARE_OFFSET
    prior = [2]*7 + [3]*17 + [4]*61 + [5]*110 + [6]*53 + [7]*2
    levels = [collection, {card: clamp(rarity(rt, card), rng.choice(prior) -
                          RARE_OFFSET.get(rarity(rt, card), 1)) for card in other}]
    dump(JOB / 'smoke-case.json', dict(created_utc=utc(), seed=case_seed, source_index=source[0],
         decks=[own, other], levels=levels, tower_levels=[6, 6], note='preflight only, no selection/validation claim'))
    # One game checks actual construction and the true non-C56 opponent path.
    name = LIVE + '-res'
    ps = players(rt, name, 'R3a', 0)
    started = time.monotonic(); before = Counter(FAILURES)
    result = play_match(rt, ps, seed=case_seed, decks=[own, other], vocab=vocab,
                        client='16.402', levels=levels, tower_levels=[6, 6], verbose=True)
    errors = {str(seat): [d for d in getattr(p.rec.inner, 'decisions', [])
                         if 'error' in d or d.get('native_failures')] for seat, p in ps.items()}
    failures = dict(Counter(FAILURES) - before)
    unmapped = {k: v for k, v in result['translator'].items()
                if v and ('unmapped' in k or 'missing' in k)}
    packet_issues = {}
    for seat, p in ps.items():
        previous = getattr(rt, 'belief_prior', None)
        packet_issues[str(seat)] = check_information(rt, p.last_info)
        rt.belief_prior = previous
    result.pop('command_events', None)
    row = dict(utc=utc(), player=name, simulator='RoyaleSim16.402', runtime_pin='live16402b-r3',
               source_commit='1a65dcd1a00c5e3f891228df878d3bbebe4de187', wall_seconds=time.monotonic()-started,
               result=result, diagnostics={str(seat): diagnostics(p) for seat, p in ps.items()},
               live_errors=errors, native_failures=failures, unmapped=unmapped, packet_issues=packet_issues,
               model_sha256={str(path): sha(path) for path in [MODEL_ROOT/'lopp-fp/k1a1.npz',
                    MODEL_ROOT/'fits/f1a2/step-001200.pt', MODEL_ROOT/'ext/R3a-fp.pt', MODEL_ROOT/'ext/main02-fp.pt']})
    dump(JOB / 'smoke-result.json', row)
    assert result['terminal'] and result['channels'][0]['rejected'] == 0, result
    assert not failures and not any(errors.values()) and not unmapped and not any(packet_issues.values()), row
    print('FULLPOOL_SMOKE_PASSED', utc(), flush=True)


if __name__ == '__main__':
    try:
        smoke()
    except BaseException as error:
        dump(JOB / 'smoke-error.json', dict(utc=utc(), error=repr(error)))
        raise
