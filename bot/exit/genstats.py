"""Summarize bot.exit.generate output dirs: games, labels, teacher/student play rates, agreement, throughput.

    python -m bot.exit.genstats DIR [DIR ...]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main(dirs):
    for d in dirs:
        rows = [json.loads(line) for p in sorted(Path(d).glob('games-*.jsonl')) for line in p.read_text().splitlines()]
        ok = [r for r in rows if 'error' not in r]
        err = [r for r in rows if 'error' in r]
        by = defaultdict(lambda: defaultdict(float))
        for r in ok:
            g = by[r['opponent']]
            g['games'] += 1; g['score'] += r['score']; g['cpu'] += r['cpu_seconds']
            for s in r['shards'].values():
                for k in ('labelled', 'hit', 'student_default', 'teacher_play', 'behavior_play_at_label', 'agree',
                          'single_candidate', 'other_skip'):
                    g[k] += s[k]
        tot = defaultdict(float)
        for g in by.values():
            for k, v in g.items():
                tot[k] += v
        print(f'## {d}: {len(ok)} games ok, {len(err)} errors')
        for name, g in sorted(by.items()) + [('ALL', tot)]:
            n = max(1, g['labelled'])
            print(f"{name:>10}: games {int(g['games'])}, labels {int(g['labelled'])} (hit {g['hit']/n:.2%}, "
                  f"S-default {g['student_default']/n:.2%}, single-cand skipped {int(g['single_candidate'])}), "
                  f"teacher play {g['teacher_play']/n:.2%}, student play {g['behavior_play_at_label']/n:.2%}, "
                  f"agree {g['agree']/n:.2%}, student score {g['score']/max(1, g['games']):.3f}, "
                  f"labels/CPU-s {g['labelled']/max(1, g['cpu']):.2f}")
        for r in err[:3]:
            print('ERROR', r['game'], r['error'])


if __name__ == '__main__':
    main(sys.argv[1:])
