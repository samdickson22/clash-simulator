"""Capture a paused native window after replaying recorded command gaps."""

import argparse
import hashlib
import json
from pathlib import Path

from smoke_reference_battle import request

from clasher.data import CardDataLoader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rich-card-id", type=int)
    args = parser.parse_args()
    if not 0 <= args.start <= args.end:
        parser.error("require 0 <= start <= end")
    plan_bytes = (args.capture / "plan.json").read_bytes()
    result_bytes = (args.capture / "result.json").read_bytes()
    plan = json.loads(plan_bytes)
    recorded = json.loads(result_bytes)
    checkpoints = {frame["tick"]: frame["native"] for frame in recorded["checkpoints"]}
    if args.start not in checkpoints:
        parser.error("start must be a recorded native checkpoint for verification")
    args.output.mkdir(parents=True, exist_ok=False)
    loader = CardDataLoader()
    commands = {}
    for command in recorded["commands"]:
        assert command["execution_tick"] == command["submitted_tick"] + 1
        commands.setdefault(command["submitted_tick"], []).append(command)
    assert request(
        26789, "configure " + json.dumps(plan["config"], separators=(",", ":"))
    )["ok"]
    status = request(26789, "status")
    assert status["paused"] and status["mode"] == "headless" and status["tick"] == 0
    receipts = []
    frames = []
    verified = []
    card_ids = {}

    def submit(tick):
        for command in commands.get(tick, []):
            card = loader.get_card(command["name"])._raw_entry["id"]
            card_ids[command["name"]] = card
            x, y = (round(value * 1000) for value in command["xy"])
            receipt = request(
                26789,
                f"replay-schedule-card {command['owner']} {card} {x} {y} {tick + 1}",
            )
            assert receipt["ok"]
            receipts.append(
                {"submitted_tick": tick, "command": command, "receipt": receipt}
            )

    def observe(tick):
        ordinary = request(26789, "observe")
        assert ordinary["tick"] == tick and not ordinary["truncated"]
        if tick in checkpoints:
            for key in ("objects", "players", "tick", "ended", "winner", "worldResult"):
                assert ordinary[key] == checkpoints[tick][key], (tick, key)
            verified.append(tick)
        selected = None
        if args.rich_card_id is not None:
            rich = request(26789, "observe-rich")
            assert rich["tick"] == tick and not rich["truncated"]
            selected = [
                entity
                for entity in rich["objects"]
                if entity["cardId"] == args.rich_card_id
            ]
        frames.append(
            {"tick": tick, "ordinary": ordinary, "selected_rich_objects": selected}
        )

    tick = 0
    try:
        for submitted in sorted(commands):
            if submitted >= args.start:
                break
            if submitted > tick:
                assert request(26789, f"step {submitted - tick}")["tick"] == submitted
            tick = submitted
            submit(tick)
        if args.start > tick:
            assert request(26789, f"step {args.start - tick}")["tick"] == args.start
        tick = args.start
        observe(tick)
        while tick < args.end:
            submit(tick)
            assert request(26789, "step 1")["tick"] == tick + 1
            tick += 1
            observe(tick)
    finally:
        (args.output / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")
        manifest = {
            "requested_start": args.start,
            "requested_end": args.end,
            "actual_tick": tick,
            "complete": bool(frames and frames[-1]["tick"] == args.end),
            "verified_checkpoint_ticks": verified,
            "card_ids": card_ids,
            "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "rich_card_id": args.rich_card_id,
            "observation_mode": "Paused sequential ordinary and optional selected rich objects; no event rings or atomic claim.",
            "receipts": receipts,
        }
        (args.output / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
    print(f"Captured {len(frames)} frames; verified checkpoints {verified}")


if __name__ == "__main__":
    main()
