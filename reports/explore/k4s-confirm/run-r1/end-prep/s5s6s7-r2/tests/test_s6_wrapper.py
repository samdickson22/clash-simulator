"""S6 exit-push wrapper r2 (k4s_end_exit_push.sh) and the S5 preflight wrapper r2 (k4s_preflight_push.sh), offline.

Each test runs a copy in which ONLY the two host-base lines, the receive-base line and the interpreter line are
replaced (checked: exactly 4 changed lines); the interpreter stand-in only makes os.uname() report the fake host.
The staged tools are byte copies of the package's safe_input.py / k4s_end_host_tool.py (the wrapper's pin holds).
hostname/rsync/timeout/nice/taskset are PATH shims. Includes Sol's hard-linked argv.nul truncation probe."""
import json
import os
import sys
from pathlib import Path

import pytest

import helpers as H
from helpers import ROOT, ok

PY = sys.executable
PRODUCER = Path(__file__).resolve().parent / "fake_producer.py"
RECEIVE = {"k4s_end_exit_push.sh": "receive_base=/mpac/sdicks02/k4s-runner/run-r1/end-received",
           "k4s_preflight_push.sh": "receive_base=/mpac/sdicks02/k4s-runner/run-r1/preflight-received"}


class Harness:
    def __init__(self, tmp, script, host="127x03"):
        self.tmp, self.host, self.script = tmp, host, script
        tmp.mkdir(parents=True, exist_ok=True)
        self.bases = {"127x03": tmp / "hostfs03" / "k4s-end-r1", "127x04": tmp / "hostfs04" / "k4s-end-r1"}
        self.base = self.bases[host]
        self.wrapper = tmp / script
        kind = "end-received" if script == "k4s_end_exit_push.sh" else "preflight-received"
        self.recv_root = tmp / "recv" / kind
        changed = H.substituted(ROOT / script, self.wrapper, [
            ("  127x03) base=/mpac/sdicks02/jobs/clasher/k4s-end-r1 ;;", f"  127x03) base={self.bases['127x03']} ;;"),
            ("  127x04) base=/mpac/sdicks02/jobs-k4s/k4s-end-r1 ;;", f"  127x04) base={self.bases['127x04']} ;;"),
            (RECEIVE[script], RECEIVE[script].replace("/mpac/sdicks02/k4s-runner/run-r1", str(tmp / "recv"))),
            ("python=/usr/bin/python3", "python=" + str(H.fake_python(tmp)))])
        ok(changed == 4, changed)
        self.parent = self.base / ("attempts" if script == "k4s_end_exit_push.sh" else "preflight")
        self.repository = self.base / "repository"
        self.tools = self.base / "tools"
        H.copy_tools(self.tools)
        H.git_repo(self.repository, files={"reports/explore/k4s-confirm/README": b"study\n"})
        for p in (self.parent, self.base / "attempts", tmp / "home"):
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
        script = self.tools / "k4s_end_preflight.py"
        if not script.exists():
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
        e = H.shim_env(self.tmp, FAKE_HOST=host or self.host, FAKE_MODE=mode, HOME=self.tmp / "home",
                       GIT_DIR="/inherited/evil", GIT_REPLACE_REF_BASE="refs/evil/", **env)
        return H.run(["bash", self.wrapper, job, *argv], e)


@pytest.fixture
def end(tmp_path):
    return Harness(tmp_path, "k4s_end_exit_push.sh")


@pytest.fixture
def pre(tmp_path):
    return Harness(tmp_path, "k4s_preflight_push.sh")


def received(h, job):
    return h.recv_root / h.host / job.name


def load(path):
    return json.loads(Path(path).read_text())


# ---------------------------------------------------------------- S6: refusals (exit 90, nothing run or pushed)

@pytest.mark.parametrize("mutate", [
    lambda h, j: (j, h.end_argv(j), dict(host="127x01")),                              # wrong host
    lambda h, j: (str(j) + "/", h.end_argv(j), {}),                                    # trailing slash
    lambda h, j: (h.base / "x" / ".." / "attempts" / j.name, h.end_argv(j), {}),        # dot-dot
    lambda h, j: (h.base / j.name, h.end_argv(j), {}),                                 # parent is not attempts
    lambda h, j: (j, h.end_argv(j, **{"--out": None}), {}),                            # no --out
    lambda h, j: (j, h.end_argv(j, **{"--out": str(j / "measurement")}), {}),           # --out not <job>/<attempt>
    lambda h, j: (j, h.end_argv(j) + ["--out", str(j / j.name)], {}),                  # two --out
    lambda h, j: (j, h.end_argv(j, **{"--out": None}) + ["--out=" + str(j / j.name)], {}),
    lambda h, j: (j, h.end_argv(j, **{"--out": None}) + ["--ou", str(j / j.name)], {}),  # argparse abbreviation
    lambda h, j: (j, h.end_argv(j, **{"--repository": None}), {}),                     # no --repository
    lambda h, j: (j, h.end_argv(j, **{"--repository": str(h.base / "runtime")}), {}),   # undeclared clone
    lambda h, j: (j, h.end_argv(j, **{"--repository": None}) + ["--repo", str(h.repository)], {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": None}), {}),                          # no --round
    lambda h, j: (j, h.end_argv(j, **{"--round": "07"}), {}),
    lambda h, j: (j, h.end_argv(j, **{"--round": "1"}), {}),                           # round != attempt name
    lambda h, j: (j, h.end_argv(j) + ["--round", "0"], {}),                            # two --round
    lambda h, j: (j, [], {}),                                                          # empty command
], ids=["host", "slash", "dotdot", "parent", "no-out", "out-measurement", "two-out", "out-eq", "out-abbrev",
        "no-repo", "repo-wrong", "repo-abbrev", "no-round", "round-07", "round-mismatch", "two-round", "empty"])
def test_wrapper_refusals(end, mutate):
    job = end.job()
    target, argv, extra = mutate(end, job)
    result = end.run(target, argv, host=extra.get("host"))
    ok(result.returncode == 90, (result.returncode, result.stderr))
    ok(not (job / "argv.nul").exists() and not end.recv_root.exists())


@pytest.mark.parametrize("name", ["end-127x03-r00", "end-127x04-r00-l00", "measurement", "end-127x03-r0-l00"])
def test_attempt_name_must_be_launch_index_form(end, name):
    job = end.job(name)
    ok(end.run(job, end.end_argv(job)).returncode == 90)


@pytest.mark.parametrize("planted", ["argv.nul", "exit.json", "exit.json.tmp", "TRANSFER-DONE.json",
                                     "PUSH-FAILED.json", "registry", "registry-listing.json"])
def test_hard_linked_metadata_canary_is_never_written(end, planted):
    """Sol S6-F2 probe: a pre-existing (here hard-linked foreign 'keep me') metadata name refuses before the command
    runs; the foreign inode keeps its bytes (r1 truncated it through `> argv.nul`)."""
    job = end.job()
    canary = H.canary(end.tmp / "keep-me")
    os.link(canary, job / planted)
    result = end.run(job, end.end_argv(job), mode="preclaim")
    ok(result.returncode == 90 and H.canary_intact(canary), result.stderr)
    ok(not (end.base / "repository/reports/explore/k4s-confirm/end").exists())


@pytest.mark.parametrize("planted", ["exit.json.tmp", "TRANSFER-DONE.json.tmp", "PUSH-FAILED.json"])
def test_alias_planted_during_the_run_is_never_written_through(end, planted):
    """A hard link planted while END runs (after the pre-checks): every later write is create-excl (no-follow,
    exclusive), so it refuses and the canary keeps its bytes."""
    job = end.job()
    canary = H.canary(end.tmp / "keep-me")
    extra = dict(FAKE_RSYNC_FAIL=job.name + "/" + job.name, FAKE_RSYNC_RC=23) if planted == "PUSH-FAILED.json" else {}
    result = end.run(job, end.end_argv(job), mode="complete", FAKE_PLANT=planted, FAKE_CANARY=canary, **extra)
    ok(result.returncode in (91, 92) and H.canary_intact(canary), (result.returncode, result.stderr))
    if planted == "exit.json.tmp":
        ok(result.returncode == 91 and not (job / "exit.json").exists())


def test_symlinked_job_or_tools_refuse(end):
    job = end.job()
    os.rename(job, end.tmp / "real-job")
    os.symlink(end.tmp / "real-job", job)
    ok(end.run(job, end.end_argv(job)).returncode == 90)
    end2 = Harness(end.tmp / "two", "k4s_end_exit_push.sh")
    job2 = end2.job()
    os.chmod(end2.tools / "k4s_end_host_tool.py", 0o644)
    with open(end2.tools / "k4s_end_host_tool.py", "a") as stream:
        stream.write("\n")
    ok(end2.run(job2, end2.end_argv(job2)).returncode == 90)


# ---------------------------------------------------------------- S6: runs

def test_complete_pushes_everything_through_safe_input(end):
    job = end.job()
    dump = end.tmp / "git-env.json"
    result = end.run(job, end.end_argv(job), FAKE_ENV_DUMP=dump)
    ok(result.returncode == 0, result.stderr)
    recv = received(end, job)
    exit_ = load(recv / "exit.json")
    ok(exit_["exit_code"] == 0 and exit_["measurement_exists"] and exit_["registry_exists"] and exit_["registry_snapshot"])
    ok(load(recv / "TRANSFER-DONE.json")["transfer_complete"] is True and not (recv / "PUSH-FAILED.json").exists())
    listing = load(recv / "registry-listing.json")
    ok([c["name"] for c in listing["claims"]] == ["attempt-00.json"])
    ok(H.sha(recv / "registry" / "attempt-00.json") == listing["claims"][0]["sha256"])
    ok((recv / "durable-measurement" / "receipt-manifest.json").exists())
    ok((recv / "argv.nul").read_bytes() == b"".join(a.encode() + b"\0" for a in end.end_argv(job)))
    for name in ("argv.nul", "exit.json", "TRANSFER-DONE.json", "registry-listing.json"):
        ok(H.nlink(job / name) == 1 and os.stat(job / name).st_mode & 0o777 == 0o444, name)
    ok(not (job / "exit.json.tmp").exists() and not (job / "TRANSFER-DONE.json.tmp").exists())
    env = load(dump)                                  # frozen-reader ruling: the command saw the P2-4 git env
    ok("GIT_DIR" not in env and "GIT_REPLACE_REF_BASE" not in env and env["GIT_NO_REPLACE_OBJECTS"] == "1")
    ok(env["GIT_CONFIG_PARAMETERS"] == "'core.hookspath=/dev/null' 'core.fsmonitor=false' 'protocol.allow=never'")


@pytest.mark.parametrize("mode,code,measured,registry", [("failed", 1, True, True), ("preclaim", 1, False, False),
                                                         ("claim-only", 1, False, True)])
def test_failed_preclaim_and_claim_only(end, mode, code, measured, registry):
    job = end.job()
    result = end.run(job, end.end_argv(job), mode=mode)
    ok(result.returncode == code, result.stderr)
    recv = received(end, job)
    exit_ = load(recv / "exit.json")
    ok(exit_["measurement_exists"] is measured and exit_["registry_exists"] is registry)
    ok((recv / "durable-measurement").exists() is measured and (recv / "registry").exists() is registry)
    ok((recv / "registry-listing.json").exists() and (recv / "TRANSFER-DONE.json").exists())


def test_round_one_and_04_base(tmp_path):
    h = Harness(tmp_path, "k4s_end_exit_push.sh", host="127x04")
    job = h.job("end-127x04-r01-l00")
    ok(h.run(job, h.end_argv(job, **{"--round": "1"})).returncode == 0)
    ok(load(received(h, job) / "registry-listing.json")["round"] == 1)


def test_push_failure_is_exclusive_and_exits_92(end):
    job = end.job()
    result = end.run(job, end.end_argv(job), FAKE_RSYNC_FAIL=job.name + "/" + job.name, FAKE_RSYNC_RC=23)
    ok(result.returncode == 92 and load(job / "PUSH-FAILED.json")["transport_failed"] is True)
    ok(not (job / "TRANSFER-DONE.json").exists() and not (received(end, job) / "TRANSFER-DONE.json").exists())


def test_hard_linked_registry_claim_is_never_pushed(end):
    """Sol S6-F1 class on the host: a claim hard-linked to a canary makes the safe_input snapshot refuse; nothing of
    it is pushed, no transfer marker exists, and the run ends PUSH-FAILED (no ACK possible)."""
    job = end.job()
    canary = H.canary(end.tmp / "outcome-canary")
    result = end.run(job, end.end_argv(job), mode="claim-only", FAKE_CLAIM_LINK=1, FAKE_CANARY=canary)
    ok(result.returncode == 92, result.stderr)
    recv = received(end, job)
    ok(not (recv / "registry").exists() and not (recv / "TRANSFER-DONE.json").exists())
    ok(load(recv / "exit.json")["registry_snapshot"] is False and H.canary_intact(canary))


def test_unverified_clone_never_runs_the_command(end):
    """Frozen-reader ruling: a replace ref in the --repository clone stops frozen-exec before the command."""
    head = H.git(end.repository, "rev-parse", "HEAD").stdout.strip()
    H.git(end.repository, "commit", "-q", "--allow-empty", "-m", "x")
    H.git(end.repository, "replace", head, H.git(end.repository, "rev-parse", "HEAD").stdout.strip())
    job = end.job()
    dump = end.tmp / "never.json"
    result = end.run(job, end.end_argv(job), FAKE_ENV_DUMP=dump)
    ok(result.returncode == 3 and not dump.exists(), result.stderr)
    ok(load(received(end, job) / "exit.json")["exit_code"] == 3)


# ---------------------------------------------------------------- S5 preflight wrapper

@pytest.mark.parametrize("mutate", [
    lambda h, j: h.preflight_argv(j, **{"--attempt-parent": str(h.base / "preflight")}),
    lambda h, j: h.preflight_argv(j, **{"--attempt-parent": None}),
    lambda h, j: h.preflight_argv(j, **{"--out": str(h.base / "attempts" / j.name)}),
    lambda h, j: h.preflight_argv(j) + ["--repository", str(h.repository)],
    lambda h, j: h.preflight_argv(j) + [str(h.base / "runtime/end_reference.py")],
    lambda h, j: [PY, str(PRODUCER), "/elsewhere/k4s_end_preflight.py", "run", "--repository", str(h.repository),
                  "--attempt-parent", str(h.base / "attempts"), "--out", str(j / j.name)],
    lambda h, j: h.preflight_argv(j, **{"--attempt-parent": None}) + ["--at", str(h.base / "attempts")],
], ids=["parent-wrong", "no-parent", "out-attempts", "two-repo", "end-reference", "script-elsewhere", "abbrev"])
def test_preflight_wrapper_refusals(pre, mutate):
    job = pre.job()
    ok(pre.run(job, mutate(pre, job), mode="preflight").returncode == 90)
    ok(not (job / "argv.nul").exists())


def test_preflight_wrapper_runs_and_pushes(pre):
    job = pre.job()
    result = pre.run(job, pre.preflight_argv(job), mode="preflight")
    ok(result.returncode == 0, result.stderr)
    recv = received(pre, job)
    ok(load(recv / "TRANSFER-DONE.json")["transfer_complete"] and (recv / "preflight" / "preflight-result.json").exists())
    ok(load(recv / "exit.json")["exit_code"] == 0 and not (recv / "registry").exists())


def test_preflight_wrapper_hard_linked_argv_nul(pre):
    job = pre.job()
    canary = H.canary(pre.tmp / "keep-me")
    os.link(canary, job / "argv.nul")
    ok(pre.run(job, pre.preflight_argv(job), mode="preflight").returncode == 90 and H.canary_intact(canary))


def test_wrapper_sources_have_no_writing_redirection():
    """No shell redirection at all (`>`, `>>`, `>|`) in either wrapper outside quoted text and comments: every file
    the wrapper creates goes through the safe_input CLI (Sol S6-F2)."""
    import re
    for name in ("k4s_end_exit_push.sh", "k4s_preflight_push.sh"):
        for line in (ROOT / name).read_text().splitlines():
            code = re.sub(r"'[^']*'", "", line).split("#", 1)[0]
            ok(">" not in code, (name, line))
