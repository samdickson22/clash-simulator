"""Reusable END-FULL-F1 conformance kit (bootstrap-r1). Stdlib only; Python 3.8+; no assert (holds under -O).

Describe an entrypoint once, then run every alias scenario against it. Each scenario builds a fresh synthetic tree,
substitutes the alias BEFORE the entrypoint starts, identifies the canary/decoy/layer inodes, sets their atime to the
epoch, and runs the entrypoint in a fresh interpreter under kit_harness.py (read/open recorders installed first).
The verdict combines three independent signals: the harness recorders (opens and bytes per watched inode), the
kernel atime of every watched regular file (a read moves it), and execution markers (canary and decoy bytes create
a marker file if they are ever executed).

    from k4s_bootstrap_kit import Entrypoint, SCENARIOS, run_scenario, check_scenario
    EP = Entrypoint("s2", files={"s2_end_evidence.py": src, "safe_input.py": layer}, entry="s2_end_evidence.py",
                    layer="safe_input.py", sha256=PIN, size=SIZE, argv=["--help"], refusal_regex="k4s bootstrap refused")
    @pytest.mark.parametrize("scenario", EP.scenarios())
    def test_f1(tmp_path, scenario):
        check_scenario(run_scenario(EP, scenario, str(tmp_path)))

Expectations per scenario:
  ok                 control: success; the layer inode opened exactly once and read exactly SIZE bytes whose
                     SHA-256 is the pin; a bootstrapped module records (path, pin, size)
  swap-ok            ok, and the decoy renamed over the layer path right after hashing never runs, is never opened
  refuse-unread      refused (refusal_regex); canary inode never opened, zero bytes, atime unchanged, no marker
  refuse-after-hash  same-size mismatching bytes at the true path: refused by the SHA pin; read once (exactly SIZE
                     bytes from one descriptor), never executed (no marker)
"""
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "kit_harness.py")
OUTCOME_DIR_NAMES = ("games", "GAMES", "Games.d", "hub-blocks", "Hub_Block", "old.hubblocks",
                     "x-complete.json.d", "Interference.JSON.old", "hub.ack.json", "END-RAW.json.bak", "gameſ")


class KitFailure(AssertionError):
    pass


def ok(condition, message):
    if not condition:
        raise KitFailure(message)


class Entrypoint:
    """One entrypoint under test.

    files      {relative name: bytes} placed in the package directory (entry, layer and any siblings it needs)
    entry      relative name of the program run (mode run_path/import); for mode loader it is the pinned tool itself
    layer      relative name of the pinned file the bootstrap reads (for mode loader: the tool, == entry)
    sha256/size  the pins the entrypoint (or loader call) carries
    mode       run_path | import | loader
    module_name  for mode import
    loader_file  for mode loader: the canonical shell loader program (k4s_bootstrap_loader_r1.py)
    ok_outcome   callable(report) -> bool for the control (default: returned, or exit code 0/None)
    refusal_regex  must match the refusal text (exception message, SystemExit text or stderr)
    supports_swap  the entrypoint uses the canonical bootstrap (the swap trigger is its "<k4s-bootstrap " compile)
    env        extra environment for the run
    """

    def __init__(self, name, files, entry, layer, sha256, size, argv=(), mode="run_path", module_name=None,
                 loader_file=None, ok_outcome=None, refusal_regex=r"k4s bootstrap refused", supports_swap=True,
                 env=None, outcome_dir_names=OUTCOME_DIR_NAMES):
        ok(mode in ("run_path", "import", "loader"), "unknown mode " + repr(mode))
        ok(entry in files and layer in files, "entry and layer must be in files")
        ok(mode != "loader" or (entry == layer and loader_file), "mode loader runs the pinned tool itself")
        self.name, self.files, self.entry, self.layer = name, dict(files), entry, layer
        self.sha256, self.size, self.argv, self.mode = sha256, size, list(argv), mode
        self.module_name, self.loader_file = module_name, loader_file
        self.ok_outcome = ok_outcome or default_ok
        self.refusal_regex, self.supports_swap, self.env = refusal_regex, supports_swap, dict(env or {})
        self.outcome_dir_names = tuple(outcome_dir_names)

    def scenarios(self):
        names = [s for s in SCENARIOS if s != "swap-ok" or self.supports_swap]
        return names + ["outcome-named-ancestor:" + n for n in self.outcome_dir_names]


def default_ok(report):
    o = report["outcome"]
    return o["kind"] == "returned" or (o["kind"] == "exit" and o.get("code") in (0, None))


SCENARIOS = ("control", "swap-ok", "ancestor-symlink", "ancestor-symlink-high", "ancestor-symlink-plain-target",
             "leaf-symlink",
             "leaf-symlink-pinned-bytes", "hard-link", "hard-link-pinned-bytes", "wrong-size-larger",
             "wrong-size-smaller", "same-size-mismatch", "fifo-leaf", "dir-leaf", "non-normalized-dotdot-alias",
             "non-normalized-dot", "non-normalized-double-slash")


def make_canary(size, marker, avoid):
    """Bytes of exactly `size`, different from `avoid`, that create `marker` and stop if they are ever executed."""
    code = ("import os\nos.close(os.open(%r, os.O_WRONLY | os.O_CREAT, 0o600))\n"
            "raise SystemExit(\"K4S CANARY EXECUTED\")\n" % marker).encode()
    if size >= len(code) + 2:
        data = code + b"#" * (size - len(code) - 1) + b"\n"
    else:
        data = bytes(b ^ 1 for b in avoid[:size]) + b"#" * max(0, size - len(avoid))
    ok(len(data) == size and data != avoid, "canary construction")
    return data


def write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def populate(directory, files, override=None):
    os.makedirs(directory)
    for rel, data in files.items():
        if override and rel in override:
            continue
        write(os.path.join(directory, rel), data)


class Scenario:
    def __init__(self, name, expect, entry_path, layer_path, watch, swap=None):
        self.name, self.expect, self.entry_path, self.layer_path = name, expect, entry_path, layer_path
        self.watch, self.swap = watch, swap


def build(ep, name, root):
    """Create scenario `name` under the fresh directory `root`; return a Scenario (nothing is run)."""
    real, synth, markers = root + "/real", root + "/synth", root + "/markers"
    os.makedirs(real)
    os.makedirs(markers)
    layer_bytes = ep.files[ep.layer]
    canary = make_canary(ep.size, markers + "/canary-executed", layer_bytes)
    pkg = real + "/pkg"
    games_pkg = synth + "/games/pkg"
    if name == "control":
        populate(pkg, ep.files)
        return Scenario(name, "ok", pkg + "/" + ep.entry, pkg + "/" + ep.layer, {"layer": pkg + "/" + ep.layer})
    if name == "swap-ok":
        populate(pkg, ep.files)
        decoy = real + "/decoy-" + ep.layer
        write(decoy, make_canary(ep.size, markers + "/decoy-executed", layer_bytes))
        return Scenario(name, "swap-ok", pkg + "/" + ep.entry, pkg + "/" + ep.layer,
                        {"layer": pkg + "/" + ep.layer, "decoy": decoy}, swap={"decoy": decoy, "layer": pkg + "/" + ep.layer})
    if name == "ancestor-symlink-plain-target":                    # no outcome name anywhere: only the walk can refuse
        plain_pkg = synth + "/plain/pkg"
        populate(plain_pkg, ep.files, override={ep.layer})
        write(plain_pkg + "/" + ep.layer, canary)
        populate(pkg, ep.files)
        os.symlink(plain_pkg, real + "/alias")
        return Scenario(name, "refuse-unread", real + "/alias/" + ep.entry, real + "/alias/" + ep.layer,
                        {"canary": plain_pkg + "/" + ep.layer})
    if name in ("ancestor-symlink", "ancestor-symlink-high", "non-normalized-dotdot-alias"):
        populate(games_pkg, ep.files, override={ep.layer})
        write(games_pkg + "/" + ep.layer, canary)
        os.makedirs(synth + "/games/sub")
        populate(pkg, ep.files)                                    # the honest package also exists, untouched
        if name == "ancestor-symlink":
            os.symlink(games_pkg, real + "/alias")
            base = real + "/alias"
        elif name == "ancestor-symlink-high":
            os.symlink(synth + "/games", real + "/up")
            base = real + "/up/pkg"
        else:                                                      # lexically real/pkg; the kernel: games/pkg
            os.symlink(synth + "/games/sub", real + "/hop")
            base = real + "/hop/../pkg"
        return Scenario(name, "refuse-unread", base + "/" + ep.entry, base + "/" + ep.layer,
                        {"canary": games_pkg + "/" + ep.layer})
    if name in ("leaf-symlink", "leaf-symlink-pinned-bytes", "hard-link", "hard-link-pinned-bytes"):
        os.makedirs(synth + "/games")
        target = synth + "/games/" + ep.layer
        write(target, layer_bytes if name.endswith("pinned-bytes") else canary)
        populate(pkg, ep.files, override={ep.layer})
        if name.startswith("leaf-symlink"):
            os.symlink(target, pkg + "/" + ep.layer)
        else:
            os.link(target, pkg + "/" + ep.layer)
        return Scenario(name, "refuse-unread", pkg + "/" + ep.entry, pkg + "/" + ep.layer, {"canary": target})
    if name in ("wrong-size-larger", "wrong-size-smaller", "same-size-mismatch"):
        populate(pkg, ep.files, override={ep.layer})
        size = {"wrong-size-larger": ep.size + 1, "wrong-size-smaller": ep.size - 1, "same-size-mismatch": ep.size}[name]
        write(pkg + "/" + ep.layer, make_canary(size, markers + "/canary-executed", layer_bytes))
        expect = "refuse-after-hash" if name == "same-size-mismatch" else "refuse-unread"
        return Scenario(name, expect, pkg + "/" + ep.entry, pkg + "/" + ep.layer, {"canary": pkg + "/" + ep.layer})
    if name in ("fifo-leaf", "dir-leaf"):
        populate(pkg, ep.files, override={ep.layer})
        if name == "fifo-leaf":
            os.mkfifo(pkg + "/" + ep.layer)
        else:
            os.mkdir(pkg + "/" + ep.layer)
            write(pkg + "/" + ep.layer + "/inside", canary)
        return Scenario(name, "refuse-unread", pkg + "/" + ep.entry, pkg + "/" + ep.layer, {"canary": pkg + "/" + ep.layer})
    if name in ("non-normalized-dot", "non-normalized-double-slash"):
        populate(pkg, ep.files)                                    # correct bytes; the path form alone must refuse
        base = real + ("/./pkg" if name == "non-normalized-dot" else "//pkg")
        return Scenario(name, "refuse-unread", base + "/" + ep.entry, base + "/" + ep.layer, {"canary": pkg + "/" + ep.layer})
    if name.startswith("outcome-named-ancestor:"):
        directory = root + "/" + name.split(":", 1)[1] + "/pkg"
        populate(directory, ep.files)                              # pinned bytes; the name alone must refuse
        return Scenario(name, "refuse-unread", directory + "/" + ep.entry, directory + "/" + ep.layer,
                        {"canary": directory + "/" + ep.layer})
    raise KitFailure("unknown scenario " + name)


def ident(path):
    st = os.stat(path, follow_symlinks=False)
    return [st.st_dev, st.st_ino]


def atime_supported(directory):
    probe = directory + "/atime-probe"
    write(probe, b"probe\n")
    st = os.stat(probe)
    os.utime(probe, ns=(0, st.st_mtime_ns))
    with open(probe, "rb") as handle:
        handle.read()
    moved = os.stat(probe).st_atime_ns != 0
    os.unlink(probe)
    return moved


def run_scenario(ep, name, workdir, python=None, optimize=None, timeout=180):
    """Build and run one scenario in `workdir` (a fresh, empty, writable directory). Returns a result dict."""
    python = python or sys.executable
    optimize = bool(sys.flags.optimize) if optimize is None else optimize
    root = os.path.join(workdir, "scenario")
    os.makedirs(root)
    sc = build(ep, name, root)
    watch_ids = {label: ident(path) for label, path in sc.watch.items()}
    regular = {label: path for label, path in sc.watch.items()
               if __import__("stat").S_ISREG(os.stat(path, follow_symlinks=False).st_mode)}
    atime_ok = atime_supported(workdir)
    handles = {}                                    # O_PATH: keeps the inode for a post-run fstat, never reads it
    for label, path in regular.items():
        st = os.stat(path, follow_symlinks=False)
        os.utime(path, ns=(0, st.st_mtime_ns), follow_symlinks=False)
        handles[label] = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    report_path = os.path.join(workdir, "report.json")
    spec = {"mode": ep.mode, "entry": sc.entry_path, "argv": ep.argv, "module_name": ep.module_name,
            "watch": watch_ids, "report": report_path, "swap": sc.swap, "loader_file": ep.loader_file,
            "layer": sc.layer_path, "sha256": ep.sha256, "size": ep.size}
    spec_path = os.path.join(workdir, "spec.json")
    with open(spec_path, "w", encoding="utf-8") as handle:
        json.dump(spec, handle)
    argv = [python] + (["-O"] if optimize else []) + ["-B", "-I"] + (["-S"] if ep.mode == "loader" else [])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **ep.env)
    try:
        proc = subprocess.run(argv + [HARNESS, spec_path], capture_output=True, text=True, timeout=timeout,
                              cwd=workdir, env=env, stdin=subprocess.DEVNULL)
        atime = {label: os.fstat(fd).st_atime_ns != 0 for label, fd in handles.items()}
    finally:
        for fd in handles.values():
            os.close(fd)
    ok(proc.returncode == 0 and os.path.exists(report_path),
       "harness failed rc=%s\n%s\n%s" % (proc.returncode, proc.stdout[-3000:], proc.stderr[-3000:]))
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    markers = sorted(os.listdir(root + "/markers"))
    return {"ep": ep, "scenario": sc, "report": report, "proc": proc, "atime_moved": atime,
            "atime_supported": atime_ok, "markers": markers, "optimize": optimize}


def refusal_text(result):
    o = result["report"]["outcome"]
    return " ".join(str(x) for x in (o.get("message"), o.get("code"), result["proc"].stderr))


def check_scenario(result):
    """Raise KitFailure unless the result meets its scenario's expectation (see module docstring)."""
    ep, sc, report = result["ep"], result["scenario"], result["report"]
    tag = "%s/%s: " % (ep.name, sc.name)
    ok(report["optimize"] == (1 if result["optimize"] else 0), tag + "interpreter optimize flag not as requested")
    opens, nbytes = report["opens"], report["bytes"]
    ok(not result["markers"], tag + "canary/decoy bytes were EXECUTED: %s" % result["markers"])
    if sc.expect in ("ok", "swap-ok"):
        ok(ep.ok_outcome(report), tag + "control did not succeed: %s %s" % (report["outcome"], result["proc"].stderr[-2000:]))
        ok(opens.get("layer") == 1, tag + "layer inode opened %s times (want exactly 1)" % opens.get("layer"))
        ok(nbytes.get("layer") == ep.size, tag + "layer bytes read %s (want exactly %d)" % (nbytes.get("layer"), ep.size))
        ok(report["read_sha256"].get("layer") == ep.sha256, tag + "bytes read from the layer inode are not the pin")
        tagged = [m for m in report["bootstrapped_modules"] if m[2] == sc.layer_path and m[3] == ep.sha256 and m[4] == ep.size]
        ok(len(tagged) >= 1, tag + "no bootstrapped module records (path, pin, size): %s" % report["bootstrapped_modules"])
        if result["atime_supported"]:
            ok(result["atime_moved"].get("layer") is True, tag + "atime instrument did not see the control read")
        if sc.expect == "swap-ok":
            ok(report["swapped"] is True, tag + "the post-hash swap never triggered")
            ok(opens.get("decoy", 0) == 0 and nbytes.get("decoy", 0) == 0, tag + "decoy consumed after the swap")
        return
    ok(not ep.ok_outcome(report), tag + "entrypoint did not refuse: %s" % report["outcome"])
    ok(re.search(ep.refusal_regex, refusal_text(result)) is not None,
       tag + "refusal text does not match %r: %s" % (ep.refusal_regex, refusal_text(result)[-2000:]))
    if sc.expect == "refuse-unread":
        ok(opens.get("canary", 0) == 0, tag + "canary inode opened %d times" % opens.get("canary", 0))
        ok(nbytes.get("canary", 0) == 0, tag + "canary bytes consumed: %d" % nbytes.get("canary", 0))
        if result["atime_supported"] and "canary" in result["atime_moved"]:
            ok(result["atime_moved"]["canary"] is False, tag + "kernel atime shows the canary was read")
    elif sc.expect == "refuse-after-hash":
        ok(opens.get("canary") == 1 and nbytes.get("canary") == ep.size,
           tag + "same-size mismatch must be read once, exactly SIZE bytes: opens=%s bytes=%s"
           % (opens.get("canary"), nbytes.get("canary")))
    else:
        raise KitFailure(tag + "unknown expectation " + sc.expect)


def file_sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()
