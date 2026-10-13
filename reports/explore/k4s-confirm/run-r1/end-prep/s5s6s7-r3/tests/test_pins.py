"""Cross-file pins and shared constants (r2): every SHA pin is current (tests/repin.py --check), the vendored
safe_input is byte-identical to its source with the pinned fingerprint, T1 originals and quiet-read v3 are the
approved bytes, and every component agrees on bases, receive roots and the manifest of record."""
import hashlib
import re
import subprocess
import sys

import helpers as H
from helpers import ROOT, ok

T1 = {"t1-originals/end_exit_push.sh": "0a87166f", "t1-originals/end_verify_push.py": "753722c9",
      "t1-originals/detach.sh": "1648dfdc"}
SAFE_INPUT_SOURCES = {"806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00":          # r3 (final pin)
                      "/mpac/sdicks02/k4s-runner/run-r1/end-prep/safe-input-r3/safe_input.py"}


def test_every_pin_is_current():
    done = subprocess.run([sys.executable, str(ROOT / "tests" / "repin.py"), "--check"], capture_output=True, text=True)
    ok(done.returncode == 0, done.stdout + done.stderr)


def test_vendored_safe_input_is_byte_identical_and_fingerprinted():
    data = (ROOT / "safe_input.py").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    ok(digest in SAFE_INPUT_SOURCES and open(SAFE_INPUT_SOURCES[digest], "rb").read() == data)
    si, tool = H.load_layers()
    import k4s_end_launch_gate as G
    import k4s_end_preflight as S
    for module in (S, G, tool):
        ok(module.SAFE_INPUT_SHA256 == digest and module.SAFE_INPUT_FINGERPRINT == si.constants_fingerprint())
    if __debug__:
        import k4s_end_verify_push as V
        ok(V.SAFE_INPUT_SHA256 == digest and V.SAFE_INPUT_FINGERPRINT == si.constants_fingerprint())
        ok(V.RECEIVE_BASE == si.D3_RECEIVE_BASE)


def test_t1_originals_quiet_and_detach():
    for rel, prefix in T1.items():
        ok(H.sha(ROOT / rel).startswith(prefix), rel)
    import k4s_end_launch_gate as G
    ok(H.sha(ROOT / "quiet-read-v3.cmd") == G.QUIET_V3_SHA256 == H.sha(
        "/mpac/sdicks02/k4s-runner/run-r1/rounds/r4/quiet-read-v3.cmd"))
    ok(H.sha(ROOT / "t1-originals/detach.sh") == G.DETACH_SHA256)


def test_shared_constants_agree():
    si, tool = H.load_layers()
    import k4s_end_launch_gate as G
    import k4s_end_preflight as S
    ok(S.K4S_MANIFEST_SHA256 == G.K4S_MANIFEST_SHA256 == si.APPROVED_K4S_MANIFEST_SHA256)
    ok(S.SEED_COMMITS == G.SEED_COMMITS and S.GUARD_SIDE_FILES == G.GUARD_SIDE_FILES)
    ok(S.MIN_HOLD_SECONDS == G.MIN_PREFLIGHT_HOLD and S.MIN_LOADED_SECONDS == G.MIN_LOADED_SECONDS)
    ok(S.CORPUS_INVENTORY_REL == G.CORPUS_INVENTORY_REL and S.VERIFIED_SCHEMA == G.VERIFIED_SCHEMA)
    ok(S.RECEIVE_BASE == G.RECEIVE["preflight"])
    for name in ("k4s_end_exit_push.sh", "k4s_preflight_push.sh"):
        text = (ROOT / name).read_text()
        bases = dict(re.findall(r"  (127x0[34])\) base=(\S+) ;;", text))
        ok(bases == si.END_BASES, (name, bases))
    ok("receive_base=" + G.RECEIVE["end"] in (ROOT / "k4s_end_exit_push.sh").read_text())
    ok("receive_base=" + G.RECEIVE["preflight"] in (ROOT / "k4s_preflight_push.sh").read_text())
    ok(G.SSH_BINARY == si.SSH_BINARY and "k4s-confirm-end-r1" not in "".join(si.END_BASES.values()))
