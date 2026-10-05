"""Export A* route cases from the Python engine (unmodified src) for the Rust micro-port check.

Times the uncached Python `_native_grid_route` on each case and writes inputs + routes to
~/.cache/clasher-engine-speed/astar_cases.json. usage: PYTHONPATH=<repo>/src python es_astar_export.py N
"""
import json, random, sys, time
from pathlib import Path

from clasher import pathfinding as pf
from clasher.battle import BattleState
from clasher.player import PlayerState

n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
rng = random.Random(7)
b = BattleState(players=[PlayerState(player_id=0, tower_level=11), PlayerState(player_id=1, tower_level=11)])
towers = tuple(pf.native_building_cost_cells(b))
W, H = pf.STANDARD_PATH_WIDTH, pf.STANDARD_PATH_HEIGHT
profiles = [(lane, jump) for lane in range(0, 4) for jump in (False, True)]
cost_maps = {f"{l}_{int(j)}": [[pf._standard_path_cost_map(l, j)[(x, y)] for x in range(W)] for y in range(H)] for l, j in profiles}
cases = []
py_time = 0.0
for i in range(n):
    lane, jump = rng.choice([(0, False), (1, False), (2, False), (1, True), (2, True)])
    start = (rng.randrange(W), rng.randrange(H))
    goal = (rng.randrange(W), rng.randrange(H))
    cells = set(towers)
    for _ in range(rng.choice([0, 0, 1, 2])):  # extra 2x2..3x3 buildings
        cx, cy, r = rng.randrange(2, W - 3), rng.randrange(2, H - 3), rng.choice([2, 3])
        cells |= {(cx + dx, cy + dy) for dx in range(r) for dy in range(r)}
    cells = tuple(sorted(cells))
    base = pf._standard_path_cost_map(lane, jump)
    costs = dict(base)
    for c in cells:
        costs[c] = max(costs[c], 50)
    t0 = time.perf_counter()
    route = pf._native_grid_route(start, goal, costs.get)
    py_time += time.perf_counter() - t0
    cases.append({"lane": lane, "jump": jump, "start": start, "goal": goal, "cells": cells,
                  "route": route})
out = {"W": W, "H": H, "neighbors": pf._NATIVE_NEIGHBORS, "cost_maps": cost_maps, "cases": cases,
       "python_seconds": py_time, "python_us_per_route": 1e6 * py_time / n}
p = Path.home() / ".cache/clasher-engine-speed/astar_cases.json"
p.write_text(json.dumps(out))
print(f"{n} cases, python {1e6*py_time/n:.1f} us/route, mean route len {sum(len(c['route'] or []) for c in cases)/n:.1f}")
