"""S10 r2 on namespaced fake hosts: k4s-end-r1 bases (S10-F2), safe_input reader checks, status-preserving facts
(S10-F3), receive (D4), bundles only and S4 test-only refusal (S10-F4), F/POST, never deleting on a host. Includes
Sol's probes: base symlinked to a foreign dir, failed probes with valid stdout, pre-existing hard-linked targets."""
import json
import os
import shutil

import pytest

from conftest import (C, CANARY, S3, S9, S10, Args, canary_file, make_bundle, make_file, ok, read, refused, s10_args,
                      s3_args, sha, si)

BASE03 = si.END_BASES["127x03"]


def make_base(hosts, host="127x03"):
    base = hosts.path(host, si.END_BASES[host])
    for d in S10.BASE_SUBDIRS:
        os.makedirs(os.path.join(base, d))
    return base


def run(a):
    return S10.run(a, log=lambda *x: None)


def record_receipt(record):
    names = [n for n in os.listdir(record) if n.startswith("S10-REFUSAL-")]
    ok(len(names) == 1, os.listdir(record))
    return json.loads(read(os.path.join(record, names[0])))


def bundle_args(world, runtime, tmpdir_, b, **kw):
    base = dict(runtime_manifest_for_checks=runtime["out"], runtime_manifest_sha256=runtime["sha"],
                bundle=[(b["dir"], b["tiers"], b["receipt"])], record=os.path.join(tmpdir_, "rec"))
    base.update(kw)
    return s10_args(**base)


@pytest.fixture
def bundle(world, runtime, tmpdir_):
    return make_bundle(world, tmpdir_, "bundle-03-rd00-a00", "127x03", runtime["manifest"])


def test_bases_and_layout():
    """r4 (B2): the runtime is <base>/runtime-<P12> (S5 layout / S7 RC-6), not <base>/runtime/runtime-<P12>."""
    ok(S10.END_BASES == {"127x03": "/mpac/sdicks02/jobs/clasher/k4s-end-r1",
                         "127x04": "/mpac/sdicks02/jobs-k4s/k4s-end-r1"})
    ok(S10.BASE_SUBDIRS == ("attempts", "preflight", "bundles"))
    for host in ("127x03", "127x04"):
        base = si.END_BASES[host]
        r = S10.roots(host, "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb")
        ok(r["runtime"] == base + "/runtime-98566c032d0b" and r["bundles"] == base + "/bundles")
        ok(r["repository"] == base + "/repository" and r["attempts"] == base + "/attempts"
           and r["preflight"] == base + "/preflight" and r["guard_parent"] == si.Q4_GUARD_PARENTS[host]
           and r["tools"] == base + "/tools" and r["native"] == base + "/end-inputs-r1/clasher_core.abi3.so"
           and r["corpus"] == base + "/end-inputs-r1/K4-states.pkl")
        ok(S10.roots(host)["runtime"] is None)
    ok(S10.main(["--print-layout"]) == 0)
    with pytest.raises(SystemExit):
        S10.main(["--print-roots"])                                    # r3's draft schema is gone


def test_inputs_option_is_gone():
    with pytest.raises(SystemExit) as info:
        S10.main(["--host", "127x03", "--inputs", "--dry-run"])
    ok(info.value.code == 2)


def test_dry_run_no_ssh_no_writes(world, runtime, bundle, hosts, tmpdir_):
    lines = []
    S10.run(bundle_args(world, runtime, tmpdir_, bundle, record=None, dry_run=True), log=lines.append)
    ok(hosts.logins() == [] and not os.path.exists(os.path.join(tmpdir_, "rec")))
    ok(json.loads(lines[0])["mode"] == "dry-run" and any(l.startswith("# P-check request") for l in lines))


def test_existing_base_bundle_only(world, runtime, bundle, hosts, tmpdir_):
    make_base(hosts)
    m = run(bundle_args(world, runtime, tmpdir_, bundle))
    ok([l["label"] for l in m["logins"]] == ["P-check", "P-facts", "receive-bundle", "F", "POST"])
    final = hosts.path("127x03", BASE03 + "/bundles/" + bundle["name"])
    ok(sorted(os.listdir(final)) == sorted(os.listdir(bundle["dir"])))
    for rel in ("tiers-pins.json", "assembly-receipt.json", "states.pkl", "t1-guard/t1-freeze.json"):
        st = os.lstat(os.path.join(final, rel))
        ok(st.st_nlink == 1 and st.st_mode & 0o777 == 0o444 and read(os.path.join(final, rel)) ==
           read(os.path.join(bundle["dir"], rel)))
    ok(os.lstat(final).st_mode & 0o777 == 0o555)


def test_no_delete_and_pinned_programs_in_every_login(world, runtime, bundle, hosts, tmpdir_):
    make_base(hosts)
    run(bundle_args(world, runtime, tmpdir_, bundle))
    for line in hosts.logins():
        words = line.replace("~", " ").split()
        ok(not {"rm", "rmdir", "unlink", "/usr/bin/rm", "/bin/rm", "tar", "find"} & set(words), line[:200])
    ok(si.receive_program_sha256() in " ".join(hosts.logins()))
    for script in (S10.facts_script(),):
        ok(" rm " not in script and "unlink" not in script)


def test_probe_base_symlinked_to_a_foreign_dir(world, runtime, bundle, hosts, tmpdir_):
    """Sol (S7-F1 class / S10): the declared base replaced by a static symlink to a foreign directory must refuse at
    P-check; nothing is created in the foreign directory."""
    foreign = hosts.path("127x03", "/mpac/sdicks02/foreign-dir")
    for d in S10.BASE_SUBDIRS:
        os.makedirs(os.path.join(foreign, d))
    os.symlink("/mpac/sdicks02/foreign-dir", hosts.path("127x03", BASE03))
    a = bundle_args(world, runtime, tmpdir_, bundle)
    error = refused("remote-refused", run, a)
    ok(error.reason.startswith("root:"), error.reason)
    ok(len(hosts.logins()) == 1 and all(os.listdir(os.path.join(foreign, d)) == [] for d in S10.BASE_SUBDIRS))
    record_receipt(a.record)


def test_probe_guard_parent_symlink_refused(world, s1b_out, runtime, hosts, tmpdir_):
    make_base(hosts)
    out = os.path.join(tmpdir_, "g")
    m = S3.build(s3_args(world, s1b_out, out, round_="01", attempt="00"), log=lambda *x: None)
    parent = hosts.path("127x03", "/mpac/sdicks02/jobs/clasher")
    elsewhere = hosts.path("127x03", "/mpac/sdicks02/elsewhere")
    os.rename(parent, elsewhere)
    os.symlink("/mpac/sdicks02/elsewhere", parent)
    a = s10_args(guard_job=out, guard_job_name=m["job_name"], guard_manifest_sha256=m["_sha256"],
                 record=os.path.join(tmpdir_, "rec"))
    with pytest.raises(si.Refusal):
        run(a)
    ok(len(hosts.logins()) == 1 and not [n for n in os.listdir(elsewhere) if n.startswith("k4s-end-guard")])


@pytest.mark.parametrize("case", ["final", "partial-hardlink", "partial-symlink"])
def test_probe_pre_existing_targets_are_never_written(world, runtime, bundle, hosts, tmpdir_, case):
    """Sol S6-F2 class (argv-style truncation): a pre-existing target or .partial (even holding a hard link to a
    foreign 'keep me' inode) refuses before any byte is written; the foreign inode is unchanged."""
    make_base(hosts)
    keep = canary_file(hosts.path("127x03", "/mpac/sdicks02/keep"))
    bundles = hosts.path("127x03", BASE03 + "/bundles")
    if case == "final":
        os.makedirs(os.path.join(bundles, bundle["name"]))
    elif case == "partial-hardlink":
        os.makedirs(os.path.join(bundles, bundle["name"] + ".partial"))
        os.link(keep, os.path.join(bundles, bundle["name"] + ".partial", "tiers-pins.json"))
    else:
        os.symlink("/mpac/sdicks02/keep", os.path.join(bundles, bundle["name"] + ".partial"))
    a = bundle_args(world, runtime, tmpdir_, bundle)
    error = refused("remote-refused", run, a)
    ok(error.reason.startswith("exists:"), error.reason)
    ok(read(keep) == CANARY and os.lstat(keep).st_nlink == (2 if case == "partial-hardlink" else 1))
    ok(len(hosts.logins()) == 1)


def test_base_must_exist_without_create_and_be_absent_with_it(world, runtime, bundle, hosts, tmpdir_):
    refused("remote-refused", run, bundle_args(world, runtime, tmpdir_, bundle))
    make_base(hosts)
    refused("remote-refused", run, bundle_args(world, runtime, tmpdir_, bundle, create_base=True,
                                               record=os.path.join(tmpdir_, "rec2")))


FAKE_DF = '#!/bin/sh\necho "Filesystem 1-blocks Used Available Capacity Mounted on"\necho "/dev/x 9 1 %s 1%% /mpac"\nexit %d\n'


@pytest.mark.parametrize("tool,script,code", [
    ("df", FAKE_DF % ("999999999999999999", 37), "subprocess"),
    ("who", "#!/bin/sh\necho 'user pts/0 2026-10-12 10:00'\nexit 37\n", "subprocess"),
    ("hostname", "#!/bin/sh\necho 127x03\nexit 37\n", "subprocess"),
    ("hostname", "#!/bin/sh\necho 127x04\n", "host"),
    ("df", FAKE_DF % ("1000", 0), "space")])
def test_probe_facts_status_is_never_masked(world, runtime, bundle, hosts, tmpdir_, tool, script, code):
    """Sol S10-F3: a probe printing valid-looking output then exiting 37 refuses before its output is used."""
    make_base(hosts)
    S10.REMOTE_TOOLS[tool] = hosts.tool("127x03", tool, script)[0]
    a = bundle_args(world, runtime, tmpdir_, bundle)
    refused(code, run, a)
    ok(len(hosts.logins()) == 2 and not os.listdir(hosts.path("127x03", BASE03 + "/bundles")))
    record_receipt(a.record)


@pytest.mark.parametrize("tool,script,where", [
    ("mv", "#!/bin/sh\nexit 1\n", "F"),
    ("mv", '#!/bin/sh\n/usr/bin/cp -a "$4" "$5"\n', "POST"),
    ("chmod", "#!/bin/sh\nexit 0\n", "POST"),
    ("chmod", "#!/bin/sh\nexit 1\n", "F"),
    ("mv", '#!/bin/sh\n/usr/bin/cp -a "$4" "$5" && /usr/bin/mv "$4" "$4.moved"\n', "POST")])
def test_finalize_failures_keep_partials_and_refuse(world, runtime, bundle, hosts, tmpdir_, tool, script, where):
    make_base(hosts)
    S10.REMOTE_TOOLS[tool] = hosts.tool("127x03", tool, script)[0]
    a = bundle_args(world, runtime, tmpdir_, bundle)
    with pytest.raises(si.Refusal):
        run(a)
    labels = [l.split(" -- ")[0] for l in hosts.logins()]
    ok(len(labels) == (4 if where == "F" else 5), labels)
    partial = hosts.path("127x03", BASE03 + "/bundles/" + bundle["name"] + ".partial")
    final = hosts.path("127x03", BASE03 + "/bundles/" + bundle["name"])
    if tool == "mv" and where == "F" or tool == "chmod" and where == "F":
        ok(os.path.isdir(partial) and not os.path.exists(final))
    else:
        ok(os.path.isdir(partial) or os.path.isdir(final))
    receipt = record_receipt(a.record)
    ok(receipt["context"]["host_paths_created_or_attempted_needing_authorized_cleanup"] == [
        BASE03 + "/bundles/" + bundle["name"] + ".partial"])


def test_local_change_while_streaming_refuses_and_keeps_the_partial(world, runtime, bundle, hosts, tmpdir_,
                                                                   monkeypatch):
    make_base(hosts)
    real = si.remote_receive
    path = os.path.join(bundle["dir"], "states.pkl")

    def mutate(*args, **kw):
        os.chmod(path, 0o644)
        make_file(path, b"SYNTHETIC STATEX\n"[:len(read(path))].ljust(len(read(path)), b"x"))
        return real(*args, **kw)
    monkeypatch.setattr(si, "remote_receive", mutate)
    a = bundle_args(world, runtime, tmpdir_, bundle)
    with pytest.raises(si.Refusal) as info:
        run(a)
    ok(info.value.code in ("sha", "remote-refused"), str(info.value))
    ok(os.path.isdir(hosts.path("127x03", BASE03 + "/bundles/" + bundle["name"] + ".partial")))


@pytest.mark.parametrize("case,code", [
    ("synthetic-stamp", "check"), ("stamp-in-field", "check"), ("receipt-not-production", "check"), ("receipt-status", "check"),
    ("synthetic-name", "check"), ("tiers-sha", "sha"), ("receipt-sha", "sha"), ("extra-file", "check"),
    ("pin-mismatch", "check"), ("games-file", "name"), ("hardlink", "nlink"), ("symlink", "symlink"),
    ("production-identity", "check"), ("wrong-host", "check"), ("admissions", "check"),
    ("runtime-mismatch", "check"), ("no-runtime", "policy"), ("guard-outside-q4", "policy"),
    ("complete-json", "name")])
def test_bundle_refusals_before_any_login(world, runtime, hosts, tmpdir_, case, code, monkeypatch):
    """S10-F1 / S10-F4: every bundle input is role-gated and pinned before any login; S4 test-only bundles refuse
    whatever their file pins say."""
    make_base(hosts)
    kw, mo, ro = {}, None, None
    name = "bundle-03-rd00-a00"
    if case == "synthetic-stamp":
        mo = {"k4s_s4_synthetic": "x"}                                # the key alone refuses
    elif case == "stamp-in-field":
        mo = {"specification": {"note": "SYNTHETIC-TEST-ONLY"}}             # the stamp anywhere refuses
    elif case == "receipt-not-production":
        ro = {"production_pins": False}
    elif case == "receipt-status":
        ro = {"status": "SYNTHETIC-TEST-ONLY"}
    elif case == "synthetic-name":
        name = "bundle-SYNTHETIC-03"
    elif case == "wrong-host":
        mo = {"reference_load_profile": {"host": "127x04", "guard": {}}}
    elif case == "guard-outside-q4":
        mo = {"reference_load_profile": {"host": "127x03", "guard": {"job": "/mpac/sdicks02/jobs-k4s/"
                                                                            "k4s-end-guard-r1-rd00-a00"}}}
    elif case == "runtime-mismatch":
        mo = {"measurement_files": {"x.py": "0" * 64}}
    b = make_bundle(world, tmpdir_, name, "127x03", runtime["manifest"], manifest_overrides=mo, receipt_overrides=ro,
                    **kw)
    root = b["dir"]
    canary = canary_file(os.path.join(tmpdir_, "elsewhere"))
    args = dict()
    if case == "tiers-sha":
        b["tiers"] = "0" * 64
    elif case == "receipt-sha":
        b["receipt"] = "0" * 64
    elif case == "extra-file":
        make_file(os.path.join(root, "extra.bin"), b"x")
    elif case == "pin-mismatch":
        os.chmod(os.path.join(root, "v1.pt"), 0o644)
        make_file(os.path.join(root, "v1.pt"), b"synthetic v1 modeX\n")
    elif case == "games-file":
        make_file(os.path.join(root, "games", "g.json"), CANARY)
    elif case == "complete-json":
        make_file(os.path.join(root, "t1-guard", "complete.json"), CANARY)
    elif case == "hardlink":
        os.link(canary, os.path.join(root, "hl.bin"))
    elif case == "symlink":
        os.symlink(canary, os.path.join(root, "ln.bin"))
    elif case == "production-identity":
        from conftest import ORIG
        monkeypatch.setattr(S10, "PRODUCTION_PINS", ORIG[("s10_stage_host", "PRODUCTION_PINS")])
    elif case == "admissions":
        doc = json.loads(read(os.path.join(root, "tiers-pins.json")))
    if case == "no-runtime":
        args.update(runtime_manifest_for_checks=None, runtime_manifest_sha256=None)
    a = bundle_args(world, runtime, tmpdir_, b, **args)
    if case == "admissions":
        a.host = "127x03"
        monkeypatch.setitem(S3.END_ADMISSIONS, "127x03", ("system-bus-admission.json", "idle-services.json"))
    refused(code, run, a)
    ok(hosts.logins() == [] and read(canary) == CANARY)
    record_receipt(a.record)


@pytest.mark.parametrize("case,code", [("symlinked-ancestor", "root"), ("wrong-sha", "sha"), ("hardlink", "nlink")])
def test_probe_aux_runtime_manifest_is_role_gated(world, runtime, bundle, hosts, tmpdir_, case, code):
    """Sol S10-F1: the auxiliary S9 manifest (--runtime-manifest-for-checks) goes through the same role gate."""
    make_base(hosts)
    kw = {}
    if case == "symlinked-ancestor":
        os.symlink(os.path.dirname(runtime["out"]), os.path.join(tmpdir_, "alias"))
        kw["runtime_manifest_for_checks"] = os.path.join(tmpdir_, "alias", os.path.basename(runtime["out"]))
    elif case == "wrong-sha":
        kw["runtime_manifest_sha256"] = "0" * 64
    else:
        copy = os.path.join(tmpdir_, "rtcopy")
        os.makedirs(copy)
        shutil.copyfile(os.path.join(runtime["out"], S9.MANIFEST), os.path.join(tmpdir_, "m.json"))
        os.link(os.path.join(tmpdir_, "m.json"), os.path.join(copy, S9.MANIFEST))
        kw["runtime_manifest_for_checks"] = copy
    refused(code, run, bundle_args(world, runtime, tmpdir_, bundle, **kw))
    ok(hosts.logins() == [])


def test_preflight_guard_job_stages_to_q4(world, s1b_out, hosts, tmpdir_):
    out = os.path.join(tmpdir_, "pf")
    m = S3.build(s3_args(world, s1b_out, out, host="127x04", preflight="01"), log=lambda *x: None)
    make_base(hosts, "127x04")
    a = s10_args(host="127x04", guard_job=out, guard_job_name=m["job_name"], guard_manifest_sha256=m["_sha256"],
                 record=os.path.join(tmpdir_, "rec"))
    result = run(a)
    final = hosts.path("127x04", "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf01")
    ok(os.path.isdir(final) and os.lstat(final).st_mode & 0o777 == 0o755)
    ok(read(os.path.join(final, "FROZEN-T1.json")) == world.files[S3.FREEZE_REL])
    ok(not os.path.exists(hosts.path("127x04", "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf01.partial")))
    ok(result["components"][0]["kind"] == "guard-job")
    ok(os.listdir(hosts.path("127x04", "/mpac/sdicks02/jobs/perception-never-touch")) == [])


def test_guard_job_for_the_other_host_refused(world, guard03, hosts, tmpdir_):
    make_base(hosts, "127x04")
    a = s10_args(host="127x04", guard_job=guard03["out"], guard_job_name=guard03["job"],
                 guard_manifest_sha256=guard03["sha"], record=os.path.join(tmpdir_, "rec"))
    refused("check", run, a)
    ok(hosts.logins() == [])


@pytest.mark.parametrize("where", ["exists", "shm"])
def test_record_confinement(world, runtime, bundle, hosts, tmpdir_, where):
    record = os.path.join(tmpdir_, "rec") if where == "exists" else "/dev/shm/k4s-s10-never"
    if where == "exists":
        os.makedirs(record)
    with pytest.raises(si.Refusal):
        run(bundle_args(world, runtime, tmpdir_, bundle, record=record))
    ok(hosts.logins() == [] and not os.path.exists("/dev/shm/k4s-s10-never"))


def test_window_acknowledgement_required(world, runtime, bundle, hosts, tmpdir_):
    a = bundle_args(world, runtime, tmpdir_, bundle, outside_end_window="")
    refused("policy", run, a)
    ok(hosts.logins() == [])
    record_receipt(a.record)


@pytest.mark.parametrize("subdir", ["bundles", "attempts", "preflight"])
def test_base_subdirectory_missing_refused_at_p(world, runtime, bundle, hosts, tmpdir_, subdir):
    base = make_base(hosts)
    os.rmdir(os.path.join(base, subdir))
    refused("remote-refused", run, bundle_args(world, runtime, tmpdir_, bundle))
    ok(len(hosts.logins()) == 1)


def reader_reply(request, items):
    req = json.loads(request)
    return (json.dumps({"schema": si.REMOTE_RESPONSE_SCHEMA, "status": "ok", "host": req["host"],
                        "request_sha256": sha(request), "items": items}, sort_keys=True, separators=(",", ":"))
            + "\n").encode()


def test_parse_f_requires_every_step_status(world, runtime, bundle, tmpdir_):
    """F: the reader reply must be valid and every chmod/mv status line present and 0, even when rc is 0."""
    policy = S10.local_policy(bundle_args(world, runtime, tmpdir_, bundle))
    c = S10.bundle_component(policy, "b00", "127x03", bundle["dir"], bundle["tiers"], bundle["receipt"],
                             runtime["manifest"], None)
    checkp, roles = S10.check_policy("127x03", [c], False)
    request = si.build_remote_request(checkp, S10.f_items([c], roles))
    req = json.loads(request)
    items = [dict(kind=i["kind"], root=i["root"], rel=i["rel"], **({"dev": 1, "ino": 2, "mode": 0o40755}
                                                                     if i["kind"] == "dir" else {}))
             for i in req["items"]]
    good = reader_reply(request, items) + b"@@RC|check|0\n@@RC|chmod|0|0\n@@RC|mv|0|0\n@@DONE\n"
    ok(S10.parse_f("127x03", request, 0, good, [c]) == {c.partial: {"dev": 1, "ino": 2}})
    for bad in (b"@@RC|check|0\n@@RC|chmod|0|0\n@@DONE\n", b"@@RC|check|0\n@@RC|mv|0|0\n@@DONE\n",
                b"@@RC|check|0\n@@RC|chmod|0|0\n@@RC|mv|0|0\n"):
        refused("remote", S10.parse_f, "127x03", request, 0, reader_reply(request, items) + bad, [c])


def test_bundle_guard_bytes_must_equal_the_staged_guard_job(world, runtime, guard03, hosts, tmpdir_):
    """X21: a self-consistent bundle whose t1-guard freeze differs from the staged guard job's is refused."""
    make_base(hosts)
    b = make_bundle(world, tmpdir_, "bundle-03-rd00-a00", "127x03", runtime["manifest"], guard=guard03,
                    freeze_bytes=b'{"other": "freeze"}\n')
    a = bundle_args(world, runtime, tmpdir_, b, guard_job=guard03["out"], guard_job_name=guard03["job"],
                    guard_manifest_sha256=guard03["sha"])
    error = refused("check", run, a)
    ok("guard job's bytes" in error.reason, error.reason)
    ok(hosts.logins() == [])
