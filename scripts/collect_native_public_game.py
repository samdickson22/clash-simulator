"""Collect a public-controlled reference game with an explicit evidence role."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
from collect_public_development_games import choose_public_action
from read_native_public_levels import read_levels
from smoke_reference_battle import request

from clasher.data import CardDataLoader
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.calibration_artifacts import capture_artifact_paths, seal_artifacts
from clasher.rl.calibration_collection import verify_collection_protocol
from clasher.rl.calibration_families import (
    claim_acceptance_collection,
    require_development_member,
)
from clasher.rl.native_command_checks import validate_command_step
from clasher.rl.native_match_registry import (
    canonical_digest,
    native_match_id,
    register_native_root,
)
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_match_archive import (
    MatchProvenance,
    PublicDecision,
    load_match_archive,
    save_match_archive,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_reference_checks import (
    check_reference_entities,
    check_reference_packet,
    reference_token_maps,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument(
        "--family-id",
        help="Require this preassigned family before native collection; development unless an acceptance protocol is supplied",
    )
    parser.add_argument(
        "--acceptance-protocol",
        type=Path,
        help="Frozen prospective protocol; requires --family-id and prior acceptance registration",
    )
    parser.add_argument("--batched-native-levels", action="store_true")
    parser.add_argument("--public-opponent-seat", type=int, choices=(0, 1))
    parser.add_argument(
        "--public-opponent-style",
        choices=("balanced", "pressure", "defense"),
        default="balanced",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.plan.read_text())["config"]
    config["rndSeed"] = args.seed
    role = "development"
    frozen_protocol_sha = None
    if args.acceptance_protocol is not None:
        if args.family_id is None:
            raise ValueError("acceptance collection requires a registered family")
        frozen_collection, family, frozen_protocol_sha = verify_collection_protocol(
            args.acceptance_protocol,
            workspace=Path.cwd(),
            registry=args.registry,
            family_id=args.family_id,
            config=config,
            gamedata=args.gamedata,
            catalog=args.catalog,
            opponent_seat=args.public_opponent_seat,
            opponent_style=args.public_opponent_style,
        )
        role = "acceptance"
        (args.output / "family-identity.json").write_text(
            family.model_dump_json(indent=2) + "\n"
        )
        (args.output / "collection-protocol.json").write_bytes(
            args.acceptance_protocol.read_bytes()
        )
    elif args.family_id is not None:
        family = require_development_member(
            args.registry, args.family_id, "native-root-v1:" + canonical_digest(config)
        )
        (args.output / "family-identity.json").write_text(
            family.model_dump_json(indent=2) + "\n"
        )
    root_record = register_native_root(args.registry, config, role=role)
    (args.output / "root-identity.json").write_text(
        root_record.model_dump_json(indent=2) + "\n"
    )
    loader = CardDataLoader(args.gamedata)
    card_names = {
        card._raw_entry["id"]: name for name, card in loader.load_cards().items()
    }
    decks = [
        [card_names[c["d"]] for c in config["battle"][f"deck{owner}"]["sp"]]
        for owner in (0, 1)
    ]
    names = PUBLIC_REFERENCE_CARDS
    supported_ids = {loader.get_card(name)._raw_entry['id'] for name in names}
    if any(c['d'] not in supported_ids for owner in (0, 1) for c in config['battle'][f'deck{owner}']['sp']):
        raise ValueError('deck is outside the declared public reference roster')
    catalog = NativeProjectileCatalog.from_csv(
        args.catalog, expected_sha256=args.catalog_sha256
    )
    builder = public_reference_builder(
        loader, catalog,
        card_semantics_version=4 if args.public_opponent_seat is not None else 1,
    )
    public_opponent = None
    if args.public_opponent_seat is not None:
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent

        public_opponent = PublicScriptedOpponent(
            builder, style=args.public_opponent_style
        )
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", digest(args.gamedata)),
        card_names=tuple(names),
        projectile_catalog=catalog,
    )
    reference_maps = reference_token_maps(builder, names, catalog)
    masks_builder = PublicActionMaskBuilder(builder)
    space = DiscreteTileActionSpace()
    source_files = sorted(Path("src/clasher").rglob("*.py")) + [
        Path("scripts/collect_native_public_game.py"),
        Path("scripts/read_native_public_levels.py"),
        Path("scripts/smoke_reference_battle.py"),
        Path("scripts/collect_public_development_games.py"),
    ]
    sources = {str(p): digest(p) for p in source_files}
    producer = args.output / "producer-source.zip"
    with zipfile.ZipFile(producer, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files:
            archive.write(path, str(path.resolve().relative_to(Path.cwd())))
    (args.output / "gamedata.json").write_bytes(args.gamedata.read_bytes())
    plan = {
        "config": config,
        "decks": decks,
        "public_card_roster": list(PUBLIC_REFERENCE_CARDS),
        "token_vocabulary_sha256": canonical_digest(builder.token_names),
        "role": role,
        "collection_protocol_sha256": frozen_protocol_sha,
        "controller_source": (
            "native-public-only-fixed-geometry-v1"
            if public_opponent is None
            else f"native-public-scripted-{args.public_opponent_style}-v1-seat{args.public_opponent_seat}"
        ),
        "controllers_by_owner": [
            f"public-scripted-{args.public_opponent_style}-v1"
            if owner == args.public_opponent_seat
            else "fixed-public-geometry-v1"
            for owner in (0, 1)
        ],
        "native_level_transport": "batched-adb"
        if args.batched_native_levels
        else "serial-adb",
        "decision_stride": 30,
        "command_delay": 1,
        "startup_wait_ticks": 90,
        "max_tick": 6001,
        "producer_sources": sources,
    }
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if args.acceptance_protocol is not None:
        verify_collection_protocol(
            args.acceptance_protocol,
            workspace=Path.cwd(),
            registry=args.registry,
            family_id=args.family_id,
            config=config,
            gamedata=args.gamedata,
            catalog=args.catalog,
            opponent_seat=args.public_opponent_seat,
            opponent_style=args.public_opponent_style,
        )
        if (
            canonical_digest(request(26789, "attest"))
            != frozen_collection.native_attestation_sha256
        ):
            raise ValueError("native runtime differs from frozen attestation")
        claim_acceptance_collection(
            args.registry,
            family_id=args.family_id,
            root_id=root_record.duplicate_group_id,
            protocol_sha256=frozen_protocol_sha,
            output_path=args.output,
        )
    request(26789, "configure " + json.dumps(config, separators=(",", ":")))
    attestation = request(26789, "attest")
    (args.output / "native-attestation.json").write_text(
        json.dumps(attestation, indent=2) + "\n"
    )
    initial = request(26789, "observe")
    (args.output / "initial.json").write_text(json.dumps(initial, indent=2) + "\n")
    request(26789, "step 90")
    rngs = [np.random.default_rng(args.seed + owner) for owner in (0, 1)]
    histories = [None, None]
    observations = [[], []]
    decisions = [[], []]
    masks = [[], []]
    commands = []
    checkpoints = []
    failure = None
    try:
        with gzip.open(args.output / "native-frames.jsonl.gz", "xt") as stream:
            while True:
                before = request(26789, "observe")
                if before["ended"] or before["tick"] >= 6001:
                    break
                levels = read_levels(args.adb, batched=args.batched_native_levels)
                assert levels["ordinary"] == before
                rich = request(26789, "observe-rich")
                assert before == request(26789, "observe")
                evidence = NativePublicLevelEvidence(
                    tick=before["tick"],
                    generation=before["generation"],
                    state_epoch=before["stateEpoch"],
                    source_sha256=hashlib.sha256(
                        json.dumps(
                            levels, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                    levels=levels["levels"],
                    confidence={k: 1.0 for k in levels["levels"]},
                )
                views = [
                    adapter.project(
                        before,
                        owner,
                        rich_snapshot=rich,
                        level_evidence=evidence,
                        own_last_play=histories[owner],
                    )
                    for owner in (0, 1)
                ]
                for owner, view in enumerate(views):
                    card_tokens, body_tokens, effect_tokens, tower_tokens = (
                        reference_maps
                    )
                    errors = check_reference_packet(
                        before, view, owner, card_tokens=card_tokens
                    )
                    errors += check_reference_entities(
                        before,
                        rich,
                        view,
                        owner,
                        body_tokens=body_tokens,
                        effect_tokens=effect_tokens,
                        tower_tokens=tower_tokens,
                        levels=evidence.levels,
                        level_confidence=evidence.confidence,
                    )
                    if errors:
                        raise ValueError(
                            "Public reference validation failed: " + "; ".join(errors)
                        )
                if any(v.observation.terminal for v in views):
                    break
                stream.write(
                    json.dumps(
                        {"ordinary": before, "rich": rich, "level_source": levels},
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                selected = []
                for owner in (0, 1):
                    mask = masks_builder.build(
                        PublicActionMaskInput.from_confidence_observation(views[owner])
                    )
                    action = (
                        public_opponent.select_action(views[owner])
                        if owner == args.public_opponent_seat
                        else choose_public_action(
                            views[owner].observation, mask, rngs[owner]
                        )
                    )
                    assert mask[action], (
                        "controller selected an action outside the public mask"
                    )
                    selection = space.decode_action(action, owner)
                    observations[owner].append(views[owner])
                    masks[owner].append(mask)
                    if selection.is_no_op:
                        selected.append((owner, action, None, None, None))
                        continue
                    name = builder.card_name_for_token_id(
                        int(views[owner].observation.hand_ids[selection.slot])
                    )
                    card = loader.get_card(name)._raw_entry["id"]
                    hud = next(p for p in before["players"] if p["owner"] == owner)
                    hand = next(
                        c for c in hud["hand"] if c["handIndex"] == selection.slot
                    )
                    assert hand["cardId"] == card
                    x, y = (
                        round(selection.position.x * 1000),
                        round(selection.position.y * 1000),
                    )
                    receipt = request(
                        26789,
                        f"replay-schedule-card {owner} {card} {x} {y} {before['tick'] + 1}",
                    )
                    selected.append((owner, action, name, hand["cost"], receipt))
                request(26789, "step 1")
                after = request(26789, "observe")
                validate_command_step(
                    before, after, [item[4] for item in selected if item[4] is not None]
                )
                for owner, action, name, cost, receipt in selected:
                    accepted = None
                    if name is not None:
                        old = next(p for p in before["players"] if p["owner"] == owner)
                        new = next(p for p in after["players"] if p["owner"] == owner)
                        delta = (old["elixirRaw"] - new["elixirRaw"]) / 10000
                        accepted = delta >= cost - 0.1
                        selection = space.decode_action(action, owner)
                        commands.append(
                            {
                                "owner": owner,
                                "name": name,
                                "action": action,
                                "xy": [selection.position.x, selection.position.y],
                                "cost": cost,
                                "submitted_tick": before["tick"],
                                "execution_tick": after["tick"],
                                "schedule_receipt": receipt,
                                "native_spend_delta": delta,
                                "native_acceptance_spend_evidence": accepted,
                            }
                        )
                        if (
                            accepted
                            and loader.get_card(name)._raw_entry["id"] != 28000006
                        ):
                            histories[owner] = AcceptedOwnPlay(name, cost)
                    decisions[owner].append(
                        PublicDecision(
                            observation_tick=before["tick"],
                            submission_tick=before["tick"],
                            action=action,
                            accepted=accepted,
                            execution_tick=after["tick"] if accepted else None,
                            rejection_reason="no native spend"
                            if accepted is False
                            else None,
                        )
                    )
                    if accepted is False:
                        raise ValueError("public-mask action lacked native acceptance")
                checkpoints.append({"tick": after["tick"], "native": after})
                if len(checkpoints) % 10 == 0:
                    print(
                        "native-driven checkpoints",
                        len(checkpoints),
                        "tick",
                        after["tick"],
                        flush=True,
                    )
                target = min(before["tick"] + 30, 6001)
                if target > after["tick"]:
                    request(26789, f"step {target - after['tick']}")
    except (ValueError, AssertionError, RuntimeError, OSError, KeyError) as error:
        failure = {"type": type(error).__name__, "message": str(error)}
    playable = request(26789, "observe")
    final = playable
    if failure is None:
        for _ in range(400):
            if final["finalized"]:
                break
            request(26789, "step 1")
            final = request(26789, "observe")
        if not final["finalized"]:
            failure = {"type": "incomplete_finalization"}
    unchanged = (
        all(digest(Path(p)) == sha for p, sha in sources.items())
        and digest(args.gamedata) == adapter.scope.ruleset_sha256
        and request(26789, "attest") == attestation
        and (
            args.acceptance_protocol is None
            or digest(args.acceptance_protocol) == frozen_protocol_sha
        )
    )
    if not unchanged:
        failure = {"type": "producer_changed"}
    result = {
        "decks": decks,
        "commands": commands,
        "checkpoints": checkpoints,
        "failure": failure,
        "native_playable_final": playable,
        "native_final": final,
        "producer_sources_unchanged": unchanged,
        "controller_source": plan["controller_source"],
    }
    result_path = args.output / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    if failure is not None:
        raise RuntimeError(failure)
    canonical_commands = [
        {
            "owner": c["owner"],
            "card_id": loader.get_card(c["name"])._raw_entry["id"],
            "x": round(c["xy"][0] * 1000),
            "y": round(c["xy"][1] * 1000),
            "submitted_tick": c["submitted_tick"],
            "execution_tick": c["execution_tick"],
        }
        for c in commands
    ]
    match_id = native_match_id(root_record, canonical_commands)
    for owner in (0, 1):
        sequence = PublicPolicySequence.from_observations(builder, observations[owner])
        provenance = MatchProvenance(
            physical_match_id=match_id,
            duplicate_group_id=root_record.duplicate_group_id,
            perspective=owner,
            role=role,
            source_kind="native_reference",
            source_sha256=digest(result_path),
            ruleset_sha256=adapter.scope.ruleset_sha256,
            producer_sha256=digest(producer),
            game_build="15.535.86",
            observation_domain="causal-frame-v1",
            seed=args.seed,
            opened_for_development=role == "development",
            coverage="complete",
            terminal_tick=playable["tick"],
            terminal_result="draw"
            if final["winner"] is None
            else ("owner_win" if final["winner"] == owner else "owner_loss"),
        )
        save_match_archive(
            args.output / f"seat{owner}",
            sequence,
            provenance,
            decisions[owner],
            np.stack(masks[owner]),
        )
        load_match_archive(
            args.output / f"seat{owner}",
            token_names=builder.token_names,
            source_path=result_path,
            ruleset_path=args.output / "gamedata.json",
            producer_path=producer,
        )
    seal_artifacts(
        args.output,
        kind="native_capture",
        role=role,
        protocol_sha256=frozen_protocol_sha,
        paths=capture_artifact_paths(
            family=args.family_id is not None,
            prospective=args.acceptance_protocol is not None,
        ),
    )
    print(
        "Completed native-driven game",
        playable["tick"],
        "winner",
        final["winner"]
        if role == "development"
        else "withheld pending frozen evaluation",
        flush=True,
    )


if __name__ == "__main__":
    main()
