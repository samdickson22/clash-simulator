"""Capture building command anchors in the task-owned offline native engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.data import CardDataLoader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    loader = CardDataLoader()
    cases = []
    for name in ["Tesla", "Cannon", "Xbow"]:
        stats = loader.get_card(name)
        card_id = stats._raw_entry["id"]
        for x in [7500, 7800, 8000, 8200]:
            config = json.loads(args.config.read_text())
            names = [
                "Musketeer",
                "Skeletons",
                name,
                "HogRider",
                "IceGolem",
                "IceSpirit",
                "Fireball",
                "Log",
            ]
            for owner in (0, 1):
                deck = list(names)
                if owner:
                    deck[2], deck[3] = deck[3], deck[2]
                config["battle"][f"deck{owner}"]["sp"] = [
                    {"d": loader.get_card(n)._raw_entry["id"]} for n in deck
                ]
            encoded = json.dumps(config, separators=(",", ":"))
            request(args.port, "configure " + encoded)
            request(args.port, "step 70")
            before = request(args.port, "observe")
            actions = []
            commands = []
            for owner in (0, 1):
                player = next(p for p in before["players"] if p["owner"] == owner)
                card = next(c for c in player["hand"] if c["cardId"] == card_id)
                y = (10000 if owner == 0 else 21000) + x % 1000
                actions.extend([owner, card["handIndex"], x, y])
                commands.append([x, y])
            frame = request(args.port, "play 1 25 2 " + " ".join(map(str, actions)))
            assert not frame["truncated"]
            filename = f"{name}-{x}.json"
            (args.output / filename).write_text(
                json.dumps(
                    {"config": config, "before": before, "after": frame}, indent=2
                )
                + "\n"
            )
            for owner in (0, 1):
                objects = [
                    o
                    for o in frame["objects"]
                    if o.get("cardId") == card_id
                    and o["owner"] == owner
                    and o["hp"] is not None
                ]
                assert len(objects) == 1, objects
                obj = objects[0]
                cases.append(
                    {
                        "card": name,
                        "owner": owner,
                        "radius": stats.collision_radius,
                        "command_xy": commands[owner],
                        "native_xy": [obj["x"], obj["y"]],
                        "capture": filename,
                    }
                )
    (args.output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
