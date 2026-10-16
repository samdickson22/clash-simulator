"""Pre-register row-sampled, C56-projected cases before any pilot games are played.

`created` is provenance, not part of case identity. Rebuilding an existing bank keeps
its timestamp; every other field must match. The source row order is significant.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random

from . import profile

REPO = Path(__file__).resolve().parents[2]


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def project(deck, catalog):
    """Maximum overlap, then frequency, then the catalog's literal card tuple."""
    cards = set(deck)
    best = min(catalog, key=lambda d: (-len(cards & set(d['cards'])),
                                      -d['frequency'], tuple(d['cards'])))
    return list(best['cards']), len(cards & set(best['cards']))


def build(rt, base, n, out_path, *, source=None):
    """Write an immutable bank, or return the identical existing bank."""
    if n < 0:
        raise ValueError('n must be nonnegative')
    from .scope import install
    scope = install(rt)
    original_catalog = rt.levels_original_prior['decks']
    source = Path(source) if source is not None else REPO / 'reports/live/loop/opponent-decks.jsonl'
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    pool = []
    for index, row in enumerate(rows):
        if row['opp_trophies'] < 600:
            continue
        deck, overlap = project(row['opp_deck'], original_catalog)
        if (deck, overlap) != project(row['opp_deck'], rt.PRIOR['decks']):
            raise ValueError(f'supported scope changes original projection for source row {index}')
        pool.append(dict(source_index=index, run=row['run'], original_deck=row['opp_deck'],
                         projected_deck=deck, overlap=overlap, opp_trophies=row['opp_trophies']))
    if not pool:
        raise ValueError('empty opponent pool')
    cases = []
    for i in range(n):
        seed, seat = base + i, i % 2
        rng = random.Random(seed)
        row = rng.choice(pool)
        opp, own = list(row['projected_deck']), list(profile.LIVE_DECK)
        rng.shuffle(opp)
        rng.shuffle(own)
        levels = profile.sample_opponent(rt, opp, random.Random(seed ^ 0x1E7E1))
        decks = [own, opp] if seat == 0 else [opp, own]
        prof = profile.true_profile(rt, decks, seat, levels)
        cases.append(dict(index=i, seed=seed, seat=seat, opponent=('R3a', 'v1')[(i // 2) % 2],
                          row_id=row['run'], row_source_index=row['source_index'], decks=decks,
                          profile=prof.as_json(), view=dict(own_levels=prof.cards[seat],
                          own_tower=prof.towers[seat], opp_tower=prof.towers[1-seat])))
    try:
        source_name = str(source.resolve().relative_to(REPO.resolve()))
    except ValueError:
        source_name = str(source.resolve())
    bank = dict(base=base, n=n, created=utcnow(), pool=pool,
                constants={k: getattr(profile, k) for k in
                           ('OWN_LEVELS', 'OWN_TOWER', 'COMMON_PRIOR', 'OPP_TOWER', 'RARE_OFFSET')},
                source=source_name,
                source_sha256=hashlib.sha256(raw).hexdigest(), scope=scope, cases=cases)
    # Normalize tuples before comparing with a JSON-loaded prior registration.
    bank = json.loads(json.dumps(bank))
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as stream:
            json.dump(bank, stream, indent=2, sort_keys=True)
            stream.write('\n')
    except FileExistsError:
        old = json.loads(path.read_text())
        if {k: v for k, v in old.items() if k != 'created'} != {
                k: v for k, v in bank.items() if k != 'created'}:
            raise FileExistsError(f'refusing to replace different bank: {path}') from None
        return old
    return bank


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source', type=Path, help='fixed population snapshot (use the registered receipt for the pilot)')
    a = ap.parse_args()
    if os.environ.get('PYTHONHASHSEED') != '0':
        ap.error('launch with PYTHONHASHSEED=0')
    from bot.players.runtime import Runtime
    bank = build(Runtime(), a.base, a.n, a.out, source=a.source)
    print(f"{a.out}: {bank['n']} cases, {len(bank['pool'])} pool rows", flush=True)


if __name__ == '__main__':
    main()
