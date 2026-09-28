# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import load_corpus
from clasher.rl.model import ClasherPolicy
from scripts.train_student_state_symmetry_dagger import (
    PLACEMENT_ACTIONS,
    _load_policy,
    _single_step_inputs,
    build_teacher_targets,
    episode_sequences,
    masked_joint_probabilities,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@torch.no_grad()
def recurrent_policy_probabilities(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    *,
    device: torch.device,
    trim_entity_padding: bool,
) -> np.ndarray:
    """Evaluate exact masked joint probabilities in episode order."""

    sample_count = int(arrays["hand_ids"].shape[0])
    probabilities = np.full(
        (sample_count, PLACEMENT_ACTIONS + 2), np.nan, dtype=np.float32
    )
    model.eval()
    rows = np.arange(sample_count, dtype=np.int64)
    for episode_rows in episode_sequences(arrays["episode_ids"], rows):
        state = model.initial_state(1, device=device)
        for index in episode_rows:
            inputs = _single_step_inputs(
                arrays,
                int(index),
                device,
                trim_entity_padding=trim_entity_padding,
            )
            output = model(inputs, state)
            state = tuple(value.detach() for value in output.next_state)
            probabilities[index] = (
                masked_joint_probabilities(
                    output,
                    inputs.action_mask,
                    temperature=1.0,
                )[0]
                .float()
                .cpu()
                .numpy()
            )
    if not np.isfinite(probabilities).all():
        raise FloatingPointError("policy probability evaluation left non-finite rows")
    return probabilities


def summarize_designated_probability(
    probabilities: np.ndarray,
    arrays: dict[str, np.ndarray],
    *,
    card_token_id: int,
) -> dict[str, float | int | None]:
    """Summarize joint probability assigned to one currently held legal card."""

    sample_count = int(arrays["hand_ids"].shape[0])
    expected_shape = (sample_count, PLACEMENT_ACTIONS + 2)
    if probabilities.shape != expected_shape:
        raise ValueError(f"probabilities must have shape {expected_shape}")
    if not np.isfinite(probabilities).all():
        raise ValueError("probabilities must be finite")
    if not np.allclose(probabilities.sum(axis=-1), 1.0, atol=2e-6):
        raise ValueError("probabilities must sum to one")

    hands = np.asarray(arrays["hand_ids"][:, :NUM_HAND_SLOTS], dtype=np.int64)
    masks = np.asarray(arrays["action_masks"][:, :PLACEMENT_ACTIONS], dtype=np.bool_)
    masks = masks.reshape(sample_count, NUM_HAND_SLOTS, NUM_TILES)
    matches = hands == int(card_token_id)
    if np.any(matches.sum(axis=-1) > 1):
        raise ValueError("designated card appears in multiple current-hand slots")
    in_hand = matches.any(axis=-1)
    slot = matches.argmax(axis=-1)
    row = np.arange(sample_count)
    legal = in_hand & masks[row, slot].any(axis=-1)

    placement = probabilities[:, :PLACEMENT_ACTIONS].reshape(
        sample_count, NUM_HAND_SLOTS, NUM_TILES
    )
    mass = placement[row, slot].sum(axis=-1)
    greedy_action = probabilities.argmax(axis=-1)
    greedy_slot = greedy_action // NUM_TILES
    greedy_designated = legal & (greedy_action < PLACEMENT_ACTIONS) & (greedy_slot == slot)

    observed_actions = np.asarray(arrays["expert_actions"], dtype=np.int64)
    observed_slot = observed_actions // NUM_TILES
    observed_designated = (
        legal
        & (observed_actions < PLACEMENT_ACTIONS)
        & (observed_slot == slot)
    )
    selected = mass[legal]
    if selected.size == 0:
        return {
            "samples": sample_count,
            "in_hand_samples": int(in_hand.sum()),
            "legal_samples": 0,
            "mean_probability": None,
            "median_probability": None,
            "maximum_probability": None,
            "greedy_count": 0,
            "greedy_rate": None,
            "observed_play_count": 0,
            "observed_play_rate": None,
        }
    return {
        "samples": sample_count,
        "in_hand_samples": int(in_hand.sum()),
        "legal_samples": int(legal.sum()),
        "mean_probability": float(selected.mean()),
        "median_probability": float(np.median(selected)),
        "maximum_probability": float(selected.max()),
        "greedy_count": int(greedy_designated.sum()),
        "greedy_rate": float(greedy_designated.sum() / legal.sum()),
        "observed_play_count": int(observed_designated.sum()),
        "observed_play_rate": float(observed_designated.sum() / legal.sum()),
    }


def _checkpoint_payload(path: Path) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError(f"checkpoint is not an object: {path}")
    return payload


def audit_corpus(
    *,
    archetype: str,
    designated_card: str,
    corpus_path: Path,
    teacher: ClasherPolicy,
    student: ClasherPolicy,
    teacher_checkpoint: Path,
    student_checkpoint: Path,
    state_behavior_checkpoint: Path,
    device: torch.device,
    trim_entity_padding: bool,
) -> dict[str, Any]:
    metadata, arrays = load_corpus(corpus_path)
    if metadata.label_source != "behavior":
        raise ValueError("audit corpus must contain behavior-policy trajectories")
    if metadata.behavior_checkpoint is None:
        raise ValueError("audit corpus has no behavior checkpoint provenance")
    if (
        Path(metadata.behavior_checkpoint).resolve()
        != state_behavior_checkpoint.resolve()
    ):
        raise ValueError("audit corpus behavior checkpoint provenance mismatch")
    try:
        token_id = metadata.token_names.index(designated_card)
    except ValueError as error:
        raise ValueError(f"unknown designated card token {designated_card!r}") from error

    symmetrized, original, teacher_metrics = build_teacher_targets(
        teacher,
        arrays,
        device=device,
        temperature=1.0,
        trim_entity_padding=trim_entity_padding,
        progress_interval=max(1, len(arrays["episode_ids"])),
    )
    student_probabilities = recurrent_policy_probabilities(
        student,
        arrays,
        device=device,
        trim_entity_padding=trim_entity_padding,
    )
    return {
        "archetype": archetype,
        "designated_card": designated_card,
        "corpus": str(corpus_path.resolve()),
        "corpus_sha256": file_sha256(corpus_path),
        "corpus_metadata": json.loads(metadata.to_json()),
        "teacher_checkpoint": str(teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": file_sha256(teacher_checkpoint),
        "student_checkpoint": str(student_checkpoint.resolve()),
        "student_checkpoint_sha256": file_sha256(student_checkpoint),
        "state_behavior_checkpoint": str(state_behavior_checkpoint.resolve()),
        "state_behavior_matches_student": (
            state_behavior_checkpoint.resolve() == student_checkpoint.resolve()
        ),
        "teacher_target_metrics": teacher_metrics,
        "teacher_original": summarize_designated_probability(
            original,
            arrays,
            card_token_id=token_id,
        ),
        "teacher_symmetrized": summarize_designated_probability(
            symmetrized,
            arrays,
            card_token_id=token_id,
        ),
        "student": summarize_designated_probability(
            student_probabilities,
            arrays,
            card_token_id=token_id,
        ),
    }


def _manifest_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("win-condition manifest has no entries")
    return entries


def select_manifest_entries(
    entries: list[dict[str, Any]],
    archetypes: Iterable[str],
) -> list[dict[str, Any]]:
    """Select requested archetypes, treating an empty request as all entries."""

    selected = set(archetypes)
    filtered = [
        entry
        for entry in entries
        if not selected or entry.get("archetype") in selected
    ]
    available = {str(entry.get("archetype")) for entry in filtered}
    if selected and selected != available:
        missing = sorted(selected - available)
        raise ValueError(f"unknown requested archetypes: {missing}")
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit original teacher, 24-way symmetrized teacher, and student "
            "win-condition probabilities on evaluation-only behavior states"
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--teacher-checkpoint", type=Path, required=True)
    parser.add_argument("--student-checkpoint", type=Path, required=True)
    parser.add_argument(
        "--state-behavior-checkpoint",
        type=Path,
        default=None,
        help=(
            "checkpoint that generated the fixed audit states; defaults to the "
            "audited student, but can pin an earlier policy for matched comparisons"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archetype", action="append", default=[])
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--trim-entity-padding", action="store_true")
    args = parser.parse_args()

    device = torch.device(args.device)
    teacher_path = args.teacher_checkpoint.resolve()
    student_path = args.student_checkpoint.resolve()
    state_behavior_path = (
        args.state_behavior_checkpoint.resolve()
        if args.state_behavior_checkpoint is not None
        else student_path
    )
    teacher = _load_policy(_checkpoint_payload(teacher_path), device=device)
    student = _load_policy(_checkpoint_payload(student_path), device=device)
    entries = select_manifest_entries(
        _manifest_entries(args.manifest),
        args.archetype,
    )

    results = []
    for entry in entries:
        archetype = str(entry["archetype"])
        tag = archetype.replace("-", "_")
        corpus_path = (args.corpus_root / f"{tag}.npz").resolve()
        if not corpus_path.is_file():
            raise FileNotFoundError(corpus_path)
        results.append(
            audit_corpus(
                archetype=archetype,
                designated_card=str(entry["designated_card"]),
                corpus_path=corpus_path,
                teacher=teacher,
                student=student,
                teacher_checkpoint=teacher_path,
                student_checkpoint=student_path,
                state_behavior_checkpoint=state_behavior_path,
                device=device,
                trim_entity_padding=args.trim_entity_padding,
            )
        )
        print(json.dumps(results[-1], sort_keys=True), flush=True)

    output = {
        "schema_version": 1,
        "purpose": "evaluation_only_symmetrized_teacher_ceiling_audit",
        "heldout_states_used_for_training": False,
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": file_sha256(args.manifest),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
