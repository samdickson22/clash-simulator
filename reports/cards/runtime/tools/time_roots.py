"""Native rollout cost per saved root: python time_roots.py ROOTS.jsonl.gz... (one process; run under the full pins).

Per root: entities, wall time of rollout_e1(WAIT, style) for the 3 styles at the frozen no-deadline budget (the same
call the K kernel makes per candidate x style), and of step(150). Prints per-deck medians and the top entity names
of the slowest roots."""
import gzip, json, statistics, sys, time
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.players.runtime import Runtime
rt = Runtime()
import clasher_core
from bot.live.native_parity import rollout_args
from bot.search.lopp_fast import split_snapshot
R, args = rt.R, rollout_args(rt.R)
per = defaultdict(list)
slow = []
for path in sys.argv[1:]:
    for line in gzip.open(path, 'rt'):
        r = json.loads(line)
        root = clasher_core.BattleState(r['snapshot'])
        head = split_snapshot(r['snapshot'])[0]
        ents = json.JSONDecoder().raw_decode(head, head.index('"entities":') + 11)[0]
        t0 = time.perf_counter()
        for s in ('balanced', 'pressure', 'defense'):
            R.native.rollout_e1(root, r['seat'], 2304, s, args['command_delay'], args['opponent_delay'], args['horizon'],
                                args['interval'], args['elixir_weight'], 1e6)
        ms = 1000 * (time.perf_counter() - t0) / 3
        c = root.clone(); t0 = time.perf_counter(); c.step(150); step = 1000 * (time.perf_counter() - t0)
        per[r['deck']].append((ms, step, len(ents)))
        slow.append((ms, r['deck'], Counter((e.get('stats') or {}).get('name') for e in ents)))
out = {d: dict(roots=len(v), rollout_ms_median=round(statistics.median(x[0] for x in v), 2),
               rollout_ms_p90=round(sorted(x[0] for x in v)[int(0.9 * len(v))], 2),
               step150_ms_median=round(statistics.median(x[1] for x in v), 2),
               entities_median=statistics.median(x[2] for x in v)) for d, v in sorted(per.items())}
print(json.dumps(out, indent=1))
for ms, d, names in sorted(slow, key=lambda x: -x[0])[:8]:
    print(round(ms, 1), d, dict(names.most_common(8)))
