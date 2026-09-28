from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "clasher.youtube.deck_closed_causal_corpus_audit.v1"
MINIMUM_REPLAY_GROUPS = 20
MINIMUM_ACTION_TARGETS = 1_000
MINIMUM_FULL_ACTOR_TARGETS = 250


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl_gzip(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def audit_match(manifest_path: Path, contract_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "clasher.youtube.fullmatch.extraction_manifest.v3":
        raise ValueError("causal manifest must use extraction manifest v3")
    mask_contract = manifest.get("public_mask_v3", {})
    if (
        mask_contract.get("contract_version") != 2
        or mask_contract.get("label_independent") is not True
        or mask_contract.get("offline_event_source")
        != "precision_gated_hud_cycle_events_v3"
    ):
        raise ValueError("causal manifest does not use cycle-v3 and mask-v2")
    artifacts = manifest["artifacts"]
    target_artifact = artifacts["offline_actor_targets"]
    if target_artifact.get("inference_eligible") is not False:
        raise ValueError("offline targets must be inference-ineligible")
    targets = json.loads(Path(target_artifact["path"]).read_text(encoding="utf-8"))
    if not isinstance(targets, list):
        raise TypeError("offline targets must be a JSON array")
    neutral_rows = _jsonl_gzip(Path(artifacts["neutral_sequence"]["path"]))
    neutral = {str(row["snapshot_id"]): row for row in neutral_rows}
    actors: dict[tuple[int, str], dict[str, Any]] = {}
    for artifact in artifacts["actor_trajectories"]:
        for row in _jsonl_gzip(Path(artifact["path"])):
            actors[(int(row["actor_id"]), str(row["snapshot_id"]))] = row

    in_mask = 0
    clocked = 0
    action_ready = 0
    full_actor_ready = 0
    for target in targets:
        key = (int(target["actor_id"]), str(target["snapshot_id"]))
        if key not in actors or key[1] not in neutral:
            raise ValueError("offline target does not join to actor and neutral rows")
        actor = actors[key]
        public = neutral[key[1]]["public"]
        target_in_mask = bool(target["expert_action_in_public_mask"])
        clock_valid = bool(public["clock"]["valid"])
        own_complete = bool(actor["own_hud"]["complete_valid"])
        in_mask += int(target_in_mask)
        clocked += int(clock_valid)
        action_ready += int(target_in_mask and clock_valid)
        full_actor_ready += int(target_in_mask and clock_valid and own_complete)

    source = manifest["source"]
    video_sha256 = str(source["video_sha256"])
    return {
        "video_sha256": video_sha256,
        "split_group_id": video_sha256,
        "manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
        "contract": {
            "path": str(contract_path),
            "sha256": _sha256(contract_path),
            "status": contract.get("status"),
            "failed_gates": contract.get("failed_gates", []),
        },
        "counts": {
            "offline_targets": len(targets),
            "targets_in_public_mask": in_mask,
            "targets_with_public_clock": clocked,
            "action_component_ready": action_ready,
            "full_actor_ready": full_actor_ready,
        },
    }


def audit_corpus(
    manifests: list[Path], contracts: list[Path]
) -> dict[str, Any]:
    if not manifests or len(manifests) != len(contracts):
        raise ValueError("manifest and contract lists must be nonempty and paired")
    matches = [
        audit_match(manifest.resolve(), contract.resolve())
        for manifest, contract in zip(manifests, contracts, strict=True)
    ]
    groups = [row["split_group_id"] for row in matches]
    if len(set(groups)) != len(groups):
        raise ValueError("replay groups must be unique")
    totals = {
        key: sum(int(row["counts"][key]) for row in matches)
        for key in (
            "offline_targets",
            "targets_in_public_mask",
            "targets_with_public_clock",
            "action_component_ready",
            "full_actor_ready",
        )
    }
    fully_verified = sum(row["contract"]["status"] == "passed" for row in matches)
    gates = {
        "minimum_replay_groups": len(matches) >= MINIMUM_REPLAY_GROUPS,
        "minimum_action_component_targets": (
            totals["action_component_ready"] >= MINIMUM_ACTION_TARGETS
        ),
        "minimum_full_actor_targets": (
            totals["full_actor_ready"] >= MINIMUM_FULL_ACTOR_TARGETS
        ),
        "at_least_three_fully_verified_replays": fully_verified >= 3,
    }
    return {
        "schema": SCHEMA,
        "decision": "ready_for_fresh_causal_bc" if all(gates.values()) else "collect_more",
        "mixing_policy": "youtube_current_client_only_no_hf_training_rows",
        "thresholds": {
            "minimum_replay_groups": MINIMUM_REPLAY_GROUPS,
            "minimum_action_component_targets": MINIMUM_ACTION_TARGETS,
            "minimum_full_actor_targets": MINIMUM_FULL_ACTOR_TARGETS,
            "minimum_fully_verified_replays": 3,
        },
        "gates": gates,
        "counts": {
            "replay_groups": len(matches),
            "fully_verified_replays": fully_verified,
            **totals,
        },
        "matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=Path, required=True)
    parser.add_argument("--contract", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = audit_corpus(args.manifest, args.contract)
    _atomic_json(args.output, payload)
    print(json.dumps({"output": str(args.output), **payload["counts"], "decision": payload["decision"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
