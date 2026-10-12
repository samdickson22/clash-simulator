"""End-to-end happy path on the synthetic world: prepare-clone -> S1b (fake hosts) -> S3 -> S9 build/verify/
equivalence -> S10 staging onto a namespaced fake 127x03 (create-base, runtime + bundle + guard job)."""
import json
import os
import stat

from conftest import (C, HOSTS, S1B, S3, S9, S10, Args, admissions, make_bundle, ok, read, s10_args, sha, si)


def test_prepare_clone_receipt(world):
    receipt = json.loads(read(world.repo_full + "-PREPARE.json"))
    ok(receipt["commit"] == world.P and receipt["head"] == world.P and receipt["origin"] == S9.ORIGIN_URL)
    ok(not os.path.exists(world.repo_full + "/.git/hooks"))
    ok(receipt["safe_input_sha256"] == C.SAFE_INPUT_SHA256)


def test_s1b_copies_in_e3_layout(world, s1b_out):
    manifest = json.loads(read(s1b_out["manifest"]))
    ok(manifest["status"] == "copied" and manifest["ssh_logins"] == 2 and len(s1b_out["logins"]) == 2)
    for f in manifest["files"]:
        data = read(os.path.join(s1b_out["dest"], f["local_path"]))
        ok(data == admissions(f["host"])[f["name"]] and sha(data) == f["remote_sha256"] == f["local_sha256"])
        ok(f["remote_nlink"] == 1 and f["e3_repository_path"] == "%s/%s-%s" % (si.E3_ADMISSIONS_DIR, f["host"],
                                                                               f["name"]))
        ok(stat.S_IMODE(os.lstat(os.path.join(s1b_out["dest"], f["local_path"])).st_mode) == 0o444)
    ok(sorted(os.listdir(os.path.join(s1b_out["dest"], "end-guard-admissions"))) ==
       ["127x03-idle-services.json", "127x03-system-bus-admission.json", "127x04-system-bus-admission.json"])


def test_s3_build_and_verify(world, guard03):
    m = guard03["manifest"]
    ok(m["job_name"] == "k4s-end-guard-r1-rd00-a00" and m["target_job"] == "/mpac/sdicks02/jobs/clasher/" + m["job_name"])
    ok(m["top_level"] == ["FROZEN-T1.json", "idle-services.json", "repo", "system-bus-admission.json"])
    ok(m["frozen_seed_check"]["admit_accepted"] == [] and m["frozen_seed_check"]["optimize"] == 0)
    ok(not os.path.exists(os.path.join(guard03["out"], m["job_name"], "repo", ".git", "FETCH_HEAD")))
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", guard03["out"], guard03["job"]))
    S3.verify(policy, "s3", guard03["out"], guard03["job"], guard03["sha"], log=lambda *a: None)


def test_s9_build_verify_equivalence(world, runtime):
    m = runtime["manifest"]
    ok(m["commit"] == world.P and m["r6_end_dir_absent"])
    files = m["inventory"]["files"]
    ok("docs/notes.md" not in files and "src/clasher/core.py" in files and si.E1_ALIAS in files)
    ok(files[si.E1_ALIAS]["sha256"] == files[si.E1_LINK_TEXT]["sha256"])
    ok(not os.path.islink(os.path.join(runtime["out"], "runtime", si.E1_ALIAS)))
    ok([r["path"] for r in m["tracked_pin_sha_differs_from_git"]] == ["data/stale.json"])
    ok(set(m["support_members"]) <= set(files))
    from conftest import E5_PATH, E5_BYTES
    ok(m["e5_members"] == [E5_PATH] and files[E5_PATH]["e5"] is True and files[E5_PATH]["sha256"] == sha(E5_BYTES))
    ok(E5_PATH in [g["path"] for g in m["git_members"]])
    policy = si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", runtime["out"]))
    S9.verify(policy, "s9", runtime["sha"], frozen=True, python=world.python, log=lambda *a: None)
    result = S9.equivalence(policy, "s9", runtime["sha"], world.X, log=lambda *a: None)
    ok(result["diff"] == [S9.END_JOB_REL] and result["runtime_files_identical"])


def test_s10_stage_runtime_bundle_guard(world, runtime, guard03, hosts, tmpdir_):
    b = make_bundle(world, tmpdir_, "bundle-03-rd00-a00", "127x03", runtime["manifest"], guard=guard03)
    record = os.path.join(tmpdir_, "rec")
    a = s10_args(runtime=runtime["out"], runtime_manifest_sha256=runtime["sha"],
                 bundle=[(b["dir"], b["tiers"], b["receipt"])], guard_job=guard03["out"],
                 guard_job_name=guard03["job"], guard_manifest_sha256=guard03["sha"], create_base=True, record=record)
    manifest = S10.run(a, log=lambda *a: None)
    labels = [l["label"] for l in manifest["logins"]]
    ok(labels == ["P-check", "P-facts", "base", "receive-runtime", "receive-bundle", "receive-guard-job", "F", "POST"],
       labels)
    ok(len(hosts.logins()) == len(labels))
    base = hosts.path("127x03", si.END_BASES["127x03"])
    ok(sorted(os.listdir(base)) == ["attempts", "bundles", "preflight", "runtime"])
    rt = os.path.join(base, "runtime", "runtime-" + world.P[:12])
    for rel, f in runtime["manifest"]["inventory"]["files"].items():
        st = os.lstat(os.path.join(rt, rel))
        ok(st.st_nlink == 1 and stat.S_ISREG(st.st_mode) and sha(read(os.path.join(rt, rel))) == f["sha256"], rel)
        ok(stat.S_IMODE(st.st_mode) == (0o555 if f["executable"] else 0o444), rel)
    ok(stat.S_IMODE(os.lstat(rt).st_mode) == 0o555)
    guard = hosts.path("127x03", guard03["manifest"]["target_job"])
    ok(os.path.isdir(guard) and stat.S_IMODE(os.lstat(guard).st_mode) == 0o755)
    ok(not [n for n in os.listdir(os.path.dirname(guard)) if n.endswith(".partial")])
    ok(os.listdir(hosts.path("127x04", "/mpac/sdicks02/jobs/perception-never-touch")) == [])
    ok(json.loads(read(os.path.join(record, "s10-staging-manifest.json")))["status"] == "staged")
    from conftest import E5_PATH, E5_BYTES
    ok(read(os.path.join(rt, E5_PATH)) == E5_BYTES and os.lstat(os.path.join(rt, E5_PATH)).st_mode & 0o777 == 0o444)
    for line in hosts.logins():                              # nothing on a host is ever deleted or extracted
        words = set(line.replace("~", " ").split())
        ok(not {"rm", "rmdir", "unlink", "tar", "/usr/bin/rm", "/bin/rm"} & words, line[:160])
