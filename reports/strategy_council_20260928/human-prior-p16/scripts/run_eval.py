"""Pilot diagnostic cells for one checkpoint, on seeds the pilot never used.

Mirrors council_pilot.evaluation_commands(final=False): clasher.rl.eval, opponent
public-script in {balanced, pressure, defense}, level-mode nominal, 32 games,
stochastic, decision interval 5, max ticks 6001; candidate decks = development
holdout decks and the hog26 deployment deck; opponent decks = training decks.
Seeds: EVALUATION_SEED + 1_000_003 * (role * 6 + style + 12) with
EVALUATION_SEED = 770031 (the pilot uses 9413 for its diagnostic and final cells).
Runs from the frozen runtime with its own interpreter. Finished cells are skipped.

  python run_eval.py --checkpoint X.pt --name label [--parallel 4] [--trace-games 8]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
COUNCIL = HERE.parents[1]
RUNTIME = COUNCIL / "m0/runtime-snapshots/pilot-runtime-v4"
TRAINING = COUNCIL / "m0/data/roles_v2/training.json"
ROLES = (("holdout", COUNCIL / "m0/data/roles_v2/development.json"), ("hog26", COUNCIL / "pilot/hog26-deployment.json"))
STYLES = ("balanced", "pressure", "defense")
EVALUATION_SEED = 770031


def commands(checkpoint: Path, output: Path, games: int, trace_games: int, seed: int):
    for role_index, (role, decks) in enumerate(ROLES):
        for style_index, style in enumerate(STYLES):
            prefix = output / f"{role}-nominal-{style}"
            args = [
                str(RUNTIME / ".venv/bin/python"), "-B", "-m", "clasher.rl.eval",
                "--checkpoint", str(checkpoint), "--decks-path", str(TRAINING),
                "--candidate-sampling-decks-path", str(decks), "--opponent-sampling-decks-path", str(TRAINING),
                "--opponent", "public-script", "--public-script-style", style, "--level-mode", "nominal",
                "--games", str(games), "--seed", str(seed + 1_000_003 * (role_index * 6 + style_index + 12)),
                "--decision-interval", "5", "--max-ticks", "6001", "--device", "cpu", "--torch-threads", "1",
                "--stochastic", "--json-out", str(prefix) + ".json", "--games-json-out", str(prefix) + ".games.json",
            ]
            if trace_games:
                args += ["--decisions-json-out", str(prefix) + ".decisions.json"]
                for game in range(min(trace_games, games)):
                    args += ["--decision-trace-game", str(game)]
            yield prefix, args


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--games", type=int, default=32)
    parser.add_argument("--trace-games", type=int, default=8)
    parser.add_argument("--seed", type=int, default=EVALUATION_SEED)
    args = parser.parse_args()
    if not 1 <= args.parallel <= 4:
        raise SystemExit("use at most four evaluation processes")
    output = OUT / "evaluation" / args.name
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(CLASHER_ROOT=str(RUNTIME), PYTHONPATH=f"{RUNTIME}/src:{RUNTIME}/scripts",
                       PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    pending = [(prefix, command) for prefix, command in commands(args.checkpoint.resolve(), output, args.games, args.trace_games, args.seed)
               if not Path(str(prefix) + ".json").exists()]
    running: list[tuple[Path, subprocess.Popen]] = []
    failed = []
    while pending or running:
        while pending and len(running) < args.parallel:
            prefix, command = pending.pop(0)
            log = open(str(prefix) + ".log", "w")
            running.append((prefix, subprocess.Popen(["nice", "-n", "10", *command], cwd=RUNTIME, env=environment,
                                                     stdout=log, stderr=subprocess.STDOUT)))
        prefix, process = running.pop(0)
        if process.wait() != 0:
            failed.append(str(prefix))
        print(json.dumps({"cell": prefix.name, "returncode": process.returncode}), flush=True)
    if failed:
        raise SystemExit(f"failed cells: {failed}")


if __name__ == "__main__":
    main()
