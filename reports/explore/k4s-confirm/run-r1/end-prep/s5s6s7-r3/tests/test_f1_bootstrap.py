"""END-FULL-F1 (wrapper half and every Part B pre-confinement read), r3: adoption of the canonical bootstrap r1.

(1) The Python components (host tool, S5 preflight, S7 gate, S6 verifier) embed bootstrap-r1/k4s_bootstrap_r1.py
    byte for byte; both wrappers embed bootstrap-r1/k4s_bootstrap_shell_r1.sh byte for byte; the old loaders
    (read_pinned / module_from_bytes / test -f + sha256sum) are gone; the vendored kit is the canonical one.
(2) The bootstrap-r1 conformance kit (vendored byte-identical in tests/bootstrap_kit/) runs each Python loader in a
    fresh interpreter with every alias substituted BEFORE it starts (ancestor symlinks, leaf symlink, hard link,
    wrong sizes, same-size mismatching bytes, FIFO/dir leaf, non-normalized forms, outcome-named ancestors): zero
    canary opens/bytes (recorders + kernel atime), nothing executed; the control and the post-hash swap execute
    exactly the hashed bytes.
(3) Both wrappers, as real bash processes with the scenario's tools directory substituted for $base/tools: every
    alias scenario exits 90 before any tool call (no argv.nul, the command never starts, canary atime unmoved, no
    marker); a same-size mismatch is hashed but never executed; a host tool swapped for a decoy AFTER verification
    (by the wrapped command itself) is never executed by the later tool calls."""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import helpers as H
from helpers import ROOT, ok

KIT = H.HERE / "bootstrap_kit"
sys.path.insert(0, str(KIT))
from k4s_bootstrap_kit import Entrypoint, OUTCOME_DIR_NAMES, SCENARIOS, build, check_scenario, run_scenario  # noqa

CANONICAL = {"k4s_bootstrap_r1.py": "5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b",
             "k4s_bootstrap_loader_r1.py": "378c2b138677d7c8077fb24d25baff7decc54cea3b723949d5cb73bc31cf8332",
             "k4s_bootstrap_shell_r1.sh": "1ed816fa777c3121454796d18977f68a19bf824e5bd0d9c45adfc91225333f77"}
KIT_FILES = {"k4s_bootstrap_kit.py": "a1d2021c006b128b4ac60eaf6d9011c36268efd69d8fd478edf19326d856522f",
             "kit_harness.py": "57ffa09921225a769d5ea8d45015bad79e4bb7ad1ebbcb99855e0c05d1e32515"}
BOOTSTRAP_DIR = Path("/mpac/sdicks02/k4s-runner/run-r1/end-prep/bootstrap-r1")      # origin, when present
PY_BEGIN, PY_END = b"# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 ", b"# ==== END K4S CANONICAL BOOTSTRAP r1 ====\n"
SH_BEGIN = b"# ==== BEGIN K4S CANONICAL SHELL BOOTSTRAP r1 "
SH_END = b"# ==== END K4S CANONICAL SHELL BOOTSTRAP r1 ====\n"
PY_COMPONENTS = ("k4s_end_host_tool.py", "k4s_end_preflight.py", "k4s_end_launch_gate.py", "k4s_end_verify_push.py")
WRAPPERS = ("k4s_end_exit_push.sh", "k4s_preflight_push.sh")
SI = (ROOT / "safe_input.py").read_bytes()
HT = (ROOT / "k4s_end_host_tool.py").read_bytes()


def region(data, begin, end):
    ok(data.count(begin) == 1 and data.count(end) == 1, "exactly one canonical region")
    start = data.index(begin)
    ok(start == 0 or data[start - 1:start] == b"\n", "region starts a line")
    return data[start:data.index(end) + len(end)]


# ---------------------------------------------------------------- (1) static adoption

def test_vendored_kit_and_canonical_files_are_the_bootstrap_r1_bytes():
    for name, digest in dict(CANONICAL, **KIT_FILES).items():
        data = (KIT / name).read_bytes()
        ok(hashlib.sha256(data).hexdigest() == digest, name)
        origin = BOOTSTRAP_DIR / ("tests/" + name if name in KIT_FILES else name)
        if origin.exists():
            ok(origin.read_bytes() == data, "vendored copy differs from bootstrap-r1: " + name)


@pytest.mark.parametrize("name", PY_COMPONENTS)
def test_python_components_embed_the_canonical_region(name):
    data = (ROOT / name).read_bytes()
    ok(region(data, PY_BEGIN, PY_END) == (KIT / "k4s_bootstrap_r1.py").read_bytes(), name)
    text = data.decode()
    for gone in ("def read_pinned", "def module_from_bytes", "def load_module(", "os.path.realpath(path) != path"):
        ok(gone not in text, "%s still has the pre-r3 loader %r" % (name, gone))
    ok("k4s_bootstrap_load(" in text.split("# ==== END K4S CANONICAL BOOTSTRAP r1 ====", 1)[1], name)


@pytest.mark.parametrize("name", WRAPPERS)
def test_wrappers_embed_the_canonical_shell_fragment(name):
    data = (ROOT / name).read_bytes()
    ok(region(data, SH_BEGIN, SH_END) == (KIT / "k4s_bootstrap_shell_r1.sh").read_bytes(), name)
    text = data.decode()
    outside = text.replace(region(data, SH_BEGIN, SH_END).decode(), "")
    ok("sha256sum" not in outside and 'test -f "$host_tool"' not in outside, name)
    ok('"$python" -I -S "$host_tool"' not in text, "a tool() definition that opens the host tool by path remains")
    ok(text.count("\ntool() {") == 1, "the only tool() is the canonical one")
    pins = dict(line.split("=", 1) for line in outside.splitlines() if line.startswith("host_tool_s"))
    ok(pins == {"host_tool_sha": hashlib.sha256(HT).hexdigest(), "host_tool_size": str(len(HT))}, pins)
    ok(outside.index("host_tool_size=") < text.index(SH_BEGIN.decode()), "pins are set before the fragment")


def test_size_pins_match_the_layers():
    import k4s_end_launch_gate as G
    import k4s_end_preflight as S
    import k4s_end_host_tool as T
    ok(S.SAFE_INPUT_SIZE == G.SAFE_INPUT_SIZE == T.SAFE_INPUT_SIZE == len(SI))
    ok(S.HOST_TOOL_SIZE == G.HOST_TOOL_SIZE == len(HT))


# ---------------------------------------------------------------- (2) the kit against every Python loader

DRIVER = '''import importlib.util, os, sys
here = os.path.dirname(__file__)                       # as given: an alias or a non-normalized form stays visible
spec = importlib.util.spec_from_file_location("%(module)s", here + "/%(component)s")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.%(call)s
'''


def entrypoint(label, component, call, layer, needs_tool=False, refusal=r"k4s bootstrap refused"):
    """A kit Entrypoint running `call` of `component` loaded from the scenario directory. The kit's swap trigger is
    the FIRST "<k4s-bootstrap " compile; for the host-tool layer that is safe_input's compile (loaded first), so the
    decoy would replace the tool BEFORE it is hashed (refused by its SHA pin, never executed): swap-ok is run for
    the first-loaded layer only; the post-hash swap of the host tool is test_wrapper_never_executes_..."""
    files = {component: (ROOT / component).read_bytes(), "safe_input.py": SI,
             "drive.py": (DRIVER % dict(module="under_test_" + label, component=component, call=call)).encode()}
    if needs_tool:
        files["k4s_end_host_tool.py"] = HT
    data = files[layer]
    return Entrypoint(label, files, "drive.py", layer, hashlib.sha256(data).hexdigest(), len(data),
                      refusal_regex=refusal, supports_swap=layer == "safe_input.py")


EPS = {
    "host-tool:safe_input": entrypoint("ht", "k4s_end_host_tool.py", "load_safe_input()", "safe_input.py"),
    "preflight:safe_input": entrypoint("pf", "k4s_end_preflight.py", "load_layers()", "safe_input.py", True),
    "preflight:host_tool": entrypoint("pft", "k4s_end_preflight.py", "load_layers()", "k4s_end_host_tool.py", True),
    "gate:safe_input": entrypoint("lg", "k4s_end_launch_gate.py", "load_layers()", "safe_input.py", True),
    "gate:host_tool": entrypoint("lgt", "k4s_end_launch_gate.py", "load_layers()", "k4s_end_host_tool.py", True),
    "verifier:safe_input": entrypoint("ev", "k4s_end_verify_push.py", "load_si()", "safe_input.py"),
}
CASES = [(ep, sc) for ep in sorted(EPS) for sc in EPS[ep].scenarios()]


@pytest.mark.parametrize("ep,scenario", CASES, ids=["%s/%s" % c for c in CASES])
def test_python_loader_meets_every_kit_scenario(tmp_path, ep, scenario):
    if ep.startswith("verifier") and sys.flags.optimize:
        pytest.skip("the S6 verifier refuses optimized Python at import (T1 R3-1), before any bootstrap")
    check_scenario(run_scenario(EPS[ep], scenario, str(tmp_path)))


# ---------------------------------------------------------------- (3) the wrappers as real bash processes

TOOL_EP = Entrypoint("wrapper-tool", {"k4s_end_host_tool.py": HT, "safe_input.py": SI}, "k4s_end_host_tool.py",
                     "k4s_end_host_tool.py", hashlib.sha256(HT).hexdigest(), len(HT), mode="loader",
                     loader_file=str(KIT / "k4s_bootstrap_loader_r1.py"))
WRAPPER_SCENARIOS = [s for s in SCENARIOS if s != "swap-ok"] + ["outcome-named-ancestor:" + n for n in
                                                                  ("games", "Hub_Block", "x-complete.json.d")]


def held(paths):
    out = {}
    for label, path in paths.items():
        st = os.stat(path, follow_symlinks=False)
        if (st.st_mode & 0o170000) == 0o100000:
            os.utime(path, ns=(0, st.st_mtime_ns), follow_symlinks=False)
            out[label] = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    return out


def released(handles):
    moved = {label: os.fstat(fd).st_atime_ns != 0 for label, fd in handles.items()}
    for fd in handles.values():
        os.close(fd)
    return moved


def wrapper_harness(tmp, script, tools_dir):
    """test_s6_wrapper.Harness, plus ONE more substituted line: tools=<the scenario's tools directory>."""
    from test_s6_wrapper import Harness
    h = Harness(tmp / "w", script)
    text = h.wrapper.read_text()
    ok(text.count("\ntools=$base/tools\n") == 1)
    h.wrapper.write_text(text.replace("\ntools=$base/tools\n", "\ntools=%s\n" % tools_dir))
    h.tools = Path(tools_dir)                  # the preflight wrapper requires <tools>/k4s_end_preflight.py in argv
    return h


def run_wrapper(h, job):
    if h.script == "k4s_end_exit_push.sh":
        return h.run(job, h.end_argv(job))
    return h.run(job, h.preflight_argv(job), mode="preflight")


@pytest.mark.parametrize("script", WRAPPERS)
@pytest.mark.parametrize("scenario", WRAPPER_SCENARIOS)
def test_wrapper_bootstrap_meets_the_kit_scenarios(tmp_path, script, scenario):
    """Zero canary consumption before refusal for every alias of the host tool, in the wrapper itself."""
    root = tmp_path / "s"
    root.mkdir()
    sc = build(TOOL_EP, scenario, str(root))
    h = wrapper_harness(tmp_path, script, os.path.dirname(sc.layer_path))
    job = h.job()
    handles = held(sc.watch)
    done = run_wrapper(h, job)
    moved = released(handles)
    ok(not os.listdir(str(root / "markers")), "canary executed")
    if sc.expect == "ok":
        ok(done.returncode == 0 and (job / "argv.nul").is_file(), (done.returncode, done.stderr[-2000:]))
        ok(moved.get("layer") is True, "atime instrument did not see the control read")
        return
    ok(done.returncode == 90 and "k4s bootstrap refused" in done.stderr, (done.returncode, done.stderr[-2000:]))
    ok(not (job / "argv.nul").exists() and not (job / job.name).exists() and not (job / "exit.json").exists())
    if sc.expect == "refuse-unread":
        ok(moved.get("canary", False) is False, "kernel atime shows the canary was read")
    else:
        ok(sc.expect == "refuse-after-hash" and "SHA-256" in done.stderr, done.stderr)


SWAP_PRODUCER = '''import os, sys
tool, decoy = os.environ["SWAP_TOOL"], os.environ["SWAP_DECOY"]
os.rename(decoy, tool)                                  # after the wrapper verified and used the real host tool
sys.exit(0)
'''


@pytest.mark.parametrize("script", WRAPPERS)
def test_wrapper_never_executes_a_host_tool_swapped_after_verification(tmp_path, script):
    """Every tool() call re-walks, re-gates and re-hashes, then runs the verified bytes: a same-size decoy renamed
    over the host tool by the wrapped command (after verification and after the argv.nul tool call) is hashed and
    refused, never executed; the wrapper fails closed."""
    from k4s_bootstrap_kit import make_canary
    w = wrapper_harness(tmp_path, script, str(tmp_path / "w" / "hostfs03" / "k4s-end-r1" / "tools"))
    job = w.job()
    markers = tmp_path / "markers"
    markers.mkdir()
    decoy = H.write(tmp_path / "w" / "hostfs03" / "k4s-end-r1" / "decoy-tool.py",
                    make_canary(len(HT), str(markers / "decoy-executed"), HT))
    producer = H.write(tmp_path / "swap_producer.py", SWAP_PRODUCER)
    argv = (w.end_argv(job) if script == "k4s_end_exit_push.sh" else w.preflight_argv(job))
    i = argv.index(str(Path(__file__).resolve().parent / "fake_producer.py"))
    argv[i] = str(producer)
    e = H.shim_env(w.tmp, FAKE_HOST=w.host, FAKE_MODE="complete", HOME=w.tmp / "home",
                   SWAP_TOOL=w.tools / "k4s_end_host_tool.py", SWAP_DECOY=decoy)
    done = H.run(["bash", w.wrapper, job, *argv], e)
    ok((job / "argv.nul").is_file(), "the first tool call (argv.nul) ran with the verified tool")
    ok(not (markers / "decoy-executed").exists(), "the swapped-in decoy was EXECUTED")
    ok(done.returncode != 0 and "k4s bootstrap refused" in done.stderr and "SHA-256" in done.stderr,
       (done.returncode, done.stderr[-2000:]))
