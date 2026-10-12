"""Cross-file pins and shared constants of S5/S6/S7 (and the T1 originals they derive from)."""
import re

import k4s_end_launch_gate as G
import k4s_end_preflight as S
from helpers import ROOT, sha


def test_t1_originals_and_frozen_inputs():
    assert sha(ROOT / "t1-originals/end_exit_push.sh").startswith("0a87166f")
    assert sha(ROOT / "t1-originals/end_verify_push.py").startswith("753722c9")
    assert sha(ROOT / "t1-originals/detach.sh") == G.DETACH_SHA256
    assert sha(ROOT / "quiet-read-v3.cmd") == G.QUIET_V3_SHA256


def test_gate_and_verifier_pins_are_the_delivered_files():
    assert G.WRAPPER_SHA256 == {"end": sha(ROOT / "k4s_end_exit_push.sh"),
                                "preflight": sha(ROOT / "k4s_preflight_push.sh")}
    assert G.PREFLIGHT_SHA256 == sha(ROOT / "k4s_end_preflight.py")
    assert G.REMOTE_SHA256 == sha(ROOT / "k4s_end_launch_remote.py")
    verifier = (ROOT / "k4s_end_verify_push.py").read_text()
    assert "launch['wrapper_sha256'] == '%s'" % sha(ROOT / "k4s_end_exit_push.sh") in verifier


def test_paths_agree_across_files():
    for script in ("k4s_end_exit_push.sh", "k4s_preflight_push.sh"):
        text = (ROOT / script).read_text()
        bases = dict(re.findall(r"^  (127x0[34])\) base=(\S+) ;;$", text, re.M))
        assert bases == G.HOST_BASES
    assert 'receive="%s/$host/$attempt"' % G.RECEIVE["end"] in (ROOT / "k4s_end_exit_push.sh").read_text()
    assert 'receive="%s/$host/$attempt"' % G.RECEIVE["preflight"] in (ROOT / "k4s_preflight_push.sh").read_text()
    assert S.RECEIVE_BASE == G.RECEIVE["preflight"]
    assert "BASE = Path('%s')" % G.RUNNER in (ROOT / "k4s_end_verify_push.py").read_text()
    assert G.MIN_PREFLIGHT_HOLD == S.MIN_HOLD_SECONDS
