"""Feasibility spike: RoyaleSim in-memory clone (Clasher fork of 0.1.34, see patch_clone.py).

    PYTHONPATH=REPO forkvenv/bin/python -m bot.rsim_fork.clone_test --episodes a,b,... [--out OUT.json]

Per fixture (15.535.29 arm, the replay script from bot.fidelity):
  1. replay to tick T (1/3 and 2/3 of the fixture), then
  2. timing: clone() x200, restore_from() x200, save()+load() x50 (median us);
  3. determinism: c = b.clone(); step b and c with the SAME remaining script for up to 600 ticks and compare
     state_hash() every tick; also compare against a fresh replay from scratch to the same tick;
  4. independence: c2 = b.clone(); step c2 with NO commands for 200 ticks; b's hash must be unchanged.
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
from pathlib import Path

import royalesim

from bot.fidelity.engines import RsimEngine
from bot.fidelity.fixture import load_fixture, load_split

D = Path("/mpac/sdicks02/repos/clasher-bot-data")
IDS = json.loads((Path(__file__).resolve().parents[1] / "fidelity" / "c56_native_ids.json").read_text())


def script_iter(fix):
    plays = sorted(fix.plays, key=lambda p: (p.exec_tick - 1, p.side, p.slot))
    return plays


def advance(eng, plays, pi, to_tick):
    """Replay the script on adapter `eng` until eng.tick == to_tick. Returns new play index."""
    while eng.tick < to_tick:
        t = eng.tick
        while pi < len(plays) and plays[pi].exec_tick - 1 <= t:
            eng.deploy(plays[pi]); pi += 1
        eng.step()
    return pi


def fork_adapter(eng, battle):
    e2 = copy.copy(eng)
    e2.b = battle
    e2._state = None
    e2._pending = list(eng._pending)
    e2.counters = copy.copy(eng.counters)
    return e2


def med_us(fn, reps):
    ts = []
    for _ in range(reps):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return 1e6 * statistics.median(ts)


def run(fix):
    out = []
    plays = script_iter(fix)
    span = fix.end_tick - fix.start_tick
    for frac in (1 / 3, 2 / 3):
        T = fix.start_tick + int(span * frac)
        eng = RsimEngine(IDS, client="15.535.29")
        eng.reset(fix)
        pi = advance(eng, plays, 0, T)
        b = eng.b
        units = len(json.loads(b.state_json())["entities"])
        spare = eng.b.clone()
        r = dict(episode=fix.episode, tick=T, units=units,
                 clone_us=med_us(lambda: b.clone(), 200),
                 restore_us=med_us(lambda: spare.restore_from(b), 200))
        blob = b.save()
        r["save_us"] = med_us(lambda: b.save(), 50)
        r["load_us"] = med_us(lambda: spare.load(blob), 50)
        # determinism: original vs clone on the same remaining script
        h0 = b.state_hash()
        c = fork_adapter(eng, b.clone())
        assert c.b.state_hash() == h0
        end = min(fix.end_tick, T + 600)
        mism = 0; ticks = 0; pa = pc = pi
        while eng.tick < end and c.tick < end:
            pa = advance(eng, plays, pa, eng.tick + 1)
            pc = advance(c, plays, pc, c.tick + 1)
            ticks += 1
            if eng.b.state_hash() != c.b.state_hash():
                mism += 1
        r["det_ticks"], r["det_mismatch"] = ticks, mism
        # versus a fresh replay from scratch to the same tick
        fresh = RsimEngine(IDS, client="15.535.29"); fresh.reset(fix)
        advance(fresh, plays, 0, eng.tick)
        r["fresh_equal"] = fresh.b.state_hash() == eng.b.state_hash()
        # independence: stepping a clone must not touch the original
        h1 = eng.b.state_hash()
        c2 = eng.b.clone(); c2.step([], 200)
        r["independent"] = eng.b.state_hash() == h1 and c2.state_hash() != h1
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    print("royalesim", royalesim.__file__, royalesim.Battle.provenance())
    splits = load_split(D / "t1-split.json")
    rows = []
    for ep in a.episodes.split(","):
        fix = load_fixture(D / "t1-trainval" / ep, splits)
        for r in run(fix):
            rows.append(r); print(json.dumps(r), flush=True)
    s = dict(n=len(rows),
             clone_us_median=statistics.median(r["clone_us"] for r in rows),
             clone_us_max=max(r["clone_us"] for r in rows),
             restore_us_median=statistics.median(r["restore_us"] for r in rows),
             save_load_us_median=statistics.median(r["save_us"] + r["load_us"] for r in rows),
             det_ticks=sum(r["det_ticks"] for r in rows), det_mismatch=sum(r["det_mismatch"] for r in rows),
             fresh_equal=sum(r["fresh_equal"] for r in rows), independent=sum(r["independent"] for r in rows),
             units_median=statistics.median(r["units"] for r in rows))
    print("SUMMARY", json.dumps(s))
    if a.out:
        Path(a.out).write_text(json.dumps(dict(summary=s, rows=rows), indent=1))


if __name__ == "__main__":
    main()
