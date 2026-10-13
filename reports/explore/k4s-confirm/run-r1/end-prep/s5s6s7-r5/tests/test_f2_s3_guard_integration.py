"""END-FULL-F2 integration: REAL S3-built guard jobs (Part A s3_guard_job.build, unmodified, in Part A's own synthetic
world; tests/s3_guard_builder.py) through the S5 preflight (k4s_end_preflight.run: guard_repo + repository_clone checks)
and the S7 host program (k4s_end_launch_remote via the fake-ssh end-to-end launch). The actual S3 job directory is
placed byte-for-byte (copytree, modes kept) at the Q4 guard-job path the bundle names; no other repository shape is
constructed for the guard role. Negatives: a shallow --repository (evidence/END-JOB) clone, an extra graft,
alternates, a replace ref, a promisor remote and a hook in a copy of the real S3 repo, and the real S3 repo checked in
the "repository" role.

Part A source: s3s9s10-r2 (deterministic; S3 construction logic is unchanged in r3), or $K4S_PARTA_DIR (e.g. the
revised s3s9s10-r3); its SHA256SUMS is verified before use and the choice is printed."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import helpers as H
import k4s_end_launch_gate as G
import k4s_end_preflight as S
import s5_fixture
from helpers import ok, raises
from test_s7_gate import Site, refused_on_host

END_PREP = "/mpac/sdicks02/k4s-runner/run-r1/end-prep"
BUILDER_PYTHON = "/mpac/sdicks02/venvs/k4s-freeze/bin/python"       # the 05-side interpreter Part A is run with


def parta_dir():
    """Deterministic: the reviewed, immutable s3s9s10-r2 (S3 construction logic is unchanged in r3); set
    K4S_PARTA_DIR=<end-prep>/s3s9s10-r3 to run the same tests against the revised Part A."""
    return os.environ.get("K4S_PARTA_DIR") or str(Path(END_PREP) / "s3s9s10-r2")


@pytest.fixture(scope="module")
def s3jobs():
    work = Path(tempfile.mkdtemp(prefix="s567r3-s3jobs-", dir="/tmp"))
    try:
        python = BUILDER_PYTHON if os.path.exists(BUILDER_PYTHON) else sys.executable
        done = subprocess.run([python, "-B", str(H.HERE / "s3_guard_builder.py"), parta_dir(), str(work),
                               str(work / "jobs.json")], capture_output=True, text=True, cwd="/tmp",
                              env=dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
                                       PYTHONDONTWRITEBYTECODE="1"), timeout=600)
        ok(done.returncode == 0, "S3 builder failed: " + done.stdout[-1500:] + done.stderr[-3000:])
        doc = json.loads((work / "jobs.json").read_text())
        print("F2 integration: real S3 guard jobs from %s (s3_guard_job.py %s, %d SHA256SUMS entries verified)"
              % (doc["parta"], doc["s3_sha256"][:12], doc["parta_sums"]))
        yield doc
    finally:
        H.make_writable(work)
        shutil.rmtree(work, ignore_errors=True)


def place(job, target):
    """The actual S3 job directory at `target` (a byte/mode copy, as S10 stages it); returns target."""
    target = Path(target)
    if target.exists():
        H.make_writable(target)
        shutil.rmtree(target)
    shutil.copytree(job["path"], target, symlinks=True)
    return target


@pytest.fixture
def writable_tmp(tmp_path):
    yield tmp_path
    H.make_writable(tmp_path)


# ---------------------------------------------------------------- the real S3 job through the host helpers

def test_real_s3_guard_repo_is_shallow_and_passes_the_guard_role(s3jobs, monkeypatch):
    si, tool = H.load_layers()
    for key, job in sorted(s3jobs["jobs"].items()):
        monkeypatch.setattr(os, "uname", H.fake_uname(job["host"]))
        repo = job["path"] + "/repo"
        ok(os.path.isfile(repo + "/.git/shallow"), "S3 contract: the Q3 guard repo is shallow")
        got = tool.verify_clone(si, job["host"], repo, grants=("guard-job",), role="guard-repo")
        ok(got["role"] == "guard-repo" and sorted(got["shallow_commits"]) == sorted(s3jobs["bindings"]), got)
        ok(tool.seed_commits(si, repo, s3jobs["q3_commits"], role="guard-repo") ==
           {c: True for c in s3jobs["q3_commits"]})


def test_real_s3_guard_repo_refused_in_the_repository_role(s3jobs, monkeypatch):
    """Shallow stays refused for every role except the guard one (the evidence/END-JOB clone must be full)."""
    si, tool = H.load_layers()
    monkeypatch.setattr(os, "uname", H.fake_uname("127x03"))
    job = s3jobs["jobs"]["03-pf00"]
    error = H.refused(si, "indirection", tool.verify_clone, si, "127x03", job["path"] + "/repo", grants=("guard-job",),
                      role="repository")
    ok("shallow not declared" in str(error), error)


@pytest.mark.parametrize("mutate", ["graft", "alternates", "replace", "promisor", "hook", "include"])
def test_real_s3_guard_repo_other_indirections_still_refused(s3jobs, writable_tmp, monkeypatch, mutate):
    si, tool = H.load_layers()
    monkeypatch.setattr(os, "uname", H.fake_uname("127x03"))
    job = place(s3jobs["jobs"]["03-pf00"], writable_tmp / "k4s-end-guard-r1-pf00")
    repo = job / "repo"
    c = s3jobs["q3_commits"][0]
    if mutate == "graft":
        H.write(repo / ".git/info/grafts", c + "\n")
    elif mutate == "alternates":
        H.write(repo / ".git/objects/info/alternates", str(writable_tmp) + "\n")
    elif mutate == "replace":
        H.git(repo, "update-ref", "refs/replace/" + c, c)
    elif mutate == "promisor":
        os.chmod(repo / ".git/config", 0o644)
        H.git(repo, "config", "remote.origin.promisor", "true")
    elif mutate == "hook":
        H.write(repo / ".git/hooks/post-checkout", "#!/bin/sh\n", 0o755)
    else:
        os.chmod(repo / ".git/config", 0o644)
        H.git(repo, "config", "include.path", str(writable_tmp / "x"))
    error = raises((si.Refusal, tool.HostRefusal), tool.verify_clone, si, "127x03", str(repo), grants=("guard-job",),
                   role="guard-repo")
    ok(error.code in ("indirection", "allowlist"), error)


# ---------------------------------------------------------------- S5: the preflight with the real S3 -pf00 job

@pytest.fixture
def s5_host_os(monkeypatch):
    """= test_s5_preflight.host_os: in-process stand-ins for the slot affinity/priority read-back of fake workers."""
    saved = dict(os.environ)
    masks = {900001 + i: {2 + 2 * i, 3 + 2 * i} for i in range(10)}
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: None)
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: masks.get(pid, {0, 1}))
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 10)
    yield
    os.environ.clear()
    os.environ.update(saved)


def s5_env(tmp, monkeypatch, s3jobs, host="127x03"):
    env = s5_fixture.build(tmp, monkeypatch, host=host)
    key = "03-pf00" if host == "127x03" else "04-pf00"
    place(s3jobs["jobs"][key], env.pf_job)
    monkeypatch.setattr(S, "SEED_COMMITS", tuple(s3jobs["q3_commits"]))
    return env


@pytest.mark.parametrize("host", ["127x03", "127x04"])
def test_s5_preflight_passes_with_the_real_s3_guard_job(s3jobs, writable_tmp, monkeypatch, s5_host_os, host):
    env = s5_env(writable_tmp, monkeypatch, s3jobs, host)
    code, result, seal = s5_fixture.go(env)
    rows = {r["name"]: r for r in result["checks"]}
    ok(code == 0 and result["passed"] and seal["status"] == "passed",
       [(r["name"], r.get("error")) for r in result["checks"] if r.get("passed") is False])
    guard = rows["guard_repo"]
    ok(guard["role"] == "guard-repo" and sorted(guard["shallow_commits"]) == sorted(s3jobs["bindings"]), guard)
    ok(guard["commits"] == {c: True for c in s3jobs["q3_commits"]})
    ok(rows["repository_clone"]["role"] == "repository" and "shallow_commits" not in rows["repository_clone"])


def test_s5_preflight_refuses_a_shallow_repository_clone(s3jobs, writable_tmp, monkeypatch, s5_host_os):
    env = s5_env(writable_tmp, monkeypatch, s3jobs)
    repo = Path(env.a.repository)
    H.make_writable(repo)
    shutil.rmtree(repo)
    source = writable_tmp / "repository-source"
    H.git_repo(source, commits=2, files={"reports/explore/k4s-confirm/README": b"study\n"})
    H.run(["/usr/bin/git", "clone", "-q", "--depth=1", "--no-local", "file://" + str(source), str(repo)],
          env=dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **H.GIT_ENV), check=True)
    code, result, seal = s5_fixture.go(env)
    rows = {r["name"]: r for r in result["checks"]}
    ok(code == 1 and seal["status"] == "failed" and rows["guard_repo"]["passed"] is True)
    ok(rows["repository_clone"]["passed"] is False and "shallow" in rows["repository_clone"]["error"],
       rows["repository_clone"])


def test_s5_preflight_refuses_the_real_job_with_an_extra_graft(s3jobs, writable_tmp, monkeypatch, s5_host_os):
    env = s5_env(writable_tmp, monkeypatch, s3jobs)
    H.write(env.pf_job / "repo/.git/info/grafts", s3jobs["q3_commits"][0] + "\n")
    code, result, _ = s5_fixture.go(env)
    rows = {r["name"]: r for r in result["checks"]}
    ok(code == 1 and rows["guard_repo"]["passed"] is False and "grafts" in rows["guard_repo"]["error"])


# ---------------------------------------------------------------- S7: the host program with the real S3 jobs

def s7_site(tmp, monkeypatch, s3jobs):
    site = Site(tmp, monkeypatch)
    q4 = Path(site.decl["hosts"]["127x03"]["guard_parent"])
    place(s3jobs["jobs"]["03-rd00-a00"], q4 / "k4s-end-guard-r1-rd00-a00")
    place(s3jobs["jobs"]["03-pf00"], q4 / "k4s-end-guard-r1-pf00")
    monkeypatch.setattr(G, "SEED_COMMITS", tuple(s3jobs["q3_commits"]))
    return site


@pytest.mark.parametrize("kind", ["end", "preflight"])
def test_s7_host_program_launches_with_the_real_s3_guard_job(s3jobs, writable_tmp, monkeypatch, kind):
    site = s7_site(writable_tmp, monkeypatch, s3jobs)
    code, doc, _ = site.launch(kind)
    ok(code == 0 and doc["launched"] is True, doc and doc["host_gate"]["failures"])
    fr = doc["host_gate"]["frozen_reader"]
    ok(fr["guard_repo"]["role"] == "guard-repo" and sorted(fr["guard_repo"]["shallow_commits"]) ==
       sorted(s3jobs["bindings"]), fr["guard_repo"])
    ok(fr["seed_commits"] == {c: True for c in s3jobs["q3_commits"]} and fr["repository"]["role"] == "repository")


def test_s7_host_program_refuses_a_shallow_repository_clone(s3jobs, writable_tmp, monkeypatch):
    site = s7_site(writable_tmp, monkeypatch, s3jobs)
    repo = Path(site.decl["hosts"]["127x03"]["repository"])
    H.make_writable(repo)
    shutil.rmtree(repo)
    source = writable_tmp / "repository-source"
    H.git_repo(source, commits=2, files={"reports/explore/k4s-confirm/README": b"study\n"})
    H.run(["/usr/bin/git", "clone", "-q", "--depth=1", "--no-local", "file://" + str(source), str(repo)],
          env=dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **H.GIT_ENV), check=True)
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "shallow")


@pytest.mark.parametrize("mutate", ["graft", "alternates"])
def test_s7_host_program_refuses_the_real_job_with_an_indirection(s3jobs, writable_tmp, monkeypatch, mutate):
    site = s7_site(writable_tmp, monkeypatch, s3jobs)
    repo = Path(site.decl["hosts"]["127x03"]["guard_parent"]) / "k4s-end-guard-r1-rd00-a00" / "repo"
    if mutate == "graft":
        H.write(repo / ".git/info/grafts", s3jobs["q3_commits"][0] + "\n")
    else:
        H.write(repo / ".git/objects/info/alternates", str(writable_tmp) + "\n")
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "frozen-reader")
