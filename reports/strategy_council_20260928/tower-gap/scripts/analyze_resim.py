"""Analyse resim outputs: validation vs extraction, kill attribution, damage bias vs real final HP, variant retention."""
import sys, json, glob, gzip
from collections import Counter, defaultdict
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
prefix = sys.argv[1] if len(sys.argv) > 1 else "resim300"
R = []
for p in sorted(glob.glob(str(HERE / f"data/{prefix}-w*.jsonl"))):
    R += [json.loads(l) for l in open(p) if l.strip()]
F = {}
with gzip.open(HERE / "data/payload_facts.jsonl.gz", "rt") as f:
    for line in f:
        r = json.loads(line); F[r["tag"]] = r
EXT = {(r["match_id"], r["side"]): r for r in map(json.loads, open(HERE / "data/sample300_extraction.jsonl"))}
base = {(r["match_id"], r["side"]): r for r in R if r["variant"] == "base" and "error" not in r}
for r in R:
    if r.get("same_as_base") and (r["match_id"], r["side"]) in base:
        r.update({k: v for k, v in base[(r["match_id"], r["side"])].items() if k != "variant"})
errors = [r for r in R if "error" in r]
out = {"runs": len(R), "errors": len(errors), "error_examples": [e["error"] for e in errors[:5]]}
# A. validation
ok = n = 0; sup_diff = []
for key, r in base.items():
    e = EXT[key]
    n += 1
    if e["cut_reason"] == "sim_kill_of_tower_standing_in_real":
        ok += bool(r["contradiction"]) and r["contradiction"][0] == e["cut_tick"]
    else:
        ok += (r["contradiction"] is None or r["contradiction"][0] >= e["cut_tick"])
    sup_diff.append(r["supervised_cut"] - e["supervised_rows"])
out["validation"] = {"n": n, "contradiction_matches_extraction": ok, "supervised_abs_diff_mean": float(np.mean(np.abs(sup_diff))) if sup_diff else None,
                     "retention_ext": sum(EXT[k]["supervised_rows"] for k in base) / max(1, sum(EXT[k]["possible"] for k in base)),
                     "retention_mine": sum(r["supervised_cut"] for r in base.values()) / max(1, sum(r["possible"] for r in base.values()))}
# B. attribution for the killed tower (base)
SPELLS = {"Fireball", "Log", "Rocket", "Earthquake", "Poison", "Tornado", "Arrows", "Zap", "Lightning", "RoyalDelivery",
          "BarbarianBarrel", "GiantSnowball", "Freeze", "GoblinCurse", "Vines", "Void", "TheLog", "ElectroSpirit"}
kill_share = Counter(); last_hit = Counter(); kind_share = Counter(); total = 0.0; all_dmg = Counter(); all_total = 0.0
per_kill = []
for r in base.values():
    for d in r["damage"]:
        all_dmg[d[4]] += d[3]; all_total += d[3]
    if not r["contradiction"]:
        continue
    t, pid, slot = r["contradiction"]
    ev = [d for d in r["damage"] if d[1] == pid and d[2] == slot and d[0] <= t]
    s = sum(d[3] for d in ev)
    src = Counter()
    for d in ev:
        src[d[4]] += d[3]
    for k, v in src.items():
        kill_share[k] += v / s
    if ev:
        last_hit[ev[-1][4]] += 1
    spell = sum(v for k, v in src.items() if k in SPELLS) / s
    kinds = Counter()
    for d in ev:
        kinds[d[5]] += d[3] / s
    for k, v in kinds.items():
        kind_share[k] += v
    per_kill.append({"match_id": r["match_id"], "t": t, "spell_share": spell, "top": src.most_common(1)[0][0], "top_share": src.most_common(1)[0][1] / s})
    total += 1
out["kills"] = int(total)
out["kill_damage_share_by_source_top20"] = {k: round(v / total, 4) for k, v in kill_share.most_common(20)}
out["last_hit_top15"] = dict(last_hit.most_common(15))
out["kill_damage_share_by_object_kind"] = {k: round(v / total, 4) for k, v in kind_share.most_common()}
pk = pd.DataFrame(per_kill)
if len(pk):
    out["kill_spell_share_mean"] = round(pk.spell_share.mean(), 4)
    out["kills_spell_majority"] = round((pk.spell_share > 0.5).mean(), 4)
    out["kill_top_source_share_median"] = round(pk.top_share.median(), 4)
out["all_tower_damage_share_top20"] = {k: round(v / all_total, 4) for k, v in all_dmg.most_common(20)}
# C. damage bias: princess HP lost fraction per side, sim (at end of nocut run, capped at real end) vs real final
PM = {11: 3052, 12: 3346, 13: 3668, 14: 4032, 15: 4424, 16: 4858}
bias = []
for r in base.values():
    f = F[r["match_id"]]
    end = r["playable_end_tick"]
    hp = [h for h in r["hp"] if h[0] <= end] or r["hp"]
    if r.get("hp_end") and r["hp_end"][0] <= end:
        hp = hp + [r["hp_end"]]
    tick, last = hp[-1]
    for pid, sd in enumerate(("team", "opponent")):
        fin = f[sd]["final"]; lvl = (f[sd]["tower_card"] or {}).get("level") or 16
        pm = PM.get(lvl, 4858); km = 4824 if lvl == 11 else 7728
        king_dead_real = (fin.get("king") or 0) <= 0
        real_p = 2.0 if king_dead_real else sum(1 - min(1, (fin.get(k) or 0) / pm) for k in ("princess_left", "princess_right"))
        sim_p = sum(1 - max(0, h) / 3052 for h in last[pid][:2])
        bias.append({"match_id": r["match_id"], "pid": pid, "sim_end_tick": tick, "reached_real_end": tick >= end - 25,
                     "real_lost": real_p, "sim_lost": sim_p, "overtime": f["timeline_seconds"] * 20 - 91 > 3600})
B = pd.DataFrame(bias)
if len(B):
    def summ(X):
        return {"n_sides": len(X), "real_lost_mean_towers": round(X.real_lost.mean(), 3), "sim_lost_mean_towers": round(X.sim_lost.mean(), 3),
                "share_sim_gt_real": round((X.sim_lost > X.real_lost + 1e-9).mean(), 3),
                "share_sim_lt_real": round((X.sim_lost < X.real_lost - 1e-9).mean(), 3),
                "abs_err_mean": round((X.sim_lost - X.real_lost).abs().mean(), 3)}
    out["damage_bias_all"] = summ(B)
    out["damage_bias_reached_real_end"] = summ(B[B.reached_real_end])
    out["damage_bias_ended_early"] = summ(B[~B.reached_real_end])
# D. variants
V = defaultdict(dict)
for r in R:
    if "error" in r or "supervised_cut" not in r:
        continue
    V[r["variant"]][(r["match_id"], r["side"])] = r
keys = set.intersection(*[set(v) for v in V.values()]) if V else set()
rng = np.random.default_rng(0)
kl = sorted(keys)
var_out = {}
for name, runs in V.items():
    sup = np.array([runs[k]["supervised_cut"] for k in kl]); pos = np.array([runs[k]["possible"] for k in kl])
    bsup = np.array([V["base"][k]["supervised_cut"] for k in kl])
    con = np.array([runs[k]["contradiction"] is not None for k in kl])
    boots = []
    for _ in range(2000):
        i = rng.integers(0, len(kl), len(kl))
        boots.append((sup[i].sum() - bsup[i].sum()) / pos[i].sum())
    var_out[name] = {"n": len(kl), "retention": round(sup.sum() / pos.sum(), 4), "simkill_contradiction_rate": round(con.mean(), 4),
                     "delta_vs_base_pts": round(100 * (sup.sum() - bsup.sum()) / pos.sum(), 2),
                     "delta_ci95_pts": [round(100 * np.percentile(boots, 2.5), 2), round(100 * np.percentile(boots, 97.5), 2)],
                     "other_cut_counts": dict(Counter(runs[k]["other_cut"] for k in kl))}
out["variants_paired"] = var_out
json.dump(out, open(HERE / f"data/{prefix}_analysis.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))

# E. timing-matched over/undershoot at t = 180 s (tick 3600) for matches whose real end is >= 180 s:
#    overtime matches had level crowns c = min(crowns) at 180 s; regulation-ended matches keep final counts.
def at180(runs_by_key, label):
    rows = []
    for (m, side), r in runs_by_key.items():
        if "hp" not in r:
            continue
        f = F[m]
        end_tick = f["timeline_seconds"] * 20 - 91
        early = end_tick < 3600 - 30
        ot = end_tick > 3600 and not early
        crowns = (f["team"]["crowns"], f["opponent"]["crowns"])
        samples = [h for h in r["hp"] if h[0] <= 3600]
        if r.get("hp_end") and r["hp_end"][0] <= 3600:
            samples.append(r["hp_end"])
        if not samples:
            continue
        tick, hp = samples[-1]
        ended_early = tick < 3600 - 100
        if ended_early and r["other_cut"] != "sim_game_over" and not (early and r["other_cut"] == "recorded_end"):
            continue  # stopped by a non-tower cut before 180 s
        for pid, sd in enumerate(("team", "opponent")):
            if ot:
                real_down = min(crowns)
            else:
                fin = f[sd]["final"]
                real_down = 3 if (fin.get("king") or 0) <= 0 else sum((fin.get(k) or 0) <= 0 for k in ("princess_left", "princess_right"))
            sim_down = 3 if hp[pid][2] <= 0 else sum(h <= 0 for h in hp[pid][:2])
            rows.append({"m": m, "pid": pid, "ot": ot, "early": early, "real": real_down, "sim": sim_down})
    X = pd.DataFrame(rows)
    if not len(X):
        return {}
    d = (X.sim - X.real).to_numpy(); g = pd.factorize(X.m)[0]
    rng2 = np.random.default_rng(1); ng = g.max() + 1; bs = []
    for _ in range(2000):
        pick = rng2.integers(0, ng, ng); w = np.bincount(pick, minlength=ng)[g]
        bs.append((d * w).sum() / w.sum())
    res = {"mean_crowns_diff_sim_minus_real": round(d.mean(), 3), "ci95": np.percentile(bs, [2.5, 97.5]).round(3).tolist(),
           "n_early_end_sides": int(X.early.sum()), "n_sides": len(X), "overshoot_share": round((X.sim > X.real).mean(), 4), "undershoot_share": round((X.sim < X.real).mean(), 4),
           "exact_share": round((X.sim == X.real).mean(), 4), "real_mean_down": round(X.real.mean(), 3), "sim_mean_down": round(X.sim.mean(), 3)}
    for ot in (True, False):
        Y = X[X.ot == ot]
        if len(Y):
            res[f"ot={ot}"] = {"n": len(Y), "over": round((Y.sim > Y.real).mean(), 4), "under": round((Y.sim < Y.real).mean(), 4),
                               "real_mean": round(Y.real.mean(), 3), "sim_mean": round(Y.sim.mean(), 3)}
    return res
out["at180"] = {name: at180(runs, name) for name, runs in V.items() if name in ("base", "tower_real", "rel", "evo2", "spell_ctd")}
# F. clamp: retention as a function of the overshoot threshold (excess damage / tower max HP)
if "clamp" in V:
    thr_res = {}
    ck = sorted(k for k in V["clamp"] if V["clamp"][k].get("row_ticks_valid") is not None)
    pos = sum(V["clamp"][k]["possible"] for k in ck)
    excess_frac = []
    for thr in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, float("inf")):
        sup = 0; cuts = 0
        for k in ck:
            r = V["clamp"][k]
            cut = None
            for t, pid, slot, cum, mx in r["excess_events"]:
                if cum > thr * mx:
                    cut = t; break
            ticks = np.asarray(r["row_ticks_valid"])
            sup += int((ticks < cut).sum()) if cut is not None else len(ticks)
            cuts += cut is not None
        thr_res[str(thr)] = {"retention": round(sup / pos, 4), "cut_share": round(cuts / len(ck), 4)}
    for k in ck:
        ev = V["clamp"][k]["excess_events"]
        if ev:
            per = {}
            for t, pid, slot, cum, mx in ev:
                per[(pid, slot)] = cum / mx
            excess_frac.append(max(per.values()))
    base_ck = [k for k in ck if k in V["base"]]
    out["clamp"] = {"n": len(ck), "thresholds": thr_res,
                    "base_retention_same_keys": round(sum(V["base"][k]["supervised_cut"] for k in base_ck) / max(1, sum(V["base"][k]["possible"] for k in base_ck)), 4),
                    "max_excess_frac_quantiles_when_clamped": np.quantile(excess_frac, [.1, .25, .5, .75, .9]).round(3).tolist() if excess_frac else None,
                    "share_runs_clamped": round(len(excess_frac) / max(1, len(ck)), 4),
                    "other_cut_counts": dict(Counter(V["clamp"][k]["other_cut"] for k in ck))}
json.dump(out, open(HERE / f"data/{prefix}_analysis.json", "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ("at180", "clamp") if k in out}, indent=1, default=str))

# G. projection to the full corpus: recovered share of the sample's sim-kill loss on the same keys
if "clamp" in out:
    ck = [k for k in V["clamp"] if k in EXT]
    pos = sum(EXT[k]["possible"] for k in ck)
    lost_sk = sum(max(0, EXT[k]["possible"] - EXT[k]["supervised_rows"]) for k in ck
                  if EXT[k]["cut_reason"] == "sim_kill_of_tower_standing_in_real")
    proj = {"sample_lost_to_simkill_pts": round(100 * lost_sk / pos, 2)}
    base_ret = out["clamp"]["base_retention_same_keys"]
    for thr, v in out["clamp"]["thresholds"].items():
        gain = 100 * (v["retention"] - base_ret)
        frac = gain / (100 * lost_sk / pos) if lost_sk else None
        proj[thr] = {"gain_pts": round(gain, 2), "recovered_share": round(frac, 3) if frac is not None else None,
                     "full_corpus_projection": round(74.55 + frac * 18.15, 1) if frac is not None else None}
    out["projection"] = proj
    json.dump(out, open(HERE / f"data/{prefix}_analysis.json", "w"), indent=1, default=str)
    print(json.dumps(proj, indent=1))
