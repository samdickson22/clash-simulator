"""r4 (INTEGRATION-AUDIT-r1 U8): the END-JOB builder (k4s_a6_builder.py). Synthetic repositories under tmp_path for every
guard; one integration test runs the REAL build + self-check (frozen end_evidence/end_job and S9 equivalence) against
the 05 full clone at P' when it is present (read only; scratch copy of .git in /dev/shm, removed). Test names avoid
the END-claim name families because pytest's tmp_path embeds them."""
import ast
import io
import contextlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

import helpers as H
import k4s_a6_builder as J
from helpers import ROOT, ok, raises

STUDY = J.STUDY_DIR


def commit_all(repo, message):
    H.git(repo, "add", "-A")
    H.git(repo, "commit", "-qm", message)
    return H.git(repo, "rev-parse", "HEAD").stdout.strip()


class World:
    """A synthetic repository shaped like k4s-end-r1 at P': C1 commits plan/completion/ledger/inventory/manifest, C2
    adds end-evidence.json binding them. Constants are monkeypatched to its SHAs (test-only route)."""

    def __init__(self, tmp, mp, hosts=("127x03", "127x04"), study="PREREG-K4S", plan_path=None, item_over=None):
        self.tmp, self.mp = tmp, mp
        self.si = J.load_si(str(ROOT))
        self.repo = repo = tmp / "repo"
        repo.mkdir()
        H.git(repo, "init", "-q")
        files = {"plan.json": json.dumps(dict(study=study)).encode(),
                 "run-r1/completion-v2/REPORTING-COMPLETION.json": json.dumps(dict(
                     reporting_complete=True, outcomes_sealed=True,
                     counted_host_phases={h: ["reporting-1"] for h in hosts})).encode(),
                 "run-r1/ledger/blind-ledger-final.json": b'{"sealed": true}\n',
                 "run-r1/completion-v2/counted-inventory.json": b'{"outcomes_sealed": true}\n',
                 "mac/K4S-MAC-MANIFEST.json": b'{"synthetic": "manifest"}\n'}
        for rel, data in files.items():
            H.write(repo / STUDY / rel, data)
        self.c1 = commit_all(repo, "c1")
        items = {}
        for key, rel in (("plan", "plan.json"), ("completion", "run-r1/completion-v2/REPORTING-COMPLETION.json"),
                         ("blind_ledger", "run-r1/ledger/blind-ledger-final.json"),
                         ("counted_inventory", "run-r1/completion-v2/counted-inventory.json")):
            items[key] = dict(commit=self.c1, path=rel, repository_path=STUDY + "/" + rel,
                              sha256=H.sha_bytes(files[rel]))
        for key, over in (item_over or {}).items():
            items[key].update(over)
        evidence = dict(schema=J.EVIDENCE_SCHEMA, kind="counted-reporting", phases=[], **items)
        self.evidence = (json.dumps(evidence, indent=1, sort_keys=True) + "\n").encode()
        H.write(repo / J.END_EVIDENCE_REL, self.evidence)
        self.c2 = commit_all(repo, "c2")
        mp.setattr(J, "END_EVIDENCE_SHA256", H.sha_bytes(self.evidence))
        mp.setattr(J, "K4S_MANIFEST_SHA256", H.sha_bytes(files["mac/K4S-MAC-MANIFEST.json"]))
        mp.setattr(J, "COMPLETION_SHA256", items["completion"]["sha256"])
        mp.setattr(J, "REPO_FULL", str(repo))
        mp.setattr(J, "EVIDENCE_COMMIT", self.c2)
        self.out = str(tmp / "out")

    def build(self, declared_by="tester", out=None, commit=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return J.build(self.si, declared_by, out or self.out, root=str(self.repo), commit=commit or self.c2)


def test_build_writes_exactly_the_frozen_fields(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    job, digest = w.build()
    data = Path(w.out, "END-JOB.json").read_bytes()
    ok(H.sha_bytes(data) == digest and data == J.job_bytes(job) and tuple(sorted(json.loads(data))) == J.JOB_FIELDS)
    ok(job["schema"] == J.JOB_SCHEMA and job["study"] == "PREREG-K4S" and job["counted_hosts"] == ["127x03", "127x04"])
    ok(job["end_evidence_sha256"] == J.END_EVIDENCE_SHA256 and job["completion_sha256"] == J.COMPLETION_SHA256)
    ok(job["k4s_manifest_sha256"] == J.K4S_MANIFEST_SHA256 and job["declared_by"] == "tester")
    receipt = json.loads(Path(w.out, "BUILD.json").read_text())
    ok(receipt["end_job_sha256"] == digest and receipt["sources"]["commit"] == w.c2)
    ok(receipt["sources"]["plan"]["commit"] == w.c1 and receipt["outcomes_read"] is False)
    ok(sorted(os.listdir(w.out)) == ["BUILD.json", "END-JOB.json"])
    ok(all(os.stat(Path(w.out, n)).st_mode & 0o777 == 0o444 for n in os.listdir(w.out)))


def test_build_is_exclusive(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.build()
    raises(w.si.Refusal, w.build)
    other = tmp_path / "existing"
    other.mkdir()
    raises(w.si.Refusal, w.build, out=str(other))
    ok(os.listdir(other) == [])


def side_commit(w):
    """A commit that is not an ancestor of P' (an orphan branch holding the same plan bytes)."""
    H.git(w.repo, "checkout", "-q", "--orphan", "side")
    commit = commit_all(w.repo, "side")
    H.git(w.repo, "checkout", "-q", "--detach", w.c2)
    return commit


@pytest.mark.parametrize("case,needle", [
    ("evidence-pin", "SHA-256 mismatch"),
    ("manifest-pin", "SHA-256 mismatch"),
    ("completion-not-of-record", "completion of record"),
    ("one-counted-host", "counted hosts"),
    ("three-counted-hosts", "counted hosts"),
    ("plan-study", "K4S reporting plan"),
    ("end-namespace-at-p", "R6"),
    ("item-not-ancestor", "ancestor"),
    ("item-path", "evidence-relative"),
    ("item-sha", "SHA-256 mismatch"),
    ("item-keys", "malformed"),
    ("declared-by-empty", "printable"),
    ("declared-by-newline", "printable"),
    ("declared-by-long", "printable"),
    ("commit-short", "40 hex"),
    ("out-relative", "absolute"),
])
def test_build_refusals(tmp_path, monkeypatch, case, needle):
    hosts = {"one-counted-host": ("127x03",), "three-counted-hosts": ("127x03", "127x04", "127x05")}.get(
        case, ("127x03", "127x04"))
    item_over = {"item-path": {"plan": dict(repository_path="reports/elsewhere/plan.json")},
                 "item-sha": {"plan": dict(sha256="0" * 64)},
                 "item-keys": {"plan": dict(extra=1)}}.get(case)
    w = World(tmp_path, monkeypatch, hosts=hosts, study="OTHER" if case == "plan-study" else "PREREG-K4S",
              item_over=item_over)
    declared_by, commit, out = "tester", None, None
    if case == "evidence-pin":
        monkeypatch.setattr(J, "END_EVIDENCE_SHA256", "0" * 64)
    elif case == "manifest-pin":
        monkeypatch.setattr(J, "K4S_MANIFEST_SHA256", "0" * 64)
    elif case == "completion-not-of-record":
        monkeypatch.setattr(J, "COMPLETION_SHA256", "0" * 64)
    elif case == "end-namespace-at-p":
        H.write(w.repo / J.END_DIR / "registry" / "x.json", b"{}")
        commit = commit_all(w.repo, "end dir")
    elif case == "item-not-ancestor":
        side = side_commit(w)
        evidence = json.loads(w.evidence)
        evidence["plan"]["commit"] = side
        data = (json.dumps(evidence, indent=1, sort_keys=True) + "\n").encode()
        H.write(w.repo / J.END_EVIDENCE_REL, data)
        commit = commit_all(w.repo, "evidence on side plan")
        monkeypatch.setattr(J, "END_EVIDENCE_SHA256", H.sha_bytes(data))
    elif case.startswith("declared-by"):
        declared_by = {"declared-by-empty": " ", "declared-by-newline": "a\nb", "declared-by-long": "x" * 201}[case]
    elif case == "commit-short":
        commit = w.c2[:12]
    elif case == "out-relative":
        out = "relative/out"
    raises((J.JobRefusal, w.si.Refusal), w.build, declared_by=declared_by, commit=commit, out=out, match=needle)
    ok(not Path(w.out).exists())


def frozen_job_fields():
    path = Path(J.FROZEN_RUNTIME) / "runtime" / J.STUDY_DIR / "end_evidence.py"
    if not path.exists():
        pytest.skip("frozen runtime not on this machine")
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["JOB_FIELDS"]:
            return tuple(sorted(ast.literal_eval(node.value.args[0])))
    raise AssertionError("JOB_FIELDS not found")


def test_job_fields_equal_the_frozen_end_evidence():
    ok(J.JOB_FIELDS == frozen_job_fields())


def test_scratch_commit_is_the_job_alone(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    job, digest = w.build()
    clone = tmp_path / "clone"
    clone.mkdir()
    shutil.copytree(w.repo / ".git", clone / ".git", symlinks=True)     # .git only, as self_check copies it
    ok(sorted(os.listdir(clone)) == [".git"])
    data = Path(w.out, "END-JOB.json").read_bytes()
    x = J.scratch_commit(w.si, str(clone), data, w.c2)
    names = H.git(clone, "diff-tree", "-r", "--name-only", "--no-renames", w.c2, x).stdout.split()
    ok(names == [J.END_JOB_REL] and H.git(clone, "show", x + ":" + J.END_JOB_REL).stdout.encode() == data)
    ok(H.git(clone, "rev-parse", x + "^").stdout.strip() == w.c2)
    raises(J.JobRefusal, J.scratch_commit, w.si, str(clone), data, w.c2, match="not P'")
    other = tmp_path / "clone-staged"                          # an index that already stages another change
    other.mkdir()
    shutil.copytree(w.repo / ".git", other / ".git", symlinks=True)
    H.write(other / STUDY / "extra.json", b"{}\n")
    H.git(other, "add", "--", STUDY + "/extra.json")
    raises(J.JobRefusal, J.scratch_commit, w.si, str(other), data, w.c2, match="END-JOB alone")


def test_materialize_evidence_writes_exactly_its_artifacts(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    target = tmp_path / "evidence"
    path, count = J.materialize_evidence(w.si, str(w.repo), w.c2, str(target))
    ok(count == 5 and Path(path).read_bytes() == w.evidence)
    written = sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())
    ok(written == sorted(["end-evidence.json", "plan.json", "run-r1/completion-v2/REPORTING-COMPLETION.json",
                          "run-r1/ledger/blind-ledger-final.json", "run-r1/completion-v2/counted-inventory.json"]))


def test_cli_build_and_optimized_refusal(tmp_path, monkeypatch, capsys):
    w = World(tmp_path, monkeypatch)
    rc = J.main(["build", "--declared-by", "cli", "--out", w.out], si=w.si)
    if sys.flags.optimize:
        ok(rc == 2 and "-O" in capsys.readouterr().err and not Path(w.out).exists())
    else:
        printed = json.loads(capsys.readouterr().out)
        ok(rc == 0 and printed["end_job_sha256"] == H.sha(Path(w.out, "END-JOB.json")))


@pytest.mark.skipif(not (Path(J.REPO_FULL) / ".git").is_dir() or not Path(J.FROZEN_RUNTIME).is_dir(),
                    reason="05 full clone / S9 runtime not on this machine")
def test_real_a6_builder_proof_frozen_and_s9(tmp_path):
    """INTEGRATION (05, read only): build from the real P' and self-check: the frozen end_evidence + end_job accept the
    END-JOB at a scratch commit X = P' + END-JOB alone, and S9 r3 equivalence passes on that scratch clone."""
    si = J.load_si(str(ROOT))
    before = sorted(n for n in os.listdir(J.SCRATCH_PARENT) if n.startswith("k4s-a6-scratch-"))
    out = str(tmp_path / "proof")
    with contextlib.redirect_stdout(io.StringIO()):
        job, digest = J.build(si, "test_a6_builder integration (scratch only)", out)
        result = J.self_check(si, out, digest)
    ok(result["ok"] is True and result["frozen"]["end_job"]["sha256"] == digest)
    ok(result["frozen"]["end_job"]["commit"] == result["scratch_end_job_commit"])
    ok(result["frozen"]["end_evidence"]["completion_sha256"] == J.COMPLETION_SHA256 == job["completion_sha256"])
    ok(result["s9_equivalence"]["git_members"] > 0 and result["scratch_diff"] == [J.END_JOB_REL])
    ok(sorted(n for n in os.listdir(J.SCRATCH_PARENT) if n.startswith("k4s-a6-scratch-")) == before)


FROZEN_STUB = """
import json, subprocess, sys
rt, evp, evsha, repo, jobsha, k4s = sys.argv[1:7]
x = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
commit = "0" * 40 if "%(mode)s" == "bad-frozen" else x
print("__K4S_FROZEN__ " + json.dumps(dict(end_evidence=dict(counted_hosts=["127x03", "127x04"], plan_sha256="p",
      completion_sha256="c", sha256=evsha), end_job=dict(commit=commit, sha256=jobsha, repository_path="r",
      registry_root="g"), job_fields=%(fields)r, job_schema=%(schema)r, end_job_path=%(path)r)))
"""
S9_STUB = """
import json, sys
x = sys.argv[sys.argv.index("--end-job-commit") + 1]
diff = [] if "%(mode)s" == "bad-s9" else [%(path)r]
print(json.dumps(dict(end_job_commit=x, runtime_commit=%(commit)r, diff=diff, runtime_files_identical=True,
                      measurement_files_identical=True, git_members=1)))
"""


@pytest.mark.parametrize("mode", ["ok", "bad-frozen", "bad-s9"])
def test_self_check_verdicts_with_stub_drivers(tmp_path, monkeypatch, mode):
    """The self-check's own verdict logic, with the frozen and S9 children replaced by stubs (the real children run
    in test_real_a6_builder_proof_frozen_and_s9): a wrong frozen commit or a wrong S9 diff refuses; the scratch
    directory is removed and no SELF-CHECK.json is written on refusal."""
    w = World(tmp_path, monkeypatch)
    job, digest = w.build()
    fmt = dict(mode=mode, fields=list(J.JOB_FIELDS), schema=J.JOB_SCHEMA, path=J.END_JOB_REL, commit=w.c2)
    monkeypatch.setattr(J, "FROZEN_DRIVER", FROZEN_STUB % fmt)
    monkeypatch.setattr(J, "S9_DRIVER", S9_STUB % fmt)
    monkeypatch.setattr(J, "FROZEN_PYTHON", sys.executable)
    monkeypatch.setattr(J, "frozen_inputs", lambda si: None)
    scratch = tmp_path / "shm"
    scratch.mkdir()
    monkeypatch.setattr(J, "SCRATCH_PARENT", str(scratch))
    if mode == "ok":
        with contextlib.redirect_stdout(io.StringIO()):
            result = J.self_check(w.si, w.out, digest, commit=w.c2)
        ok(result["ok"] and json.loads(Path(w.out, "SELF-CHECK.json").read_text())["scratch_end_job_commit"]
           == result["frozen"]["end_job"]["commit"])
    else:
        raises(J.JobRefusal, J.self_check, w.si, w.out, digest, commit=w.c2,
               match="frozen end_job" if mode == "bad-frozen" else "S9 equivalence")
        ok(not Path(w.out, "SELF-CHECK.json").exists())
    ok(os.listdir(scratch) == [])


@pytest.mark.skipif(not Path(J.FROZEN_RUNTIME).is_dir() or not Path(J.S9_PATH).is_file(),
                    reason="S9 runtime / s3s9s10-r3 not on this machine")
@pytest.mark.parametrize("pin", ["none", "runtime-manifest", "frozen-file", "s9"])
def test_frozen_inputs_are_pinned(monkeypatch, pin):
    si = J.load_si(str(ROOT))
    if pin == "runtime-manifest":
        monkeypatch.setattr(J, "FROZEN_RUNTIME_MANIFEST_SHA256", "0" * 64)
    elif pin == "frozen-file":
        rel = sorted(J.FROZEN_PINS)[0]
        monkeypatch.setitem(J.FROZEN_PINS, rel, "0" * 64)
    elif pin == "s9":
        monkeypatch.setattr(J, "S9_SHA256", "0" * 64)
    if pin == "none":
        ok(J.frozen_inputs(si) is None)
    else:
        raises(J.JobRefusal, J.frozen_inputs, si, match="differs from")
