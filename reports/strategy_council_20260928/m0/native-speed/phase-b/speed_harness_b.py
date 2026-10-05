"""Phase B native speed and equivalence harness (opened development roots only).

Wraps ``../speed_harness.py`` without modifying it: the same ``prepare``, job
loop and profile, plus
  * the Phase B read flags (``--native-level-reader``, ``--native-rich-transfer``,
    ``--native-probe-build``, ``--native-probe-process-identity``);
  * a keyword-aware compaction timer and ADB labels for helper walks;
  * per-job host process CPU time (``host-cpu.json``), since 8-10 emulators
    make the host CPU-bound;
  * optional dual reads at every decision, on the same paused frame:
      --dual-read-levels  the branch uses the session's reader; every other
                          reader in --dual-readers must return the identical
                          level map for the identical ordinary frame;
      --dual-read-rich    with --native-rich-transfer delta, a full cumulative
                          observe-rich is also fetched; the reconstructed rich
                          object must serialize to identical bytes.
    Any mismatch is written to dual-read.jsonl and raises (fail closed).

Never run this against an instance that belongs to a live attempt. It takes an
exclusive lock and requires --i-own-this-instance.

Usage (repository root, .venv/bin/python -B):
  speed_harness_b.py prepare --output DIR --native-attestation-sha256 PIN
  speed_harness_b.py run --plan DIR/plan/execution-plan.json --output OUT --port P --serial S
      --job-index I [--job-index J ...] --native-path fast --native-branch-start snapshot
      [--render-off] [--native-level-reader legacy|batched|probe]
      [--native-rich-transfer full|delta] [--native-probe-build pinned|phaseb]
      [--native-probe-process-identity] [--dual-read-levels [--dual-readers batched,probe]]
      [--dual-read-rich] --native-lock LOCK --i-own-this-instance
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import speed_harness as base

runner, reader, transport_module = base.runner, base.reader, base.transport_module
from clasher.rl import native_frame_storage as storage

ORIGINAL_COMPACT = runner.compact_native_frame
ORIGINAL_EXCHANGE = reader._PersistentAdbShell._exchange
ORIGINAL_READ_LEVELS = reader.VerifiedNativeReadSession.read_levels
ORIGINAL_RICH_READ = runner.NativeRichReader.read
ORIGINAL_EXECUTE_JOB = runner.execute_job
BASE_INSTRUMENT = base.instrument
STATE = {"output": None, "flags": {}, "dual_readers": (), "dual_rich": False}
KEY_SOURCES_B = (
    "src/clasher/rl/native_rich_delta.py",
    "tools/native_level_walk/clasher_level_walk.c",
    f"{HERE.relative_to(base.ROOT)}/speed_harness_b.py",
)


def exchange_kind(command):
    if command.startswith("H="):
        return "walk"
    if command.startswith("sha256sum"):
        return "helper-sha"
    if command.startswith("p=$(pidof"):
        return "pid+stat"
    if command.startswith("pidof"):
        return "pid"
    if command.startswith("cat /proc"):
        return "stat"
    return "memory"


def instrument(profile):
    BASE_INSTRUMENT(profile)

    def timed_compact(frame, **kwargs):
        start = time.perf_counter()
        if profile.first_frame is None:
            profile.first_frame = json.loads(json.dumps(frame))
        try:
            return ORIGINAL_COMPACT(frame, **kwargs)
        finally:
            profile.add("host.compact_frame", time.perf_counter() - start)

    def timed_exchange(self, command, *, max_bytes):
        start = time.perf_counter()
        try:
            return ORIGINAL_EXCHANGE(self, command, max_bytes=max_bytes)
        finally:
            profile.add(f"adb[{profile.scope()}].{exchange_kind(command)}", time.perf_counter() - start)

    runner.compact_native_frame = timed_compact
    reader._PersistentAdbShell._exchange = timed_exchange


def _record(row):
    with (STATE["output"] / "dual-read.jsonl").open("a") as stream:
        stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def dual_read_levels(self, ordinary=None):
    result = ORIGINAL_READ_LEVELS(self, ordinary=ordinary)
    row = {"kind": "levels", "tick": result["ordinary"]["tick"], "reference": self.level_reader,
           "levels": sorted([int(k), v] for k, v in result["levels"].items()), "others": {}}
    for other in STATE["dual_readers"]:
        if other == self.level_reader:
            continue
        if other == "batched" and not self._helper_verifications:
            self._check_helper()
        start = time.perf_counter()
        try:
            alternative = reader._read_levels(
                self.adb, port=self.port, serial=self.serial, batched=True, transport=self._transport,
                session=self, ordinary=result["ordinary"], level_reader=other)
            identical = (alternative["levels"] == result["levels"]
                         and alternative["ordinary"] == result["ordinary"])
            row["others"][other] = {"identical": identical, "seconds": round(time.perf_counter() - start, 4),
                                    "recoveries": alternative["transport_recoveries"]}
        except (ValueError, OSError, TimeoutError, KeyError) as error:
            row["others"][other] = {"identical": False, "error": f"{type(error).__name__}: {error}"}
            identical = False
        if not identical:
            _record(row)
            raise ValueError(f"dual level read mismatch ({other}) at tick {row['tick']}")
    _record(row)
    return result


def dual_read_rich(self):
    rich = ORIGINAL_RICH_READ(self)
    if self.accumulator is not None:
        start = time.perf_counter()
        full = self.call("observe-rich")
        identical = storage._json_bytes(full) == storage._json_bytes(rich)
        row = {"kind": "rich", "tick": rich.get("tick"), "identical": identical,
               "full_bytes": len(storage._json_bytes(full)), "seconds": round(time.perf_counter() - start, 4),
               "cursors": self.accumulator.cursors()}
        _record(row)
        if not identical:
            raise ValueError(f"dual rich read mismatch at tick {row['tick']}")
    return rich


def execute_job(plan, job, output, namespace):
    for key, value in STATE["flags"].items():
        setattr(namespace, key, value)
    STATE["output"] = output
    cpu, children, wall = time.process_time(), os.times(), time.perf_counter()
    try:
        return ORIGINAL_EXECUTE_JOB(plan, job, output, namespace)
    finally:
        after = os.times()
        (output / "host-cpu.json").write_text(json.dumps({
            "process_cpu_seconds": round(time.process_time() - cpu, 3),
            "children_cpu_seconds": round((after.children_user + after.children_system)
                                          - (children.children_user + children.children_system), 3),
            "wall_seconds": round(time.perf_counter() - wall, 3),
            "read_options": runner.native_read_options(namespace),
            "dual_readers": list(STATE["dual_readers"]), "dual_rich": STATE["dual_rich"],
        }, indent=2) + "\n")


def prepare(args):
    base.ATTESTATION = args.native_attestation_sha256
    base.prepare(args)


def run(args):
    if not args.i_own_this_instance:
        raise SystemExit("refusing: pass --i-own-this-instance for an instance no live attempt uses")
    STATE["flags"] = {
        "native_level_reader": args.native_level_reader,
        "native_rich_transfer": args.native_rich_transfer,
        "native_probe_build": args.native_probe_build,
        "native_probe_process_identity": args.native_probe_process_identity,
    }
    runner.native_read_options(argparse.Namespace(**STATE["flags"]))  # validate before any device call
    if args.dual_read_levels:
        STATE["dual_readers"] = tuple(r for r in args.dual_readers.split(",") if r)
        if not set(STATE["dual_readers"]) <= set(reader.LEVEL_READERS):
            raise SystemExit("unknown dual reader")
        if "probe" in STATE["dual_readers"] and args.native_probe_build != "phaseb":
            raise SystemExit("probe dual reads need --native-probe-build phaseb")
        reader.VerifiedNativeReadSession.read_levels = dual_read_levels
    if args.dual_read_rich:
        if args.native_rich_transfer != "delta":
            raise SystemExit("--dual-read-rich needs --native-rich-transfer delta")
        STATE["dual_rich"] = True
        runner.NativeRichReader.read = dual_read_rich
    base.KEY_SOURCES = tuple(base.KEY_SOURCES) + KEY_SOURCES_B
    base.instrument = instrument
    runner.execute_job = execute_job
    with args.native_lock.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()
        base.run(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--native-attestation-sha256", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--plan", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--port", type=int, required=True)
    execute.add_argument("--serial", required=True)
    execute.add_argument("--job-index", type=int, action="append", required=True)
    execute.add_argument("--native-path", choices=runner.NATIVE_PATHS, required=True)
    execute.add_argument("--native-branch-start", choices=runner.NATIVE_BRANCH_STARTS, required=True)
    execute.add_argument("--render-off", action="store_true")
    execute.add_argument("--max-wall-seconds", type=int, default=5400)
    execute.add_argument("--native-level-reader", choices=reader.LEVEL_READERS, default="legacy")
    execute.add_argument("--native-rich-transfer", choices=runner.NATIVE_RICH_TRANSFERS, default="full")
    execute.add_argument("--native-probe-build", choices=tuple(runner.NATIVE_PROBE_BUILDS), default="pinned")
    execute.add_argument("--native-probe-process-identity", action="store_true")
    execute.add_argument("--dual-read-levels", action="store_true")
    execute.add_argument("--dual-readers", default="legacy,batched,probe")
    execute.add_argument("--dual-read-rich", action="store_true")
    execute.add_argument("--native-lock", type=Path, required=True)
    execute.add_argument("--i-own-this-instance", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "run": run}[args.command](args)


if __name__ == "__main__":
    main()
