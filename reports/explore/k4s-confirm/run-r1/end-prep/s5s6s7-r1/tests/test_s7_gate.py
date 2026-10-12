"""S7 launch gate: 05-side validation, host-side parsers, and an end-to-end launch through PATH shims
(fake ssh/ps/systemctl/who/hostname/nice/taskset; the real frozen detach.sh; a stub wrapper and stub END script).
The host program runs under /usr/bin/python3 (3.8 here, as on the Ubuntu 20.04 hosts)."""
import calendar
import json
import os
import socket
import sys
import time
from pathlib import Path

import pytest

import k4s_end_launch_gate as G
import k4s_end_launch_remote as R
from helpers import ROOT, SHIMS, Store, sha, write_detach

R4_QUIET = """apt-daily.service=inactive
apt-daily-upgrade.service=inactive
helper=   2368 Wed Sep 23 17:37:32 2026 unattended-upgr /usr/bin/python3 /usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal
maint_lines=<<>>
maint=0
who=0
"""
HELPER_PS = ("   2368 Wed Sep 23 17:37:32 2026 unattended-upgr /usr/bin/python3 "
             "/usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal\n")


def timer_line(unit, seconds_from_now):
    if seconds_from_now is None:
        return "n/a                         n/a      Mon 2026-10-12 04:20:06 UTC 2h ago  %s  x.service" % unit
    t = time.strftime("%a %Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() + seconds_from_now))
    return "%s 10h left  Mon 2026-10-12 04:20:06 UTC 2h 44min ago %s  x.service" % (t, unit)


def timers_text(*rows):
    return "\n".join(["NEXT LEFT LAST PASSED UNIT ACTIVATES"] + [timer_line(u, s) for u, s in rows] +
                     ["", "%d timers listed." % len(rows)]) + "\n"


# ---------------------------------------------------------------- site fixture (05 + one host in tmp)

class Site:
    def __init__(self, tmp, monkeypatch, host="127x03", kind="end"):
        self.tmp, self.host, self.kind, self.mp = tmp, host, kind, monkeypatch
        bases = {h: str(tmp / ("base" + h[-2:])) for h in G.HOST_BASES}
        monkeypatch.setattr(G, "HOST_BASES", bases)
        self.base = Path(bases[host])
        monkeypatch.setattr(G, "RECEIVE", {"end": tmp / "recv" / "end-received",
                                           "preflight": tmp / "recv" / "preflight-received"})
        monkeypatch.setattr(G, "QUIET_GAP_SECONDS", 0)
        monkeypatch.setattr(G, "POSTEXEC_SECONDS", 8)
        monkeypatch.setattr(G, "REMOTE_SHA256", sha(ROOT / "k4s_end_launch_remote.py"))
        monkeypatch.setattr(socket, "gethostname", lambda: "127x05")
        monkeypatch.setattr(G, "optimized", lambda: False)    # the -O refusal itself: test_gate_refuses_optimized
        for d in ("attempts", "preflight", "repository", "venv/bin", "runtime/reports/explore/k4s-confirm", "tools"):
            (self.base / d).mkdir(parents=True, exist_ok=True)
        self.detach = write_detach(self.base)
        (self.base / "venv/bin/python").symlink_to("/usr/bin/python3")
        self.script = self.base / "runtime/reports/explore/k4s-confirm/end_reference.py"
        self.script.write_text("import time, pathlib, sys\ntime.sleep(2)\n")
        self.pre_script = self.base / "tools" / "k4s_end_preflight.py"
        self.pre_script.write_text("import time\ntime.sleep(2)\n")
        self.wrapper = self.base / "K4S-exit-push.sh"
        self.wrapper.write_text('#!/usr/bin/env bash\njob=$1; shift\necho ran > "$job/WRAPPER-RAN"\n"$@"\n'
                                'echo $? > "$job/STUB-EXIT"\n')
        self.pre_wrapper = self.base / "tools" / "k4s_preflight_push.sh"
        self.pre_wrapper.write_text(self.wrapper.read_text())
        monkeypatch.setattr(G, "WRAPPER_SHA256", {"end": sha(self.wrapper), "preflight": sha(self.pre_wrapper)})
        monkeypatch.setattr(G, "PREFLIGHT_SHA256", sha(self.pre_script))
        stamps = {}
        for key, age in (("release_upgrade_available", 3600), ("updates_available", 100), ("apt_lists", 200)):
            p = tmp / "stamps" / key
            p.parent.mkdir(exist_ok=True)
            p.write_text("")
            os.utime(p, (time.time() - age, time.time() - age))
            stamps[key] = str(p)
        monkeypatch.setattr(G, "STAMPS", stamps)
        self.timers = tmp / "timers.txt"
        self.timers.write_text(timers_text(("apt-daily.timer", 5 * 3600), ("motd-news.timer", 3 * 3600),
                                           ("fstrim.timer", None)))
        self.quiet_ps = tmp / "quiet-ps.txt"
        self.quiet_ps.write_text(HELPER_PS)
        self.log = tmp / "fake.log"
        env = dict(PATH=str(SHIMS) + os.pathsep + os.environ["PATH"], FAKE_LOG=str(self.log), FAKE_HOST=host,
                   FAKE_TIMERS=str(self.timers), FAKE_QUIET_PS=str(self.quiet_ps), FAKE_CHILD_MARK=str(tmp),
                   FAKE_REMOTE_PY="/usr/bin/python3")
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        self.n = 0

    def argv(self, kind=None, launch=None, **opts):
        kind = kind or self.kind
        if kind == "end":
            job = self.base / "attempts" / ("end-%s-r00-l%02d" % (self.host, launch if launch is not None else self.n))
            script, wrapper = self.script, self.wrapper
            o = {"--bundle": "B", "--runtime-root": str(self.base / "runtime"), "--native": "N", "--corpus": "C",
                 "--corpus-inventory": "CI", "--k4s-manifest-sha256": "1", "--sd1-manifest-sha256": "2",
                 "--end-evidence": "E", "--end-evidence-sha256": "3", "--repository": str(self.base / "repository"),
                 "--end-job-sha256": "4", "--round": "0", "--out": None}
            tail = [str(script)]
        else:
            job = self.base / "preflight" / ("preflight-%s-l%02d" % (self.host, launch if launch is not None else self.n))
            script, wrapper = self.pre_script, self.pre_wrapper
            o = {"--bundle": "B", "--runtime-root": str(self.base / "runtime"), "--native": "N", "--corpus": "C",
                 "--corpus-inventory": "CI", "--k4s-manifest-sha256": "1", "--sd1-manifest-sha256": "2",
                 "--end-evidence": "E", "--end-evidence-sha256": "3", "--repository": str(self.base / "repository"),
                 "--attempt-parent": str(self.base / "attempts"), "--out": None, "--hold-seconds": "960"}
            tail = [str(script), "run"]
        o["--out"] = str(job / job.name)
        o.update(opts)
        argv = ["nice", "-n", "10", "taskset", "-c", "61", "bash", str(self.detach), str(job / "detach.log"),
                str(job / "detach.json"), "bash", str(wrapper), str(job), "env", "OMP_NUM_THREADS=1",
                "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", str(self.base / "venv/bin/python"), "-B"] + tail
        for k, v in o.items():
            if v is not None:
                argv += [k, v] if v is not True else [k]
        return argv, job

    def prepare(self, job, kind=None):
        kind = kind or self.kind
        root = G.RECEIVE[kind] / self.host / job.name
        root.mkdir(parents=True)
        if kind == "preflight":
            return None
        proof = dict(receive=str(root), host=self.host, attempt=job.name, created_empty=True, nonce="a" * 32,
                     utc=G.iso(time.time() - 60))
        (root / "PREPARED.json").write_text(json.dumps(proof, sort_keys=True) + "\n")
        copy = self.tmp / ("proof-%s.json" % job.name)
        copy.write_text((root / "PREPARED.json").read_text())
        return copy

    def preflights(self):
        out = []
        for h in G.HOST_BASES:
            p = self.tmp / ("PREFLIGHT-VERIFIED-%s.json" % h)
            p.write_text(json.dumps(dict(host=h, passed=True, registry_and_attempt_parent_unchanged=True)))
            out += ["--preflight-verified", "%s:%s" % (p, sha(p))]
        return out

    def launch(self, argv=None, job=None, extra=(), prepare=True, kind=None):
        kind = kind or self.kind
        if argv is None:
            argv, job = self.argv(kind=kind)
        self.n += 1
        a = self.tmp / ("argv-%s.json" % job.name)
        a.write_text(json.dumps(argv))
        receipt = self.tmp / ("receipt-%s.json" % job.name)
        cli = ["launch", "--host", self.host, "--kind", kind, "--argv-json", str(a),
               "--argv-sha256", G.sha_bytes(G.argv_nul(argv)), "--quiet-cmd", str(ROOT / "quiet-read-v3.cmd"),
               "--receipt-out", str(receipt)]
        proof = self.prepare(job, kind) if prepare else None
        if proof:
            cli += ["--prepare-proof", str(proof), "--prepare-proof-sha256", sha(proof)]
        if kind == "end":
            cli += self.preflights()
        cli += list(extra)
        code = G.main(cli)
        doc = json.loads(receipt.read_text()) if receipt.exists() else None
        if doc and doc.get("launched"):
            limit = time.time() + 15
            while not (job / "STUB-EXIT").exists() and time.time() < limit:
                time.sleep(.2)
        return code, doc, job


@pytest.fixture
def site(tmp_path, monkeypatch):
    return Site(tmp_path, monkeypatch)


# ---------------------------------------------------------------- end to end

def test_launch_happy_path(site):
    code, doc, job = site.launch()
    assert code == 0 and doc["launched"] is True, doc and doc["host_gate"]["failures"]
    gate = doc["C5_preexec_gate"]
    assert gate["preexec_gate_pass"] and gate["ps_nice"] == "0" and gate["SCHED_OTHER"] and gate["command_byte_equal"]
    assert doc["postexec"]["python_visible"] and doc["postexec"]["postexec_priority_pass"]
    assert doc["postexec"]["no_signals_sent"] is True
    assert (job / "detach.json").is_file() and (job / "WRAPPER-RAN").is_file()
    assert (job / "STUB-EXIT").read_text().strip() == "0"
    assert doc["utc"] == json.loads((job / "detach.json").read_text())["launched_at_utc"]
    assert doc["measurement_argv"][0] == "env" and doc["launch_command"][:3] == ["nice", "-n", "10"]
    host = doc["host_gate"]
    assert host["quiet_1"]["helper_changed"] is False and host["quiet_2"]["values"]["maint"] == 0
    assert {t["unit"] for t in host["timers"]["timers"]} == {"apt-daily.timer", "motd-news.timer", "fstrim.timer"}
    log = site.log.read_text()
    assert "TZ=UTC LC_ALL=C ARGS=list-timers --all --no-pager" in log
    sessions = [l for l in log.splitlines() if l.startswith("SSH ") and " -O " not in l]
    assert len(sessions) == 1 and "ControlMaster=no" in sessions[0] and "ControlPath=none" in sessions[0]
    assert doc["session_open_utc"] <= doc["session_close_utc"]


def test_launch_preflight_kind(tmp_path, monkeypatch):
    s = Site(tmp_path, monkeypatch, kind="preflight")
    code, doc, job = s.launch()
    assert code == 0 and doc["launched"] is True
    assert doc["host_gate"]["file_pins"][str(s.pre_script)]["matches"] is True


def refused(site, code, doc, job, needle):
    assert code == 3, doc and doc["host_gate"]
    assert doc["launched"] is False and not job.exists()
    assert any(needle in f for f in doc["host_gate"]["failures"]), doc["host_gate"]["failures"]


@pytest.mark.parametrize("setup,needle", [
    (lambda s: s.mp.setenv("FAKE_ACTIVE_apt_daily_service", "active"), "apt-daily.service"),
    (lambda s: s.mp.setenv("FAKE_ACTIVE_apt_daily_upgrade_service", "activating"), "apt-daily-upgrade"),
    (lambda s: ((s.tmp / "who").write_text("student tty2 2026-10-12 08:00\n"), s.mp.setenv("FAKE_WHO", str(s.tmp / "who"))),
     "who"),
    (lambda s: s.quiet_ps.write_text(HELPER_PS + "   4242 Mon Oct 12 15:00:00 2026 apt-get /usr/bin/apt-get update\n"),
     "maint"),
    (lambda s: s.timers.write_text(timers_text(("apt-daily.timer", 5 * 3600), ("anacron.timer", 1800))),
     "anacron.timer"),
    (lambda s: s.timers.write_text(timers_text(("apt-daily.timer", -10))), "apt-daily.timer"),
    (lambda s: s.timers.write_text("NEXT LEFT\nsoon weird.timer\n"), "unparseable"),
    (lambda s: s.timers.write_text("NEXT LEFT\n0 timers listed.\n"), "no timer"),
    (lambda s: s.mp.setenv("FAKE_TIMERS_RC", "1"), "systemctl rc"),
    (lambda s: os.utime(G.STAMPS["release_upgrade_available"], (time.time() - 80000,) * 2), "release-upgrade"),
    (lambda s: os.utime(G.STAMPS["updates_available"], (time.time() - 300,) * 2), "updates-available"),
    (lambda s: Path(G.STAMPS["apt_lists"]).unlink(), "missing"),
    (lambda s: ((s.tmp / "ps-extra").write_text("  55555       1   0  TS sshd: someone [priv]\n"),
                s.mp.setenv("FAKE_PS_EXTRA", str(s.tmp / "ps-extra"))), "other SSH sessions"),
    (lambda s: s.mp.setenv("FAKE_GATE_NI", "5"), "C5 pre-exec gate"),
    (lambda s: s.wrapper.write_text(s.wrapper.read_text() + "# tampered\n"), "pin"),
    (lambda s: s.mp.setenv("FAKE_HOST", "127x04"), "host is"),
], ids=["apt-daily", "apt-upgrade-activating", "who", "maint", "timer-close", "timer-overdue", "timer-garbled",
        "timer-none", "timer-rc", "stamp-stale", "stamp-order", "stamp-missing", "sshd-session", "gate-nice",
        "wrapper-pin", "wrong-host"])
def test_host_refusals(site, setup, needle):
    setup(site)
    code, doc, job = site.launch()
    if needle == "host is":
        assert code == 3 and doc["host_gate"]["failures"] == ["host is '127x04'"] and not job.exists()
        return
    refused(site, code, doc, job, needle)


def test_allowlisted_timer_launches(site):
    site.timers.write_text(timers_text(("apt-daily.timer", 5 * 3600), ("anacron.timer", 1800)))
    code, doc, job = site.launch(extra=["--allow-timer", "anacron.timer=hourly; idle in K4S reporting (ref)"])
    assert code == 0 and doc["launched"]
    assert [t for t in doc["host_gate"]["timers"]["timers"] if t["unit"] == "anacron.timer"][0]["allowlisted"]


def test_helper_change_is_noted_not_fatal(site):
    site.quiet_ps.write_text(HELPER_PS.replace("2368", "9999"))
    code, doc, job = site.launch()
    assert code == 0 and doc["host_gate"]["quiet_2"]["helper_changed"] is True


def test_existing_job_refused(site):
    argv, job = site.argv()
    job.mkdir()
    code, doc, _ = site.launch(argv, job)
    assert code == 3 and any("job" in f for f in doc["host_gate"]["failures"])


def test_registry_attempt_limits(site):
    reg = site.base / "repository/reports/explore/k4s-confirm/end/registry/round-00" / site.host
    reg.mkdir(parents=True)
    (reg / "attempt-00.json").write_text("{}")
    code, doc, job = site.launch()
    refused(site, code, doc, job, "coordinator ruling")
    code, doc, job = site.launch(extra=["--second-attempt-ruling", "COORDINATOR 2026-10-13 ruling abc123"])
    assert code == 0 and doc["host_gate"]["registry"]["claims"] == 1
    (reg / "attempt-01.json").write_text("{}")
    code, doc, job = site.launch(extra=["--second-attempt-ruling", "x"])
    refused(site, code, doc, job, "two claims")


def test_local_controlmaster_refused_before_any_session(site, monkeypatch):
    monkeypatch.setenv("FAKE_MUX_RC", "0")
    with pytest.raises(G.GateRefusal, match="ControlMaster"):
        site.launch()
    assert all(" -O " in l for l in site.log.read_text().splitlines() if l.startswith("SSH "))


def test_local_refusals(site):
    argv, job = site.argv()
    a = site.tmp / "argv.json"
    a.write_text(json.dumps(argv))
    base = ["launch", "--host", "127x03", "--kind", "end", "--argv-json", str(a), "--quiet-cmd",
            str(ROOT / "quiet-read-v3.cmd"), "--receipt-out", str(site.tmp / "r.json")]
    with pytest.raises(G.GateRefusal, match="pin"):
        G.main(base + ["--argv-sha256", "0" * 64])
    good = ["--argv-sha256", G.sha_bytes(G.argv_nul(argv))]
    bad_quiet = site.tmp / "q.cmd"
    bad_quiet.write_text((ROOT / "quiet-read-v3.cmd").read_text().replace("who=", "WHO="))
    with pytest.raises(G.GateRefusal, match="v3"):
        G.main([x if x != str(ROOT / "quiet-read-v3.cmd") else str(bad_quiet) for x in base] + good)
    with pytest.raises(G.GateRefusal, match="not prepared"):
        G.main(base + good)
    proof = site.prepare(job)
    with pytest.raises(G.GateRefusal, match="Prepare proof SHA"):
        G.main(base + good + ["--prepare-proof", str(proof), "--prepare-proof-sha256", "0" * 64])
    p = ["--prepare-proof", str(proof), "--prepare-proof-sha256", sha(proof)]
    with pytest.raises(G.GateRefusal, match="Both host preflights"):
        G.main(base + good + p)
    (G.RECEIVE["end"] / "127x03" / job.name / "extra").write_text("")
    with pytest.raises(G.GateRefusal, match="only PREPARED"):
        G.main(base + good + p + site.preflights())
    (G.RECEIVE["end"] / "127x03" / job.name / "extra").unlink()
    with pytest.raises(G.GateRefusal, match="Clearance"):
        G.main(base + good + p + site.preflights() + ["--clearance-seconds", "7199"])
    with pytest.raises(G.GateRefusal, match="allow-timer"):
        G.main(base + good + p + site.preflights() + ["--allow-timer", "anacron.timer="])
    (site.tmp / "r.json").write_text("")
    with pytest.raises(G.GateRefusal, match="Receipt already exists"):
        G.main(base + good + p + site.preflights())


def test_prerequisites_rc9(site, tmp_path):
    ns = lambda **k: type("A", (), dict(dict(kind="end", host="127x03", preflight_verified=None, prior_03_ack=None), **k))
    with pytest.raises(G.GateRefusal, match="Both"):
        G.prerequisites(ns())
    flags = site.preflights()
    specs = flags[1::2]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(host="127x04", passed=False)))
    with pytest.raises(G.GateRefusal, match="did not pass"):
        G.prerequisites(ns(preflight_verified=[specs[0], "%s:%s" % (bad, sha(bad))]))
    assert set(G.prerequisites(ns(preflight_verified=specs))["preflights"]) == {"127x03", "127x04"}
    with pytest.raises(G.GateRefusal, match="03's verified complete"):
        G.prerequisites(ns(host="127x04", preflight_verified=specs))
    ack = tmp_path / "ack.json"
    ack.write_text(json.dumps(dict(host="127x03", classification="SEALED", status="failed", ack_allowed=True)))
    with pytest.raises(G.GateRefusal, match="not complete"):
        G.prerequisites(ns(host="127x04", preflight_verified=specs, prior_03_ack="%s:%s" % (ack, sha(ack))))
    ack.write_text(json.dumps(dict(host="127x03", classification="SEALED", status="complete", ack_allowed=True)))
    out = G.prerequisites(ns(host="127x04", preflight_verified=specs, prior_03_ack="%s:%s" % (ack, sha(ack))))
    assert out["prior_03_ack_sha256"] == sha(ack)
    with pytest.raises(G.GateRefusal, match="SHA mismatch"):
        G.prerequisites(ns(host="127x04", preflight_verified=specs, prior_03_ack="%s:%s" % (ack, "0" * 64)))
    assert G.prerequisites(ns(kind="preflight")) == {}


# ---------------------------------------------------------------- argv structure (05, pure)

def mutate(argv, index_of=None, value=None, insert=None, drop=None):
    argv = list(argv)
    if drop is not None:
        i = argv.index(drop)
        del argv[i:i + 2]
    if index_of is not None:
        argv[argv.index(index_of) + 1] = value
    if insert is not None:
        argv[insert[0]:insert[0]] = insert[1]
    return argv


@pytest.mark.parametrize("change,needle", [
    (lambda a, s: ["nice", "-n", "19"] + a, "frozen inner nice"),
    (lambda a, s: a[3:], "frozen inner nice"),
    (lambda a, s: a[:5] + ["60"] + a[6:], "frozen inner nice"),
    (lambda a, s: a[:6] + ["sh"] + a[7:], "bash"),
    (lambda a, s: a[:12] + [str(s.base / "attempts" / "end-127x04-r00-l00")] + a[13:], "Job must"),
    (lambda a, s: a[:12] + [str(s.base / "preflight" / "end-127x03-r00-l00")] + a[13:], "Job must"),
    (lambda a, s: a[:12] + [str(s.base / "attempts" / "end-127x03-r0-l00")] + a[13:], "Job must"),
    (lambda a, s: a[:8] + ["/tmp/detach.log"] + a[9:], "Detach log"),
    (lambda a, s: a[:7] + ["/elsewhere/detach.sh"] + a[8:], "staged under"),
    (lambda a, s: a[:13] + ["nice", "-n", "10"] + a[13:], "start with env"),
    (lambda a, s: mutate(a, insert=(17, ["nice", "-n", "10"])), "priority/scheduler"),
    (lambda a, s: mutate(a, insert=(17, ["EXTRA=1"])), "Environment"),
    (lambda a, s: [x for x in a if x != "MKL_NUM_THREADS=1"], "Environment"),
    (lambda a, s: mutate(a, insert=(17, ["PYTHONPATH=a", "PYTHONPATH=b"])), "Repeated env"),
    (lambda a, s: [x if x != "-B" else "-O" for x in a], "optimizer"),
    (lambda a, s: mutate(a, insert=(19, ["-u"])), "end_reference"),
    (lambda a, s: [x if x != "OMP_NUM_THREADS=1" else "OMP_NUM_THREADS=1" for x in a] + ["--kernel", "k"],
     "Unknown"),
    (lambda a, s: mutate(a, drop="--end-job-sha256"), "exactly the required"),
    (lambda a, s: a + ["--round", "0"], "Repeated option"),
    (lambda a, s: mutate(a, drop="--out") + ["--ou", "x"], "Unknown"),
    (lambda a, s: mutate(a, drop="--out") + ["--out=x"], "Unexpected"),
    (lambda a, s: mutate(a, index_of="--out", value="/tmp/x"), "--out must"),
    (lambda a, s: mutate(a, index_of="--repository", value=str(s.base / "runtime")), "--repository must"),
    (lambda a, s: mutate(a, index_of="--round", value="1"), "attempt name"),
    (lambda a, s: mutate(a, index_of="--round", value="01"), "attempt name"),
    (lambda a, s: mutate(a, index_of="--runtime-root", value="/elsewhere"), "end_reference.py"),
    (lambda a, s: mutate(a, index_of="--bundle", value="--x"), "looks like an option"),
], ids=["outer-nice", "no-nice", "cpu", "sh", "job-host", "job-parent", "job-name", "log", "detach", "inner-nice",
        "nice-after-env",
        "env-extra", "env-missing", "env-repeat", "opt-O", "flag-u", "kernel", "no-endjob", "repeat", "abbrev",
        "eq-form", "out", "repository", "round-name", "round-format", "runtime", "value-option"])
def test_end_argv_refusals(site, change, needle):
    argv, job = site.argv()
    assert G.validate_argv(argv, "end", "127x03")["job"] == str(job)
    with pytest.raises(G.GateRefusal, match=needle):
        G.validate_argv(change(argv, site), "end", "127x03")


def test_preflight_argv(tmp_path, monkeypatch):
    s = Site(tmp_path, monkeypatch, kind="preflight")
    argv, job = s.argv()
    shape = G.validate_argv(argv, "preflight", "127x03")
    assert shape["registry_dir"] is None and str(s.pre_script) in shape["file_pins"]
    with pytest.raises(G.GateRefusal, match="run subcommand"):
        G.validate_argv([x for x in argv if x != "run"], "preflight", "127x03")
    with pytest.raises(G.GateRefusal, match="attempt-parent"):
        G.validate_argv(mutate(argv, index_of="--attempt-parent", value=str(s.base / "preflight")), "preflight", "127x03")
    flag = argv + ["--no-reference-work"]
    assert G.validate_argv(flag, "preflight", "127x03")
    with pytest.raises(G.GateRefusal, match="staged k4s_end_preflight"):
        G.validate_argv([x if not x.endswith("k4s_end_preflight.py") else str(s.script) for x in argv],
                        "preflight", "127x03")
    s4 = Site(tmp_path / "h4", monkeypatch, host="127x04", kind="preflight")
    argv4, _ = s4.argv(**{"--hold-seconds": "899"})
    with pytest.raises(G.GateRefusal, match="RC-2"):
        G.validate_argv(argv4, "preflight", "127x04")
    argv4, _ = s4.argv(**{"--hold-seconds": "960"})
    assert G.validate_argv(argv4, "preflight", "127x04")


# ---------------------------------------------------------------- host-side parsers (pure)

def test_parse_quiet_r4_sample_and_failures():
    ok = R.parse_quiet(R4_QUIET, 0, 2368)
    assert ok["failures"] == [] and ok["helper_changed"] is False and ok["helper_pids"] == [2368]
    assert R.parse_quiet(R4_QUIET, 0, 2296)["helper_changed"] is True
    assert R.parse_quiet(R4_QUIET, 0, 2296)["failures"] == []
    for text, rc, needle in [
        (R4_QUIET.replace("apt-daily.service=inactive", "apt-daily.service=active"), 0, "apt-daily.service"),
        (R4_QUIET.replace("apt-daily-upgrade.service=inactive", "apt-daily-upgrade.service=deactivating"), 0, "upgrade"),
        (R4_QUIET.replace("maint=0", "maint=1"), 0, "maint"),
        (R4_QUIET.replace("who=0", "who=1"), 0, "who"),
        (R4_QUIET, 1, "rc"),
        (R4_QUIET.replace("maint_lines", "x"), 0, "helper line"),
        ("", 0, "apt-daily.service"),
    ]:
        assert any(needle in f for f in R.parse_quiet(text, rc, 2368)["failures"]), (needle, text)
    two = R4_QUIET.replace("--wait-for-signal\n", "--wait-for-signal\n   77 x unattended-upgr y\n", 1)
    assert R.parse_quiet(two, 0, 2368)["helper_pids"] == [2368, 77]


def test_parse_timers_epoch_and_allowlist():
    now = calendar.timegm((2026, 10, 12, 20, 0, 0))
    text = ("NEXT LEFT LAST PASSED UNIT ACTIVATES\n"
            "Mon 2026-10-12 23:00:00 UTC 3h left Mon 2026-10-12 04:20:06 UTC 2h ago apt-daily.timer apt-daily.service\n"
            "Mon 2026-10-12 21:00:00 UTC 1h left n/a n/a anacron.timer anacron.service\n"
            "n/a n/a n/a n/a snapd.snap-repair.timer snapd.snap-repair.service\n\n3 timers listed.\n")
    timers, failures = R.parse_timers(text, now, 7200, {})
    assert [t["clearance_seconds"] for t in timers] == [10800, 3600, None]
    assert failures == ["timers: anacron.timer fires in 3600s (< 7200s)"]
    assert R.parse_timers(text, now, 7200, {"anacron.timer": "why"})[1] == []


def test_other_ssh_sessions_excludes_own_ancestry():
    table = {1: dict(pid=1, ppid=0, args="sshd: /usr/sbin/sshd -D [listener] 0 of 10-100 startups"),
             10: dict(pid=10, ppid=1, args="sshd: sdicks02 [priv]"), 11: dict(pid=11, ppid=10, args="sshd: sdicks02@notty"),
             12: dict(pid=12, ppid=11, args="/usr/bin/python3 -I -B -"),
             20: dict(pid=20, ppid=1, args="sshd: sdicks02 [priv]"), 21: dict(pid=21, ppid=20, args="sshd: sdicks02@notty")}
    assert R.other_ssh_sessions(table, 12) == [20, 21]
    del table[20], table[21]
    assert R.other_ssh_sessions(table, 12) == []


def test_stamps_rules(tmp_path):
    now = time.time()
    paths = {}
    for key, age in (("release_upgrade_available", 3600), ("updates_available", 100), ("apt_lists", 200)):
        p = tmp_path / key
        p.write_text("")
        os.utime(p, (now - age, now - age))
        paths[key] = str(p)
    cfg = dict(stamps=paths, window_seconds=7200)
    assert R.stamps_check(cfg, now)["failures"] == []
    os.utime(paths["release_upgrade_available"], (now - (86400 - 7200) - 5,) * 2)
    assert "stale" in R.stamps_check(cfg, now)["failures"][0]


# ---------------------------------------------------------------- admission vs session close

def test_admission_record(site, tmp_path):
    receipt = tmp_path / "launch.json"
    attempt = "end-127x03-r00-l00"
    root = G.RECEIVE["end"] / "127x03" / attempt
    store = Store(root / "durable-measurement", "K4S-END-REFERENCE")
    admitted = time.time()
    store.write("guard-admission.json", dict(utc=admitted, event="admit"))
    store.seal("complete")
    (root / "DURABLE-ACK.json").write_text("{}")
    for close, expected in ((admitted - 30, 0), (admitted + 30, 2)):
        receipt.write_text(json.dumps(dict(kind="end", host="127x03", attempt=attempt, session_close_utc=G.iso(close))))
        out = tmp_path / ("adm-%d.json" % expected)
        code = G.main(["admission", "--launch-receipt", str(receipt), "--launch-receipt-sha256", sha(receipt),
                       "--out", str(out)])
        assert code == expected and json.loads(out.read_text())["closed_before_admission"] is (expected == 0)


def test_gate_refuses_off_05_and_optimized(site, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "127x03")
    with pytest.raises(G.GateRefusal, match="127x05"):
        site.launch()


def test_host_program_reports_unexpected_exception(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setenv("PATH", str(SHIMS) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_HOST", "127x03")
    program = b"import json\nCONFIG = json.loads('{\"host\": \"127x03\", \"kind\": \"end\"}')\n" + \
        (ROOT / "k4s_end_launch_remote.py").read_bytes()
    done = subprocess.run(["/usr/bin/python3", "-I", "-B", "-"], input=program, capture_output=True)
    line = [l for l in done.stdout.decode().splitlines() if l.startswith(R.MARK)]
    assert done.returncode == 3 and len(line) == 1
    result = json.loads(line[0][len(R.MARK):])
    assert result["launched"] is False and "exception in host gate" in result["failures"][-1]


def test_gate_refuses_optimized(tmp_path):
    """Both subcommands refuse under python -O (real check, no patch); this host is 127x05."""
    import subprocess
    if socket.gethostname() != "127x05":
        pytest.skip("hostname check precedes the -O check")
    for argv in (["launch", "--host", "127x03", "--kind", "end", "--argv-json", "x", "--argv-sha256", "0",
                  "--quiet-cmd", "q", "--receipt-out", str(tmp_path / "r")],
                 ["admission", "--launch-receipt", "x", "--launch-receipt-sha256", "0", "--out", str(tmp_path / "o")]):
        done = subprocess.run([sys.executable, "-O", str(ROOT / "k4s_end_launch_gate.py")] + argv,
                              capture_output=True, text=True)
        assert done.returncode != 0 and "not under -O" in done.stderr
    assert not (tmp_path / "r").exists() and not (tmp_path / "o").exists()
