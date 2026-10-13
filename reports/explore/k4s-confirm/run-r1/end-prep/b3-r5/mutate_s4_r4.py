#!/usr/bin/env python3
"""Mutation check of the S4 r4 safe_input adoption (CANDIDATE b3-r4b: layer r3 + E5; offline; writes only below /dev/shm).

Each mutant replaces one exact snippet of assemble_fleet_reference.py (or a listed set: a JOINT mutant; every
snippet must occur exactly once) in a scratch copy (a TemporaryDirectory below /dev/shm, removed after) next to the
unmodified safe_input.py and both test files, and runs both suites under python -O with -x and a --basetemp inside the
scratch directory. KILLED = pytest exit 1 (a test failed or errored, e.g. in a fixture); any other exit is INVALID. NULL controls (unmodified
source) are interleaved and must SURVIVE. Single mutants listed in EQUIVALENT are masked by a stronger adjacent gate by
design; each has a JOINT counterpart that must be KILLED.

  K4S_FROZEN_ROOT=<read-only origin/main export> nice -n 19 python -B mutate_s4_r4.py [--jobs N] [--json OUT]
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
TESTS = ("test_assemble_fleet_reference.py", "test_s4_r4_git.py")

MUTANTS = [
    # ---- the pinned layer loader and the production re-check
    # r5: the loader is the canonical bootstrap r1; these two entries now target its embedded lines (its full guard
    # set is mutated by bootstrap-r1/mutate_adopter.py; MUTATION-RESULTS-r5-*.json)
    ("L sha pin off", '    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:', "    if len(data) != size:"),
    ("L fingerprint pin off", "    if module.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:", "    if False:"),
    ("L nlink check off JOINT", [('        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:',
                                  '        if not stat.S_ISREG(before.st_mode) or before.st_size != size:'),
                                 ('if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size', 'if (not stat.S_ISREG(info.st_mode) or info.st_size != size')]),
    ("L production in-process re-check off",
     "        require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT,", "        require(True,"),
    # ---- names first (S4-R3-F2 and every input class before any access)
    ("N Sources full-path gate off", "            guarded(label, si.name_gate, path, host, ())", "            pass"),
    ("N Sources leaf gate off", "            guarded(labels[path], si.gate_names, self.policy, name, split(path)[1])",
     "            pass"),
    ("N Sources both gates off JOINT", [
        ("            guarded(label, si.name_gate, path, host, ())", "            pass"),
        ("            guarded(labels[path], si.gate_names, self.policy, name, split(path)[1])", "            pass")]),
    ("N evidence artifact pre-open gate off",
     '        guarded("evidence artifact " + name, si.gate_names, art, "artifacts", name)', "        pass"),
    ("N runtime pin entries not gated",
     '                guarded("S1 runtime-pin entry " + name, si.gate_names, self.policy, self.role, name,',
     '                (lambda *a, **k: None)("S1 runtime-pin entry " + name, si.gate_names, self.policy, self.role, name,'),
    ("N guard job remote gate off", '    guarded("guard job", si.gate_names, remote, "guard-parent", os.path.basename(job))',
     "    pass"),
    ("N --out name gate off", '        guarded("--out", si.gate_names, self.policy, "out", self.name)', "        pass"),
    ("N --out leaf never gated JOINT", [
        ('        guarded("--out", si.gate_names, self.policy, "out", self.name)', "        pass"),
        ('        guarded("--out", si.check_absent, self.policy, "out", self.name,\n                mismatch="--out must be a new absolute directory", codes=("exists",))',
         "        pass")]),
    # ---- exemption constants (single source in safe_input); r4b: E5 from the layer (the r4 hook mutants are gone
    #      with the hook; these target the r4b E5 adoption)
    ("X E4 SHAs not bound to the layer", "    require(exceptions == si.E4_COMPLETE_JSON,", "    require(True,"),
    ("X E5 runtime role without the E5 exemption", 'exemptions=("E4", "E5"))])', 'exemptions=("E4",))])'),
    ("X E5 entry hashed by sha256_input (ordinary read path)",
     '                found = guarded("runtime E5 entry " + rel, si.hash_e5, self.policy, self.role, rel,',
     '                found = guarded("runtime E5 entry " + rel, si.sha256_input, self.policy, self.role, rel,'),
    ("X E5 runtime pin entries gated without the E5 flag",
     '            if guarded("S1 runtime-pin entry " + name, si.e5_blob_oid, name) is None:',
     '            if guarded("S1 runtime-pin entry " + name, si.e5_blob_oid, name) is None or True:'),
    ("X E5 non-members accepted", "        require(not stray,", "        require(True,"),
    ("X E5 all-hashed check off", '    require(set(inventory.e5_oids) == set(inventory.walk["e5"]),', "    require(True,"),
    ("X E5 non-members accepted and all-hashed check off JOINT", [
        ("        require(not stray,", "        require(True,"),
        ('    require(set(inventory.e5_oids) == set(inventory.walk["e5"]),', "    require(True,")]),
    ("G E5 runtime/committed binding skipped", "    repo.check_e5(inventory.e5_oids)", "    pass"),
    ("G E5 committed OID not compared", "            require(committed.get(rel) == oid,", "            require(True,"),
    ("G repository role without the E5 exemption", 'exemptions=("E1", "E4", "E5"))])', 'exemptions=("E1", "E4"))])'),
    ("G E5 paths not planned at HEAD", "        wanted = set(self.needed) | set(si.E4_COMPLETE_JSON) | set(si.E5_PATHS)",
     "        wanted = set(self.needed) | set(si.E4_COMPLETE_JSON)"),
    # ---- committed side (S4-R3-F1/F3): si.git_plan, E1 (D2), E3, E4
    ("G git_plan screens the whole tree (no D1-style members)", 'members=lambda e: e["path"] in wanted)', "members=None)"),
    ("G E4 committed hashes skipped", "    repo.check_e4()", "    pass"),
    ("G E1 committed check skipped", "    repo.check_e1()", "    pass"),
    ("G E1 shipped copy not verified", "        repo.verify_shipped_e1(runtime)", "        pass"),
    ("G E3 committed admission blob not checked",
     '"Committed admission blob differs from --committed-admission SHA: " + name)',
     '"Committed admission blob differs from --committed-admission SHA: " + name) if False else None'),
    ("G evidence committed blob not checked",
     '    repo.blob(repo.evidence_rel, evidence_sha, "END evidence", "END evidence differs from its committed HEAD blob")',
     "    pass"),
    # ---- reads with expected SHA-256
    ("R runtime pin/qualified read without SHA", "        raw = guarded(label, si.read_bytes, self.policy, self.role, rel, None, expected,",
     "        raw = guarded(label, si.read_bytes, self.policy, self.role, rel, None, None,"),
    ("R E4 non-member runtime entries not hashed", '        for rel in self.walk["e4"]:                    # E4 non-members',
     '        for rel in []:                    # E4 non-members'),
    ("R pinned_json without SHA", '    raw = guarded(label, si.read_bytes, policy, role, rel, None, entry["sha256"], mismatch="Pin mismatch: " + label)',
     '    raw = guarded(label, si.read_bytes, policy, role, rel, None, None, mismatch="Pin mismatch: " + label)'),
    ("R pinned_source SHA not compared", '    require(found["sha256"] == entry["sha256"], "Pin mismatch: " + label)',
     '    require(True, "Pin mismatch: " + label)'),
    ("R request read without SHA",
     '    raw = guarded("--request", si.read_bytes, policy, "request", parents[1][1], None, a.request_sha256,',
     '    raw = guarded("--request", si.read_bytes, policy, "request", parents[1][1], None, None,'),
    ("R synthetic pins read with a plain open",
     '    pins = parse_json(guarded(SYNTHETIC_ENV, si.read_bytes, policy, "synthetic-pins", leaf), "synthetic pins")',
     '    pins = parse_json(open(path, "rb").read(), "synthetic pins")'),
    ("R runtime role without the E4 exemption", 'exemptions=("E4", "E5"))])', 'exemptions=("E5",))])'),
    # ---- writes (R7 plain copies, exclusive stage, re-hash)
    ("W copy without expected SHA", "                    copy.size, 0o444, mismatch=\"Source changed while copying: \" + name)",
     "                    None, 0o444, mismatch=\"Source changed while copying: \" + name) if False else "
     "guarded(\"copy \" + name, si.copy_input, copy.policy, copy.role, copy.rel, writer, rel, None, None, 0o444)"),
    ("W copy re-hash off", '            require(found["sha256"] == copy.sha256, "Copy differs from its pin: " + name)',
     '            require(True, "Copy differs from its pin: " + name)'),
    ("W copy unchecked and re-hash off JOINT", [
        ("                    copy.size, 0o444, mismatch=\"Source changed while copying: \" + name)",
         "                    None, 0o444, mismatch=\"Source changed while copying: \" + name) if False else "
         "guarded(\"copy \" + name, si.copy_input, copy.policy, copy.role, copy.rel, writer, rel, None, None, 0o444)"),
        ('            require(found["sha256"] == copy.sha256, "Copy differs from its pin: " + name)',
         '            require(True, "Copy differs from its pin: " + name)')]),
    ("W previous partial accepted", 'mismatch="A previous partial bundle exists: " + text, codes=("exists",))',
     'mismatch="A previous partial bundle exists: " + text, codes=("exists",)) if False else None'),
    ("W manifest writable", 'writer.create_excl, target.stage + "/" + MANIFEST, data, 0o444)',
     'writer.create_excl, target.stage + "/" + MANIFEST, data, 0o644)'),
]

EQUIVALENT = {
    'L sha pin off': 'r5: masked in the r4 test files by the earlier size pin (their other-bytes layer is longer); the SHA compare is killed by test_s4_r5_bootstrap kit scenario same-size-mismatch (MUTATION-RESULTS-r5-behaviour.json, R sha compare off)',
    "N Sources full-path gate off": "the same names are refused by si.Policy (roots) + si.gate_names (leaves) a few "
                                    "lines later, still before any access; only the label differs (JOINT killed)",
    "N Sources leaf gate off": "the full-path si.name_gate pass covers every leaf first (JOINT killed)",
    "X E5 all-hashed check off": "every walked E5 entry must be a runtime member (stray check) and every member is "
                                 "hashed by members(), so the set equality is implied (JOINT with the stray check "
                                 "killed)",
    "N guard job remote gate off": "the leaf is fixed by JOB_NAME (k4s-end-guard-...), which no family matches, and the "
                                   "parent is name-gated when the remote si.Policy is built",
    "N --out name gate off": "si.check_absent(<out>) name-gates the same leaf before any access (JOINT killed)",
    "W copy without expected SHA": "masked by the stage re-hash against the planned SHA (JOINT killed)",
    "W copy re-hash off": "masked by si.copy_input's expected-SHA check of the bytes it wrote (JOINT killed)",
}
NULL_CONTROLS = 3


def run_suite(directory, env):
    done = subprocess.run([sys.executable, "-B", "-O", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-rf",
                           "-k", "not test_production_q6",           # r5: the two real-Q6 tests are never run
                           "--basetemp", str(directory / "bt"), *TESTS], capture_output=True, text=True, env=env,
                          cwd=directory)
    failed = re.findall(r"^(?:FAILED|ERROR) \S+::(\S+)", done.stdout, flags=re.M)
    summary = (done.stdout.strip().splitlines() or [""])[-1]
    return done.returncode, failed, summary


def one(label, old, new, env):
    source = (HERE / ASM).read_text()
    pairs = [] if old is None else old if new is None else [(old, new)]
    for before, after in pairs:
        if source.count(before) != 1:
            return dict(mutant=label, result="INVALID", detail="snippet occurs %d times" % source.count(before))
        source = source.replace(before, after)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="b3r4b-mut-", dir="/dev/shm") as scratch:
        scratch = Path(scratch)
        (scratch / ASM).write_text(source)
        for name in (LAYER,) + TESTS:
            shutil.copyfile(HERE / name, scratch / name)
        code, failed, summary = run_suite(scratch, env)
    result = "KILLED" if code == 1 else "SURVIVED" if code == 0 else "INVALID"     # 1 = a test failed or errored
    return dict(mutant=label, result=result, returncode=code, killing_test=failed[:1], summary=summary,
                seconds=round(time.time() - started, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json")
    a = ap.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    plan = list(MUTANTS)
    for i in range(NULL_CONTROLS):
        plan.insert((i + 1) * len(plan) // (NULL_CONTROLS + 1), ("NULL-%d" % i, None, None))
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        results = list(pool.map(lambda m: one(m[0], m[1], m[2] if len(m) > 2 else None, env), plan))
    real = [r for r in results if not r["mutant"].startswith("NULL-")]
    survived = [r["mutant"] for r in real if r["result"] == "SURVIVED"]
    digest = lambda name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
    summary = dict(assembler_sha256=digest(ASM), safe_input_sha256=digest(LAYER),
                   tests_sha256={t: digest(t) for t in TESTS}, frozen_root=bool(os.environ.get("K4S_FROZEN_ROOT")),
                   finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), optimize=True,
                   python=sys.version.split()[0], executable=sys.executable,
                   total=len(real), killed=sum(r["result"] == "KILLED" for r in real), survived=survived,
                   survived_equivalent={n: EQUIVALENT[n] for n in survived if n in EQUIVALENT},
                   survived_unexplained=[n for n in survived if n not in EQUIVALENT],
                   invalid=[r["mutant"] for r in real if r["result"] == "INVALID"],
                   null_controls={r["mutant"]: r["result"] for r in results if r["mutant"].startswith("NULL-")},
                   results=results)
    for r in results:
        print("%-9s %-58s %s" % (r["result"], r["mutant"], (r.get("killing_test") or [r.get("detail") or r.get("summary")])[0]))
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(summary, indent=1) + "\n")
    good = not summary["survived_unexplained"] and not summary["invalid"] and all(
        v == "SURVIVED" for v in summary["null_controls"].values())
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
