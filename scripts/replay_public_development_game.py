"""Verify archived public decisions against a deterministic source-event replay."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_match_archive import load_match_archive
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.capture / f"game{args.game}-source.json"
    data = json.loads(source.read_text())
    decks = data["initial_decks"]
    builder = StructuredObservationBuilder(
        card_vocab=sorted(set(decks[0] + decks[1])), max_entities=128
    )
    archives = [
        load_match_archive(
            args.capture / f"game{args.game}-seat{owner}",
            token_names=builder.token_names,
            source_path=source,
            ruleset_path=args.capture / "gamedata.json",
            producer_path=args.capture / "producer-source.zip",
        )
        for owner in (0, 1)
    ]
    battle = BattleState(
        players=[
            PlayerState(owner, deck=deck, hand=deck[:4])
            for owner, deck in enumerate(decks)
        ],
        rng=random.Random(data["case"]["seed"]),
    )
    space = DiscreteTileActionSpace()
    mask_builder = PublicActionMaskBuilder(builder)
    by_tick = {}
    for event in data["events"]:
        by_tick.setdefault(event["tick"], []).append(event)
    indices = [0, 0]
    while not battle.game_over and battle.tick <= data["terminal"]["tick"]:
        events = by_tick.get(battle.tick, [])
        for event in events:
            owner = event["owner"]
            _, sequence, decisions, masks = archives[owner]
            index = indices[owner]
            actual = builder.build_actor(battle, owner)
            packed = PublicPolicySequence.from_observations(builder, [actual])
            for name, array in packed.arrays.items():
                np.testing.assert_array_equal(
                    array[0],
                    sequence.arrays[name][index],
                    err_msg=f"tick{battle.tick}/seat{owner}/{name}",
                )
            mask = mask_builder.build(
                PublicActionMaskInput.from_confidence_observation(
                    exact_public_observation(actual)
                )
            )
            np.testing.assert_array_equal(mask, masks[index])
            assert (
                decisions[index].action == event["action"]
                and decisions[index].accepted == event["accepted"]
            )
            indices[owner] += 1
        for event in events:
            selection = space.decode_action(event["action"], event["owner"])
            if selection.is_no_op:
                assert event["accepted"] is None
            else:
                name = battle.players[event["owner"]].hand[selection.slot]
                assert name == event["card"]
                assert [selection.position.x, selection.position.y] == event["world_xy"]
                assert (
                    battle.deploy_card(event["owner"], name, selection.position)
                    == event["accepted"]
                )
        battle.step()
    assert (
        battle.game_over
        and battle.tick == data["terminal"]["tick"]
        and battle.winner == data["terminal"]["winner"]
    )
    towers = [
        {"owner": e.player_id, "name": e.card_stats.name, "hp": e.hitpoints}
        for e in battle.entities.values()
        if e.entity_kind == 1 and e.card_stats.name in ("Tower", "KingTower")
    ]
    assert towers == data["terminal"]["towers"]
    assert indices == [archive[0].count for archive in archives]
    with args.output.open("x") as output:
        json.dump(
            {
                "game": args.game,
                "verified_decisions": sum(indices),
                "terminal_tick": battle.tick,
                "winner": battle.winner,
                "public_arrays_exact": True,
                "masks_exact": True,
                "source_events_exact": True,
            },
            output,
            indent=2,
        )
        output.write("\n")
    print("Verified", sum(indices), "decisions and exact terminal state")


if __name__ == "__main__":
    main()
