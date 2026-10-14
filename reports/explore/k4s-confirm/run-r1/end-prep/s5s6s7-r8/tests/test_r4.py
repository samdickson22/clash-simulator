"""r4 (INTEGRATION-AUDIT-r1 U5, U6, U7, L1, U12): S7 build-argv / prepare-preflight-receive, the host program's
staged-runtime and END-JOB-at-HEAD checks, the verifier's PREPARE-PROOF copy, the coordinator-file templates.

build-argv is proven against the REAL gate: the argv it writes passes `launch` (fake ssh, composed host program),
equals the hand-built fixture argv token for token, and every single-token change (re-pinned, so the pin alone never
decides) is refused, on 05 before any session or, for the three host-only facts, by the host program before any job
is created. All bytes are synthetic, under pytest's tmp_path."""
import json
import os
import re
import shutil
import time
from pathlib import Path

import pytest

import helpers as H
import k4s_end_launch_gate as G
from helpers import ROOT, ok, raises
from test_s7_gate import Site, end_job_bytes, refused_on_host

if __debug__:
    import k4s_end_verify_push as V
else:
    V = None
needs_debug = pytest.mark.skipif(not __debug__, reason="verifier refuses -O at import")
TEMPLATES = ROOT / "templates"


@pytest.fixture
def site(tmp_path, monkeypatch):
    return Site(tmp_path, monkeypatch)


def stage(site, receipt_over=None, names=None):
    """The S4 outputs on 05 (end-staging/bundles/<name>/): the host's tiers-pins.json bytes (RC-6 SHA), sidecar and a
    production CANDIDATE assembly receipt; plus the 05 full clone with the END-JOB committed (returns X)."""
    staging = site.tmp / "end-staging" / "bundles"
    site.mp.setattr(G, "STAGING_BUNDLES", str(staging))
    for h in G.END_HOSTS:
        for name, b in site.decl["hosts"][h]["bundles"].items():
            if names and name not in names:
                continue
            target = staging / name if h == site.host else staging.parent / ("other-" + h) / name
            data = (Path(b["path"]) / "tiers-pins.json").read_bytes()
            H.write(target / "tiers-pins.json", data)
            H.write(target / "tiers-pins.sha256", b["tiers_pins_sha256"] + "  tiers-pins.json\n")
            receipt = dict(schema=G.ASSEMBLY_SCHEMA, production_pins=True, status="CANDIDATE",
                           manifest_sha256=b["tiers_pins_sha256"], host=h, guard_job=b["guard_job"])
            receipt.update((receipt_over or {}).get(name, {}))
            H.write(target / "assembly-receipt.json", H.canonical(receipt) + "\n")
    repo = site.tmp / "repo-full"
    if not repo.exists():
        H.git_repo(repo, files={"reports/explore/k4s-confirm/README": b"study\n", G.END_JOB_REL: end_job_bytes()})
        site.mp.setattr(G, "REPO_FULL", str(repo))
    return H.git(repo, "rev-parse", "HEAD").stdout.strip()


def build(site, kind="end", attempt=None, bundle=None, extra=(), x=None, host=None):
    h = host or site.host
    if kind == "end":
        attempt = attempt or "end-%s-r00-l00" % h
        x = x or stage(site)
        pf = [] if any(e == "--preflight-verified" for e in extra) else site.verified(h)
        cli = ["build-argv", "--kind", "end", "--host", h, "--attempt", attempt, "--roots-sha256", site.roots_sha,
               "--bundle", bundle or "a00", "--end-job-commit", x] + pf
    else:
        attempt = attempt or "preflight-%s-l00" % h
        stage(site)
        d = site.decl["hosts"][h]
        cli = ["build-argv", "--kind", "preflight", "--host", h, "--attempt", attempt, "--roots-sha256",
               site.roots_sha, "--bundle", bundle or "pf00", "--compare-bundle", "a00",
               "--native", d["base"] + "/inputs/native.so", "--corpus", d["base"] + "/inputs/k4-states.pkl",
               "--hold-seconds", "960" if h == "127x04" else "120"]
    return G.build_argv(G.parser().parse_args(cli + list(extra)), layers=(site.si, site.tool)), attempt


def launch_cli(site, kind, attempt, sha, extra=(), dry=False):
    cli = ["launch", "--host", site.host, "--kind", kind, "--attempt", attempt, "--argv-sha256", sha,
           "--roots-sha256", site.roots_sha]
    if kind == "end":
        proof = site.launch_dir(attempt) / "PREPARE-PROOF.json"
        cli += ["--prepare-proof-sha256", H.sha(proof)] if proof.exists() else site.prepare(kind, attempt)
        cli += site.verified("127x03") + site.verified("127x04")
    else:
        (Path(G.RECEIVE["preflight"]) / site.host / attempt).mkdir(parents=True, exist_ok=True)
    return cli + list(extra) + (["--dry-run"] if dry else [])


def run_launch(site, kind, attempt, sha, dry=False):
    code = G.main(launch_cli(site, kind, attempt, sha, dry=dry), layers=(site.si, site.tool))
    receipt = site.launch_dir(attempt) / "LAUNCH-RECEIPT.json"
    doc = json.loads(receipt.read_text()) if receipt.exists() else None
    job = Path(site.decl["hosts"][site.host]["attempts" if kind == "end" else "preflight"]) / attempt
    if doc and doc.get("launched"):
        limit = time.time() + 15
        while not (job / "STUB-EXIT").exists() and time.time() < limit:
            time.sleep(.2)
    return code, doc, job


# ---------------------------------------------------------------- U5: build-argv

@pytest.mark.parametrize("kind", ["end", "preflight"])
def test_build_argv_output_passes_the_gate_and_launches(site, kind):
    result, attempt = build(site, kind)
    path = site.launch_dir(attempt) / "launch-argv.json"
    data = path.read_bytes()
    argv = json.loads(data)
    ok(result["argv_sha256"] == G.sha_bytes(G.argv_nul(argv)) and result["argv_json_sha256"] == H.sha_bytes(data))
    ok(os.stat(path).st_mode & 0o777 == 0o444 and H.nlink(path) == 1)
    hand, _ = site.argv(kind)
    ok(argv == hand, "build-argv differs from the hand-built gate fixture argv")
    if kind == "end":
        ok(len([t for t in argv[20:] if t.startswith("--")]) == 13 and argv[17] == G.HOST_PYTHON)
        ok(result["end_job"]["sha256"] == site.end_job_sha[site.host])
    code, doc, job = run_launch(site, kind, attempt, result["argv_sha256"])
    ok(code == 0 and doc["launched"] is True, doc and doc["host_gate"]["failures"])
    ok(doc["argv_json_sha256"] == result["argv_json_sha256"] and doc["argv_nul_sha256"] == result["argv_sha256"])
    staged = doc["host_gate"]["staged"]
    ok(staged["end_reference_sha256"] == G.END_REFERENCE_SHA256 and staged["inputs_present"] is True)
    ok((staged["end_job"]["bound"] is True and staged["end_job"]["sha256"] == site.end_job_sha[site.host])
       if kind == "end" else "end_job" not in staged)


def flip(tok, previous):
    """One plausible single-token change of the same shape."""
    if previous == "--hold-seconds":
        return str(int(tok) - 1)                     # an above-minimum hold is a free choice bound only by the pin
    if re.fullmatch(r"[0-9a-f]{64}", tok):
        return tok[:-1] + ("0" if tok[-1] != "0" else "1")
    if re.fullmatch(r"[0-9]+", tok):
        return str(int(tok) + 1)
    if "=" in tok and not tok.startswith("/"):
        return tok + "0"
    return tok + "x"


HOST_ONLY = {"end": {"--end-job-sha256"}, "preflight": {"--native", "--corpus"}}


@pytest.mark.parametrize("kind", ["end", "preflight"])
def test_build_argv_every_single_field_change_refuses(site, kind, capsys):
    """For every token of the built argv: the changed argv, re-pinned, is refused. 05 refuses all but the facts only
    the host can see (END: the END-JOB at HEAD; preflight: the staged native/corpus), which the host program refuses
    before creating the job."""
    result, attempt = build(site, kind)
    path = site.launch_dir(attempt) / "launch-argv.json"
    argv = json.loads(path.read_text())
    ok(run_launch(site, kind, attempt, result["argv_sha256"], dry=True)[0] == 0)
    capsys.readouterr()
    on_host = set()
    for i in range(len(argv)):
        changed = list(argv)
        changed[i] = flip(argv[i], argv[i - 1] if i else None)
        os.chmod(path, 0o644)
        H.write(path, json.dumps(changed), 0o444)
        sha = G.sha_bytes(G.argv_nul(changed))
        try:
            run_launch(site, kind, attempt, sha, dry=True)
        except (G.GateRefusal, site.si.Refusal):
            continue
        finally:
            capsys.readouterr()
        code, doc, job = run_launch(site, kind, attempt, sha)
        ok(code == 3 and doc["launched"] is False and not job.exists(), (i, argv[i], doc and doc["host_gate"]))
        ok(any(f.startswith("staged:") or f.startswith("END-JOB") for f in doc["host_gate"]["failures"]),
           doc["host_gate"]["failures"])
        on_host.add(argv[i - 1])
        receipt = site.launch_dir(attempt) / "LAUNCH-RECEIPT.json"      # test-only: let the next probe launch
        os.chmod(receipt, 0o644)
        os.unlink(receipt)
    ok(on_host == HOST_ONLY[kind], on_host)


@pytest.mark.parametrize("case,needle", [
    ("undeclared-bundle", "Not a declared RC-6 bundle"),
    ("receipt-synthetic", "not a production receipt"),
    ("receipt-host", "not a production receipt"),
    ("receipt-manifest", "not a production receipt"),
    ("sidecar", "tiers-pins.sha256 differs"),
    ("manifest-sha", "SHA-256"),
    ("no-evidence", "END evidence of record"),
    ("job-other-evidence", "does not bind"),
    ("job-missing", "not tracked"),
    ("job-commit-short", "40 hex"),
    ("pf-other-host", "this host's --preflight-verified only"),
    ("pf-identity", "identity paths differ"),
    ("pf-schema", "not this host's verified preflight"),
    ("end-with-native", "this host's --preflight-verified only"),
    ("roots-sha", "SHA"),
    ("attempt-host", "Attempt name"),
    ("exists", "exists"),
], ids=lambda x: x if isinstance(x, str) and " " not in x else None)
def test_build_argv_refusals(site, case, needle):
    over, extra, bundle, x, attempt = {}, [], None, None, None
    x = stage(site)
    a00 = Path(G.STAGING_BUNDLES) / "a00"
    if case == "undeclared-bundle":
        bundle = "a99"
    elif case.startswith("receipt-"):
        field = dict(synthetic=dict(production_pins=False), host=dict(host="127x04"),
                     manifest=dict(manifest_sha256="0" * 64))[case.split("-", 1)[1]]
        stage(site, receipt_over={"a00": field})
    elif case == "sidecar":
        os.chmod(a00 / "tiers-pins.sha256", 0o644)
        H.write(a00 / "tiers-pins.sha256", "0" * 64 + "  tiers-pins.json\n")
    elif case == "manifest-sha":
        os.chmod(a00 / "tiers-pins.json", 0o644)
        H.write(a00 / "tiers-pins.json", (a00 / "tiers-pins.json").read_text() + " ")
    elif case == "no-evidence":
        site.mp.setattr(G, "END_EVIDENCE_REL", "k4s-end-evidence/other.json")
    elif case == "job-other-evidence":
        repo = Path(G.REPO_FULL)
        H.write(repo / G.END_JOB_REL, end_job_bytes(end_evidence_sha256="1" * 64))
        H.git(repo, "commit", "-qam", "other job")
        x = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    elif case == "job-missing":
        x = H.git_repo(site.tmp / "repo-empty", files={"README": b"x\n"})[0]
        site.mp.setattr(G, "REPO_FULL", str(site.tmp / "repo-empty"))
    elif case == "job-commit-short":
        x = x[:12]
    elif case == "pf-other-host":
        extra = site.verified("127x04")
    elif case == "pf-identity":
        extra = site.verified("127x03", identity=dict(native="/elsewhere/native.so", _merge=True))
    elif case == "pf-schema":
        extra = site.verified("127x03", schema="clasher.k4s.end-preflight-verified.v2")
    elif case == "end-with-native":
        extra = ["--native", "/x"]
    elif case == "roots-sha":
        site.roots_sha = "0" * 64
    elif case == "attempt-host":
        attempt = "end-127x04-r00-l00"
    elif case == "exists":
        build(site, x=x)
    raises((G.GateRefusal, site.si.Refusal), build, site, bundle=bundle, x=x, extra=extra, attempt=attempt,
           match=needle)
    if case != "exists":
        ok(not (site.launch_dir(attempt or "end-127x03-r00-l00") / "launch-argv.json").exists())


def test_build_argv_preflight_inputs(site):
    raises(G.GateRefusal, build, site, "preflight", extra=["--hold-seconds", "119"], match="minimum")
    for drop in ("--native", "--corpus", "--compare-bundle", "--hold-seconds"):
        stage(site)
        d = site.decl["hosts"]["127x03"]
        cli = ["build-argv", "--kind", "preflight", "--host", "127x03", "--attempt", "preflight-127x03-l01",
               "--roots-sha256", site.roots_sha, "--bundle", "pf00", "--compare-bundle", "a00", "--native",
               d["base"] + "/inputs/native.so", "--corpus", d["base"] + "/inputs/k4-states.pkl", "--hold-seconds", "120"]
        i = cli.index(drop)
        del cli[i:i + 2]
        raises(G.GateRefusal, G.build_argv, G.parser().parse_args(cli), layers=(site.si, site.tool), match="required")
    raises(G.GateRefusal, build, site, "preflight", attempt="preflight-127x03-l02", bundle="a01",
           match="-pfNN guard job")
    result, attempt = build(site, "preflight", attempt="preflight-127x03-l03", extra=["--diagnostic-preflight"])
    argv = json.loads((site.launch_dir(attempt) / "launch-argv.json").read_text())
    ok(result["mode"] == "diagnostic" and argv[-1] == "--no-reference-work")
    result, attempt = build(site, "preflight", attempt="preflight-127x03-l04", extra=["--end-job-commit", stage(site)])
    argv = json.loads((site.launch_dir(attempt) / "launch-argv.json").read_text())
    ok(argv[argv.index("--end-job-sha256") + 1] == site.end_job_sha["127x03"])


def test_build_argv_launch_dir_existing_or_aliased(site):
    attempt = "end-127x03-r00-l00"
    site.launch_dir(attempt).mkdir(parents=True)             # e.g. made first by the verifier's --prepare
    result, _ = build(site)
    ok(result["created"] == dict(host_created=False, attempt_created=False))
    elsewhere = site.tmp / "foreign"
    elsewhere.mkdir()
    os.symlink(elsewhere, Path(G.LAUNCH_BASE) / "127x04")
    site.host = "127x04"
    raises(site.si.Refusal, build, site, host="127x04")
    ok(os.listdir(elsewhere) == [])


# ---------------------------------------------------------------- U6: prepare-preflight-receive

def test_prepare_preflight_receive_then_build_and_launch(site):
    site.host = "127x03"
    shutil.rmtree(Path(G.RECEIVE["preflight"]).parent, ignore_errors=True)
    Path(G.RECEIVE["preflight"]).parent.mkdir()
    a = G.parser().parse_args(["prepare-preflight-receive", "--host", "127x03", "--attempt", "preflight-127x03-l00"])
    made = G.prepare_preflight_receive(a, layers=(site.si, site.tool))
    root = Path(G.RECEIVE["preflight"]) / "127x03" / "preflight-127x03-l00"
    ok(made["receive"] == str(root) and os.listdir(root) == [] and os.stat(root).st_mode & 0o777 == 0o700)
    ok(made["created"] == dict(base=True, host=True) and made["mode"] == "700")
    raises(site.si.Refusal, G.prepare_preflight_receive, a, layers=(site.si, site.tool))   # never reused
    result, attempt = build(site, "preflight")
    code = G.main(["launch", "--host", "127x03", "--kind", "preflight", "--attempt", attempt, "--argv-sha256",
                   result["argv_sha256"], "--roots-sha256", site.roots_sha], layers=(site.si, site.tool))
    ok(code == 0)


@pytest.mark.parametrize("case", ["host-symlink", "base-file", "wrong-name", "end-name"])
def test_prepare_preflight_receive_refusals(site, case):
    base = Path(G.RECEIVE["preflight"])
    shutil.rmtree(base, ignore_errors=True)
    attempt = "preflight-127x03-l00"
    if case == "host-symlink":
        base.mkdir(parents=True)
        (site.tmp / "foreign").mkdir()
        os.symlink(site.tmp / "foreign", base / "127x03")
    elif case == "base-file":
        H.write(base, b"")
    elif case == "wrong-name":
        attempt = "preflight-127x04-l00"
    else:
        attempt = "end-127x03-r00-l00"
    a = G.parser().parse_args(["prepare-preflight-receive", "--host", "127x03", "--attempt", attempt])
    raises((G.GateRefusal, site.si.Refusal), G.prepare_preflight_receive, a, layers=(site.si, site.tool))
    ok(case != "host-symlink" or os.listdir(site.tmp / "foreign") == [])


# ---------------------------------------------------------------- U7: verifier --prepare writes PREPARE-PROOF

@needs_debug
def test_verifier_prepare_writes_the_proof_s7_accepts(site, monkeypatch):
    vsi = V.load_si(str(ROOT))                                 # before the test-only receive-base patch
    recv = Path(G.RECEIVE["end"]).parent
    for name, value in (("BASE", str(recv)), ("RECEIVE_BASE", G.RECEIVE["end"]), ("LAUNCH_BASE", G.LAUNCH_BASE)):
        monkeypatch.setattr(V, name, value)
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 19)
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: {63})
    result, attempt = build(site)                              # build-argv first: the launch dir already exists
    root = G.RECEIVE["end"] + "/127x03/" + attempt
    import io
    import contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ok(V.main(["--receive", root, "--prepare"], si=vsi) == 0)
    printed = json.loads(out.getvalue())
    proof = site.launch_dir(attempt) / "PREPARE-PROOF.json"
    ok(proof.read_bytes() == (Path(root) / "PREPARED.json").read_bytes() and H.nlink(proof) == 1)
    ok(printed["prepare_proof_sha256"] == H.sha(proof) and printed["prepare_proof"] == str(proof))
    ok(os.stat(proof).st_mode & 0o777 == 0o444)
    time.sleep(1.1)                                            # the gate requires the proof to predate `now`
    cli = ["launch", "--host", "127x03", "--kind", "end", "--attempt", attempt, "--argv-sha256",
           result["argv_sha256"], "--roots-sha256", site.roots_sha, "--prepare-proof-sha256", printed[
               "prepare_proof_sha256"]] + site.verified("127x03") + site.verified("127x04")
    code = G.main(cli, layers=(site.si, site.tool))
    receipt = json.loads((site.launch_dir(attempt) / "LAUNCH-RECEIPT.json").read_text())
    ok(code == 0 and receipt["receive"]["prepare_proof_sha256"] == printed["prepare_proof_sha256"])


@needs_debug
@pytest.mark.parametrize("case", ["proof-exists", "no-launch-base", "launch-host-symlink", "receive-exists"])
def test_verifier_prepare_refuses_before_creating_anything(tmp_path, monkeypatch, case):
    si = V.load_si(str(ROOT))
    base, launch = tmp_path / "recv", tmp_path / "end-launch"
    for name, value in (("BASE", str(base)), ("RECEIVE_BASE", str(base / "end-received")),
                        ("LAUNCH_BASE", str(launch))):
        monkeypatch.setattr(V, name, value)
    base.mkdir()
    attempt = "end-127x03-r00-l00"
    if case == "proof-exists":
        H.write(launch / "127x03" / attempt / "PREPARE-PROOF.json", b"{}")
    elif case == "launch-host-symlink":
        launch.mkdir()
        (tmp_path / "foreign").mkdir()
        os.symlink(tmp_path / "foreign", launch / "127x03")
    elif case == "receive-exists":
        launch.mkdir()
        (base / "end-received" / "127x03" / attempt).mkdir(parents=True)
    raises(si.Refusal, V.prepare, si, str(base / "end-received" / "127x03" / attempt))
    ok(case == "receive-exists" or not (base / "end-received" / "127x03" / attempt).exists())
    ok(case != "receive-exists" or not (launch / "127x03").exists())
    ok(case != "launch-host-symlink" or os.listdir(tmp_path / "foreign") == [])


# ---------------------------------------------------------------- L1: host program, staged runtime / END-JOB

def relaunch_with_job(site, job):
    """Commit a different END-JOB at HEAD of the host's --repository and pin the argv to `job` bytes' SHA."""
    repo = Path(site.decl["hosts"]["127x03"]["repository"])
    if job is not None:
        os.chmod(repo / G.END_JOB_REL, 0o644)
        H.write(repo / G.END_JOB_REL, job)
        H.git(repo, "commit", "-qam", "job")
    else:
        H.git(repo, "rm", "-q", G.END_JOB_REL)
        H.git(repo, "commit", "-qm", "no job")


@pytest.mark.parametrize("case,needle", [
    ("job-changed-at-head", "staged:"),
    ("job-absent-at-head", "staged:"),
    ("job-other-evidence", "does not bind"),
    ("job-other-manifest", "does not bind"),
    ("end-reference-changed", "runtime:"),
    ("runtime-symlink", "staged:"),
    ("native-missing", "staged:"),
    ("corpus-hard-link", "staged:"),
])
def test_host_l1_refusals(site, case, needle):
    argv, attempt = site.argv()
    d = site.decl["hosts"]["127x03"]
    if case == "job-changed-at-head":
        relaunch_with_job(site, end_job_bytes(declared_by="someone else"))
    elif case == "job-absent-at-head":
        relaunch_with_job(site, None)
    elif case in ("job-other-evidence", "job-other-manifest"):
        job = end_job_bytes(**({"end_evidence_sha256": "1" * 64} if case == "job-other-evidence"
                               else {"k4s_manifest_sha256": "1" * 64}))
        relaunch_with_job(site, job)
        argv[argv.index("--end-job-sha256") + 1] = H.sha_bytes(job)
    elif case == "end-reference-changed":
        H.write(Path(d["runtime"]) / G.END_REFERENCE_REL, "import time\ntime.sleep(3)\n")
    elif case == "runtime-symlink":
        moved = Path(d["base"]) / "moved-runtime"
        shutil.move(d["runtime"], moved)
        os.symlink(moved, d["runtime"])
    elif case == "native-missing":
        os.unlink(Path(d["base"]) / "inputs/native.so")
    else:
        os.link(Path(d["base"]) / "inputs/k4-states.pkl", site.tmp / "alias")
    code, doc, job = site.launch(argv=argv, attempt=attempt)
    refused_on_host(code, doc, job, needle)


def test_host_l1_preflight_job_pin_optional_and_checked(site):
    code, doc, _ = site.launch("preflight")
    ok(code == 0 and "end_job" not in doc["host_gate"]["staged"])
    argv, attempt = site.argv("preflight", attempt="preflight-127x03-l01", **{"--end-job-sha256": "2" * 64})
    code, doc, job = site.launch("preflight", argv=argv, attempt=attempt)
    refused_on_host(code, doc, job, "staged:")
    argv, attempt = site.argv("preflight", attempt="preflight-127x03-l02",
                              **{"--end-job-sha256": site.end_job_sha["127x03"]})
    code, doc, _ = site.launch("preflight", argv=argv, attempt=attempt)
    ok(code == 0 and doc["host_gate"]["staged"]["end_job"]["bound"] is True)


@pytest.mark.parametrize("option,value,needle", [
    ("python", "/usr/bin/python3", "host python"),
    ("--sd1-manifest-sha256", "5" * 64, "SD1"),
    ("--end-evidence-sha256", "e" * 64, "evidence of record"),
    ("--end-evidence", "/end-evidence.json", "S4 evidence copy"),
    ("--end-job-sha256", "4" * 63, "SHA-256"),
])
def test_validate_argv_r4_pins(site, option, value, needle):
    argv, attempt = site.argv()
    if option == "python":
        argv[argv.index(G.HOST_PYTHON)] = value
    elif option == "--end-evidence":
        argv[argv.index(option) + 1] = argv[argv.index("--bundle") + 1] + value
    else:
        argv[argv.index(option) + 1] = value
    raises(G.GateRefusal, G.validate_argv, site.si, argv, "end", "127x03", attempt, site.decl["hosts"], match=needle)
    pf, pf_attempt = site.argv("preflight", **{"--corpus-inventory-sha256": "1" * 64})
    raises(G.GateRefusal, G.validate_argv, site.si, pf, "preflight", "127x03", pf_attempt, site.decl["hosts"],
           match="corpus inventory")


# ---------------------------------------------------------------- U12: coordinator-file templates

def filled(name, **values):
    doc = json.loads((TEMPLATES / name).read_text())
    doc.pop("_template", None)
    doc.update(values)
    return doc


def test_templates_have_exactly_the_gate_schemas():
    bus = json.loads((TEMPLATES / "BUS-DECISION.template.json").read_text())
    rep = json.loads((TEMPLATES / "REPEAT-RULING.template.json").read_text())
    ok(bus["schema"] == G.BUS_DECISION_SCHEMA and bus["decision"] == "proceed")
    ok(set(bus) - {"_template"} == {"schema", "decision", "preflight_attempt", "receipt_manifest_sha256",
                                     "coordinator_ref"})
    ok(rep["schema"] == G.REPEAT_RULING_SCHEMA and set(rep) - {"_template"} == {"schema", "host", "attempt",
                                                                                  "coordinator_ref"})
    raises(G.GateRefusal, G.check_bus_decision, filled("BUS-DECISION.template.json"), "preflight-127x04-l00", "a" * 64)
    raises(G.GateRefusal, G.check_repeat_ruling, filled("REPEAT-RULING.template.json"), "127x03", "end-127x03-r00-l01")


def test_bus_decision_template_filled_passes_and_each_field_change_refuses():
    good = filled("BUS-DECISION.template.json", preflight_attempt="preflight-127x04-l00",
                  receipt_manifest_sha256="a" * 64, coordinator_ref="COORDINATOR 2026-10-13 ref")
    ok(G.check_bus_decision(good, "preflight-127x04-l00", "a" * 64) == good)
    for key, value in (("schema", "x"), ("decision", "stop"), ("preflight_attempt", "preflight-127x04-l01"),
                       ("receipt_manifest_sha256", "b" * 64), ("coordinator_ref", " ")):
        raises(G.GateRefusal, G.check_bus_decision, dict(good, **{key: value}), "preflight-127x04-l00", "a" * 64)


def test_repeat_ruling_template_filled_passes_and_each_field_change_refuses():
    good = filled("REPEAT-RULING.template.json", host="127x03", attempt="end-127x03-r00-l01",
                  coordinator_ref="COORDINATOR 2026-10-13 ref")
    ok(G.check_repeat_ruling(good, "127x03", "end-127x03-r00-l01") == good)
    for key, value in (("schema", "x"), ("host", "127x04"), ("attempt", "end-127x03-r00-l02"), ("coordinator_ref", "")):
        raises(G.GateRefusal, G.check_repeat_ruling, dict(good, **{key: value}), "127x03", "end-127x03-r00-l01")


# ---------------------------------------------------------------- constants agree across components

def test_r4_constants_agree_with_the_preflight_and_s4():
    import k4s_a6_builder as J
    import k4s_end_preflight as S5
    ok(G.SD1_MANIFEST_SHA256 == S5.FROZEN_CLOSURE["reports/explore/k4s-confirm/SD1-MANIFEST.json"])
    ok(G.END_REFERENCE_SHA256 == S5.FROZEN_CLOSURE[G.END_REFERENCE_REL])
    ok(G.ASSEMBLY_SCHEMA == S5.ASSEMBLY_SCHEMA and G.END_EVIDENCE_SHA256 == J.END_EVIDENCE_SHA256)
    ok(G.END_JOB_REL == J.END_JOB_REL and G.END_JOB_SCHEMA == J.JOB_SCHEMA and G.REPO_FULL == J.REPO_FULL)
    ok(all(S5.FROZEN_CLOSURE[rel] == pin for rel, pin in J.FROZEN_PINS.items()))
    ok(G.K4S_MANIFEST_SHA256 == J.K4S_MANIFEST_SHA256 == S5.K4S_MANIFEST_SHA256)
    s4 = Path(G.RUNNER) / "end-prep" / "b3-r5" / "assemble_fleet_reference.py"
    if s4.exists():                                           # S4 EVIDENCE_NAME = EVIDENCE_DIR + "/" + EVIDENCE_FILE
        text = s4.read_text()
        ok('EVIDENCE_DIR = "k4s-end-evidence"' in text and 'EVIDENCE_FILE = "end-evidence.json"' in text)
        ok(G.END_EVIDENCE_REL == "k4s-end-evidence/end-evidence.json")


# ---------------------------------------------------------------- L6: S5 pins DELTA-MANIFEST.json

@pytest.mark.parametrize("case", ["absent", "changed", "hard-link"])
def test_s5_pre_import_pins_require_the_pinned_delta_manifest(tmp_path, monkeypatch, case):
    import s5_fixture as X
    import k4s_end_preflight as S5
    env = X.build(tmp_path, monkeypatch)
    delta = Path(env.runtime) / S5.DELTA_MANIFEST_REL
    if case == "absent":
        os.unlink(delta)
    elif case == "changed":
        os.chmod(delta, 0o644)
        H.write(delta, b'{"synthetic": "other DELTA"}\n')
    else:
        os.link(delta, tmp_path / "delta-alias")
    code, result, seal = X.go(env)
    rows = {c["name"]: c for c in result["checks"]}
    ok(code == 1 and seal["status"] == "failed" and rows["pre_import_pins"]["passed"] is False, rows["pre_import_pins"])
    ok("DELTA-MANIFEST" in str(rows["pre_import_pins"].get("error")), rows["pre_import_pins"])
    ok(rows.get("frozen_import", {}).get("passed") is not True)


def test_s5_delta_pin_recorded_when_present(tmp_path, monkeypatch):
    import s5_fixture as X
    import k4s_end_preflight as S5
    env = X.build(tmp_path, monkeypatch)
    code, result, _ = X.go(env)
    row = {c["name"]: c for c in result["checks"]}["pre_import_pins"]
    ok(row["passed"] is True and row["delta_manifest_sha256"] == S5.DELTA_MANIFEST_SHA256)


P_PRIME = "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb"


@pytest.mark.skipif(not (Path(G.REPO_FULL) / ".git").is_dir(), reason="05 full clone not on this machine")
def test_production_pins_equal_the_committed_blobs_at_p_prime():
    """Every r4 production pin is the blob at P' of the 05 full clone (gated git reader, read only)."""
    import k4s_a6_builder as J
    import k4s_end_preflight as S5
    si, _ = G.load_layers(str(ROOT))
    g = si.GitRepo(work_tree=G.REPO_FULL)
    for rel, pin in ((S5.DELTA_MANIFEST_REL, S5.DELTA_MANIFEST_SHA256), (J.END_EVIDENCE_REL, G.END_EVIDENCE_SHA256),
                     ("reports/explore/k4s-confirm/SD1-MANIFEST.json", G.SD1_MANIFEST_SHA256),
                     (G.END_REFERENCE_REL, G.END_REFERENCE_SHA256), (J.K4S_MANIFEST_REL, G.K4S_MANIFEST_SHA256)):
        P = si.Policy("127x05", [si.Role("repo", G.REPO_FULL, "read", 16 << 20, exact=(rel,))])
        si.git_show_file(P, "repo", g, P_PRIME, rel, expected_sha256=pin)
    ok(J.EVIDENCE_COMMIT == P_PRIME)
    P = si.Policy("127x05", [si.Role("repo", G.REPO_FULL, "read", 16 << 20, exact=(J.END_EVIDENCE_REL,))])
    evidence = si.loads_strict(si.git_show_file(P, "repo", g, P_PRIME, J.END_EVIDENCE_REL))
    ok(evidence["completion"]["sha256"] == J.COMPLETION_SHA256)
