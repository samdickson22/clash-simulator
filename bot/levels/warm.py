"""Build exact-match level exports before starting a live session.

Source bot/fullpool/run/env.sh, set CLASHER_LEVELS_CACHE to a writable directory,
then run under cpu_job: python -m bot.levels.warm --levels 16
Includes level-11 validation and Mirror's +1 exports (16 -> 11,16,17).
Each export includes its recursive spawn/death payloads. No runtime files change.
"""
from __future__ import annotations

import argparse
import json
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--levels', default='16', help='comma-separated card levels, 1..16; Mirror +1 is included')
    a = ap.parse_args()
    levels = set(map(int, a.levels.split(',')))
    if not levels or any(not 1 <= level <= 16 for level in levels):
        ap.error('levels must be in 1..16')
    from bot.players.runtime import Runtime
    from bot.levels.match import level_configs
    rt = Runtime()
    lc = level_configs(rt)
    for level in sorted({11} | levels | {level + 1 for level in levels}):
        t = time.perf_counter()
        hit = lc.path(level).exists()
        data = lc.load(level)
        print(json.dumps(dict(level=level, disk_hit=hit, cards=len(data['cards']), errors=data['errors'],
                              seconds=round(time.perf_counter()-t, 3), cache=str(lc.path(level)),
                              export_code_sha256=lc.export_code_sha256)), flush=True)
        if data['errors']:
            raise SystemExit(f'level {level} has export errors')
    good = lc.supported()
    expected = set(lc.load(11)['cards'])
    if good != expected:
        raise SystemExit(f'unsupported level-11 exports: {sorted(expected-good)}')
    print(f'ready: {len(good)} supported cards; cache {lc.dir}', flush=True)


if __name__ == '__main__':
    main()
