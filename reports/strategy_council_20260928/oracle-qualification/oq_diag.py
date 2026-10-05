"""Diagnostic: inspect the root bandit of a planner config on real game states.

For each snapshot and each seat with a playable action, report: root candidates,
arms visited, spread of per-arm mean leaf value, and how the returned action relates
to visits (unvisited / single-visit / most-visited). Writes cost/diag.json.
"""

from __future__ import annotations

import json
import statistics
import sys

import numpy as np

import oq_cost
import oq_lib
from clasher.rl import oracle_planner
from clasher.rl.train_recurrent import maybe_silence_stdio

names = sys.argv[1:] or ["default", "legacy", "greedy1", "roll_raw", "roll_ctr"]
players = json.loads((oq_lib.OQ_DIR / "batches.json").read_text())["players"]
ctx = oq_lib.Context()
snaps = []
for role, style, game in (("holdout", "balanced", 0), ("holdout", "defense", 1)):
    s, _, _ = oq_cost.collect_snapshots(ctx, role, style, game, every_ticks=250)
    snaps += s
env = ctx.envs("holdout", 0)[0]
space = env.action_space
no_op = space.no_op_action

created: list = []
_Orig = oracle_planner._PlannerNode


class _Node(_Orig):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        created.append(self)


oracle_planner._PlannerNode = _Node
_diag_path = oq_lib.OQ_DIR / "cost" / "diag.json"
out = json.loads(_diag_path.read_text()) if _diag_path.exists() else {}
for name in names:
    rows = []
    for b in snaps:
        legal = {p: np.flatnonzero(space.legal_action_mask(b, p)) for p in (0, 1)}
        seats = [p for p in (0, 1) if legal[p].size > 1]
        if not seats:
            continue
        created.clear()
        planner = oq_lib.make_planner(env, players[name], seed=11)
        with maybe_silence_stdio(True):
            chosen = planner.select_actions(b)
        root = created[0]
        node_visits = [
            sum(n.by_player[0].alpha.values()) + sum(n.by_player[0].beta.values())
            - 2.0 * len(n.by_player[0].alpha)
            for n in created
        ]
        tree_nodes = len(created)
        revisited = sum(v > 1.5 for v in node_visits[1:])
        for p in seats:
            bandit = root.by_player[p]
            visits = {a: bandit.alpha[a] + bandit.beta[a] - 2.0 for a in bandit.alpha}
            visited = {a: v for a, v in visits.items() if v > 0.5}
            means = {a: (bandit.alpha[a] - 1.0) / visits[a] for a in visited}
            c = chosen[p]
            vals = list(means.values())
            rows.append(
                {
                    "tick": int(b.tick),
                    "tree_nodes": tree_nodes,
                    "nonroot_nodes_revisited": revisited,
                    "seat": p,
                    "legal": int(legal[p].size),
                    "arms_seen": len(visits),
                    "arms_visited": len(visited),
                    "max_visits": max(visited.values()),
                    "value_min": min(vals),
                    "value_max": max(vals),
                    "value_sd": statistics.pstdev(vals),
                    "noop_visits": visited.get(no_op, 0.0),
                    "chosen_is_noop": c == no_op,
                    "chosen_visits": visits.get(c, 0.0),
                    "chosen_value": means.get(c),
                    "chosen_rank_by_value": (
                        1 + sum(v > means[c] for v in vals) if c in means else None
                    ),
                }
            )
    n = len(rows)
    out[name] = {
        "config": players[name],
        "root_decisions": n,
        "mean_legal": statistics.mean(r["legal"] for r in rows),
        "mean_tree_nodes": statistics.mean(r["tree_nodes"] for r in rows),
        "mean_nonroot_nodes_revisited": statistics.mean(r["nonroot_nodes_revisited"] for r in rows),
        "mean_arms_visited": statistics.mean(r["arms_visited"] for r in rows),
        "mean_max_visits": statistics.mean(r["max_visits"] for r in rows),
        "mean_value_spread": statistics.mean(r["value_max"] - r["value_min"] for r in rows),
        "mean_value_sd": statistics.mean(r["value_sd"] for r in rows),
        "chosen_unvisited_frac": sum(r["chosen_visits"] < 0.5 for r in rows) / n,
        "chosen_noop_frac": sum(r["chosen_is_noop"] for r in rows) / n,
        "chosen_is_best_value_frac": sum(r["chosen_rank_by_value"] == 1 for r in rows) / n,
        "chosen_mean_rank_by_value": statistics.mean(
            r["chosen_rank_by_value"] for r in rows if r["chosen_rank_by_value"]
        ) if any(r["chosen_rank_by_value"] for r in rows) else None,
        "rows": rows,
    }
    print(name, json.dumps({k: v for k, v in out[name].items() if k not in ("rows", "config")}), flush=True)
    oq_lib.write_json_atomic(oq_lib.OQ_DIR / "cost" / "diag.json", out)
