"""S4 r5 regression controls for SOL-REVIEW-END-FULL-r1 END-FULL-F1: the vendored safe_input layer is read only through
the canonical bootstrap r1. (1) The embedded region is the canonical text byte for byte (pins outside it). (2) The
bootstrap-r1 conformance kit runs the assembler itself (as a script and as an import) with every alias substitution
made BEFORE the bootstrap runs: zero canary opens/bytes (recorders + kernel atime), nothing executed, refusal in S4's
convention (RuntimeError at import, before any assembler code touches a path); the control and the post-hash swap run
exactly the hashed bytes. (3) The pins match the vendored file and the fingerprint is still checked after the
bootstrap. Checks use ok() (an explicit raise), never a bare assert."""
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

S4_FILE = Path(__file__).resolve().parent / "assemble_fleet_reference.py"

HERE = Path(__file__).resolve().parent
BOOTSTRAP_DIR = HERE.parent / "bootstrap-r1"
sys.path.append(str(BOOTSTRAP_DIR / "tests"))
from k4s_bootstrap_kit import Entrypoint, check_scenario, run_scenario   # noqa: E402  (bootstrap-r1 kit)

CANONICAL_SHA256 = "5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b"    # bootstrap-r1 CANONICAL-READY
BEGIN = b"# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 "
END = b"# ==== END K4S CANONICAL BOOTSTRAP r1 ====\n"
LAYER = S4_FILE.parent / "safe_input.py"


def ok(condition, message=""):
    if not condition:
        raise AssertionError(message)


def region(source):
    start = source.index(BEGIN)
    stop = source.index(END) + len(END)
    ok(source.count(BEGIN) == 1 and source.count(END) == 1)
    ok(source[start - 1:start] == b"\n")
    return source[start:stop]


def load_s4(name):
    spec = importlib.util.spec_from_file_location(name, S4_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedded_bootstrap_is_the_canonical_text():
    embedded = region(S4_FILE.read_bytes())
    ok(hashlib.sha256(embedded).hexdigest() == CANONICAL_SHA256, "S4's bootstrap region is not canonical r1")
    canonical = BOOTSTRAP_DIR / "k4s_bootstrap_r1.py"
    if canonical.exists():
        ok(embedded == canonical.read_bytes(), "differs from bootstrap-r1/k4s_bootstrap_r1.py")


def test_layer_pins_match_the_vendored_file_and_the_old_loader_is_gone():
    s4 = load_s4("_s4_r5_pins")
    data = LAYER.read_bytes()
    ok(len(data) == s4.SAFE_INPUT_SIZE == 133606)
    ok(hashlib.sha256(data).hexdigest() == s4.SAFE_INPUT_SHA256)
    ok(s4.si.__k4s_bootstrap__ == ("k4s-bootstrap-r1", str(LAYER), s4.SAFE_INPUT_SHA256, s4.SAFE_INPUT_SIZE))
    ok(s4.si is sys.modules[s4.SAFE_INPUT_MODULE])
    text = S4_FILE.read_text()
    head = text[:text.index("si = load_safe_input()")]                # everything that runs before si exists
    ok("abspath(" not in head and "realpath(" not in head.replace("realpath is never called", ""))
    ok(head.count("os.open(") == 3 and head.count("os.read(") == 2, "only the bootstrap opens/reads before si exists")


ENTRY_FILES = {"assemble_fleet_reference.py": S4_FILE.read_bytes(), "safe_input.py": LAYER.read_bytes()}
SHA, SIZE = hashlib.sha256(ENTRY_FILES["safe_input.py"]).hexdigest(), len(ENTRY_FILES["safe_input.py"])
EPS = {
    "script": Entrypoint("s4-script", ENTRY_FILES, "assemble_fleet_reference.py", "safe_input.py", SHA, SIZE,
                         argv=["--help"], refusal_regex=r"^k4s bootstrap refused: "),
    "import": Entrypoint("s4-import", ENTRY_FILES, "assemble_fleet_reference.py", "safe_input.py", SHA, SIZE, mode="import",
                         module_name="_s4_r5_kit_import", refusal_regex=r"^k4s bootstrap refused: "),
}
CASES = [(kind, scenario) for kind, ep in EPS.items() for scenario in ep.scenarios()]


@pytest.mark.parametrize("kind,scenario", CASES)
def test_end_full_f1_alias_substitutions_before_bootstrap(tmp_path, kind, scenario):
    result = run_scenario(EPS[kind], scenario, str(tmp_path))
    check_scenario(result)
    outcome = result["report"]["outcome"]
    if result["scenario"].expect.startswith("refuse"):
        ok(outcome["kind"] == "exception" and outcome["type"] == "RuntimeError", outcome)    # S4's refusal convention
    elif kind == "script":
        ok("usage: assemble_fleet_reference.py" in result["proc"].stdout, result["proc"].stdout)


def test_post_hash_swap_to_a_same_size_edited_layer_runs_the_verified_bytes(tmp_path, monkeypatch):
    """A same-size layer with one constant edited (its fingerprint would refuse) is renamed over the path right
    after hashing: S4 still holds and runs the verified bytes, so its fingerprint check passes."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    layer = pkg / "safe_input.py"
    layer.write_bytes(LAYER.read_bytes())
    edited = LAYER.read_bytes().replace(b"7c9502037a75263dcfaaf5ab33666d2b8382a201",
                                        b"7c9502037a75263dcfaaf5ab33666d2b8382a200", 1)
    ok(len(edited) == SIZE and edited != LAYER.read_bytes())
    decoy = tmp_path / "decoy.py"
    decoy.write_bytes(edited)
    s4 = load_s4("_s4_r5_swap")
    real = s4.k4s_bootstrap_read_verified

    def read_then_swap(*args):
        data = real(*args)
        os.rename(str(decoy), str(layer))
        return data
    monkeypatch.setattr(s4, "k4s_bootstrap_read_verified", read_then_swap)
    module = s4.load_safe_input(str(layer))
    ok(module.constants_fingerprint() == s4.SAFE_INPUT_FINGERPRINT)
    ok(layer.read_bytes() == edited)                              # the path now names the edited bytes


def test_fingerprint_still_checked_after_the_bootstrap(tmp_path):
    s4 = load_s4("_s4_r5_fp")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    edited = LAYER.read_bytes().replace(b"7c9502037a75263dcfaaf5ab33666d2b8382a201",
                                        b"7c9502037a75263dcfaaf5ab33666d2b8382a200", 1)
    (pkg / "safe_input.py").write_bytes(edited)
    s4.SAFE_INPUT_SHA256 = hashlib.sha256(edited).hexdigest()       # pin moved; only the fingerprint can refuse
    with pytest.raises(RuntimeError, match="constants fingerprint differs"):
        s4.load_safe_input(str(pkg / "safe_input.py"))


def test_explicit_path_goes_through_the_same_gates(tmp_path):
    s4 = load_s4("_s4_r5_explicit")
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "safe_input.py").write_bytes(LAYER.read_bytes())
    with pytest.raises(RuntimeError, match=r"^k4s bootstrap refused: outcome name family games"):
        s4.load_safe_input(str(tmp_path / "games" / "safe_input.py"))
    os.symlink(str(LAYER.parent), str(tmp_path / "alias"))
    with pytest.raises(RuntimeError, match=r"^k4s bootstrap refused: ancestor 'alias' is a symlink"):
        s4.load_safe_input(str(tmp_path / "alias" / "safe_input.py"))
