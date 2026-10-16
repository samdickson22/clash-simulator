"""Full-pool deck sampler: valid 8-card decks from the 121 playable ladder cards, weighted toward the live arenas.

    from bot.fullpool.decks import Sampler
    s = Sampler.from_spec('fullpool:7')          # deterministic given the spec and the two pinned input files
    s.deck(i)                                    # i-th deck of the stream (independent of draw order), sorted names
    s.deck(i, c56_only=True)                     # same weights restricted to C56 (own seat while R.bots is C56)

Spec: 'fullpool:<seed>' = the default mixture; 'fullpool-uniform:<seed>' = uniform over the pool;
optional ':obs=<a>,next=<b>,floor=<c>' overrides the mixture weights (renormalised), e.g. 'fullpool:7:floor=0.3'.

Per-card weight (the Plackett-Luce weight of a slot draw), w = OBS*p_obs + NEXT*p_next + FLOOR*p_floor:
- p_obs   (OBS = 0.65): the LIVE Battle Log table (reports/live/loop/arena-card-freq.json). For each arena a with
          n_a battles, share s_a(c) = (count_a(c) + K*u_a(c)) / (n_a + K), K = 4 pseudo-battles, u_a(c) = 8/|U_a| if
          c is unlocked at or below arena a (ARENA-CARDS.md lists; Training Camp included), else 0. Arenas are pooled
          by battles, then normalised to a distribution over the pool.
- p_next  (NEXT = 0.25): cards first unlocked in the next arenas after the highest observed arena A
          (ARENA-CARDS.md): arena A+1 gets 2/3, A+2 gets 1/3, uniform within an arena.
- p_floor (FLOOR = 0.10): uniform over all 121, so no card has zero weight.
Draw: 8 distinct cards one at a time with probability proportional to w over the remaining cards; after a champion
the other champions get weight 0 (game rule: one champion slot). Deck i uses random.Random(int(sha256(spec|i))).

Inputs are read at runtime from pinned (path, sha256). Refresh: commit the new file and pass its sha via
BOT_FULLPOOL_FREQ='<path>@<sha256>' (or BOT_FULLPOOL_ARENAS for ARENA-CARDS.md), or update the pins below.
A file whose sha differs from its pin raises, so a refreshed table is always an explicit choice.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from pathlib import Path

from bot.fullpool.cards import C56, CHAMPIONS, POOL, engine_name

REPO = Path(__file__).resolve().parents[2]
FREQ = (REPO / 'reports/live/loop/arena-card-freq.json',
        '36bfa0cfc9912c7316fa366c89b8d96586dccef22e5af95b3bd2b7716fd3e58d')     # origin/main 70b27ec7
ARENAS = (REPO / 'reports/live/loop/ARENA-CARDS.md',
          '75a8a0ab6696fe3a5cdc27139d830adb4d0bbae53184b073153242eb64f4a0c6')   # origin/main 29cc2041
MIX = dict(obs=0.65, next=0.25, floor=0.10)
PSEUDO_BATTLES = 4.0
AHEAD = (2 / 3, 1 / 3)
DECK = 8


def _pinned(default, env):
    path, sha = default
    if os.environ.get(env):
        p, _, s = os.environ[env].rpartition('@')
        path, sha = Path(p), s
    data = Path(path).read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        raise ValueError(f'{path}: sha256 {got} != pinned {sha} (set {env}=<path>@<sha256> to refresh)')
    return data, str(path), sha


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower().replace("'", '').replace('.', '')).strip('-')


def parse_arena_cards(text):
    """ARENA-CARDS.md table -> ({arena index: [engine names unlocked there]}, {slug: index}, unresolved [(arena, name)])."""
    unlocks, slugs, unresolved = {}, {}, []
    for line in text.splitlines():
        cols = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cols) < 9 or not line.startswith('|'):
            continue
        m = re.fullmatch(r'(\d+) (.+)', cols[0])
        if m:
            idx, name = int(m[1]), m[2]
        elif cols[0] == 'Training Camp':
            idx, name = 0, 'Training Camp'
        else:
            continue
        slugs[_slug(name)] = idx
        card = re.sub(r'\s*\(.*?\)\s*', '', cols[2]).strip()
        hit = engine_name(card, strict=False)
        if hit in POOL:
            unlocks.setdefault(idx, [])
            if hit not in unlocks[idx]:
                unlocks[idx].append(hit)
        else:
            unresolved.append((idx, card))
    return unlocks, slugs, unresolved


def weights(mix=None):
    """{card: weight} over POOL (sums to 1) and a provenance dict."""
    mix = dict(MIX if mix is None else mix)
    total = sum(mix.values())
    mix = {k: v / total for k, v in mix.items()}
    fdata, fpath, fsha = _pinned(FREQ, 'BOT_FULLPOOL_FREQ')
    adata, apath, asha = _pinned(ARENAS, 'BOT_FULLPOOL_ARENAS')
    freq = json.loads(fdata)
    unlocks, slugs, unresolved = parse_arena_cards(adata.decode())
    upto = lambda a: sorted({c for i, cs in unlocks.items() if i <= a for c in cs})
    obs = dict.fromkeys(POOL, 0.)
    battles = 0
    observed = {}
    for slug, arena in sorted(freq['arenas'].items()):
        if slug not in slugs:
            raise ValueError(f'arena {slug!r} not in ARENA-CARDS.md')
        a, n = slugs[slug], float(arena['battles'])
        unlocked = upto(a)
        counts = {engine_name(c): float(v['count']) for c, v in arena['cards'].items()}
        bad = sorted(set(counts) - set(POOL))
        if bad:
            raise ValueError(f'{slug}: cards outside the pool {bad}')
        for c in POOL:
            u = DECK / len(unlocked) if c in unlocked else 0.
            obs[c] += n * (counts.get(c, 0.) + PSEUDO_BATTLES * u) / (n + PSEUDO_BATTLES)
        battles += n
        observed[slug] = a
    top = max(observed.values()) if observed else 0
    s = sum(obs.values())
    p_obs = {c: v / s for c, v in obs.items()} if s else dict.fromkeys(POOL, 0.)
    p_next = dict.fromkeys(POOL, 0.)
    seen = set(upto(top))
    ahead = []
    for j, share in enumerate(AHEAD, 1):
        new = [c for c in unlocks.get(top + j, []) if c not in seen]
        seen |= set(new)
        ahead.append(dict(arena=top + j, cards=new, share=share))
        for c in new:
            p_next[c] += share / len(new)
    z = sum(p_next.values())
    p_next = {c: v / z for c, v in p_next.items()} if z else p_next
    if not z:
        mix['obs'] += mix.pop('next'); mix['next'] = 0.
    w = {c: mix['obs'] * p_obs[c] + mix['next'] * p_next[c] + mix['floor'] / len(POOL) for c in POOL}
    z = sum(w.values())
    w = {c: v / z for c, v in w.items()}
    prov = dict(freq=dict(path=fpath, sha256=fsha), arenas=dict(path=apath, sha256=asha), mix=mix,
                pseudo_battles=PSEUDO_BATTLES, observed_arenas=observed, battles=battles, ahead=ahead,
                unresolved_arena_cards=unresolved)
    return w, prov


class Sampler:
    def __init__(self, spec, w, prov):
        self.spec, self.w, self.prov = spec, w, prov

    @classmethod
    def from_spec(cls, spec):
        kind, _, rest = spec.partition(':')
        seed, _, opts = rest.partition(':')
        int(seed)
        if kind == 'fullpool':
            mix = dict(MIX)
        elif kind == 'fullpool-uniform':
            mix = dict(obs=0., next=0., floor=1.)
        else:
            raise ValueError(f'deck spec {spec!r}: fullpool:<seed>[:k=v,...] or fullpool-uniform:<seed>')
        for kv in filter(None, opts.split(',')):
            k, v = kv.split('=')
            if k not in mix:
                raise ValueError(f'deck spec {spec!r}: unknown weight {k!r}')
            mix[k] = float(v)
        if kind == 'fullpool-uniform' and not opts:
            w = {c: 1 / len(POOL) for c in POOL}
            return cls(spec, w, dict(mix=mix))
        return cls(spec, *weights(mix))

    def rng(self, i, salt=''):
        h = hashlib.sha256(f'bot-fullpool-deck|{self.spec}|{salt}|{int(i)}'.encode()).digest()
        return random.Random(int.from_bytes(h[:8], 'big'))

    def deck(self, i, *, c56_only=False, salt='', require=()):
        """Sorted 8 distinct engine names. require: cards that must be in the deck (belief completion)."""
        rng = self.rng(i, salt)
        cards = [c for c in POOL if (c in C56 or not c56_only)]
        deck = list(dict.fromkeys(require))
        if len(deck) > DECK or len([c for c in deck if c in CHAMPIONS]) > 1:
            raise ValueError(f'required cards cannot form a deck: {deck}')
        while len(deck) < DECK:
            champ = any(c in CHAMPIONS for c in deck)
            left = [c for c in cards if c not in deck and not (champ and c in CHAMPIONS)]
            ws = [self.w[c] for c in left]
            u = rng.random() * sum(ws)
            acc = 0.
            for c, x in zip(left, ws):
                acc += x
                if u < acc:
                    break
            deck.append(c)
        return sorted(deck)

    def inclusion(self, n=20000, **kw):
        """Monte-Carlo per-card deck inclusion rate (for documentation)."""
        counts = dict.fromkeys(POOL, 0)
        for i in range(n):
            for c in self.deck(i, salt='inclusion', **kw):
                counts[c] += 1
        return {c: counts[c] / n for c in POOL}


def is_valid(deck, scope=POOL):
    deck = list(deck)
    return (len(deck) == DECK and len(set(deck)) == DECK and all(c in scope for c in deck)
            and sum(c in CHAMPIONS for c in deck) <= 1)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', default='fullpool:0')
    ap.add_argument('--n', type=int, default=20000)
    a = ap.parse_args()
    s = Sampler.from_spec(a.spec)
    inc = s.inclusion(a.n)
    print(json.dumps(dict(spec=a.spec, prov=s.prov, weights={c: round(s.w[c], 5) for c in POOL},
                          inclusion={c: round(v, 4) for c, v in sorted(inc.items(), key=lambda kv: -kv[1])},
                          examples=[s.deck(i) for i in range(5)]), indent=1))
