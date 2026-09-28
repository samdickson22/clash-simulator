"""Collect bounded public mask/action/history round trips without policy training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from clasher.battle import BattleState
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Mirror", "Fireball", "Archers"], max_entities=32
    )
    bundle = {
        str(p.relative_to(root)): digest(p)
        for p in sorted((root / "src/clasher").rglob("*.py"))
    }
    manifest = {
        "source_files": bundle,
        "collector_sha256": digest(Path(__file__)),
        "gamedata_sha256": digest(builder.loader.data_file),
    }
    (args.output / "producer.json").write_text(json.dumps(manifest, indent=2) + "\n")
    producer = digest(args.output / "producer.json")
    receipts = []
    for owner in (0, 1):
        battle = BattleState()
        battle.players[owner].hand = ["Knight", "Mirror", "Fireball", "Archers"]
        battle.players[owner].elixir = 10
        space = DiscreteTileActionSpace()
        mask_builder = PublicActionMaskBuilder(builder)
        observations = []
        decisions = []
        masks = []
        events = []
        for name in ("Mirror", "Knight", "Mirror"):
            observation = builder.build_actor(battle, owner)
            mask = mask_builder.build(
                PublicActionMaskInput.from_confidence_observation(
                    exact_public_observation(observation)
                )
            )
            slot = battle.players[owner].hand.index(name)
            action = slot * 576 + 10 * 18 + 8
            selection = space.decode_action(action, owner)
            assert (
                space.encode_action(
                    slot, int(selection.position.x), int(selection.position.y), owner
                )
                == action
            )
            tick = battle.tick
            before_history = observation.own_last_play
            success = battle.deploy_card(owner, name, selection.position)
            after = builder.build_actor(battle, owner)
            assert success == bool(mask[action])
            if name == "Knight":
                assert success and after.own_last_play.card_name == "Knight"
            elif success:
                assert after.own_last_play == before_history
            else:
                assert after.own_last_play == before_history is None
            observations.append(observation)
            masks.append(mask)
            decisions.append(
                PublicDecision(
                    observation_tick=tick,
                    submission_tick=tick,
                    action=action,
                    accepted=success,
                    execution_tick=tick if success else None,
                    rejection_reason=None
                    if success
                    else "Mirror has no confirmed previous ordinary play",
                )
            )
            events.append(
                {
                    "tick": tick,
                    "card": name,
                    "slot": slot,
                    "world_xy": [selection.position.x, selection.position.y],
                    "action": action,
                    "mask_allows": bool(mask[action]),
                    "accepted": success,
                    "elixir_after": battle.players[owner].elixir,
                    "history_after": None
                    if after.own_last_play is None
                    else {
                        "card": after.own_last_play.card_name,
                        "cost": after.own_last_play.elixir_cost,
                    },
                }
            )
            battle.step()
        source = args.output / f"source-seat{owner}.json"
        source.write_text(
            json.dumps(
                {
                    "kind": "synthetic_diagnostic",
                    "owner": owner,
                    "initial_hand": ["Knight", "Mirror", "Fireball", "Archers"],
                    "events": events,
                },
                indent=2,
            )
            + "\n"
        )
        provenance = MatchProvenance(
            physical_match_id=f"mirror-roundtrip-seat{owner}",
            duplicate_group_id="mirror-roundtrip",
            perspective=owner,
            role="development",
            source_kind="synthetic_diagnostic",
            source_sha256=digest(source),
            ruleset_sha256=manifest["gamedata_sha256"],
            producer_sha256=producer,
            game_build="clasher-scalar-diagnostic",
            observation_domain="simulator-exact",
            seed=None,
            opened_for_development=True,
        )
        sequence = PublicPolicySequence.from_observations(builder, observations)
        destination = args.output / f"seat{owner}"
        receipt = save_match_archive(
            destination, sequence, provenance, decisions, np.stack(masks)
        )
        restored = load_match_archive(
            destination,
            token_names=builder.token_names,
            source_path=source,
            ruleset_path=builder.loader.data_file,
            producer_path=args.output / "producer.json",
        )
        assert restored[0] == receipt
        receipts.append(receipt)
    validate_split_assignments([r.provenance for r in receipts])
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "archives": len(receipts),
                "decisions": sum(r.count for r in receipts),
                "role": "development",
                "training_started": False,
            },
            indent=2,
        )
        + "\n"
    )
    print("Verified two seats and six recorded decisions; no training.")


if __name__ == "__main__":
    main()
