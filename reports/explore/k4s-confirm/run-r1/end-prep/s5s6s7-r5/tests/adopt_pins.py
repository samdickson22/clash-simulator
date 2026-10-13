"""Dev tool (r5, finding 1): adopt the S9 code and the PRODUCTION runtime manifest into k4s_a6_builder.py from the
two markers, computing every value (nothing typed), and write the record ADOPTED-S9-RUNTIME.json that
tests/test_r5.py ties the builder constants to. Offline, 05 only; reads the markers, the S9 file, the sibling
SHA256SUMS and runtime-manifest.json (metadata) read-only; writes only k4s_a6_builder.py and the record in this
package. Refuses unless the S9-FINAL rows equal the bytes of the chain they list, RUNTIME-r5-READY names exactly the
production manifest (and, if listed, the same S9), the manifest bytes hash to it, and the manifest's script_sha256 is
the S9-FINAL S9. (The sibling SHA256SUMS is checked by tests/test_r5.py once that package is final.)

  python3 -I -B tests/adopt_pins.py            adopt (the record must be absent)
  python3 -I -B tests/adopt_pins.py --check    exit 1 unless builder constants == record == markers == bytes
"""
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNNER = "/mpac/sdicks02/k4s-runner/run-r1"
S9_PACKAGE = RUNNER + "/end-prep/s3s9s10-r5"
S9_FINAL = S9_PACKAGE + "/S9-FINAL"
RUNTIME_READY = RUNNER + "/end-staging/RUNTIME-r5-READY"
RUNTIME_EXPECTED = RUNNER + "/end-staging/runtime-98566c032d0b"
RECORD = os.path.join(ROOT, "ADOPTED-S9-RUNTIME.json")
RECORD_SCHEMA = "clasher.k4s.end-job-builder-adopted-pins.v1"
BUILDER = os.path.join(ROOT, "k4s_a6_builder.py")
HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def fail(message):
    raise SystemExit("ADOPT REFUSED: " + message)


def sha_file(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def marker_rows(path, width):
    """The marker's data rows (comment lines skipped), each exactly `width` whitespace-separated columns."""
    with open(path, "rb") as stream:
        raw = stream.read()
    rows = [line.split() for line in raw.decode("utf-8").splitlines() if line.strip() and not line.startswith("#")]
    if not rows or any(len(r) != width or not HEX.fullmatch(r[0]) for r in rows):
        fail("%s: rows must be %d columns starting with a SHA-256" % (path, width))
    return rows, hashlib.sha256(raw).hexdigest()


def adopted():
    for path in (S9_FINAL, RUNTIME_READY):
        if not os.path.isfile(path) or os.path.islink(path):
            fail("marker absent or not a regular file: " + path)
    rows, s9_marker_sha = marker_rows(S9_FINAL, 3)                 # sha256 size file (relative to the package)
    s9_rows = [r for r in rows if r[2] == "s9_end_runtime.py"]
    if len(s9_rows) != 1:
        fail("S9-FINAL must list s9_end_runtime.py exactly once")
    s9_sha, s9_size = s9_rows[0][0], int(s9_rows[0][1])
    s9_path = S9_PACKAGE + "/s9_end_runtime.py"
    for sha, size, name in rows:                                   # the whole loaded chain must be as marked
        if sha_file(S9_PACKAGE + "/" + name) != sha or os.path.getsize(S9_PACKAGE + "/" + name) != int(size):
            fail("S9-FINAL row differs from the bytes: " + name)
    rows, rt_marker_sha = marker_rows(RUNTIME_READY, 2)            # sha256 absolute-path
    named = dict((r[1], r[0]) for r in rows)
    manifest_path = RUNTIME_EXPECTED + "/runtime-manifest.json"
    if len(named) != len(rows) or manifest_path not in named:
        fail("RUNTIME-r5-READY must name %s exactly once" % manifest_path)
    if set(named) - {manifest_path, s9_path} or named.get(s9_path, s9_sha) != s9_sha:
        fail("RUNTIME-r5-READY names another runtime or another S9: %r" % sorted(named))
    manifest_sha = named[manifest_path]
    with open(manifest_path, "rb") as stream:
        raw = stream.read()
    if hashlib.sha256(raw).hexdigest() != manifest_sha:
        fail("runtime-manifest.json differs from RUNTIME-r5-READY")
    manifest = json.loads(raw)
    if manifest.get("script_sha256") != s9_sha:
        fail("the production runtime was not built by the S9-FINAL S9 (script_sha256)")
    return dict(schema=RECORD_SCHEMA,
                s9=dict(path=s9_path, sha256=s9_sha, size=s9_size),
                s9_final_marker=dict(path=S9_FINAL, sha256=s9_marker_sha),
                runtime=dict(path=RUNTIME_EXPECTED, manifest_sha256=manifest_sha,
                             manifest_script_sha256=manifest["script_sha256"], manifest_commit=manifest.get("commit"),
                             manifest_python=manifest.get("python"),
                             manifest_git_members_sha256=manifest.get("git_members_sha256"),
                             manifest_runtime_files_sha256=manifest.get("runtime_files_sha256"),
                             manifest_measurement_files_sha256=manifest.get("measurement_files_sha256")),
                runtime_ready_marker=dict(path=RUNTIME_READY, sha256=rt_marker_sha))


CONSTANTS = (("S9_PATH", lambda r: 'RUNNER + "/end-prep/' + os.path.relpath(r["s9"]["path"], RUNNER + "/end-prep") + '"'),
             ("S9_SHA256", lambda r: '"%s"' % r["s9"]["sha256"]),
             ("FROZEN_RUNTIME", lambda r: 'RUNNER + "/' + os.path.relpath(r["runtime"]["path"], RUNNER) + '"'),
             ("FROZEN_RUNTIME_MANIFEST_SHA256", lambda r: '"%s"' % r["runtime"]["manifest_sha256"]))


def main():
    check = "--check" in sys.argv
    record = adopted()
    text = open(BUILDER).read()
    new = text
    for name, value in CONSTANTS:
        new, count = re.subn(r"(?m)^(%s = )[^\n#]*?(\s*(#[^\n]*)?)$" % name,
                             lambda m: m.group(1) + value(record) + m.group(2), new)
        if count != 1:
            fail("%s assigned %d times in the builder" % (name, count))
    if check:
        stored = json.load(open(RECORD))
        stored.pop("adopted_utc", None)
        good = new == text and stored == record
        print("adopted pins current" if good else "STALE: builder constants / record differ from the markers")
        return 0 if good else 1
    if os.path.exists(RECORD):
        fail("record exists: " + RECORD)
    with open(BUILDER, "w") as stream:
        stream.write(new)
    record["adopted_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fd = os.open(RECORD, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w") as stream:
        stream.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps(record, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
