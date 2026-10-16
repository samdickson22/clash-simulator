"""Compare two cfg_dump outputs, ignoring only the Batch A keys at their inert defaults. Usage: cfg_diff.py A B"""
import json, sys
NEW = {'min_range': 0.0, 'death_first_update': False, 'first_update': False}
def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not (k in NEW and v == NEW[k])}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o
a, b = (json.load(open(p)) for p in sys.argv[1:3])
raw_equal = a == b
sa, sb = strip(a), strip(b)
diffs = []
def walk(x, y, path):
    if len(diffs) > 20: return
    if type(x) != type(y): diffs.append((path, str(x)[:80], str(y)[:80])); return
    if isinstance(x, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y: diffs.append((path + '/' + k, k in x, k in y))
            else: walk(x[k], y[k], path + '/' + k)
    elif isinstance(x, list):
        if len(x) != len(y): diffs.append((path, len(x), len(y))); return
        for i, (u, v) in enumerate(zip(x, y)): walk(u, v, f'{path}[{i}]')
    elif x != y: diffs.append((path, x, y))
walk(sa, sb, '')
print(json.dumps(dict(raw_equal=raw_equal, equal_modulo_inert_new_keys=not diffs, first_diffs=diffs[:20])))
