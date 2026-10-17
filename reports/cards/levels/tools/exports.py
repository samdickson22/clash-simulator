"""Build/check the per-level native export cache of the selected runtime (LevelConfigs, locked) and print errors.

    (source env-fp.sh) python reports/cards/levels/tools/exports.py OUT.json 16,17
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def main():
    out_path, levels = Path(sys.argv[1]), [int(x) for x in sys.argv[2].split(',')]
    from bot.players.runtime import Runtime
    rt = Runtime()
    from bot.levels.match import level_configs
    lc = level_configs(rt)
    out = dict(cache=str(lc.dir))
    t = time.process_time()
    good, bad = lc.check11()
    out.update(supported11=len(good), unsupported11=bad)
    for level in levels:
        d = lc.load(level)
        out[f'L{level}'] = dict(cards=len(d['cards']), errors=d['errors'],
                                unavailable=sorted(c for c in good if lc.entry(c, level) is None))
        print(level, len(d['cards']), sorted(d['errors']), flush=True)
    out['cpu'] = time.process_time() - t
    out_path.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
