from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import gc
import json
import statistics
import time
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.imitation import _sequence_batch_inputs, load_corpus
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import resolve_torch_device

VARIANTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("attention_lstm_hybrid", {}),
    ("deepsets_lstm_hybrid", {"encoder_kind": "deepsets"}),
    (
        "noattention_lstm_hybrid",
        {"encoder_kind": "deepsets", "decoder_kind": "global"},
    ),
    (
        "noattention_gru_hybrid",
        {
            "encoder_kind": "deepsets",
            "decoder_kind": "global",
            "memory_kind": "gru",
        },
    ),
    (
        "noattention_feedforward_hybrid",
        {
            "encoder_kind": "deepsets",
            "decoder_kind": "global",
            "memory_kind": "feedforward",
        },
    ),
    (
        "attention_global_lstm_hybrid",
        {"decoder_kind": "global"},
    ),
    (
        "noattention_lstm_hybrid_wide272",
        {
            "encoder_kind": "deepsets",
            "decoder_kind": "global",
            "d_model": 272,
            "num_heads": 8,
            "memory_size": 544,
        },
    ),
    (
        "attention_lstm_residual_hybrid",
        {"card_input_mode": "residual-hybrid"},
    ),
    ("attention_lstm_idonly", {"card_input_mode": "id-only"}),
    (
        "noattention_lstm_idonly",
        {
            "encoder_kind": "deepsets",
            "decoder_kind": "global",
            "card_input_mode": "id-only",
        },
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark matched Clasher architecture training steps"
    )
    parser.add_argument("--corpus", default="datasets/human_safety_balanced_v1.npz")
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--seed", type=int, default=1041001)
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--batch-sequences", type=int, default=8)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def _fixed_sequence_chunks(
    episode_ids: np.ndarray,
    *,
    sequence_length: int,
    count: int,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids):
        indices = np.flatnonzero(episode_ids == episode_id)
        for start in range(0, len(indices) - sequence_length + 1, sequence_length):
            chunks.append(indices[start : start + sequence_length])
            if len(chunks) == count:
                return np.stack(chunks)
    raise ValueError(
        f"corpus has fewer than {count} complete {sequence_length}-row chunks"
    )


def _synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize(device)


def main() -> None:
    args = parse_args()
    if min(args.sequence_length, args.batch_sequences, args.repetitions) <= 0:
        raise ValueError(
            "sequence length, batch sequences, and repetitions must be positive"
        )
    if args.warmups < 0:
        raise ValueError("warmups must be non-negative")
    device = resolve_torch_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    metadata, arrays = load_corpus(corpus_path)
    chunks = _fixed_sequence_chunks(
        arrays["episode_ids"],
        sequence_length=args.sequence_length,
        count=args.batch_sequences,
    )
    inputs = _sequence_batch_inputs(arrays, chunks, device)
    targets = torch.as_tensor(
        arrays["expert_actions"][chunks], dtype=torch.long, device=device
    )
    builder = StructuredObservationBuilder(
        decks_path=resolve_decks_path(args.decks_path, must_exist=True),
        max_entities=metadata.max_entities,
        token_names=metadata.token_names,
        card_semantics_version=1,
    )

    results: list[dict[str, Any]] = []
    for name, overrides in VARIANTS:
        torch.manual_seed(args.seed)
        config_values: dict[str, Any] = {
            "num_tokens": builder.spec.num_tokens,
            "max_entities": builder.max_entities,
            "card_semantics_version": 1,
            "d_model": 192,
            "num_heads": 6,
            "actor_layers": 5,
            "critic_layers": 3,
            "memory_size": 384,
        }
        config_values.update(overrides)
        config = PolicyConfig(
            **config_values,
        )
        model = ClasherPolicy(config, builder.card_stat_features).to(device).train()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        timings: list[float] = []
        for step in range(args.warmups + args.repetitions):
            started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            output = model(inputs)
            loss = torch.nn.functional.cross_entropy(
                output.joint_logits.reshape(-1, output.joint_logits.shape[-1]),
                targets.reshape(-1),
            )
            loss.backward()
            optimizer.step()
            _synchronize(device)
            elapsed = time.perf_counter() - started
            if step >= args.warmups:
                timings.append(elapsed)
        results.append(
            {
                "variant": name,
                "model_config": config.to_dict(),
                "parameters": sum(
                    parameter.numel() for parameter in model.parameters()
                ),
                "median_train_step_seconds": statistics.median(timings),
                "raw_train_step_seconds": timings,
            }
        )
        del model, optimizer, output, loss
        gc.collect()
        if device.type == "mps":
            torch.mps.empty_cache()
        elif device.type == "cuda":
            torch.cuda.empty_cache()

    baseline = float(results[0]["median_train_step_seconds"])
    for result in results:
        elapsed = float(result["median_train_step_seconds"])
        result["speedup_vs_attention_lstm"] = baseline / elapsed
        result["time_reduction_vs_attention_lstm"] = 1.0 - elapsed / baseline
    payload = {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "device": str(device),
        "seed": args.seed,
        "sequence_length": args.sequence_length,
        "batch_sequences": args.batch_sequences,
        "warmups": args.warmups,
        "repetitions": args.repetitions,
        "results": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
