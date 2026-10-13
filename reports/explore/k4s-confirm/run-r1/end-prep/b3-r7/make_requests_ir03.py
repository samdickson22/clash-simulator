#!/usr/bin/python3
"""b3-r7 (ruling IR-03, proposed): rewrite the three 127x03 S4 requests with guard.admissions = system bus only.

Offline, 127x05 only. For each of end-staging/requests/request-127x03-{pf00,rd00-a00,rd00-a01}.json:
- the source bytes must hash to the sha256 recorded in end-staging/requests/make_requests.out.json, and must be exactly
  json.dumps(request, indent=1, sort_keys=True) + "\\n" (the writer make_requests.py used);
- the only change is: delete guard.admissions["idle-services.json"]. Everything else (guard.job included) is kept;
- the new bytes use the same writer, are written O_CREAT|O_EXCL (never overwrite) with mode 0444 into OUT_DIR, and the
  parsed result is checked to differ from the source in exactly that one key.
The retired idle admission file itself is never opened: only the request's entry naming it is removed.
Writes OUT_DIR/make_requests_ir03.out.json (source and new sha256 per request, admissions {name: sha256}).

usage: make_requests_ir03.py OUT_DIR"""
import copy
import hashlib
import json
import os
import sys

STAGING = "/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests"
NAMES = ("request-127x03-pf00.json", "request-127x03-rd00-a00.json", "request-127x03-rd00-a01.json")
IDLE, BUS = "idle-services.json", "system-bus-admission.json"


def dumps(value):
    return (json.dumps(value, indent=1, sort_keys=True) + "\n").encode()


def write_excl(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def main(out_dir):
    meta = json.load(open(os.path.join(STAGING, "make_requests.out.json")))["requests"]
    record = {}
    for name in NAMES:
        src = os.path.join(STAGING, name)
        raw = open(src, "rb").read()
        src_sha = hashlib.sha256(raw).hexdigest()
        if src_sha != meta[src]["sha256"]:
            raise SystemExit("source sha differs from make_requests.out.json: " + name)
        request = json.loads(raw)
        if dumps(request) != raw:
            raise SystemExit("source is not the make_requests writer's bytes: " + name)
        if request["host"] != "127x03" or set(request["guard"]["admissions"]) != {BUS, IDLE}:
            raise SystemExit("unexpected source admissions: " + name)
        new = copy.deepcopy(request)
        del new["guard"]["admissions"][IDLE]
        expect = copy.deepcopy(new)
        expect["guard"]["admissions"][IDLE] = request["guard"]["admissions"][IDLE]
        if expect != request:
            raise SystemExit("more than the idle entry changed: " + name)
        dst = os.path.join(out_dir, name)
        new_sha = write_excl(dst, dumps(new))
        record[dst] = dict(source=src, source_sha256=src_sha, sha256=new_sha, host=new["host"], job=new["guard"]["job"],
                           admissions={n: e["sha256"] for n, e in sorted(new["guard"]["admissions"].items())},
                           removed={IDLE: request["guard"]["admissions"][IDLE]["sha256"]})
        print(name, new_sha)
    write_excl(os.path.join(out_dir, "make_requests_ir03.out.json"),
               dumps(dict(ruling="IR-03 (proposed): 127x03 has no idle resident for K4S END; guard.admissions = "
                                 + BUS + " only", writer="json.dumps(indent=1, sort_keys=True) + newline",
                          requests=record)))


if __name__ == "__main__":
    os.umask(0o022)
    main(sys.argv[1])
