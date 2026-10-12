"""S2 END evidence builder + validator on a synthetic committed repository, using the REAL frozen code."""
import json
import shutil
import sys

from conftest import S2, STUDY, git, pins_args, py, sha

EVIDENCE = STUDY + "/end-evidence.json"


def build(repo, commit, files, *extra, out=None):
    return py(S2, "build", "--repository", repo, "--commit", commit, "--out", out or repo / EVIDENCE,
              *pins_args(files), *extra)


def commit_evidence(repo):
    git(repo, "add", EVIDENCE)
    git(repo, "commit", "-q", "-m", "evidence")


def validate(repo, commit, files, evidence_sha, result, code_root, *extra):
    args = ["validate", "--repository", repo, "--commit", commit, "--evidence-sha256", evidence_sha,
            "--result", result, "--expect-blocks", "3900", "--expect-losses", "1", *pins_args(files), *extra]
    return py(S2, *args, "--code-root", code_root)


def built(synthetic, variant=None):
    repo, commit, files = synthetic(variant)
    out = build(repo, commit, files)
    assert out.returncode == 0, out.stderr
    commit_evidence(repo)
    return repo, commit, files, sha((repo / EVIDENCE).read_bytes())


def test_build_and_validate_happy_path(synthetic, code_root, tmp_path):
    repo, commit, files, evidence_sha = built(synthetic)
    doc = json.loads((repo / EVIDENCE).read_text())
    assert doc["schema"] == "clasher.k4s.end-evidence.v1" and doc["kind"] == "counted-reporting"
    assert doc["plan"] == dict(path="plan.json", sha256=sha(files[STUDY + "/plan.json"]), commit=commit,
                               repository_path=STUDY + "/plan.json")
    assert [(p["host"], p["phase"]) for p in doc["phases"]] == [("127x03", "reporting"), ("127x03", "replacement-r1"),
                                                                ("127x04", "reporting")]
    assert doc["phases"][0]["mhz"]["path"] == "end-sources/127x03/reporting/mhz.jsonl"
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 0, result.stdout + result.stderr
    r = json.loads((tmp_path / "r.json").read_text())
    assert r["ok"] is True and r["frozen_manifest_verified"] is True
    assert r["optimize"] == sys.flags.optimize                      # the subprocess ran under -O when pytest did
    assert r["membership"] == dict(blocks=3900, losses=1, host_phases=[["127x03", "replacement-r1"],
                                                                       ["127x03", "reporting"],
                                                                       ["127x04", "reporting"]])
    assert r["hosts"]["127x03"]["full_occupancy_rows"] == 8 and r["hosts"]["127x04"]["full_occupancy_rows"] == 4
    assert r["hosts"]["127x03"]["reference_cpus"] == [1, 2, 3, 4, 5] and r["hosts"]["127x03"]["background_slots"] == 10


def test_build_refuses_evidence_inside_end_namespace(synthetic):
    repo, commit, files = synthetic()
    out = build(repo, commit, files, "--evidence-repository-path", STUDY + "/end/end-evidence.json",
                out=repo / "x.json")
    assert out.returncode == 2 and "OUTSIDE the strict END namespace" in out.stderr


def test_build_refuses_authority_like_name(synthetic):
    repo, commit, files = synthetic()
    out = build(repo, commit, files, "--evidence-repository-path", STUDY + "/END-JOB-evidence.json",
                out=repo / "x.json")
    assert out.returncode == 2 and "END authority" in out.stderr


def test_build_refuses_wrong_pinned_completion(synthetic):
    repo, commit, files = synthetic()
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", repo / EVIDENCE)   # real-run pins
    assert out.returncode == 2 and "!= pinned" in out.stderr and not (repo / EVIDENCE).exists()


def test_build_refuses_uncommitted_sources(synthetic):
    repo, commit, files = synthetic(dict(no_sources={("127x04", "reporting")}))
    out = build(repo, commit, files)
    assert out.returncode == 2 and "S2Error: git show" in out.stderr and "end-sources/127x04/reporting" in out.stderr


def test_build_refuses_unbound_supervisor_exit(synthetic):
    def unbind(completion):
        completion["supervisor_exits"]["127x04/reporting"]["sha256"] = "0" * 64
    repo, commit, files = synthetic(dict(completion=unbind))
    out = build(repo, commit, files)
    assert out.returncode == 2 and "not bound by the completion" in out.stderr


def test_build_refuses_overwrite(synthetic):
    repo, commit, files = synthetic()
    (repo / EVIDENCE).write_text("{}")
    out = build(repo, commit, files)
    assert out.returncode == 2 and "overwrite" in out.stderr


def test_build_s1_manifest_cross_check(synthetic, tmp_path):
    repo, commit, files = synthetic()
    rows = []
    for rel, data in files.items():
        if "/end-sources/" in rel:
            host, phase, name = rel.split("/")[-3:]
            rows.append(dict(host=host, phase=phase, name=name, local_sha256=sha(data), remote_sha256_before=sha(data),
                             local_size=len(data)))
    meta = []
    for rel, data in files.items():
        if "/phase-meta/" in rel:
            hp, name = rel.split("/")[-2:]
            host, phase = hp[:6], hp[7:]
            meta.append(dict(host=host, phase=phase, name=name, remote_sha256=sha(data), committed_sha256=sha(data),
                             committed_repository_path=rel))
    good = tmp_path / "good.json"
    good.write_text(json.dumps(dict(files=rows, meta=meta)))
    out = build(repo, commit, files, "--s1-manifest", good, out=tmp_path / "e1.json")
    assert out.returncode == 0, out.stderr
    rows[0]["local_sha256"] = "f" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(files=rows, meta=meta)))
    out = build(repo, commit, files, "--s1-manifest", bad, out=tmp_path / "e2.json")
    assert out.returncode == 2 and "S1 copy manifest" in out.stderr


def test_validate_refuses_evidence_sha_mismatch(synthetic, tmp_path, code_root):
    repo, commit, files, _ = built(synthetic)
    result = validate(repo, commit, files, "a" * 64, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and json.loads((tmp_path / "r.json").read_text())["error"] == "evidence SHA mismatch"


def test_validate_refuses_worktree_artifact_differing_from_commit(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    path = repo / STUDY / "end-sources/127x04/reporting/census.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    r = json.loads((tmp_path / "r.json").read_text())
    assert result.returncode == 2 and r["ok"] is False and "pin mismatch" in r["error"]


def test_validate_refuses_commit_not_ancestor(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    git(repo, "checkout", "-q", "--orphan", "other")
    git(repo, "commit", "-q", "-m", "orphan copy")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "merge-base" in json.loads((tmp_path / "r.json").read_text())["error"]


def test_validate_refuses_broken_clock_join(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic, dict(clock={("127x04", "reporting"): dict(drop_mhz=2)}))
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "differ" in json.loads((tmp_path / "r.json").read_text())["error"]


def test_validate_refuses_insufficient_full_occupancy(synthetic, tmp_path, code_root):
    variant = dict(clock={("127x04", "reporting"): dict(inflight=10)})
    repo, commit, files, evidence_sha = built(synthetic, variant)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    r = json.loads((tmp_path / "r.json").read_text())
    assert result.returncode == 2 and "Insufficient full-occupancy" in r["error"]


def test_validate_refuses_extra_top_level_key(synthetic, tmp_path, code_root):
    repo, commit, files, _ = built(synthetic)
    doc = json.loads((repo / EVIDENCE).read_text())
    doc["note"] = "extra"
    (repo / EVIDENCE).write_text(json.dumps(doc))
    result = validate(repo, commit, files, sha((repo / EVIDENCE).read_bytes()), tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "top-level keys" in json.loads((tmp_path / "r.json").read_text())["error"]


def test_validate_refuses_wrong_membership_expectation(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root, "--expect-losses", "99")
    assert result.returncode == 2 and "membership" in json.loads((tmp_path / "r.json").read_text())["error"]


def test_validate_refuses_modified_frozen_code(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    tampered = tmp_path / "code"
    shutil.copytree(code_root, tampered)
    helper = tampered / "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_end.py"
    helper.write_text(helper.read_text() + "\n# tampered\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", tampered)
    r = json.loads((tmp_path / "r.json").read_text())
    assert result.returncode == 2 and "Pin mismatch" in r["error"]


def test_validate_refuses_result_overwrite(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    (tmp_path / "r.json").write_text("{}")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "result exists" in result.stderr


def test_validate_no_manifest_check_is_recorded(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root, "--no-manifest-check")
    r = json.loads((tmp_path / "r.json").read_text())
    assert result.returncode == 0 and r["ok"] is True and r["frozen_manifest_verified"] is False


def test_validate_refuses_code_root_without_frozen_code(synthetic, tmp_path):
    repo, commit, files, evidence_sha = built(synthetic)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", repo)
    assert result.returncode == 2 and json.loads((tmp_path / "r.json").read_text())["ok"] is False
