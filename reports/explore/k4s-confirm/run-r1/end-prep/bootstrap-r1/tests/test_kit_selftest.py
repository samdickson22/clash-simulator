"""bootstrap-r1: the conformance kit run against (a) synthetic entrypoints that paste the canonical bootstrap, in all
three modes (run_path, import, the shell loader in-process), every scenario; and (b) negative controls: a verbatim
copy of the pre-r5 loader and, when present, the immutable S2/S4 r4b candidates. The kit must FLAG their canary
consumption (END-FULL-F1 reproduced), which shows the instrument is sensitive."""
import hashlib
import os

import pytest

from conftest import END_PREP, LOADER_FILE, SNIPPET_FILE, SI_FILE, ok
from k4s_bootstrap_kit import Entrypoint, KitFailure, check_scenario, run_scenario


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


LAYER = (b"MARK = \"verified\"\nVALUE = 42\n" + b"# padding so that the canary fits in the same size\n" * 40)
LAYER_SHA, LAYER_SIZE = hashlib.sha256(LAYER).hexdigest(), len(LAYER)

ENTRY_TAIL = """
LAYER_SHA256 = "%s"
LAYER_SIZE = %d
layer = k4s_bootstrap_load(k4s_bootstrap_default_path(__file__, "layer.py"), LAYER_SHA256, LAYER_SIZE,
                           "_kit_selftest_layer", RuntimeError)
if layer.MARK != "verified" or layer.VALUE != 42:
    raise SystemExit("WRONG LAYER EXECUTED")
if __name__ == "__main__":
    print("ENTRY OK")
""" % (LAYER_SHA, LAYER_SIZE)
ENTRY = read(SNIPPET_FILE) + ENTRY_TAIL.encode()

TOOL = (b"import sys\nif sys.argv[1:] != [\"a\", \"b c\"]:\n    raise SystemExit(\"argv not passed\")\n"
        b"if __name__ != \"__main__\":\n    raise SystemExit(\"not main\")\nprint(\"TOOL OK\")\n"
        + b"# tool padding so that the canary fits in the same size\n" * 30)
TOOL_SHA, TOOL_SIZE = hashlib.sha256(TOOL).hexdigest(), len(TOOL)

CANONICAL = {
    "run_path": Entrypoint("canonical-run-path", {"entry.py": ENTRY, "layer.py": LAYER}, "entry.py", "layer.py",
                           LAYER_SHA, LAYER_SIZE),
    "import": Entrypoint("canonical-import", {"entry.py": ENTRY, "layer.py": LAYER}, "entry.py", "layer.py",
                         LAYER_SHA, LAYER_SIZE, mode="import", module_name="_kit_selftest_entry"),
    "loader": Entrypoint("canonical-shell-loader", {"tool.py": TOOL}, "tool.py", "tool.py", TOOL_SHA, TOOL_SIZE,
                         argv=["a", "b c"], mode="loader", loader_file=LOADER_FILE),
}
CASES = [(mode, scenario) for mode, ep in CANONICAL.items() for scenario in ep.scenarios()]


@pytest.mark.parametrize("mode,scenario", CASES)
def test_canonical_bootstrap_meets_every_scenario(tmp_path, mode, scenario):
    result = run_scenario(CANONICAL[mode], scenario, str(tmp_path))
    check_scenario(result)
    if scenario == "control":
        ok(("ENTRY OK" if mode != "loader" else "TOOL OK") in result["proc"].stdout or mode == "import",
           result["proc"].stdout)


# ---------------------------------------------------------------- negative controls: the kit detects consumption

LEGACY = b'''import hashlib, os, stat, sys, types
SAFE_INPUT_SHA256 = "%s"


def load_safe_input(directory=None):
    path = os.path.join(directory or os.path.dirname(os.path.abspath(__file__)), "layer.py")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > 1 << 20:
            raise RuntimeError("legacy: not a single-link regular file")
        chunks, left = [], st.st_size
        while left:
            chunk = os.read(fd, left)
            if not chunk:
                raise RuntimeError("legacy: shrank")
            chunks.append(chunk)
            left -= len(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if hashlib.sha256(data).hexdigest() != SAFE_INPUT_SHA256:
        raise RuntimeError("legacy: is not the pinned layer")
    module = types.ModuleType("_legacy_layer")
    sys.modules["_legacy_layer"] = module
    exec(compile(data, path, "exec"), module.__dict__)
    return module


layer = load_safe_input()
''' % LAYER_SHA.encode()

LEGACY_EP = Entrypoint("legacy-r4b-style", {"entry.py": LEGACY, "layer.py": LAYER}, "entry.py", "layer.py",
                       LAYER_SHA, LAYER_SIZE, refusal_regex=r"legacy:", supports_swap=False)


@pytest.mark.parametrize("scenario,consumed", [
    ("ancestor-symlink", True), ("ancestor-symlink-high", True), ("ancestor-symlink-plain-target", True),
    ("outcome-named-ancestor:games", True),
    ("outcome-named-ancestor:Hub_Block", True), ("non-normalized-dot", True),
    # abspath() collapses hop/.. lexically, so the legacy loader reads the honest real/pkg layer although the kernel
    # ran the entry from games/pkg: no canary bytes, but it accepts a path it should refuse.
    ("non-normalized-dotdot-alias", False)])
def test_kit_flags_the_legacy_loader(tmp_path, scenario, consumed):
    """The pre-r5 loader (leaf-only O_NOFOLLOW on a full pathname) consumes the canary: the kit must say so."""
    result = run_scenario(LEGACY_EP, scenario, str(tmp_path))
    with pytest.raises(KitFailure, match=r"canary (inode opened|bytes consumed)|did not refuse|atime"):
        check_scenario(result)
    if not consumed:
        return
    ok(result["report"]["bytes"].get("canary", 0) > 0 or result["report"]["opens"].get("canary", 0) > 0)
    if result["atime_supported"] and "canary" in result["atime_moved"]:
        ok(result["atime_moved"]["canary"] is True, "the kernel atime instrument agrees")


R4B = {"s2": (END_PREP + "/s1s2-r4b/s2_end_evidence.py", "s2_end_evidence.py", r"is not the pinned safe_input r3"),
       "s4": (END_PREP + "/b3-r4b/assemble_fleet_reference.py", "assemble_fleet_reference.py",
              r"is not the pinned safe_input r3")}


@pytest.mark.parametrize("component", sorted(R4B))
def test_kit_reproduces_end_full_f1_on_the_r4b_candidates(tmp_path, component):
    source, name, refusal = R4B[component]
    if not os.path.exists(source):
        pytest.skip("immutable r4b candidate not present next to bootstrap-r1")
    layer = read(SI_FILE)
    ep = Entrypoint("r4b-" + component, {name: read(source), "safe_input.py": layer}, name, "safe_input.py",
                    hashlib.sha256(layer).hexdigest(), len(layer), argv=["--help"], refusal_regex=refusal,
                    supports_swap=False)
    result = run_scenario(ep, "ancestor-symlink", str(tmp_path))
    with pytest.raises(KitFailure, match=r"canary (inode opened|bytes consumed)"):
        check_scenario(result)
    ok(result["report"]["bytes"].get("canary") == len(layer), result["report"]["bytes"])
