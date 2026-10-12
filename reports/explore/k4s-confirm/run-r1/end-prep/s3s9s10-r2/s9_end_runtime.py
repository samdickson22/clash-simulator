#!/usr/bin/env python3
"""S9 (PREREG-K4S END, Q5 / D1 / D2 / E1-E5 / R6 / P2-2): 05-only END runtime builder. r2: safe_input adoption.

CANDIDATE: needs Sol review before any use. No ssh, no host.

Source (ruling 21:28Z "full clone"): ONLY the runner-owned full clone REPO_FULL; never the shared partial checkout.
Every git call is si.git_run (scrubbed environment, no replace objects, no hooks, static refusal of alternates /
grafts / shallow / gitfile / config drivers; P2-4) except the one network clone in `prepare-clone`, which uses
si.run_checked with the same fixed environment and global flags plus protocol.https.allow (git_run disables every
network transport by design) and is then verified through safe_input before anything reads it.

Subcommands
  prepare-clone  Create REPO_FULL with a no-filter `git clone` from origin, then verify through safe_input: plain
                 config (no promisor / partialclonefilter / extensions / drivers / includes), no alternates, grafts,
                 shallow, hooks, replace refs or .promisor packs; --commit P present; check out P (detached).
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

_HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [_HERE]:
    sys.path.insert(0, _HERE)
import end_prep_common as C                                           # noqa: E402

if os.path.dirname(os.path.abspath(C.__file__)) != _HERE:
    raise SystemExit("end_prep_common imported from outside " + _HERE)

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-runtime.v2"
LOCATE_SCHEMA = "clasher.k4s.end-runtime-locate.v2"
EQUIV_SCHEMA = "clasher.k4s.end-runtime-equivalence.v2"
CLONE_SCHEMA = "clasher.k4s.end-runtime-full-clone.v1"
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
SUPPORT_MEMBERS = frozenset((RUNTIME_PIN_REL, QUALIFIED_REL, K4S_MANIFEST_REL, K4S_MAC_REL + "/K4S-MAC-PROCEDURE.md",
                             E4V3_REL + "/spec-pins.json", E4V3_REL + "/build_tiers.sh"))
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

def clone_policy():
    parent, leaf = REPO_FULL.rsplit("/", 1)
    return si.Policy(C.local_host(), [
        si.Role("clone-parent", parent, "write", 1 << 20, exact=(leaf, leaf + "-PREPARE.json")),
        si.Role("clone-parent-read", parent, "read", 1 << 20, exact=(leaf + "-PREPARE.json",)),
        si.Role("clone", REPO_FULL, "read", 16 << 30, exact=(".git/config", ".git/hooks"),
                patterns=(".git/objects/pack/*",)),
        repo_role(), C.code_role()])


def check_clone_config(policy):
    text = si.read_bytes(policy, "clone", ".git/config", max_size=64 << 10).decode("utf-8", "replace")
    keys, section, values = [], None, {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            head = line[1:].split("]", 1)[0].strip()
            name, _, sub = head.partition(" ")
            section = name.casefold() + ("." + sub.strip().strip('"') if sub else "")
            continue
        key, _, value = line.partition("=")
        full = "%s.%s" % (section, key.strip().casefold())
        keys.append(full)
        values[full] = value.strip()
    require(sorted(keys) == sorted(CLONE_CONFIG_KEYS), "indirection",
            "full clone config is not the plain clone config (promisor/partial/extension/driver keys refuse): %r"
            % sorted(set(keys) ^ set(CLONE_CONFIG_KEYS)))
    require(values.get("remote.origin.url") == ORIGIN_URL and values.get("core.repositoryformatversion") == "0",
            "indirection", "full clone origin/format differ")
    return keys


def verify_clone(policy, commit):
    """Everything the full-clone ruling requires, through safe_input (each git_run re-runs the static preflight)."""
    g = repo()
    keys = check_clone_config(policy)
    si.check_absent(policy, "clone", ".git/hooks")
    packs = si.walk_tree(policy, "clone", ".git/objects/pack")
    names = [f["rel"].rsplit("/", 1)[1] for f in packs["files"]]
    require(not [n for n in names if n.endswith(".promisor")], "indirection", "promisor pack in the full clone")
    shallow = si.git_run(g, ["rev-parse", "--is-shallow-repository"], timeout=60).stdout
    require(shallow == b"false\n", "indirection", "the full clone is shallow")
    replace = si.git_run(g, ["for-each-ref", "refs/replace"], timeout=60).stdout
    require(replace == b"", "indirection", "the full clone has replace refs")
    is_commit(g, commit)
    return dict(config_keys=sorted(keys), packs=sorted(names))


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
    facts = verify_clone(policy, commit)
    si.git_run(repo(), ["checkout", "-q", "--detach", commit], timeout=3600)
    head = si.git_run(repo(), ["rev-parse", "HEAD"], timeout=60).stdout.decode().strip()
    require(head == commit, "check", "checkout HEAD %s is not %s" % (head, commit))
    status = si.git_run(repo(), ["status", "--porcelain", "--untracked-files=no"], timeout=3600).stdout
    require(status == b"", "check", "the full clone work tree is not clean at P")
    facts = dict(schema=CLONE_SCHEMA, utc=C.utc(), repository=REPO_FULL, origin=ORIGIN_URL, commit=commit,
                 head=head, safe_input_sha256=C.SAFE_INPUT_SHA256,
                 script_sha256=C.code_sha(policy, "s9_end_runtime.py"), **facts)
    with si.Writer(policy, "clone-parent") as writer:
        writer.write_json_once(leaf + "-PREPARE.json", facts)
    log("S9 prepare-clone OK: %s at %s (receipt %s-PREPARE.json)" % (REPO_FULL, commit, REPO_FULL))
    return facts


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
    return dict(k4s_pins_verified=len(pins), measurement_files_sha256=C.canonical_sha(measurement),
                import_closure=list(IMPORT_CLOSURE))


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
        member_rule="runtime-pin-r2 files U every *.py U SUPPORT_MEMBERS (D1; tree metadata only)",
        support_members=sorted(SUPPORT_MEMBERS), git_members=members, git_members_sha256=C.canonical_sha(members),
        e4_members=[e["path"] for e in plan.e4], e5_members=[e["path"] for e in plan.e5], e1=e1,
        runtime_files=local, runtime_files_count=len(local), runtime_files_sha256=C.canonical_sha(local),
        measurement_files=measurement, measurement_files_sha256=C.canonical_sha(measurement),
        externals=externals, q5_source=Q5_SOURCE, tracked_pin_sha_differs_from_git=tracked_mismatch,
        frozen_check=dict((k, v) for k, v in frozen.items() if k != "runtime_files"), frozen_runtime_files_equal=True,
        inventory=inv, inventory_files=len(inventory), inventory_bytes=sum(f["size"] for f in inventory.values()),
        inventory_sha256=C.canonical_sha(inv), r6_end_dir_absent=True, python=python,
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
    manifest = load_manifest(policy, prefix, manifest_sha256)
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
                  runtime_files_identical=True, measurement_files_identical=True, externals_unchanged=True)
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
        elif a.command == "build":
            build(a)
        elif a.command == "locate":
            policy = si.Policy(C.local_host(), [repo_role(), q5_role()])
            pins, _, _ = commit_pins(policy, full_commit(a.commit, "--commit"))
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
