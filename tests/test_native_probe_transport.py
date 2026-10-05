"""Persistent probe session and root snapshot receipts against a mock probe."""

import json
import socket
import threading
from pathlib import Path

import pytest

from clasher.rl.native_probe_transport import (
    MAX_SESSION_COMMAND_BYTES,
    NativeRootSnapshotCache,
    PerCommandProbeTransport,
    PersistentProbeSession,
    create_root_snapshot,
    release_root_snapshot,
    restore_root_snapshot,
)


class MockProbe:
    """Single-threaded accept loop like ``run_control_server``."""

    def __init__(self, handler=None, greeting=None, close_ack=None):
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        self.accepts = 0
        self.commands = []
        self.handler = handler or (lambda command: {"ok": True, "echo": command})
        self.greeting = greeting or {"ok": True, "session": "control-session.v1"}
        self.close_ack = close_ack or {"ok": True, "sessionClosed": True}
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def respond(self, connection, value):
        if isinstance(value, bytes):
            connection.sendall(value)
        elif value is not None:
            connection.sendall(json.dumps(value).encode() + b"\n")

    def serve(self):
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            self.accepts += 1
            with connection, connection.makefile("rb") as stream:
                first = stream.readline().rstrip(b"\n").decode()
                if first != "session-v1":
                    self.commands.append(first)
                    self.respond(connection, self.handler(first))
                    self.hang_up(connection)
                    continue
                self.respond(connection, self.greeting)
                for raw in stream:
                    command = raw.rstrip(b"\n").decode()
                    if command == "session-close":
                        self.respond(connection, self.close_ack)
                        break
                    self.commands.append(command)
                    reply = self.handler(command)
                    if reply == "hang-up":
                        break
                    self.respond(connection, reply)
                self.hang_up(connection)

    @staticmethod
    def hang_up(connection):
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def stop(self):
        self.server.close()


@pytest.fixture
def probe():
    servers = []

    def make(**kwargs):
        server = MockProbe(**kwargs)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.stop()


def test_session_uses_one_connection_for_many_commands_and_closes_verified(probe):
    server = probe()
    with PersistentProbeSession(server.port) as session:
        assert session("status") == {"ok": True, "echo": "status"}
        assert session("observe")["echo"] == "observe"
        assert session("step 4")["echo"] == "step 4"
    assert server.accepts == 1
    assert server.commands == ["status", "observe", "step 4"]
    receipt = session.receipt
    assert receipt["status"] == "closed" and receipt["commands"] == 3
    assert receipt["greeting"] == {"ok": True, "session": "control-session.v1"}
    assert receipt["close_acknowledgement"] == {"ok": True, "sessionClosed": True}
    with pytest.raises(ValueError, match="not open"):
        session("status")


def test_per_command_transport_matches_historical_request(probe, monkeypatch):
    import sys

    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    sys.modules.pop("smoke_reference_battle", None)
    from smoke_reference_battle import request

    server = probe()
    transport = PerCommandProbeTransport(server.port)
    assert transport("observe") == request(server.port, "observe")
    assert server.accepts == 2 and transport.commands == 1


def test_rejected_command_raises_like_request_but_session_stays_usable(probe):
    server = probe(
        handler=lambda c: {"ok": False, "error": "no"} if c == "bad" else {"ok": True}
    )
    with PersistentProbeSession(server.port) as session:
        with pytest.raises(ValueError, match="native command rejected"):
            session("bad")
        assert session("status") == {"ok": True}
    assert session.receipt["status"] == "closed"


@pytest.mark.parametrize(
    "command",
    ["two\nlines", "carriage\rreturn", "", "x" * (MAX_SESSION_COMMAND_BYTES + 1),
     "session-close"],
)
def test_session_rejects_unframeable_or_reserved_commands_before_sending(probe, command):
    server = probe()
    with PersistentProbeSession(server.port) as session:
        with pytest.raises(ValueError):
            session(command)
        assert session("status")["ok"]
    assert server.commands == ["status"]


@pytest.mark.parametrize(
    "reply",
    ["hang-up", b"{not json}\n", b'{"ok":true}\n{"ok":true}\n'],
)
def test_session_fault_fails_closed_without_retry(probe, reply):
    server = probe(handler=lambda c: reply if c == "observe" else {"ok": True})
    session = PersistentProbeSession(server.port, timeout=5).open()
    with pytest.raises(ValueError):
        session("observe")
    assert session.state == "failed" and session.receipt["failures"]
    with pytest.raises(ValueError, match="not open"):
        session("status")
    session.close()
    assert server.commands == ["observe"]


def test_session_rejects_unexpected_greeting_and_close_ack(probe):
    server = probe(greeting={"ok": True, "session": "other"})
    with pytest.raises(ValueError, match="greeting"):
        PersistentProbeSession(server.port).open()
    server = probe(close_ack={"ok": True})
    session = PersistentProbeSession(server.port).open()
    with pytest.raises(ValueError, match="close acknowledgement"):
        session.close()
    assert session.state == "failed"


def test_session_timeout_fails_closed(probe):
    server = probe(handler=lambda c: None)
    session = PersistentProbeSession(server.port, timeout=0.2).open()
    with pytest.raises((TimeoutError, socket.timeout)):
        session("observe")
    assert session.state == "failed"


SNAPSHOT = {
    "ok": True, "handle": 3, "scope": "process", "generation": 5,
    "configRevision": 5, "stateEpoch": 5, "tick": 400, "steps": 400,
    "digest": "effe4ad9a0c3140e", "bytes": 2461,
}
ROOT = {"tick": 400, "generation": 5, "stateEpoch": 5}


def restore_reply(**changes):
    reply = {**SNAPSHOT, "restored": True, "stateEpoch": 6}
    reply.pop("scope")
    return {**reply, **changes}


def test_snapshot_create_restore_release_receipts():
    snapshot = create_root_snapshot(lambda c: dict(SNAPSHOT), expected_tick=400, current=ROOT)
    assert snapshot == SNAPSHOT
    sent = []

    def call(command):
        sent.append(command)
        return restore_reply()

    receipt = restore_root_snapshot(call, snapshot, previous_epoch=5)
    assert sent == ["restore 3"] and receipt["digest"] == SNAPSHOT["digest"]
    released = release_root_snapshot(
        lambda c: {"ok": True, "released": True, "handle": 3, "generation": 5}, snapshot
    )
    assert released["released"] is True


@pytest.mark.parametrize(
    "change",
    [{"digest": "0" * 16}, {"digest": "XYZ"}, {"tick": 401}, {"scope": "slot"},
     {"handle": 0}, {"bytes": 0}, {"generation": 6}],
)
def test_snapshot_creation_rejects_invalid_or_mismatched_receipts(change):
    reply = {**SNAPSHOT, **change}
    current = ROOT
    if change.get("digest") == "0" * 16:
        # A valid-looking digest is accepted at creation; restores verify it.
        assert create_root_snapshot(lambda c: reply, expected_tick=400, current=current)
        return
    with pytest.raises(ValueError):
        create_root_snapshot(lambda c: reply, expected_tick=400, current=current)


@pytest.mark.parametrize(
    "change",
    [{"digest": "0" * 16}, {"bytes": 1}, {"tick": 405}, {"handle": 4}, {"steps": 401},
     {"generation": 6}, {"configRevision": 6}, {"stateEpoch": 5}, {"restored": False}],
)
def test_restore_rejects_any_receipt_that_differs_from_the_snapshot(change):
    with pytest.raises(ValueError):
        restore_root_snapshot(lambda c: restore_reply(**change), SNAPSHOT, previous_epoch=5)


def test_restore_rejected_by_probe_propagates(probe):
    server = probe(handler=lambda c: {"ok": False, "handle": 3, "error": "stale"})
    with (
        PersistentProbeSession(server.port) as session,
        pytest.raises(ValueError, match="native command rejected"),
    ):
        restore_root_snapshot(session, SNAPSHOT, previous_epoch=5)


def test_root_snapshot_cache_matches_only_its_root_and_releases():
    cache = NativeRootSnapshotCache()
    key = ("family", "root", "config", 1)
    assert not cache.matches(key) and cache.release(lambda c: {}) is None
    cache.store(key, SNAPSHOT)
    assert cache.matches(key) and not cache.matches(("family", "root", "config", 2))
    with pytest.raises(ValueError, match="release"):
        cache.store(key, SNAPSHOT)
    sent = []

    def call(command):
        sent.append(command)
        return {"ok": True, "released": True, "handle": 3}

    assert cache.release(call)["released"] and sent == ["release-snapshot 3"]
    assert cache.snapshot is None and not cache.matches(key)


def test_runner_native_options_default_to_the_historical_path(monkeypatch):
    import importlib.util
    import sys
    import types

    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    spec = importlib.util.spec_from_file_location(
        "readiness_native_options_test", Path("scripts/run_readiness_v2.py")
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    assert runner.native_options(types.SimpleNamespace()) == ("legacy", "replay", False)
    assert runner.native_options(
        types.SimpleNamespace(native_path="fast", native_branch_start="snapshot",
                              native_render_off=True)
    ) == ("fast", "snapshot", True)
    with pytest.raises(ValueError, match="unknown native"):
        runner.native_options(types.SimpleNamespace(native_path="turbo"))
