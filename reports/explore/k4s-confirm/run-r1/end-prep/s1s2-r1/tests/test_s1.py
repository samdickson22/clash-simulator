"""S1 exact-path copier against a fake ssh shim (no real ssh)."""
import importlib.util
import json
import os
import re

import pytest

from conftest import CLASHER, PHASES, S1, phase_dir, py, sha, ssh_log

ALLOWED = {"launch.json", "supervisor-exit.json", "mhz.jsonl", "census.jsonl"}
REQUIRED_OPTIONS = ("BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes")


def load_s1():
    spec = importlib.util.spec_from_file_location("s1_under_test", S1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(f, *extra, window=True):
    args = ["--repository", CLASHER, "--commit", f["commit"], "--dest", f["dest"]]
    if window:
        args += ["--outside-end-window", "test: offline fixture"]
    return py(S1, *args, *extra, env=f["env"])


def all_paths(entries):
    return [p for e in entries for p in re.findall(r"/mpac/sdicks02/[A-Za-z0-9._/-]+", e["command"])]


def test_happy_path_exact_paths_six_logins(fake_hosts):
    f = fake_hosts
    result = run(f)
    assert result.returncode == 0, result.stderr
    entries = ssh_log(f["log"])
    assert [(e["host"]) for e in entries] == ["127x03", "127x04", "127x03", "127x03", "127x04", "127x04"]
    for e in entries:
        for option in REQUIRED_OPTIONS:
            assert option in e["argv"]
        assert not re.search(r"[*?\[\]]|\bfind\b|\bls\b|\btar\b|\brsync\b|\bscp\b|-r\b|-R\b", e["command"])
        assert "nice -n 19" in e["command"]
    prefix = {"127x03": "/mpac/sdicks02/jobs/clasher/", "127x04": "/mpac/sdicks02/jobs-k4s/"}
    namespaces = dict(PHASES)
    for e in entries:
        paths = all_paths([e])
        assert paths and len(paths) == (10 if " cat -- " in e["command"] else 2 * 20)
        for path in paths:
            head, phase, name = path.rsplit("/", 2)
            assert name in ALLOWED and head == prefix[e["host"]] + namespaces[phase], path
        if e["host"] == "127x04":
            assert "/mpac/sdicks02/jobs/" not in e["command"]
    dest = f["dest"]
    names = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert names == sorted([f"{h}/{p}/{n}" for h in ("127x03", "127x04") for p, _ in PHASES
                            for n in ("mhz.jsonl", "census.jsonl")] + ["s1-copy-manifest.json"])
    manifest = json.loads((dest / "s1-copy-manifest.json").read_text())
    assert manifest["status"] == "copied" and manifest["ssh_logins"] == 6 and len(manifest["files"]) == 20
    assert len(manifest["meta"]) == 20 and all(m["remote_sha256"] == m["committed_sha256"] for m in manifest["meta"])
    for row in manifest["files"]:
        host, phase, name = row["host"], row["phase"], row["name"]
        namespace = dict(PHASES)[phase]
        original = (phase_dir(f["root"], host, phase, namespace) / name).read_bytes()
        local = (dest / row["local_path"]).read_bytes()
        assert local == original and f'"tag":"{host}/{phase}/{name[:-6]}"'.encode() in local
        assert row["local_sha256"] == row["remote_sha256_before"] == row["remote_sha256_after"] == sha(original)
        assert row["local_size"] == row["remote_size"] == len(original)
        assert row["remote_path"].endswith(f"/{namespace}/{phase}/{name}")


def test_dry_run_makes_no_ssh_and_writes_nothing(fake_hosts):
    f = fake_hosts
    result = py(S1, "--repository", CLASHER, "--commit", f["commit"], "--dry-run", env=f["env"])
    assert result.returncode == 0, result.stderr
    assert not f["log"].exists() and not f["dest"].exists()
    assert result.stdout.count("# login ") == 6
    assert "BatchMode=yes" in result.stdout and "ControlPath=none" in result.stdout
    assert "88debddf7bf33c1b0bc2f14002339c87072be956398d90bfb727c2d0c36a1033" in result.stdout


def tamper(f, host, phase, name, data=b"tampered\n"):
    (phase_dir(f["root"], host, phase, dict(PHASES)[phase]) / name).write_bytes(data)


def test_launch_sha_mismatch_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    tamper(f, "127x04", "replacement-r3", "launch.json")
    result = run(f)
    assert result.returncode == 2 and "REFUSE on-host" in result.stderr and "launch.json" in result.stderr
    assert [e["host"] for e in ssh_log(f["log"])] == ["127x03", "127x04"]
    assert not f["dest"].exists()


def test_supervisor_exit_sha_mismatch_refuses(fake_hosts):
    f = fake_hosts
    tamper(f, "127x03", "reporting", "supervisor-exit.json")
    result = run(f)
    assert result.returncode == 2 and "supervisor-exit.json" in result.stderr
    assert len(ssh_log(f["log"])) == 1 and not f["dest"].exists()


def test_oversize_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    path = phase_dir(f["root"], "127x03", "replacement-r2", dict(PHASES)["replacement-r2"]) / "census.jsonl"
    with open(path, "r+b") as stream:
        stream.truncate(95 * 1024 * 1024 + 1)                     # sparse
    result = run(f)
    assert result.returncode == 2 and "> 95 MiB" in result.stderr
    assert len(ssh_log(f["log"])) == 1 and not f["dest"].exists()          # refused at P03, before P04


def test_oversize_on_second_host_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    path = phase_dir(f["root"], "127x04", "reporting", dict(PHASES)["reporting"]) / "mhz.jsonl"
    with open(path, "r+b") as stream:
        stream.truncate(95 * 1024 * 1024 + 1)
    result = run(f)
    assert result.returncode == 2 and "> 95 MiB" in result.stderr
    assert [e["host"] for e in ssh_log(f["log"])] == ["127x03", "127x04"] and not f["dest"].exists()


def test_size_boundary_unit():
    s1 = load_s1()
    entry = dict(committed={})
    ok = {"/x/mhz.jsonl": dict(entry=entry, name="mhz.jsonl", size=s1.MAX_BYTES, sha256="0" * 64)}
    s1.check_inspection(ok, "unit")
    with pytest.raises(s1.Refusal):
        s1.check_inspection({"/x/mhz.jsonl": dict(ok["/x/mhz.jsonl"], size=s1.MAX_BYTES + 1)}, "unit")
    with pytest.raises(s1.Refusal):
        s1.check_inspection({"/x/mhz.jsonl": dict(ok["/x/mhz.jsonl"], size=0)}, "unit")


def test_missing_file_refuses(fake_hosts):
    f = fake_hosts
    (phase_dir(f["root"], "127x04", "replacement-r3", dict(PHASES)["replacement-r3"]) / "census.jsonl").unlink()
    result = run(f)
    assert result.returncode == 2 and "failed rc=" in result.stderr and "census.jsonl" in result.stderr
    assert not f["dest"].exists()


def test_symlink_refuses(fake_hosts):
    f = fake_hosts
    d = phase_dir(f["root"], "127x03", "replacement-r1", dict(PHASES)["replacement-r1"])
    (d / "mhz.jsonl").unlink()
    os.symlink(d / "mhz.jsonl.old", d / "mhz.jsonl")
    result = run(f)
    assert result.returncode == 2 and "not a regular file" in result.stderr
    assert not f["dest"].exists()


def test_change_during_copy_refuses(fake_hosts):
    f = fake_hosts
    rel = "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/replacement-r4/mhz.jsonl"
    f["env"]["FAKE_SSH_MUTATE"] = "127x03:" + rel
    result = run(f)
    assert result.returncode == 2 and "changed during the copy" in result.stderr
    refusal = json.loads((f["dest"] / "S1-REFUSAL.json").read_text())
    assert refusal["status"] == "refused" and not (f["dest"] / "s1-copy-manifest.json").exists()


def test_extra_stream_bytes_refuse(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_EXTRA"] = "127x04"
    result = run(f)
    assert result.returncode == 2 and "copy stream length" in result.stderr
    assert not (f["dest"] / "s1-copy-manifest.json").exists()


def test_ssh_failure_refuses(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_FAIL_HOST"] = "127x04"
    result = run(f)
    assert result.returncode == 2 and "rc=255" in result.stderr and not f["dest"].exists()


def test_live_run_requires_window_ack(fake_hosts):
    f = fake_hosts
    result = run(f, window=False)
    assert result.returncode == 2 and "--outside-end-window" in result.stderr
    assert not f["log"].exists()


def test_existing_dest_refuses(fake_hosts):
    f = fake_hosts
    f["dest"].mkdir()
    result = run(f)
    assert result.returncode == 2 and "must not exist" in result.stderr and not f["log"].exists()


def test_forbidden_path_guard_unit():
    s1 = load_s1()
    with pytest.raises(s1.Refusal):
        s1.phase_dir("127x04", "../jobs/clasher/x", "reporting")
    s1.JOB_ROOTS["127x04"] = "/mpac/sdicks02/jobs/clasher"
    with pytest.raises(s1.Refusal):
        s1.phase_dir("127x04", "k4s-confirm-reporting-r1", "reporting")
