"""Diagnose snapshot restore fidelity after advancing N ticks past the root.

Opened-development root only; no ledger. Replays the recorded prefix exactly as
run_readiness_v2 does, creates a snapshot at the root, then for each N steps N
ticks, restores, and diffs the observed frame against the root frame.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from compare_equivalence import diff_paths, generalize, strip  # noqa: E402

from clasher.data import CardDataLoader  # noqa: E402
from clasher.rl.native_probe_transport import PersistentProbeSession  # noqa: E402

IGNORE = {"generation", "stateEpoch", "snapshotHandles"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--advance", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pre-ticks", type=int, default=0,
                        help="snapshot this many ticks before the root, then replay them after each restore")
    args = parser.parse_args()
    result = json.loads((args.capture / "result.json").read_text())
    config = json.loads((args.capture / "plan.json").read_text())["config"]
    root_tick = result["selection"]["root_tick"]
    loader = CardDataLoader(args.capture / "gamedata.json")
    prefix = [c for c in result["commands"] if c["submitted_tick"] < root_tick]
    report = {"capture": str(args.capture), "root_tick": root_tick, "trials": []}
    with PersistentProbeSession(args.port) as call:
        call("configure " + json.dumps(config, separators=(",", ":")))

        def advance(target):
            tick = call("observe")["tick"]
            if target > tick:
                call(f"step {target - tick}")

        snapshot_tick = root_tick - args.pre_ticks

        def submit(command):
            card = loader.get_card(command["name"])._raw_entry["id"]
            x, y = (round(v * 1000) for v in command["xy"])
            call(f"replay-schedule-card {command['owner']} {card} {x} {y} {command['submitted_tick'] + 1}")

        early = [c for c in prefix if c["submitted_tick"] < snapshot_tick]
        window = [c for c in prefix if c["submitted_tick"] >= snapshot_tick]
        for command in early:
            advance(command["submitted_tick"])
            submit(command)
        advance(snapshot_tick)
        snapshot = call("snapshot-create")
        report["snapshot"] = snapshot
        report["window_commands"] = len(window)

        def replay_window():
            for command in window:
                advance(command["submitted_tick"])
                submit(command)
            advance(root_tick)

        replay_window()
        root = call("observe")
        root_rich = call("observe-rich")
        try:
            for count in args.advance:
                if count:
                    stepped = call(f"step {count}")
                else:
                    stepped = None
                moved = call("observe")
                restored = call(f"restore {snapshot['handle']}")
                call("replay-schedule-clear")
                replay_window()
                back = call("observe")
                back_rich = call("observe-rich")
                ordinary = diff_paths(strip(root, IGNORE), strip(back, IGNORE), limit=100000)
                rich_objects = diff_paths(root_rich["objects"], back_rich["objects"], limit=100000)
                report["trials"].append({
                    "advance": count,
                    "step": stepped,
                    "moved_tick": moved["tick"],
                    "moved_objects": moved["count"],
                    "restore": restored,
                    "restored_tick": back["tick"],
                    "restored_objects": back["count"],
                    "root_objects": root["count"],
                    "ordinary_identical": not ordinary,
                    "ordinary_differences": generalize(ordinary),
                    "ordinary_difference_examples": ordinary[:12],
                    "rich_object_differences": generalize(rich_objects),
                })
                print(json.dumps({k: report["trials"][-1][k] for k in (
                    "advance", "moved_tick", "restored_tick", "restored_objects",
                    "root_objects", "ordinary_identical")}), flush=True)
        finally:
            report["release"] = call(f"release-snapshot {snapshot['handle']}")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
