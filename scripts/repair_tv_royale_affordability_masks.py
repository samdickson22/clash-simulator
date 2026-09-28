from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.structured_obs import StructuredObservationBuilder

SPLIT_NAMES = ("train", "validation", "archetype_test", "chronology_test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair TV Royale action masks using observed elixir affordability"
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--manifest-out", required=True)
    return parser.parse_args()


def _decode_metadata(value: np.ndarray) -> dict[str, Any]:
    payload = json.loads(str(np.asarray(value).item()))
    if not isinstance(payload, dict):
        raise TypeError("corpus metadata_json must encode an object")
    return payload


def _recurrent_columns(
    *,
    episode_ids: np.ndarray,
    expert_actions: np.ndarray,
    no_op_action: int,
) -> tuple[np.ndarray, np.ndarray]:
    starts = np.zeros((len(episode_ids),), dtype=np.bool_)
    previous = np.full((len(episode_ids),), no_op_action, dtype=np.int64)
    last_action: dict[int, int] = {}
    for index, (episode_id, expert_action) in enumerate(
        zip(episode_ids.tolist(), expert_actions.tolist(), strict=True)
    ):
        episode = int(episode_id)
        starts[index] = episode not in last_action
        previous[index] = last_action.get(episode, no_op_action)
        last_action[episode] = int(expert_action)
    return starts, previous


def repair_split(
    input_path: Path,
    output_path: Path,
    *,
    decks_path: Path,
) -> dict[str, Any]:
    with np.load(input_path, allow_pickle=False) as source:
        arrays = {name: np.asarray(source[name]) for name in source.files}
    metadata = _decode_metadata(arrays["metadata_json"])
    token_names = tuple(str(name) for name in metadata["token_names"])
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=int(metadata["max_entities"]),
        token_names=token_names,
    )
    card_costs = np.zeros((len(token_names),), dtype=np.float32)
    for token_id, name in enumerate(token_names):
        if name.startswith("<"):
            continue
        stats = builder.loader.get_card(name)
        card_costs[token_id] = float(getattr(stats, "mana_cost", 0.0) or 0.0)

    hand_ids = np.asarray(arrays["hand_ids"], dtype=np.int64)
    elixir = np.asarray(arrays["global_features"], dtype=np.float32)[:, 5] * 10.0
    masks = np.asarray(arrays["action_masks"], dtype=np.bool_).copy()
    legal_before = np.count_nonzero(masks, axis=1)
    for slot in range(NUM_HAND_SLOTS):
        slot_cost = card_costs[hand_ids[:, slot]]
        unaffordable = slot_cost > elixir + 1e-5
        start = slot * NUM_TILES
        masks[unaffordable, start : start + NUM_TILES] = False
    no_op_action = NUM_HAND_SLOTS * NUM_TILES
    masks[:, no_op_action] = True
    arrays["action_masks"] = masks

    expert_actions = np.asarray(arrays["expert_actions"], dtype=np.int64)
    expert_legal = masks[np.arange(len(expert_actions)), expert_actions]
    removed_indices = np.flatnonzero(~expert_legal)
    row_columns = {
        name
        for name, value in arrays.items()
        if name != "metadata_json" and value.ndim >= 1 and value.shape[0] == len(expert_actions)
    }
    for name in row_columns:
        arrays[name] = arrays[name][expert_legal]

    starts, previous = _recurrent_columns(
        episode_ids=np.asarray(arrays["episode_ids"], dtype=np.int64),
        expert_actions=np.asarray(arrays["expert_actions"], dtype=np.int64),
        no_op_action=no_op_action,
    )
    arrays["episode_starts"] = starts
    arrays["previous_actions"] = previous
    metadata["decisions"] = int(expert_legal.sum())
    metadata["samples"] = int(expert_legal.sum())
    metadata["label_source"] = f"{metadata['label_source']}-affordability-v1"
    affordability_provenance = {
        "source": "observed-global-elixir-and-official-card-cost",
        "unaffordable_expert_rows_removed": int((~expert_legal).sum()),
        "epsilon": 1e-5,
    }
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
    arrays["affordability_repair_json"] = np.asarray(
        json.dumps(affordability_provenance, sort_keys=True)
    )
    atomic_save_npz(output_path, arrays)

    legal_after_all = np.count_nonzero(masks, axis=1)
    retained_legal_after = legal_after_all[expert_legal]
    return {
        "input": str(input_path),
        "input_sha256": file_sha256(input_path),
        "output": str(output_path),
        "output_sha256": file_sha256(output_path),
        "input_rows": len(expert_actions),
        "output_rows": int(expert_legal.sum()),
        "removed_unaffordable_expert_rows": int((~expert_legal).sum()),
        "removed_source_indices": [int(index) for index in removed_indices],
        "legal_actions_before": {
            "mean": float(np.mean(legal_before)),
            "median": float(np.median(legal_before)),
        },
        "legal_actions_after": {
            "mean": float(np.mean(retained_legal_after)),
            "median": float(np.median(retained_legal_after)),
        },
        "expert_actions_all_legal": bool(
            np.all(
                arrays["action_masks"][
                    np.arange(int(expert_legal.sum())), arrays["expert_actions"]
                ]
            )
        ),
        "episode_starts": int(np.count_nonzero(starts)),
    }


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    decks_path = Path(args.decks_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for split in SPLIT_NAMES:
        input_path = input_dir / f"{split}.npz"
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        results[split] = repair_split(
            input_path,
            output_dir / f"{split}.npz",
            decks_path=decks_path,
        )
    source_manifest = input_dir / "split_manifest.json"
    if source_manifest.is_file():
        results["source_split_manifest"] = {
            "path": str(source_manifest),
            "sha256": file_sha256(source_manifest),
        }
    manifest = {
        "schema": "tv-royale-affordability-mask-repair-v1",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "decks_path": str(decks_path),
        "decks_sha256": file_sha256(decks_path),
        "splits": results,
    }
    manifest_path = Path(args.manifest_out).resolve()
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
