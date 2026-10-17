"""Every registry spell constructed at level L via the levels path vs its level-11 registry object.

    (source env-fp.sh) python reports/cards/levels/tools/spell_audit.py OUT.json [16]

Expected differences: `level` and level-scaled numbers (ratio ~ multiplier(L)/multiplier(11)). Anything else
(None vs set, changed strings/tuples, numbers that do not scale) is listed as suspect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def main():
    out_path, level = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 16
    from bot.players.runtime import Runtime
    rt = Runtime()
    from bot.levels.match import install_engine_levels
    install_engine_levels()
    import clasher.dynamic_spells as ds
    from clasher.spells import SPELL_REGISTRY
    from clasher.stat_scaling import level_multiplier
    ratio = level_multiplier(level) / level_multiplier(11)
    loader = rt.R.builder.loader
    out, suspects = {}, {}
    for name, base in sorted(SPELL_REGISTRY.items()):
        stats = loader.get_card(name)
        if stats is None or getattr(stats, '_raw_entry', None) is None or base.name != name:
            continue
        try:
            new = ds.create_spell_from_json(stats._raw_entry, level=level)
        except Exception as ex:
            out[name] = dict(error=repr(ex)[:300])
            suspects[name] = ['error']
            continue
        diff, bad = {}, []
        a, b = vars(base), vars(new)
        for k in sorted(set(a) | set(b)):
            if k.startswith('_') or k == 'level':
                continue
            x, y = a.get(k), b.get(k)
            if x == y:
                continue
            diff[k] = [repr(x)[:120], repr(y)[:120]]
            scaled = (isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool)
                      and x > 0 and abs(y / x - ratio) < 0.03)
            if not scaled:
                bad.append(k)
        out[name] = dict(type=type(new).__name__, diff=diff)
        if bad:
            suspects[name] = bad
    Path(out_path).write_text(json.dumps(dict(level=level, ratio=ratio, spells=out, suspects=suspects), indent=1))
    print('spells', len(out), 'suspects', json.dumps(suspects))


if __name__ == '__main__':
    main()
