import importlib.util
import socket
import threading
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "query_reference_probe",
    Path(__file__).parents[1] / "scripts/query_reference_probe.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def response_server(payload):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve():
        with server:
            connection, _ = server.accept()
            with connection:
                request = b""
                while not request.endswith(b"\n"):
                    request += connection.recv(1024)
                assert request == b"status\n"
                connection.sendall(payload)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return port, thread


def test_reads_complete_probe_response():
    port, thread = response_server(b'{"ok":true,"ready":false}\n')
    assert module.query(port, "status") == {"ok": True, "ready": False}
    thread.join(timeout=1)
    assert not thread.is_alive()


@pytest.mark.parametrize(
    "payload,error", [(b"[]", TypeError), (b"{", ValueError), (b"x" * 101, ValueError)]
)
def test_rejects_invalid_or_oversized_response(payload, error):
    port, thread = response_server(payload)
    with pytest.raises(error):
        module.query(port, "status", max_bytes=100)
    thread.join(timeout=1)
    assert not thread.is_alive()


def test_refuses_mutating_command_before_connecting():
    with pytest.raises(ValueError, match="read-only"):
        module.query(1, "reset")
