"""S10 against the fake ssh shim (FAKE_SSH_ROOT/<host> plays the host). Real S3 guard job, real S9 runtime;
synthetic Q6 inputs (constants monkeypatched) and synthetic S4 bundles."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import S3, S9, S10, logins, make_writable_copy, on_host, sha

GUARD_TARGET = "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00"
BASE03 = "/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1"
STAND_INS = {name: (name * 20).encode() for name in S10.PRODUCTION_PINS}


@pytest.fixture(autouse=True)
def stand_in_production_pins(monkeypatch):
    """Bundles here carry small stand-ins for the six production model/state files."""
    monkeypatch.setattr(S10, "PRODUCTION_PINS", {name: sha(data) for name, data in STAND_INS.items()})


@pytest.fixture
def inputs_dir(tmp_path, monkeypatch):
    d = tmp_path / "t1-inputs"
    d.mkdir()
    table = {}
    for name in S10.INPUTS:
        data = (name * 50).encode()
        (d / name).write_bytes(data)
        table[name] = (sha(data), len(data))
    (d / "golden.json").write_text("{}")                         # present in the source, never shipped
    monkeypatch.setattr(S10, "INPUTS", table)
    return d


def make_bundle(root, host, guard_out, runtime_out, name="b-rd00-a00", extra=None, pin_change=None, profile_host=None,
                admission_bytes=None, drop_admission=None):
    gm = json.loads((guard_out / "guard-job-manifest.json").read_text())
    rm = json.loads((runtime_out / "runtime-manifest.json").read_text())
    job = guard_out / gm["job_name"]
    d = root / name
    files = {}

    def put(rel, data):
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(data)
        files[rel] = sha(data)

    put("t1-freeze.json", (job / "FROZEN-T1.json").read_bytes())
    admissions = {}
    for n in gm["admissions"]:
        if n == drop_admission:
            continue
        put("guard-admissions/" + n, admission_bytes if admission_bytes and n == "system-bus-admission.json"
            else (job / n).read_bytes())
        admissions[n] = "guard-admissions/" + n
    seeds = {}
    for b in gm["bindings"]:
        put("seed-inputs/" + b["path"], (job / "repo" / b["path"]).read_bytes())
        seeds[b["path"]] = "seed-inputs/" + b["path"]
    for stand_in, data in STAND_INS.items():
        put(stand_in, data)
    if pin_change:
        files[pin_change] = "0" * 64
    manifest = dict(schema="clasher.e4v3.inputs.v1", profile="fleet-reference", files=files,
                    runtime_files=rm["runtime_files"], measurement_files=rm["measurement_files"],
                    reference_load_profile=dict(host=profile_host or host, slot_count=11, guard=dict(
                        job=gm["target_job"], root="t1-guard", freeze="t1-freeze.json", admissions=admissions,
                        seed_inputs=seeds)))
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (d / "tiers-pins.json").write_bytes(raw)
    (d / "tiers-pins.sha256").write_text(f"{sha(raw)}  tiers-pins.json\n")
    if extra:
        (d / extra).write_text("x")
    return d


def run(monkeypatch, fake, argv, env=None):
    for key, value in (env or fake["env"]).items():
        monkeypatch.setenv(key, value)
    return S10.main(argv)


def base_argv(tmp_path, guard03, runtime_build, inputs_dir, bundle):
    return ["--host", "127x03", "--inputs", "--inputs-source", str(inputs_dir), "--bundle", str(bundle),
            "--guard-job", str(guard03), "--runtime-manifest-for-checks", str(runtime_build),
            "--record", str(tmp_path / "record"), "--outside-end-window", "A2 GO test"]


# Ancestors that P/TV only test (`test -d`, `test ! -L`, `stat`), plus the tar extract root.
ALLOWED_EXTRA = {"/mpac", "/mpac/sdicks02", "/mpac/sdicks02/jobs", "/mpac/sdicks02/jobs/clasher", "/mpac/sdicks02/jobs-k4s"}


def named_paths(command):
    return set(re.findall(r"/mpac/sdicks02[A-Za-z0-9._/-]*", command))


def test_happy_inputs_bundle_guard(monkeypatch, fake_hosts, tmp_path, guard03, runtime_build, inputs_dir):
    bundle = make_bundle(tmp_path, "127x03", guard03, runtime_build)
    rc = run(monkeypatch, fake_hosts, base_argv(tmp_path, guard03, runtime_build, inputs_dir, bundle))
    assert rc == 0
    calls = logins(fake_hosts["log"])
    assert len(calls) == 3 and all(c["host"] == "127x03" for c in calls)
    assert "tar -x" in calls[1]["command"] and "mv -T" in calls[2]["command"] and "mv" not in calls[0]["command"]
    for call in calls:
        assert {"BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes"} <= set(call["opts"])
        for path in named_paths(call["command"]):
            if path not in ALLOWED_EXTRA:
                S10.check_remote("127x03", path)
        assert not re.search(r"(^|[;\n&|(] *)(rm|rmdir|unlink) ", call["command"]) and "t1-20261010" not in call["command"]
    # inputs: bytes and read-only
    remote_inputs = on_host(fake_hosts, "127x03", BASE03 + "/t1-background-inputs")
    assert sorted(os.listdir(remote_inputs)) == sorted(S10.INPUTS)
    for name in S10.INPUTS:
        assert (remote_inputs / name).read_bytes() == (inputs_dir / name).read_bytes()
        assert os.stat(remote_inputs / name).st_mode & 0o222 == 0
    assert os.stat(remote_inputs).st_mode & 0o777 == 0o555
    # bundle
    remote_bundle = on_host(fake_hosts, "127x03", BASE03 + "/bundles/" + bundle.name)
    assert (remote_bundle / "tiers-pins.json").read_bytes() == (bundle / "tiers-pins.json").read_bytes()
    # guard job: files 0444, dir writable, git proofs on the "host" copy
    job = on_host(fake_hosts, "127x03", GUARD_TARGET)
    assert sorted(os.listdir(job)) == ["FROZEN-T1.json", "idle-services.json", "repo", "system-bus-admission.json"]
    assert os.stat(job).st_mode & 0o777 == 0o755
    for name in ("FROZEN-T1.json", "idle-services.json", "system-bus-admission.json"):
        assert os.stat(job / name).st_mode & 0o777 == 0o444
        assert (job / name).read_bytes() == (guard03 / "k4s-end-guard-r1-rd00-a00" / name).read_bytes()
    for commit in S3.Q3_COMMITS:
        assert subprocess.run(["git", "-C", str(job / "repo"), "cat-file", "-e", commit + "^{commit}"]).returncode == 0
    assert not list(Path(fake_hosts["root"]).rglob("*.partial"))
    record = json.loads((tmp_path / "record" / "s10-staging-manifest.json").read_text())
    assert record["ssh_logins"] == 3 and record["status"] == "staged"
    assert [c["kind"] for c in record["components"]] == ["inputs", "bundle", "guard-job"]
    assert record["components"][1]["guard_job_bytes_equal"] is True and record["components"][1]["runtime_consistent"]


def test_happy_runtime_real_tree(monkeypatch, fake_hosts, tmp_path, runtime_build):
    rc = run(monkeypatch, fake_hosts, ["--host", "127x04", "--runtime", str(runtime_build), "--record",
                                       str(tmp_path / "rec"), "--outside-end-window", "GO"])
    assert rc == 0
    manifest = json.loads((runtime_build / "runtime-manifest.json").read_text())
    remote = on_host(fake_hosts, "127x04", f"/mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1/runtime-{manifest['commit'][:12]}")
    assert S9.runtime_files(remote) == manifest["runtime_files"]
    assert S9.inventory(remote) == manifest["inventory"]
    assert not any(os.lstat(os.path.join(d, f)).st_mode & 0o222 for d, _, fs in os.walk(remote) for f in fs)
    assert not on_host(fake_hosts, "127x04", "/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1").exists()


def test_dry_run(monkeypatch, fake_hosts, tmp_path, guard03, runtime_build, inputs_dir, capsys):
    bundle = make_bundle(tmp_path, "127x03", guard03, runtime_build)
    argv = base_argv(tmp_path, guard03, runtime_build, inputs_dir, bundle) + ["--dry-run"]
    assert run(monkeypatch, fake_hosts, argv) == 0
    assert not fake_hosts["log"].exists() and not (tmp_path / "record").exists()
    assert capsys.readouterr().out.count("# login ") == 3


@pytest.mark.parametrize("case", ["target_exists", "partial_exists", "disk", "corrupt_on_host", "flip_on_host",
                                  "fail_finalize", "chmod_noop"])
def test_host_side_refusals(monkeypatch, fake_hosts, tmp_path, guard03, runtime_build, inputs_dir, case):
    bundle = make_bundle(tmp_path, "127x03", guard03, runtime_build)
    env = dict(fake_hosts["env"])
    want_logins = {"target_exists": 1, "partial_exists": 1, "disk": 1, "corrupt_on_host": 2, "flip_on_host": 2,
                   "fail_finalize": 3, "chmod_noop": 3}[case]
    if case == "target_exists":
        on_host(fake_hosts, "127x03", GUARD_TARGET).mkdir(parents=True)
    if case == "partial_exists":
        on_host(fake_hosts, "127x03", BASE03 + "/t1-background-inputs.partial").mkdir(parents=True)
    if case == "disk":
        monkeypatch.setattr(S10, "HEADROOM", 10 ** 18)
    if case == "corrupt_on_host":
        env["FAKE_TAR_CORRUPT"] = "k4s-end-guard-r1-rd00-a00.partial/system-bus-admission.json"
    if case == "flip_on_host":
        env["FAKE_TAR_FLIP"] = "t1-background-inputs.partial/states.pkl"
    if case == "fail_finalize":
        env["FAKE_SSH_FAIL_AT"] = "3"
    if case == "chmod_noop":
        env["FAKE_CHMOD_NOOP"] = "1"
    rc = run(monkeypatch, fake_hosts, base_argv(tmp_path, guard03, runtime_build, inputs_dir, bundle), env)
    assert rc == 2
    assert len(logins(fake_hosts["log"])) == want_logins
    refusal = json.loads((tmp_path / "record" / "S10-REFUSAL.json").read_text())
    assert refusal["status"] == "refused" and GUARD_TARGET + ".partial" in refusal["leftover_partials_needing_authorized_cleanup"]
    assert not (tmp_path / "record" / "s10-staging-manifest.json").exists()
    if case == "flip_on_host":
        assert "TV inputs: on-host SHA differs" in refusal["error"]
    if case == "chmod_noop":
        assert "not in place with mode" in refusal["error"] or "writable entries remain" in refusal["error"]
    if case == "corrupt_on_host":
        assert "differs on host" in refusal["error"] or "on-host SHA differs" in refusal["error"]
        assert on_host(fake_hosts, "127x03", GUARD_TARGET + ".partial").exists()          # never finalized
        assert not on_host(fake_hosts, "127x03", GUARD_TARGET).exists()


@pytest.mark.parametrize("case", ["extra_file", "pin_mismatch", "wrong_host", "admission_differs", "runtime",
                                  "production_pin", "no_idle_on_03"])
def test_bundle_refusals_before_any_login(monkeypatch, fake_hosts, tmp_path, guard03, runtime_build, inputs_dir, case):
    kwargs = dict(extra_file=dict(extra="notes.txt"), wrong_host=dict(profile_host="127x04"),
                  admission_differs=dict(admission_bytes=b"{}\n"), runtime={}, pin_mismatch=dict(pin_change="states.pkl"),
                  production_pin={}, no_idle_on_03=dict(drop_admission="idle-services.json"))[case]
    bundle = make_bundle(tmp_path, "127x03", guard03, runtime_build, **kwargs)
    if case == "production_pin":
        monkeypatch.setitem(S10.PRODUCTION_PINS, "v1.pt", "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed")
    argv = base_argv(tmp_path, guard03, runtime_build, inputs_dir, bundle)
    if case == "no_idle_on_03":                    # bundle alone (no guard job in this run): the per-host set check
        i = argv.index("--guard-job")
        del argv[i:i + 2]
    if case == "runtime":
        other = make_writable_copy(runtime_build, tmp_path / "rt-other")
        m = json.loads((other / "runtime-manifest.json").read_text())
        m["runtime_files_sha256"] = "0" * 64
        (other / "runtime-manifest.json").write_text(json.dumps(m))
        argv[argv.index("--runtime-manifest-for-checks") + 1] = str(other)
    assert run(monkeypatch, fake_hosts, argv) == 2
    assert not fake_hosts["log"].exists()
    assert json.loads((tmp_path / "record" / "S10-REFUSAL.json").read_text())["logins"] == []


def test_guard_job_for_other_host_refused(monkeypatch, fake_hosts, tmp_path, guard03):
    rc = run(monkeypatch, fake_hosts, ["--host", "127x04", "--guard-job", str(guard03), "--record",
                                       str(tmp_path / "r"), "--outside-end-window", "GO"])
    assert rc == 2 and not fake_hosts["log"].exists()


def test_inputs_sha_mismatch_refused(monkeypatch, fake_hosts, tmp_path, inputs_dir):
    (inputs_dir / "states.pkl").write_bytes(b"different")
    rc = run(monkeypatch, fake_hosts, ["--host", "127x03", "--inputs", "--inputs-source", str(inputs_dir),
                                       "--record", str(tmp_path / "r"), "--outside-end-window", "GO"])
    assert rc == 2 and not fake_hosts["log"].exists()


def test_window_and_record_checked_before_login(monkeypatch, fake_hosts, tmp_path, inputs_dir):
    argv = ["--host", "127x03", "--inputs", "--inputs-source", str(inputs_dir), "--record", str(tmp_path / "r")]
    assert run(monkeypatch, fake_hosts, argv) == 2                      # no window: receipt, no login
    assert "outside-end-window" in json.loads((tmp_path / "r" / "S10-REFUSAL.json").read_text())["error"]
    assert run(monkeypatch, fake_hosts, argv + ["--outside-end-window", "GO"]) == 2   # record exists: no receipt
    assert os.listdir(tmp_path / "r") == ["S10-REFUSAL.json"] and not fake_hosts["log"].exists()


def test_record_confinement(monkeypatch, fake_hosts, tmp_path, inputs_dir, foreign_dir):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    for record in (tmp_path / "link" / "r", foreign_dir / "r"):
        assert run(monkeypatch, fake_hosts, ["--host", "127x03", "--inputs", "--inputs-source", str(inputs_dir),
                                             "--record", str(record), "--outside-end-window", "GO"]) == 2
    assert os.listdir(tmp_path / "real") == [] and os.listdir(foreign_dir) == []
    assert not fake_hosts["log"].exists()


@pytest.mark.parametrize("alias", ["base", "guard_parent"])
def test_symlinked_remote_ancestor_refused_at_p(monkeypatch, fake_hosts, tmp_path, guard03, inputs_dir, alias):
    elsewhere = on_host(fake_hosts, "127x03", "/mpac/sdicks02/jobs/clasher/t1-20261010-r1")
    elsewhere.mkdir(parents=True)
    if alias == "base":
        on_host(fake_hosts, "127x03", BASE03).symlink_to(elsewhere)
        argv = ["--host", "127x03", "--inputs", "--inputs-source", str(inputs_dir)]
    else:
        parent = on_host(fake_hosts, "127x03", "/mpac/sdicks02/jobs/clasher")
        shutil.move(str(parent), str(parent.parent / "clasher-real"))
        parent.symlink_to(parent.parent / "clasher-real")
        argv = ["--host", "127x03", "--guard-job", str(guard03)]
    rc = run(monkeypatch, fake_hosts, argv + ["--record", str(tmp_path / "r"), "--outside-end-window", "GO"])
    assert rc == 2 and len(logins(fake_hosts["log"])) == 1
    assert "symlink" in json.loads((tmp_path / "r" / "S10-REFUSAL.json").read_text())["error"]
    assert os.listdir(elsewhere) == []


def test_hashing_reader_detects_change(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"abc")
    reader = S10.HashingReader(f, sha(b"abd"), 3)
    reader.read(10)
    with pytest.raises(S10.Refusal, match="changed while streaming"):
        reader.close()


@pytest.mark.parametrize("host,path,ok", [
    ("127x03", BASE03 + "/runtime-0123456789ab", True),
    ("127x03", BASE03 + "/bundles/b1.partial", True),
    ("127x03", GUARD_TARGET + ".partial", True),
    ("127x03", "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/x", False),
    ("127x03", "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/x", False),
    ("127x03", "/mpac/sdicks02/jobs/clasher/k4s-confirm-r1-stage/x", False),
    ("127x03", "/mpac/sdicks02/repos/clasher-v4-cache/x", False),
    ("127x03", "/mpac/sdicks02/jobs/clasher/other", False),
    ("127x03", BASE03 + "/../t1-20261010-r1", False),
    ("127x04", "/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1", False),
    ("127x04", "/mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1/t1-background-inputs", True),
    ("127x04", "/mpac/sdicks02/jobs-k4s/k4s-prep-20261011/x", False),
    ("127x04", "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00", True),
])
def test_check_remote(host, path, ok):
    if ok:
        assert S10.check_remote(host, path) == path
    else:
        with pytest.raises(S10.Refusal):
            S10.check_remote(host, path)


def test_cli_dry_run_subprocess(fake_hosts, guard03):
    from conftest import py
    result = py("s10_stage_host.py", "--host", "127x03", "--guard-job", guard03, "--dry-run", env=fake_hosts["env"])
    assert result.returncode == 0 and result.stdout.count("# login ") == 3 and not fake_hosts["log"].exists()


def test_forbidden_prefixes_hold_even_if_a_base_were_misconfigured(monkeypatch):
    """Defense in depth: FORBIDDEN refuses T1/reporting/repos paths even if END_BASES pointed into them."""
    for bad in ("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end", "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/end",
                "/mpac/sdicks02/repos/clasher-v4-cache/end"):
        monkeypatch.setitem(S10.END_BASES, "127x03", bad)
        with pytest.raises(S10.Refusal, match="forbidden"):
            S10.check_remote("127x03", bad + "/runtime-x")


def test_guard_only_chmod_noop_caught_by_writable_check(monkeypatch, fake_hosts, tmp_path, guard03):
    env = dict(fake_hosts["env"], FAKE_CHMOD_NOOP="1")
    rc = run(monkeypatch, fake_hosts, ["--host", "127x03", "--guard-job", str(guard03), "--record",
                                       str(tmp_path / "r"), "--outside-end-window", "GO"], env)
    assert rc == 2 and len(logins(fake_hosts["log"])) == 3
    assert "writable entries remain" in json.loads((tmp_path / "r" / "S10-REFUSAL.json").read_text())["error"]



def test_run_bounded_limits_and_timeout():
    from conftest import ROOT
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    import end_prep_common as C
    with pytest.raises(C.Refusal, match="exceeds"):
        C.run_bounded(["/bin/sh", "-c", "head -c 5000000 /dev/zero"], 30, 1 << 20)
    with pytest.raises(C.Refusal, match="timed out"):
        C.run_bounded(["/bin/sleep", "30"], 1, 1024)
    rc, out, _ = C.run_bounded(["/bin/sh", "-c", "printf ok; exit 3"], 30, 1024)
    assert (rc, out) == (3, b"ok")
