"""Ruling D4: the shipped receive mode (replaces S10's on-host `tar -x`). The receiver runs locally under
/usr/bin/python3 (3.8, the fleet interpreter) either directly or through a fake ssh shim that re-parses the remote
words with /bin/sh exactly as the remote login shell would. No real ssh is ever invoked; every destination is under
pytest's tmp_path."""
import ast
import hashlib
import json
import os
import re
import subprocess

import pytest

from conftest import (HOST, canary_unchanged, ident, make_canary, make_file, ok, policy, refusal, role, si)

PY = "/usr/bin/python3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def shim(base):
    log = os.path.join(base, "ssh.log")
    path = os.path.join(base, "ssh")
    with open(path, "w") as stream:
        stream.write('#!/bin/sh\n'
                     'case "$*" in *"ControlMaster=no"*"ControlPath=none"*"StrictHostKeyChecking=yes"*) ;; '
                     '*) echo "bad ssh options" >&2; exit 99;; esac\n'
                     'echo "$*" >> %s\n'
                     'while [ "$1" != "--" ]; do shift; done\nshift; shift\nexec /bin/sh -c "$*"\n' % log)
    os.chmod(path, 0o755)
    return path, log


@pytest.fixture
def src(base):
    root = os.path.join(base, "src")
    files = {"a.py": b"print('a')\n", "pkg/b.py": b"B = 2\n", "pkg/deep/c.bin": bytes(range(256)) * 9,
             "bin/run.sh": b"#!/bin/sh\necho run\n", "empty.txt": b""}
    for rel, data in files.items():
        make_file(os.path.join(root, rel), data)
    return root, files


def spec(files, modes=None):
    modes = modes or {}
    return [{"src_role": "src", "src_rel": rel, "dst": rel, "size": len(data), "sha256": sha(data),
             "mode": modes.get(rel, 0o444)} for rel, data in sorted(files.items())]


def policies(base, srcroot, dest_name="runtime-abc.partial", **dest_kw):
    host_root = os.path.join(base, "host")
    os.makedirs(host_root, exist_ok=True)
    args = dict(patterns=("**",))
    args.update(dest_kw)
    remote = policy([role("dest", os.path.join(host_root, dest_name), access="write", **args)], remote=True)
    local = policy([role("src", srcroot, patterns=("**",), exemptions=("E4",))])
    return remote, local, os.path.join(host_root, dest_name)


DIRS = ["bin", "pkg", "pkg/deep"]


def test_receive_happy_path_through_fake_ssh(base, src, shim):
    root, files = src
    remote, local, dest = policies(base, root)
    receipt = si.remote_receive(remote, "dest", local, spec(files, {"bin/run.sh": 0o555}), DIRS, ssh_binary=shim[0])
    ok([f["rel"] for f in receipt["files"]] == sorted(files))
    for rel, data in files.items():
        path = os.path.join(dest, rel)
        st = os.lstat(path)
        with open(path, "rb") as stream:
            ok(stream.read() == data, rel)
        ok(st.st_nlink == 1 and oct(st.st_mode & 0o777) == oct(0o555 if rel == "bin/run.sh" else 0o444), rel)
    ok(sorted(os.listdir(dest)) == ["a.py", "bin", "empty.txt", "pkg"])
    with open(shim[1]) as stream:
        words = stream.read().split()
    ok("-c" in words and words[-3] == str(len(si.receive_program_source().encode())))
    ok(words[-2] == si.receive_program_sha256())


def test_receive_e4_carried_with_pin(base, src, shim, monkeypatch):
    root, files = src
    e4 = sorted(si.E4_COMPLETE_JSON)[0]
    data = b"stand-in E4 receipt\n"
    make_file(os.path.join(root, e4), data)
    real_pin = si.E4_COMPLETE_JSON[e4]
    monkeypatch.setitem(si.E4_COMPLETE_JSON, e4, sha(data))
    shipped = si.receive_program_source().replace(real_pin, sha(data))   # the host program carries its own pins
    ok(shipped.count(sha(data)) == 1)
    monkeypatch.setattr(si, "receive_program_source", lambda: shipped)
    dirs = [e4.split("/")[0]] + ["/".join(e4.split("/")[:i]) for i in range(2, e4.count("/") + 1)]
    remote, local, dest = policies(base, root, exemptions=("E4",))
    item = {"src_role": "src", "src_rel": e4, "dst": e4, "size": len(data), "sha256": sha(data), "e4": True}
    si.remote_receive(remote, "dest", local, [item], dirs, ssh_binary=shim[0])
    with open(os.path.join(dest, e4), "rb") as stream:
        ok(stream.read() == data)
    remote2, _, dest2 = policies(base, root, dest_name="runtime-def.partial", exemptions=("E4",))
    bad = dict(item, sha256="0" * 64)
    refusal("exemption", si.remote_receive, remote2, "dest", local, [bad], dirs, ssh_binary=shim[0])
    monkeypatch.undo()                                               # real pins: the receiver itself refuses E4
    with open(os.path.join(root, e4), "rb") as stream:
        ok(stream.read() == data)
    req = json.loads(manifest(dest2, [(e4, data)], dirs))
    req["files"][0]["e4"] = True
    man = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
    reply = refused_directly(man, data, "exemption")
    ok(reply["created"] == [] and not os.path.exists(dest2))
    refusal("name", si.remote_receive, remote2, "dest", local, [dict(item, e4=False)], dirs, ssh_binary=shim[0])


def test_existing_destination_is_never_touched(base, src, shim):
    root, files = src
    remote, local, dest = policies(base, root)
    make_file(os.path.join(dest, "keep.txt"), b"keep me\n")
    e = refusal("remote-refused", si.remote_receive, remote, "dest", local, spec(files), DIRS, ssh_binary=shim[0])
    ok(e.reason.startswith("exists:") and "created, kept: []" in e.reason, e.reason)
    ok(os.listdir(dest) == ["keep.txt"])
    os.rename(dest, dest + "-moved")
    os.symlink(dest + "-moved", dest)                                # a pre-existing symlink at the root name
    e = refusal("remote-refused", si.remote_receive, remote, "dest", local, spec(files), DIRS, ssh_binary=shim[0])
    ok(e.reason.startswith("exists:") and os.listdir(dest + "-moved") == ["keep.txt"])


def test_symlinked_destination_parent_refuses(base, src, shim):
    root, files = src
    real = os.path.join(base, "elsewhere")
    os.makedirs(real)
    os.symlink(real, os.path.join(base, "host"))
    remote = policy([role("dest", os.path.join(base, "host", "runtime-x.partial"), access="write",
                          patterns=("**",))], remote=True)
    local = policy([role("src", root, patterns=("**",))])
    e = refusal("remote-refused", si.remote_receive, remote, "dest", local, spec(files), DIRS, ssh_binary=shim[0])
    ok(e.reason.startswith("root:") and os.listdir(real) == [], e.reason)


@pytest.mark.parametrize("dst,code", [("games/x.py", "name"), ("pkg/END-FINAL.json", "name"),
                                      ("x-complete.json", "name"), ("hub-blocks.tmp", "name"),
                                      ("../x.py", "path"), ("/abs.py", "path"), ("a//b.py", "path")])
def test_forbidden_destination_names_refuse_locally_before_ssh(base, src, shim, dst, code):
    root, files = src
    remote, local, dest = policies(base, root)
    items = spec(files)
    items[0] = dict(items[0], dst=dst)
    dirs = DIRS + (["games"] if dst.startswith("games/") else [])
    refusal(code, si.remote_receive, remote, "dest", local, items, dirs, ssh_binary=shim[0])
    ok(not os.path.exists(shim[1]), "ssh was started for a forbidden name")
    ok(not os.path.exists(dest))


def test_local_source_gates(base, src, shim):
    root, files = src
    canary = make_canary(base)
    os.link(canary, os.path.join(root, "linked.json"))
    remote, local, dest = policies(base, root)
    item = {"src_role": "src", "src_rel": "linked.json", "dst": "linked.json", "size": 42, "sha256": "0" * 64}
    refusal("nlink", si.remote_receive, remote, "dest", local, [item], [], ssh_binary=shim[0])
    ok(canary_unchanged(canary) and not os.path.exists(shim[1]), "ssh started before the source descriptor gate")
    refusal("name", si.remote_receive, remote, "dest", local,
            [dict(item, src_rel="games/x.json")], [], ssh_binary=shim[0])
    ok(not os.path.exists(shim[1]), "ssh started before the local source names were gated")
    refusal("name", si.remote_receive, remote, "dest", local, [], ["Games"], ssh_binary=shim[0])
    ok(not os.path.exists(shim[1]))
    refusal("policy", si.remote_receive, remote, "dest", local, [dict(item, sha256=None)], [], ssh_binary=shim[0])
    refusal("policy", si.remote_receive, remote, "dest", remote, [item], [], ssh_binary=shim[0])


def test_sha_and_size_mismatch_keep_partials(base, src, shim):
    root, files = src
    remote, local, dest = policies(base, root)
    items = spec(files)
    wrong = [i for i in items if i["dst"] == "pkg/b.py"][0]
    wrong["sha256"] = "0" * 64
    refusal("sha", si.remote_receive, remote, "dest", local, items, DIRS, ssh_binary=shim[0])
    ok(os.path.exists(os.path.join(dest, "pkg", "b.py")), "the partial must be kept, never deleted")
    remote2, _, dest2 = policies(base, root, dest_name="runtime-2.partial")
    items = spec(files)
    items[0]["size"] += 1
    os.unlink(shim[1])
    refusal("size", si.remote_receive, remote2, "dest", local, items, DIRS, ssh_binary=shim[0])
    ok(not os.path.exists(dest2) and not os.path.exists(shim[1]))       # refused before ssh: nothing created


# ---------------------------------------------------------------- the program itself, run directly
def manifest(dest, files, dirs=(), host=HOST, **extra):
    req = {"schema": si.RECEIVE_REQUEST_SCHEMA, "host": host, "root": dest, "grants": [], "dirs": list(dirs),
           "files": [{"rel": rel, "size": len(data), "sha256": sha(data), "mode": 0o444, "e4": False,
                      "e5": False} for rel, data in files], "max_total": sum(len(d) for _, d in files)}
    req.update(extra)
    return json.dumps(req, sort_keys=True, separators=(",", ":")).encode()


def run_receiver(man, body, program=None, program_sha=None, manifest_sha=None, length=None, extra_argv=()):
    program = program if program is not None else si.receive_program_source().encode()
    stream = program + (len(man) if length is None else length).to_bytes(8, "big") + man + body
    argv = [PY, "-I", "-S", "-c", si.RECEIVE_BOOTSTRAP, str(len(program)), program_sha or sha(program),
            manifest_sha or sha(man)] + list(extra_argv)
    proc = subprocess.run(argv, input=stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def refused_directly(man, body, code, **kw):
    rc, out, err = run_receiver(man, body, **kw)
    ok(rc == 3, (rc, out, err))
    reply = json.loads(out)
    ok(reply["code"] == code, reply)
    return reply


def test_direct_happy_path_and_parser(base):
    dest = os.path.join(base, "d")
    man = manifest(dest, [("x/a.txt", b"aaa"), ("b.txt", b"")], dirs=["x"])
    rc, out, err = run_receiver(man, b"aaa")
    ok(rc == 0, (rc, out, err))
    reply = si.parse_receive_receipt(man, rc, out)
    ok([f["rel"] for f in reply["files"]] == ["x/a.txt", "b.txt"])
    body = json.loads(out)
    for mutate in (lambda r: r["files"][0].update(nlink=2), lambda r: r["files"][0].update(sha256="0" * 64),
                   lambda r: r["files"][0].update(mode=0o100644), lambda r: r.update(root="/elsewhere"),
                   lambda r: r.update(extra=1), lambda r: r["files"].pop(), lambda r: r.update(dirs=[]),
                   lambda r: r.update(manifest_sha256="0" * 64), lambda r: r.update(host="127x01")):
        tampered = json.loads(out)
        mutate(tampered)
        line = (json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n").encode()
        e = refusal(e_code(tampered, body), si.parse_receive_receipt, man, 0, line)
        ok(e is not None)
    refusal("remote", si.parse_receive_receipt, man, 4, out)
    refusal("remote", si.parse_receive_receipt, man, 3, out)                 # rc 3 must carry a refusal body
    refusal("remote", si.parse_receive_receipt, man, 0, out + out)


def e_code(tampered, body):
    if tampered.get("files") and tampered["files"][0].get("nlink") == 2:
        return "nlink"
    if tampered.get("files") and tampered["files"][0].get("mode") == 0o100644:
        return "not-regular"
    return "remote"


@pytest.mark.parametrize("label", ["dotdot", "absolute", "duplicate", "casefold-duplicate", "outside-dirs",
                                   "dir-before-parent", "bad-mode", "e4-wrong", "games", "end-claim",
                                   "extra-key", "over-total", "wrong-host", "extra-request-key",
                                   "forbidden-dir-only"])
def test_direct_manifest_refusals_create_nothing(base, label):
    dest = os.path.join(base, "d")
    files, dirs, extra = [("a.txt", b"a")], [], {}
    if label == "dotdot":
        files = [("../a.txt", b"a")]
    elif label == "absolute":
        files = [("/a.txt", b"a")]
    elif label == "duplicate":
        files = [("a.txt", b"a"), ("a.txt", b"a")]
    elif label == "casefold-duplicate":
        files = [("a.txt", b"a"), ("A.TXT", b"a")]
    elif label == "outside-dirs":
        files = [("x/a.txt", b"a")]
    elif label == "dir-before-parent":
        dirs = ["x/y", "x"]
    elif label == "games":
        files, dirs = [("Games/a.txt", b"a")], ["Games"]
    elif label == "end-claim":
        files = [("attempt-00.json", b"a")]
    elif label == "forbidden-dir-only":
        dirs = ["x", "x/Games"]
    elif label == "wrong-host":
        extra = {"host": "127x01" if HOST != "127x01" else "127x02"}
    man = manifest(dest, files, dirs, **extra)
    if label in ("bad-mode", "e4-wrong", "extra-key", "over-total", "extra-request-key"):
        req = json.loads(man)
        if label == "bad-mode":
            req["files"][0]["mode"] = 0o4755
        elif label == "e4-wrong":
            req["files"][0]["e4"] = True
        elif label == "extra-key":
            req["files"][0]["link"] = "x"
        elif label == "extra-request-key":
            req["symlinks"] = []
        else:
            req["max_total"] = 0
        man = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
    code = {"dotdot": "path", "absolute": "path", "games": "name", "end-claim": "name", "e4-wrong": "exemption",
            "forbidden-dir-only": "name",
            "over-total": "size", "wrong-host": "host"}.get(label, "request")
    reply = refused_directly(man, b"a", code)
    ok(reply["created"] == [] and not os.path.exists(dest), reply)


def test_direct_stream_refusals(base):
    dest = os.path.join(base, "short")
    reply = refused_directly(manifest(dest, [("a.txt", b"aaaa")]), b"aa", "stream")
    ok(reply["created"] == ["", "a.txt"] and os.path.getsize(os.path.join(dest, "a.txt")) == 2)   # partial kept
    dest = os.path.join(base, "extra")
    reply = refused_directly(manifest(dest, [("a.txt", b"aa")]), b"aaXX", "stream")
    ok("extra bytes" in reply["reason"])
    dest = os.path.join(base, "badsha")
    man = manifest(dest, [("a.txt", b"aa")])
    refused_directly(man, b"aa", "request", manifest_sha="1" * 64)
    ok(not os.path.exists(dest))
    reply = refused_directly(man, b"ab", "sha")
    ok(reply["created"] == ["", "a.txt"])
    rc, out, err = run_receiver(manifest(os.path.join(base, "p"), [("a.txt", b"a")]), b"a", program_sha="2" * 64)
    ok(rc == 4 and out == b"" and not os.path.exists(os.path.join(base, "p")), (rc, out, err))   # bootstrap refusal
    rc, out, err = run_receiver(manifest(os.path.join(base, "q"), [("a.txt", b"a")]), b"a", length=1 << 40)
    ok(rc == 3 and json.loads(out)["code"] == "request")
    refused_directly(manifest(os.path.join(base, "r"), [("a.txt", b"a")]), b"a", "request", manifest_sha="zz")
    ok(not os.path.exists(os.path.join(base, "r")))
    refused_directly(manifest(os.path.join(base, "s"), [("a.txt", b"a")]), b"a", "request", extra_argv=["x"])
    ok(not os.path.exists(os.path.join(base, "s")))


def test_direct_pre_existing_symlink_inside_parent_chain(base):
    real = os.path.join(base, "real")
    os.makedirs(real)
    os.symlink(real, os.path.join(base, "lnk"))
    dest = os.path.join(base, "lnk", "d")
    reply = refused_directly(manifest(dest, [("a.txt", b"a")]), b"a", "root")
    ok(os.listdir(real) == [] and reply["created"] == [])


def test_program_shape():
    src = si.receive_program_source()
    ast.parse(src, feature_version=(3, 8))
    ok(si._CORE in src and si.receive_program_sha256() == sha(src.encode()))
    ok("'" not in si.RECEIVE_BOOTSTRAP)
    argv = si.receive_ssh_argv("127x03", b"p", b"m")
    words = argv[argv.index("--") + 1:]
    odd = [w for w in words if re.fullmatch(r"[A-Za-z0-9/-]+", w) is None]
    ok(odd == ["'" + si.RECEIVE_BOOTSTRAP + "'"], odd)
    refusal("policy", si.receive_ssh_argv, "laptop", b"p", b"m")
    rc = subprocess.run([PY, "-I", "-S", os.path.join(os.path.dirname(os.path.abspath(si.__file__)), "safe_input.py"),
                         "receive-program-sha256"], stdout=subprocess.PIPE)
    ok(rc.returncode == 0 and rc.stdout.decode().strip() == si.receive_program_sha256())


def test_local_manifest_builder_rules(base):
    remote = policy([role("dest", os.path.join(base, "d"), access="write", patterns=("**",))], remote=True)
    item = {"dst": "a.txt", "size": 1, "sha256": "0" * 64}
    refusal("request", si.build_receive_manifest, remote, "dest", [], [item, item], 2)
    refusal("request", si.build_receive_manifest, remote, "dest", [], [dict(item, dst="x/a.txt")], 1)
    refusal("request", si.build_receive_manifest, remote, "dest", [], [dict(item, mode=0o777)], 1)
    refusal("size", si.build_receive_manifest, remote, "dest", [], [item], 0)
    local = policy([role("dest", os.path.join(base, "d"), access="write", patterns=("**",))])
    refusal("policy", si.build_receive_manifest, local, "dest", [], [item], 1)
    read_role = policy([role("dest", os.path.join(base, "d"), patterns=("**",))], remote=True)
    refusal("policy", si.build_receive_manifest, read_role, "dest", [], [item], 1)
    ok(json.loads(si.build_receive_manifest(remote, "dest", [], [item], 1))["files"][0]["e4"] is False)


def test_input_chunks_single_use(base):
    root = os.path.join(base, "c")
    make_file(os.path.join(root, "a.bin"), b"abc")
    p = policy([role("c", root, exact=("a.bin",))])
    item = si.open_input(p, "c", "a.bin")
    ok(b"".join(item.chunks()) == b"abc")
    refusal("state", lambda: list(item.chunks()))
