"""S1b r2: safe_input remote reader per host (2 logins), exact names, nlink == 1 on the host (S1b-F1), E3 output
layout, receipts for every refusal, pinned history read through the git helper."""
import json
import os

import pytest

from conftest import (C, S1B, CANARY, FakeHosts, admissions, bus_admission, canary_file, idle_admission, make_file,
                      ok, read, refused, s1b_args, sha, si)


def run(world, hosts, dest, **kw):
    return S1B.run(s1b_args(world, dest, **kw), log=lambda *a: None)


def receipts(dest):
    return sorted(n for n in os.listdir(dest) if n.startswith("S1B-REFUSAL-"))


def only_receipt(dest):
    names = os.listdir(dest)
    ok(len(names) == 1 and names[0].startswith("S1B-REFUSAL-"), names)
    return json.loads(read(os.path.join(dest, names[0])))


def job(hosts, host):
    return hosts.path(host, "%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE))


def test_requests_name_exactly_the_three_files_and_the_probe():
    for host in S1B.HOSTS:
        request = json.loads(si.build_remote_request(S1B.remote_policy(host), S1B.remote_items(host),
                                                     S1B.max_content(host)))
        rels = [(i["kind"], i["rel"], i["root"]) for i in request["items"]]
        want = [("absent", S1B.NEXT_NAMESPACE, S1B.JOB_ROOTS[host])]
        want += [("file", "%s/%s" % (S1B.NAMESPACE, n), S1B.JOB_ROOTS[host]) for n in S1B.NAMES[host]]
        ok(rels == want and all(i["grants"] == ["reporting-job-exact"] for i in request["items"]))
    ok(S1B.JOB_ROOTS == {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"})


def test_remote_role_cannot_name_anything_else():
    policy = S1B.remote_policy("127x03")
    for rel in ("k4s-confirm-replacement-r3/system-bus-admission.json", "k4s-confirm-replacement-r4/games/x.json",
                "k4s-confirm-replacement-r4/complete.json", "k4s-confirm-replacement-r4/other.json"):
        with pytest.raises(si.Refusal):
            si.build_remote_request(policy, [{"role": "job", "rel": rel, "kind": "file", "content": True}], 1 << 20)


def test_dry_run_no_ssh_no_writes(world, hosts, tmpdir_):
    lines = []
    S1B.run(s1b_args(world, None, dry_run=True), log=lines.append)
    ok(hosts.logins() == [] and os.listdir(tmpdir_) == [])
    ok(any(l.startswith("# login 127x03") for l in lines) and si.remote_program_sha256() in lines[0])


def test_happy_path_two_logins_reader_program(world, hosts, tmpdir_):
    dest = os.path.join(tmpdir_, "dest")
    manifest = run(world, hosts, dest)
    logins = hosts.logins()
    ok(len(logins) == 2 and manifest["ssh_logins"] == 2)
    for line, host in zip(logins, ("127x03", "127x04")):
        words = line.split()
        ok(words[words.index("--") + 1:words.index("--") + 9][:8] == [host, "nice", "-n", "19", "/usr/bin/python3",
                                                                       "-I", "-S", "-"], line[:200])
        ok("/mpac/sdicks02/jobs/" not in line or host == "127x03")
    ok(manifest["reader_program_sha256"] == C.REMOTE_PROGRAM_SHA256)
    names = sorted(os.listdir(os.path.join(dest, "end-guard-admissions")))
    ok(names == ["127x03-idle-services.json", "127x03-system-bus-admission.json", "127x04-system-bus-admission.json"])


def test_probe_hard_linked_admission_refused_before_any_read(world, hosts, tmpdir_):
    """Sol S1b-F1: an admission leaf hard-linked to a separate canary must refuse on the host (st_nlink) before any
    byte is read; nothing but the refusal receipt is written locally; 04 is never contacted."""
    path = os.path.join(job(hosts, "127x03"), "system-bus-admission.json")
    os.unlink(path)
    canary = canary_file(os.path.join(hosts.base, "elsewhere"))
    os.link(canary, path)
    dest = os.path.join(tmpdir_, "dest")
    error = refused("remote-refused", run, world, hosts, dest)
    ok(error.reason.startswith("nlink:"), error.reason)
    ok(len(hosts.logins()) == 1 and read(canary) == CANARY)
    receipt = only_receipt(dest)
    ok(receipt["code"] == "remote-refused" and "nlink" in receipt["reason"] and CANARY.decode() not in json.dumps(receipt))


@pytest.mark.parametrize("case,code", [
    ("leaf-symlink", "symlink"), ("dir-symlink", "symlink"), ("fifo", "not-regular"), ("oversize", "size"),
    ("missing", "missing"), ("r5-exists", "exists"), ("r5-dangling", "exists")])
def test_host_side_refusals(world, hosts, tmpdir_, case, code):
    j = job(hosts, "127x03")
    leaf = os.path.join(j, "idle-services.json")
    if case == "leaf-symlink":
        os.unlink(leaf)
        os.symlink(canary_file(os.path.join(hosts.base, "elsewhere")), leaf)
    elif case == "dir-symlink":
        moved = j + "-moved"
        os.rename(j, moved)
        os.symlink(moved, j)
    elif case == "fifo":
        os.unlink(leaf)
        os.mkfifo(leaf)
    elif case == "oversize":
        make_file(leaf, b"x" * (S1B.MAX_BYTES + 1))
    elif case == "missing":
        os.unlink(leaf)
    elif case == "r5-exists":
        os.makedirs(hosts.path("127x03", S1B.JOB_ROOTS["127x03"] + "/" + S1B.NEXT_NAMESPACE))
    else:
        os.symlink("/nonexistent", hosts.path("127x03", S1B.JOB_ROOTS["127x03"] + "/" + S1B.NEXT_NAMESPACE))
    dest = os.path.join(tmpdir_, "dest")
    error = refused("remote-refused", run, world, hosts, dest)
    ok(error.reason.startswith(code + ":") or (code == "symlink" and error.reason.startswith("not-dir:")), error.reason)
    ok(len(hosts.logins()) == 1)
    only_receipt(dest)


@pytest.mark.parametrize("host,name,data", [
    ("127x03", "system-bus-admission.json", bus_admission("127x03", pid=9999)),
    ("127x04", "system-bus-admission.json", bus_admission("127x03")),
    ("127x03", "idle-services.json", idle_admission(pid=1)),
    ("127x03", "idle-services.json", b'{"host": "127x03", "host": "127x03"}\n')])
def test_identity_and_content_refusals(world, hosts, tmpdir_, host, name, data):
    make_file(os.path.join(job(hosts, host), name), data)
    dest = os.path.join(tmpdir_, "dest")
    with pytest.raises(si.Refusal):
        run(world, hosts, dest)
    only_receipt(dest)


@pytest.mark.parametrize("mode", ["junk", "flip"])
def test_transport_corruption_refused(world, hosts, tmpdir_, mode):
    hosts.write_shim(mode=mode)
    dest = os.path.join(tmpdir_, "dest")
    with pytest.raises(si.Refusal) as info:
        run(world, hosts, dest)
    ok(info.value.code in ("remote", "json"), str(info.value))
    only_receipt(dest)


def test_ssh_failure_on_second_login(world, hosts, tmpdir_):
    hosts.write_shim(fail_at=2)
    dest = os.path.join(tmpdir_, "dest")
    refused("subprocess", run, world, hosts, dest)
    receipt = only_receipt(dest)
    ok(len(receipt["context"]["logins"]) == 2)


def test_window_acknowledgement_required(world, hosts, tmpdir_):
    dest = os.path.join(tmpdir_, "dest")
    refused("policy", run, world, hosts, dest, outside_end_window="")
    only_receipt(dest)
    ok(hosts.logins() == [])


def test_history_must_be_the_pinned_bytes(world, hosts, tmpdir_):
    dest = os.path.join(tmpdir_, "dest")
    old = S1B.HISTORY_SHA256
    S1B.HISTORY_SHA256 = "0" * 64
    try:
        refused("sha", run, world, hosts, dest)
    finally:
        S1B.HISTORY_SHA256 = old
    only_receipt(dest)
    ok(hosts.logins() == [])


def test_bad_commit_refused(world, hosts, tmpdir_):
    dest = os.path.join(tmpdir_, "dest")
    refused("policy", run, world, hosts, dest, commit="HEAD")
    only_receipt(dest)


@pytest.mark.parametrize("where", ["exists", "not-permitted", "symlinked-parent"])
def test_dest_confinement(world, hosts, tmpdir_, where):
    if where == "exists":
        dest = os.path.join(tmpdir_, "dest")
        os.makedirs(dest)
        refused("exists", run, world, hosts, dest)
        ok(os.listdir(dest) == [])
    elif where == "not-permitted":
        refused("path", run, world, hosts, "/dev/shm/k4s-s1b-never")
        ok(not os.path.exists("/dev/shm/k4s-s1b-never"))
    else:
        real = os.path.join(tmpdir_, "real")
        os.makedirs(real)
        os.symlink(real, os.path.join(tmpdir_, "alias"))
        refused("root", run, world, hosts, os.path.join(tmpdir_, "alias", "dest"))
        ok(os.listdir(real) == [])
    ok(hosts.logins() == [])


def test_git_env_indirection_does_not_change_the_history_read(world, hosts, tmpdir_, monkeypatch):
    """P2-4: inherited GIT_* variables cannot redirect the pinned history read (the helper scrubs them)."""
    foreign = os.path.join(tmpdir_, "foreign")
    os.makedirs(foreign)
    world.git(foreign, "init", "-q")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY", "GIT_INDEX_FILE"):
        monkeypatch.setenv(key, foreign + "/.git")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'core.hooksPath'='/nonexistent'")
    policy = si.Policy(C.local_host(), [S1B.repo_role(world.repo_full)])
    ok(S1B.committed_latest(policy, world.repo_full, world.P) == S1B.HISTORY_SHA256)


def test_check_admission_units():
    ok(S1B.check_admission("127x04", "system-bus-admission.json", admissions("127x04")["system-bus-admission.json"])
       ["pid"] == 2005)
    refused("check", S1B.check_admission, "127x04", "idle-services.json", idle_admission("127x04"))
    doc = json.loads(bus_admission("127x03"))
    doc["identity"]["extra"] = 1
    refused("check", S1B.check_admission, "127x03", "system-bus-admission.json", json.dumps(doc).encode())
    refused("json", S1B.check_admission, "127x03", "system-bus-admission.json", b"{NaN}")
    refused("size", S1B.check_admission, "127x03", "system-bus-admission.json", b"")
