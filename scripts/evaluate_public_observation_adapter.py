from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from typing import Any

import numpy as np

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    load_corpus,
    load_public_observation_sidecar,
    sequence_chunks,
)
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.train_recurrent import resolve_learner_device
from scripts.fit_public_observation_adapter import evaluate_adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate confidence adapters against an exact-state teacher"
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-observation-sidecar", required=True)
    parser.add_argument("--teacher-checkpoint", required=True)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    return parser.parse_args()


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if args.sequence_length <= 1 or args.batch_size <= 0:
        raise ValueError("sequence length and batch size must be positive")
    device = resolve_learner_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    sidecar_path = resolve_path(args.public_observation_sidecar, must_exist=True)
    teacher_path = resolve_path(args.teacher_checkpoint, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    metadata, exact_arrays = load_corpus(corpus_path)
    public_arrays = load_public_observation_sidecar(
        sidecar_path,
        base_arrays=exact_arrays,
    )
    all_indices = np.arange(len(exact_arrays["episode_ids"]), dtype=np.int64)
    chunks = sequence_chunks(
        exact_arrays["episode_ids"],
        all_indices,
        sequence_length=args.sequence_length,
    )
    teacher_loaded = load_policy_checkpoint(
        teacher_path,
        device=device,
        decks_path=decks_path,
    )
    if tuple(teacher_loaded.checkpoint["token_names"]) != tuple(metadata.token_names):
        raise ValueError("teacher checkpoint and corpus token vocabularies do not match")
    candidates: dict[str, Any] = {}
    for candidate_arg in args.candidate:
        candidate_path = resolve_path(candidate_arg, must_exist=True)
        loaded = load_policy_checkpoint(
            candidate_path,
            device=device,
            decks_path=decks_path,
        )
        if not loaded.model.config.public_observation_confidence:
            raise ValueError(f"candidate is not confidence-aware: {candidate_path}")
        if tuple(loaded.checkpoint["token_names"]) != tuple(metadata.token_names):
            raise ValueError(
                f"candidate and corpus token vocabularies do not match: {candidate_path}"
            )
        candidates[str(candidate_path)] = {
            "sha256": file_sha256(candidate_path),
            "metrics": evaluate_adapter(
                teacher=teacher_loaded.model,
                student=loaded.model,
                exact_arrays=exact_arrays,
                public_arrays=public_arrays,
                chunks=chunks,
                device=device,
                batch_size=args.batch_size,
            ),
        }
    return {
        "schema_version": 1,
        "objective": "exact-to-public-policy-distillation-evaluation-v1",
        "device": str(device),
        "corpus": str(corpus_path),
        "corpus_sha256": file_sha256(corpus_path),
        "public_observation_sidecar": str(sidecar_path),
        "public_observation_sidecar_sha256": file_sha256(sidecar_path),
        "teacher_checkpoint": str(teacher_path),
        "teacher_checkpoint_sha256": file_sha256(teacher_path),
        "sequence_length": args.sequence_length,
        "sequences": len(chunks),
        "evaluated_tokens": int(chunks.size),
        "candidates": candidates,
    }


def main() -> None:
    args = parse_args()
    result = evaluate(args)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
