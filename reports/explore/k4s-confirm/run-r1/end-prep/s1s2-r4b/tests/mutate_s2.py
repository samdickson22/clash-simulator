"""Mutation check of the S2 r3 gates (not a pytest module). Each mutant replaces ONE exact snippet (or one listed set
of snippets) of s2_end_evidence.py (each asserted to occur exactly once), in a scratch copy of the package under SCRATCH/<name>/, then runs
the S2 suites there under python -O with -x and its own --basetemp. Killed = pytest exit 1 (a test failed); any
other exit (e.g. a collection error) is reported as INVALID, not as killed. Results -> SCRATCH/mutation-results.json.

Usage: nice -n 19 python -B tests/mutate_s2.py SCRATCH [JOBS]"""
import ast
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
S2_TESTS = ["tests/test_s2.py", "tests/test_s2_gate_profile.py"]

MUTANTS = [
    # ---- S2-R2-F1: the shared location gate
    ("F1-forbidden-predicate-off", '''    """Pure (no system call): why `path` is an outcome / strict-END / job-tree location, or None."""
''', '''    """Pure (no system call): why `path` is an outcome / strict-END / job-tree location, or None."""
    return None
'''),
    ("F1-no-end-component", '''FORBIDDEN_COMPONENTS = frozenset(("games", "hub-blocks", "end"))''',
     '''FORBIDDEN_COMPONENTS = frozenset(("games", "hub-blocks"))'''),
    ("F1-no-games-component", '''FORBIDDEN_COMPONENTS = frozenset(("games", "hub-blocks", "end"))''',
     '''FORBIDDEN_COMPONENTS = frozenset(("hub-blocks", "end"))'''),
    ("F1-no-hub-blocks-component", '''FORBIDDEN_COMPONENTS = frozenset(("games", "hub-blocks", "end"))''',
     '''FORBIDDEN_COMPONENTS = frozenset(("games", "end"))'''),
    ("F1-no-outcome-names", '''        if OUTCOME_NAME.fullmatch(part):''', '''        if False:'''),
    ("F1-no-job-tree-names", '''        if JOB_TREE.fullmatch(part):''', '''        if False:'''),
    ("F1-no-host-job-roots", '''        if path == root or path.startswith(root + "/"):''', '''        if False:'''),
    ("F1-no-allowed-root", '''        require(allowed(path), f"{label}: outside its allowed root''',
     '''        require(True or allowed(path), f"{label}: outside its allowed root'''),
    ("F1-no-normalisation", '''            and posixpath.normpath(path) == path, f"{label}: not an absolute normalised path''',
     '''            , f"{label}: not an absolute normalised path'''),
    ("F1-walk-follows-symlinks", '''        require(not stat.S_ISLNK(st.st_mode), f"{label}: component {prefix} is a symlink''',
     '''        require(True, f"{label}: component {prefix} is a symlink'''),
    ("F1-walk-no-nlink", '''        require(st.st_nlink == 1, f"{label}: {path} is a hard-link alias''',
     '''        require(True, f"{label}: {path} is a hard-link alias'''),
    ("F1-walk-after-each-lexical", '''            name_rule(path.rsplit("/", 1)[1])
    return {label''', '''            name_rule(path.rsplit("/", 1)[1])
        lstat_walk(path, label, leaf)
    return {label'''),
    ("F1-open-no-pre-lstat-symlink", '''                    require(not stat.S_ISLNK(pre.st_mode), f"{label}: {rel} is a symlink (alias), refused unopened")''',
     '''                    require(True, f"{label}: {rel} is a symlink (alias), refused unopened")'''),
    ("F1-open-no-pre-lstat-nlink", '''                    require(pre.st_nlink == 1, f"{label}: {rel} is a hard-link alias''',
     '''                    require(True, f"{label}: {rel} is a hard-link alias'''),
    ("F1-open-no-gate-identity", '''        require(expect is None or (st.st_dev, st.st_ino) == (expect.st_dev, expect.st_ino),''',
     '''        require(True,'''),
    ("F1-open-dir-not-lexical", '''    parts = lexical(path, label).split("/")[1:]''', '''    parts = path.split("/")[1:]'''),
    ("F1-write-new-not-lexical", '''    parent, name = lexical(path, label).rsplit("/", 1)''', '''    parent, name = path.rsplit("/", 1)'''),
    ("F1-repo-relative-no-predicate", '''    reason = forbidden_reason(rel)
    require(reason is None, f"{label}: forbidden location ({reason}): {rel!r}")''', ''''''),
    ("F1-s1-name-rule-off", '''    require(name == S1_MANIFEST_NAME, f"--s1-manifest must be''', '''    require(True, f"--s1-manifest must be'''),
    ("F1-json-name-rule-off", '''    require(name.endswith(".json"), f"--profile-json must be''', '''    require(True, f"--profile-json must be'''),
    ("F1-dest-receipt-pairing-off", '''        require(a.s1_manifest == f"{a.s1_dest}/{S1_MANIFEST_NAME}",''', '''        require(True,'''),
    ("F1-production-accepts-test-root", '''            require(value is None, f"{TEST_ROOT_ENV} is a TEST-ONLY setting''',
     '''            require(True, f"{TEST_ROOT_ENV} is a TEST-ONLY setting'''),
    ("F1-test-root-anywhere", '''            require(value.startswith("/tmp/"), f"{TEST_ROOT_ENV} must lie''', '''            require(True, f"{TEST_ROOT_ENV} must lie'''),
    ("F1-production-out-anywhere", '''(lambda path: path == f"{a.repository}/{location.as_posix()}")''', '''(lambda path: True)'''),
    ("F1-result-ungated", '''        result_path = gate_paths([("--result", a.result, mode.roots.prep, "new", output_name)])["--result"][0]''',
     '''        result_path = a.result'''),
    ("F1-s1-rows-untyped", '''            require(all(type(r[k]) is int if k.endswith("_size") else type(r[k]) is str for k in fields)''',
     '''            require(True'''),
    ("F1-s1-rows-unchecked", '''        require(isinstance(rows, list) and rows and all(isinstance(r, dict) and set(fields) <= set(r) for r in rows),''',
     '''        require(True,'''),
    ("F1-s1-lenient-json", '''    doc = strict_json(raw, "S1 manifest")''', '''    doc = json.loads(raw)'''),
    # ---- S2-R2-F2: strict profiles, no fallback
    ("F2-r2-fallback-restored", '''    for host in mode.hosts:
        check_profile(profiles[host], host, "profile JSON")''', '''    require(isinstance(profiles, dict), "x")'''),
    ("F2-r2-behaviour-restored", [('''        profile = profiles[host]                              # validated; never completed from defaults''',
      '''        profile = profiles.get(host) or dict(host=host, reference_slot=0, slot_count=11, console_rule=False,
                                             warmup_seconds=mode.warmup, perception="none")'''),
     ('''    for host in mode.hosts:
        check_profile(profiles[host], host, "profile JSON")''', '''    pass''')]),
    ("F2-empty-allowed", '''    require(type(profile) is dict and profile, f"{label}: the profile of''', '''    require(type(profile) is dict, f"{label}: the profile of'''),
    ("F2-missing-allowed", '''    require(not missing, f"{label}: the profile of {host} lacks''', '''    require(True, f"{label}: the profile of {host} lacks'''),
    ("F2-unknown-allowed", '''    require(not extra, f"{label}: the profile of {host} has unknown''', '''    require(True, f"{label}: the profile of {host} has unknown'''),
    ("F2-host-unchecked", '''    require(type(profile["host"]) is str and profile["host"] == host,''', '''    require(True,'''),
    ("F2-slot-unchecked", '''    require(type(profile["reference_slot"]) is int and profile["reference_slot"] == 0,''', '''    require(True,'''),
    ("F2-count-unchecked", '''    require(type(profile["slot_count"]) is int and profile["slot_count"] == REPORTING_SLOTS,''', '''    require(True,'''),
    ("F2-console-unchecked", '''    require(profile["console_rule"] is False,''', '''    require(True,'''),
    ("F2-warmup-unchecked", '''    require(type(warmup) in (int, float) and math.isfinite(warmup) and warmup >= MIN_WARMUP_SECONDS,''', '''    require(True,'''),
    ("F2-perception-unchecked", '''    require(profile["perception"] == "none",''', '''    require(True,'''),
    ("F2-extras-untyped", '''            require(type(profile[key]) is kind and profile[key],''', '''            require(True,'''),
    ("F2-duplicate-keys-allowed", '''        require(len(keys) == len(set(keys)), f"{label}: duplicate JSON key")''', '''        pass'''),
    ("F2-nan-allowed", '''        raise S2Error(f"{label}: non-finite JSON constant {name}")''', '''        return float(name)'''),
    ("F2-both-sources-allowed", '''    require(supplied != default, "validation needs exactly one''', '''    require(supplied or default, "validation needs exactly one'''),
    ("F2-neither-source-allowed", '''    require(supplied != default, "validation needs exactly one''', '''    require(not (supplied and default), "validation needs exactly one'''),
    ("F2-sha-pairing-off", '''    require(supplied == (a.profile_json_sha256 is not None), "--profile-json and --profile-json-sha256 go together")''',
     '''    pass'''),
    ("F2-source-mislabelled", '''    return profiles, dict(profile_source="s4-bundles",''', '''    return profiles, dict(profile_source="declared-default",'''),
    ("F2-source-path-unrecorded", '''profile_json_path=gated["--profile-json"][0],''', '''profile_json_path=None,'''),
    # ---- regression: r2 gates still guarded
    ("R2-bootstrap-skipped", '''    if not mode.verify_code:                                   # TEST-ONLY''', '''    if True:                                   # TEST-ONLY'''),
    ("R2-closure-finder-permissive", '''        raise ImportError(f"S2 closure: {name} from {spec.origin} is outside the verified frozen closure")''',
     '''        return spec'''),
    ("R2-exact-role-off", '''        require(item["repository_path"] == rel, f"artifact {key} repository_path''', '''        require(True, f"artifact {key} repository_path'''),
    ("R2-worktree-confinement-off", '''        require(confined_size(repository, rel, f"artifact {key}") > 0, f"empty artifact {rel}")''', '''        pass'''),
    ("R2-finite-positive-mhz-off", '''        require(all(type(clocks[c]) in (int, float) and math.isfinite(clocks[c]) and clocks[c] > 0 for c in cpus),''',
     '''        require(True,'''),
    ("R2-s1-meta-crosscheck-off", '''        require(row["remote_sha256"] == row["committed_sha256"] == item["sha256"]''', '''        require(True'''),
]


def run(scratch, name, old, new=None):
    """old/new: one snippet, or old = [(old, new), ...] applied together (one combined mutant)."""
    mutated = (PACKAGE / "s2_end_evidence.py").read_text()
    for before, after in (old if new is None else [(old, new)]):
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
    done = subprocess.run([sys.executable, "-B", "-O", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                           "--basetemp", str(work / "bt"), *S2_TESTS], cwd=work / "pkg", capture_output=True,
                          text=True, env=env)
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED")]
    status = "KILLED" if done.returncode == 1 and failed else "SURVIVED" if done.returncode == 0 else "INVALID"
    result = dict(name=name, status=status, returncode=done.returncode, seconds=round(time.time() - started, 1),
                  first_failure=failed[0] if failed else None, tail=done.stdout.splitlines()[-1:] if done.stdout else [])
    shutil.rmtree(work, ignore_errors=True)
    return result


def main():
    scratch = Path(sys.argv[1]).resolve()
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    scratch.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda m: run(scratch, *m), MUTANTS))
    digest = lambda rel: hashlib.sha256((PACKAGE / rel).read_bytes()).hexdigest()
    summary = dict(s2_sha256=digest("s2_end_evidence.py"), tests_sha256={t: digest(t) for t in S2_TESTS},
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   total=len(results), killed=sum(r["status"] == "KILLED" for r in results),
                   survived=[r["name"] for r in results if r["status"] == "SURVIVED"],
                   invalid=[r["name"] for r in results if r["status"] == "INVALID"],
                   optimize=True, python=sys.version.split()[0], results=results)
    (scratch / "mutation-results.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))
    for r in results:
        print(f"{r['status']:9} {r['name']:36} {r.get('first_failure') or r.get('detail') or r.get('tail')}")
    return 0 if summary["killed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
