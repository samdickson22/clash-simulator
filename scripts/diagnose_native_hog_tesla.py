"""Record the predeclared Hog/Tesla placement that disagrees on tower damage."""

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
    request(26789, "play 1 21 2 0 0 3500 14500 1 1 5500 18500")
    b = BattleState()
    for _ in range(91):
        b.step()
    for owner, name, p in [
        (0, "HogRider", Position(3.5, 14.5)),
        (1, "Tesla", Position(5.5, 18.5)),
    ]:
        b.players[owner].hand = [name]
        assert b.deploy_card(owner, name, p)
    frames = []
    first_difference = {}
    for tick in range(92, 492):
        request(26789, "step 1")
        native = request(26789, "observe")
        b.step()
        scalar = []
        for name, nid in [("HogRider", 5000006), ("Tesla", 5000007)]:
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
                if s.hitpoints != n["hp"]:
                    differences.append("hp")
            for field in differences:
                key = name + "-" + field
                if key not in first_difference:
                    first_difference[key] = tick
                    (args.output / (key + "-first.json")).write_text(
                        json.dumps(request(26789, "observe-atomic"), indent=2) + "\n"
                    )
        frames.append({"tick": tick, "native": native, "scalar": scalar})
    (args.output / "frames.json").write_text(json.dumps(frames) + "\n")
    (args.output / "first-differences.json").write_text(
        json.dumps(first_difference, indent=2) + "\n"
    )
    print(json.dumps(first_difference, indent=2))


if __name__ == "__main__":
    main()
