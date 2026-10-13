import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (str(HERE), str(HERE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)


def pytest_sessionstart(session):
    """END-FULL-F6: fail the whole run loudly if the PATH shims lost their execute bits."""
    import helpers
    helpers.require_executable_shims()
