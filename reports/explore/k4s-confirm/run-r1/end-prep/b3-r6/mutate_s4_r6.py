#!/usr/bin/env python3
"""Mutation check of the S4 r6 changes (B1: runtime-pin-r2 "files" shape; L4: assembler_sha256) (offline; writes
only below /dev/shm).

Each mutant replaces one exact snippet of assemble_fleet_reference.py (or a listed set; every snippet must occur exactly
once) in a scratch copy (a TemporaryDirectory below /dev/shm, removed after) next to the unmodified safe_input.py and
the test files, then runs, under python -O with --basetemp inside the scratch directory:
  1. its NAMED killing tests only (node ids): KILLED = pytest exit 1 and every named test is reported FAILED/ERROR;
  2. the suite (test_assemble_fleet_reference.py, test_s4_r4_git.py, test_s4_r6_runtime_pin.py; -x), as a cross-check:
     KILLED = exit 1. (test_s4_r5_bootstrap.py needs ../bootstrap-r1 and covers only the loader, which no r6 mutant
     touches.)
Any other exit is INVALID. NULL controls (unmodified source) must SURVIVE both runs. The two real-Q6 tests are
deselected (-k "not test_production_q6") in every run.

  K4S_FROZEN_ROOT=<read-only origin/main export> nice -n 19 python -B mutate_s4_r6.py [--jobs N] [--json OUT]
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASM, LAYER = "assemble_fleet_reference.py", "safe_input.py"
TESTS = ("test_assemble_fleet_reference.py", "test_s4_r4_git.py", "test_s4_r6_runtime_pin.py")
R6 = "test_s4_r6_runtime_pin.py::"
SHAPE = '        require(isinstance(listed, (dict, list)) and all(isinstance(n, str) for n in listed),'
NAMES = '        names = {relative(n, "S1 runtime-pin entry") for n in listed}'
RESULT = '        result = {name: self.sha(name) for name in sorted(names)}'
RECEIPT = '                       assembler_sha256=facts["assembler_sha256"], safe_input_sha256=facts["safe_input_sha256"],'

MUTANTS = [
    # ---- B1: the runtime-pin-r2 "files" shape (frozen prepare_bundle.py:42: names = set(...["files"]))
    ("B1 list only (the b3-r5 rule)", SHAPE,
     '        require(isinstance(listed, list) and all(isinstance(n, str) for n in listed),',
     [R6 + "test_r6_real_runtime_membership_equals_frozen_rule_and_s9",
      R6 + "test_r6_real_pin_bytes_through_members_in_synthetic_world",
      R6 + "test_r6_dict_membership_is_the_keys_not_the_values",
      "test_assemble_fleet_reference.py::test_happy_path_bundle"]),
    ("B1 dict only (a list refused)", SHAPE,
     '        require(isinstance(listed, dict) and all(isinstance(n, str) for n in listed),',
     [R6 + "test_r6_list_form_gives_the_same_set_as_frozen"]),
    ("B1 membership = the dict values", NAMES,
     '        names = {relative(n, "S1 runtime-pin entry") for n in (listed.values() if isinstance(listed, dict) '
     'else listed)}',
     [R6 + "test_r6_dict_membership_is_the_keys_not_the_values",
      R6 + "test_r6_real_runtime_membership_equals_frozen_rule_and_s9"]),
    ("B1 per-file SHAs compared (stricter than frozen)", RESULT,
     RESULT + '\n        require(not isinstance(listed, dict) or all(result.get(n) == v for n, v in listed.items()),'
              ' "S1 runtime pin SHA differs")',
     [R6 + "test_r6_dict_per_file_shas_are_never_compared[ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff]",
      R6 + "test_r6_real_runtime_membership_equals_frozen_rule_and_s9",
      R6 + "test_r6_real_pin_bytes_through_members_in_synthetic_world"]),
    ("B1 per-file SHAs must be 64-hex (S9's shape rule, not frozen)", SHAPE,
     SHAPE + '\n                "S1 runtime pin lacks a files dict (or list) of names")\n'
             '        require(not isinstance(listed, dict) or all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v)'
             ' for v in listed.values()),',
     [R6 + "test_r6_dict_per_file_shas_are_never_compared[None]", R6 + "test_r6_dict_per_file_shas_are_never_compared[7]"]),
    ("B1 a string accepted as an iterable of names", SHAPE,
     '        require(isinstance(listed, (dict, list, str)) and all(isinstance(n, str) for n in listed),',
     [R6 + "test_r6_other_files_shapes_refused[string]"]),
    ("B1 name type check off", SHAPE, '        require(isinstance(listed, (dict, list)),',
     [R6 + "test_r6_other_files_shapes_refused[list-int]", R6 + "test_r6_other_files_shapes_refused[list-null]",
      R6 + "test_r6_other_files_shapes_refused[list-list]"]),
    ("B1 shape check off", SHAPE, '        require(True,',
     [R6 + "test_r6_other_files_shapes_refused[null]", R6 + "test_r6_other_files_shapes_refused[int]",
      R6 + "test_r6_other_files_shapes_refused[no-files]", R6 + "test_r6_other_files_shapes_refused[top-list]"]),
    ("B1 dict keys not path-checked", NAMES, '        names = set(listed)',
     [R6 + "test_r6_dict_keys_are_gated_like_list_items",
      "test_assemble_fleet_reference.py::test_f1_dotdot_runtime_pin_entry_refused_before_read"]),
    # ---- L4: the assembler's own SHA-256 in the receipt and the stderr summaries
    ("L4 receipt assembler_sha256 dropped", RECEIPT,
     '                       safe_input_sha256=facts["safe_input_sha256"],',
     [R6 + "test_r6_receipt_and_summary_carry_assembler_sha256"]),
    ("L4 receipt assembler_sha256 = the request SHA", '    facts["assembler_sha256"] = assembler',
     '    facts["assembler_sha256"] = a.request_sha256',
     [R6 + "test_r6_receipt_and_summary_carry_assembler_sha256"]),
    ("L4 dry-run summary assembler_sha256 dropped", '                             assembler_sha256=assembler)),',
     '                             )),', [R6 + "test_r6_receipt_and_summary_carry_assembler_sha256"]),
    ("L4 real-run summary assembler_sha256 dropped",
     '                         production_pins=not facts["synthetic"], assembler_sha256=assembler)), file=sys.stderr)',
     '                         production_pins=not facts["synthetic"])), file=sys.stderr)',
     [R6 + "test_r6_receipt_and_summary_carry_assembler_sha256"]),
]
NULL_CONTROLS = 2
NULL_NAMED = [R6 + "test_r6_real_runtime_membership_equals_frozen_rule_and_s9",
              R6 + "test_r6_receipt_and_summary_carry_assembler_sha256"]


def pytest(directory, env, args, tag):
    done = subprocess.run([sys.executable, "-B", "-O", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE",
                           "-k", "not test_production_q6", "--basetemp", str(directory / ("bt-" + tag)), *args],
                          capture_output=True, text=True, env=env, cwd=directory)
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+?)(?: - |$)", done.stdout, flags=re.M)
    return done.returncode, failed, (done.stdout.strip().splitlines() or [""])[-1]


def one(label, old, new, named, env):
    source = (HERE / ASM).read_text()
    if old is not None:
        if source.count(old) != 1:
            return dict(mutant=label, result="INVALID", detail="snippet occurs %d times" % source.count(old))
        source = source.replace(old, new)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="b3r6-mut-", dir="/dev/shm") as scratch:
        scratch = Path(scratch)
        (scratch / ASM).write_text(source)
        for name in (LAYER,) + TESTS:
            shutil.copyfile(HERE / name, scratch / name)
        n_code, n_failed, n_summary = pytest(scratch, env, named, "named")
        s_code, s_failed, s_summary = pytest(scratch, env, ["-x", *TESTS], "suite")
    named_killed = n_code == 1 and sorted(set(n_failed)) == sorted(set(named))
    verdict = lambda code: "KILLED" if code == 1 else "SURVIVED" if code == 0 else "INVALID"
    result = ("KILLED" if named_killed and s_code == 1 else "SURVIVED" if n_code == 0 and s_code == 0 else "INVALID"
              if n_code not in (0, 1) or s_code not in (0, 1) else "PARTIAL")
    return dict(mutant=label, result=result, named_tests=named, named_result=verdict(n_code), named_failed=n_failed,
                named_summary=n_summary, every_named_test_failed=named_killed, suite_result=verdict(s_code),
                suite_first_failure=s_failed[:1], suite_summary=s_summary, seconds=round(time.time() - started, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json")
    a = ap.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    plan = [(m[0], m[1], m[2], m[3]) for m in MUTANTS]
    for i in range(NULL_CONTROLS):
        plan.insert((i + 1) * len(plan) // (NULL_CONTROLS + 1), ("NULL-%d" % i, None, None, NULL_NAMED))
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        results = list(pool.map(lambda m: one(*m, env), plan))
    real = [r for r in results if not r["mutant"].startswith("NULL-")]
    digest = lambda name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
    summary = dict(assembler_sha256=digest(ASM), safe_input_sha256=digest(LAYER), driver_sha256=digest(Path(__file__).name),
                   tests_sha256={t: digest(t) for t in TESTS}, frozen_root=bool(os.environ.get("K4S_FROZEN_ROOT")),
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), optimize=True,
                   python=sys.version.split()[0], executable=sys.executable,
                   total=len(real), killed=sum(r["result"] == "KILLED" for r in real),
                   not_killed=[r["mutant"] for r in real if r["result"] != "KILLED"],
                   null_controls={r["mutant"]: r["result"] for r in results if r["mutant"].startswith("NULL-")},
                   results=results)
    for r in results:
        print("%-8s %-62s named=%s suite=%s %s" % (r["result"], r["mutant"], r.get("named_result"),
                                                   r.get("suite_result"), r.get("detail") or r.get("suite_first_failure")))
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(summary, indent=1) + "\n")
    good = not summary["not_killed"] and all(v == "SURVIVED" for v in summary["null_controls"].values())
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
