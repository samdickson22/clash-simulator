#!/usr/bin/env python3
"""Mutation check of the S4 r7 changes (ruling IR-03: 127x03 admissions = system bus only; the IR-03 refusals) and of
the kept plan idle-host check (:989) (offline; writes only below /dev/shm).

Each mutant replaces one exact snippet of assemble_fleet_reference.py (or a listed set; every snippet must occur exactly
once) in a scratch copy (a TemporaryDirectory below /dev/shm, removed after) next to the unmodified safe_input.py and
the test files, then runs, under python -O with --basetemp inside the scratch directory:
  1. its NAMED killing tests only (node ids): KILLED = pytest exit 1 and every named test is reported FAILED/ERROR;
  2. the suite (test_assemble_fleet_reference.py, test_s4_r4_git.py, test_s4_r6_runtime_pin.py, test_s4_r7_ir03.py; -x),
     as a cross-check: KILLED = exit 1. (test_s4_r5_bootstrap.py needs ../bootstrap-r1 and covers only the loader,
     which no r7 mutant touches.)
Any other exit is INVALID. NULL controls (unmodified source) must SURVIVE both runs. The two real-Q6 tests are
deselected (-k "not test_production_q6") in every run.

  K4S_FROZEN_ROOT=<read-only origin/main export> nice -n 19 python -B mutate_s4_r7.py [--jobs N] [--json OUT]
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
TESTS = ("test_assemble_fleet_reference.py", "test_s4_r4_git.py", "test_s4_r6_runtime_pin.py", "test_s4_r7_ir03.py")
R7 = "test_s4_r7_ir03.py::"
T = "test_assemble_fleet_reference.py::"
PIN03 = "        },                                                        # r7 (IR-03): no idle-services.json pin on 03\n"
R6_IDLE_PIN = ('            "idle-services.json": {"service": {\n'
               '                "pid": 2180947, "ppid": 2180946, "pgid": 2180934, "start_ticks": 139691386,\n'
               '                "cmdline_sha256": "16152ceb7942621141a2d8d91189affdeacde28ad1a9059ffbadde5e9bde799a", '
               '"uid": 3822945}},\n        },\n')
ARGV = ('        require(not retired_idle(host, (name,), pins), "--committed-admission idle-services.json on 127x03" '
        '+ IR03_RETIRED)\n')
GUARD = ('    require(not (isinstance(admissions, dict) and retired_idle(host, admissions, PINS)),\n'
         '            "guard.admissions idle-services.json on 127x03" + IR03_RETIRED)\n')
HOST = '    return (host == IR03_HOST and "idle-services.json" in names\n'
PINNED = '            and "idle-services.json" not in pins["admissions"].get(host, {}))'
KEPT_989 = ('    require("idle-services.json" not in admissions or host in idle_hosts, "Idle-service admission on a host '
            'without the exception")\n')
IR03_REFUSALS = [R7 + "test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it",
                 R7 + "test_r7_03_committed_idle_binding_refuses_citing_ir03",
                 R7 + "test_r7_committed_bindings_refusal_is_pure",
                 R7 + "test_r7_03_idle_only_still_refuses_the_missing_bus"]

MUTANTS = [
    # ---- the pin: PRODUCTION_PINS["admissions"]["127x03"] = system bus only
    ("IR-03 pin: the r6 03 idle-service pin restored", PIN03, R6_IDLE_PIN,
     [R7 + "test_r7_production_admission_pins_are_bus_only_on_both_hosts", R7 + "test_r7_every_other_pin_is_the_r6_value",
      R7 + "test_r7_retired_idle_is_pin_driven_and_03_only",
      R7 + "test_r7_bus_only_passes_under_the_production_admission_pins[127x03]",
      R7 + "test_r7_03_bus_only_ignores_the_retired_committed_idle_copy",
      R7 + "test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it",
      R7 + "test_r7_committed_bindings_refusal_is_pure",
      T + "test_f2_production_pins_are_the_verified_constants"]),
    # ---- the two IR-03 refusals
    ("IR-03 --committed-admission check off", ARGV, "",
     [R7 + "test_r7_03_committed_idle_binding_refuses_citing_ir03", R7 + "test_r7_committed_bindings_refusal_is_pure"]),
    ("IR-03 guard.admissions check off", GUARD, "",
     [R7 + "test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it",
      R7 + "test_r7_03_idle_only_still_refuses_the_missing_bus"]),
    ("IR-03 both checks off (generic r6 messages only)", "def retired_idle(host, names, pins):\n",
     "def retired_idle(host, names, pins):\n    return False\n", IR03_REFUSALS),
    ("IR-03 message does not cite the ruling", 'IR03_RETIRED = (" refused: ruling IR-03 (127x03',
     'IR03_RETIRED = (" refused: (127x03', IR03_REFUSALS),
    # ---- retired_idle's conditions
    ("IR-03 on every host (04 loses its r6 refusal)", HOST, '    return (True and "idle-services.json" in names\n',
     [R7 + "test_r7_retired_idle_is_pin_driven_and_03_only", R7 + "test_r7_04_idle_in_request_keeps_the_r6_refusal",
      T + "test_f2_idle_admission_refused_on_04"]),
    ("IR-03 ignores the pins (a re-pin cannot lift it)", PINNED, "            and True)",
     [R7 + "test_r7_retired_idle_is_pin_driven_and_03_only", R7 + "test_r7_03_repinned_idle_is_accepted_test_only",
      T + "test_f2_idle_admission_required_on_03_when_repinned"]),
    ("IR-03 retires the bus admission too", HOST, "    return (host == IR03_HOST and bool(names)\n",
     [R7 + "test_r7_retired_idle_is_pin_driven_and_03_only", R7 + "test_r7_03_bus_only_bundle",
      R7 + "test_r7_bus_only_passes_under_the_production_admission_pins[127x03]", T + "test_happy_path_bundle"]),
    # ---- kept unchanged: :989 (an idle admission only on a plan idle_service_exception host)
    ("kept :989 plan idle-host check off", KEPT_989, "", [R7 + "test_r7_plan_idle_host_check_unchanged"]),
]
NULL_CONTROLS = 2
NULL_NAMED = [R7 + "test_r7_production_admission_pins_are_bus_only_on_both_hosts", R7 + "test_r7_03_bus_only_bundle",
              R7 + "test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it"]


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
    with tempfile.TemporaryDirectory(prefix="b3r7-mut-", dir="/dev/shm") as scratch:
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
