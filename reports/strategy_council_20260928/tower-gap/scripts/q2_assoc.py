"""Q1/Q2 on extraction summaries: who loses the tower, when, and associations (logit, match-clustered SEs)."""
import sys, json
sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *
import statsmodels.formula.api as smf

P, F = load()
P = P[P.phase == "s117"].copy()
out = {}
S = P[P.sim_kill]
out["n_persp"] = len(P); out["n_simkill"] = len(S)
out["owner_slot_share"] = (S.groupby(["kill_owner_rel", "kill_slot"]).size() / len(S)).round(4).to_dict()
out["owner_seat_share"] = (S.groupby(["kill_owner_seat"]).size() / len(S)).round(4).to_dict()
out["cut_s_quantiles"] = S.cut_s.quantile([.1, .25, .5, .75, .9]).round(1).tolist()
out["cut_frac_quantiles"] = (S.cut_tick / S.playable_end_tick).quantile([.1, .25, .5, .75, .9]).round(3).tolist()
out["share_pre180_in_overtime_match"] = float(((S.cut_tick <= 3600) & S.overtime).mean())
out["share_overtime_all"] = float(P.overtime.mean()); out["share_overtime_simkill"] = float(S.overtime.mean())
# time bins
bins = [0, 60, 120, 180, 240, 300, 400]
out["cut_time_hist"] = pd.cut(S.cut_s, bins).value_counts().sort_index().astype(int).rename(str).to_dict()

# side-level long table: defender side D (own / opp of learner)
rows = []
for r in P.itertuples():
    lv = r.info["deck_levels"]; sl = r.info["deck_slugs"]
    for rel in ("own", "opp"):
        d = r.seat if rel == "own" else 1 - r.seat
        a = 1 - d
        fd = F[r.match_id][("team", "opponent")[d]]["final"]
        real_lost = 3 if (fd.get("king") or 0) <= 0 else sum((fd.get(k) or 0) <= 0 for k in ("princess_left", "princess_right"))
        rows.append(dict(match_id=r.match_id, rel=rel, y=int(r.sim_kill and r.kill_owner_rel == rel),
                         d_lvl=np.mean(lv[d]), a_lvl=np.mean(lv[a]),
                         d_evo=sum("-ev" in s for s in sl[d]), a_evo=sum("-ev" in s for s in sl[a]),
                         d_hero=sum("-hero" in s for s in sl[d]), a_hero=sum("-hero" in s for s in sl[a]),
                         real_lost=min(real_lost, 2), overtime=int(r.overtime), mode=r.game_mode,
                         capped=int(max(max(lv[0]), max(lv[1])) <= 11), d_deck=list(r.own_deck if d == r.seat else r.opponent_deck),
                         a_deck=list(r.opponent_deck if d == r.seat else r.own_deck), d_won=int((r.recorded_result == 1) == (d == r.seat))))
L = pd.DataFrame(rows)
L["lvl_diff"] = L.a_lvl - L.d_lvl
out["capped_share"] = float(L.capped.mean())
out["rate_by_capped"] = L.groupby("capped").y.mean().round(4).to_dict()
out["rate_by_rel"] = L.groupby("rel").y.mean().round(4).to_dict()
out["rate_by_real_lost"] = L.groupby("real_lost").y.mean().round(4).to_dict()
out["rate_by_overtime"] = L.groupby("overtime").y.mean().round(4).to_dict()
out["rate_by_d_won"] = L.groupby("d_won").y.mean().round(4).to_dict()
out["lvl_diff_dist"] = pd.cut(L.lvl_diff, [-9, -1.01, -0.26, 0.25, 1, 9]).value_counts().sort_index().astype(int).rename(str).to_dict()
out["rate_by_lvl_diff"] = L.groupby(pd.cut(L.lvl_diff, [-9, -1.01, -0.26, 0.25, 1, 9])).y.mean().round(4).rename(str).to_dict()
out["rate_by_d_evo"] = L.groupby(L.d_evo.clip(upper=3)).y.agg(["mean", "size"]).round(4).to_dict()
out["rate_by_a_evo"] = L.groupby(L.a_evo.clip(upper=3)).y.agg(["mean", "size"]).round(4).to_dict()
L["evo_diff"] = L.a_evo + L.a_hero - L.d_evo - L.d_hero
L["mode2"] = L["mode"].where(L["mode"].isin(["Ranked", "Ladder", "1v1 Battle"]), "other")
m = smf.logit("y ~ C(rel) + C(real_lost) + overtime + d_won + lvl_diff + d_evo + a_evo + d_hero + a_hero + capped + C(mode2)",
              data=L).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(L.match_id)[0]})
coef = pd.DataFrame({"coef": m.params, "lo": m.conf_int()[0], "hi": m.conf_int()[1], "p": m.pvalues}).round(4)
out["logit_main"] = coef.to_dict(orient="index")
print(coef)
# card presence: attacker card and defender card (one model each, many dummies, ridge-free; keep cards with >=1500 sides)
from collections import Counter
cnt = Counter(c for deck in L.a_deck for c in deck)
cards = [c for c, n in cnt.items() if n >= 1500]
for c in cards:
    L["A_" + c] = L.a_deck.map(lambda d, c=c: int(c in d))
    L["D_" + c] = L.d_deck.map(lambda d, c=c: int(c in d))
formula = "y ~ C(rel) + C(real_lost) + overtime + d_won + lvl_diff + d_evo + a_evo + " + " + ".join("A_" + c for c in cards) + " + " + " + ".join("D_" + c for c in cards)
m2 = smf.logit(formula, data=L).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(L.match_id)[0]}, maxiter=200)
c2 = pd.DataFrame({"coef": m2.params, "lo": m2.conf_int()[0], "hi": m2.conf_int()[1], "p": m2.pvalues})
c2 = c2[c2.index.str.match(r"^[AD]_")].sort_values("coef")
c2["n"] = [cnt[i[2:]] for i in c2.index]
out["logit_cards"] = c2.round(4).to_dict(orient="index")
print(c2.head(12).round(3)); print(c2.tail(15).round(3))
out = json.loads(json.dumps({k: ({str(kk): vv for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in out.items()}, default=str)); json.dump(out, open(HERE / "data/q1_q2_stats.json", "w"), indent=1, default=str)
for k, v in out.items():
    if not k.startswith("logit"):
        print(k, v)
