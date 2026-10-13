#!/usr/bin/env python3
"""S9 (PREREG-K4S END, Q5 / D1 / D2 / E1-E5 / R6 / P2-2): 05-only END runtime builder. r2: safe_input adoption.
r3: END-FULL-F4 (the live full-clone verification is a mandatory precondition of locate / build / verify /
equivalence, and of S3 / S1b on the clone) and END-FULL-F1 (siblings through the canonical bootstrap).
r4 (integration audit B3/B5/U10): SD1-MANIFEST.json, the t1 corpora.json and DELTA-MANIFEST.json join the SHA-pinned
support members (SUPPORT_PINS; a D1 extension pending ratification); `refresh-clone` brings X into REPO_FULL.
r5 (Sol integration r1 finding 2): GIT_WRITE_GUARD, the git write confinement shared with the S11 host program:
before refresh-clone's fetch and --checkout, every path git may write and every ancestor is checked (no symlink, no
hard link, no stale lock, regular single-link leaves, real directories), with write-reducing config (GW_CONFIG).

CANDIDATE: needs Sol review before any use. No ssh, no host.

Source (ruling 21:28Z "full clone"): ONLY the runner-owned full clone REPO_FULL; never the shared partial checkout.
Every git call is si.git_run (scrubbed environment, no replace objects, no hooks, static refusal of alternates /
grafts / shallow / gitfile / config drivers; P2-4) except the one network clone in `prepare-clone`, which uses
si.run_checked with the same fixed environment and global flags plus protocol.https.allow (git_run disables every
network transport by design) and is then verified through safe_input before anything reads it.

Subcommands
  prepare-clone  Create REPO_FULL with a no-filter `git clone` from origin, then verify_clone() through safe_input
                 (below); --commit P present; check out P (detached).
  (every subcommand below first runs require_full_clone(): the LIVE verify_clone() of REPO_FULL, every time:
                 canonical real root/.git/objects, no hooks / shallow / grafts / alternates / http-alternates /
                 commondir / config.worktree, the exact plain clone config in a strict grammar (no promisor /
                 partial-clone filter / extensions / includes / drivers), only plain pack files (no .promisor),
                 git's own view non-bare / non-shallow at REPO_FULL, no replace refs, the given commits present)
  locate         The 33 runtime-pin-r2 names not in git at --commit, each read ONLY at its exact path under the one
                 explicit Q5 source root (Q5_SOURCE; exact-name role; descriptor gate before hashing). Exit 3 if any
                 is missing: STOP for a ruling, never substitute.
  build          R6: reports/explore/k4s-confirm/end/ must be ABSENT at P. D1: the export is the runtime member set
                 decided from tree METADATA only (si.git_plan phase 1: runtime-pin-r2 files U every *.py U the six
                 pinned files the frozen verifiers themselves read, SUPPORT_MEMBERS); every tracked complete.json must
                 be an exact E4 path with its pinned blob OID (member or not); member names pass the family denylist
                 (E-listed exceptions only); non-members are never read. D2: E1 is exported as a regular file whose
                 bytes are the verified target blob. The 33 externals are copied byte-exact from Q5_SOURCE with their
                 pins (R7: exclusive plain copies, st_nlink 1). Then the confined walk + descriptor-gated rehash of the
                 whole tree, stdlib verification of the K4S closure (74314eda pins, measurement 42b8986d, import
                 closure) BEFORE the frozen cross-check runs in a P2-4-environment child (never -O).
  refresh-clone  r4 (U10): fetch refs/heads/k4s-end-r1 ONLY (fast-forward, no '+') into the existing verified REPO_FULL
                 with prepare-clone's hygiene (scrubbed env, no filter, fsck, https only, no auto-gc); the live
                 verify_clone() before and after (with X); proofs that every pre-existing .git/objects file is unchanged,
                 that no other ref moved and that the tip is exactly X; HEAD untouched unless --checkout.
                 r5: the git write guard (gw_check) before the fetch and before --checkout, gw_after after each.
  verify         Re-hash a built runtime against its manifest (pinned by --manifest-sha256).
  equivalence    P2-2 hard gate: X (END-JOB commit) is a strict descendant of P (the built runtime's commit), the
                 P..X diff is exactly reports/explore/k4s-confirm/end/END-JOB.json (names only; the blob is never
                 read), and the member plans at P and X are identical (path, mode, blob OID) and equal to the built
                 manifest's git members, so runtime_files and measurement_files are identical.
Exit codes: 0 ok; 2 refused; 3 missing pins (STOP); 1 unexpected error (still fail closed).
"""
import argparse
import json
import os
import re
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

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-runtime.v2"
LOCATE_SCHEMA = "clasher.k4s.end-runtime-locate.v2"
EQUIV_SCHEMA = "clasher.k4s.end-runtime-equivalence.v2"
CLONE_SCHEMA = "clasher.k4s.end-runtime-full-clone.v1"
REFRESH_SCHEMA = "clasher.k4s.end-runtime-refresh-clone.v1"
END_BRANCH = "k4s-end-r1"                                           # BR-1 (COORDINATOR 7f93dbbf): the END line
END_BRANCH_REF = "refs/remotes/origin/" + END_BRANCH
REPO_FULL = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full"   # ruling 21:28Z
ORIGIN_URL = "https://github.com/samdickson22/clash-simulator.git"
CLONE_PROTOCOL = "https"
BASE_COMMIT = "133f3ae4f414c9b8a3715eb8f44832fc96a6e5db"          # Q5: the END runtime commit is at or after this
RUNTIME_PIN_REL = "reports/explore/s1/receipts/runtime-pin-r2.json"
RUNTIME_PIN_SHA = "f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d"
QUALIFIED_REL = "reports/explore/s1/receipts/qualified-source-binding.json"
QUALIFIED_SHA = "56b67dd430636c90462156f3790f3a03df40410a77ffbd3d2d4c0b11acc0dce6"
K4S_MANIFEST_REL = "reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json"
K4S_MANIFEST_SHA = si.APPROVED_K4S_MANIFEST_SHA256                # 74314eda
K4S_MAC_REL = "reports/explore/k4s-confirm/mac"
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
END_JOB_REL = si.STRICT_END_DIR + "/END-JOB.json"
# The six tracked files outside (runtime-pin-r2 U *.py) that the frozen verifiers read from the runtime itself:
# prepare_bundle.runtime_pins reads the pin list and the qualified binding; k4s_logic.load_k4s_manifest reads the
# manifest and verifies K4S-MAC-PROCEDURE.md and spec-pins.json (reused_readonly); the 42b8986d measurement inventory
# (prepare_bundle.py:117 rule) includes build_tiers.sh and spec-pins.json. Each is pinned (f81f3655 / 56b67dd4 /
# 74314eda / the manifest / the measurement inventory); none is in runtime_files.
# r4 (integration audit B3/B5; a D1 EXTENSION that needs coordinator ratification): three more tracked, non-runtime_files
# files the frozen END identity check and S5 read from the runtime itself, each SHA-pinned here and re-hashed after the
# export (verify_closure, verify). SD1: K4S-MAC-MANIFEST.json (74314eda) sd1_manifest.{path,sha256}; S5 FROZEN_CLOSURE
# (k4s_end_preflight.py:96); the frozen END default --sd1-manifest HERE/SD1-MANIFEST.json (end_reference.py:426).
# Corpus inventory: K4S manifest references.t1_corpus_inventory.{path,sha256} and corpus.inventory; S5/S7
# CORPUS_INVENTORY_REL/_SHA256 (k4s_end_preflight.py:78,83; k4s_end_launch_gate.py:89,92). DELTA: read by the frozen
# end_reference.k4s_pins as HERE/DELTA-MANIFEST.json (end_reference.py:128); its SHA is the tracked blob at P' (98566c03)
# and the freeze record's F-5 row (reports/explore/k4s-confirm/FREEZE-RECORD-SKELETON.md:25). All three are .json
# outside e4v3 and outside runtime-pin-r2, so runtime_files (pin names U *.py) and measurement_files (e4v3 direct
# children *.py/*.sh/spec-pins.json) are unchanged by construction.
SD1_REL = "reports/explore/k4s-confirm/SD1-MANIFEST.json"
CORPORA_REL = "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json"
DELTA_REL = "reports/explore/k4s-confirm/DELTA-MANIFEST.json"
SUPPORT_PINS = {SD1_REL: "b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76",
                CORPORA_REL: "3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13",
                DELTA_REL: "34eca2b74c0345649d350c9cc33bf5b557a4ed3cf533a72fbaf85a2f0a690056"}
SUPPORT_MEMBERS = frozenset((RUNTIME_PIN_REL, QUALIFIED_REL, K4S_MANIFEST_REL, K4S_MAC_REL + "/K4S-MAC-PROCEDURE.md",
                             E4V3_REL + "/spec-pins.json", E4V3_REL + "/build_tiers.sh") + tuple(sorted(SUPPORT_PINS)))
IMPORT_CLOSURE = (E4V3_REL + "/prepare_bundle.py", E4V3_REL + "/tier_backend.py", E4V3_REL + "/receipts.py",
                  K4S_MAC_REL + "/k4s_logic.py")
MEASUREMENT_SHA = "42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25"
EXTERNAL = frozenset("""
imitation/__init__.py
imitation/evaluation/legacy_audit.py
imitation/evaluation/runtime_dependencies/derived_d1.py
imitation/evaluation/runtime_dependencies/own_cycle.py
imitation/evaluation/runtime_dependencies/sidecar_observer.py
imitation/evaluation/seed_compat.py
reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json
reports/strategy_council_20260928/m0/data/roles_v2/training.json
reports/strategy_council_20260928/search-noise-s6/runtime/support/human_deck_catalog.json
reports/strategy_council_20260928/search-noise-s6/runtime/support/selection.json
src/clasher/analysis/loss_review/delay_fixes.py
src/clasher/analysis/loss_review/delay_runtime.py
src/clasher/analysis/loss_review/delay_simulate.py
src/clasher/analysis/loss_review/scheduling.py
src/clasher/analysis/loss_review/search_ab.py
src/clasher/analysis/loss_review/tempo.py
src/clasher/analysis/loss_review/throughput_guard.py
student-source/exit_r3/__init__.py
student-source/exit_r3/network.py
student-source/exit_r3/rows.py
student-source/exit_r3/student.py
student-source/exit_r3/teacher_batch.py
student-source/exit_r3/test_r3.py
student-source/exit_r3/test_round2.py
student-source/exit_r3/train.py
tests/analysis/test_delay_fixes.py
tests/analysis/test_delay_fixes_summary.py
tests/analysis/test_search_ab.py
tests/analysis/test_search_ab_guard.py
tests/analysis/test_tempo.py
tests/analysis/test_tempo_launch.py
tests/analysis/test_throughput_guard.py
tests/test_l1_v4.py
""".split())
# Q5 provenance, explicit (S9-F2): the one 05 tree that holds all 33 at <root>/<name> (r1 locate: 33/33 there).
Q5_SOURCE = "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-CANDIDATE-0775b704-0108-r1/runtime"
DEFAULT_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
MAX_MEMBER_BYTES = 256 << 20
MAX_EXTERNAL_BYTES = 64 << 20
MANIFEST = "runtime-manifest.json"
COMMIT = re.compile(r"[0-9a-f]{40}")
CLONE_CONFIG_KEYS = ("branch.main.merge", "branch.main.remote", "core.bare", "core.filemode", "core.logallrefupdates",
                     "core.repositoryformatversion", "remote.origin.fetch", "remote.origin.url")
# F4 (r3): names under the full clone that must be ABSENT in any form, every time the clone is used: hooks, the static
# object/history indirections (shallow, grafts, alternates), a linked-worktree commondir and a per-worktree config.
CLONE_ABSENT = (".git/hooks", ".git/shallow", ".git/info/grafts", ".git/objects/info/alternates",
                ".git/objects/info/http-alternates", ".git/commondir", ".git/config.worktree")
# Pack directory entries a plain no-filter clone/fetch writes; anything else (a .promisor marker, a tmp_pack_*) refuses.
CLONE_PACK_NAME = re.compile(r"pack-[0-9a-f]{40}(?:[0-9a-f]{24})?\.(?:pack|idx|keep|bitmap|rev)")
# Strict git-config grammar for the plain clone config: `[section]` or `[section "sub"]` alone on its line, and
# `key = value` lines whose value has no quote, backslash or comment character (git would reinterpret those).
CONFIG_SECTION = re.compile(r'\[([A-Za-z][A-Za-z0-9-]*)(?: "([^"\\]*)")?\]')
CONFIG_ENTRY = re.compile(r'([A-Za-z][A-Za-z0-9-]*)[ \t]*=[ \t]*([^"\\;#]*)')


class Missing(si.Refusal):
    """At least one of the 33 pins was not found on 05 by SHA: STOP for a ruling, never substitute."""

    def __init__(self, reason):
        si.Refusal.__init__(self, "missing-pins", reason)


def full_commit(value, label):
    require(isinstance(value, str) and COMMIT.fullmatch(value) is not None, "policy",
            "%s must be a full 40-hex commit: %r" % (label, value))
    return value


def repo():
    return si.GitRepo(work_tree=REPO_FULL)


def repo_role():
    return si.Role("repo", REPO_FULL, "read", MAX_MEMBER_BYTES, patterns=("**",), exemptions=("E1", "E4", "E5"))


def is_commit(g, commit):
    kind = si.git_run(g, ["cat-file", "-t", full_commit(commit, "commit")], timeout=60, stdout_limit=64).stdout
    require(kind == b"commit\n", "git", "%s is not a commit in the full clone" % commit[:12])


def is_ancestor(g, older, newer):
    return si.git_run(g, ["merge-base", "--is-ancestor", older, newer], timeout=120, ok_rcs=(0, 1)).rc == 0


def commit_pins(policy, commit, build=False):
    """Pinned bytes at the commit (runtime-pin-r2 f81f3655, qualified binding 56b67dd4, K4S manifest 74314eda) through
    si.git_show_file; the 33 external names from tree metadata; R6 (build only): the strict END dir is absent."""
    g = repo()
    is_commit(g, commit)
    require(is_ancestor(g, BASE_COMMIT, commit), "check", "commit is not at or after 133f3ae4 (Q5): " + commit)
    raw = si.git_show_file(policy, "repo", g, commit, RUNTIME_PIN_REL, 64 << 20, expected_sha256=RUNTIME_PIN_SHA)
    qualified = si.loads_strict(si.git_show_file(policy, "repo", g, commit, QUALIFIED_REL, 16 << 20,
                                                 expected_sha256=QUALIFIED_SHA), QUALIFIED_REL)
    k4s = si.loads_strict(si.git_show_file(policy, "repo", g, commit, K4S_MANIFEST_REL, 4 << 20,
                                           expected_sha256=K4S_MANIFEST_SHA), K4S_MANIFEST_REL)
    pins = si.loads_strict(raw, RUNTIME_PIN_REL).get("files")
    require(isinstance(pins, dict) and all(C.is_sha256(v) for v in pins.values()), "check", "malformed runtime pin")
    for name in pins:
        si.check_rel(name)
    entries = si.git_ls_tree(g, commit)                                # metadata only
    tracked = {e["path"] for e in entries}
    if build:                                                          # R6 (17:23Z): build at the evidence commit
        inside = sorted(p for p in tracked if p == si.STRICT_END_DIR or p.startswith(si.STRICT_END_DIR + "/"))
        require(not inside, "check", "R6: %s/ exists at the build commit (%s ...); build at the evidence commit P"
                % (si.STRICT_END_DIR, inside[0] if inside else ""))
    external = {name for name in pins if name not in tracked}
    require(external == EXTERNAL, "check", "the non-git runtime-pin names at this commit differ from the 33 of "
            "record: %r" % sorted(external ^ EXTERNAL)[:6])
    missing = sorted(SUPPORT_MEMBERS - tracked)
    require(not missing, "check", "support members not tracked: %r" % missing)
    return pins, qualified, k4s


def member_predicate(pins):
    names = frozenset(pins) | SUPPORT_MEMBERS

    def member(entry):
        return entry["path"] in names or entry["path"].endswith(".py")
    return member


def member_plan(policy, commit, pins):
    """D1 phase 1: tree metadata screened to completion; no object content read."""
    return si.git_plan(policy, "repo", repo(), commit, members=member_predicate(pins))


def git_members(plan):
    rows = [dict(path=e["path"], mode=e["mode"], oid=e["oid"]) for e in plan.files + plan.e4 + plan.e5]
    if plan.e1 is not None:
        rows.append(dict(path=plan.e1["path"], mode=plan.e1["mode"], oid=plan.e1["oid"]))
    return sorted(rows, key=lambda r: r["path"])


# ---------------------------------------------------------------- prepare-clone

def clone_role(path=None):
    """Read role over the full clone's git metadata: its config, the names that must be absent, the pack directory."""
    return si.Role("clone", path or REPO_FULL, "read", 16 << 30, exact=(".git/config",) + CLONE_ABSENT,
                   patterns=(".git/objects/pack/*",))


def clone_policy():
    parent, leaf = REPO_FULL.rsplit("/", 1)
    return si.Policy(C.local_host(), [
        si.Role("clone-parent", parent, "write", 1 << 20, exact=(leaf, leaf + "-PREPARE.json")),
        si.Role("clone-parent-read", parent, "read", 1 << 20, exact=(leaf + "-PREPARE.json",)),
        clone_role(), repo_role(), C.code_role()])


def check_clone_config(policy, origin=None):
    """The clone config must be exactly the plain `git clone` config (CLONE_CONFIG_KEYS, each once) in the strict
    grammar above: any other key (remote.*.promisor, remote.*.partialclonefilter, core.partialclonefilter,
    extensions.*, include*, drivers, ...), a variable after a section header, a quoted/escaped/commented value,
    old-style `[a.b]` sections or non-UTF-8 bytes refuse."""
    raw = si.read_bytes(policy, "clone", ".git/config", max_size=64 << 10)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        si.refuse("indirection", "full clone config is not UTF-8")
    keys, section, values = [], None, {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        head = CONFIG_SECTION.fullmatch(line)
        if head is not None:
            section = head.group(1).casefold() + ("." + head.group(2) if head.group(2) is not None else "")
            continue
        entry = CONFIG_ENTRY.fullmatch(line)
        require(entry is not None and section is not None, "indirection",
                "full clone config line %d is outside the plain clone grammar: %r" % (number, line[:80]))
        full = "%s.%s" % (section, entry.group(1).casefold())
        keys.append(full)
        values[full] = entry.group(2).strip()
    require(sorted(keys) == sorted(CLONE_CONFIG_KEYS), "indirection",
            "full clone config is not the plain clone config (promisor/partial/extension/driver keys refuse): %r"
            % sorted(set(keys) ^ set(CLONE_CONFIG_KEYS) or keys))
    require(values.get("remote.origin.url") == (origin or ORIGIN_URL)
            and values.get("core.repositoryformatversion") == "0" and values.get("core.bare") == "false",
            "indirection", "full clone origin/format/bare differ")
    return keys


def verify_clone(policy, commits=(), path=None):
    """F4 (r3): the LIVE full-clone verification (ruling 21:28Z), through safe_input, every time: the clone root, .git
    and .git/objects are canonical real directories (no gitfile, no symlink); none of CLONE_ABSENT exists; the config
    is the plain clone config (no promisor / partial-clone filter / extensions / includes / drivers); the pack
    directory holds only plain pack files (no .promisor); git itself reports the expected git dir and work tree, not
    bare, not shallow; no replace refs; every given commit is present. Each git_run re-runs the static preflight."""
    path = path or REPO_FULL
    g = si.GitRepo(work_tree=path)
    identity = si.check_dir(policy, "clone")
    for rel in (".git", ".git/objects", ".git/objects/pack"):
        si.check_dir(policy, "clone", rel)
    for rel in CLONE_ABSENT:
        try:
            si.check_absent(policy, "clone", rel)
        except si.Refusal as error:
            if error.code != "missing":                               # a missing parent directory: absent too
                si.refuse("indirection", "full clone has %s (%s)" % (rel, error.reason))
    keys = check_clone_config(policy)
    packs = si.walk_tree(policy, "clone", ".git/objects/pack")
    names = sorted(f["rel"].rsplit("/", 1)[1] for f in packs["files"])
    require(not [n for n in names if n.endswith(".promisor")], "indirection", "promisor pack in the full clone")
    require(all(CLONE_PACK_NAME.fullmatch(n) for n in names), "indirection",
            "unexpected pack directory entries in the full clone: %r" % [n for n in names
                                                                        if not CLONE_PACK_NAME.fullmatch(n)][:4])
    facts = si.git_run(g, ["rev-parse", "--absolute-git-dir", "--is-bare-repository", "--is-shallow-repository",
                           "--show-toplevel"], timeout=60, stdout_limit=1 << 16).stdout
    require(facts == ("%s/.git\nfalse\nfalse\n%s\n" % (path, path)).encode(), "indirection",
            "the full clone is not the expected non-bare, non-shallow repository at %s: %r" % (path, facts[:200]))
    replace = si.git_run(g, ["for-each-ref", "refs/replace"], timeout=60).stdout
    require(replace == b"", "indirection", "the full clone has replace refs")
    for commit in commits:
        is_commit(g, commit)
    return dict(repository=path, root_dev=identity["dev"], root_ino=identity["ino"], config_keys=sorted(keys),
                packs=names, absent=list(CLONE_ABSENT), shallow=False, bare=False, replace_refs=0,
                commits=list(commits))


def require_full_clone(commits=(), path=None):
    """F4 (r3): the MANDATORY precondition of every entrypoint that reads the dedicated clone (S9 locate / build /
    verify / equivalence, S3 build / verify, S1b on REPO_FULL). It builds its own read-only policy and runs the live
    verify_clone() every time: nothing is inferred from the directory name or from the prepare-clone receipt."""
    path = path or REPO_FULL
    policy = si.Policy(C.local_host(), [clone_role(path)])
    return verify_clone(policy, tuple(full_commit(c, "commit") for c in commits), path)


def prepare_clone(a, log=print):
    commit = full_commit(a.commit, "--commit")
    policy = clone_policy()
    leaf = REPO_FULL.rsplit("/", 1)[1]
    si.check_absent(policy, "clone-parent", leaf)
    with C.ScrubbedEnv() as env:
        argv = [si.GIT_BINARY, "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                "-c", "protocol.allow=never", "-c", "protocol.%s.allow=always" % CLONE_PROTOCOL,
                "-c", "transfer.fsckObjects=true", "clone", "-q", "--no-checkout", "--template=", "--",
                ORIGIN_URL, REPO_FULL]
        si.run_checked(argv, 7200, 1 << 20, env=env, cwd=REPO_FULL.rsplit("/", 1)[0])
    facts = verify_clone(policy, (commit,))
    si.git_run(repo(), ["checkout", "-q", "--detach", commit], timeout=3600)
    head = si.git_run(repo(), ["rev-parse", "HEAD"], timeout=60).stdout.decode().strip()
    require(head == commit, "check", "checkout HEAD %s is not %s" % (head, commit))
    status = si.git_run(repo(), ["status", "--porcelain", "--untracked-files=no"], timeout=3600).stdout
    require(status == b"", "check", "the full clone work tree is not clean at P")
    facts = dict(facts, schema=CLONE_SCHEMA, utc=C.utc(), repository=REPO_FULL, origin=ORIGIN_URL, commit=commit,
                 head=head, safe_input_sha256=C.SAFE_INPUT_SHA256,
                 script_sha256=C.code_sha(policy, "s9_end_runtime.py"))
    with si.Writer(policy, "clone-parent") as writer:
        writer.write_json_once(leaf + "-PREPARE.json", facts)
    log("S9 prepare-clone OK: %s at %s (receipt %s-PREPARE.json)" % (REPO_FULL, commit, REPO_FULL))
    return facts


# ---------------------------------------------------------------- r5 (Sol integration r1 finding 2): git write confinement

# The git write guard: Python 3.8 stdlib source, executed here (S9 refresh-clone) AND composed verbatim into the S11
# host program (s11_host_repository.host_program), so both mutation paths run the same checks. Contract: BEFORE any
# git command that writes, every path git may write during it (GW write-set table, README r5) and every ancestor of
# each is inspected without following anything: directories must be real directories (no symlink), every existing
# leaf git writes/appends/replaces must be a regular single-link file, every lock sibling must be absent, and every
# file under .git/objects a regular single-link file. Only lstat/fstatat and O_PATH directory descriptors are used
# (no file content is read; os.listdir only under .git/objects and the provision work-tree root). gw_post re-runs the
# scan after the command and requires every pre-existing directory to keep its identity: detection only, never the
# guard. Refusals: raise refuse(reason) (the caller's convention).
# r6 (Sol fix-check r5, U10): a symbolic or indirect destination ref would move the ref and reflog writes to paths
# outside the plan, so gw_scan also requires every ref the command updates (plan "direct") to be a DIRECT ref: its
# loose file (already validated as a regular single-link file) holds exactly one object name, and packed-refs
# (validated the same way) is well formed and has no peeled line for it. These two leaves are the only content read.
GIT_WRITE_GUARD = r'''
import os as _gw_os
import stat as _gw_stat

GW_RELEASE = "k4s-git-write-guard-r6"
# Write-reducing configuration for every writing git command (git 2.25.1 on 05 and on the Ubuntu 20.04 hosts). These
# REDUCE the write set; the scan confines what remains. core.logAllRefUpdates=false stops reflog CREATION but git
# still appends to an existing reflog, so reflogs stay in the scanned set. git 2.25 has no --no-write-fetch-head, so
# FETCH_HEAD is confined, not disabled.
GW_CONFIG = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "core.logAllRefUpdates=false",
             "-c", "core.splitIndex=false", "-c", "core.untrackedCache=false", "-c", "gc.auto=0",
             "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "fetch.writeCommitGraph=false",
             "-c", "fetch.recurseSubmodules=false", "-c", "submodule.recurse=false", "-c", "fetch.prune=false",
             "-c", "fetch.pruneTags=false")
GW_FETCH_FLAGS = ("-q", "--no-tags", "--no-auto-gc", "--no-recurse-submodules")
# Directories that must already exist as real directories.
GW_DIRS = (".git", ".git/objects", ".git/objects/pack", ".git/refs")
# Directories git may create; an existing one must be a real directory.
GW_MAY_DIRS = (".git/objects/info", ".git/refs/heads", ".git/logs", ".git/logs/refs", ".git/logs/refs/heads")
# Leaves git writes in place (FETCH_HEAD: fopen "w"; reflogs: O_APPEND), replaces through a lock file (HEAD, index,
# packed-refs, config, refs: lock + rename; the index / packed-refs / config locks RESOLVE a symlinked target) or might
# write (ORIG_HEAD, gc.pid, gc.log, commit-graph, info/packs): absent, or a regular single-link file.
GW_FILES = (".git/HEAD", ".git/index", ".git/FETCH_HEAD", ".git/ORIG_HEAD", ".git/packed-refs", ".git/config",
            ".git/logs/HEAD", ".git/gc.pid", ".git/gc.log", ".git/objects/info/commit-graph",
            ".git/objects/info/packs")
# Must not exist in any form (indirections, hooks, the split-index / commit-graph chain directories).
GW_ABSENT = (".git/hooks", ".git/shallow", ".git/commondir", ".git/config.worktree", ".git/objects/info/alternates",
             ".git/objects/info/http-alternates", ".git/objects/info/commit-graphs", ".git/info/grafts",
             ".git/modules", ".git/worktrees")
GW_TREES = (".git/objects",)
_GW_PATH = _gw_os.O_PATH | _gw_os.O_DIRECTORY | _gw_os.O_NOFOLLOW | _gw_os.O_CLOEXEC
_GW_LIST = _gw_os.O_RDONLY | _gw_os.O_DIRECTORY | _gw_os.O_NOFOLLOW | _gw_os.O_CLOEXEC
_GW_READ = _gw_os.O_RDONLY | _gw_os.O_NOFOLLOW | _gw_os.O_NONBLOCK | _gw_os.O_NOCTTY | _gw_os.O_CLOEXEC
GW_PACKED = ".git/packed-refs"
_GW_HEX = frozenset("0123456789abcdef")


def gw_plan(ref, worktree=(), worktree_only=None):
    """The write set of one fetch/checkout that updates `ref` (refs/heads/... or refs/remotes/...): GW_* plus the ref
    file, its reflog, their parent directories, every lock sibling, and the work-tree paths the checkout writes
    (`worktree`: exactly the paths that differ; `worktree_only`: the names allowed in a fresh work-tree root)."""
    parts = ref.split("/")
    if len(parts) < 3 or parts[0] != "refs" or any(p in ("", ".", "..") for p in parts):
        raise ValueError("bad ref %r" % ref)
    may = list(GW_MAY_DIRS)
    for top in (".git/", ".git/logs/"):
        for i in range(2, len(parts)):
            may.append(top + "/".join(parts[:i]))
    files = list(GW_FILES) + [".git/" + ref, ".git/logs/" + ref]
    absent = list(GW_ABSENT) + [f + ".lock" for f in files]
    return dict(release=GW_RELEASE, ref=ref, dirs=list(GW_DIRS), may_dirs=sorted(set(may) - set(GW_DIRS)),
                files=files, absent=absent, trees=list(GW_TREES), direct=[ref], worktree=list(worktree),
                worktree_only=None if worktree_only is None else sorted(worktree_only))


def _gw_parts(rel, refuse):
    parts = rel.split("/") if isinstance(rel, str) else [""]
    if not rel or rel.startswith("/") or any(p in ("", ".", "..") or "\x00" in p for p in parts):
        raise refuse("bad write-set path %r" % (rel,))
    return parts


def _gw_lstat(fd, name, rel, refuse):
    try:
        return _gw_os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise refuse("%s cannot be inspected (%s)" % (rel, _gw_os.strerror(error.errno)))


def _gw_open_dir(fd, name, st, rel, refuse, flags=_GW_PATH):
    try:
        child = _gw_os.open(name, flags, dir_fd=fd)
    except OSError as error:
        raise refuse("%s is not a real directory (%s)" % (rel, _gw_os.strerror(error.errno)))
    info = _gw_os.fstat(child)
    if not _gw_stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (st.st_dev, st.st_ino):
        _gw_os.close(child)
        raise refuse("%s changed while it was checked" % rel)
    return child


def gw_open_root(path, refuse):
    """The repository root, walked from / one component at a time without following anything."""
    if not isinstance(path, str) or not path.startswith("/") or path == "/" or _gw_os.path.normpath(path) != path:
        raise refuse("repository path %r is not absolute and normalized" % (path,))
    fd = _gw_os.open("/", _GW_PATH)
    try:
        done = ""
        for name in path[1:].split("/"):
            done += "/" + name
            st = _gw_lstat(fd, name, done, refuse)
            if st is None or not _gw_stat.S_ISDIR(st.st_mode):
                raise refuse("repository path component %s is not a real directory" % done)
            child = _gw_open_dir(fd, name, st, done, refuse)
            _gw_os.close(fd)
            fd = child
    except BaseException:
        _gw_os.close(fd)
        raise
    return fd


def _gw_dirs(root, parts, must, refuse, facts):
    """Walk `parts` below root: each existing component a real directory (recorded in facts); returns its fd, or None
    at the first absent component (allowed only when not `must`)."""
    fd = _gw_os.dup(root)
    try:
        for i, name in enumerate(parts):
            rel = "/".join(parts[:i + 1])
            st = _gw_lstat(fd, name, rel, refuse)
            if st is None:
                if must:
                    raise refuse("%s is missing (a real directory is required)" % rel)
                facts.setdefault(rel, ("absent",))
                _gw_os.close(fd)
                return None
            if not _gw_stat.S_ISDIR(st.st_mode):
                raise refuse("%s is not a real directory (a symlink or another file type)" % rel)
            child = _gw_open_dir(fd, name, st, rel, refuse)
            _gw_os.close(fd)
            fd = child
            facts[rel] = ("dir", st.st_dev, st.st_ino)
        return fd
    except BaseException:
        _gw_os.close(fd)
        raise


def _gw_leaf(root, rel, absent_only, refuse, facts):
    parts = _gw_parts(rel, refuse)
    fd = _gw_dirs(root, parts[:-1], False, refuse, facts)
    if fd is None:
        facts[rel] = ("absent",)
        return
    try:
        st = _gw_lstat(fd, parts[-1], rel, refuse)
    finally:
        _gw_os.close(fd)
    if st is None:
        facts[rel] = ("absent",)
        return
    if absent_only:
        raise refuse("%s exists; it must not exist in any form" % rel)
    if not _gw_stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise refuse("%s is not a regular single-link file (a symlink, a hard link or another file type)" % rel)
    facts[rel] = ("file", st.st_dev, st.st_ino)


def _gw_tree(root, rel, refuse, facts):
    """Every entry below rel: real directories and regular single-link files only (no symlink, no hard link)."""
    parts = _gw_parts(rel, refuse)
    top = _gw_dirs(root, parts[:-1], True, refuse, facts)
    stack = []
    try:
        st = _gw_lstat(top, parts[-1], rel, refuse)
        if st is None or not _gw_stat.S_ISDIR(st.st_mode):
            raise refuse("%s is not a real directory" % rel)
        stack.append((_gw_open_dir(top, parts[-1], st, rel, refuse, _GW_LIST), rel))
        facts[rel] = ("dir", st.st_dev, st.st_ino)
        while stack:
            fd, here = stack.pop()
            try:
                names = sorted(_gw_os.listdir(fd))
                for name in names:
                    sub = here + "/" + name
                    st = _gw_lstat(fd, name, sub, refuse)
                    if st is None:
                        raise refuse("%s vanished while it was checked" % sub)
                    if _gw_stat.S_ISDIR(st.st_mode):
                        stack.append((_gw_open_dir(fd, name, st, sub, refuse, _GW_LIST), sub))
                        facts[sub] = ("dir", st.st_dev, st.st_ino)
                    elif _gw_stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
                        facts[sub] = ("file", st.st_dev, st.st_ino)
                    else:
                        raise refuse("%s is not a real directory or a regular single-link file" % sub)
            finally:
                _gw_os.close(fd)
    finally:
        _gw_os.close(top)
        for fd, _ in stack:
            _gw_os.close(fd)


def _gw_read(root, rel, facts, limit, refuse):
    """r6: the bytes of a leaf this scan has just validated (facts: absent, or a regular single-link file), read through
    a no-follow descriptor whose fstat must be that same file; None when it is absent."""
    state = facts.get(rel)
    if state is None or state[0] not in ("absent", "file"):
        raise refuse("%s was not validated before it is read" % rel)
    if state[0] == "absent":
        return None
    parts = _gw_parts(rel, refuse)
    walked = {}
    fd = _gw_dirs(root, parts[:-1], True, refuse, walked)
    try:
        if any(facts.get(d) != s for d, s in walked.items()):
            raise refuse("the directories above %s changed while they were checked" % rel)
        try:
            leaf = _gw_os.open(parts[-1], _GW_READ, dir_fd=fd)
        except OSError as error:
            raise refuse("%s cannot be opened without following (%s)" % (rel, _gw_os.strerror(error.errno)))
    finally:
        _gw_os.close(fd)
    try:
        info = _gw_os.fstat(leaf)
        if not _gw_stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (info.st_dev, info.st_ino) != state[1:]:
            raise refuse("%s changed while it was checked" % rel)
        chunks, size = [], 0
        while True:
            chunk = _gw_os.read(leaf, 1 << 16)
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > limit:
                raise refuse("%s is larger than %d bytes" % (rel, limit))
            chunks.append(chunk)
    finally:
        _gw_os.close(leaf)


def _gw_oid(text):
    return len(text) == 40 and set(text) <= _GW_HEX


def _gw_packed(data, refuse):
    """packed-refs as {ref: peeled}: an optional '# pack-refs with:' header, then '<oid> <ref>' lines, each optionally
    followed by one '^<oid>' line. Anything else refuses (git itself never writes it)."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise refuse("%s is not ASCII" % GW_PACKED)
    if text and not text.endswith("\n"):
        raise refuse("%s does not end with a newline" % GW_PACKED)
    entries, last = {}, None
    for n, line in enumerate(text.split("\n")[:-1]):
        if n == 0 and line.startswith("# pack-refs with:"):
            continue
        if line.startswith("^"):
            if last is None or not _gw_oid(line[1:]):
                raise refuse("%s line %d is an unexpected peeled line" % (GW_PACKED, n + 1))
            entries[last], last = True, None
            continue
        oid, sep, name = line.partition(" ")
        if not sep or not _gw_oid(oid) or not name.startswith("refs/") or " " in name or name in entries:
            raise refuse("%s line %d is not '<object name> <ref>' (an indirection or another form)" % (GW_PACKED,
                                                                                                      n + 1))
        entries[name], last = False, name
    return entries


def gw_refs(root, plan, facts, refuse):
    """r6 (Sol fix-check r5, U10): every ref the command updates is a DIRECT ref, so git writes exactly the planned
    ref and reflog leaves: its loose file, when present, is exactly '<40 hex>\\n' (a 'ref:' symbolic ref or any other
    form refuses), and packed-refs is well formed with no peeled line for it."""
    data = _gw_read(root, GW_PACKED, facts, 64 << 20, refuse)
    packed = {} if data is None else _gw_packed(data, refuse)
    for ref in plan["direct"]:
        rel = ".git/" + ref
        data = _gw_read(root, rel, facts, 4096, refuse)
        if data is not None and data.startswith(b"ref:"):
            raise refuse("%s is a symbolic ref (%r): git would update its referent instead" % (rel, data[:120]))
        if data is not None and not (len(data) == 41 and data[40:] == b"\n" and _gw_oid(data[:40].decode("latin-1"))):
            raise refuse("%s is not exactly one object name (%r)" % (rel, data[:120]))
        if packed.get(ref):
            raise refuse("%s has a peeled (indirect) entry for %s" % (GW_PACKED, ref))


def gw_scan(path, plan, refuse):
    """Check the whole write set of `plan` in the repository at `path`; returns {rel: state} (dir/file identities,
    absences). Raises refuse(reason) at the first violation, before git runs."""
    if not isinstance(plan, dict) or plan.get("release") != GW_RELEASE:
        raise refuse("not a %s write-set plan" % GW_RELEASE)
    facts = {}
    root = gw_open_root(path, refuse)
    try:
        for rel in plan["dirs"]:
            _gw_os.close(_gw_dirs(root, _gw_parts(rel, refuse), True, refuse, facts))
        for rel in plan["may_dirs"]:
            fd = _gw_dirs(root, _gw_parts(rel, refuse), False, refuse, facts)
            if fd is not None:
                _gw_os.close(fd)
        for rel in plan["files"]:
            _gw_leaf(root, rel, False, refuse, facts)
        for rel in plan["absent"]:
            _gw_leaf(root, rel, True, refuse, facts)
        for rel in plan["trees"]:
            _gw_tree(root, rel, refuse, facts)
        gw_refs(root, plan, facts, refuse)                              # r6: after its leaves are validated
        if plan["worktree_only"] is not None:
            listing = _gw_os.open(".", _GW_LIST, dir_fd=root)
            try:
                names = sorted(_gw_os.listdir(listing))
            finally:
                _gw_os.close(listing)
            if names != plan["worktree_only"]:
                raise refuse("the work tree root holds %r, not exactly %r" % (names[:6], plan["worktree_only"]))
        for rel in plan["worktree"]:
            if rel == ".git" or rel.startswith(".git/"):
                raise refuse("work-tree path %r is inside .git" % rel)
            _gw_leaf(root, rel, False, refuse, facts)
    finally:
        _gw_os.close(root)
    return facts


def gw_post(path, plan, before, refuse):
    """After the git command (detection only, never the guard): the write set still passes gw_scan, and every
    directory that existed before is still the same directory."""
    after = gw_scan(path, dict(plan, worktree_only=None), refuse)         # a checkout populates a fresh root
    moved = sorted(rel for rel, state in before.items() if state[0] == "dir" and after.get(rel) != state)
    if moved:
        raise refuse("directories in the git write set changed identity during the command: %r" % moved[:4])
    return after


def gw_summary(facts):
    kinds = {}
    for state in facts.values():
        kinds[state[0]] = kinds.get(state[0], 0) + 1
    return dict(release=GW_RELEASE, checked=len(facts), kinds=dict(sorted(kinds.items())))
'''
_GW = {"__name__": "k4s_git_write_guard"}
exec(compile(GIT_WRITE_GUARD, "<k4s-git-write-guard>", "exec"), _GW)
GW_CONFIG, GW_FETCH_FLAGS = _GW["GW_CONFIG"], _GW["GW_FETCH_FLAGS"]


def gw_refusal(reason):
    return si.Refusal("git-write", reason)


def gw_check(path, plan):
    return _GW["gw_scan"](path, plan, gw_refusal)


def gw_after(path, plan, before):
    return _GW["gw_post"](path, plan, before, gw_refusal)


def require_direct_ref(g, ref):
    """r6 (Sol fix-check r5, U10): git's own reading of `ref` (read-only, through si.git_run's scrubbed environment;
    `symbolic-ref` is not in the pinned safe_input's subcommand allowlist, for-each-ref's %(symref) is the same
    answer): `ref` must be absent or a ref with no symbolic target; anything else refuses before any write."""
    out = si.git_run(g, ["for-each-ref", "--format=%(refname) %(symref)", ref], timeout=60).stdout
    if out not in (b"", (ref + " \n").encode()):
        raise gw_refusal("%s is a symbolic or indirect ref (%r): git would update its referent instead"
                         % (ref, out[:200].decode("utf-8", "replace")))


def changed_paths(g, old, new):
    """Every work-tree path a checkout from `old` to `new` writes or removes (tree metadata only)."""
    raw = si.git_run(g, ["diff-tree", "-r", "-z", "--no-renames", "--name-only", old, new], timeout=3600,
                     stdout_limit=64 << 20).stdout
    return sorted(p for p in raw.decode("utf-8", "surrogateescape").split("\x00") if p)


# ---------------------------------------------------------------- refresh-clone (r4, U10)

def objects_role(path=None):
    """Read role over every file under the clone's .git/objects (packs, loose objects, info): the never-rewrite proof."""
    return si.Role("clone-objects", (path or REPO_FULL) + "/.git/objects", "read", 16 << 30, patterns=("**",))


def objects_snapshot(policy):
    """{rel: (size, sha256)} of every regular single-link file under .git/objects (confined walk + gated hash)."""
    out = {}
    for f in si.walk_tree(policy, "clone-objects")["files"]:
        got = si.sha256_input(policy, "clone-objects", f["rel"], expected_size=f["size"])
        out[f["rel"]] = (got["size"], got["sha256"])
    return out


def ref_table(g):
    raw = si.git_run(g, ["for-each-ref", "--format=%(objectname) %(refname)"], timeout=120, stdout_limit=8 << 20).stdout
    table = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        oid, _, name = line.partition(" ")
        require(COMMIT.fullmatch(oid) is not None and name and name not in table, "git", "bad ref line %r" % line[:120])
        table[name] = oid
    return table


def fetch_argv():
    """The one network fetch (the second git call outside si.git_run, beside prepare-clone's clone): the fixed P2-4
    flags plus https only, fsck on receive, the r5 write-reducing GW_CONFIG (no reflog creation, auto-gc,
    maintenance, commit-graph, submodules or prune) and GW_FETCH_FLAGS (no tags, --no-auto-gc), an explicit git dir
    and the ORIGIN_URL (never the config remote), and exactly the END branch into its remote-tracking ref WITHOUT '+'
    (git itself refuses a non-fast-forward update)."""
    return ([si.GIT_BINARY, "--no-replace-objects", "--no-optional-locks"] + list(GW_CONFIG)
            + ["-c", "protocol.allow=never", "-c", "protocol.%s.allow=always" % CLONE_PROTOCOL,
               "-c", "transfer.fsckObjects=true", "--git-dir=" + REPO_FULL + "/.git", "fetch"] + list(GW_FETCH_FLAGS)
            + ["--", ORIGIN_URL, "refs/heads/%s:%s" % (END_BRANCH, END_BRANCH_REF)])


def checkout_argv(commit):
    """r5: refresh-clone --checkout (the third git call outside si.git_run): si.git_run's fixed flags plus GW_CONFIG
    (git_run cannot take global -c options), explicit git dir and work tree, detached X."""
    return ([si.GIT_BINARY, "--no-replace-objects", "--no-optional-locks"] + list(GW_CONFIG)
            + ["-c", "protocol.allow=never", "--git-dir=" + REPO_FULL + "/.git", "--work-tree=" + REPO_FULL,
               "checkout", "-q", "--detach", full_commit(commit, "commit")])


def refresh_clone(a, record, log=print):
    """U10: bring the END-JOB commit X into the EXISTING verified REPO_FULL. The live verify_clone() runs first; then
    ONE fetch of refs/heads/k4s-end-r1 only (fetch_argv: scrubbed P2-4 environment, no filter, fsck, https only,
    fast-forward only); then the full live verify_clone() with X. Proofs: every pre-existing file under .git/objects
    is byte-identical afterwards (objects are only added); every other ref is unchanged; the remote-tracking ref moved
    from its old value to exactly X, a descendant of the old value (and of --base-commit when given). HEAD and the
    work tree are untouched unless --checkout (then: detached X, clean status).
    r5 (Sol integration r1 finding 2): immediately before the fetch, and before the --checkout, the git write guard
    (gw_check) confines every path git may write (FETCH_HEAD, the remote-tracking ref and its reflog, HEAD and its
    reflog, index, packed-refs, lock siblings, .git/objects, the checkout's work-tree paths, and all their ancestors);
    gw_after re-checks after each command (detection only).
    r6 (Sol fix-check r5, U10): gw_check also requires the destination ref to be a DIRECT ref (no 'ref:' loose file,
    no peeled packed-refs entry), then require_direct_ref asks git itself; both before the fetch and the checkout."""
    commit = full_commit(a.commit, "--commit")
    base = full_commit(a.base_commit, "--base-commit") if a.base_commit else None
    policy = si.Policy(C.local_host(), [clone_role(), objects_role(), repo_role(), C.code_role()])
    before = require_full_clone(())                                    # F4: live, before the fetch
    g = repo()
    refs_before = ref_table(g)
    old = refs_before.get(END_BRANCH_REF)
    require(old is not None, "check", "the full clone has no %s (prepare-clone fetches every branch)" % END_BRANCH_REF)
    head_before = si.git_run(g, ["rev-parse", "HEAD"], timeout=60).stdout.decode().strip()
    objects_before = objects_snapshot(policy)
    plan = _GW["gw_plan"](END_BRANCH_REF)
    guard = gw_check(REPO_FULL, plan)                                  # r5: the write set, BEFORE the fetch
    require_direct_ref(g, END_BRANCH_REF)                              # r6: and git's own view of the destination
    with C.ScrubbedEnv() as env:
        si.run_checked(fetch_argv(), 3600, 1 << 20, env=env, cwd=REPO_FULL)
    gw_after(REPO_FULL, plan, guard)
    after = require_full_clone((commit,) + ((base,) if base else ()))  # F4: the full live verification again
    refs_after = ref_table(g)
    require(refs_after.get(END_BRANCH_REF) == commit, "check", "%s is %s after the fetch, not the given X %s"
            % (END_BRANCH_REF, refs_after.get(END_BRANCH_REF), commit))
    changed = sorted(n for n in set(refs_before) | set(refs_after) if refs_before.get(n) != refs_after.get(n))
    require(changed in ([], [END_BRANCH_REF]), "check", "the fetch changed other refs: %r" % changed[:6])
    require(is_ancestor(g, old, commit), "check", "X %s is not a fast-forward of %s %s" % (commit, END_BRANCH_REF, old))
    if base is not None:
        require(base != commit and is_ancestor(g, base, commit), "check", "X is not a strict descendant of --base-commit")
    objects_after = objects_snapshot(policy)
    lost = sorted(rel for rel, v in objects_before.items() if objects_after.get(rel) != v)
    require(not lost, "check", "pre-existing object files changed or vanished: %r" % lost[:4])
    head = si.git_run(g, ["rev-parse", "HEAD"], timeout=60).stdout.decode().strip()
    require(head == head_before, "check", "HEAD moved during the fetch")
    checkout_guard = None
    if a.checkout:
        plan = _GW["gw_plan"](END_BRANCH_REF, worktree=changed_paths(g, head, commit))
        before_checkout = gw_check(REPO_FULL, plan)                    # r5: BEFORE the checkout
        require_direct_ref(g, END_BRANCH_REF)                          # r6 (HEAD itself: --detach never dereferences)
        with C.ScrubbedEnv() as env:
            si.run_checked(checkout_argv(commit), 3600, 1 << 20, env=env, cwd=REPO_FULL)
        checkout_guard = _GW["gw_summary"](gw_after(REPO_FULL, plan, before_checkout))
        head = si.git_run(g, ["rev-parse", "HEAD"], timeout=60).stdout.decode().strip()
        require(head == commit, "check", "checkout HEAD %s is not %s" % (head, commit))
        status = si.git_run(g, ["status", "--porcelain", "--untracked-files=no"], timeout=3600).stdout
        require(status == b"", "check", "the full clone work tree is not clean at X")
    result = dict(schema=REFRESH_SCHEMA, utc=C.utc(), repository=REPO_FULL, origin=ORIGIN_URL, branch=END_BRANCH,
                  ref=END_BRANCH_REF, old=old, commit=commit, base_commit=base, fetch_argv=fetch_argv(),
                  refs_changed=changed, objects_before=len(objects_before),
                  objects_added=sorted(set(objects_after) - set(objects_before)), objects_unchanged=True,
                  head_before=head_before, head=head, checkout=bool(a.checkout), full_clone_before=before,
                  git_write_guard=dict(_GW["gw_summary"](guard), config=list(GW_CONFIG), checkout=checkout_guard),
                  full_clone=after, safe_input_sha256=C.SAFE_INPUT_SHA256,
                  script_sha256=C.code_sha(policy, "s9_end_runtime.py"))
    sha = record.write("s9-refresh-clone.json", result)
    log("S9 refresh-clone OK: %s %s -> %s (record sha256 %s)" % (END_BRANCH_REF, old[:12], commit[:12], sha))
    return result


# ---------------------------------------------------------------- locate (exact Q5 paths only)

def q5_role():
    return si.Role("q5", Q5_SOURCE, "read", MAX_EXTERNAL_BYTES, exact=tuple(sorted(EXTERNAL)))


def locate(policy, pins):
    files, missing = [], []
    for name in sorted(EXTERNAL):
        row = dict(path=name, expected_sha256=pins[name], source=Q5_SOURCE + "/" + name)
        try:
            got = si.sha256_input(policy, "q5", name)
        except si.Refusal as error:
            row.update(found=False, refusal=error.code)
        else:
            row.update(found=got["sha256"] == pins[name], size=got["size"], sha256=got["sha256"])
        files.append(row)
        if not row["found"]:
            missing.append(name)
    return dict(schema=LOCATE_SCHEMA, utc=C.utc(), source=Q5_SOURCE, wanted=len(EXTERNAL),
                found=len(EXTERNAL) - len(missing), missing=missing, ok=not missing, files=files)


def print_locate(result, log=print):
    for row in result["files"]:
        tag = "FOUND  " if row["found"] else "MISSING"
        log("%s  %s  %s" % (tag, row["expected_sha256"][:12], row["path"]))
    log("locate: %d/%d found; missing %d" % (result["found"], result["wanted"], len(result["missing"])))
    if result["missing"]:
        log("!!! MISSING PINS: STOP for a coordinator ruling; never substitute bytes !!!")


# ---------------------------------------------------------------- frozen inventory rules (stdlib, from the inventory)

def measurement_files(inventory):
    """prepare_bundle.py:117 rule over the e4v3 directory's direct children."""
    prefix = E4V3_REL + "/"
    out = {}
    for path, f in inventory.items():
        if path.startswith(prefix) and "/" not in path[len(prefix):]:
            name = path[len(prefix):]
            if name.endswith((".py", ".sh")) or name == "spec-pins.json":
                out[name] = f["sha256"]
    return dict(sorted(out.items()))


def runtime_files(inventory, pins, qualified):
    """prepare_bundle.runtime_pins (prepare_bundle.py:36-52): pin names U every *.py of the tree."""
    names = set(pins) | {p for p in inventory if p.endswith(".py")}
    missing = sorted(n for n in names if n not in inventory)
    require(not missing, "check", "Incomplete frozen runtime: %r" % missing[:8])
    result = {n: inventory[n]["sha256"] for n in sorted(names)}
    for n, expected in sorted(qualified["qualified_source_files"].items()):
        require(result.get(n) == expected, "check", "Not the qualified S1 tier source: " + n)
    return result


def verify_closure(inventory, k4s):
    """Stdlib, BEFORE any frozen import: the runtime's K4S manifest bytes are 74314eda, every file it pins matches,
    the e4v3 measurement inventory is 42b8986d, and every module of IMPORT_CLOSURE is covered by a verified pin."""
    require(inventory.get(K4S_MANIFEST_REL, {}).get("sha256") == K4S_MANIFEST_SHA, "check",
            "runtime K4S manifest is not 74314eda")
    pins = {}
    for key in ("k4s_files", "end_files", "reused_readonly"):
        pins.update(k4s[key])
    pins.update(k4s["k4s_kernel"]["files"])
    for name, expected in sorted(pins.items()):
        require(inventory.get(name, {}).get("sha256") == expected, "check", "K4S-pinned file differs: " + name)
    measurement = measurement_files(inventory)
    require(C.canonical_sha(measurement) == MEASUREMENT_SHA, "check", "e4v3 measurement inventory is not 42b8986d")
    for name in IMPORT_CLOSURE:
        covered = name in pins or (name.startswith(E4V3_REL + "/") and name.rsplit("/", 1)[1] in measurement)
        require(covered, "check", "import closure module is not covered by a verified pin: " + name)
    support = check_support_pins(inventory, k4s)
    return dict(k4s_pins_verified=len(pins), measurement_files_sha256=C.canonical_sha(measurement),
                import_closure=list(IMPORT_CLOSURE), support_pins_verified=support)


def check_support_pins(inventory, k4s=None):
    """r4 (B3/B5): every SUPPORT_PINS file is in the runtime with its pinned SHA-256; with the K4S manifest, the SD1
    and corpus-inventory pins must also be the manifest's own (sd1_manifest, references.t1_corpus_inventory,
    corpus.inventory), so a stale constant cannot pass."""
    for rel, pin in sorted(SUPPORT_PINS.items()):
        require(inventory.get(rel, {}).get("sha256") == pin, "check",
                "r4 support member missing or differs from its pin: %s (want %s)" % (rel, pin[:12]))
    if k4s is not None:
        sd1, corpora = k4s.get("sd1_manifest") or {}, (k4s.get("references") or {}).get("t1_corpus_inventory") or {}
        require(sd1.get("path") == SD1_REL and sd1.get("sha256") == SUPPORT_PINS[SD1_REL], "check",
                "the K4S manifest's sd1_manifest is not the pinned SD1 support member")
        require(corpora.get("path") == CORPORA_REL and corpora.get("sha256") == SUPPORT_PINS[CORPORA_REL]
                and (k4s.get("corpus") or {}).get("inventory") == CORPORA_REL, "check",
                "the K4S manifest's corpus inventory is not the pinned corpora.json support member")
    return sorted(SUPPORT_PINS)


FROZEN_SNIPPET = r"""
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
e4v3 = root / sys.argv[2]; mac = root / sys.argv[3]
sys.path.insert(0, str(e4v3)); sys.path.insert(0, str(mac))
import prepare_bundle, k4s_logic
closure = {str(root / n) for n in json.loads(sys.argv[6])}
loaded = {str(Path(m.__file__).resolve()) for m in list(sys.modules.values()) if getattr(m, "__file__", None)
          and str(Path(m.__file__).resolve()).startswith(str(root) + "/")}
if not loaded <= closure or str((e4v3 / "prepare_bundle.py").resolve()) not in loaded:
    raise SystemExit("runtime modules imported outside the verified closure: " + repr(sorted(loaded - closure)))
runtime = prepare_bundle.runtime_pins(root)
manifest = k4s_logic.load_k4s_manifest(root / sys.argv[4], sys.argv[5], root, require_frozen=True)
print(json.dumps(dict(runtime_files=runtime, prepare_bundle=str(Path(prepare_bundle.__file__).resolve()),
                      k4s_logic=str(Path(k4s_logic.__file__).resolve()), python=sys.version.split()[0],
                      optimize=sys.flags.optimize, k4s_manifest_schema=manifest["schema"],
                      k4s_reused_readonly=len(manifest["reused_readonly"]))))
"""


def frozen_check(root, inventory, k4s, python):
    """The FROZEN prepare_bundle.runtime_pins and k4s_logic.load_k4s_manifest, imported from the runtime itself, ONLY
    after verify_closure() verified their bytes with stdlib; P2-4 environment; never -O."""
    closure = verify_closure(inventory, k4s)
    with C.ScrubbedEnv() as env:
        argv = [python, "-I", "-B", "-c", FROZEN_SNIPPET, root, E4V3_REL, K4S_MAC_REL, K4S_MANIFEST_REL,
                K4S_MANIFEST_SHA, json.dumps(IMPORT_CLOSURE)]
        result = si.run_checked(argv, 1800, 64 << 20, env=env, cwd="/")
    out = si.loads_strict(result.stdout, "frozen runtime check output")
    require(isinstance(out, dict) and out.get("optimize") == 0, "check", "frozen check did not run unoptimized")
    out["stdlib_verified"] = closure
    return out


# ---------------------------------------------------------------- build

def build_policy(parent, leaf):
    partial = parent + "/" + leaf + ".partial"
    return si.Policy(C.local_host(), [
        repo_role(), q5_role(), C.code_role(),
        si.Role("out-parent", parent, "write", 1 << 20, exact=(leaf, leaf + ".partial")),
        si.Role("partial", partial, "write", 1 << 30, exact=(MANIFEST,), patterns=("S9-REFUSAL-*.json",)),
        si.Role("runtime-out", partial + "/runtime", "write", MAX_MEMBER_BYTES, patterns=("**",),
                exemptions=("E4", "E5")),
        si.Role("runtime-in", partial + "/runtime", "read", MAX_MEMBER_BYTES, patterns=("**",),
                exemptions=("E4", "E5"))])


def build(a, log=print):
    commit = full_commit(a.commit, "--commit")
    parent, leaf = C.output_path(a.out, "--out")
    python = C.input_dir(a.python, "--python")
    policy = build_policy(parent, leaf)
    with si.Writer(policy, "out-parent") as top:
        top.mkdir_excl(leaf + ".partial")                             # first: refusals leave a receipt inside it
    writer = si.Writer(policy, "partial")
    try:
        manifest = _build(policy, writer, commit, python, log)
    except BaseException as error:
        si.write_refusal_receipt(writer, "S9", error, {"commit": commit})
        raise
    finally:
        writer.close()
    C.publish_dir(policy, "out-parent", leaf + ".partial", leaf)
    log("S9 OK: %s/%s/%s sha256 %s" % (parent, leaf, MANIFEST, manifest["_sha256"]))
    log("  runtime_files %d canonical %s" % (manifest["runtime_files_count"], manifest["runtime_files_sha256"]))
    log("  measurement_files canonical %s; inventory %d files, %d bytes, canonical %s"
        % (manifest["measurement_files_sha256"], manifest["inventory_files"], manifest["inventory_bytes"],
           manifest["inventory_sha256"]))
    return manifest


def _build(policy, writer, commit, python, log):
    started = C.utc()
    full_clone = require_full_clone((commit,))                         # F4: live, before any read of the clone
    pins, qualified, k4s = commit_pins(policy, commit, build=True)
    located = locate(policy, pins)
    print_locate(located, log)
    if located["missing"]:
        raise Missing("33-pin locate incomplete; missing: " + ", ".join(located["missing"]))
    plan = member_plan(policy, commit, pins)                          # phase 1 complete before any blob read
    writer.mkdir_excl("runtime")
    out = si.Writer(policy, "runtime-out")
    try:
        exported = plan.export(out)                                    # phase 2: planned members only (D1, D2)
        made = set(C.dirs_of(exported))
        for d in C.dirs_of(EXTERNAL):
            if d not in made:
                out.mkdir_excl(d)
                made.add(d)
        externals = []
        for name in sorted(EXTERNAL):                                  # R7: exclusive plain copies, pinned
            copied = si.copy_input(policy, "q5", name, out, name, expected_sha256=pins[name])
            externals.append(dict(path=name, sha256=copied["sha256"], size=copied["size"],
                                  source_path=Q5_SOURCE + "/" + name))
    finally:
        out.close()
    executable = {e["path"] for e in plan.files if e["mode"] == "100755"}
    inventory = tree_inventory(policy, "runtime-in", executable)
    expected = set(exported) | set(EXTERNAL)
    require(set(inventory) == expected, "check", "tree differs from the planned members + externals: %r"
            % sorted(set(inventory) ^ expected)[:6])
    for path, f in exported.items():
        require(inventory[path]["sha256"] == f["sha256"], "check", "exported file changed: " + path)
    e1 = plan.e1_verify_shipped(policy, "runtime-in") if plan.e1 is not None else None
    local = runtime_files(inventory, pins, qualified)
    measurement = measurement_files(inventory)
    root = policy.role("runtime-in").root
    frozen = frozen_check(root, inventory, k4s, python)
    require(frozen.get("runtime_files") == local, "check", "frozen runtime_pins differs from the S9 computation")
    tracked_mismatch = [dict(path=n, git_sha256=local.get(n), runtime_pin_r2_sha256=pins[n])
                        for n in sorted(pins) if n not in EXTERNAL and local.get(n) != pins[n]]
    dirs = C.dirs_of(inventory)
    inv = dict(files=inventory, dirs=dirs)
    members = git_members(plan)
    manifest = dict(
        schema=SCHEMA, status="CANDIDATE-built", started_utc=started, finished_utc=C.utc(), commit=commit,
        repository=REPO_FULL, base_commit=BASE_COMMIT, runtime_dir="runtime", k4s_manifest_sha256=K4S_MANIFEST_SHA,
        runtime_pin_r2_sha256=RUNTIME_PIN_SHA, qualified_source_binding_sha256=QUALIFIED_SHA,
        member_rule="runtime-pin-r2 files U every *.py U SUPPORT_MEMBERS (D1 + r4 extension; tree metadata only)",
        support_members=sorted(SUPPORT_MEMBERS), support_pins=dict(sorted(SUPPORT_PINS.items())), git_members=members, git_members_sha256=C.canonical_sha(members),
        e4_members=[e["path"] for e in plan.e4], e5_members=[e["path"] for e in plan.e5], e1=e1,
        runtime_files=local, runtime_files_count=len(local), runtime_files_sha256=C.canonical_sha(local),
        measurement_files=measurement, measurement_files_sha256=C.canonical_sha(measurement),
        externals=externals, q5_source=Q5_SOURCE, tracked_pin_sha_differs_from_git=tracked_mismatch,
        frozen_check=dict((k, v) for k, v in frozen.items() if k != "runtime_files"), frozen_runtime_files_equal=True,
        inventory=inv, inventory_files=len(inventory), inventory_bytes=sum(f["size"] for f in inventory.values()),
        inventory_sha256=C.canonical_sha(inv), r6_end_dir_absent=True, python=python, full_clone=full_clone,
        safe_input_sha256=C.SAFE_INPUT_SHA256, script_sha256=C.code_sha(policy, "s9_end_runtime.py"),
        common_sha256=C.code_sha(policy, "end_prep_common.py"))
    result = writer.write_json_once(MANIFEST, manifest)
    manifest["_sha256"] = result["sha256"]
    return manifest


def tree_inventory(policy, role_name, executable):
    """The confined walk (names gated before lstat; symlink/special/hard link/undeclared refuse; E4 only at the exact
    paths) + a descriptor-gated hash of every file; E4 files through si.hash_e4 (hash only, pinned SHA-256) and E5
    files through si.hash_e5 (hash only, pinned git blob OID); neither is ever returned as bytes or parsed."""
    walk = si.walk_tree(policy, role_name)
    require(walk["e1"] is None, "check", "D2: the runtime must hold no symlink (E1 is materialised)")
    inventory = {}
    for f in walk["files"]:
        got = si.sha256_input(policy, role_name, f["rel"], expected_size=f["size"])
        inventory[f["rel"]] = dict(size=got["size"], sha256=got["sha256"], executable=f["rel"] in executable)
    for rel in walk["e4"]:
        got = si.hash_e4(policy, role_name, rel)
        inventory[rel] = dict(size=got["size"], sha256=got["sha256"], executable=False, e4=True)
    for rel in walk["e5"]:
        got = si.hash_e5(policy, role_name, rel)
        inventory[rel] = dict(size=got["size"], sha256=got["sha256"], executable=False, e5=True)
    return dict(sorted(inventory.items()))


# ---------------------------------------------------------------- verify / load (also used by S10)

def verify_roles(prefix, out):
    return [si.Role(prefix + "-out", out, "read", 256 << 20, exact=(MANIFEST,)),
            si.Role(prefix + "-runtime", out + "/runtime", "read", MAX_MEMBER_BYTES, patterns=("**",),
                    exemptions=("E4", "E5"))]


def load_manifest(policy, prefix, manifest_sha256):
    C.need_sha256(manifest_sha256, "runtime manifest SHA-256")
    manifest = si.read_json(policy, prefix + "-out", MANIFEST, 256 << 20, expected_sha256=manifest_sha256)
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA
            and manifest.get("k4s_manifest_sha256") == K4S_MANIFEST_SHA and manifest.get("runtime_dir") == "runtime"
            and manifest.get("measurement_files_sha256") == MEASUREMENT_SHA, "check", "not an S9 r2 runtime manifest")
    full_commit(manifest.get("commit"), "manifest commit")
    return manifest


def verify(policy, prefix, manifest_sha256, frozen=False, python=DEFAULT_PYTHON, log=print):
    require_full_clone()                                               # F4: live, before anything else
    manifest = load_manifest(policy, prefix, manifest_sha256)
    is_commit(repo(), manifest["commit"])                              # the built commit is in the verified clone
    executable = {p for p, f in manifest["inventory"]["files"].items() if f.get("executable")}
    inventory = tree_inventory(policy, prefix + "-runtime", executable)
    inv = dict(files=inventory, dirs=C.dirs_of(inventory))
    require(inv == manifest["inventory"] and C.canonical_sha(inv) == manifest["inventory_sha256"], "check",
            "runtime tree differs from its manifest inventory")
    require(set(manifest["runtime_files"]) <= set(inventory) and all(
        inventory[n]["sha256"] == s for n, s in manifest["runtime_files"].items())
        and C.canonical_sha(manifest["runtime_files"]) == manifest["runtime_files_sha256"], "check",
        "runtime_files differ from the manifest")
    measurement = measurement_files(inventory)
    require(measurement == manifest["measurement_files"] and C.canonical_sha(measurement) == MEASUREMENT_SHA, "check",
            "measurement_files differ")
    check_support_pins(inventory)                                      # r4: a pre-r4 runtime (no SD1/corpora/DELTA)
    if si.E1_ALIAS in inventory:
        require(inventory[si.E1_ALIAS]["sha256"] == inventory[si.E1_LINK_TEXT]["sha256"], "check",
                "D2: shipped visualize_battle.py differs from its target bytes")
    if frozen:
        k4s = si.loads_strict(si.read_bytes(policy, prefix + "-runtime", K4S_MANIFEST_REL,
                                            expected_sha256=K4S_MANIFEST_SHA), K4S_MANIFEST_REL)
        result = frozen_check(policy.role(prefix + "-runtime").root, inventory, k4s, python)
        require(result.get("runtime_files") == manifest["runtime_files"], "check", "frozen runtime_pins differs")
    log("S9 VERIFY OK: manifest %s; runtime_files %s; inventory %s%s" % (
        manifest_sha256, manifest["runtime_files_sha256"], manifest["inventory_sha256"],
        " (frozen re-run)" if frozen else ""))
    return manifest


# ---------------------------------------------------------------- equivalence (P2-2 hard gate)

def equivalence(policy, prefix, manifest_sha256, end_job_commit, log=print):
    full_clone = require_full_clone()                                  # F4: live, before anything else
    manifest = load_manifest(policy, prefix, manifest_sha256)
    p, x = manifest["commit"], full_commit(end_job_commit, "--end-job-commit")
    g = repo()
    is_commit(g, p)
    is_commit(g, x)
    require(p != x and is_ancestor(g, p, x), "check", "the END-JOB commit is not a strict descendant of P")
    raw = si.git_run(g, ["diff-tree", "-r", "-z", "--name-only", "--no-renames", p, x], timeout=300).stdout
    require(raw.endswith(b"\x00"), "git", "diff-tree output not NUL-terminated")
    names = [n.decode("utf-8", "replace") for n in raw.split(b"\x00")[:-1]]
    require(names == [END_JOB_REL], "check", "P2-2: the P..X diff must be exactly %s, got %r" % (END_JOB_REL, names[:6]))
    entry = [e for e in si.git_ls_tree(g, x) if e["path"].startswith(si.STRICT_END_DIR + "/")]
    require([(e["path"], e["type"], e["mode"]) for e in entry] == [(END_JOB_REL, "blob", "100644")], "check",
            "R6: at X the END dir must hold exactly END-JOB.json (a regular blob)")
    pins_p, _, _ = commit_pins(policy, p, build=True)
    pins_x, _, _ = commit_pins(policy, x)
    require(pins_p == pins_x, "check", "runtime-pin-r2 differs between P and X")
    plan_p, plan_x = member_plan(policy, p, pins_p), member_plan(policy, x, pins_p)
    members_p, members_x = git_members(plan_p), git_members(plan_x)
    require(members_p == members_x, "check", "member (path, mode, oid) differ between P and X")
    require(members_p == manifest["git_members"] and C.canonical_sha(members_p) == manifest["git_members_sha256"],
            "check", "the built runtime's git members differ from the member plan at P")
    result = dict(schema=EQUIV_SCHEMA, utc=C.utc(), runtime_commit=p, end_job_commit=x, diff=names,
                  runtime_manifest_sha256=manifest_sha256, git_members=len(members_p),
                  git_members_sha256=C.canonical_sha(members_p), runtime_files_sha256=manifest["runtime_files_sha256"],
                  measurement_files_sha256=manifest["measurement_files_sha256"],
                  runtime_files_identical=True, measurement_files_identical=True, externals_unchanged=True,
                  full_clone=full_clone)
    log(json.dumps(result, indent=1, sort_keys=True))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command")
    cp = sub.add_parser("prepare-clone", allow_abbrev=False)
    cp.add_argument("--commit", required=True, help="evidence commit P (checked out after verification)")
    lp = sub.add_parser("locate", allow_abbrev=False)
    lp.add_argument("--commit", required=True)
    lp.add_argument("--record", help="new local directory for the locate result / refusal receipt")
    bp = sub.add_parser("build", allow_abbrev=False)
    bp.add_argument("--commit", required=True, help="evidence commit P")
    bp.add_argument("--out", required=True)
    bp.add_argument("--python", default=DEFAULT_PYTHON)
    vp = sub.add_parser("verify", allow_abbrev=False)
    vp.add_argument("--out", required=True)
    vp.add_argument("--manifest-sha256", required=True)
    vp.add_argument("--frozen", action="store_true")
    vp.add_argument("--python", default=DEFAULT_PYTHON)
    vp.add_argument("--record")
    ep = sub.add_parser("equivalence", allow_abbrev=False)
    ep.add_argument("--out", required=True, help="the S9 output built at P")
    ep.add_argument("--manifest-sha256", required=True)
    ep.add_argument("--end-job-commit", required=True)
    ep.add_argument("--record")
    rp = sub.add_parser("refresh-clone", allow_abbrev=False)
    rp.add_argument("--commit", required=True, help="X: the END-JOB commit, the new tip of refs/heads/k4s-end-r1")
    rp.add_argument("--base-commit", help="P: X must be its strict descendant")
    rp.add_argument("--checkout", action="store_true", help="also check out X detached (default: HEAD untouched)")
    rp.add_argument("--record", required=True, help="new local directory for the refresh record / refusal receipt")
    a = ap.parse_args(argv)
    if a.command is None:
        ap.print_usage(sys.stderr)
        return 2
    record = None
    try:
        if getattr(a, "record", None):
            record = C.Record(a.record, "S9", ("s9-%s.json" % a.command,))
            record.open()                                             # first: every later refusal leaves a receipt
        if a.command == "prepare-clone":
            prepare_clone(a)
        elif a.command == "refresh-clone":
            refresh_clone(a, record)
        elif a.command == "build":
            build(a)
        elif a.command == "locate":
            policy = si.Policy(C.local_host(), [repo_role(), q5_role()])
            require_full_clone((full_commit(a.commit, "--commit"),))   # F4: live, before any read of the clone
            pins, _, _ = commit_pins(policy, a.commit)
            result = locate(policy, pins)
            result["commit"] = a.commit
            print_locate(result)
            if record is not None:
                print("locate result sha256 %s" % record.write("s9-locate.json", result))
            if not result["ok"]:
                return 3
        else:
            out = C.input_dir(a.out, "--out")
            policy = si.Policy(C.local_host(), [repo_role()] + verify_roles("s9", out))
            if a.command == "verify":
                result = verify(policy, "s9", a.manifest_sha256, a.frozen, C.input_dir(a.python, "--python"))
                summary = dict(commit=result["commit"], runtime_files_sha256=result["runtime_files_sha256"],
                               inventory_sha256=result["inventory_sha256"], manifest_sha256=a.manifest_sha256)
            else:
                summary = equivalence(policy, "s9", a.manifest_sha256, a.end_job_commit)
            if record is not None:
                record.write("s9-%s.json" % a.command, summary)
    except Missing as error:
        if record is not None:
            record.refusal(error)
        print("S9 STOP (missing pins): " + str(error), file=sys.stderr)
        return 3
    except si.Refusal as error:
        if record is not None:
            record.refusal(error)
        print("S9 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        if record is not None:
            record.refusal(error)
        print("S9 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    finally:
        if record is not None:
            record.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
