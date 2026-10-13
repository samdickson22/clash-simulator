#!/usr/bin/env python3
"""S2 (PREREG-K4S END, RC-4b): END evidence builder + offline validator + clock diagnosis. r4. 127x05 only; no ssh.

CANDIDATE: requires Sol review before use.

build          Writes the ``clasher.k4s.end-evidence.v1`` document (kind ``counted-reporting``) for the frozen
               ``end_evidence.end_evidence``. Every artifact item is {path, sha256, commit, repository_path}: ``commit``
               is the single --commit X that holds every artifact, ``repository_path`` the fixed repo path of its
               role, ``path`` that path relative to the evidence file's directory (evidence location
               ``reports/explore/k4s-confirm/end-evidence.json``, OUTSIDE the strict ``end/`` namespace). Bytes and
               SHAs come from si.git_show_file(X, <repository_path>) only (never the work tree), each with its
               expected SHA-256 (record pins; completion-bound exits; the table of record; the verified S1 receipt).
               Refuses to overwrite.

validate       Fail closed, in this order, and BEFORE ANY ARTIFACT READ:
               1. Stdlib-only bootstrap: the raw K4S manifest (code root) must hash to the approved 74314eda; every
                  file it pins (K4S, END, reused read-only TIERS/e4v3, kernel) is read no-follow and hashed; the frozen
                  modules S2 uses (k4s_logic, end_evidence, fleet_end, fleet_profile, receipts) are later executed
                  from THOSE verified bytes by a meta-path loader; every other non-stdlib import is refused.
               2. The evidence (fixed repo path, no-follow read, --evidence-sha256) has exactly the S2 layout; every
                  artifact item has exactly its role's repository_path (records; per host/phase phase-meta and
                  end-sources), commit X, and ``path`` == repository_path relative to the evidence; record SHAs ==
                  the pins; in production launch/exit SHAs == the committed table and mhz/census == the verified S1
                  receipt; host/phase set == the pinned completion's counted_host_phases.
               3. Every artifact's committed blob (si.git_show_file) and work-tree file (si descriptor gate:
                  canonical root, every component O_NOFOLLOW, leaf regular with st_nlink == 1) has the item's SHA.
                  The frozen reader's own git calls then run only inside frozen_git_env() (ruling 21:28Z: os.environ
                  replaced by the P2-4 environment, declared GIT_DIR/GIT_WORK_TREE) on a checkout with no
                  refs/replace/ that si's static preflight accepts.
               Then the frozen end_evidence.end_evidence(), record bindings, membership, per counted host the frozen
               fleet_profile.slot_layout + fleet_end.host_reporting, and the reporting half of compare_mhz (every
               occupied physical core present, each finite > 0 MHz). On a clock-join refusal the outcome-blind clock
               diagnosis of that host is attached; the frozen refusal stands.

diagnose-clock Outcome-blind census/MHz join diagnosis (health fields utc/host/inflight/slots/MHz only): per
               host/phase the counts, duplicate/wrong-host census rows, unmatched census and MHz utc keys with line
               positions, slot mismatches, full-occupancy rows, and the first frozen host_reporting rule that would
               refuse. It never repairs, filters, re-times or zips rows. Exit 0 = every join clean, 3 = mismatch
               found (diagnosed), 2 = refusal.

r4 (r4b: layer r3): every file read/hash/stat/open and every write goes through the shared safe_input r3 layer
(vendored byte-identical as safe_input.py; r5, END-FULL-F1: read ONLY through the canonical bootstrap r1, i.e.
normalized path, outcome-name gate on every component, O_NOFOLLOW component walk from /, single-link regular file of
the pinned size BEFORE any byte is read; SHA-256 806e5ebb verified with hashlib before exactly those bytes are
executed, constants fingerprint 33f594ed; r3 = r2 + ruling E5, and S2 grants no E-exemption, so the nine E5 names refuse here), and
every git call through si.git_run / si.git_show_file (P2-4: scrubbed environment, fresh empty HOME, replacement
objects off, hooks/fsmonitor off, transports off, explicit --git-dir/--work-tree, static refusal of alternates/grafts/
shallow/gitfiles/undeclared commondir/driver config, object type+size+OID verified, rc checked before stdout).
A linked-worktree checkout must declare --git-dir and --git-common-dir.

Location gate (every entrypoint, EVERY explicit path: --repository, --code-root, --out, --result, --s1-manifest,
--s1-dest, --profile-json, --git-dir, --git-common-dir), BEFORE any stat/open/read/hash of it: (1) lexical, no system
call: absolute, normalised, safe characters, NOT a refused location (the shared case-insensitive safe_input family
denylist on every component: games, hub-blocks, *complete*.json, *interference*.json, *hub-ack*.json, *end-raw*.json,
END-JOB*, END-FINAL*, attempt-*.json and their variants; the strict END pair; k4s-confirm-*/k4s-end-guard-* jobs;
FROZEN-T1 launch namespaces; plus S2's stricter local rules: any 'end' component, any t1-* tree, the host job roots
/mpac/sdicks02/jobs and /mpac/sdicks02/jobs-k4s), and inside its allowed root (checkouts: /mpac/sdicks02/repos/clasher
or /tmp/k4s-s2-<name>; S1 receipt/dest, profile, result: strictly below /mpac/sdicks02/k4s-runner/run-r1/end-prep;
build --out: exactly the evidence path in --repository); (2) one si.Policy (host 127x05) declares a role per path
(directories: their exact names/patterns; files: their exact leaf; outputs: a write role with the exact leaf) and si
checks it: si.check_dir, si.open_input (descriptor gate; the open descriptor is the one later read, with the expected
SHA-256) or si.check_absent. Artifact, evidence and frozen-code paths inside a checkout pass the same lexical predicate
and their role allowlists. Profiles are validated strictly (no default fallback).

Production vs test: the defaults are the records of run r1. Every override (record pins, hosts, membership,
evidence path, warm-up, --no-manifest-check) is TEST-ONLY: it requires --test-mode AND the environment
K4S_S2_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION, and a test-mode run can only write a TEST-ONLY result schema
(test_mode=true); a production result is never produced in test mode. In test mode every allowed root is replaced by
K4S_S2_TEST_ROOT (strictly below /tmp/); the outcome/strict-END refusals, the lstat walk and nlink are unchanged.

Offline limits: slot_layout is called with host = the counted host and nice = the plan's nice, so its live
host/priority gate is NOT exercised here (it runs on host, pre-claim). The profile is the S4 bundle's
reference_load_profile (--profile-json + --profile-json-sha256: {host: profile}, every counted host, each a
non-empty object validated field by field: host == its key, reference_slot the int 0, slot_count the int 11,
console_rule the bool false, warmup_seconds a finite number >= 300, perception "none"; only the S4 extras plan,
end_evidence, amendment (strings) and guard (object) besides; duplicate keys and NaN/Infinity refused) or, explicitly
acknowledged with --declared-default-profile, the declared S4 profile (slot 0, 11 slots, console_rule false, warmup
300 s, perception none). Exactly one of the two, in every mode; the result records which (path + SHA-256).
"""
import argparse
import contextlib
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import math
import os
import posixpath
import re
import stat
import sys
import sysconfig
import tempfile
import time
import types
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

# ---------------------------------------------------------------- the shared safe_input layer (P2-1, P2-4; r4; r5)
# safe_input r3 is vendored byte-identical next to this file. r5 (END-FULL-F1): it is read ONLY through the canonical
# bootstrap r1 below (bootstrap-r1/k4s_bootstrap_r1.py, pasted verbatim between its BEGIN/END lines; the pins stay
# outside): the path (default: next to __file__, never resolved or normalized) must be absolute and normalized, every
# component must pass the safe_input r3 outcome-name families, the walk opens every ancestor O_DIRECTORY|O_NOFOLLOW from
# "/", and the leaf must be a regular single-link file of exactly SAFE_INPUT_SIZE bytes BEFORE any byte is read; exactly
# those bytes are hashed (SHA-256 pin) and executed (no re-open, no import path, no .pyc). Then the constants fingerprint
# must equal the README pin, BEFORE any other S2 code touches a path.
SAFE_INPUT_FILE = "safe_input.py"
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_SIZE = 133606
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
SAFE_INPUT_MODULE = "_k4s_s2_safe_input_r3"

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
    """The vendored layer through the canonical bootstrap (refusal: RuntimeError, as before), then its fingerprint."""
    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path
    module = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, SAFE_INPUT_MODULE, RuntimeError)
    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:
        raise RuntimeError("S2: safe_input constants fingerprint differs from the pinned r3 value")
    return module


si = load_safe_input()

EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
RESULT_SCHEMA = "clasher.k4s.end-evidence-validation.v2"
TEST_RESULT_SCHEMA = "clasher.k4s.end-evidence-validation.TEST-ONLY.v2"
DIAGNOSIS_SCHEMA = "clasher.k4s.end-clock-diagnosis.v1"
TEST_DIAGNOSIS_SCHEMA = "clasher.k4s.end-clock-diagnosis.TEST-ONLY.v1"
S1_SCHEMA = "clasher.k4s.end-sources-copy.v2"
S1_TEST_SCHEMA = "clasher.k4s.end-sources-copy.TEST-ONLY.v2"
TEST_ENV, TEST_MARKER = "K4S_S2_TEST_MODE", "SYNTHETIC-NOT-FOR-PRODUCTION"
STUDY = "reports/explore/k4s-confirm"
END_DIR = STUDY + "/end"
EVIDENCE_REL = STUDY + "/end-evidence.json"
PLAN = STUDY + "/plan.json"
COMPLETION = STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"
INVENTORY = STUDY + "/run-r1/completion-v2/counted-inventory.json"
LEDGER = STUDY + "/run-r1/ledger/blind-ledger-final.json"
PHASE_META = STUDY + "/run-r1/phase-meta/{host}-{phase}/{name}"
SOURCES = STUDY + "/end-sources/{host}/{phase}/{name}"
K4S_MANIFEST = STUDY + "/mac/K4S-MAC-MANIFEST.json"
APPROVED_K4S_MANIFEST_SHA256 = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
NATIVE_PROVENANCE_SHA = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"   # k4s_logic.py:29
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
# The frozen modules S2 executes, and the manifest pin section that must hold each file.
SERVED = {"k4s_logic": ("k4s_files", STUDY + "/mac/k4s_logic.py"),
          "end_evidence": ("end_files", STUDY + "/end_evidence.py"),
          "fleet_end": ("reused_readonly", E4V3_REL + "/fleet_end.py"),
          "fleet_profile": ("reused_readonly", E4V3_REL + "/fleet_profile.py"),
          "receipts": ("reused_readonly", E4V3_REL + "/receipts.py")}
DEFAULTS = dict(plan="38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf",
                completion="3794d953efb2c8af47a09ccb086cc0441f1c0dd9ea7a4f46e331315972c6e891",
                counted_inventory="22c41cb7624ca04d111b08af9273af074d016efd439a7b0f7f8cccb103aa0f7e",
                blind_ledger="649272bdae066e49a524bd46e0155cdaf99f6d1b543e78014d357e1eb18a4f08")
DEFAULT_HOSTS = ("127x03", "127x04")
DEFAULT_BLOCKS, DEFAULT_LOSSES = 3900, 99
PHASE_NAMES = ("reporting", "replacement-r1", "replacement-r2", "replacement-r3", "replacement-r4")
PRODUCTION_PHASES = {h: list(PHASE_NAMES) for h in DEFAULT_HOSTS}
# Committed phase-meta (launch.json, supervisor-exit.json) SHA-256, identical to S1's EXPECTED table.
EXPECTED_META = {
    ("127x03", "reporting"): ("116f1ed5f998649ba950fbde08846b47b052294acbbb6432b4a04b2a324e0159",
                              "88debddf7bf33c1b0bc2f14002339c87072be956398d90bfb727c2d0c36a1033"),
    ("127x03", "replacement-r1"): ("b864703e102d9dea314e1b332ee1415518f90153a0a633a9c2b1b0ac0ca1a70b",
                                   "bffde5d4008b2a47fc867e690f18d6ae087fd09e58464816f9a2fa60dddb5efa"),
    ("127x03", "replacement-r2"): ("1d917968d9875f89c2024ba173fb1a16fcdaf8b7a5f6a5504fe3bc7b6b9df299",
                                   "834fc2475b5a071d1564076b77403d83b983dbdf2026f4ccccf7df84012c3e3f"),
    ("127x03", "replacement-r3"): ("6c49a6679c1c654879a071c44a86cda952fb40bc1722af43e3b2c22914b13efb",
                                   "cccb86839ef970ae6e9bda6a8bb3b10451aa73baad8ac0978750f7c654688616"),
    ("127x03", "replacement-r4"): ("e8f72fb483e73b5bcbb78b4aa129e5b31c61b4e2f0c45fec67d6b9637f65f2e6",
                                   "c9066d63cd1aa73de74d2214498dc7543d2d863282d3593887aec2f65642027c"),
    ("127x04", "reporting"): ("7cd6b140551d8f1d66858d98b3cf2d74b14339e7d334e6b4fc3650a3fa383c48",
                              "c0a935f6cd1ecf022bf197dc3e88604769491bb461973bcd3c106e393aa71084"),
    ("127x04", "replacement-r1"): ("420f7ec1076885ddb0c0211a39bcfa0d0ced72b9c9c3856c382eef1f4f727f0e",
                                   "c11ae500e34504872095ba1d2b50d836546923c14641684d6ab97f635e4114b2"),
    ("127x04", "replacement-r2"): ("ea88e4d5c11590390875bfc8c044f5027950349e70bdd3f5b3eef82f3683cf32",
                                   "37aafa6a128757e80082d0fbad6a1e518de88a277e342538cb2f33dbbdfc8e8b"),
    ("127x04", "replacement-r3"): ("9cd6bc37da5638dbc95a065cfd47ad467980d9b348bef2d7a711f8f9a7b4264e",
                                   "91475244cc702e33dbf0a4fd20635dcb5b2fa435b21361094263723fc4cd414c"),
    ("127x04", "replacement-r4"): ("38730d445b2a8095cbad8b393f709fbf5e0a79eb0267d6eb69c9875c2ee6c69a",
                                   "21269aa00b3340f8b75a02de5526c5f20d525d3af27a2b1c0ac6d56f8fc47cb9"),
}
REPORTING_SLOTS = 11                                  # plan compute.slots == every counted launch's slots
TOP_FIELDS = frozenset(("schema", "kind", "plan", "completion", "blind_ledger", "counted_inventory", "phases"))
ITEM_FIELDS = frozenset(("path", "sha256", "commit", "repository_path"))
PHASE_FIELDS = frozenset(("host", "phase", "launch", "supervisor_exit", "mhz", "census"))
RECORDS = (("plan", PLAN), ("completion", COMPLETION), ("counted_inventory", INVENTORY), ("blind_ledger", LEDGER))
PHASE_FILES = (("launch", PHASE_META, "launch.json"), ("supervisor_exit", PHASE_META, "supervisor-exit.json"),
               ("mhz", SOURCES, "mhz.jsonl"), ("census", SOURCES, "census.jsonl"))
# end_evidence.JOB_LIKE / FINAL_LIKE / CLAIM_LIKE: the evidence file must never look like an END authority.
AUTHORITY_LIKE = re.compile(r"(END-JOB.*|END-FINAL.*|attempt-.*)\.json", re.IGNORECASE)
# forbidden_reason(): the shared safe_input family denylist (si.name_gate) plus S2's stricter local location rules.
T1_JOB_TREE = re.compile(r"t1-.*", re.IGNORECASE)
HOST_JOB_ROOTS = ("/mpac/sdicks02/jobs", "/mpac/sdicks02/jobs-k4s")
S2_HOST = "127x05"                                    # si.Policy host (test mode: the fleet host running the tests)
# Allowed roots (production). Test mode: strictly below K4S_S2_TEST_ROOT, itself strictly below /tmp/.
MAIN_CHECKOUT = "/mpac/sdicks02/repos/clasher"
TMP_CHECKOUT = re.compile(r"/tmp/k4s-s2-[A-Za-z0-9._-]+")
PREP_ROOT = "/mpac/sdicks02/k4s-runner/run-r1/end-prep"
TEST_ROOT_ENV = "K4S_S2_TEST_ROOT"
S1_MANIFEST_NAME = "s1-copy-manifest.json"
# reference_load_profile: the fields the frozen slot_layout/host_reporting read, and the S4 bundle extras.
PROFILE_REQUIRED = ("host", "reference_slot", "slot_count", "console_rule", "warmup_seconds", "perception")
PROFILE_EXTRAS = {"plan": str, "end_evidence": str, "amendment": str, "guard": dict}
MIN_WARMUP_SECONDS = 300                              # fleet_profile.py:27
HOST_NAME = re.compile(r"127x[0-9]{2}")
PHASE_NAME = re.compile(r"reporting|replacement-r[1-9][0-9]*")     # end_evidence.registered_phase
SAFE_PART = re.compile(r"[A-Za-z0-9._-]+")
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
TEST_ONLY_OPTIONS = ("expect_plan", "expect_completion", "expect_counted_inventory", "expect_blind_ledger",
                     "expect_hosts", "expect_blocks", "expect_losses", "evidence_repository_path", "warmup_seconds")


class S2Error(RuntimeError):
    """Fail-closed S2 refusal (never an assert: the checks hold under python -O)."""


def require(condition, message):
    if not condition:
        raise S2Error(message)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def si_refusal(label, error):
    """A safe_input Refusal as an S2Error: '<label>: safe_input refused [<code>]: <reason>'."""
    return S2Error(f"{label}: safe_input refused [{error.code}]: {error.reason}")


def guarded(label, function, *args, **kwargs):
    """Call a safe_input function; its Refusal becomes an S2Error naming the label (fail closed, never an assert)."""
    try:
        return function(*args, **kwargs)
    except si.Refusal as error:
        raise si_refusal(label, error) from None


def this_host(testing):
    """The si.Policy host: S2 is a 127x05-only tool; test mode runs on whichever fleet host runs the tests."""
    node = os.uname().nodename.split(".")[0]
    require(node in si.HOSTS, f"S2 must run on a fleet host, not {node!r}")
    require(testing or node == S2_HOST, f"S2 runs on {S2_HOST} only (this is {node})")
    return node


# ---------------------------------------------------------------- git: every call through si.git_run (P2-4; S2-R3-F1)

class Checkout:
    """A declared checkout: its si.GitRepo (work tree; a linked worktree must declare git_dir + common_dir) and the
    si.Policy whose 'repository' role is rooted at it. Every git command is si.git_run: scrubbed environment, fresh
    empty HOME, --no-replace-objects + GIT_NO_REPLACE_OBJECTS=1, hooks/fsmonitor off, transports off, explicit
    --git-dir, static refusal of alternates/grafts/shallow/gitfile/undeclared commondir/driver config, rc checked
    before stdout is visible. Object bytes come only from si.git_show_file (type, size and OID verified)."""

    def __init__(self, policy, role, path, git_dir=None, common_dir=None):
        self.policy, self.role, self.path = policy, role, path
        self.repo = guarded("--repository", si.GitRepo, work_tree=path, git_dir=git_dir, common_dir=common_dir)

    def run(self, args, label, ok_rcs=(0,), limit=1 << 20):
        return guarded(label, si.git_run, self.repo, list(args), 120, limit, None, ok_rcs).stdout

    def show(self, commit, rel, expected_sha256, label, mismatch=None, cap=64 << 20):
        """HEAD-independent bytes of commit:rel (a regular tracked blob), refused unless its SHA-256 is expected
        (a SHA refusal reads `mismatch` when given)."""
        return expected_read(label, mismatch, si.git_show_file, self.policy, self.role, self.repo, commit, rel, cap,
                             expected_sha256)

    def no_replace_refs(self):
        """Frozen-reader precondition (21:28Z): the clone carries no replacement refs at all."""
        listing = self.run(["for-each-ref", "--format=%(refname)", "refs/replace/"], "replace refs")
        require(listing == b"", "the checkout carries refs/replace/ entries (replacement objects), refused")


def full_commit(checkout, commit):
    require(isinstance(commit, str) and COMMIT.fullmatch(commit) is not None, "--commit must be a full 40-hex commit")
    resolved = checkout.run(["rev-parse", "--verify", commit + "^{commit}"], "rev-parse").decode().strip()
    require(resolved == commit, "commit does not resolve to itself: " + commit)
    return commit


@contextlib.contextmanager
def frozen_git_env(checkout):
    """Ruling 2026-10-12 21:28Z (frozen-reader interim): the frozen readers (fleet_end.artifact's own `git -C ... show`
    and `merge-base`) run only with os.environ REPLACED by the P2-4 environment (si.GIT_FIXED_ENV: no inherited GIT_*,
    GIT_NO_REPLACE_OBJECTS=1, no system/global config, PATH=/usr/bin:/bin) plus a fresh empty HOME and the DECLARED
    GIT_DIR / GIT_WORK_TREE, and only on a checkout that si has pre-verified (static preflight inside every si.git_run;
    no refs/replace/). The previous environment is restored afterwards; git must leave the HOME empty."""
    checkout.no_replace_refs()
    saved = dict(os.environ)
    home = tempfile.mkdtemp(prefix="s2-frozen-git-home-")
    try:
        os.environ.clear()
        os.environ.update(si.GIT_FIXED_ENV)
        os.environ.update(HOME=home, XDG_CONFIG_HOME=home + "/xdg-config-absent", GIT_DIR=checkout.repo.git_dir,
                          GIT_WORK_TREE=checkout.repo.work_tree)
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
        try:
            os.rmdir(home)
        except OSError:
            raise S2Error(f"frozen git wrote into its empty HOME {home} (kept)") from None


# ---------------------------------------------------------------- the location gate (every explicit path, pure first)

def forbidden_reason(path):
    """Pure (no system call): why `path` is a refused location, or None. The shared safe_input family denylist
    (si.name_gate: outcome and END-claim name families, case-insensitive, any component; the strict END pair; K4S
    reporting / guard job components; FROZEN-T1 launch namespaces; the v4 cache repo), plus S2's stricter local
    location rules: no 'end' component at all, no t1-* job tree, neither host job root."""
    text = path if path.startswith("/") else "/" + path
    try:
        si.name_gate(text, S2_HOST, ())
    except si.Refusal as error:
        if error.code == "name":                              # syntax ('path') is lexical()'s own, earlier check
            return f"{error.code}: {error.reason}"
    for part in path.split("/"):
        if part.lower() == "end":
            return f"strict-END component {part!r}"
        if T1_JOB_TREE.fullmatch(part):
            return f"T1 job tree {part!r}"
    for root in HOST_JOB_ROOTS:
        if text == root or text.startswith(root + "/"):
            return "host job tree " + root
    return None


def lexical(path, label):
    """Pure: an absolute, normalised, safe-character path that is not a forbidden location."""
    require(isinstance(path, str) and path.startswith("/") and not path.startswith("//") and path != "/"
            and posixpath.normpath(path) == path, f"{label}: not an absolute normalised path: {path!r}")
    require(all(SAFE_PART.fullmatch(p) for p in path.split("/")[1:]), f"{label}: unsafe path characters: {path!r}")
    reason = forbidden_reason(path)
    require(reason is None, f"{label}: forbidden location ({reason}), refused before any access: {path}")
    return path


class Roots:
    """Allowed roots per role. Production: fixed. Test mode: strictly below K4S_S2_TEST_ROOT (below /tmp/)."""

    def __init__(self, testing):
        value = os.environ.get(TEST_ROOT_ENV)
        if not testing:
            require(value is None, f"{TEST_ROOT_ENV} is a TEST-ONLY setting (present in production)")
        else:
            require(value is not None, f"test mode requires {TEST_ROOT_ENV}")
            lexical(value, TEST_ROOT_ENV)
            require(value.startswith("/tmp/"), f"{TEST_ROOT_ENV} must lie strictly below /tmp/")
        self.test_root = value if testing else None
        self.testing = testing

    def checkout(self, path):
        if self.test_root:
            return path.startswith(self.test_root + "/")
        return path == MAIN_CHECKOUT or TMP_CHECKOUT.fullmatch(path) is not None

    def prep(self, path):
        return path.startswith((self.test_root or PREP_ROOT) + "/")

    def worktree_git_dirs(self, checkout, git_dir, common_dir):
        """A linked (detached) worktree checkout must declare its git dir and common dir (si.GitRepo); production:
        only a /tmp/k4s-s2-<name> checkout of the main repository, git dir <main>/.git/worktrees/<name>."""
        if git_dir is None and common_dir is None:
            return None, None
        require(git_dir is not None and common_dir is not None, "--git-dir and --git-common-dir go together")
        lexical(git_dir, "--git-dir")
        lexical(common_dir, "--git-common-dir")
        if self.test_root:
            require(git_dir.startswith(self.test_root + "/") and common_dir.startswith(self.test_root + "/"),
                    "--git-dir/--git-common-dir: outside the test root")
        else:
            require(TMP_CHECKOUT.fullmatch(checkout) is not None and common_dir == MAIN_CHECKOUT + "/.git"
                    and posixpath.dirname(git_dir) == MAIN_CHECKOUT + "/.git/worktrees",
                    "a linked worktree must be a /tmp/k4s-s2-<name> checkout of " + MAIN_CHECKOUT)
        return git_dir, common_dir


# The names each directory role may ever read (si.Role allowlists). Files: their exact leaf. Outputs: a write role
# rooted at the parent with the exact leaf. The frozen closure lies under these code patterns (K4S manifest sections).
REPOSITORY_EXACT = (PLAN, COMPLETION, INVENTORY, LEDGER, EVIDENCE_REL)
REPOSITORY_PATTERNS = (STUDY + "/run-r1/phase-meta/*/launch.json", STUDY + "/run-r1/phase-meta/*/supervisor-exit.json",
                       STUDY + "/end-sources/*/*/mhz.jsonl", STUDY + "/end-sources/*/*/census.jsonl")
CODE_PATTERNS = (STUDY + "/mac/*", STUDY + "/*.py", "reports/explore/e1/*", "reports/explore/s1/*", E4V3_REL + "/*")
DIR_NAMES = {"--repository": (REPOSITORY_EXACT, REPOSITORY_PATTERNS), "--code-root": ((K4S_MANIFEST,), CODE_PATTERNS),
             "--s1-dest": ((S1_MANIFEST_NAME,), ("*/*/mhz.jsonl", "*/*/census.jsonl"))}
ROLE_CAP = 1 << 30


def role_name(label):
    return label.lstrip("-")


class Gated:
    """gate_paths() result: the per-invocation si.Policy (one role per supplied path) and, per label, (path, handle):
    handle is the OPEN gated si.Input of a 'file' (the descriptor later read: gate-to-read identity by construction),
    None for a 'dir' or 'new' path."""

    def __init__(self, policy, entries):
        self.policy, self._entries = policy, entries

    def __getitem__(self, label):
        return self._entries[label]

    def __contains__(self, label):
        return label in self._entries

    def role(self, label):
        return role_name(label)


def gate_paths(specs, repository_exact=()):
    """specs: [(label, path, allowed(path) -> bool, leaf, name_rule or None)], path None = not supplied. EVERY path
    passes the lexical gate (the shared denylist + S2's local rules), its allowed root and its name rule with no system
    call, before ANY is touched. Then one si.Policy declares a role per path ('dir': rooted at it with DIR_NAMES;
    'file': rooted at its parent, exactly its leaf; 'new': a write role rooted at its parent, exactly its leaf) and si
    checks each: si.check_dir (canonical root, component-wise O_DIRECTORY|O_NOFOLLOW), si.open_input (descriptor gate:
    regular, st_nlink == 1, same dev/ino; nothing read yet) or si.check_absent (the leaf does not exist in any form)."""
    specs = [s for s in specs if s[1] is not None]
    for label, path, allowed, leaf, name_rule in specs:
        lexical(path, label)
        require(allowed(path), f"{label}: outside its allowed root, refused before any access: {path}")
        if name_rule is not None:
            name_rule(path.rsplit("/", 1)[1])
    roles = []
    for label, path, allowed, leaf, name_rule in specs:
        if leaf == "dir":
            exact, patterns = DIR_NAMES.get(label, ((), ()))
            exact = tuple(exact) + (tuple(repository_exact) if label == "--repository" else ())
            roles.append((label, path, "read", exact, patterns))
        else:
            parent, name = path.rsplit("/", 1)
            roles.append((label, parent, "write" if leaf == "new" else "read", (name,), ()))
    testing = os.environ.get(TEST_ENV) == TEST_MARKER
    policy = guarded("policy", si.Policy, this_host(testing),
                     [guarded(label, si.Role, role_name(label), root, access, ROLE_CAP, exact=exact, patterns=patterns)
                      for label, root, access, exact, patterns in roles])
    entries = {}
    try:
        for label, path, allowed, leaf, name_rule in specs:
            if leaf == "dir":
                guarded(label, si.check_dir, policy, role_name(label))
                entries[label] = (path, None)
            elif leaf == "new":
                guarded(label, si.check_absent, policy, role_name(label), path.rsplit("/", 1)[1])
                entries[label] = (path, None)
            else:
                entries[label] = (path, guarded(label, si.open_input, policy, role_name(label), path.rsplit("/", 1)[1]))
    except BaseException:
        for path, handle in entries.values():
            if handle is not None:
                handle.close()
        raise
    return Gated(policy, entries)


def expected_read(label, mismatch, function, *args, codes=("sha",)):
    """A safe_input read given an expected SHA-256 (and size): a refusal with one of `codes` becomes `mismatch` (the
    r3 message), any other refusal an S2Error naming the label."""
    try:
        return function(*args)
    except si.Refusal as error:
        if error.code in codes and mismatch is not None:
            raise S2Error(mismatch) from None
        raise si_refusal(label, error) from None


def read_gated(gated, label, expected_sha256, mismatch=None):
    """The bytes of an explicit input file that passed gate_paths, from the SAME gated descriptor (never re-opened),
    exactly its gated size, refused unless its SHA-256 is the expected one; a gated file must not be empty."""
    path, handle = gated
    require(isinstance(handle, si.Input), f"{label}: {path} did not pass gate_paths")
    require(SHA.fullmatch(expected_sha256 or "") is not None, f"{label}: an expected SHA-256 is required")
    data = expected_read(label, mismatch, handle.read_bytes, expected_sha256)
    require(len(data) > 0, f"{label}: {path} is empty")
    return data


def repo_relative(rel, label):
    """A normalised repo-relative path: no absolute, no '..'/'.'/empty part, not a forbidden location."""
    require(isinstance(rel, str) and rel and not rel.startswith("/"), f"{label}: not a repo-relative path: {rel!r}")
    parts = rel.split("/")
    require(all(SAFE_PART.fullmatch(p) and p not in (".", "..") for p in parts), f"{label}: unsafe path {rel!r}")
    reason = forbidden_reason(rel)
    require(reason is None, f"{label}: forbidden location ({reason}): {rel!r}")
    require(not (rel + "/").startswith(END_DIR + "/"), f"{label}: path inside the strict END namespace {rel!r}")
    return rel


def write_gated(gated, label, data):
    """Exclusive creation (si.Writer: O_CREAT|O_EXCL|O_NOFOLLOW via the canonical parent; never overwrites) of a
    'new' path that passed gate_paths."""
    path = gated[label][0]
    with guarded(label, si.Writer, gated.policy, gated.role(label)) as writer:
        guarded(label, writer.create_excl, path.rsplit("/", 1)[1], data, 0o644)
    return path


def strict_json(raw, label):
    """si.loads_strict: strict UTF-8 JSON refusing duplicate keys and the non-standard NaN/Infinity constants."""
    return guarded(label, si.loads_strict, raw, label)


# ---------------------------------------------------------------- mode, pins and roles

class Mode:
    def __init__(self, a):
        env = os.environ.get(TEST_ENV)
        self.testing = bool(getattr(a, "test_mode", False))
        require(env in (None, TEST_MARKER), f"{TEST_ENV} is set but is not the synthetic test marker")
        require(self.testing == (env == TEST_MARKER),
                f"test mode requires BOTH --test-mode and {TEST_ENV}={TEST_MARKER}; production requires neither")
        for name in TEST_ONLY_OPTIONS + ("no_manifest_check",):
            if getattr(a, name, None) not in (None, False):
                require(self.testing, f"--{name.replace('_', '-')} is a TEST-ONLY option (requires test mode)")
        pick = lambda name, default: default if getattr(a, name, None) is None else getattr(a, name)
        self.pins = {k: pick("expect_" + k, DEFAULTS[k]) for k in DEFAULTS}
        self.hosts = sorted(pick("expect_hosts", list(DEFAULT_HOSTS)))
        self.blocks = pick("expect_blocks", DEFAULT_BLOCKS)
        self.losses = pick("expect_losses", DEFAULT_LOSSES)
        self.location = pick("evidence_repository_path", EVIDENCE_REL)
        self.warmup = pick("warmup_seconds", 300.0)
        self.verify_code = not getattr(a, "no_manifest_check", False)
        require(all(SHA.fullmatch(str(v)) for v in self.pins.values()), "record pins must be 64-hex SHA-256")
        require(all(HOST_NAME.fullmatch(h) for h in self.hosts) and len(set(self.hosts)) == len(self.hosts),
                "unsafe/duplicate expected hosts")
        self.roots = Roots(self.testing)


def s1_manifest_name(name):
    require(name == S1_MANIFEST_NAME, f"--s1-manifest must be S1's {S1_MANIFEST_NAME}, not {name!r}")


def json_name(name):
    require(name.endswith(".json"), f"--profile-json must be a .json file, not {name!r}")


def output_name(name):
    require(name.endswith(".json") and AUTHORITY_LIKE.fullmatch(name) is None,
            f"output must be a .json file not named like an END authority/claim: {name!r}")


def evidence_location(rel):
    require(isinstance(rel, str) and not (rel + "/").startswith(END_DIR + "/"),
            "evidence must lie OUTSIDE the strict END namespace " + END_DIR)
    repo_relative(rel, "evidence repository path")
    p = PurePosixPath(rel)
    require(rel.endswith(".json") and rel.startswith(STUDY + "/"), "evidence must be a .json file inside " + STUDY)
    require(AUTHORITY_LIKE.fullmatch(p.name) is None, "evidence name looks like an END authority/claim: " + p.name)
    return p


def counted_phases(completion, mode):
    counted = completion.get("counted_host_phases")
    require(isinstance(counted, dict) and counted, "completion lacks counted_host_phases")
    require(sorted(counted) == mode.hosts, f"counted hosts {sorted(counted)} != {mode.hosts}")
    for host, phases in counted.items():
        require(HOST_NAME.fullmatch(host) and isinstance(phases, list) and phases and len(set(phases)) == len(phases)
                and all(isinstance(p, str) and PHASE_NAME.fullmatch(p) for p in phases),
                f"unsafe/unregistered counted phases for {host}")
    if not mode.testing:
        require(counted == PRODUCTION_PHASES, "completion counted_host_phases differ from the 10 pairs of record")
    return [(host, phase) for host in sorted(counted) for phase in counted[host]]


def role_paths(pairs):
    """{role key: repository_path}: the ONLY paths S2 ever reads as artifacts."""
    roles = {key: rel for key, rel in RECORDS}
    for host, phase in pairs:
        for field, pattern, name in PHASE_FILES:
            roles[(host, phase, field)] = repo_relative(pattern.format(host=host, phase=phase, name=name), "role")
    return roles


def pinned_completion(checkout, commit, mode):
    """commit:COMPLETION through si.git_show_file, refused unless it is the pinned completion (before parsing)."""
    data = checkout.show(commit, COMPLETION, mode.pins["completion"], "completion", "completion SHA != pinned completion")
    return strict_json(data, "completion"), data


S1_FILE_FIELDS = ("host", "phase", "name", "local_path", "local_sha256", "remote_sha256_before", "remote_sha256_after",
                  "local_size", "remote_size")
S1_META_FIELDS = ("host", "phase", "name", "remote_sha256", "committed_sha256", "committed_repository_path")


def load_s1(gated, digest, mode, pairs=None):
    """The verified S1 receipt (already through gate_paths): pinned SHA, production schema (TEST schema only in test
    mode), typed rows, exact 20+20 rows for `pairs` (None: the receipt's own pairs, diagnose-clock)."""
    require(gated is not None and SHA.fullmatch(digest or ""), "--s1-manifest and --s1-manifest-sha256 are required")
    lexical(gated[0], "--s1-manifest")                        # pure, even on a direct call
    raw = read_gated(gated, "S1 manifest", digest, "S1 manifest SHA != --s1-manifest-sha256")
    doc = strict_json(raw, "S1 manifest")
    require(isinstance(doc, dict), "S1 manifest is not a JSON object")
    schemas = (S1_SCHEMA, S1_TEST_SCHEMA) if mode.testing else (S1_SCHEMA,)
    require(doc.get("schema") in schemas and doc.get("status") == "copied"
            and doc.get("test_mode", False) is (doc.get("schema") == S1_TEST_SCHEMA),
            f"S1 manifest schema/status not acceptable here: {doc.get('schema')}/{doc.get('status')}")
    for section, fields in (("files", S1_FILE_FIELDS), ("meta", S1_META_FIELDS)):
        rows = doc.get(section)
        require(isinstance(rows, list) and rows and all(isinstance(r, dict) and set(fields) <= set(r) for r in rows),
                f"S1 manifest {section} rows are malformed")
        for r in rows:
            require(all(type(r[k]) is int if k.endswith("_size") else type(r[k]) is str for k in fields)
                    and HOST_NAME.fullmatch(r["host"]) and PHASE_NAME.fullmatch(r["phase"]),
                    f"S1 manifest {section} row has a wrong type or an unsafe host/phase")
    files = {(f["host"], f["phase"], f["name"]): f for f in doc["files"]}
    meta = {(m["host"], m["phase"], m["name"]): m for m in doc["meta"]}
    if pairs is None:
        pairs = sorted({(h, p) for h, p, _ in files})
    want_files = {(h, p, n) for h, p in pairs for n in ("mhz.jsonl", "census.jsonl")}
    want_meta = {(h, p, n) for h, p in pairs for n in ("launch.json", "supervisor-exit.json")}
    require(set(files) == want_files and len(doc["files"]) == len(want_files), "S1 manifest files differ from the phases")
    require(set(meta) == want_meta and len(doc["meta"]) == len(want_meta), "S1 manifest meta differ from the phases")
    for f in files.values():
        require(f["local_sha256"] == f["remote_sha256_before"] == f["remote_sha256_after"]
                and f["local_size"] == f["remote_size"] > 0, "S1 manifest row is not a verified copy: " + f["local_path"])
    for m in meta.values():
        require(m["remote_sha256"] == m["committed_sha256"], "S1 manifest meta row differs from committed bytes")
    return dict(files=files, meta=meta, sha256=digest, schema=doc["schema"], path=gated[0], pairs=pairs)


def s1_check(item, host, phase, field, rel, s1, size=None):
    """Launch/exit: S1 on-host == committed == item, same committed path. mhz/census: S1 local == item."""
    name = dict((f, n) for f, _, n in PHASE_FILES)[field]
    if field in ("launch", "supervisor_exit"):
        row = s1["meta"][(host, phase, name)]
        require(row["remote_sha256"] == row["committed_sha256"] == item["sha256"]
                and row["committed_repository_path"] == rel,
                f"phase-meta differs from the on-host file recorded by S1: {rel}")
    else:
        row = s1["files"][(host, phase, name)]
        require(row["local_sha256"] == item["sha256"] and (size is None or row["local_size"] == size),
                f"evidence source differs from the S1 copy manifest: {rel}")


# ---------------------------------------------------------------- build

def build(a, mode):
    location = evidence_location(mode.location)
    edir = location.parent
    require(a.s1_manifest is not None or mode.testing, "--s1-manifest and --s1-manifest-sha256 are required")
    roots = mode.roots
    # production: --out is exactly the evidence path inside --repository (a new file); test: below the test root
    out_allowed = roots.prep if mode.testing else (lambda path: path == f"{a.repository}/{location.as_posix()}")
    git_dirs = roots.worktree_git_dirs(a.repository, a.git_dir, a.git_common_dir)       # pure
    gated = gate_paths([("--repository", a.repository, roots.checkout, "dir", None),
                        ("--s1-manifest", a.s1_manifest, roots.prep, "file", s1_manifest_name),
                        ("--out", a.out, out_allowed, "new", output_name)], repository_exact=(location.as_posix(),))
    checkout = Checkout(gated.policy, gated.role("--repository"), gated["--repository"][0], *git_dirs)
    commit = full_commit(checkout, a.commit)
    completion, _ = pinned_completion(checkout, commit, mode)
    pairs = counted_phases(completion, mode)
    roles = role_paths(pairs)
    s1 = load_s1(gated["--s1-manifest"], a.s1_manifest_sha256, mode, pairs) if "--s1-manifest" in gated else None

    def item(rel, expected, label, mismatch=None):
        """commit:rel through si.git_show_file with its expected SHA-256 (production: always one; test mode without
        an S1 receipt: the commit-bound blob only)."""
        require(expected is not None or mode.testing, f"{label}: production reads need an expected SHA-256: {rel}")
        data = checkout.show(commit, rel, expected, label, mismatch or f"{label} SHA != pinned {expected}: {rel}")
        require(len(data) > 0, "empty artifact: " + rel)
        return dict(path=PurePosixPath(rel).relative_to(edir).as_posix(), sha256=sha_bytes(data), commit=commit,
                    repository_path=rel), data

    def phase_pin(host, phase, field, rel):
        """(expected SHA, refusal message) of one phase artifact: the completion's binding (exit), the table of record
        (launch, production), the verified S1 receipt (launch on-host == committed; mhz/census local copy)."""
        if field == "supervisor_exit":
            bound = completion.get("supervisor_exits", {}).get(f"{host}/{phase}", {}).get("sha256")
            require(isinstance(bound, str) and SHA.fullmatch(bound) is not None,
                    f"supervisor exit SHA not bound by the completion: {rel}")
            return bound, f"supervisor exit SHA not bound by the completion: {rel}"
        if field == "launch" and not mode.testing:
            return EXPECTED_META[(host, phase)][0], f"phase-meta SHA differs from the table of record: {rel}"
        if s1 is None:
            return None, None
        name = dict((f, n) for f, _, n in PHASE_FILES)[field]
        if field == "launch":
            return (s1["meta"][(host, phase, name)]["committed_sha256"],
                    f"phase-meta differs from the on-host file recorded by S1: {rel}")
        return s1["files"][(host, phase, name)]["local_sha256"], f"evidence source differs from the S1 copy manifest: {rel}"

    doc = dict(schema=EVIDENCE_SCHEMA, kind="counted-reporting")
    for key, rel in RECORDS:
        doc[key], data = item(rel, mode.pins[key], key)
        if key == "plan":
            require(strict_json(data, "plan").get("study") == "PREREG-K4S", "plan is not the PREREG-K4S plan")
    require(completion.get("counted_inventory_sha256") == doc["counted_inventory"]["sha256"]
            and completion.get("blind_ledger_sha256") == doc["blind_ledger"]["sha256"],
            "completion does not bind the pinned inventory/ledger")
    phases = []
    for host, phase in pairs:
        entry = dict(host=host, phase=phase)
        for field, _, _ in PHASE_FILES:
            rel = roles[(host, phase, field)]
            pin, mismatch = phase_pin(host, phase, field, rel)
            entry[field], data = item(rel, pin, f"{host}/{phase} {field}", mismatch)
            if field == "supervisor_exit":
                bound = completion.get("supervisor_exits", {}).get(f"{host}/{phase}", {}).get("sha256")
                require(bound == entry[field]["sha256"], f"supervisor exit SHA not bound by the completion: {rel}")
            if field in ("launch", "supervisor_exit") and not mode.testing:
                want = EXPECTED_META[(host, phase)][0 if field == "launch" else 1]
                require(entry[field]["sha256"] == want, f"phase-meta SHA differs from the table of record: {rel}")
            if s1 is not None:
                s1_check(entry[field], host, phase, field, rel, s1, len(data))
        phases.append(entry)
    doc["phases"] = phases
    data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    written = write_gated(gated, "--out", data)
    summary = dict(status="built", test_mode=mode.testing, evidence=written,
                   evidence_repository_path=location.as_posix(), sha256=sha_bytes(data), commit=commit,
                   phases=len(phases), s1_manifest_sha256=s1["sha256"] if s1 else None, utc=utc())
    print(json.dumps(summary, indent=1))
    return summary


# ---------------------------------------------------------------- stdlib-only verification of the frozen closure

def stdlib_dirs():
    dirs = {os.path.realpath(sysconfig.get_paths()[k]) for k in ("stdlib", "platstdlib")}
    return tuple(sorted(dirs))


class VerifiedLoader(importlib.abc.Loader):
    """Executes a frozen module from the exact bytes whose SHA-256 was verified (no re-open, no .pyc)."""

    def __init__(self, origin, data):
        self.origin, self.data = origin, data

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.data, self.origin, "exec", dont_inherit=True), module.__dict__)


class ClosureFinder(importlib.abc.MetaPathFinder):
    """First on sys.meta_path: serves the verified frozen modules; any other import must resolve inside the
    interpreter's stdlib (no site-packages, no repository/code-root file), else ImportError."""

    def __init__(self, served):
        self.served, self.stdlib = served, stdlib_dirs()
        self.preloaded = frozenset(sys.modules)           # interpreter start-up (site, S2's own stdlib imports)

    def find_spec(self, name, path=None, target=None):
        if name in self.served:
            origin, data, _ = self.served[name]
            spec = importlib.machinery.ModuleSpec(name, VerifiedLoader(origin, data), origin=origin)
            spec.has_location = True
            return spec
        spec = None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                break
        if spec is None or spec.origin in ("built-in", "frozen"):
            return spec
        real = os.path.realpath(spec.origin or "")
        parts = real.split("/")
        if (spec.origin and any(real.startswith(d + "/") for d in self.stdlib)
                and "site-packages" not in parts and "dist-packages" not in parts):
            return spec
        raise ImportError(f"S2 closure: {name} from {spec.origin} is outside the verified frozen closure")


def verify_pin_set(files, label, read):
    require(isinstance(files, dict) and files, "Empty pin set: " + label)
    for name, expected in sorted(files.items()):
        repo_relative(name, label)
        require(isinstance(expected, str) and SHA.fullmatch(expected), f"Unfilled pin ({label}): {name}")
        read(name, expected, f"Pin mismatch ({label}): {name}")


def bootstrap(gated, mode):
    """Stdlib only, BEFORE any frozen import: the manifest bytes == the approved SHA; every pinned file verified
    (k4s_logic.load_k4s_manifest semantics, require_frozen); the served modules keep their verified bytes. Every
    read is si.read_bytes on the 'code-root' role with the file's expected SHA-256 (the approved manifest SHA, then
    the manifest's pins), checked by safe_input before the bytes are returned."""
    root = gated["--code-root"][0]                             # already through gate_paths
    policy, role = gated.policy, gated.role("--code-root")
    for name in list(SERVED) + ["end_pool", "fleet_validity"]:
        require(name not in sys.modules, "frozen module already imported: " + name)
    cache = {}

    def read(rel, expected, mismatch):
        repo_relative(rel, "frozen code")
        if rel not in cache:
            cache[rel] = expected_read(f"frozen code {rel}", mismatch, si.read_bytes, policy, role, rel, None, expected)
        require(expected is None or sha_bytes(cache[rel]) == expected, mismatch)
        return cache[rel]
    if not mode.verify_code:                                   # TEST-ONLY: unverified bytes, recorded as such
        return {name: (root + "/" + rel, read(rel, None, None), None) for name, (_, rel) in SERVED.items()}, None
    raw = read(K4S_MANIFEST, APPROVED_K4S_MANIFEST_SHA256, "K4S manifest SHA != approved 74314eda")
    manifest = strict_json(raw, "K4S manifest")
    require(manifest.get("schema") == "clasher.k4s.mac-manifest.v1", "Unsupported K4S manifest schema")
    for section, label in (("k4s_files", "K4S Mac files"), ("end_files", "K4S END producer/pooler files"),
                           ("reused_readonly", "reused read-only TIERS files")):
        verify_pin_set(manifest[section], label, read)
    tiers = manifest["measure_tiers_unmodified"]
    require(manifest["reused_readonly"].get(tiers["path"]) == tiers["sha256"],
            "measure_tiers.py statement disagrees with its read-only pin")
    require(manifest["native"]["provenance_linux_sha256"] == NATIVE_PROVENANCE_SHA, "Native provenance SHA changed")
    require(manifest.get("frozen") is True, "K4S manifest is not frozen")
    require(SHA.fullmatch(str(manifest["sd1_manifest"].get("sha256"))), "SD1 manifest SHA is not filled")
    kernel = manifest["k4s_kernel"]
    require(kernel.get("files") and all(SHA.fullmatch(str(v)) for v in kernel["files"].values()),
            "K4S kernel pins are not filled")
    verify_pin_set(kernel["files"], "K4S kernel", read)
    served = {}
    for name, (section, rel) in SERVED.items():
        pin = manifest[section].get(rel)
        require(isinstance(pin, str) and SHA.fullmatch(pin) is not None, f"served module {name} is not pinned: {rel}")
        served[name] = (root + "/" + rel, read(rel, pin, f"served module {name} is not pinned: {rel}"), pin)
    verified = dict(manifest_sha256=APPROVED_K4S_MANIFEST_SHA256,
                    files_verified=len(cache), served={n: v[2] for n, v in served.items()})
    return served, verified


def frozen_modules(gated, mode):
    code_root = gated["--code-root"][0]
    served, verified = bootstrap(gated, mode)
    finder = ClosureFinder(served)
    sys.meta_path.insert(0, finder)
    modules = {name: importlib.import_module(name) for name in ("k4s_logic", "end_evidence", "fleet_end",
                                                                 "fleet_profile", "receipts")}
    for name, module in modules.items():                      # retained import-origin checks
        require(isinstance(module.__spec__.loader, VerifiedLoader) and module.__file__ == served[name][0],
                "wrong frozen module imported: " + name)
    if verified is not None:                                  # redundant second opinion by the verified frozen code
        modules["k4s_logic"].load_k4s_manifest(Path(code_root) / K4S_MANIFEST, APPROVED_K4S_MANIFEST_SHA256,
                                               Path(code_root), require_frozen=True)
    return modules, served, verified, finder


def closure_audit(served, finder):
    """After validation: every loaded non-stdlib module is one of the verified served modules."""
    for name, module in list(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin or name in finder.preloaded:
            continue
        real = os.path.realpath(origin)
        if any(real.startswith(d + "/") for d in finder.stdlib) and "site-packages" not in real.split("/"):
            continue
        require(name in served and isinstance(module.__spec__.loader, VerifiedLoader),
                f"unverified module loaded during validation: {name} ({origin})")


# ---------------------------------------------------------------- validate

def structure(doc, commit, edir, roles, pairs):
    """Exact layout: key sets, phase order == the pinned completion, every item exactly its role's path."""
    require(isinstance(doc, dict) and set(doc) == TOP_FIELDS, "evidence top-level keys differ from the S2 layout")
    require(doc["schema"] == EVIDENCE_SCHEMA and doc["kind"] == "counted-reporting", "wrong evidence schema/kind")
    require(isinstance(doc["phases"], list) and doc["phases"], "evidence lacks phases")
    for entry in doc["phases"]:
        require(isinstance(entry, dict) and set(entry) == PHASE_FIELDS, "phase entry keys differ from the S2 layout")
    got = [(e["host"], e["phase"]) for e in doc["phases"]]
    require(got == pairs, f"evidence host/phases {got} != the pinned completion's counted host phases {pairs}")
    items = [(key, doc[key], roles[key]) for key, _ in RECORDS]
    for entry in doc["phases"]:
        items += [((entry["host"], entry["phase"], f), entry[f], roles[(entry["host"], entry["phase"], f)])
                  for f, _, _ in PHASE_FILES]
    for key, item, rel in items:
        require(isinstance(item, dict) and set(item) == ITEM_FIELDS, f"artifact item keys differ: {key}")
        require(item["repository_path"] == rel, f"artifact {key} repository_path {item['repository_path']!r} != {rel!r}")
        require(isinstance(item["path"], str) and (edir / item["path"]).as_posix() == rel
                and repo_relative(item["path"], "artifact path") == PurePosixPath(rel).relative_to(edir).as_posix(),
                f"artifact {key} path is not its repository path relative to the evidence: {item['path']!r}")
        require(isinstance(item["sha256"], str) and SHA.fullmatch(item["sha256"]) and item["commit"] == commit,
                f"artifact {key} SHA malformed or commit differs from --commit")
    return items


def mhz_preconditions(rows, cpus, host, slots):
    """Reporting half of frozen fleet_profile.compare_mhz, per core (stricter: each core finite > 0)."""
    for row in rows:
        require(row["slots"] == slots and row.get("inflight") == slots, "non full-occupancy reporting row selected")
        clocks = {v["cpu"]: v["mhz"] for v in row["physical_core_mhz"]}
        require(set(cpus) <= set(clocks), f"reporting MHz row lacks an occupied physical core: {host} {row['utc']}")
        require(all(type(clocks[c]) in (int, float) and math.isfinite(clocks[c]) and clocks[c] > 0 for c in cpus),
                f"non-finite/non-positive reporting MHz: {host} {row['utc']}")


def check_profile(profile, host, label):
    """One reference_load_profile, field by field (fleet_profile.slot_layout:9-29, fleet_end.host_reporting:189-202,
    the S4 declared profile). Never completed from defaults."""
    require(type(profile) is dict and profile, f"{label}: the profile of {host} must be a non-empty JSON object")
    missing = [k for k in PROFILE_REQUIRED if k not in profile]
    extra = sorted(set(profile) - set(PROFILE_REQUIRED) - set(PROFILE_EXTRAS))
    require(not missing, f"{label}: the profile of {host} lacks {missing}")
    require(not extra, f"{label}: the profile of {host} has unknown fields {extra}")
    require(type(profile["host"]) is str and profile["host"] == host, f"{label}: profile host differs from {host}")
    require(type(profile["reference_slot"]) is int and profile["reference_slot"] == 0,
            f"{label}: {host} reference_slot must be the integer 0 (Amendment 1)")
    require(type(profile["slot_count"]) is int and profile["slot_count"] == REPORTING_SLOTS,
            f"{label}: {host} slot_count must be the integer {REPORTING_SLOTS}")
    require(profile["console_rule"] is False, f"{label}: {host} console_rule must be the Boolean false")
    warmup = profile["warmup_seconds"]
    require(type(warmup) in (int, float) and math.isfinite(warmup) and warmup >= MIN_WARMUP_SECONDS,
            f"{label}: {host} warmup_seconds must be a finite number >= {MIN_WARMUP_SECONDS}")
    require(profile["perception"] == "none", f"{label}: {host} perception must be \"none\"")
    for key, kind in PROFILE_EXTRAS.items():
        if key in profile:
            require(type(profile[key]) is kind and profile[key], f"{label}: {host} {key} must be a non-empty {kind.__name__}")
    return profile


def load_profiles(a, mode, gated):
    """Exactly one source, in every mode: the S4 profiles (gated file + SHA) or the acknowledged declared default."""
    supplied, default = a.profile_json is not None, bool(a.declared_default_profile)
    require(supplied != default, "validation needs exactly one of --profile-json/--profile-json-sha256 (S4) "
                                 "or --declared-default-profile")
    require(supplied == (a.profile_json_sha256 is not None), "--profile-json and --profile-json-sha256 go together")
    if default:
        profiles = {host: check_profile(dict(host=host, reference_slot=0, slot_count=REPORTING_SLOTS,
                                             console_rule=False, warmup_seconds=mode.warmup, perception="none"),
                                        host, "declared default profile") for host in mode.hosts}
        return profiles, dict(profile_source="declared-default", profile_json_path=None, profile_json_sha256=None)
    require(SHA.fullmatch(a.profile_json_sha256), "--profile-json-sha256 must be 64-hex SHA-256")
    raw = read_gated(gated["--profile-json"], "profile JSON", a.profile_json_sha256, "profile JSON SHA mismatch")
    profiles = strict_json(raw, "profile JSON")
    require(type(profiles) is dict and sorted(profiles) == mode.hosts,
            f"profile JSON must be an object holding exactly the counted hosts {mode.hosts}")
    for host in mode.hosts:
        check_profile(profiles[host], host, "profile JSON")
    return profiles, dict(profile_source="s4-bundles", profile_json_path=gated["--profile-json"][0],
                          profile_json_sha256=a.profile_json_sha256)


def validate(a, mode, context):
    started = utc()
    context["test_mode"] = mode.testing
    require(a.s1_manifest is not None or mode.testing, "--s1-manifest and --s1-manifest-sha256 are required")
    roots = mode.roots
    location = evidence_location(mode.location)              # pure
    edir = location.parent
    git_dirs = roots.worktree_git_dirs(a.repository, a.git_dir, a.git_common_dir)       # pure
    gated = gate_paths([("--repository", a.repository, roots.checkout, "dir", None),
                        ("--code-root", a.code_root or a.repository, roots.checkout, "dir", None),
                        ("--s1-manifest", a.s1_manifest, roots.prep, "file", s1_manifest_name),
                        ("--profile-json", a.profile_json, roots.prep, "file", json_name)],
                       repository_exact=(location.as_posix(),))
    repository, code_root = gated["--repository"][0], gated["--code-root"][0]
    checkout = Checkout(gated.policy, gated.role("--repository"), repository, *git_dirs)
    profiles, profile_record = load_profiles(a, mode, gated)
    commit = full_commit(checkout, a.commit)
    checkout.run(["merge-base", "--is-ancestor", commit, "HEAD"], "merge-base --is-ancestor")
    # 1. stdlib-only bootstrap of the frozen code (nothing frozen is imported yet)
    served, verified = None, None
    modules, served, verified, finder = frozen_modules(gated, mode)
    E, fleet_end, fleet_profile = modules["end_evidence"], modules["fleet_end"], modules["fleet_profile"]
    # 2. evidence, exact roles, pins, S1 receipt: before any artifact read
    require(SHA.fullmatch(a.evidence_sha256 or "") is not None, "evidence SHA mismatch")
    raw = expected_read("evidence", "evidence SHA mismatch", si.read_bytes, gated.policy, gated.role("--repository"),
                        location.as_posix(), None, a.evidence_sha256)
    doc = strict_json(raw, "evidence")
    require(isinstance(doc, dict) and set(doc) == TOP_FIELDS, "evidence top-level keys differ from the S2 layout")
    require(isinstance(doc["completion"], dict) and doc["completion"].get("repository_path") == COMPLETION
            and doc["completion"].get("sha256") == mode.pins["completion"] and doc["completion"].get("commit") == commit,
            "evidence completion item differs from the completion of record")
    completion, _ = pinned_completion(checkout, commit, mode)
    pairs = counted_phases(completion, mode)
    roles = role_paths(pairs)
    items = structure(doc, commit, edir, roles, pairs)
    for key, _ in RECORDS:
        require(doc[key]["sha256"] == mode.pins[key], f"evidence {key} SHA != the pinned record")
    require(completion.get("counted_inventory_sha256") == doc["counted_inventory"]["sha256"]
            and completion.get("blind_ledger_sha256") == doc["blind_ledger"]["sha256"],
            "completion does not bind the evidence inventory/ledger")
    s1 = load_s1(gated["--s1-manifest"], a.s1_manifest_sha256, mode, pairs) if "--s1-manifest" in gated else None
    for entry in doc["phases"]:
        host, phase = entry["host"], entry["phase"]
        bound = completion.get("supervisor_exits", {}).get(f"{host}/{phase}", {}).get("sha256")
        require(bound == entry["supervisor_exit"]["sha256"], f"supervisor exit not bound by the completion: {host}/{phase}")
        if not mode.testing:
            require((entry["launch"]["sha256"], entry["supervisor_exit"]["sha256"]) == EXPECTED_META[(host, phase)],
                    f"phase-meta SHA differs from the table of record: {host}/{phase}")
        if s1 is not None:
            for field, _, _ in PHASE_FILES:
                s1_check(entry[field], host, phase, field, roles[(host, phase, field)], s1)
    # 3. before the frozen reader: every artifact's committed blob (si.git_show_file: replacement objects off, type
    #    and OID verified) and its work-tree file (si descriptor gate: no symlink/alias anywhere, st_nlink == 1) must
    #    have the item's SHA-256; the frozen reader's own git reads then run only inside frozen_git_env()
    for key, item, rel in items:
        label = f"artifact {key}"
        checkout.show(commit, rel, item["sha256"], label, f"{label}: committed blob pin mismatch: {rel}")
        found = guarded(label, si.sha256_input, gated.policy, gated.role("--repository"), rel)
        require(found["sha256"] == item["sha256"], f"{label}: work-tree pin mismatch: {rel}")
        require(found["size"] > 0, f"empty artifact {rel}")
    # 4. the frozen reader and checks (P2-4 environment, pre-verified checkout)
    with frozen_git_env(checkout):
        ev, hosts, membership = frozen_checks(E, fleet_end, fleet_profile, a, mode, context, repository, location,
                                              profiles, pairs)
    closure_audit(served, finder)
    return dict(schema=TEST_RESULT_SCHEMA if mode.testing else RESULT_SCHEMA, test_mode=mode.testing, ok=True,
                started_utc=started, finished_utc=utc(), evidence=str(Path(repository) / location),
                evidence_sha256=a.evidence_sha256, commit=commit,
                repository_head=checkout.run(["rev-parse", "HEAD"], "rev-parse HEAD").decode().strip(),
                code_root=code_root, frozen_manifest_verified=verified is not None, frozen_bootstrap=verified,
                frozen_module_sha256={n: sha_bytes(v[1]) for n, v in served.items()},
                python=sys.version.split()[0], executable=sys.executable, optimize=sys.flags.optimize,
                kind=ev["kind"], counted_hosts=ev["counted_hosts"], membership=membership,
                plan_sha256=ev["plan_sha256"], completion_sha256=ev["completion_sha256"], hosts=hosts,
                **profile_record, safe_input_sha256=SAFE_INPUT_SHA256, frozen_git_env="P2-4 (si.GIT_FIXED_ENV)",
                slot_layout_offline_note="host/nice supplied offline (plan nice); live gate runs on host pre-claim",
                s1_manifest_path=s1["path"] if s1 else None, s1_manifest_sha256=s1["sha256"] if s1 else None)


def frozen_checks(E, fleet_end, fleet_profile, a, mode, context, repository, location, profiles, pairs):
    """The frozen end_evidence reader, record bindings, membership and per counted host the frozen slot_layout and
    host_reporting (called only inside frozen_git_env)."""
    ev = E.end_evidence(Path(repository) / location, a.evidence_sha256, Path(repository), fleet_end)
    require(ev["completion_sha256"] == mode.pins["completion"] and ev["plan_sha256"] == mode.pins["plan"],
            "evidence binds a completion/plan other than the record")
    require(ev["counted_hosts"] == mode.hosts, f"counted hosts {ev['counted_hosts']} != {mode.hosts}")
    membership = ev["membership"]
    require(membership["blocks"] == mode.blocks and membership["losses"] == mode.losses,
            f"membership {membership['blocks']}/{membership['losses']} != expected {mode.blocks}/{mode.losses}")
    require(set(ev["phases"]) == set(pairs), "evidence phases differ from the completion's counted host phases")
    for key, values in ev["phases"].items():
        bound = ev["completion"]["supervisor_exits"].get(f"{key[0]}/{key[1]}", {}).get("sha256")
        require(bound == values["exit_sha256"], f"supervisor exit not bound by the completion: {key}")
    plan = ev["plan"]
    hosts = {}
    for host in ev["counted_hosts"]:
        profile = profiles[host]                              # validated; never completed from defaults
        search, background, census_cpu = fleet_profile.slot_layout(profile, plan, host, plan["compute"]["nice"])
        try:
            rows = fleet_end.host_reporting(ev, profile, plan)
        except (ValueError, KeyError, TypeError) as error:
            context["clock_diagnosis"] = {f"{h}/{p}": diagnose_phase(v["census"], v["mhz"], h, v["launch"]["slots"])
                                          for (h, p), v in ev["phases"].items() if h == host}
            raise S2Error(f"frozen host_reporting refused {host}: {type(error).__name__}: {error} "
                          "(outcome-blind clock_diagnosis attached; nothing repaired)") from None
        mhz_preconditions(rows, search + sum(background, []), host, profile["slot_count"])
        per_phase = {}
        for row in rows:
            per_phase[row["phase"]] = per_phase.get(row["phase"], 0) + 1
        hosts[host] = dict(profile=profile, reference_cpus=search, background_slots=len(background),
                           census_cpu=census_cpu, full_occupancy_rows=len(rows), full_occupancy_rows_by_phase=per_phase,
                           census_rows_by_phase={p: len(v["census"]) for (h, p), v in ev["phases"].items() if h == host})
    return ev, hosts, membership


# ---------------------------------------------------------------- outcome-blind clock diagnosis

def parse_rows(data, keep):
    """frozen parsing (data.splitlines(), blank lines skipped) projected to health-only fields, with line numbers."""
    rows, errors = [], []
    for number, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            require(isinstance(row, dict), "row is not an object")
        except (ValueError, S2Error):
            errors.append(number)
            continue
        rows.append((number, keep(row)))
    return rows, errors


def key_text(value):
    return value if isinstance(value, str) else repr(value)


def census_fields(row):
    return dict(utc=key_text(row.get("utc")), host=row.get("host"), inflight=row.get("inflight"))


def mhz_fields(row):
    cores = row.get("physical_core_mhz")
    values = [v.get("mhz") for v in cores if isinstance(v, dict)] if isinstance(cores, list) else []
    return dict(utc=key_text(row.get("utc")), slots=row.get("slots"), cores=len(values),
                mhz_all_finite_positive=bool(values) and all(type(v) in (int, float) and math.isfinite(v) and v > 0
                                                             for v in values))


def diagnose_phase(census, mhz, host, slots):
    """Accepts the frozen reader's parsed rows (dicts) or (line, dict) pairs; reports, never repairs."""
    census = [(i + 1, census_fields(r)) if isinstance(r, dict) else (r[0], census_fields(r[1]))
              for i, r in enumerate(census)]
    mhz = [(i + 1, mhz_fields(r)) if isinstance(r, dict) else (r[0], mhz_fields(r[1])) for i, r in enumerate(mhz)]
    return diagnosis(census, mhz, host, slots, [], [])


def diagnosis(census, mhz, host, slots, census_errors, mhz_errors):
    first_rule = None
    by_utc, dup_census, wrong_host = {}, {}, []
    for line, row in census:
        if row["utc"] in by_utc:
            dup_census.setdefault(row["utc"], [by_utc[row["utc"]][0]]).append(line)
            first_rule = first_rule or f"Duplicate/wrong host census row (census line {line})"
        else:
            by_utc[row["utc"]] = (line, row)
        if row["host"] != host:
            wrong_host.append(dict(line=line, utc=row["utc"], host=row["host"]))
            first_rule = first_rule or f"Duplicate/wrong host census row (census line {line})"
    seen, dup_mhz, mhz_unmatched, slot_mismatch, nonfinite, joined, full = {}, {}, [], [], [], 0, 0
    for line, row in mhz:
        key = row["utc"]
        if key in seen:
            dup_mhz.setdefault(key, [seen[key]]).append(line)
            first_rule = first_rule or f"Missing/duplicate full-occupancy clock join (duplicate mhz line {line})"
            continue
        seen[key] = line
        if key not in by_utc:
            mhz_unmatched.append(dict(utc=key, line=line))
            first_rule = first_rule or f"Missing/duplicate full-occupancy clock join (mhz line {line} has no census row)"
            continue
        if row["slots"] != slots:
            slot_mismatch.append(dict(utc=key, line=line, slots=row["slots"]))
            first_rule = first_rule or f"Missing/duplicate full-occupancy clock join (mhz line {line} slots)"
        joined += 1
        if by_utc[key][1]["inflight"] == slots:
            full += 1
            if not row["mhz_all_finite_positive"]:
                nonfinite.append(dict(utc=key, line=line))
    order = [line for line, _ in census]
    census_unmatched = []
    for key, (line, _) in sorted(by_utc.items(), key=lambda kv: kv[1][0]):
        if key in seen:
            continue
        index = order.index(line)
        before = [census[j][1]["utc"] for j in range(index - 1, -1, -1) if census[j][1]["utc"] in seen][:1]
        after = [census[j][1]["utc"] for j in range(index + 1, len(census)) if census[j][1]["utc"] in seen][:1]
        census_unmatched.append(dict(utc=key, line=line, position="last" if index == len(census) - 1 else
                                     "first" if index == 0 else "interior",
                                     previous_joined_utc=(before or [None])[0], next_joined_utc=(after or [None])[0]))
    if census_unmatched and first_rule is None:
        first_rule = "Reporting MHz/census inventories differ"
    if (census_errors or mhz_errors) and first_rule is None:
        first_rule = "unparseable JSON line (frozen json.loads would raise)"
    return dict(census_rows=len(census), mhz_rows=len(mhz), census_unparseable_lines=census_errors,
                mhz_unparseable_lines=mhz_errors,
                census_duplicate_utc=[dict(utc=k, lines=v) for k, v in dup_census.items()],
                census_wrong_host=wrong_host, mhz_duplicate_utc=[dict(utc=k, lines=v) for k, v in dup_mhz.items()],
                mhz_without_census=mhz_unmatched, census_without_mhz=census_unmatched,
                mhz_slots_mismatch=slot_mismatch, joined_rows=joined, full_occupancy_rows=full,
                full_occupancy_nonfinite_or_nonpositive_mhz=nonfinite, expected_slots=slots,
                frozen_join_would_pass=first_rule is None, first_frozen_rule_violated=first_rule)


def diagnose(a, mode):
    """Reads ONLY end-sources census.jsonl/mhz.jsonl (+ the pinned completion in repository mode)."""
    sources, origin, roots = {}, {}, mode.roots
    if a.s1_dest:
        require(a.repository is None and a.commit is None, "give either --s1-dest or --repository/--commit")
        require(a.s1_manifest is not None and a.s1_manifest_sha256 is not None,
                "--s1-dest needs --s1-manifest with a matching --s1-manifest-sha256")
        require(a.s1_manifest == f"{a.s1_dest}/{S1_MANIFEST_NAME}",
                f"--s1-manifest must be the receipt S1 wrote in --s1-dest ({S1_MANIFEST_NAME})")
        gated = gate_paths([("--s1-dest", a.s1_dest, roots.prep, "dir", None),
                            ("--s1-manifest", a.s1_manifest, roots.prep, "file", s1_manifest_name)])
        dest = gated["--s1-dest"][0]
        s1 = load_s1(gated["--s1-manifest"], a.s1_manifest_sha256, mode)
        manifest_pairs = s1["pairs"]
        if not mode.testing:
            require(manifest_pairs == sorted((h, p) for h, ps in PRODUCTION_PHASES.items() for p in ps),
                    "S1 manifest phases differ from the 10 pairs of record")
        for (host, phase, name), row in sorted(s1["files"].items()):
            require(HOST_NAME.fullmatch(host) and PHASE_NAME.fullmatch(phase), "unsafe S1 host/phase")
            rel = f"{host}/{phase}/{name}"
            sources[(host, phase, name)] = expected_read(f"S1 copy {rel}", f"S1 copy differs from its manifest: {rel}",
                                                         si.read_bytes, gated.policy, gated.role("--s1-dest"), rel,
                                                         row["local_size"], row["local_sha256"], codes=("sha", "size"))
        pairs = manifest_pairs
        origin = dict(source="s1-dest", s1_dest=dest, s1_manifest_path=s1["path"], s1_manifest_sha256=s1["sha256"])
    else:
        require(a.repository is not None and a.commit is not None and a.s1_manifest is None,
                "give --s1-dest (+ its --s1-manifest) or --repository and --commit")
        git_dirs = roots.worktree_git_dirs(a.repository, a.git_dir, a.git_common_dir)   # pure
        gated = gate_paths([("--repository", a.repository, roots.checkout, "dir", None)])
        repository = gated["--repository"][0]
        checkout = Checkout(gated.policy, gated.role("--repository"), repository, *git_dirs)
        commit = full_commit(checkout, a.commit)
        completion, _ = pinned_completion(checkout, commit, mode)
        pairs = counted_phases(completion, mode)
        for host, phase in pairs:
            for name in ("mhz.jsonl", "census.jsonl"):
                rel = repo_relative(SOURCES.format(host=host, phase=phase, name=name), "source")
                # commit-bound: si verifies the blob's type, size and OID from the full commit's tree (no other pin)
                sources[(host, phase, name)] = checkout.show(commit, rel, None, f"source {rel}")
        origin = dict(source="repository", repository=repository, commit=commit)
    phases, hosts = {}, {}
    for host, phase in pairs:
        census, census_errors = parse_rows(sources[(host, phase, "census.jsonl")], lambda r: r)
        mhz, mhz_errors = parse_rows(sources[(host, phase, "mhz.jsonl")], lambda r: r)
        report = diagnosis([(n, census_fields(r)) for n, r in census], [(n, mhz_fields(r)) for n, r in mhz],
                           host, REPORTING_SLOTS, census_errors, mhz_errors)
        report.update(census_sha256=sha_bytes(sources[(host, phase, "census.jsonl")]),
                      mhz_sha256=sha_bytes(sources[(host, phase, "mhz.jsonl")]))
        phases[f"{host}/{phase}"] = report
        h = hosts.setdefault(host, dict(full_occupancy_rows=0, phases_failing_join=[]))
        h["full_occupancy_rows"] += report["full_occupancy_rows"]
        if not report["frozen_join_would_pass"]:
            h["phases_failing_join"].append(phase)
    for host, h in hosts.items():
        h["frozen_minimum_two_full_occupancy_met"] = h["full_occupancy_rows"] >= 2
    clean = all(p["frozen_join_would_pass"] for p in phases.values()) and all(
        h["frozen_minimum_two_full_occupancy_met"] for h in hosts.values())
    return dict(schema=TEST_DIAGNOSIS_SCHEMA if mode.testing else DIAGNOSIS_SCHEMA, test_mode=mode.testing,
                utc=utc(), clean=clean, repair="none: diagnosis only; the frozen host_reporting refusal stands",
                health_fields_only=["utc", "host", "inflight", "slots", "physical_core_mhz (count/finite only)"],
                slots_rule=f"mhz.slots must equal {REPORTING_SLOTS} (every counted launch's slots; launch not read)",
                **origin, hosts=hosts, phases=phases)


# ---------------------------------------------------------------- CLI

def add_test_options(ap, *, validate_options=False):
    ap.add_argument("--test-mode", action="store_true", help=f"TESTS ONLY (also needs {TEST_ENV}={TEST_MARKER})")
    for key in ("plan", "completion", "counted_inventory", "blind_ledger"):
        ap.add_argument("--expect-" + key.replace("_", "-"), dest="expect_" + key, help="TEST-ONLY pin override")
    ap.add_argument("--expect-hosts", nargs="+", help="TEST-ONLY")
    ap.add_argument("--evidence-repository-path", help="TEST-ONLY (production: %s)" % EVIDENCE_REL)
    if validate_options:
        ap.add_argument("--expect-blocks", type=int, help="TEST-ONLY")
        ap.add_argument("--expect-losses", type=int, help="TEST-ONLY")
        ap.add_argument("--warmup-seconds", type=float, help="TEST-ONLY")
        ap.add_argument("--no-manifest-check", action="store_true", help="TEST-ONLY: skip the frozen-code bootstrap")


def add_worktree_options(ap):
    ap.add_argument("--git-dir", help="a linked worktree checkout's git dir (<main>/.git/worktrees/<name>)")
    ap.add_argument("--git-common-dir", help="a linked worktree checkout's common dir (<main>/.git)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repository", required=True)
    b.add_argument("--commit", required=True, help="the one commit containing every artifact")
    b.add_argument("--out", required=True, help="evidence file to write (exclusive, no-follow)")
    b.add_argument("--s1-manifest", help="S1 s1-copy-manifest.json (required in production)")
    b.add_argument("--s1-manifest-sha256")
    add_worktree_options(b)
    add_test_options(b)
    v = sub.add_parser("validate")
    v.add_argument("--repository", required=True, help="canonical checkout whose HEAD contains --commit")
    v.add_argument("--commit", required=True)
    v.add_argument("--evidence-sha256", required=True)
    v.add_argument("--code-root", help="canonical checkout holding the frozen code (default: --repository)")
    v.add_argument("--s1-manifest", help="S1 s1-copy-manifest.json (required in production)")
    v.add_argument("--s1-manifest-sha256")
    v.add_argument("--profile-json", help="{host: reference_load_profile} from the S4 bundles")
    v.add_argument("--profile-json-sha256")
    v.add_argument("--declared-default-profile", action="store_true",
                   help="acknowledge the declared S4 default profile (re-validate with --profile-json after S4)")
    v.add_argument("--result", required=True, help="result JSON to write (exclusive, no-follow)")
    add_worktree_options(v)
    add_test_options(v, validate_options=True)
    d = sub.add_parser("diagnose-clock")
    d.add_argument("--repository")
    d.add_argument("--commit")
    d.add_argument("--s1-dest", help="S1 destination tree (before the end-sources commit)")
    d.add_argument("--s1-manifest")
    d.add_argument("--s1-manifest-sha256")
    d.add_argument("--result", required=True)
    add_worktree_options(d)
    add_test_options(d)
    a = ap.parse_args(argv)
    if a.command == "build":
        try:
            build(a, Mode(a))
        except Exception as error:                        # fail closed
            print(f"S2 BUILD REFUSED: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        return 0
    context, code, mode, result_path, result_gate = {}, 2, None, None, None
    try:
        mode = Mode(a)
        # the result location is gated (lexical, allowed root, lstat walk, must not exist) before anything else
        result_gate = gate_paths([("--result", a.result, mode.roots.prep, "new", output_name)])
        result_path = result_gate["--result"][0]
        if a.command == "validate":
            result = validate(a, mode, context)
            code = 0
        else:
            result = diagnose(a, mode)
            code = 0 if result["clean"] else 3
    except Exception as error:                            # fail closed: frozen EvidenceError/ValueError included
        if result_path is None:                           # no gated result location: nothing is written anywhere
            print(f"S2 REFUSED (no result written): {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        testing = mode.testing
        base = (TEST_DIAGNOSIS_SCHEMA if testing else DIAGNOSIS_SCHEMA) if a.command == "diagnose-clock" else \
            (TEST_RESULT_SCHEMA if testing else RESULT_SCHEMA)
        result = dict(schema=base, test_mode=testing, ok=False, error_type=type(error).__name__, error=str(error),
                      utc=utc(), **({"clock_diagnosis": context["clock_diagnosis"]} if "clock_diagnosis" in context else {}))
        code = 2
    data = json.dumps(result, indent=1, sort_keys=True) + "\n"
    try:
        write_gated(result_gate, "--result", data.encode())
    except Exception as error:
        print(f"S2 REFUSED: result not written: {error}", file=sys.stderr)
        return 2
    print(data, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
