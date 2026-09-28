"""Training-family-only diagnostic of independently reconstructed scalar openings."""

import argparse
import hashlib
import json
import pickle
import platform
import random
import subprocess
from pathlib import Path

import numpy as np
import torch

from clasher.card_aliases import resolve_card_name
from clasher.rl.simple_pytorch_backend import (
    SimpleTensorStrategyOpponent,
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import CanonicalOpeningSchedule
from scripts.probe_hog26_scalar_complete_replay_20260909 import DECK, run


def source_hashes(root):
    paths = [p for p in subprocess.check_output(
        ["rg", "--files", "src/clasher", "scripts"], cwd=root, text=True,
    ).splitlines() if p.endswith(".py")]
    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(paths)}


def global_rng_digest():
    values = (random.getstate(), np.random.get_state(), torch.get_rng_state().numpy())
    return hashlib.sha256(pickle.dumps(values, protocol=5)).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    root = Path(__file__).resolve().parents[1]
    sources = source_hashes(root)
    manifest_path = root / "training_decks/hog26_procedural_supported_seed1278401.json"
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    manifest = json.loads(manifest_path.read_text())
    decks = [d for d in manifest["decks"] if d["split"] == "train"]
    if len(decks) != 32:
        raise ValueError("training deck authority changed")
    torch.set_num_threads(1)
    model, builder = load_model(checkpoint, torch.device("cpu"))
    definitions = builder.loader.load_card_definitions()
    canonical = lambda names: [resolve_card_name(name, definitions) for name in names]
    inventory = sorted({c for row in decks for c in canonical(row["cards"])} | set(canonical(DECK)))
    vocabulary = load_current_client_typed_vocabulary()
    setup = compile_standard_simple_setup(builder.loader, inventory, device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    resource_paths = {"manifest": manifest_path, "checkpoint": checkpoint,
                      "card_data": Path(builder.loader.data_file)}
    resources = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in resource_paths.items()}
    report = {"scope": "Diagnostic training deck13 only, balanced/random styles, one seeded deal per "
              "style, paired seats and exact repeats. Not collection authority or independent repeat samples.",
              "source_sha256": sources, "resource_sha256": resources,
              "vocabulary_sha256": vocabulary.sha256,
              "runtime": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__},
              "schedules": [], "runs": []}
    for style in ("balanced", "random"):
        # The pin is constructed from the declared diagnostic config and manifest,
        # not copied from the producer's self-reported metadata.
        pin = {"version": "clasher.scalar-canonical-opening.v1", "campaign_seed": "1279211",
               "role": "diagnostic-opening-audit", "deck_name": decks[13]["name"],
               "opponent_style": style, "relative_templates": [canonical(DECK), canonical(decks[13]["cards"])],
               "episodes": 1, "canonical_names": inventory}
        schedule = CanonicalOpeningSchedule(
            campaign_seed=1279211, role=pin["role"], deck_name=pin["deck_name"], opponent_style=style,
            learner_template=pin["relative_templates"][0], opponent_template=pin["relative_templates"][1],
            canonical_names=inventory, episodes=1,
        ).metadata()
        audited, = audit_scalar_opening_metadata(schedule, expected_authority=pin)
        report["schedules"].append({"external_authority": pin, "metadata": schedule})
        streams = dict(audited.stream_seeds)
        for seat in (0, 1):
            pair = []
            for _ in range(2):
                opponent = None if style == "random" else SimpleTensorStrategyOpponent(
                    builder, strategy_name=style, device=torch.device("cpu"),
                )
                before = global_rng_digest()
                result = run(model, builder, vocabulary, provider, opponent, seat=seat,
                             seed=streams["battle"], expanded_receipts=True, opening_scenario=audited,
                             random_opponent_seed=streams["opponent"] if style == "random" else None)
                if global_rng_digest() != before:
                    raise AssertionError("scalar diagnostic consumed process-global RNG")
                expected_decks = [list(deck) for deck in audited.world_decks(seat)]
                expected_hands = [[vocabulary.resolve(card, "card_action") for card in deck[:5]]
                                  for deck in expected_decks]
                if result["initial_ordered_decks"] != expected_decks or result["initial_public_hand_ids"] != expected_hands:
                    raise AssertionError("actual initial scalar deal/public hand differs from independent reconstruction")
                pair.append(result)
            if ({k: v for k, v in pair[0].items() if k != "elapsed_seconds"}
                    != {k: v for k, v in pair[1].items() if k != "elapsed_seconds"}):
                raise AssertionError("seeded scalar exact repeat diverged")
            report["runs"].append({"style": style, "learner_seat": seat, "executions": pair})
    report["source_unchanged"] = source_hashes(root) == sources
    report["resources_unchanged"] = all(
        hashlib.sha256(path.read_bytes()).hexdigest() == resources[key] for key, path in resource_paths.items()
    ) and load_current_client_typed_vocabulary().sha256 == vocabulary.sha256
    if not report["source_unchanged"] or not report["resources_unchanged"]:
        raise RuntimeError("diagnostic source or resource authority changed")
    report["status"] = "diagnostic_seeded_replay_verified"
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "scenarios": 4, "executions": 8}), flush=True)


if __name__ == "__main__":
    main()
