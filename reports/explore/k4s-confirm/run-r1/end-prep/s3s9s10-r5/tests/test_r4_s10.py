"""r4 S10 on namespaced fake hosts: the runtime at <base>/runtime-<P12> (B2), the exact S7 RC-6 declaration (B7/U9),
the tools (U2) and end-inputs (U3) components, the interpreter probe in the P-facts login (U4) and the adopted-S4 pin
(L4). The CONSUMERS are the approved Part B code itself: S5's layout() and S7's validate_roots / validate_argv are
loaded from byte copies of s5s6s7-r4 (tests/vendor_s5s6s7_r5/, SHA-pinned below; the adopted Part B package, its
SHA256SUMS d04c6ca1 verified when copied) and run on what S10 produces."""
import hashlib
import importlib.util
import json
import os
import sys
import types

import pytest

from conftest import (C, S3, S9, S10, SYNTHETIC_S4_SHA256, make_bundle, make_file, ok, read, refused, s10_args, s3_args,
                      sha, si)

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor_s5s6s7_r5")
# byte copies of s5s6s7-r4 (its SHA256SUMS verified when copied): the S7 gate, S5, and every tools file. r5: the S7
# gate is s5s6s7-r5's (U4: HOST_PYTHON = the runtime.sh venv python); every other file is byte-identical in r4 and r5
# (s5s6s7-r5/TOOLS-FINAL lists the six tools files with these SHAs).
VENDOR_SHA256 = {
    "k4s_end_launch_gate.py": "4fc53765a506d1b9c5c9e740b515cc77b6a657bc6289b4e4337b7be4c91ad72c",
    "k4s_end_preflight.py": "c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5",
    "k4s_end_host_tool.py": "22c441b1db0fb7e1cf31cd259a5e838f375a7a935b3c78f5f5f5891869508647",
    "safe_input.py": "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00",
    "k4s_end_exit_push.sh": "65625fc0eac95079c83f2664c5a3244dbe19941cb91075eca5b2093f135679af",
    "k4s_preflight_push.sh": "c9779cfb339b335bb62d09995e6a14e0202a835af337d641a19b25fffe85c580",
    "t1-originals/detach.sh": "1648dfdcf85097a54c00b488a5d5570f7c4d0820052a31f89553501084c5b3bb",
}
P_REAL = "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb"


def vendored(name):
    path = os.path.join(VENDOR, name)
    ok(hashlib.sha256(read(path)).hexdigest() == VENDOR_SHA256[name], name)
    module_name = "vendored_" + name[:-3]
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
    return sys.modules[module_name]


def make_base(hosts, host="127x03"):
    base = hosts.path(host, si.END_BASES[host])
    for d in S10.BASE_SUBDIRS:
        os.makedirs(os.path.join(base, d))
    return base


def run(a):
    return S10.run(a, log=lambda *x: None)


def record_receipt(record):
    names = [n for n in os.listdir(record) if n.startswith("S10-REFUSAL-")]
    ok(len(names) == 1, os.listdir(record))
    return json.loads(read(os.path.join(record, names[0])))


@pytest.fixture
def end_inputs(tmpdir_, monkeypatch):
    """Synthetic stand-ins for the two 05 sources (same names/roles; synthetic bytes and pins)."""
    files = {S10.NATIVE_NAME: b"\x7fELF synthetic native\n", S10.CORPUS_NAME: b"synthetic K4 corpus\n" * 50}
    table = {}
    for i, (name, data) in enumerate(sorted(files.items())):
        directory = os.path.join(tmpdir_, "ei-src-%d" % i)
        make_file(os.path.join(directory, name), data)
        table[name] = (directory, name, sha(data), len(data))
    monkeypatch.setattr(S10, "END_INPUTS", table)
    return files


# ---------------------------------------------------------------- production constants

def test_production_constants():
    from conftest import ORIG
    for name, (src, digest, size) in S10.TOOL_PINS.items():
        ok(VENDOR_SHA256[src] == digest and os.path.getsize(os.path.join(VENDOR, src)) == size, name)
    gate = vendored("k4s_end_launch_gate.py")
    pre = vendored("k4s_end_preflight.py")
    ok(S10.TOOL_PINS["detach.sh"][1] == gate.DETACH_SHA256 and S10.TOOL_PINS["k4s_end_exit_push.sh"][1]
       == gate.WRAPPER_SHA256["end"] and S10.TOOL_PINS["k4s_preflight_push.sh"][1] == gate.WRAPPER_SHA256["preflight"]
       and S10.TOOL_PINS["k4s_end_preflight.py"][1] == gate.PREFLIGHT_SHA256
       and S10.TOOL_PINS["safe_input.py"][1] == gate.SAFE_INPUT_SHA256 == C.SAFE_INPUT_SHA256
       and S10.TOOL_PINS["k4s_end_host_tool.py"][1] == gate.HOST_TOOL_SHA256)
    ok(set(S10.TOOL_PINS) == {"detach.sh", "k4s_end_exit_push.sh", "k4s_preflight_push.sh", "k4s_end_preflight.py",
                              "safe_input.py", "k4s_end_host_tool.py"})
    ok(S10.END_INPUTS[S10.NATIVE_NAME][2] == gate.NATIVE_SHA256 == pre.NATIVE_SHA256)
    ok(S10.END_INPUTS[S10.CORPUS_NAME][2] == gate.CORPUS_SHA256 == pre.CORPUS_SHA256)
    ok(S10.END_INPUTS[S10.NATIVE_NAME][:2] == ("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native",
                                               "clasher_core.abi3.so"))
    ok(S10.END_INPUTS[S10.CORPUS_NAME][:2] == ("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/"
                                               "corpus-publication-staging-r1", "K4-states.pkl"))
    ok(S10.ROOTS_SCHEMA == gate.ROOTS_SCHEMA)
    # r5 (U4 ruling): S7 pins the END interpreter: S10 probes exactly that path; S9 exports the SD1 pin it requires
    ok(ORIG[("s10_stage_host", "HOST_PYTHON")] == gate.HOST_PYTHON)
    ok(ORIG[("s9_end_runtime", "SUPPORT_PINS")][S9.SD1_REL] == gate.SD1_MANIFEST_SHA256 == pre.FROZEN_CLOSURE[S9.SD1_REL])
    ok(ORIG[("s9_end_runtime", "SUPPORT_PINS")][S9.CORPORA_REL] == gate.CORPUS_INVENTORY_SHA256)
    ok(ORIG[("s10_stage_host", "HOST_PYTHON")] == "/mpac/sdicks02/repos/clasher/.venv/bin/python")
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_VERSION")] == "3.12.13")
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_PREFIX")] == "/mpac/sdicks02/repos/clasher/.venv")
    base = "/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu"       # the r4 pin, now only the venv's base
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_BASE_PREFIX")] == base)
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_REALPATH")] == base + "/bin/python3.12")
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_INFO")] == ())
    ok(S10.HOST_PYTHON_SOURCE == (
        "reports/explore/k4s-confirm/runtime.sh", "67249aac5f7ff0027bb7bf5fb19c4275f1fe7d9b56a9ab4977a731169b8570f3"))
    ok(gate.RUNTIME_SH_REL == S10.HOST_PYTHON_SOURCE[0])
    ok(ORIG[("s10_stage_host", "HOST_PYTHON_IMPORTS")] == ("numpy", "torch", "cv2", "scipy"))
    adopted = ORIG[("s10_stage_host", "ADOPTED_S4_SHA256")]
    ok(adopted == "2b8f5fb3b79b85103394e18c39330b772fbf2deb28d95fbd01d2d73273d7f016", adopted)                    # b3-r7 assemble_fleet_reference.py (IR-03; runner update)
    b3r6 = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r7/assemble_fleet_reference.py"   # runner: the IR-03 S4
    if os.path.exists(b3r6):                                            # the source of record, when beside this tree
        ok(hashlib.sha256(read(b3r6)).hexdigest() == adopted)


# ---------------------------------------------------------------- B2: runtime at <base>/runtime-<P12>

def test_runtime_staged_at_base_runtime_p12_and_accepted_by_s5_layout(world, runtime, hosts, tmpdir_):
    a = s10_args(runtime=runtime["out"], runtime_manifest_sha256=runtime["sha"], create_base=True,
                 record=os.path.join(tmpdir_, "rec"))
    m = run(a)
    leaf = "runtime-" + world.P[:12]
    base = si.END_BASES["127x03"]
    final = hosts.path("127x03", base + "/" + leaf)
    ok(os.path.isdir(final) and not os.path.exists(hosts.path("127x03", base + "/runtime")))
    ok(sorted(os.listdir(hosts.path("127x03", base))) == sorted(list(S10.BASE_SUBDIRS) + [leaf]))
    ok(m["components"][0]["final"] == base + "/" + leaf and m["final"][base + "/" + leaf]["mode"] == "0o555")
    for rel in S9.SUPPORT_PINS:                                         # B3/B5 members arrive with the runtime
        ok(read(os.path.join(final, rel)) == world.files[rel])
    ok([l["label"] for l in m["logins"]] == ["P-check", "P-facts", "base", "receive-runtime", "F", "POST"])
    # the CONSUMER: S5 layout() (vendored s5s6s7-r4) on the paths S10 declares
    pre = vendored("k4s_end_preflight.py")
    r = S10.roots("127x03", world.P)
    job = base + "/preflight/preflight-127x03-l00"
    args = types.SimpleNamespace(
        runtime_root=r["runtime"], bundle=base + "/bundles/end-ref-127x03-pf00",
        compare_bundle=base + "/bundles/end-ref-127x03-rd00-a00", repository=r["repository"],
        attempt_parent=r["attempts"], out=job + "/preflight-127x03-l00",
        corpus_inventory=r["runtime"] + "/" + S9.CORPORA_REL, native=r["native"], corpus=r["corpus"],
        end_evidence=base + "/bundles/end-ref-127x03-pf00/k4s-end-evidence/end-evidence.json",
        bundle_pins_sha256="1" * 64, corpus_inventory_sha256=pre.CORPUS_INVENTORY_SHA256, end_evidence_sha256="2" * 64,
        sd1_manifest_sha256="3" * 64, compare_bundle_pins_sha256="4" * 64)
    ok(pre.layout(args, "127x03", base)["runtime_root"] == r["runtime"])
    ok(S9.CORPORA_REL == pre.CORPUS_INVENTORY_REL)
    args.runtime_root = base + "/runtime/" + leaf                       # r3's location: S5 refuses it (B2)
    args.corpus_inventory = args.runtime_root + "/" + S9.CORPORA_REL
    with pytest.raises(pre.PreflightRefusal):
        pre.layout(args, "127x03", base)


# ---------------------------------------------------------------- U2 / U3: tools and end-inputs

def test_tools_and_end_inputs_staged_a_w_single_link(world, hosts, tmpdir_, end_inputs):
    make_base(hosts)
    a = s10_args(tools_source=VENDOR, end_inputs=True, record=os.path.join(tmpdir_, "rec"))
    m = run(a)
    ok([l["label"] for l in m["logins"]] == ["P-check", "P-facts", "receive-tools", "receive-end-inputs", "F", "POST"])
    base = si.END_BASES["127x03"]
    tools = hosts.path("127x03", base + "/tools")
    ok(sorted(os.listdir(tools)) == sorted(S10.TOOL_PINS) and os.lstat(tools).st_mode & 0o777 == 0o555)
    for name, (src, digest, size) in S10.TOOL_PINS.items():
        st = os.lstat(os.path.join(tools, name))
        ok(st.st_nlink == 1 and st.st_mode & 0o777 == 0o444 and st.st_size == size)
        ok(hashlib.sha256(read(os.path.join(tools, name))).hexdigest() == digest, name)
    ei = hosts.path("127x03", base + "/end-inputs-r1")
    ok(sorted(os.listdir(ei)) == sorted(end_inputs) and os.lstat(ei).st_mode & 0o777 == 0o555)
    for name, data in end_inputs.items():
        ok(read(os.path.join(ei, name)) == data and os.lstat(os.path.join(ei, name)).st_nlink == 1)
    r = S10.roots("127x03")
    ok(m["components"][1]["native"] == r["native"] == base + "/end-inputs-r1/clasher_core.abi3.so")


@pytest.mark.parametrize("case,code", [("wrong-bytes", "sha"), ("missing", "missing"), ("hardlink", "nlink"),
                                       ("symlink", "symlink"), ("size", "size")])
def test_tools_refused_before_any_login(world, hosts, tmpdir_, case, code):
    make_base(hosts)
    src = os.path.join(tmpdir_, "tools-src")
    for name, (rel, _, _) in S10.TOOL_PINS.items():
        make_file(os.path.join(src, rel), read(os.path.join(VENDOR, rel)))
    victim = os.path.join(src, "k4s_end_host_tool.py")
    data = read(victim)
    if case == "wrong-bytes":
        make_file(victim, data[:-2] + b"#\n")
    elif case == "missing":
        os.unlink(victim)
    elif case == "hardlink":
        os.link(victim, os.path.join(tmpdir_, "alias"))
    elif case == "symlink":
        os.unlink(victim)
        make_file(os.path.join(tmpdir_, "real.py"), data)
        os.symlink(os.path.join(tmpdir_, "real.py"), victim)
    else:
        make_file(victim, data + b"\n")
    a = s10_args(tools_source=src, record=os.path.join(tmpdir_, "rec"))
    refused(code, run, a)
    ok(hosts.logins() == [])
    record_receipt(a.record)


@pytest.mark.parametrize("case,code", [("wrong-bytes", "sha"), ("size", "size"), ("hardlink", "nlink")])
def test_end_inputs_refused_before_any_login(world, hosts, tmpdir_, end_inputs, case, code):
    make_base(hosts)
    directory, leaf, _, size = S10.END_INPUTS[S10.CORPUS_NAME]
    path = os.path.join(directory, leaf)
    if case == "wrong-bytes":
        make_file(path, b"X" + read(path)[1:])
    elif case == "size":
        make_file(path, read(path) + b"x")
    else:
        os.link(path, os.path.join(tmpdir_, "alias"))
    a = s10_args(end_inputs=True, record=os.path.join(tmpdir_, "rec"))
    refused(code, run, a)
    ok(hosts.logins() == [])


# ---------------------------------------------------------------- U4: interpreter probe (inside P-facts)

def test_interpreter_probe_recorded(world, runtime, hosts, tmpdir_, end_inputs):
    make_base(hosts)
    m = run(s10_args(end_inputs=True, record=os.path.join(tmpdir_, "rec")))
    py = m["inspect"]["interpreter"]
    ok(py["ok"] and py["executable"] == S10.HOST_PYTHON and py["version"] == S10.HOST_PYTHON_VERSION)
    ok(sorted(py["imports"]) == sorted(S10.HOST_PYTHON_IMPORTS) and all(v["ok"] for v in py["imports"].values()))
    ok(C.is_sha256(py["realpath_sha256"]) and py["flags"]["isolated"] == 0 and py["flags"]["optimize"] == 0)
    info = m["inspect"]["interpreter_candidates_informational"]
    ok(len(info) == 1 and info[0]["ok"] is False and info[0]["rc"] != "0")     # a missing candidate never refuses
    ok(len(hosts.logins()) == 5)                                        # no extra login for the probe
    ok("-B -c" in hosts.logins()[1])


@pytest.mark.parametrize("case,code", [("version", "interpreter"), ("import", "interpreter"), ("missing", "subprocess"),
                                       ("two-records", "interpreter"), ("exit-37", "subprocess"),
                                       ("executable", "interpreter")])
def test_interpreter_probe_refusals(world, hosts, tmpdir_, end_inputs, monkeypatch, case, code):
    make_base(hosts)
    if case == "version":
        monkeypatch.setattr(S10, "HOST_PYTHON_VERSION", "3.12.13")
    elif case == "import":
        monkeypatch.setattr(S10, "HOST_PYTHON_IMPORTS", ("json", "torch_is_not_here_k4s"))
    elif case == "missing":
        monkeypatch.setattr(S10, "HOST_PYTHON", "/mpac/sdicks02/fakebin/absent-python")
    elif case in ("two-records", "exit-37", "executable"):
        script = {"two-records": "#!/bin/sh\n/usr/bin/python3 \"$@\"\n/usr/bin/python3 \"$@\"\n",
                  "exit-37": "#!/bin/sh\n/usr/bin/python3 \"$@\"\nexit 37\n",
                  "executable": "#!/bin/sh\nexec /usr/bin/python3 \"$@\"\n"}[case]
        path = hosts.tool("127x03", "py-wrapper", script)[0]
        monkeypatch.setattr(S10, "HOST_PYTHON", path)
    a = s10_args(end_inputs=True, record=os.path.join(tmpdir_, "rec"))
    error = refused(code, run, a)
    ok(len(hosts.logins()) == 2, hosts.logins())
    ok(not os.path.exists(hosts.path("127x03", si.END_BASES["127x03"] + "/end-inputs-r1.partial")), error.reason)
    record_receipt(a.record)


def test_probe_command_mirrors_the_end_launch_environment():
    cmd = S10.python_probe_command("/x/python3.12")
    ok(cmd.startswith("cd / && /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "
                      "MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 HOME=\"$HOME\" /usr/bin/nice -n 19 /x/python3.12 -B -c "))
    gate = vendored("k4s_end_launch_gate.py")
    ok(set(gate.ENV_REQUIRED.items()) <= {tuple(e.split("=", 1)) for e in S10.PYTHON_ENV})
    ok("-I" not in cmd.split(" -c ")[0].split())                        # END runs python -B without -I


# ---------------------------------------------------------------- L4: adopted S4

def test_bundle_from_another_s4_refused(world, runtime, hosts, tmpdir_, monkeypatch):
    make_base(hosts)
    b = make_bundle(world, tmpdir_, "end-ref-127x03-rd00-a00", "127x03", runtime["manifest"],
                    receipt_overrides={"assembler_sha256": "e" * 64})
    a = s10_args(runtime_manifest_for_checks=runtime["out"], runtime_manifest_sha256=runtime["sha"],
                 bundle=[(b["dir"], b["tiers"], b["receipt"])], record=os.path.join(tmpdir_, "rec"))
    error = refused("check", run, a)
    ok("not the adopted" in error.reason)
    monkeypatch.setattr(S10, "ADOPTED_S4_SHA256", "PENDING-b3-r6-not-DONE")
    b2 = make_bundle(world, tmpdir_, "end-ref-127x03-rd00-a01", "127x03", runtime["manifest"])
    a2 = s10_args(runtime_manifest_for_checks=runtime["out"], runtime_manifest_sha256=runtime["sha"],
                  bundle=[(b2["dir"], b2["tiers"], b2["receipt"])], record=os.path.join(tmpdir_, "rec2"))
    error = refused("policy", run, a2)
    ok("ADOPTED_S4_SHA256 is not set" in error.reason)
    ok(hosts.logins() == [])


# ---------------------------------------------------------------- B7 / U9: the RC-6 declaration

@pytest.fixture
def six_bundles(world, runtime, tmpdir_):
    out = []
    for host in ("127x03", "127x04"):
        for tag in ("pf00", "rd00-a00", "rd00-a01"):
            name = "end-ref-%s-%s" % (host, tag)
            b = make_bundle(world, os.path.join(tmpdir_, "bundles"), name, host, runtime["manifest"])
            job = S3.GUARD_PARENTS[host] + "/k4s-end-guard-r1-" + tag
            doc = json.loads(read(os.path.join(b["dir"], "tiers-pins.json")))
            doc["reference_load_profile"]["guard"]["job"] = job          # each bundle its own guard job (RC-9)
            b = make_bundle(world, os.path.join(tmpdir_, "bundles-" + tag + host), name, host, runtime["manifest"],
                            manifest_overrides={"reference_load_profile": doc["reference_load_profile"]},
                            receipt_overrides={"guard_job": job})
            out.append((host, b))
    return out


def declare_args(runtime, bundles, out, commit):
    return s10_args(declare_roots=True, commit=commit, runtime_manifest_for_checks=runtime["out"],
                    runtime_manifest_sha256=runtime["sha"], out=out,
                    declare_bundle=[(h, b["dir"], b["tiers"], b["receipt"]) for h, b in bundles])


def test_declare_roots_is_exactly_what_s7_consumes(world, runtime, six_bundles, tmpdir_):
    out = os.path.join(tmpdir_, "ROOTS-DECLARATION.json")
    lines = []
    doc, digest = S10.declare_roots(declare_args(runtime, six_bundles, out, world.P), log=lines.append)
    ok(hashlib.sha256(read(out)).hexdigest() == digest and os.lstat(out).st_mode & 0o777 == 0o444)
    ok(json.loads(read(out)) == doc and doc["schema"] == "clasher.k4s.end-roots-declaration.v1" and doc["commit"] == world.P)
    gate = vendored("k4s_end_launch_gate.py")
    hosts_ = gate.validate_roots(si, json.loads(read(out)))             # the REAL S7 parser accepts it
    for host, b in six_bundles:
        d = hosts_[host]
        name = os.path.basename(b["dir"])
        ok(d["bundles"][name] == dict(path=si.END_BASES[host] + "/bundles/" + name, tiers_pins_sha256=b["tiers"],
                                      guard_job=json.loads(read(os.path.join(b["dir"], "tiers-pins.json")))
                                      ["reference_load_profile"]["guard"]["job"]))
        ok(d["runtime"] == si.END_BASES[host] + "/runtime-" + world.P[:12] and d["tools"] == si.END_BASES[host] + "/tools")
    # ... and the S7 argv check accepts an END argv built from the S10 roots (runtime, tools, native, corpus)
    host, base = "127x03", si.END_BASES["127x03"]
    r = S10.roots(host, world.P)
    job = base + "/attempts/end-127x03-r00-l00"
    bundle = base + "/bundles/end-ref-127x03-rd00-a00"
    argv = ["nice", "-n", "10", "taskset", "-c", "61", "bash", r["tools"] + "/detach.sh", job + "/detach.log",
            job + "/detach.json", "bash", r["tools"] + "/k4s_end_exit_push.sh", job, "env", "OMP_NUM_THREADS=1",
            "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", gate.HOST_PYTHON, "-B",
            r["runtime"] + "/reports/explore/k4s-confirm/end_reference.py", "--bundle", bundle, "--runtime-root",
            r["runtime"], "--native", r["native"], "--corpus", r["corpus"], "--corpus-inventory",
            r["runtime"] + "/" + S9.CORPORA_REL, "--k4s-manifest-sha256", gate.K4S_MANIFEST_SHA256,
            "--sd1-manifest-sha256", gate.SD1_MANIFEST_SHA256, "--end-evidence", bundle + "/" + gate.END_EVIDENCE_REL,
            "--end-evidence-sha256", gate.END_EVIDENCE_SHA256, "--repository", r["repository"], "--end-job-sha256", "3" * 64,
            "--round", "0", "--out", job + "/end-127x03-r00-l00"]
    shape = gate.validate_argv(si, argv, "end", host, "end-127x03-r00-l00", hosts_)
    ok(set(shape["file_pins"]) == {r["tools"] + "/" + n for n in ("detach.sh", "k4s_end_exit_push.sh", "safe_input.py",
                                                                    "k4s_end_host_tool.py")})
    for path, pin in shape["file_pins"].items():                       # every S7 file pin is a TOOL_PINS file
        ok(S10.TOOL_PINS[os.path.basename(path)][1] == pin)
    ok(any("RC-6 ROOTS-DECLARATION sha256 " + digest in line for line in lines))


@pytest.mark.parametrize("case,code", [
    ("commit-not-runtime", "check"), ("tiers-sha", "sha"), ("receipt-sha", "sha"), ("wrong-host", "check"),
    ("duplicate", "policy"), ("synthetic", "check"), ("other-s4", "check"), ("out-exists", "exists"),
    ("out-outside", "path"), ("only-one-host", "check"), ("shared-guard-job", "check")])
def test_declare_roots_refusals(world, runtime, six_bundles, tmpdir_, case, code):
    out = os.path.join(tmpdir_, "ROOTS-DECLARATION.json")
    bundles, commit = list(six_bundles), world.P
    if case == "commit-not-runtime":
        commit = world.X
    elif case == "tiers-sha":
        bundles[0] = (bundles[0][0], dict(bundles[0][1], tiers="0" * 64))
    elif case == "receipt-sha":
        bundles[0] = (bundles[0][0], dict(bundles[0][1], receipt="0" * 64))
    elif case == "wrong-host":
        bundles[0] = ("127x04", bundles[0][1])
    elif case == "duplicate":
        bundles.append(bundles[0])
    elif case == "synthetic":
        b = make_bundle(world, os.path.join(tmpdir_, "syn"), "end-ref-127x03-rd01-a00", "127x03", runtime["manifest"],
                        synthetic=True)
        bundles.append(("127x03", b))
    elif case == "other-s4":
        b = make_bundle(world, os.path.join(tmpdir_, "o4"), "end-ref-127x03-rd01-a00", "127x03", runtime["manifest"],
                        receipt_overrides={"assembler_sha256": "e" * 64})
        bundles.append(("127x03", b))
    elif case == "out-exists":
        make_file(out, b"keep\n")
    elif case == "out-outside":
        out = "/dev/shm/k4s-s10-never"
    elif case == "only-one-host":
        bundles = [x for x in bundles if x[0] == "127x03"]
    elif case == "shared-guard-job":
        b = make_bundle(world, os.path.join(tmpdir_, "sg"), "end-ref-127x03-rd00-a09", "127x03", runtime["manifest"])
        bundles.append(("127x03", b))
        bundles.append(("127x03", make_bundle(world, os.path.join(tmpdir_, "sg2"), "end-ref-127x03-rd00-a08", "127x03",
                                              runtime["manifest"])))
    refused(code, S10.declare_roots, declare_args(runtime, bundles, out, commit), log=lambda *a: None)
    if case == "out-exists":
        ok(read(out) == b"keep\n")
    elif case != "out-outside":
        ok(not os.path.exists(out))
    ok(not os.path.exists("/dev/shm/k4s-s10-never"))


def mutate_doc(doc, case):
    d = doc["hosts"]["127x03"]
    name = sorted(d["bundles"])[0]
    if case == "schema":
        doc["schema"] = "clasher.k4s.end-rc6-roots.DRAFT.v1"
    elif case == "commit":
        doc["commit"] = "PENDING"
    elif case == "extra-key":
        doc["status"] = "draft"
    elif case == "host-key":
        d["guard_job_parent"] = d.pop("guard_parent")
    elif case == "runtime-r3-location":
        d["runtime"] = d["base"] + "/runtime/runtime-" + doc["commit"][:12]
    elif case == "runtime-other-commit":
        d["runtime"] = d["base"] + "/runtime-" + "0" * 12
    elif case == "tools":
        d["tools"] = d["base"] + "/tool"
    elif case == "bundle-path":
        d["bundles"][name]["path"] = d["base"] + "/bundles/other"
    elif case == "bundle-sha":
        d["bundles"][name]["tiers_pins_sha256"] = "PENDING-S4-BLOCKED"
    elif case == "guard-parent":
        d["bundles"][name]["guard_job"] = "/mpac/sdicks02/jobs-k4s/" + os.path.basename(d["bundles"][name]["guard_job"])
    elif case == "no-bundles":
        d["bundles"] = {}
    elif case == "one-host":
        del doc["hosts"]["127x04"]
    elif case == "repository":
        d["repository"] = d["base"] + "/repo"
    return doc


@pytest.mark.parametrize("case", ["schema", "commit", "extra-key", "host-key", "runtime-r3-location",
                                  "runtime-other-commit", "tools", "bundle-path", "bundle-sha", "guard-parent",
                                  "no-bundles", "one-host", "repository"])
def test_validate_roots_matches_s7_rule_for_rule(world, runtime, six_bundles, tmpdir_, case):
    """Every malformed variant refused by S10's self-check is refused by S7's own validate_roots too (and vice versa
    for the valid one), except the producer-only rule (runtime leaf == runtime-<commit12>), which S7 cannot know."""
    out = os.path.join(tmpdir_, "R.json")
    doc, _ = S10.declare_roots(declare_args(runtime, six_bundles, out, world.P), log=lambda *a: None)
    gate = vendored("k4s_end_launch_gate.py")
    bad = mutate_doc(json.loads(json.dumps(doc)), case)
    refused("check", S10.validate_roots, bad)
    if case != "runtime-other-commit":
        with pytest.raises((gate.GateRefusal, KeyError, TypeError, AttributeError)):
            gate.validate_roots(si, bad)


def test_declare_roots_cli(world, runtime, six_bundles, tmpdir_):
    out = os.path.join(tmpdir_, "cli.json")
    argv = ["--declare-roots", "--commit", world.P, "--runtime-manifest-for-checks", runtime["out"],
            "--runtime-manifest-sha256", runtime["sha"], "--out", out]
    for host, b in six_bundles:
        argv += ["--declare-bundle", host, b["dir"], b["tiers"], b["receipt"]]
    ok(S10.main(argv) == 0 and os.path.exists(out))
    ok(S10.main(argv) == 2)                                             # exclusive: never replaced
    ok(S10.main(argv[:3]) == 2)


# ---------------------------------------------------------------- r4 IR-03 (03 has no idle resident)

def test_ir03_03_guard_job_is_bus_only_while_s1b_keeps_its_contract(world, s1b_out, guard03):
    """IR-03: the S1b copy contract still names 03's idle-services.json (A1b ran under it) and the S1b manifest still
    has that row, but the 03 guard job S3 builds and verifies carries the system-bus admission only."""
    ok(S3.S1B.NAMES["127x03"] == ("system-bus-admission.json", "idle-services.json"))
    ok(S3.END_ADMISSIONS == {"127x03": ("system-bus-admission.json",), "127x04": ("system-bus-admission.json",)})
    rows = json.loads(read(s1b_out["manifest"]))["files"]
    ok(any(r["host"] == "127x03" and r["name"] == "idle-services.json" for r in rows))
    m = guard03["manifest"]
    ok(sorted(m["admissions"]) == ["system-bus-admission.json"] and "idle-services.json" not in m["top_level"])
    ok(not os.path.exists(os.path.join(guard03["out"], guard03["job"], "idle-services.json")))
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", guard03["out"], guard03["job"]))
    S3.verify(policy, "s3", guard03["out"], guard03["job"], guard03["sha"], log=lambda *a: None)


@pytest.mark.parametrize("case", ["file-in-job", "manifest-row"])
def test_ir03_guard_job_with_idle_services_is_refused(world, guard03, tmpdir_, case):
    """A 03 guard job that carries idle-services.json (in the tree, or as a manifest admission) is refused by verify."""
    import shutil
    out = os.path.join(tmpdir_, "g")
    shutil.copytree(guard03["out"], out, symlinks=True)
    job = os.path.join(out, guard03["job"])
    sha_m = guard03["sha"]
    from conftest import admissions as adm
    if case == "file-in-job":
        os.chmod(job, 0o755)
        make_file(os.path.join(job, "idle-services.json"), adm("127x03")["idle-services.json"], 0o444)
    else:
        path = os.path.join(out, S3.MANIFEST)
        doc = json.loads(read(path))
        doc["admissions"]["idle-services.json"] = dict(doc["admissions"]["system-bus-admission.json"],
                                                       sha256=sha(adm("127x03")["idle-services.json"]))
        os.chmod(path, 0o644)
        raw = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
        make_file(path, raw, 0o444)
        sha_m = sha(raw)
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", out, guard03["job"]))
    error = refused("check", S3.verify, policy, "s3", out, guard03["job"], sha_m, log=lambda *a: None)
    ok("top level" in error.reason or "IR-03" in error.reason, error.reason)


def test_ir03_bundle_with_03_idle_admission_refused(world, runtime, hosts, tmpdir_, monkeypatch):
    """S10 (bundle header): a 03 bundle whose guard admissions still include idle-services.json is refused."""
    os.makedirs(hosts.path("127x03", si.END_BASES["127x03"] + "/bundles"))
    with monkeypatch.context() as m:
        m.setitem(S3.END_ADMISSIONS, "127x03", ("system-bus-admission.json", "idle-services.json"))
        b = make_bundle(world, tmpdir_, "end-ref-127x03-rd00-a00", "127x03", runtime["manifest"])
    a = s10_args(runtime_manifest_for_checks=runtime["out"], runtime_manifest_sha256=runtime["sha"],
                 bundle=[(b["dir"], b["tiers"], b["receipt"])], record=os.path.join(tmpdir_, "rec"))
    error = refused("check", run, a)
    ok("guard admissions must be exactly" in error.reason, error.reason)
    ok(hosts.logins() == [])


# ---------------------------------------------------------------- guards masked in the first campaign (V11, V14)

def test_parse_python_requires_exactly_one_record():
    """V11: two probe records with an otherwise valid interpreter are refused (not masked by the executable check)."""
    from test_r5_u4 import good_record                                   # r5: a record of the pinned venv
    rec = good_record()
    line = "@@PY " + json.dumps(rec)
    ok(S10.parse_python([line], S10.HOST_PYTHON, True)["ok"] is True)
    refused("interpreter", S10.parse_python, [line, line], S10.HOST_PYTHON, True)
    refused("interpreter", S10.parse_python, [], S10.HOST_PYTHON, True)


def test_validate_roots_runtime_is_runtime_commit12_on_both_hosts(world, runtime, six_bundles, tmpdir_):
    """V14: both hosts declaring the SAME wrong runtime leaf (so the two-host equality cannot mask it) is refused."""
    doc, _ = S10.declare_roots(declare_args(runtime, six_bundles, os.path.join(tmpdir_, "R.json"), world.P),
                               log=lambda *a: None)
    for d in doc["hosts"].values():
        d["runtime"] = d["base"] + "/runtime-" + "0" * 12
    refused("check", S10.validate_roots, doc)
