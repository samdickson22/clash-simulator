#!/usr/bin/env python3
"""K4S END fleet-reference bundle assembler (CANDIDATE b3-r3b; offline; never launches anything, never reads outcomes).

One explicit, SHA-pinned request describes every input by absolute path and expected SHA-256. The assembler checks
everything first, then copies each input into a fresh bundle directory, re-hashes every copy and writes the
`tiers-pins.json` manifest (schema clasher.e4v3.inputs.v1, profile fleet-reference) that the frozen consumers read:
tier_backend.validate_bundle (A3 02e2139f), fleet_validity.ReportingGuard (A5 0775b704), fleet_profile.slot_layout,
end_reference.frozen_identity and end_background.k4s_reporting_profile. Any mismatch raises AssemblyError and
leaves no bundle. Inputs are only read.

Read confinement (r2 S4-F1; r3 SOL-REVIEW-END-PKG1-r2 S4-R2-F1..F3). Every path, of every input class (request,
synthetic pins, runtime inventory and its S1 metadata, measurement entries, models and state rows, sets, END
evidence and its artifacts, guard freeze/modules/admissions/seeds) and every auxiliary location (--repository,
--out, the guard-job parent, committed-admission paths, evidence paths) goes through the same helpers BEFORE any
byte is read:
- inventory names must be normalized relative paths: not absolute, no '', '.', '..', backslash or NUL;
- location_free() on the COMPLETE absolute path: no 'games' or 'hub-blocks' component; no complete.json /
  local-complete.json / end-complete.json / interference.json / hub-ack.json / end-raw.json leaf; no K4S reporting
  job or live guard job component (k4s-confirm-*, k4s-end-guard-*); no strict END namespace (a 'k4s-confirm'
  component followed by 'end', i.e. reports/explore/k4s-confirm/end/ wherever it is rooted); none of FROZEN-T1's
  reporting/qualification/smoke launch namespaces;
- every component is lstat-walked from its declared root (request sources: from '/'): no symlink anywhere, and the
  leaf must be a regular file with st_nlink == 1 (a hard link to anything is refused before it is opened);
- each file is then opened O_NOFOLLOW|O_NONBLOCK and its fstat must still be a regular file with the walked
  (st_dev, st_ino) and st_nlink == 1 before any byte is read, hashed or copied. Replacement of an ancestor directory
  between the walk and the open is the accepted single-operator TOCTOU residual (coordinator scope ruling
  2026-10-12 16:00Z).
Exemptions (coordinator rulings 2026-10-12 16:55Z, E4 at 17:12Z), nothing else:
- E1: visualize_battle.py, only as the exact committed git mode-120000 entry of --repository HEAD whose blob is
  'examples/visualize_battle.py' and only as the same root-level link in the runtime tree. The link is never opened:
  its target is walked and opened by its own confined path and must pass the hard-link gate.
- E2/E4: exactly four tracked complete.json files (E4_COMPLETE_JSON: E2's throughput receipt plus three receipts under
  live-loop/v4), each only at its exact path and with its exact SHA; hashed, never parsed, never followed or aliased,
  and still subject to the location and hard-link gates. Fail-closed: any other path with a complete.json component,
  in the --repository HEAD tree (the build commit) or anywhere in the runtime tree, refuses, as does any of the four
  with another SHA or a non-regular entry. Runtime membership is unchanged (S1 list + rglob '*.py'; of the four, only
  E2 is listed in the A3 manifests' runtime_files): any of the four present in the runtime tree is hashed for this
  check, and only a member is added to runtime_files.
- E3: admissions only at reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>, with the pinned r4
  identities; a stale identity is refused (a re-pin needs a coordinator ruling).

Production pins (r2, S4-F2). Without the test switch, the constants in PRODUCTION_PINS are enforced: frozen models,
the Q6 state bytes (states.pkl 0addf7c0, states-rows.json bcd30777, states-rows.bin 8cc2f611), T1's own-tier sets
(canonical d84b07f6, equal in END-A3-manifest-01/08-f6cebbaa and the five A3/A5 manifests on 05), the measurement
inventory, the 128-CPU topology, the exact per-host guard admissions (03: system bus + idle service PID 2180947;
04: system bus only), the FROZEN-T1 freeze and the K4S plan. Each admission must also be the copy committed at
HEAD of --repository, bound by --committed-admission NAME REPOSITORY_PATH SHA256 (required; refused without it).
Test-only mode: K4S_S4_SYNTHETIC_PINS=<pins.json with "marker": "SYNTHETIC"> substitutes synthetic pins; it requires
an --out whose name contains SYNTHETIC and stamps the manifest and receipt SYNTHETIC-TEST-ONLY, so it can never
produce a production manifest. The pins file itself is read through the same confinement helpers, and test mode
cannot widen, narrow or move the E1/E4 exemptions (only the four E4 SHAs may differ, for synthetic bytes).

  assemble_fleet_reference.py --request R.json --request-sha256 S --repository REPO
      --committed-admission NAME REPOSITORY_PATH SHA256 [...] --out NEW_BUNDLE_DIR [--dry-run]

--dry-run validates everything (all hashes included) and prints the planned tiers-pins.json bytes to stdout;
it writes nothing. A real run prints nothing on stdout but writes NEW_BUNDLE_DIR/{<inputs>, tiers-pins.json,
tiers-pins.sha256, assembly-receipt.json} and prints a one-line summary to stderr.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

REQUEST_SCHEMA = "clasher.k4s.end-fleet-reference-request.v2"
RECEIPT_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"
PINS_SCHEMA = "clasher.k4s.end-fleet-reference-pins.v1"
BUNDLE_SCHEMA = "clasher.e4v3.inputs.v1"
EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
STATE_ROWS_SCHEMA = "clasher.e4v3.state-rows.v1"                  # state_rows.py:20
STATE_ROWS_PROTOCOL = 5                                            # state_rows.py:23
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
S1_RUNTIME_PINS = ("reports/explore/s1/receipts/runtime-pin-r2.json", "reports/explore/s1/receipts/runtime-pin.json")
S1_QUALIFIED = "reports/explore/s1/receipts/qualified-source-binding.json"
EVIDENCE_REPO_DIR = "reports/explore/k4s-confirm"                  # plan v2 S2: evidence outside end/
EVIDENCE_FILE = "end-evidence.json"
END_DIR = EVIDENCE_REPO_DIR + "/end"                               # END-RUNBOOK END_DIR (strict END namespace)
END_PAIR = ("k4s-confirm", "end")                                  # END_DIR's last two components, at any root
ADMISSION_REPO_DIR = EVIDENCE_REPO_DIR + "/end-guard-admissions"   # E3 (COORDINATOR 2026-10-12 16:55Z; Sol R1)
# E1 / E2 exemptions (COORDINATOR 2026-10-12 16:55Z). Fixed here: neither pins file can widen or move them.
E1_ALIAS, E1_TARGET = "visualize_battle.py", "examples/visualize_battle.py"
E2_PATH = "imitation/model/receipts/throughput-0935/complete.json"
E2_SHA256 = "d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc"
# E4 (COORDINATOR 2026-10-12 17:12Z): the ONLY tracked complete.json files allowed, at exact path and SHA (E2 first).
# Hashed, never parsed. Any other complete.json at the build commit or in the runtime tree refuses (a new ruling is
# needed to add one). Fixed here: test mode may substitute only the SHAs (synthetic bytes), never the paths.
OUTCOME_RECEIPT = "complete.json"
E4_COMPLETE_JSON = {
    E2_PATH: E2_SHA256,
    "reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json":
        "0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json":
        "9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json":
        "724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d",
}
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

# Production pins (coordinator rulings 15:41Z Q2/Q6 and 16:00Z S4). Sources, all verified in this session:
# - Q6 bytes: sha256 of the 05 copies in t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle/ (read-only), equal to
#   files[] of END-A3-manifest-01/08-f6cebbaa.json (bd9804c3 / 1bd8a4c7);
# - sets: canonical sha256 of `sets` (golden 125; speed 4 x 300) in END-A3-manifest-01/08-f6cebbaa.json and in the A5
#   manifests f81c9288 (= END-A5-reference-approved-argv-08-r1 manifest_sha256), 93daf063, 5df0fa00, c84d65ed on 05;
# - measurement inventory: canonical sha of the frozen e4v3 18-file rule (= END-A5-runtime-manifest-inventory-diff);
# - admissions: committed r4 host admissions rounds/r4/evidence/step7/127x0{3,4}-host-admission.json (process rows),
#   and t1/receipts/idle-services-admission-127x03.json (service identity, PID 2180947);
# - runtime alias / outcome-name exception: runtime_files of END-A3-manifest-01/08-f6cebbaa.json (a tracked git
#   symlink and an S1 runtime-pin-r2 member; the latter's bytes were not opened by the implementer);
# - E4 list: the ruled path + SHA of each; b3-r3b re-hashed each `git show origin/main:<path>` (d482ab3d, sha256 only).
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
    "runtime_aliases": {E1_ALIAS: E1_TARGET},
    "runtime_outcome_name_exceptions": dict(E4_COMPLETE_JSON),
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
JOB_PARENTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
JOB_NAME = re.compile(r"k4s-end-guard-r[1-9][0-9]*-(rd[0-9]{2}-a[0-9]{2}|pf[0-9]{2})")
PROFILE = dict(reference_slot=0, console_rule=False, warmup_seconds=300, perception="none")

# Outcome / block / job-tree locations that no input may come from (checked on names BEFORE any read).
OUTCOME_DIRS = frozenset(("games", "hub-blocks"))
OUTCOME_LEAVES = frozenset(("complete.json", "local-complete.json", "end-complete.json", "interference.json",
                            "hub-ack.json", "end-raw.json"))
JOB_COMPONENT = re.compile(r"k4s-confirm-.+|k4s-end-guard-.+")
T1_LAUNCH_NAMESPACES = (                                           # FROZEN-T1.json launch_namespaces
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op5-08join-r2",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/smoke-after-op6-08-r7",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op6-0108-r1",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op6-01-r1",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op6-08-r1",
)
REPO_PATH = re.compile(r"[A-Za-z0-9._/-]+")

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


# ---------------------------------------------------------------- confinement (names first, then lstat, then open)

def relative(name, label):
    """A normalized relative POSIX path: not absolute, no '', '.', '..', backslash or NUL component."""
    require(isinstance(name, str) and name and "\\" not in name and "\x00" not in name,
            "Unsafe relative path (" + label + "): " + repr(name))
    require(not name.startswith("/") and all(p not in ("", ".", "..") for p in name.split("/")),
            "Unsafe relative path (" + label + "): " + name)
    return str(PurePosixPath(name))


def outcome_free(parts, label, exception=False):
    """Refuse outcome, block and job-tree locations by name (never by reading)."""
    parts = list(parts)
    for part in parts[:-1] if parts else ():
        require(part not in OUTCOME_DIRS, "Outcome-bearing path refused (" + label + ")")
    for part in parts:
        require(JOB_COMPONENT.fullmatch(part) is None, "Reporting/guard job tree refused (" + label + ")")
    if parts:
        require(parts[-1] not in OUTCOME_DIRS, "Outcome-bearing path refused (" + label + ")")
        require(exception or parts[-1] not in OUTCOME_LEAVES, "Outcome-bearing path refused (" + label + ")")


def no_t1_launch_namespace(path, label):
    text = str(path)
    for prefix in T1_LAUNCH_NAMESPACES:
        require(text != prefix and not text.startswith(prefix + "/"), "T1 reporting job tree refused (" + label + ")")


def end_namespace_free(parts, label):
    """The strict END namespace (END_DIR = reports/explore/k4s-confirm/end) is refused wherever it is rooted: in the
    repository, a runtime export or any copy. Its receipts/registry/pools are sealed END outputs (END-RUNBOOK)."""
    parts = list(parts)
    for i in range(len(parts) - 1):
        require((parts[i], parts[i + 1]) != END_PAIR, "Strict END namespace refused (" + label + ")")


def location_free(path, label, exception=False):
    """Every name gate on a COMPLETE absolute path, before any lstat or open (r3: one helper for every input class
    and every auxiliary location). ``exception`` only exempts the leaf from OUTCOME_LEAVES (the exact E4 paths only)."""
    text = str(path)
    require(isinstance(path, (str, Path)) and text.startswith("/") and not text.startswith("//")
            and os.path.normpath(text) == text and "\x00" not in text and "\\" not in text,
            "Unsafe absolute path (" + label + "): " + repr(text))
    parts = text[1:].split("/") if text != "/" else []
    outcome_free(parts, label, exception)
    end_namespace_free(parts, label)
    no_t1_launch_namespace(text, label)
    return text


def walk(root, rel, label, kind="file", alias=None, exception=False):
    """Name gates on root/rel, then lstat every component (root itself already confined). Returns (path, lstat).

    No component may be a symlink; a file leaf must be regular with st_nlink == 1 (r3, S4-R2-F1). ``alias`` = the
    exact readlink text of a pinned in-tree alias for the LEAF (E1): then the leaf must be that symlink and the walk
    restarts at its (relative, confined) target, which passes every gate including the hard-link gate."""
    location_free(os.path.join(str(root), rel), label, exception)
    current = Path(root)
    parts = rel.split("/")
    for i, part in enumerate(parts):
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise AssemblyError("Missing input (" + label + "): " + rel) from None
        except OSError as error:
            raise AssemblyError("Unreadable input path (" + label + "): " + rel + ": " + error.strerror) from None
        last = i == len(parts) - 1
        if stat.S_ISLNK(st.st_mode):
            require(last and alias is not None, "Symlink/alias component refused (" + label + "): " + rel)
            require(len(parts) == 1, "A pinned alias must sit at the root (its link text is root-relative): " + rel)
            require(os.readlink(current) == alias, "Runtime alias differs from its pin: " + rel)
            target = relative(alias, "alias target")
            return walk(root, target, label, kind)       # never opened through the link: the target walks on its own
        require(alias is None or not last, "Pinned runtime alias is not a symlink: " + rel)
        if not last:
            require(stat.S_ISDIR(st.st_mode), "Non-directory path component (" + label + "): " + rel)
    if kind == "dir":
        require(stat.S_ISDIR(st.st_mode), label + " is not a directory: " + rel)
    else:
        require(stat.S_ISREG(st.st_mode), label + " is not a regular file: " + rel)
        require(st.st_nlink == 1, "Hard-linked input refused (" + label + "): " + rel)
    return current, st


def absolute(value, label, kind):
    """An absolute request path, normalized, name-gated and lstat-walked from '/' (walk applies location_free)."""
    require(isinstance(value, str) and value.startswith("/") and "\x00" not in value and "\\" not in value,
            label + " must be an absolute path")
    require(os.path.normpath(value) == value and not value.startswith("//"), label + " must be a normalized path: " + value)
    rel = value[1:]
    relative(rel, label)
    path, st = walk("/", rel, label, kind)
    return Path(value), st


def open_confined(path, st):
    """The descriptor gate: O_NOFOLLOW open, then fstat BEFORE any read: the descriptor must be the regular file the
    walk saw (same st_dev/st_ino) and must have exactly one link (r3, S4-R2-F1)."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise AssemblyError("Cannot open input without following links: " + str(path) + ": " + error.strerror) from None
    now = os.fstat(fd)
    if not (stat.S_ISREG(now.st_mode) and (now.st_dev, now.st_ino) == (st.st_dev, st.st_ino)):
        os.close(fd)
        raise AssemblyError("Input changed between check and open: " + str(path))
    if now.st_nlink != 1:
        os.close(fd)
        raise AssemblyError("Hard-linked input refused at open (st_nlink " + str(now.st_nlink) + "): " + str(path))
    return os.fdopen(fd, "rb")


def sha_confined(path, st):
    digest = hashlib.sha256()
    with open_confined(path, st) as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_confined(path, st):
    with open_confined(path, st) as stream:
        return stream.read()


class Source:
    """A confined input: path + the lstat identity it must still have when it is opened (hash, parse or copy)."""
    __slots__ = ("path", "st")

    def __init__(self, path, st):
        self.path, self.st = Path(path), st

    def sha(self):
        return sha_confined(self.path, self.st)

    def read(self):
        return read_confined(self.path, self.st)

    def size(self):
        return self.st.st_size


def entry_shape(entry, label):
    require(isinstance(entry, dict) and set(entry) == {"source", "sha256"}, "Input entry must be {source, sha256}: " + label)
    require(is_sha(entry["sha256"]), "Input SHA is not a SHA-256: " + label)


def pinned_source(entry, label, expected=None):
    """{source, sha256} -> (Source, sha); the file's SHA must equal the request's and, if given, the pinned value."""
    entry_shape(entry, label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the pinned value: " + label)
    source = Source(*absolute(entry["source"], label, "file"))
    require(source.sha() == entry["sha256"], "Pin mismatch: " + label)
    return source, entry["sha256"]


def parse_json(raw, label):
    try:
        return json.loads(raw)
    except ValueError:
        raise AssemblyError("Not JSON: " + label) from None


def pinned_json(entry, label, expected=None):
    """Hash and parse the same bytes (one open)."""
    entry_shape(entry, label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the pinned value: " + label)
    source = Source(*absolute(entry["source"], label, "file"))
    raw = source.read()
    require(hashlib.sha256(raw).hexdigest() == entry["sha256"], "Pin mismatch: " + label)
    return source, entry["sha256"], parse_json(raw, label)


# ---------------------------------------------------------------- pins (production constants or test-only synthetic)

def active_pins():
    """PRODUCTION_PINS unless the test-only switch names a SYNTHETIC pins file. Returns (pins, synthetic)."""
    location = os.environ.get(SYNTHETIC_ENV)
    if location is None:
        return PRODUCTION_PINS, False
    # r3 (S4-R2-F3): the same name, lstat-walk, hard-link and descriptor gates as every other input, before any read.
    pins = parse_json(read_confined(*absolute(location, SYNTHETIC_ENV, "file")), "synthetic pins")
    require(isinstance(pins, dict) and pins.get("schema") == PINS_SCHEMA and pins.get("marker") == SYNTHETIC_MARKER
            and set(pins) == PIN_KEYS | {"schema"}, "Synthetic pins must carry marker SYNTHETIC and every pin key")
    check_exemptions(pins, synthetic=True)
    return pins, True


def check_exemptions(pins, synthetic):
    """E1/E4 are fixed: the alias map is exactly E1 and the outcome-name exceptions are exactly the four E4 paths (their
    SHAs are E4's in production; test mode may only substitute the SHAs of synthetic bytes)."""
    require(pins.get("runtime_aliases") == {E1_ALIAS: E1_TARGET}, "Runtime aliases must be exactly the E1 exemption")
    exceptions = pins.get("runtime_outcome_name_exceptions")
    require(isinstance(exceptions, dict) and set(exceptions) == set(E4_COMPLETE_JSON)
            and all(is_sha(digest) for digest in exceptions.values()),
            "Runtime outcome-name exceptions must be exactly the E4 exempt list")
    require(synthetic or exceptions == E4_COMPLETE_JSON,
            "Runtime outcome-name exceptions must carry the E4 SHAs in production")


# ---------------------------------------------------------------- frozen inventory rules, confined (prepare_bundle.py)

def measurement_files(e4v3):
    """prepare_bundle.py:117 rule (suffix .py/.sh or spec-pins.json, non-recursive); every entry is gated and walked
    (regular, single link) before any entry is hashed."""
    e4v3 = Path(e4v3)
    checked = {}
    for entry in sorted(os.scandir(e4v3), key=lambda e: e.name):
        if Path(entry.name).suffix in (".py", ".sh") or entry.name == "spec-pins.json":
            checked[entry.name] = walk(e4v3, relative(entry.name, "measurement entry"), "measurement entry")
    return {name: sha_confined(*found) for name, found in checked.items()}


def runtime_python(root, aliases, exceptions):
    """The names prepare_bundle's root.rglob('*.py') yields (Python 3.12: file symlinks matched, symlinked directories
    not descended), found WITHOUT following any link. Refuses every symlink except the pinned aliases, and every
    outcome/block/job directory and the strict END namespace directory (refused, never listed or descended).
    E4: any entry named complete.json (file, directory, link, anything) must be one of the exact exempt paths.
    Returns (python names, exempt complete.json names present)."""
    found, present, stack = [], [], [""]
    while stack:
        prefix = stack.pop()
        with os.scandir(Path(root) / prefix if prefix else root) as entries:
            for entry in entries:
                name = prefix + entry.name
                if entry.name == OUTCOME_RECEIPT:
                    require(name in exceptions, "complete.json not on the E4 exempt list refused (runtime tree): " + name)
                    present.append(name)
                if entry.is_symlink():
                    require(name in aliases, "Symlink/alias in the runtime tree refused: " + name)
                elif entry.is_dir(follow_symlinks=False):
                    require(entry.name not in OUTCOME_DIRS and JOB_COMPONENT.fullmatch(entry.name) is None,
                            "Outcome/job directory in the runtime tree refused: " + name)
                    end_namespace_free(os.path.join(str(root), name)[1:].split("/"), "runtime directory " + name)
                    stack.append(name + "/")
                if entry.name.endswith(".py"):          # as rglob: directories/specials too (then refused as non-files)
                    found.append(name)
    return found, present


def runtime_files(root, pins=None):
    """prepare_bundle.runtime_pins (prepare_bundle.py:36-52), same membership rule; every name confined first."""
    root = Path(root)
    pins = active_pins()[0] if pins is None else pins
    check_exemptions(pins, synthetic=pins is not PRODUCTION_PINS)
    aliases = pins["runtime_aliases"]
    exceptions = pins["runtime_outcome_name_exceptions"]
    source = None
    for candidate in S1_RUNTIME_PINS:                     # runtime-pin-r2.json, else runtime-pin.json (fixed names)
        try:
            source = walk(root, candidate, "S1 runtime pin")
            break
        except AssemblyError as error:
            if not str(error).startswith("Missing input"):
                raise
    require(source is not None, "Runtime lacks the S1 runtime pin")
    listing = parse_json(read_confined(*source), "S1 runtime pin")
    listed = listing.get("files") if isinstance(listing, dict) else None
    require(isinstance(listed, list) and all(isinstance(n, str) for n in listed), "S1 runtime pin lacks a files list")
    names = {relative(n, "S1 runtime-pin entry") for n in listed}
    python, present = runtime_python(root, aliases, exceptions)
    names.update(python)
    checked = {}
    for name in sorted(names | set(present)):   # every name is gated and walked before ANY runtime member is hashed
        try:
            checked[name] = walk(root, name, "runtime entry " + name, alias=aliases.get(name),
                                 exception=name in exceptions)
        except AssemblyError as error:
            if str(error).startswith("Missing input"):
                checked[name] = None
            else:
                raise
    missing = sorted(name for name, found in checked.items() if found is None)
    require(not missing, "Incomplete frozen runtime: " + repr(missing[:8]))
    hashed = {name: sha_confined(*found) for name, found in sorted(checked.items())}     # one open each
    for name, expected in exceptions.items():
        require(name not in hashed or hashed[name] == expected, "Runtime outcome-named entry differs from its pin: " + name)
    result = {name: hashed[name] for name in sorted(names)}    # E4 non-members are checked, never runtime members
    qualified = parse_json(read_confined(*walk(root, S1_QUALIFIED, "S1 qualified binding")), "S1 qualified binding")
    files = qualified.get("qualified_source_files") if isinstance(qualified, dict) else None
    require(isinstance(files, dict), "S1 qualified binding lacks qualified_source_files")
    for name, expected in files.items():
        require(result.get(name) == expected, "Not the qualified S1 tier source: " + str(name))
    return result


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


# ---------------------------------------------------------------- committed admissions (--repository HEAD)

def git_run(repository, args, label):
    """Read-only git plumbing in the confined repository; a nonzero status always refuses."""
    try:
        done = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, timeout=300,
                              env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    except (OSError, subprocess.SubprocessError):
        raise AssemblyError("git unavailable for " + label) from None
    require(done.returncode == 0, "Not committed at HEAD of --repository (" + label + "): " + " ".join(args[-1:]))
    return done.stdout


def git_blob(repository, rel, label):
    """Bytes of HEAD:<rel> (one named blob). The repository path passes the same name gates as every input."""
    require(REPO_PATH.fullmatch(rel) is not None, "Repository path has unsupported characters (" + label + ")")
    location_free(os.path.join(str(repository), relative(rel, label)), label)
    return git_run(repository, ["cat-file", "blob", "HEAD:" + rel], label)


def committed_alias(repository):
    """E1: visualize_battle.py is exempt only as the exact committed git entry: mode 120000 at the repository root of
    HEAD, whose blob (the link text) is exactly examples/visualize_battle.py. Tree metadata and one blob only."""
    listing = git_run(repository, ["ls-tree", "-z", "HEAD", "--", E1_ALIAS], "E1 alias")
    match = re.fullmatch(rb"120000 blob ([0-9a-f]{40}|[0-9a-f]{64})\t" + re.escape(E1_ALIAS.encode()) + rb"\x00", listing)
    require(match is not None, "E1 alias is not a committed mode-120000 entry at HEAD of --repository: " + E1_ALIAS)
    require(git_run(repository, ["cat-file", "blob", match.group(1).decode()], "E1 alias") == E1_TARGET.encode(),
            "E1 alias link text at HEAD is not " + E1_TARGET)


def committed_receipts(repository, exceptions):
    """E4 at the build commit: every path tracked at HEAD of --repository with a complete.json component must be one of
    the exact exempt paths, a regular blob (mode 100644, never a link) whose bytes hash to its pin. Tree metadata
    first; only exempt blobs are then streamed by git, hashed and never parsed. Any other tracked complete.json refuses.
    (These are git objects, not paths: the location and hard-link gates apply where a file is opened, i.e. the runtime.)"""
    listing = git_run(repository, ["ls-tree", "-r", "-z", "--full-tree", "HEAD"], "E4 tracked complete.json")
    for record in listing.split(b"\x00"):
        if not record:
            continue
        meta, tab, raw = record.partition(b"\t")
        name = os.fsdecode(raw)
        require(tab == b"\t" and raw, "Malformed git ls-tree record at HEAD of --repository")
        if OUTCOME_RECEIPT not in name.split("/"):
            continue
        require(name in exceptions, "Tracked complete.json not on the E4 exempt list refused: " + name)
        match = re.fullmatch(rb"100644 blob ([0-9a-f]{40}|[0-9a-f]{64})", meta)
        require(match is not None, "Tracked E4 exempt entry is not a regular committed file: " + name)
        blob = git_run(repository, ["cat-file", "blob", match.group(1).decode()], "E4 tracked " + name)
        require(hashlib.sha256(blob).hexdigest() == exceptions[name],
                "Tracked E4 exempt complete.json differs from its pin: " + name)


def committed_bindings(values, repository, host, pins):
    """--committed-admission NAME REPOSITORY_PATH SHA256 -> {name: (rel, sha)}; exactly the host's pinned set, each at
    its E3 path reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>."""
    required = set(pins["admissions"].get(host, {}))
    require(required, "No pinned admissions for host " + str(host))
    bindings = {}
    for name, rel, digest in values or ():
        require(name in ADMISSIONS and name not in bindings, "Unknown/duplicate --committed-admission: " + repr(name))
        rel = relative(rel, "committed admission path")
        location_free(os.path.join(str(repository), rel), "committed admission")
        expected = ADMISSION_REPO_DIR + "/" + host + "-" + name
        require(rel == expected, "Committed admission must be exactly " + expected + " (E3): " + rel)
        require(is_sha(digest), "Committed admission SHA is not a SHA-256: " + name)
        bindings[name] = (rel, digest)
    require(set(bindings) == required, "--committed-admission is required for exactly " + repr(sorted(required))
            + " on " + host + " (got " + repr(sorted(bindings)) + ")")
    for name, (rel, digest) in bindings.items():
        require(hashlib.sha256(git_blob(repository, rel, name)).hexdigest() == digest,
                "Committed admission blob differs from --committed-admission SHA: " + name)
    return bindings


# ---------------------------------------------------------------- planning (all checks; no writes)

def plan_bundle(request, repository, committed):
    """Every check, in order. Returns (copies {bundle name: (Source, sha)}, manifest, facts)."""
    PINS, synthetic = active_pins()
    require(isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA, "Unsupported request schema")
    keys = {"schema", "host", "runtime_root", "runtime_files_sha256", "measurement_files_sha256", "topology", "sets",
            "models", "end_evidence", "guard"}
    require(set(request) == keys, "Request keys differ from the schema: " + repr(sorted(set(request) ^ keys)))
    host = request["host"]
    require(host in JOB_PARENTS, "Host is not a K4S END host: " + repr(host))
    copies = {}

    def add(name, source, digest):
        name = relative(name, "bundle name")
        require(name not in copies and name not in (MANIFEST, MANIFEST_SHA, RECEIPT), "Bundle name collision: " + name)
        copies[name] = (source, digest)
        return name

    repo, _ = absolute(str(repository) if repository is not None else None, "--repository", "dir")
    bindings = committed_bindings(committed, repo, host, PINS)
    committed_alias(repo)                                              # E1, before the runtime walk relies on it
    committed_receipts(repo, PINS["runtime_outcome_name_exceptions"])  # E4 at the build commit (tree, exempt blobs)

    # 1. runtime + e4v3 (the e4v3 that end_reference imports is ROOT/E4V3_REL of the runtime tree)
    root, _ = absolute(request["runtime_root"], "runtime_root", "dir")
    e4v3, _ = walk(root, E4V3_REL, "runtime e4v3", "dir")
    measured = measurement_files(e4v3)
    require(request["measurement_files_sha256"] == PINS["measurement_files_sha256"],
            "measurement_files_sha256 differs from the pinned inventory")
    require(canonical_sha(measured) == request["measurement_files_sha256"],
            "measurement_files differ from the request (computed " + canonical_sha(measured) + ")")
    specification = parse_json(read_confined(*walk(e4v3, "spec-pins.json", "e4v3 spec-pins")), "e4v3 spec-pins.json")
    runtime = runtime_files(root, PINS)
    require(is_sha(request["runtime_files_sha256"]) and canonical_sha(runtime) == request["runtime_files_sha256"],
            "runtime_files differ from the request (computed " + canonical_sha(runtime) + ")")

    # 2. models and state rows (tier_backend.py:459-461, :466-468; state_rows.py:34-61 mirrored, no pickle)
    models = request["models"]
    require(isinstance(models, dict) and set(models) == set(MODEL_NAMES), "Model inputs must be exactly " + repr(MODEL_NAMES))
    model_pins = {}
    for name in MODEL_NAMES:
        if name == "states-rows.json":
            continue
        source, digest = pinned_source(models[name], "model " + name, PINS["models"][name])
        model_pins[name] = digest
        add(name, source, digest)
    source, digest, index = pinned_json(models["states-rows.json"], "model states-rows.json", PINS["models"]["states-rows.json"])
    add("states-rows.json", source, digest)
    ids = check_state_index(index, model_pins, copies["states-rows.bin"][0].size())

    # 3. sets: T1's own-tier sets exactly (canonical pin); TierBackend._load_inputs / corpus_loop shape
    _, _, sets = pinned_json(request["sets"], "sets")
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
    require(evidence["artifacts_root"] == str(repo / EVIDENCE_REPO_DIR)
            and evidence["source"] == str(repo / EVIDENCE_REPO_DIR / EVIDENCE_FILE),
            "END evidence must be --repository/" + EVIDENCE_REPO_DIR + "/" + EVIDENCE_FILE + " with that artifacts_root")
    source, evidence_sha, document = pinned_json(dict(source=evidence["source"], sha256=evidence["sha256"]), "END evidence")
    require(hashlib.sha256(git_blob(repo, EVIDENCE_REPO_DIR + "/" + EVIDENCE_FILE, "END evidence")).hexdigest()
            == evidence_sha, "END evidence differs from its committed HEAD blob")
    add(EVIDENCE_NAME, source, evidence_sha)
    artifacts, _ = absolute(evidence["artifacts_root"], "artifacts_root", "dir")
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
    for item in items:
        require(isinstance(item, dict) and {"path", "sha256", "commit", "repository_path"} <= set(item),
                "END evidence item lacks path/sha256/commit/repository_path")
        name = relative(item["path"], "evidence item")
        require(item["repository_path"] == EVIDENCE_REPO_DIR + "/" + name,
                "END evidence item is not its repository path relative to the evidence: " + name)
        location_free(os.path.join(str(artifacts), name), "evidence artifact")     # incl. the strict END namespace
        require(is_sha(item["sha256"]) and isinstance(item["commit"], str) and COMMIT.fullmatch(item["commit"]),
                "END evidence item needs a SHA-256 and a full commit: " + name)
        commits.add(item["commit"])
        if name in seen:
            require(seen[name] == item["sha256"], "Conflicting END evidence pin: " + name)
            continue
        seen[name] = item["sha256"]
        artifact = Source(*walk(artifacts, name, "END evidence artifact"))
        require(artifact.sha() == item["sha256"], "Pin mismatch: END evidence artifact " + name)
        add(EVIDENCE_DIR + "/" + name, artifact, item["sha256"])
    require(len(commits) == 1, "END evidence artifacts must be bound to one commit")
    plan_item = document["plan"]
    require(plan_item["sha256"] == PINS["k4s_plan_sha256"], "END evidence plan is not the frozen K4S plan")
    plan_name = EVIDENCE_DIR + "/" + relative(plan_item["path"], "plan")
    raw = copies[plan_name][0].read()
    require(hashlib.sha256(raw).hexdigest() == PINS["k4s_plan_sha256"], "Pin mismatch: K4S plan")
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
    job = guard["job"]
    location_free(JOB_PARENTS[host], "guard job parent")      # the job leaf is the one k4s-end-guard-* name allowed
    require(isinstance(job, str) and os.path.normpath(job) == job and os.path.dirname(job) == JOB_PARENTS[host]
            and JOB_NAME.fullmatch(os.path.basename(job)) is not None,
            "Guard job must be " + JOB_PARENTS[host] + "/k4s-end-guard-r<N>-rd<RR>-a<NN> or -pf<NN> on " + host)
    require(not os.path.lexists(job), "Guard job already exists (each attempt/preflight needs a fresh job): " + job)
    source, digest, freeze = pinned_json(guard["freeze"], "guard freeze", PINS["frozen_t1_sha256"])
    add(FREEZE_NAME, source, digest)
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
        source, digest = pinned_source(modules[name], "guard module " + name, expected)
        add(GUARD_ROOT + "/" + name, source, digest)
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
        require(entry["source"] == str(repo / rel), "Admission source is not its committed copy: " + name)
        source, digest, value = pinned_json(entry, "admission " + name, committed_sha)
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
        admission_map[name] = add(ADMISSION_DIR + "/" + name, source, digest)
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
        source, digest, value = pinned_json(seeds[name], "seed " + name, b["sha256"])
        parsed[name] = (source, digest)
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
    seed_map = {name: add(SEED_DIR + "/" + name, *parsed[name]) for name in sorted(parsed)}

    # 7. manifest (key order irrelevant: written canonically)
    files = {name: digest for name, (_, digest) in copies.items()}
    profile = dict(PROFILE, host=host, slot_count=slot_count, plan=plan_name, end_evidence=EVIDENCE_NAME,
                   guard=dict(root=GUARD_ROOT, job=job, freeze=FREEZE_NAME, admissions=admission_map, seed_inputs=seed_map))
    manifest = dict(schema=BUNDLE_SCHEMA, final=False, profile="fleet-reference", threshold=THRESHOLD,
                    specification=specification, files=files, runtime_files=runtime, measurement_files=measured,
                    topology=topology, sets=sets, reference_load_profile=profile)
    if synthetic:
        manifest["k4s_s4_synthetic"] = SYNTHETIC_STAMP
    facts = dict(synthetic=synthetic, pins_sha256=canonical_sha(PINS), repository=str(repo),
                 committed_admissions={n: dict(repository_path=r, sha256=s) for n, (r, s) in sorted(bindings.items())},
                 trees=(root, artifacts, repo))
    return copies, manifest, facts


# ---------------------------------------------------------------- writing (only after every check passed)

def manifest_bytes(manifest):
    return (canonical(manifest) + "\n").encode()


def check_out(out, facts):
    """A new absolute directory whose parent is lstat-confined (no symlink component), outside every input tree."""
    out = Path(out) if out is not None else None
    require(out is not None and str(out).startswith("/") and os.path.normpath(str(out)) == str(out)
            and out.name and not str(out).startswith("//"), "--out must be a new normalized absolute directory")
    location_free(str(out), "--out")                    # r3 (S4-R2-F2): never into an outcome/END/job/T1 location
    parent, _ = walk("/", str(out.parent)[1:], "--out parent", "dir") if str(out.parent) != "/" else (Path("/"), None)
    require(not os.path.lexists(out), "--out must be a new absolute directory")
    require(not os.path.lexists(out.parent / (out.name + ".partial")), "A previous partial bundle exists: " + str(out))
    for tree in facts["trees"]:
        tree = Path(tree)
        require(tree not in out.parents and tree != out, "--out must not be inside an input tree: " + str(tree))
    if facts["synthetic"]:
        require(SYNTHETIC_MARKER in out.name, "Synthetic (test-only) pins require an --out named *SYNTHETIC*")
    return out


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def copy_verified(source, target, digest):
    """Copy from the confined descriptor while hashing; exclusive no-follow target; then re-hash the copy."""
    seen = hashlib.sha256()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o644)
    with open_confined(source.path, source.st) as reader, os.fdopen(fd, "wb") as writer:
        for block in iter(lambda: reader.read(1 << 20), b""):
            seen.update(block)
            writer.write(block)
    require(seen.hexdigest() == digest, "Source changed while copying: " + str(target.name))


def write_bundle(copies, manifest, out, request, request_sha, facts):
    out = check_out(out, facts)
    stage = out.parent / (out.name + ".partial")
    os.mkdir(stage, 0o755)
    try:
        for name, (source, digest) in sorted(copies.items()):
            target = stage / name
            directory = stage
            for part in name.split("/")[:-1]:
                directory = directory / part
                if not os.path.lexists(directory):
                    os.mkdir(directory, 0o755)
                require(stat.S_ISDIR(os.lstat(directory).st_mode), "Bundle directory is not a plain directory: " + name)
            copy_verified(source, target, digest)
            require(sha_confined(target, os.lstat(target)) == digest, "Copy differs from its pin: " + name)
            os.chmod(target, 0o444)
        data = manifest_bytes(manifest)
        digest = hashlib.sha256(data).hexdigest()
        write_new(stage / MANIFEST, data)
        write_new(stage / MANIFEST_SHA, (digest + "  " + MANIFEST + "\n").encode())
        status = SYNTHETIC_STAMP if facts["synthetic"] else "CANDIDATE"
        receipt = dict(schema=RECEIPT_SCHEMA, request_sha256=request_sha, manifest_sha256=digest,
                       files=len(manifest["files"]), host=request["host"], guard_job=request["guard"]["job"],
                       assembler_sha256=facts["assembler_sha256"],
                       pins_sha256=facts["pins_sha256"], production_pins=not facts["synthetic"],
                       committed_admissions=facts["committed_admissions"], final=False, outcomes_read=False,
                       live_actions=False, status=status)
        write_new(stage / RECEIPT, (canonical(receipt) + "\n").encode())
        for name in (MANIFEST, MANIFEST_SHA, RECEIPT):
            os.chmod(stage / name, 0o444)
        require(not os.path.lexists(out), "--out appeared during assembly")
        os.rename(stage, out)
    except BaseException:
        remove_stage(stage)
        raise
    return digest


def remove_stage(stage):
    """Remove our own partial directory without following links (copies are 0444; make writable first)."""
    for dirpath, dirnames, filenames in os.walk(stage, topdown=False, followlinks=False):
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]:
            try:
                os.unlink(os.path.join(dirpath, name))
            except OSError:
                pass
        for name in dirnames:
            try:
                os.rmdir(os.path.join(dirpath, name))
            except OSError:
                pass
    try:
        os.rmdir(stage)
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--request-sha256", required=True)
    ap.add_argument("--repository", required=True, help="K4S repository checkout holding the committed evidence/admissions")
    ap.add_argument("--committed-admission", nargs=3, action="append", metavar=("NAME", "REPOSITORY_PATH", "SHA256"),
                    help="committed Q2 admission copy (required: bus on both hosts; idle-services on 127x03)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    assembler = Source(*absolute(os.path.abspath(__file__), "assembler", "file")).sha()
    raw = Source(*absolute(str(a.request.absolute()), "--request", "file")).read()   # r3: confined like every input
    require(is_sha(a.request_sha256) and hashlib.sha256(raw).hexdigest() == a.request_sha256, "Request SHA mismatch")
    request = parse_json(raw, "request")
    copies, manifest, facts = plan_bundle(request, a.repository, a.committed_admission)
    facts["assembler_sha256"] = assembler
    check_out(a.out, facts)
    if a.dry_run:
        sys.stdout.buffer.write(manifest_bytes(manifest))
        sys.stdout.flush()
        print(canonical(dict(dry_run=True, manifest_sha256=hashlib.sha256(manifest_bytes(manifest)).hexdigest(),
                             files=len(manifest["files"]), production_pins=not facts["synthetic"], written=False)),
              file=sys.stderr)
        return 0
    digest = write_bundle(copies, manifest, a.out, request, a.request_sha256, facts)
    print(canonical(dict(dry_run=False, manifest_sha256=digest, files=len(manifest["files"]), out=str(a.out),
                         production_pins=not facts["synthetic"])), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssemblyError as error:
        print("ASSEMBLY REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
