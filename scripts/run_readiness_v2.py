"""Five-tick readiness-v2 development branches and identical execution repeats.

Preparation reads existing development captures only. Execution is explicit and
never restarts an emulator. Fresh execution requires the dedicated ownership
ledger, both prospective seals and pinned calibration. Historical v7 is unchanged.
"""

from __future__ import annotations

import argparse
import fcntl
import gzip
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from contextlib import ExitStack, contextmanager
from pathlib import Path

from compare_reacting_public_branches import scalar_initial
from read_native_public_levels import (
    EXPECTED as NATIVE_PINNED_BUILD,
)
from read_native_public_levels import (
    EXPECTED_PHASEB as NATIVE_PHASEB_BUILD,
)
from read_native_public_levels import (
    LEVEL_READERS as NATIVE_LEVEL_READERS,
)
from read_native_public_levels import (
    VerifiedNativeReadSession,
)
from smoke_reference_battle import request

from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_command_checks import validate_command_step
from clasher.rl.native_frame_storage import (
    compact_native_frame,
    validate_native_frame_storage,
)
from clasher.rl.native_probe_transport import (
    DEFAULT_RECOVERY_BUDGET_SECONDS,
    AdbLinkControl,
    NativeLinkRecovery,
    NativeRecoveryRejected,
    NativeRootSnapshotCache,
    PerCommandProbeTransport,
    PersistentProbeSession,
    create_root_snapshot,
    restore_root_snapshot,
)
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicScope,
    native_out_of_arena_positions,
    native_public_level_coverage,
    public_reference_builder,
)
from clasher.rl.native_rich_delta import NativeRichTraceAccumulator
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_reference_checks import (
    check_reference_entities,
    check_reference_packet,
    reference_token_maps,
)
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.readiness_capture_ownership import (
    _checked_calibration,
    claim_branch,
    claim_technical_rerun,
    claimed_branch_keys,
    record_branch_result,
    require_execution_plan,
    technical_rerun_candidates,
)
from clasher.rl.readiness_execution import (
    CAPTURE_FILES,
    CaptureBinding,
    ExecutionPlan,
    canonical_sha,
    condition_styles,
    decision_ticks,
    file_sha,
    jobs,
    packet_sha,
    public_v4_structure_valid,
    require_development_execution,
)
from clasher.rl.readiness_job_selection import branch_key, select_job_indices
from clasher.rl.readiness_tier_b_ledger import (
    claim_tier_b_branch,
    record_tier_b_branch_result,
    require_tier_b_execution_plan,
    tier_b_claimed_branch_keys,
)
from clasher.rl.readiness_transport import (
    audit_native_transport_files,
    compact_transport_snapshot,
    public_packet_record,
)
from clasher.rl.training_readiness_v2 import (
    Branch,
    Family,
    MeasurementFloors,
    Protocol,
    Repetition,
    generate_candidates,
)


class RunInvalidatedError(ValueError):
    """An error that invalidates every remaining job, not only the current one.

    Source/input pin drift, ownership-ledger integrity and native device or
    attestation failures stop the runner. Any other job exception is recorded
    in that job's failure.json and the runner continues with the next job.
    """


# Device/transport and filesystem failures (missing emulator, adb, sockets,
# the wall-time budget) are never job-local.
RUN_INVALIDATING_TYPES = (RunInvalidatedError, OSError, subprocess.SubprocessError)


def run_invalidating(error):
    seen = set()
    while error is not None and id(error) not in seen:
        # A recovered link whose branch could not continue with proven
        # semantics (frame changed, unprovable delivery) is job-local, even
        # though its chained cause is the transient socket/adb error.
        if isinstance(error, NativeRecoveryRejected):
            return False
        if isinstance(error, RUN_INVALIDATING_TYPES):
            return True
        seen.add(id(error))
        error = error.__cause__
    return False


class RunnerTerminated(BaseException):
    """A termination signal stopped the runner mid-shard.

    A BaseException, so no job-local handler treats it as a job failure and
    continues. The current job's failure.json records it (type
    ``RunnerTerminated``) when that job has none yet.
    """

    def __init__(self, signum):
        super().__init__(f"runner terminated by {signal.Signals(signum).name}")
        self.signum = signum


TERMINATION_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


@contextmanager
def termination_signals_raise():
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum, frame):
        raise RunnerTerminated(signum)

    previous = {s: signal.signal(s, handler) for s in TERMINATION_SIGNALS}
    try:
        yield
    finally:
        for number, old in previous.items():
            signal.signal(number, old)


def record_termination(output, error):
    """Write failure.json for a signalled job unless it already has one."""
    if output is None or not output.is_dir() or (output / "failure.json").exists():
        return
    write_new(
        output / "failure.json",
        {
            "type": "RunnerTerminated",
            "message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
            "run_invalidating": True,
            # A failure after result.json is never eligible for a technical rerun.
            "after_result": (output / "result.json").exists(),
        },
    )


def verify_run_inputs(plan):
    try:
        plan.verify_inputs()
    except Exception as error:
        raise RunInvalidatedError(f"execution input pin drift: {error}") from error


def session_invalidates_run(provenance):
    """A branch session whose boundary attestation failed invalidates the run."""
    expected = provenance.get("expected_attestation_sha256")
    return expected is not None and any(
        provenance.get(key) != expected
        for key in ("start_attestation_sha256", "end_attestation_sha256")
    )


def write_new(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load_frame(capture, tick):
    matches = []
    with gzip.open(capture / "native-frames.jsonl.gz", "rt") as stream:
        for line in stream:
            frame = json.loads(line)
            if frame["ordinary"]["tick"] == tick:
                matches.append(frame)
    if len(matches) != 1:
        raise ValueError("root must have exactly one recorded public frame")
    return matches[0]


def components(capture, catalog_path, catalog_sha):
    loader = CardDataLoader(capture / "gamedata.json")
    catalog = NativeProjectileCatalog.from_csv(
        catalog_path, expected_sha256=catalog_sha
    )
    builder = public_reference_builder(
        loader, catalog, card_semantics_version=4, public_contract_version=4
    )
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", file_sha(capture / "gamedata.json")),
        card_names=tuple(PUBLIC_REFERENCE_CARDS),
        projectile_catalog=catalog,
    )
    return (
        loader,
        builder,
        adapter,
        reference_token_maps(builder, PUBLIC_REFERENCE_CARDS, catalog),
    )


def public_views(frame, adapter, maps, history):
    validate_native_frame_storage(frame)
    before, rich, levels = frame["ordinary"], frame["rich"], frame["level_source"]
    if levels["ordinary"] != before:
        raise ValueError("level evidence frame mismatch")
    level_values = {}
    for key, value in levels["levels"].items():
        if type(key) is int:
            identity = key
        elif isinstance(key, str) and key.isdecimal() and str(int(key)) == key:
            identity = int(key)
        else:
            raise ValueError("invalid serialized level identity")
        if identity in level_values:
            raise ValueError("duplicate serialized level identity")
        level_values[identity] = value
    evidence = NativePublicLevelEvidence(
        tick=before["tick"],
        generation=before["generation"],
        state_epoch=before["stateEpoch"],
        source_sha256=canonical_sha(levels),
        levels=level_values,
        confidence={key: 1.0 for key in level_values},
    )
    views = []
    card_tokens, body_tokens, effect_tokens, tower_tokens = maps
    for owner in (0, 1):
        view = adapter.project(
            before,
            owner,
            rich_snapshot=rich,
            level_evidence=evidence,
            own_last_play=history[owner],
        )
        errors = check_reference_packet(before, view, owner, card_tokens=card_tokens)
        errors += check_reference_entities(
            before,
            rich,
            view,
            owner,
            body_tokens=body_tokens,
            effect_tokens=effect_tokens,
            tower_tokens=tower_tokens,
            levels=evidence.levels,
            level_confidence=evidence.confidence,
        )
        if errors:
            raise ValueError("invalid public serialization: " + "; ".join(errors))
        views.append(view)
    return views


def prefix_history(commands):
    history = [None, None]
    for command in commands:
        if command["native_acceptance_spend_evidence"] is not True:
            raise ValueError("prefix command lacks native acceptance evidence")
        history[command["owner"]] = AcceptedOwnPlay(command["name"], command["cost"])
    return history


def prepare(args):
    # Requests are fixed before inspecting candidate outcomes. Missing roots fail;
    # no replacement draw is made here.
    requests = json.loads(args.roots.read_text())
    families, bindings, failures = [], [], []
    for root in requests:
        try:
            capture = Path(root["capture_path"]).resolve()
            metadata = json.loads((capture / "plan.json").read_text())
            result = json.loads((capture / "result.json").read_text())
            if (
                metadata.get("role") != "development"
                or result.get("failure") is not None
                or result.get("producer_sources_unchanged") is not True
            ):
                raise ValueError(
                    "preparation requires a successful opened-development capture"
                )
            frame = load_frame(capture, root["root_tick"])
            _loader, builder, adapter, maps = components(
                capture, args.catalog, args.catalog_sha256
            )
            commands = [
                c for c in result["commands"] if c["submitted_tick"] < root["root_tick"]
            ]
            views = public_views(frame, adapter, maps, prefix_history(commands))
            controller = PublicScriptedOpponent(builder, style="balanced")
            view = views[root["root_owner"]]
            binding = CaptureBinding(
                family_id=root["family_id"],
                capture_path=str(capture),
                root_tick=root["root_tick"],
                input_hashes={name: file_sha(capture / name) for name in CAPTURE_FILES},
                config_sha256=canonical_sha(metadata["config"]),
                root_frame_sha256=canonical_sha(frame),
            )
            families.append(
                Family(
                    family_id=root["family_id"],
                    independence_id=root["independence_id"],
                    root_sha256=binding.root_sha256,
                    public_packet_sha256=packet_sha(view),
                    root_owner=root["root_owner"],
                    role="opened_development",
                    candidates=generate_candidates(controller, view),
                    original_recommendation=controller.decide(view).action_id,
                )
            )
            bindings.append(binding)
        except (ValueError, OSError, KeyError, TypeError, AssertionError) as error:
            failures.append(
                {"root": root, "type": type(error).__name__, "message": str(error)}
            )
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "root-requests.json", requests)
    write_new(args.output / "generation-failures.json", failures)
    if failures:
        raise ValueError(
            "root generation failed; requests and failures retained, no replacements"
        )
    protocol = Protocol(attempt_id=args.attempt_id, families=tuple(families))
    workspace = Path(__file__).resolve().parents[1]
    sources = sorted((workspace / "src/clasher").rglob("*.py")) + [
        workspace / "scripts" / name
        for name in (
            "run_readiness_v2.py",
            "compare_reacting_public_branches.py",
            "read_native_public_levels.py",
            "smoke_reference_battle.py",
            "collect_public_development_games.py",
            "prepare_prospective_branch.py",
        )
    ]
    plan = ExecutionPlan(
        protocol=protocol,
        captures=tuple(bindings),
        catalog_path=str(args.catalog.resolve()),
        catalog_sha256=args.catalog_sha256,
        native_attestation_sha256=args.native_attestation_sha256,
        source_pins={str(path.resolve()): file_sha(path) for path in sources},
        selected_conditions=tuple(args.repetition_conditions.split(",")),
        selected_roles=tuple(args.repetition_roles.split(",")),
        repetitions=args.repetitions,
        engines=tuple(args.engines.split(",")),
        purpose=args.purpose,
    )
    write_new(args.output / "execution-plan.json", plan.model_dump(mode="json"))
    write_new(
        args.output / "jobs.json", [job.model_dump(mode="json") for job in jobs(plan)]
    )


NATIVE_PATHS = ("legacy", "fast")
NATIVE_BRANCH_STARTS = ("replay", "snapshot")
SNAPSHOT_LEAD_TICKS = 1


def native_options(args):
    """Native execution mode; defaults reproduce the historical path exactly.

    ``legacy``: one TCP connection per probe command and the historical
    observe sequence. ``fast``: one session-v1 connection per branch; the
    caller's frame observe is shared with the level reader, observe-rich is
    read inside the reader's closing frame-equality bracket, and tick lookups
    reuse the last observed frame instead of re-observing an unchanged paused
    frame. ``snapshot`` replays the root prefix once, then restores a
    digest-verified probe snapshot before every branch of that root.
    """
    path = getattr(args, "native_path", "legacy")
    start = getattr(args, "native_branch_start", "replay")
    render_off = bool(getattr(args, "native_render_off", False))
    if path not in NATIVE_PATHS or start not in NATIVE_BRANCH_STARTS:
        raise ValueError("unknown native execution mode")
    return path, start, render_off


NATIVE_RICH_TRANSFERS = ("full", "delta")
NATIVE_PROBE_BUILDS = {"pinned": NATIVE_PINNED_BUILD, "phaseb": NATIVE_PHASEB_BUILD}
DEFAULT_NATIVE_READ_OPTIONS = {
    "level_reader": "legacy",
    "rich_transfer": "full",
    "probe_build": "pinned",
    "probe_process_identity": False,
}


def native_read_options(args):
    """Native level/rich read mechanism; defaults reproduce the current path.

    ``level_reader``: ``legacy`` (host walk, one ``dd`` per range), ``batched``
    (the same walk in one pinned on-device helper process per frame, replayed
    and re-validated on the host) or ``probe`` (Phase B in-probe
    ``observe-levels``). ``rich_transfer``: ``full`` (cumulative
    ``observe-rich``) or ``delta`` (Phase B ``observe-rich-since`` with
    host-side reconstruction of the identical cumulative envelope).
    ``probe_build`` selects the attestation build pin checked by the verified
    read session; the Phase B readers require ``phaseb``. Every frame is still
    read from native memory; nothing is cached across frames.
    """
    options = {
        "level_reader": getattr(args, "native_level_reader", "legacy"),
        "rich_transfer": getattr(args, "native_rich_transfer", "full"),
        "probe_build": getattr(args, "native_probe_build", "pinned"),
        "probe_process_identity": bool(
            getattr(args, "native_probe_process_identity", False)
        ),
    }
    if (
        options["level_reader"] not in NATIVE_LEVEL_READERS
        or options["rich_transfer"] not in NATIVE_RICH_TRANSFERS
        or options["probe_build"] not in NATIVE_PROBE_BUILDS
    ):
        raise ValueError("unknown native read mechanism")
    phaseb_only = options["level_reader"] == "probe" or options["rich_transfer"] == "delta"
    if phaseb_only and options["probe_build"] != "phaseb":
        raise ValueError("Phase B level/rich reads require --native-probe-build phaseb")
    if options["probe_process_identity"] and options["level_reader"] != "probe":
        raise ValueError("probe process identity requires the probe level reader")
    return options


class NativeRichReader:
    """Per-branch rich read: full cumulative, or delta plus reconstruction."""

    def __init__(self, call, transfer):
        if transfer not in NATIVE_RICH_TRANSFERS:
            raise ValueError("unknown native rich transfer")
        self.call = call
        self.accumulator = NativeRichTraceAccumulator() if transfer == "delta" else None

    def read(self):
        if self.accumulator is None:
            return self.call("observe-rich")
        return self.accumulator.apply(self.call(self.accumulator.command()))

    def compact(self, frame):
        cache = None
        if self.accumulator is not None:
            cache = self.accumulator.event_cache(frame["rich"])
        return compact_native_frame(frame, event_cache=cache)

    @property
    def receipt(self):
        return None if self.accumulator is None else self.accumulator.receipt


def _native_execution_receipt(output, record):
    write_new(output / "native-execution.json", record)
    return file_sha(output / "native-execution.json")


def execute_job(plan, job, output, args):
    sessions = []
    native_record = {}
    try:
        with ExitStack() as stack:
            result = _execute_job_body(
                plan, job, output, args, stack, sessions, native_record
            )
    except BaseException as error:
        if sessions:
            write_new(output / "native-session.json", sessions[0].provenance)
        if native_record:
            native_record["status"] = "failed"
            _finish_native_record(native_record)
            _native_execution_receipt(output, native_record)
            recovery = native_record.get("transport", {}).get("link_recovery") or {}
            if isinstance(error, Exception) and recovery.get("device_lost"):
                # Teardown errors can replace the primary exception; the
                # recorded verdict still stops the shard.
                raise RunInvalidatedError(
                    f"native device link lost: {recovery['events'][-1].get('error')}"
                ) from error
        if (
            isinstance(error, Exception)
            and not run_invalidating(error)
            and sessions
            and session_invalidates_run(sessions[0].provenance)
        ):
            raise RunInvalidatedError(
                f"native session attestation failed: {error}"
            ) from error
        raise
    if sessions:
        provenance = sessions[0].provenance
        if provenance["status"] != "verified":
            raise RunInvalidatedError(
                "native read session did not close with verified identity"
            )
        write_new(output / "native-session.json", provenance)
        result["native_read_session"] = provenance
        result["native_session_sha256"] = file_sha(output / "native-session.json")
    if native_record:
        native_record["status"] = "completed"
        _finish_native_record(native_record)
        transport = native_record["transport"]
        if native_record["path"] == "fast" and (
            transport.get("status") != "closed" or transport.get("failures")
        ):
            raise ValueError("native probe session did not close cleanly")
        result["native_execution"] = native_record
        result["native_execution_sha256"] = _native_execution_receipt(
            output, native_record
        )
    return result


def _finish_native_record(record):
    transport = record.pop("_transport", None)
    if transport is not None:
        record["transport"] = transport.receipt
    rich_reader = record.pop("_rich_reader", None)
    if rich_reader is not None:
        record["rich_delta"] = rich_reader.receipt


def _execute_job_body(plan, job, output, args, stack, sessions, native_record=None):
    family = next(f for f in plan.protocol.families if f.family_id == job.family_id)
    binding = next(c for c in plan.captures if c.family_id == job.family_id)
    capture = Path(binding.capture_path)
    loader, builder, adapter, maps = components(
        capture, Path(plan.catalog_path), plan.catalog_sha256
    )
    names = {
        loader.get_card(name)._raw_entry["id"]: name for name in PUBLIC_REFERENCE_CARDS
    }
    source = json.loads((capture / "result.json").read_text())
    config = json.loads((capture / "plan.json").read_text())["config"]
    initial = json.loads((capture / "initial.json").read_text())
    archived_frame = load_frame(capture, binding.root_tick)
    if canonical_sha(archived_frame) != binding.root_frame_sha256:
        raise ValueError("root frame differs from frozen binding")
    prefix = [c for c in source["commands"] if c["submitted_tick"] < binding.root_tick]
    history = prefix_history(prefix)
    native = job.engine == "reference"
    call = lambda command: request(args.port, command)
    fast = False
    # ``known`` holds the most recent observe of the current paused frame in
    # the fast path; any step clears it. Legacy always re-observes.
    known = {"frame": None}
    if native:
        path, branch_start, render_off = native_options(args)
        read_options = native_read_options(args)
        fast = path == "fast"
        if native_record is None:
            native_record = {}
        native_record.update(
            {
                "schema": "readiness-native-execution.v1",
                "path": path,
                "transport_mode": PersistentProbeSession.mode
                if fast
                else PerCommandProbeTransport.mode,
                "branch_start": branch_start,
                "render_off_requested": render_off,
                **(
                    {"read_options": read_options}
                    if read_options != DEFAULT_NATIVE_READ_OPTIONS
                    else {}
                ),
                "transport": {
                    "mode": PerCommandProbeTransport.mode,
                    "implementation": "smoke_reference_battle.request",
                },
            }
        )
        recovery = None
        budget = getattr(
            args, "native_link_recovery_budget", DEFAULT_RECOVERY_BUDGET_SECONDS
        )
        if fast and budget > 0:
            # Bounded link recovery for the owned serial/forward only; see
            # native_probe_transport. Measured commands and frames are unchanged.
            recovery = NativeLinkRecovery(
                AdbLinkControl(args.adb, args.serial, args.port),
                expected_attestation_sha256=plan.native_attestation_sha256,
                budget_seconds=budget,
            )
        if fast:
            transport = PersistentProbeSession(args.port, recovery=recovery)
            native_record["_transport"] = transport
            stack.enter_context(transport)
            call = transport
        # Legacy keeps using the module-level request() so historical
        # behavior (and tests that replace it) is unchanged.
        if canonical_sha(call("attest")) != plan.native_attestation_sha256:
            raise RunInvalidatedError("native attestation mismatch")
        status = call("status")
        if status.get("paused") is not True or status.get("ready") is not True:
            raise ValueError("native reference must already be ready and paused")
        if render_off:
            gate = call("render off")
            if gate.get("renderSuppressed") is not True:
                raise ValueError("native render gate did not engage")
            native_record["render_off"] = gate

            def render_on(exc_type, exc, traceback):
                try:
                    native_record["render_restored"] = call("render on")
                except NativeRecoveryRejected as error:
                    # The recovered session still owns the probe; a single-shot
                    # connection would only queue behind it.
                    native_record["render_restore_failure"] = (
                        f"{type(error).__name__}: {error}"
                    )
                    if exc is None:
                        raise
                except (OSError, ValueError):
                    # A failed session has already closed its socket, so a
                    # single-shot connection can restore the render gate.
                    try:
                        native_record["render_restored"] = request(
                            args.port, "render on"
                        )
                    except (OSError, ValueError) as error:
                        # Never let a teardown restore replace the branch's
                        # primary failure (it decides run invalidation).
                        native_record["render_restore_failure"] = (
                            f"{type(error).__name__}: {error}"
                        )
                        if exc is None:
                            raise
                return False

            stack.push(render_on)
        cache = getattr(args, "native_root_cache", None)
        snapshot_key = (
            job.family_id,
            binding.root_frame_sha256,
            binding.config_sha256,
            args.port,
        )
        restore_from_cache = branch_start == "snapshot" and (
            cache is not None and cache.matches(snapshot_key)
        )
        if branch_start == "snapshot" and cache is None:
            raise ValueError("snapshot branch start requires a root snapshot cache")
        if not restore_from_cache:
            if branch_start == "snapshot" and cache.snapshot is not None:
                native_record["released_previous_snapshot"] = cache.release(call)
            call("configure " + json.dumps(config, separators=(",", ":")))
            current = call("observe")
            if any(current[k] != initial[k] for k in ("objects", "players", "tick")):
                raise ValueError("reconstructed initial state differs from capture")
            known["frame"] = current
        battle = None
    else:
        battle = scalar_initial(initial, names, config, loader)

    def observe():
        frame = call("observe")
        known["frame"] = frame if fast else None
        return frame

    def advance(target):
        if native:
            current = known["frame"] if fast and known["frame"] is not None else observe()
            if target < current["tick"]:
                raise ValueError("schedule moved backwards")
            if target > current["tick"] and not current["ended"]:
                count = target - current["tick"]
                known["frame"] = None
                stepped = call(f"step {count}")
                if fast and not stepped.get("ended") and (
                    stepped.get("tick") != target or stepped.get("advanced") != count
                ):
                    raise ValueError("native step did not reach its target tick")
        else:
            while battle.tick < target and not battle.game_over:
                battle.step()

    def submit(owner, name, xy, tick):
        if native:
            return call(
                f"replay-schedule-card {owner} {loader.get_card(name)._raw_entry['id']} {round(xy[0] * 1000)} {round(xy[1] * 1000)} {tick + 1}"
            )
        if not battle.deploy_card(owner, name, Position(*xy)):
            raise ValueError("scalar rejected declared command")
        return None

    def check_root(current):
        if any(
            current[key] != archived_frame["ordinary"][key]
            for key in ("objects", "players", "tick", "ended", "winner")
        ):
            raise ValueError("native replay did not reproduce frozen root")

    # Snapshot branches: libg's StateSnapshot omits some per-object caches
    # (e.g. movement targets) that the next step recomputes. A restore made
    # directly at the root therefore leaves stale caches in the root frame.
    # The snapshot is taken SNAPSHOT_LEAD_TICKS before the root; after each
    # restore the recorded prefix commands in that window are re-scheduled and
    # the lead ticks are stepped, reproducing the full root frame.
    snapshot_tick = binding.root_tick - SNAPSHOT_LEAD_TICKS
    window = [c for c in prefix if c["submitted_tick"] >= snapshot_tick]

    def replay(commands, target):
        for command in commands:
            advance(command["submitted_tick"])
            submit(
                command["owner"],
                command["name"],
                command["xy"],
                command["submitted_tick"],
            )
        advance(target)

    def restore_root():
        before_restore = observe()
        receipt = restore_root_snapshot(
            call, cache.snapshot, previous_epoch=before_restore["stateEpoch"]
        )
        cache.restores += 1
        # Entries scheduled under an earlier epoch can never execute (the
        # probe fails them on epoch mismatch); clearing restores the empty
        # schedule a fresh configure would have.
        cleared = call("replay-schedule-clear")
        restored = observe()
        if (
            restored["stateEpoch"] != receipt["stateEpoch"]
            or restored["tick"] != receipt["tick"]
        ):
            raise ValueError("restored frame differs from the restore receipt")
        replay(window, binding.root_tick)
        current = observe()
        check_root(current)
        native_record.setdefault("restores", []).append(
            {
                "restore": receipt,
                "schedule_clear": cleared,
                "restore_index": cache.restores,
                "lead_ticks_replayed": SNAPSHOT_LEAD_TICKS,
                "window_commands_rescheduled": len(window),
                "root_ordinary_sha256": canonical_sha(current),
            }
        )

    if native and restore_from_cache:
        native_record["root_replayed"] = False
        native_record["snapshot"] = cache.snapshot
        restore_root()
    elif native and branch_start == "snapshot":
        native_record["root_replayed"] = "to-snapshot-tick"
        replay([c for c in prefix if c["submitted_tick"] < snapshot_tick], snapshot_tick)
        current = observe()
        snapshot = create_root_snapshot(call, expected_tick=snapshot_tick, current=current)
        cache.store(snapshot_key, snapshot)
        native_record["snapshot"] = snapshot
        native_record["snapshot_lead_ticks"] = SNAPSHOT_LEAD_TICKS
        # Every snapshot branch, including the first, starts from a restore.
        restore_root()
    else:
        # Replay captured prefix without changing commands or schedules.
        replay(prefix, binding.root_tick)
        if native:
            native_record["root_replayed"] = True
            check_root(observe())
    if native:
        level_session = VerifiedNativeReadSession(
            args.adb,
            port=args.port,
            serial=args.serial,
            expected_attestation_sha256=plan.native_attestation_sha256,
            probe=call if fast else None,
            combined_identity_reads=fast,
            level_reader=read_options["level_reader"],
            expected_build=NATIVE_PROBE_BUILDS[read_options["probe_build"]],
            probe_process_identity=read_options["probe_process_identity"],
            recovery=recovery,
        )
        sessions.append(level_session)
        try:
            stack.enter_context(level_session)
        except Exception as error:
            # Entry only attests the device and its runtime identity; failing
            # it is a device/attestation problem shared by every later job.
            raise RunInvalidatedError(
                f"native read session could not open: {error}"
            ) from error
        rich_reader = NativeRichReader(call, read_options["rich_transfer"])
        if rich_reader.accumulator is not None:
            native_record["_rich_reader"] = rich_reader
    styles = condition_styles(job.condition, family.root_owner)
    controllers = [PublicScriptedOpponent(builder, style=style) for style in styles]
    mask_builder, space = PublicActionMaskBuilder(builder), DiscreteTileActionSpace()
    full_actor_contract_valid = True
    coverage_totals = {
        name: {"observed": 0, "visible": 0}
        for name in (
            "body_levels",
            "tower_levels",
            "own_hand_levels",
            "own_next_card_level",
        )
    }
    candidate = next(c for c in family.candidates if c.role == job.candidate_role)
    with (
        gzip.open(output / "decisions.jsonl.gz", "xt") as stream,
        gzip.open(output / "transport.jsonl.gz", "xt") as transport_stream,
    ):
        for boundary in decision_ticks(binding.root_tick):
            if time.monotonic() > args.deadline:
                raise TimeoutError("declared execution wall-time budget exhausted")
            advance(boundary)
            before = observe() if native else None
            if before["ended"] if native else battle.game_over:
                break
            if native and fast:
                # Rich is read first; the level reader's status/identity check
                # and closing observe (required equal to ``before``) bracket
                # both reads, so a frame change still fails closed.
                rich = rich_reader.read()
                levels = level_session.read_levels(ordinary=before)
                frame = {"ordinary": before, "rich": rich, "level_source": levels}
            elif native:
                levels = level_session.read_levels()
                frame = {
                    "ordinary": before,
                    "rich": rich_reader.read(),
                    "level_source": levels,
                }
                if call("observe") != before:
                    raise ValueError("native frame changed during projection")
            if native:
                views = public_views(frame, adapter, maps, history)
                if (
                    boundary == binding.root_tick
                    and packet_sha(views[family.root_owner])
                    != family.public_packet_sha256
                ):
                    raise ValueError(
                        "native root public packet differs from candidate source"
                    )
            else:
                frame = None
                views = [
                    reference_public_observation(builder.build_actor(battle, owner))
                    for owner in (0, 1)
                ]
            # Explicit unknown 0/confidence 0 is structurally valid v4 data.
            # Count measured channels separately; never infer nominal levels.
            full_actor_contract_valid = full_actor_contract_valid and all(
                public_v4_structure_valid(view) for view in views
            )
            level_coverage = [
                native_public_level_coverage(builder, view) for view in views
            ]
            for coverage in level_coverage:
                for name, counts in coverage.items():
                    for key, count in counts.items():
                        coverage_totals[name][key] += count
            selected = []
            for owner, view in enumerate(views):
                action = (
                    candidate.action_id
                    if boundary == binding.root_tick and owner == family.root_owner
                    else controllers[owner].select_action(view)
                )
                mask = mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(view)
                )
                if not mask[action]:
                    raise ValueError("declared action illegal; no tactical fallback")
                choice = space.decode_action(action, owner)
                name = (
                    None
                    if choice.is_no_op
                    else builder.card_name_for_token_id(
                        int(view.observation.hand_ids[choice.slot])
                    )
                )
                if (
                    boundary == binding.root_tick
                    and owner == family.root_owner
                    and name is not None
                ) and (
                    int(view.observation.hand_ids[choice.slot]) != candidate.card_token
                ):
                    raise ValueError("root hand slot identity differs from candidate")
                cost = None if name is None else int(loader.get_card(name).mana_cost)
                selected.append((owner, action, name, cost, choice.position))
            stream.write(
                json.dumps(
                    {
                        "tick": boundary,
                        "actions": [s[1] for s in selected],
                        "public_sha256": [packet_sha(v) for v in views],
                        "public_packets": None
                        if native
                        else [public_packet_record(v) for v in views],
                        "native_frame": None
                        if frame is None
                        else rich_reader.compact(frame),
                        "level_coverage_by_owner": level_coverage,
                        # Raw positions the projection clipped (bounded
                        # out-of-arena objects such as the thrown Log).
                        "native_out_of_arena_positions": None
                        if frame is None
                        else native_out_of_arena_positions(frame["ordinary"]),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            receipts = []
            submitted_commands = []
            for owner, action, name, cost, pos in selected:
                if name is not None:
                    receipt = submit(owner, name, [pos.x, pos.y], boundary)
                    if native:
                        receipts.append(receipt)
                        submitted_commands.append(
                            f"replay-schedule-card {owner} {loader.get_card(name)._raw_entry['id']} {round(pos.x * 1000)} {round(pos.y * 1000)} {boundary + 1}"
                        )
            advance(boundary + 1)
            if native:
                after = observe()
                transport_stream.write(
                    json.dumps(
                        {
                            "tick": boundary,
                            "selected": [
                                {
                                    "owner": owner,
                                    "action": action,
                                    "name": name,
                                    "cost": cost,
                                    "xy": None if name is None else [pos.x, pos.y],
                                }
                                for owner, action, name, cost, pos in selected
                            ],
                            "receipts": receipts,
                            "commands": submitted_commands,
                            "before": compact_transport_snapshot(before),
                            "after": compact_transport_snapshot(after),
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                validate_command_step(before, after, receipts)
            for owner, action, name, cost, pos in selected:
                if name is not None:
                    if native:
                        old = next(p for p in before["players"] if p["owner"] == owner)
                        new = next(p for p in after["players"] if p["owner"] == owner)
                        if (old["elixirRaw"] - new["elixirRaw"]) / 10000 < cost - 0.1:
                            raise ValueError("native command lacked spend evidence")
                    history[owner] = AcceptedOwnPlay(name, cost)
    if native:
        audit_native_transport_files(output, loader)
    advance(6001)
    if native:
        playable = observe()
        if not playable["ended"] and playable["tick"] != 6001:
            raise ValueError("native playable horizon incomplete")
        final = playable
        for _ in range(400):
            if final["finalized"]:
                break
            call("step 1")
            final = call("observe")
        if not final["finalized"]:
            raise ValueError("native finalization exceeded deadline")
        winner = final["winner"]
        totals = [
            sum(
                max(0, e["hp"])
                for e in playable["objects"]
                if e["cardId"] == -1 and e["hp"] is not None and e["owner"] == owner
            )
            for owner in (0, 1)
        ]
        if canonical_sha(call("attest")) != plan.native_attestation_sha256:
            raise RunInvalidatedError("native runtime changed during branch")
    else:
        if not battle.game_over:
            raise ValueError("scalar terminal state missing")
        winner = battle.winner
        totals = [
            sum(
                max(0, e.hitpoints)
                for e in battle.entities.values()
                if e.player_id == owner
                and e.entity_kind == 1
                and e.card_stats.name in ("Tower", "KingTower")
            )
            for owner in (0, 1)
        ]
    if winner not in (None, -1, 0, 1):
        raise ValueError("unknown terminal winner")
    score = 0.5 if winner in (None, -1) else float(winner == family.root_owner)
    terminal_evidence = (
        {"playable": playable, "final": final}
        if native
        else {
            "tick": battle.tick,
            "game_over": battle.game_over,
            "winner": battle.winner,
            "towers": [
                {"owner": e.player_id, "hp": max(0, e.hitpoints)}
                for e in battle.entities.values()
                if e.entity_kind == 1 and e.card_stats.name in ("Tower", "KingTower")
            ],
        }
    )
    write_new(output / "terminal.json", terminal_evidence)
    return {
        "job": job.model_dump(mode="json"),
        "score": score,
        "own_remaining_hp": float(totals[family.root_owner]),
        "enemy_remaining_hp": float(totals[1 - family.root_owner]),
        "winner": winner,
        "root_sha256": family.root_sha256,
        "public_packet_sha256": family.public_packet_sha256,
        "protocol_sha256": plan.protocol.sha256,
        "terminal": True,
        "capture_path": str(capture.resolve()),
        "gamedata_path": str((capture / "gamedata.json").resolve()),
        "gamedata_sha256": file_sha(capture / "gamedata.json"),
        "catalog_path": plan.catalog_path,
        "catalog_sha256": plan.catalog_sha256,
        "native_attestation_sha256": plan.native_attestation_sha256,
        "native_reader_sha256": file_sha(
            Path(__file__).resolve().parent / "read_native_public_levels.py"
        ),
        "native_frame_storage_sha256": file_sha(
            Path(__file__).resolve().parents[1]
            / "src/clasher/rl/native_frame_storage.py"
        ),
        **(
            {
                "native_read_options": native_read_options(args),
                "native_rich_delta_sha256": file_sha(
                    Path(__file__).resolve().parents[1]
                    / "src/clasher/rl/native_rich_delta.py"
                ),
            }
            if native and native_read_options(args) != DEFAULT_NATIVE_READ_OPTIONS
            else {}
        ),
        "root_tick": binding.root_tick,
        "root_owner": family.root_owner,
        "terminal_sha256": file_sha(output / "terminal.json"),
        "public_contract_valid": full_actor_contract_valid,
        "legacy_public_projection_valid": True,
        "public_calibration_established": bool(
            getattr(args, "calibration_verified", False)
        ),
        "calibration_receipt_sha256": getattr(args, "calibration_receipt_sha256", None),
        "level_coverage": coverage_totals,
        "projection_contract": {
            "wrapper_schema": views[0].schema_version,
            "visible_body_levels": True,
            "own_hand_next_card_level_fields": full_actor_contract_valid,
            "claim": "v4 structural validation allows explicit unknown levels; observed channel coverage is separate and calibration remains unestablished",
        },
        "legal_transport_valid": True,
        "decisions_sha256": file_sha(output / "decisions.jsonl.gz"),
        "transport_sha256": file_sha(output / "transport.jsonl.gz"),
        "command_transport_independently_audited": native,
    }


def execute(args):
    args.deadline = time.monotonic() + args.max_wall_seconds
    plan = ExecutionPlan.model_validate_json(args.plan.read_text())
    # Tier B blocks use the same executor and branch evidence, owned by the
    # Tier B tables of the readiness-v2 ledger (never by Tier A admission).
    tier_b = plan.purpose == "tier_b_transfer"
    fresh = plan.purpose == "fresh_acceptance" or tier_b
    ledger_claim = claim_tier_b_branch if tier_b else claim_branch
    ledger_record = record_tier_b_branch_result if tier_b else record_branch_result
    ledger_claimed = tier_b_claimed_branch_keys if tier_b else claimed_branch_keys
    declaration = None
    if fresh:
        if (
            args.ownership_ledger is None
            or args.attempt_id is None
            or args.calibration_receipt is None
        ):
            raise ValueError(
                "fresh execution requires its ledger, attempt and pinned calibration receipt"
            )
        declaration = (
            require_tier_b_execution_plan if tier_b else require_execution_plan
        )(args.ownership_ledger, plan, attempt_id=args.attempt_id)
    else:
        require_development_execution(plan)
    args.calibration_verified = False
    args.calibration_receipt_sha256 = None
    if args.calibration_receipt is not None:
        calibration = _checked_calibration(args.calibration_receipt)
        digest = file_sha(args.calibration_receipt)
        if calibration.catalog_sha256 != plan.catalog_sha256 or any(
            c.input_hashes["gamedata.json"] not in calibration.ruleset_sha256
            for c in plan.captures
        ):
            raise ValueError("calibration ruleset/catalog differs from branch scope")
        if (
            declaration is not None
            and declaration.input_pins.get(str(args.calibration_receipt.resolve()))
            != digest
        ):
            raise ValueError("calibration receipt was not pinned before capture")
        args.calibration_verified = True
        args.calibration_receipt_sha256 = digest
    plan.verify_inputs()
    technical_reruns = bool(getattr(args, "technical_reruns", False))
    if technical_reruns and (not fresh or tier_b):
        raise ValueError(
            "--technical-reruns is valid only for ledger-owned fresh Tier A execution"
        )
    if technical_reruns and (args.unclaimed_only or args.job_index):
        raise ValueError(
            "--technical-reruns selects its own jobs; omit --unclaimed-only and --job-index"
        )
    claimed = None
    if args.unclaimed_only:
        if not fresh:
            raise ValueError(
                "--unclaimed-only is valid only for ledger-owned fresh execution"
            )
        claimed = ledger_claimed(args.ownership_ledger, attempt_id=args.attempt_id)
    selection = select_job_indices(
        plan,
        engine=args.engine,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        explicit_indices=tuple(args.job_index),
        claimed_keys=claimed,
    )
    declared_jobs = jobs(plan)
    selected_indices = selection.selected_indices
    rerun_targets = {}
    if technical_reruns:
        # Only claims the ledger finds eligible (no result, no prior rerun,
        # declared infrastructure failure or hard kill) within this shard.
        candidates = technical_rerun_candidates(
            args.ownership_ledger, attempt_id=args.attempt_id
        )
        rerun_targets = {
            i: candidates[branch_key(declared_jobs[i])]
            for i in selection.selected_indices
            if branch_key(declared_jobs[i]) in candidates
        }
        selected_indices = tuple(sorted(rerun_targets))
    # A scalar-only batch of the same sealed plan never contacts the device.
    if args.adb is None and any(
        declared_jobs[i].engine == "reference" for i in selected_indices
    ):
        raise ValueError("native execution requires explicit adb path")
    native_path, native_start, native_render_off = native_options(args)
    if native_start == "snapshot" and fresh:
        raise ValueError(
            "snapshot branch starts need a prospective protocol declaration before fresh use"
        )
    if native_read_options(args) != DEFAULT_NATIVE_READ_OPTIONS and fresh:
        raise ValueError(
            "Phase B/batched native reads need a prospective protocol declaration before fresh use"
        )
    args.native_root_cache = NativeRootSnapshotCache()
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "execution-plan.json", plan.model_dump(mode="json"))
    write_new(args.output / "job-selection.json", selection.model_dump(mode="json"))
    if technical_reruns:
        write_new(
            args.output / "technical-rerun-selection.json",
            [
                {
                    "index": index,
                    "original_nonce": claim.nonce,
                    "original_output_path": claim.output_path,
                    "reason": reason,
                    "failure_type": failure_type,
                }
                for index, (claim, reason, failure_type) in rerun_targets.items()
            ],
        )
    # One local lock protects all conditions/repetitions. An occupied lock fails
    # immediately; this runner never takes over another collector's process.
    with args.native_lock.open("a+") as lock, termination_signals_raise():
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()
        # Job-local failures keep their claim without a result (never retried
        # or re-executed, except once through a pre-declared ledger-checked
        # technical rerun) and the runner moves on; see RunInvalidatedError.
        failed_jobs = []
        for index in selected_indices:
            output = None
            try:
                job = declared_jobs[index]
                output = args.output / f"job-{index:05d}"
                ownership = None
                if index in rerun_targets:
                    # New output path; the original directory is never touched.
                    ownership = claim_technical_rerun(
                        args.ownership_ledger,
                        attempt_id=args.attempt_id,
                        original_nonce=rerun_targets[index][0].nonce,
                        output_path=output,
                    )
                elif fresh:
                    ownership = ledger_claim(
                        args.ownership_ledger,
                        attempt_id=args.attempt_id,
                        family_id=job.family_id,
                        condition=job.condition,
                        candidate_role=job.candidate_role,
                        engine=job.engine,
                        output_path=output,
                    )
                output.mkdir()
                if ownership is not None:
                    write_new(
                        output / "ownership-claim.json",
                        ownership.model_dump(mode="json"),
                    )
                write_new(output / "claim.json", job.model_dump(mode="json"))
                try:
                    verify_run_inputs(plan)
                    result = execute_job(plan, job, output, args)
                    verify_run_inputs(plan)
                    write_new(output / "result.json", result)
                    candidate = next(
                        c
                        for f in plan.protocol.families
                        if f.family_id == job.family_id
                        for c in f.candidates
                        if c.role == job.candidate_role
                    )
                    if (
                        result["public_contract_valid"]
                        and result["public_calibration_established"]
                    ):
                        branch = Branch(
                            protocol_sha256=plan.protocol.sha256,
                            family_id=job.family_id,
                            root_sha256=result["root_sha256"],
                            public_packet_sha256=result["public_packet_sha256"],
                            candidate_role=job.candidate_role,
                            action_id=candidate.action_id,
                            condition=job.condition,
                            engine=job.engine,
                            artifact_sha256=file_sha(output / "result.json"),
                            score=result["score"],
                            own_remaining_hp=result["own_remaining_hp"],
                            enemy_remaining_hp=result["enemy_remaining_hp"],
                            terminal=True,
                            public_contract_valid=True,
                            legal_transport_valid=True,
                        )
                        write_new(output / "branch.json", branch.model_dump(mode="json"))
                        if ownership is not None:
                            try:
                                ledger_record(
                                    args.ownership_ledger,
                                    ownership,
                                    branch,
                                    artifact_hashes={
                                        str(p.relative_to(output)): file_sha(p)
                                        for p in output.rglob("*")
                                        if p.is_file()
                                    },
                                )
                            except Exception as error:
                                raise RunInvalidatedError(
                                    f"ownership ledger integrity: {error}"
                                ) from error
                    else:
                        write_new(
                            output / "branch-ineligible.json",
                            {
                                "reason": "structural v4 validation and measured public calibration must both be established before acceptance",
                                "public_contract_valid": result["public_contract_valid"],
                                "public_calibration_established": result[
                                    "public_calibration_established"
                                ],
                                "result_sha256": file_sha(output / "result.json"),
                            },
                        )
                    if plan.purpose == "identical_repetition":
                        row = Repetition(
                            engine=job.engine,
                            root_sha256=result["root_sha256"],
                            execution_sha256=job.execution_sha256,
                            artifact_sha256=file_sha(output / "result.json"),
                            score=result["score"],
                            own_remaining_hp=result["own_remaining_hp"],
                            enemy_remaining_hp=result["enemy_remaining_hp"],
                        )
                        write_new(output / "repetition.json", row.model_dump(mode="json"))
                except Exception as error:
                    invalidating = run_invalidating(error)
                    write_new(
                        output / "failure.json",
                        {
                            "type": type(error).__name__,
                            "message": str(error),
                            "traceback": traceback.format_exc(),
                            "run_invalidating": invalidating,
                        },
                    )
                    if invalidating:
                        raise
                    failed_jobs.append(
                        {
                            "index": index,
                            "output": output.name,
                            "family_id": job.family_id,
                            "condition": job.condition,
                            "candidate_role": job.candidate_role,
                            "engine": job.engine,
                            "type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                    print(
                        f"job {output.name} failed ({type(error).__name__}: {error}); "
                        "claim kept without a result, continuing",
                        file=sys.stderr,
                        flush=True,
                    )
                finally:
                    if (
                        args.native_root_cache.snapshot is not None
                        and index == selected_indices[-1]
                    ):
                        args.native_root_cache.release(
                            lambda command: request(args.port, command)
                        )
            except RunnerTerminated as error:
                record_termination(output, error)
                raise

    status = (
        "completed_fresh_technical_rerun_batch"
        if technical_reruns
        else "completed_tier_b_branch_batch"
        if tier_b
        else "completed_fresh_branch_batch"
        if fresh
        else "completed_development_only"
        if len(selection.selected_indices) == selection.full_job_count
        else "completed_development_batch"
    )
    if failed_jobs:
        # Never let a run with failed jobs pass as a complete batch.
        status += "_with_failed_jobs"
    write_new(
        args.output / "complete.json",
        {
            "native_execution": {
                "path": native_path,
                "branch_start": native_start,
                "render_off": native_render_off,
            },
            "jobs": len(selected_indices),
            "full_job_count": selection.full_job_count,
            "selected_indices": selected_indices,
            "purpose": plan.purpose,
            "status": status,
            "failed_jobs": failed_jobs,
        },
    )
    if failed_jobs:
        print(
            f"{len(failed_jobs)} of {len(selected_indices)} jobs failed: "
            + ", ".join(f["output"] for f in failed_jobs),
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


def summarize(args):
    plan = ExecutionPlan.model_validate_json(
        (args.run / "execution-plan.json").read_text()
    )
    complete = json.loads((args.run / "complete.json").read_text())
    declared = jobs(plan)
    if plan.purpose != "identical_repetition" or complete["jobs"] != len(declared):
        raise ValueError("completed identical-repetition run required")
    repetitions = []
    for index, job in enumerate(declared):
        folder = args.run / f"job-{index:05d}"
        claim = json.loads((folder / "claim.json").read_text())
        result = json.loads((folder / "result.json").read_text())
        row = Repetition.model_validate_json((folder / "repetition.json").read_text())
        if claim != job.model_dump(mode="json") or result["job"] != claim:
            raise ValueError("job provenance differs from declaration")
        if row.artifact_sha256 != file_sha(folder / "result.json") or result[
            "decisions_sha256"
        ] != file_sha(folder / "decisions.jsonl.gz"):
            raise ValueError("repetition artifacts changed")
        if row.execution_sha256 != job.execution_sha256 or row.engine != job.engine:
            raise ValueError("repetition execution identity changed")
        repetitions.append(row)
    groups = {}
    for row in repetitions:
        groups.setdefault(
            (row.engine, row.root_sha256, row.execution_sha256), []
        ).append(row)
    floor = MeasurementFloors(
        score=max(
            args.score_rounding_allowance,
            max(
                max(r.score for r in rows) - min(r.score for r in rows)
                for rows in groups.values()
            ),
        ),
        margin=max(
            args.margin_rounding_allowance,
            max(
                max(r.margin for r in rows) - min(r.margin for r in rows)
                for rows in groups.values()
            ),
        ),
        score_rounding_allowance=args.score_rounding_allowance,
        margin_rounding_allowance=args.margin_rounding_allowance,
        repetitions=tuple(repetitions),
    )
    write_new(
        args.output,
        {
            "floors": floor.model_dump(mode="json"),
            "rounding_basis": args.rounding_basis,
            "scope": "finite identical-execution development envelope; not a population bound or acceptance result",
            "execution_plan_sha256": file_sha(args.run / "execution-plan.json"),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--roots", type=Path, required=True)
    prep.add_argument("--catalog", type=Path, required=True)
    prep.add_argument("--catalog-sha256", required=True)
    prep.add_argument("--native-attestation-sha256")
    prep.add_argument("--attempt-id", required=True)
    prep.add_argument(
        "--purpose",
        choices=("development_coverage", "identical_repetition"),
        required=True,
    )
    prep.add_argument("--repetitions", type=int, default=1)
    prep.add_argument("--engines", default="scalar,reference")
    prep.add_argument(
        "--repetition-conditions",
        default="balanced/pressure,balanced/balanced,defense/pressure,defense/balanced",
    )
    prep.add_argument(
        "--repetition-roles",
        default="immediate_play,wait,alternate_card,displaced_placement",
    )
    prep.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("execute")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--adb", type=Path)
    run.add_argument("--serial", default="emulator-5580")
    run.add_argument("--port", type=int, default=26789)
    run.add_argument("--native-lock", type=Path, required=True)
    run.add_argument("--max-wall-seconds", type=int, default=7200)
    run.add_argument("--ownership-ledger", type=Path)
    run.add_argument("--attempt-id")
    run.add_argument("--calibration-receipt", type=Path)
    run.add_argument(
        "--engine", choices=("both", "scalar", "reference"), default="both"
    )
    run.add_argument("--shard-index", type=int, default=0)
    run.add_argument("--shard-count", type=int, default=1)
    run.add_argument("--job-index", type=int, action="append", default=[])
    run.add_argument("--unclaimed-only", action="store_true")
    run.add_argument(
        "--technical-reruns",
        action="store_true",
        help="fresh Tier A only: re-execute, once and at a new path, this engine/shard's claims the ledger finds eligible (no result; declared infrastructure failure or hard kill); requires technical_rerun_policy once_before_result in the attempt declaration",
    )
    run.add_argument(
        "--native-path",
        choices=NATIVE_PATHS,
        default="legacy",
        help="legacy: per-command connections and historical observes; fast: one session-v1 connection with shared frame observes",
    )
    run.add_argument(
        "--native-branch-start",
        choices=NATIVE_BRANCH_STARTS,
        default="replay",
        help="replay the prefix from zero per branch, or restore a digest-verified root snapshot",
    )
    run.add_argument("--native-render-off", action="store_true")
    run.add_argument(
        "--native-level-reader",
        choices=NATIVE_LEVEL_READERS,
        default="legacy",
        help="legacy: host walk with one dd per range; batched: one pinned on-device helper process per frame; probe: Phase B in-probe observe-levels",
    )
    run.add_argument(
        "--native-rich-transfer",
        choices=NATIVE_RICH_TRANSFERS,
        default="full",
        help="full: cumulative observe-rich; delta: Phase B observe-rich-since with host reconstruction",
    )
    run.add_argument(
        "--native-probe-build",
        choices=tuple(NATIVE_PROBE_BUILDS),
        default="pinned",
        help="attestation build pin for the verified read session (phaseb requires the Phase B probe and plan pin)",
    )
    run.add_argument(
        "--native-link-recovery-budget",
        type=float,
        default=DEFAULT_RECOVERY_BUDGET_SECONDS,
        help="fast path: seconds per bounded adb/probe link recovery (0 disables); recovered branches keep identical commands and frames",
    )
    run.add_argument(
        "--native-probe-process-identity",
        action="store_true",
        help="per-frame pid/start time from the probe response instead of ADB (probe reader only; ADB still checks at session boundaries)",
    )
    summary = sub.add_parser("summarize-repetitions")
    summary.add_argument("--run", type=Path, required=True)
    summary.add_argument("--score-rounding-allowance", type=float, required=True)
    summary.add_argument("--margin-rounding-allowance", type=float, required=True)
    summary.add_argument("--rounding-basis", required=True)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        status = {
            "prepare": prepare,
            "execute": execute,
            "summarize-repetitions": summarize,
        }[args.command](args)
    except RunnerTerminated as error:
        print(str(error), file=sys.stderr, flush=True)
        sys.exit(128 + error.signum)
    # ``execute`` returns 1 when any job failed without invalidating the run.
    if type(status) is int and status != 0:
        sys.exit(status)


if __name__ == "__main__":
    main()
