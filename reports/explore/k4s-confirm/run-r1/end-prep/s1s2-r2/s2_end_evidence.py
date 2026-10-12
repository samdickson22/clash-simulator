#!/usr/bin/env python3
"""S2 (PREREG-K4S END, RC-4b): END evidence builder + offline validator + clock diagnosis. r2. 127x05 only; no ssh.

CANDIDATE: requires Sol review before use.

build          Writes the ``clasher.k4s.end-evidence.v1`` document (kind ``counted-reporting``) for the frozen
               ``end_evidence.end_evidence``. Every artifact item is {path, sha256, commit, repository_path}: ``commit``
               is the single --commit X that holds every artifact, ``repository_path`` the fixed repo path of its
               role, ``path`` that path relative to the evidence file's directory (evidence location
               ``reports/explore/k4s-confirm/end-evidence.json``, OUTSIDE the strict ``end/`` namespace). Bytes and
               SHAs come from ``git show X:<repository_path>`` only (never the work tree). Refuses to overwrite.

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
               3. Every work-tree artifact path is confined: canonical repository root, every component opened
                  O_NOFOLLOW (no symlink anywhere), leaf regular with st_nlink == 1.
               Then the frozen end_evidence.end_evidence(), record bindings, membership, per counted host the frozen
               fleet_profile.slot_layout + fleet_end.host_reporting, and the reporting half of compare_mhz (every
               occupied physical core present, each finite > 0 MHz). On a clock-join refusal the outcome-blind clock
               diagnosis of that host is attached; the frozen refusal stands.

diagnose-clock Outcome-blind census/MHz join diagnosis (health fields utc/host/inflight/slots/MHz only): per
               host/phase the counts, duplicate/wrong-host census rows, unmatched census and MHz utc keys with line
               positions, slot mismatches, full-occupancy rows, and the first frozen host_reporting rule that would
               refuse. It never repairs, filters, re-times or zips rows. Exit 0 = every join clean, 3 = mismatch
               found (diagnosed), 2 = refusal.

Production vs test: the defaults are the records of run r1. Every override (record pins, hosts, membership,
evidence path, warm-up, --no-manifest-check) is TEST-ONLY: it requires --test-mode AND the environment
K4S_S2_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION, and a test-mode run can only write a TEST-ONLY result schema
(test_mode=true); a production result is never produced in test mode.

Offline limits: slot_layout is called with host = the counted host and nice = the plan's nice, so its live
host/priority gate is NOT exercised here (it runs on host, pre-claim). The profile is the S4 bundle's
reference_load_profile (--profile-json + --profile-json-sha256) or, explicitly acknowledged with
--declared-default-profile, the declared S4 profile (slot 0, 11 slots, console_rule false, warmup 300 s,
perception none).
"""
import argparse
import errno
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
import sys
import sysconfig
import time
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

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
FORBIDDEN_PARTS = frozenset(("games", "complete.json", "hub-blocks"))
HOST_NAME = re.compile(r"127x[0-9]{2}")
PHASE_NAME = re.compile(r"reporting|replacement-r[1-9][0-9]*")     # end_evidence.registered_phase
SAFE_PART = re.compile(r"[A-Za-z0-9._-]+")
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
NEW_FILE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
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


def git(repository, *args):
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True)
    require(result.returncode == 0, f"git {' '.join(args[:2])} failed: " + result.stderr.decode(errors="replace")[-300:])
    return result.stdout


def full_commit(repository, commit):
    require(isinstance(commit, str) and COMMIT.fullmatch(commit) is not None, "--commit must be a full 40-hex commit")
    resolved = git(repository, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    require(resolved == commit, "commit does not resolve to itself: " + commit)
    return commit


# ---------------------------------------------------------------- confined, no-follow local filesystem (05)

def repo_relative(rel, label):
    """A normalised repo-relative path: no absolute, no '..'/'.'/empty part, no forbidden or END-namespace part."""
    require(isinstance(rel, str) and rel and not rel.startswith("/"), f"{label}: not a repo-relative path: {rel!r}")
    parts = rel.split("/")
    require(all(SAFE_PART.fullmatch(p) and p not in (".", "..") for p in parts), f"{label}: unsafe path {rel!r}")
    require(not FORBIDDEN_PARTS.intersection(parts), f"{label}: forbidden (outcome/block) path {rel!r}")
    require(not (rel + "/").startswith(END_DIR + "/"), f"{label}: path inside the strict END namespace {rel!r}")
    return rel


def canonical_abs(path, label):
    text = os.path.abspath(str(path))
    require(text != "/" and "//" not in text and os.path.realpath(text) == text,
            f"{label} is not canonical (a component is a symlink/alias): {path}")
    require(not FORBIDDEN_PARTS.intersection(text.split("/")), f"{label}: forbidden (outcome/block) path {text}")
    return text


def open_dir(path, label, create_leaf=False):
    fd = os.open("/", DIR_FLAGS)
    try:
        parts = canonical_abs(path, label).split("/")[1:]
        for i, part in enumerate(parts):
            if create_leaf and i == len(parts) - 1:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                raise S2Error(f"{label}: component {part!r} of {path} is a symlink/alias, missing or not a directory "
                              f"({errno.errorcode.get(error.errno, error.errno)})") from None
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_confined(root, rel, label):
    """Leaf descriptor of root/rel: every component O_NOFOLLOW, regular file, st_nlink == 1. Nothing is read."""
    parts = rel.split("/")
    fd = open_dir(root, label + " root")
    try:
        for i, part in enumerate(parts):
            leaf = i == len(parts) - 1
            try:
                nxt = os.open(part, LEAF_FLAGS if leaf else DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                raise S2Error(f"{label}: component {part!r} of {rel} is a symlink/alias, missing or not a directory "
                              f"({errno.errorcode.get(error.errno, error.errno)})") from None
            os.close(fd)
            fd = nxt
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode), f"{label}: {rel} is not a regular file")
        require(st.st_nlink == 1, f"{label}: {rel} is a hard-link alias (st_nlink={st.st_nlink})")
        return fd
    except BaseException:
        os.close(fd)
        raise


def confined_size(root, rel, label):
    fd = open_confined(root, rel, label)
    try:
        return os.fstat(fd).st_size
    finally:
        os.close(fd)


def read_confined(root, rel, label):
    fd = open_confined(root, rel, label)
    try:
        size, chunks = os.fstat(fd).st_size, []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        require(len(data) == size == os.fstat(fd).st_size, f"{label}: {rel} changed while read")
        return data
    finally:
        os.close(fd)


def read_input(path, label):
    """An explicit operator input file (S1 manifest, profiles): canonical, regular, no-follow, outside outcomes."""
    text = canonical_abs(path, label)
    parent, name = text.rsplit("/", 1)
    return read_confined(parent, name, label)


def write_new(path, data, label):
    """Exclusive, no-follow creation under a canonical existing parent; never overwrites."""
    text = os.path.abspath(str(path))
    require(not os.path.lexists(text), f"{label} exists, refusing to overwrite: {text}")
    parent, name = canonical_abs(text, label).rsplit("/", 1)
    fd_dir = open_dir(parent, label + " parent")
    try:
        try:
            fd = os.open(name, NEW_FILE_FLAGS, 0o644, dir_fd=fd_dir)
        except FileExistsError:
            raise S2Error(f"{label} exists, refusing to overwrite: {text}") from None
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(fd_dir)
    return text


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


def pinned_completion(repository, commit, mode):
    data = git(repository, "show", f"{commit}:{COMPLETION}")
    require(sha_bytes(data) == mode.pins["completion"], "completion SHA != pinned completion")
    return json.loads(data), data


def load_s1(path, digest, mode, pairs):
    """The verified S1 receipt: pinned SHA, production schema (TEST schema only in test mode), exact 20+20 rows."""
    require(path is not None and SHA.fullmatch(digest or ""), "--s1-manifest and --s1-manifest-sha256 are required")
    raw = read_input(path, "S1 manifest")
    require(sha_bytes(raw) == digest, "S1 manifest SHA != --s1-manifest-sha256")
    doc = json.loads(raw)
    schemas = (S1_SCHEMA, S1_TEST_SCHEMA) if mode.testing else (S1_SCHEMA,)
    require(doc.get("schema") in schemas and doc.get("status") == "copied"
            and doc.get("test_mode", False) is (doc.get("schema") == S1_TEST_SCHEMA),
            f"S1 manifest schema/status not acceptable here: {doc.get('schema')}/{doc.get('status')}")
    files = {(f["host"], f["phase"], f["name"]): f for f in doc["files"]}
    meta = {(m["host"], m["phase"], m["name"]): m for m in doc["meta"]}
    want_files = {(h, p, n) for h, p in pairs for n in ("mhz.jsonl", "census.jsonl")}
    want_meta = {(h, p, n) for h, p in pairs for n in ("launch.json", "supervisor-exit.json")}
    require(set(files) == want_files and len(doc["files"]) == len(want_files), "S1 manifest files differ from the phases")
    require(set(meta) == want_meta and len(doc["meta"]) == len(want_meta), "S1 manifest meta differ from the phases")
    for f in files.values():
        require(f["local_sha256"] == f["remote_sha256_before"] == f["remote_sha256_after"]
                and f["local_size"] == f["remote_size"] > 0, "S1 manifest row is not a verified copy: " + f["local_path"])
    for m in meta.values():
        require(m["remote_sha256"] == m["committed_sha256"], "S1 manifest meta row differs from committed bytes")
    return dict(files=files, meta=meta, sha256=digest, schema=doc["schema"])


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

def build(a):
    mode = Mode(a)
    repository = Path(canonical_abs(a.repository, "--repository"))
    commit = full_commit(repository, a.commit)
    location = evidence_location(mode.location)
    edir = location.parent
    completion, _ = pinned_completion(repository, commit, mode)
    pairs = counted_phases(completion, mode)
    roles = role_paths(pairs)
    s1 = load_s1(a.s1_manifest, a.s1_manifest_sha256, mode, pairs) if (a.s1_manifest or not mode.testing) else None
    out_text = os.path.abspath(a.out)
    require(not os.path.lexists(out_text), "refusing to overwrite " + out_text)
    canonical_abs(out_text, "--out")

    def item(rel, expected=None, label=""):
        data = git(repository, "show", f"{commit}:{rel}")
        digest = sha_bytes(data)
        require(expected is None or digest == expected, f"{label} SHA {digest} != pinned {expected}: {rel}")
        require(len(data) > 0, "empty artifact: " + rel)
        return dict(path=PurePosixPath(rel).relative_to(edir).as_posix(), sha256=digest, commit=commit,
                    repository_path=rel), data

    doc = dict(schema=EVIDENCE_SCHEMA, kind="counted-reporting")
    for key, rel in RECORDS:
        doc[key], data = item(rel, mode.pins[key], key)
        if key == "plan":
            require(json.loads(data).get("study") == "PREREG-K4S", "plan is not the PREREG-K4S plan")
    require(completion.get("counted_inventory_sha256") == doc["counted_inventory"]["sha256"]
            and completion.get("blind_ledger_sha256") == doc["blind_ledger"]["sha256"],
            "completion does not bind the pinned inventory/ledger")
    phases = []
    for host, phase in pairs:
        entry = dict(host=host, phase=phase)
        for field, _, _ in PHASE_FILES:
            rel = roles[(host, phase, field)]
            entry[field], data = item(rel, None, f"{host}/{phase} {field}")
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
    written = write_new(out_text, data, "--out")
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


def verify_pin_set(root, files, label, read):
    require(isinstance(files, dict) and files, "Empty pin set: " + label)
    for name, expected in sorted(files.items()):
        repo_relative(name, label)
        require(isinstance(expected, str) and SHA.fullmatch(expected), f"Unfilled pin ({label}): {name}")
        require(sha_bytes(read(name)) == expected, f"Pin mismatch ({label}): {name}")


def bootstrap(code_root, mode):
    """Stdlib only, BEFORE any frozen import: the manifest bytes == the approved SHA; every pinned file verified
    (k4s_logic.load_k4s_manifest semantics, require_frozen); the served modules keep their verified bytes."""
    root = canonical_abs(code_root, "--code-root")
    for name in list(SERVED) + ["end_pool", "fleet_validity"]:
        require(name not in sys.modules, "frozen module already imported: " + name)
    cache = {}

    def read(rel):
        if rel not in cache:
            cache[rel] = read_confined(root, rel, "frozen code")
        return cache[rel]
    if not mode.verify_code:                                   # TEST-ONLY: unverified bytes, recorded as such
        return {name: (root + "/" + rel, read(rel), None) for name, (_, rel) in SERVED.items()}, None
    raw = read(K4S_MANIFEST)
    require(sha_bytes(raw) == APPROVED_K4S_MANIFEST_SHA256, "K4S manifest SHA != approved 74314eda")
    manifest = json.loads(raw)
    require(manifest.get("schema") == "clasher.k4s.mac-manifest.v1", "Unsupported K4S manifest schema")
    for section, label in (("k4s_files", "K4S Mac files"), ("end_files", "K4S END producer/pooler files"),
                           ("reused_readonly", "reused read-only TIERS files")):
        verify_pin_set(root, manifest[section], label, read)
    tiers = manifest["measure_tiers_unmodified"]
    require(manifest["reused_readonly"].get(tiers["path"]) == tiers["sha256"],
            "measure_tiers.py statement disagrees with its read-only pin")
    require(manifest["native"]["provenance_linux_sha256"] == NATIVE_PROVENANCE_SHA, "Native provenance SHA changed")
    require(manifest.get("frozen") is True, "K4S manifest is not frozen")
    require(SHA.fullmatch(str(manifest["sd1_manifest"].get("sha256"))), "SD1 manifest SHA is not filled")
    kernel = manifest["k4s_kernel"]
    require(kernel.get("files") and all(SHA.fullmatch(str(v)) for v in kernel["files"].values()),
            "K4S kernel pins are not filled")
    verify_pin_set(root, kernel["files"], "K4S kernel", read)
    served = {}
    for name, (section, rel) in SERVED.items():
        pin = manifest[section].get(rel)
        require(pin is not None and sha_bytes(read(rel)) == pin, f"served module {name} is not pinned: {rel}")
        served[name] = (root + "/" + rel, read(rel), pin)
    verified = dict(manifest_sha256=APPROVED_K4S_MANIFEST_SHA256,
                    files_verified=len(cache), served={n: v[2] for n, v in served.items()})
    return served, verified


def frozen_modules(code_root, mode):
    served, verified = bootstrap(code_root, mode)
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


def validate(a, context):
    started = utc()
    mode = Mode(a)
    context["test_mode"] = mode.testing
    repository = canonical_abs(a.repository, "--repository")
    code_root = canonical_abs(a.code_root or repository, "--code-root")
    if not mode.testing:
        require(a.profile_json is not None or a.declared_default_profile,
                "production validation needs --profile-json/--profile-json-sha256 (S4) or --declared-default-profile")
    commit = full_commit(repository, a.commit)
    git(repository, "merge-base", "--is-ancestor", commit, "HEAD")
    location = evidence_location(mode.location)
    edir = location.parent
    # 1. stdlib-only bootstrap of the frozen code (nothing frozen is imported yet)
    served, verified = None, None
    modules, served, verified, finder = frozen_modules(code_root, mode)
    E, fleet_end, fleet_profile = modules["end_evidence"], modules["fleet_end"], modules["fleet_profile"]
    # 2. evidence, exact roles, pins, S1 receipt: before any artifact read
    raw = read_confined(repository, location.as_posix(), "evidence")
    require(SHA.fullmatch(a.evidence_sha256 or "") and sha_bytes(raw) == a.evidence_sha256, "evidence SHA mismatch")
    doc = json.loads(raw)
    require(isinstance(doc, dict) and set(doc) == TOP_FIELDS, "evidence top-level keys differ from the S2 layout")
    require(isinstance(doc["completion"], dict) and doc["completion"].get("repository_path") == COMPLETION
            and doc["completion"].get("sha256") == mode.pins["completion"] and doc["completion"].get("commit") == commit,
            "evidence completion item differs from the completion of record")
    completion, _ = pinned_completion(repository, commit, mode)
    pairs = counted_phases(completion, mode)
    roles = role_paths(pairs)
    items = structure(doc, commit, edir, roles, pairs)
    for key, _ in RECORDS:
        require(doc[key]["sha256"] == mode.pins[key], f"evidence {key} SHA != the pinned record")
    require(completion.get("counted_inventory_sha256") == doc["counted_inventory"]["sha256"]
            and completion.get("blind_ledger_sha256") == doc["blind_ledger"]["sha256"],
            "completion does not bind the evidence inventory/ledger")
    s1 = load_s1(a.s1_manifest, a.s1_manifest_sha256, mode, pairs) if (a.s1_manifest or not mode.testing) else None
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
    # 3. work-tree confinement of every artifact (no symlink/alias anywhere), before the frozen reader opens it
    for key, item, rel in items:
        require(confined_size(repository, rel, f"artifact {key}") > 0, f"empty artifact {rel}")
    profiles, profile_source, profile_sha = {}, "declared-default", None
    if a.profile_json:
        require(SHA.fullmatch(a.profile_json_sha256 or ""), "--profile-json requires --profile-json-sha256")
        profile_raw = read_input(a.profile_json, "profile JSON")
        require(sha_bytes(profile_raw) == a.profile_json_sha256, "profile JSON SHA mismatch")
        profiles, profile_source, profile_sha = json.loads(profile_raw), "s4-bundles", a.profile_json_sha256
        require(isinstance(profiles, dict) and sorted(profiles) == mode.hosts, "profile JSON must hold every counted host")
    # 4. the frozen reader and checks
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
        profile = profiles.get(host) or dict(host=host, reference_slot=0, slot_count=11, console_rule=False,
                                             warmup_seconds=mode.warmup, perception="none")
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
    closure_audit(served, finder)
    return dict(schema=TEST_RESULT_SCHEMA if mode.testing else RESULT_SCHEMA, test_mode=mode.testing, ok=True,
                started_utc=started, finished_utc=utc(), evidence=str(Path(repository) / location),
                evidence_sha256=a.evidence_sha256, commit=commit,
                repository_head=git(repository, "rev-parse", "HEAD").decode().strip(), code_root=code_root,
                frozen_manifest_verified=verified is not None, frozen_bootstrap=verified,
                frozen_module_sha256={n: sha_bytes(v[1]) for n, v in served.items()},
                python=sys.version.split()[0], executable=sys.executable, optimize=sys.flags.optimize,
                kind=ev["kind"], counted_hosts=ev["counted_hosts"], membership=membership,
                plan_sha256=ev["plan_sha256"], completion_sha256=ev["completion_sha256"], hosts=hosts,
                profile_source=profile_source, profile_json_sha256=profile_sha,
                slot_layout_offline_note="host/nice supplied offline (plan nice); live gate runs on host pre-claim",
                s1_manifest_sha256=s1["sha256"] if s1 else None)


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


def diagnose(a):
    """Reads ONLY end-sources census.jsonl/mhz.jsonl (+ the pinned completion in repository mode)."""
    mode = Mode(a)
    sources, origin = {}, {}
    if a.s1_dest:
        require(a.repository is None, "give either --s1-dest or --repository/--commit")
        dest = canonical_abs(a.s1_dest, "--s1-dest")
        manifest_pairs = None
        raw = read_input(a.s1_manifest, "S1 manifest") if a.s1_manifest else None
        require(raw is not None and sha_bytes(raw) == (a.s1_manifest_sha256 or ""),
                "--s1-dest needs --s1-manifest with a matching --s1-manifest-sha256")
        files = json.loads(raw)["files"]
        manifest_pairs = sorted({(f["host"], f["phase"]) for f in files})
        if not mode.testing:
            require(manifest_pairs == sorted((h, p) for h, ps in PRODUCTION_PHASES.items() for p in ps),
                    "S1 manifest phases differ from the 10 pairs of record")
        s1 = load_s1(a.s1_manifest, a.s1_manifest_sha256, mode, manifest_pairs)
        for (host, phase, name), row in s1["files"].items():
            require(HOST_NAME.fullmatch(host) and PHASE_NAME.fullmatch(phase), "unsafe S1 host/phase")
            data = read_confined(dest, f"{host}/{phase}/{name}", "S1 copy")
            require(sha_bytes(data) == row["local_sha256"], f"S1 copy differs from its manifest: {host}/{phase}/{name}")
            sources[(host, phase, name)] = data
        pairs = manifest_pairs
        origin = dict(source="s1-dest", s1_dest=dest, s1_manifest_sha256=a.s1_manifest_sha256)
    else:
        require(a.repository is not None and a.commit is not None, "give --s1-dest or --repository and --commit")
        repository = canonical_abs(a.repository, "--repository")
        commit = full_commit(repository, a.commit)
        completion, _ = pinned_completion(repository, commit, mode)
        pairs = counted_phases(completion, mode)
        for host, phase in pairs:
            for name in ("mhz.jsonl", "census.jsonl"):
                rel = repo_relative(SOURCES.format(host=host, phase=phase, name=name), "source")
                sources[(host, phase, name)] = git(repository, "show", f"{commit}:{rel}")
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repository", required=True)
    b.add_argument("--commit", required=True, help="the one commit containing every artifact")
    b.add_argument("--out", required=True, help="evidence file to write (exclusive, no-follow)")
    b.add_argument("--s1-manifest", help="S1 s1-copy-manifest.json (required in production)")
    b.add_argument("--s1-manifest-sha256")
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
    add_test_options(v, validate_options=True)
    d = sub.add_parser("diagnose-clock")
    d.add_argument("--repository")
    d.add_argument("--commit")
    d.add_argument("--s1-dest", help="S1 destination tree (before the end-sources commit)")
    d.add_argument("--s1-manifest")
    d.add_argument("--s1-manifest-sha256")
    d.add_argument("--result", required=True)
    add_test_options(d)
    a = ap.parse_args(argv)
    if a.command == "build":
        try:
            build(a)
        except Exception as error:                        # fail closed
            print(f"S2 BUILD REFUSED: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        return 0
    result_path = os.path.abspath(a.result)
    if os.path.lexists(result_path):
        print("S2 REFUSED: result exists: " + result_path, file=sys.stderr)
        return 2
    context, code = {}, 2
    try:
        if a.command == "validate":
            result = validate(a, context)
            code = 0
        else:
            result = diagnose(a)
            code = 0 if result["clean"] else 3
    except Exception as error:                            # fail closed: frozen EvidenceError/ValueError included
        testing = bool(context.get("test_mode", getattr(a, "test_mode", False)))
        base = (TEST_DIAGNOSIS_SCHEMA if testing else DIAGNOSIS_SCHEMA) if a.command == "diagnose-clock" else \
            (TEST_RESULT_SCHEMA if testing else RESULT_SCHEMA)
        result = dict(schema=base, test_mode=testing, ok=False, error_type=type(error).__name__, error=str(error),
                      utc=utc(), **({"clock_diagnosis": context["clock_diagnosis"]} if "clock_diagnosis" in context else {}))
        code = 2
    data = json.dumps(result, indent=1, sort_keys=True) + "\n"
    try:
        write_new(result_path, data.encode(), "--result")
    except Exception as error:
        print(f"S2 REFUSED: result not written: {error}", file=sys.stderr)
        return 2
    print(data, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
