"""Atomic publication of owned archives and audit records; never overwrite."""

import json
import os
from pathlib import Path


def publish_archive(temporary, final):
    os.link(temporary, final)
    Path(temporary).unlink()


def publish_json(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("existing parallel record differs")
        return
    temporary = path.with_name(f".pending-{path.name}-{os.getpid()}")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.link(temporary, path)
    temporary.unlink()
