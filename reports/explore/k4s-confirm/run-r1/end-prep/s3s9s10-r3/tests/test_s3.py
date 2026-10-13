"""S3 r2: committed inputs through the git helper with expected SHAs; E3 exact admission paths (no --admissions-dir);
role-gated S1b manifest; -pfNN form; safe_input inventory/verify; guard repo via si.git_run; frozen check in the P2-4
environment. Includes Sol's S3-F1/F2 probes and the git indirection controls."""
import json
import os
import shutil

import pytest

from conftest import (C, CANARY, S1B, S3, admissions, canary_file, make_file, ok, read, refused, s3_args, sha,
                      si)


@pytest.fixture
def repo_copy(world, tmpdir_, monkeypatch):
    """A private copy of the full clone (so probes can add commits/refs/files) as S3.REPO_FULL."""
    path = os.path.join(tmpdir_, "repo-full-copy")
    shutil.copytree(world.repo_full, path, symlinks=True)
    monkeypatch.setattr(S3, "REPO_FULL", path)
    return path


def build(world, s1b, out, **kw):
    return S3.build(s3_args(world, s1b, out, **kw), log=lambda *a: None)


def partial_receipt(out):
    names = os.listdir(out + ".partial")
    rec = [n for n in names if n.startswith("S3-REFUSAL-")]
    ok(len(rec) == 1 and not os.path.exists(out), names)
    return json.loads(read(os.path.join(out + ".partial", rec[0])))


def test_04_has_no_idle_and_pf_form(world, s1b_out, tmpdir_):
    out = os.path.join(tmpdir_, "pf")
    m = build(world, s1b_out, out, host="127x04", preflight="00")
    ok(m["job_name"] == "k4s-end-guard-r1-pf00" and m["job"] == {"kind": "preflight", "preflight": "00"})
    ok(m["target_job"] == "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00")
    ok(m["top_level"] == ["FROZEN-T1.json", "repo", "system-bus-admission.json"])
    ok(sorted(os.listdir(os.path.join(out, m["job_name"]))) == m["top_level"])
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", out, m["job_name"]))
    S3.verify(policy, "s3", out, m["job_name"], m["_sha256"], log=lambda *a: None)


def test_job_name_forms():
    ok(S3.target_job("127x03", "01", "02") == ("k4s-end-guard-r1-rd01-a02",
                                               "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd01-a02"))
    ok(S3.target_job("127x04", preflight="03")[1] == "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf03")
    for args in (("127x03", "1", "02"), ("127x03", "01", None), ("127x05", "01", "02"), ("127x03", "01", "02", "03")):
        refused("policy", S3.target_job, *args)
    for name in ("k4s-end-guard-r1", "k4s-end-guard-r2-rd00-a00", "k4s-end-guard-r1-pf000", "k4s-end-guard-r1-pf00x",
                 "k4s-end-guard-r1-rd00-a00.partial", "k4s-end-guard-r1-rd00"):
        refused("policy", S3.check_name, name)
    S3.check_target("127x04", "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00")
    refused("policy", S3.check_target, "127x04", "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf00")
    refused("policy", S3.check_target, "127x03", "/mpac/sdicks02/jobs/clasher/x/k4s-end-guard-r1-pf00")
    ok(S3.GUARD_PARENTS == si.Q4_GUARD_PARENTS)


def test_admissions_dir_option_removed(world, s1b_out, tmpdir_):
    with pytest.raises(SystemExit) as info:
        S3.main(["build", "--host", "127x03", "--round", "00", "--attempt", "00", "--commit", world.P,
                 "--s1b-manifest", s1b_out["manifest"], "--s1b-manifest-sha256", s1b_out["sha"],
                 "--out", os.path.join(tmpdir_, "o"), "--admissions-dir", "reports/x"])
    ok(info.value.code == 2 and not os.path.exists(os.path.join(tmpdir_, "o.partial")))


def test_probe_admissions_only_under_end_receipts_refused(world, s1b_out, repo_copy, tmpdir_, monkeypatch):
    """Sol S3-F1: committed admissions under end/receipts/reviewer/<host>-<name> must not be accepted; only the exact
    E3 path is ever asked for, and the END-located blob is never read."""
    reads = []
    real = si._git_object

    def spy(repo, oid, *a, **k):
        reads.append(oid)
        return real(repo, oid, *a, **k)
    monkeypatch.setattr(si, "_git_object", spy)
    files = {"%s/%s" % (si.E3_ADMISSIONS_DIR, S1B.e3_name("127x03", n)): None for n in S1B.NAMES["127x03"]}
    end_rel = "reports/explore/k4s-confirm/end/receipts/reviewer/127x03-system-bus-admission.json"
    files[end_rel] = admissions("127x03")["system-bus-admission.json"]
    commit = world.git.commit(repo_copy, files, "move admissions under end/")
    end_oid = world.git(repo_copy, "rev-parse", commit + ":" + end_rel).decode().strip()
    out = os.path.join(tmpdir_, "out")
    refused("missing", build, world, s1b_out, out, commit=commit)
    ok(end_oid not in reads)
    partial_receipt(out)


def test_probe_s1b_manifest_in_end_location_refused_before_any_read(world, s1b_out, tmpdir_):
    """Sol S3-F1: a valid S1b manifest placed under a strict END location is refused by name (policy construction),
    before anything is created or read."""
    end_dir = os.path.join(tmpdir_, "k4s-confirm", "end")
    os.makedirs(end_dir)
    shutil.copyfile(s1b_out["manifest"], os.path.join(end_dir, S3.S1B_MANIFEST))
    out = os.path.join(tmpdir_, "out")
    refused("name", build, world, s1b_out, out, s1b_manifest=os.path.join(end_dir, S3.S1B_MANIFEST))
    ok(not os.path.exists(out + ".partial"))


@pytest.mark.parametrize("case,code", [("hardlink", "nlink"), ("wrong-sha", "sha"), ("symlinked-dir", "root"),
                                       ("other-name", "policy")])
def test_s1b_manifest_gates(world, s1b_out, tmpdir_, case, code):
    src = os.path.join(tmpdir_, "s1b")
    os.makedirs(src)
    target = os.path.join(src, S3.S1B_MANIFEST)
    kw = {}
    if case == "hardlink":
        private = os.path.join(tmpdir_, "private-copy.json")
        shutil.copyfile(s1b_out["manifest"], private)
        os.link(private, target)
    elif case == "wrong-sha":
        shutil.copyfile(s1b_out["manifest"], target)
        kw["s1b_manifest_sha256"] = "0" * 64
    elif case == "symlinked-dir":
        os.rmdir(src)
        os.symlink(s1b_out["dest"], src)
    else:
        target = os.path.join(src, "manifest.json")
        shutil.copyfile(s1b_out["manifest"], target)
    out = os.path.join(tmpdir_, "out")
    refused(code, build, world, s1b_out, out, s1b_manifest=target, **kw)
    ok(not os.path.exists(out))


def test_doctored_s1b_sha_mismatches_the_committed_admission(world, s1b_out, tmpdir_):
    doc = json.loads(read(s1b_out["manifest"]))
    for f in doc["files"]:
        if f["host"] == "127x03" and f["name"] == "system-bus-admission.json":
            f["remote_sha256"] = f["local_sha256"] = "1" * 64
    path = make_file(os.path.join(tmpdir_, "s1b", S3.S1B_MANIFEST), json.dumps(doc).encode())
    out = os.path.join(tmpdir_, "out")
    refused("sha", build, world, s1b_out, out, s1b_manifest=path, s1b_manifest_sha256=sha(read(path)))
    partial_receipt(out)


def test_tampered_guard_module_never_executes(world, s1b_out, repo_copy, tmpdir_):
    marker = os.path.join(tmpdir_, "EXECUTED")
    rel = "reports/explore/t1/parent_source_seed.py"
    evil = read(os.path.join(repo_copy, rel)) + ("\nopen(%r, 'w').write('x')\n" % marker).encode()
    commit = world.git.commit(repo_copy, {rel: evil}, "tamper module")
    out = os.path.join(tmpdir_, "out")
    refused("sha", build, world, s1b_out, out, commit=commit)
    ok(not os.path.exists(marker))
    partial_receipt(out)


def test_frozen_check_nonzero_with_valid_stdout_refused(world, s1b_out, tmpdir_, monkeypatch):
    good = json.dumps(dict(committed_binding_hosts=["127x03", "127x08", "127x08", "127x08"], admit_accepted=[],
                           admit_host="127x05", module="parent_source_seed.py", optimize=0))
    monkeypatch.setattr(S3, "FROZEN_SNIPPET", "import sys\nprint(%r)\nsys.exit(37)\n" % good)
    out = os.path.join(tmpdir_, "out")
    refused("subprocess", build, world, s1b_out, out)
    partial_receipt(out)


def test_git_replace_ref_and_env_cannot_substitute_bytes(world, s1b_out, guard03, repo_copy, tmpdir_, monkeypatch):
    freeze_oid = world.git(repo_copy, "rev-parse", world.P + ":" + S3.FREEZE_REL).decode().strip()
    canary_oid = world.git(repo_copy, "hash-object", "-w", "--stdin", data=CANARY).decode().strip()
    world.git(repo_copy, "replace", freeze_oid, canary_oid)
    ok(world.git(repo_copy, "show", world.P + ":" + S3.FREEZE_REL) == CANARY)        # raw git is fooled
    foreign = os.path.join(tmpdir_, "foreign")
    os.makedirs(foreign)
    world.git(foreign, "init", "-q")
    monkeypatch.setenv("GIT_DIR", foreign + "/.git")
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", foreign + "/.git/objects")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/replace/")
    out = os.path.join(tmpdir_, "out")
    error = refused("indirection", build, world, s1b_out, out)              # F4 (r3): the live precondition
    ok("replace refs" in error.reason, error.reason)
    # Defense in depth: with the precondition stubbed out (test-only), the layer still ignores replace refs and env.
    monkeypatch.setattr(S3.S9, "require_full_clone", lambda *a, **k: {"stubbed": True})
    out = os.path.join(tmpdir_, "out2")
    m = build(world, s1b_out, out)
    job = os.path.join(out, m["job_name"])
    ok(read(os.path.join(job, "FROZEN-T1.json")) == world.files[S3.FREEZE_REL])
    for name in ("system-bus-admission.json", "idle-services.json"):
        ok(read(os.path.join(job, name)) == read(os.path.join(guard03["out"], guard03["job"], name)))


@pytest.mark.parametrize("kind", ["alternates", "grafts", "hookspath", "include", "filter", "gitfile"])
def test_repository_indirection_refused(world, s1b_out, repo_copy, tmpdir_, kind):
    git_dir = os.path.join(repo_copy, ".git")
    if kind == "alternates":
        make_file(os.path.join(git_dir, "objects", "info", "alternates"), (tmpdir_ + "\n").encode())
    elif kind == "grafts":
        make_file(os.path.join(git_dir, "info", "grafts"), (world.P + "\n").encode())
    elif kind in ("hookspath", "include", "filter"):
        extra = {"hookspath": "[core]\n\thooksPath = /tmp\n", "include": "[include]\n\tpath = /tmp/x\n",
                 "filter": '[filter "x"]\n\tclean = cat\n'}[kind]
        with open(os.path.join(git_dir, "config"), "a") as stream:
            stream.write(extra)
    else:
        os.rename(git_dir, os.path.join(tmpdir_, "moved.git"))
        make_file(git_dir, ("gitdir: %s/moved.git\n" % tmpdir_).encode())
    out = os.path.join(tmpdir_, "out")
    with pytest.raises(si.Refusal) as info:
        build(world, s1b_out, out)
    ok(info.value.code in ("indirection", "root", "not-dir"), str(info.value))
    ok(not os.path.exists(out))


def copy_out(guard03, tmpdir_):
    dst = os.path.join(tmpdir_, "copy")
    shutil.copytree(guard03["out"], dst, symlinks=True)
    return dst, os.path.join(dst, guard03["job"])


def verify(out, job, digest):
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", out, job))
    return S3.verify(policy, "s3", out, job, digest, log=lambda *a: None)


@pytest.mark.parametrize("case,code", [("hardlink", "nlink"), ("symlink", "symlink"), ("games", "name"),
                                       ("admission", "check"), ("extra", "check"), ("seed", "check"),
                                       ("complete", "name"), ("fifo", "not-regular")])
def test_probe_verify_refuses_aliases_and_tampering(guard03, tmpdir_, case, code):
    """Sol S3-F2: verification inputs must refuse static aliases and forbidden names before hashing."""
    out, job = copy_out(guard03, tmpdir_)
    verify(out, guard03["job"], guard03["sha"])
    canary = canary_file(os.path.join(tmpdir_, "elsewhere"))
    adm = os.path.join(job, "system-bus-admission.json")
    if case == "hardlink":
        os.link(canary, os.path.join(job, "repo", "hl.json"))
    elif case == "symlink":
        os.chmod(job, 0o755)
        os.symlink(canary, os.path.join(job, "link.json"))
    elif case == "games":
        make_file(os.path.join(job, "repo", "games", "g.json"), CANARY)
    elif case == "admission":
        os.chmod(adm, 0o644)
        data = read(adm)
        make_file(adm, data.replace(b"13:30:00", b"13:30:01"))
    elif case == "extra":
        make_file(os.path.join(job, "repo", "extra.txt"), b"extra\n")
    elif case == "seed":
        seed = os.path.join(job, "repo", S3.SEEDS[0]["path"])
        os.chmod(seed, 0o644)
        make_file(seed, b'{"host": "127x0X"}\n')
    elif case == "complete":
        make_file(os.path.join(job, "repo", "complete.json"), CANARY)
    else:
        os.mkfifo(os.path.join(job, "repo", "pipe"))
    with pytest.raises(si.Refusal) as info:
        verify(out, guard03["job"], guard03["sha"])
    ok(info.value.code == code or (case in ("admission", "extra") and info.value.code in ("check", "sha")),
       str(info.value))
    ok(read(canary) == CANARY)


def test_verify_manifest_pins_and_roots(guard03, tmpdir_):
    out, job = copy_out(guard03, tmpdir_)
    refused("sha", verify, out, guard03["job"], "0" * 64)
    refused("check", verify, out, "k4s-end-guard-r1-rd09-a09", guard03["sha"])
    os.symlink(out, os.path.join(tmpdir_, "alias"))
    refused("root", verify, os.path.join(tmpdir_, "alias"), guard03["job"], guard03["sha"])
    refused("policy", S3.verify_roles, "s3", out, "not-a-guard-job")


@pytest.mark.parametrize("where,code", [("exists", "exists"), ("partial-exists", "exists"), ("shm", "path"),
                                        ("symlinked-parent", "root")])
def test_out_confinement(world, s1b_out, tmpdir_, where, code):
    out = os.path.join(tmpdir_, "out")
    if where == "exists":
        os.makedirs(out)
    elif where == "partial-exists":
        os.makedirs(out + ".partial")
    elif where == "shm":
        out = "/dev/shm/k4s-s3-never"
    else:
        real = os.path.join(tmpdir_, "real")
        os.makedirs(real)
        os.symlink(real, os.path.join(tmpdir_, "alias"))
        out = os.path.join(tmpdir_, "alias", "out")
    refused(code, build, world, s1b_out, out)
    ok(not os.path.exists("/dev/shm/k4s-s3-never") and not os.path.exists("/dev/shm/k4s-s3-never.partial"))
    if where == "symlinked-parent":
        ok(os.listdir(os.path.join(tmpdir_, "real")) == [])


def test_guard_repo_shape(guard03):
    root = os.path.join(guard03["out"], guard03["job"], "repo")
    ok(not os.path.exists(os.path.join(root, ".git", "FETCH_HEAD")))
    ok(os.path.exists(os.path.join(root, ".git", "shallow")))
    refs = sorted(os.listdir(os.path.join(root, ".git", "refs", "k4s-end")))
    ok(refs == sorted(b["label"] for b in S3.BINDINGS))
    for b in S3.BINDINGS:
        st = os.lstat(os.path.join(root, b["path"]))
        ok(st.st_mode & 0o777 == 0o444 and st.st_nlink == 1)
    config = read(os.path.join(root, ".git", "config")).decode()
    ok("[remote" not in config and "promisor" not in config and "/mpac" not in config)
    m = guard03["manifest"]
    ok([p["commit"] for p in m["commit_proofs"][:2]] == list(S3.Q3_COMMITS))
    ok(set(S3.GIT_DIRS) <= {d[len("repo/"):] for d in m["dirs"] if d.startswith("repo/")})


def test_cli_build_requires_s1b_manifest_and_sha(world, tmpdir_):
    with pytest.raises(SystemExit) as info:
        S3.main(["build", "--host", "127x03", "--round", "00", "--attempt", "00", "--commit", world.P, "--out",
                 os.path.join(tmpdir_, "o")])
    ok(info.value.code == 2)


@pytest.mark.parametrize("case,code", [("fetch-head", "exists"), ("extra-ref", "check"), ("remote-config", "check"),
                                       ("not-shallow", "check"), ("seed-bytes", "sha")])
def test_prove_repo_gates(guard03, tmpdir_, case, code):
    out, job = copy_out(guard03, tmpdir_)
    root = os.path.join(job, "repo")
    git_dir = os.path.join(root, ".git")
    if case == "fetch-head":
        make_file(os.path.join(git_dir, "FETCH_HEAD"), b"x\tfile:///mpac/x\n")
    elif case == "extra-ref":
        make_file(os.path.join(git_dir, "refs", "heads", "extra"), (S3.Q3_COMMITS[0] + "\n").encode())
    elif case == "remote-config":
        with open(os.path.join(git_dir, "config"), "a") as stream:
            stream.write('[remote "origin"]\n\turl = file:///mpac/sdicks02/repos/clasher\n')
    elif case == "not-shallow":
        os.unlink(os.path.join(git_dir, "shallow"))
    else:
        seed = os.path.join(root, S3.SEEDS[1]["path"])
        os.chmod(seed, 0o644)
        make_file(seed, b'{"host": "127x0Z"}\n')
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", out, guard03["job"]))
    refused(code, S3.prove_repo, policy, "s3-repo", root)


def test_doctored_s1b_nlink_refused(world, s1b_out, tmpdir_):
    doc = json.loads(read(s1b_out["manifest"]))
    doc["files"][0]["remote_nlink"] = 2
    path = make_file(os.path.join(tmpdir_, "s1b", S3.S1B_MANIFEST), json.dumps(doc).encode())
    out = os.path.join(tmpdir_, "out")
    refused("check", build, world, s1b_out, out, s1b_manifest=path, s1b_manifest_sha256=sha(read(path)))
    partial_receipt(out)


def test_changed_freeze_refused(world, s1b_out, repo_copy, tmpdir_):
    doc = json.loads(world.files[S3.FREEZE_REL])
    doc["note"] = "structurally valid but not the pinned freeze"
    commit = world.git.commit(repo_copy, {S3.FREEZE_REL: json.dumps(doc).encode()}, "changed freeze")
    out = os.path.join(tmpdir_, "out")
    refused("sha", build, world, s1b_out, out, commit=commit)
    partial_receipt(out)


def test_frozen_admit_must_accept_nothing_on_05(world, s1b_out, tmpdir_, monkeypatch):
    out_doc = json.dumps(dict(committed_binding_hosts=["127x03", "127x08", "127x08", "127x08"], admit_accepted=["x"],
                              admit_host="127x05", module="parent_source_seed.py", optimize=0))
    monkeypatch.setattr(S3, "FROZEN_SNIPPET", "print(%r)\n" % out_doc)
    out = os.path.join(tmpdir_, "out")
    error = refused("check", build, world, s1b_out, out)
    ok("admit" in error.reason)
