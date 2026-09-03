from __future__ import annotations

from pathlib import Path

from scripts.run_hog26_procedural_outcome_shard import (
    collection_args,
    load_protocol,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports" / "hog26_procedural_outcome_protocol_seed1278401.json"


def test_frozen_training_shard_builds_exact_collector_arguments() -> None:
    protocol = load_protocol(PROTOCOL, ROOT)
    row = protocol["training"][1]
    args = collection_args(protocol, row, root=ROOT, device="cuda")
    assert args.seed == 1278502
    assert args.device == "cuda"
    assert args.opponents == "bridge-pressure,reactive-defense"
    assert args.opponent_deck_split == "train"
    assert args.opponent_family_id == tuple(row["family_ids"])
    assert args.episodes_per_seat == 1
    assert args.chunk_steps == 64
    assert args.output == ROOT / row["output_corpus"]
    assert args.report == ROOT / row["output_report"]
