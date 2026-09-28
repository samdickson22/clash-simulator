"""Complete scripted public-observation games for data-pipeline diagnostics."""

from __future__ import annotations

import argparse
import json
import random
import zipfile
from pathlib import Path

import numpy as np

from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_match_archive import (
    MatchProvenance,
    PublicDecision,
    digest,
    load_match_archive,
    save_match_archive,
    validate_split_assignments,
)
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

DECKS = (
    (
        "HogRider",
        "Musketeer",
        "Cannon",
        "Skeletons",
        "IceGolem",
        "IceSpirit",
        "Fireball",
        "Log",
    ),
    ("Giant", "Prince", "Knight", "Archers", "Tesla", "Fireball", "Zap", "Mirror"),
)


def choose_public_action(observation, mask, rng):
    """Fixed public geometry controller; no simulation search or model fitting."""
    legal = np.flatnonzero(mask[:2304])
    if len(legal) == 0 or rng.random() < 0.25:
        return 2304
    slots = np.unique(legal // 576)
    slot = int(rng.choice(slots))
    rows = observation.entity_features[observation.entity_mask]
    threats = rows[(rows[:, 3] > 0.5) & (rows[:, 1] < 0.5) & (rows[:, 4] > 0.5)]
    if len(threats):
        target = threats[np.argmin(threats[:, 1])]
        x, y = target[0] * 18, target[1] * 32
    else:
        x, y = (3.5 if rng.random() < 0.5 else 14.5), 13.5
    candidates = legal[legal // 576 == slot]
    tiles = candidates % 576
    distances = (tiles % 18 + 0.5 - x) ** 2 + (tiles // 18 + 0.5 - y) ** 2
    return int(candidates[np.argmin(distances)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1283101)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    builder = StructuredObservationBuilder(
        card_vocab=sorted(set(DECKS[0] + DECKS[1])), max_entities=128
    )
    source_files = sorted((root / "src/clasher").rglob("*.py")) + [
        Path(__file__).resolve()
    ]
    snapshot = args.output / "producer-source.zip"
    with zipfile.ZipFile(snapshot, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files:
            archive.write(path, str(path.relative_to(root)))
    ruleset = args.output / "gamedata.json"
    ruleset.write_bytes(builder.loader.data_file.read_bytes())
    plan = [
        {
            "seed": args.seed,
            "reverse": reverse,
            "decks": list(reversed(DECKS)) if reverse else DECKS,
        }
        for reverse in (False, True)
    ]
    (args.output / "plan.json").write_text(
        json.dumps(
            {
                "role": "development",
                "controller": "fixed-public-geometry-v1",
                "cadence_ticks": 20,
                "cases": plan,
            },
            indent=2,
        )
        + "\n"
    )
    receipts = []
    summary = []
    for number, case in enumerate(plan):
        rng = np.random.default_rng(case["seed"])
        decks = [list(d) for d in case["decks"]]
        for deck in decks:
            rng.shuffle(deck)
        battle = BattleState(
            players=[
                PlayerState(owner, deck=deck, hand=deck[:4])
                for owner, deck in enumerate(decks)
            ],
            rng=random.Random(case["seed"]),
        )
        space = DiscreteTileActionSpace()
        masks_builder = PublicActionMaskBuilder(builder)
        observations = [[], []]
        decisions = [[], []]
        masks = [[], []]
        events = []
        while not battle.game_over and battle.tick < 6200:
            if battle.tick % 20 == 0:
                prepared = []
                for owner in (0, 1):
                    view = builder.build_actor(battle, owner)
                    mask = masks_builder.build(
                        PublicActionMaskInput.from_confidence_observation(
                            exact_public_observation(view)
                        )
                    )
                    action = choose_public_action(view, mask, rng)
                    prepared.append((owner, view, mask, action))
                for owner, view, mask, action in prepared:
                    selection = space.decode_action(action, owner)
                    name = None
                    if selection.is_no_op:
                        accepted = None
                    else:
                        name = battle.players[owner].hand[selection.slot]
                        assert (
                            space.encode_action(
                                selection.slot,
                                int(selection.position.x),
                                int(selection.position.y),
                                owner,
                            )
                            == action
                        )
                        accepted = battle.deploy_card(owner, name, selection.position)
                    observations[owner].append(view)
                    masks[owner].append(mask)
                    decisions[owner].append(
                        PublicDecision(
                            observation_tick=battle.tick,
                            submission_tick=battle.tick,
                            action=action,
                            accepted=accepted,
                            execution_tick=battle.tick if accepted else None,
                            rejection_reason="simulator rejected a public-mask-approved play"
                            if accepted is False
                            else None,
                        )
                    )
                    events.append(
                        {
                            "tick": battle.tick,
                            "owner": owner,
                            "action": action,
                            "card": name,
                            "world_xy": None
                            if selection.position is None
                            else [selection.position.x, selection.position.y],
                            "accepted": accepted,
                        }
                    )
            battle.step()
        if not battle.game_over:
            (args.output / f"game{number}-incomplete.json").write_text(
                json.dumps(
                    {"case": case, "tick": battle.tick, "events": events}, indent=2
                )
                + "\n"
            )
            raise RuntimeError("match did not reach an actual terminal state")
        source = args.output / f"game{number}-source.json"
        terminal = {
            "tick": battle.tick,
            "winner": battle.winner,
            "towers": [
                {"owner": e.player_id, "name": e.card_stats.name, "hp": e.hitpoints}
                for e in battle.entities.values()
                if e.entity_kind == 1 and e.card_stats.name in ("Tower", "KingTower")
            ],
        }
        source.write_text(
            json.dumps(
                {
                    "case": case,
                    "initial_decks": decks,
                    "events": events,
                    "terminal": terminal,
                },
                indent=2,
            )
            + "\n"
        )
        for owner in (0, 1):
            provenance = MatchProvenance(
                physical_match_id=f"public-development-{args.seed}-{number}",
                duplicate_group_id=f"public-development-paired-{args.seed}",
                perspective=owner,
                role="development",
                source_kind="synthetic_diagnostic",
                source_sha256=digest(source),
                ruleset_sha256=digest(ruleset),
                producer_sha256=digest(snapshot),
                game_build="clasher-scalar-development",
                observation_domain="simulator-exact",
                seed=case["seed"],
                opened_for_development=True,
                coverage="complete",
                terminal_tick=battle.tick,
                terminal_result="draw"
                if battle.winner is None
                else ("owner_win" if battle.winner == owner else "owner_loss"),
            )
            sequence = PublicPolicySequence.from_observations(
                builder, observations[owner]
            )
            path = args.output / f"game{number}-seat{owner}"
            receipt = save_match_archive(
                path, sequence, provenance, decisions[owner], np.stack(masks[owner])
            )
            assert (
                load_match_archive(
                    path,
                    token_names=builder.token_names,
                    source_path=source,
                    ruleset_path=ruleset,
                    producer_path=snapshot,
                )[0]
                == receipt
            )
            receipts.append(receipt)
        summary.append(
            {
                "game": number,
                "terminal": terminal,
                "decisions": len(events),
                "rejected": sum(e["accepted"] is False for e in events),
                "cards_played": sorted({e["card"] for e in events if e["accepted"]}),
            }
        )
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary[-1]), flush=True)
    validate_split_assignments([r.provenance for r in receipts])


if __name__ == "__main__":
    main()
