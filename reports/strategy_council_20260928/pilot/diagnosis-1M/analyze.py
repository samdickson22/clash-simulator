"""Read-only learning-dynamics analysis of the v7r1 pilot (scripted arm, first 1M decisions).

Reads train-*.log, training-monitor.jsonl, opponents/*-outcomes.jsonl, the s2901
diagnostic evaluation, the human-comparison results/policy sims and the s2901
scripted demonstrations. Writes diagnosis-1M.json next to this file. Never writes
under the run directories. Run with the pilot-runtime-v1 venv (numpy needed):
  OMP_NUM_THREADS=1 nice -n 15 <venv>/bin/python -B analyze.py
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import math
import re
import statistics as st
from pathlib import Path

import numpy as np

ROOT = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
RUNS = ROOT / "pilot/v7r1-launch/runs"
HC = ROOT / "m0/human-comparison"
OUT = Path(__file__).resolve().parent / "diagnosis-1M.json"
SEEDS = ["s2901", "s2902", "s2903"]
DPU = 8192  # learner decisions per PPO update
CRITIC_WARMUP = 20
DIAG_DECISIONS = 1_000_000
COST = {"Knight": 3, "Goblins": 2, "Giant": 5, "Skeletons": 1, "Musketeer": 4, "Prince": 5,
        "HogRider": 4, "DarkPrince": 4, "IceSpirit": 1, "Cannon": 3, "Tesla": 4, "Fireball": 4,
        "Zap": 2, "Log": 2, "Archers": 3, "IceGolem": 2}
# Median legal tiles per held card (of 576), measured from 300 s2901 teacher games below.
FIELDS = ["update", "transitions", "reward", "abs_reward", "policy", "value", "entropy", "type_ent",
          "loc_ent", "card_ent", "mode_ent", "kl", "clip", "opt_steps", "kl_stop", "critic_warmup",
          "ev", "play", "noop", "noop_when_playable", "episodes", "wld", "lr"]


def num(v):
    try:
        return float(v)
    except ValueError:
        return v


def parse_updates(seed):
    rows = {}
    for f in sorted(glob.glob(str(RUNS / seed / "seed-*/scripted/train-*.log"))):
        for line in open(f):
            if not line.startswith("update="):
                continue
            kv = dict(re.findall(r"(\S+?)=(\S+)", line))
            r = {k: num(kv[k]) for k in FIELDS if k in kv}
            r["update"] = int(r["update"])
            w, l, d = map(int, str(r.pop("wld")).split("/"))
            r.update(wins=w, losses=l, draws=d, log=Path(f).name)
            # Location entropy is sum_k pi_k H(loc|k); dividing by the mean play
            # probability (~ sampled play rate) gives entropy per placement.
            r["loc_ent_per_play"] = r["loc_ent"] / r["play"] if r["play"] else None
            r["eff_tiles_per_play"] = math.exp(r["loc_ent_per_play"]) if r["play"] else None
            rows[r["update"]] = r  # a resumed run overwrites nothing (start_update follows)
    return [rows[k] for k in sorted(rows) if rows[k]["transitions"] <= DIAG_DECISIONS + DPU]


def parse_monitor(seed):
    out = []
    for line in open(glob.glob(str(RUNS / seed / "seed-*/scripted/training-monitor.jsonl"))[0]):
        d = json.loads(line)
        cs = d.get("card_share") or {}
        tot = sum(cs.values()) or 1.0
        held = d.get("held_play_share") or {}
        by_cost = collections.defaultdict(list)
        for c, v in held.items():
            by_cost[COST[c]].append(v)
        out.append({
            "update": d["update"], "learner_decisions": d["learner_decisions"],
            "mean_play_cost": sum(COST[c] * v for c, v in cs.items()) / tot,
            "play_share_cost_le2": sum(v for c, v in cs.items() if COST[c] <= 2) / tot,
            "play_share_cost_ge4": sum(v for c, v in cs.items() if COST[c] >= 4) / tot,
            "plays_per_match": d.get("plays_per_match"),
            "play_when_held_by_cost": {str(k): round(float(np.mean(v)), 4) for k, v in sorted(by_cost.items())} if len(held) > 3 else None,
            "play_when_held": {c: round(held[c], 4) for c in ("Zap", "Log", "Fireball", "IceGolem", "Archers", "Knight", "Cannon", "Tesla", "HogRider", "Giant", "Prince") if c in held} if len(held) > 3 else None,
        })
    return [r for r in out if r["learner_decisions"] <= DIAG_DECISIONS + DPU]


def warm_start_shas(seed):
    pool = json.load(open(glob.glob(str(RUNS / seed / "seed-*/scripted/opponents/pool.json"))[0]))
    lab = {}
    for e in pool["initial"]:
        lab[e["sha256"]] = "random-control (untrained)" if "random-control" in e["path"] else "warm-start copy"
    return lab


def outcomes(seed):
    lab = warm_start_shas(seed)
    rows = []
    for f in glob.glob(str(RUNS / seed / "seed-*/scripted/opponents/worker-*-outcomes.jsonl")):
        for line in open(f):
            rows.append(json.loads(line))
    note = None
    if seed == "s2901":
        # The s2901 run was resumed at update 13 without restoring RNG state and,
        # with the actor frozen in critic warm-up, replayed the first run's games
        # exactly.  Drop the first run's copies (assigned before 98,304 decisions).
        n0 = len(rows)
        rows = [r for r in rows if r["learner_decisions_at_assignment"] >= 98304]
        note = f"dropped {n0 - len(rows)} first-run rows replayed identically after resume"
    rows = [r for r in rows if r["learner_decisions_at_assignment"] < DIAG_DECISIONS]
    def kind(r):
        if r["kind"] == "script":
            return "script:" + r["style"]
        return lab.get(r["checkpoint_sha256"], r["kind"])
    width = CRITIC_WARMUP * DPU
    table = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        b = r["learner_decisions_at_assignment"] // width
        for k in (kind(r), "scripts (all)" if r["kind"] == "script" else None, "ALL"):
            if k:
                table[(b, k)][r["learner_result"]] += 1
    kinds = sorted({k for _, k in table})
    buckets = []
    for b in sorted({b for b, _ in table}):
        cell = {}
        for k in kinds:
            c = table[(b, k)]
            n = sum(c.values())
            if n:
                cell[k] = {"wins": c["win"], "games": n, "win_rate": round(c["win"] / n, 3)}
        lo, hi = b * width, (b + 1) * width
        buckets.append({"assigned_decisions": [lo, hi], "policy": "warm start (actor frozen)" if b == 0 else f"after PPO updates {b*20+1}-{(b+1)*20}", "cells": cell})
    wins_from_random = sum(1 for r in rows if kind(r).startswith("random") and r["learner_result"] == "win")
    wins = sum(1 for r in rows if r["learner_result"] == "win")
    return {"note": note, "buckets": buckets, "share_of_wins_from_random_control": round(wins_from_random / max(1, wins), 3),
            "share_of_games_vs_random_control": round(sum(1 for r in rows if kind(r).startswith("random")) / max(1, len(rows)), 3)}


def elixir_at_play_from_sim(path):
    el, cost, n = [], [], 0
    for line in gzip.open(path, "rt"):
        r = json.loads(line)
        if r["side"] != "candidate":
            continue
        n += 1
        for p in r["plays"]:
            el.append(p[4]); cost.append(COST.get(p[1], 0))
    q = np.quantile(el, [0.25, 0.5, 0.75])
    return {"sides": n, "plays": len(el), "elixir_at_play_q25_50_75": [round(float(x), 2) for x in q],
            "mean_card_cost": round(float(np.mean(cost)), 2), "share_cost_ge4": round(float(np.mean(np.array(cost) >= 4)), 3),
            "median_elixir_minus_cost": round(float(np.median(np.array(el) - np.array(cost))), 2)}


def teacher_stats(n_games=300):
    demo = RUNS / "s2901/seed-2901/initialization/scripted-demonstrations"
    names = None
    el_play, cost_play, nwp_n, nwp_d = [], [], 0, 0
    legal = collections.defaultdict(list)
    ck = None
    for f in sorted(demo.glob("game-*.npz"))[:n_games]:
        z = np.load(f)
        a, mask, g, h, ok = z["expert_actions"], z["action_masks"], z["global_features"], z["hand_ids"], z["expert_action_supervision_valid"]
        el = g[:, 5] * 10
        playable = mask[:, :2304].any(-1)
        for t in np.flatnonzero(ok):
            if playable[t]:
                nwp_d += 1; nwp_n += int(a[t] == 2304)
            if a[t] < 2304:
                el_play.append(el[t])
            for s in range(4):
                n = int(mask[t, s * 576:(s + 1) * 576].sum())
                if n:
                    legal[int(h[t, s])].append(n)
    tokens = ('<pad>', '<unknown>', 'Archer', 'ArcherArrow', 'Archers', 'Cannon', 'DarkPrince', 'Fireball', 'FireballSpell', 'Freeze', 'FreezeIceGolemite', 'Giant', 'Goblin_Stab', 'Goblins', 'HogRider', 'IceGolem', 'IceGolemite', 'IceSpirit', 'IceSpirits', 'IceSpiritsProjectile', 'IceWizardSlowDown', 'KingTower', 'Knight', 'Log', 'LogProjectile', 'LogProjectileRolling', 'Musketeer', 'MusketeerProjectile', 'Prince', 'Skeleton', 'Skeletons', 'Tesla', 'Tower', 'TowerCannonball', 'Zap', 'ZapFreeze')
    med = {tokens[k]: int(np.median(v)) for k, v in sorted(legal.items())}
    q = np.quantile(el_play, [0.25, 0.5, 0.75])
    return {"games": n_games, "plays_per_game": round(len(el_play) / n_games, 1),
            "noop_when_playable": round(nwp_n / nwp_d, 3),
            "elixir_at_play_q25_50_75": [round(float(x), 2) for x in q],
            "median_legal_tiles_when_held": med,
            "max_location_entropy_nats": {k: round(math.log(v), 2) for k, v in med.items()}}


def entropy_equilibrium(h_loc):
    """Joint entropy H = H(type) + sum_k pi_k H_k is maximized by pi_k ∝ exp(H_k), pi_noop ∝ 1."""
    return {"one_slot_legal": round(1 / (1 + math.exp(h_loc)), 4), "two_slots_legal": round(1 / (1 + 2 * math.exp(h_loc)), 4)}


def main():
    res = {"schema": "clasher.pilot-diagnosis-1M.v1", "decisions_per_update": DPU,
           "updates_for_1M": math.ceil(DIAG_DECISIONS / DPU), "critic_warmup_updates": CRITIC_WARMUP,
           "recipe": {"entropy_coef": 0.01, "entropy_target": "joint flattened distribution (type + p(play)-weighted location)",
                      "action_type_entropy_coef": None, "location_entropy_coef": None, "conditional_slot_entropy_coef": 0.0,
                      "anchor_policy_kl_coef": 0.0, "anchor_l2_coef": 0.0, "gamma": 1.0, "gae_lambda": 0.95,
                      "reward": "terminal +-1 plus 0.05 * objective-v1 tower/crown potential (no elixir or board term)",
                      "advantages": "normalized over all 8192 decisions incl. forced no-op states",
                      "target_kl": 0.02, "kl_check": "per 2-sequence minibatch (256 decisions)", "epochs": 2, "lr": 1e-4,
                      "opponents_first_1M": "50% scripts (balanced/pressure/defense), 50% initial policies (warm-start copy, untrained random-control)"},
           "seeds": {}}
    for seed in SEEDS:
        ups = parse_updates(seed)
        actor = [u for u in ups if not u["critic_warmup"]]
        summ = {
            "updates_parsed": len(ups), "last_update": ups[-1]["update"], "last_transitions": ups[-1]["transitions"],
            "actor_updates": len(actor),
            "mean_opt_steps_per_actor_update_of_64": round(float(np.mean([u["opt_steps"] for u in actor])), 1) if actor else None,
            "kl_early_stop_fraction": round(float(np.mean([u["kl_stop"] for u in actor])), 3) if actor else None,
        }
        def window(lo, hi):
            sel = [u for u in ups if lo <= u["update"] <= hi]
            if not sel:
                return None
            keys = ["policy", "value", "ev", "kl", "clip", "entropy", "type_ent", "mode_ent", "card_ent", "loc_ent", "loc_ent_per_play", "play", "noop_when_playable"]
            w = {k: round(float(np.mean([u[k] for u in sel if u[k] is not None])), 4) for k in keys}
            w["wins"] = sum(u["wins"] for u in sel); w["losses"] = sum(u["losses"] for u in sel)
            w["win_rate"] = round(w["wins"] / max(1, w["wins"] + w["losses"]), 3)
            return w
        wins = {f"{lo}-{hi}": window(lo, hi) for lo, hi in [(1, 20), (21, 40), (41, 60), (61, 80), (81, 100), (101, 123)]}
        res["seeds"][seed] = {
            "summary": summ,
            "windows_by_update": {k: v for k, v in wins.items() if v},
            "per_update": ups,
            "monitor": parse_monitor(seed),
            "training_outcomes": outcomes(seed),
            "reward_breakdown": {
                "sum_reward": round(sum(u["reward"] * DPU for u in ups), 1),
                "sum_terminal_wins_minus_losses": sum(u["wins"] - u["losses"] for u in ups),
            },
        }
        rb = res["seeds"][seed]["reward_breakdown"]
        rb["implied_shaping_total"] = round(rb["sum_reward"] - rb["sum_terminal_wins_minus_losses"], 1)
    t = teacher_stats()
    res["elixir_at_play"] = {
        "scripted_teachers_s2901_demos": t,
        "warm_start_policy_u12_sim (actor frozen = init)": elixir_at_play_from_sim(HC / "policy_sim_s2901-scripted-u12-smoke.jsonl.gz"),
        "policy_1M_sim": elixir_at_play_from_sim(HC / "policy_sim_policy_decisions_001000000.jsonl.gz"),
        "human_p16": {"elixir_at_play_q25_50_75": [4.91, 6.59, 8.53]},
    }
    s1 = res["seeds"]["s2901"]["per_update"]
    h0 = float(np.mean([u["loc_ent_per_play"] for u in s1 if u["update"] <= 20]))
    h1 = float(np.mean([u["loc_ent_per_play"] for u in s1 if u["update"] >= 104]))
    res["entropy_bonus_mechanism"] = {
        "claim": "With entropy_coef on the flattened joint, dH/dz_play = p(1-p)[H_loc + log((1-p)/p)] > 0 until p(play|playable) = sigmoid(H_loc); slot choice is pulled toward pi_k ∝ exp(H_loc,k), favouring cards with more legal tiles (Zap/Fireball 548 > Log 256 > troops 190 > buildings 117-128).",
        "H_loc_per_play_nats": {"updates_1_20": round(h0, 2), "updates_104_123": round(h1, 2)},
        "entropy_max_noop_when_playable": {"at_warm_start_H": entropy_equilibrium(h0), "at_1M_H": entropy_equilibrium(h1)},
        "observed_noop_when_playable": {"updates_1_20": round(float(np.mean([u["noop_when_playable"] for u in s1 if u["update"] <= 20])), 3),
                                         "updates_104_123": round(float(np.mean([u["noop_when_playable"] for u in s1 if u["update"] >= 104])), 3)},
        "push_at_warm_start": "0.01 * p(1-p) * (H_loc + log((1-p)/p)) at p=0.13, H_loc=2.7: ~0.005 per playable decision, equivalent to a constant ~+0.05 sigma normalized-advantage bonus for playing at every playable state",
    }
    ev = RUNS / "s2901/seed-2901/scripted/diagnostic-evaluation"
    cells = {}
    for f in sorted(ev.glob("*.json")):
        if f.name.endswith((".games.json", ".complete.json")):
            continue
        m = json.load(open(f))["metrics"]
        cells[f.stem] = {"wins": int(m["games"] - m["losses"] - m["draws"]), "games": int(m["games"]),
                         "noop_when_playable": round(m["candidate_noop_when_playable"], 3)}
    res["s2901_diagnostic_evaluation"] = cells
    OUT.write_text(json.dumps(res, indent=1, default=float))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
