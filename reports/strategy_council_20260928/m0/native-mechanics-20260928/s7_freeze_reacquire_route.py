"""Scenario 7: route used when a frozen, re-acquired, stationary Giant is pushed out of range.

Resolves the open detail of readiness/tier-a-fresh-v6/review/episode-24-mechanism.md.
Two native mechanisms fit every v6 event; they differ only when the troop is
displaced between its stop and its stationary re-acquisition:

  H1: resume the unconsumed walking route held at the stop;
  H2: rebuild the route at the stationary re-acquisition (from that position),
      consuming the first node there if the reached test (< 1001) passes.

Setup (pilot cards only: Giant, Ice Spirit, Goblins, towers). Owner 1 deploys a
Giant at (10.5, 17.5) at tick 100 (native ignores commands in the first ~2 s);
it walks the right lane and stops in range of owner 0's right Princess Tower
(tick 352, cell (28,18), remaining route [(28,16)]). Owner 0 then plays an Ice
Spirit (357) that freezes the Giant (target dropped), and Goblins (367) whose
deployment pushes the stationary Giant sideways while it stays in range, into a
different cell. The Giant re-acquires the tower standing (411). Then owner 0's
own Giant is deployed next to it (413) and pushes it out of range, so it
restarts toward the same tower from a third position (416 or 475).
Variants move the Goblins/Giant placements: in some H1 equals current scalar and
H2 does not, in the others the reverse.

All commands are static and identical on both engines. Native frames (ordinary +
rich) are read every tick; scalar is run with the current main source ("main"),
with the landed rule reverted in memory ("revert", the pre-fix behaviour), and with
the candidate models of ``s7_candidate_models.py``. Round 1 (the first five
variants) separated H1 from H2 and showed neither; round 2 separated the two
refinements H9/H11 and showed neither; H12 (resume only if the troop is still in
its stop cell and the retained head is not yet reached) matches all ten, and
is the rule landed in ``Troop.update_movement_component`` ("main").

Usage: s7_freeze_reacquire_route.py <emulator-serial> [variant ...]
       (emulator-5582 only for the 2026-09-30 run; one job at a time)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402
import s7_candidate_models as M  # noqa: E402

D0 = ["Fireball", "Log", "HogRider", "Prince", "Giant", "Goblins", "Knight", "IceSpirit"]
D1 = ["Zap", "Knight", "Goblins", "Cannon", "Musketeer", "IceGolem", "Archers", "Giant"]
G1 = {"tick": 100, "owner": 1, "card": "Giant", "xy": (10.5, 17.5)}
ICE = {"tick": 357, "owner": 0, "card": "IceSpirit", "xy": (14.5, 11.5)}


def cmd(tick, owner, card, xy):
    return {"tick": tick, "owner": owner, "card": card, "xy": xy}


VARIANTS = {
    # Round 1 (H1 vs H2). Goblins push the stopped Giant right into cell
    # (29,18) or left into (27,18) before the freeze; owner 0's Giant then
    # pushes it out of range after the stationary re-acquisition.
    "gob_right_push_up": [G1, ICE, cmd(367, 0, "Goblins", (14.5, 10.5)), cmd(413, 0, "Giant", (14.5, 8.5))],
    "gob_right_push_side": [G1, ICE, cmd(367, 0, "Goblins", (14.5, 10.5)), cmd(413, 0, "Giant", (16.5, 7.5))],
    "gob_left_push_up": [G1, ICE, cmd(367, 0, "Goblins", (15.5, 10.5)), cmd(413, 0, "Giant", (14.5, 8.5))],
    "gob_left_push_side": [G1, ICE, cmd(367, 0, "Goblins", (15.5, 10.5)), cmd(413, 0, "Giant", (12.5, 7.5))],
    # Control: no displacement before the re-acquisition (H1 == H2 by construction).
    "control_no_goblins": [G1, ICE, cmd(413, 0, "Giant", (14.5, 8.5))],
    # Round 2 (H9 vs H11). Displaced toward the tower inside the stop cell so
    # the retained head passes the reached test (H9 rebuilds, H11 resumes).
    "same_cell_reached_a": [cmd(100, 1, "Giant", (14.5, 19.5)), cmd(336, 0, "Goblins", (15.5, 10.5)),
                            cmd(346, 0, "IceSpirit", (14.5, 11.5)), cmd(416, 0, "Giant", (14.5, 8.5))],
    "same_cell_reached_b": [cmd(100, 1, "Giant", (15.5, 21.5)), cmd(382, 0, "Goblins", (15.5, 10.5)),
                            cmd(392, 0, "IceSpirit", (14.5, 11.5)), cmd(448, 0, "Giant", (14.5, 8.5))],
    # Displaced into another cell without reaching the head (H9 resumes, H11 rebuilds).
    "cell_change_unreached_a": [cmd(100, 1, "Giant", (11.5, 21.5)), cmd(411, 0, "IceSpirit", (13.5, 11.5)),
                                cmd(416, 0, "Goblins", (12.5, 8.5)), cmd(466, 0, "Giant", (14.5, 8.5))],
    "cell_change_unreached_b": [cmd(100, 1, "Giant", (9.5, 21.5)), cmd(419, 0, "Goblins", (14.5, 10.5)),
                                cmd(429, 0, "IceSpirit", (14.5, 11.5)), cmd(484, 0, "Giant", (15.5, 8.5))],
    # Not displaced, but the retained head is already inside the reached
    # distance at the re-acquisition (H9 rebuilds, H1/H11 resume).
    "undisplaced_reached": [cmd(100, 1, "Giant", (17.5, 19.5)), cmd(365, 0, "IceSpirit", (14.5, 11.5)),
                            cmd(370, 0, "Goblins", (15.5, 8.5)), cmd(421, 0, "Giant", (14.5, 8.5))],
}
END = 660
MODELS = ("main", "revert", "H1", "H2", "H9", "H11", "H12")
GIANT = 26000003


def giant_track(frames, engine):
    rows = []
    for f in frames:
        g = [o for o in f["objects"] if o["owner"] == 1 and (o.get("card") == GIANT or o.get("name") == "Giant")]
        if g:
            o = g[0]
            rows.append([f["tick"], o["x"], o["y"], round(o["hp"]), o.get("target")])
    return rows


def first_diff(a, b):
    ma = {r[0]: r[1:3] for r in a}
    for r in b:
        if r[0] in ma and ma[r[0]] != r[1:3]:
            return r[0]
    return None


def main():
    serial = sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"
    port = L.PORTS[serial]
    only = set(sys.argv[2:])
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(port, D0, D1, need0=("IceSpirit", "Goblins", "Giant"), need1=("Giant",),
                                        start=1609280025)
    res = {"scenario": "freeze_reacquire_route", "serial": serial, "seed": seed, "config": config,
           "initial_hands": {p["owner"]: [L.NAME_OF_ID.get(c["cardId"], c["cardId"]) for c in p["hand"]]
                             for p in initial["players"]},
           "initial": initial, "variants": {}}
    for name, extra in VARIANTS.items():
        if only and name not in only:
            continue
        cmds = extra
        row = {"commands": cmds}
        for model in MODELS:
            M.LOG.clear()
            M.install(model)
            try:
                sc = L.run_scalar(initial, config, [D0, D1], cmds, END)
            finally:
                M.uninstall()
            row[model] = {"rejected": sc["rejected"], "giant": giant_track(sc["frames"], "scalar"),
                          "events": list(M.LOG)}
        na = L.run_native(port, config, cmds, END, rich=True)
        row["native"] = {"receipts": na["receipts"], "giant": giant_track(na["frames"], "native"),
                         "bodies": {f["tick"]: [[o["id"], o["owner"], o["card"], o["x"], o["y"], o["hp"], o.get("target")]
                                                for o in f["objects"] if o["card"] != -1]
                                    for f in na["frames"] if f["tick"] >= 340}}
        n = row["native"]["giant"]
        row["first_divergence_vs_native"] = {m: first_diff(n, row[m]["giant"]) for m in MODELS}
        row["exact_ticks_vs_native"] = {
            m: sum(1 for a, b in zip(n, row[m]["giant"]) if a[:3] == b[:3]) for m in MODELS}
        res["variants"][name] = row
        print(name, "native ticks", len(n), "first divergence", row["first_divergence_vs_native"],
              "exact", row["exact_ticks_vs_native"], [e for e in row["H1"]["events"]][:2],
              [e for e in row["H2"]["events"]][:2], flush=True)
    res["provenance"] = L.provenance({"models": str(Path(M.__file__).name), "models_sha256": L.sha(Path(M.__file__))})
    L.dump("s7_freeze_reacquire_route.json", res)


if __name__ == "__main__":
    main()
