"""Does a root snapshot's native-serialized config parse back equal (as a subset) to normalized R.config?"""
import gzip, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.players.runtime import Runtime
rt = Runtime()
from bot.search.lopp_fast import split_snapshot
base = json.loads(json.dumps(rt.R.config))
n = bad = 0
for line in gzip.open(sys.argv[1], 'rt'):
    r = json.loads(line)
    cfg = split_snapshot(r['snapshot'])[1]
    t0 = time.perf_counter(); d = json.loads(cfg); t1 = time.perf_counter()
    diffs = []
    for k, v in d.items():
        if k not in base:
            diffs.append(('extra key', k)); continue
        if isinstance(v, dict) and isinstance(base[k], dict):
            diffs += [(k, x) for x, y in v.items() if base[k].get(x) != y]
        elif v != base[k]:
            diffs.append((k, 'value'))
    t2 = time.perf_counter()
    n += 1; bad += bool(diffs)
    if diffs and bad <= 3:
        print('diff', diffs[:5])
        k, x = diffs[0]
        if isinstance(d.get(k), dict) and x in d[k]:
            a, b = d[k][x], base[k].get(x)
            def first(a, b, path=''):
                if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    return path, repr(a)[:80], repr(b)[:80]
                if isinstance(a, dict):
                    for kk in set(a) | set(b):
                        if a.get(kk) != b.get(kk):
                            return first(a.get(kk), b.get(kk), path + '/' + str(kk))
                if isinstance(a, list):
                    if len(a) != len(b): return path, len(a), len(b)
                    for i, (p, q) in enumerate(zip(a, b)):
                        if p != q: return first(p, q, path + f'[{i}]')
                return path, repr(a)[:80], repr(b)[:80]
            print('  first', first(a, b))
    if n >= 30:
        break
print(dict(roots=n, mismatching=bad, parse_ms=round(1e3 * (t1 - t0), 1), compare_ms=round(1e3 * (t2 - t1), 1), bytes=len(cfg)))
