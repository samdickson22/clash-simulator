#!/usr/bin/env python3
"""Collect admitted full-game public-script examples and fit a fresh council actor."""
import argparse
import json
import os
import sys
import tomllib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decisions", type=int)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--device", choices=("cpu", "mps"))
    args = parser.parse_args()
    raw = tomllib.loads(args.config.read_text())
    expected_root = str(Path(raw["gamedata_path"]).parent)
    expected_pythonpath = str(Path(raw["source_root"]) / "src")
    if os.environ.get("CLASHER_ROOT") != expected_root or os.environ.get("PYTHONPATH") != expected_pythonpath:
        environment = os.environ.copy()
        environment.update(CLASHER_ROOT=expected_root, PYTHONPATH=expected_pythonpath, PYTHONDONTWRITEBYTECODE="1")
        os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], environment)
    from clasher.rl.council_warmstart import run_script_warmstart
    result = run_script_warmstart(config_path=args.config, admission_path=args.admission,
        seed=args.seed, output_checkpoint=args.output, decisions=args.decisions,
        epochs=args.epochs, batch_size=args.batch_size, device=args.device, resume=args.resume)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
