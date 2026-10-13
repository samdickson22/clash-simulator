"""r3 END-FULL-F2 (Part A side): the guard-job fixture CLI builds a REAL S3-produced job (shipped S3.build) that
Part B feeds into its S5/S7 host checks. These tests pin the contract that Part B relies on: Q3 shallow depth-1 repo
holding exactly the four binding commits, loose refs/k4s-end/<label>, plain init config, no FETCH_HEAD, no remote;
deterministic across runs; verifiable by the shipped S3.verify; and refused by a GitRepo without the shallow
allowance (the F2 incompatibility, which Part B resolves with an explicit guard-role allowance)."""
import json
import os
import subprocess
import tempfile

import pytest

from conftest import C, S3, ok, read, refused, rmtree, run_py, si

GIT = ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "--no-replace-objects"]


def git(repo, *args):
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(GIT + ["-C", repo] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                          check=True).stdout.decode()


@pytest.fixture(scope="module")
def jobs():
    made, out = [], {}
    try:
        for key, args in (("a", ()), ("b", ()), ("pf04", ("--host", "127x04", "--preflight", "07"))):
            d = os.path.realpath(tempfile.mkdtemp(prefix="k4s-fx-", dir="/tmp"))
            made.append(d)
            proc = run_py("tests/fixture_guard_job.py", "--dir", d, *args)
            ok(proc.returncode == 0, proc.stderr.decode()[-2000:])
            out[key] = json.loads(proc.stdout)
        yield out
    finally:
        for d in made:
            rmtree(d)


def test_cli_builds_a_real_s3_job(jobs):
    f = jobs["a"]
    ok(f["schema"] == "clasher.k4s.test.s3-guard-job-fixture.v1" and f["synthetic"] is True)
    ok(f["job_name"] == "k4s-end-guard-r1-rd00-a00" and f["target_job"] == S3.GUARD_PARENTS["127x03"] + "/" + f["job_name"])
    ok(sorted(os.listdir(f["job_dir"])) == S3.top_level("127x03") == f["top_level"])
    manifest = json.loads(read(f["manifest_path"]))
    ok(C.sha_bytes(read(f["manifest_path"])) == f["manifest_sha256"] and manifest["schema"] == S3.SCHEMA)
    ok(f["code_sha256"]["s3_guard_job"] == C.sha_bytes(read(os.path.join(os.path.dirname(C.__file__),
                                                                          "s3_guard_job.py"))))
    ok(manifest["full_clone"]["repository"] == f["world"]["repo_full"])          # F4 ran inside the fixture too


def test_guard_repo_contract(jobs):
    for f in jobs.values():
        repo = f["repo_dir"]
        commits = sorted(b["commit"] for b in f["bindings"])
        ok(git(repo, "rev-parse", "--is-shallow-repository") == "true\n")
        ok(f["shallow"] == sorted(read(os.path.join(repo, ".git", "shallow")).decode().split()) == commits)
        refs = dict(reversed(line.split()) for line in git(repo, "for-each-ref", "--format=%(objectname) %(refname)")
                    .splitlines())
        ok(refs == f["refs"] and sorted(refs.values()) == commits)
        for absent in ("FETCH_HEAD", "hooks", "shallow.lock", "packed-refs", "info", "commondir", "config.worktree"):
            ok(not os.path.lexists(os.path.join(repo, ".git", absent)), absent)
        ok(read(os.path.join(repo, ".git", "HEAD")) == b"ref: refs/heads/master\n")      # the unborn init default
        for ref in refs:
            ok(os.stat(os.path.join(repo, ".git", ref)).st_mode & 0o777 == 0o444, ref)    # loose ref files, 0444
        ok(sorted(git(repo, "config", "--local", "--name-only", "--list").split()) == f["git_config_keys"])
        for b in f["bindings"]:
            ok(git(repo, "cat-file", "-t", b["commit"]) == "commit\n")
            path = os.path.join(repo, b["path"])
            ok(C.sha_bytes(read(path)) == b["sha256"] and os.stat(path).st_mode & 0o777 == 0o444)
        for d in f["git_dirs"]:
            ok(os.path.isdir(os.path.join(repo, d)) and not os.path.islink(os.path.join(repo, d)), d)


def test_deterministic(jobs):
    a, b = jobs["a"], jobs["b"]
    for key in ("bindings", "refs", "shallow", "q3_commits", "admissions", "frozen_t1_sha256", "job_name"):
        ok(a[key] == b[key], key)
    # byte-identical jobs except the git index (its stat cache records inode/mtime of the checked-out seed files)
    inv = [{r["path"]: r for r in json.loads(read(f["manifest_path"]))["inventory"]} for f in (a, b)]
    ok(set(inv[0]) == set(inv[1]) and "repo/.git/index" in inv[0])
    ok([p for p in inv[0] if inv[0][p] != inv[1][p]] in ([], ["repo/.git/index"]))
    objects = [git(f["repo_dir"], "cat-file", "--batch-all-objects", "--batch-check") for f in (a, b)]
    ok(objects[0] == objects[1] and objects[0])


def test_preflight_job_for_04(jobs):
    f = jobs["pf04"]
    ok(f["job_name"] == "k4s-end-guard-r1-pf07" and f["job"] == {"kind": "preflight", "preflight": "07"})
    ok(f["target_job"] == S3.GUARD_PARENTS["127x04"] + "/k4s-end-guard-r1-pf07")
    ok(sorted(os.listdir(f["job_dir"])) == S3.top_level("127x04"))


def test_session_constants_verify_the_cli_job(world, jobs):
    """The fixture's bindings equal the session world's (deterministic synthetic commits): the shipped S3.verify
    accepts the CLI-built job in-process."""
    f = jobs["a"]
    ok([b["commit"] for b in f["bindings"]] == [b["commit"] for b in S3.BINDINGS])
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", f["out"], f["job_name"]))
    m = S3.verify(policy, "s3", f["out"], f["job_name"], f["manifest_sha256"], log=lambda *a: None)
    ok(m["inventory_sha256"] == f["inventory_sha256"])


def test_shallow_needs_an_explicit_guard_role_allowance(jobs):
    """END-FULL-F2: an ordinary GitRepo refuses the S3 guard repo (.git/shallow) before git runs; only the declared
    shallow allowance (S3's prove_repo; Part B's guard-role allowance) admits it, with every other indirection still
    refused."""
    repo = jobs["a"]["repo_dir"]
    error = refused("indirection", si.git_run, si.GitRepo(work_tree=repo), ["rev-parse", "HEAD"])
    ok("shallow" in error.reason)
    ok(si.git_run(si.GitRepo(work_tree=repo, allow=("shallow",)), ["rev-parse", "--is-shallow-repository"]).stdout
       == b"true\n")


@pytest.mark.parametrize("case", ["nonempty", "not-tmp"])
def test_cli_refuses_a_bad_dir(case):
    d = os.path.realpath(tempfile.mkdtemp(prefix="k4s-fx-", dir="/tmp"))
    try:
        target = d
        if case == "nonempty":
            open(os.path.join(d, "x"), "w").close()
        else:
            target = "/dev/shm"
        proc = run_py("tests/fixture_guard_job.py", "--dir", target)
        ok(proc.returncode == 2 and b"empty directory under /tmp/" in proc.stderr, proc.stderr[-500:])
        ok(os.listdir(d) == (["x"] if case == "nonempty" else []))
    finally:
        rmtree(d)
