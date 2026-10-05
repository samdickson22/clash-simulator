"""Fit one human-replay BC variant with the pilot architecture (resumable).

Variants
  natural  : every supervised row weight 1 (the scripted warm start's handling)
  wait02   : waits more than 4 decision steps before a play weigh 0.2
  winners  : fine-tune --initial on winners' perspectives only (filtered BC)

Run (frozen runtime environment, see reconstruct.py):
  ... nice -n 10 python fit_bc.py --variant natural --threads 2
Rerun the same command to resume after an interruption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hp_bootstrap as hb  # noqa: E402

RECON = hb.OUT / "data" / "recon"
CHECKPOINTS = hb.OUT / "checkpoints"
PILOT_INIT = hb.COUNCIL / "pilot/v7r2-launch/runs/s2903/seed-2903/initialization"


def manifest_digest(parts: list[Path]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.name.encode())
        digest.update(str(part.stat().st_size).encode())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True, choices=["natural", "wait02", "winners"])
    parser.add_argument("--seed", type=int, default=2903)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-pools", type=int, default=None)
    parser.add_argument("--initial", type=Path, default=None)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    if not 1 <= args.threads <= 4:
        raise SystemExit("use at most four torch threads")
    torch.set_num_threads(args.threads)
    hb.bind_runtime()
    bc = hb.load_new_module("human_replay_bc")
    hb.load_new_module("human_replay_demonstrations")
    from clasher.rl.council_pilot import build_council_model_config
    from clasher.rl.model import ClasherPolicy

    builder = hb.pilot_builder()
    model_config = build_council_model_config(builder)
    done = sorted(RECON.glob("shard-*.done.json"))
    parts = sorted(RECON / part["path"] for path in done for part in json.loads(path.read_text())["parts"])
    if args.variant == "winners" and args.initial is None:
        raise SystemExit("the winners variant fine-tunes an --initial checkpoint")
    config = bc.HumanReplayFitConfig(
        seed=args.seed, variant=args.variant, epochs=args.epochs, max_pools=args.max_pools,
        wait_row_weight=0.2 if args.variant == "wait02" else 1.0, winners_only=args.variant == "winners")
    name = args.name or f"human-bc-{args.variant}-seed{args.seed}"
    output = CHECKPOINTS / f"{name}.pt"
    CHECKPOINTS.mkdir(exist_ok=True)
    log_path = hb.OUT / "logs" / f"fit-{name}.jsonl"

    def log(record: dict) -> None:
        with log_path.open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        print(json.dumps(record, sort_keys=True), flush=True)

    # The same seed gives the pilot scripted arm's untrained weights (matched control).
    if args.initial is None and args.seed == 2903 and (PILOT_INIT / "scripted-random-control.pt").exists():
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)
        fresh = ClasherPolicy(model_config, builder.card_stat_features).state_dict()
        control = torch.load(PILOT_INIT / "scripted-random-control.pt", map_location="cpu", weights_only=False)
        same = all(torch.equal(fresh[key], control["model_state_dict"][key]) for key in fresh)
        log({"event": "initialization", "equals_pilot_scripted_random_control": bool(same),
             "token_names_equal": tuple(control["token_names"]) == tuple(builder.token_names)})
    metadata = {
        "gamedata_sha256": bc.file_sha256(hb.RUNTIME / "gamedata.json"),
        "training_decks_sha256": bc.file_sha256(hb.TRAINING_DECKS),
        "human_replay_recon_manifest_sha256": manifest_digest(parts),
        "human_replay_runtime": str(hb.RUNTIME),
    }
    log({"event": "start", "variant": args.variant, "parts": len(parts), "threads": args.threads,
         "output": str(output), "config": config.__dict__})
    result = bc.fit_human_replay(
        parts=parts, output_checkpoint=output, model_config=model_config,
        card_stat_features=builder.card_stat_features, config=config, device=torch.device("cpu"),
        initial_checkpoint=args.initial, checkpoint_metadata=metadata, log=log)
    (hb.OUT / "results").mkdir(exist_ok=True)
    (hb.OUT / "results" / f"fit-{name}.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    log({"event": "done", "checkpoint": result["checkpoint"], "sha256": result["checkpoint_sha256"]})


if __name__ == "__main__":
    main()
