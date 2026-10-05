"""Open-loop re-simulation pilot: replay recorded timed placements in the scalar engine.

Team = player 0 (bottom, native y < 16000), opponent = player 1 (top).  All
cards level 11, evo/hero forms -> base, tower troops -> Tower Princess.
Placements are issued at their recorded 20 Hz tick at native_world_units/1000.
Hand legality is relaxed (the recorded card is swapped into hand if the
reconstructed cycle disagrees) and elixir shortfalls are topped up; both are
counted.  Champion ability events call activate_champion_ability for the side.

Plausibility evidence (only end state + action stream are recorded):
  * contradicted_tower_kill: the sim destroys a tower that the recording shows
    standing at the end -> divergence no later than that sim time;
  * pocket evidence: a recorded troop/building placement in the enemy half
    proves the enemy tower on that side was down by then in the real match; if
    the sim tower is still up the placement is rejected -> divergence by then;
  * missing_real_kill: a tower down in the recording never falls in the sim.
Horizon = earliest contradiction time (or match end if none).

Run: OMP_NUM_THREADS=1 nice -n 15 .venv/bin/python resim_pilot.py [pool] [n]
"""

from __future__ import annotations

import collections
import gzip
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from card_map import SLUG_TO_GAMEDATA, base_slug  # noqa: E402
from clasher.arena import Position  # noqa: E402
from clasher.battle import BattleState  # noqa: E402
from clasher.rl.deck_pool import apply_ordered_deck_to_player  # noqa: E402

SIDE_PID = {"team": 0, "opponent": 1}
TOWER_SLOTS = ("left", "right", "king")
REAL_TOWER_KEYS = {"left": "princess_left", "right": "princess_right", "king": "king"}


def gd(slug):
    return SLUG_TO_GAMEDATA[base_slug(slug)[0]]


def initial_order(deck_names, plays):
    """First-appearance order of plays, then unplayed cards (approximate cycle)."""
    order = []
    for name in plays:
        if name not in order:
            order.append(name)
    order += [c for c in deck_names if c not in order]
    return order[:8]


def ensure_in_hand(player, name):
    if name in player.hand:
        return False
    if name in player.cycle_queue:
        player.cycle_queue.remove(name)
    for i, slot in enumerate(player.hand):
        if slot is None:
            player.hand[i] = name
            return True
    evicted = player.hand[0]
    player.hand[0] = name
    if evicted is not None:
        player.cycle_queue.appendleft(evicted)
    return True


def tower_state(b):
    out = {}
    for pid in (0, 1):
        p = b.players[pid]
        out[pid] = {"left": p.left_tower_hp, "right": p.right_tower_hp, "king": p.king_tower_hp}
    return out


def run_match(rec, donor=None):
    pl = rec["payload"]
    bt = pl["battle"]
    if donor is not None:
        # Control: keep this match's opponent, substitute the team deck and
        # team actions from a different match; compare against THIS result.
        dpl = donor["payload"]
        pl = dict(pl)
        pl["events"] = [e for e in rec["payload"]["events"] if e["side"] == "opponent"] + [e for e in dpl["events"] if e["side"] == "team"]
        bt = {**bt, "team": {**bt["team"], "players": [{**bt["team"]["players"][0], "deck": dpl["battle"]["team"]["players"][0]["deck"]}]}}
        pl["battle"] = bt
    decks = {}
    for side in ("team", "opponent"):
        decks[side] = [gd(c["card_key"]) for c in bt[side]["players"][0]["deck"]]
    events = sorted(pl["events"], key=lambda e: (e["replay_tick_20hz"], e["source_index"]))
    b = BattleState()
    loader = b.card_loader
    for side, pid in SIDE_PID.items():
        plays = [gd(e["card_key"]) for e in events if e["kind"] == "play_card" and e["side"] == side]
        apply_ordered_deck_to_player(b.players[pid], initial_order(decks[side], plays))
    real_end_s = float(pl["replay"]["duration"]["timeline_seconds"])
    real_final = {SIDE_PID[s]: bt[s]["players"][0]["final_tower_hitpoints"] for s in ("team", "opponent")}
    # Real destroyed: towers of side X with 0 HP at end.
    real_down = {pid: {slot for slot in TOWER_SLOTS if (real_final[pid].get(REAL_TOWER_KEYS[slot]) or 0) <= 0} for pid in (0, 1)}
    stats = {"plays": 0, "accepted": 0, "hand_forced": 0, "elixir_topups": 0, "elixir_shortfall_total": 0.0,
             "nudged": 0, "rejected": [], "abilities": 0, "abilities_ok": 0}
    contradictions = []
    sim_kill_time = {}
    prev = tower_state(b)
    ei = 0
    end_tick = int(math.ceil(real_end_s * 20)) + 1
    t_sim_end = None
    while b.tick <= end_tick + 20 * 60 and not b.game_over:
        while ei < len(events) and events[ei]["replay_tick_20hz"] <= b.tick:
            e = events[ei]
            ei += 1
            pid = SIDE_PID[e["side"]]
            t = e["replay_tick_20hz"] / 20.0
            if e["kind"] == "activate_ability":
                stats["abilities"] += 1
                stats["abilities_ok"] += bool(b.activate_champion_ability(pid))
                continue
            coords = (e.get("coordinates") or {}).get("native_world_units")
            if not coords:
                continue
            stats["plays"] += 1
            name = gd(e["card_key"])
            player = b.players[pid]
            stats["hand_forced"] += ensure_in_hand(player, name)
            play = b.resolve_card_play(pid, name)
            if play is not None:
                cost = play[1].mana_cost
                if player.elixir + 1e-9 < cost:
                    stats["elixir_topups"] += 1
                    stats["elixir_shortfall_total"] += cost - player.elixir
                    player.elixir = float(cost)
            x, y = coords["x"] / 1000.0, coords["y"] / 1000.0
            stats_card = loader.get_card(name)
            is_spell = str(getattr(stats_card, "card_type", "")).lower() == "spell"
            anywhere = bool(getattr(stats_card, "can_deploy_on_enemy_side", False))
            pocket = (not is_spell and not anywhere) and ((pid == 0 and y >= 15.0) or (pid == 1 and y < 17.0))
            ok = b.deploy_card(pid, name, Position(x, y))
            if not ok:
                for dx, dy in ((0, -1 if pid == 0 else 1), (1, 0), (-1, 0), (0, 1 if pid == 0 else -1), (1, -1 if pid == 0 else 1), (-1, -1 if pid == 0 else 1)):
                    if b.deploy_card(pid, name, Position(x + dx, y + dy)):
                        ok = True
                        stats["nudged"] += 1
                        break
            if ok:
                stats["accepted"] += 1
            else:
                enemy = 1 - pid
                lane = "left" if x < 9.0 else "right"
                reason = "pocket_tower_alive_in_sim" if pocket and getattr(b.players[enemy], f"{lane}_tower_hp") > 0 else "other"
                stats["rejected"].append({"t": t, "side": e["side"], "card": name, "xy": [x, y], "reason": reason})
                if reason == "pocket_tower_alive_in_sim":
                    contradictions.append({"t": t, "kind": "pocket_play_but_sim_tower_alive", "side": e["side"], "lane": lane})
            if pocket and ok:
                enemy = 1 - pid
                lane = "left" if x < 9.0 else "right"
                if lane not in real_down[enemy]:
                    contradictions.append({"t": t, "kind": "pocket_play_but_real_final_tower_alive(data)", "side": e["side"]})
        b.step()
        cur = tower_state(b)
        for pid in (0, 1):
            for slot in TOWER_SLOTS:
                if prev[pid][slot] > 0 and cur[pid][slot] <= 0:
                    sim_kill_time[(pid, slot)] = b.time
                    if slot not in real_down[pid]:
                        contradictions.append({"t": round(b.time, 2), "kind": "sim_kill_of_tower_standing_in_real", "owner": pid, "slot": slot})
        prev = cur
        if t_sim_end is None and b.tick >= end_tick:
            t_sim_end = {"crowns": [b.get_crown_count(0), b.get_crown_count(1)], "towers": tower_state(b), "game_over": b.game_over, "winner": b.winner}
    if t_sim_end is None:  # sim ended (3 crowns / tiebreak) before the real end
        t_sim_end = {"crowns": [b.get_crown_count(0), b.get_crown_count(1)], "towers": tower_state(b), "game_over": b.game_over, "winner": b.winner}
    for pid in (0, 1):
        for slot in real_down[pid]:
            if (pid, slot) not in sim_kill_time:
                contradictions.append({"t": None, "kind": "real_kill_missing_in_sim", "owner": pid, "slot": slot})
    real_crowns = [bt["team"]["crowns"], bt["opponent"]["crowns"]]
    real_winner = {"victory": 0, "defeat": 1}.get(bt["result"])
    sc = t_sim_end["crowns"]
    if sc[0] != sc[1]:
        sim_winner = 0 if sc[0] > sc[1] else 1
    elif b.game_over:
        sim_winner = b.winner
    else:
        # Crown tie at the real end time: lowest remaining tower HP tiebreak.
        lows = [min(v for v in t_sim_end["towers"][pid].values() if v > 0) for pid in (0, 1)]
        sim_winner = 0 if lows[0] > lows[1] else (1 if lows[1] > lows[0] else None)
    timed = [c["t"] for c in contradictions if c["t"] is not None and "(data)" not in c["kind"]]
    horizon = min(timed) if timed else None
    return {
        "tag": rec["tag"], "real_result": bt["result"], "real_crowns": real_crowns, "real_end_s": real_end_s,
        "decks": decks, "sim_crowns_at_real_end": sc, "sim_winner": sim_winner, "real_winner": real_winner,
        "winner_agree": sim_winner == real_winner, "crowns_exact": sc == real_crowns,
        "crown_abs_err": abs(sc[0] - real_crowns[0]) + abs(sc[1] - real_crowns[1]),
        "tower_down_agreement_6": sum(
            ((t_sim_end["towers"][pid][slot] <= 0) == (slot in real_down[pid])) for pid in (0, 1) for slot in TOWER_SLOTS) / 6.0,
        "real_towers_down": {str(k): sorted(v) for k, v in real_down.items()},
        "sim_kill_times": {f"{k[0]}:{k[1]}": round(v, 2) for k, v in sorted(sim_kill_time.items())},
        "first_contradiction_s": horizon, "contradictions": contradictions,
        "action_stats": stats,
    }


def main():
    pool = sys.argv[1] if len(sys.argv) > 1 else "p16"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    control = len(sys.argv) > 3 and sys.argv[3] == "control"
    path = HERE / f"payloads_{pool}_tier_a.jsonl.gz"
    recs = []
    with gzip.open(path, "rt") as f:
        for line in f:
            rec = json.loads(line)
            if rec["payload"]["battle"]["result"] not in ("victory", "defeat", "draw"):
                continue
            recs.append(rec)
    # Deterministic spread: every k-th record across shards.
    step = max(1, len(recs) // n)
    chosen = recs[::step][:n]
    results = []
    t0 = time.time()
    for ci, rec in enumerate(chosen):
        try:
            r = run_match(rec, donor=chosen[(ci + 1) % len(chosen)] if control else None)
        except Exception as exc:
            r = {"tag": rec["tag"], "error": f"{type(exc).__name__}: {exc}"}
        results.append(r)
        print(json.dumps({k: r.get(k) for k in ("tag", "real_result", "real_crowns", "sim_crowns_at_real_end", "winner_agree", "first_contradiction_s", "real_end_s", "error")}), flush=True)
    ok = [r for r in results if "error" not in r]
    decisive = [r for r in ok if r["real_winner"] is not None]
    summary = {
        "pool": pool, "pool_size": len(recs), "n": len(results), "errors": len(results) - len(ok),
        "winner_agreement": sum(r["winner_agree"] for r in decisive) / max(1, len(decisive)),
        "crowns_exact_rate": sum(r["crowns_exact"] for r in ok) / max(1, len(ok)),
        "mean_crown_abs_err": sum(r["crown_abs_err"] for r in ok) / max(1, len(ok)),
        "mean_tower_down_agreement_6": sum(r["tower_down_agreement_6"] for r in ok) / max(1, len(ok)),
        "control_cross_paired_team_actions": control,
        "contradiction_kinds_first": dict(collections.Counter(
            min((c for c in r["contradictions"] if c["t"] is not None and "(data)" not in c["kind"]), key=lambda c: c["t"])["kind"]
            for r in ok if r["first_contradiction_s"] is not None)),
        "matches_with_real_kill_missing_in_sim": sum(any(c["kind"] == "real_kill_missing_in_sim" for c in r["contradictions"]) for r in ok),
        "real_team_win_rate_in_sample": sum(r["real_winner"] == 0 for r in decisive) / max(1, len(decisive)),
        "sim_team_win_rate_in_sample": sum(r["sim_winner"] == 0 for r in decisive) / max(1, len(decisive)),
        "placement_accept_rate": sum(r["action_stats"]["accepted"] for r in ok) / max(1, sum(r["action_stats"]["plays"] for r in ok)),
        "hand_forced_rate": sum(r["action_stats"]["hand_forced"] for r in ok) / max(1, sum(r["action_stats"]["plays"] for r in ok)),
        "elixir_topup_rate": sum(r["action_stats"]["elixir_topups"] for r in ok) / max(1, sum(r["action_stats"]["plays"] for r in ok)),
        "first_contradiction_s": sorted(r["first_contradiction_s"] for r in ok if r["first_contradiction_s"] is not None),
        "first_contradiction_frac_of_match": sorted(round(r["first_contradiction_s"] / r["real_end_s"], 3) for r in ok if r["first_contradiction_s"] is not None),
        "matches_without_timed_contradiction": sum(r["first_contradiction_s"] is None for r in ok),
        "wall_s": round(time.time() - t0, 1),
    }
    (HERE / f"resim_{pool}_n{n}{'_control' if control else ''}.json").write_text(json.dumps({"summary": summary, "matches": results}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
