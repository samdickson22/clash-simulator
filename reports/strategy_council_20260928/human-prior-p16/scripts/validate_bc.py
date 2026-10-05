"""Per-head validation metrics of any pilot-architecture checkpoint on the held-out human matches.

  ... python validate_bc.py --checkpoint X.pt --name label [--perspectives N] [--threads 2]
Writes results/validation-<name>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hp_bootstrap as hb  # noqa: E402

RECON = hb.OUT / "data" / "recon"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--perspectives", type=int, default=None)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--split", type=int, default=1)
    args = parser.parse_args()
    torch.set_num_threads(min(4, args.threads))
    hb.bind_runtime()
    bc = hb.load_new_module("human_replay_bc")
    from clasher.rl.eval import load_policy_checkpoint

    loaded = load_policy_checkpoint(args.checkpoint, device=torch.device("cpu"), decks_path=hb.TRAINING_DECKS)
    done = sorted(RECON.glob("shard-*.done.json"))
    parts = sorted(RECON / part["path"] for path in done for part in json.loads(path.read_text())["parts"])
    slices = {
        "all": lambda s: s["fit_split"] == args.split,
        "winners": lambda s: s["fit_split"] == args.split and s["recorded_result"] == 1,
        "losers": lambda s: s["fit_split"] == args.split and s["recorded_result"] == -1,
    }
    result = {"checkpoint": str(args.checkpoint), "checkpoint_sha256": bc.file_sha256(args.checkpoint),
              "split": args.split, "maximum_perspectives": args.perspectives}
    for name, keep in slices.items():
        result[name] = bc.evaluate_human_replay(loaded.model, parts, keep=keep, device=torch.device("cpu"),
                                                maximum_perspectives=args.perspectives)
        print(json.dumps({name: result[name]}), flush=True)
        if args.perspectives is not None:
            break
    (hb.OUT / "results").mkdir(exist_ok=True)
    (hb.OUT / "results" / f"validation-{args.name}.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
