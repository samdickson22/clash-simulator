"""Record a controlled Null's-engine interaction without claiming official parity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    names = [
        "Musketeer",
        "Skeletons",
        "HogRider",
        "Cannon",
        "IceGolem",
        "IceSpirit",
        "Fireball",
        "Log",
    ]
    loader = CardDataLoader()
    ids = {name: loader.get_card(name)._raw_entry["id"] for name in names}
    config = json.loads(args.config.read_text())
    for owner in (0, 1):
        config["battle"][f"deck{owner}"]["sp"] = [{"d": ids[name]} for name in names]
    encoded = json.dumps(config, separators=(",", ":"))
    (args.output / "config.json").write_text(encoded + "\n")
    request(args.port, "configure " + encoded)
    request(args.port, "step 70")
    before = request(args.port, "observe")
    tuples = []
    for owner, name, x, y in ((0, "HogRider", 3500, 14500), (1, "Cannon", 7500, 19500)):
        player = next(p for p in before["players"] if p["owner"] == owner)
        card = next(c for c in player["hand"] if c["cardId"] == ids[name])
        tuples.extend([owner, card["handIndex"], x, y])
    first = request(args.port, "play 1 1 2 " + " ".join(map(str, tuples)))
    frames = [before, first]
    for _ in range(199):
        request(args.port, "step 1")
        frame = request(args.port, "observe")
        if frame["truncated"]:
            raise ValueError("native trace truncated")
        frames.append(frame)
    (args.output / "native-frames.json").write_text(json.dumps(frames) + "\n")

    # The owned simulator remains pinned to July; retain a diagnostic alongside
    # the native trace rather than falsely declaring matching external rulesets.
    battle = BattleState()
    for _ in range(70):
        battle.step()
    for owner, name, x, y in ((0, "HogRider", 3.5, 14.5), (1, "Cannon", 7.5, 19.5)):
        battle.players[owner].hand = [name]
        assert battle.deploy_card(owner, name, Position(x, y))
    scalar = []
    for tick in range(201):
        scalar.append(
            {
                "relative_tick": tick,
                "entities": [
                    {
                        "id": e.id,
                        "owner": e.player_id,
                        "name": e.card_stats.name if e.card_stats else None,
                        "x": e.position.x,
                        "y": e.position.y,
                        "hp": e.hitpoints,
                        "alive": e.is_alive,
                        "target_id": getattr(e, "target_id", None),
                    }
                    for e in battle.entities.values()
                ],
            }
        )
        if tick < 200:
            battle.step()
    (args.output / "scalar-frames.json").write_text(json.dumps(scalar) + "\n")
    result = {
        "status": "native_and_scalar_diagnostic_traces_recorded",
        "native_frames": len(frames),
        "scalar_frames": len(scalar),
        "native_tick_range": [frames[0]["tick"], frames[-1]["tick"]],
        "config_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "native_final_objects": frames[-1]["objects"],
        "limitations": [
            "Null's15.535.86 is not an official-game reference.",
            "Scalar July ruleset differs; no global parity claim.",
            "Commands scheduled one tick ahead natively; align accepted command/deployment phases before timing comparison.",
            "Scalar initial hand overridden only to make the controlled setup legal.",
        ],
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Recorded", len(frames), "native frames and", len(scalar), "scalar frames")


if __name__ == "__main__":
    main()
