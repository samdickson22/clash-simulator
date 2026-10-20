"""Run repository tests against the full-pool Python engine (engine-cards/py), not src/clasher.

    python -m pytest -q engine-cards/py/tests      # from the repository root, as its own session

The modules here re-export test functions from tests/ (calibration batches 1+2, engine-scope cards). Collected in this
directory, `clasher` resolves to engine-cards/py/src and the gamedata to engine-cards/py/gamedata.json (a temporary
CLASHER_ROOT holding that file plus the repository's hitboxes.json, pyproject.toml and decks.json).
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PY = Path(__file__).resolve().parents[1]
REPO = PY.parents[1]

_loaded = sys.modules.get("clasher")
if _loaded is not None and not str(getattr(_loaded, "__file__", "")).startswith(str(PY / "src")):
    raise pytest.UsageError(
        f"clasher was already imported from {_loaded.__file__}; run engine-cards/py/tests in its own pytest session"
    )
sys.path.insert(0, str(PY / "src"))

_root = Path(tempfile.mkdtemp(prefix="engine-cards-root-"))
atexit.register(shutil.rmtree, _root, True)
(_root / "gamedata.json").symlink_to(PY / "gamedata.json")
for _name in ("hitboxes.json", "pyproject.toml", "decks.json"):
    (_root / _name).symlink_to(REPO / _name)
os.environ["CLASHER_ROOT"] = str(_root)


def pytest_collection_finish(session):
    import clasher

    assert Path(clasher.__file__).resolve().is_relative_to(PY / "src"), clasher.__file__
