"""Scalar-engine smoke test for every base card that appears in IL_Replay.

For each base slug: fresh BattleState, level 11.  Player 1 sends a Giant +
Knight down the left lane at t=0; player 0 deploys a Knight at t=0 and the
card under test at t=4 s (spells aimed at the enemy Giant, rolling/deploy-zone
spells at the nearest own-territory tile).  We compare 30 s of outcome against
a Knight-only baseline: enemy HP removed, own HP gained, entities spawned and
own elixir.  No fitting, no external code.

Run: OMP_NUM_THREADS=1 nice -n 15 .venv/bin/python <this file>
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from card_map import PILOT16, SLUG_TO_GAMEDATA  # noqa: E402
from clasher.arena import Position  # noqa: E402
from clasher.battle import BattleState  # noqa: E402
from clasher.entities import Building, Troop  # noqa: E402
from clasher.rl.deck_pool import apply_ordered_deck_to_player  # noqa: E402

FILLERS = ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Zap", "Cannon", "Skeletons", "Goblins"]


def hp_sum(battle, player_id):
    total = 0.0
    for e in battle.entities.values():
        if e.player_id == player_id and getattr(e, "is_alive", True):
            total += max(0.0, float(e.hitpoints))
    return total


def run(card: str | None):
    b = BattleState()
    deck0 = ([card] if card else []) + [f for f in FILLERS if f != card and f != "Knight"]
    deck0 = ["Knight"] + deck0
    deck0 = list(dict.fromkeys(deck0))[:8]
    apply_ordered_deck_to_player(b.players[0], deck0)
    apply_ordered_deck_to_player(b.players[1], ["Giant", "Knight", "Archers", "Minions", "Musketeer", "Zap", "Cannon", "Skeletons"])
    b.players[0].hand = [deck0[0], deck0[1], deck0[2], deck0[3]]
    b.players[0].elixir = 10.0
    b.players[1].elixir = 10.0
    ok_enemy = b.deploy_card(1, "Giant", Position(3.5, 22.5)) and b.deploy_card(1, "Knight", Position(4.5, 22.5))
    b.deploy_card(0, "Knight", Position(3.5, 10.5))
    for _ in range(80):
        b.step()
    start_enemy = hp_sum(b, 1)
    start_own = hp_sum(b, 0)
    n_before = len(b.entities)
    ids_before = set(b.entities)
    accepted = None
    where = None
    if card:
        b.players[0].elixir = 10.0
        if card not in b.players[0].hand:
            b.players[0].hand[1] = card
        giant = next((e for e in b.entities.values() if e.player_id == 1 and isinstance(e, Troop)), None)
        gx, gy = (giant.position.x, giant.position.y) if giant else (3.5, 20.5)
        candidates = [
            (gx, gy),                      # spells on the Giant
            (3.5, 14.5), (gx, 14.5),       # own bridge front (rolling / deploy-zone spells, troops)
            (3.5, 12.5), (8.5, 11.5), (9.0, 9.0), (6.5, 12.5),
        ]
        for x, y in candidates:
            if b.deploy_card(0, card, Position(x, y)):
                accepted, where = True, (round(x, 2), round(y, 2))
                break
        else:
            accepted = False
    spawned = {}
    elixir_trace = []
    for i in range(600):
        b.step()
        for eid, e in b.entities.items():
            if eid not in ids_before and e.player_id == 0:
                nm = getattr(getattr(e, "card_stats", None), "name", type(e).__name__)
                spawned[f"{type(e).__name__}:{nm}"] = spawned.get(f"{type(e).__name__}:{nm}", 0) or 1
        if i % 100 == 0:
            elixir_trace.append(round(b.players[0].elixir, 2))
    return {
        "accepted": accepted,
        "where": where,
        "enemy_hp_removed": round(start_enemy - hp_sum(b, 1), 1),
        "own_hp_delta": round(hp_sum(b, 0) - start_own, 1),
        "entities_spawned": sorted(spawned),
        "elixir_trace": elixir_trace,
        "enemy_setup_ok": bool(ok_enemy),
    }


def main():
    base = run(None)
    out = {"baseline_knight_only": base, "cards": {}}
    for slug, name in sorted(SLUG_TO_GAMEDATA.items()):
        try:
            r = run(name)
            r["exception"] = None
        except Exception as exc:  # record, do not hide
            r = {"accepted": None, "exception": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-600:]}
        r["gamedata"] = name
        r["pilot16"] = name in PILOT16
        if r.get("accepted"):
            r["enemy_hp_removed_vs_baseline"] = round(r["enemy_hp_removed"] - base["enemy_hp_removed"], 1)
            r["own_hp_delta_vs_baseline"] = round(r["own_hp_delta"] - base["own_hp_delta"], 1)
        out["cards"][slug] = r
        print(slug, name, r.get("accepted"), r.get("exception"), r.get("enemy_hp_removed_vs_baseline"), r.get("entities_spawned"), flush=True)
    (HERE / "card_smoke.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
