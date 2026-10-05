"""Bounded native link recovery against a fake paused probe and a fake adb.

No emulator, adb binary or socket is used. The fake probe keeps the real
probe's single-threaded session semantics: a dropped connection either never
delivered the in-flight line ("before") or applied it and lost the response
("after"), and the forward stays down until ``adb forward`` re-adds it.
"""

import copy
import importlib
import json
import struct
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

from clasher.rl.native_probe_transport import (
    AdbLinkControl,
    AdbShellLost,
    NativeLinkLost,
    NativeLinkRecovery,
    NativeRecoveryRejected,
    PersistentProbeSession,
    _canonical_sha,
    is_read_only_command,
)

ADB = "/fixture/adb"
SERIAL = "emulator-5582"
HOST_PORT = 26790
UNKNOWN = {"ok": False, "error": "scheduled replay action is unknown for this manager"}


class FakeGame:
    """A paused native runtime: nothing changes between commands."""

    def __init__(self):
        self.tick, self.generation, self.epoch, self.revision = 20, 7, 7, 7
        self.steps = 20
        self.sequence = 40  # process-global schedule counter
        self.schedule, self.units = [], []
        self.render_suppressed = False
        self.attestation = {"ok": True, "attestation": {"probe_sha256": "fixture"}}
        self.pid, self.start_ticks = 2053, 1201

    def frame(self):
        return {"ok": True, "tick": self.tick, "generation": self.generation,
                "stateEpoch": self.epoch, "ended": False, "truncated": False,
                "objects": [dict(u) for u in self.units]}

    def handle(self, command):
        words = command.split()
        if command == "attest":
            return copy.deepcopy(self.attestation)
        if command == "status":
            return {"ok": True, "paused": True, "ready": True, "mode": "headless",
                    "tick": self.tick, "generation": self.generation,
                    "stateEpoch": self.epoch, "configRevision": self.revision,
                    "steps": self.steps, "ended": False,
                    "renderSuppressed": self.render_suppressed}
        if command == "observe":
            return self.frame()
        if command == "observe-rich":
            return {"ok": True, "schema": "rich", "tick": self.tick,
                    "events": [[u["seq"], u["tick"]] for u in self.units]}
        if command in ("render on", "render off"):
            self.render_suppressed = command == "render off"
            return {"ok": True, "renderSuppressed": self.render_suppressed}
        if command == "render status":
            return {"ok": True, "renderSuppressed": self.render_suppressed}
        if words[0] == "configure":
            self.generation += 1
            self.epoch += 1
            self.revision += 1
            self.tick, self.units, self.schedule = 0, [], []
            return {"ok": True, "configured": True, "configRevision": self.revision,
                    "generation": self.generation, "tick": 0}
        if words[0] == "step":
            count = int(words[1])
            for _ in range(count):
                self.tick += 1
                self.steps += 1
                for entry in self.schedule:
                    if entry["executeTick"] == self.tick and entry["state"] == "pending":
                        entry["state"] = "succeeded"
                        self.units.append({"seq": entry["sequence"], "tick": self.tick,
                                           "owner": entry["owner"], "cardId": entry["cardId"]})
            return {"ok": True, "generation": self.generation, "steps": self.steps,
                    "advanced": count, "tick": self.tick, "ended": False}
        if words[0] == "replay-schedule-card":
            owner, card, _x, _y, execute = map(int, words[1:])
            if execute <= self.tick:
                return {"ok": False, "error": "not in the future"}
            self.sequence += 1
            self.schedule.append({"sequence": self.sequence, "owner": owner, "cardId": card,
                                  "executeTick": execute, "registeredAtTick": self.tick,
                                  "state": "pending"})
            return {"ok": True, "sequence": self.sequence, "mode": "headless",
                    "generation": self.generation, "stateEpoch": self.epoch,
                    "kind": "card", "registeredAtTick": self.tick, "executeTick": execute}
        if words[0] == "replay-schedule-status":
            for entry in self.schedule:
                if entry["sequence"] == int(words[1]):
                    return {"ok": True, "sequence": entry["sequence"], "mode": "headless",
                            "generation": self.generation, "stateEpoch": self.epoch,
                            "kind": "card", "state": entry["state"], "error": "none",
                            "owner": entry["owner"], "cardId": entry["cardId"],
                            "registeredAtTick": entry["registeredAtTick"],
                            "queuedAtTick": -1, "executeTick": entry["executeTick"],
                            "resolvedCommandCardId": 0, "resolvedCardParameter": 0}
            return dict(UNKNOWN)
        return {"ok": False, "error": f"unknown command {command}"}


class FakeSocket:
    def __init__(self, link):
        self.link, self.pending, self.out, self.dead = link, b"", bytearray(), False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def sendall(self, data):
        if self.dead:
            raise BrokenPipeError(32, "Broken pipe")
        self.pending += data
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            self.link.deliver(self, line.decode())

    def recv(self, size):
        chunk = bytes(self.out[:size])
        del self.out[:size]
        return chunk  # empty means EOF: closed session or dropped link

    def close(self):
        self.dead = True


class FakeLink:
    """Host forward plus the probe's single-threaded session server."""

    def __init__(self, game, drops=None):
        self.game, self.drops = game, dict(drops or {})
        self.forward_up, self.lines, self.log = True, 0, []

    def connect(self, address, timeout):
        assert address == ("127.0.0.1", HOST_PORT)
        if not self.forward_up:
            raise ConnectionRefusedError(61, "Connection refused")
        return FakeSocket(self)

    def deliver(self, sock, line):
        if line == "session-v1":
            sock.out += b'{"ok":true,"session":"control-session.v1"}\n'
            return
        if line == "session-close":
            if self.drops.pop("close", None) == "after":
                return self.cut(sock)
            sock.out += b'{"ok":true,"sessionClosed":true}\n'
            return
        self.lines += 1
        plan = self.drops.pop(self.lines, None)
        if callable(plan):
            plan = plan(self.game)
        if plan == "before":
            return self.cut(sock)
        self.log.append(line)
        response = self.game.handle(line)
        if plan == "after":
            return self.cut(sock)
        sock.out += json.dumps(response).encode() + b"\n"

    def cut(self, sock):
        # An adb transport reconnect drops this device's forwards.
        sock.dead, self.forward_up = True, False
        sock.out.clear()


class FakeAdb:
    def __init__(self, link, game, *, offline=0, clock=None):
        self.link, self.game, self.offline, self.clock = link, game, offline, clock
        self.calls = []

    def __call__(self, argv, *, capture_output, timeout, check):
        assert capture_output and not check and timeout > 0
        self.calls.append(list(argv))
        if self.clock is not None:
            self.clock.now += 0.25
        verb = argv[3]
        if self.offline and verb in ("wait-for-device", "forward"):
            self.offline -= 1
            return subprocess.CompletedProcess(argv, 1, b"", b"error: device offline")
        if verb == "forward":
            self.link.forward_up = True
        if verb == "shell":
            stat = (f"{self.game.pid} (nullsroyale.rel.free) S " + "0 " * 18
                    + f"{self.game.start_ticks} 0 0\n")
            return subprocess.CompletedProcess(argv, 0, f"{self.game.pid}\n{stat}".encode(), b"")
        return subprocess.CompletedProcess(argv, 0, b"", b"")


class Clock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def make_recovery(game, link, **kwargs):
    clock = Clock()
    adb = FakeAdb(link, game, clock=clock, offline=kwargs.pop("offline", 0))
    control = AdbLinkControl(ADB, SERIAL, HOST_PORT, run=adb)
    recovery = NativeLinkRecovery(
        control, expected_attestation_sha256=_canonical_sha(game.attestation),
        clock=clock, sleep=clock.sleep, **kwargs)
    return recovery, adb, clock


def run_branch(drops=None, *, mutate=None, recovery_kwargs=None, recover=True):
    """A fast-path branch: prefix schedule, three five-tick decisions."""
    game = FakeGame()
    link = FakeLink(game, drops)
    recovery, adb, clock = make_recovery(game, link, **(recovery_kwargs or {}))
    if mutate is not None:
        mutate(game, link, adb)
    rows = []
    session = PersistentProbeSession(HOST_PORT, connect=link.connect,
                                     recovery=recovery if recover else None)
    with session as call:
        assert _canonical_sha(call("attest")) == recovery.expected_attestation_sha256
        call("status")
        call("render off")
        call("configure {}")
        call("observe")
        call("replay-schedule-card 0 26000000 3500 10500 3")
        call("step 5")
        for boundary in (5, 10, 15):
            before = call("observe")
            rich = call("observe-rich")
            receipt = call(f"replay-schedule-card {boundary % 2} 26000001 4000 20000 {boundary + 1}")
            stepped = call("step 1")
            assert stepped["tick"] == boundary + 1 and stepped["advanced"] == 1
            after = call("observe")
            rows.append(json.dumps({"before": before, "rich": rich, "receipt": receipt,
                                    "stepped": stepped, "after": after},
                                   separators=(",", ":")))
            call("step 4")
        call("render on")
    output = ("\n".join(rows) + "\n").encode()
    return output, session, link, adb, clock, game


def applied(log):
    """State-changing commands the game applied (recovery adds only reads)."""
    return [c for c in log if not is_read_only_command(c)]


BASELINE, BASE_SESSION, BASE_LINK, _, _, BASE_GAME = run_branch()
COMMANDS = list(BASE_LINK.log)
FIRST_SCHEDULE = next(c for c in COMMANDS if c.startswith("replay-schedule-card"))


def test_no_drop_run_is_unrecovered_and_exercises_every_command_kind():
    receipt = BASE_SESSION.receipt
    assert receipt["status"] == "closed" and receipt["connections"] == 1
    assert receipt["link_recovery"]["count"] == 0
    assert receipt["commands"] == len(COMMANDS)
    assert {c.split()[0] for c in COMMANDS} >= {
        "attest", "status", "observe", "observe-rich", "step", "replay-schedule-card",
        "render", "configure"}


def test_drop_between_requests_recovers_with_byte_identical_outputs():
    index = COMMANDS.index("observe-rich") + 1  # the observed incident
    output, session, link, _adb, _clock, game = run_branch({index: "before"})
    assert output == BASELINE
    assert applied(link.log) == applied(COMMANDS)  # nothing lost, doubled or added
    assert set(link.log) <= set(COMMANDS)  # recovery issued only verification reads
    assert game.steps == BASE_GAME.steps and game.sequence == BASE_GAME.sequence
    receipt = session.receipt
    assert receipt["status"] == "closed" and receipt["failures"] == []
    assert receipt["connections"] == 2 and receipt["commands"] == len(COMMANDS)
    record = receipt["link_recovery"]
    assert record["count"] == record["recovered"] == 1 and not record["device_lost"]
    event = record["events"][0]
    assert event["outcome"] == "recovered" and event["operation"] == "observe-rich"
    assert event["cause"].startswith("ProbeLinkClosed")
    assert event["duration_seconds"] > 0
    verification = event["verification"]
    assert verification["attestation_sha256"] == record["expected_attestation_sha256"]
    assert verification["process_identity"] == {"pid": 2053, "process_start_ticks": 1201}
    assert verification["observe_equal"] is True
    assert verification["state"]["tick"] == 5
    assert "re-issued" in verification["resolution"]


@pytest.mark.parametrize("mode", ["before", "after"])
@pytest.mark.parametrize("index", range(1, len(COMMANDS) + 1))
def test_every_drop_point_completes_identically_or_fails_closed(index, mode):
    command = COMMANDS[index - 1]
    try:
        output, session, link, *_ = run_branch({index: mode})
    except NativeRecoveryRejected:
        # Unprovable deliveries: configure (no probe state proves it) and the
        # connection's first schedule (no acknowledged sequence predecessor).
        assert command.startswith("configure") or command == FIRST_SCHEDULE
        return
    assert output == BASELINE
    assert applied(link.log) == applied(COMMANDS)
    assert session.receipt["link_recovery"]["recovered"] == 1


def test_drop_with_changed_process_identity_stops_the_shard():
    index = COMMANDS.index("observe-rich") + 1

    def restart(game):
        game.pid = 3001  # the game was restarted while the link was down
        return "before"

    with pytest.raises(NativeLinkLost, match="process identity changed"):
        run_branch({index: restart})


def test_drop_with_changed_start_time_or_attestation_stops_the_shard():
    index = COMMANDS.index("observe-rich") + 1

    def restarted(game):
        game.start_ticks += 1
        return "before"

    with pytest.raises(NativeLinkLost):
        run_branch({index: restarted})

    def rebuilt(game):
        game.attestation["attestation"]["probe_sha256"] = "other"
        return "before"

    with pytest.raises(NativeLinkLost, match="attestation"):
        run_branch({index: rebuilt})


def test_drop_with_changed_frame_fails_only_the_branch():
    index = COMMANDS.index("observe-rich") + 1

    def advanced(game):
        game.handle("step 1")  # the frame moved: the recorded state is stale
        return "before"

    with pytest.raises(NativeRecoveryRejected, match="state changed"):
        run_branch({index: advanced})


def test_unacknowledged_step_is_resolved_from_state_never_resent():
    index = COMMANDS.index("step 1") + 1
    output, session, link, *_ = run_branch({index: "after"})
    assert output == BASELINE and applied(link.log) == applied(COMMANDS)  # once
    resolution = session.receipt["link_recovery"]["events"][0]["verification"]["resolution"]
    assert "proven applied" in resolution
    output, session, link, *_ = run_branch({index: "before"})
    assert output == BASELINE and applied(link.log) == applied(COMMANDS)
    resolution = session.receipt["link_recovery"]["events"][0]["verification"]["resolution"]
    assert "proven not applied" in resolution


def test_unacknowledged_step_with_unprovable_outcome_fails():
    index = COMMANDS.index("step 1") + 1

    def partial(game):
        game.handle("step 1")
        game.handle("step 1")  # neither "not applied" nor "applied exactly once"
        return "before"

    with pytest.raises(NativeRecoveryRejected, match="unprovable"):
        run_branch({index: partial})


def test_unacknowledged_schedule_needs_proven_registration():
    index = COMMANDS.index("replay-schedule-card 1 26000001 4000 20000 6") + 1
    # Registered and response lost: proven from the probe's sequence state.
    output, session, link, *_ = run_branch({index: "after"})
    assert output == BASELINE and applied(link.log) == applied(COMMANDS)
    event = session.receipt["link_recovery"]["events"][0]
    assert "proven registered once" in event["verification"]["resolution"]
    # Never delivered: proven unknown sequence, then sent exactly once.
    output, session, link, *_ = run_branch({index: "before"})
    assert output == BASELINE and applied(link.log) == applied(COMMANDS)
    assert "proven not registered" in session.receipt["link_recovery"]["events"][0][
        "verification"]["resolution"]


def test_unacknowledged_schedule_with_mismatched_registration_fails():
    index = COMMANDS.index("replay-schedule-card 1 26000001 4000 20000 6") + 1

    def other(game):
        game.handle("replay-schedule-card 0 99 1 1 9")  # a different registration
        return "before"

    with pytest.raises(NativeRecoveryRejected, match="unprovable"):
        run_branch({index: other})


def test_unacknowledged_schedule_without_sequence_baseline_fails():
    game = FakeGame()
    link = FakeLink(game, {3: "after"})
    recovery, *_ = make_recovery(game, link)
    session = PersistentProbeSession(HOST_PORT, connect=link.connect, recovery=recovery)
    with pytest.raises(NativeRecoveryRejected, match="sequence"), session as call:
        call("status")
        call("observe")
        call("replay-schedule-card 0 26000000 3500 10500 30")
    # The first schedule of the connection has no acknowledged predecessor.
    assert game.sequence == 41


def test_unprovable_state_changing_command_fails_and_keeps_healthy_link():
    index = COMMANDS.index("configure {}") + 1
    game = FakeGame()
    link = FakeLink(game, {index: "after"})
    recovery, *_ = make_recovery(game, link)
    session = PersistentProbeSession(HOST_PORT, connect=link.connect, recovery=recovery)
    with pytest.raises(NativeRecoveryRejected, match="ambiguous"), session as call:
        for command in COMMANDS[:index]:
            call(command)
    # Teardown can still close cleanly; the verdict remains in the receipt.
    receipt = session.receipt
    assert receipt["status"] == "closed"
    assert receipt["failures"] and "ambiguous" in receipt["failures"][0]
    assert receipt["link_recovery"]["events"][0]["outcome"] == "rejected"
    assert not receipt["link_recovery"]["device_lost"]
    assert link.log.count("configure {}") == 1


def test_budget_exhaustion_declares_device_lost():
    index = COMMANDS.index("observe-rich") + 1
    with pytest.raises(NativeLinkLost, match="not recovered within 30s"):
        run_branch({index: "before"},
                   recovery_kwargs={"budget_seconds": 30, "offline": 10**6})


def test_budget_exhaustion_record_and_backoff():
    game = FakeGame()
    link = FakeLink(game, {2: "before"})
    recovery, _adb, clock = make_recovery(game, link, budget_seconds=30, offline=10**6)
    session = PersistentProbeSession(HOST_PORT, connect=link.connect, recovery=recovery)
    with pytest.raises(NativeLinkLost), session as call:
        call("status")
        call("observe")
    record = session.receipt["link_recovery"]
    assert record["device_lost"] and record["events"][0]["outcome"] == "budget-exhausted"
    assert 30 <= record["events"][0]["duration_seconds"] <= 31
    assert clock.slept[:5] == [0.5, 1.0, 2.0, 4.0, 8.0] and max(clock.slept) == 8.0
    assert session.state == "failed"
    with pytest.raises(ValueError, match="not open"):
        session("status")


def test_transient_adb_errors_retry_within_budget():
    index = COMMANDS.index("observe-rich") + 1
    output, session, *_ = run_branch({index: "before"}, recovery_kwargs={"offline": 3})
    assert output == BASELINE
    event = session.receipt["link_recovery"]["events"][0]
    assert event["outcome"] == "recovered" and len(event["attempts"]) == 3
    assert all("device offline" in a["error"] for a in event["attempts"])


def test_forward_re_add_is_scoped_to_the_owned_port_and_serial():
    index = COMMANDS.index("observe-rich") + 1
    _output, _session, _link, adb, *_ = run_branch({index: "before"})
    assert all(call[:3] == [ADB, "-s", SERIAL] for call in adb.calls)
    forwards = [call[3:] for call in adb.calls if call[3] == "forward"]
    assert forwards == [["forward", f"tcp:{HOST_PORT}", "tcp:26789"]]
    verbs = {call[3] for call in adb.calls}
    assert verbs == {"wait-for-device", "forward", "shell"}
    shells = [call[4] for call in adb.calls if call[3] == "shell"]
    assert all(s.startswith("p=$(pidof nullsroyale.rel.free)") for s in shells)
    assert not any("--remove" in part or "kill" in part or "reconnect" in part
                   for call in adb.calls for part in call)


@pytest.mark.parametrize("serial,port", [("", 1), ("-a", 1), ("a b", 1), (SERIAL, 0),
                                         (SERIAL, 70000), (SERIAL, "26789")])
def test_adb_control_rejects_unscoped_targets(serial, port):
    with pytest.raises(ValueError):
        AdbLinkControl(ADB, serial, port)


def test_drop_on_session_close_recovers_and_closes_verified():
    output, session, *_ = run_branch({"close": "after"})
    assert output == BASELINE
    receipt = session.receipt
    assert receipt["status"] == "closed" and receipt["connections"] == 2
    assert receipt["link_recovery"]["events"][0]["operation"] == "session-close"


def test_recovery_disabled_keeps_historical_fail_closed_behavior():
    index = COMMANDS.index("observe-rich") + 1
    with pytest.raises(ValueError, match="closed before a response delimiter"):
        run_branch({index: "before"}, recover=False)


# -- adb shell (level reader) channel ------------------------------------------


@pytest.fixture
def reader_runtime(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    reader = importlib.import_module("read_native_public_levels")
    data = bytearray(0x10000)
    for address, fmt, values in [
        (0x10a8, "<Q", (0x2000,)), (0x20e0, "<Q", (0x3000,)),
        (0x3010, "<Q", (0x4000,)), (0x4008, "<Q", (0x5000,)),
        (0x4010, "<ii", (1, 1)), (0x5000, "<Q", (0x6000,)),
        (0x6008, "<I", (5000006,)), (0x6078, "<i", (0,)),
        (0x60ac, "<i", (26000000,)), (0x6018, "<Q", (0x9000,)),
        (0x6020, "<i", (3,)), (0x9010, "<Q", (0xb000,)),
        (0xb008, "<Q", (0x6000,)), (0x6120, "<i", (10,)),
    ]:
        struct.pack_into(fmt, data, address, *values)
    runtime = SimpleNamespace(
        status={"ok": True, "ready": True, "paused": True, "configured": True,
                "contentReady": True, "contentPublished": True, "mode": "headless",
                "manager": "0x1000", "contentRoot": "0x100", "contentContext": "0x200",
                "configRoot": "0x300", "configLocationId": 1,
                "generation": 1, "stateEpoch": 1, "configRevision": 1, "tick": 20},
        ordinary={"ok": True, "tick": 20, "generation": 1, "stateEpoch": 1,
                  "truncated": False, "count": 1, "returned": 1,
                  "objects": [{"nativeObjectId": 5000006, "owner": 0,
                               "cardId": 26000000, "hp": 1766}]},
        attestation={"ok": True, "attestation": {**reader.EXPECTED, "content_version": "f"}},
        pid=123, start_ticks=99, shells=[], lose_reads=0, reads=0, new_pid=None, data=data,
    )

    class Shell:
        def __init__(self, adb, serial):
            assert serial == SERIAL
            self.closed = False
            runtime.shells.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.closed = True

        def pid(self):
            return runtime.pid

        def process_start_ticks(self, pid):
            return runtime.start_ticks

        def pid_and_start_ticks(self):
            if len(runtime.shells) > 1 and runtime.new_pid is not None:
                runtime.pid = runtime.new_pid
            return runtime.pid, runtime.start_ticks

        def read(self, pid, ranges):
            runtime.reads += 1
            if runtime.lose_reads and runtime.reads == runtime.lose_reads:
                raise AdbShellLost("native memory shell closed before its response delimiter")
            return b"".join(bytes(runtime.data[a:a + n]) for a, n in ranges)

    monkeypatch.setattr(reader, "_PersistentAdbShell", Shell)

    def probe(command):
        return copy.deepcopy({"attest": runtime.attestation, "status": runtime.status,
                              "observe": runtime.ordinary}[command])

    class Game:  # identity source for the fake adb identity shell
        pass

    game = Game()
    game.pid, game.start_ticks = runtime.pid, runtime.start_ticks
    clock = Clock()
    adb = FakeAdb(FakeLink(FakeGame()), game, clock=clock)
    recovery = NativeLinkRecovery(
        AdbLinkControl(ADB, SERIAL, HOST_PORT, run=adb),
        expected_attestation_sha256=reader._canonical_sha(runtime.attestation),
        clock=clock, sleep=clock.sleep)
    recovery.establish_baseline()
    return reader, runtime, probe, recovery


def _session(reader, runtime, probe, recovery):
    return reader.VerifiedNativeReadSession(
        Path(ADB), serial=SERIAL, probe=probe, recovery=recovery,
        expected_attestation_sha256=reader._canonical_sha(runtime.attestation))


def test_interrupted_level_read_is_repeated_on_the_same_frame(reader_runtime):
    reader, runtime, probe, recovery = reader_runtime
    with _session(reader, runtime, probe, recovery) as session:
        clean = session.read_levels(ordinary=copy.deepcopy(runtime.ordinary))
    baseline_provenance = session.provenance

    reader, runtime, probe, recovery = reader_runtime
    runtime.shells.clear()
    runtime.reads, runtime.lose_reads = 0, 3  # lose the shell mid-walk
    with _session(reader, runtime, probe, recovery) as session:
        recovered = session.read_levels(ordinary=copy.deepcopy(runtime.ordinary))
    provenance = session.provenance
    strip = lambda r: {k: v for k, v in r.items() if k != "verified_session"}
    assert json.dumps(strip(recovered), sort_keys=True) == json.dumps(strip(clean), sort_keys=True)
    assert recovered["transport_recoveries"] == [] and recovered["levels"] == {5000006: 11}
    assert recovered["verified_session"]["read_index"] == 1
    assert provenance["status"] == "verified" and provenance["failures"] == []
    assert provenance["reads_completed"] == baseline_provenance["reads_completed"] == 1
    assert len(runtime.shells) == 2 and all(s.closed for s in runtime.shells)
    event = recovery.record["events"][-1]
    assert event["channel"] == "adb-shell" and event["outcome"] == "recovered"
    assert event["operation"] == "read_levels#1"
    assert event["verification"]["process_identity"] == {"pid": 123, "process_start_ticks": 99}


def test_interrupted_level_read_with_changed_process_fails(reader_runtime):
    reader, runtime, probe, recovery = reader_runtime
    runtime.lose_reads, runtime.new_pid = 2, 124
    session = _session(reader, runtime, probe, recovery)
    with pytest.raises((NativeLinkLost, ValueError)), session:
        session.read_levels()
    assert session.provenance["status"] == "failed"
    assert recovery.device_lost
    assert recovery.record["events"][-1]["outcome"] == "device-lost"


def test_shell_loss_without_recovery_fails_as_before(reader_runtime):
    reader, runtime, probe, _recovery = reader_runtime
    runtime.lose_reads = 2
    session = _session(reader, runtime, probe, None)
    with pytest.raises(ValueError), session:
        session.read_levels()
    assert session.provenance["status"] == "failed"


# -- runner classification ------------------------------------------------------


@pytest.fixture
def runner(monkeypatch):
    import importlib.util
    import sys

    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    spec = importlib.util.spec_from_file_location(
        "readiness_link_recovery_test", Path("scripts/run_readiness_v2.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_classifies_rejected_recovery_as_job_local(runner):
    try:
        try:
            raise ConnectionResetError("reset")
        except ConnectionResetError as cause:
            raise NativeRecoveryRejected("frame changed") from cause
    except NativeRecoveryRejected as error:
        assert runner.run_invalidating(error) is False
    assert runner.run_invalidating(NativeLinkLost("budget")) is True
    assert runner.run_invalidating(ConnectionRefusedError()) is True


def test_runner_stops_shard_on_recorded_device_loss_even_if_teardown_replaced_error(
        runner, tmp_path, monkeypatch):
    class Transport:
        receipt: ClassVar[dict] = {"status": "failed", "failures": ["NativeLinkLost: gone"],
                   "link_recovery": {"device_lost": True,
                                     "events": [{"error": "NativeLinkLost: gone"}]}}

    def body(plan, job, output, args, stack, sessions, native_record):
        native_record.update({"path": "fast", "_transport": Transport()})
        raise ValueError("native session closing verification failed")

    monkeypatch.setattr(runner, "_execute_job_body", body)
    with pytest.raises(runner.RunInvalidatedError, match="device link lost"):
        runner.execute_job(None, None, tmp_path, None)
    record = json.loads((tmp_path / "native-execution.json").read_text())
    assert record["status"] == "failed" and record["transport"]["link_recovery"]["device_lost"]


def test_runner_completes_recovered_branch_and_records_recovery(runner, tmp_path, monkeypatch):
    index = COMMANDS.index("observe-rich") + 1
    _output, session, *_ = run_branch({index: "before"})

    def body(plan, job, output, args, stack, sessions, native_record):
        native_record.update({"path": "fast", "_transport": session})
        return {"terminal": True}

    monkeypatch.setattr(runner, "_execute_job_body", body)
    result = runner.execute_job(None, None, tmp_path, None)
    record = json.loads((tmp_path / "native-execution.json").read_text())
    assert record["status"] == "completed"
    assert record["transport"]["link_recovery"]["recovered"] == 1
    assert result["native_execution"]["transport"]["connections"] == 2


def test_runner_fast_path_arguments_default_to_bounded_recovery(runner):
    parser_args = ["execute", "--plan", "p", "--output", "o", "--native-lock", "l"]
    import sys
    captured = {}
    original = runner.execute
    try:
        runner.execute = lambda args: captured.setdefault("args", args) and 0
        old = sys.argv
        sys.argv = ["run_readiness_v2.py", *parser_args]
        try:
            runner.main()
        finally:
            sys.argv = old
    finally:
        runner.execute = original
    assert captured["args"].native_link_recovery_budget == 120.0
