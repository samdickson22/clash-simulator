"""Replay a recorded development trajectory only to a paused profiling frame."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from smoke_reference_battle import request
from clasher.rl.action_space import DiscreteTileActionSpace

CAPTURE = ROOT / "artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0"
TRACE = ROOT / "reports/strategy_council_20260928/m0/readiness/paired-repetition-run-v6/job-00002/decisions.jsonl.gz"
OUT = Path(__file__).resolve().parent / "late-frame-3090"
TARGET = 3090


def main():
    OUT.mkdir(exist_ok=False)
    commands = []
    expected = None
    space = DiscreteTileActionSpace()
    with gzip.open(TRACE, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["tick"] == TARGET:
                expected = row["native_frame"]["ordinary"]
                break
            if row["tick"] > TARGET:
                raise ValueError("target frame missing")
            for owner, action in enumerate(row["actions"]):
                if action == space.no_op_action:
                    continue
                if action >= 2304:
                    raise ValueError("unsupported profiling replay action")
                play = space.decode_action(action, owner)
                player = next(p for p in row["native_frame"]["ordinary"]["players"] if p["owner"] == owner)
                card = next(c for c in player["hand"] if c["handIndex"] == play.slot)
                commands.append((row["tick"], owner, card["cardId"], round(play.position.x * 1000), round(play.position.y * 1000)))
    if expected is None:
        raise ValueError("target frame absent")
    prefix = json.loads((CAPTURE / "result.json").read_text())["commands"]
    if any(command["submitted_tick"] < 90 for command in prefix):
        raise ValueError("this profiling replay requires an empty pre-root prefix")
    attestation = request(26789, "attest")
    digest = hashlib.sha256(json.dumps(attestation, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != "864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93":
        raise ValueError("reference runtime differs")
    config = json.loads((CAPTURE / "plan.json").read_text())["config"]
    request(26789, "configure " + json.dumps(config, separators=(",", ":")))
    tick = 0
    for boundary, owner, card, x, y in commands:
        if boundary > tick:
            request(26789, f"step {boundary-tick}")
            tick = boundary
        request(26789, f"replay-schedule-card {owner} {card} {x} {y} {boundary+1}")
    request(26789, f"step {TARGET-tick}")
    observed = request(26789, "observe")
    keys = ("objects", "players", "tick", "ended", "winner")
    differences = [key for key in keys if observed[key] != expected[key]]
    (OUT / "ordinary.json").write_text(json.dumps(observed, indent=2) + "\n")
    (OUT / "receipt.json").write_text(json.dumps({
        "target_tick": TARGET, "commands": len(commands), "differences": differences,
        "trace_sha256": hashlib.sha256(TRACE.read_bytes()).hexdigest(),
        "attestation_sha256": digest, "scope": "opened development replay for read-only profiling",
    }, indent=2) + "\n")
    if differences:
        raise ValueError(f"profiling frame differs: {differences}")
    print(f"Restored exact gameplay fields at tick {TARGET}; {len(commands)} recorded commands")


if __name__ == "__main__":
    main()
