"""RoyaleSim-style replay-parity scoring (exploration re-implementation).

Follows RoyaleSim's examples/replay_parity/harness.rs (2026-10-13, commit 39e7d482):
- towers pair by (side, slot);
- other units are reduced to their ROOT card; within one (side, root) both sides are
  cut into GROUPS (units first seen on one tick together) and a truth group pairs with
  sim units first seen within PAIR_WINDOW ticks, preferring a pool of the same size,
  then the nearest in time; members are assigned by least total first-frame distance
  (exact up to 7 members, greedy beyond), ties broken by first-frame hp agreement;
- a UNIT-TICK is one pair (or unmatched unit) on one truth frame tick where at least
  one side has the unit alive; position columns count both-alive unit-ticks within
  250 / 500 / 1000 native units (a tile is 1000); hp exact counts both-alive equal hp;
  every fraction is over all of the row's unit-ticks (alive mismatches count as misses).
Differences: the truth here is sampled (native frames every 1-4 ticks, as in
RoyaleSim's corpus, which also has frame gaps); there is no reliable deploy-state
column, so "moving" drops each truth unit's first DEPLOY_TICKS ticks instead.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict

PAIR_WINDOW = 100
EXACT_MAX = 7
TOLS = (250, 500, 1000)
DEPLOY_TICKS = 20
EARLY_TICKS = 100  # short-horizon column: a truth unit's first 5 s


def _d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def assign(tp, sp, thp, shp):
    n = min(len(tp), len(sp))
    if n == 0:
        return []
    def cost(i, j):
        return _d2(tp[i], sp[j]), int(thp[i] != shp[j])
    if len(tp) <= EXACT_MAX and len(sp) <= EXACT_MAX:
        best = None
        if len(tp) >= len(sp):
            for perm in itertools.permutations(range(len(tp)), len(sp)):
                c = [cost(perm[k], k) for k in range(len(sp))]
                tot = (sum(x[0] for x in c), sum(x[1] for x in c))
                if best is None or tot < best[0]:
                    best = (tot, [(perm[k], k) for k in range(len(sp))])
        else:
            for perm in itertools.permutations(range(len(sp)), len(tp)):
                c = [cost(k, perm[k]) for k in range(len(tp))]
                tot = (sum(x[0] for x in c), sum(x[1] for x in c))
                if best is None or tot < best[0]:
                    best = (tot, [(k, perm[k]) for k in range(len(tp))])
        return best[1]
    cands = sorted((cost(i, j), i, j) for i in range(len(tp)) for j in range(len(sp)))
    ut, us, out = set(), set(), []
    for _, i, j in cands:
        if i in ut or j in us:
            continue
        ut.add(i); us.add(j); out.append((i, j))
    return out


def pair_units(truth, sim):
    """truth/sim: dict key -> obj with side, root, tower_slot, first_tick, rows{tick:(x,y,hp)}.
    Returns list of (truth_key|None, sim_key|None)."""
    pairs = []
    used_s = set()
    used_t = set()
    # towers
    tt = {(u.side, u.tower_slot): k for k, u in truth.items() if u.tower_slot is not None}
    st = {(u.side, u.tower_slot): k for k, u in sim.items() if u.tower_slot is not None}
    for key, tk in tt.items():
        sk = st.get(key)
        pairs.append((tk, sk)); used_t.add(tk)
        if sk is not None:
            used_s.add(sk)
    # groups per (side, root)
    tg = defaultdict(lambda: defaultdict(list))
    sg = defaultdict(lambda: defaultdict(list))
    for k, u in truth.items():
        if u.tower_slot is None:
            tg[(u.side, u.root)][u.first_tick].append(k)
    for k, u in sim.items():
        if u.tower_slot is None:
            sg[(u.side, u.root)][u.first_tick].append(k)
    for sr, groups in tg.items():
        pools = sorted(sg.get(sr, {}).items())
        free = {t: list(ks) for t, ks in pools}
        for t, members in sorted(groups.items()):
            n = len(members)
            cands = sorted((len(f) != n, abs(st_ - t), st_) for st_, f in free.items() if f and abs(st_ - t) <= PAIR_WINDOW)
            taken = []
            for _, _, st_ in cands:
                for sk in free[st_]:
                    if len(taken) >= n:
                        break
                    taken.append((st_, sk))
                if len(taken) >= n:
                    break
            if not taken:
                continue
            tp = [truth[k].rows[truth[k].first_tick][:2] for k in members]
            thp = [truth[k].rows[truth[k].first_tick][2] for k in members]
            sp = [sim[sk].rows[sim[sk].first_tick][:2] for _, sk in taken]
            shp = [sim[sk].rows[sim[sk].first_tick][2] for _, sk in taken]
            for mi, k in assign(tp, sp, thp, shp):
                st_, sk = taken[k]
                free[st_].remove(sk)
                pairs.append((members[mi], sk)); used_t.add(members[mi]); used_s.add(sk)
    for k in truth:
        if k not in used_t:
            pairs.append((k, None))
    for k in sim:
        if k not in used_s:
            pairs.append((None, k))
    return pairs


def new_row():
    return {"unit_ticks": 0, "both_alive": 0, "w250": 0, "w500": 0, "w1000": 0, "hp_exact": 0,
            "alive_mismatch": 0, "moving_ticks": 0, "moving_w250": 0,
            "early_ticks": 0, "early_w250": 0, "early_hp_exact": 0}


def score(truth, sim, ticks, card_name):
    """Returns {"towers": row, "no_towers": row, "per_card": {name: row}, "first_divergence": ...}."""
    rows = {"towers": new_row(), "no_towers": new_row()}
    per_card = defaultdict(new_row)
    first_div = None
    pairs = pair_units(truth, sim)
    for tk, sk in pairs:
        tu = truth.get(tk) if tk is not None else None
        su = sim.get(sk) if sk is not None else None
        ref = tu or su
        is_tower = ref.tower_slot is not None
        bucket = rows["towers" if is_tower else "no_towers"]
        card = "Tower" if is_tower else card_name(ref.root)
        pc = per_card[card]
        trows = tu.rows if tu else {}
        srows = su.rows if su else {}
        t_first = tu.first_tick if tu else None
        for t in ticks:
            a, b = trows.get(t), srows.get(t)
            if a is None and b is None:
                continue
            for r in (bucket, pc):
                r["unit_ticks"] += 1
            moving = tu is not None and t >= t_first + DEPLOY_TICKS
            early = tu is not None and not is_tower and t < t_first + EARLY_TICKS
            if moving:
                for r in (bucket, pc):
                    r["moving_ticks"] += 1
            if early:
                for r in (bucket, pc):
                    r["early_ticks"] += 1
            if a is None or b is None:
                for r in (bucket, pc):
                    r["alive_mismatch"] += 1
                continue
            d = math.sqrt(_d2(a, b))
            for r in (bucket, pc):
                r["both_alive"] += 1
                if d <= 250:
                    r["w250"] += 1
                    if moving:
                        r["moving_w250"] += 1
                    if early:
                        r["early_w250"] += 1
                if early and a[2] == b[2]:
                    r["early_hp_exact"] += 1
                if d <= 500:
                    r["w500"] += 1
                if d <= 1000:
                    r["w1000"] += 1
                if a[2] == b[2]:
                    r["hp_exact"] += 1
            if d > 1000 and not is_tower and (first_div is None or t < first_div[0]):
                first_div = (t, card)
    return {"towers": rows["towers"], "no_towers": rows["no_towers"], "per_card": dict(per_card),
            "first_divergence": first_div, "n_pairs": sum(1 for p in pairs if p[0] is not None and p[1] is not None),
            "n_truth": len(truth), "n_sim": len(sim)}


def add_rows(a, b):
    for k, v in b.items():
        a[k] = a.get(k, 0) + v
    return a


def pct(r, k):
    return 100.0 * r[k] / r["unit_ticks"] if r["unit_ticks"] else float("nan")
