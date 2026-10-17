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
from pathlib import Path

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
    # Live full-pool switch gate (A/B, 2026-10-16): e16 vs the LIVE Battle Log decks; base drawn 19:12Z before any game.
    'LIVE-AB1': dict(base=2988209034608560, decks='e16bl', games=1600,
                     use='arm A aliased:K4L-R-gs-mpool vs arm B K4L-R-gs-mk1a1, paired; claim bank (fresh, unselected)'),
    # Deck-diverse strong-opponent row (BOT LEAD 2026-10-17: leaf/value gains must hold across OUR decks): own deck
    # rotates over DD1_OWN, opponent deck over the distinct Battle Log decks; base drawn 08:00Z before any game.
    'DD1': dict(base=3241892761760944, decks='dd1', games=800,
                use='deck-diverse gate row: our deck in DD1_OWN (s62, e16, Inferno pick, 5 Battle Log decks) vs LIVE-K4CW-r16 at L16'),
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


E16 = ('Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer')   # live e16 deck
S62 = ('Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant')        # Sam's live deck from s62
INFERNO = ('Valkyrie', 'Archers', 'Goblins', 'InfernoTower', 'Fireball', 'Giant', 'MiniPekka', 'Skeletons')   # deckopt2 pick
# 5 Battle Log decks for the deck-diverse row: random.Random(52648481096922).sample(distinct deck indices, 5), the seed
# from os.urandom on 05 2026-10-17T08:00Z -> indices 1, 28, 30, 64, 76 of battlelog_decks()
DD1_BL = (1, 28, 30, 64, 76)
BATTLELOG = (Path(__file__).resolve().parents[2] / 'reports/bot/fullpool/ab/opponent-decks-20261016.jsonl',
             '3a7c4e78afe1ade7')    # LIVE LEAD Battle Log, 91 opponent decks (sha256 prefix)
_BL = []


def battlelog_decks():
    if not _BL:
        import hashlib
        import json
        from bot.fullpool.cards import engine_name
        data = BATTLELOG[0].read_bytes()
        if not hashlib.sha256(data).hexdigest().startswith(BATTLELOG[1]):
            raise ValueError(f'{BATTLELOG[0]}: sha256 mismatch')
        _BL.extend(sorted(engine_name(c) for c in json.loads(l)['opp_deck']) for l in data.decode().splitlines() if l.strip())
    return _BL


def dd1_own():
    bl = battlelog_decks()
    return [list(S62), list(E16), list(INFERNO)] + [list(bl[i]) for i in DD1_BL]


def distinct_battlelog():
    out = []
    for d in battlelog_decks():
        if list(d) not in out:
            out.append(list(d))
    return out


def case(rt, index, base, decks='x4s', *, opp_c56=False):
    """opp_c56: force the other seat's deck to C56 for this case (e.g. an RL league game against a search player)."""
    from bot.players.ours import x4s_setup
    if decks == 'x4s':
        return x4s_setup(rt, index, base)
    if decks == 'dd1':
        # our deck dd1_own()[index % 8] (row label own_deck_id), opponent deck distinct Battle Log deck (index // 8) % N
        owns, opps = dd1_own(), distinct_battlelog()
        seed, seat = base + index, (index // len(owns)) % 2    # each deck alternates seats (not tied to index % 2)
        own, other = list(owns[index % len(owns)]), list(opps[(index // len(owns)) % len(opps)])
        rng = random.Random(seed)
        rng.shuffle(own); rng.shuffle(other)
        return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own], deck_spec=decks,
                    own_deck_id=index % len(owns))
    if decks.startswith('arch1:'):
        # our deck 'arch1:<Card>+...' vs a full-pool training-sampler deck that must contain an archetype core
        # (bot/fullpool/archetype.ARCH_CORES[index % 9]); same seed/seat/shuffle rule as x4s_setup
        from bot.fullpool.archetype import ARCH_CORES
        seed, seat = base + index, index % 2
        own = decks[6:].split('+')
        if len(own) != 8 or len(set(own)) != 8:
            raise ValueError(f'{decks}: need 8 distinct cards')
        arch, core = ARCH_CORES[index % len(ARCH_CORES)]
        other = sampler('fullpool:11433651:freq=b53b02a1fde4').deck(index, salt=f'arch|{base}', require=list(core))
        rng = random.Random(seed)
        rng.shuffle(own); rng.shuffle(other)
        return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own], deck_spec=decks,
                    archetype=arch)
    if decks == 'e16bl' or decks.startswith('bl:'):
        # our deck (e16, or 'bl:<Card>+<Card>+...' = 8 engine names) vs Battle Log opponent deck index % 91,
        # same seed/seat/shuffle rule as x4s_setup
        bl = battlelog_decks()
        seed, seat = base + index, index % 2
        own = list(E16) if decks == 'e16bl' else decks[3:].split('+')
        if len(own) != 8 or len(set(own)) != 8:
            raise ValueError(f'{decks}: need 8 distinct cards')
        other = list(bl[index % len(bl)])
        rng = random.Random(seed)
        rng.shuffle(own); rng.shuffle(other)
        return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own], deck_spec=decks)
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
        belief = ('fullpool:11433651:freq=b53b02a1fde4' if decks in ('e16bl', 'dd1') or decks.startswith(('bl:', 'arch1:'))
                  else parse(decks)[0])
    rt.belief_prior = belief  # preserve explicit c56: it must beat BOT_BELIEF_PRIOR
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
