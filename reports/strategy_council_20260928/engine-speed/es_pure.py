"""Torch-free engine driver: random-legal full matches on the unmodified scalar engine.

Runs under any interpreter that can import clasher.battle (CPython 3.12 / 3.14,
PyPy 3.11). Same workload as es_engine.py but with its own deterministic driver
(Python random for action choice) so digests can be compared across interpreters
and engine variants. Every --digest-every decisions the full battle digest is
recorded; identical digest lists == bit-identical trajectories.

Usage: PYTHONPATH=<repo>/src python -B es_pure.py --label X [--matches N] [--fast-path]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time

sys.dont_write_bytecode = True
from es_common import RESULTS, TRAIN_DECKS, battle_digest, host_info, write_json  # noqa: E402

import numpy as np  # noqa: E402

from clasher.battle import BattleState  # noqa: E402
from clasher.player import PlayerState  # noqa: E402
from clasher.rl.action_space import DiscreteTileActionSpace  # noqa: E402
from clasher.rl.deck_pool import apply_ordered_deck_to_player  # noqa: E402


def load_decks():
    payload = json.loads(TRAIN_DECKS.read_text())
    return [list(d["cards"][:8]) for d in payload["decks"]]


def new_battle(seed: int, decks, fast_path: bool) -> BattleState:
    r = random.Random(seed * 7 + 3)
    battle = BattleState(
        players=[PlayerState(player_id=0, tower_level=11), PlayerState(player_id=1, tower_level=11)],
        fast_path=fast_path,
        rng=random.Random(seed),
    )
    for pid in (0, 1):
        deck = list(r.choice(decks))
        r.shuffle(deck)
        apply_ordered_deck_to_player(battle.players[pid], deck)
    return battle


def play(seed: int, decks, space, *, fast_path: bool, deploy_prob: float, digest_every: int,
         interval: int = 5, max_ticks: int = 6001, snapshot_every: int = 0):
    battle = new_battle(seed, decks, fast_path)
    choose = random.Random(seed * 13 + 1)
    digests, snaps = [], []
    t_mask = t_step = c_mask = c_step = 0.0
    decisions = deploys = ent_sum = 0
    next_snap = snapshot_every
    while not battle.game_over and battle.tick < max_ticks:
        w0, p0 = time.perf_counter(), time.process_time()
        actions = []
        for pid in (0, 1):
            if choose.random() >= deploy_prob:
                actions.append(space.no_op_action)
                continue
            legal = np.flatnonzero(space.legal_action_mask(battle, pid, fast_path=False))
            actions.append(int(legal[choose.randrange(len(legal))]) if len(legal) else space.no_op_action)
        order = [0, 1]
        choose.shuffle(order)
        for pid in order:
            if actions[pid] != space.no_op_action:
                deploys += 1
            space.apply_action(battle, pid, actions[pid])
        w1, p1 = time.perf_counter(), time.process_time()
        for _ in range(interval):
            if battle.game_over or battle.tick >= max_ticks:
                break
            battle.step()
        w2, p2 = time.perf_counter(), time.process_time()
        t_mask += w1 - w0; c_mask += p1 - p0
        t_step += w2 - w1; c_step += p2 - p1
        decisions += 1
        ent_sum += len(battle.entities)
        if digest_every and decisions % digest_every == 0:
            digests.append(battle_digest(battle))
        if snapshot_every and battle.tick >= next_snap:
            snaps.append(battle.clone())
            next_snap += snapshot_every
    return {
        "seed": seed, "ticks": int(battle.tick), "decisions": decisions, "deploys": deploys,
        "mean_entities": ent_sum / max(1, decisions), "winner": battle.winner,
        "final_digest": battle_digest(battle), "digests": digests,
        "mask_wall": t_mask, "mask_cpu": c_mask, "step_wall": t_step, "step_cpu": c_step,
    }, snaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7100)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--fast-path", action="store_true")
    ap.add_argument("--deploy-prob", type=float, default=1.0)
    ap.add_argument("--digest-every", type=int, default=20)
    ap.add_argument("--clone", action="store_true")
    ap.add_argument("--label", required=True)
    args = ap.parse_args()
    decks = load_decks()
    space = DiscreteTileActionSpace(canonical_perspective=True)
    out = {"args": vars(args), "interpreter": sys.version, "implementation": sys.implementation.name,
           "host_before": host_info()}
    warm = []
    for w in range(args.warmup):
        # PyPy needs JIT warm-up; recorded separately.
        w0, p0 = time.perf_counter(), time.process_time()
        r, _ = play(args.seed - 1 - w, decks, space, fast_path=args.fast_path, deploy_prob=args.deploy_prob,
                    digest_every=0)
        warm.append({"ticks": r["ticks"], "wall": time.perf_counter() - w0, "cpu": time.process_time() - p0})
    out["warmup"] = warm
    matches, snaps = [], []
    w0, p0 = time.perf_counter(), time.process_time()
    for m in range(args.matches):
        r, s = play(args.seed + 1009 * m, decks, space, fast_path=args.fast_path, deploy_prob=args.deploy_prob,
                    digest_every=args.digest_every, snapshot_every=600 if args.clone else 0)
        matches.append(r)
        snaps += s
        print(f"match {m}: {r['ticks']} ticks ent {r['mean_entities']:.1f} step-cpu {r['step_cpu']:.1f}s",
              flush=True)
    wall, cpu = time.perf_counter() - w0, time.process_time() - p0
    ticks = sum(r["ticks"] for r in matches)
    step_cpu = sum(r["step_cpu"] for r in matches)
    mask_cpu = sum(r["mask_cpu"] for r in matches)
    out.update(matches=matches, ticks=ticks, wall=wall, cpu=cpu,
               ticks_per_s_wall=ticks / wall, ticks_per_s_cpu=ticks / cpu,
               step_only_ticks_per_s_cpu=ticks / step_cpu, mask_share_cpu=mask_cpu / cpu,
               host_after=host_info())
    if snaps:
        times = []
        for b in snaps:
            for _ in range(3):
                t0 = time.process_time()
                b.clone()
                times.append(time.process_time() - t0)
        out["clone_cpu_ms_mean"] = 1e3 * sum(times) / len(times)
        out["clone_entities"] = [len(b.entities) for b in snaps]
    write_json(RESULTS / f"pure_{args.label}.json", out)
    print(f"{sys.implementation.name} {sys.version.split()[0]}: {out['ticks_per_s_cpu']:.0f} ticks/s cpu "
          f"(step-only {out['step_only_ticks_per_s_cpu']:.0f}), wall {out['ticks_per_s_wall']:.0f}")


if __name__ == "__main__":
    main()
