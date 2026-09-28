"""Run paired public-controller diagnostics with explicit native command latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
from collections import deque
from pathlib import Path

import numpy as np
from collect_public_development_games import DECKS, choose_public_action
from smoke_reference_battle import request
from trace_native_public_prefix import producer_source_hashes

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--gamedata", type=Path)
    parser.add_argument("--decks", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text())
    decks = json.loads(args.decks.read_text()) if args.decks else DECKS
    if not isinstance(decks, (list, tuple)) or len(decks) != 2 or any(
        not isinstance(deck, (list, tuple)) or len(deck) != 8
        or any(not isinstance(name, str) for name in deck)
        for deck in decks
    ):
        parser.error("--decks must contain two arrays of eight card names")
    decks = list(reversed(decks)) if args.reverse else decks
    card_names = sorted({name for deck in decks for name in deck})
    loader = CardDataLoader(args.gamedata)
    builder = StructuredObservationBuilder(
        card_vocab=card_names, max_entities=128,
        card_loader=loader,
    )
    root = Path(__file__).resolve().parents[1]
    source_name = str(Path(__file__).resolve().relative_to(root))
    sources = producer_source_hashes()
    sources[source_name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    ruleset_bytes = loader.data_file.read_bytes()
    ruleset_sha = hashlib.sha256(ruleset_bytes).hexdigest()
    archive_path = args.output / "producer-source.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, expected_sha in sorted(sources.items()):
            data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected_sha:
                raise RuntimeError("source changed before collection")
            archive.writestr(name, data)
        archive.writestr("ruleset/gamedata.json", ruleset_bytes)
    attestation = request(26789, "attest")
    if not attestation["ok"] or not attestation["attestation"]["production_ready"]:
        raise RuntimeError("native reference attestation is not ready")
    (args.output / "native-attestation.json").write_text(json.dumps(attestation, indent=2) + "\n")
    ids = {
        n: builder.loader.get_card(n)._raw_entry["id"] for n in card_names
    }
    if any(len({ids[name] for name in deck}) != 8 for deck in decks):
        parser.error("each deck must contain eight distinct card IDs")
    names = {v: k for k, v in ids.items()}
    for owner, deck in enumerate(decks):
        config["battle"][f"deck{owner}"]["sp"] = [{"d": ids[n]} for n in deck]
    (args.output / "plan.json").write_text(
        json.dumps(
            {
                "config": config,
                "decks": decks,
                "gamedata_path": str(loader.data_file),
                "gamedata_sha256": ruleset_sha,
                "producer_sources": sources,
                "producer_archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                "native_attestation_digest": attestation["attestation"]["attestation_digest"],
                "decision_stride": 30,
                "command_delay": 1,
                "startup_wait_ticks": 90,
                "role": "opened_development",
                "controller_source": "scalar_public_only",
                "max_tick": 6001,
            },
            indent=2,
        )
        + "\n"
    )
    request(26789, "configure " + json.dumps(config, separators=(",", ":")))
    initial = request(26789, "observe")
    assert initial["tick"] == 0 and not initial["truncated"]
    players = []
    for owner, deck in enumerate(decks):
        player = next(p for p in initial["players"] if p["owner"] == owner)
        hand = [
            names[c["cardId"]]
            for c in sorted(player["hand"], key=lambda c: c["handIndex"])
        ]
        cycle = [
            names[c["cardId"]]
            for c in sorted(player["cycle"], key=lambda c: c["cycleIndex"])
        ]
        assert len(hand) == 4 and len(cycle) == 4
        players.append(
            PlayerState(
                owner,
                elixir=player["elixir"],
                deck=list(deck),
                hand=hand,
                cycle_queue=deque(cycle),
            )
        )
    battle = BattleState(players=players, rng=random.Random(config["rndSeed"]), card_loader=loader)
    request(26789, "step 90")
    for _ in range(90):
        battle.step()
    rng = np.random.default_rng(config["rndSeed"])
    space = DiscreteTileActionSpace()
    mask_builder = PublicActionMaskBuilder(builder)
    checkpoints = []
    commands = []
    failure = None
    (args.output / "initial.json").write_text(json.dumps(initial, indent=2) + "\n")
    while battle.tick < 6001 and not battle.game_over:
        before = request(26789, "observe")
        if before["ended"]:
            failure = {"kind": "native_ended_before_scalar", "tick": battle.tick}
            break
        assert before["tick"] == battle.tick and not before["truncated"]
        pending = []
        wire = []
        for owner in (0, 1):
            observation = builder.build_actor(battle, owner)
            mask = mask_builder.build(
                PublicActionMaskInput.from_confidence_observation(
                    exact_public_observation(observation)
                )
            )
            action = choose_public_action(observation, mask, rng)
            selection = space.decode_action(action, owner)
            if selection.is_no_op:
                continue
            name = battle.players[owner].hand[selection.slot]
            player = next(p for p in before["players"] if p["owner"] == owner)
            card = next(
                (c for c in player["hand"] if c["handIndex"] == selection.slot), None
            )
            if card is None or card["cardId"] != ids[name]:
                failure = {
                    "kind": "hand_divergence",
                    "tick": battle.tick,
                    "owner": owner,
                    "scalar_card": name,
                    "native_card": card,
                }
                break
            wire.extend(
                [
                    owner,
                    selection.slot,
                    round(selection.position.x * 1000),
                    round(selection.position.y * 1000),
                ]
            )
            pending.append(
                {
                    "owner": owner,
                    "name": name,
                    "action": action,
                    "xy": [selection.position.x, selection.position.y],
                    "cost": card["cost"],
                    "submitted_tick": battle.tick,
                    "execution_tick": battle.tick + 1,
                    "elixir_before": player["elixir"],
                }
            )
        if failure:
            break
        for command in pending:
            command["schedule_receipt"] = request(
                26789,
                f"replay-schedule-card {command['owner']} {ids[command['name']]} "
                f"{round(command['xy'][0] * 1000)} {round(command['xy'][1] * 1000)} {command['execution_tick']}",
            )
        for command in pending:
            command["scalar_accepted"] = battle.deploy_card(
                command["owner"], command["name"], Position(*command["xy"])
            )
        request(26789, "step 1")
        battle.step()
        after = request(26789, "observe-atomic")
        native = after["ordinary"]
        assert (
            native["tick"] == battle.tick
            and not native["truncated"]
            and after["atomic"]
        )
        for command in pending:
            player = next(
                p for p in native["players"] if p["owner"] == command["owner"]
            )
            spent = command["elixir_before"] - player["elixir"]
            command["native_spend_delta"] = spent
            command["native_acceptance_spend_evidence"] = (
                command["cost"] - 0.5 < spent <= command["cost"] + 0.0001
            )
            if (
                not command["scalar_accepted"]
                or not command["native_acceptance_spend_evidence"]
            ):
                failure = {"kind": "execution_divergence", "command": command}
            commands.append(command)
        scalar_towers = [
            {
                "owner": e.player_id,
                "x": round(e.position.x * 1000),
                "y": round(e.position.y * 1000),
                "hp": e.hitpoints,
            }
            for e in battle.entities.values()
            if e.entity_kind == 1 and e.card_stats.name in ("Tower", "KingTower")
        ]
        native_towers = [
            {k: o[k] for k in ("owner", "x", "y", "hp")}
            for o in native["objects"]
            if o["cardId"] == -1 and o["hp"] is not None
        ]
        checkpoints.append(
            {
                "tick": battle.tick,
                "native": native,
                "scalar_towers": scalar_towers,
                "native_towers": native_towers,
                "scalar_elixir": [p.elixir for p in battle.players],
            }
        )
        if failure:
            (args.output / "failure-atomic.json").write_text(
                json.dumps(after, indent=2) + "\n"
            )
            break
        if battle.tick + 29 <= 6001 and not battle.game_over:
            request(26789, "step 29")
            for _ in range(29):
                battle.step()
        if len(checkpoints) % 20 == 0:
            print("paired tick", battle.tick, flush=True)
    native_playable_final = request(26789, "observe")
    native_final = native_playable_final
    # After the last playable interval, native tiebreaker presentation can
    # continue while the policy episode has already ended. Resolve its actual
    # result before comparing winners; never label a live result as final.
    if failure is None and battle.game_over and battle.tick >= 6001:
        for _ in range(400):
            if native_final["ended"]:
                break
            previous_tick = native_final["tick"]
            request(26789, "step 1")
            native_final = request(26789, "observe")
            if native_final["tick"] <= previous_tick and not native_final["ended"]:
                failure = {"kind": "native_finalization_no_progress", "tick": previous_tick}
                break
    if failure is None and not battle.game_over:
        failure = {"kind": "scalar_not_terminal", "tick": battle.tick}
    if failure is None and battle.game_over and (
        not native_final["ended"] or native_final["winner"] != battle.winner
    ):
        failure = {"kind": "terminal_result_mismatch", "native_ended": native_final["ended"], "native_winner": native_final["winner"], "scalar_winner": battle.winner}
    final_sources = producer_source_hashes()
    final_sources[source_name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    final_attestation = request(26789, "attest")
    sources_unchanged = final_sources == sources
    ruleset_unchanged = hashlib.sha256(loader.data_file.read_bytes()).hexdigest() == ruleset_sha
    native_unchanged = final_attestation == attestation
    if failure is None and not (sources_unchanged and ruleset_unchanged and native_unchanged):
        failure = {"kind": "producer_changed_during_collection"}
    result = {
        "decks": decks,
        "producer_sources_unchanged": sources_unchanged,
        "ruleset_unchanged": ruleset_unchanged,
        "native_attestation_unchanged": native_unchanged,
        "last_tick": battle.tick,
        "failure": failure,
        "scalar_terminal": battle.game_over,
        "scalar_winner": battle.winner,
        "native_playable_final": native_playable_final,
        "native_final": native_final,
        "native_finalization_ticks": native_final["tick"] - native_playable_final["tick"],
        "commands": commands,
        "checkpoints": checkpoints,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("commands", "checkpoints", "native_final", "native_playable_final")
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
