#!/usr/bin/env python3
"""Mutation check of the canonical bootstrap r1 (not a pytest module). Stdlib only.

Each mutant applies exact edits (each `old` must occur exactly once) to a scratch copy of this package:
  snippet  -> k4s_bootstrap_r1.py AND the identical prefix of k4s_bootstrap_loader_r1.py (one canonical text)
  main     -> the loader main block (k4s_bootstrap_loader_r1.py only)
  builder  -> build_shell_fragment.py (HEAD/TAIL of the shell fragment)
then regenerates k4s_bootstrap_shell_r1.sh from the mutated loader with the mutated builder (so the text-consistency
tests stay consistent and a mutant must be killed by BEHAVIOUR), copies the pinned safe_input r3 into the scratch
end-prep tree, and runs the whole tests/ suite with -x under the given interpreter and flags. KILLED = pytest exit 1
(a failing test); SURVIVED = exit 0; anything else (collection error, timeout) is INVALID, never counted as killed.
`expect` documents the intent: kill, equivalent (a later guard makes it unobservable; its JOINT mutant must be
killed) or null (no-op control that must survive).

    nice -n 19 taskset -c 0-7 python3 -B mutate_bootstrap.py --python PY [--optimize] --scratch /dev/shm/X --jobs N --json OUT
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("k4s_bootstrap_r1.py", "k4s_bootstrap_loader_r1.py", "build_shell_fragment.py", "k4s_bootstrap_shell_r1.sh")
SI = os.path.join(os.path.dirname(HERE), "safe-input-r3", "safe_input.py")

S = "snippet"
M = "main"
F = "builder"
MUTANTS = [
    # ---- 2. name gate
    ("N name gate off", "kill", [(S, "        if family is not None:\n            raise refused(\"outcome name family \"",
                                  "        if False:\n            raise refused(\"outcome name family \"")]),
    ("N no casefold", "kill", [(S, "    folded = component.casefold()\n", "    folded = component\n")]),
    ("N lower not casefold", "kill", [(S, "    folded = component.casefold()\n", "    folded = component.lower()\n")]),
    ("N games family dropped", "kill", [(S, "    (\"games\", r\"(?:.*[^a-z])?\" + r\"games\" + r\"(?:[^a-z].*)?\"),",
                                         "    (\"games\", r\"(?!)\"),")]),
    ("N end-raw family dropped", "kill", [(S, "    (\"end-raw-json\", r\".*end[-_.]?raw.*\\.json.*\"),\n", "")]),
    ("N match not fullmatch", "kill", [(S, "if re.fullmatch(rx, folded, re.S):", "if re.match(rx, folded, re.S):")]),
    ("N search not fullmatch", "kill", [(S, "if re.fullmatch(rx, folded, re.S):", "if re.search(rx, folded, re.S):")]),
    ("N no DOTALL", "kill", [(S, "if re.fullmatch(rx, folded, re.S):", "if re.fullmatch(rx, folded):")]),
    ("N leaf not gated", "kill", [(S, "    for p in parts:\n        family", "    for p in parts[:-1]:\n        family")]),
    ("N ancestors not gated", "kill", [(S, "    for p in parts:\n        family", "    for p in parts[-1:]:\n        family")]),
    # ---- 1. pins and path form
    ("P sha pin format off", "kill", [(S, "    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in \"0123456789abcdef\" for c in sha256):",
                                       "    if False:")]),
    ("P size pin off", "kill", [(S, "    if type(size) is not int or not 0 < size <= K4S_BOOTSTRAP_MAX_SIZE:",
                                 "    if False:")]),
    ("P size pin accepts bool", "kill", [(S, "    if type(size) is not int or not", "    if not isinstance(size, int) or not")]),
    ("P not-absolute off", "kill", [(S, "    if (not isinstance(path, str) or not path.startswith(\"/\") or path.startswith(\"//\")",
                                     "    if (not isinstance(path, str) or path.startswith(\"//\")")]),
    ("P double-slash-start off", "equivalent", [(S, " or path.startswith(\"//\") or path.endswith(\"/\")",
                                                 " or path.endswith(\"/\")")]),
    ("P trailing-slash off", "equivalent", [(S, " or path.endswith(\"/\")\n", "\n")]),
    ("P normpath off", "equivalent", [(S, "            or os.path.normpath(path) != path):", "            ):")]),
    ("P component check off", "kill", [(S, "    if any(p in (\"\", \".\", \"..\") for p in parts):", "    if False:")]),
    ("P JOINT normpath+component off", "kill", [(S, "            or os.path.normpath(path) != path):", "            ):"),
                                                (S, "    if any(p in (\"\", \".\", \"..\") for p in parts):", "    if False:")]),
    ("P JOINT slashes+component off", "kill", [(S, " or path.startswith(\"//\") or path.endswith(\"/\")\n", "\n"),
                                               (S, "    if any(p in (\"\", \".\", \"..\") for p in parts):", "    if False:")]),
    ("P control/backslash off", "kill", [(S, "    if \"\\\\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):",
                                          "    if False:")]),
    # ---- 3. walk
    ("W ancestor follows symlinks", "kill", [(S, "child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)",
                                              "child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=fd)")]),
    ("W ancestor without O_DIRECTORY", "kill", [(S, "child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)",
                                                 "child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)")]),
    ("W ancestor S_ISDIR off", "kill", [(S, "            if not stat.S_ISDIR(os.fstat(fd).st_mode):\n                raise refused(\"ancestor \"",
                                         "            if False:\n                raise refused(\"ancestor \"")]),
    ("W root S_ISDIR off", "kill", [(S, "        if not stat.S_ISDIR(os.fstat(fd).st_mode):\n            raise refused(\"/ is",
                                     "        if False:\n            raise refused(\"/ is")]),
    ("W full-path open (no walk)", "kill", [(S, "        for name in parts[:-1]:\n            try:",
                                             "        fd2 = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)\n"
                                             "        os.close(fd)\n        fd = fd2\n        for name in []:\n            try:")]),
    ("W walk not from /", "kill", [(S, "    fd = os.open(\"/\", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)",
                                    "    fd = os.open(\".\", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)")]),
    # ---- 4. leaf before any read
    ("L pre-open inspection off", "kill", [(S, "        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:",
                                            "        if False:")]),
    ("L pre-open nlink off", "kill", [(S, "        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:",
                                       "        if not stat.S_ISREG(before.st_mode) or before.st_size != size:")]),
    ("L pre-open size off", "kill", [(S, "        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:",
                                      "        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:")]),
    ("L pre-open stat follows", "kill", [(S, "before = os.stat(leaf, dir_fd=fd, follow_symlinks=False)",
                                          "before = os.stat(leaf, dir_fd=fd)")]),
    ("L leaf open follows", "kill", [(S, "leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK",
                                            "leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NONBLOCK")]),
    ("L JOINT pre-open off + leaf follows", "kill", [
        (S, "        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:", "        if False:"),
        (S, "leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK", "leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NONBLOCK")]),
    ("L leaf open not relative to parent", "kill", [(S, " | os.O_NOCTTY | os.O_CLOEXEC,\n                              dir_fd=fd)",
                                                     " | os.O_NOCTTY | os.O_CLOEXEC)")]),
    ("L post-open checks off", "kill", [(S, "            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size\n"
                                            "                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):",
                                         "            if False:")]),
    ("L post-open dev/ino off", "kill", [(S, "\n                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):", "):")]),
    ("L post-open nlink off", "kill", [(S, "if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size",
                                        "if (not stat.S_ISREG(info.st_mode) or info.st_size != size")]),
    ("L post-open size off", "kill", [(S, "if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size",
                                       "if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1")]),
    ("L post-open S_ISREG off", "kill", [(S, "if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size",
                                          "if (info.st_nlink != 1 or info.st_size != size")]),
    # ---- 5. read, hash, execute
    ("R shrink check breaks", "kill", [(S, "                    raise refused(\"leaf shrank while read\")", "                    break")]),
    ("R EOF probe off", "kill", [(S, "            if os.read(leaf_fd, 1) != b\"\":", "            if False:")]),
    ("R sha compare off", "kill", [(S, "    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:",
                                    "    if len(data) != size:")]),
    ("R length compare off", "equivalent", [(S, "    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:",
                                             "    if hashlib.sha256(data).hexdigest() != sha256:")]),
    ("X re-read by path before exec", "kill", [(S, "    code = compile(data, filename, \"exec\", dont_inherit=True)",
                                                "    code = compile(open(path, \"rb\").read(), filename, \"exec\", dont_inherit=True)")]),
    ("X filename is the path", "kill", [(S, "    filename = \"<k4s-bootstrap sha256=\" + sha256 + \" \" + path + \">\"",
                                         "    filename = path")]),
    ("X linecache not seeded", "kill", [(S, "    linecache.cache[filename] = (len(data), None, data.decode(\"utf-8\", \"replace\").splitlines(True), filename)\n", "")]),
    ("X sys.modules not restored", "kill", [(S, "        if previous is None:\n            sys.modules.pop(module_name, None)\n"
                                                "        else:\n            sys.modules[module_name] = previous\n", "")]),
    ("X registered after exec", "kill", [(S, "    sys.modules[module_name] = module\n    try:\n        exec(code, module.__dict__)\n",
                                          "    try:\n        exec(code, module.__dict__)\n        sys.modules[module_name] = module\n")]),
    ("X __file__ not set", "kill", [(S, "    module.__file__ = path\n", "")]),
    ("X tag not set", "kill", [(S, "    module.__k4s_bootstrap__ = (K4S_BOOTSTRAP_RELEASE, path, sha256, len(data))\n", "")]),
    ("D default path normalizes", "kill", [(S, "    directory = os.path.dirname(module_file)\n",
                                            "    directory = os.path.dirname(os.path.abspath(module_file))\n")]),
    ("D default path resolves", "kill", [(S, "    directory = os.path.dirname(module_file)\n",
                                          "    directory = os.path.dirname(os.path.realpath(module_file))\n")]),
    # ---- shell loader main
    ("S isolation check off", "kill", [(M, "    if not (sys.flags.isolated and sys.flags.no_site):", "    if False:")]),
    ("S usage check off", "kill", [(M, "    if (len(argv) < 4 or argv[3] not in (\"--\", \"--verify-only\")",
                                    "    if (len(argv) < 3")]),
    ("S verify-only extra args allowed", "kill", [(M, " or (argv[3] == \"--verify-only\" and len(argv) != 4)", "")]),
    ("S size regex off", "kill", [(M, "            or not re.fullmatch(r\"[1-9][0-9]{0,8}\", argv[2])):", "            or not argv[2].strip().isdigit()):")]),
    ("S verify-only executes", "kill", [(M, "    if argv[3] == \"--verify-only\":\n        return 0\n", "")]),
    ("S refusal status 1", "kill", [(M, "        return SystemExit(90)", "        return SystemExit(1)")]),
    ("S argv not set", "kill", [(M, "    sys.argv = [path] + list(argv[4:])\n", "")]),
    ("S not run as __main__", "kill", [(M, "    k4s_bootstrap_exec(data, path, sha256, \"__main__\")", "    k4s_bootstrap_exec(data, path, sha256, \"tool\")")]),
    ("S runs the path, not the bytes", "kill", [(M, "    k4s_bootstrap_exec(data, path, sha256, \"__main__\")",
                                                 "    import runpy\n    runpy.run_path(path, run_name=\"__main__\")")]),
    # ---- shell fragment
    ("F initial verify dropped", "kill", [(F, "k4s_verify_host_tool || exit 90\n", ":\n")]),
    ("F tool runs the path directly", "kill", [(F, "tool() { \"$python\" -I -S -c \"$k4s_loader\" \"$host_tool\" \"$host_tool_sha\" \"$host_tool_size\" -- \"$@\"; }",
                                                "tool() { \"$python\" -I -S \"$host_tool\" \"$@\"; }")]),
    ("F verify via sha256sum", "kill", [(F, "k4s_verify_host_tool || exit 90\n",
                                         "test -f \"$host_tool\" && printf \"%s  %s\\\\n\" \"$host_tool_sha\" \"$host_tool\" | sha256sum --check --status --strict || exit 90\n")]),
    # ---- controls
    ("NULL snippet comment", "null", [(S, "    \"\"\"The OUTCOME family label of one path component (casefolded fullmatch), or None.\"\"\"",
                                       "    \"\"\"The OUTCOME family label of one path component (casefolded fullmatch), or None. \"\"\"")]),
    ("NULL main comment", "null", [(M, "and creates no file. Refusal:", "and creates no file.  Refusal:")]),
]


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def apply(texts, edits):
    """snippet edits change the canonical text and therefore the loader prefix too; main edits change only the loader
    body after that prefix; builder edits change the fragment builder. Each `old` must occur exactly once."""
    snippet = texts["k4s_bootstrap_r1.py"]
    loader = texts["k4s_bootstrap_loader_r1.py"]
    if not loader.startswith(snippet):
        raise SystemExit("loader does not start with the snippet")
    parts = {"snippet": snippet, "main": loader[len(snippet):], "builder": texts["build_shell_fragment.py"]}
    for kind, old, new in edits:
        if parts[kind].count(old) != 1:
            raise SystemExit("%s edit not unique (%d): %r" % (kind, parts[kind].count(old), old))
        parts[kind] = parts[kind].replace(old, new)
    texts["k4s_bootstrap_r1.py"] = parts["snippet"]
    texts["k4s_bootstrap_loader_r1.py"] = parts["snippet"] + parts["main"]
    texts["build_shell_fragment.py"] = parts["builder"]
    return texts


def run_one(index, mutant, args):
    label, expect, edits = mutant
    root = os.path.join(args.scratch, "m%02d" % index)
    end_prep = os.path.join(root, "end-prep")
    pkg = os.path.join(end_prep, "bootstrap-r1")
    os.makedirs(os.path.join(end_prep, "safe-input-r3"))
    shutil.copyfile(SI, os.path.join(end_prep, "safe-input-r3", "safe_input.py"))
    shutil.copytree(os.path.join(HERE, "tests"), os.path.join(pkg, "tests"),
                    ignore=shutil.ignore_patterns("__pycache__", "mutate_*"))
    texts = {}
    for name in FILES:
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            texts[name] = handle.read()
    texts = apply(texts, [(k, o, n) for k, o, n in edits])
    for name in FILES[:3]:
        with open(os.path.join(pkg, name), "w", encoding="utf-8") as handle:
            handle.write(texts[name])
    regen = subprocess.run([sys.executable, "-I", "-B", os.path.join(pkg, "build_shell_fragment.py"),
                            os.path.join(pkg, "k4s_bootstrap_loader_r1.py")], capture_output=True, text=True)
    if regen.returncode != 0:
        return dict(label=label, expect=expect, status="INVALID", detail="fragment regeneration failed: " + regen.stderr[-500:])
    with open(os.path.join(pkg, "k4s_bootstrap_shell_r1.sh"), "w", encoding="utf-8") as handle:
        handle.write(regen.stdout)
    cmd = [args.python] + (["-O"] if args.optimize else []) + ["-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                                                              "--basetemp", os.path.join(root, "bt"), os.path.join(pkg, "tests")]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if args.pythonpath:
        env["PYTHONPATH"] = args.pythonpath
    start = time.time()
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, cwd=root, env=env)
        rc, tail = done.returncode, (done.stdout + done.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        rc, tail = "timeout", ""
    status = {1: "KILLED", 0: "SURVIVED"}.get(rc, "INVALID")
    failed = [line for line in tail.splitlines() if line.startswith("FAILED ")]
    shutil.rmtree(root, ignore_errors=True)
    return dict(label=label, expect=expect, status=status, rc=rc, seconds=round(time.time() - start, 1),
                killed_by=failed[:1], detail=tail if status == "INVALID" else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--pythonpath", default="")
    ap.add_argument("--optimize", action="store_true")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--json", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    os.makedirs(args.scratch)
    chosen = [(i, m) for i, m in enumerate(MUTANTS) if not args.only or args.only in m[0]]
    originals = {}
    for name in FILES:
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            originals[name] = handle.read()
    for _, (label, _, edits) in chosen:                       # every edit must apply exactly once before anything runs
        apply(dict(originals), edits)
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda im: run_one(im[0], im[1], args), chosen))
    ok = all((r["status"] == "KILLED") if r["expect"] == "kill" else (r["status"] == "SURVIVED") for r in results)
    summary = dict(tool="bootstrap-r1 mutate_bootstrap.py", python=args.python, optimize=args.optimize,
                   utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   sha256={n: sha(os.path.join(HERE, n)) for n in FILES},
                   tests_sha256={n: sha(os.path.join(HERE, "tests", n)) for n in sorted(os.listdir(os.path.join(HERE, "tests")))
                                 if n.endswith(".py")},
                   counts={k: sum(1 for r in results if r["status"] == k) for k in ("KILLED", "SURVIVED", "INVALID")},
                   expected_kill=sum(1 for r in results if r["expect"] == "kill"),
                   all_as_expected=ok, mutants=results)
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print(json.dumps(summary["counts"]), "all_as_expected=%s" % ok)
    for r in results:
        if (r["expect"] == "kill") != (r["status"] == "KILLED") or r["status"] == "INVALID":
            print("UNEXPECTED", r["label"], r["expect"], r["status"], r.get("detail", "")[-400:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
