"""PREREG-K4S Amendment 1 regression: measure_tiers.py re-pinned after TIERS Amendment 2 (outcome-blind)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k4s_logic as L  # noqa: E402

TIERS_SCRIPT = L.E4V3_REL + "/measure_tiers.py"
OLD_PIN = "5d7de8e36890f0f8d086e77be5ec4e20de1b3cc1f48943bd06e8bbd103046124"  # frozen K4S manifest d89cab16
NEW_PIN = "6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e"  # TIERS A2, main 6afcbbab


def test_verify_pinned_accepts_amended_measure_tiers_pin_and_rejects_old():
    manifest = json.loads((L.MAC_DIR / L.MANIFEST_NAME).read_text())
    assert manifest["reused_readonly"][TIERS_SCRIPT] == manifest["measure_tiers_unmodified"]["sha256"] == NEW_PIN
    L.verify_pinned(L.REPO_ROOT, {TIERS_SCRIPT: NEW_PIN}, "amended")
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch .*measure_tiers.py"):
        L.verify_pinned(L.REPO_ROOT, {TIERS_SCRIPT: OLD_PIN}, "frozen d89cab16")
