#!/usr/bin/env python3
"""Mutation check of an ADOPTER's embedded canonical bootstrap (S2 / S4) (not a pytest module). Stdlib only.

Every snippet mutant of mutate_bootstrap.py (kind "snippet") is applied to the adopter's embedded copy, plus the
adopter glue mutants below (pins, default path, fingerprint, refusal convention, explicit path). Each mutant runs in a
scratch copy laid out as <scratch>/mNN/end-prep/{bootstrap-r1, <adopter dir>} (the kit is found next to it, as in the
delivered tree), with -x, under the given interpreter/flags; pytest base temps are tempfile dirs below /tmp (S2 test
roots must lie below /tmp/). Two campaigns:
  default      the adopter's canonical-text test is EXCLUDED (-k "not canonical_text"): a mutant must be killed by
               behaviour at the entrypoint (kit scenarios, swap, fingerprint, explicit path). ENTRY_KILL lists the
               mutants expected to die here; the rest are UNIT mutants (races, pin formats, traceback cache ...), which
               only bootstrap-r1's unit suite can observe (mutate_bootstrap.py kills them there).
  --with-text  the canonical-text test included: every edit of the embedded region must be killed.
S4 always runs with -k "not test_production_q6" (the two real-Q6 tests are never run).

    nice -n 19 taskset -c 0-7 python3 -B mutate_adopter.py --adopter s2|s4 --python PY [--optimize] [--with-text]
        --scratch /dev/shm/X --jobs N --json OUT [--pythonpath P] [--frozen-root DIR]
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
END_PREP = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("mutate_bootstrap", os.path.join(HERE, "mutate_bootstrap.py"))
MB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MB)

ADOPTERS = {
    "s2": dict(dir="s1s2-r5", file="s2_end_evidence.py", tests=["tests/test_s2_r5_bootstrap.py", "tests/test_s2_r4_git.py"],
               keyword=""),
    "s4": dict(dir="b3-r5", file="assemble_fleet_reference.py", tests=["test_s4_r5_bootstrap.py", "test_s4_r4_git.py"],
               keyword="not test_production_q6"),
}
GLUE = [
    ("G size pin off by one", "kill", [("SAFE_INPUT_SIZE = 133606\n", "SAFE_INPUT_SIZE = 133605\n")]),
    ("G fingerprint check off", "kill", [("    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:\n        raise",
                                          "    if False:\n        raise")]),
    ("G refusal convention SystemExit", "kill", [
        ("    module = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, SAFE_INPUT_MODULE, RuntimeError)",
         "    module = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, SAFE_INPUT_MODULE, SystemExit)")]),
    ("G explicit path ignored", "kill", [
        ("    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path",
         "    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE)")]),
    ("G old abspath default", "kill", [
        ("    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path",
         "    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SAFE_INPUT_FILE) if path is None else path")]),
    ("G realpath default", "kill", [
        ("    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path",
         "    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), SAFE_INPUT_FILE) if path is None else path")]),
    ("G sha pin wrong", "kill", [("SAFE_INPUT_SHA256 = \"806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00\"\n",
                                  "SAFE_INPUT_SHA256 = \"806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f01\"\n")]),
    ("NULL adopter comment", "null", [("\"\"\"The vendored layer through the canonical bootstrap (refusal: RuntimeError, as before)", None)]),
]
# Snippet mutants that the adopter's ENTRYPOINT tests must kill without the canonical-text test (predicted before
# the run from the scenario list; every other snippet mutant is a UNIT mutant, observable only in bootstrap-r1).
ENTRY_KILL = {"N name gate off", "N no casefold", "N lower not casefold", "N games family dropped",
              "N end-raw family dropped", "N ancestors not gated", "P JOINT normpath+component off",
              "W ancestor follows symlinks", "W full-path open (no walk)", "W walk not from /",
              "L pre-open inspection off", "L pre-open nlink off", "L pre-open size off",
              "L JOINT pre-open off + leaf follows", "L leaf open not relative to parent", "R sha compare off",
              "X re-read by path before exec", "X tag not set", "D default path normalizes", "D default path resolves"}


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def mutants(adopter_text, with_text):
    out = []
    for label, expect, edits in MB.MUTANTS:
        if not all(kind == MB.S for kind, _, _ in edits):
            continue
        if label.startswith("NULL"):
            continue
        if with_text:
            want = "kill"
        else:
            want = "kill" if label in ENTRY_KILL else ("unit" if expect == "kill" else expect)
        out.append((label, want, [(o, n) for _, o, n in edits]))
    for label, expect, edits in GLUE:
        if label.startswith("NULL"):
            edits = [(edits[0][0], edits[0][0] + " ")]
        out.append((label, expect, edits))
    for label, expect, edits in out:
        region_start = adopter_text.index("# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 ")
        for old, new in edits:
            if adopter_text.count(old) != 1:
                raise SystemExit("edit not unique in adopter (%d): %s %r" % (adopter_text.count(old), label, old))
            if not label.startswith(("G ", "NULL")) and adopter_text.index(old) < region_start:
                raise SystemExit("snippet edit outside the embedded region: " + label)
    return out


def run_one(index, mutant, args, cfg):
    label, expect, edits = mutant
    root = os.path.join(args.scratch, "m%02d" % index)
    end_prep = os.path.join(root, "end-prep")
    shutil.copytree(os.path.join(END_PREP, "bootstrap-r1"), os.path.join(end_prep, "bootstrap-r1"),
                    ignore=shutil.ignore_patterns("__pycache__", "PROGRESS.md", "MUTATION-*"))
    pkg = os.path.join(end_prep, cfg["dir"])
    shutil.copytree(os.path.join(END_PREP, cfg["dir"]), pkg, ignore=shutil.ignore_patterns("__pycache__", "MUTATION-*"))
    target = os.path.join(pkg, cfg["file"])
    with open(target, encoding="utf-8") as handle:
        text = handle.read()
    for old, new in edits:
        text = text.replace(old, new)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    keyword = " and ".join(k for k in (cfg["keyword"], "" if args.with_text else "not canonical_text") if k)
    base = tempfile.mkdtemp(prefix="k4s-bs1-mutad-", dir="/tmp")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if args.pythonpath:
        env["PYTHONPATH"] = args.pythonpath
    if args.frozen_root:
        env["K4S_FROZEN_ROOT"] = args.frozen_root
    start = time.time()
    rc, tail = 0, ""
    for number, test_file in enumerate(cfg["tests"]):  # one pytest per file, the r5 bootstrap file first: a mutant
        cmd = [args.python] + (["-O"] if args.optimize else []) + [  # that breaks the import of the adopter is judged
            "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",  # by its failing tests, not by another file's
            "--basetemp", os.path.join(base, "bt%d" % number)]           # collection error
        if keyword:
            cmd += ["-k", keyword]
        cmd.append(test_file)
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, cwd=pkg, env=env)
            rc, tail = done.returncode, (done.stdout + done.stderr)[-1500:]
        except subprocess.TimeoutExpired:
            rc, tail = "timeout", ""
        if rc == 5:                                     # every test of this file deselected: not a verdict
            rc = 0
        if rc != 0:
            break
    status = {1: "KILLED", 0: "SURVIVED"}.get(rc, "INVALID")
    failed = [line for line in tail.splitlines() if line.startswith("FAILED ")]
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(base, ignore_errors=True)
    return dict(label=label, expect=expect, status=status, rc=rc, seconds=round(time.time() - start, 1),
                killed_by=failed[:1], detail=tail if status == "INVALID" else "")


def as_expected(r):
    if r["expect"] == "kill":
        return r["status"] == "KILLED"
    if r["expect"] in ("null", "equivalent", "unit"):
        return r["status"] in (("SURVIVED",) if r["expect"] == "null" else ("SURVIVED", "KILLED"))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adopter", required=True, choices=sorted(ADOPTERS))
    ap.add_argument("--python", required=True)
    ap.add_argument("--pythonpath", default="")
    ap.add_argument("--frozen-root", default="")
    ap.add_argument("--optimize", action="store_true")
    ap.add_argument("--with-text", action="store_true")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()
    cfg = ADOPTERS[args.adopter]
    with open(os.path.join(END_PREP, cfg["dir"], cfg["file"]), encoding="utf-8") as handle:
        chosen = list(enumerate(mutants(handle.read(), args.with_text)))
    os.makedirs(args.scratch)
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda im: run_one(im[0], im[1], args, cfg), chosen))
    ok = all(as_expected(r) for r in results) and not any(r["status"] == "INVALID" for r in results)
    files = [cfg["file"]] + cfg["tests"]
    summary = dict(tool="bootstrap-r1 mutate_adopter.py", adopter=args.adopter, campaign="with-text" if args.with_text
                   else "behaviour (canonical-text test excluded)", python=args.python, optimize=args.optimize,
                   utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   sha256={f: sha(os.path.join(END_PREP, cfg["dir"], f)) for f in files},
                   kit_sha256={n: sha(os.path.join(HERE, "tests", n)) for n in ("k4s_bootstrap_kit.py", "kit_harness.py")},
                   counts={k: sum(1 for r in results if r["status"] == k) for k in ("KILLED", "SURVIVED", "INVALID")},
                   by_expectation={e: {k: sum(1 for r in results if r["expect"] == e and r["status"] == k)
                                       for k in ("KILLED", "SURVIVED", "INVALID")}
                                   for e in sorted({r["expect"] for r in results})},
                   all_as_expected=ok, mutants=results)
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print(json.dumps(summary["by_expectation"]), "all_as_expected=%s" % ok)
    for r in results:
        if not as_expected(r) or r["status"] == "INVALID":
            print("UNEXPECTED", r["label"], r["expect"], r["status"], r.get("detail", "")[-300:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
