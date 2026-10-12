"""S6 exit-push wrapper (k4s_end_exit_push.sh) and the S5 preflight wrapper (k4s_preflight_push.sh), offline.

The wrappers hard-code host paths; each test runs a copy in which ONLY the two host-base lines and the receive line
are replaced by temporary paths (asserted: exactly 3 changed lines). hostname/rsync/timeout/nice/taskset are shims.
"""
import json
import os
import sys
from pathlib import Path

import pytest

from helpers import ROOT, run, shim_env, substituted

PY = sys.executable
PRODUCER = Path(__file__).resolve().parent / "fake_producer.py"
LINES = {
    "k4s_end_exit_push.sh": 'receive="/mpac/sdicks02/k4s-runner/run-r1/end-received/$host/$attempt"',
    "k4s_preflight_push.sh": 'receive="/mpac/sdicks02/k4s-runner/run-r1/preflight-received/$host/$attempt"',
}


class Harness:
    def __init__(self, tmp, script, host="127x03"):
        self.tmp, self.host, self.script = tmp, host, script
        self.bases = {"127x03": tmp / "base03", "127x04": tmp / "base04"}
        self.base = self.bases[host]
        self.wrapper = tmp / script
        kind = "end-received" if script == "k4s_end_exit_push.sh" else "preflight-received"
        self.recv_root = tmp / "recv" / kind
        changed = substituted(ROOT / script, self.wrapper, [
            ("  127x03) base=/mpac/sdicks02/jobs/clasher/k4s-end-r1 ;;", f"  127x03) base={self.bases['127x03']} ;;"),
            ("  127x04) base=/mpac/sdicks02/jobs-k4s/k4s-end-r1 ;;", f"  127x04) base={self.bases['127x04']} ;;"),
            (LINES[script], LINES[script].replace("/mpac/sdicks02/k4s-runner/run-r1", str(tmp / "recv")))])
        assert changed == 3
        self.parent = self.base / ("attempts" if script == "k4s_end_exit_push.sh" else "preflight")
        self.repository = self.base / "repository"
        for p in (self.parent, self.repository, self.base / "attempts"):
            p.mkdir(parents=True, exist_ok=True)

    def job(self, name=None):
        name = name or ("end-%s-r00-l00" % self.host if "end_exit" in self.script else "preflight-%s-l00" % self.host)
        job = self.parent / name
        job.mkdir()
        (job / "detach.log").write_text("")
        (job / "detach.json").write_text('{"pid":1}\n')
        return job

    def end_argv(self, job, **override):
        opts = {"--bundle": "B", "--repository": str(self.repository), "--round": "0", "--out": str(job / job.name)}
        opts.update(override)
        argv = [PY, str(PRODUCER)]
        for k, v in opts.items():
            if v is not None:
                argv += [k, v]
        return argv

    def preflight_argv(self, job, **override):
        script = self.base / "tools" / "k4s_end_preflight.py"
        script.parent.mkdir(exist_ok=True)
        script.write_text("")
        opts = {"--repository": str(self.repository), "--attempt-parent": str(self.base / "attempts"),
                "--out": str(job / job.name)}
        opts.update(override)
        argv = [PY, str(PRODUCER), str(script), "run"]
        for k, v in opts.items():
            if v is not None:
                argv += [k, v]
        return argv

    def run(self, job, argv, mode="complete", host=None, **env):
        return run(["bash", self.wrapper, job, *argv], shim_env(self.tmp, FAKE_HOST=host or self.host,
                                                                FAKE_MODE=mode, **env))


@pytest.fixture
def end(tmp_path):
    return Harness(tmp_path, "k4s_end_exit_push.sh")


@pytest.fixture
def pre(tmp_path):
    return Harness(tmp_path, "k4s_preflight_push.sh")


def received(h, job):
    return h.recv_root / h.host / job.name


# ---------------------------------------------------------------- S6: refusals (exit 90, nothing run or pushed)

@pytest.mark.parametrize("mutate", [
    lambda h, j: (j, h.end_argv(j), dict(host="127x01")),                              # wrong host
    lambda h, j: (str(j) + "/", h.end_argv(j), {}),                                    # trailing slash
    lambda h, j: (h.base / "x" / ".." / "attempts" / j.name, h.end_argv(j), {}),        # dot-dot
    lambda h, j: (h.base / j.name, h.end_argv(j), {}),                                 # parent is not attempts
    lambda h, j: (j, h.end_argv(j, **{"--out": None}), {}),                            # no --out
    lambda h, j: (j, h.end_argv(j, **{"--out": str(j / "measurement")}), {}),           # --out not <job>/<attempt>
    lambda h, j: (j, h.end_argv(j, **{"--out": str(h.base / "attempts" / j.name)}), {}),
    lambda h, j: (j, h.end_argv(j) + ["--out", str(j / j.name)], {}),                  # two --out
    lambda h, j: (j, h.end_argv(j, **{"--out": None}) + ["--out=" + str(j / j.name)], {}),
    lambda h, j: (j, h.end_argv(j, **{"--out": None}) + ["--ou", str(j / j.name)], {}),  # argparse abbreviation
    lambda h, j: (j, h.end_argv(j, **{"--repository": None}), {}),                     # no --repository
    lambda h, j: (j, h.end_argv(j, **{"--repository": str(h.base / "runtime")}), {}),   # undeclared clone
    lambda h, j: (j, h.end_argv(j, **{"--repository": None}) + ["--repo", str(h.repository)], {}),
    lambda h, j: (j, h.end_argv(j, **{"--repository": None}) + ["--repository=" + str(h.repository)], {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": None}), {}),                          # no --round
    lambda h, j: (j, h.end_argv(j, **{"--round": "07"}), {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": "100"}), {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": "-1"}), {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": None}) + ["--rou", "0"], {}),
    lambda h, j: (j, h.end_argv(j) + ["--round", "1"], {}),                            # two --round
], ids=["host", "slash", "dotdot", "parent", "no-out", "out-measurement", "out-parent", "two-out", "out-eq",
        "out-abbrev", "no-repo", "repo-wrong", "repo-abbrev", "repo-eq", "no-round", "round-07", "round-100",
        "round-neg", "round-abbrev", "two-round"])
def test_wrapper_refusals(end, mutate):
    job = end.job()
    target, argv, extra = mutate(end, job)
    result = end.run(target, argv, host=extra.get("host"))
    assert result.returncode == 90, result.stderr
    assert not (job / "argv.nul").exists() and not (job / "exit.json").exists()
    assert not (end.repository / "reports").exists()
    assert not end.recv_root.exists()


def test_wrapper_refuses_existing_measurement_exit_and_missing_detach(end):
    job = end.job()
    (job / job.name).mkdir()
    assert end.run(job, end.end_argv(job)).returncode == 90
    job2 = end.job("end-127x03-r00-l01")
    (job2 / "exit.json").write_text("{}")
    assert end.run(job2, end.end_argv(job2)).returncode == 90
    job3 = end.job("end-127x03-r00-l02")
    (job3 / "detach.json").write_text("")
    assert end.run(job3, end.end_argv(job3)).returncode == 90
    job4 = end.job("end-127x03-r00-l03")
    (job4 / "detach.log").unlink()
    assert end.run(job4, end.end_argv(job4)).returncode == 90
    assert end.run(job4, []).returncode == 90


def test_wrapper_refuses_symlinked_job(end):
    real = end.job()
    link = end.parent / "end-127x03-r00-l09"
    link.symlink_to(real)
    assert end.run(link, end.end_argv(link)).returncode == 90


# ---------------------------------------------------------------- S6: post-exit pushes

def test_complete_pushes_registry_and_measurement(end):
    job = end.job()
    result = end.run(job, end.end_argv(job))
    assert result.returncode == 0, result.stderr
    recv = received(end, job)
    exit_ = json.loads((recv / "exit.json").read_text())
    assert exit_["measurement_exists"] is True and exit_["registry_exists"] is True and exit_["exit_code"] == 0
    assert sorted(p.name for p in (recv / "registry").iterdir()) == ["attempt-00.json"]
    assert (recv / "durable-measurement" / "receipt-manifest.json").is_file()
    assert json.loads((recv / "TRANSFER-COMPLETE.json").read_text())["transfer_complete"] is True
    assert (recv / "argv.nul").read_bytes() == b"".join(a.encode() + b"\0" for a in end.end_argv(job))


def test_claim_without_receipt_still_pushes_registry(end):
    """RC-5: a failure between the claim and K4SStore creation leaves only the claim; it is pushed."""
    job = end.job()
    result = end.run(job, end.end_argv(job), mode="claim-only")
    assert result.returncode == 1
    recv = received(end, job)
    exit_ = json.loads((recv / "exit.json").read_text())
    assert exit_["measurement_exists"] is False and exit_["registry_exists"] is True
    assert (recv / "registry" / "attempt-00.json").is_file()
    assert not (recv / "durable-measurement").exists()
    assert (recv / "TRANSFER-COMPLETE.json").is_file()


def test_preclaim_refusal_pushes_metadata_only(end):
    job = end.job()
    result = end.run(job, end.end_argv(job), mode="preclaim")
    assert result.returncode == 1
    recv = received(end, job)
    exit_ = json.loads((recv / "exit.json").read_text())
    assert exit_["registry_exists"] is False and exit_["measurement_exists"] is False
    assert not (recv / "registry").exists()
    assert sorted(p.name for p in recv.iterdir()) == ["TRANSFER-COMPLETE.json", "argv.nul", "detach.json",
                                                      "detach.log", "exit.json"]


def test_push_failure_writes_push_failed(end):
    job = end.job()
    result = end.run(job, end.end_argv(job), FAKE_RSYNC_FAIL="/registry/", FAKE_RSYNC_RC=12)
    assert result.returncode == 92
    recv = received(end, job)
    assert (recv / "PUSH-FAILED.json").is_file() and not (recv / "TRANSFER-COMPLETE.json").exists()


def test_round_selects_registry_directory(end):
    job = end.job("end-127x03-r01-l00")
    result = end.run(job, end.end_argv(job, **{"--round": "1"}))
    assert result.returncode == 0, result.stderr
    assert (end.repository / "reports/explore/k4s-confirm/end/registry/round-01/127x03/attempt-00.json").is_file()
    assert (received(end, job) / "registry" / "attempt-00.json").is_file()


def test_04_uses_its_own_base(tmp_path):
    h = Harness(tmp_path, "k4s_end_exit_push.sh", host="127x04")
    job = h.job()
    assert h.run(job, h.end_argv(job)).returncode == 0
    job3 = h.bases["127x03"] / "attempts" / "end-127x04-r00-l01"
    job3.parent.mkdir(parents=True, exist_ok=True)
    job3.mkdir()
    (job3 / "detach.log").write_text("")
    (job3 / "detach.json").write_text("{}")
    assert h.run(job3, h.end_argv(job3)).returncode == 90       # 04 refuses 03's base


# ---------------------------------------------------------------- S5 preflight wrapper

@pytest.mark.parametrize("mutate", [
    lambda h, j, a: (h.base / "attempts" / j.name, a),                       # attempt parent, not preflight/
    lambda h, j, a: (j, a + [str(h.base / "runtime" / "end_reference.py")]),  # end_reference.py anywhere
    lambda h, j, a: (j, [x for x in a if not x.endswith("k4s_end_preflight.py")]),
    lambda h, j, a: (j, a + [str(h.base / "tools2" / "k4s_end_preflight.py")]),
    lambda h, j, a: (j, a + ["--attempt-parent", str(h.base / "attempts")]),
    lambda h, j, a: (j, [x if x != str(h.base / "attempts") else str(h.base / "other") for x in a]),
    lambda h, j, a: (j, a + ["--att", "x"]),
    lambda h, j, a: (j, [x if x != "--out" else "--ou" for x in a]),
    lambda h, j, a: (j, [x if x != str(h.repository) else str(h.base / "repo2") for x in a]),
], ids=["attempt-parent", "end-reference", "no-script", "two-scripts", "two-parent", "parent-wrong", "parent-abbrev",
        "out-abbrev", "repo-wrong"])
def test_preflight_wrapper_refusals(pre, mutate):
    job = pre.job()
    target, argv = mutate(pre, job, pre.preflight_argv(job))
    if target != job:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.mkdir()
            (target / "detach.log").write_text("")
            (target / "detach.json").write_text("{}")
    assert pre.run(target, argv, mode="sleep", FAKE_SLEEP=0).returncode == 90
    assert not pre.recv_root.exists()


def test_preflight_wrapper_records_unchanged_registry_and_parent(pre):
    job = pre.job()
    (pre.base / "attempts" / "end-127x03-r00-l00").mkdir()
    result = pre.run(job, pre.preflight_argv(job), mode="sleep", FAKE_SLEEP=0)
    assert result.returncode == 0, result.stderr
    exit_ = json.loads((received(pre, job) / "exit.json").read_text())
    assert exit_["registry_listing_before"] == exit_["registry_listing_after"] == "absent"
    assert exit_["attempts_listing_before"] == exit_["attempts_listing_after"] != "absent"


def test_preflight_wrapper_exposes_a_registry_write(pre):
    job = pre.job()
    result = pre.run(job, pre.preflight_argv(job), mode="claim-in-preflight")
    assert result.returncode == 0, result.stderr
    exit_ = json.loads((received(pre, job) / "exit.json").read_text())
    assert exit_["registry_listing_before"] == "absent" != exit_["registry_listing_after"]
    assert (received(pre, job) / "preflight" / "receipt-manifest.json").is_file()
