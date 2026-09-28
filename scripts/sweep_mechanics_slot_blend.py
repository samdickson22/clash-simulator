"""Sweep conservative incumbent/mechanics-only conditional-card mixtures."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import resolve_path
from scripts.fit_mechanics_slot_probe import (
    MechanicsSlotScorer,
    SlotExamples,
    extract_examples,
)


def normalized_legal_logits(
    logits: torch.Tensor, legal: torch.Tensor
) -> torch.Tensor:
    masked = logits.masked_fill(~legal, -torch.inf)
    return masked - torch.logsumexp(masked, dim=-1, keepdim=True)


@torch.no_grad()
def mixture_metrics(
    model: MechanicsSlotScorer,
    examples: SlotExamples,
    *,
    alpha: float,
) -> dict[str, float | int]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("blend alpha must be in [0, 1]")
    base = normalized_legal_logits(examples.base_logits, examples.legal)
    mechanics = normalized_legal_logits(
        model(examples.state, examples.cards), examples.legal
    )
    blended = ((1.0 - alpha) * base + alpha * mechanics).masked_fill(
        ~examples.legal, -torch.inf
    )
    predictions = blended.argmax(dim=-1)
    base_predictions = base.argmax(dim=-1)
    base_correct = base_predictions == examples.target
    blended_correct = predictions == examples.target
    return {
        "accuracy": float(blended_correct.float().mean()),
        "base_accuracy": float(base_correct.float().mean()),
        "disagreement_with_base": float(
            (predictions != base_predictions).float().mean()
        ),
        "improvements_vs_base": int((~base_correct & blended_correct).sum()),
        "regressions_vs_base": int((base_correct & ~blended_correct).sum()),
        "nll": float(torch.nn.functional.cross_entropy(blended, examples.target)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-checkpoint", action="append", required=True, type=Path)
    parser.add_argument("--validation-corpus", required=True, type=Path)
    parser.add_argument("--heldout-corpus", required=True, type=Path)
    parser.add_argument("--human-corpus", required=True, type=Path)
    parser.add_argument("--human-sidecar", required=True, type=Path)
    parser.add_argument("--simulator-checkpoint", required=True, type=Path)
    parser.add_argument("--public-checkpoint", required=True, type=Path)
    parser.add_argument("--decks-path", default="decks.json", type=Path)
    parser.add_argument("--alpha-step", type=float, default=0.025)
    parser.add_argument("--max-simulator-disagreement", type=float, default=0.01)
    parser.add_argument("--min-human-accuracy-gain", type=float, default=0.01)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _validate_probe_compatibility(
    probes: list[dict[str, Any]],
) -> tuple[int, int, tuple[str, ...]]:
    versions = {int(probe["semantics_version"]) for probe in probes}
    hidden_sizes = {int(probe["hidden_size"]) for probe in probes}
    token_sets = {tuple(probe["token_names"]) for probe in probes}
    if len(versions) != 1 or len(hidden_sizes) != 1 or len(token_sets) != 1:
        raise ValueError("probe checkpoints are not architecture/vocabulary compatible")
    return versions.pop(), hidden_sizes.pop(), token_sets.pop()


def main() -> None:
    args = parse_args()
    if not 0.0 < args.alpha_step <= 1.0:
        raise ValueError("alpha step must be in (0, 1]")
    if not 0.0 <= args.max_simulator_disagreement <= 1.0:
        raise ValueError("simulator disagreement limit must be in [0, 1]")
    if not 0.0 < args.min_human_accuracy_gain <= 1.0:
        raise ValueError("minimum human accuracy gain must be in (0, 1]")
    probe_paths = [resolve_path(path, must_exist=True) for path in args.probe_checkpoint]
    probes = [
        torch.load(path, map_location="cpu", weights_only=False) for path in probe_paths
    ]
    semantics_version, hidden_size, token_names = _validate_probe_compatibility(probes)
    decks_path = resolve_path(args.decks_path, must_exist=True)
    simulator_checkpoint = resolve_path(args.simulator_checkpoint, must_exist=True)
    public_checkpoint = resolve_path(args.public_checkpoint, must_exist=True)
    corpora = {
        "validation": resolve_path(args.validation_corpus, must_exist=True),
        "heldout": resolve_path(args.heldout_corpus, must_exist=True),
        "human": resolve_path(args.human_corpus, must_exist=True),
    }
    human_sidecar = resolve_path(args.human_sidecar, must_exist=True)
    examples: dict[str, SlotExamples] = {}
    examples["validation"], validation_tokens = extract_examples(
        corpus_path=corpora["validation"],
        checkpoint_path=simulator_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
    )
    examples["heldout"], heldout_tokens = extract_examples(
        corpus_path=corpora["heldout"],
        checkpoint_path=simulator_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
    )
    examples["human"], human_tokens = extract_examples(
        corpus_path=corpora["human"],
        checkpoint_path=public_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
        public_sidecar=human_sidecar,
    )
    if not (
        validation_tokens == heldout_tokens == human_tokens == token_names
    ):
        raise ValueError("probe and evaluation vocabularies differ")

    alpha_count = round(1.0 / args.alpha_step)
    alphas = sorted(
        {
            0.0,
            1.0,
            *(min(1.0, index * args.alpha_step) for index in range(alpha_count + 1)),
        }
    )
    per_probe: list[dict[str, Any]] = []
    for probe_path, probe in zip(probe_paths, probes, strict=True):
        model = MechanicsSlotScorer(
            state_size=examples["human"].state.shape[-1],
            card_size=examples["human"].cards.shape[-1],
            hidden_size=hidden_size,
        )
        model.load_state_dict(probe["state_dict"])
        model.eval()
        rows = []
        for alpha in alphas:
            rows.append(
                {
                    "alpha": alpha,
                    **{
                        split: mixture_metrics(model, current, alpha=alpha)
                        for split, current in examples.items()
                    },
                }
            )
        per_probe.append({"probe": str(probe_path), "rows": rows})

    aggregate_rows: list[dict[str, Any]] = []
    base_human_accuracy = per_probe[0]["rows"][0]["human"]["base_accuracy"]
    for index, alpha in enumerate(alphas):
        rows = [probe["rows"][index] for probe in per_probe]
        human_accuracies = [row["human"]["accuracy"] for row in rows]
        validation_disagreements = [
            row["validation"]["disagreement_with_base"] for row in rows
        ]
        heldout_disagreements = [
            row["heldout"]["disagreement_with_base"] for row in rows
        ]
        accepted = (
            min(human_accuracies)
            >= base_human_accuracy + args.min_human_accuracy_gain
            and max(validation_disagreements) <= args.max_simulator_disagreement
            and max(heldout_disagreements) <= args.max_simulator_disagreement
        )
        aggregate_rows.append(
            {
                "alpha": alpha,
                "human_accuracy_mean": float(np.mean(human_accuracies)),
                "human_accuracy_min": min(human_accuracies),
                "human_accuracy_max": max(human_accuracies),
                "validation_disagreement_max": max(validation_disagreements),
                "heldout_disagreement_max": max(heldout_disagreements),
                "accepted": accepted,
            }
        )
    accepted_rows = [row for row in aggregate_rows if row["accepted"]]
    selected = (
        max(
            accepted_rows,
            key=lambda row: (row["human_accuracy_mean"], -row["alpha"]),
        )
        if accepted_rows
        else None
    )
    payload = {
        "schema": "mechanics-slot-normalized-blend-sweep-v1",
        "probe_checkpoints": [str(path) for path in probe_paths],
        "semantics_version": semantics_version,
        "hidden_size": hidden_size,
        "alpha_step": args.alpha_step,
        "max_simulator_disagreement": args.max_simulator_disagreement,
        "min_human_accuracy_gain": args.min_human_accuracy_gain,
        "base_human_accuracy": base_human_accuracy,
        "selected": selected,
        "aggregate_rows": aggregate_rows,
        "per_probe": per_probe,
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    torch.set_grad_enabled(False)
    main()
