"""DECK SEARCH v3 game driver: paired deck arms on live-diag's L16 driver (bot/livediag/l16_cadence.py, unchanged).

One case = (seed, seat, Battle Log row, opponent policy). Every deck arm plays every case, so arms are paired.
Each (case, deck) is one bank entry; l16_cadence.run_worker plays it with player `res-wintp` (the live
LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint, deadlines cleared) and noise `clean`. Rows go to OUT/rows/
<entry>-00.json, keyed for analysis by entry id `<case id>:<deck>`.

Case draws (rng = random.Random(seed)):
- `freq`: a pool row uniformly over the eligible rows (= observed Battle Log frequency);
- `stratum:<name>`: uniformly over the rows of a named stratum (supplementary P.E.K.K.A / Hog cases for row B).
Our deck order: random.Random(f'{seed}:{deck}').shuffle; the opponent deck order: the case rng (same for all arms).
Levels: `account` = --our-levels (one level per owned card, King) vs the row's logged levels and King;
`l16` = every card and tower L16. No game is played by --plan.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import traceback
from pathlib import Path


def pekka_hog(row):
    return 'Pekka' in row['opp_deck'] or 'HogRider' in row['opp_deck']


def eligible_rows(population, leveled, exclude=()):
    out = []
    for i, row in enumerate(population):
        if any(c in row['opp_deck'] for c in exclude):
            continue
        if leveled and not (row.get('opp_levels') and all(row['opp_levels']) and row.get('opp_king_level')):
            continue
        out.append(i)
    return out


def make_cases(base, n, population, rows, opponent, draw, tag):
    from bot.fullpool.cards import engine_name
    cases = []
    for i in range(n):
        seed = base + i
        rng = random.Random(seed)
        source = rows[rng.randrange(len(rows))]
        row = population[source]
        deck = [engine_name(c) for c in row['opp_deck']]
        other = list(deck)
        rng.shuffle(other)
        lv = dict(zip(deck, row.get('opp_levels') or [None] * 8))
        cases.append(dict(case=f'{tag}-{i:04d}', seed=seed, seat=i % 2, opponent=opponent, draw=draw,
                          source_index=source, source_run=row.get('run'), pekka_hog=pekka_hog(row),
                          pekka='Pekka' in row['opp_deck'], hog='HogRider' in row['opp_deck'],
                          opponent_deck=other, opponent_levels=lv, opponent_king=row.get('opp_king_level')))
    return cases


def expand(cases, decks):
    entries = []
    for case in cases:
        for name, deck in decks.items():
            own = list(deck)
            random.Random(f"{case['seed']}:{name}").shuffle(own)
            entries.append(dict(case, id=f"{case['case']}:{name}", deck=name, own_deck=own))
    return entries


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--base', type=lambda s: int(s, 0), required=True)
    p.add_argument('--cases', type=int, required=True)
    p.add_argument('--tag', required=True, help='case id prefix, e.g. scr / A / Bsup')
    p.add_argument('--draw', default='freq', help="freq | stratum:pekka_hog")
    p.add_argument('--decks', type=Path, required=True, help='json {name: [8 cards]}')
    p.add_argument('--arms', default='', help='comma-separated subset of deck names (default: all)')
    p.add_argument('--pool', type=Path, required=True)
    p.add_argument('--leveled', action='store_true', help='only rows with logged card + King levels')
    p.add_argument('--exclude-card', default='', help='drop pool rows whose deck contains any of these cards (finals: GoblinHut)')
    p.add_argument('--opponent', default='LIVE-K4CW-r16-fp', choices=['LIVE-K4CW-r16-fp', 'R3a'])
    p.add_argument('--levels', default='account', choices=['account', 'l16'])
    p.add_argument('--our-levels', default='')
    p.add_argument('--vocab', type=Path, required=True)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--shard', default='', help='K[,K2..]/N over bank entries (several hosts, same bank)')
    p.add_argument('--skip', type=Path, default=None, help='resume: a file of entry ids already played elsewhere')
    p.add_argument('--plan', action='store_true', help='write bank.json and exit (no runtime, no game)')
    args = p.parse_args()
    assert 1 <= args.workers <= 40 and args.cases > 0
    assert (args.levels == 'account') == bool(args.our_levels)
    assert os.environ.get('PYTHONHASHSEED') == '0' and os.environ.get('NUMPY_MADVISE_HUGEPAGE') == '0'
    assert 'BOT_BELIEF_PRIOR' not in os.environ and 'CLASHER_LIVE_FAST' not in os.environ
    assert str(args.out).startswith('/mpac/sdicks02/jobs/clasher/bot-deckopt3/')
    assert not args.out.exists(), 'fresh out directory required'
    import l16_cadence as L  # the caller's PYTHONPATH pins live-diag's driver copy
    from sam_common import sha, dump, utc

    population = [json.loads(x) for x in args.pool.read_text().splitlines() if x.strip()]
    exclude = [c for c in args.exclude_card.split(',') if c]
    rows = eligible_rows(population, args.leveled, exclude)
    if args.draw.startswith('stratum:'):
        key = args.draw.split(':', 1)[1]
        assert key == 'pekka_hog'
        rows = [i for i in rows if pekka_hog(population[i])]
    decks = json.loads(args.decks.read_text())
    if args.arms:
        decks = {k: decks[k] for k in args.arms.split(',')}
    assert all(len(set(d)) == 8 for d in decks.values())
    cases = make_cases(args.base, args.cases, population, rows, args.opponent, args.draw, args.tag)
    if args.levels == 'account':
        ours = dict(x.split('=') for x in args.our_levels.split(','))
        assert 'King' in ours and all(c in ours for d in decks.values() for c in d)
        assert all(all(c.get('opponent_levels', {}).get(k) for k in c['opponent_deck']) and c['opponent_king'] for c in cases)
    entries = expand(cases, decks)
    skip = set(args.skip.read_text().split()) if args.skip else set()
    if args.shard:
        ks, n = args.shard.split('/')
        ks, n = {int(x) for x in ks.split(',')}, int(n)
        entries = [e for j, e in enumerate(entries) if j % n in ks]
    entries = [e for e in entries if e['id'] not in skip]
    for j, e in enumerate(entries):
        e['index'] = j
    args.out.mkdir(parents=True)
    (args.out / 'rows').mkdir()
    import bot.players.runtime as runtime_module
    source = Path(runtime_module.__file__).resolve().parents[2]
    bank = dict(created_utc=utc(), base=args.base, tag=args.tag, draw=args.draw, n_cases=args.cases, shard=args.shard,
                decks=decks, opponent=args.opponent, levels=args.levels, our_levels=args.our_levels,
                leveled=args.leveled, exclude_card=exclude, eligible_rows=rows, population_path=str(args.pool), population_sha256=sha(args.pool),
                vocab_path=str(args.vocab), vocab_sha256=sha(args.vocab), player='res-wintp', noise='clean',
                skipped=len(skip), source_checkout=str(source), driver_sha256=sha(__file__), l16_cadence_sha256=sha(L.__file__),
                host=os.uname().nodename, cases=entries)
    dump(args.out / 'bank.json', bank, True)
    print(json.dumps(dict(entries=len(entries), cases=len(cases), arms=len(decks), bank_sha256=sha(args.out / 'bank.json'))))
    if args.plan:
        return
    ns = argparse.Namespace(out=args.out, shard='', workers=args.workers, players='res-wintp', noise='clean',
                            levels=args.levels, our_levels=args.our_levels)
    pgid = os.getpgrp()
    reserved = 0
    for f in Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims').glob('lease-*'):
        try:
            n, g = map(int, f.read_text().split())
        except (OSError, ValueError):
            continue
        if g == pgid:
            reserved = max(reserved, n)
    assert reserved >= args.workers + 2, (reserved, args.workers)
    rt, strong, vocab = L.build_runtime(args.vocab)
    children = []
    for wid in range(args.workers):
        pid = os.fork()
        if pid == 0:
            try:
                L.run_worker(wid, ns, bank, rt, strong, vocab)
            except BaseException:
                traceback.print_exc()
                os._exit(1)
            os._exit(0)
        children.append(pid)
    statuses = {pid: os.waitpid(pid, 0)[1] for pid in children}
    dump(args.out / 'finished.json', dict(utc=utc(), statuses=statuses))
    assert not any(statuses.values()), statuses


if __name__ == '__main__':
    main()
