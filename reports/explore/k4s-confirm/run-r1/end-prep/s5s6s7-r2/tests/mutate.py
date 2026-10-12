"""Mutation check of the safe_input adoption points and the new gates (offline).

Each mutant: copy the package into a fresh /dev/shm/s567r2-mut-* directory, apply its edits (each old text must occur
exactly once), re-pin the copy (tests/repin.py) so the SHA bootstraps load it, then run the named test files with
`python -O -B -m pytest -x` (test_pins.py is never included, so no mutant is killed by a pin alone). KILLED = the
suite fails. NULL controls (no edit) must SURVIVE. The verifier refuses -O at import (T1 R3-1), so its mutants run
without -O and are labelled so. The copy is removed afterwards.

  python3 tests/mutate.py --check-edits
  python3 tests/mutate.py --python /usr/bin/python3 --pythonpath /dev/shm/s567r2-pytest38 --jobs 12 --out R.json
"""
import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = "tests/"
HT, S5, S6W, S6V, S7 = (T + "test_host_tool.py", T + "test_s5_preflight.py", T + "test_s6_wrapper.py",
                        T + "test_s6_verifier.py", T + "test_s7_gate.py")
TOOL, PF, EW, PW, VER, GATE, REM = ("k4s_end_host_tool.py", "k4s_end_preflight.py", "k4s_end_exit_push.sh",
                                    "k4s_preflight_push.sh", "k4s_end_verify_push.py", "k4s_end_launch_gate.py",
                                    "k4s_end_launch_remote.py")

# (id, description, file, [(old, new)], tests)
MUTANTS = [
    # ---- k4s_end_host_tool.py
    ("H01", "registry: claim-name regex off", TOOL, [("if CLAIM.fullmatch(name) is None:", "if False:")], [HT]),
    ("H02", "registry: claim nlink/regular check off",
     TOOL, [("if st is None or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:", "if st is None:")], [HT]),
    ("H03", "verify_clone: replace refs ignored", TOOL, [('if replace != b"":', "if False:")], [HT]),
    ("H04", "verify_clone: any hook allowed", TOOL, [('patterns=("*.sample",)', 'patterns=("*",)')], [HT]),
    ("H05", "frozen env: inherited GIT_* kept",
     TOOL, [('env = {k: v for k, v in inherited.items() if not k.startswith("GIT_")}', "env = dict(inherited)")],
     [HT]),
    ("H06", "frozen env: no GIT_CONFIG_PARAMETERS", TOOL, [('    env["GIT_CONFIG_PARAMETERS"] = GIT_CONFIG_PARAMETERS\n',
                                                          "")], [HT]),
    ("H07", "global git config not checked",
     TOOL, [("si._check_git_config(parent, parts[-1], os.path.dirname(path))", "pass")], [HT]),
    ("H08", "read_pinned: nlink not checked",
     TOOL, [("or st.st_nlink != 1 or st.st_size > cap:", "or st.st_size > cap:")], [HT]),
    ("H09", "read_pinned: SHA not checked", TOOL, [("    if hashlib.sha256(data).hexdigest() != sha256:\n"
                                                    "        refuse(", "    if False:\n        refuse(")], [HT]),
    ("H10", "snapshot copies no claim",
     TOOL, [('names = listing["claims"].get("round-%02d/%s" % (round_index, host), []) if listing["exists"] else []',
             "names = []")], [HT, S6W]),
    ("H11", "Q3 seed commits not checked", TOOL, [("    for commit in commits:\n        si.git_run",
                                                   "    for commit in commits[:0]:\n        si.git_run")], [HT, S5]),
    ("H12", "frozen-exec: clone not verified",
     TOOL, [('record = verify_clone(si, host, option_value(command, "--repository"))', "record = {}")], [S6W]),
    # ---- k4s_end_preflight.py (S5)
    ("P01", "caller manifest SHA accepted", PF, [("if k4s_manifest_sha256 != K4S_MANIFEST_SHA256:", "if False:")], [S5]),
    ("P02", "manifest read without the anchor",
     PF, [("expected_sha256=K4S_MANIFEST_SHA256), MANIFEST_REL)", "expected_sha256=None), MANIFEST_REL)")], [S5]),
    ("P03", "closure table not compared", PF, [("require(derived == FROZEN_CLOSURE,", "require(True,")], [S5]),
    ("P04", "closure files not hashed against pins",
     PF, [('si.read_bytes(policy, "runtime", rel, max_size=64 << 20, expected_sha256=pin)',
           'si.read_bytes(policy, "runtime", rel, max_size=64 << 20, expected_sha256=None)')], [S5]),
    ("P05", "pre-import pins skipped", PF, [("row.update(pre_import_pins(si, policy))", "pass")], [S5]),
    ("P06", "S4 synthetic stamp accepted", PF, [("require(SYNTHETIC_KEY not in manifest,", "require(True,")], [S5]),
    ("P07", "non-production assembly receipt accepted",
     PF, [('receipt.get("production_pins") is True', "True")], [S5]),
    ("P08", "bundle manifest read without its SHA",
     PF, [('"tiers-pins.json", 64 << 20, expected_sha256=pins_sha256)', '"tiers-pins.json", 64 << 20)')], [S5]),
    ("P09", "runtime-<commit12> layout not enforced",
     PF, [("and RUNTIME_NAME.fullmatch(os.path.basename(runtime)),", ",")], [S5]),
    ("P10", "pf/rd guard-job form not enforced",
     PF, [('require(m.group(1).startswith("pf") == preflight,', "require(True,")], [S5]),
    ("P11", "guard repo clone not verified",
     PF, [('row.update(tool.verify_clone(si, host, guard_job + "/repo", grants=("guard-job",)))', "pass")], [S5]),
    ("P12", "repository clone not verified",
     PF, [("row.update(tool.verify_clone(si, host, str(a.repository)))", "pass")], [S5]),
    ("P13", "frozen git env not applied",
     PF, [("os.environ.update(tool.frozen_git_env(si, inherited))", "os.environ.update(inherited)")], [S5]),
    ("P14", "binding without reference work",
     PF, [('result["mode_requested"] == "binding" and load.get("reference_slot_work") is True',
           'result["mode_requested"] == "binding"')], [S5]),
    ("P15", "binding without measured duration",
     PF, [("and measured is not None and measured >= MIN_LOADED_SECONDS.get(host, float(\"inf\")))",
           "and True)")], [S5]),
    ("P16", "bus stop band never reached",
     PF, [('"stop" if percent >= BUS_STOP_MIN else', '"stop" if percent >= 99 else')], [S5]),
    ("P17", "attempt parent / guard-source copy not required",
     PF, [("unchanged and empty and copied and", "unchanged and")], [S5]),
    ("P18", "guard job freshness not checked",
     PF, [('                si.check_absent(policy, "guard-job", name)', "                pass")], [S5]),
    ("P19", "sample minimum not enforced",
     PF, [("require(len(admitted) >= a.min_samples,", "require(True,")], [S5]),
    ("P20", "loaded non-closure runtime module accepted",
     PF, [("require(rel in runtime_files,", "require(True,")], [S5]),
    ("P21", "closure_only off", PF, [("require(not outside,", "require(True,")], [S5]),
    ("P22", "verify-received: extra files accepted",
     PF, [("require(walked == set(names),", "require(True,")], [S5]),
    ("P23", "verify-received: file SHAs not compared",
     PF, [('require(si.sha256_input(S, "sealed", name)["sha256"] == digest,', "require(True,")], [S5]),
    ("P24", "verify-received: PUSH-FAILED ignored",
     PF, [('    si.check_absent(P, "recv", "PUSH-FAILED.json")\n', "")], [S5]),
    ("P25", "frozen manifest not bound to the pinned bundle",
     PF, [("require(canonical(manifest) == canonical(ctx.manifest),", "require(True,")], [S5]),
    # ---- wrappers (S6)
    ("W01", "END wrapper: argv.nul by truncating redirection (r1 bug)",
     EW, [('for name in "$attempt" exit.json exit.json.tmp argv.nul TRANSFER-DONE.json',
           'for name in "$attempt" exit.json exit.json.tmp TRANSFER-DONE.json'),
          ("receipt=$(printf '%s\\0' \"$@\" | tool si -- create-excl --host \"$host\" --root \"$job\" --rel argv.nul "
           "--max-size 65536) \\\n  || exit 91", "printf '%s\\0' \"$@\" > \"$job/argv.nul\" || exit 91")], [S6W]),
    ("W02", "END wrapper: metadata pre-checks off",
     EW, [('  test ! -e "$job/$name" && test ! -L "$job/$name" || exit 90', "  true")], [S6W]),
    ("W03", "END wrapper: command not through frozen-exec", EW, [('tool frozen-exec -- "$@"', '"$@"')], [S6W]),
    ("W04", "END wrapper: refused registry snapshot ignored", EW, [('"$snapshot" || failed=1', "true")], [S6W]),
    ("W05", "END wrapper: host tool SHA not checked",
     EW, [('"$host_tool" | sha256sum --check --status --strict || exit 90', '"$host_tool" | true')], [S6W]),
    ("W06", "END wrapper: PUSH-FAILED by redirection",
     EW, [("    | tool si -- create-excl --host \"$host\" --root \"$job\" --rel PUSH-FAILED.json --max-size 4096) "
           "|| exit 92", "    > \"$job/PUSH-FAILED.json\")")], [S6W]),
    ("W07", "preflight wrapper: argv.nul by truncating redirection",
     PW, [('for name in "$attempt" exit.json exit.json.tmp argv.nul TRANSFER-DONE.json',
           'for name in "$attempt" exit.json exit.json.tmp TRANSFER-DONE.json'),
          ("receipt=$(printf '%s\\0' \"$@\" | tool si -- create-excl --host \"$host\" --root \"$job\" --rel argv.nul "
           "--max-size 65536) \\\n  || exit 91", "printf '%s\\0' \"$@\" > \"$job/argv.nul\" || exit 91")], [S6W]),
    # ---- verifier (S6; refuses -O: run without -O)
    ("V01", "C-d not enforced", VER, [("c_d_satisfied=now >= exit_epoch + C_D_SECONDS)", "c_d_satisfied=True)")], [S6V]),
    ("V02", "D3 members not hashed", VER, [('        si.hash_sealed_end_member(S, "s6-sealed-end", attempt + '
                                            '"/durable-measurement/" + name, files[name])', "        pass")], [S6V]),
    ("V03", "sealed listing not compared", VER, [("require(sealed_names(si, data, set(d3)) == sorted(set(files) | "
                                                  "set(SEAL_FILES)),", "require(True,")], [S6V]),
    ("V04", "received registry not bound to the listing",
     VER, [('require(walked == ["registry/" + n for n in names],', "require(True,")], [S6V]),
    ("V05", "registry claims read without listing SHA",
     VER, [('1 << 20, expected_sha256=entry["sha256"])', "1 << 20)")], [S6V]),
    ("V06", "ordinary member SHA not compared",
     VER, [('require(si.sha256_input(S, "sealed", name)["sha256"] == files[name],', "require(True,")], [S6V]),
    ("V07", "PUSH-FAILED ignored", VER, [('        si.check_absent(P, "recv", "PUSH-FAILED.json")\n',
                                          "        pass\n")], [S6V]),
    ("V08", "wrapper SHA not checked", VER, [("require(launch['wrapper_sha256'] == WRAPPER_SHA256,", "require(True,")],
     [S6V]),
    # ---- gate (S7, 05 side)
    ("G01", "RC-6 roots not bound to k4s-end-r1/Q4",
     GATE, [('and d["guard_parent"] == si.Q4_GUARD_PARENTS[host], "RC-6 %s: roots differ',
             'or True, "RC-6 %s: roots differ')], [S7]),
    ("G02", "undeclared bundle accepted",
     GATE, [('    raise GateRefusal("Not a declared RC-6 bundle for %s: %s" % (host, path))',
             '    return dict(path=path, tiers_pins_sha256="0" * 64, guard_job=path)')], [S7]),
    ("G03", "preflight receipt schema not checked",
     GATE, [('require(v.get("schema") == VERIFIED_SCHEMA and v.get("scope") == "K4S-END-PREFLIGHT" and',
             'require(True and')], [S7]),
    ("G04", "diagnostic preflight accepted for RC-9",
     GATE, [('require(v.get("mode") == "binding" and v.get("qualifying") is True,', "require(True,")], [S7]),
    ("G05", "reference load not required",
     GATE, [('require(load.get("reference_slot_work") is True and', "require(True or")], [S7]),
    ("G06", "loaded duration not required",
     GATE, [('require((duration.get("loaded_seconds_measured") or 0) >= MIN_LOADED_SECONDS[host],',
             "require(True,")], [S7]),
    ("G07", "04 bus STOP band accepted",
     GATE, [('require(v.get("bus_band") == "proceed",', "require(True,")], [S7]),
    ("G08", "preflight provenance not re-hashed",
     GATE, [('            == v.get("receipt_manifest_sha256")\n', '            == si.sha256_input(P, "pf-recv", base + '
                                                                  '"preflight/receipt-manifest.json")["sha256"]\n')],
     [S7]),
    ("G09", "preflight input binding not checked",
     GATE, [('require(inputs.get("runtime_root") == d["runtime"] and', "require(True or")], [S7]),
    ("G10", "03 ACK verified before C-d accepted",
     GATE, [('and ack["verified_epoch"] >= ack["exit_epoch"] + C_D_SECONDS, "03 ACK', 'or True, "03 ACK')], [S7]),
    ("G11", "RC-7 admission not required",
     GATE, [('and adm.get("closed_before_admission") is True, "03 launch', 'or True, "03 launch')], [S7]),
    ("G12", "03 failed seal accepted", GATE, [('and ack.get("status") == "complete"', "")], [S7]),
    ("G13", "open ControlMaster accepted", GATE, [("ok_rcs=(255,))", "ok_rcs=(0, 255))")], [S7]),
    ("G14", "diagnostic preflight launch without the flag",
     GATE, [('require("--no-reference-work" not in opts or diagnostic,', "require(True,")], [S7]),
    ("G15", "preflight receive dir not empty accepted",
     GATE, [('require(names == [], "Preflight receive directory must be empty")', "pass")], [S7]),
    ("G16", "END bundle of another round accepted",
     GATE, [('require(g.group(1).startswith("rd%02d-a" % int(opts["--round"])),', "require(True,")], [S7]),
    # ---- host program (S7, host side)
    ("R01", "failed ps not reported", REM, [('        failures.append("ps: %s" % str(error)[:300])\n', "")], [S7]),
    ("R02", "hostname not bound to the host", REM, [('expected=cfg["host"])', "expected=None)")], [S7]),
    ("R03", "frozen-reader checks skipped", REM, [("    frozen_reader(cfg, P, res, failures)\n", "")], [S7]),
    ("R04", "staged pins not compared",
     REM, [('ok = si.sha256_input(P, "tools", os.path.basename(path))["sha256"] == expected',
            'ok = bool(si.sha256_input(P, "tools", os.path.basename(path)))')], [S7]),
    ("R05", "C5 nice not checked", REM, [('(gate["ps_nice"] == "0" and', '(True and')], [S7]),
    ("R06", "two claims accepted", REM, [("if len(names) >= 2:", "if False:")], [S7]),
]
# Equivalent mutants (masked by a stronger check on the same path; documented, not test gaps):
EQUIVALENT = {
    "P14": "load['reference_slot_work'] and mode_requested == 'binding' both derive from the same --no-reference-work "
           "argument (result['load'] is set from a.reference_work); the states-worked > 0 condition remains",
    "P22": "the walk role allows exactly the sealed names (an extra file refuses as allowlist) and every listed file is "
           "hashed (a missing one refuses as missing), so the set equality cannot fail on its own",
}
NULLS = [("N%02d" % i, "NULL control (unmodified)", None, [], files)
         for i, files in enumerate([[HT, S5], [S6W, S6V], [S7], [S5], [S7], [S6W]], 1)]


def apply(root, mutant):
    _, _, name, edits, _ = mutant
    if name is None:
        return
    path = root / name
    text = path.read_text()
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise SystemExit("%s: edit target occurs %d times in %s: %r" % (mutant[0], count, name, old[:80]))
        text = text.replace(old, new)
    path.write_text(text)


def run_one(mutant, python, pythonpath, timeout):
    ident, desc, name, edits, files = mutant
    work = Path(tempfile.mkdtemp(prefix="s567r2-mut-%s-" % ident, dir="/dev/shm"))
    try:
        pkg = work / "s5s6s7-r2"
        shutil.copytree(ROOT, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        apply(pkg, mutant)
        subprocess.run([sys.executable, "-B", str(pkg / "tests" / "repin.py")], check=True, capture_output=True)
        optimized = name != VER and not (name is None and S6V in files)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if pythonpath:
            env["PYTHONPATH"] = pythonpath
        argv = ["nice", "-n", "19", python] + (["-O"] if optimized else []) + ["-B", "-m", "pytest", "-x", "-q",
                                                                               "-p", "no:cacheprovider"] + files
        started = time.time()
        try:
            done = subprocess.run(argv, cwd=str(pkg), env=env, capture_output=True, text=True, timeout=timeout)
            rc, tail = done.returncode, (done.stdout + done.stderr)[-600:]
        except subprocess.TimeoutExpired:
            rc, tail = "timeout", "timeout"
        verdict = "KILLED" if rc != 0 else "SURVIVED"
        return dict(id=ident, description=desc, file=name, tests=files, optimized=optimized, rc=rc,
                    verdict=verdict, seconds=round(time.time() - started, 1), tail=tail)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-edits", action="store_true")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--pythonpath", default="")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.check_edits:
        for mutant in MUTANTS:
            path = ROOT / mutant[2]
            text = path.read_text()
            for old, _ in mutant[3]:
                if text.count(old) != 1:
                    raise SystemExit("%s: target occurs %d times: %r" % (mutant[0], text.count(old), old[:80]))
        print("%d mutants, every edit target occurs exactly once" % len(MUTANTS))
        return 0
    todo = [m for m in MUTANTS + NULLS if not a.only or m[0] in a.only]
    results = []
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        for result in pool.map(lambda m: run_one(m, a.python, a.pythonpath, a.timeout), todo):
            results.append(result)
            print("%-4s %-9s %6ss  %s" % (result["id"], result["verdict"], result["seconds"], result["description"]),
                  flush=True)
    import hashlib
    for r in results:
        if r["id"] in EQUIVALENT:
            r["equivalent"] = EQUIVALENT[r["id"]]
    summary = dict(python=a.python, equivalent_survivors=sorted(r["id"] for r in results if r["id"] in EQUIVALENT
                                                                   and r["verdict"] == "SURVIVED"), created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   package_sha256={n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
                                   for n in (TOOL, PF, EW, PW, VER, GATE, REM, "safe_input.py")},
                   mutants=len([r for r in results if not r["id"].startswith("N")]),
                   killed=len([r for r in results if not r["id"].startswith("N") and r["verdict"] == "KILLED"]),
                   nulls_survived=len([r for r in results if r["id"].startswith("N") and r["verdict"] == "SURVIVED"]),
                   nulls=len([r for r in results if r["id"].startswith("N")]), results=results)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, sort_keys=True))
    if a.out:
        Path(a.out).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
