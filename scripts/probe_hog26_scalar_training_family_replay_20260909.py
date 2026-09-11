"""Diagnostic scalar replay of training decks; no outcome corpus or gate scoring."""

import argparse
import hashlib
import json
import subprocess
import traceback
from pathlib import Path

import torch

from clasher.rl.simple_pytorch_backend import (
    SimpleTensorStrategyOpponent,
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.probe_hog26_scalar_complete_replay_20260909 import DECK, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deck-index", type=int, action="append")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "training_decks/hog26_procedural_supported_seed1278401.json"
    manifest = json.loads(manifest_path.read_text())
    decks = [row for row in manifest["decks"] if row["split"] == "train"]
    if len(decks) != 32:
        raise ValueError("declared training deck inventory changed")
    indices = list(range(32)) if args.deck_index is None else sorted(set(args.deck_index))
    if not indices or any(index not in range(32) for index in indices):
        raise ValueError("diagnostic indices must select declared training decks")
    paths = [p for p in subprocess.check_output(
        ["rg", "--files", "src/clasher", "scripts"], cwd=root, text=True,
    ).splitlines() if p.endswith(".py")]
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(paths)}
    torch.set_num_threads(1)
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    model, builder = load_model(checkpoint, torch.device("cpu"))
    vocabulary = load_current_client_typed_vocabulary()
    public_cards = sorted(set(DECK) | {card for row in decks for card in row["cards"]})
    setup = compile_standard_simple_setup(
        builder.loader, public_cards, device="cpu", canonical_lane_globals=True,
    )
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    report = {
        "status": "diagnostic_only", "scope": "All selected training decks, both learner seats, "
        "balanced public strategy, two exact executions per scenario. Failures retained. "
        "No training corpus, fitting, calibration, ranking or final evaluation.",
        "training_deck_indices": indices, "source_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "vocabulary_sha256": vocabulary.sha256,
        "card_data_sha256": hashlib.sha256(Path(builder.loader.data_file).read_bytes()).hexdigest(),
        "base_mask_semantics_digest": provider.tables.semantics_digest, "scenarios": [],
    }
    for index in indices:
        for seat in (0, 1):
            row = {"training_deck_index": index, "deck": decks[index], "seat": seat,
                   "seed": 1279061 + index}
            pair = []
            try:
                for _ in range(2):
                    opponent = SimpleTensorStrategyOpponent(
                        builder, strategy_name="balanced", device=torch.device("cpu"),
                    )
                    pair.append(run(
                        model, builder, vocabulary, provider, opponent,
                        seat=seat, seed=row["seed"], opponent_deck=decks[index]["cards"],
                        expanded_receipts=True,
                    ))
                comparable = [{k: v for k, v in item.items() if k != "elapsed_seconds"}
                              for item in pair]
                if comparable[0] != comparable[1]:
                    raise AssertionError("complete repeated scalar trajectory diverged")
                row["status"] = "complete_exact_repeat"
            except Exception as exc:  # noqa: BLE001 - retain failed scenarios, never certify them
                row.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                           traceback=traceback.format_exc())
            row["runs"] = pair
            report["scenarios"].append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in {"runs", "traceback"}}), flush=True)
    final_paths = {p for p in subprocess.check_output(
        ["rg", "--files", "src/clasher", "scripts"], cwd=root, text=True,
    ).splitlines() if p.endswith(".py")}
    report["source_unchanged"] = final_paths == set(hashes) and all(
        hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in hashes.items()
    )
    report["resources_unchanged"] = all((
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() == report["manifest_sha256"],
        hashlib.sha256(checkpoint.read_bytes()).hexdigest() == report["checkpoint_sha256"],
        hashlib.sha256(Path(builder.loader.data_file).read_bytes()).hexdigest() == report["card_data_sha256"],
        load_current_client_typed_vocabulary().sha256 == report["vocabulary_sha256"],
    ))
    report["status"] = ("diagnostic_pass" if report["source_unchanged"] and report["resources_unchanged"] and all(
        row["status"] == "complete_exact_repeat" for row in report["scenarios"])
        else "diagnostic_failed")
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "scenarios": len(report["scenarios"])}), flush=True)


if __name__ == "__main__":
    main()
