"""Capture controlled native movement cases and aligned scalar diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader

CASES = (
    ("hog_cannon", "HogRider", "Cannon", 0),
    ("hog_cannon_reverse", "HogRider", "Cannon", 1),
    ("hog_tesla", "HogRider", "Tesla", 0),
    ("prince_cannon", "Prince", "Cannon", 0),
    ("knight_cannon", "Knight", "Cannon", 0),
    ("baby_dragon_cannon", "BabyDragon", "Cannon", 0),
)


def scalar_frames(attacker, defender, owner, ticks=120):
    battle = BattleState()
    placements = [(owner, attacker, 3.5, 14.5), (1 - owner, defender, 7.5, 19.5)]
    for seat, name, x, y in placements:
        if owner:
            x, y = 18 - x, 32 - y
        battle.players[seat].hand = [name]
        assert battle.deploy_card(seat, name, Position(x, y))
    frames = []
    for tick in range(ticks + 1):
        frames.append(
            {
                "tick": tick,
                "objects": [
                    {
                        "name": e.card_stats.name,
                        "owner": e.player_id,
                        "x": round(e.position.x * 1000),
                        "y": round(e.position.y * 1000),
                        "hp": e.hitpoints,
                        "jump": getattr(e, "_river_jump_active", False),
                    }
                    for e in battle.entities.values()
                    if e.card_stats.name in (attacker, defender)
                    and e.entity_kind in (0, 1)
                ],
            }
        )
        if tick < ticks:
            battle.step()
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    loader = CardDataLoader()
    for label, attacker, defender, owner in CASES:
        if args.case and label not in args.case:
            continue
        out = args.output / label
        out.mkdir()
        config = json.loads(args.config.read_text())
        names = [
            "Musketeer",
            "Skeletons",
            attacker,
            defender,
            "IceGolem",
            "IceSpirit",
            "Fireball",
            "Log",
        ]
        if owner:
            names[2], names[3] = names[3], names[2]
        ids = {name: loader.get_card(name)._raw_entry["id"] for name in names}
        for seat in (0, 1):
            config["battle"][f"deck{seat}"]["sp"] = [{"d": ids[n]} for n in names]
        encoded = json.dumps(config, separators=(",", ":"))
        (out / "config.json").write_text(encoded + "\n")
        request(args.port, "configure " + encoded)
        request(args.port, "step 70")
        before = request(args.port, "observe")
        actions = []
        for seat, name, x, y in (
            (owner, attacker, 3500, 14500),
            (1 - owner, defender, 7500, 19500),
        ):
            if owner:
                x, y = 18000 - x, 32000 - y
            player = next(p for p in before["players"] if p["owner"] == seat)
            card = next(c for c in player["hand"] if c["cardId"] == ids[name])
            actions.extend([seat, card["handIndex"], x, y])
        first = request(args.port, "play 1 1 2 " + " ".join(map(str, actions)))
        native = [before, first]
        for tick in range(2, 142):
            request(args.port, "step 1")
            frame = request(args.port, "observe")
            assert not frame["truncated"]
            native.append(frame)
        assert any(o.get("cardId") == ids[attacker] for o in native[42]["objects"])
        (out / "native.json").write_text(json.dumps(native) + "\n")
        (out / "scalar.json").write_text(
            json.dumps(scalar_frames(attacker, defender, owner)) + "\n"
        )
        (out / "case.json").write_text(
            json.dumps(
                {
                    "attacker": attacker,
                    "defender": defender,
                    "owner": owner,
                    "ids": ids,
                    "scope": "Null's15.535.86 reference versus July scalar; deployment phases must be aligned. No official parity claim.",
                },
                indent=2,
            )
            + "\n"
        )
        print(label, "captured", flush=True)


if __name__ == "__main__":
    main()
