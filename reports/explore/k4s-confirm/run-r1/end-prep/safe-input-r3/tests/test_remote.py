"""The shipped remote reader, run locally under /usr/bin/python3 (3.8 on the fleet) through a fake ssh shim, and the
strict local response parser. No real ssh is ever invoked."""
import ast
import binascii
import hashlib
import json
import os
import subprocess

import pytest

from conftest import (HOST, canary_unchanged, ident, make_canary, make_file, ok, policy, refusal, role, si)

PY = "/usr/bin/python3"
AUDIT_PRELUDE = r'''
import sys as _s, os as _o
def _hook(event, args):
    if event == "open" and isinstance(args[0], str):
        _o.write(2, ("AUDIT-OPEN " + args[0] + "\n").encode())
_s.addaudithook(_hook)
_real_read = _o.read
def _logged_read(fd, n):
    _o.write(2, b"READ-FD\n")
    return _real_read(fd, n)
_o.read = _logged_read
'''


@pytest.fixture
def shim(base):
    """Fake ssh: checks the hygiene options, drops them and the host, then runs the remote words locally."""
    path = os.path.join(base, "ssh")
    with open(path, "w") as stream:
        stream.write('#!/bin/sh\n'
                     'case "$*" in *"ControlMaster=no"*"ControlPath=none"*"StrictHostKeyChecking=yes"*) ;; '
                     '*) echo "bad ssh options" >&2; exit 99;; esac\n'
                     'while [ "$1" != "--" ]; do shift; done\nshift; shift\nexec "$@"\n')
    os.chmod(path, 0o755)
    return path


@pytest.fixture
def tree(base):
    root = os.path.join(base, "host")
    make_file(os.path.join(root, "job", "system-bus-admission.json"), b'{"pid": 1}\n')
    make_file(os.path.join(root, "job", "b.bin"), b"\x00\x01\x02")
    os.makedirs(os.path.join(root, "base"))
    return root


def rpol(root, host=HOST, **kw):
    args = dict(patterns=("**",), max_size=1 << 16)
    args.update(kw)
    return policy([role("h", root, **args)], host=host, remote=True)


def run_program(request, prelude=""):
    """Run the shipped program directly (stdin = source) with one hex request word."""
    src = (prelude + si.remote_program_source()).encode()
    proc = subprocess.run([PY, "-I", "-S", "-", binascii.hexlify(request).decode()], input=src,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def test_program_is_py38_stdlib_and_deterministic():
    src = si.remote_program_source()
    ast.parse(src, feature_version=(3, 8))
    ok(si.remote_program_sha256() == hashlib.sha256(src.encode()).hexdigest())
    ok(si._CORE in src)                                           # the same gate code as the local layer
    out = subprocess.run([PY, "-c", "import sys; print(sys.version_info[:2])"], stdout=subprocess.PIPE)
    ok(out.stdout.strip() == b"(3, 8)", "the fleet interpreter here is not 3.8: %r" % out.stdout)


def test_happy_path_through_fake_ssh(shim, tree):
    p = rpol(tree)
    got = si.remote_check(p, [{"role": "h", "rel": "job/system-bus-admission.json", "kind": "file", "content": True},
                              {"role": "h", "rel": "job/b.bin", "kind": "file", "expected_size": 3},
                              {"role": "h", "rel": "base", "kind": "dir"},
                              {"role": "h", "rel": None, "kind": "dir"},
                              {"role": "h", "rel": "base/attempt-01", "kind": "absent"}],
                          max_content=1024, ssh_binary=shim)
    ok(got[0]["content"] == b'{"pid": 1}\n' and got[0]["nlink"] == 1 and got[0]["size"] == 11)
    ok(got[1]["sha256"] == hashlib.sha256(b"\x00\x01\x02").hexdigest() and "content" not in got[1])
    ok(got[2]["ino"] == os.stat(os.path.join(tree, "base")).st_ino)
    ok(got[3]["ino"] == os.stat(tree).st_ino and got[4] == {"kind": "absent", "root": tree,
                                                            "rel": "base/attempt-01"})


def refused(shim, policy_, items, code, max_content=0):
    e = refusal("remote-refused", si.remote_check, policy_, items, max_content, shim)
    ok(e.reason.startswith(code + ":"), "expected remote code %s, got %s" % (code, e.reason))
    return e


def test_remote_hard_link_canary_never_opened(base, shim, tree):
    canary = make_canary(base)
    os.link(canary, os.path.join(tree, "job", "alias.json"))
    req = si.build_remote_request(rpol(tree), [{"role": "h", "rel": "job/alias.json", "kind": "file",
                                                "content": True}], 4096)
    rc, out, err = run_program(req, AUDIT_PRELUDE)
    ok(rc == 3 and json.loads(out)["code"] == "nlink", (rc, out, err))
    ok(b"alias.json" not in err, "the remote program opened the hard-linked alias: %r" % err)
    ok(canary_unchanged(canary))
    refused(shim, rpol(tree), [{"role": "h", "rel": "job/alias.json", "kind": "file"}], "nlink")


def test_remote_two_pass_gates_before_any_read(base, tree):
    """A refusal on the LAST item means no byte of the earlier (valid) items is read either."""
    canary = make_canary(base)
    os.link(canary, os.path.join(tree, "job", "zz.json"))
    req = si.build_remote_request(rpol(tree), [{"role": "h", "rel": "job/b.bin", "kind": "file", "content": True},
                                               {"role": "h", "rel": "job/zz.json", "kind": "file"}], 4096)
    rc, out, err = run_program(req, AUDIT_PRELUDE)
    body = json.loads(out)
    ok(rc == 3 and body["code"] == "nlink" and "items" not in body)
    ok(b"READ-FD" not in err, "bytes were read before every item passed its gate: %r" % err)
    rc, out, err = run_program(si.build_remote_request(rpol(tree), [{"role": "h", "rel": "job/b.bin",
                                                                      "kind": "file"}]), AUDIT_PRELUDE)
    ok(rc == 0 and b"READ-FD" in err)                            # the probe does see reads when they happen


@pytest.mark.parametrize("setup,rel,code", [
    ("leaf-symlink", "job/link.json", "symlink"),
    ("dir-symlink", "jl/system-bus-admission.json", "symlink"),
    ("fifo", "job/fifo", "not-regular"),
    ("dir", "job", "not-regular"),
    ("missing", "job/none.json", "missing"),
    ("big", "job/big.bin", "size"),
])
def test_remote_walk_refusals(base, shim, tree, setup, rel, code):
    job = os.path.join(tree, "job")
    if setup == "leaf-symlink":
        os.symlink(os.path.join(job, "b.bin"), os.path.join(job, "link.json"))
    elif setup == "dir-symlink":
        os.symlink(job, os.path.join(tree, "jl"))
    elif setup == "fifo":
        os.mkfifo(os.path.join(job, "fifo"))
    elif setup == "big":
        make_file(os.path.join(job, "big.bin"), b"x" * ((1 << 16) + 1))
    refused(shim, rpol(tree), [{"role": "h", "rel": rel, "kind": "file"}], code)


def test_remote_root_and_ancestor_symlink(base, shim, tree):
    os.symlink(tree, os.path.join(base, "hostlink"))
    refused(shim, rpol(os.path.join(base, "hostlink")), [{"role": "h", "rel": "job/b.bin", "kind": "file"}], "root")
    os.symlink(base, os.path.join(base, "anc"))
    refused(shim, rpol(os.path.join(base, "anc", "host")), [{"role": "h", "rel": "job/b.bin", "kind": "file"}],
            "root")
    os.symlink(os.path.join(base, "elsewhere"), os.path.join(tree, "base", "k4s-end-r1"))
    refused(shim, rpol(tree), [{"role": "h", "rel": "base/k4s-end-r1", "kind": "dir"}], "symlink")
    refused(shim, rpol(tree), [{"role": "h", "rel": "base/k4s-end-r1", "kind": "absent"}], "exists")


def test_remote_host_mismatch(shim, tree):
    other = "127x03" if HOST != "127x03" else "127x04"
    refused(shim, rpol(tree, host=other), [{"role": "h", "rel": "job/b.bin", "kind": "file"}], "host")


def raw_request(host, items, max_content=0):
    return json.dumps({"schema": si.REMOTE_REQUEST_SCHEMA, "host": host, "items": items,
                       "max_content": max_content}, sort_keys=True, separators=(",", ":")).encode()


def file_item(root, rel, **kw):
    item = {"kind": "file", "root": root, "rel": rel, "grants": [], "max_size": 1024, "expected_size": None,
            "content": False, "e4": False}
    item.update(kw)
    return item


@pytest.mark.parametrize("root,rel,host", [
    ("/x", "games/a.json", None), ("/x", "a/complete.json", None), ("/x/k4s-confirm-reporting-r1", "a", None),
    ("/x", "reports/explore/k4s-confirm/end/a.json", None), (si.T1_LAUNCH_NAMESPACES[0], "a.json", None),
    ("/mpac/sdicks02/jobs/clasher", "a.json", "127x04"), ("/mpac/sdicks02/repos/clasher-v4-cache", "a", None),
])
def test_remote_name_gates_apply_even_to_a_hand_built_request(root, rel, host):
    """build_remote_request refuses these locally; the remote program refuses them again, by name, before it even
    checks which host it runs on."""
    rc, out, _ = run_program(raw_request(host or HOST, [file_item(root, rel)]))
    body = json.loads(out)
    ok(rc == 3 and body["code"] == "name", (rc, out))


def test_local_request_builder_refuses_first(tree):
    p = rpol(tree)
    refusal("name", si.build_remote_request, p, [{"role": "h", "rel": "games/x", "kind": "file"}])
    refusal("allowlist", si.build_remote_request, rpol(tree, patterns=("job/*.json",)),
            [{"role": "h", "rel": "job/b.bin", "kind": "file"}])
    refusal("policy", si.build_remote_request, policy([role("h", tree, patterns=("**",))]),
            [{"role": "h", "rel": "job/b.bin", "kind": "file"}])     # a local policy cannot build remote requests
    refusal("policy", si.build_remote_request, p, [{"role": "h", "rel": "job/b.bin", "kind": "rm"}])
    refusal("exemption", si.build_remote_request, rpol(tree, exemptions=("E4",)),
            [{"role": "h", "rel": sorted(si.E4_COMPLETE_JSON)[0], "kind": "file", "e4": True, "content": True}])
    refusal("policy", si.build_remote_request, p, [])


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(schema="x"), lambda r: r.update(extra=1), lambda r: r.update(max_content=1 << 30),
    lambda r: r["items"][0].update(kind="exec"), lambda r: r["items"][0].update(content="yes"),
    lambda r: r["items"][0].update(grants=["root"]), lambda r: r["items"][0].update(max_size=0),
    lambda r: r["items"][0].update(e4=True), lambda r: r["items"][0].pop("e4"),
])
def test_remote_rejects_malformed_requests(tree, mutate):
    body = json.loads(raw_request(HOST, [file_item(tree, "job/b.bin")]))
    mutate(body)
    rc, out, _ = run_program(json.dumps(body).encode())
    ok(rc == 3 and json.loads(out)["code"] in ("request", "exemption"), (rc, out))
    rc, out, _ = run_program(b'{"a": 1, "a": 2}')
    ok(rc == 3 and json.loads(out)["code"] == "request")


def test_remote_refuses_duplicate_keys_in_an_otherwise_valid_request(tree):
    good = raw_request(HOST, [file_item(tree, "job/b.bin")])
    rc, out, _ = run_program(good)
    ok(rc == 0, out)
    rc, out, _ = run_program(b'{"host":"127x99",' + good[1:])
    ok(rc == 3 and json.loads(out)["code"] == "request", out)


# ---------------------------------------------------------------- strict local parser
@pytest.fixture
def exchange(tree):
    req = si.build_remote_request(rpol(tree), [{"role": "h", "rel": "job/b.bin", "kind": "file", "content": True}],
                                  64)
    rc, out, _ = run_program(req)
    ok(rc == 0)
    return req, json.loads(out)


def dump(body):
    return (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_parser_accepts_the_genuine_reply(exchange):
    req, body = exchange
    ok(si.parse_remote_response(req, 0, dump(body))[0]["content"] == b"\x00\x01\x02")


@pytest.mark.parametrize("rc,mutate,code", [
    (37, None, "remote"), (4, None, "remote"), (255, None, "remote"),
    (3, None, "remote"),                                          # rc 3 with an 'ok' body
    (0, lambda b: b.update(status="refused"), "remote"),
    (0, lambda b: b.update(extra=1), "remote"),
    (0, lambda b: b.update(request_sha256="0" * 64), "remote"),
    (0, lambda b: b.update(host="127x99"), "remote"),
    (0, lambda b: b.update(schema="v0"), "remote"),
    (0, lambda b: b["items"].append(dict(b["items"][0])), "remote"),
    (0, lambda b: b["items"][0].update(rel="job/other"), "remote"),
    (0, lambda b: b["items"][0].update(nlink=2), "nlink"),
    (0, lambda b: b["items"][0].update(mode=0o10644), "not-regular"),
    (0, lambda b: b["items"][0].update(size=1 << 17), "size"),
    (0, lambda b: b["items"][0].update(sha256="A" * 64), "remote"),
    (0, lambda b: b["items"][0].update(content_b64="AAEE"), "remote"),
    (0, lambda b: b["items"][0].update(content_b64=None), "remote"),
    (0, lambda b: b["items"][0].update(size=True), "remote"),
    (0, lambda b: b["items"][0].pop("dev"), "remote"),
])
def test_parser_refusals(exchange, rc, mutate, code):
    req, body = exchange
    body = json.loads(json.dumps(body))
    if mutate:
        mutate(body)
    refusal(code, si.parse_remote_response, req, rc, dump(body))


def test_parser_output_shape(exchange):
    req, body = exchange
    refusal("remote", si.parse_remote_response, req, 0, dump(body) + dump(body))   # two lines
    refusal("remote", si.parse_remote_response, req, 0, dump(body)[:-1])            # no newline
    refusal("json", si.parse_remote_response, req, 0, b'{"a":1,"a":1}\n')


def test_parser_unrequested_content(tree):
    req = si.build_remote_request(rpol(tree), [{"role": "h", "rel": "job/b.bin", "kind": "file"}])
    rc, out, _ = run_program(req)
    body = json.loads(out)
    body["items"][0]["content_b64"] = "AAEC"
    refusal("remote", si.parse_remote_response, req, 0, dump(body))


def test_parser_e4_pin(tree, base):
    path = sorted(si.E4_COMPLETE_JSON)[0]
    make_file(os.path.join(tree, path), b"synthetic")
    req = si.build_remote_request(rpol(tree, exemptions=("E4",)), [{"role": "h", "rel": path, "kind": "file",
                                                                    "e4": True}])
    rc, out, _ = run_program(req)
    ok(rc == 3 and json.loads(out)["code"] == "exemption")     # the program itself refuses the wrong pin
    body = {"schema": si.REMOTE_RESPONSE_SCHEMA, "status": "ok", "host": HOST,
            "request_sha256": hashlib.sha256(req).hexdigest(),
            "items": [{"kind": "file", "root": tree, "rel": path, "size": 9, "nlink": 1, "mode": 0o100644, "dev": 1,
                       "ino": 1, "sha256": hashlib.sha256(b"synthetic").hexdigest(), "content_b64": None}]}
    refusal("exemption", si.parse_remote_response, req, 0, dump(body))
