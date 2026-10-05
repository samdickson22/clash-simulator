import gzip, json, math
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
def load():
    P = pd.read_json(HERE / "data/perspectives.jsonl.gz", lines=True)
    F = {}
    with gzip.open(HERE / "data/payload_facts.jsonl.gz", "rt") as f:
        for line in f:
            r = json.loads(line); F[r["tag"]] = r
    P["possible"] = np.ceil(P.playable_end_tick / 5).astype(int)
    P["lost"] = (P.possible - P.supervised_rows).clip(lower=0)
    P["learner_side"] = P.side
    P["sim_kill"] = P.cut_reason == "sim_kill_of_tower_standing_in_real"
    d = P.cut_detail
    P["kill_owner_rel"] = [("own" if c.get("owner") == s else "opp") if k else None for c, s, k in zip(d, P.seat, P.sim_kill)]
    P["kill_slot"] = [c.get("slot") if k else None for c, k in zip(d, P.sim_kill)]
    P["kill_owner_seat"] = [c.get("owner") if k else None for c, k in zip(d, P.sim_kill)]
    P["cut_s"] = P.cut_tick / 20.0
    P["end_s"] = P.playable_end_tick / 20.0
    facts = [F[m] for m in P.match_id]
    P["timeline_s"] = [f["timeline_seconds"] for f in facts]
    P["overtime"] = (P.timeline_s * 20 - 91) > 3600
    lv = P["info"].map(lambda i: i["deck_levels"])
    P["own_lvl_mean"] = [np.mean(l[s]) for l, s in zip(lv, P.seat)]
    P["opp_lvl_mean"] = [np.mean(l[1 - s]) for l, s in zip(lv, P.seat)]
    P["team_lvl"] = [np.mean(l[0]) for l in lv]; P["oppo_lvl"] = [np.mean(l[1]) for l in lv]
    P["tower_team"] = [f["team"]["tower_card"]["card_key"] if f["team"]["tower_card"] else None for f in facts]
    P["tower_oppo"] = [f["opponent"]["tower_card"]["card_key"] if f["opponent"]["tower_card"] else None for f in facts]
    P["tower_lvl_team"] = [f["team"]["tower_card"]["level"] if f["team"]["tower_card"] else None for f in facts]
    P["tower_lvl_oppo"] = [f["opponent"]["tower_card"]["level"] if f["opponent"]["tower_card"] else None for f in facts]
    P["game_mode"] = P["info"].map(lambda i: i["game_mode"]); P["battle_type"] = P["info"].map(lambda i: i["battle_type"])
    slugs = P["info"].map(lambda i: i["deck_slugs"])
    P["n_evo_team"] = [sum("-ev" in s for s in sl[0]) for sl in slugs]
    P["n_evo_oppo"] = [sum("-ev" in s for s in sl[1]) for sl in slugs]
    P["n_hero_team"] = [sum("-hero" in s for s in sl[0]) for sl in slugs]
    P["n_hero_oppo"] = [sum("-hero" in s for s in sl[1]) for sl in slugs]
    return P, F
PMAX = {11: 3052, 12: 3346, 13: 3668, 14: 4032, 15: 4424, 16: 4858, 0: 4858}
def real_tower_fracs(F, tag, seat):
    f = F[tag][("team", "opponent")[seat]]
    lvl = f["tower_card"]["level"] if f["tower_card"] else 16
    pm = PMAX.get(lvl, 4858)
    fin = f["final"]
    km = 4824 if lvl == 11 else 7728
    pl, pr = (fin.get("princess_left") or 0) / pm, (fin.get("princess_right") or 0) / pm
    return min(pl, pr), max(pl, pr), (fin.get("king") or 0) / km
