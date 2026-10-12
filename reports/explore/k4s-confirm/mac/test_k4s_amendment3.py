"""PREREG-K4S Amendment 3 regression: fleet_validity.py re-pinned after TIERS Amendment 5 (E4 guard census-ownership
race fix; outcome-blind)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_manifest as B  # noqa: E402
import k4s_logic as L  # noqa: E402

FLEET_VALIDITY = L.E4V3_REL + "/fleet_validity.py"
OLD_FLEET_VALIDITY = "94d0e7f2c20bfc139f5d95ccefb375f52293a06c2c78bee84e9442fc62bcb0ae"  # K4S manifest c1fb1e9a
NEW_FLEET_VALIDITY = "0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f"  # TIERS A5, main 8799a0d6


def manifest():
    return json.loads((L.MAC_DIR / L.MANIFEST_NAME).read_text())


def test_verify_pinned_accepts_amended_fleet_validity_and_rejects_old():
    assert manifest()["reused_readonly"][FLEET_VALIDITY] == NEW_FLEET_VALIDITY
    assert "fleet_validity.py" in B.E4V3_REUSED
    L.verify_pinned(L.REPO_ROOT, {FLEET_VALIDITY: NEW_FLEET_VALIDITY}, "amended")
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch .*fleet_validity.py"):
        L.verify_pinned(L.REPO_ROOT, {FLEET_VALIDITY: OLD_FLEET_VALIDITY}, "c1fb1e9a")


def test_every_other_reused_pin_unchanged_from_amendment_2():
    """Only the fleet_validity leaf moves; every other pinned file still verifies on the amended tree."""
    m = manifest()
    others = {k: v for k, v in m["reused_readonly"].items() if k != FLEET_VALIDITY}
    L.verify_pinned(L.REPO_ROOT, others, "unchanged")


def test_fleet_reporting_runtime_never_imports_fleet_validity():
    """Fleet reporting runs the frozen 391d2006 runner/supervisor, which never imports fleet_validity; outside mac/,
    only the END modules (and their tests/docs) name it or e4v3."""
    here = Path(__file__).resolve().parent.parent
    for rel in ("run.py", "supervise.py", "host_audit.py", "launch.sh", "runtime.sh"):
        assert "fleet_validity" not in (here / rel).read_text(), rel
    names = {p.name for p in here.glob("*") if p.is_file() and p.suffix in (".py", ".sh")
             and ("fleet_validity" in p.read_text() or "e4v3" in p.read_text())}
    assert names == {"end_background.py", "end_evidence.py", "end_pool.py", "end_reference.py",
                     "test_end_background.py", "test_end_reference.py"}, names
