"""LV2 'dist' opponent-level table: what the live planner can know about an opponent's card levels without perception.

    python3 -m bot.fullpool.lv2_table --logs 'DIR/opponent-decks-20261017-s7[3-8]-royal-arena.jsonl' \
        --exclude-rows reports/bot/live-diag/pools/wintacc1-rows.json --out reports/bot/fullpool/lv2/opp-levels-dist.json

From the logged Battle Logs (read-only): every opponent card slot with a logged level, card names mapped to engine
names (bot.fullpool.cards.engine_name; evolved/hero forms count as the base card). Battles whose run id is one of the
sim bank's case rows (--exclude-rows: the pool rows the A/B draws its decks from) are left out, so a case deck's own
logged levels never enter its plan.
- cards[c] = {n, median} over the remaining battles; a card with n >= min_n (3) plans at its median.
- median_offset = median over the remaining battles of (median opponent card level - median of our logged deck
  levels); own[c] = our logged level of each card in our deck (the latest battle). A card with n < min_n plans at
  own[c] + median_offset if it is in our deck, else at own_median + median_offset (own_median = our deck's median
  level; the collection's levels outside our deck are not reliable enough to use, e.g. BabyDragon logged at 3).
- king = 9 (every remaining battle's logged opp_king_level is reported; the live planner uses the constant).
Only level numbers are written (no screenshots, names or paths beyond the inputs' file names).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

MIN_N = 3


def main(argv=None):
    from bot.fullpool.cards import engine_name
    ap = argparse.ArgumentParser()
    ap.add_argument('--logs', required=True)
    ap.add_argument('--exclude-rows', required=True)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    files = sorted(f for p in a.logs.split(',') for f in glob.glob(p))
    rows = [json.loads(l) for f in files for l in open(f) if l.strip()]
    excl = set(json.loads(Path(a.exclude_rows).read_text())['runs'])
    kept = [r for r in rows if r['run'] not in excl and r.get('opp_levels')]
    per, offsets, kings, last_own = defaultdict(list), [], Counter(), {}
    for r in sorted(kept, key=lambda r: r['run']):
        lv = [(engine_name(c), int(v)) for c, v in zip(r['opp_deck'], r['opp_levels'])
              if c is not None and v is not None]          # unidentified slots carry no name
        for c, v in lv:
            per[c].append(v)
        ours = [int(v) for v in r.get('our_levels') or [] if v is not None]
        if lv and ours:
            offsets.append(statistics.median(v for _, v in lv) - statistics.median(ours))
        kings[r.get('opp_king_level')] += 1
        for c, v in zip(r.get('our_deck') or [], r.get('our_levels') or []):
            if c is not None and v is not None:
                last_own[engine_name(c)] = int(v)
    allv = [v for vs in per.values() for v in vs]
    out = dict(
        source=dict(files=[Path(f).name for f in files], sha256={Path(f).name: hashlib.sha256(Path(f).read_bytes()).hexdigest()
                                                                 for f in files},
                    battles=len(rows), excluded_runs=sorted(excl & {r['run'] for r in rows}), kept_battles=len(kept),
                    exclude_rows=str(a.exclude_rows)),
        min_n=MIN_N, king=9, opp_king_levels_logged={str(k): v for k, v in sorted(kings.items(), key=str)},
        cards={c: dict(n=len(v), median=statistics.median(v)) for c, v in sorted(per.items())},
        median_offset=statistics.median(offsets) if offsets else 0.,
        own=dict(sorted(last_own.items())), own_median=statistics.median(last_own.values()) if last_own else 11,
        pooled_median=statistics.median(allv) if allv else 11)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('min_n', 'king', 'median_offset', 'own_median', 'pooled_median')}),
          'kept', len(kept), 'of', len(rows), 'cards', len(out['cards']),
          'n>=3', sum(e['n'] >= MIN_N for e in out['cards'].values()))


if __name__ == '__main__':
    main()
