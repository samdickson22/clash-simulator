"""S9 r2: full-clone preparation and verification; D1 member export through si.git_plan (metadata first, non-members
never read); E1 materialised (D2); E4 hash-only; R6; explicit Q5 source; confined verify; the P2-2 equivalence hard
gate. Includes Sol's S9-F1/F2 probes and git indirection controls."""
import json
import os
import shutil

import pytest

from conftest import (C, CANARY, EXTERNALS, S9, Args, canary_file, make_file, ok, read, refused, sha, si)


@pytest.fixture
def repo_copy(world, tmpdir_, monkeypatch):
    path = os.path.join(tmpdir_, "repo-full-copy")
    shutil.copytree(world.repo_full, path, symlinks=True)
    monkeypatch.setattr(S9, "REPO_FULL", path)
    return path


@pytest.fixture
def reads(monkeypatch):
    """Every object id handed to the ONLY object-content read (si._git_object)."""
    seen = []
    real = si._git_object

    def spy(repo, oid, *a, **k):
        seen.append(oid)
        return real(repo, oid, *a, **k)
    monkeypatch.setattr(si, "_git_object", spy)
    return seen


def build(world, out, commit=None):
    return S9.build(Args(commit=commit or world.P, out=out, python=world.python), log=lambda *a: None)


def oid(world, repo, commit, rel):
    return world.git(repo, "rev-parse", "%s:%s" % (commit, rel)).decode().strip()


def assert_not_published(out):
    ok(not os.path.exists(out))
    names = os.listdir(out + ".partial")
    ok([n for n in names if n.startswith("S9-REFUSAL-")], names)


def test_runtime_is_the_member_set_only(world, runtime):
    files = runtime["manifest"]["inventory"]["files"]
    tracked = set(world.files) | {si.E1_ALIAS}
    members = {p for p in tracked if p in world.pins or p.endswith(".py") or p in S9.SUPPORT_MEMBERS}
    ok(set(files) == members | set(EXTERNALS), sorted(set(files) ^ (members | set(EXTERNALS))))
    ok("docs/notes.md" not in files and S9.E4V3_REL + "/README.md" not in files and S9.END_JOB_REL not in files)
    ok(files["src/clasher/tool.py"]["executable"] is False)


def test_prepare_clone_refuses_an_existing_clone(world):
    refused("exists", S9.prepare_clone, Args(commit=world.P), log=lambda *a: None)


@pytest.mark.parametrize("kind,code", [
    ("promisor", "indirection"), ("partialclonefilter", "indirection"), ("extensions", "indirection"),
    ("hooks", "indirection"), ("promisor-pack", "indirection"), ("shallow", "indirection"), ("alternates", "indirection"),
    ("replace", "indirection"), ("grafts", "indirection"), ("filter", "indirection")])
def test_full_clone_verification_refuses(world, repo_copy, kind, code):
    git_dir = os.path.join(repo_copy, ".git")
    config = os.path.join(git_dir, "config")
    if kind in ("promisor", "partialclonefilter", "extensions", "filter"):
        extra = {"promisor": '[remote "origin"]\n\tpromisor = true\n',
                 "partialclonefilter": '[remote "origin"]\n\tpartialclonefilter = blob:none\n',
                 "extensions": "[extensions]\n\tpartialclone = origin\n",
                 "filter": '[filter "lfs"]\n\tsmudge = cat\n'}[kind]
        with open(config, "a") as stream:
            stream.write(extra)
    elif kind == "hooks":
        make_file(os.path.join(git_dir, "hooks", "post-checkout"), b"#!/bin/sh\n", 0o755)
    elif kind == "promisor-pack":
        make_file(os.path.join(git_dir, "objects", "pack", "pack-0000.promisor"), b"")
    elif kind == "shallow":
        make_file(os.path.join(git_dir, "shallow"), (world.P + "\n").encode())
    elif kind == "alternates":
        make_file(os.path.join(git_dir, "objects", "info", "alternates"), b"/tmp\n")
    elif kind == "replace":
        world.git(repo_copy, "replace", oid(world, repo_copy, world.P, "src/clasher/core.py"),
                  world.git(repo_copy, "hash-object", "-w", "--stdin", data=CANARY).decode().strip())
    else:
        make_file(os.path.join(git_dir, "info", "grafts"), (world.P + "\n").encode())
    refused(code, S9.verify_clone, S9.clone_policy(), world.P)


def test_r6_build_at_the_end_job_commit_refused(world, tmpdir_, reads):
    out = os.path.join(tmpdir_, "rt")
    error = refused("check", build, world, out, world.X)
    ok("R6" in error.reason)
    assert_not_published(out)
    ok(len(reads) == 3, reads)                                # only the three pinned JSON files were read


def test_probe_export_never_reads_non_members(world, repo_copy, tmpdir_, reads):
    """Sol S9-F1: a tree holding games/reviewer.json (non-member) builds, and its blob is never requested."""
    q = world.git.commit(repo_copy, {"games/reviewer.json": CANARY, "reports/other/notes.txt": b"x\n"}, "non-members")
    out = os.path.join(tmpdir_, "rt")
    m = build(world, out, q)
    games_oid = oid(world, repo_copy, q, "games/reviewer.json")
    ok(games_oid not in reads and "games/reviewer.json" not in m["inventory"]["files"])
    ok(not os.path.exists(os.path.join(out, "runtime", "games")))


@pytest.mark.parametrize("rel,code", [("tools/check_games.py", "name"), ("tools/END-FINAL.py", "name"),
                                      ("reports/other/complete.json", "name"), ("x/complete.json/y.py", "name"),
                                      ("reports/explore/k4s-confirm/end/END-JOB.py", "name")])
def test_probe_family_names_refused_in_phase_one(world, repo_copy, tmpdir_, reads, rel, code):
    """Sol S9-F1 / D1 / E4 fail-closed: a family-named member, or ANY unlisted complete.json (member or not), refuses
    the whole tree in phase 1: its blob and every member blob stay unread."""
    q = world.git.commit(repo_copy, {rel: CANARY}, "probe " + rel)
    out = os.path.join(tmpdir_, "rt")
    before = len(reads)
    with pytest.raises(si.Refusal) as info:
        build(world, out, q)
    ok(info.value.code in (code, "check"), str(info.value))       # R6 also refuses an end/ path (check)
    ok(oid(world, repo_copy, q, rel) not in reads and len(reads) - before <= 3, reads[before:])
    ok(not os.path.exists(os.path.join(out + ".partial", "runtime", "src")))
    assert_not_published(out)


@pytest.mark.parametrize("case,code", [("e1-text", "exemption"), ("extra-symlink", "symlink"), ("gitlink", "name"),
                                       ("gitlink-member", "not-regular")])
def test_tree_shape_refusals(world, repo_copy, tmpdir_, reads, case, code):
    if case == "e1-text":
        os.unlink(os.path.join(repo_copy, si.E1_ALIAS))
        os.symlink("examples/../examples/visualize_battle.py", os.path.join(repo_copy, si.E1_ALIAS))
        world.git(repo_copy, "add", si.E1_ALIAS)
        world.git(repo_copy, "commit", "-q", "-m", "e1 text")
        q = world.git(repo_copy, "rev-parse", "HEAD").decode().strip()
    elif case == "extra-symlink":
        q = world.git.commit(repo_copy, {}, "link", links={"src/clasher/alias.py": "core.py"})
    else:
        sub = "1" * 40
        name = "vendor/complete.json" if case == "gitlink" else "vendor/sub.py"
        world.git(repo_copy, "update-index", "--add", "--cacheinfo", "160000,%s,%s" % (sub, name))
        world.git(repo_copy, "commit", "-q", "-m", "gitlink")
        q = world.git(repo_copy, "rev-parse", "HEAD").decode().strip()
    out = os.path.join(tmpdir_, "rt")
    with pytest.raises(si.Refusal) as info:
        build(world, out, q)
    ok(info.value.code == code, str(info.value))
    ok(len(reads) <= 3)


def test_e4_member_is_hash_only_and_pinned(world, repo_copy, tmpdir_, monkeypatch, reads):
    data = b'{"synthetic": "E2 stand-in"}\n'
    q0 = world.git.commit(repo_copy, {si.E2_PATH: data}, "E2 stand-in (member below)")
    blob = oid(world, repo_copy, q0, si.E2_PATH)
    monkeypatch.setitem(si.E4_COMPLETE_JSON, si.E2_PATH, sha(data))
    monkeypatch.setitem(si.E4_GIT_BLOB_OIDS, si.E2_PATH, blob)
    pins = dict(world.pins, **{si.E2_PATH: sha(data)})
    raw = (json.dumps({"files": pins}, indent=1, sort_keys=True) + "\n").encode()
    q = world.git.commit(repo_copy, {S9.RUNTIME_PIN_REL: raw}, "pin E2")
    monkeypatch.setattr(S9, "RUNTIME_PIN_SHA", sha(raw))
    out = os.path.join(tmpdir_, "rt")
    m = build(world, out, q)
    ok(m["e4_members"] == [si.E2_PATH] and m["inventory"]["files"][si.E2_PATH]["e4"] is True)
    ok(read(os.path.join(out, "runtime", si.E2_PATH)) == data)
    # a changed E4 blob at the exact path refuses in phase 1 (OID pin), before its bytes are read
    q2 = world.git.commit(repo_copy, {si.E2_PATH: data + b" "}, "changed E2")
    before = len(reads)
    refused("exemption", build, world, os.path.join(tmpdir_, "rt2"), q2)
    ok(oid(world, repo_copy, q2, si.E2_PATH) not in reads[before:])


def test_externals_missing_is_a_stop(world, tmpdir_, monkeypatch):
    src = os.path.join(tmpdir_, "q5")
    for rel, data in list(EXTERNALS.items())[1:]:
        make_file(os.path.join(src, rel), data)
    monkeypatch.setattr(S9, "Q5_SOURCE", src)
    out = os.path.join(tmpdir_, "rt")
    with pytest.raises(S9.Missing):
        build(world, out)
    assert_not_published(out)
    ok(S9.main(["locate", "--commit", world.P]) == 3)


def test_probe_hard_linked_external_is_not_located(world, tmpdir_, monkeypatch):
    """Sol S9-F2: a hard-linked candidate is refused by the descriptor gate before hashing (counts as missing)."""
    src = os.path.join(tmpdir_, "q5")
    for rel, data in EXTERNALS.items():
        make_file(os.path.join(src, rel), data)
    first = sorted(EXTERNALS)[0]
    os.link(os.path.join(src, first), os.path.join(tmpdir_, "alias"))
    monkeypatch.setattr(S9, "Q5_SOURCE", src)
    policy = si.Policy(C.local_host(), [S9.repo_role(), S9.q5_role()])
    result = S9.locate(policy, world.pins)
    row = [r for r in result["files"] if r["path"] == first][0]
    ok(not result["ok"] and row["refusal"] == "nlink" and "sha256" not in row)


@pytest.mark.parametrize("root", ["reports/explore/k4s-confirm/end/receipts", "x/games/runtime",
                                  "jobs/clasher/k4s-confirm-replacement-r4"])
def test_probe_q5_source_in_a_forbidden_location(world, tmpdir_, monkeypatch, root):
    """Sol S9-F2: a canonical root inside the strict END dir, games or a K4S job is refused by name (policy
    construction) before any candidate is opened or hashed."""
    src = os.path.join(tmpdir_, root)
    for rel, data in EXTERNALS.items():
        make_file(os.path.join(src, rel), data)
    monkeypatch.setattr(S9, "Q5_SOURCE", src)
    out = os.path.join(tmpdir_, "rt")
    refused("name", build, world, out)
    ok(not os.path.exists(out + ".partial"))


def test_tampered_k4s_logic_never_executes(world, repo_copy, tmpdir_):
    marker = os.path.join(tmpdir_, "EXECUTED")
    rel = S9.K4S_MAC_REL + "/k4s_logic.py"
    q = world.git.commit(repo_copy, {rel: read(os.path.join(repo_copy, rel)) +
                                     ("\nopen(%r, 'w').write('x')\n" % marker).encode()}, "tamper k4s_logic")
    out = os.path.join(tmpdir_, "rt")
    error = refused("check", build, world, out, q)
    ok("K4S-pinned" in error.reason and not os.path.exists(marker))


def test_frozen_check_nonzero_with_valid_stdout_refused(world, tmpdir_, monkeypatch):
    monkeypatch.setattr(S9, "FROZEN_SNIPPET", "import sys\nprint('{\"optimize\": 0, \"runtime_files\": {}}')\n"
                                              "sys.exit(37)\n")
    out = os.path.join(tmpdir_, "rt")
    refused("subprocess", build, world, out)
    assert_not_published(out)


def test_git_env_and_replace_refs_cannot_substitute_bytes(world, runtime, repo_copy, tmpdir_, monkeypatch):
    core = oid(world, repo_copy, world.P, "src/clasher/core.py")
    canary = world.git(repo_copy, "hash-object", "-w", "--stdin", data=CANARY).decode().strip()
    world.git(repo_copy, "replace", core, canary)
    ok(world.git(repo_copy, "show", world.P + ":src/clasher/core.py") == CANARY)      # raw git is fooled
    foreign = os.path.join(tmpdir_, "foreign")
    os.makedirs(foreign)
    world.git(foreign, "init", "-q")
    for key, value in (("GIT_DIR", foreign + "/.git"), ("GIT_OBJECT_DIRECTORY", foreign + "/.git/objects"),
                       ("GIT_ALTERNATE_OBJECT_DIRECTORIES", foreign + "/.git/objects"),
                       ("GIT_INDEX_FILE", foreign + "/index"), ("GIT_CONFIG_PARAMETERS", "'core.hooksPath'='/tmp'")):
        monkeypatch.setenv(key, value)
    out = os.path.join(tmpdir_, "rt")
    error = refused("indirection", build, world, out)                       # F4 (r3): the live precondition
    ok("replace refs" in error.reason, error.reason)
    # Defense in depth: with the precondition stubbed out (test-only), the layer still ignores replace refs and env.
    monkeypatch.setattr(S9, "require_full_clone", lambda *a, **k: {"stubbed": True})
    out = os.path.join(tmpdir_, "rt2")
    m = build(world, out)
    ok(read(os.path.join(out, "runtime", "src/clasher/core.py")) == world.files["src/clasher/core.py"])
    ok(m["inventory_sha256"] == runtime["manifest"]["inventory_sha256"])


@pytest.mark.parametrize("kind", ["grafts", "alternates", "hookspath", "gitfile"])
def test_build_refuses_repository_indirection(world, repo_copy, tmpdir_, kind):
    git_dir = os.path.join(repo_copy, ".git")
    if kind == "grafts":
        make_file(os.path.join(git_dir, "info", "grafts"), (world.P + "\n").encode())
    elif kind == "alternates":
        make_file(os.path.join(git_dir, "objects", "info", "alternates"), b"/tmp\n")
    elif kind == "hookspath":
        with open(os.path.join(git_dir, "config"), "a") as stream:
            stream.write("[core]\n\thooksPath = /tmp\n")
    else:
        os.rename(git_dir, os.path.join(tmpdir_, "moved.git"))
        make_file(git_dir, ("gitdir: %s/moved.git\n" % tmpdir_).encode())
    out = os.path.join(tmpdir_, "rt")
    with pytest.raises(si.Refusal) as info:
        build(world, out)
    ok(info.value.code in ("indirection", "root", "not-dir"), str(info.value))


def copy_runtime(runtime, tmpdir_):
    dst = os.path.join(tmpdir_, "rtcopy")
    shutil.copytree(runtime["out"], dst, symlinks=True)
    for directory, dirs, _ in os.walk(dst):
        os.chmod(directory, 0o755)
    return dst


def verify(out, digest, frozen=False, python=None):
    policy = si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", out))
    return S9.verify(policy, "s9", digest, frozen=frozen, python=python or S9.DEFAULT_PYTHON, log=lambda *a: None)


@pytest.mark.parametrize("case,code", [("modified", "check"), ("hardlink", "nlink"), ("symlink", "symlink"),
                                       ("extra", "check"), ("games", "name"), ("e1-symlink", "symlink"),
                                       ("hub-ack", "name")])
def test_probe_verify_refuses_aliases_and_tampering(runtime, tmpdir_, case, code):
    out = copy_runtime(runtime, tmpdir_)
    root = os.path.join(out, "runtime")
    canary = canary_file(os.path.join(tmpdir_, "elsewhere"))
    core = os.path.join(root, "src/clasher/core.py")
    if case == "modified":
        os.chmod(core, 0o644)
        make_file(core, b"CORE = 2\n")
    elif case == "hardlink":
        os.link(canary, os.path.join(root, "src", "hl.json"))
    elif case == "symlink":
        os.symlink(canary, os.path.join(root, "src", "ln.json"))
    elif case == "extra":
        make_file(os.path.join(root, "src", "extra.py"), b"X = 1\n")
    elif case == "games":
        make_file(os.path.join(root, "games", "x.json"), CANARY)
    elif case == "e1-symlink":
        os.unlink(os.path.join(root, si.E1_ALIAS))
        os.symlink(si.E1_LINK_TEXT, os.path.join(root, si.E1_ALIAS))
    else:
        make_file(os.path.join(root, "hub-ack.returned.json"), CANARY)
    refused(code, verify, out, runtime["sha"])
    ok(read(canary) == CANARY)


def test_verify_manifest_pin_and_root_alias(runtime, tmpdir_, world):
    verify(runtime["out"], runtime["sha"], frozen=True, python=world.python)
    refused("sha", verify, runtime["out"], "0" * 64)
    os.symlink(os.path.dirname(runtime["out"]), os.path.join(tmpdir_, "alias"))
    refused("root", verify, os.path.join(tmpdir_, "alias", os.path.basename(runtime["out"])), runtime["sha"])


def equiv(runtime, x, digest=None):
    policy = si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", runtime["out"]))
    return S9.equivalence(policy, "s9", digest or runtime["sha"], x, log=lambda *a: None)


def test_equivalence_hard_gate(world, runtime, repo_copy):
    ok(equiv(runtime, world.X)["git_members"] == len(runtime["manifest"]["git_members"]))
    refused("check", equiv, runtime, world.P)                                  # X == P
    refused("sha", equiv, runtime, world.X, "0" * 64)
    world.git(repo_copy, "checkout", "-q", world.X)
    two = world.git.commit(repo_copy, {"docs/more.md": b"x\n"}, "X plus another path")
    refused("check", equiv, runtime, two)                                       # diff is not exactly END-JOB
    world.git(repo_copy, "checkout", "-q", world.P)
    py = world.git.commit(repo_copy, {"src/clasher/core.py": b"CORE = 3\n", S9.END_JOB_REL: b"{}\n"}, "member change")
    refused("check", equiv, runtime, py)
    world.git(repo_copy, "checkout", "-q", world.base_commit)
    side = world.git.commit(repo_copy, {S9.END_JOB_REL: b"{}\n"}, "not a descendant of P")
    refused("check", equiv, runtime, side)
    world.git(repo_copy, "checkout", "-q", world.P)
    make_file(os.path.join(repo_copy, S9.END_JOB_REL), b"{}\n", 0o755)
    world.git(repo_copy, "add", S9.END_JOB_REL)
    world.git(repo_copy, "commit", "-q", "-m", "executable END-JOB")
    exe = world.git(repo_copy, "rev-parse", "HEAD").decode().strip()
    refused("check", equiv, runtime, exe)


def test_cli_codes_and_records(world, runtime, tmpdir_):
    ok(S9.main(["build", "--commit", "HEAD", "--out", os.path.join(tmpdir_, "rt")]) == 2)
    ok(S9.main(["build", "--commit", world.P, "--out", "/dev/shm/k4s-s9-never"]) == 2)
    ok(not os.path.exists("/dev/shm/k4s-s9-never.partial"))
    rec = os.path.join(tmpdir_, "rec")
    ok(S9.main(["equivalence", "--out", runtime["out"], "--manifest-sha256", runtime["sha"], "--end-job-commit",
                world.X, "--record", rec]) == 0)
    ok(json.loads(read(os.path.join(rec, "s9-equivalence.json")))["runtime_files_identical"] is True)
    rec2 = os.path.join(tmpdir_, "rec2")
    ok(S9.main(["equivalence", "--out", runtime["out"], "--manifest-sha256", runtime["sha"], "--end-job-commit",
                world.P, "--record", rec2]) == 2)
    ok([n for n in os.listdir(rec2) if n.startswith("S9-REFUSAL-")])
    rec3 = os.path.join(tmpdir_, "rec3")
    ok(S9.main(["locate", "--commit", world.P, "--record", rec3]) == 0)
    ok(json.loads(read(os.path.join(rec3, "s9-locate.json")))["found"] == len(EXTERNALS))


def test_production_constants():
    from conftest import ORIG
    ok(ORIG[("s9_end_runtime", "REPO_FULL")] == "/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full")
    ok(ORIG[("s9_end_runtime", "ORIGIN_URL")] == "https://github.com/samdickson22/clash-simulator.git")
    ok(ORIG[("s9_end_runtime", "CLONE_PROTOCOL")] == "https")
    ok(ORIG[("s9_end_runtime", "K4S_MANIFEST_SHA")] == si.APPROVED_K4S_MANIFEST_SHA256)
    ok(ORIG[("s9_end_runtime", "Q5_SOURCE")].endswith("/end-a5-CANDIDATE-0775b704-0108-r1/runtime"))
    ok(len(ORIG[("s9_end_runtime", "EXTERNAL")]) == 33)
    ok(S9.SUPPORT_MEMBERS == frozenset((S9.RUNTIME_PIN_REL, S9.QUALIFIED_REL, S9.K4S_MANIFEST_REL,
                                        S9.K4S_MAC_REL + "/K4S-MAC-PROCEDURE.md", S9.E4V3_REL + "/spec-pins.json",
                                        S9.E4V3_REL + "/build_tiers.sh")))
    ok(S9.END_JOB_REL == "reports/explore/k4s-confirm/end/END-JOB.json")


def test_external_with_other_bytes_is_missing(world, tmpdir_, monkeypatch):
    src = os.path.join(tmpdir_, "q5")
    for rel, data in EXTERNALS.items():
        make_file(os.path.join(src, rel), data)
    first = sorted(EXTERNALS)[0]
    make_file(os.path.join(src, first), EXTERNALS[first] + b"# changed\n")
    monkeypatch.setattr(S9, "Q5_SOURCE", src)
    policy = si.Policy(C.local_host(), [S9.repo_role(), S9.q5_role()])
    result = S9.locate(policy, world.pins)
    ok(result["missing"] == [first])
    out = os.path.join(tmpdir_, "rt")
    with pytest.raises(S9.Missing):
        build(world, out)


def test_measurement_change_refused(world, repo_copy, tmpdir_):
    q = world.git.commit(repo_copy, {S9.E4V3_REL + "/build_tiers.sh": b"#!/bin/sh\necho changed\n"}, "measurement")
    out = os.path.join(tmpdir_, "rt")
    error = refused("check", build, world, out, q)
    ok("42b8986d" in error.reason, error.reason)


def test_frozen_runtime_files_must_equal(world, tmpdir_, monkeypatch):
    monkeypatch.setattr(S9, "FROZEN_SNIPPET", "print('{\"optimize\": 0, \"runtime_files\": {\"x\": \"y\"}}')\n")
    out = os.path.join(tmpdir_, "rt")
    error = refused("check", build, world, out)
    ok("frozen runtime_pins" in error.reason)


def test_equivalence_same_tree_but_not_a_descendant(world, runtime, repo_copy):
    tree = world.git(repo_copy, "rev-parse", world.X + "^{tree}").decode().strip()
    other = world.git(repo_copy, "commit-tree", tree, "-p", world.base_commit, "-m", "same tree, other parent"
                      ).decode().strip()
    ok(world.git(repo_copy, "diff-tree", "-r", "--name-only", world.P, other).decode().split() == [S9.END_JOB_REL])
    refused("check", equiv, runtime, other)


def test_equivalence_checks_the_manifest_members(world, runtime, tmpdir_):
    out = copy_runtime(runtime, tmpdir_)
    path = os.path.join(out, S9.MANIFEST)
    doc = json.loads(read(path))
    doc["git_members"] = doc["git_members"][:-1]
    os.chmod(path, 0o644)
    data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    make_file(path, data)
    fake = dict(runtime, out=out)
    refused("check", equiv, fake, world.X, sha(data))


def test_e5_member_changed_moved_or_tampered(world, runtime, repo_copy, tmpdir_, reads):
    """E5 (r3): the opaque member is pinned by path + blob OID in phase 1; a changed blob or a moved copy refuses before
    its bytes are read; on disk a changed or hard-linked copy refuses by the pinned blob OID / descriptor gate."""
    from conftest import E5_PATH, E5_BYTES
    q = world.git.commit(repo_copy, {E5_PATH: E5_BYTES + b"# changed\n"}, "changed E5")
    before = len(reads)
    refused("exemption", build, world, os.path.join(tmpdir_, "a"), q)
    ok(oid(world, repo_copy, q, E5_PATH) not in reads[before:])
    world.git(repo_copy, "checkout", "-q", world.P)
    moved = "scripts/compare_native_public_games2.py"
    q2 = world.git.commit(repo_copy, {moved: E5_BYTES}, "moved E5 copy")
    refused("name", build, world, os.path.join(tmpdir_, "b"), q2)
    out = copy_runtime(runtime, tmpdir_)
    path = os.path.join(out, "runtime", E5_PATH)
    os.chmod(path, 0o644)
    make_file(path, E5_BYTES.replace(b"1", b"2"))
    refused("exemption", verify, out, runtime["sha"])
    make_file(path, E5_BYTES)
    os.link(path, os.path.join(tmpdir_, "e5-alias"))
    refused("nlink", verify, out, runtime["sha"])
