"""Verify a materialized mechanics policy and score frozen held-out splits."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from clasher.paths import resolve_path
from scripts.fit_mechanics_slot_probe import (
    MechanicsSlotScorer,
    SlotExamples,
    extract_examples,
)
from scripts.sweep_mechanics_slot_blend import normalized_legal_logits


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_aligned(parent: SlotExamples, candidate: SlotExamples) -> None:
    for name in ("cards", "legal", "target", "target_card"):
        if not torch.equal(getattr(parent, name), getattr(candidate, name)):
            raise ValueError(f"candidate examples changed aligned {name}")
    if parent.episode.shape != candidate.episode.shape or not bool(
        (parent.episode == candidate.episode).all()
    ):
        raise ValueError("candidate examples changed episode alignment")


@torch.no_grad()
def evaluate_materialized_split(
    *,
    model: MechanicsSlotScorer,
    alpha: float,
    parent: SlotExamples,
    candidate: SlotExamples,
) -> dict[str, float | int]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("blend alpha must be in [0, 1]")
    _assert_aligned(parent, candidate)
    base = normalized_legal_logits(parent.base_logits, parent.legal)
    mechanics = normalized_legal_logits(
        model(parent.state, parent.cards),
        parent.legal,
    )
    expected = normalized_legal_logits(
        (1.0 - alpha) * base + alpha * mechanics,
        parent.legal,
    )
    actual = normalized_legal_logits(candidate.base_logits, candidate.legal)
    torch.testing.assert_close(actual, expected, atol=2e-6, rtol=2e-6)
    predictions = actual.argmax(dim=-1)
    base_predictions = base.argmax(dim=-1)
    target = parent.target
    correct = predictions == target
    base_correct = base_predictions == target
    return {
        "samples": int(target.numel()),
        "accuracy": float(correct.float().mean()),
        "base_accuracy": float(base_correct.float().mean()),
        "accuracy_gain": float(correct.float().mean() - base_correct.float().mean()),
        "disagreement_with_base": float(
            (predictions != base_predictions).float().mean()
        ),
        "improvements_vs_base": int((~base_correct & correct).sum()),
        "regressions_vs_base": int((base_correct & ~correct).sum()),
        "conditional_nll": float(torch.nn.functional.cross_entropy(actual, target)),
        "materialized_logit_parity": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-checkpoint", required=True, type=Path)
    parser.add_argument("--candidate-checkpoint", required=True, type=Path)
    parser.add_argument("--probe-checkpoint", required=True, type=Path)
    parser.add_argument("--alpha", required=True, type=float)
    parser.add_argument("--simulator-validation-corpus", required=True, type=Path)
    parser.add_argument("--simulator-heldout-corpus", required=True, type=Path)
    parser.add_argument("--human-validation-corpus", required=True, type=Path)
    parser.add_argument("--human-validation-sidecar", required=True, type=Path)
    parser.add_argument("--human-archetype-corpus", required=True, type=Path)
    parser.add_argument("--human-archetype-sidecar", required=True, type=Path)
    parser.add_argument("--human-chronology-corpus", required=True, type=Path)
    parser.add_argument("--human-chronology-sidecar", required=True, type=Path)
    parser.add_argument("--decks-path", default=Path("decks.json"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    parent_checkpoint = resolve_path(args.parent_checkpoint, must_exist=True)
    candidate_checkpoint = resolve_path(args.candidate_checkpoint, must_exist=True)
    probe_path = resolve_path(args.probe_checkpoint, must_exist=True)
    decks_path = resolve_path(args.decks_path, must_exist=True)
    probe = torch.load(probe_path, map_location="cpu", weights_only=False)
    if int(probe.get("semantics_version", 0)) != 1:
        raise ValueError("candidate evaluator requires a mechanics-v1 probe")
    if int(probe.get("hidden_size", -1)) != 0:
        raise ValueError("candidate evaluator requires the linear probe")
    model = MechanicsSlotScorer(
        state_size=probe["state_dict"]["state_query.weight"].shape[1],
        card_size=16,
        hidden_size=0,
    ).eval()
    model.load_state_dict(probe["state_dict"])
    split_paths = {
        "simulator_validation": (
            resolve_path(args.simulator_validation_corpus, must_exist=True),
            None,
        ),
        "simulator_heldout": (
            resolve_path(args.simulator_heldout_corpus, must_exist=True),
            None,
        ),
        "human_validation": (
            resolve_path(args.human_validation_corpus, must_exist=True),
            resolve_path(args.human_validation_sidecar, must_exist=True),
        ),
        "human_archetype_test": (
            resolve_path(args.human_archetype_corpus, must_exist=True),
            resolve_path(args.human_archetype_sidecar, must_exist=True),
        ),
        "human_chronology_test": (
            resolve_path(args.human_chronology_corpus, must_exist=True),
            resolve_path(args.human_chronology_sidecar, must_exist=True),
        ),
    }
    metrics: dict[str, dict[str, float | int]] = {}
    token_names: tuple[str, ...] | None = None
    for name, (corpus, sidecar) in split_paths.items():
        parent, parent_tokens = extract_examples(
            corpus_path=corpus,
            checkpoint_path=parent_checkpoint,
            decks_path=decks_path,
            semantics_version=1,
            public_sidecar=sidecar,
        )
        candidate, candidate_tokens = extract_examples(
            corpus_path=corpus,
            checkpoint_path=candidate_checkpoint,
            decks_path=decks_path,
            semantics_version=1,
            public_sidecar=sidecar,
        )
        token_names = token_names or parent_tokens
        if parent_tokens != token_names or candidate_tokens != token_names:
            raise ValueError("candidate evaluation token vocabularies differ")
        metrics[name] = evaluate_materialized_split(
            model=model,
            alpha=args.alpha,
            parent=parent,
            candidate=candidate,
        )
    if tuple(probe.get("token_names", ())) != token_names:
        raise ValueError("probe/candidate token vocabulary mismatch")
    payload: dict[str, Any] = {
        "schema": "mechanics-slot-materialized-evaluation-v1",
        "parent_checkpoint": str(parent_checkpoint),
        "parent_checkpoint_sha256": _sha256(parent_checkpoint),
        "candidate_checkpoint": str(candidate_checkpoint),
        "candidate_checkpoint_sha256": _sha256(candidate_checkpoint),
        "probe_checkpoint": str(probe_path),
        "probe_checkpoint_sha256": _sha256(probe_path),
        "alpha": float(args.alpha),
        "selection_splits": [
            "simulator_validation",
            "simulator_heldout",
            "human_validation",
        ],
        "post_selection_evaluation_only_splits": [
            "human_archetype_test",
            "human_chronology_test",
        ],
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
