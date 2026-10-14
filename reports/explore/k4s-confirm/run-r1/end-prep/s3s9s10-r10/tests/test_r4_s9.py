"""r4 S9: the three SHA-pinned support members (integration audit B3/B5, a D1 extension) and `refresh-clone` (U10).
Synthetic world only: the support files carry synthetic bytes at their production paths (SUPPORT_PINS patched for the
session); refresh-clone fetches from the session's file:// origin into a private copy of the full clone."""
import json
import os
import shutil

import pytest

from conftest import C, S9, Args, make_file, ok, read, refused, sha, si

R4_SUPPORT = ("reports/explore/k4s-confirm/DELTA-MANIFEST.json", "reports/explore/k4s-confirm/SD1-MANIFEST.json",
              "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json")
OLD_SIX = frozenset(sorted(S9.SUPPORT_MEMBERS - set(R4_SUPPORT)))


def build(world, out, commit=None):
    return S9.build(Args(commit=commit or world.P, out=out, python=world.python), log=lambda *a: None)


# ---------------------------------------------------------------- B3/B5: support members

def test_support_members_are_exported_pinned_and_outside_the_file_hash_sets(world, runtime):
    m = runtime["manifest"]
    inv = m["inventory"]["files"]
    ok(sorted(S9.SUPPORT_PINS) == list(R4_SUPPORT) and m["support_pins"] == dict(sorted(S9.SUPPORT_PINS.items())))
    for rel in R4_SUPPORT:
        ok(inv[rel]["sha256"] == S9.SUPPORT_PINS[rel] == sha(world.files[rel]), rel)
        ok(rel not in m["runtime_files"], rel)
        ok(read(os.path.join(runtime["out"], "runtime", rel)) == world.files[rel])
    ok(set(R4_SUPPORT) <= set(m["support_members"]))
    ok(not {n.rsplit("/", 1)[1] for n in R4_SUPPORT} & set(m["measurement_files"]))
    ok(m["frozen_check"]["stdlib_verified"]["support_pins_verified"] == list(R4_SUPPORT))


def test_membership_neutral_for_runtime_and_measurement_files(world, runtime, tmpdir_, monkeypatch):
    """The audit's claim, proved: building at the same P with the r3 member set (the six) yields the SAME runtime_files
    and measurement_files canonical SHAs (bundle pins and S4 requests stay valid); the inventories differ by exactly
    the three r4 support files."""
    monkeypatch.setattr(S9, "SUPPORT_MEMBERS", OLD_SIX)
    monkeypatch.setattr(S9, "check_support_pins", lambda inventory, k4s=None: [])
    old = build(world, os.path.join(tmpdir_, "rt-r3-members"))
    new = runtime["manifest"]
    ok(old["runtime_files"] == new["runtime_files"] and old["runtime_files_sha256"] == new["runtime_files_sha256"])
    ok(old["measurement_files_sha256"] == new["measurement_files_sha256"] == S9.MEASUREMENT_SHA)
    ok(set(new["inventory"]["files"]) - set(old["inventory"]["files"]) == set(R4_SUPPORT))
    ok(set(old["inventory"]["files"]) <= set(new["inventory"]["files"]))
    ok([g for g in new["git_members"] if g["path"] not in R4_SUPPORT] == old["git_members"])


def test_a_pre_r4_runtime_is_refused_by_verify(world, tmpdir_, monkeypatch):
    """S9.verify (hence S10 before any login) refuses a runtime without the r4 support members."""
    with monkeypatch.context() as m:
        m.setattr(S9, "SUPPORT_MEMBERS", OLD_SIX)
        m.setattr(S9, "check_support_pins", lambda inventory, k4s=None: [])
        old = build(world, os.path.join(tmpdir_, "rt"))
    policy = si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", os.path.join(tmpdir_, "rt")))
    error = refused("check", S9.verify, policy, "s9", old["_sha256"], log=lambda *a: None)
    ok("r4 support member missing" in error.reason, error.reason)


@pytest.mark.parametrize("rel", R4_SUPPORT)
def test_support_pin_mismatch_refuses_the_build(world, tmpdir_, monkeypatch, rel):
    pins = dict(S9.SUPPORT_PINS)
    pins[rel] = "0" * 64
    monkeypatch.setattr(S9, "SUPPORT_PINS", pins)
    out = os.path.join(tmpdir_, "rt")
    error = refused("check", build, world, out)
    ok("support" in error.reason or "sd1" in error.reason or "corpus" in error.reason, error.reason)
    ok(not os.path.exists(out))


@pytest.mark.parametrize("case", ["sd1-sha", "sd1-path", "corpora-sha", "corpora-path", "corpus-inventory", "absent"])
def test_support_pins_cross_checked_against_the_k4s_manifest(world, runtime, case):
    inv = runtime["manifest"]["inventory"]["files"]
    k4s = json.loads(world.files[S9.K4S_MANIFEST_REL])
    ok(S9.check_support_pins(inv, k4s) == list(R4_SUPPORT))
    if case == "sd1-sha":
        k4s["sd1_manifest"]["sha256"] = "1" * 64
    elif case == "sd1-path":
        k4s["sd1_manifest"]["path"] = "reports/explore/k4s-confirm/mac/SD1-MANIFEST.json"
    elif case == "corpora-sha":
        k4s["references"]["t1_corpus_inventory"]["sha256"] = "2" * 64
    elif case == "corpora-path":
        k4s["references"]["t1_corpus_inventory"]["path"] = "reports/explore/t1/corpora/other/corpora.json"
    elif case == "corpus-inventory":
        k4s["corpus"]["inventory"] = "reports/explore/t1/corpora/other/corpora.json"
    else:
        inv = {k: v for k, v in inv.items() if k != S9.DELTA_REL}
    refused("check", S9.check_support_pins, inv, k4s)


def test_support_members_must_be_tracked(world, repo_copy, tmpdir_):
    q = world.git.commit(repo_copy, {S9.DELTA_REL: None}, "drop DELTA")
    error = refused("check", build, world, os.path.join(tmpdir_, "rt"), q)
    ok("support members not tracked" in error.reason or "R6" in error.reason or "133f3ae4" in error.reason,
       error.reason)


# ---------------------------------------------------------------- U10: refresh-clone

@pytest.fixture
def origin_branch(world):
    """Move the session origin's refs/heads/k4s-end-r1; always restored to P afterwards."""
    def move(commit):
        world.git(world.origin, "update-ref", "refs/heads/" + S9.END_BRANCH, commit)
    yield move
    move(world.P)


def refresh_args(tmpdir_, commit, base=None, checkout=False, name="rec"):
    return Args(command="refresh-clone", commit=commit, base_commit=base, checkout=checkout,
                record=os.path.join(tmpdir_, name))


def refresh(tmpdir_, commit, **kw):
    a = refresh_args(tmpdir_, commit, **kw)
    record = C.Record(a.record, "S9", ("s9-refresh-clone.json",)).open()
    try:
        return S9.refresh_clone(a, record, log=lambda *x: None)
    except BaseException as error:
        record.refusal(error)
        raise
    finally:
        record.close()


def refs_of(world, repo):
    return world.git(repo, "for-each-ref", "--format=%(objectname) %(refname)").decode()


def test_refresh_brings_x_and_proves_nothing_else_changed(world, repo_copy, origin_branch, tmpdir_):
    with pytest.raises(RuntimeError):                                   # X2 is not in the clone yet
        world.git(repo_copy, "cat-file", "-e", world.X2 + "^{commit}")
    head = world.git(repo_copy, "rev-parse", "HEAD").decode().strip()
    packs = {n: read(os.path.join(repo_copy, ".git/objects/pack", n))
             for n in os.listdir(os.path.join(repo_copy, ".git/objects/pack"))}
    origin_branch(world.X2)
    result = refresh(tmpdir_, world.X2, base=world.P)
    ok(result["old"] == world.P and result["commit"] == world.X2 and result["refs_changed"] == [S9.END_BRANCH_REF])
    ok(result["objects_unchanged"] is True and result["objects_added"] and result["head"] == head == world.P)
    ok(world.git(repo_copy, "rev-parse", S9.END_BRANCH_REF).decode().strip() == world.X2)
    ok(world.git(repo_copy, "rev-parse", "HEAD").decode().strip() == head)
    for n, data in packs.items():                                       # never rewritten
        ok(read(os.path.join(repo_copy, ".git/objects/pack", n)) == data, n)
    rec = json.loads(read(os.path.join(tmpdir_, "rec", "s9-refresh-clone.json")))
    ok(rec["commit"] == world.X2 and rec["full_clone"]["commits"] == [world.X2, world.P])
    argv = rec["fetch_argv"]
    ok("refs/heads/k4s-end-r1:refs/remotes/origin/k4s-end-r1" == argv[-1] and "+" not in argv[-1])
    ok("transfer.fsckObjects=true" in argv and "gc.auto=0" in argv and "--no-tags" in argv)
    ok(argv[argv.index("--") + 1] == S9.ORIGIN_URL)
    S9.require_full_clone((world.P, world.X2))                          # the clone still passes the live check


def test_refresh_checkout_only_when_asked(world, repo_copy, origin_branch, tmpdir_):
    origin_branch(world.X2)
    result = refresh(tmpdir_, world.X2, checkout=True)
    ok(result["head"] == world.X2 and world.git(repo_copy, "rev-parse", "HEAD").decode().strip() == world.X2)
    ok(read(os.path.join(repo_copy, S9.END_JOB_REL)) == world.end_job2)


@pytest.mark.parametrize("case", ["tip-not-x", "non-fast-forward", "not-descendant-of-base", "x-equals-base"])
def test_refresh_refusals(world, repo_copy, origin_branch, tmpdir_, case):
    before = refs_of(world, repo_copy)
    if case == "tip-not-x":
        origin_branch(world.X2)
        error = refused("check", refresh, tmpdir_, world.X)               # the tip is X2, not the given X
        ok("not the given X" in error.reason)
    elif case == "non-fast-forward":
        origin_branch(world.base_commit)                                  # a rewritten branch (not a descendant)
        refused("subprocess", refresh, tmpdir_, world.base_commit)
        ok(refs_of(world, repo_copy) == before)                           # git itself refused: nothing moved
    elif case == "not-descendant-of-base":
        origin_branch(world.X2)
        refused("check", refresh, tmpdir_, world.X2, base=world.X)
    else:
        origin_branch(world.X2)
        refused("check", refresh, tmpdir_, world.X2, base=world.X2)
    names = os.listdir(os.path.join(tmpdir_, "rec"))
    ok(len(names) == 1 and names[0].startswith("S9-REFUSAL-"), names)


@pytest.mark.parametrize("kind", ["promisor", "hooks", "shallow", "replace-ref"])
def test_refresh_refuses_a_corrupted_clone_before_the_fetch(world, repo_copy, origin_branch, tmpdir_, monkeypatch,
                                                            kind):
    if kind == "promisor":
        with open(os.path.join(repo_copy, ".git/config"), "a") as stream:
            stream.write('[remote "origin"]\n\tpromisor = true\n')
    elif kind == "hooks":
        make_file(os.path.join(repo_copy, ".git/hooks/post-merge"), b"#!/bin/sh\n", 0o755)
    elif kind == "shallow":
        make_file(os.path.join(repo_copy, ".git/shallow"), (world.P + "\n").encode())
    else:
        world.git(repo_copy, "update-ref", "refs/replace/" + world.P, world.X)
    origin_branch(world.X2)
    runs = []
    real = si.run_checked
    monkeypatch.setattr(si, "run_checked", lambda argv, *a, **k: runs.append(argv) or real(argv, *a, **k))
    with pytest.raises(si.Refusal):
        refresh(tmpdir_, world.X2)
    ok(not [r for r in runs if "fetch" in r], "the fetch ran on a corrupted clone")


def test_refresh_never_rewrites_existing_objects(world, repo_copy, origin_branch, tmpdir_, monkeypatch):
    """A fetch that rewrote a pre-existing object file (simulated: the fetch also rewrites one pack byte) refuses."""
    origin_branch(world.X2)
    real = si.run_checked
    packdir = os.path.join(repo_copy, ".git/objects/pack")
    victim = sorted(n for n in os.listdir(packdir) if n.endswith(".pack"))[0]

    def fetch_and_damage(argv, *a, **k):
        result = real(argv, *a, **k)
        if "fetch" in argv:
            path = os.path.join(packdir, victim)
            os.chmod(path, 0o644)
            data = bytearray(read(path))
            data[-30] ^= 1
            with open(path, "wb") as stream:
                stream.write(bytes(data))
        return result
    monkeypatch.setattr(si, "run_checked", fetch_and_damage)
    error = refused("check", refresh, tmpdir_, world.X2)
    ok("pre-existing object files changed" in error.reason, error.reason)


def test_refresh_cli(world, repo_copy, origin_branch, tmpdir_):
    origin_branch(world.X2)
    ok(S9.main(["refresh-clone", "--commit", world.X2, "--base-commit", world.P, "--record",
                os.path.join(tmpdir_, "cli")]) == 0)
    ok(os.listdir(os.path.join(tmpdir_, "cli")) == ["s9-refresh-clone.json"])
    with pytest.raises(SystemExit):
        S9.main(["refresh-clone", "--commit", world.X2])                 # --record is required
    ok(S9.main(["refresh-clone", "--commit", "abc", "--record", os.path.join(tmpdir_, "cli2")]) == 2)


def test_s9_equivalence_of_the_refreshed_x(world, runtime, repo_copy, origin_branch, tmpdir_):
    """After refresh-clone, the P2-2 hard gate accepts X2 = P + END-JOB (the U10 -> equivalence -> S11 advance chain)."""
    origin_branch(world.X2)
    refresh(tmpdir_, world.X2, base=world.P)
    policy = si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", runtime["out"]))
    result = S9.equivalence(policy, "s9", runtime["sha"], world.X2, log=lambda *a: None)
    ok(result["runtime_commit"] == world.P and result["end_job_commit"] == world.X2)


def test_refresh_forced_fetch_is_still_fast_forward_only(world, repo_copy, origin_branch, tmpdir_, monkeypatch):
    """Defense in depth behind git's own non-fast-forward refusal: even a forced refspec (fault injection) cannot move
    the END branch to a non-descendant; the ancestry check refuses."""
    real = S9.fetch_argv
    monkeypatch.setattr(S9, "fetch_argv", lambda: real()[:-1] + ["+" + real()[-1]])
    origin_branch(world.base_commit)
    error = refused("check", refresh, tmpdir_, world.base_commit)
    ok("not a fast-forward" in error.reason, error.reason)


def test_refresh_head_must_not_move(world, repo_copy, origin_branch, tmpdir_, monkeypatch):
    origin_branch(world.X2)
    real = si.run_checked

    def fetch_and_move_head(argv, *a, **k):
        result = real(argv, *a, **k)
        if "fetch" in argv:
            world.git(repo_copy, "update-ref", "--no-deref", "HEAD", world.X)
        return result
    monkeypatch.setattr(si, "run_checked", fetch_and_move_head)
    error = refused("check", refresh, tmpdir_, world.X2)
    ok("HEAD moved" in error.reason, error.reason)


def test_refresh_other_refs_must_not_move(world, repo_copy, origin_branch, tmpdir_, monkeypatch):
    origin_branch(world.X2)
    real = si.run_checked

    def fetch_and_move_a_ref(argv, *a, **k):
        result = real(argv, *a, **k)
        if "fetch" in argv:
            world.git(repo_copy, "update-ref", "refs/remotes/origin/main", world.P)
        return result
    monkeypatch.setattr(si, "run_checked", fetch_and_move_a_ref)
    error = refused("check", refresh, tmpdir_, world.X2)
    ok("changed other refs" in error.reason, error.reason)
