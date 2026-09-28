"""Finite opened-development branch comparisons; never selects a deployed action."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import traceback
import zipfile
from collections import deque
from pathlib import Path

import numpy as np
from collect_public_development_games import choose_public_action
from prepare_prospective_branch import prepare as prepare_prospective_branch
from read_native_public_levels import read_levels
from smoke_reference_battle import request

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.calibration_artifacts import branch_artifact_paths, seal_artifacts
from clasher.rl.calibration_families import claim_acceptance_branches
from clasher.rl.native_command_checks import validate_command_step
from clasher.rl.native_match_registry import canonical_digest
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
from clasher.rl.public_observation import (
    exact_public_observation,
    reference_public_observation,
)
from clasher.rl.public_reference_checks import (
    check_reference_entities,
    check_reference_packet,
    reference_token_maps,
)
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def decision_schedule(root, delay_ticks):
    """Submit only during playable time; an expired delayed play stays unplayed."""
    schedule = set(range(root, 6001, 30))
    if delay_ticks and root + delay_ticks < 6001:
        schedule.add(root + delay_ticks)
    return sorted(schedule)


def finalize_native(playable):
    # At the playable horizon, native tiebreak resolution
    # can still be running before the ended flag is set.
    assert playable["ended"] or playable["tick"] == 6001, (
        "native stopped before the playable horizon",
        playable["tick"],
    )
    final = playable
    for _ in range(400):
        if final["finalized"]:
            break
        request(26789, "step 1")
        final = request(26789, "observe")
    assert final["finalized"], (
        "native finalization exceeded 400 ticks",
        final["tick"],
    )
    return final


def response_rng(seed, tick, owner):
    # A skipped action cannot shift the other branch's subsequent random draws.
    return np.random.default_rng(np.random.SeedSequence([seed, tick, owner]))


def response_styles(protocol):
    styles = protocol.get("response_styles_by_owner", ["geometry", "geometry"])
    if (
        not isinstance(styles, list)
        or len(styles) != 2
        or any(
            not isinstance(style, str)
            or style not in {"geometry", "balanced", "pressure", "defense"}
            for style in styles
        )
    ):
        raise ValueError("response styles must declare two supported controllers")
    if "geometry" not in styles and len(protocol["response_seeds"]) != 1:
        raise ValueError(
            "deterministic response controllers require exactly one seed label"
        )
    return styles


def scalar_initial(initial, names, config, loader):
    players = []
    for owner in (0, 1):
        p = next(p for p in initial["players"] if p["owner"] == owner)
        players.append(
            PlayerState(
                owner,
                deck=[names[c["cardId"]] for c in p["deck"]],
                hand=[
                    names[c["cardId"]]
                    for c in sorted(p["hand"], key=lambda c: c["handIndex"])
                ],
                cycle_queue=deque(
                    names[c["cardId"]]
                    for c in sorted(p["cycle"], key=lambda c: c["cycleIndex"])
                ),
                elixir=p["elixir"],
            )
        )
    return BattleState(
        players=players, rng=random.Random(config["rndSeed"]), card_loader=loader
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--engine", choices=("both", "native", "scalar"), default="both"
    )
    parser.add_argument("--collection-protocol", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--family-id")
    parser.add_argument("--batched-native-levels", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    prospective = args.collection_protocol is not None
    if prospective:
        if args.registry is None or args.family_id is None:
            raise ValueError("prospective branches require registry and family")
        expected = prepare_prospective_branch(
            args.capture,
            args.collection_protocol,
            args.registry,
            args.family_id,
            args.catalog,
            Path.cwd(),
        )
        if protocol != expected:
            raise ValueError("branch protocol differs from frozen candidate derivation")
        if sha(args.gamedata) != sha(args.capture / "gamedata.json"):
            raise ValueError("branch ruleset differs from acceptance capture")
    elif protocol.get("role") != "development":
        raise ValueError("acceptance branches require a frozen collection protocol")
    if protocol["cadence_ticks"] != 30:
        raise ValueError("unsupported branch cadence")
    styles = response_styles(protocol)
    uses_public_opponents = any(style != "geometry" for style in styles)
    root = protocol["root_tick"]
    assert 90 <= root < 6001
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads((args.capture / "plan.json").read_text())
    if plan.get("role") == "acceptance" and not prospective:
        raise ValueError(
            "Acceptance captures require the frozen prospective branch evaluator; this runner is development-only"
        )
    recorded = json.loads((args.capture / "result.json").read_text())
    initial = json.loads((args.capture / "initial.json").read_text())
    config = plan["config"]
    loader = CardDataLoader(args.gamedata)
    names = {
        loader.get_card(n)._raw_entry["id"]: n for n in PUBLIC_REFERENCE_CARDS
    }
    card_names = PUBLIC_REFERENCE_CARDS
    catalog = NativeProjectileCatalog.from_csv(
        args.catalog, expected_sha256=args.catalog_sha256
    )
    builder = public_reference_builder(
        loader, catalog,
        card_semantics_version=4 if uses_public_opponents else 1,
    )
    controllers = [
        None if style == "geometry" else PublicScriptedOpponent(builder, style=style)
        for style in styles
    ]
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", sha(args.gamedata)),
        card_names=tuple(card_names),
        projectile_catalog=catalog,
    )
    reference_maps = reference_token_maps(builder, card_names, catalog)
    mask_builder = PublicActionMaskBuilder(builder)
    space = DiscreteTileActionSpace()
    sources = sorted(Path("src/clasher").rglob("*.py")) + [
        Path("scripts") / n
        for n in (
            "compare_reacting_public_branches.py",
            "prepare_prospective_branch.py",
            "select_reacting_public_root.py",
            "collect_public_development_games.py",
            "read_native_public_levels.py",
            "smoke_reference_battle.py",
        )
    ]
    source_hashes = {str(p): sha(p) for p in sources}
    inputs = [
        args.protocol,
        args.gamedata,
        args.catalog,
        *[
            args.capture / n
            for n in (
                "plan.json",
                "result.json",
                "initial.json",
                "native-frames.jsonl.gz",
            )
        ],
    ]
    if prospective:
        inputs.append(args.collection_protocol)
        frozen = json.loads(args.collection_protocol.read_text())
        inputs.extend(
            args.collection_protocol.parent / frozen[k + "_path"]
            for k in ("family_manifest", "reference_criteria", "decision_criteria")
        )
    input_hashes = {str(p): sha(p) for p in inputs}
    write(args.output / "protocol.json", protocol)
    write(
        args.output / "provenance.json",
        {
            "sources": source_hashes,
            "inputs": input_hashes,
            "public_card_roster": list(PUBLIC_REFERENCE_CARDS),
            "token_names": list(builder.token_names),
            "native_level_transport": "batched-adb"
            if args.batched_native_levels
            else "serial-adb",
        },
    )
    with zipfile.ZipFile(
        args.output / "producer-source.zip", "x", zipfile.ZIP_DEFLATED
    ) as z:
        for p in sources:
            z.write(p, str(p))
    root_reference = None
    with gzip.open(args.capture / "native-frames.jsonl.gz", "rt") as f:
        for line in f:
            frame = json.loads(line)
            if frame["ordinary"]["tick"] == root:
                root_reference = frame["ordinary"]
                break
    assert root_reference is not None
    commands = [c for c in recorded["commands"] if c["submitted_tick"] < root]
    assert all(c["native_acceptance_spend_evidence"] for c in commands)
    if prospective:
        claim_acceptance_branches(
            args.registry,
            family_id=args.family_id,
            root_id=protocol["root_duplicate_group_id"],
            protocol_sha256=protocol["collection_protocol_sha256"],
            branch_protocol_sha256=canonical_digest(protocol),
            attempts=[
                (c["name"], e)
                for c in protocol["candidates"]
                for e in (
                    ("native", "scalar") if args.engine == "both" else (args.engine,)
                )
            ],
            output_path=args.output,
        )
    outcomes = []
    for seed in protocol["response_seeds"]:
        for candidate in protocol["candidates"]:
            for engine in (
                ("native", "scalar") if args.engine == "both" else (args.engine,)
            ):
                out = args.output / f"{seed}-{candidate['name']}-{engine}"
                out.mkdir()
                events, history, decision_counts = [], [None, None], [0, 0]
                failure = None
                battle = None
                terminal = None
                attestation = request(26789, "attest") if engine == "native" else None
                try:
                    if engine == "native":
                        if (
                            prospective
                            and canonical_digest(attestation)
                            != frozen["native_attestation_sha256"]
                        ):
                            raise ValueError(
                                "native runtime differs from frozen attestation"
                            )
                        assert request(
                            26789,
                            "configure " + json.dumps(config, separators=(",", ":")),
                        )["ok"]
                        current = request(26789, "observe")
                        for key in ("objects", "players", "tick"):
                            assert current[key] == initial[key], key
                    else:
                        battle = scalar_initial(initial, names, config, loader)
                    tick = 0

                    def advance(target, engine=engine, battle=battle):
                        nonlocal tick
                        assert target >= tick
                        if engine == "native":
                            if target > tick and not request(26789, "observe")["ended"]:
                                request(26789, f"step {target - tick}")
                            tick = request(26789, "observe")["tick"]
                        else:
                            while battle.tick < target and not battle.game_over:
                                battle.step()
                            tick = battle.tick

                    def submit(owner, name, xy, at, engine=engine, battle=battle):
                        # Archived commands may use display aliases. Bind both
                        # engines to the fixed roster's action-card identity.
                        name = names[loader.get_card(name)._raw_entry["id"]]
                        if engine == "native":
                            card = loader.get_card(name)._raw_entry["id"]
                            receipt = request(
                                26789,
                                f"replay-schedule-card {owner} {card} {round(xy[0] * 1000)} {round(xy[1] * 1000)} {at + 1}",
                            )
                            assert receipt["ok"]
                            return receipt
                        else:
                            assert battle.deploy_card(owner, name, Position(*xy)), (
                                at,
                                owner,
                                name,
                            )

                    for c in commands:
                        advance(c["submitted_tick"])
                        submit(c["owner"], c["name"], c["xy"], tick)
                        if loader.get_card(c["name"])._raw_entry["id"] != 28000006:
                            history[c["owner"]] = AcceptedOwnPlay(c["name"], c["cost"])
                    advance(root)
                    if engine == "native":
                        current = request(26789, "observe")
                        for key in ("objects", "players", "tick", "ended", "winner"):
                            assert current[key] == root_reference[key], key
                    with gzip.open(out / "decisions.jsonl.gz", "xt") as stream:
                        schedule = decision_schedule(root, candidate["delay_ticks"])
                        for boundary in schedule:
                            advance(boundary)
                            before = (
                                request(26789, "observe")
                                if engine == "native"
                                else None
                            )
                            if before["ended"] if before else battle.game_over:
                                break
                            if engine == "native":
                                levels = read_levels(
                                    args.adb, batched=args.batched_native_levels
                                )
                                assert levels["ordinary"] == before
                                rich = request(26789, "observe-rich")
                                assert before == request(26789, "observe")
                                evidence = NativePublicLevelEvidence(
                                    tick=tick,
                                    generation=before["generation"],
                                    state_epoch=before["stateEpoch"],
                                    source_sha256=hashlib.sha256(
                                        json.dumps(levels, sort_keys=True).encode()
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
                                        own_last_play=history[owner],
                                    )
                                    for owner in (0, 1)
                                ]
                            else:
                                views = [
                                    (
                                        reference_public_observation
                                        if uses_public_opponents
                                        else exact_public_observation
                                    )(builder.build_actor(battle, owner))
                                    for owner in (0, 1)
                                ]
                            if prospective and engine == "native":
                                (
                                    card_tokens,
                                    body_tokens,
                                    effect_tokens,
                                    tower_tokens,
                                ) = reference_maps
                                for owner, view in enumerate(views):
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
                                            "Public reference validation failed: "
                                            + "; ".join(errors)
                                        )
                            selected = []
                            public_masks = []
                            for owner in (0, 1):
                                view = views[owner]
                                mask = mask_builder.build(
                                    PublicActionMaskInput.from_confidence_observation(
                                        view
                                    )
                                )
                                public_masks.append(mask.tolist())
                                action = 2304
                                forced = None
                                if boundary == root:
                                    forced = (
                                        protocol["opponent_root_action"]
                                        if owner != protocol["owner"]
                                        else (
                                            candidate["action"]
                                            if not candidate["delay_ticks"]
                                            else None
                                        )
                                    )
                                elif (
                                    boundary == root + candidate["delay_ticks"]
                                    and candidate["delay_ticks"]
                                ):
                                    forced = (
                                        candidate["action"]
                                        if owner == protocol["owner"]
                                        else None
                                    )
                                else:
                                    action = (
                                        controllers[owner].select_action(view)
                                        if controllers[owner] is not None
                                        else choose_public_action(
                                            view.observation,
                                            mask,
                                            response_rng(seed, boundary, owner),
                                        )
                                    )
                                if forced is not None:
                                    card_id = loader.get_card(forced["card"])._raw_entry["id"]
                                    token = builder.token_id(names[card_id])
                                    slots = np.flatnonzero(
                                        view.observation.hand_ids == token
                                    )
                                    assert len(slots) == 1
                                    action = space.encode_action(
                                        int(slots[0]),
                                        int(forced["xy"][0]),
                                        int(forced["xy"][1]),
                                        owner,
                                    )
                                assert mask[action], (boundary, owner, action)
                                choice = space.decode_action(action, owner)
                                name = (
                                    None
                                    if choice.is_no_op
                                    else builder.card_name_for_token_id(
                                        int(view.observation.hand_ids[choice.slot])
                                    )
                                )
                                cost = None
                                if name is not None:
                                    if engine == "native":
                                        hud = next(
                                            p
                                            for p in before["players"]
                                            if p["owner"] == owner
                                        )
                                        cost = next(
                                            c["cost"]
                                            for c in hud["hand"]
                                            if c["handIndex"] == choice.slot
                                        )
                                    else:
                                        cost = (
                                            history[owner].elixir_cost + 1
                                            if loader.get_card(name)._raw_entry["id"]
                                            == 28000006
                                            else loader.get_card(name).mana_cost
                                        )
                                selected.append(
                                    (owner, action, name, cost, choice.position)
                                )
                                decision_counts[owner] += 1
                            stream.write(
                                json.dumps(
                                    {
                                        "tick": tick,
                                        "actions": [s[1] for s in selected],
                                        "masks": public_masks,
                                        "public": [
                                            {
                                                "hand": v.observation.hand_ids.tolist(),
                                                "entity_ids": v.observation.entity_ids[
                                                    v.observation.entity_mask
                                                ].tolist(),
                                                "entities": v.observation.entity_features[
                                                    v.observation.entity_mask
                                                ].tolist(),
                                            }
                                            for v in views
                                        ],
                                        "native": before,
                                        "native_rich": rich
                                        if engine == "native"
                                        else None,
                                        "level_source": levels
                                        if engine == "native"
                                        else None,
                                    },
                                    separators=(",", ":"),
                                )
                                + "\n"
                            )
                            receipts = []
                            for owner, action, name, cost, pos in selected:
                                if name is not None:
                                    receipt = submit(owner, name, [pos.x, pos.y], tick)
                                    if engine == "native":
                                        receipts.append(receipt)
                            advance(boundary + 1)
                            after = (
                                request(26789, "observe")
                                if engine == "native"
                                else None
                            )
                            if prospective and engine == "native":
                                validate_command_step(before, after, receipts)
                            for owner, action, name, cost, pos in selected:
                                if name is None:
                                    continue
                                if engine == "native":
                                    old = next(
                                        p
                                        for p in before["players"]
                                        if p["owner"] == owner
                                    )
                                    new = next(
                                        p
                                        for p in after["players"]
                                        if p["owner"] == owner
                                    )
                                    spent = (
                                        old["elixirRaw"] - new["elixirRaw"]
                                    ) / 10000
                                    if spent < cost - 0.1:
                                        raise RuntimeError(
                                            "Native deployment lacked elixir-spend evidence: "
                                            f"tick={tick}, owner={owner}, card={name}, "
                                            f"action={action}, xy={[pos.x, pos.y]}, "
                                            f"cost={cost}, net_spent={spent}, "
                                            f"before_raw={old['elixirRaw']}, "
                                            f"after_raw={new['elixirRaw']}"
                                        )
                                if loader.get_card(name)._raw_entry["id"] != 28000006:
                                    history[owner] = AcceptedOwnPlay(name, cost)
                                events.append(
                                    {
                                        "submitted_tick": boundary,
                                        "execution_tick": tick,
                                        "owner": owner,
                                        "name": name,
                                        "action": action,
                                        "xy": [pos.x, pos.y],
                                        "cost": cost,
                                    }
                                )
                            if decision_counts[0] % 10 == 0:
                                print(
                                    engine,
                                    seed,
                                    candidate["name"],
                                    "tick",
                                    tick,
                                    "decisions",
                                    decision_counts,
                                    flush=True,
                                )
                        advance(6001)
                        if engine == "native":
                            playable = request(26789, "observe")
                            final = finalize_native(playable)
                            towers = [
                                e
                                for e in playable["objects"]
                                if e["cardId"] == -1 and e["hp"] is not None
                            ]
                            terminal = {
                                "tick": playable["tick"],
                                "winner": final["winner"],
                                "towers": towers,
                            }
                            assert attestation == request(26789, "attest")
                        else:
                            assert battle.game_over
                            terminal = {
                                "tick": battle.tick,
                                "winner": battle.winner,
                                "towers": [
                                    {
                                        "owner": e.player_id,
                                        "hp": e.hitpoints,
                                        "x": round(e.position.x * 1000),
                                        "y": round(e.position.y * 1000),
                                    }
                                    for e in battle.entities.values()
                                    if e.entity_kind == 1
                                    and e.card_stats.name in ("Tower", "KingTower")
                                ],
                            }
                except (
                    AssertionError,
                    ValueError,
                    RuntimeError,
                    OSError,
                    KeyError,
                    AttributeError,
                ) as error:
                    failure = {
                        "type": type(error).__name__,
                        "message": str(error),
                        "traceback": traceback.format_exc(),
                    }
                result = {
                    "engine": engine,
                    "candidate": candidate["name"],
                    "response_seed": seed,
                    "terminal": terminal,
                    "failure": failure,
                    "commands": events,
                    "decision_counts": decision_counts,
                }
                if prospective:
                    result["native_attestation_sha256"] = (
                        canonical_digest(attestation) if engine == "native" else None
                    )
                write(out / "result.json", result)
                outcomes.append(result)
                write(args.output / "results.json", outcomes)
                print(
                    engine,
                    seed,
                    candidate["name"],
                    "failure",
                    failure,
                    "terminal",
                    None
                    if terminal is None
                    else (
                        "withheld pending frozen evaluation"
                        if prospective
                        else (terminal["tick"], terminal["winner"])
                    ),
                    flush=True,
                )
                if failure:
                    raise RuntimeError(failure)
    assert source_hashes == {str(p): sha(p) for p in sources}
    assert input_hashes == {str(p): sha(p) for p in inputs}
    write(
        args.output / "complete.json",
        {
            "role": protocol["role"],
            "sources_unchanged": True,
            "branches": len(outcomes),
            "collection_protocol_sha256": protocol.get("collection_protocol_sha256"),
        },
    )

    seal_artifacts(
        args.output,
        kind="paired_branches",
        role=protocol["role"],
        protocol_sha256=protocol.get("collection_protocol_sha256"),
        paths=branch_artifact_paths(
            protocol, ("native", "scalar") if args.engine == "both" else (args.engine,)
        ),
    )


if __name__ == "__main__":
    main()
