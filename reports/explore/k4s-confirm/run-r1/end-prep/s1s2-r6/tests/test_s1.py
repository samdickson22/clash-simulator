"""S1 exact-path copier (r2) against a fake ssh shim (no real ssh). The remote program really runs (local
/usr/bin/python3, 3.8 like 03/04) against fake host trees."""
import importlib.util
import json
import os
import re
import shlex
import time

import pytest

from conftest import CLASHER, PHASES, S1, phase_dir, py, refusal_receipts, sha, ssh_log

ALLOWED = {"launch.json", "supervisor-exit.json", "mhz.jsonl", "census.jsonl"}
REQUIRED_OPTIONS = ("BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes")
R3 = "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/replacement-r4"


def load_s1():
    spec = importlib.util.spec_from_file_location("s1_under_test", S1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(f, *extra, window=True, dest=None):
    args = ["--repository", CLASHER, "--commit", f["commit"], "--dest", dest or f["dest"]]
    if window:
        args += ["--outside-end-window", "test: offline fixture"]
    return py(S1, *args, *extra, env=f["env"])


def remote_parts(command):
    """(prefix tokens, program, mode, operands) of one remote command."""
    tokens = shlex.split(command)
    i = tokens.index("-c")
    return tokens[:i], tokens[i + 1], tokens[i + 2], tokens[i + 3:]


def operand_path(mode, operand):
    return operand.split(":", 2)[2] if mode == "inspect" else operand.split(":", 3)[3]


def pdir(f, host, phase):
    return phase_dir(f["root"], host, phase, dict(PHASES)[phase])


def assert_refused(f, result, *words, logins=None, dest_exists=False):
    assert result.returncode == 2, result.stderr
    for word in words:
        assert word in result.stderr, (word, result.stderr)
    receipts = refusal_receipts(f)
    assert len(receipts) == 1 and receipts[0]["status"] == "refused" and receipts[0]["test_mode"] is True
    assert receipts[0]["schema"] == "clasher.k4s.end-sources-copy-refusal.TEST-ONLY.v2"
    if logins is not None:
        assert [(e["host"], e["streaming"]) for e in ssh_log(f["log"])] == logins
    assert f["dest"].exists() is dest_exists
    if dest_exists:
        assert not (f["dest"] / "s1-copy-manifest.json").exists()
        assert (f["dest"] / "S1-REFUSAL.json").exists()
    return receipts[0]


P2 = [("127x03", False), ("127x04", False)]


def test_happy_path_exact_paths_six_logins(fake_hosts):
    f = fake_hosts
    s1 = load_s1()
    result = run(f)
    assert result.returncode == 0, result.stderr
    entries = ssh_log(f["log"])
    assert [(e["host"], e["streaming"]) for e in entries] == [("127x03", False), ("127x04", False), ("127x03", True),
                                                              ("127x03", False), ("127x04", True), ("127x04", False)]
    prefix = {"127x03": "/mpac/sdicks02/jobs/clasher/", "127x04": "/mpac/sdicks02/jobs-k4s/"}
    namespaces = dict(PHASES)
    for e in entries:
        for option in REQUIRED_OPTIONS:
            assert option in e["argv"]
        head, program, mode, operands = remote_parts(e["command"])
        assert head == ["set", "-eu;", "LC_ALL=C;", "export", "LC_ALL;", "exec", "nice", "-n", "19",
                        "/usr/bin/python3", "-I", "-S"]
        assert program == s1.REMOTE_PROGRAM and mode == ("stream" if e["streaming"] else "inspect")
        assert len(operands) == (10 if e["streaming"] else 20)
        for operand in operands:
            path = operand_path(mode, operand)
            assert not re.search(r"[*?\[\]]", operand)
            directory, phase, name = path.rsplit("/", 2)
            assert name in ALLOWED and directory == prefix[e["host"]] + namespaces[phase], path
            if e["streaming"]:
                assert name in ("mhz.jsonl", "census.jsonl")
        if e["host"] == "127x04":
            assert "/mpac/sdicks02/jobs/" not in e["command"]
    dest = f["dest"]
    names = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert names == sorted([f"{h}/{p}/{n}" for h in ("127x03", "127x04") for p, _ in PHASES
                            for n in ("mhz.jsonl", "census.jsonl")] + ["s1-copy-manifest.json"])
    manifest = json.loads((dest / "s1-copy-manifest.json").read_text())
    assert manifest["schema"] == "clasher.k4s.end-sources-copy.TEST-ONLY.v2" and manifest["test_mode"] is True
    assert manifest["status"] == "copied" and manifest["ssh_logins"] == 6 and len(manifest["files"]) == 20
    assert manifest["remote_program_sha256"] == sha(s1.REMOTE_PROGRAM.encode())
    assert len(manifest["meta"]) == 20 and all(m["remote_sha256"] == m["committed_sha256"] and
                                               m["remote_size"] == m["committed_size"] for m in manifest["meta"])
    for row in manifest["files"]:
        host, phase, name = row["host"], row["phase"], row["name"]
        original = (pdir(f, host, phase) / name).read_bytes()
        local = (dest / row["local_path"]).read_bytes()
        assert local == original and f'"tag":"{host}/{phase}/{name[:-6]}"'.encode() in local
        assert row["local_sha256"] == row["remote_sha256_before"] == row["remote_sha256_after"] == sha(original)
        assert row["local_size"] == row["remote_size"] == len(original)
        assert row["remote_path"].endswith(f"/{dict(PHASES)[phase]}/{phase}/{name}")
    assert refusal_receipts(f) == []


def test_dry_run_makes_no_ssh_and_writes_nothing(fake_hosts):
    f = fake_hosts
    result = py(S1, "--repository", CLASHER, "--commit", f["commit"], "--dry-run", env=f["env"])
    assert result.returncode == 0, result.stderr
    assert not f["log"].exists() and not f["dest"].exists() and not f["refusals"].exists()
    assert result.stdout.count("# login ") == 6
    assert "BatchMode=yes" in result.stdout and "ControlPath=none" in result.stdout
    assert "88debddf7bf33c1b0bc2f14002339c87072be956398d90bfb727c2d0c36a1033" in result.stdout


def tamper(f, host, phase, name, data=b"tampered\n"):
    (pdir(f, host, phase) / name).write_bytes(data)


def test_launch_size_mismatch_refused_remotely_before_any_read(fake_hosts):
    f = fake_hosts
    tamper(f, "127x04", "replacement-r3", "launch.json")
    result = run(f)
    assert_refused(f, result, "REMOTE REFUSE", "size 9 != committed size 350", "launch.json", logins=P2)


def test_launch_same_size_sha_mismatch_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    path = pdir(f, "127x04", "replacement-r3") / "launch.json"
    data = path.read_bytes()
    path.write_bytes(data[:-2] + b" \n")                       # same length, different bytes
    result = run(f)
    assert_refused(f, result, "REFUSE on-host", "launch.json", logins=P2)


def test_supervisor_exit_sha_mismatch_refuses(fake_hosts):
    f = fake_hosts
    path = pdir(f, "127x03", "reporting") / "supervisor-exit.json"
    data = path.read_bytes()
    path.write_bytes(data[:-2] + b" \n")
    result = run(f)
    assert_refused(f, result, "supervisor-exit.json", logins=[("127x03", False)])


def test_oversize_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    path = pdir(f, "127x03", "replacement-r2") / "census.jsonl"
    with open(path, "r+b") as stream:
        stream.truncate(95 * 1024 * 1024 + 1)                     # sparse
    result = run(f)
    assert_refused(f, result, "REMOTE REFUSE", "outside 1..99614720", logins=[("127x03", False)])


def test_oversize_on_second_host_refuses_before_any_copy(fake_hosts):
    f = fake_hosts
    path = pdir(f, "127x04", "reporting") / "mhz.jsonl"
    with open(path, "r+b") as stream:
        stream.truncate(95 * 1024 * 1024 + 1)
    assert_refused(f, run(f), "outside 1..99614720", logins=P2)


def test_huge_source_is_never_hashed(fake_hosts):
    """A 64 GiB sparse census (last operand on 04) is refused by the size gate before ANY file is hashed: hashing
    it would take minutes, the refusal takes seconds."""
    f = fake_hosts
    path = pdir(f, "127x04", "replacement-r4") / "census.jsonl"
    with open(path, "r+b") as stream:
        stream.truncate(64 << 30)
    started = time.monotonic()
    result = run(f)
    assert time.monotonic() - started < 60
    assert_refused(f, result, "outside 1..99614720", logins=P2)


def test_size_boundary_unit():
    s1 = load_s1()
    entry = dict(committed={})
    ok = {"/x/mhz.jsonl": dict(entry=entry, name="mhz.jsonl", size=s1.MAX_BYTES, sha256="0" * 64)}
    s1.check_inspection(ok, "unit")
    with pytest.raises(s1.Refusal):
        s1.check_inspection({"/x/mhz.jsonl": dict(ok["/x/mhz.jsonl"], size=s1.MAX_BYTES + 1)}, "unit")
    with pytest.raises(s1.Refusal):
        s1.check_inspection({"/x/mhz.jsonl": dict(ok["/x/mhz.jsonl"], size=0)}, "unit")
    assert "<= 99614720" in s1.REMOTE_PROGRAM and s1.MAX_BYTES == 99614720


def test_empty_source_refused(fake_hosts):
    f = fake_hosts
    (pdir(f, "127x03", "reporting") / "mhz.jsonl").write_bytes(b"")
    assert_refused(f, run(f), "outside 1..99614720", logins=[("127x03", False)])


def test_missing_file_refuses(fake_hosts):
    f = fake_hosts
    (pdir(f, "127x04", "replacement-r3") / "census.jsonl").unlink()
    assert_refused(f, run(f), "REMOTE REFUSE", "ENOENT", "census.jsonl", logins=P2)


def test_leaf_symlink_into_games_is_never_followed(fake_hosts):
    """O_NOFOLLOW refuses the leaf with ELOOP: the kernel never resolves the link, so games/ is never opened."""
    f = fake_hosts
    d = pdir(f, "127x03", "replacement-r1")
    (d / "mhz.jsonl").unlink()
    os.symlink(d / "games" / "decoy.json", d / "mhz.jsonl")
    os.chmod(d / "games" / "decoy.json", 0)                     # if it were followed: EACCES, not ELOOP
    result = run(f)
    assert_refused(f, result, "REMOTE REFUSE", "'mhz.jsonl'", "ELOOP", logins=[("127x03", False)])
    assert "EACCES" not in result.stderr


def test_phase_directory_alias_into_perception_tree_refused(fake_hosts):
    """04's phase dir replaced by a symlink into the fake /mpac/sdicks02/jobs/clasher/ (perception) tree with
    valid-looking files: refused at that component; nothing below it is opened."""
    f = fake_hosts
    real = pdir(f, "127x04", "reporting")
    alias_target = f["root"] / "127x04" / "mpac/sdicks02/jobs/clasher/k4s-confirm-reporting-r1/reporting"
    for name in ("launch.json", "supervisor-exit.json", "mhz.jsonl", "census.jsonl"):
        (alias_target / name).write_bytes((real / name).read_bytes())
    real.rename(real.with_name("reporting-moved"))
    os.symlink(alias_target, real)
    result = run(f)
    assert_refused(f, result, "REMOTE REFUSE", "component 'reporting'", logins=P2)
    assert "ELOOP" in result.stderr or "ENOTDIR" in result.stderr


def test_namespace_ancestor_symlink_refused(fake_hosts):
    f = fake_hosts
    real = pdir(f, "127x03", "replacement-r2").parent
    moved = real.with_name(real.name + "-moved")
    real.rename(moved)
    os.symlink(moved, real)
    result = run(f)
    assert_refused(f, result, "REMOTE REFUSE", "component 'k4s-confirm-replacement-r2'", logins=[("127x03", False)])


def test_hard_link_alias_refused(fake_hosts):
    f = fake_hosts
    d = pdir(f, "127x03", "reporting")
    (d / "census.jsonl").unlink()
    os.link(d / "games" / "decoy.json", d / "census.jsonl")
    assert_refused(f, run(f), "REMOTE REFUSE", "hard-link alias: st_nlink=2", logins=[("127x03", False)])


def test_fifo_refused_without_blocking(fake_hosts):
    f = fake_hosts
    d = pdir(f, "127x04", "replacement-r1")
    (d / "mhz.jsonl").unlink()
    os.mkfifo(d / "mhz.jsonl")
    assert_refused(f, run(f), "not a regular file", logins=P2)


def test_change_during_copy_refuses_and_keeps_partial(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_MUTATE"] = "127x03:" + R3 + "/mhz.jsonl"
    receipt = assert_refused(f, run(f), "changed during the copy", dest_exists=True,
                             logins=[("127x03", False), ("127x04", False), ("127x03", True), ("127x03", False)])
    assert len(receipt["partial_files"]) == 10 and receipt["dest_created"] is True
    assert (f["dest"] / "127x03/replacement-r4/mhz.jsonl").exists()


def test_growth_between_p_and_c_refused_before_streaming(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_GROW"] = "127x03:" + R3 + "/census.jsonl"
    receipt = assert_refused(f, run(f), "size/device/inode changed since login P", "ended early", dest_exists=True,
                             logins=[("127x03", False), ("127x04", False), ("127x03", True)])
    assert receipt["partial_files"] == []                        # remote refused before writing one byte


def test_replacement_between_p_and_c_refused_before_streaming(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_REPLACE"] = "127x03:" + R3 + "/mhz.jsonl"   # same bytes, new inode
    receipt = assert_refused(f, run(f), "size/device/inode changed since login P", dest_exists=True,
                             logins=[("127x03", False), ("127x04", False), ("127x03", True)])
    assert receipt["partial_files"] == []


def test_extra_stream_bytes_refuse(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_EXTRA"] = "127x04"
    assert_refused(f, run(f), "excess bytes", dest_exists=True)


def test_flooding_stream_is_bounded(fake_hosts):
    """A remote that keeps sending after the inspected lengths: 05 reads sum(sizes) + 1 bytes, kills the login and
    refuses; nothing larger than its inspected size is ever written locally."""
    f = fake_hosts
    f["env"]["FAKE_SSH_FLOOD"] = "127x03"
    started = time.monotonic()
    result = run(f)
    assert time.monotonic() - started < 60
    assert_refused(f, result, "excess bytes", dest_exists=True)
    manifest_sizes = {}
    for phase, namespace in PHASES:
        for name in ("mhz.jsonl", "census.jsonl"):
            manifest_sizes[f"127x03/{phase}/{name}"] = (pdir(f, "127x03", phase) / name).stat().st_size
    local = {p.relative_to(f["dest"]).as_posix(): p.stat().st_size for p in f["dest"].rglob("*.jsonl")}
    assert local == manifest_sizes
    flooded = int((f["tmp"] / "ssh-log.jsonl.flood").read_text()) if (f["tmp"] / "ssh-log.jsonl.flood").exists() else 0
    assert flooded < 256 << 20                                   # the writer was stopped, not drained


def test_same_length_transport_corruption_refused(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_CORRUPT"] = "127x04"
    assert_refused(f, run(f), "local copy SHA differs from on-host SHA", dest_exists=True)


def test_valid_stream_with_remote_rc_37_refused(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_RC"] = "127x03:C:37"
    assert_refused(f, run(f), "rc=37", dest_exists=True,
                   logins=[("127x03", False), ("127x04", False), ("127x03", True)])


def test_ssh_failure_refuses(fake_hosts):
    f = fake_hosts
    f["env"]["FAKE_SSH_FAIL_HOST"] = "127x04"
    assert_refused(f, run(f), "rc=255", logins=P2)


def test_live_run_requires_window_ack_with_receipt(fake_hosts):
    f = fake_hosts
    receipt = assert_refused(f, run(f, window=False), "--outside-end-window", logins=[])
    assert receipt["logins"] == [] and receipt["dest_created"] is False


def test_existing_dest_refuses_with_receipt(fake_hosts):
    f = fake_hosts
    f["dest"].mkdir()
    result = run(f)
    assert result.returncode == 2 and "must not exist" in result.stderr and not f["log"].exists()
    assert len(refusal_receipts(f)) == 1 and list(f["dest"].iterdir()) == []


def test_dest_below_symlinked_ancestor_refused_and_alias_untouched(fake_hosts):
    f = fake_hosts
    elsewhere = f["tmp"] / "elsewhere"
    elsewhere.mkdir()
    os.symlink(elsewhere, f["dest_root"] / "alias")
    result = run(f, dest=f["dest_root"] / "alias" / "end-sources")
    assert result.returncode == 2 and "not canonical" in result.stderr and not f["log"].exists()
    assert list(elsewhere.iterdir()) == [] and len(refusal_receipts(f)) == 1


def test_dest_outside_declared_root_refused(fake_hosts):
    f = fake_hosts
    result = run(f, dest=f["tmp"] / "outside")
    assert result.returncode == 2 and "strictly below" in result.stderr and not (f["tmp"] / "outside").exists()
    assert len(refusal_receipts(f)) == 1 and not f["log"].exists()


def test_argument_error_writes_receipt(fake_hosts):
    f = fake_hosts
    result = py(S1, "--repository", CLASHER, "--no-such-option", env=f["env"])
    assert result.returncode == 2 and "argument error" in result.stderr
    assert refusal_receipts(f)[0]["error"].startswith("argument error")


def test_invalid_commit_writes_receipt(fake_hosts):
    f = fake_hosts
    result = py(S1, "--repository", CLASHER, "--commit", "abc", "--dest", f["dest"], "--outside-end-window", "t",
                env=f["env"])
    assert result.returncode == 2 and "40-hex" in result.stderr
    assert len(refusal_receipts(f)) == 1 and not f["log"].exists() and not f["dest"].exists()


def test_refusal_dir_symlink_never_written(fake_hosts):
    f = fake_hosts
    target = f["tmp"] / "redirected"
    target.mkdir()
    os.symlink(target, f["refusals"])
    result = run(f, window=False)
    assert result.returncode == 2 and "RECEIPT NOT WRITTEN" in result.stderr
    assert list(target.iterdir()) == []


def test_exclusive_no_follow_writer_unit(tmp_path):
    s1 = load_s1()
    victim = tmp_path / "victim"
    victim.write_text("keep")
    os.symlink(victim, tmp_path / "planted")
    (tmp_path / "existing").write_text("keep")
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in ("planted", "existing"):
            with pytest.raises(s1.Refusal):
                s1.write_exclusive(fd, name, b"overwrite")
        s1.write_exclusive(fd, "fresh", b"new")
    finally:
        os.close(fd)
    assert victim.read_text() == "keep" and (tmp_path / "existing").read_text() == "keep"
    assert (tmp_path / "fresh").read_bytes() == b"new"


def test_forbidden_path_guard_unit():
    s1 = load_s1()
    with pytest.raises(s1.Refusal):
        s1.phase_dir("127x04", "../jobs/clasher/x", "reporting")
    s1.JOB_ROOTS["127x04"] = "/mpac/sdicks02/jobs/clasher"
    with pytest.raises(s1.Refusal):
        s1.phase_dir("127x04", "k4s-confirm-reporting-r1", "reporting")


def test_test_marker_and_production_ssh_unit(monkeypatch, fake_hosts, tmp_path):
    s1 = load_s1()
    monkeypatch.setenv("K4S_S1_TEST_MODE", "yes")
    with pytest.raises(s1.Refusal):
        s1.test_mode()
    monkeypatch.delenv("K4S_S1_TEST_MODE")
    assert s1.test_mode() is False
    root = os.path.realpath(tmp_path)
    monkeypatch.setattr(s1, "DEST_ROOT", root)
    monkeypatch.setenv("PATH", fake_hosts["env"]["PATH"])
    args = type("A", (), dict(repository=CLASHER, commit=fake_hosts["commit"], dest=root + "/d", ssh="ssh",
                              outside_end_window="t", dry_run=False))
    with pytest.raises(s1.Refusal, match="production ssh must be /usr/bin/ssh"):
        s1.run(args, s1.Context(), log=lambda *_: None)
    assert not os.path.exists(root + "/d")


# ---------------------------------------------------------------- r6: ssh exit after stdout EOF (A1 refusal rc -9)

def test_r6_ssh_exiting_after_stdout_eof_is_awaited_six_logins(fake_hosts):
    """Every fake login closes stdout, then lingers 0.5 s before exiting (as OpenSSH does). r2 killed it (rc -9)."""
    f = fake_hosts
    f["env"]["FAKE_SSH_LINGER"] = "0.5"
    result = run(f)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((f["dest"] / "s1-copy-manifest.json").read_text())
    assert manifest["status"] == "copied" and manifest["ssh_logins"] == 6 and len(manifest["files"]) == 20
    assert refusal_receipts(f) == []


def _lingering_ssh(tmp_path, linger):
    shim = tmp_path / "ssh-linger"
    shim.write_text("#!/bin/sh\necho out\nexec 1>&-\nsleep %s\nexit 0\n" % linger)
    shim.chmod(0o755)
    return str(shim)


def test_r6_exit_within_grace_is_success_unit(tmp_path):
    s1 = load_s1()
    for linger in ("0", "0.3"):
        session = s1.Session(_lingering_ssh(tmp_path, linger), lambda *a: None)
        assert session.run("127x03", "true", "P") == b"out\n"
        assert session.logins[-1]["returncode"] == 0


def test_r6_exit_beyond_grace_is_killed_and_refused_unit(tmp_path, monkeypatch):
    s1 = load_s1()
    monkeypatch.setattr(s1, "EXIT_GRACE", 0.2)
    session = s1.Session(_lingering_ssh(tmp_path, "5"), lambda *a: None)
    try:
        session.run("127x03", "true", "P")
    except s1.Refusal as error:
        assert "rc=-9" in str(error)
    else:
        raise AssertionError("a login that does not exit within EXIT_GRACE must refuse")
    assert session.logins[-1]["returncode"] == -9
