"""Replay the 200 frozen Stage 5 trace hashes with 1/2/4 native workers."""
import hashlib
import json
from pathlib import Path
import sys
import time
from dataclasses import replace
import qualify
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.c56_rollout_planner import C56RolloutPlanner

HERE = Path(__file__).resolve().parent
reference = json.loads((HERE.parent/'stage5/parity-r3.json').read_text())
assert reference['complete'] and len(reference['results']) == 200

def check(b, seat, builder, bots, scripts, cfg, index, search_cfg):
    start = time.perf_counter()
    hashes = []
    for threads in (1, 2, 4):
        # Large finite budget forces the anytime code even for one worker.
        p = C56RolloutPlanner(builder, bots, backend='native', seed=880000+index,
            native=scripts, native_config=cfg,
            config=replace(search_cfg, threads=threads, deadline_seconds=120.))
        action = p.select_action(b, seat, trace=True)
        got = hashlib.sha256(repr(p.last).encode()).hexdigest()
        want = reference['results'][index]
        assert got == want['trace_sha256'] and action == want['action'], (index, threads, got, want)
        assert not p.deadline_stats['truncated']
        hashes.append(got)
    return dict(index=index, action=action, trace_sha256=hashes[0], threads=[1,2,4], wall=time.perf_counter()-start)

qualify.check = check
qualify.plannerspace = DiscreteTileActionSpace()
sys.argv = [__file__, '--roots', '200', '--output', str(HERE/'parity.json')]
qualify.main()
