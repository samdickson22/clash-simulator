"""end_prep_common: the pinned safe_input load, output confinement, no-clobber publication, the scrubbed frozen
environment, records; plus static adoption checks over the five production files."""
import ast
import hashlib
import os
import shutil
import subprocess
import sys

import pytest

from conftest import C, ROOT, make_file, ok, read, refused, sha, si

PRODUCTION = ("end_prep_common.py", "s1b_copy_admissions.py", "s3_guard_job.py", "s9_end_runtime.py",
              "s10_stage_host.py", "s11_host_repository.py")


def test_pinned_safe_input_identity(monkeypatch):
    from conftest import ORIG
    for (module_name, name), value in ORIG.items():          # the production constants (the session patches E5)
        if module_name == "safe_input":
            monkeypatch.setattr(si, name, value)
    ok(sha(read(os.path.join(ROOT, "safe_input.py"))) == C.SAFE_INPUT_SHA256)
    ok(C.SAFE_INPUT_RELEASE == "safe-input-r3")
    ok(si.constants_fingerprint() == C.SAFE_INPUT_FINGERPRINT)
    ok(si.remote_program_sha256() == C.REMOTE_PROGRAM_SHA256)
    ok(si.receive_program_sha256() == C.RECEIVE_PROGRAM_SHA256)
    ok(si.__k4s_bootstrap__ == (C.K4S_BOOTSTRAP_RELEASE, C.SAFE_INPUT_PATH, C.SAFE_INPUT_SHA256, C.SAFE_INPUT_SIZE)
       and sys.modules["safe_input"] is si and os.path.getsize(os.path.join(ROOT, "safe_input.py")) == C.SAFE_INPUT_SIZE)


def copy_code(tmpdir_):
    code = os.path.join(tmpdir_, "code")
    os.makedirs(code)
    for name in PRODUCTION + ("safe_input.py",):
        shutil.copyfile(os.path.join(ROOT, name), os.path.join(code, name))
    return code


def import_in(code):
    return subprocess.run([sys.executable, "-I", "-B", "-c", "import sys; sys.path.insert(0, %r); "
                           "import end_prep_common; print('LOADED')" % code],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/tmp")


@pytest.mark.parametrize("same_size", [True, False])
def test_tampered_safe_input_never_executes(tmpdir_, same_size):
    """Same-size changed bytes: read once, refused by the SHA-256 pin. Any other size: refused before any read
    (END-FULL-F1: the size pin is checked on the inspected leaf). Never executed either way."""
    code = copy_code(tmpdir_)
    ok(b"LOADED" in import_in(code).stdout)
    marker = os.path.join(tmpdir_, "EXECUTED")
    path = os.path.join(code, "safe_input.py")
    data = read(path)
    inject = b"open(%r, 'w').write('x')\n" % marker
    tampered = data.replace(b"import binascii\n", b"import binascii\n" + inject, 1)
    if same_size:                                    # drop as many bytes of a comment line as were injected
        dashes = b"-" * 110                          # a comment divider line; shortened by exactly len(inject)
        ok(dashes in tampered and len(inject) < 110)
        tampered = tampered.replace(dashes, dashes[len(inject):], 1)
    ok(tampered != data and (len(tampered) == len(data)) == same_size)
    os.chmod(path, 0o644)
    make_file(path, tampered)
    result = import_in(code)
    want = b"not the pinned SHA-256" if same_size else b"single-link regular file of the pinned size"
    ok(result.returncode != 0 and want in result.stderr and not os.path.exists(marker), result.stderr[-400:])


@pytest.mark.parametrize("alias", ["hardlink", "symlink"])
def test_aliased_safe_input_refused(tmpdir_, alias):
    code = copy_code(tmpdir_)
    path = os.path.join(code, "safe_input.py")
    if alias == "hardlink":
        os.link(path, os.path.join(tmpdir_, "extra-link"))
    else:
        os.rename(path, os.path.join(tmpdir_, "real.py"))
        os.symlink(os.path.join(tmpdir_, "real.py"), path)
    result = import_in(code)
    ok(result.returncode != 0 and b"LOADED" not in result.stdout, result.stderr)


def test_no_assert_and_no_raw_io_in_production():
    """Every gate is an explicit raise; production code never calls raw open/subprocess/os.walk/os.listdir/Path/
    shutil.copy* (only safe_input does), except the documented spots in end_prep_common (the safe_input load,
    publish_dir/unlink_own/chmod_readonly on gated fds) and S3's rmtree of its own throw-away tempdir."""
    allowed = {"end_prep_common.py": {"os.close", "os.stat", "os.fsync", "os.unlink", "os.fchmod", "os.rmdir",
                                      "tempfile.mkdtemp", "ctypes.CDLL", "ctypes.get_errno", "os.uname"},
               "s3_guard_job.py": {"shutil.rmtree", "tempfile.mkdtemp"},
               # r4: S11 empties and removes its OWN private /tmp bundle directory (mkdtemp) after the run
               "s11_host_repository.py": {"tempfile.mkdtemp", "os.listdir", "os.unlink", "os.rmdir"}}
    forbidden_names = {"open", "exec", "eval", "compile", "__import__"}
    forbidden_attrs = {"subprocess", "shutil", "os", "tempfile", "pathlib", "Path", "ctypes", "tarfile"}
    import k4s_adopt
    for name in PRODUCTION:
        text = read(os.path.join(ROOT, name)).decode()
        i, j = k4s_adopt.block_span(text, name)          # the canonical block is checked byte-equal in test_f1.py
        tree = ast.parse(text[:i] + text[j:])
        ok(not [n for n in ast.walk(tree) if isinstance(n, ast.Assert)], name + " uses assert")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_names:
                ok(False, "%s calls %s outside the canonical block" % (name, func.id))
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in forbidden_attrs:
                call = "%s.%s" % (func.value.id, func.attr)
                benign = call in ("os.path.dirname", "os.path.abspath", "os.path.join", "os.path.split",
                                  "os.path.normpath", "os.path.basename", "os.strerror")
                ok(benign or call in allowed.get(name, set()), "%s calls %s" % (name, call))


@pytest.mark.parametrize("path,code", [("relative/out", "path"), ("/mpac/sdicks02/k4s-runner/a/../b", "path"),
                                       ("/dev/shm/out", "path"), ("/mpac/sdicks02/repos/out", "path"),
                                       ("/tmp/x/out.partial", "path"), ("/tmp/x/-bad", "path"), ("/tmp/", "path")])
def test_output_path_confinement(path, code):
    refused(code, C.output_path, path, "--out")


def test_output_path_ok():
    ok(C.output_path("/mpac/sdicks02/k4s-runner/run-r1/end-staging/rt", "--out") ==
       ("/mpac/sdicks02/k4s-runner/run-r1/end-staging", "rt"))


def pub_policy(parent):
    return si.Policy(C.local_host(), [si.Role("w", parent, "write", 1 << 20, exact=("a", "a.partial"))])


@pytest.mark.parametrize("kind", ["dir", "file", "symlink", "dangling"])
def test_publish_dir_never_replaces(tmpdir_, kind):
    os.makedirs(os.path.join(tmpdir_, "a.partial"))
    final = os.path.join(tmpdir_, "a")
    if kind == "dir":
        os.makedirs(final)                                         # rename(2) would silently replace an empty dir
    elif kind == "file":
        make_file(final, b"keep")
    elif kind == "symlink":
        os.symlink(tmpdir_, final)
    else:
        os.symlink(os.path.join(tmpdir_, "nowhere"), final)
    refused("exists", C.publish_dir, pub_policy(tmpdir_), "w", "a.partial", "a")
    ok(os.path.isdir(os.path.join(tmpdir_, "a.partial")))


def test_publish_dir_source_must_be_a_real_dir(tmpdir_):
    os.makedirs(os.path.join(tmpdir_, "elsewhere"))
    os.symlink(os.path.join(tmpdir_, "elsewhere"), os.path.join(tmpdir_, "a.partial"))
    refused("not-dir", C.publish_dir, pub_policy(tmpdir_), "w", "a.partial", "a")
    ok(not os.path.lexists(os.path.join(tmpdir_, "a")))


def test_publish_dir_ok(tmpdir_):
    make_file(os.path.join(tmpdir_, "a.partial", "x"), b"x")
    C.publish_dir(pub_policy(tmpdir_), "w", "a.partial", "a")
    ok(read(os.path.join(tmpdir_, "a", "x")) == b"x" and not os.path.exists(os.path.join(tmpdir_, "a.partial")))


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_unlink_own_refuses_aliases(tmpdir_, kind):
    keep = make_file(os.path.join(tmpdir_, "keep"), b"keep me\n")
    target = os.path.join(tmpdir_, "d", "f")
    os.makedirs(os.path.dirname(target))
    (os.link if kind == "hardlink" else os.symlink)(keep, target)
    policy = si.Policy(C.local_host(), [si.Role("w", os.path.join(tmpdir_, "d"), "write", 1 << 20, exact=("f",))])
    refused("nlink" if kind == "hardlink" else "symlink", C.unlink_own, policy, "w", "f")
    ok(os.path.lexists(target) and read(keep) == b"keep me\n")


def test_scrubbed_env(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/nonexistent")
    monkeypatch.setenv("PYTHONPATH", "/nonexistent")
    with C.ScrubbedEnv() as env:
        home = env["HOME"]
        ok(set(env) == set(si.GIT_FIXED_ENV) | {"HOME", "XDG_CONFIG_HOME", "PYTHONDONTWRITEBYTECODE"})
        ok(os.listdir(home) == [] and "GIT_DIR" not in env and "PYTHONPATH" not in env)
    ok(not os.path.exists(home))
    with pytest.raises(si.Refusal):
        with C.ScrubbedEnv() as env:
            make_file(os.path.join(env["HOME"], "planted"), b"x")
    leftover = [d for d in os.listdir("/tmp") if d.startswith("k4s-frozen-home-")]
    for d in leftover:                                              # the refusal kept it as evidence; clean the test's
        if os.path.exists(os.path.join("/tmp", d, "planted")):
            shutil.rmtree(os.path.join("/tmp", d))


def test_record_is_exclusive_and_receipts(tmpdir_):
    path = os.path.join(tmpdir_, "rec")
    record = C.Record(path, "S9", ("s9-x.json",)).open()
    digest = record.write("s9-x.json", {"a": 1})
    ok(digest == sha(read(os.path.join(path, "s9-x.json"))))
    name = record.refusal(si.Refusal("check", "boom"))
    ok(name.startswith("S9-REFUSAL-") and os.path.exists(os.path.join(path, name)))
    refused("exists", record.write, "s9-x.json", {"a": 2})
    record.close()
    refused("exists", C.Record(path, "S9", ("s9-x.json",)).open)


def test_record_refuses_symlinked_parent(tmpdir_):
    real = os.path.join(tmpdir_, "real")
    os.makedirs(real)
    os.symlink(real, os.path.join(tmpdir_, "alias"))
    refused("root", C.Record(os.path.join(tmpdir_, "alias", "rec"), "S9", ("s9-x.json",)).open)
    ok(os.listdir(real) == [])


def test_dirs_of_parents_first():
    ok(C.dirs_of(["a/b/c.txt", "a/d.txt", "e.txt", "f/g/h/i"]) == ["a", "f", "a/b", "f/g", "f/g/h"])


def test_local_host_is_05():
    ok(C.local_host() == "127x05")


@pytest.mark.parametrize("constant", ["SAFE_INPUT_FINGERPRINT", "REMOTE_PROGRAM_SHA256", "RECEIVE_PROGRAM_SHA256"])
def test_wrong_layer_pins_refuse_the_import(tmpdir_, constant):
    """The fingerprint and both shipped-program SHAs are checked at import (not only the file SHA)."""
    code = copy_code(tmpdir_)
    path = os.path.join(code, "end_prep_common.py")
    text = read(path).decode()
    value = getattr(C, constant)
    ok(text.count('%s = "%s"' % (constant, value)) == 1)
    make_file(path, text.replace('%s = "%s"' % (constant, value), '%s = "%s"' % (constant, "0" * 64)).encode())
    result = import_in(code)
    ok(result.returncode != 0 and b"LOADED" not in result.stdout and b"is not the pinned" in result.stderr,
       result.stderr)
