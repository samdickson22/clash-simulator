"""Record an internal Hog/Cannon control; this is not external game evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import deque
from pathlib import Path

from clasher.arena import Position
from clasher.balance import BALANCE_VERSION, TOURNAMENT_LEVEL
from clasher.battle import BattleState
from clasher.fidelity import CandidateTrace, ReferenceCase, compare_files, sha256
from clasher.paths import project_root

DECK = [
    "HogRider",
    "Cannon",
    "Musketeer",
    "Skeletons",
    "IceGolem",
    "IceSpirit",
    "Fireball",
    "Log",
]


def record(*, fast_path: bool, ticks: int = 200) -> list[dict]:
    battle = BattleState(rng=random.Random(1282001), fast_path=fast_path)
    for player in battle.players:
        player.deck = list(DECK)
        player.hand = list(DECK[:4])
        player.cycle_queue = deque(DECK[4:])
        player.elixir = 10.0
    labels = {
        entity.id: f"p{entity.player_id}.{entity._crown_tower_slot}"
        for entity in battle.entities.values()
        if hasattr(entity, "_crown_tower_slot")
    }
    for owner, card, x, y, label in [
        (0, "HogRider", 3.5, 14.5, "hog"),
        (1, "Cannon", 7.5, 19.5, "cannon"),
    ]:
        before = set(battle.entities)
        if not battle.deploy_card(owner, card, Position(x, y)):
            raise RuntimeError(f"control deployment rejected: {card}")
        spawned = set(battle.entities) - before
        if len(spawned) != 1:
            raise RuntimeError(f"unexpected control spawn count: {card}")
        labels[spawned.pop()] = label
    ids = {label: entity_id for entity_id, label in labels.items()}
    frames = []
    for tick in range(ticks + 1):
        if battle.tick != tick:
            raise RuntimeError("control terminated before its declared horizon")
        facts = {"game_over": battle.game_over, "winner": battle.winner}
        for label, entity_id in ids.items():
            entity = battle.entities.get(entity_id)
            alive = entity is not None and entity.is_alive
            facts[f"{label}.alive"] = alive
            if entity is not None:
                facts.update(
                    {
                        f"{label}.x": entity.position.x,
                        f"{label}.y": entity.position.y,
                        f"{label}.hp": entity.hitpoints,
                        f"{label}.target": labels.get(entity.target_id),
                    }
                )
        frames.append({"tick": tick, "facts": facts})
        if tick != ticks:
            battle.step()
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = project_root()
    files = sorted((root / "src/clasher").rglob("*.py")) + [
        root / "gamedata.json",
        Path(__file__).resolve(),
    ]
    manifest = {str(path.relative_to(root)): sha256(path) for path in files}
    source_digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    metadata = json.loads((root / "gamedata.json").read_text())["meta"]
    ruleset = {
        "declared_balance_version": BALANCE_VERSION,
        "tournament_level": TOURNAMENT_LEVEL,
        "gamedata_sha256": sha256(root / "gamedata.json"),
        "balance_overrides_sha256": sha256(root / "src/clasher/balance.py"),
        "external_game_build": None,
    }
    ruleset_id = hashlib.sha256(json.dumps(ruleset, sort_keys=True).encode()).hexdigest()
    recipe = {
        "role": "internal-control-only",
        "seed": 1282001,
        "ticks": 200,
        "deck": DECK,
        "starting_hand": DECK[:4],
        "starting_elixir": 10,
        "commands": [[0, 0, "HogRider", 3.5, 14.5], [0, 1, "Cannon", 7.5, 19.5]],
        "source_manifest": manifest,
        "ruleset": ruleset,
        "gamedata_metadata": metadata,
        "game_build": None,
        "external_version_compatibility": "unverified",
    }
    recipe_path = args.output / "recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    frames = record(fast_path=False)
    case = ReferenceCase.model_validate(
        {
            "schema_version": 1,
            "case_id": "hog-cannon-internal-control",
            "ruleset_id": ruleset_id,
            "tick_ms": 50,
            "evidence": {
                "kind": "simulator_control",
                "artifact": "recipe.json",
                "artifact_sha256": sha256(recipe_path),
                "source": "Clasher scalar control",
                "game_build": None,
                "annotation_method": "exact scalar state snapshots",
                "timing_method": "post-command tick zero; every completed 50 ms step",
            },
            "observations": [
                {
                    "earliest_tick": row["tick"],
                    "latest_tick": row["tick"],
                    "facts": {
                        key: {"kind": "exact", "value": value}
                        for key, value in row["facts"].items()
                    },
                }
                for row in frames
            ],
        }
    )
    case_path = args.output / "case.json"
    case_path.write_text(case.model_dump_json(indent=2) + "\n")
    for variant, candidate in [
        ("repeat", record(fast_path=False)),
        ("fast", record(fast_path=True)),
    ]:
        trace = CandidateTrace.model_validate(
            {
                "schema_version": 1,
                "case_id": case.case_id,
                "ruleset_id": case.ruleset_id,
                "tick_ms": 50,
                "game_build": None,
                "backend": "scalar_reference",
                "source_sha256": source_digest,
                "frames": candidate,
            }
        )
        trace_path = args.output / f"{variant}-trace.json"
        trace_path.write_text(trace.model_dump_json(indent=2) + "\n")
        report = compare_files(case_path, trace_path)
        (args.output / f"{variant}-comparison.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(variant, report["status"], "first_divergence", report["first_divergence"])


if __name__ == "__main__":
    main()
