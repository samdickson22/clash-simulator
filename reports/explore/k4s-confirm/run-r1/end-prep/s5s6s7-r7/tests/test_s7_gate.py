"""S7 launch gate r2: 05-side RC-6/argv/RC-9 validation through safe_input, host-side parsers, and end-to-end
launches through a generated fake ssh that runs the composed host program (shipped safe_input + host tool, SHA
checked on the "host") under /usr/bin/python3 3.8, with fake ps/systemctl/who/hostname/nice/taskset, the real
frozen detach.sh and stub wrapper/END scripts. Includes Sol's probes: host base symlink -> foreign launch dir,
failed ps (rc 37) with a valid table, schema-less Boolean preflight documents, 0.8 % bus without a ruling."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

import helpers as H
import host_shims
import k4s_end_launch_gate as G
import k4s_end_launch_remote as R
from helpers import ROOT, ok, raises

R4_QUIET = """apt-daily.service=inactive
apt-daily-upgrade.service=inactive
helper=   2368 Wed Sep 23 17:37:32 2026 unattended-upgr /usr/bin/python3 /usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal
maint_lines=<<>>
maint=0
who=0
"""
HELPER_PS = ("   2368 Wed Sep 23 17:37:32 2026 unattended-upgr /usr/bin/python3 "
             "/usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal\n")
RUNTIME = "runtime-0123456789ab"
GUARDS = {"pf00": "pf00", "a00": "rd00-a00", "a01": "rd00-a01", "r1a00": "rd01-a00"}
END_REFERENCE_STUB = "import time\ntime.sleep(2)\n"
STUB_WRAPPER = '#!/usr/bin/env bash\njob=$1; shift\necho ran > "$job/WRAPPER-RAN"\n"$@"\necho $? > "$job/STUB-EXIT"\n'


def end_job_bytes(**over):
    """A synthetic END-JOB (frozen JOB_FIELDS) bound to the gate's END evidence of record and K4S manifest."""
    job = dict(schema=G.END_JOB_SCHEMA, study="PREREG-K4S", end_evidence_sha256=G.END_EVIDENCE_SHA256,
               completion_sha256="3" * 64, plan_sha256="9" * 64, k4s_manifest_sha256=G.K4S_MANIFEST_SHA256,
               counted_hosts=["127x03", "127x04"], declared_utc="2026-10-13T00:00:00Z", declared_by="test")
    job.update(over)
    return (json.dumps(job, indent=1, sort_keys=True) + "\n").encode()


def timer_line(unit, seconds_from_now):
    if seconds_from_now is None:
        return "n/a                         n/a      Mon 2026-10-12 04:20:06 UTC 2h ago  %s  x.service" % unit
    t = time.strftime("%a %Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() + seconds_from_now))
    return "%s 10h left  Mon 2026-10-12 04:20:06 UTC 2h 44min ago %s  x.service" % (t, unit)


def timers_text(*rows):
    return "\n".join(["NEXT LEFT LAST PASSED UNIT ACTIVATES"] + [timer_line(u, s) for u, s in rows] +
                     ["", "%d timers listed." % len(rows)]) + "\n"


class Site:
    """05 (launch inputs, receive dirs) and both fake hosts' k4s-end-r1 layouts under tmp_path."""

    def __init__(self, tmp, mp, host="127x03"):
        self.tmp, self.host, self.mp = tmp, host, mp
        self.si, self.tool = G.load_layers(str(ROOT))
        self.shims = host_shims.Shims(tmp / "hshims")
        mp.setattr(G, "LAUNCH_BASE", str(tmp / "end-launch"))
        mp.setattr(G, "RECEIVE", {"end": str(tmp / "recv" / "end-received"),
                                  "preflight": str(tmp / "recv" / "preflight-received")})
        mp.setattr(G, "QUIET_GAP_SECONDS", 0)
        mp.setattr(G, "optimized", lambda: False)   # test-only: the real -O refusal is test_gate_refuses_optimized
        mp.setattr(G, "POSTEXEC_SECONDS", 8)
        mp.setattr(G, "SSH_BINARY", self.shims.path("ssh"))
        mp.setattr(G, "HOST_PATH", str(self.shims.dir) + ":/usr/bin:/bin")
        mp.setattr(G, "HOST_BIN", dict(G.HOST_BIN, **{n: self.shims.path(n) for n in ("ps", "hostname", "systemctl",
                                                                                        "who")}))
        mp.setattr(G, "MIN_PREFLIGHT_HOLD", {"127x03": 120, "127x04": 900})
        self.stub_wrapper = STUB_WRAPPER
        mp.setattr(G, "WRAPPER_SHA256", {"end": H.sha_bytes(STUB_WRAPPER.encode()),
                                         "preflight": H.sha_bytes(STUB_WRAPPER.encode())})
        self.pre_script = "import time\ntime.sleep(2)\n"
        mp.setattr(G, "PREFLIGHT_SHA256", H.sha_bytes(self.pre_script.encode()))
        # r4: the gate pins the host python and end_reference.py (L1); test-only stand-ins (r5 U4: the venv layout of
        # runtime.sh's <repo>/.venv/bin/python)
        python = tmp / "clasher" / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        os.symlink("/usr/bin/python3", python)
        mp.setattr(G, "HOST_PYTHON", str(python))
        mp.setattr(G, "END_REFERENCE_SHA256", H.sha_bytes(END_REFERENCE_STUB.encode()))
        self.end_job_sha = {}
        self.decl = dict(schema=G.ROOTS_SCHEMA, commit="c" * 40, hosts={})
        self.sans, self.pf_used = {}, {}
        for h in G.END_HOSTS:
            self.decl["hosts"][h] = self.host_fs(h)
        Path(G.LAUNCH_BASE).mkdir(parents=True)
        self.roots_sha = H.sha(H.write(Path(G.LAUNCH_BASE) / "ROOTS-DECLARATION.json",
                                       json.dumps(self.decl, sort_keys=True)))
        stamps = {}
        for key, (d, rel), age in (("release_upgrade_available", ("ru", "release-upgrade-available"), 3600),
                                   ("updates_available", ("un", "updates-available"), 100),
                                   ("apt_lists", ("apt", "lists"), 200)):
            root = tmp / "stamps" / d
            p = root / rel
            if key == "apt_lists":
                p.mkdir(parents=True)
            else:
                H.write(p, b"")
            os.utime(p, (time.time() - age, time.time() - age))
            stamps[key] = (str(root), rel)
        mp.setattr(G, "STAMPS", stamps)
        self.timers = H.write(tmp / "timers.txt", timers_text(("apt-daily.timer", 5 * 3600),
                                                               ("motd-news.timer", 3 * 3600), ("fstrim.timer", None)))
        self.quiet_ps = H.write(tmp / "quiet-ps.txt", HELPER_PS)
        self.log = tmp / "fake.log"
        self.shims.set(FAKE_LOG=self.log, FAKE_HOST=host, FAKE_TIMERS=self.timers, FAKE_QUIET_PS=self.quiet_ps,
                       FAKE_CHILD_MARK=str(tmp), HOME=tmp / "home")
        (tmp / "home").mkdir(exist_ok=True)

    def host_fs(self, h):
        fs = self.tmp / ("hostfs" + h[-2:])
        base, q4 = fs / "k4s-end-r1", fs / "q4"
        self.mp.setitem(self.si.END_BASES, h, str(base))
        self.mp.setitem(self.si.Q4_GUARD_PARENTS, h, str(q4))
        tools = base / "tools"
        H.copy_tools(tools)
        shutil.copyfile(ROOT / "t1-originals" / "detach.sh", tools / "detach.sh")
        for name in ("k4s_end_exit_push.sh", "k4s_preflight_push.sh"):
            H.write(tools / name, self.stub_wrapper, 0o755)
        H.write(tools / "k4s_end_preflight.py", self.pre_script)
        H.write(base / RUNTIME / "reports/explore/k4s-confirm/end_reference.py", END_REFERENCE_STUB)
        H.write(base / RUNTIME / G.CORPUS_INVENTORY_REL, b"{}\n")
        for d in ("attempts", "preflight", "venv/bin"):
            (base / d).mkdir(parents=True, exist_ok=True)
        os.symlink("/usr/bin/python3", base / "venv/bin/python")
        H.write(base / "inputs/native.so", b"n")
        H.write(base / "inputs/k4-states.pkl", b"c")
        job = end_job_bytes()
        self.end_job_sha[h] = H.sha_bytes(job)
        H.git_repo(base / "repository", files={"reports/explore/k4s-confirm/README": b"study\n", G.END_JOB_REL: job})
        bundles = {}
        self.manifests = getattr(self, "manifests", {})
        for name, guard in GUARDS.items():
            job = q4 / ("k4s-end-guard-r1-" + guard)
            seeds = H.shallow_guard_repo(job / "repo", fs / "seed-sources" / guard)
            manifest = dict(profile="fleet-reference", files={G.END_EVIDENCE_REL: G.END_EVIDENCE_SHA256},
                            reference_load_profile=dict(host=h, guard=dict(job=str(job)), end_evidence=G.END_EVIDENCE_REL))
            digest = H.sha(H.write(base / "bundles" / name / "tiers-pins.json", H.canonical(manifest) + "\n"))
            self.sans[h] = self.tool.bundle_sans_guard_sha256(manifest)
            self.manifests[(h, name)] = manifest
            bundles[name] = dict(path=str(base / "bundles" / name), tiers_pins_sha256=digest, guard_job=str(job))
        self.mp.setattr(G, "SEED_COMMITS", seeds)
        return dict(base=str(base), runtime=str(base / RUNTIME), bundles=bundles, repository=str(base / "repository"),
                    attempts=str(base / "attempts"), preflight=str(base / "preflight"), tools=str(tools),
                    guard_parent=str(q4))

    # ------------------------------------------------------------ argv / inputs
    def argv(self, kind="end", attempt=None, bundle=None, host=None, **opts):
        h = host or self.host
        d = self.decl["hosts"][h]
        if kind == "end":
            attempt = attempt or "end-%s-r00-l00" % h
            job = d["attempts"] + "/" + attempt
            o = {"--bundle": d["bundles"][bundle or "a00"]["path"], "--runtime-root": d["runtime"],
                 "--native": d["base"] + "/inputs/native.so", "--corpus": d["base"] + "/inputs/k4-states.pkl",
                 "--corpus-inventory": d["runtime"] + "/" + G.CORPUS_INVENTORY_REL,
                 "--k4s-manifest-sha256": G.K4S_MANIFEST_SHA256, "--sd1-manifest-sha256": G.SD1_MANIFEST_SHA256,
                 "--end-evidence": d["bundles"][bundle or "a00"]["path"] + "/" + G.END_EVIDENCE_REL,
                 "--end-evidence-sha256": G.END_EVIDENCE_SHA256, "--repository": d["repository"],
                 "--end-job-sha256": self.end_job_sha[h],
                 "--round": "0", "--out": job + "/" + attempt}
            tail = [d["runtime"] + "/reports/explore/k4s-confirm/end_reference.py"]
            wrapper = d["tools"] + "/k4s_end_exit_push.sh"
        else:
            attempt = attempt or "preflight-%s-l00" % h
            job = d["preflight"] + "/" + attempt
            pf, at = d["bundles"]["pf00"], d["bundles"]["a00"]
            o = {"--bundle": pf["path"], "--bundle-pins-sha256": pf["tiers_pins_sha256"], "--runtime-root": d["runtime"],
                 "--native": d["base"] + "/inputs/native.so", "--corpus": d["base"] + "/inputs/k4-states.pkl",
                 "--corpus-inventory": d["runtime"] + "/" + G.CORPUS_INVENTORY_REL,
                 "--corpus-inventory-sha256": G.CORPUS_INVENTORY_SHA256, "--k4s-manifest-sha256": G.K4S_MANIFEST_SHA256,
                 "--sd1-manifest-sha256": G.SD1_MANIFEST_SHA256, "--end-evidence": pf["path"] + "/" + G.END_EVIDENCE_REL,
                 "--end-evidence-sha256": G.END_EVIDENCE_SHA256, "--repository": d["repository"],
                 "--attempt-parent": d["attempts"],
                 "--out": job + "/" + attempt, "--hold-seconds": "960" if h == "127x04" else "120",
                 "--compare-bundle": at["path"], "--compare-bundle-pins-sha256": at["tiers_pins_sha256"]}
            tail = [d["tools"] + "/k4s_end_preflight.py", "run"]
            wrapper = d["tools"] + "/k4s_preflight_push.sh"
        o.update(opts)
        argv = ["nice", "-n", "10", "taskset", "-c", "61", "bash", d["tools"] + "/detach.sh", job + "/detach.log",
                job + "/detach.json", "bash", wrapper, job, "env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1",
                "MKL_NUM_THREADS=1", G.HOST_PYTHON, "-B"] + tail
        for k, v in o.items():
            if v is not None:
                argv += [k] if v is True else [k, v]
        return argv, attempt

    def launch_dir(self, attempt, host=None):
        return Path(G.LAUNCH_BASE) / (host or self.host) / attempt

    def prepare(self, kind, attempt, host=None):
        h = host or self.host
        root = Path(G.RECEIVE[kind]) / h / attempt
        root.mkdir(parents=True, exist_ok=True)
        if kind == "preflight":
            return []
        proof = dict(receive=str(root), host=h, attempt=attempt, created_empty=True, nonce="a" * 32,
                     utc=G.iso(time.time() - 60))
        H.write(root / "PREPARED.json", json.dumps(proof, sort_keys=True) + "\n")
        sha = H.sha(H.write(self.launch_dir(attempt, h) / "PREPARE-PROOF.json", json.dumps(proof, sort_keys=True) + "\n"))
        return ["--prepare-proof-sha256", sha]

    def verified(self, h, bus_percent=0.05, **over):
        """A PREFLIGHT-VERIFIED.json (schema v3) + the sealed files it binds, under the declared receive path. The bus
        evidence is numerically consistent (percent = 100 ticks / hz / span) and banded by the P2-3 rule."""
        d = self.decl["hosts"][h]
        attempt = "preflight-%s-l00" % h
        root = Path(G.RECEIVE["preflight"]) / h / attempt
        seal = H.write(root / "preflight/receipt-manifest.json", b'{"synthetic": "seal"}\n')
        result = H.write(root / "preflight/preflight-result.json", b'{"synthetic": "result"}\n')
        pf, at = d["bundles"]["pf00"], d["bundles"]["a00"]
        seconds, hz = (958.0 if h == "127x04" else 118.0), 100
        band = G.bus_band(bus_percent)
        native, corpus = d["base"] + "/inputs/native.so", d["base"] + "/inputs/k4-states.pkl"
        inventory = d["runtime"] + "/" + G.CORPUS_INVENTORY_REL
        doc = dict(schema=G.VERIFIED_SCHEMA, scope="K4S-END-PREFLIGHT", host=h, attempt=attempt, receive=str(root),
                   status="passed", passed=True, mode="binding", qualifying=True, failed_checks=[],
                   registry_and_attempt_parent_unchanged=True, attempt_parent_empty=True,
                   login_detected_during_hold=False,
                   load=dict(reference_slot_work=True, reference_slot_states_worked=4000, background_slots_ready=10,
                             background_slots_expected=10, slot_count=11),
                   duration=dict(loaded_seconds_measured=seconds),
                   bus_band=band, bus_gate=band if h == "127x04" else "not-gated-on-" + h,
                   bus_cumulative_loaded=dict(percent=bus_percent, seconds=seconds, hz=hz,
                                              cpu_ticks=bus_percent * hz * seconds / 100.),
                   inputs=dict(runtime_root=d["runtime"], repository=d["repository"],
                               k4s_manifest_sha256=G.K4S_MANIFEST_SHA256, bundle=pf["path"],
                               bundle_pins_sha256=pf["tiers_pins_sha256"], guard_job=pf["guard_job"],
                               compare_bundle=at["path"], compare_bundle_pins_sha256=at["tiers_pins_sha256"],
                               end_evidence_sha256=G.END_EVIDENCE_SHA256, sd1_manifest_sha256=G.SD1_MANIFEST_SHA256,
                               native=native,
                               corpus=corpus, corpus_inventory=inventory,
                               corpus_inventory_sha256=G.CORPUS_INVENTORY_SHA256),
                   identity=dict(native=native, native_sha256=G.NATIVE_SHA256, corpus=corpus,
                                 corpus_sha256=G.CORPUS_SHA256, corpus_inventory=inventory,
                                 corpus_inventory_sha256=G.CORPUS_INVENTORY_SHA256),
                   bundle_identity=dict(bundle_sans_guard_sha256=self.sans[h],
                                        compare_bundle_sans_guard_sha256=self.sans[h]),
                   safe_input_sha256=G.SAFE_INPUT_SHA256, receipt_manifest_sha256=H.sha(seal),
                   preflight_result_sha256=H.sha(result))
        for k, v in over.items():
            if v is None:
                doc.pop(k, None)
            elif isinstance(v, dict) and k in ("inputs", "identity", "bundle_identity", "bus_cumulative_loaded") \
                    and v.pop("_merge", False):
                doc[k] = dict(doc[k], **v)
            else:
                doc[k] = v
        path = root / "PREFLIGHT-VERIFIED.json"
        if path.exists():
            os.chmod(path, 0o644)
        digest = H.sha(H.write(path, json.dumps(doc)))
        self.pf_used[h] = (attempt, digest)
        return ["--preflight-verified", "%s=%s:%s" % (h, attempt, digest)]

    def prior_03(self, attempt="end-127x03-r00-l00", **over):
        """03's SEALED complete ACK, its RC-7 admission record and its LAUNCH-RECEIPT (the lineage this 04 launch
        must share: same round, RC-6 declaration and qualifying preflight receipts)."""
        root = Path(G.RECEIVE["end"]) / "127x03" / attempt
        seal = H.write(root / "durable-measurement/receipt-manifest.json", b'{"synthetic": "seal"}\n')
        round_ = str(int(G.ATTEMPT["end"].fullmatch(attempt).group(2)))
        receipt = dict(schema=G.RECEIPT_SCHEMA, kind="end", host="127x03", attempt=attempt, launched=True,
                       roots_sha256=self.roots_sha, measurement_argv=["env", "x", "--round", round_],
                       prerequisites=dict(preflights={h: dict(attempt=a, sha256=s) for h, (a, s) in
                                                      sorted(self.pf_used.items())}))
        receipt.update(over.pop("receipt", {}))
        rpath = self.launch_dir(attempt, "127x03") / "LAUNCH-RECEIPT.json"
        if rpath.exists():
            os.chmod(rpath, 0o644)
        receipt_sha = H.sha(H.write(rpath, json.dumps(receipt)))
        ack = dict(schema=G.ACK_SCHEMA, host="127x03", attempt=attempt, classification="SEALED", status="complete",
                   ack_allowed=True, c_d_satisfied=True, exit_epoch=1000.0, verified_epoch=2300.0,
                   receipt_manifest_sha256=H.sha(seal), launch_receipt_sha256=receipt_sha)
        ack.update(over.pop("ack", {}))
        a = H.sha(H.write(root / "DURABLE-ACK.json", json.dumps(ack)))
        adm = dict(schema=G.ADMISSION_SCHEMA, host="127x03", attempt=attempt, kind="end", closed_before_admission=True,
                   verified_sha256=a, launch_receipt_sha256=receipt_sha)
        adm.update(over.pop("admission", {}))
        b = H.sha(H.write(self.launch_dir(attempt, "127x03") / "ADMISSION.json", json.dumps(adm)))
        return ["--prior-03", "%s:%s:%s" % (attempt, a, b)]

    def cli(self, kind, attempt, argv, extra=(), prepare=True):
        H.write(self.launch_dir(attempt) / "launch-argv.json", json.dumps(argv))
        cli = ["launch", "--host", self.host, "--kind", kind, "--attempt", attempt, "--argv-sha256",
               G.sha_bytes(G.argv_nul(argv)), "--roots-sha256", self.roots_sha]
        if prepare:
            cli += self.prepare(kind, attempt)
        return cli + list(extra)

    def launch(self, kind="end", argv=None, attempt=None, extra=(), prepare=True, rc9=True):
        if argv is None:
            argv, attempt = self.argv(kind)
        extra = list(extra)
        if kind == "end" and rc9:
            extra += self.verified("127x03") + self.verified("127x04")
            if self.host == "127x04":
                extra += self.prior_03()
        code = G.main(self.cli(kind, attempt, argv, extra, prepare), layers=(self.si, self.tool))
        receipt = self.launch_dir(attempt) / "LAUNCH-RECEIPT.json"
        doc = json.loads(receipt.read_text()) if receipt.exists() else None
        job = Path(self.decl["hosts"][self.host]["attempts" if kind == "end" else "preflight"]) / attempt
        if doc and doc.get("launched"):
            limit = time.time() + 15
            while not (job / "STUB-EXIT").exists() and time.time() < limit:
                time.sleep(.2)
        return code, doc, job


@pytest.fixture
def site(tmp_path, monkeypatch):
    return Site(tmp_path, monkeypatch)


def refused_on_host(code, doc, job, needle):
    ok(code == 3 and doc is not None, doc and doc.get("host_gate"))
    ok(doc["launched"] is False and not job.exists())
    ok(any(needle in f for f in doc["host_gate"]["failures"]), doc["host_gate"]["failures"])


# ---------------------------------------------------------------- end to end

def test_launch_happy_path(site):
    code, doc, job = site.launch()
    ok(code == 0 and doc["launched"] is True, doc and doc["host_gate"]["failures"])
    gate = doc["C5_preexec_gate"]
    ok(gate["preexec_gate_pass"] and gate["ps_nice"] == "0" and gate["SCHED_OTHER"] and gate["command_byte_equal"])
    ok(doc["postexec"]["python_visible"] and doc["postexec"]["postexec_priority_pass"])
    ok(doc["postexec"]["no_signals_sent"] is True and (job / "WRAPPER-RAN").is_file())
    ok((job / "STUB-EXIT").read_text().strip() == "0")
    ok(doc["utc"] == json.loads((job / "detach.json").read_text())["launched_at_utc"])
    ok(doc["schema"] == G.RECEIPT_SCHEMA and doc["measurement_argv"][0] == "env" and doc["roots_commit"] == "c" * 40)
    host = doc["host_gate"]
    ok(host["quiet_1"]["helper_changed"] is False and host["quiet_2"]["values"]["maint"] == 0)
    ok({t["unit"] for t in host["timers"]["timers"]} == {"apt-daily.timer", "motd-news.timer", "fstrim.timer"})
    fr = host["frozen_reader"]
    ok(fr["guard_job_fresh"] and fr["repository"]["replace_refs"] == 0 and fr["guard_repo"]["static_preflight"])
    ok(host["ps"]["rc"] == 0 and host["host"] == "127x03" and host["safe_input_sha256"] == G.SAFE_INPUT_SHA256)
    log = site.log.read_text()
    ok("TZ=UTC LC_ALL=C ARGS=list-timers --all --no-pager" in log)
    sessions = [l for l in log.splitlines() if l.startswith("SSH ") and " -O " not in l]
    ok(len(sessions) == 1 and "ControlMaster=no" in sessions[0] and "ControlPath=none" in sessions[0])
    ok(doc["session_open_utc"] <= doc["session_close_utc"] and doc["session_close_epoch"] >= doc["session_open_epoch"])
    ok(set(doc["prerequisites"]["preflights"]) == {"127x03", "127x04"})
    ok(H.nlink(site.launch_dir("end-127x03-r00-l00") / "LAUNCH-RECEIPT.json") == 1)


def test_launch_preflight_kind(tmp_path, monkeypatch):
    s = Site(tmp_path, monkeypatch)
    code, doc, job = s.launch("preflight")
    ok(code == 0 and doc["launched"] is True and doc["mode"] == "binding" and doc["qualifying_preflight"])
    pins = doc["host_gate"]["file_pins"]
    ok(pins[s.decl["hosts"]["127x03"]["tools"] + "/k4s_end_preflight.py"]["matches"] is True)


def test_base_symlink_never_launches_into_a_foreign_directory(site):
    """Sol S7-F1 probe: the declared base replaced by a static symlink to a foreign directory -> refused on the host;
    no job or wrapper marker is created under the foreign directory (r1 launched there)."""
    base = Path(site.decl["hosts"]["127x03"]["base"])
    moved = site.tmp / "foreign-dir"
    shutil.move(str(base), str(moved))
    os.symlink(moved, base)
    code, doc, _ = site.launch()
    ok(code == 3 and doc["launched"] is False, doc["host_gate"]["failures"])
    ok(not (moved / "attempts" / "end-127x03-r00-l00").exists())
    ok(any(f.startswith("pin:") or f.startswith("job:") for f in doc["host_gate"]["failures"]))


def test_failed_ps_with_valid_table_is_refused(site):
    """Sol S7-F2 probe: ps prints its full valid table, then exits 37 -> no census, no launch."""
    site.shims.set(FAKE_PS_RC=37)
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "ps:")
    ok(doc["host_gate"]["ps"]["rc"] is None and "37" in doc["host_gate"]["ps"]["refused"])


def test_failed_hostname_with_valid_stdout_is_refused(site):
    site.shims.set(FAKE_HOSTNAME_RC=37)
    code, doc, job = site.launch()
    ok(code == 3 and doc["host_gate"]["host"] is None and not job.exists())
    ok(any("hostname" in f for f in doc["host_gate"]["failures"]))


@pytest.mark.parametrize("setup,needle", [
    (lambda s: s.shims.set(FAKE_ACTIVE_apt_daily_service="active"), "apt-daily.service"),
    (lambda s: s.shims.set(FAKE_ACTIVE_apt_daily_upgrade_service="activating"), "apt-daily-upgrade"),
    (lambda s: (H.write(s.tmp / "who", "student tty2 2026-10-12 08:00\n"), s.shims.set(FAKE_WHO=s.tmp / "who")),
     "who"),
    (lambda s: s.shims.set(FAKE_WHO_RC=1), "who"),
    (lambda s: H.write(s.quiet_ps, HELPER_PS + "   4242 Mon Oct 12 15:00:00 2026 apt-get /usr/bin/apt-get update\n"),
     "maint"),
    (lambda s: H.write(s.timers, timers_text(("apt-daily.timer", 5 * 3600), ("anacron.timer", 1800))),
     "anacron.timer"),
    (lambda s: H.write(s.timers, timers_text(("apt-daily.timer", -10))), "apt-daily.timer"),
    (lambda s: H.write(s.timers, "NEXT LEFT\nsoon weird.timer\n"), "unparseable"),
    (lambda s: H.write(s.timers, "NEXT LEFT\n0 timers listed.\n"), "no timer"),
    (lambda s: s.shims.set(FAKE_TIMERS_RC=1), "timers:"),
    (lambda s: os.utime(os.path.join(*G.STAMPS["release_upgrade_available"]), (time.time() - 80000,) * 2),
     "release-upgrade"),
    (lambda s: os.utime(os.path.join(*G.STAMPS["updates_available"]), (time.time() - 300,) * 2), "updates-available"),
    (lambda s: os.rmdir(os.path.join(*G.STAMPS["apt_lists"])), "missing"),
    (lambda s: (H.write(s.tmp / "ps-extra", "  55555       1   0  TS sshd: someone [priv]\n"),
                s.shims.set(FAKE_PS_EXTRA=s.tmp / "ps-extra")), "other SSH sessions"),
    (lambda s: s.shims.set(FAKE_GATE_NI=5), "C5 pre-exec gate"),
    (lambda s: s.shims.set(FAKE_GATE_NI=5, FAKE_PARENT_NI=0), "C5 pre-exec gate"),
    (lambda s: s.shims.set(FAKE_GATE_NI=0, FAKE_PARENT_NI=5), "C5 pre-exec gate"),
    (lambda s: H.write(Path(s.decl["hosts"]["127x03"]["tools"]) / "k4s_end_exit_push.sh", STUB_WRAPPER + "#\n"),
     "pin"),
    (lambda s: os.link(Path(s.decl["hosts"]["127x03"]["tools"]) / "detach.sh", s.tmp / "alias"), "pin"),
    (lambda s: H.write(Path(s.decl["hosts"]["127x03"]["bundles"]["a00"]["guard_job"]) / "STOP", ""), "frozen-reader"),
    (lambda s: H.write(Path(s.decl["hosts"]["127x03"]["repository"]) / ".git/info/grafts", ""), "frozen-reader"),
    (lambda s: H.git(Path(s.decl["hosts"]["127x03"]["bundles"]["a00"]["guard_job"]) / "repo", "config",
                     "filter.x.smudge", "cat"), "frozen-reader"),
    (lambda s: s.mp.setattr(G, "SEED_COMMITS", ("0" * 40, G.SEED_COMMITS[1])), "frozen-reader"),
], ids=["apt-daily", "apt-upgrade-activating", "who", "who-rc", "maint", "timer-close", "timer-overdue",
        "timer-garbled", "timer-none", "timer-rc", "stamp-stale", "stamp-order", "stamp-missing", "sshd-session",
        "gate-nice", "own-nice", "parent-nice", "wrapper-pin", "tool-hard-link", "guard-not-fresh", "repo-grafts", "guard-filter", "seed-commit"])
def test_host_refusals(site, setup, needle):
    setup(site)
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, needle)


def test_wrong_host(site):
    site.shims.set(FAKE_HOST="127x04")
    code, doc, job = site.launch()
    ok(code == 3 and doc["host_gate"]["host"] is None and not job.exists())


def test_allowlisted_timer_launches(site):
    H.write(site.timers, timers_text(("apt-daily.timer", 5 * 3600), ("anacron.timer", 1800)))
    code, doc, _ = site.launch(extra=["--allow-timer", "anacron.timer=hourly; idle in K4S reporting (ref)"])
    ok(code == 0 and doc["launched"])
    ok([t for t in doc["host_gate"]["timers"]["timers"] if t["unit"] == "anacron.timer"][0]["allowlisted"])


def test_helper_change_is_noted_not_fatal(site):
    H.write(site.quiet_ps, HELPER_PS.replace("2368", "9999"))
    code, doc, _ = site.launch()
    ok(code == 0 and doc["host_gate"]["quiet_2"]["helper_changed"] is True)


def test_existing_job_refused(site):
    argv, attempt = site.argv()
    Path(site.decl["hosts"]["127x03"]["attempts"], attempt).mkdir()
    code, doc, _ = site.launch(argv=argv, attempt=attempt)
    ok(code == 3 and any(f.startswith("job:") for f in doc["host_gate"]["failures"]))


def test_registry_attempt_limits(site):
    reg = Path(site.decl["hosts"]["127x03"]["repository"]) / "reports/explore/k4s-confirm/end/registry/round-00/127x03"
    H.write(reg / "attempt-00.json", "{}")
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "coordinator ruling")
    argv, attempt = site.argv(attempt="end-127x03-r00-l01", bundle="a01")
    ruling = H.sha(H.write(site.launch_dir(attempt) / "REPEAT-RULING.json",
                           json.dumps(dict(schema="clasher.k4s.end-second-attempt-ruling.v1", host="127x03",
                                           attempt=attempt, coordinator_ref="COORDINATOR 2026-10-13 abc123"))))
    code, doc, _ = site.launch(argv=argv, attempt=attempt, extra=["--second-attempt-ruling-sha256", ruling])
    ok(code == 0 and doc["host_gate"]["registry"]["claims_this_round"] == 1, doc["host_gate"]["failures"])
    H.write(reg / "attempt-01.json", "{}")
    argv, attempt = site.argv(attempt="end-127x03-r00-l02", bundle="a00")
    code, doc, job = site.launch(argv=argv, attempt=attempt)
    refused_on_host(code, doc, job, "registry:")


def test_registry_hard_link_alias_refused_on_host(site):
    reg = Path(site.decl["hosts"]["127x03"]["repository"]) / "reports/explore/k4s-confirm/end/registry/round-00/127x03"
    reg.mkdir(parents=True)
    canary = H.canary(site.tmp / "canary")
    os.link(canary, reg / "attempt-00.json")
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "single-link")
    ok(H.canary_intact(canary))


def test_local_controlmaster_refused_before_any_session(site):
    site.shims.set(FAKE_MUX_RC=0)
    raises(G.GateRefusal, site.launch, match="ControlMaster")
    ok(all(" -O " in l for l in site.log.read_text().splitlines() if l.startswith("SSH ")))


# ---------------------------------------------------------------- RC-9 / P2-3 / C-d (local, before any session)

def rc9(site, extra, host="127x03"):
    site.host = host
    site.shims.set(FAKE_HOST=host)
    argv, attempt = site.argv()
    return lambda: G.main(site.cli("end", attempt, argv, extra), layers=(site.si, site.tool))


@pytest.mark.parametrize("over,needle", [
    (dict(schema=None), "not a verified"),
    (dict(scope="K4S-END-REFERENCE"), "not a verified"),
    (dict(passed=False), "did not pass"),
    (dict(failed_checks=["topology"]), "did not pass"),
    (dict(mode="diagnostic", qualifying=False), "BINDING"),
    (dict(load=dict(reference_slot_work=False, reference_slot_states_worked=0, background_slots_ready=10,
                    background_slots_expected=10, slot_count=11)), "full reference load"),
    (dict(load=dict(reference_slot_work=True, reference_slot_states_worked=9, background_slots_ready=9,
                    background_slots_expected=10, slot_count=11)), "full reference load"),
    (dict(duration=dict(loaded_seconds_measured=899.0)), "duration"),
    (dict(login_detected_during_hold=True), "login"),
    (dict(bus_percent=0.8), "STOP"),
    (dict(bus_band="unavailable", bus_gate="unavailable", bus_cumulative_loaded=dict(percent=None, seconds=None,
                                                                                     hz=100, cpu_ticks=None)),
     "missing or not finite"),
    (dict(bus_percent=0.5), "SHA-256 pin is required"),
    (dict(safe_input_sha256="0" * 64), "binding differs"),
    (dict(receipt_manifest_sha256="0" * 64), "sealed receipt differs"),
], ids=["no-schema", "scope", "not-passed", "failed-check", "diagnostic", "no-reference-work", "slots", "duration",
        "login", "bus-stop", "bus-unavailable", "bus-decision-missing", "layer", "provenance"])
def test_rc9_preflight_receipt_validation(site, over, needle):
    """Sol S5-F3/S7-F3 probes: schema-less Boolean documents, a background-only run, 0.8 % bus without a ruling and
    insufficient load/duration never satisfy RC-9 (r1 accepted them)."""
    extra = site.verified("127x03") + site.verified("127x04", **over)
    raises(G.GateRefusal, rc9(site, extra), match=needle)


def test_rc9_schema_less_boolean_document(site):
    root = Path(G.RECEIVE["preflight"]) / "127x04" / "preflight-127x04-l00"
    doc = H.write(root / "PREFLIGHT-VERIFIED.json", json.dumps(dict(host="127x04", passed=True,
                                                                    registry_and_attempt_parent_unchanged=True)))
    extra = site.verified("127x03") + ["--preflight-verified", "127x04=preflight-127x04-l00:" + H.sha(doc)]
    raises(G.GateRefusal, rc9(site, extra), match="not a verified")


def test_rc9_bus_decision_band(site):
    extra = site.verified("127x03") + site.verified("127x04", bus_percent=0.5)
    seal = H.sha(Path(G.RECEIVE["preflight"]) / "127x04/preflight-127x04-l00/preflight/receipt-manifest.json")
    rel = Path(G.LAUNCH_BASE) / "127x04" / "BUS-DECISION-preflight-127x04-l00.json"
    bad = H.sha(H.write(rel, json.dumps(dict(schema="clasher.k4s.end-bus-decision.v1", decision="stop",
                                             preflight_attempt="preflight-127x04-l00",
                                             receipt_manifest_sha256=seal, coordinator_ref="C"))))
    raises(G.GateRefusal, rc9(site, extra + ["--bus-decision-sha256", bad]), match="proceed")
    os.chmod(rel, 0o644)
    good = H.sha(H.write(rel, json.dumps(dict(schema="clasher.k4s.end-bus-decision.v1", decision="proceed",
                                              preflight_attempt="preflight-127x04-l00",
                                              receipt_manifest_sha256=seal, coordinator_ref="COORDINATOR x"))))
    code = rc9(site, extra + ["--bus-decision-sha256", good])()
    ok(code == 0)


def test_rc9_end_binding_to_this_argv(site):
    extra = site.verified("127x03", inputs=None) + site.verified("127x04")
    raises((G.GateRefusal, site.si.Refusal, TypeError, AttributeError, KeyError), rc9(site, extra))
    d = site.decl["hosts"]["127x03"]
    bad_inputs = dict(runtime_root=d["runtime"], repository=d["repository"], k4s_manifest_sha256=G.K4S_MANIFEST_SHA256,
                      bundle=d["bundles"]["pf00"]["path"], bundle_pins_sha256=d["bundles"]["pf00"]["tiers_pins_sha256"],
                      guard_job=d["bundles"]["pf00"]["guard_job"], compare_bundle=d["bundles"]["a00"]["path"],
                      compare_bundle_pins_sha256=d["bundles"]["a00"]["tiers_pins_sha256"],
                      end_evidence_sha256="0" * 64, sd1_manifest_sha256="5" * 64)
    extra = site.verified("127x03", inputs=dict(bad_inputs, _merge=True)) + site.verified("127x04")
    raises(G.GateRefusal, rc9(site, extra), match="evidence/SD1")


@pytest.mark.parametrize("over,needle", [
    (dict(ack=dict(status="failed")), "SEALED complete"),
    (dict(ack=dict(classification="UNSEALED")), "SEALED complete"),
    (dict(ack=dict(verified_epoch=2299.0)), "C-d"),
    (dict(ack=dict(c_d_satisfied=False)), "C-d"),
    (dict(ack=dict(receipt_manifest_sha256="0" * 64)), "differs from its ACK"),
    (dict(admission=dict(closed_before_admission=False)), "close before admission"),
    (dict(admission=dict(schema="x")), "close before admission"),
], ids=["failed", "unsealed", "early", "cd-false", "seal", "rc7", "rc7-schema"])
def test_rc9_04_needs_03_complete_cd_and_rc7(site, over, needle):
    extra = site.verified("127x03") + site.verified("127x04") + site.prior_03(**over)
    raises(G.GateRefusal, rc9(site, extra, host="127x04"), match=needle)


def test_rc9_04_without_prior_03(site):
    extra = site.verified("127x03") + site.verified("127x04")
    raises(G.GateRefusal, rc9(site, extra, host="127x04"), match="03's verified complete")


def test_04_end_launches_with_complete_prerequisites(tmp_path, monkeypatch):
    s = Site(tmp_path, monkeypatch, host="127x04")
    code, doc, _ = s.launch()
    ok(code == 0 and doc["launched"], doc and doc["host_gate"]["failures"])
    ok(doc["prerequisites"]["prior_03"]["verified_epoch"] >= doc["prerequisites"]["prior_03"]["exit_epoch"] + 1300)


# ---------------------------------------------------------------- r3 frozen-reader env on the host (END-FULL-F3)

@pytest.mark.parametrize("xdg,needle", [("xdg", "relative"), ("", "empty"), ("//x/y", "normalized")])
def test_host_program_refuses_relative_empty_or_odd_xdg(site, xdg, needle):
    """The launched wrapper inherits this environment: a relative/empty/non-normalized XDG_CONFIG_HOME refuses before
    any launch (frozen-exec re-checks the same at exec)."""
    site.shims.set(XDG_CONFIG_HOME=xdg)
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, needle)


def test_host_program_checks_the_global_config_files(site):
    H.write(site.tmp / "home" / ".gitconfig", "[include]\n\tpath = %s\n" % (site.tmp / "elsewhere"))
    code, doc, job = site.launch()
    refused_on_host(code, doc, job, "indirection")


def test_host_program_home_double_slash_checked_canonically(site):
    H.write(site.tmp / "home" / ".gitconfig", "[user]\n\tname = t\n")
    site.shims.set(HOME="/" + str(site.tmp / "home"))
    code, doc, _ = site.launch()
    ok(code == 0 and doc["launched"], doc and doc["host_gate"]["failures"])
    record = doc["host_gate"]["frozen_reader"]["global_git_config"]
    ok(record["global_config_checked"] == [str(site.tmp / "home") + "/.gitconfig"], record)


# ---------------------------------------------------------------- r3 RC-9 binding (Sol END-FULL-F5 probes)

def rebundle(site, h, name, **fields):
    """Rewrite a declared bundle's tiers-pins.json with extra top-level fields; update the RC-6 declaration."""
    d = site.decl["hosts"][h]
    b = d["bundles"][name]
    path = Path(b["path"]) / "tiers-pins.json"
    manifest = dict(json.loads(path.read_text()), **fields)
    os.chmod(path, 0o644)
    b["tiers_pins_sha256"] = H.sha(H.write(path, H.canonical(manifest) + "\n"))
    decl = Path(G.LAUNCH_BASE) / "ROOTS-DECLARATION.json"
    os.chmod(decl, 0o644)
    site.roots_sha = H.sha(H.write(decl, json.dumps(site.decl, sort_keys=True)))


def end_with(site, host="127x03", bundle=None, verified=None, prior=None, **argv_opts):
    site.host = host
    site.shims.set(FAKE_HOST=host)
    argv, attempt = site.argv(bundle=bundle, **argv_opts)
    extra = site.verified("127x03", **(verified or {}).get("127x03", {})) + \
        site.verified("127x04", **(verified or {}).get("127x04", {}))
    if host == "127x04":
        extra += site.prior_03(**(prior or {}))
    return site.launch("end", argv=argv, attempt=attempt, extra=extra, rc9=False)


@pytest.mark.parametrize("option,needle", [("--native", "native/corpus/corpus-inventory differ"),
                                           ("--corpus", "native/corpus/corpus-inventory differ")])
def test_f5_probe_changed_native_or_corpus_path_refused(site, option, needle):
    """Sol probe: the qualifying preflight used inputs/native.so and inputs/k4-states.pkl; an END argv naming another
    K4S-owned native/corpus file under the base is refused before any SSH session."""
    d = site.decl["hosts"]["127x03"]
    other = H.write(Path(d["base"]) / "inputs" / ("other-" + option[2:] + ".bin"), b"o")
    raises(G.GateRefusal, end_with, site, **{option: str(other)}, match=needle)
    ok(not [l for l in site.log.read_text().splitlines() if l.startswith("SSH ") and " -O " not in l]
       if site.log.exists() else True)


@pytest.mark.parametrize("over,needle", [
    (dict(identity=dict(native_sha256="0" * 64, _merge=True)), "identity is missing"),
    (dict(identity=dict(corpus_sha256="0" * 64, _merge=True)), "identity is missing"),
    (dict(identity=dict(corpus_inventory_sha256="0" * 64, _merge=True)), "identity is missing"),
    (dict(inputs=dict(corpus_inventory_sha256="0" * 64, _merge=True)), "identity is missing"),
    (dict(identity=None), "identity is missing"),
    (dict(identity=dict(native="/elsewhere/native.so", _merge=True)), "identity paths"),
    (dict(inputs=dict(corpus_inventory="/x/corpora.json", _merge=True)), "identity paths"),
], ids=["native-sha", "corpus-sha", "inventory-sha", "inputs-inventory-sha", "no-identity", "native-path",
        "inventory-path"])
def test_f5_preflight_identity_binding(site, over, needle):
    raises(G.GateRefusal, end_with, site, verified={"127x03": over}, match=needle)


def test_f5_probe_other_host_preflight_identity_also_bound(site):
    raises(G.GateRefusal, end_with, site, verified={"127x04": dict(identity=dict(native_sha256="0" * 64,
                                                                                  _merge=True))},
           match="identity is missing")


def test_f5_exact_bundle_binding_recorded(site):
    code, doc, _ = end_with(site)
    ok(code == 0 and doc["launched"], doc and doc["host_gate"]["failures"])
    binding = doc["prerequisites"]["preflights"]["127x03"]["bundle_binding"]
    ok(binding["mode"] == "exact" and binding["bundle_sans_guard_sha256"] == site.sans["127x03"], binding)
    ok(doc["host_gate"]["frozen_reader"]["bundle_sans_guard_sha256"] == site.sans["127x03"])
    ok(doc["prerequisites"]["preflights"]["127x04"]["bundle_binding"] is None)


def test_f5_probe_attempt_bundle_a01_vs_preflight_a00(site):
    """Sol probe: the preflight qualified compare bundle a00; the END launch uses a01 (fresh guard job). r3 accepts it
    only as a host-VERIFIED guard-job-only equivalence: identical a01 launches (mode guard-job-equivalent) ..."""
    code, doc, _ = end_with(site, bundle="a01", attempt="end-127x03-r00-l01")
    ok(code == 0 and doc["launched"], doc and doc["host_gate"]["failures"])
    binding = doc["prerequisites"]["preflights"]["127x03"]["bundle_binding"]
    ok(binding["mode"] == "guard-job-equivalent" and binding["bundle"].endswith("/a01"), binding)


def test_f5_probe_a01_differing_beyond_guard_job_refused_on_host(site):
    """... and an a01 whose pinned manifest differs from the preflight's bundles beyond guard.job is refused by the
    host program from its bytes (nothing launched)."""
    rebundle(site, "127x03", "a01", runtime_files={"extra.py": "0" * 64})
    code, doc, job = end_with(site, bundle="a01", attempt="end-127x03-r00-l01")
    refused_on_host(code, doc, job, "beyond guard.job")


def test_f5_preflight_bundle_identity_required(site):
    for ids in (None, dict(bundle_sans_guard_sha256="1" * 64, compare_bundle_sans_guard_sha256="2" * 64),
                dict(bundle_sans_guard_sha256="x", compare_bundle_sans_guard_sha256="x")):
        raises(G.GateRefusal, end_with, site, verified={"127x03": dict(bundle_identity=ids)}, match="bundle identity")


def test_f5_preflight_digest_must_match_the_host_bundle(site):
    """A preflight receipt whose (self-consistent) digest is not the attempt bundle's: refused on the host."""
    code, doc, job = end_with(site, verified={"127x03": dict(bundle_identity=dict(
        bundle_sans_guard_sha256="1" * 64, compare_bundle_sans_guard_sha256="1" * 64))})
    refused_on_host(code, doc, job, "beyond guard.job")


@pytest.mark.parametrize("prior,needle", [
    (dict(attempt="end-127x03-r01-l00"), "not of round 00"),
    (dict(receipt=dict(measurement_argv=["env", "--round", "1"])), "of this round"),
    (dict(receipt=dict(launched=False)), "of this round"),
    (dict(receipt=dict(host="127x04")), "of this round"),
    (dict(receipt=dict(roots_sha256="0" * 64)), "different RC-6"),
    (dict(receipt=dict(prerequisites=dict(preflights={}))), "different qualifying preflights"),
    (dict(admission=dict(verified_sha256="0" * 64)), "not made from this ACK"),
    (dict(admission=dict(launch_receipt_sha256="0" * 64)), "not made from this ACK"),
    (dict(admission=dict(kind="preflight")), "not made from this ACK"),
    (dict(ack=dict(launch_receipt_sha256=None)), "not made from this ACK"),
], ids=["other-round-ack", "receipt-round", "not-launched", "receipt-host", "roots", "preflights", "adm-ack",
        "adm-receipt", "adm-kind", "ack-no-receipt"])
def test_f5_probe_03_completion_must_be_this_round_and_lineage(site, prior, needle):
    """Sol probe: a 03 ACK naming round 01 for a round-00 04 launch (and every lineage break) is refused."""
    raises((G.GateRefusal, site.si.Refusal), end_with, site, host="127x04", prior=prior, match=needle)


def test_f5_03_receipt_bound_by_ack_sha(site):
    site.host = "127x04"
    extra = site.verified("127x03") + site.verified("127x04") + site.prior_03()
    receipt = site.launch_dir("end-127x03-r00-l00", "127x03") / "LAUNCH-RECEIPT.json"
    os.chmod(receipt, 0o644)
    with open(receipt, "a") as stream:
        stream.write(" ")
    raises(site.si.Refusal, rc9(site, extra, host="127x04"), match="sha")


@pytest.mark.parametrize("h,over,needle", [
    ("127x04", dict(bus_percent=0.8, bus_band="proceed", bus_gate="proceed"), "not the P2-3 band"),
    ("127x04", dict(bus_percent=0.5, bus_band="proceed", bus_gate="proceed"), "not the P2-3 band"),
    ("127x04", dict(bus_percent=0.2, bus_band="stop", bus_gate="stop"), "not the P2-3 band"),
    ("127x03", dict(bus_percent=0.8, bus_band="proceed"), "not the P2-3 band"),
    ("127x04", dict(bus_cumulative_loaded=None), "evidence missing"),
    ("127x04", dict(bus_cumulative_loaded=dict(percent=0.05, seconds=958.0, cpu_ticks=47.9)), "not finite"),
    ("127x04", dict(bus_cumulative_loaded=dict(percent=True, seconds=958.0, hz=100, cpu_ticks=47.9)), "not finite"),
    ("127x04", dict(bus_cumulative_loaded=dict(percent=-0.1, seconds=958.0, hz=100, cpu_ticks=-95.8)), "not finite"),
    ("127x04", dict(bus_cumulative_loaded=dict(percent=0.05, seconds=958.0, hz=100, cpu_ticks=900.0)),
     "inconsistent"),
    ("127x04", dict(bus_cumulative_loaded=dict(percent=0.05, seconds=900.0, hz=100, cpu_ticks=45.0)),
     "inconsistent"),
    ("127x03", dict(bus_gate="proceed"), "gate/band mismatch"),
    ("127x04", dict(bus_gate="not-gated-on-127x04"), "gate/band mismatch"),
], ids=["04-0.8-proceed", "04-0.5-proceed", "04-0.2-stop", "03-0.8-proceed", "missing", "no-hz", "bool", "negative",
        "ticks", "span", "03-gate", "04-gate"])
def test_f5_probe_inconsistent_bus_evidence_refused(site, h, over, needle):
    """Sol probe: numeric loaded bus 0.8 % recorded with band/gate "proceed" (and every other inconsistency)."""
    raises(G.GateRefusal, end_with, site, verified={h: over}, match=needle)


def test_f5_nonfinite_bus_refused(site):
    raises((G.GateRefusal, site.si.Refusal), end_with, site,
           verified={"127x04": dict(bus_cumulative_loaded=dict(percent=float("nan"), seconds=958.0, hz=100,
                                                               cpu_ticks=1.0))})


def test_f5_bus_constants_equal_the_preflight_and_band_boundaries():
    import k4s_end_preflight as S
    ok((G.BUS_PROCEED_MAX, G.BUS_STOP_MIN) == (S.BUS_PROCEED_MAX, S.BUS_STOP_MIN) == (0.3, 0.7))
    for pct in (0.0, 0.29, 0.3, 0.31, 0.5, 0.69, 0.7, 0.8, 5.0):
        ok(G.bus_band(pct) == S.band(pct), pct)
    ok((G.NATIVE_SHA256, G.CORPUS_SHA256, G.CORPUS_INVENTORY_SHA256) ==
       (S.NATIVE_SHA256, S.CORPUS_SHA256, S.CORPUS_INVENTORY_SHA256))
    ok(G.VERIFIED_SCHEMA == S.VERIFIED_SCHEMA)


# ---------------------------------------------------------------- local refusals and RC-6

def test_local_refusals(site):
    argv, attempt = site.argv()
    base = site.cli("end", attempt, argv, prepare=False)
    run = lambda extra: G.main(base + extra, layers=(site.si, site.tool))
    i = base.index("--argv-sha256") + 1
    raises(G.GateRefusal, G.main, base[:i] + ["0" * 64] + base[i + 1:], layers=(site.si, site.tool), match="pin")
    raises(site.si.Refusal, G.main, base[:-1] + ["0" * 64], layers=(site.si, site.tool), match="sha")   # RC-6 SHA
    raises(site.si.Refusal, run, [])                         # receive dir not prepared
    proof = site.prepare("end", attempt)
    raises(site.si.Refusal, run, ["--prepare-proof-sha256", "0" * 64])
    raises(G.GateRefusal, run, proof, match="Both host preflights")
    H.write(Path(G.RECEIVE["end"]) / "127x03" / attempt / "extra", "")
    pf = site.verified("127x03") + site.verified("127x04")
    raises(G.GateRefusal, run, proof + pf, match="only PREPARED")
    os.unlink(Path(G.RECEIVE["end"]) / "127x03" / attempt / "extra")
    raises(G.GateRefusal, run, proof + pf + ["--clearance-seconds", "7199"], match="Clearance")
    raises(G.GateRefusal, run, proof + pf + ["--allow-timer", "anacron.timer="], match="allow-timer")
    H.write(site.launch_dir(attempt) / "LAUNCH-RECEIPT.json", "")
    raises(site.si.Refusal, run, proof + pf, match="exists")


def test_tampered_quiet_read_or_host_program_refused(site, monkeypatch):
    monkeypatch.setattr(G, "QUIET_V3_SHA256", "0" * 64)
    raises(site.si.Refusal, site.launch, match="sha")
    monkeypatch.undo()
    s = Site(site.tmp / "two", monkeypatch)
    monkeypatch.setattr(G, "REMOTE_SHA256", "0" * 64)
    raises(s.si.Refusal, s.launch)


def roots_variant(site, mutate):
    decl = json.loads(json.dumps(site.decl))
    mutate(decl)
    return decl


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema="x"),
    lambda d: d["hosts"].pop("127x04"),
    lambda d: d["hosts"]["127x03"].update(base="/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1"),
    lambda d: d["hosts"]["127x03"].update(runtime=d["hosts"]["127x03"]["base"] + "/runtime"),
    lambda d: d["hosts"]["127x03"].update(guard_parent=d["hosts"]["127x03"]["base"]),
    lambda d: d["hosts"]["127x03"].update(extra="x"),
    lambda d: d["hosts"]["127x03"]["bundles"]["a00"].update(path="/elsewhere/a00"),
    lambda d: d["hosts"]["127x03"]["bundles"]["a00"].update(guard_job=d["hosts"]["127x03"]["guard_parent"] + "/x"),
    lambda d: d["hosts"]["127x03"]["bundles"]["a01"].update(guard_job=d["hosts"]["127x03"]["bundles"]["a00"]["guard_job"]),
], ids=["schema", "one-host", "base", "runtime", "guard-parent", "extra-key", "bundle-path", "guard-name", "shared-guard"])
def test_rc6_declaration_validation(site, mutate):
    raises(G.GateRefusal, G.validate_roots, site.si, roots_variant(site, mutate))
    ok(G.validate_roots(site.si, site.decl))


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
    (lambda a, d: ["nice", "-n", "19"] + a, "frozen inner nice"),
    (lambda a, d: a[3:], "frozen inner nice"),
    (lambda a, d: a[:5] + ["60"] + a[6:], "frozen inner nice"),
    (lambda a, d: a[:6] + ["sh"] + a[7:], "argv must be"),
    (lambda a, d: a[:12] + [d["attempts"] + "/end-127x04-r00-l00"] + a[13:], "argv must be"),
    (lambda a, d: a[:8] + ["/tmp/detach.log"] + a[9:], "argv must be"),
    (lambda a, d: a[:7] + ["/elsewhere/detach.sh"] + a[8:], "argv must be"),
    (lambda a, d: a[:11] + [d["base"] + "/K4S-exit-push.sh"] + a[12:], "argv must be"),
    (lambda a, d: a[:13] + ["nice", "-n", "10"] + a[13:], "start with env"),
    (lambda a, d: mutate(a, insert=(17, ["nice", "-n", "10"])), "priority/scheduler"),
    (lambda a, d: mutate(a, insert=(17, ["EXTRA=1"])), "Environment"),
    (lambda a, d: [x for x in a if x != "MKL_NUM_THREADS=1"], "Environment"),
    (lambda a, d: [x if x != "-B" else "-O" for x in a], "optimizer"),
    (lambda a, d: a + ["--kernel", "k"], "Unknown"),
    (lambda a, d: mutate(a, drop="--end-job-sha256"), "exactly the required"),
    (lambda a, d: a + ["--round", "0"], "Repeated option"),
    (lambda a, d: mutate(a, drop="--out") + ["--ou", "x"], "Unknown"),
    (lambda a, d: mutate(a, drop="--out") + ["--out=x"], "Unexpected"),
    (lambda a, d: mutate(a, index_of="--out", value="/tmp/x"), "--out must"),
    (lambda a, d: mutate(a, index_of="--repository", value=d["base"] + "/runtime"), "--repository must"),
    (lambda a, d: mutate(a, index_of="--round", value="1"), "attempt name"),
    (lambda a, d: mutate(a, index_of="--runtime-root", value="/elsewhere"), "declared runtime"),
    (lambda a, d: mutate(a, index_of="--bundle", value=d["base"] + "/bundles/undeclared"), "RC-6 bundle"),
    (lambda a, d: mutate(a, index_of="--bundle", value=d["bundles"]["pf00"]["path"]), "rdRR-aNN"),
    (lambda a, d: mutate(a, index_of="--bundle", value=d["bundles"]["r1a00"]["path"]), "rdRR-aNN"),
    (lambda a, d: mutate(a, index_of="--k4s-manifest-sha256", value="1" * 64), "74314eda"),
    (lambda a, d: mutate(a, index_of="--corpus-inventory", value=d["base"] + "/inputs/corpora.json"), "corpus-inventory"),
    (lambda a, d: mutate(a, index_of="--native", value=d["attempts"] + "/native.so"), "--native"),
    (lambda a, d: mutate(a, index_of="--end-evidence", value="/tmp/end-evidence.json"), "end-evidence"),
], ids=["outer-nice", "no-nice", "cpu", "sh", "job-host", "log", "detach", "wrapper", "inner-nice", "nice-after-env",
        "env-extra", "env-missing", "opt-O", "kernel", "no-endjob", "repeat", "abbrev", "eq-form", "out",
        "repository", "round-name", "runtime", "bundle-undeclared", "bundle-preflight", "bundle-other-round",
        "manifest", "corpus-inventory", "native", "evidence"])
def test_end_argv_refusals(site, change, needle):
    argv, attempt = site.argv()
    roots = site.decl["hosts"]
    ok(G.validate_argv(site.si, argv, "end", "127x03", attempt, roots)["attempt"] == attempt)
    raises(G.GateRefusal, G.validate_argv, site.si, change(argv, roots["127x03"]), "end", "127x03", attempt, roots,
           match=needle)


def test_preflight_argv(site):
    roots = site.decl["hosts"]
    argv, attempt = site.argv("preflight")
    shape = G.validate_argv(site.si, argv, "preflight", "127x03", attempt, roots)
    ok(shape["mode"] == "binding" and roots["127x03"]["tools"] + "/k4s_end_preflight.py" in shape["file_pins"])
    bad = [
        ([x for x in argv if x != "run"], "run"),
        (mutate(argv, index_of="--attempt-parent", value=roots["127x03"]["preflight"]), "attempt-parent"),
        (argv + ["--no-reference-work"], "NON-QUALIFYING"),
        (mutate(argv, index_of="--hold-seconds", value="119"), "minimum"),
        (mutate(argv, index_of="--bundle-pins-sha256", value="0" * 64), "RC-6"),
        (mutate(mutate(argv, index_of="--bundle", value=roots["127x03"]["bundles"]["a01"]["path"]),
                index_of="--bundle-pins-sha256", value=roots["127x03"]["bundles"]["a01"]["tiers_pins_sha256"]),
         "-pfNN"),
        (mutate(argv, drop="--compare-bundle"), "lacks"),
        (mutate(argv, index_of="--min-samples", value="5") if "--min-samples" in argv else argv + ["--min-samples", "5"],
         "min-samples"),
    ]
    for candidate, needle in bad:
        raises(G.GateRefusal, G.validate_argv, site.si, candidate, "preflight", "127x03", attempt, roots, match=needle)
    shape = G.validate_argv(site.si, argv + ["--no-reference-work"], "preflight", "127x03", attempt, roots,
                            diagnostic=True)
    ok(shape["mode"] == "diagnostic")
    argv4, attempt4 = site.argv("preflight", host="127x04", **{"--hold-seconds": "899"})
    raises(G.GateRefusal, G.validate_argv, site.si, argv4, "preflight", "127x04", attempt4, roots, match="minimum")


def test_preflight_receive_dir_must_be_empty(site):
    argv, attempt = site.argv("preflight")
    root = Path(G.RECEIVE["preflight"]) / "127x03" / attempt
    H.write(root / "stale.json", b"{}")
    raises(G.GateRefusal, site.launch, "preflight", argv=argv, attempt=attempt, match="must be empty")


def test_diagnostic_preflight_launch_is_recorded_non_qualifying(site):
    argv, attempt = site.argv("preflight", **{"--no-reference-work": True})
    raises(G.GateRefusal, site.launch, "preflight", argv=argv, attempt=attempt, match="NON-QUALIFYING")
    shutil.rmtree(Path(G.RECEIVE["preflight"]) / "127x03" / attempt)
    code, doc, _ = site.launch("preflight", argv=argv, attempt=attempt, extra=["--diagnostic-preflight"])
    ok(code == 0 and doc["mode"] == "diagnostic" and doc["qualifying_preflight"] is False)


# ---------------------------------------------------------------- host-side parsers (pure)

def test_parse_quiet_r4_sample_and_failures():
    good = R.parse_quiet(R4_QUIET, 0, 2368)
    ok(good["failures"] == [] and good["helper_changed"] is False and good["helper_pids"] == [2368])
    ok(R.parse_quiet(R4_QUIET, 1, 2368)["failures"] == ["quiet: rc=1"])
    ok(R.parse_quiet(R4_QUIET.replace("maint=0", "maint=1"), 0, 2368)["failures"] == ["quiet: maint=1"])
    ok(R.parse_quiet(R4_QUIET.replace("=inactive", "=active", 1), 0, 2368)["failures"])
    ok(R.parse_quiet("", 0, 2368)["failures"])


def test_parse_timers_epoch_and_allowlist():
    now = time.time()
    timers, failures = R.parse_timers(timers_text(("a.timer", 9000), ("b.timer", 100), ("c.timer", None)), now,
                                      7200, {"b.timer": "x"})
    ok(failures == [] and [t["clear"] for t in timers] == [True, False, True] and timers[1]["allowlisted"] == "x")
    ok(R.parse_timers(timers_text(("b.timer", 100)), now, 7200, {})[1])


def test_other_ssh_sessions_excludes_own_ancestry():
    table = {1: dict(pid=1, ppid=0, args="/sbin/init"), 10: dict(pid=10, ppid=1, args="sshd: /usr/sbin/sshd [listener]"),
             20: dict(pid=20, ppid=10, args="sshd: u [priv]"), 21: dict(pid=21, ppid=20, args="sshd: u@notty"),
             22: dict(pid=22, ppid=21, args="python3"), 30: dict(pid=30, ppid=10, args="sshd: v [priv]")}
    ok(R.other_ssh_sessions(table, 22) == [30])


# ---------------------------------------------------------------- RC-7 admission record

def test_admission_record(site):
    code, doc, job = site.launch()
    ok(code == 0)
    root = Path(G.RECEIVE["end"]) / "127x03" / "end-127x03-r00-l00"
    admission = H.write(root / "durable-measurement/guard-admission.json",
                        json.dumps(dict(utc=doc["session_close_epoch"] + 30)))
    seal = H.write(root / "durable-measurement/receipt-manifest.json",
                   json.dumps(dict(files={"guard-admission.json": H.sha(admission)})))
    ack = H.write(root / "DURABLE-ACK.json", json.dumps(dict(ack_allowed=True, receipt_manifest_sha256=H.sha(seal))))
    receipt = site.launch_dir("end-127x03-r00-l00") / "LAUNCH-RECEIPT.json"
    args = ["admission", "--host", "127x03", "--kind", "end", "--attempt", "end-127x03-r00-l00",
            "--launch-receipt-sha256", H.sha(receipt), "--verified-sha256", H.sha(ack)]
    ok(G.main(args, layers=(site.si, site.tool)) == 0)
    out = json.loads((site.launch_dir("end-127x03-r00-l00") / "ADMISSION.json").read_text())
    ok(out["closed_before_admission"] is True and out["schema"] == G.ADMISSION_SCHEMA)
    raises(site.si.Refusal, G.main, args, layers=(site.si, site.tool))          # exclusive


def test_gate_refuses_optimized():
    import subprocess
    done = subprocess.run([sys.executable, "-O", str(ROOT / "k4s_end_launch_gate.py"), "launch", "--host", "127x03",
                           "--kind", "end", "--attempt", "end-127x03-r00-l00", "--argv-sha256", "0" * 64,
                           "--roots-sha256", "0" * 64], capture_output=True, text=True)
    ok(done.returncode != 0 and "-O" in done.stderr)
