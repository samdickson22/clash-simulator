"""Record aligned body and tower trajectories for a captured fixed placement case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    case = json.loads(args.case.read_text())
    request(26789, "configure " + json.dumps(case["config"], separators=(",", ":")))
    request(26789, "step 70")
    attacker = case["result"]["attacker"]
    defender = case["result"]["defender"]
    placement = case["result"]["placement"]
    deployments = [(0, attacker, Position(3.5, 14.5))]
    actions = [0, 0, 3500, 14500]
    roles = [(attacker, 5000006)]
    if placement is not None:
        deployments.append((1, defender, Position(*placement)))
        actions.extend([1, 1, round(placement[0] * 1000), round(placement[1] * 1000)])
        roles.append((defender, 5000007))
    pre = request(26789, f"play 1 21 {len(deployments)} " + " ".join(map(str, actions)))
    b = BattleState()
    for _ in range(91):
        b.step()
    tower_ids = {
        o["nativeObjectId"]: next(
            e.id
            for e in b.entities.values()
            if e.player_id == o["owner"] and round(e.position.x * 1000) == o["x"]
        )
        for o in pre["objects"]
    }
    for owner, name, p in deployments:
        b.players[owner].hand = [name]
        assert b.deploy_card(owner, name, p)
    frames = []
    first_difference = {}
    for tick in range(92, case["result"]["end_tick"] + 1):
        request(26789, "step 1")
        native = request(26789, "observe")
        b.step()
        scalar = []
        for name, nid in roles:
            s = next(
                (
                    e
                    for e in b.entities.values()
                    if e.card_stats.name == name and e.entity_kind in (0, 1)
                ),
                None,
            )
            n = next((e for e in native["objects"] if e["nativeObjectId"] == nid), None)
            scalar.append(
                None
                if s is None
                else {
                    "name": name,
                    "x": round(s.position.x * 1000),
                    "y": round(s.position.y * 1000),
                    "hp": s.hitpoints,
                    "target_id": s.target_id,
                    "hidden": getattr(s, "_hidden_building", None),
                    "jump": getattr(s, "_river_jump_active", False),
                    "cooldown": s.attack_cooldown,
                }
            )
            differences = []
            if bool(s) != bool(n):
                differences.append("presence")
            elif s is not None:
                if [round(s.position.x * 1000), round(s.position.y * 1000)] != [
                    n["x"],
                    n["y"],
                ]:
                    differences.append("position")
                if (s.position.x * 1000 - n["x"]) ** 2 + (
                    s.position.y * 1000 - n["y"]
                ) ** 2 > 100**2:
                    differences.append("position_over_0p1_tile")
                if s.hitpoints != n["hp"]:
                    differences.append("hp")
            for field in differences:
                key = name + "-" + field
                if key not in first_difference:
                    first_difference[key] = tick
                    (args.output / (key + "-first.json")).write_text(
                        json.dumps(request(26789, "observe-atomic"), indent=2) + "\n"
                    )
        tower_hp = {
            str(nid): {
                "native": next(
                    (o["hp"] for o in native["objects"] if o["nativeObjectId"] == nid),
                    0,
                ),
                "scalar": b.entities[sid].hitpoints if sid in b.entities else 0,
            }
            for nid, sid in tower_ids.items()
        }
        if "tower_hp" not in first_difference and any(
            v["native"] != v["scalar"] for v in tower_hp.values()
        ):
            first_difference["tower_hp"] = tick
            (args.output / "tower-hp-first.json").write_text(
                json.dumps(request(26789, "observe-atomic"), indent=2) + "\n"
            )
        frames.append(
            {"tick": tick, "native": native, "scalar": scalar, "tower_hp": tower_hp}
        )
    (args.output / "frames.json").write_text(json.dumps(frames) + "\n")
    (args.output / "first-differences.json").write_text(
        json.dumps(first_difference, indent=2) + "\n"
    )
    print(json.dumps(first_difference, indent=2))


if __name__ == "__main__":
    main()
