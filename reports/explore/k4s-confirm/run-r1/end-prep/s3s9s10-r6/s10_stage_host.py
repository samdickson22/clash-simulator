#!/usr/bin/env python3
"""S10 (PREREG-K4S END, A2 staging): ship END inputs from 127x05 to ONE host. r2: safe_input adoption. r3:
siblings through the canonical bootstrap (END-FULL-F1); S9.verify / S3.verify run the live full-clone check (F4) before
any login. CANDIDATE:
host-touching; Sol review and a coordinator A2 GO before any live run. Never inside an END timing window or a
preflight measurement on any host.

Components (at least one; bundles only, never raw Q6 inputs: ruling P2 decision 4):
  --runtime S9OUT --runtime-manifest-sha256 S   the S9 runtime (re-verified)   -> <base>/runtime/runtime-<commit12>/
  --bundle DIR TIERS_PINS_SHA256 RECEIPT_SHA256  an S4 fleet-reference bundle (repeatable; production only)
                                                                                -> <base>/bundles/<basename>/
  --guard-job S3OUT --guard-job-name NAME --guard-manifest-sha256 S   an S3 guard job (re-verified)
                                                                                -> its Q4 target (separate parent)
with <base> = si.END_BASES (03 /mpac/sdicks02/jobs/clasher/k4s-end-r1, 04 /mpac/sdicks02/jobs-k4s/k4s-end-r1: the
S5/S6/S7 bases, S10-F2) holding attempts/, preflight/, repository/, runtime/, bundles/ (RC-6; --print-roots). S10
creates <base> with attempts/ preflight/ runtime/ bundles/ only when told (--create-base, first staging on a host);
repository/ is provisioned by its own authorized step. Guard jobs are siblings under the Q4 parent, never in <base>.

Local side, before any login: every read through safe_input roles (canonical roots, names gated before any syscall,
component-wise no-follow, st_nlink == 1, expected SHAs): S9.verify (manifest pinned), S3.verify (manifest pinned),
and per bundle: tiers-pins.json / tiers-pins.sha256 / assembly-receipt.json read with expected SHAs, S4 test-only
bundles refused (k4s_s4_synthetic, SYNTHETIC-TEST-ONLY, production_pins != true, *SYNTHETIC* names: S10-F4), every
file hashed and equal to its pin, production identities, per-host admissions, runtime/measurement consistency with
the staged (or --runtime-manifest-for-checks) runtime, and guard-job byte equality when its guard job is staged too.

Logins (each `ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none ...`, recorded):
  P-check   si.remote_check (pinned reader): <base> and its four subdirs (or, with --create-base, <base> absent) and
            the Q4 parent are canonical directories (every ancestor lstat'ed: no symlink); every target and its
            .partial absent.
  P-facts   hostname, df, who, each captured with its own exit status (`x=$(cmd)`; `@@RC|name|$?`); any nonzero
            status refuses before its output is used (S10-F3); free space >= bytes + 50 GiB.
  [base]    --create-base only: si.remote_receive creating <base> exclusively with the four subdirs, no files.
  R-<i>     one si.remote_receive per component (D4): the pinned receive program (bootstrap-verified SHA-256) creates
            <target>.partial EXCLUSIVELY under its canonical parent, then every directory (mkdirat) and file
            (O_CREAT|O_EXCL|O_NOFOLLOW, streamed, hashed, fsynced, mode 0444/0555); refuses an existing name of any
            kind, a symlinked ancestor, a name family, a size/SHA mismatch or extra bytes; its receipt (every file's
            size, SHA-256, st_nlink == 1, mode) is validated strictly (R7: plain single-link copies).
  F         ONE session: the pinned reader re-checks every .partial is a canonical directory and every final name is
            absent; then (runtime/bundles) `chmod -R a-w` and `mv -n -T` each .partial into place, every step's
            status echoed and checked. The reader-to-mv window is the accepted residual.
  POST      si.remote_check: every final is a canonical directory with the SAME dev/ino the F check saw for its
            .partial (and mode a-w for runtime/bundles); every .partial absent.
Nothing is ever deleted on a host (no rm/rmdir/unlink anywhere). A refusal after the first receive records the exact
.partial roots in the record's S10-REFUSAL-*.json; their cleanup needs a separately authorized step.
"""
import argparse
import json
import os
import re
import shlex
import sys

# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 (bootstrap-r1/k4s_bootstrap_r1.py; paste verbatim, byte for byte) ====
# END-FULL-F1. The only way a K4S END component may read a pinned stdlib-loaded file (its vendored safe_input layer,
# or a host tool) before the shared layer exists. Stdlib only, Python 3.8+, Linux, no assert (holds under -O), no
# single-quote character (so the same text can sit inside a single-quoted shell word). Contract, in order:
#   1. the path is absolute and already normalized (normpath(p) == p; no empty, "." or ".." component, no trailing
#      slash, no control or backslash character). Nothing is canonicalized: realpath is never called;
#   2. every component (ancestors and leaf) passes the safe_input r3 OUTCOME name families (casefolded fullmatch,
#      the same regex literals; conformance-tested against si.outcome_family);
#   3. a component-wise walk from "/": each ancestor is opened O_DIRECTORY|O_NOFOLLOW relative to its parent fd and
#      fstat must say directory (a symlink, a non-directory or a missing ancestor refuses);
#   4. the leaf is fstatat-ed without following (regular, st_nlink == 1, exactly the pinned size) BEFORE it is opened,
#      then opened O_NOFOLLOW|O_NONBLOCK relative to the parent fd and fstat-ed again (same dev/ino, regular,
#      st_nlink == 1, pinned size) BEFORE any byte is read;
#   5. exactly the pinned size is read from THAT descriptor, EOF is confirmed, the SHA-256 must equal the pin, and
#      exactly those bytes are compiled and executed in a fresh module registered under the caller-given name. The
#      code object is compiled under a "<k4s-bootstrap ...>" filename (linecache is given the verified lines) so no
#      traceback, import or inspect call ever re-opens the path after hashing;
#   6. every refusal is `raise refusal(message)`, the caller-chosen refusal convention (an exception class, or a
#      callable returning the exception to raise).
K4S_BOOTSTRAP_RELEASE = "k4s-bootstrap-r1"
K4S_BOOTSTRAP_OUTCOME_FAMILIES = (                      # == safe_input r3 OUTCOME_FAMILIES (literal copy, tested)
    ("games", r"(?:.*[^a-z])?" + r"games" + r"(?:[^a-z].*)?"),
    ("hub-blocks", r"(?:.*[^a-z])?" + r"hub[-_.]?blocks?" + r"(?:[^a-z].*)?"),
    ("complete-json", r".*complete.*\.json.*"),
    ("interference-json", r".*interference.*\.json.*"),
    ("hub-ack-json", r".*hub[-_.]?ack.*\.json.*"),
    ("end-raw-json", r".*end[-_.]?raw.*\.json.*"),
)
K4S_BOOTSTRAP_MAX_SIZE = 1 << 24


def k4s_bootstrap_name_family(component):
    """The OUTCOME family label of one path component (casefolded fullmatch), or None."""
    import re
    folded = component.casefold()
    for label, rx in K4S_BOOTSTRAP_OUTCOME_FAMILIES:
        if re.fullmatch(rx, folded, re.S):
            return label
    return None


def k4s_bootstrap_default_path(module_file, leaf):
    """The sibling `leaf` of `module_file`, made absolute without resolving or normalizing anything: an alias or a
    non-normalized __file__ stays visible, so the walk refuses it."""
    import os
    directory = os.path.dirname(module_file)
    if not directory.startswith("/"):
        directory = os.getcwd() + ("/" + directory if directory else "")
    return directory + "/" + leaf


def k4s_bootstrap_read_verified(path, sha256, size, refusal):
    """Steps 1-5 up to the hash: return exactly the pinned bytes, or raise refusal(message) having read nothing that
    fails a name, walk or descriptor gate."""
    import hashlib
    import os
    import stat

    def refused(reason):
        return refusal("k4s bootstrap refused: " + reason + ": " + repr(path))

    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise refused("the SHA-256 pin is not 64 lowercase hex digits")
    if type(size) is not int or not 0 < size <= K4S_BOOTSTRAP_MAX_SIZE:
        raise refused("the size pin is not an int in 1..%d" % K4S_BOOTSTRAP_MAX_SIZE)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or path.endswith("/")
            or os.path.normpath(path) != path):
        raise refused("not an absolute normalized path")
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise refused("control or backslash character in the path")
    parts = path[1:].split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise refused("empty, . or .. component")
    for p in parts:
        family = k4s_bootstrap_name_family(p)
        if family is not None:
            raise refused("outcome name family " + family + " in component " + repr(p))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise refused("/ is not a directory")
        for name in parts[:-1]:
            try:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            except OSError as error:
                raise refused("ancestor " + repr(name) + " is a symlink, not a directory or missing ("
                              + os.strerror(error.errno) + ")")
            previous, fd = fd, child
            os.close(previous)
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise refused("ancestor " + repr(name) + " is not a directory")
        leaf = parts[-1]
        try:
            before = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as error:
            raise refused("leaf cannot be inspected (" + os.strerror(error.errno) + ")")
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise refused("leaf is not a single-link regular file of the pinned size %d" % size)
        try:
            leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC,
                              dir_fd=fd)
        except OSError as error:
            raise refused("leaf cannot be opened without following (" + os.strerror(error.errno) + ")")
        try:
            info = os.fstat(leaf_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size
                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
                raise refused("opened leaf is not the inspected single-link regular file of the pinned size")
            chunks, left = [], size
            while left > 0:
                chunk = os.read(leaf_fd, left)
                if not chunk:
                    raise refused("leaf shrank while read")
                chunks.append(chunk)
                left -= len(chunk)
            if os.read(leaf_fd, 1) != b"":
                raise refused("leaf grew while read")
        finally:
            os.close(leaf_fd)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise refused("bytes are not the pinned SHA-256 " + sha256)
    return data


def k4s_bootstrap_exec(data, path, sha256, module_name):
    """Step 5 tail: compile and execute exactly `data` (already verified) in a fresh module named `module_name`."""
    import linecache
    import sys
    import types
    filename = "<k4s-bootstrap sha256=" + sha256 + " " + path + ">"
    linecache.cache[filename] = (len(data), None, data.decode("utf-8", "replace").splitlines(True), filename)
    code = compile(data, filename, "exec", dont_inherit=True)
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__k4s_bootstrap__ = (K4S_BOOTSTRAP_RELEASE, path, sha256, len(data))
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def k4s_bootstrap_load(path, sha256, size, module_name, refusal):
    """Read `path` through the full contract and execute exactly the verified bytes as module `module_name`."""
    data = k4s_bootstrap_read_verified(path, sha256, size, refusal)
    return k4s_bootstrap_exec(data, path, sha256, module_name)
# ==== END K4S CANONICAL BOOTSTRAP r1 ====


# END-FULL-F1: the pins (SHA-256, size) of the sibling files this module loads, maintained by tests/k4s_adopt.py in
# dependency order (safe_input <- end_prep_common <- s9 <- s1b <- s3 <- s10). A pin covers the file's bytes.
K4S_SIBLING_PINS = {
    'end_prep_common.py': ('2a84775bfb1365b885cb3944840e631a41eac76243558de41cc234d8ba59b877', 22617),
    's3_guard_job.py': ('776ded238be655f4f9ef84ec217afbcd214c73a186baad009d0d4fa2f53bb8ce', 38873),
    's9_end_runtime.py': ('bdc2deeb96bf60a16b8877ffa2038760673d60bb63edcde8d947195fdfdcf3a7', 84364),
}


def _k4s_common():
    """end_prep_common.py beside this file through the canonical bootstrap (never a sys.path import): its path as
    Python was given it (aliases stay visible to the walk), its pins; an already loaded end_prep_common is reused only
    if the bootstrap loaded it from that path with those pins."""
    path = k4s_bootstrap_default_path(__file__, "end_prep_common.py")
    sha256, size = K4S_SIBLING_PINS["end_prep_common.py"]
    existing = sys.modules.get("end_prep_common")
    if existing is not None:
        if getattr(existing, "__k4s_bootstrap__", None) != (K4S_BOOTSTRAP_RELEASE, path, sha256, size):
            raise SystemExit("k4s bootstrap refused: a different end_prep_common module is already loaded (want %s %s)"
                             % (path, sha256))
        return existing
    return k4s_bootstrap_load(path, sha256, size, "end_prep_common", SystemExit)


C = _k4s_common()
S3 = C.load_sibling("s3_guard_job", *K4S_SIBLING_PINS["s3_guard_job.py"])
S9 = C.load_sibling("s9_end_runtime", *K4S_SIBLING_PINS["s9_end_runtime.py"])

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-staging.v3"
# r4 (B7/U9): the RC-6 declaration S7 consumes, exactly (k4s_end_launch_gate.py:85 ROOTS_SCHEMA, :305-331 validate_roots)
ROOTS_SCHEMA = "clasher.k4s.end-roots-declaration.v1"
ROOTS_KEYS = ("attempts", "base", "bundles", "guard_parent", "preflight", "repository", "runtime", "tools")
HOSTS = ("127x03", "127x04")
END_BASES = dict(si.END_BASES)
GUARD_PARENTS = dict(si.Q4_GUARD_PARENTS)
# r4 (B2): the runtime is <base>/runtime-<P12> (S5 layout() k4s_end_preflight.py:403-405; S7 RC-6 :319-320), not a
# subdirectory; tools/ (U2) and end-inputs-r1/ (U3) are components S10 stages whole; repository/ is S11's (U1).
BASE_SUBDIRS = ("attempts", "preflight", "bundles")                 # created with <base> (--create-base)
RUNTIME_PREFIX = "runtime-"
TOOLS_LEAF = "tools"
END_INPUTS_LEAF = "end-inputs-r1"
HEADROOM = 50 * 1024 ** 3
SSH_BINARY = si.SSH_BINARY
REMOTE_TOOLS = {"hostname": "/usr/bin/hostname", "df": "/usr/bin/df", "who": "/usr/bin/who",
                "chmod": "/usr/bin/chmod", "mv": "/usr/bin/mv", "sh": "/bin/sh", "env": "/usr/bin/env",
                "nice": "/usr/bin/nice"}
# r4 (U2): <base>/tools/ holds EXACTLY the files the s5s6s7-r4 S7 pins and runs (k4s_end_launch_gate.py:24-31
# SAFE_INPUT_SHA256, HOST_TOOL_SHA256, DETACH_SHA256, WRAPPER_SHA256, PREFLIGHT_SHA256; file_pins :434, :457, :480),
# staged from the adopted Part B package (--tools-source s5s6s7-r4, SHA256SUMS d04c6ca1; detach.sh is its
# t1-originals/ copy, T1 1648dfdc unchanged; k4s_end_preflight.py is r4's L6 c7793451). name -> (path under
# --tools-source, sha256, size). RE-PIN whenever another Part B package is adopted: a stale pin refuses before login.
# r5: s5s6s7-r5/TOOLS-FINAL (10:36:33Z) lists exactly these six files, paths and SHAs (unchanged from r4); the r5
# package may be given as --tools-source.
TOOL_PINS = {
    "detach.sh": ("t1-originals/detach.sh", "1648dfdcf85097a54c00b488a5d5570f7c4d0820052a31f89553501084c5b3bb", 599),
    "k4s_end_exit_push.sh": ("k4s_end_exit_push.sh",
                             "65625fc0eac95079c83f2664c5a3244dbe19941cb91075eca5b2093f135679af", 18012),
    "k4s_preflight_push.sh": ("k4s_preflight_push.sh",
                              "c9779cfb339b335bb62d09995e6a14e0202a835af337d641a19b25fffe85c580", 16749),
    "k4s_end_preflight.py": ("k4s_end_preflight.py",
                             "c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5", 76609),
    "safe_input.py": ("safe_input.py", "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00", 133606),
    "k4s_end_host_tool.py": ("k4s_end_host_tool.py",
                             "22c441b1db0fb7e1cf31cd259a5e838f375a7a935b3c78f5f5f5891869508647", 34444),
}
# r4 (U3): <base>/end-inputs-r1/ = the frozen native and the T1 K4 corpus (end_reference.frozen_identity:
# k4s_logic.py:10 NATIVE_PROVENANCE_SHA, :34 T1_K4_CORPUS_SHA; = S5/S7 NATIVE_SHA256 / CORPUS_SHA256,
# k4s_end_preflight.py:81-82, k4s_end_launch_gate.py:90-91), read-only from these exact 05 sources (located r4 by
# SHA; provenance in README): name -> (05 source directory, source leaf, sha256, size). S5/S7 argv: --native
# <base>/end-inputs-r1/clasher_core.abi3.so, --corpus <base>/end-inputs-r1/K4-states.pkl (under <base>, outside
# attempts/preflight/repository/tools: k4s_end_preflight.py:419-422, k4s_end_launch_gate.py:436-440).
END_INPUTS = {
    "clasher_core.abi3.so": ("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native", "clasher_core.abi3.so",
                             "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2", 6713424),
    "K4-states.pkl": ("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-publication-staging-r1", "K4-states.pkl",
                      "a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8", 2829766847),
}
NATIVE_NAME, CORPUS_NAME = "clasher_core.abi3.so", "K4-states.pkl"
# r5 (U4 ruling, COORDINATOR 2026-10-13 10:33Z): the END interpreter is the one P' runtime.sh actually executes,
# `exec /mpac/sdicks02/repos/clasher/.venv/bin/python -B "$@"` (reports/explore/k4s-confirm/runtime.sh at P' 98566c03,
# blob sha256 67249aac), checked read-only in the existing P-facts login; the bare uv binary is NOT ratified (r4's pin
# removed). = S7's HOST_PYTHON (s5s6s7-r5 k4s_end_launch_gate.py:109). The probe refuses unless sys.executable, the venv
# prefix, its base (the uv cpython-3.12.13 the committed reporting-supervisor admissions show as /proc exe,
# receipts/reporting-supervisor-admission-127x0{3,4}.json), the resolved binary, pyvenv.cfg's home and the version are
# exactly these, and every HOST_PYTHON_IMPORTS module resolves inside the venv's own site-packages.
HOST_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"
HOST_PYTHON_VERSION = "3.12.13"
HOST_PYTHON_PREFIX = "/mpac/sdicks02/repos/clasher/.venv"
HOST_PYTHON_BASE_PREFIX = "/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu"
HOST_PYTHON_REALPATH = HOST_PYTHON_BASE_PREFIX + "/bin/python3.12"
HOST_PYTHON_SOURCE = ("reports/explore/k4s-confirm/runtime.sh",
                      "67249aac5f7ff0027bb7bf5fb19c4275f1fe7d9b56a9ab4977a731169b8570f3")
HOST_PYTHON_INFO = ()                                  # r5: no informational candidate (r4 probed the venv beside the pin)
# Third-party top-level modules the frozen END path imports (static AST scan of the r4 runtime from end_reference /
# end_background / end_pool / tier_backend / replay_load and their local closure): numpy and torch
# (tier_backend.py:48,77-103; imitation/model), cv2 (replay_load.py:34, clasher/live/capture.py:65 replay_frames),
# scipy (clasher/vision/l1_temporal.py:6, the V3 fallback's DeploymentTracker). NOT required: grpc (only
# capture.grpc_frames, live emulator capture), numba (battle.py:9-10, guarded try), ultralytics (l1_perception, not on
# the replay path). Imported (code only, no model or data file is opened); clasher_core (the native) is S5's check.
HOST_PYTHON_IMPORTS = ("numpy", "torch", "cv2", "scipy")
# r4 (L4): the adopted S4 assembler = the bundle assembly receipt's assembler_sha256: b3-r6 assemble_fleet_reference.py
# (b3-r6/SHA256SUMS, verified; b3-r6 PROGRESS DONE 06:01:36Z). Any other S4 (e.g. the audit's IA-P1 copy) refuses.
ADOPTED_S4_SHA256 = "2b8f5fb3b79b85103394e18c39330b772fbf2deb28d95fbd01d2d73273d7f016"   # b3-r7 (IR-03; runner update)
BUNDLE_SCHEMA = "clasher.e4v3.inputs.v1"
ASSEMBLY_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"
BUNDLE_MANIFEST, BUNDLE_SIDE, BUNDLE_RECEIPT = "tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"
BUNDLE_UNPINNED = (BUNDLE_MANIFEST, BUNDLE_SIDE, BUNDLE_RECEIPT)
SYNTHETIC_KEY, SYNTHETIC_STAMP, SYNTHETIC_MARKER = "k4s_s4_synthetic", "SYNTHETIC-TEST-ONLY", "synthetic"
INPUT_PINS = {"states.pkl": "0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1",
              "states-rows.json": "bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5",
              "states-rows.bin": "8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb"}
# Production identities every shipped bundle must pin (frozen models; Q6 state bytes, carried inside the bundle).
PRODUCTION_PINS = dict({"v1.pt": "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed",
                        "R3a.pt": "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85",
                        "R3a-calibration.json": "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"},
                       **INPUT_PINS)
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RECORD_NAMES = ("s10-staging-manifest.json",)


def roots(host, commit=None):
    """The k4s-end-r1 layout of one host (P2 decision 3, Q4, r4 B2): <base>/runtime-<P12> (with `commit`), bundles/,
    repository/, attempts/, preflight/, tools/, end-inputs-r1/ and the separate Q4 guard-job parent."""
    require(host in HOSTS, "policy", "host must be 127x03 or 127x04")
    base = END_BASES[host]
    out = dict(base=base, runtime=None, bundles=base + "/bundles", repository=base + "/repository",
               attempts=base + "/attempts", preflight=base + "/preflight", tools=base + "/" + TOOLS_LEAF,
               guard_parent=GUARD_PARENTS[host], end_inputs=base + "/" + END_INPUTS_LEAF,
               native=base + "/" + END_INPUTS_LEAF + "/" + NATIVE_NAME,
               corpus=base + "/" + END_INPUTS_LEAF + "/" + CORPUS_NAME)
    if commit is not None:
        out["runtime"] = base + "/" + RUNTIME_PREFIX + S9.full_commit(commit, "commit")[:12]
    return out


def layout():
    """--print-layout: every path the tools agree on (informational; NOT the RC-6 declaration, see --declare-roots)."""
    return dict(schema="clasher.k4s.end-layout.v1", runtime="<base>/runtime-<P commit 12> (S9 tree, a-w)",
                hosts={h: dict(roots(h), runtime=END_BASES[h] + "/runtime-<P12>",
                               guard_jobs="<guard_parent>/k4s-end-guard-r1-rdRR-aNN | -pfNN (dirs writable)")
                       for h in HOSTS},
                staged_by_s10=["runtime-<P12>", "bundles/<name>", TOOLS_LEAF, END_INPUTS_LEAF, "guard jobs (Q4)"],
                created_by_s10_create_base=["base"] + ["base/" + d for d in BASE_SUBDIRS],
                provisioned_by_s11=["repository"], written_by_s7=["attempts/<attempt>", "preflight/<preflight>"],
                tools=sorted(TOOL_PINS), end_inputs=dict((n, v[2]) for n, v in sorted(END_INPUTS.items())),
                interpreter=dict(path=HOST_PYTHON, flags="-B", version=HOST_PYTHON_VERSION, prefix=HOST_PYTHON_PREFIX,
                                 base_prefix=HOST_PYTHON_BASE_PREFIX, source=list(HOST_PYTHON_SOURCE),
                                 status="U4 ruling COORDINATOR 2026-10-13 10:33Z; qualified by the S10 probe per host"))


class Component(object):
    def __init__(self, kind, host, parent, leaf, files, dirs, extra):
        self.kind, self.host, self.parent, self.leaf = kind, host, parent, leaf
        self.final, self.partial = parent + "/" + leaf, parent + "/" + leaf + ".partial"
        self.files, self.dirs, self.extra = files, dirs, extra
        self.bytes = sum(f["size"] for f in files)

    def dest_policy(self):
        grants = ("guard-job",) if self.kind == "guard-job" else ()
        exemptions = tuple(x for x, key in (("E4", "e4"), ("E5", "e5")) if any(f.get(key) for f in self.files))
        return si.Policy(self.host, [si.Role("dest", self.partial, "write", si.MAX_ROLE_SIZE, patterns=("**",),
                                             exemptions=exemptions, grants=grants)], remote=True)

    def summary(self):
        return dict(kind=self.kind, final=self.final, partial=self.partial, files=len(self.files), dirs=len(self.dirs),
                    bytes=self.bytes, inventory_sha256=C.canonical_sha([[f["dst"], f["size"], f["sha256"], f["mode"]]
                                                                         for f in self.files]), **self.extra)


# ---------------------------------------------------------------- local components (verified before any login)

def runtime_component(policy, host, sha, log):
    manifest = S9.verify(policy, "s9", sha, log=log)
    files = []
    for rel, f in sorted(manifest["inventory"]["files"].items()):
        files.append(dict(src_role="s9-runtime", src_rel=rel, dst=rel, size=f["size"], sha256=f["sha256"],
                          mode=0o555 if f.get("executable") else 0o444, e4=bool(f.get("e4")), e5=bool(f.get("e5"))))
    leaf = RUNTIME_PREFIX + manifest["commit"][:12]
    return Component("runtime", host, END_BASES[host], leaf, files, manifest["inventory"]["dirs"],
                     dict(commit=manifest["commit"], runtime_files_sha256=manifest["runtime_files_sha256"],
                          measurement_files_sha256=manifest["measurement_files_sha256"],
                          runtime_manifest_sha256=sha)), manifest


def guard_component(policy, host, job, sha, log):
    manifest = S3.verify(policy, "s3", policy.role("s3-out").root, job, sha, log=log)
    require(manifest["host"] == host, "check", "guard job was built for " + manifest["host"])
    final = S3.check_target(host, manifest["target_job"])
    files = [dict(src_role="s3-job", src_rel=job + "/" + r["path"], dst=r["path"], size=r["size"], sha256=r["sha256"],
                  mode=0o444, e4=False) for r in manifest["inventory"]]
    return Component("guard-job", host, GUARD_PARENTS[host], job, files, manifest["dirs"],
                     dict(job=job, kind_detail=manifest["job"], bindings=manifest["bindings"],
                          guard_manifest_sha256=sha)), manifest


def tools_component(policy, host):
    """U2: exactly TOOL_PINS from --tools-source (role "tools-src", exact names), each through the descriptor gate
    with its pinned size and SHA-256, BEFORE any login -> <base>/tools/ (files 0444, dir a-w after F)."""
    files = []
    for name, (src, digest, size) in sorted(TOOL_PINS.items()):
        got = si.sha256_input(policy, "tools-src", src, expected_size=size)
        require(got["sha256"] == digest, "sha", "tool %s (%s) is not the S7-pinned %s" % (name, src, digest[:12]))
        files.append(dict(src_role="tools-src", src_rel=src, dst=name, size=size, sha256=digest, mode=0o444, e4=False))
    return Component("tools", host, END_BASES[host], TOOLS_LEAF, files, [],
                     dict(tool_pins=dict((n, v[1]) for n, v in sorted(TOOL_PINS.items())),
                          tools_source=policy.role("tools-src").root))


def end_inputs_component(policy, host):
    """U3: the native and the K4 corpus from their exact 05 sources (roles "ei-<name>", exact leaf), pinned size and
    SHA-256 checked BEFORE any login -> <base>/end-inputs-r1/ (files 0444, dir a-w after F)."""
    files = []
    for i, (name, (directory, leaf, digest, size)) in enumerate(sorted(END_INPUTS.items())):
        got = si.sha256_input(policy, "ei-%d" % i, leaf, expected_size=size)
        require(got["sha256"] == digest, "sha", "end input %s (%s/%s) is not the frozen %s"
                % (name, directory, leaf, digest[:12]))
        files.append(dict(src_role="ei-%d" % i, src_rel=leaf, dst=name, size=size, sha256=digest, mode=0o444,
                          e4=False))
    return Component("end-inputs", host, END_BASES[host], END_INPUTS_LEAF, files, [],
                     dict(sources=dict((n, v[0] + "/" + v[1]) for n, v in sorted(END_INPUTS.items())),
                          native=roots(host)["native"], corpus=roots(host)["corpus"]))


def refuse_test_only(name, manifest, receipt, tiers_sha, host):
    """S10-F4: an S4 test-only (synthetic-pins) bundle is refused before staging, whatever its file pins say."""
    require(SYNTHETIC_MARKER not in name.casefold(), "check", "bundle %s: a *SYNTHETIC* (test-only) bundle name" % name)
    require(SYNTHETIC_KEY not in manifest, "check", "bundle %s: tiers-pins.json carries the S4 test stamp %s"
            % (name, SYNTHETIC_KEY))
    require(SYNTHETIC_STAMP not in json.dumps(manifest) and SYNTHETIC_STAMP not in json.dumps(receipt), "check",
            "bundle %s: SYNTHETIC-TEST-ONLY stamp present" % name)
    require(isinstance(receipt, dict) and receipt.get("schema") == ASSEMBLY_SCHEMA
            and receipt.get("production_pins") is True and receipt.get("status") == "CANDIDATE"
            and receipt.get("manifest_sha256") == tiers_sha and receipt.get("outcomes_read") is False
            and receipt.get("live_actions") is False and receipt.get("host") == host, "check",
            "bundle %s: assembly receipt is not a production (production_pins: true) receipt for this manifest" % name)
    # r4 (L4): only bundles built by the ADOPTED S4 assembler (fail closed while the pin is pending)
    require(C.is_sha256(ADOPTED_S4_SHA256), "policy", "ADOPTED_S4_SHA256 is not set (%s): no bundle can be staged or "
            "declared until the adopted S4 assembler is pinned" % ADOPTED_S4_SHA256)
    require(receipt.get("assembler_sha256") == ADOPTED_S4_SHA256, "check",
            "bundle %s was assembled by S4 %r, not the adopted %s" % (name, receipt.get("assembler_sha256"),
                                                                     ADOPTED_S4_SHA256[:12]))


def bundle_header(policy, role, host, directory, tiers_sha, receipt_sha, runtime_manifest):
    """The bundle's identity, as S5/S7 bind it (r4: shared by staging and --declare-roots): tiers-pins.json by the
    operator's SHA, its sidecar, the assembly receipt by SHA; S4 test-only refusal; the adopted S4 assembler (L4);
    a fleet-reference profile for `host`; the guard job under the Q4 parent and equal in the receipt; the runtime /
    measurement canonical SHAs of the given runtime manifest. Returns (name, manifest, receipt, side bytes)."""
    name = directory.rsplit("/", 1)[1]
    require(SAFE_NAME.fullmatch(name) is not None and not name.endswith(".partial"), "path", "bad bundle name: " + name)
    raw = si.read_bytes(policy, role, BUNDLE_MANIFEST, expected_sha256=C.need_sha256(tiers_sha, "tiers-pins SHA"),
                        max_size=64 << 20)
    manifest = si.loads_strict(raw, name + "/" + BUNDLE_MANIFEST)
    side = ("%s  %s\n" % (tiers_sha, BUNDLE_MANIFEST)).encode()
    si.read_bytes(policy, role, BUNDLE_SIDE, expected_sha256=C.sha_bytes(side), max_size=4096)
    receipt = si.read_json(policy, role, BUNDLE_RECEIPT, 1 << 20,
                           expected_sha256=C.need_sha256(receipt_sha, "assembly receipt SHA"))
    require(isinstance(manifest, dict), "check", "bundle %s: manifest is not an object" % name)
    refuse_test_only(name, manifest, receipt, tiers_sha, host)
    profile = manifest.get("reference_load_profile")
    require(manifest.get("schema") == BUNDLE_SCHEMA and manifest.get("profile") == "fleet-reference"
            and isinstance(profile, dict) and profile.get("host") == host and isinstance(profile.get("guard"), dict),
            "check", "bundle %s is not a fleet-reference bundle for %s" % (name, host))
    guard = profile["guard"]
    S3.check_target(host, guard.get("job"))
    require(receipt.get("guard_job") == guard["job"], "check", "bundle %s: receipt guard job differs" % name)
    require(runtime_manifest is not None, "policy", "bundles are checked against the staged runtime: give --runtime "
            "or --runtime-manifest-for-checks")
    require(C.canonical_sha(manifest.get("runtime_files")) == runtime_manifest["runtime_files_sha256"]
            and C.canonical_sha(manifest.get("measurement_files")) == runtime_manifest["measurement_files_sha256"],
            "check", "bundle %s was not built from the staged runtime (runtime/measurement canonical SHA)" % name)
    return name, manifest, receipt, side


def bundle_component(policy, role, host, directory, tiers_sha, receipt_sha, runtime_manifest, guard_manifest):
    name, manifest, receipt, side = bundle_header(policy, role, host, directory, tiers_sha, receipt_sha,
                                                  runtime_manifest)
    guard = manifest["reference_load_profile"]["guard"]
    pinned = manifest.get("files")
    require(isinstance(pinned, dict) and all(C.is_sha256(v) for v in pinned.values()), "check",
            "bundle %s: malformed files pins" % name)
    walk = si.walk_tree(policy, role)
    require(walk["e1"] is None and not walk["e4"], "check", "bundle %s holds an E1/E4 entry" % name)
    present = {f["rel"]: f for f in walk["files"]}
    require(set(present) == set(pinned) | set(BUNDLE_UNPINNED) and not set(pinned) & set(BUNDLE_UNPINNED), "check",
            "bundle %s holds unpinned or lacks pinned files: %r" % (name, sorted(set(present) ^ (set(pinned)
                                                                                   | set(BUNDLE_UNPINNED)))[:6]))
    shas = {BUNDLE_MANIFEST: tiers_sha, BUNDLE_SIDE: C.sha_bytes(side), BUNDLE_RECEIPT: receipt_sha}
    for rel, expected in sorted(pinned.items()):
        got = si.sha256_input(policy, role, rel, expected_size=present[rel]["size"])
        require(got["sha256"] == expected, "check", "bundle %s: %s differs from its pin" % (name, rel))
        shas[rel] = expected
    for rel, expected in PRODUCTION_PINS.items():
        require(pinned.get(rel) == expected, "check", "bundle %s: %s is not the production identity %s"
                % (name, rel, expected[:8]))
    want = set(S3.END_ADMISSIONS[host])                               # r4 IR-03 (03: bus only)
    require(isinstance(guard.get("admissions"), dict) and set(guard["admissions"]) == want, "check",
            "bundle %s: guard admissions must be exactly %s on %s" % (name, sorted(want), host))
    checks = dict(name=name, guard_job=guard["job"], tiers_pins_sha256=tiers_sha, assembly_receipt_sha256=receipt_sha,
                  assembler_sha256=receipt["assembler_sha256"], runtime_consistent=True, production=True)
    if guard_manifest is not None and guard["job"] == guard_manifest["target_job"]:
        pairs = [(guard.get("freeze"), S3.FROZEN_T1_SHA)]
        require(set(guard["admissions"]) == set(guard_manifest["admissions"]), "check",
                "bundle/guard-job admission names differ")
        pairs += [(guard["admissions"][n], guard_manifest["admissions"][n]["sha256"]) for n in guard["admissions"]]
        seeds = {b["path"]: b["sha256"] for b in guard_manifest["bindings"]}
        require(isinstance(guard.get("seed_inputs"), dict) and set(guard["seed_inputs"]) == set(seeds), "check",
                "bundle/guard-job seed inputs differ")
        pairs += [(guard["seed_inputs"][p], s) for p, s in seeds.items()]
        for rel, expected in pairs:
            require(pinned.get(rel) == expected, "check", "bundle %s: %s differs from the guard job's bytes"
                    % (name, rel))
        checks["guard_job_bytes_equal"] = True
    files = [dict(src_role=role, src_rel=rel, dst=rel, size=present[rel]["size"], sha256=shas[rel], mode=0o444,
                  e4=False) for rel in sorted(present)]
    return Component("bundle", host, roots(host)["bundles"], name, files, C.dirs_of(present), checks)


# ---------------------------------------------------------------- remote requests and scripts

def check_policy(host, components, create_base):
    """Remote (description-only) policy for the P/F/POST reader requests."""
    base = END_BASES[host]
    base_parent, base_leaf = base.rsplit("/", 1)
    roles = [si.Role("base-parent", base_parent, "read", 1, exact=(base_leaf,)),
             si.Role("base", base, "read", 1, exact=BASE_SUBDIRS)]
    by_parent = {}
    for c in components:
        by_parent.setdefault(c.parent, []).extend([c.leaf, c.leaf + ".partial"])
    for i, (parent, names) in enumerate(sorted(by_parent.items())):
        grants = ("guard-job",) if parent in GUARD_PARENTS.values() else ()
        roles.append(si.Role("parent-%d" % i, parent, "read", 1, exact=tuple(sorted(set(names))), grants=grants))
    return si.Policy(host, roles, remote=True), {parent: "parent-%d" % i for i, parent in enumerate(sorted(by_parent))}


def p_items(components, roles, create_base):
    if create_base:
        items = [{"role": "base-parent", "kind": "dir"}, {"role": "base-parent", "kind": "absent",
                                                           "rel": END_BASES[components[0].host].rsplit("/", 1)[1]}]
    else:
        items = [{"role": "base", "kind": "dir"}] + [{"role": "base", "kind": "dir", "rel": d} for d in BASE_SUBDIRS]
    for c in components:
        inside_new_base = create_base and c.kind != "guard-job"
        if c.kind == "guard-job":
            items.append({"role": roles[c.parent], "kind": "dir"})
        if not inside_new_base:
            items += [{"role": roles[c.parent], "kind": "absent", "rel": c.leaf},
                      {"role": roles[c.parent], "kind": "absent", "rel": c.leaf + ".partial"}]
    return items


def f_items(components, roles):
    items = []
    for c in components:
        items += [{"role": roles[c.parent], "kind": "dir", "rel": c.leaf + ".partial"},
                  {"role": roles[c.parent], "kind": "absent", "rel": c.leaf}]
    return items


def post_items(components, roles):
    items = []
    for c in components:
        items += [{"role": roles[c.parent], "kind": "dir", "rel": c.leaf},
                  {"role": roles[c.parent], "kind": "absent", "rel": c.leaf + ".partial"}]
    return items


# r4 (U4): the read-only interpreter check, run inside the P-facts login exactly as END runs Python (no -I: the
# interpreter's own site-packages apply; -B; the S7 single-thread environment; cwd /): version, prefixes, the
# interpreter binary's SHA-256, and an import of each HOST_PYTHON_IMPORTS module (code only: no model, state or data
# file is opened). One "@@PY <json>" line; Python 3.8+ stdlib.
# r5 (U4 ruling): also the venv facts: exec_prefix, the realpaths of sys.prefix and of every site-packages directory
# on sys.path (site.getsitepackages() and the user site, with whether each is on sys.path), pyvenv.cfg (SHA-256 and
# its key = value pairs), and per module its origin, the origin's realpath and its version.
PYTHON_PROBE = r"""
import hashlib, importlib, json, os, site, sys
real = os.path.realpath
rec = dict(executable=sys.executable, realpath=real(sys.executable),
           version="%d.%d.%d" % sys.version_info[:3], prefix=sys.prefix, base_prefix=sys.base_prefix,
           exec_prefix=sys.exec_prefix, prefix_realpath=real(sys.prefix),
           flags=dict(isolated=sys.flags.isolated, no_user_site=sys.flags.no_user_site, optimize=sys.flags.optimize,
                      dont_write_bytecode=sys.flags.dont_write_bytecode), imports={})
with open(rec["realpath"], "rb") as stream:
    rec["realpath_sha256"] = hashlib.sha256(stream.read()).hexdigest()
on_path = set(real(p) for p in sys.path if p)
sites = [(p, "site") for p in site.getsitepackages()] + [(site.getusersitepackages(), "user")]
rec["site_packages"] = [dict(path=p, kind=k, realpath=real(p), exists=os.path.isdir(p), on_sys_path=real(p) in on_path)
                        for p, k in sites]
cfg = os.path.join(sys.prefix, "pyvenv.cfg")
try:
    with open(cfg, "rb") as stream:
        raw = stream.read(1 << 16)
    pairs = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        key, eq, value = line.partition("=")
        if eq:
            pairs[key.strip()] = value.strip()
    rec["pyvenv_cfg"] = dict(path=cfg, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), keys=pairs)
except OSError as error:
    rec["pyvenv_cfg"] = dict(path=cfg, error="%s: %s" % (type(error).__name__, error))
for name in sys.argv[1:]:
    try:
        module = importlib.import_module(name)
        origin = getattr(module, "__file__", None)
        rec["imports"][name] = dict(ok=True, origin=origin, origin_realpath=real(origin) if origin else None,
                                    version=str(getattr(module, "__version__", "")))
    except BaseException as error:
        rec["imports"][name] = dict(ok=False, error="%s: %s" % (type(error).__name__, str(error)[:200]))
sys.stdout.write("@@PY " + json.dumps(rec, sort_keys=True) + "\n")
"""
PYTHON_ENV = ("PATH=/usr/bin:/bin", "LC_ALL=C", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1",
              "PYTHONDONTWRITEBYTECODE=1")


def python_probe_command(python):
    t, q = REMOTE_TOOLS, shlex.quote
    return "cd / && %s -i %s HOME=\"$HOME\" %s -n 19 %s -B -c %s %s" % (
        t["env"], " ".join(PYTHON_ENV), t["nice"], q(python), q(PYTHON_PROBE), " ".join(q(m) for m in HOST_PYTHON_IMPORTS))


def facts_script():
    t = REMOTE_TOOLS
    lines = ["export LC_ALL=C"]
    probes = [("hostname", t["hostname"]), ("df", t["df"] + " -P -B1 -- /mpac/sdicks02"), ("who", t["who"]),
              ("python", python_probe_command(HOST_PYTHON))]
    probes += [("python-info-%d" % i, python_probe_command(p)) for i, p in enumerate(HOST_PYTHON_INFO)]
    for name, cmd in probes:
        # The assignment's status IS the command's status; it is echoed and checked before the output is used.
        lines += ["out=$(%s)" % cmd, 'echo "@@RC|%s|$?"' % name, "printf '@@OUT|%s\\n%%s\\n' \"$out\"" % name]
    lines.append("echo @@DONE")
    return "\n".join(lines)


def venv_problems(rec, python):
    """r5 (U4): every way the probe record differs from the pinned venv interpreter (empty = the pin holds):
    sys.executable is the pinned path; version; sys.prefix and its realpath are the venv; base_prefix and the resolved
    binary are the pinned uv base; pyvenv.cfg exists and its home is the base's bin; and every HOST_PYTHON_IMPORTS
    module was imported from a site-packages directory of the venv itself (realpath inside the venv's realpath)."""
    problems = []
    want = dict(executable=python, version=HOST_PYTHON_VERSION, prefix=HOST_PYTHON_PREFIX,
                prefix_realpath=HOST_PYTHON_PREFIX, base_prefix=HOST_PYTHON_BASE_PREFIX, realpath=HOST_PYTHON_REALPATH)
    for key, value in sorted(want.items()):
        if rec.get(key) != value:
            problems.append("%s is %r, not %r" % (key, rec.get(key), value))
    cfg = rec.get("pyvenv_cfg") if isinstance(rec.get("pyvenv_cfg"), dict) else {}
    keys = cfg.get("keys") if isinstance(cfg.get("keys"), dict) else {}
    if not C.is_sha256(cfg.get("sha256")) or keys.get("home") != HOST_PYTHON_BASE_PREFIX + "/bin":
        problems.append("pyvenv.cfg %r does not name home %s/bin" % (cfg.get("error") or keys.get("home"),
                                                                    HOST_PYTHON_BASE_PREFIX))
    venv = HOST_PYTHON_PREFIX + "/"
    sites = [s.get("realpath") for s in rec.get("site_packages") or [] if isinstance(s, dict) and s.get("on_sys_path")
             and isinstance(s.get("realpath"), str) and s["realpath"].startswith(venv)]
    if not sites:
        problems.append("no site-packages directory of the venv is on sys.path")
    for name in HOST_PYTHON_IMPORTS:
        got = rec["imports"].get(name) or {}
        origin = got.get("origin_realpath")
        if got.get("ok") and not (isinstance(origin, str) and any(origin.startswith(d + "/") for d in sites)):
            problems.append("%s was imported from %r, outside the venv site-packages" % (name, origin))
    return problems


def parse_python(lines, python, required):
    """The @@PY record of one interpreter probe: exactly one such line; for the declared interpreter (`required`)
    every HOST_PYTHON_IMPORTS import must succeed and the r5 venv pin must hold (venv_problems), else refuse."""
    found = [line[len("@@PY "):] for line in lines if line.startswith("@@PY ")]
    if not required and len(found) != 1:
        return dict(path=python, ok=False, error="no probe record")
    require(len(found) == 1, "interpreter", "interpreter probe of %s printed %d records" % (python, len(found)))
    rec = si.loads_strict(found[0].encode(), "interpreter probe")
    require(isinstance(rec, dict) and isinstance(rec.get("imports"), dict), "interpreter", "malformed probe record")
    failed = sorted(m for m in HOST_PYTHON_IMPORTS if not (rec["imports"].get(m) or {}).get("ok"))
    problems = venv_problems(rec, python)
    if required:
        require(rec.get("executable") == python and rec.get("version") == HOST_PYTHON_VERSION, "interpreter",
                "declared interpreter %s is %r %r, not %s" % (python, rec.get("executable"), rec.get("version"),
                                                              HOST_PYTHON_VERSION))
        require(not failed, "interpreter", "declared interpreter %s cannot import %s: %r"
                % (python, failed, {m: rec["imports"].get(m) for m in failed}))
        require(not problems, "interpreter", "declared interpreter %s is not the pinned venv: %s"
                % (python, "; ".join(problems)[:2000]))
    return dict(rec, path=python, ok=not failed and not problems, failed_imports=failed, venv_problems=problems)


def reader_words(host, request):
    argv = si.remote_ssh_argv(host, request, SSH_BINARY)
    words = argv[argv.index("--") + 2:]
    require(all(re.fullmatch(r"[A-Za-z0-9/-]+", w) for w in words), "policy", "unsafe reader words")
    return " ".join(words)


def f_script(host, components, request):
    t = REMOTE_TOOLS
    q = shlex.quote
    lines = ["export LC_ALL=C", reader_words(host, request), "rc=$?", 'echo "@@RC|check|$rc"', '[ "$rc" = 0 ] || exit 9']
    for i, c in enumerate(components):
        if c.kind != "guard-job":
            lines += ["%s -R a-w -- %s" % (t["chmod"], q(c.partial)), "rc=$?", 'echo "@@RC|chmod|%d|$rc"' % i,
                      '[ "$rc" = 0 ] || exit 10']
        lines += ["%s -n -T -- %s %s" % (t["mv"], q(c.partial), q(c.final)), "rc=$?", 'echo "@@RC|mv|%d|$rc"' % i,
                  '[ "$rc" = 0 ] || exit 11']
    lines.append("echo @@DONE")
    return "\n".join(lines)


def ssh_script_argv(host, script):
    require(host in HOSTS, "policy", "unknown END host " + host)
    return [SSH_BINARY] + list(si.SSH_OPTIONS) + ["--", host, REMOTE_TOOLS["sh"] + " -c " + shlex.quote(script)]


def parse_facts(host, out, need_bytes):
    text = out.decode("utf-8", "replace")
    lines = text.split("\n")
    require(lines[-2:] == ["@@DONE", ""], "remote", "P-facts did not complete")
    rcs, outs, key = {}, {}, None
    for line in lines[:-2]:
        if line.startswith("@@RC|"):
            _, name, rc = line.split("|", 2)
            rcs[name] = rc
            key = None
        elif line.startswith("@@OUT|"):
            key = line.split("|", 1)[1]
            outs[key] = []
        elif key is not None:
            outs[key].append(line)
    info = ["python-info-%d" % i for i in range(len(HOST_PYTHON_INFO))]
    require(sorted(rcs) == sorted(["df", "hostname", "python", "who"] + info), "remote",
            "P-facts statuses missing: %r" % sorted(rcs))
    bad = {k: v for k, v in rcs.items() if v != "0" and k not in info}
    require(not bad, "subprocess", "P-facts: nonzero status (output not used): %r" % bad)
    require(outs.get("hostname") == [host], "host", "P-facts hostname %r is not %s" % (outs.get("hostname"), host))
    df = outs.get("df", [])
    require(len(df) == 2 and df[0].split()[:4] == ["Filesystem", "1-blocks", "Used", "Available"], "remote",
            "P-facts df output malformed: %r" % df[:3])
    fields = df[1].split()
    require(len(fields) >= 6 and fields[3].isdigit(), "remote", "P-facts df row malformed: %r" % df[1])
    free = int(fields[3])
    require(free >= need_bytes + HEADROOM, "space", "%d bytes free on /mpac < %d + 50 GiB headroom" % (free, need_bytes))
    who = [w for w in outs.get("who", []) if w.strip()]
    python = parse_python(outs.get("python", []), HOST_PYTHON, True)
    candidates = [dict(parse_python(outs.get(n, []), p, False), rc=rcs[n]) for n, p in zip(info, HOST_PYTHON_INFO)]
    return dict(free_bytes=free, need_bytes=need_bytes, who_lines=len(who), interpreter=python,
                interpreter_candidates_informational=candidates)


def parse_f(host, request, rc, out, components):
    first, _, rest = out.partition(b"\n")
    lines = rest.decode("utf-8", "replace").split("\n")
    rcs = [line for line in lines if line.startswith("@@RC|")]
    require(rcs[:1] and rcs[0].startswith("@@RC|check|"), "remote", "F: reader status missing (rc %s)" % rc)
    check_rc = rcs[0].split("|")[2]
    require(check_rc.isdigit(), "remote", "F: bad reader status")
    records = si.parse_remote_response(request, int(check_rc), first + b"\n")
    require(rc == 0 and lines[-2:] == ["@@DONE", ""], "remote", "F stopped (rc %s): %r" % (rc, rcs))
    want = []
    for i, c in enumerate(components):
        if c.kind != "guard-job":
            want.append("@@RC|chmod|%d|0" % i)
        want.append("@@RC|mv|%d|0" % i)
    require(rcs[1:] == want, "remote", "F step statuses differ: %r" % rcs[1:])
    dirs = [r for r in records if r["kind"] == "dir"]
    return {c.partial: dict(dev=d["dev"], ino=d["ino"]) for c, d in zip(components, dirs)}


# ---------------------------------------------------------------- RC-6 declaration (r4: B7 / U9)

def validate_roots(doc):
    """S7's validate_roots (k4s_end_launch_gate.py:305-331), rule for rule, plus what the declaration's producer
    knows: the runtime leaf is runtime-<commit12> and equal on both hosts, and every declared bundle passed
    bundle_header for its host. Pure."""
    require(isinstance(doc, dict) and set(doc) == {"schema", "commit", "hosts"} and doc["schema"] == ROOTS_SCHEMA
            and re.fullmatch(r"[0-9a-f]{40}", str(doc["commit"])) is not None, "check", "RC-6 declaration malformed")
    hosts = doc["hosts"]
    require(isinstance(hosts, dict) and sorted(hosts) == list(HOSTS), "check", "RC-6 declaration must name 127x03/127x04")
    for host, d in hosts.items():
        base = END_BASES[host]
        require(isinstance(d, dict) and set(d) == set(ROOTS_KEYS), "check", "RC-6 %s: keys" % host)
        require(d["base"] == base and d["repository"] == base + "/repository" and d["attempts"] == base + "/attempts"
                and d["preflight"] == base + "/preflight" and d["tools"] == base + "/tools"
                and d["guard_parent"] == GUARD_PARENTS[host], "check", "RC-6 %s: roots differ from k4s-end-r1/Q4" % host)
        require(os.path.dirname(d["runtime"]) == base
                and re.fullmatch(r"runtime-[0-9a-f]{12}", os.path.basename(d["runtime"])) is not None
                and os.path.basename(d["runtime"]) == RUNTIME_PREFIX + doc["commit"][:12], "check",
                "RC-6 %s: runtime" % host)
        require(isinstance(d["bundles"], dict) and d["bundles"], "check", "RC-6 %s: bundles" % host)
        for name, b in d["bundles"].items():
            require(isinstance(b, dict) and set(b) == {"path", "tiers_pins_sha256", "guard_job"}
                    and b["path"] == base + "/bundles/" + name
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is not None
                    and C.is_sha256(b["tiers_pins_sha256"]) and os.path.dirname(b["guard_job"]) == d["guard_parent"]
                    and si.GUARD_JOB_NAME.fullmatch(os.path.basename(b["guard_job"])) is not None, "check",
                    "RC-6 %s: bundle %s" % (host, name))
        jobs = [b["guard_job"] for b in d["bundles"].values()]
        require(len(set(jobs)) == len(jobs), "check", "RC-6 %s: a guard job is shared by two bundles" % host)
    require(len({d["runtime"].rsplit("/", 1)[1] for d in hosts.values()}) == 1, "check",
            "RC-6: the two hosts declare different runtimes")
    return hosts


def declare_policy(a):
    roles = [C.code_role()] + S9.verify_roles("s9", C.input_dir(a.runtime_manifest_for_checks,
                                                                 "--runtime-manifest-for-checks"))
    for i, (_, directory, _, _) in enumerate(a.declare_bundle or ()):
        roles.append(si.Role("d%02d" % i, C.input_dir(directory, "--declare-bundle"), "read", 64 << 20,
                             exact=BUNDLE_UNPINNED))
    if a.out:
        parent, leaf = C.output_path(a.out, "--out")
        roles.append(si.Role("out-parent", parent, "write", 1 << 20, exact=(leaf,)))
        roles.append(si.Role("out-read", parent, "read", 1 << 20, exact=(leaf,)))
    return si.Policy(C.local_host(), roles)


def declare_roots(a, log=print):
    """U9/B7: the RC-6 ROOTS-DECLARATION.json exactly as S7 consumes it, from verified inputs only: the S9 runtime
    (S9.verify, live clone check; its commit must be --commit), and every declared bundle through bundle_header
    (tiers-pins.json by SHA, the assembly receipt by SHA, production + adopted S4, guard job under Q4, runtime
    consistency). Self-checked with validate_roots (S7's rules); written exclusively to --out (never replaced).
    The runner commits it to MAIN (ruling B6), never to k4s-end-r1."""
    commit = S9.full_commit(a.commit, "--commit")
    require(a.runtime_manifest_for_checks and a.runtime_manifest_sha256, "policy",
            "--declare-roots needs --runtime-manifest-for-checks and --runtime-manifest-sha256")
    require(a.declare_bundle, "policy", "--declare-roots needs --declare-bundle HOST DIR TIERS_SHA RECEIPT_SHA")
    policy = declare_policy(a)
    runtime = S9.verify(policy, "s9", a.runtime_manifest_sha256, log=log)
    require(runtime["commit"] == commit, "check", "--commit %s is not the runtime's commit %s"
            % (commit, runtime["commit"]))
    hosts = {}
    for host in HOSTS:
        r = roots(host, commit)
        hosts[host] = dict(base=r["base"], runtime=r["runtime"], bundles={}, repository=r["repository"],
                           attempts=r["attempts"], preflight=r["preflight"], tools=r["tools"],
                           guard_parent=r["guard_parent"])
    checked = []
    for i, (host, directory, tiers_sha, receipt_sha) in enumerate(a.declare_bundle):
        require(host in HOSTS, "policy", "--declare-bundle host must be 127x03 or 127x04: %r" % host)
        name, manifest, receipt, _ = bundle_header(policy, "d%02d" % i, host, directory, tiers_sha, receipt_sha,
                                                    runtime)
        require(name not in hosts[host]["bundles"], "policy", "bundle %s declared twice for %s" % (name, host))
        hosts[host]["bundles"][name] = dict(path=hosts[host]["base"] + "/bundles/" + name, tiers_pins_sha256=tiers_sha,
                                            guard_job=manifest["reference_load_profile"]["guard"]["job"])
        checked.append(dict(host=host, name=name, source=directory, tiers_pins_sha256=tiers_sha,
                            assembly_receipt_sha256=receipt_sha, assembler_sha256=receipt["assembler_sha256"]))
    doc = dict(schema=ROOTS_SCHEMA, commit=commit, hosts=hosts)
    validate_roots(doc)
    data = C.json_bytes(doc)
    sha = C.sha_bytes(data)
    if a.out:
        parent, leaf = C.output_path(a.out, "--out")
        with si.Writer(policy, "out-parent") as writer:
            writer.create_excl(leaf, data, 0o444)
        require(si.sha256_input(policy, "out-read", leaf)["sha256"] == sha, "changed", "--out differs after writing")
    log(data.decode().rstrip("\n"))
    log("RC-6 ROOTS-DECLARATION sha256 %s%s (runtime %s; %d bundles; inputs: %s)" % (
        sha, " -> " + a.out if a.out else "", hosts[HOSTS[0]]["runtime"].rsplit("/", 1)[1], len(checked),
        json.dumps(checked, sort_keys=True)))
    return doc, sha


# ---------------------------------------------------------------- run

def local_policy(a):
    roles = [C.code_role()]
    s9out = a.runtime or a.runtime_manifest_for_checks
    if s9out:
        roles += S9.verify_roles("s9", C.input_dir(s9out, "--runtime"))
    for i, (directory, _, _) in enumerate(a.bundle or ()):
        roles.append(si.Role("b%02d" % i, C.input_dir(directory, "--bundle"), "read", si.MAX_ROLE_SIZE,
                             patterns=("**",)))
    if a.guard_job:
        roles += S3.verify_roles("s3", C.input_dir(a.guard_job, "--guard-job"), a.guard_job_name or "")
    if getattr(a, "tools_source", None):
        roles.append(si.Role("tools-src", C.input_dir(a.tools_source, "--tools-source"), "read", 1 << 20,
                             exact=tuple(sorted(v[0] for v in TOOL_PINS.values()))))
    if getattr(a, "end_inputs", False):
        for i, (_, (directory, leaf, _, size)) in enumerate(sorted(END_INPUTS.items())):
            roles.append(si.Role("ei-%d" % i, directory, "read", size, exact=(leaf,)))
    return si.Policy(C.local_host(), roles)


def plan(a, policy, log):
    host = a.host
    require(host in HOSTS, "policy", "--host must be 127x03 or 127x04")
    require(a.runtime or a.bundle or a.guard_job or getattr(a, "tools_source", None) or getattr(a, "end_inputs", False),
            "policy", "nothing to stage")
    require(not (a.runtime and a.runtime_manifest_for_checks), "policy", "--runtime and --runtime-manifest-for-checks "
            "are exclusive")
    components, runtime_manifest, guard_manifest = [], None, None
    if a.runtime:
        component, runtime_manifest = runtime_component(policy, host, a.runtime_manifest_sha256, log)
        components.append(component)
    elif a.runtime_manifest_for_checks:
        runtime_manifest = S9.load_manifest(policy, "s9", a.runtime_manifest_sha256)
    if getattr(a, "tools_source", None):
        components.append(tools_component(policy, host))
    if getattr(a, "end_inputs", False):
        components.append(end_inputs_component(policy, host))
    guard = None
    if a.guard_job:
        require(bool(a.guard_job_name) and C.is_sha256(a.guard_manifest_sha256), "policy",
                "--guard-job needs --guard-job-name and --guard-manifest-sha256")
        guard, guard_manifest = guard_component(policy, host, a.guard_job_name, a.guard_manifest_sha256, log)
    for i, (directory, tiers_sha, receipt_sha) in enumerate(a.bundle or ()):
        components.append(bundle_component(policy, "b%02d" % i, host, directory, tiers_sha, receipt_sha,
                                           runtime_manifest, guard_manifest))
    if guard is not None:
        components.append(guard)
    finals = [c.final for c in components]
    require(len(set(finals)) == len(finals), "policy", "two components share a target")
    return components


def run(a, log=print):
    started = C.utc()
    record = None if a.dry_run else C.Record(a.record, "S10", RECORD_NAMES).open()   # first: receipts need a home
    logins, components, received = [], [], []
    try:
        policy = local_policy(a)
        if not a.dry_run:
            require(bool(a.outside_end_window), "policy",
                    "live run requires --outside-end-window '<coordinator A2 GO / window reference>'")
        components = plan(a, policy, log)
        need = sum(c.bytes for c in components)
        checkp, roles = check_policy(a.host, components, a.create_base)
        p_request = si.build_remote_request(checkp, p_items(components, roles, a.create_base))
        if a.dry_run:
            log(json.dumps(dict(mode="dry-run", host=a.host, bytes=need, create_base=a.create_base,
                                components=[c.summary() for c in components],
                                reader_program_sha256=si.remote_program_sha256(),
                                receive_program_sha256=si.receive_program_sha256()), indent=1, sort_keys=True))
            log("# P-check request " + p_request.decode())
            log(shlex.join(si.remote_ssh_argv(a.host, p_request, SSH_BINARY)))
            log("# P-facts\n" + shlex.join(ssh_script_argv(a.host, facts_script())))
            for c in components:
                log("# receive %s -> %s (%d files, %d dirs, %d bytes)" % (c.kind, c.partial, len(c.files),
                                                                          len(c.dirs), c.bytes))
            return None

        def note(label, **extra):
            logins.append(dict(label=label, host=a.host, utc=C.utc(), **extra))
            log("[%s] ssh %s %s" % (C.utc(), label, a.host))

        note("P-check", request_sha256=C.sha_bytes(p_request))
        si.remote_check(checkp, p_items(components, roles, a.create_base), ssh_binary=SSH_BINARY, timeout=300)
        note("P-facts")
        facts = si.run_checked(ssh_script_argv(a.host, facts_script()), 300, 1 << 20, env={"LC_ALL": "C"})
        inspect = parse_facts(a.host, facts.stdout, need)
        if a.create_base:
            note("base")
            base_policy = si.Policy(a.host, [si.Role("dest", END_BASES[a.host], "write", 1, patterns=("**",))],
                                    remote=True)
            received.append(END_BASES[a.host])
            si.remote_receive(base_policy, "dest", policy, [], list(BASE_SUBDIRS), 0, ssh_binary=SSH_BINARY,
                              timeout=300)
        receipts = {}
        for c in components:
            note("receive-" + c.kind, partial=c.partial, files=len(c.files), bytes=c.bytes)
            received.append(c.partial)
            receipt = si.remote_receive(c.dest_policy(), "dest", policy, c.files, c.dirs, c.bytes,
                                        ssh_binary=SSH_BINARY, timeout=6 * 3600)
            receipts[c.partial] = dict(files=len(receipt["files"]), root=receipt["root"],
                                       receipt_sha256=C.canonical_sha(receipt))
        f_request = si.build_remote_request(checkp, f_items(components, roles))
        note("F", request_sha256=C.sha_bytes(f_request))
        result = si.run_checked(ssh_script_argv(a.host, f_script(a.host, components, f_request)), 1800, 1 << 20,
                                stdin_bytes=si.remote_program_source().encode(), env={"LC_ALL": "C"},
                                ok_rcs=(0, 3, 9, 10, 11))
        identities = parse_f(a.host, f_request, result.rc, result.stdout, components)
        note("POST")
        post = si.remote_check(checkp, post_items(components, roles), ssh_binary=SSH_BINARY, timeout=300)
        final = {}
        for c, d in zip(components, [r for r in post if r["kind"] == "dir"]):
            require((d["dev"], d["ino"]) == (identities[c.partial]["dev"], identities[c.partial]["ino"]), "changed",
                    "POST: %s is not the directory F moved" % c.final)
            writable = d["mode"] & 0o222
            require((writable == 0) if c.kind != "guard-job" else (d["mode"] & 0o200 != 0), "check",
                    "POST: %s has mode %o" % (c.final, d["mode"] & 0o7777))
            final[c.final] = dict(mode=oct(d["mode"] & 0o7777), dev=d["dev"], ino=d["ino"])
        manifest = dict(schema=SCHEMA, status="staged", host=a.host, started_utc=started, finished_utc=C.utc(),
                        outside_end_window=a.outside_end_window, ssh_logins=len(logins), logins=logins,
                        inspect=inspect, create_base=a.create_base, components=[c.summary() for c in components],
                        receipts=receipts, final=final, roots=roots(a.host), adopted_s4_sha256=ADOPTED_S4_SHA256,
                        tool_pins=dict((n, v[1]) for n, v in sorted(TOOL_PINS.items())),
                        reader_program_sha256=si.remote_program_sha256(),
                        receive_program_sha256=si.receive_program_sha256(), safe_input_sha256=C.SAFE_INPUT_SHA256,
                        script_sha256=C.code_sha(policy, "s10_stage_host.py"),
                        s3_sha256=C.code_sha(policy, "s3_guard_job.py"), s9_sha256=C.code_sha(policy, "s9_end_runtime.py"),
                        common_sha256=C.code_sha(policy, "end_prep_common.py"),
                        inventories={c.final: [[f["dst"], f["size"], f["sha256"], f["mode"]] for f in c.files]
                                     for c in components})
        sha = record.write("s10-staging-manifest.json", manifest)
        log("S10 OK: %s/s10-staging-manifest.json sha256 %s" % (a.record, sha))
        return manifest
    except BaseException as error:
        if record is not None:
            record.refusal(error, {"logins": logins, "started_utc": started,
                                   "host_paths_created_or_attempted_needing_authorized_cleanup": received})
        raise
    finally:
        if record is not None:
            record.close()


class BundleAction(argparse.Action):          # --bundle (3 values) and --declare-bundle (4 values)
    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, self.dest) or [])
        items.append(tuple(values))
        setattr(namespace, self.dest, items)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    ap.add_argument("--print-layout", action="store_true", help="print the k4s-end-r1 layout (informational) and exit")
    ap.add_argument("--declare-roots", action="store_true",
                    help="write the RC-6 ROOTS-DECLARATION.json S7 consumes (needs --commit, "
                         "--runtime-manifest-for-checks, --runtime-manifest-sha256, --declare-bundle ..., --out)")
    ap.add_argument("--commit", help="--declare-roots: the evidence commit P' whose runtime is declared")
    ap.add_argument("--declare-bundle", nargs=4, action=BundleAction,
                    metavar=("HOST", "DIR", "TIERS_PINS_SHA256", "RECEIPT_SHA256"))
    ap.add_argument("--out", help="--declare-roots: new file for the declaration (exclusive)")
    ap.add_argument("--tools-source", help="stage <base>/tools from this adopted Part B package (TOOL_PINS)")
    ap.add_argument("--end-inputs", action="store_true", help="stage <base>/end-inputs-r1 (native + K4 corpus)")
    ap.add_argument("--host", choices=HOSTS)
    ap.add_argument("--runtime", help="S9 output directory (ships the runtime)")
    ap.add_argument("--runtime-manifest-for-checks", help="S9 output used only to check bundles (no ship)")
    ap.add_argument("--runtime-manifest-sha256")
    ap.add_argument("--bundle", nargs=3, action=BundleAction, metavar=("DIR", "TIERS_PINS_SHA256", "RECEIPT_SHA256"))
    ap.add_argument("--guard-job", help="S3 output directory")
    ap.add_argument("--guard-job-name")
    ap.add_argument("--guard-manifest-sha256")
    ap.add_argument("--create-base", action="store_true", help="first staging on this host: create <base> + subdirs")
    ap.add_argument("--record", help="new local directory for the staging manifest (live run)")
    ap.add_argument("--outside-end-window", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.print_layout:
        print(json.dumps(layout(), indent=1, sort_keys=True))
        return 0
    if a.declare_roots:
        try:
            declare_roots(a)
        except si.Refusal as error:
            print("S10 REFUSED: " + str(error), file=sys.stderr)
            return 2
        except Exception as error:                                    # fail closed on anything unexpected
            print("S10 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
            return 1
        return 0
    if a.host is None:
        ap.error("--host is required")
    if not a.dry_run and not a.record:
        ap.error("--record is required unless --dry-run")
    try:
        run(a)
    except si.Refusal as error:
        print("S10 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print("S10 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
