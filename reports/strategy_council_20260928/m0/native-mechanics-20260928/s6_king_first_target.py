"""Scenario 6: King first-target lock during the activation first-hit phase.

Per-tick native confirmation of the episode-05 mechanism
(../readiness/tier-a-fresh-v3/diagnostic/episode-05-mechanism.md) and of the
scalar repair in ``Building._update_active_combat``.

Setup: the tier-a-fresh-v3 episode-05 battle is replayed from its native config
with identical commands on both engines: the capture prefix (ticks < 1185) and
the recorded native branch job-00161 (balanced/pressure, immediate_play Archers
action 1796) through tick END. Owner 0's Giant/Dark Prince/Goblins push destroys
owner 1's left Princess Tower (~2290); that activates the owner-1 King (3.3 s
activation ends 2355, 0.7 s first-hit phase ends 2369) while two owner-0
Goblins approach it and swap nearest-distance order during the phase (~2363).
This is a recorded, verified swap; a fresh synthetic geometry could not be
validated without an emulator when this script was written.

Variants deploy owner 0's Goblins (recorded at tick 2135) 10/30/60 ticks later.
This moves the tower fall, the activation phase and the Goblins' approach, which
gives extra lock-timing samples; in shift60 the locked Goblin dies inside the
phase (does native re-lock mid-phase?). Every variant issues the same commands
to both engines.

Observed every tick from WINDOW_START to END on native (ordinary + rich frames:
King ``targetEntityKey`` and ``attackTimelineMs``, projectile source/target) and
on scalar; per tick: King HP/target, each owner-0 Goblin position/HP/distance to
the King, the nearest Goblin, and new King projectiles. Summary per engine: the
first tick the King holds a Goblin target, whether it keeps that lock after the
nearest order flips, and the first shot's tick and target. Engines are matched by
target position (within MATCH_TILES), not by object id.

The baseline variant also checks that native reproduces recorded job-00161
frames 2355..2370 (King target and Goblin positions).

Usage (one emulator; DO NOT run while readiness shards hold the emulators):
  s6_king_first_target.py --serial emulator-5582 [--variants baseline,shift2]
  s6_king_first_target.py --port 26790
  s6_king_first_target.py --scalar-only          # no emulator, scalar side only
"""

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

from clasher.arena import Position  # noqa: E402
from clasher.entities import Projectile  # noqa: E402
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS  # noqa: E402

TIER = L.ROOT / "reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v3"
CAPTURE = TIER / "prefixes/episode-05"
NATIVE_JOB = TIER / "branches-reference-shard0-of8/job-00161"
ROOT_TICK = 1185
GOBLIN_TICK = 2135
WINDOW_START = 2340
END = 2425
KING_XY = (9000, 29000)
KING_OWNER = 1
MATCH_TILES = 0.1
GOBLINS_ID = 26000002
EXPECTED_SHA = {
    "initial.json": "459adbd71a05a49dffde77b5d16bfc715f6ce2f6353b1fae86b2cb5fab17fdd9",
    "plan.json": "315176ad0dba7f36433fa0e5db65c074eb392b234c3d2f5645b24372de9a8c0f",
    "result.json": "342b091a4da136ca84fd01ff57cc393d12130c4cdc1cc261ab55e5274eab6787",
    "gamedata.json": "daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3",
}
NATIVE_DECISIONS_SHA = "0a033ab43f9134483417594841ae1260d88f96464b3be597cf2e6adee292b5b5"
# Scalar (repaired) pre-check of each variant: baseline locks 2356, nearest
# flips 2363, shot 2369; shift10 phase 2362-2375; shift30 phase 2382-2395;
# shift60 phase 2403-2417 with the locked Goblin killed at 2415 (re-lock case).
VARIANTS = {"baseline": 0, "shift10": 10, "shift30": 30, "shift60": 60}


def load_inputs():
    for name, digest in EXPECTED_SHA.items():
        assert L.sha(CAPTURE / name) == digest, name
    assert L.sha(NATIVE_JOB / "decisions.jsonl.gz") == NATIVE_DECISIONS_SHA
    config = json.loads((CAPTURE / "plan.json").read_text())["config"]
    initial = json.loads((CAPTURE / "initial.json").read_text())
    prefix = [
        {"tick": c["submitted_tick"], "owner": c["owner"], "card": c["name"], "xy": tuple(c["xy"])}
        for c in json.loads((CAPTURE / "result.json").read_text())["commands"]
        if c["submitted_tick"] < ROOT_TICK
    ]
    branch = []
    for line in gzip.open(NATIVE_JOB / "transport.jsonl.gz", "rt"):
        record = json.loads(line)
        if record["tick"] > END:
            break
        for sel in record["selected"]:
            if sel["name"] is not None:
                branch.append({"tick": record["tick"], "owner": sel["owner"],
                               "card": sel["name"], "xy": tuple(sel["xy"])})
    recorded = {}
    for line in gzip.open(NATIVE_JOB / "decisions.jsonl.gz", "rt"):
        record = json.loads(line)
        if 2355 <= record["tick"] <= 2370:
            frame = record["native_frame"]
            rich = {o["nativeObjectId"]: o for o in frame["rich"]["objects"]}
            recorded[record["tick"]] = {
                "king_target": next(
                    ((rich.get(o["nativeObjectId"], {}).get("targetEntityKey") or [0, 0, None])[2]
                     for o in frame["ordinary"]["objects"]
                     if (o["x"], o["y"]) == KING_XY and o["owner"] == KING_OWNER), None),
                "goblins": {o["nativeObjectId"]: (o["x"], o["y"])
                            for o in frame["ordinary"]["objects"]
                            if o["cardId"] == GOBLINS_ID and o["owner"] == 0},
            }
        if record["tick"] > 2370:
            break
    return config, initial, prefix, branch, recorded


def commands_for(prefix, branch, shift):
    out = list(prefix)
    for c in branch:
        if shift and c["tick"] == GOBLIN_TICK and c["owner"] == 0 and c["card"] == "Goblins":
            c = dict(c, tick=c["tick"] + shift)
        out.append(c)
    return sorted(out, key=lambda c: (c["tick"], c["owner"]))


def tile_distance(xy):
    return math.hypot(xy[0] - KING_XY[0], xy[1] - KING_XY[1]) / 1000


# ------------------------------------------------------------------ engines --

def run_native(port, config, commands):
    """Replay natively; observe (ordinary + rich) every tick from WINDOW_START."""
    L.configure_single(port, config)
    probe = L.Probe(port)
    try:
        gate = probe("render off")
        assert gate.get("renderSuppressed") is True, gate
        by_tick = {}
        for c in commands:
            by_tick.setdefault(c["tick"], []).append(c)
        frames, receipts = [], []
        tick = probe("observe")["tick"]
        assert tick == 0
        while tick < END:
            for c in by_tick.get(tick, []):
                x, y = (round(v * 1000) for v in c["xy"])
                receipt = probe(
                    f"replay-schedule-card {c['owner']} {L.card_id(c['card'])} {x} {y} {tick + 1}")
                receipts.append({"tick": tick, "command": c, "receipt": receipt})
            stepped = probe("step 1")
            assert stepped["tick"] == tick + 1, stepped
            tick += 1
            if tick >= WINDOW_START:
                frame = L.native_frame(probe, rich=True)
                assert frame["tick"] == tick
                frames.append(frame)
                if frame["ended"]:
                    break
        return {"frames": frames, "receipts": receipts}
    finally:
        try:
            probe("render on")
        finally:
            probe.close()


def run_scalar(initial, config, commands):
    """Same commands on scalar (deploy at the submitted tick, as nm_lib does)."""
    # nm_lib's loader reads the snapshot gamedata, the same daa58b28 ruleset
    # as the capture (asserted in main).
    battle = L.scalar_from_initial(initial, config, [PUBLIC_REFERENCE_CARDS])
    king = next(e for e in battle.entities.values()
                if e.player_id == KING_OWNER and e.card_stats.name == "KingTower")
    by_tick = {}
    for c in commands:
        by_tick.setdefault(c["tick"], []).append(c)
    frames, rejected, seen = [], [], set(battle.entities)
    while battle.tick < END and not battle.game_over:
        for c in by_tick.get(battle.tick, []):
            if not battle.deploy_card(c["owner"], c["card"], Position(*c["xy"])):
                rejected.append(dict(c, tick=battle.tick))
        battle.step()
        new_shots = []
        for identity, entity in battle.entities.items():
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(entity, Projectile) and entity.source_entity is king:
                target = entity.primary_target
                new_shots.append({"id": identity, "target": getattr(target, "id", None)})
        if battle.tick >= WINDOW_START:
            frame = L.scalar_frame(battle)
            frame["king_shots"] = new_shots
            frames.append(frame)
    return {"frames": frames, "rejected": rejected}



# ----------------------------------------------------------------- analysis --

def king_rows(frames, engine):
    """Per-tick King target and Goblin distances for one engine."""
    rows, seen_projectiles = [], set()
    for f in frames:
        objs = f["objects"]
        king = next((o for o in objs if o["owner"] == KING_OWNER and (o["x"], o["y"]) == KING_XY
                     and o.get("hp") is not None), None)
        if king is None:
            continue
        if engine == "native":
            goblins = [o for o in objs if o.get("card") == GOBLINS_ID and o["owner"] == 0]
        else:
            goblins = [o for o in objs if o["name"] == "Goblins" and o["owner"] == 0 and o["hp"] > 0]
        by_id = {o["id"]: o for o in objs}
        gob = sorted(({"id": o["id"], "xy": [o["x"], o["y"]], "hp": o["hp"],
                       "d": round(tile_distance((o["x"], o["y"])), 3)} for o in goblins),
                     key=lambda g: g["d"])
        target = king.get("target")
        target_obj = by_id.get(target)
        if engine == "native":
            troop = bool(target_obj) and target_obj["owner"] != KING_OWNER and target_obj["card"] != -1
        else:
            troop = bool(target_obj) and target_obj["owner"] != KING_OWNER and \
                target_obj["name"] not in ("Tower", "KingTower")
        shots = []
        if engine == "native":
            for o in objs:
                if o.get("source") == king["id"] and o["id"] not in seen_projectiles:
                    seen_projectiles.add(o["id"])
                    t = by_id.get(o.get("target"))
                    shots.append({"id": o["id"], "target": o.get("target"),
                                  "target_xy": [t["x"], t["y"]] if t else None})
        else:
            for s in f.get("king_shots", []):
                t = by_id.get(s["target"])
                shots.append(dict(s, target_xy=[t["x"], t["y"]] if t else None))
        rows.append({
            "tick": f["tick"], "king_hp": king["hp"], "target": target,
            "target_xy": [target_obj["x"], target_obj["y"]] if target_obj else None,
            "target_is_goblin": any(g["id"] == target for g in gob),
            "target_is_troop": troop,
            "timeline": king.get("timeline"),
            "activation_delay_remaining": king.get("activation_delay_remaining"),
            "first_hit_remaining": king.get("activation_first_hit_delay_remaining"),
            "goblins": gob, "nearest": gob[0]["id"] if gob else None, "shots": shots,
        })
    return rows


def summarize(rows):
    lock = next((r for r in rows if r["target_is_troop"]), None)
    first = next(((r["tick"], s) for r in rows for s in r["shots"]), None)
    out = {"lock_tick": lock["tick"] if lock else None,
           "lock_target": lock["target"] if lock else None,
           "lock_target_xy": lock["target_xy"] if lock else None,
           "first_shot_tick": first[0] if first else None,
           "first_shot_target": first[1]["target"] if first else None,
           "first_shot_target_xy": first[1]["target_xy"] if first else None,
           "nearest_flip_ticks": [], "lock_kept_after_flip": None}
    if lock is None:
        return out
    held, prev = True, None
    for r in rows:
        if r["tick"] < out["lock_tick"] or (first and r["tick"] > first[0]):
            continue
        if prev is not None and r["nearest"] != prev:
            out["nearest_flip_ticks"].append(r["tick"])
        prev = r["nearest"]
        if r["target"] != out["lock_target"]:
            held = False
    if out["nearest_flip_ticks"]:
        out["lock_kept_after_flip"] = held
    return out


def same_xy(a, b):
    return a is not None and b is not None and math.dist(a, b) / 1000 <= MATCH_TILES


def compare(native_rows, scalar_rows, ns, ss):
    by_tick = {r["tick"]: r for r in scalar_rows}
    per_tick = []
    for n in native_rows:
        s = by_tick.get(n["tick"])
        if s is None:
            continue
        per_tick.append({"tick": n["tick"],
                         "hp": [n["king_hp"], s["king_hp"]],
                         "target_match": (n["target_is_troop"] == s["target_is_troop"])
                         and (not n["target_is_troop"] or same_xy(n["target_xy"], s["target_xy"]))})
    return {
        # Scalar lists a projectile on its launch tick; a +/-1 delta may be
        # native object-visibility order rather than a timing difference.
        "first_shot_tick_delta": (ss["first_shot_tick"] - ns["first_shot_tick"])
        if ns["first_shot_tick"] is not None and ss["first_shot_tick"] is not None else None,
        "first_shot_target_match": same_xy(ns["first_shot_target_xy"], ss["first_shot_target_xy"]),
        "lock_tick_delta": (ss["lock_tick"] - ns["lock_tick"])
        if ns["lock_tick"] is not None and ss["lock_tick"] is not None else None,
        "target_mismatch_ticks": [r["tick"] for r in per_tick if not r["target_match"]],
        "king_hp_mismatch_ticks": [r["tick"] for r in per_tick if r["hp"][0] != r["hp"][1]],
    }


def recorded_check(native_rows, recorded):
    """Native replay reproduces recorded job-00161 frames 2355..2370."""
    by_tick = {r["tick"]: r for r in native_rows}
    out = {}
    for tick, rec in sorted(recorded.items()):
        row = by_tick.get(tick)
        if row is None:
            out[tick] = None
            continue
        got = {g["id"]: tuple(g["xy"]) for g in row["goblins"]}
        out[tick] = {"king_target": row["target"] == rec["king_target"],
                     "goblins": got == rec["goblins"]}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--serial", help="emulator serial, e.g. emulator-5582")
    where.add_argument("--port", type=int, help="native probe port, e.g. 26790")
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--scalar-only", action="store_true")
    parser.add_argument("--output", default="s6_king_first_target.json")
    args = parser.parse_args()
    port = None
    if not args.scalar_only:
        port = args.port if args.port is not None else L.PORTS[args.serial or "emulator-5582"]
        assert L.free_gib() > 8
    config, initial, prefix, branch, recorded = load_inputs()
    assert L.sha(L.GAMEDATA) == EXPECTED_SHA["gamedata.json"]
    results = {"scenario": "king_first_target_lock", "port": port, "serial": args.serial,
               "capture": str(CAPTURE.relative_to(L.ROOT)),
               "native_branch": str(NATIVE_JOB.relative_to(L.ROOT)),
               "window": [WINDOW_START, END], "variants": {}}
    for name in args.variants.split(","):
        commands = commands_for(prefix, branch, VARIANTS[name])
        sc = run_scalar(initial, config, commands)
        s_rows = king_rows(sc["frames"], "scalar")
        entry = {"goblin_shift_ticks": VARIANTS[name], "scalar_rejected": sc["rejected"],
                 "scalar": summarize(s_rows), "scalar_rows": s_rows}
        if port is not None:
            na = run_native(port, config, commands)
            n_rows = king_rows(na["frames"], "native")
            entry.update({
                "native_rejected": [r for r in na["receipts"] if not r["receipt"].get("ok")],
                "native": summarize(n_rows), "native_rows": n_rows,
            })
            entry["compare"] = compare(n_rows, s_rows, entry["native"], entry["scalar"])
            if VARIANTS[name] == 0:
                entry["recorded_job_00161_match"] = recorded_check(n_rows, recorded)
        results["variants"][name] = entry
        print(name, "scalar", {k: entry["scalar"][k] for k in
                               ("lock_tick", "nearest_flip_ticks", "lock_kept_after_flip",
                                "first_shot_tick", "first_shot_target_xy")},
              "native", entry.get("native") and {k: entry["native"][k] for k in
                                                ("lock_tick", "nearest_flip_ticks",
                                                 "lock_kept_after_flip", "first_shot_tick",
                                                 "first_shot_target_xy")},
              "compare", entry.get("compare"), flush=True)
    results["provenance"] = L.provenance({"producer": str(Path(__file__).relative_to(L.ROOT)),
                                          "producer_sha256": L.sha(Path(__file__))})
    L.dump(args.output, results)


if __name__ == "__main__":
    main()
