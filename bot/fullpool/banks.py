"""Evaluation / generation cases with full-pool decks, and the bank split (exploration).

case(rt, i, base, decks) generalises bot.players.ours.x4s_setup: seed = base + i, the candidate (or student) sits in
seat i % 2, and one Random(seed) shuffles the candidate deck, then the other. Only the deck lists differ:

- decks='x4s' (default): x4s_setup itself (X-deck i%5 vs X-deck (i//5)%5); HEADLINE-v1 unchanged.
- decks='fullpool:<seed>[:k=v,...]' or 'fullpool-uniform:<seed>': both decks from bot/fullpool/decks.py, the
  candidate's = sampler.deck(i, salt='own|<base>'), the other's = sampler.deck(i, salt='opp|<base>').
  Same cases across opponents, as HEADLINE.
- option own=c56 ('fullpool:<seed>:own=c56'): the candidate deck is drawn from the same weights restricted to C56
  (opp=c56 likewise for the other seat).
  Use it while the candidate is a search player: R.bots (C56RolloutPlanner) stays C56 under r1-cards1 and raises
  'own hand outside C56 action scope' on a non-C56 own card. This is also the live situation (our deck is C56).

The search players' belief needs a prior that can hold the opponent's cards: with full-pool decks, `select()` sets
rt.belief_prior to the deck spec (bot/fullpool/belief.py), i.e. the search knows the deck DISTRIBUTION (the public
meta), never the opponent's deck.

Banks (fresh = drawn for this purpose, int.from_bytes(os.urandom(6),'big')<<4 on 2026-10-16 01:38Z, >=1e12 from
every base in bot/ and reports/bot; claims only on a bank not used for selection; results reported as they come,
nothing sealed or embargoed). Bank decks pin a frozen LIVE frequency table (':freq=<sha12>',
reports/bot/fullpool/freq/), so a LIVE refresh never changes a bank's cases:
"""
from __future__ import annotations

import random

BANKS = {
    # C56-only regression: HEADLINE-v1 itself (r1 / r1-total / r1-cards1 must give identical command hashes here).
    'C56-REG': dict(base=1455777415631152, decks='x4s', games=300,
                    use='C56 regression and continuity with every HEADLINE number so far (already used for selection)'),
    # Full-pool development bank: tune and select freely.
    'FP-DEV': dict(base=1017731189512176, decks='fullpool:846496:freq=b53b02a1fde4', games=300,
                   use='full-pool development / selection (both decks full-pool)'),
    'FPO-DEV': dict(base=1017731189512176, decks='fullpool:846496:freq=b53b02a1fde4,own=c56', games=300,
                    use='as FP-DEV, candidate deck C56 (search candidates; live-like)'),
    # Fresh full-pool claim banks: never used for selection; one claim per (bank, candidate set), reported as it comes.
    'FP-FRESH1': dict(base=3314739122528544, decks='fullpool:11574762:freq=b53b02a1fde4', games=300,
                      use='honest full-pool claims (both decks full-pool)'),
    'FPO-FRESH1': dict(base=4370374256243600, decks='fullpool:10434953:freq=b53b02a1fde4,own=c56', games=300,
                       use='honest live-like claims: candidate C56 deck vs full-pool opponents'),
    # Training generation (ExIt / RL): bot.exit.generate --base; disjoint from all of the above (checked).
    'FP-TRAIN1': dict(base=2613058991490864, decks='fullpool:11433651:freq=b53b02a1fde4', games=10**8,
                      use='full-pool label generation / self-play (games g = 0..)'),
}
EVAL_SPAN = 10**5


def reserved_eval_banks():
    """(base, span) of every eval bank, for bot.exit.generate.check_bank."""
    return tuple(sorted({(b['base'], EVAL_SPAN) for k, b in BANKS.items() if not k.startswith('FP-TRAIN')}))


_SAMPLERS: dict = {}


def parse(decks):
    """'fullpool:<seed>[:opts]' -> (sampler spec, {'own': full|c56, 'opp': full|c56})."""
    kind, _, rest = decks.partition(':')
    seed, _, opts = rest.partition(':')
    keep, seats = [], dict(own='full', opp='full')
    for kv in filter(None, opts.split(',')):
        k, _, v = kv.partition('=')
        if k in seats:
            if v not in ('full', 'c56'):
                raise ValueError(f'{decks}: {k}=full|c56')
            seats[k] = v
        else:
            keep.append(kv)
    return f'{kind}:{seed}' + (':' + ','.join(keep) if keep else ''), seats


def sampler(spec):
    if spec not in _SAMPLERS:
        from bot.fullpool.decks import Sampler
        _SAMPLERS[spec] = Sampler.from_spec(spec)
    return _SAMPLERS[spec]


def case(rt, index, base, decks='x4s', *, opp_c56=False):
    """opp_c56: force the other seat's deck to C56 for this case (e.g. an RL league game against a search player)."""
    from bot.players.ours import x4s_setup
    if decks == 'x4s':
        return x4s_setup(rt, index, base)
    spec, seats = parse(decks)
    s = sampler(spec)
    seed, seat = base + index, index % 2
    own = s.deck(index, salt=f'own|{base}', c56_only=seats['own'] == 'c56')
    other = s.deck(index, salt=f'opp|{base}', c56_only=opp_c56 or seats['opp'] == 'c56')
    rng = random.Random(seed)
    rng.shuffle(own); rng.shuffle(other)
    return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own], deck_spec=decks)


def select(rt, decks='x4s', belief=None):
    """Per-process setup for a deck option: the belief prior the search players use (None = C56 catalog)."""
    if decks == 'x4s' and belief is None:
        return
    if belief is None:
        belief = parse(decks)[0]
    rt.belief_prior = None if belief == 'c56' else belief
    if belief != 'c56':
        sampler(belief)


def check_scope(rt, decks, games, start=0, base=0):
    """Raise unless every deck of the first cases is playable by the runtime (R.costs holds every card)."""
    if decks == 'x4s':
        return
    missing = sorted({c for i in range(start, start + min(games, 50)) for d in case(rt, i, base, decks)['decks']
                      for c in d if c not in rt.R.costs})
    if missing:
        raise ValueError(f'decks {decks!r} need cards outside this runtime ({missing[:8]}...): '
                         'use CLASHER_BOT_RUNTIME_PINS=r1-cards1 with its runtime root')
