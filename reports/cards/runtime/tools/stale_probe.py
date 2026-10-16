"""Pool config freshness (lopp_fast.LearnedPool.begin, review item 2): when a root's config changes between decisions
(here: every card's damage x2 in an in-memory copy of R.config), the workers' learned/native rollouts must follow it.

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> python stale_probe.py ROOTS.jsonl.gz

For one saved root, rollouts with a style-scripted opponent ('balanced') for WAIT + 4 plays: in-process
(batch_rollouts on the root itself) vs a 1-worker pool, for config A (R.config) then config B (modified), with
base_cut=True (the content-hash protocol) and base_cut=None (legacy: base shipped once, workers cut from it).
"""
import copy
import gzip
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def scale(obj, k):
    if isinstance(obj, dict):
        return {key: (v * k if key == 'damage' and isinstance(v, (int, float)) and not isinstance(v, bool) else scale(v, k))
                for key, v in obj.items()}
    if isinstance(obj, list):
        return [scale(v, k) for v in obj]
    return obj


def main():
    from bot.players.runtime import Runtime
    rt = Runtime()
    import clasher_core
    from bot.live.native_parity import rollout_args
    from bot.search import lopp_fast as lf
    from bot.search.lopp import batch_rollouts
    R, a = rt.R, rollout_args(rt.R)
    kw = dict(delay=a['command_delay'], opp_delay=a['opponent_delay'], horizon=a['horizon'], interval=a['interval'],
              elixir_weight=a['elixir_weight'])
    r = json.loads(next(iter(gzip.open(sys.argv[1], 'rt'))))
    head, _, tail = lf.split_snapshot(r['snapshot'])
    seat = r['seat']
    cfgB = dict(R.config, cards=scale(R.config['cards'], 2))        # every card's damage x2
    # fc-sized roots (the installed fc cut of each config), as reduce_fast's fc players ship them
    roots = {n: clasher_core.BattleState(lf.ConfigCache(json.dumps(c)).payload(head, tail))
             for n, c in (('A', R.config), ('B', cfgB))}
    out0 = {n: len(lf.split_snapshot(root.snapshot())[1]) for n, root in roots.items()}
    mask = list(R.native.public_mask(roots['A'], seat))
    keys = [2304] + sorted(random.Random(5).sample([i for i in range(2304) if mask[i]], 4))
    local = {n: [float(v).hex() for v in batch_rollouts(R.native, root, seat, keys, 'balanced', deadline=None,
                                                          tick0=r['tick'], **kw)] for n, root in roots.items()}
    out = dict(keys=keys, config_bytes=out0, local_A_ne_B=local['A'] != local['B'])
    for mode in (True, None):
        pool = lf.LearnedPool(1, R.native, (), getattr(R, 'meta', None), R.config)
        try:
            res = {}
            for n in ('A', 'B'):
                pool.begin(roots[n], seat, dict(kw, tick0=r['tick']), 'balanced', None, base_cut=mode)
                pool.submit(0, n, keys)
                got = pool.collect(None)[n]
                res[n] = [float(v).hex() for v in got] if got is not None else None
        finally:
            pool.close()
        out[f'base_cut={mode}'] = {n: res[n] == local[n] for n in res}
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
