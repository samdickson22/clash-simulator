"""Derive acceptance branch candidates exclusively from the frozen collection plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from select_reacting_public_root import SelectionRule, select_protocol

from clasher.data import CardDataLoader
from clasher.rl.calibration_artifacts import capture_artifact_paths, verify_artifacts
from clasher.rl.calibration_collection import (
    verify_collection_protocol,
    verify_protocol_documents,
)
from clasher.rl.calibration_families import require_collection_claim
from clasher.rl.native_match_registry import canonical_digest


def prepare(capture, frozen_path, registry, family_id, catalog, workspace):
    plan = json.loads((capture / "plan.json").read_text())
    if plan.get("role") != "acceptance":
        raise ValueError("prospective selector requires an acceptance capture")
    protocol, family, protocol_sha = verify_collection_protocol(
        frozen_path,
        workspace=workspace,
        registry=registry,
        family_id=family_id,
        config=plan["config"],
        gamedata=capture / "gamedata.json",
        catalog=catalog,
        opponent_seat=json.loads(frozen_path.read_text())["public_opponent_seat"],
        opponent_style=json.loads(frozen_path.read_text())["public_opponent_style"],
    )
    if plan.get("collection_protocol_sha256") != protocol_sha:
        raise ValueError("capture belongs to a different collection protocol")
    saved = (capture / "collection-protocol.json").read_bytes()
    if hashlib.sha256(saved).hexdigest() != protocol_sha:
        raise ValueError("captured protocol copy differs")
    expected_controllers = ["fixed-public-geometry-v1", "fixed-public-geometry-v1"]
    expected_controllers[protocol.public_opponent_seat] = (
        f"public-scripted-{protocol.public_opponent_style}-v1"
    )
    if plan.get("controllers_by_owner") != expected_controllers:
        raise ValueError("capture controllers differ from frozen collection plan")
    require_collection_claim(
        registry,
        family_id=family_id,
        root_id="native-root-v1:" + canonical_digest(plan["config"]),
        protocol_sha256=protocol_sha,
        capture_path=capture,
    )
    verify_artifacts(
        capture,
        kind="native_capture",
        role="acceptance",
        protocol_sha256=protocol_sha,
        required_paths=capture_artifact_paths(family=True, prospective=True),
    )
    if (
        canonical_digest(json.loads((capture / "native-attestation.json").read_text()))
        != protocol.native_attestation_sha256
    ):
        raise ValueError("captured native runtime differs from frozen attestation")
    reference, _ = verify_protocol_documents(protocol, frozen_path.parent)
    if plan.get("public_card_roster") != list(reference.cards):
        raise ValueError("capture must use the full frozen public roster for tokenization")
    loader = CardDataLoader(capture / "gamedata.json")
    # Root eligibility is derived from the declared roster's base body cards,
    # never from the eventual winner, HP utility, or an attractive branch result.
    cards = [
        loader.get_card(n)._raw_entry["id"]
        for n in reference.cards
        if loader.get_card(n)._raw_entry.get("summonCharacterData")
    ]
    config_sha = canonical_digest(plan["config"])
    start = protocol.root_start_ticks[config_sha]
    styles = [protocol.branch_other_style, protocol.branch_other_style]
    styles[protocol.public_opponent_seat] = protocol.public_opponent_style
    rule = SelectionRule(
        owner=protocol.public_opponent_seat,
        earliest_tick=start,
        latest_tick=start + protocol.branch_window_ticks,
        card_ids=cards,
        x_offsets=list(protocol.branch_x_offsets),
        response_seeds=[protocol.branch_response_seed],
        include_delay_one=protocol.branch_include_delay_one,
        event_selection_seed=protocol.root_event_seeds.get(config_sha),
        response_styles_by_owner=tuple(styles),
    )
    result = select_protocol(
        capture,
        rule,
        rule_sha256=canonical_digest(rule.model_dump(mode="json")),
        expected_role="acceptance",
    )
    result.update(
        family=family.family_id,
        collection_protocol_sha256=protocol_sha,
        frozen_selection_rule=rule.model_dump(mode="json"),
    )
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--collection-protocol", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--family-id", required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = prepare(
        args.capture,
        args.collection_protocol,
        args.registry,
        args.family_id,
        args.catalog,
        Path.cwd(),
    )
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    print("Prepared frozen branch candidates; no outcomes evaluated")


if __name__ == "__main__":
    main()
