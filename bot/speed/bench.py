"""Single-core engine speed: replay the same native fixture scripts through each engine.

    taskset -c CORE python -m bot.speed.bench --engine py|rs|rsim15535|rsim16402 --episodes a,b,.. --out OUT.json

Workload per fixture: start at the recording's first tick with its decks/hands, issue every recorded card play at
its execution tick - 1 (abilities skipped), step one tick at a time to the recording's end (or the engine's game
end). Timed: the stepping loop (deploy calls included). Clone cost sampled at ticks 1000/2000/3000:
  py: BattleState.clone(); rs: clasher_core.BattleState.clone(); rsim: save() and load() into a second Battle
  (RoyaleSim has no in-memory clone; save/load is its branching primitive).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from pathlib import Path

from bot.fidelity.fixture import load_fixture, load_split

D = Path("/mpac/sdicks02/repos/clasher-bot-data")
IDS = json.loads((Path(__file__).resolve().parents[1] / "fidelity" / "c56_native_ids.json").read_text())
ID2N = {v: k for k, v in IDS.items()}
SAMPLE_TICKS = (1000, 2000, 3000)
REPS = 50


def our_name(n):
    from clasher.card_aliases import resolve_card_name
    return resolve_card_name(n)


def py_battle(fix):
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    import random
    players = []
    for s in (0, 1):
        names = [our_name(ID2N[i]) for i in fix.initial_order[s]]
        players.append(PlayerState(s, deck=list(names), hand=list(names[:4]), cycle_queue=deque(names[4:])))
    b = BattleState(players=players, rng=random.Random(fix.start_tick))
    while b.tick < fix.start_tick:
        if b.fast_forward_idle_ticks(fix.start_tick - b.tick) == 0:
            b.step()
    for s in (0, 1):
        b.players[s].elixir = fix.initial_elixir[s]
    return b


class Py:
    def __init__(self, fix):
        self.b = py_battle(fix)

    def deploy(self, p):
        from clasher.arena import Position
        return self.b.deploy_card(p.side, our_name(p.card), Position(*p.tile))

    def step(self):
        self.b.step()

    def over(self):
        return self.b.game_over

    def clone_cost(self):
        t = time.perf_counter()
        for _ in range(REPS):
            self.b.clone()
        return {"clone_us": 1e6 * (time.perf_counter() - t) / REPS}


class Rs:
    cfg_cache = {}

    def __init__(self, fix):
        import clasher_core
        from differential import config, snapshot
        cards = tuple(sorted({our_name(ID2N[i]) for s in (0, 1) for i in fix.initial_order[s]}))
        if cards not in Rs.cfg_cache:
            Rs.cfg_cache[cards] = config(cards)
        b = py_battle(fix)
        self.r = clasher_core.BattleState(snapshot(b, Rs.cfg_cache[cards]))

    def deploy(self, p):
        return self.r.apply_action(p.side, our_name(p.card), p.tile[0], p.tile[1])

    def step(self):
        self.r.step()

    def over(self):
        snap = json.loads(self.r.snapshot())
        return bool(snap.get("game_over", False))

    def clone_cost(self):
        t = time.perf_counter()
        for _ in range(REPS):
            self.r.clone()
        return {"clone_us": 1e6 * (time.perf_counter() - t) / REPS}


class Rsim:
    def __init__(self, fix, client):
        import royalesim
        from bot.fidelity.engines import RSIM_NAME
        ov = royalesim.client_arms(client) if client != "16.402" else {}
        mk = lambda: royalesim.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]], calibration_overrides=ov)
        self.b, self.b2 = mk(), mk()
        cat = json.loads(self.b.catalogue_json())
        idx = {row[0]: i for i, row in enumerate(cat)}
        self.idx = lambda n: idx[RSIM_NAME.get(n, n)]
        decks = [[self.idx(ID2N[i]) for i in fix.initial_order[s]] for s in (0, 1)]
        self.b.reset(seed=fix.start_tick, decks=decks, shuffle=0, start_tick=fix.start_tick,
                     elixir_milli=[int(e * 1000) for e in fix.initial_elixir], tower_hp=None, spawns=[])
        self.sub = royalesim.SUBTILE_PER_MILLITILE
        self._t = fix.start_tick
        self.hand = [list(decks[s][:4]) for s in (0, 1)]
        self.pending = []

    def deploy(self, p):
        # hand from state (as a bot would read it)
        st = json.loads(self.b.state_json())
        hand = st["players"][p.side]["hand"]
        want = self.idx(p.card)
        if want not in hand:
            return False
        self.pending.append((p.side, hand.index(want), int(p.tile[0] * 1000 * self.sub), int(p.tile[1] * 1000 * self.sub)))
        return True

    def step(self):
        cmds, self.pending = self.pending, []
        self.b.step(cmds, 1)

    def over(self):
        return bool(json.loads(self.b.state_json())["game_over"])

    def clone_cost(self):
        t = time.perf_counter()
        for _ in range(REPS):
            blob = self.b.save()
        save_us = 1e6 * (time.perf_counter() - t) / REPS
        t = time.perf_counter()
        for _ in range(REPS):
            self.b2.load(blob)
        load_us = 1e6 * (time.perf_counter() - t) / REPS
        t = time.perf_counter()
        for _ in range(REPS):
            json.loads(self.b.state_json())
        sj_us = 1e6 * (time.perf_counter() - t) / REPS
        return {"clone_us": save_us + load_us, "save_us": save_us, "load_us": load_us, "state_json_parse_us": sj_us,
                "blob_bytes": len(blob)}


def run(engine, fix):
    if engine == "py":
        e = Py(fix)
    elif engine == "rs":
        e = Rs(fix)
    else:
        e = Rsim(fix, "15.535.29" if engine == "rsim15535" else "16.402")
    plays = sorted((p for p in fix.plays if p.kind != "champion ability"), key=lambda p: p.exec_tick)
    t, pi, steps, deploy_s, step_s = fix.start_tick, 0, 0, 0.0, 0.0
    clones = []
    ok = fail = 0
    while t < fix.end_tick:
        t0 = time.perf_counter()
        while pi < len(plays) and plays[pi].exec_tick - 1 <= t:
            if e.deploy(plays[pi]):
                ok += 1
            else:
                fail += 1
            pi += 1
        t1 = time.perf_counter()
        e.step()
        t2 = time.perf_counter()
        deploy_s += t1 - t0
        step_s += t2 - t1
        t += 1
        steps += 1
        if t in SAMPLE_TICKS:
            clones.append(e.clone_cost())
        if steps % 50 == 0 and e.over():  # untimed
            break
    return {"episode": fix.episode, "ticks": steps, "step_s": step_s, "deploy_s": deploy_s,
            "deploys_ok": ok, "deploys_failed": fail, "clones": clones}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    splits = load_split(D / "t1-split.json")
    res = []
    for ep in a.episodes.split(","):
        fix = load_fixture(D / "t1-trainval" / ep, splits)
        try:
            res.append(run(a.engine, fix))
        except Exception as ex:  # unsupported card in the Rust scope, etc.
            res.append({"episode": ep, "error": repr(ex)[:300]})
        print(json.dumps({k: v for k, v in res[-1].items() if k != "clones"}), flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
