"""Capture a read-only response from the locally forwarded reference probe."""

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path


def query(
    port: int, command: str, *, timeout: float = 10, max_bytes: int = 8 * 1024 * 1024
):
    if command not in {"status", "attest", "observe", "observe-rich", "observe-atomic"}:
        raise ValueError("only read-only probe queries are supported")
    chunks = []
    size = 0
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
        connection.sendall((command + "\n").encode())
        while chunk := connection.recv(min(65536, max_bytes + 1 - size)):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("probe response exceeds configured bound")
            chunks.append(chunk)
    response = json.loads(b"".join(chunks))
    if not isinstance(response, dict):
        raise TypeError("probe must return a JSON object")
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument(
        "--command",
        choices=["status", "attest", "observe", "observe-rich", "observe-atomic"],
        default="status",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    response = query(args.port, args.command)
    with args.output.open("x") as target:
        json.dump(response, target, indent=2)
        target.write("\n")
    print("Captured", args.command, "to", args.output)


if __name__ == "__main__":
    main()
