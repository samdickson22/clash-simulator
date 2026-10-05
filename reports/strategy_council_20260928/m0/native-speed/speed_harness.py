"""Profile and compare native readiness branch execution modes.

Opened-development roots only. Calls the runner's own ``prepare`` and
``execute_job``; never touches an ownership ledger. Timing wrappers only
measure; they pass every argument and result through unchanged.

Usage (from the repository root, with .venv/bin/python -B):
  speed_harness.py prepare --output DIR
  speed_harness.py run --plan DIR/execution-plan.json --output DIR --port P --serial S
      --job-index I [--job-index J] --native-path legacy|fast
      --native-branch-start replay|snapshot [--render-off] [--max-wall-seconds N]
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import gzip
import hashlib
import json
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import read_native_public_levels as reader  # noqa: E402
import run_readiness_v2 as runner  # noqa: E402

from clasher.rl import native_probe_transport as transport_module  # noqa: E402
from clasher.rl.public_action_mask import PublicActionMaskBuilder  # noqa: E402
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent  # noqa: E402
from clasher.rl.readiness_execution import ExecutionPlan, file_sha, jobs  # noqa: E402

ADB = Path("/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb")
CATALOG = Path(
    "/Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"
)
CATALOG_SHA = "c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5"
ATTESTATION = "864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93"
TAIL = ROOT / (
    "reports/strategy_council_20260928/m0/readiness/native-prefix-development-v2-tail"
)
ROOT_EPISODES = ("episode-00", "episode-01", "episode-05", "episode-03")
# Files whose bytes define the executed path; pinned per run in the profile.
KEY_SOURCES = (
    "scripts/run_readiness_v2.py",
    "scripts/read_native_public_levels.py",
    "scripts/smoke_reference_battle.py",
    "src/clasher/rl/native_probe_transport.py",
    "src/clasher/rl/native_public_observation.py",
    "src/clasher/rl/public_scripted_opponent.py",
    "src/clasher/rl/public_action_mask.py",
    "src/clasher/rl/readiness_execution.py",
    "src/clasher/rl/readiness_transport.py",
    "src/clasher/rl/native_frame_storage.py",
    "src/clasher/rl/native_command_checks.py",
)


def prepare(args):
    roots = []
    for name in ROOT_EPISODES:
        capture = TAIL / name
        selection = json.loads((capture / "result.json").read_text())["selection"]
        roots.append(
            {
                "capture_path": str(capture),
                "family_id": selection["family_id"],
                "independence_id": selection["family_id"],
                "root_tick": selection["root_tick"],
                "root_owner": selection["root_owner"],
            }
        )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "roots.json").write_text(json.dumps(roots, indent=2) + "\n")
    runner.prepare(
        argparse.Namespace(
            roots=args.output / "roots.json",
            catalog=CATALOG,
            catalog_sha256=CATALOG_SHA,
            native_attestation_sha256=ATTESTATION,
            attempt_id="native-speed-equivalence-development",
            purpose="development_coverage",
            repetitions=1,
            engines="reference",
            repetition_conditions=",".join(runner.CONDITIONS)
            if hasattr(runner, "CONDITIONS")
            else "balanced/pressure,balanced/balanced,defense/pressure,defense/balanced",
            repetition_roles="immediate_play,wait,alternate_card,displaced_placement",
            output=args.output / "plan",
        )
    )


class Profile:
    def __init__(self):
        self.stats = collections.defaultdict(lambda: [0, 0.0])
        self.context = []
        self.marks = {}
        self.first_frame = None

    def add(self, key, seconds):
        entry = self.stats[key]
        entry[0] += 1
        entry[1] += seconds

    @contextlib.contextmanager
    def within(self, name):
        self.context.append(name)
        try:
            yield
        finally:
            self.context.pop()

    def scope(self):
        return self.context[-1] if self.context else "runner"

    def summary(self):
        return {
            key: {"count": count, "seconds": round(total, 4)}
            for key, (count, total) in sorted(self.stats.items())
        }


def verb(command):
    return command.split(" ", 1)[0]


def instrument(profile):
    """Wrap functions with timers; each wrapper returns the original result."""
    original_request = runner.request

    def timed_request(port, command):
        start = time.perf_counter()
        try:
            return original_request(port, command)
        finally:
            profile.add(
                f"probe[{profile.scope()}].{verb(command)}", time.perf_counter() - start
            )

    runner.request = timed_request
    reader.request = timed_request

    session_call = transport_module.PersistentProbeSession.__call__

    def timed_session_call(self, command):
        start = time.perf_counter()
        try:
            return session_call(self, command)
        finally:
            profile.add(
                f"probe[{profile.scope()}].{verb(command)}", time.perf_counter() - start
            )

    transport_module.PersistentProbeSession.__call__ = timed_session_call

    session_open = transport_module.PersistentProbeSession.open

    def timed_open(self):
        start = time.perf_counter()
        try:
            return session_open(self)
        finally:
            profile.add("probe_session.open", time.perf_counter() - start)

    transport_module.PersistentProbeSession.open = timed_open

    exchange = reader._PersistentAdbShell._exchange

    def timed_exchange(self, command, *, max_bytes):
        start = time.perf_counter()
        try:
            return exchange(self, command, max_bytes=max_bytes)
        finally:
            kind = "pid+stat" if command.startswith("p=$(pidof") else "pid" if command.startswith("pidof") else (
                "stat" if command.startswith("cat /proc") else "memory"
            )
            profile.add(f"adb[{profile.scope()}].{kind}", time.perf_counter() - start)

    reader._PersistentAdbShell._exchange = timed_exchange

    read_levels = reader.VerifiedNativeReadSession.read_levels

    def timed_read_levels(self, *args, **kwargs):
        start = time.perf_counter()
        with profile.within("level_read"):
            try:
                return read_levels(self, *args, **kwargs)
            finally:
                profile.add("level_read.total", time.perf_counter() - start)

    reader.VerifiedNativeReadSession.read_levels = timed_read_levels

    enter = reader.VerifiedNativeReadSession.__enter__

    def timed_enter(self):
        profile.marks.setdefault("root_ready", time.perf_counter())
        start = time.perf_counter()
        with profile.within("session_boundary"):
            try:
                return enter(self)
            finally:
                profile.add("level_session.enter", time.perf_counter() - start)

    reader.VerifiedNativeReadSession.__enter__ = timed_enter

    exit_ = reader.VerifiedNativeReadSession.__exit__

    def timed_exit(self, *exc):
        start = time.perf_counter()
        with profile.within("session_boundary"):
            try:
                return exit_(self, *exc)
            finally:
                profile.add("level_session.close", time.perf_counter() - start)

    reader.VerifiedNativeReadSession.__exit__ = timed_exit

    def wrap(owner, name, key):
        original = getattr(owner, name)

        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                profile.add(key, time.perf_counter() - start)

        setattr(owner, name, timed)

    wrap(runner, "public_views", "host.projection_and_checks")
    wrap(PublicScriptedOpponent, "select_action", "host.controller")
    wrap(PublicActionMaskBuilder, "build", "host.mask")

    compact = runner.compact_native_frame

    def timed_compact(frame):
        start = time.perf_counter()
        if profile.first_frame is None:
            profile.first_frame = json.loads(json.dumps(frame))
        try:
            return compact(frame)
        finally:
            profile.add("host.compact_frame", time.perf_counter() - start)

    runner.compact_native_frame = timed_compact

    audit = runner.audit_native_transport_files

    def timed_audit(*args, **kwargs):
        profile.marks.setdefault("loop_done", time.perf_counter())
        start = time.perf_counter()
        try:
            return audit(*args, **kwargs)
        finally:
            profile.add("host.transport_audit", time.perf_counter() - start)

    runner.audit_native_transport_files = timed_audit


def source_hashes():
    return {name: file_sha(ROOT / name) for name in KEY_SOURCES}


def run(args):
    plan = ExecutionPlan.model_validate_json(args.plan.read_text())
    declared = jobs(plan)
    args.output.mkdir(parents=True, exist_ok=False)
    namespace = types.SimpleNamespace(
        adb=ADB,
        serial=args.serial,
        port=args.port,
        deadline=time.monotonic() + args.max_wall_seconds,
        native_path=args.native_path,
        native_branch_start=args.native_branch_start,
        native_render_off=args.render_off,
        native_root_cache=transport_module.NativeRootSnapshotCache(),
        calibration_verified=False,
        calibration_receipt_sha256=None,
    )
    sources_at_start = source_hashes()
    summary = []
    try:
        for index in args.job_index:
            job = declared[index]
            output = args.output / f"job-{index:05d}"
            output.mkdir()
            (output / "claim.json").write_text(
                json.dumps(job.model_dump(mode="json"), indent=2) + "\n"
            )
            profile = Profile()
            instrument_state = _Patch()
            with instrument_state:
                instrument(profile)
                start = time.perf_counter()
                failure = None
                try:
                    result = runner.execute_job(plan, job, output, namespace)
                    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
                except Exception as error:  # retained; the harness keeps going
                    failure = f"{type(error).__name__}: {error}"
                    (output / "failure.json").write_text(
                        json.dumps({"failure": failure}, indent=2) + "\n"
                    )
                wall = time.perf_counter() - start
            decisions = 0
            if (output / "decisions.jsonl.gz").exists():
                with gzip.open(output / "decisions.jsonl.gz", "rt") as stream:
                    decisions = sum(1 for _ in stream)
            if profile.first_frame is not None:
                with gzip.open(output / "first-decision-full-frame.json.gz", "wt") as stream:
                    json.dump(profile.first_frame, stream, separators=(",", ":"))
            root_ready = profile.marks.get("root_ready", start) - start
            loop_done = profile.marks.get("loop_done", start + wall) - start
            record = {
                "job_index": index,
                "job": job.model_dump(mode="json"),
                "port": args.port,
                "serial": args.serial,
                "native_path": args.native_path,
                "native_branch_start": args.native_branch_start,
                "render_off": args.render_off,
                "failure": failure,
                "wall_seconds": round(wall, 3),
                "time_to_root_seconds": round(root_ready, 3),
                "decision_loop_seconds": round(loop_done - root_ready, 3),
                "terminal_seconds": round(wall - loop_done, 3),
                "decisions": decisions,
                "seconds_per_decision": round((loop_done - root_ready) / max(decisions, 1), 4),
                "breakdown": profile.summary(),
            }
            (output / "profile.json").write_text(json.dumps(record, indent=2) + "\n")
            summary.append({k: record[k] for k in record if k != "breakdown"})
            print(json.dumps(summary[-1]), flush=True)
    finally:
        if namespace.native_root_cache.snapshot is not None:
            released = namespace.native_root_cache.release(
                lambda command: runner.request(args.port, command)
            )
            (args.output / "snapshot-release.json").write_text(json.dumps(released) + "\n")
    (args.output / "run-summary.json").write_text(
        json.dumps(
            {
                "sources_at_start": sources_at_start,
                "sources_at_end": source_hashes(),
                "jobs": summary,
            },
            indent=2,
        )
        + "\n"
    )


class _Patch:
    """Restore every patched attribute after one job (fresh timers per job)."""

    TARGETS = (
        (runner, "request"), (reader, "request"), (runner, "public_views"),
        (runner, "compact_native_frame"), (runner, "audit_native_transport_files"),
        (transport_module.PersistentProbeSession, "__call__"),
        (transport_module.PersistentProbeSession, "open"),
        (reader._PersistentAdbShell, "_exchange"),
        (reader.VerifiedNativeReadSession, "read_levels"),
        (reader.VerifiedNativeReadSession, "__enter__"),
        (reader.VerifiedNativeReadSession, "__exit__"),
        (PublicScriptedOpponent, "select_action"),
        (PublicActionMaskBuilder, "build"),
    )

    def __enter__(self):
        self.saved = [(o, n, getattr(o, n)) for o, n in self.TARGETS]
        return self

    def __exit__(self, *exc):
        for owner, name, value in self.saved:
            setattr(owner, name, value)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--plan", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--port", type=int, required=True)
    execute.add_argument("--serial", required=True)
    execute.add_argument("--job-index", type=int, action="append", required=True)
    execute.add_argument("--native-path", choices=runner.NATIVE_PATHS, required=True)
    execute.add_argument(
        "--native-branch-start", choices=runner.NATIVE_BRANCH_STARTS, required=True
    )
    execute.add_argument("--render-off", action="store_true")
    execute.add_argument("--max-wall-seconds", type=int, default=5400)
    args = parser.parse_args()
    {"prepare": prepare, "run": run}[args.command](args)


if __name__ == "__main__":
    main()
