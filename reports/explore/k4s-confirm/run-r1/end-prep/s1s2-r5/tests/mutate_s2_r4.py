"""Mutation check of the S2 r4 safe_input adoption (not a pytest module). Each mutant replaces ONE exact snippet (or one
listed set of snippets: a JOINT mutant) of s2_end_evidence.py (each asserted to occur exactly once), in a scratch copy
of the package under SCRATCH/<name>/ (SCRATCH must be below /dev/shm), then runs the S2 suites there under python -O
with -x and its own --basetemp (a tempfile directory below /tmp: S2's test root must lie below /tmp/; removed after).
Killed = pytest exit 1 with a failed test; any other exit is INVALID. NULL controls (the unmodified source) must
SURVIVE. Single mutants listed in EQUIVALENT are masked by a stronger adjacent gate by design; each has a JOINT mutant
(both gates removed) that must be KILLED. Results -> SCRATCH/mutation-results.json.

Usage: nice -n 19 python -B tests/mutate_s2_r4.py SCRATCH [JOBS]"""
import ast
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
S2_TESTS = ["tests/test_s2.py", "tests/test_s2_gate_profile.py", "tests/test_s2_r4_git.py"]


R4_MUTANTS = [
    # ---- the pinned layer loader
    # r5: the loader is the canonical bootstrap r1; these entries now target its embedded lines (its full guard set
    # is mutated by bootstrap-r1/mutate_adopter.py; MUTATION-RESULTS-r5-*.json)
    ("L-sha-pin-off", '    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:', """    if len(data) != size:"""),
    ("L-fingerprint-off", """    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:""", """    if False:"""),
    ("L-nlink-off-JOINT", [('        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:',
                            '        if not stat.S_ISREG(before.st_mode) or before.st_size != size:'),
                           ('if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size', 'if (not stat.S_ISREG(info.st_mode) or info.st_size != size')]),
    # ---- S2-R3-F1: every git call through si.git_run / si.git_show_file; the frozen-reader wrapper
    ("G-show-raw-git", """        return expected_read(label, mismatch, si.git_show_file, self.policy, self.role, self.repo, commit, rel, cap,
                             expected_sha256)""",
     """        import subprocess
        data = subprocess.run(["git", "-C", self.path, "show", commit + ":" + rel], capture_output=True).stdout
        if expected_sha256 is not None and sha_bytes(data) != expected_sha256:
            raise S2Error(mismatch or (label + " SHA mismatch"))
        return data"""),
    ("G-run-raw-git", """        return guarded(label, si.git_run, self.repo, list(args), 120, limit, None, ok_rcs).stdout""",
     """        import subprocess
        done = subprocess.run(["git", "-C", self.path, *args], capture_output=True)
        require(done.returncode in ok_rcs, label + " failed")
        return done.stdout"""),
    ("G-replace-ref-check-off", """        require(listing == b"", "the checkout carries refs/replace/""", """        require(True, "the checkout carries refs/replace/"""),
    ("G-frozen-env-inherited", """        os.environ.clear()
        os.environ.update(si.GIT_FIXED_ENV)""", """        os.environ.update(si.GIT_FIXED_ENV)"""),
    ("G-frozen-env-not-used", """    with frozen_git_env(checkout):""", """    with contextlib.nullcontext():"""),
    ("G-frozen-env-no-declared-gitdir", """        os.environ.update(HOME=home, XDG_CONFIG_HOME=home + "/xdg-config-absent", GIT_DIR=checkout.repo.git_dir,
                          GIT_WORK_TREE=checkout.repo.work_tree)""",
     """        os.environ.update(HOME=home, XDG_CONFIG_HOME=home + "/xdg-config-absent")"""),
    ("G-preread-off", """        checkout.show(commit, rel, item["sha256"], label, f"{label}: committed blob pin mismatch: {rel}")""",
     """        pass"""),
    ("G-worktree-hash-off", """        require(found["sha256"] == item["sha256"], f"{label}: work-tree pin mismatch: {rel}")""",
     """        pass"""),
    ("G-gitrepo-undeclared", """        self.repo = guarded("--repository", si.GitRepo, work_tree=path, git_dir=git_dir, common_dir=common_dir)""",
     """        self.repo = guarded("--repository", si.GitRepo, work_tree=path)"""),
    ("G-worktree-rule-off", """            require(TMP_CHECKOUT.fullmatch(checkout) is not None and common_dir == MAIN_CHECKOUT + "/.git\"""",
     """            require(True or TMP_CHECKOUT.fullmatch(checkout) is not None and common_dir == MAIN_CHECKOUT + "/.git\""""),
    # ---- the shared family denylist (S2's forbidden_reason) and the all-path lexical pass
    ("N-name-gate-off", """        si.name_gate(text, S2_HOST, ())""", """        pass"""),
    ("N-name-code-filter-off", """        if error.code == "name":""", """        if False:"""),
    ("N-local-end-rule-off", """        if part.lower() == "end":""", """        if False:"""),
    ("N-t1-tree-off", """        if T1_JOB_TREE.fullmatch(part):""", """        if False:"""),
    ("N-host-roots-off", """        if text == root or text.startswith(root + "/"):""", """        if False:"""),
    ("N-touch-before-all-lexical", """    for label, path, allowed, leaf, name_rule in specs:
        lexical(path, label)""", """    for label, path, allowed, leaf, name_rule in specs:
        os.path.lexists(path)
        lexical(path, label)"""),
    # ---- reads with expected SHA-256 (all production reads)
    ("R-read-gated-no-sha", """    data = expected_read(label, mismatch, handle.read_bytes, expected_sha256)""",
     """    data = expected_read(label, mismatch, handle.read_bytes, None)"""),
    ("R-bootstrap-si-sha-off", """mismatch, si.read_bytes, policy, role, rel, None, expected)""",
     """mismatch, si.read_bytes, policy, role, rel, None, None)"""),
    ("R-bootstrap-compare-off", """        require(expected is None or sha_bytes(cache[rel]) == expected, mismatch)""", """        pass"""),
    ("R-bootstrap-both-off-JOINT", [("""mismatch, si.read_bytes, policy, role, rel, None, expected)""",
                                     """mismatch, si.read_bytes, policy, role, rel, None, None)"""),
                                    ("""        require(expected is None or sha_bytes(cache[rel]) == expected, mismatch)""",
                                     """        pass""")]),
    ("R-load-s1-lexical-off", """    lexical(gated[0], "--s1-manifest")                        # pure, even on a direct call""", """    pass"""),
    ("R-evidence-no-sha", """location.as_posix(), None, a.evidence_sha256)""", """location.as_posix(), None, None)"""),
    ("R-s1-copy-no-pin", """row["local_size"], row["local_sha256"], codes=("sha", "size"))""", """None, None, codes=("sha", "size"))"""),
    ("R-strict-json-off", """    return guarded(label, si.loads_strict, raw, label)""", """    return json.loads(raw)"""),
    # ---- writes: si.check_absent at the gate + exclusive si.Writer
    ("W-check-absent-off", """                guarded(label, si.check_absent, policy, role_name(label), path.rsplit("/", 1)[1])""",
     """                pass"""),
    ("W-both-off-JOINT", [("""                guarded(label, si.check_absent, policy, role_name(label), path.rsplit("/", 1)[1])""",
                           """                pass"""),
                          ("""        guarded(label, writer.create_excl, path.rsplit("/", 1)[1], data, 0o644)""",
                           """        open(path, "wb").write(data)""")]),
]

# Single mutants masked by a stronger adjacent gate by design (each has a KILLED JOINT counterpart or a reason).
EQUIVALENT = {
    'L-sha-pin-off': 'r5: masked in the r4 test files by the earlier size pin (their other-bytes layer is longer); the SHA compare is killed by test_s2_r5_bootstrap kit scenario same-size-mismatch (MUTATION-RESULTS-r5-behaviour.json, R sha compare off)',
    "G-frozen-env-no-declared-gitdir": "on a canonical checkout (and on a declared linked worktree) git's own discovery "
                                       "finds the same git dir; the explicit GIT_DIR/GIT_WORK_TREE is defence in depth",
    "R-bootstrap-si-sha-off": "masked by the explicit SHA compare on the cached bytes (JOINT R-bootstrap-both-off)",
    "R-bootstrap-compare-off": "masked by si.read_bytes' expected-SHA check (JOINT R-bootstrap-both-off)",
    "W-check-absent-off": "masked by si.Writer.create_excl (O_EXCL; refuses '[exists]') (JOINT W-both-off)",
}
NULL_CONTROLS = 3

# r3 mutants whose snippets still exist exactly once in r4 (profiles, roots, bindings, bootstrap)
R3_KEPT = [('F1-no-allowed-root', '        require(allowed(path), f"{label}: outside its allowed root', '        require(True or allowed(path), f"{label}: outside its allowed root'),
    ('F1-no-normalisation', '            and posixpath.normpath(path) == path, f"{label}: not an absolute normalised path', '            , f"{label}: not an absolute normalised path'),
    ('F1-repo-relative-no-predicate', '    reason = forbidden_reason(rel)\n    require(reason is None, f"{label}: forbidden location ({reason}): {rel!r}")', ''),
    ('F1-s1-name-rule-off', '    require(name == S1_MANIFEST_NAME, f"--s1-manifest must be', '    require(True, f"--s1-manifest must be'),
    ('F1-json-name-rule-off', '    require(name.endswith(".json"), f"--profile-json must be', '    require(True, f"--profile-json must be'),
    ('F1-dest-receipt-pairing-off', '        require(a.s1_manifest == f"{a.s1_dest}/{S1_MANIFEST_NAME}",', '        require(True,'),
    ('F1-production-accepts-test-root', '            require(value is None, f"{TEST_ROOT_ENV} is a TEST-ONLY setting', '            require(True, f"{TEST_ROOT_ENV} is a TEST-ONLY setting'),
    ('F1-test-root-anywhere', '            require(value.startswith("/tmp/"), f"{TEST_ROOT_ENV} must lie', '            require(True, f"{TEST_ROOT_ENV} must lie'),
    ('F1-production-out-anywhere', '(lambda path: path == f"{a.repository}/{location.as_posix()}")', '(lambda path: True)'),
    ('F1-s1-rows-untyped', '            require(all(type(r[k]) is int if k.endswith("_size") else type(r[k]) is str for k in fields)', '            require(True'),
    ('F1-s1-rows-unchecked', '        require(isinstance(rows, list) and rows and all(isinstance(r, dict) and set(fields) <= set(r) for r in rows),', '        require(True,'),
    ('F1-s1-lenient-json', '    doc = strict_json(raw, "S1 manifest")', '    doc = json.loads(raw)'),
    ('F2-r2-fallback-restored', '    for host in mode.hosts:\n        check_profile(profiles[host], host, "profile JSON")', '    require(isinstance(profiles, dict), "x")'),
    ('F2-r2-behaviour-restored', [('        profile = profiles[host]                              # validated; never completed from defaults', '        profile = profiles.get(host) or dict(host=host, reference_slot=0, slot_count=11, console_rule=False,\n                                             warmup_seconds=mode.warmup, perception="none")'),
    ('    for host in mode.hosts:\n        check_profile(profiles[host], host, "profile JSON")', '    pass')]),
    ('F2-empty-allowed', '    require(type(profile) is dict and profile, f"{label}: the profile of', '    require(type(profile) is dict, f"{label}: the profile of'),
    ('F2-missing-allowed', '    require(not missing, f"{label}: the profile of {host} lacks', '    require(True, f"{label}: the profile of {host} lacks'),
    ('F2-unknown-allowed', '    require(not extra, f"{label}: the profile of {host} has unknown', '    require(True, f"{label}: the profile of {host} has unknown'),
    ('F2-host-unchecked', '    require(type(profile["host"]) is str and profile["host"] == host,', '    require(True,'),
    ('F2-slot-unchecked', '    require(type(profile["reference_slot"]) is int and profile["reference_slot"] == 0,', '    require(True,'),
    ('F2-count-unchecked', '    require(type(profile["slot_count"]) is int and profile["slot_count"] == REPORTING_SLOTS,', '    require(True,'),
    ('F2-console-unchecked', '    require(profile["console_rule"] is False,', '    require(True,'),
    ('F2-warmup-unchecked', '    require(type(warmup) in (int, float) and math.isfinite(warmup) and warmup >= MIN_WARMUP_SECONDS,', '    require(True,'),
    ('F2-perception-unchecked', '    require(profile["perception"] == "none",', '    require(True,'),
    ('F2-extras-untyped', '            require(type(profile[key]) is kind and profile[key],', '            require(True,'),
    ('F2-both-sources-allowed', '    require(supplied != default, "validation needs exactly one', '    require(supplied or default, "validation needs exactly one'),
    ('F2-neither-source-allowed', '    require(supplied != default, "validation needs exactly one', '    require(not (supplied and default), "validation needs exactly one'),
    ('F2-sha-pairing-off', '    require(supplied == (a.profile_json_sha256 is not None), "--profile-json and --profile-json-sha256 go together")', '    pass'),
    ('F2-source-mislabelled', '    return profiles, dict(profile_source="s4-bundles",', '    return profiles, dict(profile_source="declared-default",'),
    ('F2-source-path-unrecorded', 'profile_json_path=gated["--profile-json"][0],', 'profile_json_path=None,'),
    ('R2-bootstrap-skipped', '    if not mode.verify_code:                                   # TEST-ONLY', '    if True:                                   # TEST-ONLY'),
    ('R2-closure-finder-permissive', '        raise ImportError(f"S2 closure: {name} from {spec.origin} is outside the verified frozen closure")', '        return spec'),
    ('R2-exact-role-off', '        require(item["repository_path"] == rel, f"artifact {key} repository_path', '        require(True, f"artifact {key} repository_path'),
    ('R2-finite-positive-mhz-off', '        require(all(type(clocks[c]) in (int, float) and math.isfinite(clocks[c]) and clocks[c] > 0 for c in cpus),', '        require(True,'),
    ('R2-s1-meta-crosscheck-off', '        require(row["remote_sha256"] == row["committed_sha256"] == item["sha256"]', '        require(True')]
MUTANTS = R4_MUTANTS + R3_KEPT


def run(scratch, name, old, new=None):
    """old/new: one snippet, or old = [(old, new), ...] applied together (one combined mutant)."""
    mutated = (PACKAGE / "s2_end_evidence.py").read_text()
    for before, after in ([] if old is None else old if new is None else [(old, new)]):
        count = mutated.count(before)
        if count != 1:
            return dict(name=name, status="INVALID", detail=f"snippet occurs {count} times")
        mutated = mutated.replace(before, after)
    try:
        ast.parse(mutated)
    except SyntaxError as error:
        return dict(name=name, status="INVALID", detail=f"syntax: {error}")
    work = scratch / name
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(PACKAGE, work / "pkg", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (work / "pkg" / "s2_end_evidence.py").write_text(mutated)
    started = time.time()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    basetemp = tempfile.mkdtemp(prefix="s2r4-mut-", dir="/tmp")
    done = subprocess.run([sys.executable, "-B", "-O", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                           "--basetemp", basetemp + "/bt", *S2_TESTS], cwd=work / "pkg", capture_output=True,
                          text=True, env=env)
    shutil.rmtree(basetemp, ignore_errors=True)
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED")]
    status = "KILLED" if done.returncode == 1 and failed else "SURVIVED" if done.returncode == 0 else "INVALID"
    result = dict(name=name, status=status, returncode=done.returncode, seconds=round(time.time() - started, 1),
                  first_failure=failed[0] if failed else None, tail=done.stdout.splitlines()[-1:] if done.stdout else [])
    shutil.rmtree(work, ignore_errors=True)
    return result


def main():
    scratch = Path(sys.argv[1]).resolve()
    if not str(scratch).startswith("/dev/shm/"):
        raise SystemExit("SCRATCH must lie below /dev/shm/")
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    scratch.mkdir(parents=True, exist_ok=True)
    plan = list(MUTANTS)
    for i in range(NULL_CONTROLS):                      # unmodified source, interleaved: must SURVIVE
        plan.insert((i + 1) * len(plan) // (NULL_CONTROLS + 1), ("NULL-%d" % i, None, None))
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda m: run(scratch, *m), plan))
    digest = lambda rel: hashlib.sha256((PACKAGE / rel).read_bytes()).hexdigest()
    real = [r for r in results if not r["name"].startswith("NULL-")]
    nulls = [r for r in results if r["name"].startswith("NULL-")]
    survived = [r["name"] for r in real if r["status"] == "SURVIVED"]
    summary = dict(s2_sha256=digest("s2_end_evidence.py"), safe_input_sha256=digest("safe_input.py"),
                   tests_sha256={t: digest(t) for t in S2_TESTS},
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   total=len(real), killed=sum(r["status"] == "KILLED" for r in real), survived=survived,
                   survived_equivalent={n: EQUIVALENT[n] for n in survived if n in EQUIVALENT},
                   survived_unexplained=[n for n in survived if n not in EQUIVALENT],
                   invalid=[r["name"] for r in real if r["status"] == "INVALID"],
                   null_controls={r["name"]: r["status"] for r in nulls},
                   optimize=True, python=sys.version.split()[0], executable=sys.executable, results=results)
    (scratch / "mutation-results.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))
    for r in results:
        print(f"{r['status']:9} {r['name']:36} {r.get('first_failure') or r.get('detail') or r.get('tail')}")
    good = not summary["survived_unexplained"] and not summary["invalid"] and all(
        s == "SURVIVED" for s in summary["null_controls"].values())
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
