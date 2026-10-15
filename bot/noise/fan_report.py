"""Aggregate bot/noise/shadow.py FAN rows: per chain, regret per decision, agreement, outside share, and the
difference vs the unfiltered 'base' chain paired over games (95% bootstrap over games, 4000 resamples, seed 0).

    python -m bot.noise.fan_report DIR[,DIR...]
"""
from __future__ import annotations

import glob
import json
import random
import sys
from collections import defaultdict


def main():
    games = []
    for d in sys.argv[1].split(','):
        for p in glob.glob(d + '/games-*.jsonl'):
            for line in open(p):
                r = json.loads(line)
                if 'fan' in r:
                    games.append(r)
    tags = list(games[0]['fan']) if games else []
    print(f'{len(games)} games')

    def per_dec(g, tag, key):
        c = g['fan'].get(tag, {})
        if key == 'regret':
            # outside the truth work set counts as the worst scored regret of that game (conservative)
            return c.get('regret', 0.), c.get('n', 0)
        return c.get(key, 0), c.get('n', 0)

    for key in ('regret', 'agree', 'agree_play', 'outside'):
        print(f'== {key} per decision')
        base = {i: per_dec(g, 'base', key) for i, g in enumerate(games)}
        for tag in tags:
            num = sum(per_dec(g, tag, key)[0] for g in games)
            den = sum(per_dec(g, tag, key)[1] for g in games)
            line = f'{tag:22s} {num/max(1, den):.4f} (n={den})'
            if tag != 'base':
                diffs = [(per_dec(g, tag, key)[0] - base[i][0], base[i][1]) for i, g in enumerate(games)]
                rng = random.Random(0)
                tot = sum(n for _, n in diffs)
                est = sum(d for d, _ in diffs)/max(1, tot)
                bs = []
                for _ in range(4000):
                    s = [diffs[rng.randrange(len(diffs))] for _ in diffs]
                    bs.append(sum(d for d, _ in s)/max(1, sum(n for _, n in s)))
                bs.sort()
                line += f'  vs base {est:+.4f} [{bs[100]:+.4f}, {bs[3899]:+.4f}]'
            print(line)


if __name__ == '__main__':
    main()
