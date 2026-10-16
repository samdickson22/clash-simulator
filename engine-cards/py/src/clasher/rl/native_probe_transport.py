"""Host transports and root-snapshot receipts for the pinned native probe.

Two transports expose the same ``call(command) -> dict`` contract:

* ``PerCommandProbeTransport`` opens one TCP connection per command. It is the
  historical path used by ``smoke_reference_battle.request``.
* ``PersistentProbeSession`` sends ``session-v1`` once and then one command per
  line. The probe dispatches each line to the same ``handle_control_command``
  used for single-shot connections, so command semantics are unchanged. The
  probe's control server is single-threaded: while a session is open no other
  connection is served, so every command of a branch must use the session.

Neither transport blindly retries a command. A retry could apply ``step`` or a
schedule twice. Without a ``NativeLinkRecovery`` any transport fault fails the
session closed. With one, a transient link loss (refused/reset connection,
broken pipe, EOF before a response, connect timeout) triggers a bounded
recovery: wait for the device, re-add exactly the owned adb forward, reconnect,
then prove the probe attestation, the game process identity and the paused
frame are unchanged before continuing. A read-only command is re-issued on the
verified, unchanged frame. A state-changing command whose acknowledgement was
lost is never re-sent blindly: ``step``, ``replay-schedule-card`` and
``render on|off`` are resolved from the probe's tick/sequence/render state
(proven not applied: sent once; proven applied: the acknowledgement is rebuilt
from probe state); anything unprovable fails the branch. The probe's control
server is single-threaded, so the new session's greeting proves the dropped
connection was fully served before any verification read.

Snapshot helpers validate the probe's ``snapshot-create`` / ``restore H``
receipts. The probe itself re-serializes the restored state and rejects a
digest or byte-count mismatch; the host additionally checks every receipt field
against the creation receipt and records both.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
# ``handle_persistent_control_session`` reads into a 4096-byte buffer and needs
# the newline plus a terminating NUL inside it.
MAX_SESSION_COMMAND_BYTES = 4094
SESSION_GREETING = {"ok": True, "session": "control-session.v1"}
SESSION_CLOSED = {"ok": True, "sessionClosed": True}
_DIGEST = re.compile(r"[0-9a-f]{16}")

ProbeCall = Callable[[str], dict]

# The guest-side probe control port. The pool forwards host tcp:(26789+i) of
# emulator-(5580+2i) to this port.
DEVICE_PROBE_PORT = 26789
NATIVE_PROCESS_NAME = "nullsroyale.rel.free"
DEFAULT_RECOVERY_BUDGET_SECONDS = 120.0


class ProbeLinkClosed(ValueError):
    """The probe connection ended before a response delimiter."""


class AdbShellLost(ValueError):
    """A framed adb shell ended (EOF, broken pipe or stall) mid-exchange."""


class AdbLinkTransient(ConnectionError):
    """An adb command failed with a device-transport error (offline, closed...)."""


class NativeLinkLost(ConnectionError):
    """Unrecoverable device loss: budget exhausted, or process/attestation changed.

    An ``OSError`` so the readiness runner stops the shard, as before.
    """


class NativeRecoveryRejected(ValueError):
    """The link recovered, but the branch cannot continue with proven semantics.

    The device is healthy (attestation and process identity re-verified); only
    this branch fails, e.g. the frame changed or a command's delivery is
    unprovable.
    """


_TRANSIENT_LINK_ERRORS = (
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    ProbeLinkClosed,
    AdbShellLost,
    AdbLinkTransient,
)
_ADB_TRANSIENT_MARKERS = (
    "device offline", "no devices", "closed", "not found", "protocol fault",
    "connection reset", "cannot connect", "connecting",
)


def is_transient_link_error(error: BaseException, *, connecting: bool = False) -> bool:
    if isinstance(error, (NativeLinkLost, NativeRecoveryRejected)):
        return False
    if isinstance(error, _TRANSIENT_LINK_ERRORS):
        return True
    # socket.timeout is TimeoutError; only a connect/greeting timeout is a
    # link symptom (a slow command is not).
    return connecting and isinstance(error, TimeoutError)


def _canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def parse_process_identity(raw: bytes) -> tuple[int, int]:
    """Parse ``pidof`` then ``/proc/PID/stat`` output into (pid, start ticks)."""
    first, separator, stat = raw.partition(b"\n")
    if not separator or not first.strip().isdigit():
        raise ValueError("invalid native process identity response")
    pid = int(first)
    prefix, separator, tail = stat.rpartition(b")")
    if pid <= 0 or not separator or int(prefix.split(b" ", 1)[0]) != pid:
        raise ValueError("invalid native process stat")
    fields = tail.split()
    if len(fields) < 20 or not fields[19].isdigit() or int(fields[19]) <= 0:
        raise ValueError("invalid native process start time")
    return pid, int(fields[19])


class AdbLinkControl:
    """The only adb operations recovery performs, scoped to one owned device.

    ``wait-for-device``, re-adding the pool's own forward
    ``tcp:HOST_PORT -> tcp:DEVICE_PORT`` and one read-only identity shell, all
    with ``-s SERIAL``. No other forward, server or device is touched.
    """

    def __init__(self, adb, serial: str, host_port: int, *,
                 device_port: int = DEVICE_PROBE_PORT, timeout: float = 20.0,
                 run=subprocess.run):
        if (not isinstance(serial, str) or not serial
                or any(c.isspace() for c in serial) or serial.startswith("-")):
            raise ValueError("adb recovery requires one explicit device serial")
        for port in (host_port, device_port):
            if type(port) is not int or not 0 < port < 65536:
                raise ValueError("adb recovery requires valid tcp ports")
        self.adb, self.serial = Path(adb), serial
        self.host_port, self.device_port = host_port, device_port
        self.timeout, self._run = timeout, run

    @property
    def scope(self) -> dict:
        return {"serial": self.serial, "host_port": self.host_port,
                "device_port": self.device_port,
                "forward": f"tcp:{self.host_port} tcp:{self.device_port}"}

    def _adb(self, *args: str, timeout: float) -> bytes:
        argv = [str(self.adb), "-s", self.serial, *args]
        try:
            completed = self._run(argv, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise AdbLinkTransient(f"adb {args[0]} timed out after {timeout:.1f}s") from error
        if completed.returncode != 0:
            text = (bytes(completed.stdout or b"") + bytes(completed.stderr or b"")).decode(
                errors="replace").strip()
            if args[0] != "shell" or any(m in text.lower() for m in _ADB_TRANSIENT_MARKERS):
                raise AdbLinkTransient(f"adb {args[0]} failed ({completed.returncode}): {text}")
            raise NativeLinkLost(f"native process identity unavailable: {text or completed.returncode}")
        return bytes(completed.stdout or b"")

    def wait_for_device(self, *, timeout: float) -> None:
        self._adb("wait-for-device", timeout=timeout)

    def restore_forward(self, *, timeout: float) -> None:
        self._adb("forward", f"tcp:{self.host_port}", f"tcp:{self.device_port}", timeout=timeout)

    def process_identity(self, *, timeout: float) -> dict:
        raw = self._adb(
            "shell",
            f'p=$(pidof {NATIVE_PROCESS_NAME}) && echo "$p" && cat "/proc/$p/stat"',
            timeout=timeout)
        pid, start_ticks = parse_process_identity(raw)
        return {"pid": pid, "process_start_ticks": start_ticks}


class NativeLinkRecovery:
    """Bounded, audited recovery shared by one branch's probe and adb channels.

    ``run`` waits for the device, re-adds the owned forward and calls the
    channel's ``attempt`` (reconnect plus verification), retrying transient
    failures with exponential backoff until ``budget_seconds`` is spent.
    ``attempt`` returns ``(value, verification)``. Every event is recorded.
    """

    def __init__(self, control: AdbLinkControl, *, expected_attestation_sha256: str,
                 budget_seconds: float = DEFAULT_RECOVERY_BUDGET_SECONDS,
                 max_events: int = 16, backoff_initial: float = 0.5,
                 backoff_max: float = 8.0, clock=time.monotonic, sleep=time.sleep):
        if (not isinstance(expected_attestation_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_attestation_sha256)):
            raise ValueError("link recovery requires the pinned attestation SHA-256")
        if not budget_seconds > 0 or max_events < 1:
            raise ValueError("link recovery requires a positive budget")
        self.control = control
        self.expected_attestation_sha256 = expected_attestation_sha256
        self.budget_seconds = float(budget_seconds)
        self.max_events = max_events
        self.backoff_initial, self.backoff_max = backoff_initial, backoff_max
        self._clock, self._sleep = clock, sleep
        self.baseline_identity = None
        self.events: list[dict] = []
        self.device_lost = False
        self._deadlines: list[float] = []

    def establish_baseline(self) -> dict:
        if self.baseline_identity is None:
            self.baseline_identity = self.control.process_identity(timeout=self.control.timeout)
        return copy.deepcopy(self.baseline_identity)

    def _remaining(self) -> float:
        return self._deadlines[-1] - self._clock()

    def _step_timeout(self) -> float:
        return max(0.1, min(self.control.timeout, self._remaining()))

    def check_identity(self, expected: dict | None = None) -> dict:
        identity = self.control.process_identity(timeout=self._step_timeout())
        expected = self.baseline_identity if expected is None else expected
        if expected is None or identity != expected:
            raise NativeLinkLost(
                f"native process identity changed across link recovery: {expected} -> {identity}")
        return identity

    def check_attestation(self, response) -> str:
        digest = _canonical_sha(response)
        if digest != self.expected_attestation_sha256:
            raise NativeLinkLost("native attestation changed across link recovery")
        return digest

    def run(self, *, channel: str, operation: str, cause: BaseException,
            attempt: Callable[[], tuple[Any, dict]]):
        if self.device_lost:
            raise NativeLinkLost("native device link was already declared lost")
        started = self._clock()
        event = {"index": len(self.events) + 1, "channel": channel, "operation": operation,
                 "cause": f"{type(cause).__name__}: {cause}", "attempts": [],
                 "outcome": None, "duration_seconds": None, "verification": None}
        self.events.append(event)
        if event["index"] > self.max_events:
            return self._finish(event, started, "event-limit", NativeLinkLost(
                f"native link recovery limit ({self.max_events}) exceeded"))
        deadline = started + self.budget_seconds
        if self._deadlines:  # nested (probe recovery inside adb recovery)
            deadline = min(deadline, self._deadlines[-1])
        self._deadlines.append(deadline)
        try:
            delay = self.backoff_initial
            while True:
                if self._remaining() <= 0:
                    return self._finish(event, started, "budget-exhausted", NativeLinkLost(
                        f"native link not recovered within {self.budget_seconds:g}s "
                        f"({len(event['attempts'])} attempts): {event['cause']}"))
                try:
                    self.control.wait_for_device(timeout=self._step_timeout())
                    self.control.restore_forward(timeout=self._step_timeout())
                    value, verification = attempt()
                except NativeRecoveryRejected as error:
                    return self._finish(event, started, "rejected", error)
                except NativeLinkLost as error:
                    return self._finish(event, started, "device-lost", error)
                except Exception as error:  # noqa: BLE001 - classified below
                    if not is_transient_link_error(error, connecting=True):
                        lost = NativeLinkLost(f"native link recovery failed: "
                                              f"{type(error).__name__}: {error}")
                        lost.__cause__ = error
                        return self._finish(event, started, "device-lost", lost)
                    event["attempts"].append({
                        "elapsed_seconds": round(self._clock() - started, 3),
                        "error": f"{type(error).__name__}: {error}"})
                    self._sleep(max(0.0, min(delay, self._remaining())))
                    delay = min(delay * 2, self.backoff_max)
                    continue
                event["verification"] = verification
                self._finish(event, started, "recovered", None)
                return value
        finally:
            self._deadlines.pop()

    def _finish(self, event, started, outcome, error):
        event["outcome"] = outcome
        event["duration_seconds"] = round(self._clock() - started, 3)
        if error is None:
            return
        event["error"] = f"{type(error).__name__}: {error}"
        if isinstance(error, NativeLinkLost):
            self.device_lost = True
        raise error

    @property
    def record(self) -> dict:
        recovered = [e for e in self.events if e["outcome"] == "recovered"]
        return copy.deepcopy({
            "schema": "native-link-recovery.v1", "enabled": True,
            **self.control.scope,
            "budget_seconds": self.budget_seconds,
            "expected_attestation_sha256": self.expected_attestation_sha256,
            "baseline_identity": self.baseline_identity,
            "count": len(self.events), "recovered": len(recovered),
            "total_recovery_seconds": round(sum(e["duration_seconds"] or 0 for e in self.events), 3),
            "device_lost": self.device_lost, "events": self.events,
            "semantics": "reads re-issued only on a verified unchanged paused frame; "
                         "state-changing commands resolved from probe state, never re-sent blindly",
        })


_READ_ONLY_COMMANDS = frozenset({"attest", "status", "observe", "observe-rich",
                                 "observe-levels", "render status"})
_READ_ONLY_PREFIXES = ("observe-rich-since ", "replay-schedule-status ")
_STATE_FIELDS = ("tick", "generation", "stateEpoch", "configRevision")
_SCHEDULE_UNKNOWN = "scheduled replay action is unknown for this manager"
_STEP = re.compile(r"step ([1-9][0-9]{0,6})")
_SCHEDULE_CARD = re.compile(r"replay-schedule-card (\d+) (\d+) (\d+) (\d+) (\d+)")


def is_read_only_command(command: str) -> bool:
    return command in _READ_ONLY_COMMANDS or command.startswith(_READ_ONLY_PREFIXES)


def _checked(result: Any) -> dict:
    if not isinstance(result, dict) or not result.get("ok"):
        raise ValueError(f"native command rejected: {result}")
    return result


def _validate_command(command: str, *, limit: int | None = None) -> bytes:
    if not isinstance(command, str) or not command:
        raise ValueError("native command must be a non-empty string")
    if "\n" in command or "\r" in command or "\0" in command:
        raise ValueError("native command must be one line")
    encoded = command.encode()
    if limit is not None and len(encoded) > limit:
        raise ValueError("native command exceeds the session line bound")
    return encoded


class PerCommandProbeTransport:
    """One connection per command; identical to the historical request()."""

    mode = "per-command-connection"

    def __init__(self, port: int, *, host: str = "127.0.0.1", timeout: float = 30,
                 connect=socket.create_connection):
        self.port, self.host, self.timeout, self._connect = port, host, timeout, connect
        self.commands = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __call__(self, command: str) -> dict:
        encoded = _validate_command(command)
        with self._connect((self.host, self.port), timeout=self.timeout) as connection:
            connection.sendall(encoded + b"\n")
            response = bytearray()
            while chunk := connection.recv(65536):
                response.extend(chunk)
                if len(response) > MAX_RESPONSE_BYTES:
                    raise ValueError("oversized response")
        self.commands += 1
        return _checked(json.loads(response))

    @property
    def receipt(self) -> dict:
        return {"schema": "native-probe-transport.v1", "mode": self.mode,
                "commands": self.commands}


class PersistentProbeSession:
    """One ``session-v1`` connection for all commands of a branch.

    With ``recovery`` a transient link loss is recovered as described in the
    module docstring; the connection is replaced, never the command semantics.
    """

    mode = "session-v1"

    def __init__(self, port: int, *, host: str = "127.0.0.1", timeout: float = 30,
                 connect=socket.create_connection, recovery: NativeLinkRecovery | None = None):
        self.port, self.host, self.timeout, self._connect = port, host, timeout, connect
        self._socket = None
        self._buffer = bytearray()
        self._state = "new"
        self._greeting = None
        self._close_ack = None
        self._failures: list[str] = []
        self.commands = 0
        self._recovery = recovery
        self.connections = 0
        # Last verified probe state, used to prove a recovered link resumes at
        # the same paused frame. Only acknowledged responses update it.
        self._known = dict.fromkeys(_STATE_FIELDS)
        self._last_observe = None
        self._last_sequence = None
        self._mutated = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def recovery(self) -> NativeLinkRecovery | None:
        return self._recovery

    @property
    def receipt(self) -> dict:
        receipt = {
            "schema": "native-probe-transport.v1", "mode": self.mode,
            "status": self._state, "greeting": self._greeting,
            "close_acknowledgement": self._close_ack, "commands": self.commands,
            "failures": self._failures,
            "semantics": "each line is dispatched to the probe's single-shot command handler",
        }
        if self._recovery is not None:
            receipt["connections"] = self.connections
            receipt["link_recovery"] = self._recovery.record
        return copy.deepcopy(receipt)

    def _close_socket(self) -> None:
        self._buffer.clear()
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _fail(self, error: BaseException) -> None:
        self._failures.append(f"{type(error).__name__}: {error}")
        self._state = "failed"
        self._close_socket()

    def _read_line(self) -> bytes:
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._buffer[:newline])
                del self._buffer[: newline + 1]
                return line
            if len(self._buffer) > MAX_RESPONSE_BYTES:
                raise ValueError("oversized response")
            chunk = self._socket.recv(1 << 20)
            if not chunk:
                raise ProbeLinkClosed("native probe session closed before a response delimiter")
            self._buffer.extend(chunk)

    def _exchange(self, encoded: bytes) -> Any:
        if self._buffer:
            raise ValueError("unsolicited bytes on native probe session")
        self._socket.sendall(encoded + b"\n")
        line = self._read_line()
        if self._buffer:
            raise ValueError("native probe session returned more than one response")
        return json.loads(line)

    def _connect_session(self) -> dict:
        self._close_socket()
        self._socket = self._connect((self.host, self.port), timeout=self.timeout)
        greeting = self._exchange(b"session-v1")
        if greeting != SESSION_GREETING:
            raise ValueError(f"unexpected native session greeting: {greeting}")
        self.connections += 1
        return greeting

    def open(self):
        if self._state != "new":
            raise ValueError("native probe session cannot be reopened")
        try:
            self._socket = self._connect((self.host, self.port), timeout=self.timeout)
            greeting = self._exchange(b"session-v1")
            self._greeting = greeting
            if greeting != SESSION_GREETING:
                raise ValueError(f"unexpected native session greeting: {greeting}")
            self.connections += 1
            if self._recovery is not None:
                # Process identity every recovery must reproduce.
                self._recovery.establish_baseline()
            self._state = "open"
        except BaseException as error:
            self._fail(error)
            raise
        return self

    def __enter__(self):
        return self.open()

    def __call__(self, command: str) -> dict:
        if self._state != "open":
            raise ValueError("native probe session is not open or was invalidated")
        encoded = _validate_command(command, limit=MAX_SESSION_COMMAND_BYTES)
        if encoded == b"session-close":
            raise ValueError("session-close is reserved for close()")
        if not is_read_only_command(command):
            self._mutated = True
        try:
            result = self._exchange(encoded)
        except BaseException as error:
            if self._recovery is None or not is_transient_link_error(error):
                self._fail(error)
                raise
            result = self._recover_command(command, encoded, error)
        self.commands += 1
        self._track(command, result)
        # A rejected command is a normal probe answer; the session stays usable
        # exactly as a rejected single-shot command leaves the probe usable.
        return _checked(result)

    # -- state tracking and recovery -----------------------------------------

    def _track(self, command: str, result: Any) -> None:
        if not isinstance(result, dict) or result.get("ok") is not True:
            return
        if is_read_only_command(command):
            if command in ("status", "observe"):
                for key in _STATE_FIELDS:
                    if type(result.get(key)) is int:
                        self._known[key] = result[key]
                if command == "observe":
                    self._last_observe = copy.deepcopy(result)
            return
        self._last_observe = None
        if command.startswith(("replay-schedule-card ", "replay-schedule-ability ")):
            if type(result.get("sequence")) is int:
                self._last_sequence = result["sequence"]
        elif command in ("render on", "render off", "snapshot-create", "replay-schedule-clear") \
                or command.startswith("release-snapshot "):
            pass  # the paused frame and its identity are unchanged
        elif _STEP.fullmatch(command):
            self._known["tick"] = result.get("tick") if type(result.get("tick")) is int else None
            if result.get("generation") != self._known["generation"]:
                self._known = dict.fromkeys(_STATE_FIELDS)
        else:
            # configure/restore/reset/...: keep only the identity fields the
            # acknowledgement reports; the rest is unknown until observed.
            # Schedule sequences are process-global and stay valid.
            self._known = {k: result.get(k) if type(result.get(k)) is int else None
                           for k in _STATE_FIELDS}

    def _checked_exchange(self, command: str) -> dict:
        return _checked(self._exchange(command.encode()))

    def _verified_status(self) -> tuple[dict, dict]:
        """Reconnect, then re-verify attestation and process identity."""
        greeting = self._connect_session()
        recovery = self._recovery
        verification = {"greeting": greeting,
                        "attestation_sha256": recovery.check_attestation(
                            self._checked_exchange("attest")),
                        "process_identity": recovery.check_identity()}
        status = self._checked_exchange("status")
        if status.get("paused") is not True or status.get("ready") is not True:
            raise NativeRecoveryRejected("native runtime is not ready and paused after reconnect")
        return status, verification

    def _require_known(self) -> None:
        if self._known["tick"] is None or self._known["generation"] is None:
            raise NativeRecoveryRejected("no verified pre-drop probe state to compare against")

    def _verify_unchanged(self, status: dict, *, observe: bool = True) -> dict:
        if (not self._mutated and self._last_observe is None
                and all(v is None for v in self._known.values())):
            # Nothing was sent that could change state and nothing measured yet.
            return {"state": None, "observe_equal": None,
                    "note": "no state-changing command sent and no frame observed yet"}
        self._require_known()
        mismatch = {key: [self._known[key], status.get(key)] for key in _STATE_FIELDS
                    if self._known[key] is not None and status.get(key) != self._known[key]}
        if mismatch:
            raise NativeRecoveryRejected(f"native state changed across link recovery: {mismatch}")
        checked = {"state": {k: v for k, v in self._known.items() if v is not None},
                   "observe_equal": None}
        if observe and self._last_observe is not None:
            if self._checked_exchange("observe") != self._last_observe:
                raise NativeRecoveryRejected("native frame changed across link recovery")
            checked["observe_equal"] = True
        return checked

    def _recover_command(self, command: str, encoded: bytes, error: BaseException) -> Any:
        self._close_socket()
        step = _STEP.fullmatch(command)
        schedule = _SCHEDULE_CARD.fullmatch(command)

        def attempt():
            status, verification = self._verified_status()
            if is_read_only_command(command):
                verification.update(self._verify_unchanged(status))
                verification["resolution"] = "read-only command re-issued on verified unchanged frame"
                return self._exchange(encoded), verification
            if step:
                response, resolution = self._resolve_step(int(step.group(1)), status, encoded)
            elif schedule:
                response, resolution = self._resolve_schedule(schedule, status, encoded)
            elif command in ("render on", "render off"):
                self._verify_unchanged(status)
                response, resolution = self._resolve_render(command == "render off", encoded)
            else:
                raise NativeRecoveryRejected(
                    f"delivery of state-changing command {command.split(' ', 1)[0]!r} "
                    "is ambiguous and cannot be proven from probe state")
            verification["resolution"] = resolution
            return response, verification

        try:
            return self._recovery.run(channel="probe-session", operation=command[:80],
                                      cause=error, attempt=attempt)
        except NativeRecoveryRejected as rejected:
            # The link itself is healthy again: keep it for boundary checks and
            # teardown, but the branch fails with this verdict.
            self._failures.append(f"{type(rejected).__name__}: {rejected}")
            if self._socket is None:
                self._state = "failed"
            raise
        except BaseException as lost:
            self._fail(lost)
            raise

    def _resolve_step(self, count: int, status: dict, encoded: bytes):
        self._require_known()
        tick, generation, epoch = (self._known[k] for k in ("tick", "generation", "stateEpoch"))
        if status.get("generation") != generation or (
                epoch is not None and status.get("stateEpoch") != epoch):
            raise NativeRecoveryRejected("native generation changed across an unacknowledged step")
        if status.get("tick") == tick:
            self._verify_unchanged(status)
            return self._exchange(encoded), "step proven not applied (tick unchanged); sent once"
        if (status.get("tick") == tick + count and status.get("ended") is False
                and status.get("mode") == "headless" and type(status.get("steps")) is int):
            return ({"ok": True, "generation": generation, "steps": status["steps"],
                     "advanced": count, "tick": tick + count, "ended": False},
                    "step proven applied (tick advanced exactly); acknowledgement rebuilt from status")
        raise NativeRecoveryRejected(
            f"unacknowledged step {count} from tick {tick} is unprovable (tick now {status.get('tick')})")

    def _resolve_schedule(self, match, status: dict, encoded: bytes):
        owner, card, _x, _y, execute = (int(v) for v in match.groups())
        if self._last_sequence is None:
            raise NativeRecoveryRejected("no acknowledged schedule sequence proves registration")
        # A schedule does not move the frame: the tick state must be unchanged.
        self._verify_unchanged(status, observe=False)
        expected = self._last_sequence + 1
        found = self._exchange(f"replay-schedule-status {expected}".encode())
        if found == {"ok": False, "error": _SCHEDULE_UNKNOWN}:
            response = self._exchange(encoded)
            if response.get("ok") is True and response.get("sequence") != expected:
                raise NativeRecoveryRejected("resent schedule received an unexpected sequence")
            return response, f"schedule proven not registered (sequence {expected} unknown); sent once"
        if (isinstance(found, dict) and found.get("ok") is True
                and found.get("sequence") == expected and found.get("kind") == "card"
                and found.get("owner") == owner and found.get("cardId") == card
                and found.get("executeTick") == execute
                and found.get("registeredAtTick") == self._known["tick"]
                and found.get("generation") == self._known["generation"]
                and self._known["stateEpoch"] in (None, found.get("stateEpoch"))
                and found.get("state") == "pending" and found.get("error") == "none"
                and self._exchange(f"replay-schedule-status {expected + 1}".encode())
                == {"ok": False, "error": _SCHEDULE_UNKNOWN}):
            return ({"ok": True, "sequence": expected, "mode": found.get("mode"),
                     "generation": found["generation"], "stateEpoch": found["stateEpoch"],
                     "kind": "card", "registeredAtTick": found["registeredAtTick"],
                     "executeTick": execute},
                    f"schedule proven registered once (sequence {expected}); acknowledgement rebuilt")
        raise NativeRecoveryRejected(f"unacknowledged schedule registration is unprovable: {found}")

    def _resolve_render(self, suppress: bool, encoded: bytes):
        current = self._checked_exchange("render status")
        if current.get("renderSuppressed") is suppress:
            return ({"ok": True, "renderSuppressed": suppress},
                    "render gate proven in requested state; acknowledgement rebuilt")
        return self._exchange(encoded), "render gate proven unchanged; sent once"

    def _close_exchange(self) -> None:
        ack = self._exchange(b"session-close")
        self._close_ack = ack
        if ack != SESSION_CLOSED:
            raise ValueError(f"unexpected native session close acknowledgement: {ack}")
        # The server shuts the connection down after acknowledging.
        if self._socket.recv(1):
            raise ValueError("native probe session sent bytes after close")

    def close(self):
        if self._state == "closed":
            return
        if self._state != "open":
            self._close_socket()
            return
        try:
            try:
                self._close_exchange()
            except BaseException as error:
                if self._recovery is None or not is_transient_link_error(error):
                    raise
                self._close_socket()

                def attempt():
                    status, verification = self._verified_status()
                    verification.update(self._verify_unchanged(status))
                    self._close_exchange()
                    verification["resolution"] = "session-close re-issued on verified unchanged frame"
                    return None, verification

                self._recovery.run(channel="probe-session", operation="session-close",
                                   cause=error, attempt=attempt)
            self._close_socket()
            self._state = "closed"
        except BaseException as error:
            self._fail(error)
            raise

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False


def open_probe_transport(mode: str, port: int, **kwargs):
    if mode == PerCommandProbeTransport.mode:
        return PerCommandProbeTransport(port, **kwargs)
    if mode == PersistentProbeSession.mode:
        return PersistentProbeSession(port, **kwargs)
    raise ValueError(f"unknown native probe transport: {mode}")


def _int(value, *, positive=False) -> bool:
    return type(value) is int and (value > 0 if positive else value >= 0)


def create_root_snapshot(call: ProbeCall, *, expected_tick: int, current: dict) -> dict:
    """Create a process-scoped snapshot at the verified root frame."""
    receipt = call("snapshot-create")
    if (
        not _int(receipt.get("handle"), positive=True)
        or receipt.get("scope") != "process"
        or receipt.get("tick") != expected_tick
        or not isinstance(receipt.get("digest"), str)
        or not _DIGEST.fullmatch(receipt["digest"])
        or not _int(receipt.get("bytes"), positive=True)
        or not all(_int(receipt.get(k), positive=True)
                   for k in ("generation", "configRevision", "stateEpoch"))
        or not _int(receipt.get("steps"))
    ):
        raise ValueError(f"invalid native snapshot creation receipt: {receipt}")
    for key in ("generation", "stateEpoch", "tick"):
        if current.get(key) != receipt[key]:
            raise ValueError("snapshot receipt differs from the verified root frame")
    return copy.deepcopy(receipt)


def restore_root_snapshot(call: ProbeCall, snapshot: dict, *, previous_epoch: int) -> dict:
    """Restore and verify the probe's digest against the creation receipt."""
    receipt = call(f"restore {snapshot['handle']}")
    if receipt.get("restored") is not True:
        raise ValueError(f"native restore was not acknowledged: {receipt}")
    for key in ("handle", "digest", "bytes", "tick", "generation", "configRevision", "steps"):
        if receipt.get(key) != snapshot[key]:
            raise ValueError(f"native restore receipt differs from snapshot: {key}")
    if not _int(receipt.get("stateEpoch"), positive=True) or receipt["stateEpoch"] <= previous_epoch:
        raise ValueError("native restore did not begin a fresh state epoch")
    return copy.deepcopy(receipt)


def release_root_snapshot(call: ProbeCall, snapshot: dict) -> dict:
    receipt = call(f"release-snapshot {snapshot['handle']}")
    if receipt.get("released") is not True or receipt.get("handle") != snapshot["handle"]:
        raise ValueError(f"native snapshot release was not acknowledged: {receipt}")
    return copy.deepcopy(receipt)


class NativeRootSnapshotCache:
    """Holds at most one verified root snapshot for consecutive branches."""

    def __init__(self):
        self.key = None
        self.snapshot = None
        self.restores = 0

    def matches(self, key) -> bool:
        return self.snapshot is not None and self.key == key

    def store(self, key, snapshot: dict) -> None:
        if self.snapshot is not None:
            raise ValueError("release the previous root snapshot first")
        self.key, self.snapshot, self.restores = key, copy.deepcopy(snapshot), 0

    def release(self, call: ProbeCall) -> dict | None:
        if self.snapshot is None:
            return None
        snapshot = self.snapshot
        self.key = self.snapshot = None
        return release_root_snapshot(call, snapshot)

    def forget(self) -> None:
        """Drop a snapshot invalidated by an intervening configure."""
        self.key = self.snapshot = None
