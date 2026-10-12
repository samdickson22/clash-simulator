"""S3 on a scratch clone of the real 05 repository: real FROZEN-T1, real binding commits, real frozen T1
committed_binding/admit; synthetic committed admissions. Every refusal path."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import ADMISSIONS_DIR, S1B, S3, admissions, bus_admission, commit_files, idle_admission, make_writable_copy

Q3 = ("b2f9e25e1002d43cc910a4bb476716cc4cd32623", "ce042b9775f80cb495c327b14a4712730ae95c85")


def build(scratch, out, host="127x03", commit=None, *extra):
    return S3.main(["build", "--host", host, "--round", "00", "--attempt", "01", "--repository", str(scratch["repo"]),
                    "--commit", commit or scratch["commit"], "--out", str(out), *extra])


def test_guard_job_03_contents_and_git_proofs(guard03):
    manifest = json.loads((guard03 / "guard-job-manifest.json").read_text())
    job = guard03 / "k4s-end-guard-r1-rd00-a00"
    assert manifest["target_job"] == "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00"
    assert sorted(os.listdir(job)) == ["FROZEN-T1.json", "idle-services.json", "repo", "system-bus-admission.json"]
    assert S3.sha_file(job / "FROZEN-T1.json") == S3.FROZEN_T1_SHA
    for name, data in admissions("127x03").items():
        assert (job / name).read_bytes() == data and os.stat(job / name).st_mode & 0o777 == 0o444
    repo = job / "repo"
    for commit in Q3 + tuple(b["commit"] for b in S3.JOINS):                 # independent of S3's own proof
        assert subprocess.run(["git", "-C", str(repo), "cat-file", "-e", commit + "^{commit}"]).returncode == 0
    for b in S3.BINDINGS:
        raw = subprocess.run(["git", "-C", str(repo), "show", b["commit"] + ":" + b["path"]], capture_output=True,
                             check=True).stdout
        assert raw == (repo / b["path"]).read_bytes() and S3.sha_bytes(raw) == b["sha256"]
    assert not (repo / ".git" / "objects" / "info" / "alternates").exists()
    assert not (repo / ".git" / "FETCH_HEAD").exists() and "[remote" not in (repo / ".git" / "config").read_text()
    assert subprocess.run(["git", "-C", str(repo), "fsck", "--no-progress"], capture_output=True).returncode == 0
    frozen = manifest["frozen_seed_check"]
    assert frozen["admit_accepted"] == [] and frozen["committed_binding_hosts"][:2] == ["127x03", "127x08"]
    assert frozen["optimize"] == 0
    assert not (job / "parent-source-seed-admission.json").exists()             # admit() ran on a throw-away copy
    files = [r for r in manifest["inventory"] if r["type"] == "f"]
    assert all(r["sha256"] == S3.sha_file(job / r["path"]) for r in files)
    assert S3.verify(guard03)["host"] == "127x03"


def test_guard_job_04_has_no_idle(scratch, tmp_path):
    out = tmp_path / "g04"
    assert S3.main(["build", "--host", "127x04", "--round", "01", "--attempt", "00", "--repository",
                    str(scratch["repo"]), "--commit", scratch["commit"], "--out", str(out)]) == 0
    manifest = json.loads((out / "guard-job-manifest.json").read_text())
    assert manifest["target_job"] == "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd01-a00"
    assert sorted(os.listdir(out / manifest["job_name"])) == ["FROZEN-T1.json", "repo", "system-bus-admission.json"]


def s1b_manifest(tmp_path, host="127x03", **change):
    files = []
    for h in ("127x03", "127x04"):
        for name, data in admissions(h).items():
            row = dict(host=h, name=name, remote_path=f"{S1B.job_dir(h)}/{name}", remote_sha256=S3.sha_bytes(data),
                       local_sha256=S3.sha_bytes(data), local_path=f"{h}/{name}")
            if h == host and name == "system-bus-admission.json":
                row.update(change)
            files.append(row)
    path = tmp_path / "s1b.json"
    path.write_text(json.dumps(dict(schema=S1B.SCHEMA, status="copied", files=files)))
    return path


def test_s1b_cross_check_pass_and_fail(scratch, tmp_path):
    assert build(scratch, tmp_path / "ok", "127x03", None, "--s1b-manifest", str(s1b_manifest(tmp_path))) == 0
    m = json.loads((tmp_path / "ok" / "guard-job-manifest.json").read_text())
    assert m["admissions"]["system-bus-admission.json"]["s1b_remote_path"].endswith("k4s-confirm-replacement-r4/system-bus-admission.json")
    for i, change in enumerate((dict(remote_sha256="0" * 64),
                                dict(remote_path="/mpac/sdicks02/jobs/clasher/x/system-bus-admission.json"))):
        (tmp_path / "s1b.json").unlink()
        out = tmp_path / f"bad{i}"
        assert build(scratch, out, "127x03", None, "--s1b-manifest", str(s1b_manifest(tmp_path, **change))) == 2
        assert not out.exists() and not Path(str(out) + ".partial").exists()


@pytest.mark.parametrize("case", ["bad_bus", "bad_idle", "missing_idle", "freeze", "seeds"])
def test_committed_input_refusals(scratch, tmp_path, case):
    files = {
        "bad_bus": {f"{ADMISSIONS_DIR}/127x03-system-bus-admission.json": bus_admission("127x03", start_ticks=9)},
        "bad_idle": {f"{ADMISSIONS_DIR}/127x03-idle-services.json": idle_admission(cmdline_sha256="0" * 64)},
        "missing_idle": {f"{ADMISSIONS_DIR}/127x03-idle-services.json": None},
        "freeze": {S3.FREEZE_REL: b"{}\n"},
        "seeds": {"reports/explore/t1/parent_source_seed.py": b"# changed\n"},
    }[case]
    commit = commit_files(scratch["repo"], scratch["commit"], files, case)
    out = tmp_path / "g"
    assert build(scratch, out, "127x03", commit) == 2
    assert not out.exists() and not Path(str(out) + ".partial").exists()


@pytest.mark.parametrize("args", [("127x03", "0", "00"), ("127x03", "00", "a0"), ("127x05", "00", "00")])
def test_bad_target(scratch, tmp_path, args):
    host, rd, at = args
    argv = ["build", "--host", host, "--round", rd, "--attempt", at, "--repository", str(scratch["repo"]),
            "--commit", scratch["commit"], "--out", str(tmp_path / "g")]
    if host == "127x05":
        with pytest.raises(SystemExit):                                # argparse choices
            S3.main(argv)
    else:
        assert S3.main(argv) == 2
    assert not (tmp_path / "g").exists()


@pytest.mark.parametrize("path,ok", [
    ("/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00", True),
    ("/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1", False),
    ("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/k4s-end-guard-r1-rd00-a00", False),
    ("/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4", False),
    ("/mpac/sdicks02/repos/clasher-v4-cache/k4s-end-guard-r1-rd00-a00", False),
    ("/mpac/sdicks02/jobs/clasher/../clasher/k4s-end-guard-r1-rd00-a00", False),
    ("/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00/", False),
    ("/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00", False),
])
def test_check_target_03(path, ok):
    if ok:
        assert S3.check_target("127x03", path) == path
    else:
        with pytest.raises(S3.Refusal):
            S3.check_target("127x03", path)


def test_check_target_04_never_jobs_clasher():
    assert S3.check_target("127x04", "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a01")
    with pytest.raises(S3.Refusal):
        S3.check_target("127x04", "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a01")


def test_out_exists_refused(scratch, tmp_path):
    (tmp_path / "g").mkdir()
    assert build(scratch, tmp_path / "g") == 2
    (tmp_path / "h.partial").mkdir()
    assert build(scratch, tmp_path / "h") == 2


@pytest.mark.parametrize("tamper", ["seed", "extra_top", "admission", "commit_gone", "freeze"])
def test_verify_detects(guard03, tmp_path, tamper):
    copy = make_writable_copy(guard03, tmp_path / "copy")
    job = copy / "k4s-end-guard-r1-rd00-a00"
    if tamper == "seed":
        p = job / "repo" / S3.SEEDS[0]["path"]
        p.write_bytes(p.read_bytes() + b" ")
    if tamper == "extra_top":
        (job / "owned-copier-admission.json").write_text("{}")
    if tamper == "admission":
        (job / "system-bus-admission.json").write_bytes(bus_admission("127x03") + b" ")
    if tamper == "commit_gone":
        for pack in (job / "repo/.git/objects/pack").iterdir():
            pack.unlink()
    if tamper == "freeze":
        (job / "FROZEN-T1.json").write_bytes(b"{}")
    with pytest.raises(S3.Refusal):
        S3.verify(copy)


def test_cli_exit_code(scratch, tmp_path):
    from conftest import py
    result = py("s3_guard_job.py", "build", "--host", "127x03", "--round", "00", "--attempt", "00", "--repository",
                scratch["repo"], "--commit", "0" * 40, "--out", tmp_path / "g")
    assert result.returncode == 2 and "S3 REFUSED" in result.stderr


def test_build_refuses_an_extra_top_level_entry(scratch, tmp_path, monkeypatch):
    original = S3.build_repo

    def build_repo_and_drop_stop(repository, repo, home):
        proofs = original(repository, repo, home)
        (repo.parent / "STOP").write_text("")                     # anything beyond the Q4 contents
        return proofs

    monkeypatch.setattr(S3, "build_repo", build_repo_and_drop_stop)
    out = tmp_path / "g"
    assert build(scratch, out) == 2
    assert not out.exists() and not Path(str(out) + ".partial").exists()



def test_tampered_guard_module_never_executes(scratch, tmp_path):
    """A T1 module changed in the commit is refused by its FROZEN-T1 pin before anything is imported."""
    canary = tmp_path / "canary"
    raw = subprocess.run(["git", "-C", str(scratch["repo"]), "show",
                          scratch["commit"] + ":reports/explore/t1/parent_source_seed.py"], capture_output=True).stdout
    commit = commit_files(scratch["repo"], scratch["commit"], {"reports/explore/t1/parent_source_seed.py":
                          raw + f"\nopen({str(canary)!r}, 'w').write('ran')\n".encode()}, "canary")
    assert build(scratch, tmp_path / "g", "127x03", commit) == 2
    assert not canary.exists() and not (tmp_path / "g").exists()


def test_out_confinement(scratch, tmp_path, foreign_dir):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    assert build(scratch, tmp_path / "link" / "g") == 2
    assert build(scratch, foreign_dir / "g") == 2
    assert os.listdir(tmp_path / "real") == [] and os.listdir(foreign_dir) == []
