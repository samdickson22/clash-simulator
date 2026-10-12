"""S1b against the fake ssh shim: exact paths only, 2 logins, every refusal path."""
import json
import os
import re
from pathlib import Path

import pytest

from conftest import S1B, admissions, bus_admission, head, idle_admission, logins, on_host, py

ALLOWED = {"/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/system-bus-admission.json",
           "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/idle-services.json",
           "/mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r4/system-bus-admission.json",
           "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r5",
           "/mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r5"}


def populate(fake, override=None):
    """Both hosts' admissions at the exact paths, plus decoys that must never be named."""
    override = override or {}
    for host in ("127x03", "127x04"):
        job = on_host(fake, host, S1B.job_dir(host))
        job.mkdir(parents=True, exist_ok=True)
        for name, data in admissions(host).items():
            (job / name).write_bytes(override.get((host, name), data))
        (job / "games").mkdir(exist_ok=True)
        (job / "games" / "complete.json").write_text("{}")
        (job / "replacement-r4").mkdir(exist_ok=True)
        (on_host(fake, host, S1B.JOB_ROOTS[host]) / "k4s-confirm-replacement-r3").mkdir(exist_ok=True)
        ((on_host(fake, host, S1B.JOB_ROOTS[host]) / "k4s-confirm-replacement-r3") / "system-bus-admission.json").write_text("{}")
    perception = on_host(fake, "127x04", "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4")
    perception.mkdir(parents=True, exist_ok=True)
    (perception / "system-bus-admission.json").write_text("{}")


def run(fake, dest, *extra, env=None):
    return py("s1b_copy_admissions.py", "--commit", head(), "--dest", dest, "--outside-end-window", "GO test",
              *extra, env=env or fake["env"])


def test_happy_path(fake_hosts, tmp_path):
    populate(fake_hosts)
    dest = tmp_path / "out"
    result = run(fake_hosts, dest)
    assert result.returncode == 0, result.stderr
    calls = logins(fake_hosts["log"])
    assert [c["host"] for c in calls] == ["127x03", "127x04"]
    for call in calls:
        assert {"BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes"} <= set(call["opts"])
        named = set(re.findall(r"/mpac/sdicks02/[A-Za-z0-9._/-]+", call["command"]))
        assert named <= ALLOWED, named - ALLOWED
        assert "games" not in call["command"] and "complete.json" not in call["command"]
        assert "*" not in call["command"] and " ls " not in call["command"] and "find" not in call["command"]
        assert call["command"].startswith("exec nice -n 19 /usr/bin/python3 -I -S -c ")
        assert "O_NOFOLLOW" in call["command"] and " cat " not in call["command"]
    assert not any("/mpac/sdicks02/jobs/" in c["command"] for c in calls if c["host"] == "127x04")
    files = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
    assert files == ["127x03/idle-services.json", "127x03/system-bus-admission.json",
                     "127x04/system-bus-admission.json", "s1b-admissions-manifest.json"]
    for host in ("127x03", "127x04"):
        for name, data in admissions(host).items():
            assert (dest / host / name).read_bytes() == data
            assert os.stat(dest / host / name).st_mode & 0o777 == 0o444
    manifest = json.loads((dest / "s1b-admissions-manifest.json").read_text())
    assert manifest["ssh_logins"] == 2 and len(manifest["files"]) == 3
    assert all(f["remote_sha256"] == f["local_sha256"] for f in manifest["files"])


def test_dry_run_no_ssh_no_writes(fake_hosts, tmp_path):
    result = py("s1b_copy_admissions.py", "--commit", head(), "--dry-run", env=fake_hosts["env"])
    assert result.returncode == 0 and result.stdout.count("# login ") == 2
    assert not fake_hosts["log"].exists()


@pytest.mark.parametrize("case,needle", [
    ("next_exists", "replacement-r5 exists"),
    ("missing", "REFUSE No such file or directory"),
    ("symlink", "REFUSE Too many levels of symbolic links"),
    ("dir_symlink", "REFUSE Not a directory"),
    ("fifo", "REFUSE not a regular file"),
    ("wrong_host", "host field"),
    ("wrong_bus_pid", "pinned dbus identity"),
    ("wrong_idle", "idle service identity"),
    ("oversize", "REFUSE size outside"),
    ("flip", "transport corruption"),
    ("extra", "unexpected trailing bytes"),
    ("flood", "exceeds"),
    ("ssh_fail", "failed rc=255"),
])
def test_refusals_leave_only_a_receipt(fake_hosts, tmp_path, case, needle):
    override = {}
    if case == "wrong_host":
        override[("127x04", "system-bus-admission.json")] = bus_admission("127x03")
    if case == "wrong_bus_pid":
        override[("127x04", "system-bus-admission.json")] = bus_admission("127x04", pid=2006)
    if case == "wrong_idle":
        override[("127x03", "idle-services.json")] = idle_admission(start_ticks=1)
    if case == "oversize":
        override[("127x03", "idle-services.json")] = b" " * (S1B.MAX_BYTES + 1)
    populate(fake_hosts, override)
    job04 = on_host(fake_hosts, "127x04", S1B.job_dir("127x04"))
    env = dict(fake_hosts["env"])
    if case == "next_exists":
        (job04.parent / "k4s-confirm-replacement-r5").mkdir()
    if case == "missing":
        (job04 / "system-bus-admission.json").unlink()
    if case == "symlink":
        target = job04 / "system-bus-admission.json"
        (job04 / "real.json").write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(job04 / "real.json")
    if case == "dir_symlink":                               # the whole job dir is an alias of a valid copy
        real = job04.parent / "elsewhere"
        job04.rename(real)
        job04.symlink_to(real)
    if case == "fifo":
        target = job04 / "system-bus-admission.json"
        target.unlink()
        os.mkfifo(target)
    if case == "flip":
        env["FAKE_SSH_FLIP"] = "127x04"
    if case == "flood":
        env["FAKE_SSH_FLOOD"] = "127x03"
    if case == "extra":
        env["FAKE_SSH_EXTRA"] = "127x04"
    if case == "ssh_fail":
        env["FAKE_SSH_FAIL_HOST"] = "127x04"
    dest = tmp_path / "out"
    result = run(fake_hosts, dest, env=env)
    assert result.returncode == 2, result.stderr
    assert needle in result.stderr
    assert sorted(os.listdir(dest)) == ["S1B-REFUSAL.json"]          # no admission bytes written
    assert needle in json.loads((dest / "S1B-REFUSAL.json").read_text())["error"]


def test_window_ack_and_dest_checked_before_any_login(fake_hosts, tmp_path):
    populate(fake_hosts)
    result = py("s1b_copy_admissions.py", "--commit", head(), "--dest", tmp_path / "x", env=fake_hosts["env"])
    assert result.returncode == 2 and "outside-end-window" in result.stderr
    assert "outside-end-window" in json.loads((tmp_path / "x" / "S1B-REFUSAL.json").read_text())["error"]
    (tmp_path / "exists").mkdir()
    result = run(fake_hosts, tmp_path / "exists")
    assert result.returncode == 2 and not fake_hosts["log"].exists() and os.listdir(tmp_path / "exists") == []


def test_dest_confinement(fake_hosts, tmp_path, foreign_dir):
    populate(fake_hosts)
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    for dest in (tmp_path / "link" / "out", foreign_dir / "out"):
        result = run(fake_hosts, dest)
        assert result.returncode == 2 and "--dest" in result.stderr
    assert os.listdir(tmp_path / "real") == [] and os.listdir(foreign_dir) == []
    assert not fake_hosts["log"].exists()


def test_history_must_end_at_r4(scratch, fake_hosts, tmp_path):
    from conftest import commit_files
    raw = json.loads(S1B.subprocess.run(["git", "-C", str(scratch["repo"]), "show",
                                         f"{scratch['base']}:{S1B.HISTORY}"], capture_output=True).stdout)
    raw.append(dict(phase="replacement-r5", namespace="k4s-confirm-replacement-r5"))
    commit = commit_files(scratch["repo"], scratch["base"], {S1B.HISTORY: json.dumps(raw).encode()}, "r5")
    result = py("s1b_copy_admissions.py", "--repository", scratch["repo"], "--commit", commit, "--dry-run",
                env=fake_hosts["env"])
    assert result.returncode == 2 and "does not end at" in result.stderr


@pytest.mark.parametrize("host,name,data,ok", [
    ("127x03", "system-bus-admission.json", bus_admission("127x03"), True),
    ("127x04", "idle-services.json", idle_admission("127x04"), False),
    ("127x03", "system-bus-admission.json", b"not json", False),
    ("127x03", "system-bus-admission.json", b"", False),
    ("127x03", "owned-copier-admission.json", b"{}", False),
    ("127x03", "idle-services.json", idle_admission(), True),
    ("127x03", "idle-services.json", idle_admission(pid=1), False),
])
def test_check_admission_unit(host, name, data, ok):
    if ok:
        assert S1B.check_admission(host, name, data)["pid"] in (2049, 2180947)
    else:
        with pytest.raises(S1B.Refusal):
            S1B.check_admission(host, name, data)


def test_bus_identity_extra_key_refused():
    doc = json.loads(bus_admission("127x04"))
    doc["identity"]["ppid"] = 1
    with pytest.raises(S1B.Refusal, match="keys"):
        S1B.check_admission("127x04", "system-bus-admission.json", json.dumps(doc).encode())
