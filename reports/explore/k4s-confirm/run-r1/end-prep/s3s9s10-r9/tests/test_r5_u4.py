"""r5 U4 (COORDINATOR 2026-10-13 10:33Z ruling): the END interpreter is the venv python P' runtime.sh executes
(`/mpac/sdicks02/repos/clasher/.venv/bin/python -B`), not the bare uv binary. S10's read-only probe (inside the existing
P-facts login, run exactly as END runs it) records the path, its realpath, sys.executable, prefix / base_prefix, the
site-packages realpaths, pyvenv.cfg (SHA-256 + keys), the version and each import's origin/version, and refuses
unless the venv pin holds. The fake hosts carry a real venv layout on the system python3 (conftest)."""
import json
import os
import subprocess

import pytest

from conftest import C, ORIG, S9, S10, make_file, ok, read, refused, s10_args, sha, si
from test_r4_s10 import end_inputs, make_base, record_receipt, run, vendored  # noqa: F401  (fixture)

HOST = "127x03"


def good_record(**kw):
    sp = S10.HOST_PYTHON_PREFIX + "/lib/python3/site-packages"
    rec = dict(executable=S10.HOST_PYTHON, realpath=S10.HOST_PYTHON_REALPATH, version=S10.HOST_PYTHON_VERSION,
               prefix=S10.HOST_PYTHON_PREFIX, prefix_realpath=S10.HOST_PYTHON_PREFIX,
               base_prefix=S10.HOST_PYTHON_BASE_PREFIX, exec_prefix=S10.HOST_PYTHON_PREFIX,
               pyvenv_cfg=dict(path=S10.HOST_PYTHON_PREFIX + "/pyvenv.cfg", sha256="a" * 64, size=10,
                               keys=dict(home=S10.HOST_PYTHON_BASE_PREFIX + "/bin")),
               site_packages=[dict(path=sp, kind="site", realpath=sp, exists=True, on_sys_path=True)],
               imports={m: dict(ok=True, origin=sp + "/" + m + ".py", origin_realpath=sp + "/" + m + ".py", version="1")
                        for m in S10.HOST_PYTHON_IMPORTS})
    rec.update(kw)
    return rec


def test_u4_probe_records_the_venv(world, runtime, hosts, tmpdir_, end_inputs):
    make_base(hosts)
    m = run(s10_args(end_inputs=True, record=os.path.join(tmpdir_, "rec")))
    py = m["inspect"]["interpreter"]
    ok(py["ok"] is True and py["venv_problems"] == [] and py["failed_imports"] == [], py)
    ok(py["executable"] == S10.HOST_PYTHON == "/mpac/sdicks02/fakevenv/bin/python")
    ok(py["prefix"] == py["prefix_realpath"] == S10.HOST_PYTHON_PREFIX and py["base_prefix"] == "/usr")
    ok(py["realpath"] == S10.HOST_PYTHON_REALPATH and C.is_sha256(py["realpath_sha256"]))
    cfg = py["pyvenv_cfg"]
    ok(cfg["keys"]["home"] == "/usr/bin" and C.is_sha256(cfg["sha256"]))
    ok(cfg["sha256"] == sha(read(hosts.path(HOST, "/mpac/sdicks02/fakevenv/pyvenv.cfg"))))
    venv_sites = [s for s in py["site_packages"] if s["realpath"].startswith(S10.HOST_PYTHON_PREFIX + "/")
                  and s["on_sys_path"] and s["exists"]]
    ok(len(venv_sites) == 1, py["site_packages"])
    ok([s for s in py["site_packages"] if s["kind"] == "user"], py["site_packages"])   # recorded, END has no -s
    for name in S10.HOST_PYTHON_IMPORTS:
        got = py["imports"][name]
        ok(got["ok"] and got["version"] == "0.0+k4s-fake" and got["origin_realpath"].startswith(
            venv_sites[0]["realpath"] + "/"), got)
    ok(py["flags"]["isolated"] == 0 and py["flags"]["dont_write_bytecode"] == 1)
    probe = hosts.logins()[1]
    ok(" /mpac/sdicks02/fakevenv/bin/python -B -c " in probe and " -I " not in probe.split(" -c ")[0])


@pytest.mark.parametrize("case", ["bare-binary", "prefix", "base-prefix", "realpath", "pyvenv-home", "pyvenv-missing",
                                  "import-outside-venv", "symlinked-venv", "version"])
def test_u4_probe_refuses_anything_but_the_pinned_venv(world, hosts, tmpdir_, end_inputs, monkeypatch, case):
    make_base(hosts)
    venv = hosts.path(HOST, "/mpac/sdicks02/fakevenv")
    if case == "bare-binary":                                           # r4's pin shape: the base binary itself
        monkeypatch.setattr(S10, "HOST_PYTHON", "/usr/bin/python3")
    elif case == "prefix":
        monkeypatch.setattr(S10, "HOST_PYTHON_PREFIX", "/mpac/sdicks02/other-venv")
    elif case == "base-prefix":
        monkeypatch.setattr(S10, "HOST_PYTHON_BASE_PREFIX", "/opt/other-python")
    elif case == "realpath":
        monkeypatch.setattr(S10, "HOST_PYTHON_REALPATH", "/usr/bin/python3.99")
    elif case == "pyvenv-home":                                         # python still finds /usr; the pin does not hold
        make_file(os.path.join(venv, "pyvenv.cfg"), read(os.path.join(venv, "pyvenv.cfg")).replace(
            b"home = /usr/bin", b"home = /usr/bin/"))
    elif case == "pyvenv-missing":
        os.unlink(os.path.join(venv, "pyvenv.cfg"))
    elif case == "import-outside-venv":
        monkeypatch.setattr(S10, "HOST_PYTHON_IMPORTS", tuple(S10.HOST_PYTHON_IMPORTS) + ("json",))
    elif case == "symlinked-venv":
        os.symlink(venv, venv + "-link")
        monkeypatch.setattr(S10, "HOST_PYTHON", "/mpac/sdicks02/fakevenv-link/bin/python")
        monkeypatch.setattr(S10, "HOST_PYTHON_PREFIX", "/mpac/sdicks02/fakevenv-link")
    else:
        monkeypatch.setattr(S10, "HOST_PYTHON_VERSION", "3.12.13")
    a = s10_args(end_inputs=True, record=os.path.join(tmpdir_, "rec"))
    error = refused("interpreter", run, a)
    # (without the venv's pyvenv.cfg the stand-in modules are not importable: refused one rule earlier, as the bare
    # uv binary would be for torch on a host)
    word = {"bare-binary": "cannot import", "prefix": "prefix is", "base-prefix": "base_prefix is",
            "realpath": "realpath is", "pyvenv-home": "pyvenv.cfg", "pyvenv-missing": "cannot import",
            "import-outside-venv": "json was imported from", "symlinked-venv": "prefix_realpath is",
            "version": ", not %s" % S10.HOST_PYTHON_VERSION}[case]   # V08: the first rule's own message
    ok(word in error.reason, error.reason)
    ok(len(hosts.logins()) == 2, hosts.logins())                        # refused in P-facts, before any staging
    ok(not os.path.exists(hosts.path(HOST, si.END_BASES[HOST] + "/end-inputs-r1.partial")))
    record_receipt(a.record)


VENV_FIELDS = ["executable", "version", "prefix", "prefix_realpath", "base_prefix", "realpath", "pyvenv-sha",
               "pyvenv-home", "pyvenv-error", "site-not-on-path", "site-outside-venv", "origin-outside", "origin-none"]


@pytest.mark.parametrize("field", VENV_FIELDS)
def test_u4_venv_problems_row_by_row(field):
    """Every rule of venv_problems, isolated on a crafted record (the healthy record has no problem)."""
    ok(S10.venv_problems(good_record(), S10.HOST_PYTHON) == [])
    rec = good_record()
    name = S10.HOST_PYTHON_IMPORTS[0]
    if field in ("executable", "version", "prefix", "prefix_realpath", "base_prefix", "realpath"):
        rec[field] = "/elsewhere"
    elif field == "pyvenv-sha":
        rec["pyvenv_cfg"]["sha256"] = None
    elif field == "pyvenv-home":
        rec["pyvenv_cfg"]["keys"]["home"] = "/elsewhere/bin"
    elif field == "pyvenv-error":
        rec["pyvenv_cfg"] = dict(path="x", error="FileNotFoundError")
    elif field == "site-not-on-path":
        rec["site_packages"][0]["on_sys_path"] = False
    elif field == "site-outside-venv":
        for s in rec["site_packages"]:
            s["realpath"] = "/usr/lib/python3/dist-packages"
    elif field == "origin-outside":
        rec["imports"][name]["origin_realpath"] = "/usr/lib/python3/dist-packages/" + name + ".py"
    else:
        rec["imports"][name]["origin_realpath"] = None
    problems = S10.venv_problems(rec, S10.HOST_PYTHON)
    word = {"pyvenv-sha": "pyvenv.cfg", "pyvenv-home": "pyvenv.cfg", "pyvenv-error": "pyvenv.cfg",
            "site-not-on-path": "no site-packages", "site-outside-venv": "no site-packages",
            "origin-outside": "outside the venv", "origin-none": "outside the venv"}.get(field, field + " is ")
    ok(len(problems) == 1 + (field in ("site-not-on-path", "site-outside-venv")) * len(S10.HOST_PYTHON_IMPORTS)
       and word in problems[0], (field, problems))
    refused("interpreter", S10.parse_python, ["@@PY " + json.dumps(rec)], S10.HOST_PYTHON, True)
    ok(S10.parse_python(["@@PY " + json.dumps(rec)], S10.HOST_PYTHON, False)["ok"] is False)


def test_u4_pins_agree_with_s7_and_the_layout():
    gate = vendored("k4s_end_launch_gate.py")
    ok(ORIG[("s10_stage_host", "HOST_PYTHON")] == gate.HOST_PYTHON == "/mpac/sdicks02/repos/clasher/.venv/bin/python")
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_REALPATH")] != gate.HOST_PYTHON)          # the bare binary is not the pin
    lay = S10.layout()["interpreter"]
    ok(lay["path"] == S10.HOST_PYTHON and lay["flags"] == "-B" and lay["source"] == list(S10.HOST_PYTHON_SOURCE))
    ok("PENDING" not in json.dumps(lay))


def test_u4_pin_is_the_runtime_sh_interpreter_at_p_prime():
    """The pin's source of record: runtime.sh at P' (read by its blob, one non-outcome file, read-only) execs exactly
    HOST_PYTHON with -B. Runs only beside the real clone (05); otherwise the pinned blob SHA is all that is checked."""
    repo = ORIG.get(("s9_end_runtime", "REPO_FULL"), S9.REPO_FULL)
    rel, want = S10.HOST_PYTHON_SOURCE
    if not os.path.isdir(os.path.join(repo, ".git")):
        pytest.skip("the real full clone is not beside this tree")
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C",
           "GIT_NO_REPLACE_OBJECTS": "1"}
    p = "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb"
    oid = subprocess.run(["/usr/bin/git", "--git-dir=" + repo + "/.git", "rev-parse", "%s:%s" % (p, rel)],
                         stdout=subprocess.PIPE, env=env, check=True).stdout.decode().strip()
    data = subprocess.run(["/usr/bin/git", "--git-dir=" + repo + "/.git", "cat-file", "blob", oid],
                          stdout=subprocess.PIPE, env=env, check=True).stdout
    ok(sha(data) == want)
    lines = [l for l in data.decode().splitlines() if l.startswith("exec ")]
    ok(lines == ['exec %s -B "$@"' % ORIG[("s10_stage_host", "HOST_PYTHON")]], lines)
