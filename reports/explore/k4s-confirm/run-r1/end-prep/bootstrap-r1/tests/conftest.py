"""bootstrap-r1 tests: shared fixtures. Every file the tests create lives under pytest's tmp_path (run with
--basetemp below /dev/shm/<prefix>/); the only files read outside it are this package and the pinned safe_input r3."""
import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
END_PREP = os.path.dirname(PKG)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SNIPPET_FILE = PKG + "/k4s_bootstrap_r1.py"
LOADER_FILE = PKG + "/k4s_bootstrap_loader_r1.py"
SHELL_FILE = PKG + "/k4s_bootstrap_shell_r1.sh"
BUILDER_FILE = PKG + "/build_shell_fragment.py"
SI_FILE = END_PREP + "/safe-input-r3/safe_input.py"
SI_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SI_SIZE = 133606
FLEET_PYTHON = "/usr/bin/python3"
PYTHONS = [p for p in dict.fromkeys([sys.executable, FLEET_PYTHON]) if os.path.exists(p)]


def ok(condition, message=""):
    if not condition:
        raise AssertionError(message)


def load_snippet(name="k4s_bootstrap_r1_under_test"):
    spec = importlib.util.spec_from_file_location(name, SNIPPET_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def bs():
    return load_snippet()


@pytest.fixture(scope="session")
def si(bs):
    """safe_input r3, loaded through the canonical bootstrap itself (pins: SHA-256 + size)."""
    return bs.k4s_bootstrap_load(SI_FILE, SI_SHA256, SI_SIZE, "_k4s_bootstrap_r1_tests_si", RuntimeError)
