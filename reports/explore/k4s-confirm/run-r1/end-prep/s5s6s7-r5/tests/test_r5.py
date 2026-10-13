"""r5 (SOL-REVIEW-END-INTEGRATION-r1): U4 host interpreter and finding 1 (U8 builder pins).

U4: the END/preflight interpreter S7 pins and build-argv emits is exactly the one P' runtime.sh executes
(`/mpac/sdicks02/repos/clasher/.venv/bin/python -B`), never the bare uv binary.
U8: the builder's self-check is bound to the ADOPTED S9 (s3s9s10-r5) and the PRODUCTION runtime manifest; the
constants are tied to the committed record `builder-proof/ADOPTED-PINS.json` (always, portable) and, when present,
to the sibling package's SHA256SUMS, its S9-FINAL marker, the RUNTIME-r5-READY marker and the real manifest bytes."""
import ast
import hashlib
import json
import os
from pathlib import Path

import pytest

import k4s_end_launch_gate as G
from helpers import ROOT, ok, raises
from test_s7_gate import Site

VENV_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"               # COORDINATOR 10:33Z U4 ruling
BARE_UV = "/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"   # r4 value, not ratified
REAL_HOST_PYTHON = G.HOST_PYTHON                                            # before any fixture patches it
P_PRIME = "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb"
SIBLING_A = ROOT.parent / "s3s9s10-r5"


@pytest.fixture
def site(tmp_path, monkeypatch):
    return Site(tmp_path, monkeypatch)


# ---------------------------------------------------------------- U4: the host interpreter

def test_u4_host_python_is_the_runtime_sh_venv_interpreter():
    ok(REAL_HOST_PYTHON == VENV_PYTHON, REAL_HOST_PYTHON)
    ok(G.RUNTIME_SH_REL == "reports/explore/k4s-confirm/runtime.sh")


@pytest.mark.parametrize("kind", ["end", "preflight"])
def test_u4_compose_argv_emits_the_venv_python_with_exactly_b(kind):
    d = dict(attempts="/b/attempts", preflight="/b/preflight", tools="/b/tools", runtime="/b/runtime-x",
             repository="/b/repository")
    bundle = dict(path="/b/bundles/x", tiers_pins_sha256="a" * 64)
    attempt = "end-127x03-r00-l00" if kind == "end" else "preflight-127x03-l00"
    argv = G.compose_argv(kind, "127x03", attempt, d, bundle, "/b/n.so", "/b/c.pkl", end_job_sha256="b" * 64,
                          compare=bundle, hold="120")
    i = argv.index("env") + 1 + len(G.ENV_REQUIRED)
    ok(argv[i:i + 2] == [VENV_PYTHON, "-B"], argv[i:i + 3])
    ok(BARE_UV not in argv and argv.count(VENV_PYTHON) == 1 and argv.count("-B") == 1)


def test_u4_validate_argv_accepts_only_the_venv_python(site):
    site.mp.setattr(G, "HOST_PYTHON", REAL_HOST_PYTHON)
    for kind in ("end", "preflight"):
        argv, attempt = site.argv(kind)
        G.validate_argv(site.si, argv, kind, "127x03", attempt, site.decl["hosts"])
        for bad in (BARE_UV, VENV_PYTHON + "3", VENV_PYTHON + "3.12", "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python",
                    "/mpac/sdicks02/repos/clasher/.venv/bin/../bin/python", "/usr/bin/python3"):
            changed = list(argv)
            changed[changed.index(REAL_HOST_PYTHON)] = bad
            raises(G.GateRefusal, G.validate_argv, site.si, changed, kind, "127x03", attempt, site.decl["hosts"],
                   match="host python")
        for flag, needle in (("-O", "optimizer"), ("-I", "optimizer"), ("-BO", "exactly -B"), ("-b", "exactly -B"),
                             ("-BB", "exactly -B")):
            changed = list(argv)
            changed[changed.index(REAL_HOST_PYTHON) + 1] = flag
            raises(G.GateRefusal, G.validate_argv, site.si, changed, kind, "127x03", attempt, site.decl["hosts"],
                   match=needle)


@pytest.mark.skipif(not os.path.isdir(G.REPO_FULL + "/.git"), reason="05 full clone absent (portable copy)")
def test_u4_runtime_sh_at_p_prime_executes_exactly_host_python():
    """Integration (read only): the frozen launcher at P' ends with `exec <HOST_PYTHON> -B "$@"`."""
    si, _ = G.load_layers(str(ROOT))
    g = si.GitRepo(work_tree=G.REPO_FULL)
    P = si.Policy("127x05", [si.Role("repo", G.REPO_FULL, "read", 1 << 20, exact=(G.RUNTIME_SH_REL,))])
    lines = si.git_show_file(P, "repo", g, P_PRIME, G.RUNTIME_SH_REL).decode().splitlines()
    execs = [l for l in lines if l.startswith("exec ")]
    ok(execs == ['exec %s -B "$@"' % REAL_HOST_PYTHON] and lines[-1] == execs[0], execs)


def _assigned_literal(path, name):
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == [name]:
            return ast.literal_eval(node.value)
    raise AssertionError("%s not assigned in %s" % (name, path))


@pytest.mark.skipif(not (SIBLING_A / "s10_stage_host.py").exists(), reason="sibling s3s9s10-r5 absent")
def test_u4_s10_probe_interpreter_is_the_same_string():
    ok(_assigned_literal(SIBLING_A / "s10_stage_host.py", "HOST_PYTHON") == REAL_HOST_PYTHON)


# ---------------------------------------------------------------- U8 / finding 1: builder bound to the adopted S9

RECORD = ROOT / "ADOPTED-S9-RUNTIME.json"
ADOPTED_S9 = G.RUNNER + "/end-prep/s3s9s10-r5/s9_end_runtime.py"
PRODUCTION_RUNTIME = G.RUNNER + "/end-staging/runtime-98566c032d0b"


def record():
    return json.loads(RECORD.read_text())


def sha_path(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_u8_builder_constants_equal_the_adopted_record():
    """Portable: the builder's S9 and runtime-manifest pins are exactly the committed adoption record (S9-FINAL +
    RUNTIME-r5-READY), the adopted package's S9 and the production runtime path; the record binds the manifest to
    that S9 (script_sha256), P' and the frozen interpreter."""
    import k4s_a6_builder as J
    r = record()
    ok(r["schema"] == "clasher.k4s.end-job-builder-adopted-pins.v1")
    ok(J.S9_PATH == r["s9"]["path"] == ADOPTED_S9, J.S9_PATH)
    ok(J.S9_SHA256 == r["s9"]["sha256"] == r["runtime"]["manifest_script_sha256"])
    ok(J.FROZEN_RUNTIME == r["runtime"]["path"] == PRODUCTION_RUNTIME, J.FROZEN_RUNTIME)
    ok(J.FROZEN_RUNTIME_MANIFEST_SHA256 == r["runtime"]["manifest_sha256"])
    ok(r["runtime"]["manifest_commit"] == J.EVIDENCE_COMMIT == P_PRIME and r["runtime"]["manifest_python"]
       == J.FROZEN_PYTHON)
    ok(r["s9_final_marker"]["path"] == G.RUNNER + "/end-prep/s3s9s10-r5/S9-FINAL"
       and r["runtime_ready_marker"]["path"] == G.RUNNER + "/end-staging/RUNTIME-r5-READY")


@pytest.mark.skipif(not (SIBLING_A / "SHA256SUMS").exists(), reason="adopted s3s9s10-r5 not beside this package")
def test_u8_adopted_record_matches_the_sibling_s9_package():
    r = record()
    sums = dict(reversed(line.split()) for line in (SIBLING_A / "SHA256SUMS").read_text().splitlines()
                if len(line.split()) == 2)
    ok(sums.get("s9_end_runtime.py") == r["s9"]["sha256"] == sha_path(SIBLING_A / "s9_end_runtime.py"))
    ok(os.path.getsize(SIBLING_A / "s9_end_runtime.py") == r["s9"]["size"])
    marker = SIBLING_A / "S9-FINAL"
    ok(marker.is_file() and sha_path(marker) == r["s9_final_marker"]["sha256"])


@pytest.mark.skipif(not Path(PRODUCTION_RUNTIME, "runtime-manifest.json").is_file(),
                    reason="production runtime not on this machine")
def test_u8_adopted_record_matches_the_production_runtime_manifest():
    r = record()
    manifest = Path(PRODUCTION_RUNTIME, "runtime-manifest.json")
    ok(sha_path(manifest) == r["runtime"]["manifest_sha256"])
    doc = json.loads(manifest.read_bytes())
    ok(doc["script_sha256"] == r["s9"]["sha256"] and doc["commit"] == P_PRIME
       and doc["git_members_sha256"] == r["runtime"]["manifest_git_members_sha256"])
    marker = Path(r["runtime_ready_marker"]["path"])
    ok(marker.is_file() and sha_path(marker) == r["runtime_ready_marker"]["sha256"])


def test_u8_recorded_proof_is_of_these_bytes():
    """The recorded builder-proof/ was produced by THIS builder against the adopted S9 and the production manifest."""
    r = record()
    proof = json.loads((ROOT / "builder-proof" / "SELF-CHECK.json").read_text())
    build = json.loads((ROOT / "builder-proof" / "BUILD.json").read_text())
    ok(proof["ok"] is True and proof["builder_sha256"] == build["builder_sha256"] == sha_path(ROOT / "k4s_a6_builder.py"))
    ok(proof["s9_equivalence"]["s9"] == r["s9"]["path"] and proof["s9_equivalence"]["s9_sha256"] == r["s9"]["sha256"])
    ok(proof["frozen"]["runtime"] == r["runtime"]["path"]
       and proof["frozen"]["runtime_manifest_sha256"] == r["runtime"]["manifest_sha256"]
       and proof["frozen"]["runtime_manifest_script_sha256"] == r["s9"]["sha256"])
    ok(proof["s9_equivalence"]["git_members_sha256"] == r["runtime"]["manifest_git_members_sha256"])
    ok(proof["end_job_sha256"] == sha_path(ROOT / "builder-proof" / "END-JOB.json")
       and proof["scratch_diff"] == ["reports/explore/k4s-confirm/end/END-JOB.json"])
