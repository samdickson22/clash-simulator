"""Compare ordinary native bodies with scalar frames in a recorded development game."""

import argparse
import hashlib
import json
import math
from collections import defaultdict
from itertools import permutations
from pathlib import Path

from collect_public_development_games import DECKS

from clasher.data import CardDataLoader


def read_json(path):
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-game", type=Path, required=True)
    parser.add_argument("--scalar-frames", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference, reference_sha = read_json(args.native_game)
    scalar, scalar_sha = read_json(args.scalar_frames)
    frames = {frame["tick"]: frame["scalar"] for frame in scalar}
    assert len(frames) == len(scalar), "duplicate scalar ticks"
    loader = CardDataLoader()
    names = {}
    decks = reference.get("decks", DECKS)
    for name in sorted({name for deck in decks for name in deck}):
        card = loader.get_card(name)
        names[card.name] = card._raw_entry["id"]
    differences = []
    paired_bodies = 0
    exact_positions = 0
    exact_hitpoints = 0
    for checkpoint in reference["checkpoints"]:
        tick = checkpoint["tick"]
        native_groups = defaultdict(list)
        scalar_groups = defaultdict(list)
        for entity in checkpoint["native"]["objects"]:
            if entity["hp"] is not None and entity["cardId"] != -1:
                native_groups[(entity["owner"], entity["cardId"])].append(entity)
        for entity in frames[tick]:
            if entity["id"] > 6 and entity["kind"] in (0, 1):
                # Unknown cards fail explicitly instead of becoming a missing group.
                scalar_groups[(entity["owner"], names[entity["name"]])].append(entity)
        for group in sorted(native_groups.keys() | scalar_groups.keys()):
            native = sorted(native_groups[group], key=lambda e: e["nativeObjectId"])
            simulated = sorted(scalar_groups[group], key=lambda e: e["id"])
            if len(native) != len(simulated):
                differences.append(
                    {
                        "tick": tick,
                        "group": group,
                        "kind": "count",
                        "native": len(native),
                        "scalar": len(simulated),
                    }
                )
                continue
            if not native:
                continue
            if len(native) > 8:
                raise ValueError(
                    "This small-group diagnostic supports at most eight bodies per card/seat"
                )
            matched = min(
                permutations(simulated),
                key=lambda candidates: sum(
                    (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2
                    for a, b in zip(native, candidates)
                ),
            )
            for actual, predicted in zip(native, matched):
                distance = math.hypot(
                    actual["x"] - predicted["x"], actual["y"] - predicted["y"]
                )
                hp_difference = predicted["hp"] - actual["hp"]
                paired_bodies += 1
                exact_positions += distance == 0
                exact_hitpoints += hp_difference == 0
                if distance or hp_difference:
                    differences.append(
                        {
                            "tick": tick,
                            "group": group,
                            "kind": "paired",
                            "native_id": actual["nativeObjectId"],
                            "scalar_id": predicted["id"],
                            "position_error_logic_units": round(distance, 3),
                            "native_hp": actual["hp"],
                            "scalar_hp": predicted["hp"],
                            "hp_difference": hp_difference,
                        }
                    )
    report = {
        "scope": "Opened development game; bodies only, excluding Crown Towers and projectiles.",
        "assignment": "Minimum squared position error within card and seat; inferred correspondence, not proven identity.",
        "native_game": str(args.native_game.resolve()),
        "native_sha256": reference_sha,
        "scalar_frames": str(args.scalar_frames.resolve()),
        "scalar_sha256": scalar_sha,
        "name_to_card_id": names,
        "summary": {
            "checkpoints": len(reference["checkpoints"]),
            "paired_bodies": paired_bodies,
            "exact_positions": exact_positions,
            "exact_hitpoints": exact_hitpoints,
            "count_mismatches": sum(row["kind"] == "count" for row in differences),
        },
        "differences": differences,
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
