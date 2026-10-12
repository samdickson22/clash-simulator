#!/usr/bin/env python3
"""Mutation check of the r3 gates plus ruling E4 (CANDIDATE b3-r3b; offline; writes only to a fresh temp directory).

r3b: the r3 mutants are kept (the E2-only SHA mutant is replaced by its E4 form) and the E4 list logic is added.

Each mutant replaces one exact snippet of assemble_fleet_reference.py (it must occur exactly once), in a scratch copy
next to an unmodified copy of test_assemble_fleet_reference.py, and runs the whole suite under the current
interpreter's flags plus -O. A mutant is KILLED when the suite fails. The unmutated copy must pass first.

  K4S_FROZEN_ROOT=<detached origin/main worktree> nice -n 19 python -B mutation_check_r3b.py [--jobs N] [--json OUT]
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASM, TESTS = "assemble_fleet_reference.py", "test_assemble_fleet_reference.py"

MUTANTS = [
    ("F1 walk st_nlink gate removed",
     '        require(st.st_nlink == 1, "Hard-linked input refused (" + label + "): " + rel)\n', ""),
    ("F1 descriptor st_nlink gate removed", "    if now.st_nlink != 1:\n", "    if False:\n"),
    ("F2 END namespace gate is a no-op", "!= END_PAIR,", "!= ('never', 'matches'),"),
    ("F2 location_free not called by walk",
     "    location_free(os.path.join(str(root), rel), label, exception)\n    current = Path(root)\n",
     "    current = Path(root)\n"),
    ("F2 location_free skips the END namespace", "    end_namespace_free(parts, label)\n    no_t1", "    no_t1"),
    ("F2 location_free skips the T1 namespaces", "    no_t1_launch_namespace(text, label)\n    return text\n",
     "    return text\n"),
    ("F2 location_free accepts unsafe absolute paths",
     "    require(isinstance(path, (str, Path)) and text.startswith(\"/\")",
     "    require(True or isinstance(path, (str, Path)) and text.startswith(\"/\")"),
    ("F2 runtime END directory descended",
     '                    end_namespace_free(os.path.join(str(root), name)[1:].split("/"), "runtime directory " + name)\n',
     ""),
    ("F2 --out location gate removed (check_out)",
     '    location_free(str(out), "--out")', "    pass"),
    ("F2 guard job parent not gated", '    location_free(JOB_PARENTS[host], "guard job parent")', "    pass"),
    ("F2 committed admission location gate removed",
     '        location_free(os.path.join(str(repository), rel), "committed admission")\n', ""),
    ("F2/E3 exact admission path not required",
     '        require(rel == expected, "Committed admission must be exactly "',
     '        require(True or rel == expected, "Committed admission must be exactly "'),
    ("F2 evidence item location gate removed",
     '        location_free(os.path.join(str(artifacts), name), "evidence artifact")', "        pass"),
    ("F2 git_blob location gate removed",
     "    location_free(os.path.join(str(repository), relative(rel, label)), label)\n", ""),
    ("F2 seed path back to outcome_free only",
     '        location_free("/" + name, "seed path")', '        outcome_free(name.split("/"), "seed path")'),
    ("F2 --request read without the gates",
     '    raw = Source(*absolute(str(a.request.absolute()), "--request", "file")).read()',
     "    raw = Path(str(a.request.absolute())).read_bytes()"),
    ("F2 assembler self-hash without the gates",
     '    assembler = Source(*absolute(os.path.abspath(__file__), "assembler", "file")).sha()',
     "    import hashlib as _h; assembler = _h.sha256(Path(__file__).read_bytes()).hexdigest()"),
    ("F3 synthetic pins read without the gates (r2 form)",
     '    pins = parse_json(read_confined(*absolute(location, SYNTHETIC_ENV, "file")), "synthetic pins")',
     '    pins = parse_json(Path(location).read_bytes(), "synthetic pins")'),
    ("E1/E2 check_exemptions is a no-op",
     '    require(pins.get("runtime_aliases") == {E1_ALIAS: E1_TARGET}',
     '    return\n    require(pins.get("runtime_aliases") == {E1_ALIAS: E1_TARGET}'),
    ("E1/E2 runtime_files skips check_exemptions",
     "    check_exemptions(pins, synthetic=pins is not PRODUCTION_PINS)\n", ""),
    ("E1 committed alias not checked", "    committed_alias(repo)", "    pass"),
    ("E1 git mode not required", 'rb"120000 blob', 'rb"[0-9]{6} blob'),
    ("E1 link text at HEAD not required",
     '    require(git_run(repository, ["cat-file", "blob", match.group(1).decode()], "E1 alias") == E1_TARGET.encode(),',
     '    require(True or git_run(repository, ["cat-file", "blob", match.group(1).decode()], "E1 alias") == E1_TARGET.encode(),'),
    ("E1 alias target gated only by name (no hard-link gate through the alias walk)",
     "            return walk(root, target, label, kind)",
     "            return Path(root) / target, os.lstat(Path(root) / target)"),
    ("E3 stale bus identity accepted (r2 gate, re-checked)",
     '            require(identity == pinned_admissions[name]["identity"]',
     '            require(True or identity == pinned_admissions[name]["identity"]'),
    # ---- r3b: ruling E4 (exact four-entry complete.json list)
    ("E4 pins: widened list accepted", "set(exceptions) == set(E4_COMPLETE_JSON)", "set(exceptions) >= set(E4_COMPLETE_JSON)"),
    ("E4 pins: narrowed list accepted", "set(exceptions) == set(E4_COMPLETE_JSON)", "set(exceptions) <= set(E4_COMPLETE_JSON)"),
    ("E4 pins: SHA shape not checked", "            and all(is_sha(digest) for digest in exceptions.values()),",
     "            and True,"),
    ("E4 production SHAs not enforced", "    require(synthetic or exceptions == E4_COMPLETE_JSON,", "    require(True,"),
    ("E4 HEAD tree check not called", '    committed_receipts(repo, PINS["runtime_outcome_name_exceptions"])', "    pass"),
    ("E4 HEAD: unlisted tracked complete.json skipped",
     '        require(name in exceptions, "Tracked complete.json not on the E4 exempt list refused: " + name)\n',
     "        if name not in exceptions:\n            continue\n"),
    ("E4 HEAD: leaf-only match (complete.json directory component missed)",
     '        if OUTCOME_RECEIPT not in name.split("/"):', '        if name.split("/")[-1] != OUTCOME_RECEIPT:'),
    ("E4 HEAD: mode 100644 not required", 'rb"100644 blob ', 'rb"[0-9]{6} blob '),
    ("E4 HEAD: blob SHA not compared", "        require(hashlib.sha256(blob).hexdigest() == exceptions[name],",
     "        require(True or hashlib.sha256(blob).hexdigest() == exceptions[name],"),
    ("E4 runtime: unlisted complete.json not refused by the scan",
     '                    require(name in exceptions, "complete.json not on the E4 exempt list refused (runtime tree): " + name)\n',
     ""),
    ("E4 runtime: scan block removed (unlisted untracked complete.json never seen)",
     '                if entry.name == OUTCOME_RECEIPT:\n'
     '                    require(name in exceptions, "complete.json not on the E4 exempt list refused (runtime tree): " + name)\n'
     '                    present.append(name)\n', ""),
    ("E4 runtime: directory named complete.json not matched",
     "                if entry.name == OUTCOME_RECEIPT:",
     "                if entry.name == OUTCOME_RECEIPT and not entry.is_dir(follow_symlinks=False):"),
    ("E4 runtime: present non-members not walked/hashed", "    for name in sorted(names | set(present)):",
     "    for name in sorted(names):"),
    ("E4 runtime: exempt SHA not compared",
     "        require(name not in hashed or hashed[name] == expected,", "        require(True,"),
    ("E4 runtime: non-members become runtime members", "    result = {name: hashed[name] for name in sorted(names)}",
     "    result = hashed"),
    ("E4 runtime: walk exemption for every runtime name", "exception=name in exceptions)", "exception=True)"),
    ("E4 runtime: walk exemption never applied", "exception=name in exceptions)", "exception=False)"),
    ("E3 stale idle identity accepted (r2 gate, re-checked)",
     '            require(services[0]["service"] == pinned_admissions[name]["service"]',
     '            require(True or services[0]["service"] == pinned_admissions[name]["service"]'),
]


def run_suite(directory, env):
    flags = ["-B", "-O"]
    done = subprocess.run([sys.executable, *flags, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf",
                           str(directory / TESTS)], capture_output=True, text=True, env=env, cwd=directory)
    failed = re.findall(r"^FAILED \S+::(\S+)", done.stdout, flags=re.M)
    summary = (done.stdout.strip().splitlines() or [""])[-1]
    return done.returncode, failed, summary


def one(label, old, new, env):
    with tempfile.TemporaryDirectory(prefix="b3r3b-mut-") as scratch:
        scratch = Path(scratch)
        source = (HERE / ASM).read_text()
        if source.count(old) != 1:
            return dict(mutant=label, result="NOT-APPLIED", detail="snippet occurs %d times" % source.count(old))
        (scratch / ASM).write_text(source.replace(old, new))
        shutil.copyfile(HERE / TESTS, scratch / TESTS)
        code, failed, summary = run_suite(scratch, env)
        return dict(mutant=label, result="KILLED" if code != 0 else "SURVIVED", failed=len(failed),
                    killing_tests=failed[:6], summary=summary)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json")
    a = ap.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="b3r3b-base-") as scratch:
        scratch = Path(scratch)
        for name in (ASM, TESTS):
            shutil.copyfile(HERE / name, scratch / name)
        code, failed, summary = run_suite(scratch, env)
        print("baseline (-O):", summary, flush=True)
        if code != 0:
            raise SystemExit("baseline fails: " + repr(failed))
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        results = list(pool.map(lambda m: one(*m, env), MUTANTS))
    for r in results:
        print("%-9s %-75s %s" % (r["result"], r["mutant"], ", ".join(r.get("killing_tests", []))[:200]))
    killed = sum(r["result"] == "KILLED" for r in results)
    print("killed %d of %d" % (killed, len(results)))
    if a.json:
        Path(a.json).write_text(json.dumps(dict(baseline=summary, results=results), indent=1) + "\n")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
