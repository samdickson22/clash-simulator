"""Replay recorded paired commands and capture a bounded native/scalar window."""

import argparse
import hashlib
import json
import random
import sys
from collections import deque
from pathlib import Path

from collect_public_development_games import DECKS
from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState


def producer_source_hashes():
    root = Path(__file__).resolve().parent.parent
    paths = list((root / "src/clasher").rglob("*.py"))
    paths.extend(root / "scripts" / name for name in (
        "trace_native_public_prefix.py", "collect_public_development_games.py",
        "smoke_reference_battle.py",
    ))
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scalar-only", action="store_true")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--gamedata", type=Path)
    parser.add_argument("--native-observation", choices=("atomic", "ordinary"), default="atomic")
    args = parser.parse_args()
    if args.stride < 1 or not 0 <= args.start <= args.end:
        parser.error("require stride >= 1 and 0 <= start <= end")
    args.output.mkdir(parents=True, exist_ok=False)
    producer_sources = producer_source_hashes()
    plan = json.loads((args.capture / "plan.json").read_text())
    config = plan["config"]
    decks = plan.get("decks", DECKS)
    recorded = json.loads((args.capture / "result.json").read_text())
    loader = CardDataLoader(args.gamedata)
    gamedata_sha256 = hashlib.sha256(loader.data_file.read_bytes()).hexdigest()
    commands = {}
    for c in recorded["commands"]:
        commands.setdefault(c["submitted_tick"], []).append(c)
    if args.scalar_only:
        initial = json.loads((args.capture / "initial.json").read_text())
    else:
        request(26789, "configure " + json.dumps(config, separators=(",", ":")))
        initial = request(26789, "observe")
    assert initial["tick"] == 0 and not initial["truncated"]
    players = []
    names = {loader.get_card(name)._raw_entry["id"]: name for name in {name for deck in decks for name in deck}}
    for owner in (0, 1):
        native = next(p for p in initial["players"] if p["owner"] == owner)
        deck = [names[c["cardId"]] for c in native["deck"]]
        hand = [
            names[c["cardId"]]
            for c in sorted(native["hand"], key=lambda c: c["handIndex"])
        ]
        cycle = [
            names[c["cardId"]]
            for c in sorted(native["cycle"], key=lambda c: c["cycleIndex"])
        ]
        players.append(
            PlayerState(
                owner,
                deck=deck,
                hand=hand,
                cycle_queue=deque(cycle),
                elixir=native["elixir"],
            )
        )
    battle = BattleState(
        players=players, rng=random.Random(config["rndSeed"]), card_loader=loader
    )
    frames = []
    while battle.tick < args.end and not battle.game_over:
        for c in commands.get(battle.tick, []):
            card = loader.get_card(c["name"])._raw_entry["id"]
            assert c["execution_tick"] == battle.tick + 1
            if not args.scalar_only:
                request(
                    26789,
                    f"replay-schedule-card {c['owner']} {card} {round(c['xy'][0] * 1000)} {round(c['xy'][1] * 1000)} {c['execution_tick']}",
                )
            if not battle.deploy_card(c["owner"], c["name"], Position(*c["xy"])):
                failure = {
                    "kind": "scalar_command_rejected",
                    "tick": battle.tick,
                    "command": c,
                    "gamedata_sha256": gamedata_sha256,
                    "elixir": battle.players[c["owner"]].elixir,
                    "hand": battle.players[c["owner"]].hand,
                    "entities": [
                        {
                            "id": e.id,
                            "name": e.card_stats.name if e.card_stats else type(e).__name__,
                            "owner": e.player_id,
                            "hp": e.hitpoints,
                            "x": e.position.x,
                            "y": e.position.y,
                        }
                        for e in battle.entities.values()
                    ],
                }
                (args.output / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
                (args.output / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")
                raise RuntimeError(f"scalar rejected {c['name']} at tick {battle.tick}")
        if not args.scalar_only:
            request(26789, "step 1")
        battle.step()
        if battle.tick >= args.start and (
            (battle.tick - args.start) % args.stride == 0
            or battle.tick == args.end
            or battle.game_over
        ):
            native = None
            if not args.scalar_only:
                if args.native_observation == "ordinary":
                    ordinary = request(26789, "observe")
                    native = {"tick": ordinary["tick"], "atomic": False, "ordinary": ordinary, "rich": None}
                else:
                    native = request(26789, "observe-atomic")
                assert native["tick"] == battle.tick
            scalar = [
                {
                    "id": e.id,
                    "name": e.card_stats.name if e.card_stats else type(e).__name__,
                    "kind": e.entity_kind,
                    "owner": e.player_id,
                    "x": round(e.position.x * 1000),
                    "y": round(e.position.y * 1000),
                    "hp": e.hitpoints,
                    "target": e.target_id,
                    "cooldown": getattr(e, "attack_cooldown", None),
                    "ordinary_clock": (
                        {
                            "timeline_ms": e._ordinary_clock.hit_timeline_ms,
                            "load_ms": e._ordinary_clock.load_remaining_ms,
                            "finish_ms": e._ordinary_clock.finish_elapsed_ms,
                        }
                        if e._ordinary_clock is not None else None
                    ),
                    "attack_windup_active": e._attack_windup_active,
                    "has_attacked_once": getattr(e, "_has_attacked_once", False),
                    "finish_elapsed_ms": e._attack_finish_elapsed_ms,
                    "avoidance": getattr(e, "_native_avoidance", None),
                    "facing": list(e.native_facing_units()),
                    "spawn_stagger_remaining": e.spawn_stagger_remaining,
                    "pending_lethal": e.is_expected_to_die_from_projectiles(),
                    "pending_max_duration_ms": e._pending_projectile_max_duration_ms,
                    "primary_target_id": getattr(
                        getattr(e, "primary_target", None), "id", None
                    ),
                    "reserves_pending_damage": getattr(
                        e, "reserves_pending_damage", None
                    ),
                    "source_id": getattr(getattr(e, "source_entity", None), "id", None),
                }
                for e in battle.entities.values()
            ]
            frames.append({"tick": battle.tick, "native": native, "scalar": scalar})
    (args.output / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")
    sources_unchanged = producer_sources == producer_source_hashes()
    (args.output / "replay-summary.json").write_text(
        json.dumps(
            {
                "scalar_only": args.scalar_only,
                "native_observation": None if args.scalar_only else args.native_observation,
                "requested_end_tick": args.end,
                "actual_end_tick": battle.tick,
                "scalar_game_over": battle.game_over,
                "scalar_winner": battle.winner,
                "terminal_scope": "playable_episode_before_native_result_presentation",
                "captured_frames": len(frames),
                "stride": args.stride,
                "gamedata_path": str(loader.data_file),
                "gamedata_sha256": gamedata_sha256,
                "producer_sources": producer_sources,
                "producer_sources_unchanged": sources_unchanged,
                "python_version": sys.version,
            },
            indent=2,
        )
        + "\n"
    )
    if not sources_unchanged:
        raise RuntimeError("Producer sources changed during capture; output is diagnostic only")
    print("captured", len(frames), "frames")


if __name__ == "__main__":
    main()
