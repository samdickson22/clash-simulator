"""RL deck mixture (HP1 RL, reports/bot/hp1/RL-PREREG.md amendment 3): our deck by kind, opponent deck from a ladder mix.

Environment kinds (the decks field of BOT_RL_ENVS):
- 'sam':  our deck = BOT_RL_OWN_DECK (Sam's live deck, 8 engine names joined by '+'; a launch input that follows
          the live account's deck);
- 'meta': our deck = a known deck from the human corpus deck table BOT_RL_CORPUS_DECKS (jsonl {"deck": [8 engine
          names], "n": count}: every deck in the v2/T11 replay store plus the LIVE Battle Log decks), drawn ∝ n;
- 'rand': our deck = a random legal deck (uniform full-pool sampler, at most one champion).
The opponent deck always comes from BOT_RL_OPP_MIX = 'source@share|...', a source being 'corpus' (the deck table,
∝ n) or a bot/fullpool/decks.py sampler spec (default: corpus 40%, the frozen LIVE frequency table 30%, uniform
random legal 30%). In RoyaleSim games every card in
BOT_RL_RSIM_EXCLUDE (cards whose public rows the RoyaleSim translator vocab cannot map) is redrawn, on both seats,
deterministically. Case g: seed = bank + g, our seat g % 2, both decks shuffled by Random(seed), as banks.case.
"""
from __future__ import annotations

import hashlib
import math
import os
import random

KINDS = ('sam', 'meta', 'rand')
HOG26 = ('HogRider', 'Musketeer', 'Cannon', 'IceGolem', 'IceSpirit', 'Skeletons', 'Fireball', 'Log')
OWN_DECK = tuple(c for c in os.environ.get('BOT_RL_OWN_DECK', '').split('+') if c)
OPP_MIX_SPEC = os.environ.get('BOT_RL_OPP_MIX',
                              'corpus@.4|fullpool:11433651:freq=b53b02a1fde4@.3|fullpool-uniform:11433651@.3')
CORPUS_PATH = os.environ.get('BOT_RL_CORPUS_DECKS', '')
BELIEF = os.environ.get('BOT_RL_BELIEF', 'fullpool:11433651:freq=b53b02a1fde4')   # the search players' prior
RSIM_EXCLUDE = frozenset(c for c in os.environ.get('BOT_RL_RSIM_EXCLUDE', '').split(',') if c)
RANDOM_SPEC = 'fullpool-uniform:11433651'


def _mix(spec):
    out = []
    for t in spec.split('|'):
        s, share = t.rsplit('@', 1)
        share = float(share)
        if not (math.isfinite(share) and share >= 0):
            raise ValueError(f'BOT_RL_OPP_MIX entry {t!r}')
        out.append((s, share))
    if not out or abs(sum(x for _, x in out) - 1) > 1e-9:
        raise ValueError('BOT_RL_OPP_MIX shares must sum to 1')
    return tuple(out)


OPP_MIX = _mix(OPP_MIX_SPEC)


def _u(tag, g):
    return int.from_bytes(hashlib.sha256(f'bot-rl-deck|{tag}|{g}'.encode()).digest()[:8], 'big') / 2**64


def belief_spec():
    return BELIEF


_CORPUS, _CUM = [], []


def corpus():
    """[(deck, cumulative n)] from BOT_RL_CORPUS_DECKS; every deck legal (8 distinct pool cards, <= 1 champion)."""
    if not _CORPUS:
        import json
        from bot.fullpool.decks import CHAMPIONS, POOL
        if not CORPUS_PATH:
            raise ValueError('BOT_RL_CORPUS_DECKS is not set')
        acc = 0
        for line in open(CORPUS_PATH):
            if not line.strip():
                continue
            r = json.loads(line)
            d, n = sorted(r['deck']), int(r['n'])
            if len(d) != 8 or len(set(d)) != 8 or not set(d) <= set(POOL) or len(set(d) & set(CHAMPIONS)) > 1 or n < 1:
                raise ValueError(f'{CORPUS_PATH}: bad row {r}')
            acc += n
            _CORPUS.append((d, acc))
            _CUM.append(acc)
        if sorted(HOG26) not in [d for d, _ in _CORPUS]:
            raise ValueError(f'{CORPUS_PATH}: Hog 2.6 missing')
    return _CORPUS


def _draw(spec, g, bank, salt, exclude):
    """One deck from a source ('corpus' or a sampler spec); excluded cards are redrawn with the next salt k."""
    import bisect
    for k in range(1000):
        if spec == 'corpus':
            c = corpus()
            deck = c[bisect.bisect_right(_CUM, int(_u(f'{salt}|{bank}|{k}', g) * _CUM[-1]))][0]
        else:
            from bot.fullpool.banks import sampler
            deck = sampler(spec).deck(g, salt=f'rl|{salt}|{bank}|{k}')
        if not exclude & set(deck):
            return list(deck)
    raise ValueError(f'{spec}: no deck without {sorted(exclude)} in 1000 draws')


def own_deck(kind, g, bank, exclude=frozenset()):
    if kind == 'sam':
        if len(OWN_DECK) != 8 or len(set(OWN_DECK)) != 8:
            raise ValueError('BOT_RL_OWN_DECK needs 8 distinct engine names joined by +')
        if exclude & set(OWN_DECK):
            raise ValueError(f'own deck has excluded cards {sorted(exclude & set(OWN_DECK))}')
        return list(OWN_DECK)
    if kind == 'meta':
        return _draw('corpus', g, bank, 'own-meta', exclude)
    if kind == 'rand':
        return _draw(RANDOM_SPEC, g, bank, 'own-rand', exclude)
    raise ValueError(f'deck kind {kind!r}')


def opp_deck(g, bank, exclude=frozenset()):
    u, acc = _u('opp', g), 0.
    for spec, share in OPP_MIX:
        acc += share
        if u < acc:
            break
    return _draw(spec, g, bank, 'opp', exclude), spec


def case(kind, g, bank, rsim):
    from bot.fullpool.archetype import classify
    exclude = RSIM_EXCLUDE if rsim else frozenset()
    own = own_deck(kind, g, bank, exclude)
    other, spec = opp_deck(g, bank, exclude)
    seed, seat = bank + g, g % 2
    rng = random.Random(seed)
    own, other = list(own), list(other)
    rng.shuffle(own); rng.shuffle(other)
    return dict(seed=seed, seat=seat, decks=[own, other] if seat == 0 else [other, own], deck_spec=kind,
                opp_spec=spec, own_archetype=classify(own), opp_archetype=classify(other))
