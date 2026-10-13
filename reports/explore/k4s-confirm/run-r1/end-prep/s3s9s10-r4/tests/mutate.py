#!/usr/bin/env python3
"""Mutation check of the r2 safe_input adoption points (S1b / S3 / S9 / S10 / common). Each mutant is ONE textual edit
whose target must occur exactly once (--check-edits validates them all). Every mutant runs the whole suite (-x) on a
private copy in a fresh /dev/shm/s3s9s10-mut-* directory (removed afterwards), with the interpreter's -O flag, cwd
/tmp; a mutant is KILLED when the suite fails. NULL controls (unmodified copies) are interleaved and must SURVIVE.
Before/after snapshots prove that nothing outside /tmp and /dev/shm was created (the r1 incident must not recur).

  nice -n 19 PY -B -O tests/mutate.py --jobs 10 --out /dev/shm/RESULT.json [--check-edits] [--only ID ...]
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CODE = ("end_prep_common.py", "safe_input.py", "s1b_copy_admissions.py", "s3_guard_job.py", "s9_end_runtime.py",
        "s10_stage_host.py", "s11_host_repository.py")
DATA = ()
TESTS = ("conftest.py", "fixture_guard_job.py", "k4s_adopt.py", "k4s_bootstrap_r1.py", "k4s_bootstrap_kit.py",
         "kit_harness.py", "test_common.py", "test_flow.py", "test_s1b.py", "test_s3.py", "test_s9.py", "test_s10.py",
         "test_f1.py", "test_f4.py", "test_fixture_guard_job.py", "test_r4_s9.py", "test_r4_s10.py", "test_r4_s11.py")
VENDOR = ("vendor_s5s6s7_r4",)                     # r4: byte copies of the Part B consumers (tools source, S5, S7)
WATCH = ("/mpac/sdicks02/repos", "/mpac/sdicks02/k4s-runner", "/mpac/sdicks02/k4s-runner/run-r1",
         "/mpac/sdicks02/k4s-runner/run-r1/end-prep", "/mpac/sdicks02")
NEVER = ("/dev/shm/k4s-s1b-never", "/dev/shm/k4s-s3-never", "/dev/shm/k4s-s3-never.partial", "/dev/shm/k4s-s9-never",
         "/dev/shm/k4s-s9-never.partial", "/dev/shm/k4s-s10-never")

M = []


def mutant(mid, path, old, new, what):
    M.append(dict(id=mid, file=path, old=old, new=new, what=what))


# ---------------------------------------------------------------- end_prep_common
C = "end_prep_common.py"
# r3 END-FULL-F1 adoption glue (outside the canonical block; the block itself is byte-equality-tested and mutation-
# tested by bootstrap-r1's own campaign). tests/k4s_adopt.py re-pins every mutant copy, so a mutant is judged by the
# suite, not refused by the pin chain.
mutant("G01", C, '        if getattr(existing, "__k4s_bootstrap__", None) != (K4S_BOOTSTRAP_RELEASE, path, sha256, size):\n'
                 '            raise SystemExit("k4s bootstrap refused: a different %s module',
       '        if False:\n            raise SystemExit("k4s bootstrap refused: a different %s module',
       "an already loaded sibling is reused only with the same bootstrap tag")
mutant("G02", C, 'SAFE_INPUT_PATH = k4s_bootstrap_default_path(__file__, "safe_input.py")',
       'SAFE_INPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "safe_input.py")',
       "safe_input path as given (never normalized/resolved)")
mutant("G05", C, '    return bootstrap_sibling(module_name, HERE + "/" + module_name + ".py", sha256, size)',
       '    sys.path.insert(0, HERE)\n    return __import__(module_name)', "siblings through the bootstrap, never sys.path")
mutant("G06", C, '    module = bootstrap_sibling("safe_input", SAFE_INPUT_PATH, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE)',
       '    module = k4s_bootstrap_exec(open(SAFE_INPUT_PATH, "rb").read(), SAFE_INPUT_PATH, SAFE_INPUT_SHA256, '
       '"safe_input")', "safe_input read through the canonical walk/gates (not a pathname open)")
mutant("C04", C, "        if got != want:\n            del sys.modules", "        if False:\n            del sys.modules",
       "fingerprint / remote program pins")
mutant("C05", C, '    require(any(path.startswith(root) for root in PERMITTED_OUTPUT_ROOTS), "path",',
       '    require(True or any(path.startswith(root) for root in PERMITTED_OUTPUT_ROOTS), "path",',
       "output permitted roots")
mutant("C06", C, "RENAME_NOREPLACE) != 0:", "0) != 0:", "renameat2 RENAME_NOREPLACE")
mutant("C07", C, '        require(stat.S_ISDIR(st.st_mode), "not-dir", "%s is not a real directory" % partial_leaf)',
       "        pass", "publish_dir source must be a real directory")
mutant("C08", C, '        require(st.st_nlink == 1, "nlink", "%s is hard-linked (st_nlink %d)" % (rel, st.st_nlink))',
       "        pass", "unlink_own nlink")
mutant("C09", C, "        env = dict(si.GIT_FIXED_ENV)", "        env = dict(os.environ)", "frozen child: P2-4 env, nothing inherited")
mutant("C10", C, "            if kind is None:\n                refuse(", "            if False:\n                refuse(",
       "frozen child HOME must stay empty")
mutant("C12", C, '        require(not stat.S_ISLNK(st.st_mode), "symlink", "%s is a symlink" % rel)', "        pass",
       "unlink_own symlink")

for mid, f in (("G03", "s9_end_runtime.py"), ("G07", "s1b_copy_admissions.py"), ("G08", "s3_guard_job.py"),
               ("G09", "s10_stage_host.py")):
    mutant(mid, f, '        if getattr(existing, "__k4s_bootstrap__", None) != (K4S_BOOTSTRAP_RELEASE, path, sha256, size):\n'
                   '            raise SystemExit("k4s bootstrap refused: a different end_prep_common',
           '        if False:\n            raise SystemExit("k4s bootstrap refused: a different end_prep_common',
           "entrypoint reuses end_prep_common only with its own tag")
mutant("G04", "s9_end_runtime.py", '    path = k4s_bootstrap_default_path(__file__, "end_prep_common.py")',
       '    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "end_prep_common.py")',
       "entrypoint path as given (never normalized)")
mutant("G10", "s3_guard_job.py", 'S1B = C.load_sibling("s1b_copy_admissions", *K4S_SIBLING_PINS["s1b_copy_admissions.py"])',
       'sys.path.insert(0, C.HERE)\nimport s1b_copy_admissions as S1B', "S3 loads S1b through the bootstrap")
mutant("G11", "s10_stage_host.py", 'S9 = C.load_sibling("s9_end_runtime", *K4S_SIBLING_PINS["s9_end_runtime.py"])',
       'sys.path.insert(0, C.HERE)\nimport s9_end_runtime as S9', "S10 loads S9 through the bootstrap")

# ---------------------------------------------------------------- S1b
B = "s1b_copy_admissions.py"
mutant("B01", B, 'grants=("reporting-job-exact",))], remote=True)', "grants=())], remote=True)",
       "remote read role (exact names, grant)")
mutant("B02", B, '    items = [{"role": "job", "rel": NEXT_NAMESPACE, "kind": "absent"}]\n', "    items = []\n",
       "r5 absence probe")
mutant("B03", B, '        require(identity == BUS_IDENTITY[host], "check",', '        require(True, "check",',
       "pinned dbus identity")
mutant("B04", B, "    require(identity == IDLE_IDENTITY and service.get(\"name\") == IDLE_SERVICE_NAME, \"check\",",
       "    require(True, \"check\",", "pinned idle identity")
mutant("B05", B, "                           expected_sha256=HISTORY_SHA256)", "                           expected_sha256=None)",
       "pinned history read")
mutant("B06", B, '        require(bool(a.outside_end_window), "policy",', '        require(True, "policy",',
       "window acknowledgement")
mutant("B07", B, '        si.write_refusal_receipt(writer, "S1B", error, {"logins": logins, "started_utc": started})',
       "        pass", "refusal receipt")
mutant("B08", B, "    doc = si.loads_strict(data, \"%s/%s\" % (host, name))",
       "    doc = json.loads(data)", "strict JSON (duplicate keys / NaN)")

# ---------------------------------------------------------------- S3
S3 = "s3_guard_job.py"
mutant("T01", S3, '                and row.get("remote_nlink") == 1 and C.is_sha256(row.get("remote_sha256"))',
       '                and C.is_sha256(row.get("remote_sha256"))', "S1b row single-link")
mutant("T02", S3, 'S1B.MAX_BYTES, expected_sha256=row["remote_sha256"])', "S1B.MAX_BYTES, expected_sha256=None)",
       "committed admission == S1b on-host SHA")
mutant("T03", S3, "FREEZE_REL, 16 << 20, expected_sha256=FROZEN_T1_SHA)", "FREEZE_REL, 16 << 20, expected_sha256=None)",
       "freeze pin")
mutant("T04", S3, "modules[m + \".py\"] = si.git_show_file(policy, \"repo\", repo, commit, rel, 16 << 20, expected_sha256=pin)",
       "modules[m + \".py\"] = si.git_show_file(policy, \"repo\", repo, commit, rel, 16 << 20, expected_sha256=None)",
       "T1 module pins before execution")
mutant("T06", S3, '    require(parent == GUARD_PARENTS[host] and os.path.normpath(path) == path, "policy",',
       '    require(os.path.normpath(path) == path, "policy",', "Q4 parent")
mutant("T07", S3, '    C.unlink_own(policy, "guard-repo-w", ".git/FETCH_HEAD")', "    pass", "FETCH_HEAD removed")
mutant("T08", S3, '    si.check_absent(policy, role_name, ".git/FETCH_HEAD")\n', "", "prove_repo FETCH_HEAD absent")
mutant("T09", S3, '    require(sorted(refs.splitlines()) == want, "check",', '    require(True, "check",', "refs exact")
mutant("T10", S3, '    require(sorted(keys) == sorted(GUARD_GIT_CONFIG_KEYS), "check",', '    require(True, "check",',
       "guard config keys")
mutant("T11", S3, '    require(shallow == b"true\\n", "check",', '    require(True, "check",', "Q3 shallow clone")
mutant("T12", S3, "        result = si.run_checked(argv, 600, 1 << 20, env=env, cwd=tmp)",
       "        result = si.run_checked(argv, 600, 1 << 20, env=None, env_allow=tuple(os.environ), cwd=tmp)",
       "frozen child environment (P2-4)")
mutant("T13", S3, '    require(out.get("admit_accepted") == [], "check",', '    require(True, "check",', "admit() result")
mutant("T14", S3, "        C.chmod_readonly(policy, \"guard-repo\", b[\"path\"])", "        pass", "seed files 0444")
mutant("T15", S3, "    rows, dirs = inventory(policy, prefix + \"-job\", job, host)\n    require(rows == manifest[\"inventory\"]",
       "    rows, dirs = manifest[\"inventory\"], manifest[\"dirs\"]\n    require(rows == manifest[\"inventory\"]",
       "verify re-walks/re-hashes (S3-F2)")
mutant("T16", S3, '            si.write_refusal_receipt(writer, "S3", error, {"job": name, "host": a.host})',
       "            pass", "refusal receipt in .partial")
mutant("T17", S3, '    require(s1b_name == S1B_MANIFEST, "policy", "--s1b-manifest must name %s" % S1B_MANIFEST)\n',
       "", "S1b manifest exact name (masked by the exact-name role; expected equivalent)")

# ---------------------------------------------------------------- S9
S9 = "s9_end_runtime.py"
mutant("N01", S9, "    if build:                                                          # R6",
       "    if False:                                                          # R6", "R6 end/ absent at P")
mutant("N02", S9, "        return entry[\"path\"] in names or entry[\"path\"].endswith(\".py\")",
       "        return True", "D1 member predicate (non-members never read)")
mutant("N03", S9, "            row.update(found=got[\"sha256\"] == pins[name], size=got[\"size\"], sha256=got[\"sha256\"])",
       "            row.update(found=True, size=got[\"size\"], sha256=got[\"sha256\"])", "locate SHA match")
mutant("N04", S9, '        require(inventory.get(name, {}).get("sha256") == expected, "check", "K4S-pinned file differs: " + name)',
       "        pass", "stdlib K4S pin verification before frozen import")
mutant("N05", S9, '    require(C.canonical_sha(measurement) == MEASUREMENT_SHA, "check", "e4v3 measurement inventory is not 42b8986d")\n    for name in IMPORT_CLOSURE:',
       "    for name in IMPORT_CLOSURE:", "measurement inventory 42b8986d")
mutant("N06", S9, '    require(frozen.get("runtime_files") == local, "check", "frozen runtime_pins differs from the S9 computation")',
       "    pass", "frozen cross-check equality")
mutant("N07", S9, '    require(p != x and is_ancestor(g, p, x), "check",', '    require(p != x, "check",', "X strict descendant of P")
mutant("N08", S9, '    require(names == [END_JOB_REL], "check",', '    require(END_JOB_REL in names, "check",',
       "diff exactly END-JOB")
mutant("N09", S9, '    require([(e["path"], e["type"], e["mode"]) for e in entry] == [(END_JOB_REL, "blob", "100644")], "check",',
       '    require(True, "check",', "END-JOB regular blob")
mutant("N10", S9, '    require(members_p == manifest["git_members"] and', '    require(True or members_p == manifest["git_members"] and',
       "built members == plan at P")
mutant("N11", S9, 'CLONE_ABSENT = (".git/hooks", ".git/shallow",', 'CLONE_ABSENT = (".git/shallow",',
       "no hooks in the clone (r3: via CLONE_ABSENT)")
mutant("N12", S9, '    require(sorted(keys) == sorted(CLONE_CONFIG_KEYS), "indirection",', '    require(True, "indirection",',
       "plain clone config (no promisor/partial)")
mutant("N13", S9, '    require(not [n for n in names if n.endswith(".promisor")], "indirection", "promisor pack in the full clone")',
       "    pass", "no promisor packs")
mutant("N14", S9, '    require(replace == b"", "indirection", "the full clone has replace refs")', "    pass", "no replace refs")
mutant("N15", S9, "        got = si.hash_e4(policy, role_name, rel)", "        got = si.sha256_input(policy, role_name, rel)",
       "E4 hash-only")
mutant("N16", S9, '    require(inv == manifest["inventory"] and C.canonical_sha(inv) == manifest["inventory_sha256"], "check",\n            "runtime tree differs',
       '    require(True, "check",\n            "runtime tree differs', "verify inventory equality")
mutant("N17", S9, "    return si.Role(\"q5\", Q5_SOURCE, \"read\", MAX_EXTERNAL_BYTES, exact=tuple(sorted(EXTERNAL)))",
       "    return si.Role(\"q5\", \"/tmp\", \"read\", MAX_EXTERNAL_BYTES, patterns=(\"**\",))", "explicit Q5 source role")
mutant("N18", S9, "        si.write_refusal_receipt(writer, \"S9\", error, {\"commit\": commit})",
       "        pass", "refusal receipt in .partial")
mutant("N19", S9, "        result = si.run_checked(argv, 1800, 64 << 20, env=env, cwd=\"/\")",
       "        result = si.run_checked(argv, 1800, 64 << 20, env=env, cwd=\"/\", ok_rcs=(0, 37))", "frozen child rc")
mutant("N20", S9, '    require(not missing, "check", "Incomplete frozen runtime: %r" % missing[:8])', "    pass",
       "complete runtime (masked by the frozen cross-check; expected equivalent)")

mutant("N21", S9, "    for rel in walk[\"e5\"]:\n        got = si.hash_e5(policy, role_name, rel)",
       "    for rel in []:\n        got = si.hash_e5(policy, role_name, rel)", "E5 members hashed (hash_e5) in the inventory")
mutant("N22", S9, 'patterns=("**",), exemptions=("E1", "E4", "E5"))', 'patterns=("**",), exemptions=("E1", "E4"))',
       "repo role carries E5 (r3)")
mutant("N23", S9, "        inventory[rel] = dict(size=got[\"size\"], sha256=got[\"sha256\"], executable=False, e5=True)",
       "        inventory[rel] = dict(size=got[\"size\"], sha256=got[\"sha256\"], executable=False)",
       "E5 flag recorded for S10 (receive e5 item)")

# ---------------------------------------------------------------- r3 END-FULL-F4: the live full-clone precondition
mutant("F01", S9, "    full_clone = require_full_clone((commit,))                         # F4",
       "    full_clone = {}                         # F4", "S9 build runs the live full-clone check")
mutant("F02", S9, "    require_full_clone()                                               # F4: live, before anything else\n"
                  "    manifest = load_manifest(policy, prefix, manifest_sha256)\n    is_commit",
       "    manifest = load_manifest(policy, prefix, manifest_sha256)\n    is_commit",
       "S9 verify runs the live full-clone check")
mutant("F03", S9, "    full_clone = require_full_clone()                                  # F4",
       "    full_clone = {}                                  # F4", "S9 equivalence runs the live full-clone check")
mutant("F04", S9, "            require_full_clone((full_commit(a.commit, \"--commit\"),))   # F4",
       "            (full_commit(a.commit, \"--commit\"),)   # F4", "S9 locate runs the live full-clone check")
mutant("F05", S3, '    full_clone = S9.require_full_clone((a.commit,) + tuple(b["commit"] for b in BINDINGS), REPO_FULL)',
       "    full_clone = {}", "S3 build runs the live full-clone check")
mutant("F06", S3, "    S9.require_full_clone((), REPO_FULL)\n", "", "S3 verify runs the live full-clone check")
mutant("F07", B, "    if repository == S9.REPO_FULL:", "    if False:", "S1b on REPO_FULL runs the live full-clone check")
mutant("F08", S9, '            if error.code != "missing":', "            if False:", "CLONE_ABSENT names refused")
mutant("F09", S9, "        head = CONFIG_SECTION.fullmatch(line)", "        head = CONFIG_SECTION.match(line)",
       "no variable after a section header (same-line promisor)")
mutant("F10", S9, ' and values.get("core.bare") == "false",', ",", "plain clone is not bare")
mutant("F11", S9, '    require(all(CLONE_PACK_NAME.fullmatch(n) for n in names), "indirection",',
       '    require(True, "indirection",', "pack directory: plain pack files only")
mutant("F12", S9, "    for commit in commits:\n        is_commit(g, commit)", "    for commit in ():\n        is_commit(g, commit)",
       "every given commit is in the verified clone")
mutant("F13", S9, "    is_commit(repo(), manifest[\"commit\"])                              # the built commit",
       "    pass                              # the built commit", "verify binds the manifest commit to the clone")
mutant("F14", S9, '    for rel in (".git", ".git/objects", ".git/objects/pack"):\n        si.check_dir(policy, "clone", rel)',
       '    for rel in ():\n        si.check_dir(policy, "clone", rel)', ".git is a real directory (no gitfile)")
mutant("F15", S9, "        text = raw.decode(\"utf-8\")", "        text = raw.decode(\"latin-1\")", "config must be UTF-8")
mutant("F16", S9, '    require(facts == ("%s/.git\\nfalse\\nfalse\\n%s\\n" % (path, path)).encode(), "indirection",',
       '    require(True, "indirection",', "git reports the expected non-bare, non-shallow repository")

# ---------------------------------------------------------------- S10
X = "s10_stage_host.py"
mutant("X01", X, "    require(SYNTHETIC_KEY not in manifest, \"check\",", "    require(True, \"check\",", "S4 test stamp key")
mutant("X02", X, "    require(SYNTHETIC_STAMP not in json.dumps(manifest) and SYNTHETIC_STAMP not in json.dumps(receipt), \"check\",",
       "    require(True, \"check\",", "S4 SYNTHETIC-TEST-ONLY stamp")
mutant("X03", X, '            and receipt.get("production_pins") is True and receipt.get("status") == "CANDIDATE"',
       '            and receipt.get("status") == "CANDIDATE"', "receipt production_pins")
mutant("X04", X, '    require(SYNTHETIC_MARKER not in name.casefold(), "check",', '    require(True, "check",', "SYNTHETIC name")
mutant("X05", X, "    for rel, expected in PRODUCTION_PINS.items():\n        require(pinned.get(rel) == expected, \"check\",",
       "    for rel, expected in PRODUCTION_PINS.items():\n        require(True, \"check\",", "production identities")
mutant("X06", X, '    require(isinstance(guard.get("admissions"), dict) and set(guard["admissions"]) == want, "check",',
       '    require(isinstance(guard.get("admissions"), dict), "check",', "per-host admissions")
mutant("X07", X, "            and C.canonical_sha(manifest.get(\"measurement_files\")) == runtime_manifest[\"measurement_files_sha256\"],",
       "            and True,", "runtime/measurement consistency")
mutant("X08", X, '    bad = {k: v for k, v in rcs.items() if v != "0" and k not in info}', "    bad = {}",
       "facts statuses (S10-F3; r4: the informational interpreter candidates excepted)")
mutant("X09", X, '    require(outs.get("hostname") == [host], "host",', '    require(True, "host",', "facts hostname")
mutant("X10", X, '    require(free >= need_bytes + HEADROOM, "space",', '    require(True, "space",', "free space")
mutant("X11", X, "            items += [{\"role\": roles[c.parent], \"kind\": \"absent\", \"rel\": c.leaf},\n"
                 "                      {\"role\": roles[c.parent], \"kind\": \"absent\", \"rel\": c.leaf + \".partial\"}]",
       "            pass", "P: targets and .partial absent")
mutant("X12", X, '        items = [{"role": "base", "kind": "dir"}] + [{"role": "base", "kind": "dir", "rel": d} for d in BASE_SUBDIRS]',
       '        items = [{"role": "base-parent", "kind": "dir"}]', "P: base and subdirs canonical")
mutant("X13", X, '            require((d["dev"], d["ino"]) == (identities[c.partial]["dev"], identities[c.partial]["ino"]), "changed",',
       '            require(True, "changed",', "POST dev/ino = the moved directory")
mutant("X14", X, '            require((writable == 0) if c.kind != "guard-job" else (d["mode"] & 0o200 != 0), "check",',
       '            require(True, "check",', "POST a-w modes")
mutant("X15", X, '    require(rcs[1:] == want, "remote", "F step statuses differ: %r" % rcs[1:])', "    pass",
       "F step statuses")
mutant("X16", X, "    record = None if a.dry_run else C.Record(a.record, \"S10\", RECORD_NAMES).open()   # first: receipts need a home",
       "    record = None", "record first (receipts)")
mutant("X17", X, '    raw = si.read_bytes(policy, role, BUNDLE_MANIFEST, expected_sha256=C.need_sha256(tiers_sha, "tiers-pins SHA"),',
       '    raw = si.read_bytes(policy, role, BUNDLE_MANIFEST, expected_sha256=None,', "tiers-pins expected SHA")
mutant("X18", X, '    receipt = si.read_json(policy, role, BUNDLE_RECEIPT, 1 << 20,\n                           expected_sha256=C.need_sha256(receipt_sha, "assembly receipt SHA"))',
       '    receipt = si.read_json(policy, role, BUNDLE_RECEIPT, 1 << 20)', "assembly receipt expected SHA")
mutant("X19", X, '        require(got["sha256"] == expected, "check", "bundle %s: %s differs from its pin" % (name, rel))',
       "        pass", "bundle file pins")
mutant("X20", X, "        runtime_manifest = S9.load_manifest(policy, \"s9\", a.runtime_manifest_sha256)",
       "        runtime_manifest = si.loads_strict(open(policy.role(\"s9-out\").root + \"/runtime-manifest.json\", \"rb\").read())",
       "aux runtime manifest through the role gate (S10-F1)")
mutant("X21", X, '            require(pinned.get(rel) == expected, "check", "bundle %s: %s differs from the guard job\'s bytes"',
       '            require(True, "check", "bundle %s: %s differs from the guard job\'s bytes"', "bundle/guard byte equality")
mutant("X22", X, '    require(manifest["host"] == host, "check", "guard job was built for " + manifest["host"])', "    pass",
       "guard job host")

mutant("X23", X, 'mode=0o555 if f.get("executable") else 0o444, e4=bool(f.get("e4")), e5=bool(f.get("e5"))))',
       'mode=0o555 if f.get("executable") else 0o444, e4=bool(f.get("e4")), e5=False))', "receive items carry e5 (r3)")
mutant("X24", X, '        exemptions = tuple(x for x, key in (("E4", "e4"), ("E5", "e5")) if any(f.get(key) for f in self.files))',
       '        exemptions = ()', "receive destination role exemptions")

# Mutants whose only effect is masked by a stronger, independent layer that the suite exercises (kept to document
# the redundancy; a SURVIVED verdict for these is expected and is not counted as a test gap).
# ---------------------------------------------------------------- r4 (integration audit fix round)
S9F, S10F, S11F = "s9_end_runtime.py", "s10_stage_host.py", "s11_host_repository.py"
# S9: support members (B3/B5)
mutant("R01", S9F, ' + tuple(sorted(SUPPORT_PINS)))', ')', "the three r4 files are support members")
mutant("R02", S9F, '        require(inventory.get(rel, {}).get("sha256") == pin, "check",',
       '        require(True or inventory.get(rel, {}).get("sha256") == pin, "check",', "support member pin")
mutant("R03", S9F, '        require(sd1.get("path") == SD1_REL and sd1.get("sha256") == SUPPORT_PINS[SD1_REL], "check",',
       '        require(True, "check",', "SD1 pin == the K4S manifest's")
mutant("R04", S9F, '        require(corpora.get("path") == CORPORA_REL and corpora.get("sha256") == SUPPORT_PINS[CORPORA_REL]',
       '        require(True or corpora.get("path") == CORPORA_REL', "corpus inventory pin == the K4S manifest's")
mutant("R05", S9F, '    check_support_pins(inventory)                                      # r4: a pre-r4 runtime',
       '    pass                                      # r4: a pre-r4 runtime', "verify refuses a pre-r4 runtime")
mutant("R06", S9F, '    support = check_support_pins(inventory, k4s)', '    support = sorted(SUPPORT_PINS)',
       "stdlib closure check hashes the support members")
# S9: refresh-clone (U10)
mutant("R07", S9F, '    before = require_full_clone(())                                    # F4: live, before the fetch',
       '    before = {}', "live clone check before the fetch")
mutant("R08", S9F, '    after = require_full_clone((commit,) + ((base,) if base else ()))  # F4: the full live verification again',
       '    after = before', "live clone check (with X) after the fetch")
mutant("R09", S9F, '    require(refs_after.get(END_BRANCH_REF) == commit, "check",',
       '    require(True, "check",', "the tip is exactly X")
mutant("R10", S9F, '    require(changed in ([], [END_BRANCH_REF]), "check",', '    require(True, "check",',
       "no other ref moved")
mutant("R11", S9F, '    require(is_ancestor(g, old, commit), "check",', '    require(True, "check",',
       "fast-forward of the old tip")
mutant("R12", S9F, '        require(base != commit and is_ancestor(g, base, commit), "check",',
       '        require(True, "check",', "strict descendant of --base-commit")
mutant("R13", S9F, '    require(not lost, "check",', '    require(True, "check",', "objects never rewritten")
mutant("R14", S9F, '    require(head == head_before, "check", "HEAD moved during the fetch")', '    pass',
       "HEAD untouched")
mutant("R15", S9F, '            "refs/heads/%s:%s" % (END_BRANCH, END_BRANCH_REF)]',
       '            "+refs/heads/%s:%s" % (END_BRANCH, END_BRANCH_REF)]', "no forced refspec")
mutant("R16", S9F, '"-c", "transfer.fsckObjects=true", "-c", "gc.auto=0", "-c", "fetch.writeCommitGraph=false",',
       '"-c", "gc.auto=0", "-c", "fetch.writeCommitGraph=false",', "fsck on fetch")
# S10 (B2, U2, U3, U4, L4, B7)
mutant("V01", S10F, 'BASE_SUBDIRS = ("attempts", "preflight", "bundles")',
       'BASE_SUBDIRS = ("attempts", "preflight", "runtime", "bundles")', "B2: no runtime/ subdir")
mutant("V02", S10F, '    return Component("runtime", host, END_BASES[host], leaf,',
       '    return Component("runtime", host, END_BASES[host] + "/runtime", leaf,', "B2: runtime at <base>/runtime-<P12>")
mutant("V03", S10F, '        require(got["sha256"] == digest, "sha", "tool %s', '        require(True, "sha", "tool %s',
       "U2: tool pin")
mutant("V04", S10F, '        got = si.sha256_input(policy, "tools-src", src, expected_size=size)',
       '        got = si.sha256_input(policy, "tools-src", src)', "U2: tool size before any byte")
mutant("V05", S10F, '        require(got["sha256"] == digest, "sha", "end input', '        require(True, "sha", "end input',
       "U3: end-input pin")
mutant("V06", S10F, '    require(C.is_sha256(ADOPTED_S4_SHA256), "policy",', '    require(True, "policy",',
       "L4: a pending adopted-S4 pin refuses")
mutant("V07", S10F, '    require(receipt.get("assembler_sha256") == ADOPTED_S4_SHA256, "check",',
       '    require(True, "check",', "L4: the adopted S4 only")
mutant("V08", S10F, '        require(rec.get("executable") == python and rec.get("version") == HOST_PYTHON_VERSION, "interpreter",',
       '        require(True, "interpreter",', "U4: declared interpreter path and version")
mutant("V09", S10F, '        require(not failed, "interpreter",', '        require(True, "interpreter",', "U4: imports")
mutant("V10", S10F, '    bad = {k: v for k, v in rcs.items() if v != "0" and k not in info}',
       '    bad = {k: v for k, v in rcs.items() if v != "0" and k not in info + ["python"]}', "U4: probe status")
mutant("V11", S10F, '    require(len(found) == 1, "interpreter",', '    require(len(found) >= 1, "interpreter",',
       "U4: exactly one probe record")
mutant("V12", S10F, '-B -c %s %s" % (', '-B -I -c %s %s" % (', "U4: probe runs python as END does (no -I)")
mutant("V13", S10F, '        require(isinstance(d, dict) and set(d) == set(ROOTS_KEYS), "check", "RC-6 %s: keys" % host)',
       '        require(isinstance(d, dict), "check", "RC-6 %s: keys" % host)', "B7: exact host keys")
mutant("V14", S10F, '                and os.path.basename(d["runtime"]) == RUNTIME_PREFIX + doc["commit"][:12], "check",',
       '                and True, "check",', "B7: runtime-<commit12>")
mutant("V15", S10F, '                    and C.is_sha256(b["tiers_pins_sha256"]) and os.path.dirname(b["guard_job"]) == d["guard_parent"]',
       '                    and os.path.dirname(b["guard_job"]) == d["guard_parent"]', "B7: tiers-pins SHA, never a placeholder")
mutant("V16", S10F, '        require(len(set(jobs)) == len(jobs), "check",', '        require(True, "check",',
       "B7: one guard job per bundle")
mutant("V17", S10F, '    require(len({d["runtime"].rsplit("/", 1)[1] for d in hosts.values()}) == 1, "check",',
       '    require(True, "check",', "B7: same runtime on both hosts")
mutant("V18", S10F, '    require(runtime["commit"] == commit, "check",', '    require(True, "check",',
       "B7: --commit is the runtime's commit")
mutant("V19", S10F, '        require(name not in hosts[host]["bundles"], "policy",', '        require(True, "policy",',
       "B7: a bundle declared once")
mutant("V20", S10F, '    validate_roots(doc)\n    data = C.json_bytes(doc)', '    data = C.json_bytes(doc)',
       "B7: self-check before writing")
# S11 (U1): local side
mutant("U01", S11F, '        require(tip(g) == commit, "check",', '        require(True, "check",', "the END tip is --commit")
mutant("U02", S11F, '        require(S9.is_ancestor(g, REQUIRED_ANCESTOR, commit), "check",', '        require(True, "check",',
       "descends from 022ec7bf")
mutant("U03", S11F, '            require(prior != commit and S9.is_ancestor(g, prior, commit), "check",',
       '            require(True, "check",', "advance: strict descendant of P'")
mutant("U04", S11F, '                    and equivalence.get("runtime_commit") == prior and equivalence.get("end_job_commit") == commit',
       '                    and True', "advance: the equivalence record is for P' -> X")
mutant("U05", S11F, '    require(heads == ("%s %s\\n" % (commit, BRANCH_REF)).encode(), "check",', '    require(True, "check",',
       "bundle heads")
mutant("U06", S11F, '    require(prereqs == ([] if prior is None else [prior]), "check",', '    require(True, "check",',
       "bundle prerequisites")
mutant("U07", S11F, '        clone = S9.require_full_clone((commit,) + ((prior,) if prior else ()))',
       '        clone = {}', "live clone check before the bundle")
mutant("U08", S11F, '    if rc != 0 or rcs != want or lines[-2:] != ["@@DONE", ""]:',
       '    if rc not in (0, 12) or lines[-2:] != ["@@DONE", ""] and rc == 0:', "every session stage must succeed")
# S11 (U1): host program
mutant("U09", S11F, '    _require(head == commit, "check", "%s HEAD is %s', '    _require(True, "check", "%s HEAD is %s', "host: HEAD")
mutant("U10", S11F, '    _require(symbolic == "refs/heads/" + p["branch"], "check",', '    _require(True, "check",',
       "host: HEAD on k4s-end-r1")
mutant("U11", S11F, '    _require(refs == ["%s refs/heads/%s" % (commit, p["branch"])], "check",', '    _require(True, "check",',
       "host: the only ref")
mutant("U12", S11F, '    _require(_text(si, path, ["status", "--porcelain", "--untracked-files=all"]) == "", "check",',
       '    _require(True, "check",', "host: clean, no claim")
mutant("U13", S11F, '    _require(sorted(keys) == sorted(p["core_keys"]), "check",', '    _require(True, "check",',
       "host: plain init config")
mutant("U14", S11F, '    _require(root["mode"] & 0o200 and study["mode"] & 0o200, "check",', '    _require(True, "check",',
       "host: writable work tree")
mutant("U15", S11F, 'fn(fd, partial.encode(), fd, final.encode(), 1) != 0', 'fn(fd, partial.encode(), fd, final.encode(), 0) != 0',
       "host: RENAME_NOREPLACE")
mutant("U16", S11F, '    _require(oid == p["end_job_oid"], "check",', '    _require(True, "check",', "host: END-JOB OID")
mutant("U17", S11F, '        _require(got == p["end_job_sha256"], "check",', '        _require(True, "check",',
       "host: END-JOB bytes")
mutant("U18", S11F, '    _require(si.constants_fingerprint() == p["safe_input_fingerprint"], "pins",', '    _require(True, "pins",',
       "host: safe_input fingerprint")
mutant("U19", S11F, '            si.check_absent(pol, "base", p["repository_leaf"])', '            pass',
       "host check: repository absent before any transfer")
mutant("U20", S11F, '        facts["before"] = _verify(si, tool, p, final, p["prior"])', '        facts["before"] = {}',
       "host check (advance): the repository is at P' and clean before any transfer")
mutant("U21", S11F, '    _require(_git(si, path, ["merge-base", "--is-ancestor", p["required_ancestor"], "HEAD"], ok_rcs=(0, 1)).rc == 0,',
       '    _require(True,', "host: REQUIRED_ANCESTOR")
mutant("U22", S11F, '        result["end_job_committed"] = _end_job(si, p, final, p["commit"])',
       '        result["end_job_committed"] = {}', "host: END-JOB checked before the work tree moves")
mutant("U23", S11F, '    _require(got["sha256"] == p["bundle_sha256"], "sha",', '    _require(True, "sha",',
       "host: the received bundle re-hashed")


# r4 IR-03 (03 has no idle resident; guard-job admissions from END_ADMISSIONS, not S1B.NAMES)
S3F = "s3_guard_job.py"
mutant("Z01", S3F, '    require(sorted(manifest.get("admissions") or {}) == sorted(END_ADMISSIONS[host]), "check",',
       '    require(True, "check",', "IR-03: verify requires exactly the END admissions")
mutant("Z02", S3F, 'END_ADMISSIONS = {"127x03": (S1B.BUS_NAME,), "127x04": (S1B.BUS_NAME,)}',
       'END_ADMISSIONS = {"127x03": (S1B.BUS_NAME, S1B.IDLE_NAME), "127x04": (S1B.BUS_NAME,)}', "IR-03: 03 is bus only")
mutant("Z03", S3F, '    for name in END_ADMISSIONS[host]:                     # IR-03',
       '    for name in S1B.NAMES[host]:                     # IR-03', "IR-03: S1b's extra 03 idle row is not used")
mutant("Z04", S10F, '    want = set(S3.END_ADMISSIONS[host])', '    want = set(S3.S1B.NAMES[host])',
       "IR-03: bundle guard admissions = the END admissions")


EQUIVALENT = {
    "N20": "complete-runtime check: an incomplete runtime is also refused by the frozen runtime_pins cross-check, "
           "which runs on every build",
    "X17": "tiers-pins expected SHA: a different tiers-pins.json is also refused by the side-file read, whose "
           "expected SHA is derived from the operator's tiers SHA, and by the receipt's manifest_sha256 binding",
    "T17": "S1b manifest exact name: also enforced by the exact-name s1b role (allowlist) before any read",
    "N13": "r3: the explicit .promisor refusal is also enforced by the CLONE_PACK_NAME allowlist (F11), which "
           "refuses every non-pack name in the pack directory, .promisor included",
    "V17": "r4: same runtime on both hosts is implied by the per-host rule runtime == runtime-<commit12> (V14, killed)",
    "U09": "r4: host HEAD == commit is implied by the next two host checks: HEAD is the symbolic ref refs/heads/k4s-end-r1 "
           "(U10, killed) and the only ref is refs/heads/k4s-end-r1 at the commit (U11, killed)",
    "U23": "r4: the host re-hash of the received bundle is masked by the D4 receive program's own SHA-256 check of the "
           "same bytes in the same session (and the local stream re-hash); defense in depth",
}


def snapshot():
    out = {}
    for path in WATCH:
        try:
            out[path] = sorted(os.listdir(path))
        except OSError as error:
            out[path] = "ERR " + str(error)
    return out


def tmp_leftovers():
    return sorted(n for n in os.listdir("/tmp") if n.startswith(("k4s-r2t-", "k4s-s3-frozen-", "k4s-frozen-home-",
                                                                 "si-git-home-")))


def check_edits():
    bad = []
    for m in M:
        with open(os.path.join(ROOT, m["file"])) as stream:
            count = stream.read().count(m["old"])
        if count != 1:
            bad.append((m["id"], count))
    return bad


def run_one(m, python):
    work = tempfile.mkdtemp(prefix="s3s9s10-mut-%s-" % (m["id"] if m else "NULL"), dir="/dev/shm")
    try:
        os.makedirs(os.path.join(work, "tests"))
        for name in CODE + DATA:
            shutil.copyfile(os.path.join(ROOT, name), os.path.join(work, name))
        for name in TESTS:
            shutil.copyfile(os.path.join(HERE, name), os.path.join(work, "tests", name))
        for name in VENDOR:
            shutil.copytree(os.path.join(HERE, name), os.path.join(work, "tests", name))
        if m is not None:
            path = os.path.join(work, m["file"])
            with open(path) as stream:
                text = stream.read()
            if text.count(m["old"]) != 1:
                return dict(m, verdict="INVALID")
            with open(path, "w") as stream:
                stream.write(text.replace(m["old"], m["new"]))
            # r3: re-pin the sibling chain so the mutant loads (otherwise every mutant would die at the pin)
            subprocess.run([python, "-I", "-B", os.path.join(work, "tests", "k4s_adopt.py"), "--root", work],
                           stdout=subprocess.DEVNULL, check=True)
        start = time.time()
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp"}
        if os.environ.get("PYTEST_PATH"):
            env["PYTHONPATH"] = os.environ["PYTEST_PATH"]
        try:
            proc = subprocess.run(["nice", "-n", "19", python, "-B", "-O", "-m", "pytest", "-x", "-q", "-p",
                                   "no:cacheprovider", os.path.join(work, "tests")], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, cwd="/tmp", env=env, timeout=900)
            rc, tail = proc.returncode, proc.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
        except subprocess.TimeoutExpired:
            rc, tail = "timeout", ["timeout"]
        failed = [line for line in tail if "FAILED" in line or "ERROR" in line or "failed" in line]
        verdict = "SURVIVED" if rc == 0 else "KILLED"
        out = dict(m or dict(id="NULL"), rc=rc, verdict=verdict, seconds=round(time.time() - start, 1),
                   killed_by=failed[:2])
        out.pop("old", None)
        out.pop("new", None)
        return out
    finally:
        for directory, dirs, _ in os.walk(work):
            os.chmod(directory, 0o755)
        shutil.rmtree(work, ignore_errors=True)
        for path in NEVER:
            if os.path.lexists(path):
                shutil.rmtree(path, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--check-edits", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--nulls", type=int, default=4)
    a = ap.parse_args()
    bad = check_edits()
    if a.check_edits:
        print(json.dumps(dict(mutants=len(M), invalid=bad)))
        return 1 if bad else 0
    if bad:
        print("INVALID edit targets: %r" % bad)
        return 2
    chosen = [m for m in M if not a.only or m["id"] in a.only]
    plan = []
    step = max(1, len(chosen) // max(1, a.nulls))
    for i, m in enumerate(chosen):
        if i % step == 0 and sum(p is None for p in plan) < a.nulls:
            plan.append(None)
        plan.append(m)
    before, tmp_before = snapshot(), set(tmp_leftovers())
    results = []
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        for result in pool.map(lambda m: run_one(m, sys.executable), plan):
            results.append(result)
            print("%-5s %-9s %6ss %s" % (result["id"], result["verdict"], result.get("seconds"), result.get("what", "")),
                  flush=True)
    after, tmp_after = snapshot(), set(tmp_leftovers())
    sources = {}
    for name in CODE:
        with open(os.path.join(ROOT, name), "rb") as stream:
            sources[name] = hashlib.sha256(stream.read()).hexdigest()
    mutants = [r for r in results if r["id"] != "NULL"]
    nulls = [r for r in results if r["id"] == "NULL"]
    summary = dict(python=sys.executable, version=sys.version.split()[0], optimize=sys.flags.optimize,
                   sources_sha256=sources, mutants=len(mutants),
                   killed=sum(r["verdict"] == "KILLED" for r in mutants),
                   survived=[r["id"] for r in mutants if r["verdict"] != "KILLED"],
                   equivalent_survivors={k: v for k, v in EQUIVALENT.items()
                                         if any(r["id"] == k and r["verdict"] != "KILLED" for r in mutants)},
                   unexplained_survivors=[r["id"] for r in mutants if r["verdict"] != "KILLED"
                                          and r["id"] not in EQUIVALENT],
                   nulls=len(nulls), nulls_survived=sum(r["verdict"] == "SURVIVED" for r in nulls),
                   outside_writes=before != after, new_tmp_leftovers=sorted(tmp_after - tmp_before), results=results)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))
    if a.out:
        with open(a.out, "x") as stream:
            json.dump(summary, stream, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
