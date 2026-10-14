"""Replay native T1 train/validation recordings through an engine and score fidelity.

    python -m bot.fidelity.run --engine clasher|rsim15535|rsim16402 --data DIR --split SPLIT_JSON \
        --out OUT_DIR [--episodes a,b,...] [--limit N] [--workers N] [--issue-offset K]

One JSON per fixture in OUT_DIR/<engine>/<episode>.json (resumable: existing files are
skipped), then `python -m bot.fidelity.aggregate` builds the tables.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path

from .fixture import load_fixture, load_split
from .score import score

C56_IDS: dict[str, int] = {}


@dataclass
class Traj:
    side: int
    root: int
    tower_slot: int | None
    first_tick: int
    rows: dict = field(default_factory=dict)


def make_engine(kind: str, issue_offset: int):
    from . import engines
    if kind == "clasher":
        return engines.OursEngine(C56_IDS, issue_offset=issue_offset)
    if kind == "rsim15535":
        return engines.RsimEngine(C56_IDS, client="15.535.29", issue_offset=issue_offset)
    if kind == "rsim16402":
        return engines.RsimEngine(C56_IDS, client="16.402", issue_offset=issue_offset)
    raise ValueError(kind)


def replay(fix, eng, max_retry: int = 10):
    eng.reset(fix)
    plays = sorted(fix.plays, key=lambda p: (p.exec_tick + eng.issue_offset, p.side, p.slot))
    pending = []  # (due_tick, attempts, play)
    pi = 0
    truth_ticks = set(fix.ticks)
    sim: dict[int, Traj] = {}
    deploy_log = {"issued": 0, "retried": 0, "dropped": 0, "delay_ticks": 0}
    end = fix.end_tick
    game_end_tick = None
    while eng.tick < end:
        t = eng.tick
        while pi < len(plays) and plays[pi].exec_tick + eng.issue_offset <= t:
            pending.append((t, 0, plays[pi])); pi += 1
        still = []
        for due, att, p in pending:
            if eng.deploy(p):
                deploy_log["issued"] += 1
                deploy_log["delay_ticks"] += t - (p.exec_tick + eng.issue_offset)
                if att:
                    deploy_log["retried"] += 1
            elif att + 1 >= max_retry:
                deploy_log["dropped"] += 1
            else:
                still.append((due, att + 1, p))
        pending = still
        t_before = eng.tick
        eng.step()
        t = eng.tick
        for u in eng.units():
            tr = sim.get(u.key)
            if tr is None:
                tr = sim[u.key] = Traj(u.side, u.root, u.tower_slot, t)
            if t in truth_ticks:
                tr.rows[t] = (u.x, u.y, u.hp)
        if eng.tick <= t_before or getattr(getattr(eng, "b", None), "game_over", False) is True:
            # Engine's battle is over: score its frozen state for the rest of the fixture.
            game_end_tick = eng.tick
            snap = [(u.key, (u.x, u.y, u.hp)) for u in eng.units()]
            for tt in fix.ticks:
                if tt > eng.tick and tt <= end:
                    for k, row in snap:
                        sim[k].rows[tt] = row
            break
    # sim units never present on a truth tick still count via first_tick rows: give them their first row
    for k, tr in list(sim.items()):
        if not tr.rows:
            del sim[k]
        elif tr.first_tick not in tr.rows:
            tr.first_tick = min(tr.rows)
    deploy_log["engine_game_end_tick"] = game_end_tick
    return sim, deploy_log


def run_one(args):
    kind, ep, data, split_json, out, issue_offset = args
    dst = Path(out) / kind / f"{ep}.json"
    if dst.exists():
        return ep, "skip"
    try:
        os.nice(0)
        splits = load_split(Path(split_json))
        fix = load_fixture(Path(data) / ep, splits)
        id_to_name = {v: k for k, v in C56_IDS.items()}
        t0 = time.time()
        eng = make_engine(kind, issue_offset)
        sim, dlog = replay(fix, eng)
        elapsed = time.time() - t0
        ticks = [t for t in fix.ticks if fix.start_tick <= t <= fix.end_tick]
        res = score(fix.units, sim, ticks, lambda cid: id_to_name.get(cid, f"unrooted:{cid}"))
        last = max(ticks)
        def crowns(units):
            lost = {0: set(), 1: set()}
            for u in units.values():
                if u.tower_slot is not None and last not in u.rows:
                    lost[u.side].add(u.tower_slot)
            return [3 if 0 in lost[1] else len(lost[1]), 3 if 0 in lost[0] else len(lost[0])]
        tc, sc = crowns(fix.units), crowns(sim)
        sign = lambda c: (c[0] > c[1]) - (c[0] < c[1])
        res.update(truth_crowns=tc, sim_crowns=sc, winner_agrees=sign(tc) == sign(sc), crowns_equal=tc == sc)
        res.update(episode=ep, split=fix.split, engine=kind, issue_offset=issue_offset,
                   deploy=dlog, counters=dict(eng.counters), n_plays=len(fix.plays),
                   sim_seconds=elapsed, ticks=fix.end_tick - fix.start_tick)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(res))
        tmp.rename(dst)
        return ep, "ok"
    except Exception:
        err = Path(out) / kind / f"{ep}.err"
        err.parent.mkdir(parents=True, exist_ok=True)
        err.write_text(traceback.format_exc())
        return ep, "err"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--ids", required=True, help="json name->native card id (C56)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--episodes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--issue-offset", type=int, default=0)
    a = ap.parse_args()
    C56_IDS.update(json.loads(Path(a.ids).read_text()))
    splits = load_split(Path(a.split))
    if a.episodes:
        eps = a.episodes.split(",")
    else:
        eps = sorted(e for e in os.listdir(a.data) if splits.get(e) in ("train", "validation"))
    eps = [e for e in eps if splits.get(e) in ("train", "validation")]
    if a.limit:
        eps = eps[: a.limit]
    jobs = [(a.engine, e, a.data, a.split, a.out, a.issue_offset) for e in eps]
    with Pool(a.workers, initializer=C56_IDS.update, initargs=(dict(C56_IDS),)) as pool:
        for ep, st in pool.imap_unordered(run_one, jobs):
            print(ep, st, flush=True)


if __name__ == "__main__":
    main()
