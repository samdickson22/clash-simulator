"""Python <-> Rust (clasher_core) lockstep parity on native fixture scripts.

    PYTHONPATH=engine-rs:src:. python -m bot.fidelity.rs_parity --episodes a,b|--split train --limit N \
        --out OUT.jsonl [--workers N]

Per fixture: the Python battle at the recording's first tick (decks/hands/elixir as bot.speed.bench), imported into
Rust with differential.snapshot(config(cards)). Every recorded card play (abilities skipped) is applied to both at
exec-1; both step one tick at a time to the recording's end or game over. The digests (es_common.battle_digest vs
clasher_core digest) are compared every tick; the first mismatch is recorded with the differing entities.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from multiprocessing import Pool
from pathlib import Path

D = Path("/mpac/sdicks02/repos/clasher-bot-data")
IDS = json.loads((Path(__file__).resolve().parent / "c56_native_ids.json").read_text())
ID2N = {v: k for k, v in IDS.items()}
_CFG: dict = {}


def _name(n):
    from clasher.card_aliases import resolve_card_name
    return resolve_card_name(n)


def _py_battle(fix):
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    players = []
    for s in (0, 1):
        names = [_name(ID2N[i]) for i in fix.initial_order[s]]
        players.append(PlayerState(s, deck=list(names), hand=list(names[:4]), cycle_queue=deque(names[4:])))
    b = BattleState(players=players, rng=random.Random(fix.start_tick))
    while b.tick < fix.start_tick:
        if b.fast_forward_idle_ticks(fix.start_tick - b.tick) == 0:
            b.step()
    for s in (0, 1):
        b.players[s].elixir = fix.initial_elixir[s]
    return b


def _py_entities(b):
    return {eid: (e.player_id, round(e.position.x, 6), round(e.position.y, 6), round(float(e.hitpoints), 3),
                  bool(e.is_alive), type(e).__name__, e.target_id, getattr(e.card_stats, "name", None))
            for eid, e in b.entities.items()}


def _rs_entities(r):
    s = json.loads(r.snapshot())
    out = {}
    for e in s["entities"]:
        out[e["id"]] = (e["owner"], round(e["x"], 6), round(e["y"], 6), round(float(e["hp"]), 3), bool(e["alive"]),
                        e.get("class"), e.get("target"))
    return out


def run_one(ep):
    import clasher_core
    from differential import battle_digest, config, snapshot
    from bot.fidelity.fixture import load_fixture, load_split
    from clasher.arena import Position
    fix = load_fixture(D / "t1-trainval" / ep, load_split(D / "t1-split.json"))
    res = {"episode": ep, "split": fix.split}
    try:
        b = _py_battle(fix)
        cards = tuple(sorted({_name(ID2N[i]) for s in (0, 1) for i in fix.initial_order[s]}))
        if cards not in _CFG:
            _CFG[cards] = config(cards)
        r = clasher_core.BattleState(snapshot(b, _CFG[cards]))
    except Exception as ex:  # card outside the Rust scope, import failure
        res["error"] = repr(ex)[:300]
        return res
    plays = sorted((p for p in fix.plays if p.kind != "champion ability"), key=lambda p: (p.exec_tick, p.side, p.slot))
    pi = 0
    res.update(start_match=battle_digest(b) == r.digest(), action_mismatch=[], first_mismatch=None)
    while b.tick < fix.end_tick and not b.game_over:
        t = b.tick
        while pi < len(plays) and plays[pi].exec_tick - 1 <= t:
            p = plays[pi]
            pa = b.deploy_card(p.side, _name(p.card), Position(*p.tile))
            ra = r.apply_action(p.side, _name(p.card), p.tile[0], p.tile[1])
            if bool(pa) != bool(ra):
                res["action_mismatch"].append((t, p.side, p.card, p.tile, bool(pa), bool(ra)))
            pi += 1
        b.step()
        r.step()
        if battle_digest(b) != r.digest():
            pe, re_ = _py_entities(b), _rs_entities(r)
            diff = []
            for eid in sorted(set(pe) | set(re_)):
                a, c = pe.get(eid), re_.get(eid)
                if a is None or c is None or a[:7] != c[:7]:
                    diff.append((eid, a, c))
            res["first_mismatch"] = {"tick": b.tick, "rel": b.tick - fix.start_tick, "entities": diff[:8],
                                     "n_entities_diff": len(diff)}
            break
    res["ticks"] = b.tick - fix.start_tick
    res["fixture_ticks"] = fix.end_tick - fix.start_tick
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="")
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    from bot.fidelity.fixture import load_split
    sp = load_split(D / "t1-split.json")
    eps = a.episodes.split(",") if a.episodes else sorted(
        e for e in sp if sp[e] == a.split and (D / "t1-trainval" / e).exists())
    if a.limit:
        eps = eps[: a.limit]
    with Pool(a.workers) as pool, open(a.out, "w") as fh:
        for r in pool.imap_unordered(run_one, eps):
            fh.write(json.dumps(r) + "\n")
            fh.flush()


if __name__ == "__main__":
    main()
