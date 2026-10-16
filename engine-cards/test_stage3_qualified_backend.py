"""Replay saved Python qualification traces through the production native flag."""

import hashlib
import json
from pathlib import Path
import cloudpickle
import numpy as np
from differential import ES
from test_stage3 import fingerprint
from test_stage3_backend import Context, run, ScriptRolloutPlanner

ctx = Context()
env = ctx.envs("holdout", 0)[0]
bot = ctx.bot("balanced")
sb = ctx.strategy_bot("balanced")
roots = cloudpickle.loads(
    (
        Path.home() / ".cache/clasher-engine-speed/stage3-srp-search-snapshots.pkl"
    ).read_bytes()
)
source = ES / "results/stage3_search_rollouts_a.json"
qualified = json.loads(source.read_text())["results"]
assert len(qualified) == 200, len(qualified)
rows = []
for i in range(200):
    q = qualified[str(i)]
    b = roots[q["root_index"]]
    seat = q["seat"]
    env.battle = b
    legal = np.flatnonzero(
        env.action_space.legal_action_mask(b, seat) & env.get_action_mask(seat)
    )
    result, cpu = run(
        ScriptRolloutPlanner, env, bot, sb, b, seat, legal, 51000 + i, backend="native"
    )
    assert result["trace_sha256"] == q["trace_sha256"], (i, "trace")
    assert result["action"] == q["chosen"], (i, "action")
    assert result["counters"]["rollouts"] == q["candidates"]
    assert result["counters"]["rollout_ticks"] == q["rollout_ticks"]
    rows.append(dict(call=i, root_index=q["root_index"], result=result, cpu=cpu))
    if i % 20 == 0:
        print(i, "PASS", flush=True)
out = dict(
    fingerprint=fingerprint(),
    driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    qualification_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    results=rows,
)
(ES / "results/stage3_qualified_backend.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(
    "PASS 200 searchable qualification traces through native backend flag", flush=True
)
