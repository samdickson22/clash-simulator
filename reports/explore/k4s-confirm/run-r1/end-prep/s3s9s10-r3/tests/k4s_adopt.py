#!/usr/bin/env python3
"""r3 END-FULL-F1 maintenance tool (stdlib only; never run by the production code).

1. --canonical FILE: paste the bootstrap-r1 canonical text VERBATIM (byte for byte, BEGIN line to END line) into every
   Part A module, replacing the previous block between the same markers (end_prep_common.py and the four entrypoints).
2. Always: recompute the sibling pins (SHA-256, size) in dependency order and rewrite each module's
   `K4S_SIBLING_PINS = {...}` block:  end_prep_common (pins safe_input itself: SAFE_INPUT_SHA256/SIZE, fixed)
   <- s9_end_runtime <- s1b_copy_admissions <- s3_guard_job <- s10_stage_host.
   (A pin covers a file's bytes, so a module's own pins must be final before its own digest is taken.)

    python3 -I -B tests/k4s_adopt.py --root DIR [--canonical FILE] [--check]

--check rewrites nothing and exits 1 if any block or pin would change. tests/mutate.py runs it on each mutant copy so
that a mutant is judged by the suite, not by the pin refusing to load it.
"""
import argparse
import hashlib
import os
import re
import sys

BEGIN = "# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 "
END = "# ==== END K4S CANONICAL BOOTSTRAP r1 ====\n"
COMMON = "end_prep_common.py"
ORDER = (("s9_end_runtime.py", (COMMON,)),
         ("s1b_copy_admissions.py", (COMMON, "s9_end_runtime.py")),
         ("s3_guard_job.py", (COMMON, "s1b_copy_admissions.py", "s9_end_runtime.py")),
         ("s10_stage_host.py", (COMMON, "s3_guard_job.py", "s9_end_runtime.py")))
MODULES = (COMMON,) + tuple(m for m, _ in ORDER)
PINS = re.compile(r"^K4S_SIBLING_PINS = \{\n(?:    .*\n)*?\}\n", re.M)


def read(path):
    with open(path, "rb") as stream:
        return stream.read().decode("utf-8")


def block_span(text, name):
    i = text.find(BEGIN)
    j = text.find(END)
    if i < 0 or j < i or text.count(BEGIN) != 1 or text.count(END) != 1 or (i and text[i - 1] != "\n"):
        raise SystemExit("%s: exactly one canonical block (BEGIN..END at line starts) is required" % name)
    return i, j + len(END)


def canonical_block(path):
    text = read(path)
    i, j = block_span(text, path)
    if (i, j) != (0, len(text)):
        raise SystemExit("the canonical file must be exactly one block, BEGIN line to END line")
    return text


def pins_text(pins):
    return "K4S_SIBLING_PINS = {\n" + "".join("    %r: (%r, %d),\n" % (k, v[0], v[1]) for k, v in pins) + "}\n"


def digest(text):
    data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest(), len(data)


def adopt(root, canonical=None):
    texts = {name: read(os.path.join(root, name)) for name in MODULES}
    if canonical is not None:
        for name in MODULES:
            i, j = block_span(texts[name], name)
            texts[name] = texts[name][:i] + canonical + texts[name][j:]
    done = {COMMON: digest(texts[COMMON])}
    for name, deps in ORDER:
        if len(PINS.findall(texts[name])) != 1:
            raise SystemExit("%s: exactly one K4S_SIBLING_PINS block is required" % name)
        texts[name] = PINS.sub(lambda m: pins_text([(d, done[d]) for d in deps]), texts[name], count=1)
        done[name] = digest(texts[name])
    return texts, done


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--canonical")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    canonical = canonical_block(a.canonical) if a.canonical else None
    texts, done = adopt(a.root, canonical)
    changed = [n for n in MODULES if texts[n] != read(os.path.join(a.root, n))]
    if a.check:
        print("changed: %r" % changed)
        return 1 if changed else 0
    for name in changed:
        path = os.path.join(a.root, name)
        mode = os.stat(path).st_mode & 0o7777
        with open(path, "wb") as stream:
            stream.write(texts[name].encode("utf-8"))
        os.chmod(path, mode)
    for name in MODULES:
        print("%s  %s  %d" % (done[name][0], name, done[name][1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
