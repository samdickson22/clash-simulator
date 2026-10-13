#!/usr/bin/env python3
"""K4S END fleet-reference bundle assembler (CANDIDATE b3-r6; offline; never launches anything, never reads outcomes).

One explicit, SHA-pinned request describes every input by absolute path and expected SHA-256. The assembler checks
everything first, then copies each input into a fresh bundle directory, re-hashes every copy and writes the
`tiers-pins.json` manifest (schema clasher.e4v3.inputs.v1, profile fleet-reference) that the frozen consumers read:
tier_backend.validate_bundle (A3 02e2139f), fleet_validity.ReportingGuard (A5 0775b704), fleet_profile.slot_layout,
end_reference.frozen_identity and end_background.k4s_reporting_profile. Any mismatch raises AssemblyError before
anything is written. Inputs are only read.

r4: the shared safe_input layer (rulings P2-1, P2-4, D1-D4); r4b: layer r3 (= r2 + ruling E5). safe_input.py is
vendored byte-identical next to this file. r5 (END-FULL-F1): it is read only through the canonical bootstrap r1
(normalized path, outcome-name gate on every component, O_NOFOLLOW component walk from /, single-link regular file of
the pinned size before any byte is read); its SHA-256 (806e5ebb) is verified with hashlib on the exact bytes that are
then executed, and its constants fingerprint (33f594ed) must match, before any other code touches a path (a production
run re-checks the fingerprint).
- Every file read, hash, stat and open goes through si roles: one si.Policy per input class (request + assembler;
  synthetic pins; the request's sources, one exact read role per absolute source rooted at its parent; the repository;
  the evidence artifacts with their exact names; the runtime tree; the bundle output). Every name is refused BEFORE any
  syscall by the shared case-insensitive family denylist (si.name_gate: games, hub-blocks, *complete*.json,
  *interference*.json, *hub-ack*.json, *end-raw*.json, END-JOB*, END-FINAL*, attempt-*.json and their variants in any
  component; the strict END pair k4s-confirm/end; k4s-confirm-* / k4s-end-guard-* jobs; FROZEN-T1 launch namespaces;
  04 perception storage; the v4 cache repo); all roots and leaves of a Policy are name-gated when it is built, before
  any of them is opened. Then the si descriptor gate: canonical root, component-wise O_DIRECTORY|O_NOFOLLOW walk,
  fstatat leaf (regular, st_nlink == 1, size cap) before open, O_NOFOLLOW open, fstat again (same dev/ino, nlink 1)
  BEFORE any byte is read; exact-size reads; every production read carries its expected SHA-256 (or is a hash-only
  pass whose result is compared with a SHA-pinned aggregate). The single accepted residual is a concurrent same-size
  rewrite by another local actor (coordinator 16:00Z, restated 18:19Z).
- Every git call goes through si.git_run (P2-4): exact environment (no inherited GIT_*), fresh empty HOME,
  --no-replace-objects + GIT_NO_REPLACE_OBJECTS=1, hooks/fsmonitor off, transports off, explicit --git-dir/--work-tree,
  static refusal of alternates/grafts/shallow/gitfiles/undeclared commondir/driver config, rc checked before stdout.
  The committed side uses the two-phase si.git_plan: phase 1 screens the WHOLE HEAD tree's metadata to completion
  (every complete.json component must be one of the four E4 paths, mode 100644, with its pinned blob OID; the members'
  names, modes, types and the exact E1 entry) before any object is read; phase 2 reads only planned blobs, each with
  its type, size and OID verified (and its expected SHA-256).
Exemptions (coordinator rulings 16:55Z E1-E3, 17:12Z E4, 18:19Z D2, 21:28Z E5), nothing else:
- E1 materialised (D2): the committed entry must be the exact mode-120000 link visualize_battle.py ->
  examples/visualize_battle.py (si.E1_LINK_OID; link blob read, never followed); the runtime ships a REGULAR
  visualize_battle.py whose bytes equal the gated target blob (si.git_e1_verify_shipped). A runtime symlink refuses.
- E2/E4: exactly the four tracked complete.json files (si.E4_COMPLETE_JSON, si.E4_GIT_BLOB_OIDS), hash only, never
  parsed. Any other complete.json at the build commit (member or not, any position) or in the runtime tree refuses.
  Runtime membership is unchanged (S1 runtime-pin-r2 names + every *.py); only a member E4 entry (E2) is a runtime file.
  r6 (B1): the pinned runtime-pin-r2 "files" is a dict {name: sha256}; as in frozen prepare_bundle.py:42
  (set(...["files"])) the names are its keys (or a list's items) and the per-file SHAs are never compared.
- E3: admissions only at reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>, with the pinned r4
  identities; a stale identity is refused (a re-pin needs a coordinator ruling).
- E5 (r4b, from the layer): exactly the nine si.E5_RUNTIME_MEMBERS (exact path + git blob OID; no S4 copy). The
  runtime and repository roles carry exemption E5; an E5 member is listed by si.walk_tree under "e5", hashed only by
  si.hash_e5 (descriptor gate, st_nlink 1, bytes must hash to the pinned blob OID), never parsed, and must be the
  committed E5 entry at HEAD of --repository (git_plan phase 1: mode 100644, pinned OID; metadata only, no blob read).
  Any other family-named member, a moved copy or a case variant refuses by name.

Production pins (r2, S4-F2). Without the test switch, the constants in PRODUCTION_PINS are enforced: frozen models,
the Q6 state bytes (states.pkl 0addf7c0, states-rows.json bcd30777, states-rows.bin 8cc2f611), T1's own-tier sets
(canonical d84b07f6), the measurement inventory, the S1 runtime pin (runtime-pin-r2.json f81f3655) and qualified
binding (56b67dd4), the 128-CPU topology, the exact per-host guard admissions (03: system bus + idle service PID
2180947; 04: system bus only), the FROZEN-T1 freeze and the K4S plan. Each admission must also be the copy committed at
HEAD of --repository, bound by --committed-admission NAME REPOSITORY_PATH SHA256 (required; refused without it).
Test-only mode: K4S_S4_SYNTHETIC_PINS=<pins.json with "marker": "SYNTHETIC"> substitutes synthetic pins; it requires
an --out whose name contains SYNTHETIC and stamps the manifest and receipt SYNTHETIC-TEST-ONLY, so it can never
produce a production manifest. The pins file is read through safe_input like every other input; test mode cannot
widen, narrow or move the E1/E4/E5 exemptions (they are safe_input's).

  assemble_fleet_reference.py --request R.json --request-sha256 S --repository REPO
      --committed-admission NAME REPOSITORY_PATH SHA256 [...] --out NEW_BUNDLE_DIR [--dry-run]

--dry-run validates everything (all hashes included) and prints the planned tiers-pins.json bytes to stdout;
it writes nothing. A real run prints nothing on stdout but writes NEW_BUNDLE_DIR/{<inputs>, tiers-pins.json,
tiers-pins.sha256, assembly-receipt.json} (staged in NEW_BUNDLE_DIR.partial through si.Writer, every copy re-hashed,
then published by one rename) and prints a one-line summary to stderr. A failed write keeps the .partial directory
(never deleted; a later run refuses until it is removed by an authorized step).
"""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
import types
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------- the shared safe_input layer (P2-1, P2-4; r4; r4b: r3; r5)
# r5 (END-FULL-F1): the vendored layer is read ONLY through the canonical bootstrap r1 below
# (bootstrap-r1/k4s_bootstrap_r1.py, pasted verbatim between its BEGIN/END lines; the pins stay outside): normalized
# absolute path (default: next to __file__, never resolved or normalized), safe_input r3 outcome-name families on every
# component, every ancestor opened O_DIRECTORY|O_NOFOLLOW from "/", the leaf a regular single-link file of exactly
# SAFE_INPUT_SIZE bytes BEFORE any byte is read; exactly those bytes are hashed and executed. Then the fingerprint pin.
SAFE_INPUT_FILE = "safe_input.py"
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_SIZE = 133606
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
SAFE_INPUT_MODULE = "_k4s_s4_safe_input_r3"

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


def load_safe_input(path=None):
    """The vendored layer through the canonical bootstrap (refusal: RuntimeError, as before), then its constants
    fingerprint (a production run re-checks it later)."""
    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path
    module = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, SAFE_INPUT_MODULE, RuntimeError)
    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:
        raise RuntimeError("S4: safe_input constants fingerprint differs from the pinned r3 value")
    return module


si = load_safe_input()

REQUEST_SCHEMA = "clasher.k4s.end-fleet-reference-request.v2"
RECEIPT_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"
PINS_SCHEMA = "clasher.k4s.end-fleet-reference-pins.v1"
BUNDLE_SCHEMA = "clasher.e4v3.inputs.v1"
EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
STATE_ROWS_SCHEMA = "clasher.e4v3.state-rows.v1"                  # state_rows.py:20
STATE_ROWS_PROTOCOL = 5                                            # state_rows.py:23
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
S1_RUNTIME_PINS = ("reports/explore/s1/receipts/runtime-pin-r2.json",)   # r4: the pinned r2 list only
S1_QUALIFIED = "reports/explore/s1/receipts/qualified-source-binding.json"
EVIDENCE_REPO_DIR = "reports/explore/k4s-confirm"                  # plan v2 S2: evidence outside end/
EVIDENCE_FILE = "end-evidence.json"
END_DIR = si.STRICT_END_DIR                                        # END-RUNBOOK END_DIR (strict END namespace)
ADMISSION_REPO_DIR = si.E3_ADMISSIONS_DIR                          # E3 (COORDINATOR 2026-10-12 16:55Z; Sol R1)
# E1 / E2 / E4 / E5 come from safe_input (single source): S4 keeps no second copy of the exemption lists.
E1_ALIAS, E1_TARGET = si.E1_ALIAS, si.E1_LINK_TEXT
E2_PATH = si.E2_PATH
E2_SHA256 = "d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc"
SYNTHETIC_ENV = "K4S_S4_SYNTHETIC_PINS"
SYNTHETIC_MARKER = "SYNTHETIC"
SYNTHETIC_STAMP = "SYNTHETIC-TEST-ONLY"

# Frozen values (tier_backend.py:18-21; FROZEN-T1.json at aeeb3003; K4S plan.json at 201db04c).
V1_SHA = "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed"
STUDENT_SHA = "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85"
CALIBRATION_SHA = "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"
THRESHOLD = .5005528330802917
FROZEN_T1_SHA256 = "24817e16c3da7b5c9b6e48c56e69144e84678b7d143a146fe2884f446d07d7e4"
K4S_PLAN_SHA256 = "38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf"
DBUS_CMDLINE_SHA256 = "f481db6887b1454cde723322eee10a57f08a0789ab8db6f16d41ac2ad3329749"
S1_RUNTIME_PIN_SHA256 = "f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d"   # = S9 RUNTIME_PIN_SHA
S1_QUALIFIED_SHA256 = "56b67dd430636c90462156f3790f3a03df40410a77ffbd3d2d4c0b11acc0dce6"     # = S9 QUALIFIED_SHA

# Production pins (coordinator rulings 15:41Z Q2/Q6 and 16:00Z S4). Sources, all verified in this session:
# - Q6 bytes: sha256 of the 05 copies in t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/ (read-only), equal to
#   files[] of END-A3-manifest-01/08-f6cebbaa.json (bd9804c3 / 1bd8a4c7);
# - sets: canonical sha256 of `sets` (golden 125; speed 4 x 300) in END-A3-manifest-01/08-f6cebbaa.json and in the A5
#   manifests f81c9288 (= END-A5-reference-approved-argv-08-r1 manifest_sha256), 93daf063, 5df0fa00, c84d65ed on 05;
# - measurement inventory: canonical sha of the frozen e4v3 18-file rule (= END-A5-runtime-manifest-inventory-diff);
# - S1 runtime pin / qualified binding: sha256 of `git show origin/main:<path>` (b3-r4, = S9's pins);
# - admissions: committed r4 host admissions rounds/r4/evidence/step7/127x0{3,4}-host-admission.json (process rows),
#   and t1/receipts/idle-services-admission-127x03.json (service identity, PID 2180947);
# - E1/E4: safe_input constants (si.E1_*, si.E4_COMPLETE_JSON, si.E4_GIT_BLOB_OIDS; OIDs ratified by the runner at
#   21:27Z, RUNNER-E4-OID-RATIFICATION.txt); E5 (r4b): si.E5_RUNTIME_MEMBERS (safe_input r3, ruling E5).
PRODUCTION_PINS = {
    "marker": "PRODUCTION",
    "models": {
        "v1.pt": V1_SHA, "R3a.pt": STUDENT_SHA, "R3a-calibration.json": CALIBRATION_SHA,
        "states.pkl": "0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1",
        "states-rows.json": "bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5",
        "states-rows.bin": "8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb",
    },
    "sets_canonical_sha256": "d84b07f6de0ac1cffbbb199221b6fbd795e9f7169aebcbdc445bba282e0c3ae2",
    "measurement_files_sha256": "42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25",
    "s1_runtime_pin_sha256": S1_RUNTIME_PIN_SHA256,
    "s1_qualified_sha256": S1_QUALIFIED_SHA256,
    "frozen_t1_sha256": FROZEN_T1_SHA256,
    "k4s_plan_sha256": K4S_PLAN_SHA256,
    "topology": {"P": list(range(128)), "E": [], "label": "Linux logical IDs; physical masks pinned by reporting plan"},
    "admissions": {
        "127x03": {
            "system-bus-admission.json": {"identity": {"pid": 2049, "start_ticks": 1273, "exe": "/usr/bin/dbus-daemon",
                                                       "cmdline_sha256": DBUS_CMDLINE_SHA256, "uid": 103}},
            "idle-services.json": {"service": {
                "pid": 2180947, "ppid": 2180946, "pgid": 2180934, "start_ticks": 139691386,
                "cmdline_sha256": "16152ceb7942621141a2d8d91189affdeacde28ad1a9059ffbadde5e9bde799a", "uid": 3822945}},
        },
        "127x04": {
            "system-bus-admission.json": {"identity": {"pid": 2005, "start_ticks": 1032, "exe": "/usr/bin/dbus-daemon",
                                                       "cmdline_sha256": DBUS_CMDLINE_SHA256, "uid": 103}},
        },
    },
    "runtime_aliases": {E1_ALIAS: E1_TARGET},                     # D2: materialised copy of the target, not a link
    "runtime_outcome_name_exceptions": dict(si.E4_COMPLETE_JSON),
}
PIN_KEYS = frozenset(PRODUCTION_PINS)

GUARD_MODULES = ("common", "host_audit", "idle_services", "system_bus", "ssh_transport",      # fleet_validity.py:10-11
                 "perception_confirmation", "owned_supervisor", "ssh_budget", "parent_source_seed")
GUARD_DELTAS = ("operational_delta_op5", "operational_delta_op5_08", "operational_delta_op6")  # fleet_validity.py:61
BUS_KEYS = ("pid", "start_ticks", "exe", "cmdline_sha256", "uid")                             # t1/system_bus.py:5
IDLE_KEYS = ("pid", "ppid", "pgid", "start_ticks", "cmdline_sha256", "uid")                   # t1/idle_services.py:7
TIERS = ("K0c", "S", "K2", "K4")                                                               # receipts.py:7
MODEL_NAMES = ("v1.pt", "R3a.pt", "R3a-calibration.json", "states.pkl", "states-rows.json", "states-rows.bin")
ADMISSIONS = ("system-bus-admission.json", "idle-services.json")
STALE_IDENTITY = (" (a stale identity after a reboot, bus replacement or cache-service restart is refused until a"
                  " coordinator re-pin ruling (E3))")
# Guard-job namespaces (DESIGN.md §A.5): never T1's, never K4S reporting jobs, never 04 perception paths. One fresh
# job per attempt (-rdRR-aNN) and per preflight (-pfNN) (ruling Q4; plan v2 S3/S5).
JOB_PARENTS = dict(si.Q4_GUARD_PARENTS)
JOB_NAME = si.GUARD_JOB_NAME
PROFILE = dict(reference_slot=0, console_rule=False, warmup_seconds=300, perception="none")
T1_LAUNCH_NAMESPACES = si.T1_LAUNCH_NAMESPACES
REPO_PATH = re.compile(r"[A-Za-z0-9._/-]+")
MAX_INPUT = si.MAX_ROLE_SIZE

# Bundle layout (T1 precedent END-A3-manifest-01-f6cebbaa.json; evidence kept in its own subdirectory).
EVIDENCE_DIR = "k4s-end-evidence"
EVIDENCE_NAME = EVIDENCE_DIR + "/" + EVIDENCE_FILE
GUARD_ROOT, FREEZE_NAME, ADMISSION_DIR, SEED_DIR = "t1-guard", "t1-freeze.json", "guard-admissions", "seed-inputs"
MANIFEST, MANIFEST_SHA, RECEIPT = "tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"

SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class AssemblyError(ValueError):
    """Explicit fail-closed assembly error (never an assert; behaves the same under python -O)."""


def require(condition, message):
    if not condition:
        raise AssemblyError(message)


def canonical(value):
    """receipts.canonical (e4v3 receipts.py:10-11)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def is_sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def is_int(value):
    return type(value) is int


# ---------------------------------------------------------------- safe_input glue (names first, then descriptors)

def si_error(label, error):
    return AssemblyError(label + ": safe_input refused [" + error.code + "]: " + error.reason)


def guarded(label, function, *args, mismatch=None, codes=("sha",), **kwargs):
    """Call safe_input; a Refusal becomes an AssemblyError naming the label (or `mismatch` for the listed codes)."""
    try:
        return function(*args, **kwargs)
    except si.Refusal as error:
        if mismatch is not None and error.code in codes:
            raise AssemblyError(mismatch) from None
        raise si_error(label, error) from None


def this_host():
    node = os.uname().nodename.split(".")[0]
    require(node in si.HOSTS, "The assembler runs on a fleet host, not " + repr(node))
    return node


def relative(name, label):
    """A normalized relative POSIX path: not absolute, no '', '.', '..', backslash or NUL component."""
    require(isinstance(name, str) and name and "\\" not in name and "\x00" not in name,
            "Unsafe relative path (" + label + "): " + repr(name))
    require(not name.startswith("/") and all(p not in ("", ".", "..") for p in name.split("/")),
            "Unsafe relative path (" + label + "): " + name)
    return str(PurePosixPath(name))


def absolute(value, label):
    """Pure: an absolute, normalized path (the caller's role then name-gates and walks it through safe_input)."""
    require(isinstance(value, str) and value.startswith("/") and "\x00" not in value and "\\" not in value,
            label + " must be an absolute path")
    require(os.path.normpath(value) == value and not value.startswith("//") and value != "/",
            label + " must be a normalized path: " + value)
    return value


def location_free(path, label):
    """Pure name gate on a complete absolute path (si.name_gate on this host; no syscall)."""
    text = absolute(str(path), label)
    guarded(label, si.name_gate, text, this_host(), ())
    return text


def split(path):
    parent, leaf = path.rsplit("/", 1)
    return parent or "/", leaf


class Sources:
    """The si.Policy for every absolute request source: one exact read role per distinct path (root = its parent,
    exact = its leaf, no exemption, no grant). Building it name-gates every root (si.Policy) and then every leaf
    (si.gate_names), BEFORE any source is touched; a source that fails is reported under its first label."""

    def __init__(self, labelled):
        self.role_of, roles, labels = {}, [], {}
        host = this_host()
        for label, path in labelled:                   # the complete path, under its own label, before anything else
            guarded(label, si.name_gate, path, host, ())
        for label, path in labelled:
            if path in self.role_of:
                continue
            name = "src-%03d" % len(roles)
            parent, leaf = split(path)
            role = guarded(label, si.Role, name, parent, "read", MAX_INPUT, exact=(leaf,))
            roles.append(role)
            self.role_of[path], labels[path] = name, label
        self.policy = guarded("request sources", si.Policy, this_host(), roles) if roles else None
        for path, name in self.role_of.items():
            guarded(labels[path], si.gate_names, self.policy, name, split(path)[1])

    def handle(self, path, label):
        require(path in self.role_of, "Input source was not declared by the request: " + label)
        return self.policy, self.role_of[path], split(path)[1]


class Copy:
    """A planned bundle copy: a gated (policy, role, rel) input with its expected SHA-256 and size."""
    __slots__ = ("policy", "role", "rel", "sha256", "size", "label")

    def __init__(self, policy, role, rel, sha256, size, label):
        self.policy, self.role, self.rel, self.sha256, self.size, self.label = policy, role, rel, sha256, size, label


def entry_shape(entry, label):
    require(isinstance(entry, dict) and set(entry) == {"source", "sha256"}, "Input entry must be {source, sha256}: " + label)
    require(is_sha(entry["sha256"]), "Input SHA is not a SHA-256: " + label)


def pinned_source(sources, entry, label, expected=None):
    """{source, sha256} -> Copy; the file's SHA (hash-only si pass, descriptor-gated) must equal the request's and,
    if given, the pinned value."""
    entry_shape(entry, label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the pinned value: " + label)
    policy, role, rel = sources.handle(absolute(entry["source"], label), label)
    found = guarded(label, si.sha256_input, policy, role, rel)
    require(found["sha256"] == entry["sha256"], "Pin mismatch: " + label)
    return Copy(policy, role, rel, entry["sha256"], found["size"], label)


def parse_json(raw, label):
    try:
        return si.loads_strict(raw, label)
    except si.Refusal:
        raise AssemblyError("Not JSON: " + label) from None


def pinned_json(sources, entry, label, expected=None):
    """Read once from the si-gated descriptor with the request's expected SHA-256 (checked before the bytes are
    returned), then parse those bytes."""
    entry_shape(entry, label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the pinned value: " + label)
    policy, role, rel = sources.handle(absolute(entry["source"], label), label)
    raw = guarded(label, si.read_bytes, policy, role, rel, None, entry["sha256"], mismatch="Pin mismatch: " + label)
    return Copy(policy, role, rel, entry["sha256"], len(raw), label), parse_json(raw, label)


# ---------------------------------------------------------------- pins (production constants or test-only synthetic)

def active_pins():
    """PRODUCTION_PINS unless the test-only switch names a SYNTHETIC pins file. Returns (pins, synthetic)."""
    location = os.environ.get(SYNTHETIC_ENV)
    if location is None:
        return PRODUCTION_PINS, False
    # r4: an exact si read role rooted at the pins file's parent (names, descriptor gate) before any byte is read.
    path = absolute(location, SYNTHETIC_ENV)
    parent, leaf = split(path)
    policy = guarded(SYNTHETIC_ENV, si.Policy, this_host(),
                     [guarded(SYNTHETIC_ENV, si.Role, "synthetic-pins", parent, "read", 16 << 20, exact=(leaf,))])
    pins = parse_json(guarded(SYNTHETIC_ENV, si.read_bytes, policy, "synthetic-pins", leaf), "synthetic pins")
    require(isinstance(pins, dict) and pins.get("schema") == PINS_SCHEMA and pins.get("marker") == SYNTHETIC_MARKER
            and set(pins) == PIN_KEYS | {"schema"}, "Synthetic pins must carry marker SYNTHETIC and every pin key")
    check_exemptions(pins, synthetic=True)
    return pins, True


def check_exemptions(pins, synthetic):
    """E1/E4 are safe_input's and fixed in every mode: the alias map is exactly E1 (D2: a materialised copy) and the
    outcome-name exceptions are exactly si.E4_COMPLETE_JSON (paths AND SHAs). E5 (r4b) is safe_input's alone
    (si.E5_RUNTIME_MEMBERS); the pins carry no E5 key, so no mode can widen, move or narrow it."""
    require(pins.get("runtime_aliases") == {E1_ALIAS: E1_TARGET}, "Runtime aliases must be exactly the E1 exemption")
    exceptions = pins.get("runtime_outcome_name_exceptions")
    require(isinstance(exceptions, dict) and set(exceptions) == set(si.E4_COMPLETE_JSON)
            and all(is_sha(digest) for digest in exceptions.values()),
            "Runtime outcome-name exceptions must be exactly the E4 exempt list")
    require(exceptions == si.E4_COMPLETE_JSON, "Runtime outcome-name exceptions must carry the E4 SHAs of safe_input")


# ---------------------------------------------------------------- runtime inventory (si.walk_tree; frozen rules)

def runtime_policy(root):
    """The runtime tree role: rooted at the (canonical) runtime root; every name allowed by pattern but every name still
    passes the shared family denylist; the exemptions are E4 and (r4b) E5, both safe_input's exact lists (D2: no
    symlink at all, E1 included)."""
    root = absolute(str(root), "runtime_root")
    return guarded("runtime_root", si.Policy, this_host(),
                   [guarded("runtime_root", si.Role, "runtime", root, "read", MAX_INPUT, patterns=("**",),
                            exemptions=("E4", "E5"))])


class RuntimeInventory:
    """One confined walk of the runtime tree (si.walk_tree on an E4+E5 role), then the frozen membership rule
    (prepare_bundle.runtime_pins: the S1 runtime-pin-r2 names + every *.py) and the measurement rule
    (prepare_bundle.py:117: e4v3 direct children with suffix .py/.sh or spec-pins.json). Every member and measurement
    entry is hashed once through the si descriptor gate (hash only); E4 entries through si.hash_e4; E5 entries (r4b)
    through si.hash_e5 (pinned git blob OID). Nothing in the runtime tree is parsed except the S1 pin list and qualified
    binding, each read with its pinned SHA-256."""

    def __init__(self, policy, role, pins):
        self.policy, self.role, self.pins = policy, role, pins
        check_exemptions(pins, synthetic=pins is not PRODUCTION_PINS)
        self.walk = guarded("runtime tree", si.walk_tree, policy, role)
        self.sizes = {f["rel"]: f["size"] for f in self.walk["files"]}
        self._hashes, self.e5_oids = {}, {}

    def sha(self, rel):
        if rel not in self._hashes:
            if rel in self.walk["e5"]:                 # r4b: opaque; bytes hashed against the pinned blob OID only
                found = guarded("runtime E5 entry " + rel, si.hash_e5, self.policy, self.role, rel,
                                mismatch="Runtime E5 entry is not its pinned git blob: " + rel, codes=("exemption",))
                self.e5_oids[rel] = found["git_oid"]
            elif rel in self.walk["e4"]:
                found = guarded("runtime E4 entry " + rel, si.hash_e4, self.policy, self.role, rel,
                                mismatch="Runtime outcome-named entry differs from its pin: " + rel,
                                codes=("exemption",))
            else:
                found = guarded("runtime entry " + rel, si.sha256_input, self.policy, self.role, rel, self.sizes[rel])
            self._hashes[rel] = found["sha256"]
        return self._hashes[rel]

    def present(self, rel):
        return rel in self.sizes or rel in self.walk["e4"] or rel in self.walk["e5"]

    def measurement(self):
        guarded("runtime e4v3", si.check_dir, self.policy, self.role, E4V3_REL)
        names = sorted(rel[len(E4V3_REL) + 1:] for rel in list(self.sizes) + list(self.walk["e5"])
                       if rel.startswith(E4V3_REL + "/") and "/" not in rel[len(E4V3_REL) + 1:])
        return {name: self.sha(E4V3_REL + "/" + name) for name in names
                if Path(name).suffix in (".py", ".sh") or name == "spec-pins.json"}

    def read_pinned(self, rel, expected, label):
        require(self.present(rel), "Missing input (" + label + "): " + rel)
        raw = guarded(label, si.read_bytes, self.policy, self.role, rel, None, expected,
                      mismatch=label + " differs from its pin: " + rel)
        return parse_json(raw, label)

    def members(self):
        """prepare_bundle.runtime_pins (prepare_bundle.py:36-52), same membership rule; every name gated first."""
        listing = self.read_pinned(S1_RUNTIME_PINS[0], self.pins["s1_runtime_pin_sha256"], "S1 runtime pin")
        listed = listing.get("files") if isinstance(listing, dict) else None
        # r6 (B1): the frozen rule is names = set(json.loads(...)["files"]) (prepare_bundle.py:42): the keys of the
        # pinned dict {name: sha256} (runtime-pin-r2 f81f3655, 1557 entries; S9 requires a dict) or a list's items.
        # The dict's per-file SHAs are never read by the frozen rule (17 differ from the bytes at P'), so not here.
        require(isinstance(listed, (dict, list)) and all(isinstance(n, str) for n in listed),
                "S1 runtime pin lacks a files dict (or list) of names")
        names = {relative(n, "S1 runtime-pin entry") for n in listed}
        for name in sorted(names):                     # every pin entry is name-gated before any member is hashed
            if guarded("S1 runtime-pin entry " + name, si.e5_blob_oid, name) is None:   # E5: gated by walk + hash_e5
                guarded("S1 runtime-pin entry " + name, si.gate_names, self.policy, self.role, name,
                        e4=name in si.E4_COMPLETE_JSON)
        names.update(rel for rel in list(self.sizes) + list(self.walk["e5"]) if rel.endswith(".py"))
        missing = sorted(name for name in names if not self.present(name))
        require(not missing, "Incomplete frozen runtime: " + repr(missing[:8]))
        stray = sorted(set(self.walk["e5"]) - names)
        require(not stray, "E5 entries that are not runtime members refused: " + repr(stray[:8]))
        for rel in self.walk["e4"]:                    # E4 non-members are checked (hash vs pin), never members
            self.sha(rel)
        result = {name: self.sha(name) for name in sorted(names)}
        qualified = self.read_pinned(S1_QUALIFIED, self.pins["s1_qualified_sha256"], "S1 qualified binding")
        files = qualified.get("qualified_source_files") if isinstance(qualified, dict) else None
        require(isinstance(files, dict), "S1 qualified binding lacks qualified_source_files")
        for name, expected in files.items():
            require(result.get(name) == expected, "Not the qualified S1 tier source: " + str(name))
        return result


def measurement_files(e4v3, pins=None):
    """Direct-caller API: the measurement inventory of <runtime>/E4V3_REL (same confined walk as plan_bundle)."""
    text = absolute(str(e4v3), "runtime e4v3")
    require(text.endswith("/" + E4V3_REL), "measurement_files needs <runtime>/" + E4V3_REL)
    root = text[:-len(E4V3_REL) - 1]
    return RuntimeInventory(runtime_policy(root), "runtime", active_pins()[0] if pins is None else pins).measurement()


def runtime_files(root, pins=None):
    """Direct-caller API: the frozen runtime membership with hashes (same confined walk as plan_bundle)."""
    pins = active_pins()[0] if pins is None else pins
    return RuntimeInventory(runtime_policy(root), "runtime", pins).members()



# ---------------------------------------------------------------- state index (mirror of frozen StateRows.__init__)

def check_state_index(index, model_pins, container_size):
    """state_rows.py:34-61 without unpickling: schema, protocol, source/container pins, contiguous positive rows,
    final length, unique IDs, container size. Stricter: integer types, string IDs, 64-hex row SHAs."""
    try:
        require(isinstance(index, dict) and index.get("schema") == STATE_ROWS_SCHEMA
                and is_int(index.get("pickle_protocol")) and index["pickle_protocol"] == STATE_ROWS_PROTOCOL,
                "Unsupported state index")
        source, container, entries = index["source"], index["container"], index["rows"]
        require(source["file"] == "states.pkl" and source["sha256"] == model_pins["states.pkl"],
                "State index is not derived from the pinned states.pkl")
        require(source.get("verified") is True, "State index was not converted from the SHA-verified states.pkl")
        require(container["file"] == "states-rows.bin" and container["sha256"] == model_pins["states-rows.bin"],
                "State index names a different container")
        require(isinstance(entries, list) and is_int(source["rows"]) and len(entries) == source["rows"],
                "State index row count differs from states.pkl")
        position = 0
        for entry in entries:
            require(isinstance(entry, dict) and is_int(entry["offset"]) and is_int(entry["length"])
                    and entry["offset"] == position and entry["length"] > 0, "Non-contiguous state index")
            require(isinstance(entry["id"], str) and is_sha(entry["sha256"]), "Malformed state index row")
            position += entry["length"]
        require(is_int(container["bytes"]) and position == container["bytes"], "State index length differs from its container")
        ids = [entry["id"] for entry in entries]
        require(len(set(ids)) == len(ids), "Duplicate fixed-state IDs")
    except (KeyError, TypeError, AttributeError):
        raise AssemblyError("Malformed state index") from None
    require(container_size == position, "State container size differs from its index")
    return ids




# ---------------------------------------------------------------- committed side (--repository HEAD; si.git_plan)

class Committed:
    """--repository through safe_input: an si.GitRepo (a linked/aliased .git refuses) and a 'repo' read role rooted at
    the work tree with exactly the names S4 reads (E1 alias + target, the END evidence, the E3 admissions, the four E4
    paths, and (r4b) the nine E5 paths; exemptions E1/E4/E5). git_plan phase 1 (metadata only) screens the WHOLE HEAD
    tree before any object read; E5 entries present at HEAD are pinned there (mode 100644, blob OID) and never read."""

    def __init__(self, repository, admission_rels):
        self.root = absolute(repository, "--repository")
        self.evidence_rel = EVIDENCE_REPO_DIR + "/" + EVIDENCE_FILE
        self.needed = (E1_ALIAS, E1_TARGET, self.evidence_rel) + tuple(admission_rels)
        exact = self.needed + tuple(si.E4_COMPLETE_JSON) + tuple(si.E5_PATHS)
        self.policy = guarded("--repository", si.Policy, this_host(), [guarded(
            "--repository", si.Role, "repo", self.root, "read", MAX_INPUT, exact=exact, exemptions=("E1", "E4", "E5"))])
        for rel in self.needed:
            guarded("repository path " + rel, si.gate_names, self.policy, "repo", rel)
        guarded("--repository", si.check_dir, self.policy, "repo")
        self.repo = guarded("--repository", si.GitRepo, work_tree=self.root)
        self.head = guarded("--repository HEAD", si.git_run, self.repo, ["rev-parse", "--verify", "HEAD^{commit}"],
                            60, 4096).stdout.decode().strip()
        require(COMMIT.fullmatch(self.head) is not None, "--repository HEAD is not a full commit id")
        wanted = set(self.needed) | set(si.E4_COMPLETE_JSON) | set(si.E5_PATHS)
        self.plan = guarded("--repository HEAD tree", si.git_plan, self.policy, "repo", self.repo, self.head,
                            members=lambda e: e["path"] in wanted)

    def entry(self, rel, label):
        hits = [f for f in self.plan.files if f["path"] == rel]
        require(len(hits) == 1, "Not committed at HEAD of --repository (" + label + "): " + rel)
        return hits[0]

    def blob(self, rel, expected, label, mismatch):
        """One planned regular blob: type, size and OID verified by si, then its SHA-256 == expected."""
        return guarded(label, self.plan.read, self.entry(rel, label), expected, mismatch=mismatch)

    def check_e1(self):
        """E1 (D2), committed side: the exact mode-120000 link (pinned OID; link blob read, never followed) whose
        target is a screened regular blob."""
        require(self.plan.e1 is not None, "E1 alias is not a committed mode-120000 entry at HEAD of --repository: "
                + E1_ALIAS)
        return guarded("E1 alias", self.plan.e1_check)

    def check_e4(self):
        """E4 at the build commit: phase 1 already refused any other complete.json and any wrong mode/OID, member or
        not; phase 2 hashes each present exempt blob (never parsed) against its ruled SHA-256."""
        return [guarded("E4 tracked " + e["path"], self.plan.hash_e4, e,
                        mismatch="Tracked E4 exempt complete.json differs from its pin: " + e["path"],
                        codes=("exemption",)) for e in self.plan.e4]

    def check_e5(self, runtime_oids):
        """E5 (r4b): every E5 member of the runtime is the E5 entry committed at HEAD (phase 1 pinned its mode 100644
        and blob OID; metadata only, the committed blob is never read) with the same OID as the shipped bytes."""
        committed = {e["path"]: e["oid"] for e in self.plan.e5}
        for rel, oid in sorted(runtime_oids.items()):
            require(committed.get(rel) == oid, "Runtime E5 entry is not committed at HEAD of --repository: " + rel)

    def verify_shipped_e1(self, runtime_policy):
        """E1 (D2), shipped side: the runtime's visualize_battle.py is a regular single-link file whose bytes equal
        the gated committed target blob."""
        return guarded("runtime E1 copy", self.plan.e1_verify_shipped, runtime_policy, "runtime",
                       mismatch="Runtime " + E1_ALIAS + " differs from the committed E1 target blob",
                       codes=("exemption", "size"))


def committed_bindings(values, host, pins):
    """--committed-admission NAME REPOSITORY_PATH SHA256 -> {name: (rel, sha)}; exactly the host's pinned set, each at
    its E3 path reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>. Pure (no access)."""
    required = set(pins["admissions"].get(host, {}))
    require(required, "No pinned admissions for host " + str(host))
    bindings = {}
    for name, rel, digest in values or ():
        require(name in ADMISSIONS and name not in bindings, "Unknown/duplicate --committed-admission: " + repr(name))
        rel = relative(rel, "committed admission path")
        require(REPO_PATH.fullmatch(rel) is not None, "Repository path has unsupported characters (" + name + ")")
        expected = ADMISSION_REPO_DIR + "/" + host + "-" + name
        require(rel == expected, "Committed admission must be exactly " + expected + " (E3): " + rel)
        require(is_sha(digest), "Committed admission SHA is not a SHA-256: " + name)
        bindings[name] = (rel, digest)
    require(set(bindings) == required, "--committed-admission is required for exactly " + repr(sorted(required))
            + " on " + host + " (got " + repr(sorted(bindings)) + ")")
    return bindings


# ---------------------------------------------------------------- planning (all checks; no writes)

def request_sources(request):
    """(label, absolute source) for every request input read through a Sources role (in request order); entries
    that are malformed or not absolute/normalized are skipped here and refused, in order, by the check that uses them."""
    out = []

    def add(label, value):
        if isinstance(value, dict) and isinstance(value.get("source"), str):
            try:
                out.append((label, absolute(value["source"], label)))
            except AssemblyError:
                pass
    models = request.get("models")
    if isinstance(models, dict):
        for name in MODEL_NAMES:
            add("model " + name, models.get(name))
    add("sets", request.get("sets"))
    guard = request.get("guard")
    if isinstance(guard, dict):
        add("guard freeze", guard.get("freeze"))
        if isinstance(guard.get("modules"), dict):
            for name in sorted(guard["modules"]):
                add("guard module " + str(name), guard["modules"][name])
        if isinstance(guard.get("seed_inputs"), dict):
            for name in sorted(guard["seed_inputs"]):
                add("seed " + str(name), guard["seed_inputs"][name])
    return out


def guard_job_name(host, job):
    """The guard job is a path on the TARGET host: pure checks only (form, parent, and the shared name gate under a
    remote policy for that host with the exact guard-job grant). Its freshness is a host-side gate (S3/S5/S7)."""
    require(isinstance(job, str) and os.path.normpath(job) == job and os.path.dirname(job) == JOB_PARENTS[host]
            and JOB_NAME.fullmatch(os.path.basename(job)) is not None,
            "Guard job must be " + JOB_PARENTS[host] + "/k4s-end-guard-r<N>-rd<RR>-a<NN> or -pf<NN> on " + host)
    remote = guarded("guard job", si.Policy, host, [guarded("guard job", si.Role, "guard-parent", JOB_PARENTS[host],
                                                            "write", 1 << 20, exact=(os.path.basename(job),),
                                                            grants=("guard-job",))], remote=True)
    guarded("guard job", si.gate_names, remote, "guard-parent", os.path.basename(job))
    return job


def plan_bundle(request, repository, committed):
    """Every check, in order. Returns (copies {bundle name: Copy}, manifest, facts)."""
    PINS, synthetic = active_pins()
    if not synthetic:                                  # a production run never uses an in-process edited layer
        require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input constants were changed in process")
    check_exemptions(PINS, synthetic)
    require(isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA, "Unsupported request schema")
    keys = {"schema", "host", "runtime_root", "runtime_files_sha256", "measurement_files_sha256", "topology", "sets",
            "models", "end_evidence", "guard"}
    require(set(request) == keys, "Request keys differ from the schema: " + repr(sorted(set(request) ^ keys)))
    host = request["host"]
    require(host in JOB_PARENTS, "Host is not a K4S END host: " + repr(host))
    copies = {}

    def add(name, copy):
        name = relative(name, "bundle name")
        require(name not in copies and name not in (MANIFEST, MANIFEST_SHA, RECEIPT), "Bundle name collision: " + name)
        copies[name] = copy
        return name

    # 0. names first: the repository, the runtime root and every request source are name-gated before any access
    require(repository is not None, "--repository must be an absolute path")
    bindings = committed_bindings(committed, host, PINS)
    sources = Sources(request_sources(request))
    runtime = runtime_policy(request["runtime_root"])
    repo = Committed(repository, [rel for rel, _ in bindings.values()])
    # E3 admissions, E1 and E4 at the build commit (whole-tree metadata already screened by git_plan phase 1)
    for name, (rel, digest) in sorted(bindings.items()):
        repo.blob(rel, digest, "committed admission " + name,
                  "Committed admission blob differs from --committed-admission SHA: " + name)
    repo.check_e1()
    repo.check_e4()

    # 1. runtime + e4v3 (the e4v3 that end_reference imports is ROOT/E4V3_REL of the runtime tree)
    inventory = RuntimeInventory(runtime, "runtime", PINS)
    measured = inventory.measurement()
    require(request["measurement_files_sha256"] == PINS["measurement_files_sha256"],
            "measurement_files_sha256 differs from the pinned inventory")
    require(canonical_sha(measured) == request["measurement_files_sha256"],
            "measurement_files differ from the request (computed " + canonical_sha(measured) + ")")
    require("spec-pins.json" in measured, "Missing input (e4v3 spec-pins): " + E4V3_REL + "/spec-pins.json")
    specification = inventory.read_pinned(E4V3_REL + "/spec-pins.json", measured["spec-pins.json"], "e4v3 spec-pins")
    runtime_map = inventory.members()
    require(is_sha(request["runtime_files_sha256"]) and canonical_sha(runtime_map) == request["runtime_files_sha256"],
            "runtime_files differ from the request (computed " + canonical_sha(runtime_map) + ")")
    if E1_ALIAS in runtime_map:                        # D2: the shipped copy equals the committed target blob
        repo.verify_shipped_e1(runtime)
    require(set(inventory.e5_oids) == set(inventory.walk["e5"]), "Runtime E5 entries were not all hashed")
    repo.check_e5(inventory.e5_oids)                   # r4b: E5 runtime members == committed E5 entries (metadata)

    # 2. models and state rows (tier_backend.py:459-461, :466-468; state_rows.py:34-61 mirrored, no pickle)
    models = request["models"]
    require(isinstance(models, dict) and set(models) == set(MODEL_NAMES), "Model inputs must be exactly " + repr(MODEL_NAMES))
    model_pins = {}
    for name in MODEL_NAMES:
        if name == "states-rows.json":
            continue
        copy = pinned_source(sources, models[name], "model " + name, PINS["models"][name])
        model_pins[name] = copy.sha256
        add(name, copy)
    copy, index = pinned_json(sources, models["states-rows.json"], "model states-rows.json",
                              PINS["models"]["states-rows.json"])
    add("states-rows.json", copy)
    ids = check_state_index(index, model_pins, copies["states-rows.bin"].size)

    # 3. sets: T1's own-tier sets exactly (canonical pin); TierBackend._load_inputs / corpus_loop shape
    _, sets = pinned_json(sources, request["sets"], "sets")
    require(isinstance(sets, dict) and {"golden", "speed"} <= set(sets) <= {"golden", "speed", "agreement", "packets"},
            "sets must hold golden and speed (optional agreement, packets) only")
    require(canonical_sha(sets) == PINS["sets_canonical_sha256"], "sets are not T1's pinned own-tier sets")
    require(isinstance(sets["speed"], dict) and set(sets["speed"]) == set(TIERS), "sets.speed must be exactly " + repr(TIERS))
    loaded = [sets["speed"][t] for t in TIERS] + [sets[k] for k in ("agreement", "packets") if k in sets]
    known = set(ids)
    for values in [sets["golden"]] + loaded:
        require(isinstance(values, list) and values and all(isinstance(v, str) for v in values)
                and len(set(values)) == len(values), "Every set must be a non-empty list of unique string IDs")
    for values in loaded:          # looked up by ID (backend.by_id / inputs); golden is only subtracted (tier_backend:147)
        require(set(values) <= known, "A set names a state absent from the pinned state index")

    # 4. topology: the pinned 128-logical-CPU Linux value (telemetry.validate_topology re-checks live in S5 preflight)
    topology = request["topology"]
    require(isinstance(topology, dict) and set(topology) == {"P", "E", "label"} and topology["E"] == []
            and isinstance(topology["label"], str) and topology["label"], "Topology must be {P, E: [], label}")
    p = topology["P"]
    require(isinstance(p, list) and p and all(type(c) is int and c >= 0 for c in p) and len(set(p)) == len(p),
            "Topology P must be unique non-negative logical CPU IDs")
    require(topology == PINS["topology"], "Topology differs from the pinned target-host topology")

    # 5. END evidence (committed at HEAD of --repository) + every artifact at its own relative path
    evidence = request["end_evidence"]
    require(isinstance(evidence, dict) and set(evidence) == {"source", "sha256", "artifacts_root"},
            "end_evidence must be {source, sha256, artifacts_root}")
    artifacts_root = repo.root + "/" + EVIDENCE_REPO_DIR
    require(evidence["artifacts_root"] == artifacts_root and evidence["source"] == artifacts_root + "/" + EVIDENCE_FILE,
            "END evidence must be --repository/" + EVIDENCE_REPO_DIR + "/" + EVIDENCE_FILE + " with that artifacts_root")
    require(is_sha(evidence["sha256"]), "Input SHA is not a SHA-256: END evidence")
    evidence_sha = evidence["sha256"]
    raw = guarded("END evidence", si.read_bytes, repo.policy, "repo", repo.evidence_rel, None, evidence_sha,
                  mismatch="Pin mismatch: END evidence")
    document = parse_json(raw, "END evidence")
    repo.blob(repo.evidence_rel, evidence_sha, "END evidence", "END evidence differs from its committed HEAD blob")
    add(EVIDENCE_NAME, Copy(repo.policy, "repo", repo.evidence_rel, evidence_sha, len(raw), "END evidence"))
    require(isinstance(document, dict) and document.get("schema") == EVIDENCE_SCHEMA
            and document.get("kind") == "counted-reporting", "Unsupported K4S END evidence")
    try:
        items = [document[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
        phases = document["phases"]
        require(isinstance(phases, list) and phases, "END evidence has no phases")
        items += [entry[f] for entry in phases for f in ("launch", "supervisor_exit", "mhz", "census")]
        phase_hosts = {entry["host"] for entry in phases}
    except (KeyError, TypeError, AttributeError):
        raise AssemblyError("Malformed END evidence") from None
    seen, commits = {}, set()
    for item in items:                                 # pure pass: every item named and shaped before any is opened
        require(isinstance(item, dict) and {"path", "sha256", "commit", "repository_path"} <= set(item),
                "END evidence item lacks path/sha256/commit/repository_path")
        name = relative(item["path"], "evidence item")
        require(item["repository_path"] == EVIDENCE_REPO_DIR + "/" + name,
                "END evidence item is not its repository path relative to the evidence: " + name)
        require(is_sha(item["sha256"]) and isinstance(item["commit"], str) and COMMIT.fullmatch(item["commit"]),
                "END evidence item needs a SHA-256 and a full commit: " + name)
        commits.add(item["commit"])
        if name in seen:
            require(seen[name] == item["sha256"], "Conflicting END evidence pin: " + name)
            continue
        seen[name] = item["sha256"]
    require(len(commits) == 1, "END evidence artifacts must be bound to one commit")
    art = guarded("evidence artifact", si.Policy, this_host(), [guarded(
        "evidence artifact", si.Role, "artifacts", artifacts_root, "read", MAX_INPUT, exact=tuple(sorted(seen)))])
    for name in sorted(seen):                          # the shared denylist + the strict END pair, before any open
        guarded("evidence artifact " + name, si.gate_names, art, "artifacts", name)
    for name in sorted(seen):
        found = guarded("END evidence artifact " + name, si.sha256_input, art, "artifacts", name)
        require(found["sha256"] == seen[name], "Pin mismatch: END evidence artifact " + name)
        add(EVIDENCE_DIR + "/" + name, Copy(art, "artifacts", name, seen[name], found["size"],
                                             "END evidence artifact " + name))
    plan_item = document["plan"]
    require(plan_item["sha256"] == PINS["k4s_plan_sha256"], "END evidence plan is not the frozen K4S plan")
    plan_name = EVIDENCE_DIR + "/" + relative(plan_item["path"], "plan")
    plan_copy = copies[plan_name]
    raw = guarded("K4S plan", si.read_bytes, plan_copy.policy, plan_copy.role, plan_copy.rel, None,
                  PINS["k4s_plan_sha256"], mismatch="Pin mismatch: K4S plan")
    try:
        plan = json.loads(raw)
        compute, study = plan["compute"], plan.get("study")
        hosts, forbidden = compute["hosts"], compute.get("forbidden_hosts", ())
        slot_count = compute["slots"]                       # console_rule false -> compute.slots (fleet_profile.py:17)
        idle_hosts = compute.get("idle_service_exception", {}).get("hosts", [])
    except (KeyError, TypeError, AttributeError, ValueError):     # no require() inside: AssemblyError is a ValueError
        raise AssemblyError("Malformed K4S plan") from None
    require(study == "PREREG-K4S", "Plan is not the K4S reporting plan")
    require(type(slot_count) is int and slot_count >= 2, "Plan compute.slots must be an integer >= 2")
    require(host in hosts and host not in forbidden, "Host absent/forbidden in plan")
    require(host in phase_hosts, "END evidence has no counted phase on this host")

    # 6. guard (fleet_validity.ReportingGuard.__init__ checks, mirrored; the frozen code re-checks on the host)
    guard = request["guard"]
    require(isinstance(guard, dict) and set(guard) == {"job", "freeze", "modules", "admissions", "seed_inputs"},
            "guard must be {job, freeze, modules, admissions, seed_inputs}")
    job = guard_job_name(host, guard["job"])
    copy, freeze = pinned_json(sources, guard["freeze"], "guard freeze", PINS["frozen_t1_sha256"])
    add(FREEZE_NAME, copy)
    for delta in GUARD_DELTAS:
        require(isinstance(freeze.get(delta), dict) and freeze[delta].get("verdict") == "CONFIRM",
                "Guard freeze lacks a CONFIRM " + delta)
    frozen_files = freeze.get("files")
    require(isinstance(frozen_files, dict), "Guard freeze lacks files")
    modules = guard["modules"]
    require(isinstance(modules, dict) and set(modules) == {m + ".py" for m in GUARD_MODULES},
            "Guard modules must be exactly the nine frozen T1 guard modules")
    for name in sorted(modules):
        expected = frozen_files.get("reports/explore/t1/" + name)
        require(is_sha(expected), "Guard module is not in the freeze: " + name)
        add(GUARD_ROOT + "/" + name, pinned_source(sources, modules[name], "guard module " + name, expected))
    admissions = guard["admissions"]
    pinned_admissions = PINS["admissions"][host]
    require(isinstance(admissions, dict) and set(admissions) == set(pinned_admissions),
            "Admissions on " + host + " must be exactly " + repr(sorted(pinned_admissions)))
    require("idle-services.json" not in admissions or host in idle_hosts, "Idle-service admission on a host without the exception")
    admission_map = {}
    for name in sorted(admissions):
        rel, committed_sha = bindings[name]
        entry = admissions[name]
        entry_shape(entry, "admission " + name)
        require(entry["source"] == repo.root + "/" + rel, "Admission source is not its committed copy: " + name)
        require(entry["sha256"] == committed_sha, "Input SHA differs from the pinned value: admission " + name)
        raw = guarded("admission " + name, si.read_bytes, repo.policy, "repo", rel, None, committed_sha,
                      mismatch="Pin mismatch: admission " + name)
        value = parse_json(raw, "admission " + name)
        require(isinstance(value, dict) and value.get("host") == host, "Admission is for a different host: " + name)
        if name == "system-bus-admission.json":
            identity = value.get("identity")
            require(isinstance(identity, dict) and set(identity) == set(BUS_KEYS) and identity.get("uid") == 103,
                    "System-bus admission identity malformed")
            require(identity == pinned_admissions[name]["identity"], "System-bus admission is not the pinned identity"
                    + STALE_IDENTITY)
        else:
            services = value.get("services")
            require(isinstance(services, list) and len(services) == 1 and all(
                isinstance(s, dict) and {"name", "service", "wrapper_trio"} <= set(s)
                and isinstance(s["wrapper_trio"], list) for s in services), "Idle-service admission malformed")
            require(services[0]["service"] == pinned_admissions[name]["service"],
                    "Idle-service admission is not the pinned service identity" + STALE_IDENTITY)
        admission_map[name] = add(ADMISSION_DIR + "/" + name, Copy(repo.policy, "repo", rel, committed_sha, len(raw),
                                                                   "admission " + name))
    seeds = guard["seed_inputs"]
    require(isinstance(seeds, dict), "seed_inputs must be a map")
    required, parsed = {}, {}

    def binding(b, label):
        require(isinstance(b, dict) and is_sha(b.get("sha256")), "Malformed frozen seed binding: " + label)
        name = relative(b.get("path"), "seed path")
        location_free("/" + name, "seed path")                   # repository-relative name: same name gates
        require(frozen_files.get(name) == b["sha256"], "Unpinned/unsafe OP-5 seed dependency: " + name)
        require(required.setdefault(name, b["sha256"]) == b["sha256"], "Conflicting seed binding: " + name)
        require(name in seeds, "Missing pinned OP-5 seed/join input: " + name)
        copy, value = pinned_json(sources, seeds[name], "seed " + name, b["sha256"])
        parsed[name] = copy
        return value
    bindings_list = freeze.get("parent_source_seeds", [])
    require(isinstance(bindings_list, list), "Malformed parent_source_seeds")
    for b in bindings_list:
        receipt = binding(b, "parent source")
        if isinstance(receipt, dict) and receipt.get("host") == "127x08":       # fleet_validity.py:105-106
            join = receipt.get("source_join")
            require(isinstance(join, dict), "08 seed lacks its source_join")
            for side in ("server", "client"):
                binding(join.get(side), "08 join " + side)
    require(set(seeds) == set(required), "OP-5 seed input map differs from frozen seed/join dependencies")
    seed_map = {name: add(SEED_DIR + "/" + name, parsed[name]) for name in sorted(parsed)}

    # 7. manifest (key order irrelevant: written canonically)
    files = {name: copy.sha256 for name, copy in copies.items()}
    profile = dict(PROFILE, host=host, slot_count=slot_count, plan=plan_name, end_evidence=EVIDENCE_NAME,
                   guard=dict(root=GUARD_ROOT, job=job, freeze=FREEZE_NAME, admissions=admission_map, seed_inputs=seed_map))
    manifest = dict(schema=BUNDLE_SCHEMA, final=False, profile="fleet-reference", threshold=THRESHOLD,
                    specification=specification, files=files, runtime_files=runtime_map, measurement_files=measured,
                    topology=topology, sets=sets, reference_load_profile=profile)
    if synthetic:
        manifest["k4s_s4_synthetic"] = SYNTHETIC_STAMP
    facts = dict(synthetic=synthetic, pins_sha256=canonical_sha(PINS), repository=repo.root, repository_head=repo.head,
                 committed_admissions={n: dict(repository_path=r, sha256=s) for n, (r, s) in sorted(bindings.items())},
                 e5_runtime_exempt=sorted(inventory.walk["e5"]), safe_input_sha256=SAFE_INPUT_SHA256,
                 trees=(request["runtime_root"], artifacts_root, repo.root))
    return copies, manifest, facts


# ---------------------------------------------------------------- writing (only after every check passed)

def manifest_bytes(manifest):
    return (canonical(manifest) + "\n").encode()


class Output:
    """--out through safe_input: a write role rooted at its (canonical) parent allowing exactly <out> and the
    <out>.partial stage, and a read role on the stage for re-hashing every copy."""

    def __init__(self, out, facts):
        text = absolute(out, "--out") if isinstance(out, str) else None
        require(text is not None and text.count("/") >= 1 and split(text)[1], "--out must be a new normalized absolute directory")
        self.parent, self.name = split(text)
        require(self.parent != "/", "--out must be a new normalized absolute directory")
        self.out, self.stage = text, self.name + ".partial"
        if facts["synthetic"]:
            require(SYNTHETIC_MARKER in self.name, "Synthetic (test-only) pins require an --out named *SYNTHETIC*")
        for tree in facts["trees"]:
            require(not (text == tree or text.startswith(str(tree) + "/")), "--out must not be inside an input tree: "
                    + str(tree))
        roles = [guarded("--out", si.Role, "out", self.parent, "write", MAX_INPUT, exact=(self.name, self.stage),
                         patterns=(self.stage + "/**",)),
                 guarded("--out", si.Role, "stage", self.parent, "read", MAX_INPUT, patterns=(self.stage + "/**",))]
        self.policy = guarded("--out", si.Policy, this_host(), roles)
        guarded("--out", si.gate_names, self.policy, "out", self.name)
        guarded("--out", si.gate_names, self.policy, "out", self.stage)
        guarded("--out parent", si.check_dir, self.policy, "out")
        guarded("--out", si.check_absent, self.policy, "out", self.name,
                mismatch="--out must be a new absolute directory", codes=("exists",))
        guarded("--out", si.check_absent, self.policy, "out", self.stage,
                mismatch="A previous partial bundle exists: " + text, codes=("exists",))


def check_out(out, facts):
    return Output(None if out is None else str(out), facts)


def write_bundle(copies, manifest, out, request, request_sha, facts):
    """Stage everything in <out>.partial through si.Writer (exclusive mkdir/create, no-follow, fsync), copy each input
    from its si-gated descriptor with its expected SHA-256 and size (plain independent copies, R7), re-hash every copy
    through the stage read role, then publish the stage with one rename relative to the canonical parent descriptor
    after si.check_absent(<out>). A failure keeps the partial stage (never deleted)."""
    target = check_out(out, facts)
    made = set()
    with guarded("--out", si.Writer, target.policy, "out") as writer:
        guarded("--out stage", writer.mkdir_excl, target.stage)
        for name, copy in sorted(copies.items()):
            parts = name.split("/")
            for i in range(1, len(parts)):
                directory = target.stage + "/" + "/".join(parts[:i])
                if directory not in made:
                    guarded("bundle directory " + name, writer.mkdir_excl, directory)
                    made.add(directory)
            rel = target.stage + "/" + name
            guarded("copy " + name, si.copy_input, copy.policy, copy.role, copy.rel, writer, rel, copy.sha256,
                    copy.size, 0o444, mismatch="Source changed while copying: " + name)
            found = guarded("copy " + name, si.sha256_input, target.policy, "stage", rel, copy.size)
            require(found["sha256"] == copy.sha256, "Copy differs from its pin: " + name)
        data = manifest_bytes(manifest)
        digest = hashlib.sha256(data).hexdigest()
        guarded("manifest", writer.create_excl, target.stage + "/" + MANIFEST, data, 0o444)
        guarded("manifest", writer.create_excl, target.stage + "/" + MANIFEST_SHA,
                (digest + "  " + MANIFEST + "\n").encode(), 0o444)
        status = SYNTHETIC_STAMP if facts["synthetic"] else "CANDIDATE"
        receipt = dict(schema=RECEIPT_SCHEMA, request_sha256=request_sha, manifest_sha256=digest,
                       files=len(manifest["files"]), host=request["host"], guard_job=request["guard"]["job"],
                       assembler_sha256=facts["assembler_sha256"], safe_input_sha256=facts["safe_input_sha256"],
                       repository_head=facts["repository_head"], e5_runtime_exempt=facts["e5_runtime_exempt"],
                       pins_sha256=facts["pins_sha256"], production_pins=not facts["synthetic"],
                       committed_admissions=facts["committed_admissions"], final=False, outcomes_read=False,
                       live_actions=False, status=status)
        guarded("receipt", writer.create_excl, target.stage + "/" + RECEIPT, (canonical(receipt) + "\n").encode(), 0o444)
    publish(target)
    return digest


def publish(target):
    """The one write safe_input r3 has no primitive for (a directory publish): rename <out>.partial -> <out> relative
    to the canonical parent descriptor (si.open_root), immediately after si.check_absent(<out>); the check/rename
    window is the accepted concurrent-replacement residual. Then fsync the parent."""
    guarded("--out", si.check_absent, target.policy, "out", target.name,
            mismatch="--out appeared during assembly", codes=("exists",))
    parent = guarded("--out parent", si.open_root, target.parent)
    try:
        os.rename(target.stage, target.name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--request", required=True)
    ap.add_argument("--request-sha256", required=True)
    ap.add_argument("--repository", required=True, help="K4S repository checkout holding the committed evidence/admissions")
    ap.add_argument("--committed-admission", nargs=3, action="append", metavar=("NAME", "REPOSITORY_PATH", "SHA256"),
                    help="committed Q2 admission copy (required: bus on both hosts; idle-services on 127x03)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    request_path = absolute(a.request if a.request.startswith("/") else os.getcwd() + "/" + a.request, "--request")
    own = absolute(os.path.abspath(__file__), "assembler")
    parents = [split(own), split(request_path)]
    policy = guarded("--request", si.Policy, this_host(), [
        guarded("assembler", si.Role, "assembler", parents[0][0], "read", 16 << 20, exact=(parents[0][1],)),
        guarded("--request", si.Role, "request", parents[1][0], "read", 64 << 20, exact=(parents[1][1],))])
    guarded("--request", si.gate_names, policy, "request", parents[1][1])
    assembler = guarded("assembler", si.sha256_input, policy, "assembler", parents[0][1])["sha256"]
    require(is_sha(a.request_sha256), "Request SHA mismatch")
    raw = guarded("--request", si.read_bytes, policy, "request", parents[1][1], None, a.request_sha256,
                  mismatch="Request SHA mismatch")
    request = parse_json(raw, "request")
    copies, manifest, facts = plan_bundle(request, a.repository, a.committed_admission)
    facts["assembler_sha256"] = assembler
    check_out(a.out, facts)
    if a.dry_run:
        sys.stdout.buffer.write(manifest_bytes(manifest))
        sys.stdout.flush()
        print(canonical(dict(dry_run=True, manifest_sha256=hashlib.sha256(manifest_bytes(manifest)).hexdigest(),
                             files=len(manifest["files"]), production_pins=not facts["synthetic"], written=False,
                             assembler_sha256=assembler)),
              file=sys.stderr)
        return 0
    digest = write_bundle(copies, manifest, a.out, request, a.request_sha256, facts)
    print(canonical(dict(dry_run=False, manifest_sha256=digest, files=len(manifest["files"]), out=str(a.out),
                         production_pins=not facts["synthetic"], assembler_sha256=assembler)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssemblyError as error:
        print("ASSEMBLY REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
