"""Policy-vs-human behaviour diagnostic for the Clasher council pilot.

Human side: IL_Replay matches from ../human-prior-scan, re-simulated open loop in
the scalar engine (same loop as resim_pilot.py) to recover the reconstructed hand
and the elixir at every recorded play.  Two human reference sets:

  * ``p16``  all 262 tier-(a) pilot-card matches (both sides human, 524 sides).
             In practice these are Hog 2.6 mirrors (523/524 sides).
  * ``ext``  sides from the G66/S120 tier-(a) payloads whose deck contains one of
             the pilot cards Hog 2.6 lacks (Giant, Prince, DarkPrince, Archers,
             Goblins, Tesla, Zap, Knight).  Card-conditional reference only: the
             rest of those decks is outside the pilot roster.

Policy side, two sources:

  * ``--monitor``   a run's training-monitor.jsonl (latest row = 20-update window):
                    card_share, held_play_share, plays/waits per match, plus match
                    length from opponents/worker-*-outcomes.jsonl.
  * ``--checkpoint`` with ``--sim-games N``: plays N games (inference only, CPU,
                    one torch thread) against the fixed public scripted pool
                    (balanced/pressure/defense, round-robin) in the scalar
                    simulator and records the same per-play data as the human
                    re-sim, so every metric (elixir, timing, placement, reaction)
                    is available.

Subcommands
  extract-human --pool p16|ext [--limit N]   build cache human_plays_<pool>.jsonl.gz
  sim-policy --checkpoint X --games N        build cache policy_sim_<tag>.jsonl.gz
  compare --monitor M [--policy-sim F]       write results JSON + print divergences

Run with the pilot runtime interpreter (read-only use; no bytecode, temp numba cache):
  RT=reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v1
  OMP_NUM_THREADS=1 nice -n 15 $RT/.venv/bin/python -B compare.py <subcommand> ...
The script sets CLASHER_ROOT / sys.path / NUMBA_CACHE_DIR itself when needed.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNCIL = HERE.parents[1]  # reports/strategy_council_20260928
SCAN = COUNCIL / "m0" / "human-prior-scan"
RUNTIME = COUNCIL / "m0" / "runtime-snapshots" / "pilot-runtime-v1"
TRAINING_DECKS = COUNCIL / "m0" / "data" / "roles_v2" / "training.json"
HOG26_DECKS = COUNCIL / "pilot" / "hog26-deployment.json"

PILOT16 = (
    "Archers", "Cannon", "DarkPrince", "Fireball", "Giant", "Goblins",
    "HogRider", "IceGolem", "IceSpirit", "Knight", "Log", "Musketeer",
    "Prince", "Skeletons", "Tesla", "Zap",
)
# Elixir costs of the pilot roster (runtime gamedata, level-independent).
COST = {"Archers": 3, "Cannon": 3, "DarkPrince": 4, "Fireball": 4, "Giant": 5, "Goblins": 2,
        "HogRider": 4, "IceGolem": 2, "IceSpirit": 1, "Knight": 3, "Log": 2, "Musketeer": 4,
        "Prince": 5, "Skeletons": 1, "Tesla": 4, "Zap": 2}
NON_HOG26 = ("Giant", "Prince", "DarkPrince", "Archers", "Goblins", "Tesla", "Zap", "Knight")
RAREST_FIRST = ("Goblins", "Prince", "DarkPrince", "Giant", "Archers", "Tesla", "Zap", "Knight")

ARENA_W, MID_Y = 18.0, 16.0
BRIDGES = ((3.5, 16.0), (14.5, 16.0))
PHASES = (("early", 0.0, 60.0), ("mid", 60.0, 120.0), ("double", 120.0, 180.0), ("overtime", 180.0, 1e9))
REACT_WINDOW_S = 20.0
REACT_FAST_S = (2.0, 4.0, 6.0)
REACTIVE_S = 6.0  # an own play within this many seconds after an opponent play counts as a response
DIST_BINS = (0.0, 2.0, 4.0, 7.0, 10.0, 1e9)
ELIXIR_BINS = (0.0, 2.0, 4.0, 6.0, 8.0, 9.5, 10.01)
TICK_S = 0.05


# ---------------------------------------------------------------------------
# environment / engine import helpers
# ---------------------------------------------------------------------------
def _engine_imports():
    """Import the scalar engine from the pilot runtime snapshot (read only)."""
    sys.dont_write_bytecode = True
    os.environ.setdefault("CLASHER_ROOT", str(RUNTIME))
    os.environ.setdefault("NUMBA_CACHE_DIR", tempfile.mkdtemp(prefix="human-comparison-numba-"))
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    for path in (str(SCAN), str(RUNTIME / "scripts"), str(RUNTIME / "src")):
        if path not in sys.path:
            sys.path.insert(0, path)


def canon(pid: int, x: float, y: float) -> tuple[float, float]:
    """Own side at the bottom (180-degree rotation for the top player)."""
    return (x, y) if pid == 0 else (ARENA_W - x, 2 * MID_Y - y)


# ---------------------------------------------------------------------------
# human extraction (open-loop re-sim)
# ---------------------------------------------------------------------------
def _load_payloads(pool: str) -> list[dict]:
    files = {"p16": ["payloads_p16_tier_a.jsonl.gz"], "ext": ["payloads_g66_tier_a.jsonl.gz", "payloads_s120_tier_a.jsonl.gz"]}[pool]
    seen, out = set(), []
    for name in files:
        with gzip.open(SCAN / name, "rt") as stream:
            for line in stream:
                rec = json.loads(line)
                if rec["tag"] in seen or rec["payload"]["battle"]["result"] not in ("victory", "defeat", "draw"):
                    continue
                seen.add(rec["tag"])
                out.append(rec)
    return out


def _deck(rec, side, gd):
    return [gd(c["card_key"]) for c in rec["payload"]["battle"][side]["players"][0]["deck"]]


def _select_ext(recs, gd, limit):
    """Matches with a non-Hog-2.6 pilot card in some deck, rarest cards first."""
    by_card = collections.defaultdict(list)
    for rec in recs:
        cards = set(_deck(rec, "team", gd)) | set(_deck(rec, "opponent", gd))
        for card in RAREST_FIRST:
            if card in cards:
                by_card[card].append(rec)
    chosen, tags = [], set()
    # Round-robin over cards (rarest first) so every card gets coverage under the limit.
    cursors = {card: 0 for card in RAREST_FIRST}
    while len(chosen) < limit and any(cursors[c] < len(by_card[c]) for c in RAREST_FIRST):
        for card in RAREST_FIRST:
            while cursors[card] < len(by_card[card]):
                rec = by_card[card][cursors[card]]
                cursors[card] += 1
                if rec["tag"] not in tags:
                    tags.add(rec["tag"])
                    chosen.append(rec)
                    break
            if len(chosen) >= limit:
                break
    return chosen


def _economy_advance(b, target_tick: int) -> None:
    """Advance only the elixir/phase/hand-refill clock (BattleState.fast_forward_idle_ticks rules)."""
    while b.tick < target_tick:
        dt = b.dt
        b.time += dt
        b.tick += 1
        b._update_battle_phases(elapsed_time=(b.tick - 1) * dt)
        regen = 0.93 if b.triple_elixir else (1.4 if b.double_elixir else 2.8)
        for player in b.players:
            player.regenerate_elixir(dt, regen)
            player.tick_card_refill(b._next_card_refill_cooldown_ms(), round(dt * 1000.0))


def resim_record(rec) -> list[dict]:
    """Re-simulate one match; return two side records (team, opponent)."""
    _engine_imports()
    from clasher.arena import Position
    from clasher.battle import BattleState
    from clasher.rl.deck_pool import apply_ordered_deck_to_player
    from resim_pilot import SIDE_PID, ensure_in_hand, gd, initial_order

    pl = rec["payload"]
    bt = pl["battle"]
    decks = {side: _deck(rec, side, gd) for side in SIDE_PID}
    events = sorted(pl["events"], key=lambda e: (e["replay_tick_20hz"], e["source_index"]))
    b = BattleState()
    for side, pid in SIDE_PID.items():
        plays = [gd(e["card_key"]) for e in events if e["kind"] == "play_card" and e["side"] == side]
        apply_ordered_deck_to_player(b.players[pid], initial_order(decks[side], plays))
    plays_by_pid = {0: [], 1: []}
    sim_live = True
    for e in events:
        # Advance the engine to the event tick. If the sim match ends first (e.g. a
        # simulated 3-crown) the rest of the match is continued economy-only:
        # the engine's elixir/phase/hand-refill rules without combat.
        while sim_live and b.tick < e["replay_tick_20hz"]:
            if b.game_over:
                sim_live = False
                break
            tick_before = b.tick
            b.step()
            if b.tick == tick_before:
                sim_live = False
        if not sim_live:
            _economy_advance(b, e["replay_tick_20hz"])
        pid = SIDE_PID[e["side"]]
        if e["kind"] == "activate_ability":
            if sim_live:
                b.activate_champion_ability(pid)
            continue
        coords = (e.get("coordinates") or {}).get("native_world_units")
        if not coords:
            continue
        name = gd(e["card_key"])
        x, y = coords["x"] / 1000.0, coords["y"] / 1000.0
        cx, cy = canon(pid, x, y)
        t = round(e["replay_tick_20hz"] * TICK_S, 2)
        if not sim_live:
            player = b.players[pid]
            forced = ensure_in_hand(player, name)
            hand = [c for c in list(player.hand)[:4] if c is not None]
            elixir = float(player.elixir)
            play = b.resolve_card_play(pid, name)
            cost = float(play[1].mana_cost) if play is not None else 0.0
            topup = player.elixir + 1e-9 < cost
            player.elixir = max(0.0, max(player.elixir, cost) - cost)
            if name in player.hand:
                player.hand[player.hand.index(name)] = None
                player.cycle_queue.append(name)
            plays_by_pid[pid].append([t, name, cx, cy, round(elixir, 3), hand, None, bool(forced), bool(topup)])
            continue
        player = b.players[pid]
        forced = ensure_in_hand(player, name)
        hand = [c for c in list(player.hand)[:4] if c is not None]
        elixir = float(player.elixir)
        play = b.resolve_card_play(pid, name)
        topup = False
        if play is not None:
            cost = play[1].mana_cost
            if player.elixir + 1e-9 < cost:
                topup = True
                player.elixir = float(cost)
        ok = b.deploy_card(pid, name, Position(x, y))
        if not ok:
            for dx, dy in ((0, -1 if pid == 0 else 1), (1, 0), (-1, 0), (0, 1 if pid == 0 else -1)):
                if b.deploy_card(pid, name, Position(x + dx, y + dy)):
                    ok = True
                    break
        plays_by_pid[pid].append([t, name, cx, cy, round(elixir, 3), hand, bool(ok), bool(forced), topup])
    duration = float(pl["replay"]["duration"]["timeline_seconds"])
    res = bt["result"]
    out = []
    for side, pid in SIDE_PID.items():
        other = 1 - pid
        result = {"victory": "win", "defeat": "loss"}.get(res, "draw")
        if side == "opponent" and result != "draw":
            result = "loss" if result == "win" else "win"
        out.append({
            "match": rec["tag"], "side": side, "pid": pid, "deck": decks[side],
            "opp_deck": decks["opponent" if side == "team" else "team"],
            "duration_s": duration, "result": result,
            "plays": plays_by_pid[pid],
            "opp_plays": [p[:4] for p in plays_by_pid[other]],
        })
    return out


def cmd_extract_human(args):
    _engine_imports()
    from resim_pilot import gd

    recs = _load_payloads(args.pool)
    if args.pool == "ext":
        recs = _select_ext(recs, gd, args.limit or 600)
    elif args.limit:
        recs = recs[: args.limit]
    out_path = HERE / f"human_plays_{args.pool}.jsonl.gz"
    tmp = out_path.with_suffix(".tmp")
    t0 = time.time()
    n_err = 0
    with gzip.open(tmp, "wt") as stream:
        for i, rec in enumerate(recs):
            try:
                for side_rec in resim_record(rec):
                    stream.write(json.dumps(side_rec) + "\n")
            except Exception as exc:  # keep going; count failures
                n_err += 1
                print(f"error {rec['tag']}: {type(exc).__name__}: {exc}", flush=True)
            if (i + 1) % 25 == 0:
                print(f"{args.pool}: {i + 1}/{len(recs)} matches, {time.time() - t0:.0f}s", flush=True)
    tmp.replace(out_path)
    print(json.dumps({"pool": args.pool, "matches": len(recs), "errors": n_err, "out": str(out_path), "wall_s": round(time.time() - t0, 1)}))


# ---------------------------------------------------------------------------
# policy simulation (inference only)
# ---------------------------------------------------------------------------
def cmd_sim_policy(args):
    _engine_imports()
    import torch

    torch.set_num_threads(1)
    from clasher.rl import eval as ev
    from clasher.rl.common import NUM_TILES
    from clasher.rl.selfplay_env import SelfPlayBattleEnv

    deck_pools = {"hog26": HOG26_DECKS, "training": TRAINING_DECKS}
    candidate_decks = Path(deck_pools.get(args.candidate_decks, args.candidate_decks))
    device = torch.device("cpu")
    loaded = ev.load_policy_checkpoint(Path(args.checkpoint), device=device, decks_path=TRAINING_DECKS)

    games: list[dict] = []
    live: dict[int, dict] = {}
    orig_reset, orig_step = SelfPlayBattleEnv.reset, SelfPlayBattleEnv.step

    def reset(self, *a, **kw):
        result = orig_reset(self, *a, **kw)
        rec = {"pid": int(self.learner_player_id), "plays": {0: [], 1: []}, "env": self}
        live[id(self)] = rec
        games.append(rec)
        return result

    def step(self, actions, **kw):
        battle = self.battle
        pre = {}
        for pid, action in actions.items():
            if action < self.action_space.no_op_action:
                player = battle.players[pid]
                sel = self.action_space.decode_action(action, pid)
                hand = list(player.hand)[:4]
                card = hand[sel.slot] if sel.slot is not None and sel.slot < len(hand) else None
                pre[pid] = (battle.tick, card, sel.position.x, sel.position.y, float(player.elixir), [c for c in hand if c is not None])
        result = orig_step(self, actions, **kw)
        info = result[2]
        rec = live.get(id(self))
        for pid, (tick, card, x, y, elixir, hand) in pre.items():
            if rec is not None and card is not None and info.action_success.get(pid, False):
                cx, cy = canon(pid, x, y)
                rec["plays"][pid].append([round(tick * TICK_S, 2), card, cx, cy, round(elixir, 3), hand, True, False, False])
        if rec is not None and result[1]:
            rec["end_tick"] = int(battle.tick)
            rec["decks"] = {pid: list(battle.players[pid].deck) for pid in (0, 1)}
        return result

    SelfPlayBattleEnv.reset, SelfPlayBattleEnv.step = reset, step
    styles = [s for s in args.styles.split(",") if s]
    per_style = {s: args.games // len(styles) + (1 if i < args.games % len(styles) else 0) for i, s in enumerate(styles)}
    game_records: list[dict] = []
    t0 = time.time()
    metrics = {}
    for style_index, (style, n) in enumerate(per_style.items()):
        if n <= 0:
            continue
        before = len(game_records)
        metrics[style] = ev.evaluate(
            candidate=loaded, decks_path=TRAINING_DECKS, games=n, seed=args.seed + 100_003 * style_index,
            decision_interval=5, max_ticks=6001, opponent_mode="public-script", opponent=None,
            deterministic=args.deterministic, quiet_engine=True, device=device,
            candidate_sampling_decks_path=candidate_decks, opponent_sampling_decks_path=TRAINING_DECKS,
            game_records=game_records, public_script_style=style, level_mode="nominal",
        )
        for gr in game_records[before:]:
            gr["style"] = style
    SelfPlayBattleEnv.reset, SelfPlayBattleEnv.step = orig_reset, orig_step
    if len(games) != len(game_records):
        raise RuntimeError(f"captured {len(games)} games but evaluate returned {len(game_records)}")
    tag = args.tag or Path(args.checkpoint).stem
    out_path = Path(args.out) if args.out else HERE / f"policy_sim_{tag}.jsonl.gz"
    with gzip.open(out_path, "wt") as stream:
        for rec, gr in zip(games, game_records):
            pid = rec["pid"]
            stream.write(json.dumps({
                "match": f"{tag}/{gr['style']}/g{gr['game']}", "side": "candidate", "pid": pid, "style": gr["style"],
                "deck": gr["candidate_deck"], "opp_deck": gr["opponent_deck"],
                "duration_s": gr["ticks"] * TICK_S, "result": gr["outcome"],
                "plays": rec["plays"][pid], "opp_plays": [p[:4] for p in rec["plays"][1 - pid]],
            }) + "\n")
    summary = {"checkpoint": str(Path(args.checkpoint).resolve()), "games": len(game_records), "per_style": per_style,
               "candidate_decks": str(candidate_decks), "out": str(out_path), "wall_s": round(time.time() - t0, 1),
               "score_by_style": {s: m["score_rate"] for s, m in metrics.items()}}
    print(json.dumps(summary, indent=1))
    return summary


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def _q(values, qs=(0.25, 0.5, 0.75)):
    if not values:
        return None
    v = sorted(values)
    return [round(v[min(len(v) - 1, int(q * len(v)))], 3) for q in qs]


def _mean(values):
    return round(sum(values) / len(values), 4) if values else None


def _hist(values, bins):
    counts = [0] * (len(bins) - 1)
    for v in values:
        for i in range(len(bins) - 1):
            if bins[i] <= v < bins[i + 1]:
                counts[i] += 1
                break
    n = max(1, len(values))
    labels = [f"{bins[i]:g}-{bins[i + 1]:g}" if bins[i + 1] < 1e8 else f"{bins[i]:g}+" for i in range(len(bins) - 1)]
    return {label: round(c / n, 4) for label, c in zip(labels, counts)}


def _phase(t):
    for name, lo, hi in PHASES:
        if lo <= t < hi:
            return name
    return PHASES[-1][0]


def _bridge_dist(x, y):
    return min(math.hypot(x - bx, y - by) for bx, by in BRIDGES)


def behavior_stats(records: list[dict], cards=PILOT16) -> dict:
    """Per-card and global behaviour statistics for a list of side records."""
    n = len(records)
    if not n:
        return {"sides": 0}
    total_plays = sum(len(r["plays"]) for r in records)
    minutes = sum(r["duration_s"] for r in records) / 60.0
    phase_time = collections.Counter()
    card_phase_time = collections.defaultdict(collections.Counter)
    for r in records:
        for name, lo, hi in PHASES:
            minutes_in_phase = max(0.0, min(r["duration_s"], hi) - lo) / 60.0
            phase_time[name] += minutes_in_phase
            for c in set(r["deck"]):
                card_phase_time[c][name] += minutes_in_phase
    in_deck = collections.Counter(c for r in records for c in set(r["deck"]))
    per_card = {}
    card_rows = collections.defaultdict(list)
    held = collections.Counter()
    held_rows = collections.Counter()
    for r in records:
        for p in r["plays"]:
            card_rows[p[1]].append(p)
            if p[5] is None:  # play after the sim match ended: no reconstructed hand
                continue
            held_rows[p[1]] += 1
            for c in set(p[5]):
                held[c] += 1
    all_elixir = [p[4] for r in records for p in r["plays"] if p[4] is not None]
    phase_counts = collections.Counter(_phase(p[0]) for r in records for p in r["plays"])
    for card in cards:
        rows = card_rows.get(card, [])
        k = len(rows)
        entry = {
            "sides_with_card": in_deck[card], "plays": k,
            "play_share": round(k / total_plays, 4) if total_plays else None,
            "plays_per_match_when_in_deck": round(k / in_deck[card], 3) if in_deck[card] else None,
            "held_placements": held[card],
            "play_when_held": round(held_rows[card] / held[card], 4) if held[card] else None,
        }
        if k:
            elixir = [p[4] for p in rows if p[4] is not None]
            dist = [_bridge_dist(p[2], p[3]) for p in rows]
            ph = collections.Counter(_phase(p[0]) for p in rows)
            entry.update({
                "elixir_at_play_mean": _mean(elixir), "elixir_at_play_q": _q(elixir),
                "elixir_at_play_hist": _hist(elixir, ELIXIR_BINS),
                "first_play_time_q": _q([min(p[0] for p in r["plays"] if p[1] == card) for r in records if any(p[1] == card for p in r["plays"])]),
                "phase_share": {name: round(ph[name] / k, 4) for name, _, _ in PHASES},
                "phase_rate_per_min_in_deck": {
                    name: (round(ph[name] / card_phase_time[card][name], 3) if card_phase_time[card][name] else None)
                    for name, _, _ in PHASES},
                "own_side_share": round(sum(p[3] < MID_Y for p in rows) / k, 4),
                "left_lane_share": round(sum(p[2] < ARENA_W / 2 for p in rows) / k, 4),
                "bridge_dist_q": _q(dist), "bridge_dist_hist": _hist(dist, DIST_BINS),
                "depth_y_q": _q([p[3] for p in rows]),
            })
        per_card[card] = entry
    # reactions
    latencies, react_by_opp = [], collections.defaultdict(lambda: {"n": 0, "lat": [], "resp": collections.Counter(), "same_lane": 0, "own_side": 0})
    reactive_plays = 0
    for r in records:
        own = sorted(r["plays"], key=lambda p: p[0])
        opp = sorted(r["opp_plays"], key=lambda p: p[0])
        own_t = [p[0] for p in own]
        j = 0
        for o in opp:
            while j < len(own_t) and own_t[j] <= o[0]:
                j += 1
            slot = react_by_opp[o[1]]
            slot["n"] += 1
            if j < len(own_t) and own_t[j] - o[0] <= REACT_WINDOW_S:
                lat = own_t[j] - o[0]
                latencies.append(lat)
                slot["lat"].append(lat)
                if lat <= REACTIVE_S:
                    resp = own[j]
                    slot["resp"][resp[1]] += 1
                    # opponent play in the responder's canonical frame: rotate 180 degrees
                    ox = ARENA_W - o[2]
                    slot["same_lane"] += int((resp[2] < 9) == (ox < 9))
                    slot["own_side"] += int(resp[3] < MID_Y)
        k = 0
        for p in own:
            while k < len(opp) and opp[k][0] < p[0]:
                k += 1
            prev_opp = opp[k - 1][0] if k else None
            reactive_plays += int(prev_opp is not None and p[0] - prev_opp <= REACTIVE_S)
    n_opp = sum(len(r["opp_plays"]) for r in records)
    reactions = {
        "opponent_plays": n_opp,
        "latency_to_next_own_play_q": _q(latencies),
        "responded_within_s": {f"{s:g}": round(sum(lat <= s for lat in latencies) / max(1, n_opp), 4) for s in REACT_FAST_S},
        "own_plays_within_6s_of_opp_play_share": round(reactive_plays / max(1, total_plays), 4),
        "by_opponent_card": {
            card: {
                "n": v["n"], "latency_q": _q(v["lat"]),
                f"responded_within_{REACTIVE_S:g}s": round(sum(lat <= REACTIVE_S for lat in v["lat"]) / v["n"], 4),
                "top_responses": [[c, round(m / max(1, sum(v["resp"].values())), 3)] for c, m in v["resp"].most_common(4)],
                "response_same_lane_share": round(v["same_lane"] / max(1, sum(v["resp"].values())), 3),
                "response_own_side_share": round(v["own_side"] / max(1, sum(v["resp"].values())), 3),
            }
            for card, v in sorted(react_by_opp.items(), key=lambda kv: -kv[1]["n"]) if v["n"] >= 20
        },
    }
    all_rows = [p for r in records for p in r["plays"]]
    with_state = [p for p in all_rows if p[6] is not None]
    accepted = sum(p[6] for p in with_state)
    return {
        "sides": n, "matches": len({r["match"] for r in records}),
        "mean_duration_s": round(minutes * 60 / n, 2),
        "plays_per_match": round(total_plays / n, 3),
        "plays_per_minute": round(total_plays / minutes, 3) if minutes else None,
        "phase_play_share": {name: round(phase_counts[name] / max(1, total_plays), 4) for name, _, _ in PHASES},
        "phase_plays_per_minute": {name: (round(phase_counts[name] / phase_time[name], 3) if phase_time[name] else None) for name, _, _ in PHASES},
        "elixir_at_play_mean": _mean(all_elixir), "elixir_at_play_q": _q(all_elixir),
        "elixir_at_play_hist": _hist(all_elixir, ELIXIR_BINS),
        "plays_at_full_elixir_share": round(sum(e >= 9.95 for e in all_elixir) / max(1, len(all_elixir)), 4),
        "plays_with_combat_resim_share": round(len(with_state) / max(1, total_plays), 4),
        "resim_accept_rate": round(accepted / max(1, len(with_state)), 4),
        "hand_forced_rate": round(sum(p[7] for p in all_rows) / max(1, len(all_rows)), 4),
        "elixir_topup_rate": round(sum(p[8] for p in all_rows) / max(1, len(all_rows)), 4),
        "per_card": per_card,
        "reactions": reactions,
    }


def _deck_inclusion(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text())
    total, inc = 0.0, collections.Counter()
    for deck in payload["decks"]:
        w = float(deck.get("sampling_weight", 1.0))
        total += w
        for c in set(deck["cards"][:8]):
            inc[c] += w
    return {c: inc[c] / total for c in PILOT16}


def monitor_policy_stats(monitor_path: Path, at_decisions: int | None = None) -> dict:
    rows = [json.loads(line) for line in monitor_path.read_text().splitlines() if line.strip()]
    # Skip resume-marker rows and rows from before the first finished episode.
    rows = [r for r in rows if r.get("plays_per_match") is not None and r.get("card_share")]
    if at_decisions is not None:
        rows = [r for r in rows if r["learner_decisions"] <= at_decisions] or rows[:1]
    last = rows[-1]
    window = int(last.get("window_updates", 20))
    by_update = {r["update"]: r for r in rows}
    start_row = by_update.get(last["update"] - window)
    start_dec = start_row["learner_decisions"] if start_row else 0
    durations, results = [], collections.Counter()
    for path in sorted((monitor_path.parent / "opponents").glob("worker-*-outcomes.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            o = json.loads(line)
            if start_dec <= o.get("learner_decisions_at_assignment", -1) <= last["learner_decisions"]:
                durations.append(o["end_tick"] * TICK_S)
                results[(o.get("kind"), o.get("style"), o["learner_result"])] += 1
    inclusion = _deck_inclusion(TRAINING_DECKS)
    ppm = last["plays_per_match"]
    mean_dur = statistics.mean(durations) if durations else None
    per_card = {}
    for card in PILOT16:
        share = last["card_share"].get(card)
        per_card[card] = {
            "play_share": round(share, 4) if share is not None else None,
            "deck_inclusion": round(inclusion[card], 4),
            "plays_per_match_when_in_deck": round(share * ppm / inclusion[card], 3) if share is not None and inclusion[card] else None,
            "play_when_held": round(last["held_play_share"][card], 4) if card in last.get("held_play_share", {}) else None,
        }
    script = collections.Counter()
    for (kind, style, res), cnt in results.items():
        script[(kind if kind != "script" else f"script:{style}", res)] += cnt
    return {
        "source": str(monitor_path), "update": last["update"], "learner_decisions": last["learner_decisions"],
        "window_updates": window, "window_episodes": last.get("window_episodes"), "window_plays": last.get("window_plays"),
        "plays_per_match": round(ppm, 3), "waits_per_match": round(last["waits_per_match"], 1),
        "mean_duration_s": round(mean_dur, 2) if mean_dur else None,
        "plays_per_minute": round(ppm / (mean_dur / 60.0), 3) if mean_dur else None,
        "outcome_episodes_in_window": len(durations),
        "window_results": {f"{k}/{r}": v for (k, r), v in sorted(script.items())},
        "active_alarms": last.get("active_alarms"),
        "entropy": last.get("window_entropy"),
        "per_card": per_card,
        "note": "monitor row = rolling 20-update window over learner plays vs all opponents; decks sampled from roles_v2/training.json",
    }


def _log2r(h, p, eps):
    if h is None or p is None:
        return None
    return math.log2((p + eps) / (h + eps))


MIN_SIM_SIDES_FOR_RANKING = 20


def divergences(human: dict, human_ext: dict | None, policy_monitor: dict | None, policy_sim: dict | None) -> list[dict]:
    """Rank card-level gaps; human reference = p16 for Hog 2.6 cards, ext otherwise.

    Simulated-policy rows enter the ranking only with at least
    MIN_SIM_SIDES_FOR_RANKING games (a 2-game smoke run is reported, not ranked).
    """
    if policy_sim and policy_sim.get("sides", 0) < MIN_SIM_SIDES_FOR_RANKING:
        policy_sim = None
    out = []
    for card in PILOT16:
        ref_name, ref = "p16", human["per_card"].get(card, {})
        if (ref.get("sides_with_card") or 0) < 100 and human_ext:
            ref_name, ref = "ext", human_ext["per_card"].get(card, {})
        for src_name, src in (("monitor", policy_monitor), ("sim", policy_sim)):
            if not src:
                continue
            pc = src["per_card"].get(card, {})
            for metric, eps in (("play_when_held", 0.01), ("plays_per_match_when_in_deck", 0.2)):
                lr = _log2r(ref.get(metric), pc.get(metric), eps)
                if lr is None:
                    continue
                out.append({"card": card, "metric": metric, "policy_source": src_name, "human_ref": ref_name,
                            "human_sides": ref.get("sides_with_card"), "human": ref.get(metric), "policy": pc.get(metric),
                            "log2_policy_over_human": round(lr, 2)})
    out.sort(key=lambda d: -abs(d["log2_policy_over_human"]))
    return out


def by_cost(per_card: dict, metric: str = "play_when_held") -> dict:
    groups = collections.defaultdict(list)
    for card, entry in per_card.items():
        if entry.get(metric) is not None and card in COST:
            groups[COST[card]].append((card, entry[metric]))
    return {str(c): {"mean": round(sum(v for _, v in rows) / len(rows), 4), "cards": dict(rows)} for c, rows in sorted(groups.items())}


def _load_records(path: Path) -> list[dict]:
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def cmd_compare(args):
    if args.checkpoint:
        sim_args = argparse.Namespace(
            checkpoint=args.checkpoint, games=args.sim_games, styles=args.styles,
            candidate_decks=args.candidate_decks, seed=args.seed, deterministic=False, tag=None, out=None)
        args.policy_sim = list(args.policy_sim) + [cmd_sim_policy(sim_args)["out"]]
    human_p16 = behavior_stats(_load_records(HERE / "human_plays_p16.jsonl.gz"))
    ext_path = HERE / "human_plays_ext.jsonl.gz"
    human_ext = None
    if ext_path.exists():
        ext_recs = [r for r in _load_records(ext_path) if set(r["deck"]) & set(NON_HOG26)]
        human_ext = behavior_stats(ext_recs)
    monitor = monitor_policy_stats(Path(args.monitor), args.at_decisions) if args.monitor else None
    sim = None
    if args.policy_sim:
        sim_recs = []
        for f in args.policy_sim:
            sim_recs += _load_records(Path(f))
        sim = behavior_stats(sim_recs)
        sim["source"] = [str(f) for f in args.policy_sim]
    div = divergences(human_p16, human_ext, monitor, sim)
    globals_cmp = {
        "plays_per_match": {"human_p16": human_p16["plays_per_match"], "policy_monitor": monitor and monitor["plays_per_match"], "policy_sim": sim and sim["plays_per_match"]},
        "plays_per_minute": {"human_p16": human_p16["plays_per_minute"], "policy_monitor": monitor and monitor["plays_per_minute"], "policy_sim": sim and sim["plays_per_minute"]},
        "mean_duration_s": {"human_p16": human_p16["mean_duration_s"], "policy_monitor": monitor and monitor["mean_duration_s"], "policy_sim": sim and sim["mean_duration_s"]},
    }
    human_ref_cards = {}
    for card in PILOT16:
        ref = human_p16["per_card"].get(card, {})
        if (ref.get("sides_with_card") or 0) < 100 and human_ext:
            ref = human_ext["per_card"].get(card, {})
        human_ref_cards[card] = ref
    cost_table = {
        "play_when_held_by_elixir_cost": {
            "human_ref": by_cost(human_ref_cards),
            "policy_monitor": monitor and by_cost(monitor["per_card"]),
            "policy_sim": sim and by_cost(sim["per_card"]),
        },
    }
    result = {
        "schema": "human-comparison-v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "definitions": {
            "play_when_held": "plays of card / own plays made while the card was in the 4-card hand (monitor held_play_share definition)",
            "plays_per_match_when_in_deck": "plays of card / sides whose deck contains it (policy monitor: card_share*plays_per_match/training-deck inclusion)",
            "elixir_at_play": "own elixir immediately before paying for the play (human: open-loop re-sim; policy: simulator)",
            "phases_s": {name: [lo, hi if hi < 1e8 else None] for name, lo, hi in PHASES},
            "coordinates": "canonical: own side at the bottom (y<16), top player rotated 180 degrees; left lane = x<9; bridge centres (3.5,16),(14.5,16)",
            "reaction": f"for each opponent play, latency to the next own play (window {REACT_WINDOW_S:g}s); responses = own play within {REACTIVE_S:g}s",
        },
        "human_p16": human_p16,
        "human_ext_card_conditional": human_ext,
        "policy_monitor": monitor,
        "policy_sim": sim,
        "global_comparison": globals_cmp,
        "by_elixir_cost": cost_table,
        "divergences": div,
    }
    if args.out:
        out = Path(args.out)
    elif args.monitor:
        mp = Path(args.monitor).resolve()
        out = HERE / f"results_{mp.parent.parent.name}_{mp.parent.name}_u{monitor['update']:04d}.json"
    else:
        out = HERE / "results.json"
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(globals_cmp, indent=1))
    print("play_when_held by elixir cost (mean over cards):")
    for src, table in cost_table["play_when_held_by_elixir_cost"].items():
        if table:
            print(f"  {src:<15} " + "  ".join(f"{c}e={v['mean']:.3f}" for c, v in table.items()))
    print(f"top divergences ({len(div)} rows) -> {out}")
    for d in div[: args.top]:
        print(f"  {d['card']:<11} {d['metric']:<30} {d['policy_source']:<7} human[{d['human_ref']}]={d['human']}  policy={d['policy']}  log2={d['log2_policy_over_human']:+.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract-human")
    p.add_argument("--pool", choices=("p16", "ext"), default="p16")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(func=cmd_extract_human)
    p = sub.add_parser("sim-policy")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--games", type=int, default=2)
    p.add_argument("--styles", default="balanced,pressure,defense")
    p.add_argument("--candidate-decks", default="hog26", help="hog26 | training | path to a decks JSON")
    p.add_argument("--seed", type=int, default=770001)
    p.add_argument("--deterministic", action="store_true", help="greedy decoding (default: stochastic, as in the pilot evaluation)")
    p.add_argument("--tag", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_sim_policy)
    p = sub.add_parser("compare")
    p.add_argument("--monitor", default=None, help="training-monitor.jsonl of a run")
    p.add_argument("--policy-sim", action="append", default=[], help="policy_sim_*.jsonl.gz (repeatable)")
    p.add_argument("--at-decisions", type=int, default=None, help="use the last monitor row at or before this learner-decision count (default: latest row)")
    p.add_argument("--checkpoint", default=None, help="also simulate this checkpoint vs the scripted pool")
    p.add_argument("--sim-games", type=int, default=2)
    p.add_argument("--styles", default="balanced,pressure,defense")
    p.add_argument("--candidate-decks", default="hog26")
    p.add_argument("--seed", type=int, default=770001)
    p.add_argument("--out", default=None)
    p.add_argument("--top", type=int, default=15)
    p.set_defaults(func=cmd_compare)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
