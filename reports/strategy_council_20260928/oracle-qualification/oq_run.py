"""Resumable worker: plays evaluation games listed by a batch name from batches.json.

Usage (inside the frozen runtime env, see PROGRESS.md):
    python -B oq_run.py <batch> [<batch> ...]

Each game is claimed with an O_EXCL lock file (games/<player>/<id>.claim, holds the
PID) and written atomically to games/<player>/<id>.json. Finished games are skipped;
claims of dead PIDs are taken over. Start up to 5 of these processes for 5 workers.
A file named STOP in this directory makes workers exit after their current game.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import oq_lib

GAMES = oq_lib.OQ_DIR / "games"


def load_specs(batch_names: list[str]) -> list[dict]:
    """Batches run in the given order. An argument "+a,b,c" interleaves batches
    a, b, c round-robin by game index (stable), so every cell advances together."""
    specs: list[dict] = []
    for name in batch_names:
        if name.startswith("+"):
            merged: list[tuple[int, int, int, dict]] = []
            for order, sub in enumerate(name[1:].split(",")):
                for index, spec in enumerate(_load_batches([sub])):
                    merged.append((spec["game"], order, index, spec))
            merged.sort(key=lambda item: item[:3])
            specs += [item[3] for item in merged]
        else:
            specs += _load_batches([name])
    return specs


def _load_batches(batch_names: list[str]) -> list[dict]:
    cfg = json.loads((oq_lib.OQ_DIR / "batches.json").read_text())
    players = cfg["players"]
    specs = []
    for name in batch_names:
        batch = cfg["batches"][name]
        lo, hi = batch["games"]
        block = []
        for game in range(lo, hi):
            for cell in batch["cells"]:
                role, opponent = cell.split(":")
                seed = batch.get("seeds", {}).get(cell) or oq_lib.PILOT_CELL_SEEDS[
                    (role, opponent if opponent != "policy" else "balanced")
                ] + int(batch.get("seed_offset", 0))
                for player in batch["players"]:
                    block.append(
                        {
                            "role": role,
                            "opponent": opponent,
                            "seed": seed,
                            "game": game,
                            "player": {"name": player, **players[player]},
                        }
                    )
        specs += block
    return specs


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def try_claim(claim: Path) -> bool:
    claim.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = int(claim.read_text().strip() or "0")
            except (ValueError, FileNotFoundError):
                owner = 0
            if owner and pid_alive(owner):
                return False
            try:
                claim.unlink()
            except FileNotFoundError:
                pass
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    return False


def main() -> None:
    specs = load_specs(sys.argv[1:])
    ctx = oq_lib.Context()
    print(f"worker pid={os.getpid()} specs={len(specs)}", flush=True)
    for spec in specs:
        if (oq_lib.OQ_DIR / "STOP").exists():
            print("STOP file present; exiting", flush=True)
            return
        gid = oq_lib.game_id(spec)
        out = GAMES / spec["player"]["name"] / f"{gid}.json"
        claim = out.with_suffix(".claim")
        if out.exists() or not try_claim(claim):
            continue
        if out.exists():
            claim.unlink(missing_ok=True)
            continue
        try:
            t0 = time.time()
            result = oq_lib.play_game(ctx, spec)
            oq_lib.write_json_atomic(out, result)
            print(
                f"{time.strftime('%H:%M:%S')} {gid} {result['outcome']} "
                f"crowns={result['candidate_crowns']}-{result['opponent_crowns']} "
                f"ticks={result['ticks']} calls={result['planner_calls']} "
                f"plan_s={result['planner_seconds']:.0f} wall={time.time() - t0:.0f}s",
                flush=True,
            )
        except Exception:  # keep the worker alive; the failure is recorded
            print(f"FAILED {gid}\n{traceback.format_exc()}", flush=True)
            oq_lib.write_json_atomic(
                out.with_suffix(".error.json"),
                {"spec": spec, "error": traceback.format_exc()},
            )
        finally:
            claim.unlink(missing_ok=True)
    print("worker done", flush=True)


if __name__ == "__main__":
    main()
