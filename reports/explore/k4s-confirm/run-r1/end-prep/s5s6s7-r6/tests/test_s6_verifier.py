"""S6 verifier r2 (k4s_end_verify_push.py) on REAL r2 wrapper output (test_s6_wrapper.Harness), all synthetic.
Covers C-d, D3 hash-only members, the registry through the exact END-claim grant, the names-only sealed listing and
Sol's probes (hard-linked registry alias, games/ member). The verifier refuses -O at import (T1 R3-1), so under -O
only that refusal is tested."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import helpers as H
from helpers import ROOT, ok, raises
from test_s6_wrapper import Harness

pytestmark = []
if __debug__:
    import k4s_end_verify_push as V
else:
    V = None
needs_debug = pytest.mark.skipif(not __debug__, reason="verifier refuses -O at import")


def test_verifier_refuses_optimized_import():
    done = subprocess.run([sys.executable, "-O", "-c", "import sys; sys.path.insert(0, %r); import k4s_end_verify_push"
                           % str(ROOT)], capture_output=True, text=True)
    ok(done.returncode != 0 and "refuses optimized" in done.stderr + done.stdout)


class Setup:
    def __init__(self, tmp, monkeypatch, mode="complete", host="127x03", **env):
        self.si = V.load_si(str(ROOT))
        recv = tmp / "recv"
        for obj, name, value in ((V, "BASE", str(recv)), (V, "RECEIVE_BASE", str(recv / "end-received")),
                                 (V, "LAUNCH_BASE", str(tmp / "end-launch")),
                                 (self.si, "D3_RECEIVE_BASE", str(recv / "end-received"))):
            monkeypatch.setattr(obj, name, value)
        self.h = Harness(tmp, "k4s_end_exit_push.sh", host=host)
        self.job = self.h.job()
        self.root = str(recv / "end-received" / host / self.job.name)
        recv.mkdir(exist_ok=True)
        (tmp / "end-launch").mkdir(exist_ok=True)              # r4 (U7): prepare also writes the PREPARE-PROOF copy
        V.prepare(self.si, self.root)
        proof = json.loads(Path(self.root, "PREPARED.json").read_text())
        proof["utc"] = "2026-10-12T00:00:00Z"                       # synthetic: well before the launch
        os.chmod(Path(self.root, "PREPARED.json"), 0o644)
        Path(self.root, "PREPARED.json").write_text(json.dumps(proof, sort_keys=True) + "\n")
        self.argv = self.h.end_argv(self.job)
        self.result = self.h.run(self.job, self.argv, mode=mode, **env)
        exit_ = json.loads(Path(self.root, "exit.json").read_text())
        self.exit_epoch = V.utc_epoch(exit_["utc"])
        self.launch = dict(schema="clasher.k4s.end-launch-receipt.v2", kind="end", host=host, job=str(self.job),
                           attempt=self.job.name, launched=True, utc=exit_["utc"], wrapper_sha256=V.WRAPPER_SHA256,
                           measurement_argv=self.argv)
        self.launch_dir = Path(tmp / "end-launch" / host / self.job.name)
        self.proof = proof

    def write_launch(self):
        receipt = H.write(self.launch_dir / "LAUNCH-RECEIPT.json", json.dumps(self.launch, sort_keys=True))
        os.chmod(self.launch_dir / "PREPARE-PROOF.json", 0o644)   # test-only: the synthetic utc rewrite above
        proof = H.write(self.launch_dir / "PREPARE-PROOF.json", json.dumps(self.proof, sort_keys=True))
        return H.sha(receipt), H.sha(proof)

    def verify(self, now=None):
        return V.verify(self.si, self.root, self.launch, self.proof,
                        now=self.exit_epoch + 1300 if now is None else now)


@pytest.fixture
def ops(monkeypatch):
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 19)
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: {63})


@needs_debug
def test_sealed_complete_ack_through_main(tmp_path, monkeypatch, ops):
    s = Setup(tmp_path, monkeypatch)
    ok(s.result.returncode == 0, s.result.stderr)
    receipt_sha, proof_sha = s.write_launch()
    rc = V.main(["--receive", s.root, "--launch-receipt-sha256", receipt_sha, "--prepare-proof-sha256", proof_sha],
                si=s.si, now=s.exit_epoch + 1300)
    ack = json.loads(Path(s.root, "DURABLE-ACK.json").read_text())
    ok(rc == 0 and ack["classification"] == "SEALED" and ack["status"] == "complete" and ack["ack_allowed"])
    ok(ack["c_d_satisfied"] and ack["verified_epoch"] >= ack["exit_epoch"] + 1300 and ack["schema"] == V.ACK_SCHEMA)
    ok(ack["d3_hash_only"] == ["end-complete.json", "end-raw.json"] and ack["claim_bound"] is True)
    ok(ack["launch_receipt_sha256"] == receipt_sha and ack["prepare_proof_sha256"] == proof_sha)
    ok([c["name"] for c in ack["registry_claims"]] == ["attempt-00.json"] and "claim" not in ack["registry_claims"][0])
    raises(s.si.Refusal, V.main, ["--receive", s.root, "--launch-receipt-sha256", receipt_sha,
                                  "--prepare-proof-sha256", proof_sha], si=s.si, now=s.exit_epoch + 1300)


@needs_debug
def test_c_d_enforced(tmp_path, monkeypatch):
    """Sol S6-F3: no ACK before exit + 1300 s."""
    s = Setup(tmp_path, monkeypatch)
    raises(ValueError, s.verify, s.exit_epoch + 1299, match="C-d")
    ok(s.verify()["ack_allowed"])


@needs_debug
@pytest.mark.parametrize("mode,classification,claimed", [("failed", "SEALED", True), ("preclaim", "UNSEALED", False),
                                                         ("claim-only", "UNSEALED", True)])
def test_failed_preclaim_claim_only(tmp_path, monkeypatch, mode, classification, claimed):
    s = Setup(tmp_path, monkeypatch, mode=mode)
    got = s.verify()
    ok(got["classification"] == classification)
    if classification == "UNSEALED":
        ok(got["ack_allowed"] is False and got["claim_without_receipt"] is claimed)
    else:
        ok(got["status"] == "failed" and got["ack_allowed"] is True)


@needs_debug
def test_registry_hard_link_alias_refused(tmp_path, monkeypatch):
    """Sol S6-F1 probe on 05: the pushed claim replaced by an identical hard-linked file is refused (nlink) before
    it is parsed; r1 returned ack_allowed:true."""
    s = Setup(tmp_path, monkeypatch)
    claim = Path(s.root, "registry", "attempt-00.json")
    twin = tmp_path / "identical-canary"
    twin.write_bytes(claim.read_bytes())
    os.unlink(claim)
    os.link(twin, claim)
    error = raises(s.si.Refusal, s.verify)
    ok(error.code == "nlink", error)


@needs_debug
def test_outcome_named_sealed_member_refused(tmp_path, monkeypatch):
    """Sol S6-F1 probe: a synthetic games/reviewer.json in an otherwise valid seal is refused by name before any
    byte is hashed (r1 hashed and ACKed it)."""
    s = Setup(tmp_path, monkeypatch, FAKE_EXTRA="games/reviewer.json")
    ok(s.result.returncode == 0)
    error = raises(s.si.Refusal, s.verify)
    ok(error.code == "name", error)


@needs_debug
@pytest.mark.parametrize("mutation", ["extra-file", "d3-hard-link", "d3-sha", "member-sha", "member-symlink", "seal-sha",
                                      "wrapper-sha", "argv", "push-failed", "listing-sha", "registry-extra",
                                      "registry-name", "prepared", "scope"])
def test_refusals(tmp_path, monkeypatch, mutation):
    s = Setup(tmp_path, monkeypatch)
    data = Path(s.root, "durable-measurement")
    if mutation == "extra-file":
        H.write(data / "unsealed.json", b"{}")
    elif mutation == "d3-hard-link":
        os.link(data / "end-raw.json", tmp_path / "raw-alias")
    elif mutation == "d3-sha":
        os.chmod(data / "end-raw.json", 0o644)
        (data / "end-raw.json").write_text('{"tampered": 1}\n')
    elif mutation == "member-sha":
        os.chmod(data / "guard-admission.json", 0o644)
        (data / "guard-admission.json").write_text('{"tampered": 1}\n')
    elif mutation == "member-symlink":
        os.unlink(data / "guard-admission.json")
        os.symlink(tmp_path / "x", data / "guard-admission.json")
    elif mutation == "seal-sha":
        os.chmod(data / "receipt-manifest.sha256", 0o644)
        (data / "receipt-manifest.sha256").write_text("0" * 64 + "  receipt-manifest.json\n")
    elif mutation == "wrapper-sha":
        s.launch["wrapper_sha256"] = "0" * 64
    elif mutation == "argv":
        s.launch["measurement_argv"] = s.argv + ["--extra"]
    elif mutation == "push-failed":
        H.write(Path(s.root, "PUSH-FAILED.json"), b'{"rsync_exit_code": 23}')
    elif mutation == "listing-sha":
        claim = Path(s.root, "registry", "attempt-00.json")
        os.chmod(claim, 0o644)
        claim.write_text(claim.read_text().replace('"round":0', '"round":0 '))
    elif mutation == "registry-extra":
        H.write(Path(s.root, "registry", "attempt-01.json"), b"{}")
    elif mutation == "registry-name":
        H.write(Path(s.root, "registry", "notes.txt"), b"x")
    elif mutation == "prepared":
        s.proof = dict(s.proof, nonce="f" * 32)
    elif mutation == "scope":
        s.launch["kind"] = "preflight"
    raises((ValueError, s.si.Refusal), s.verify)


@needs_debug
def test_prepare_is_exclusive_and_refuses_aliased_base(tmp_path, monkeypatch):
    si = V.load_si(str(ROOT))
    base = tmp_path / "recv"
    monkeypatch.setattr(V, "BASE", str(base))
    monkeypatch.setattr(V, "RECEIVE_BASE", str(base / "end-received"))
    monkeypatch.setattr(V, "LAUNCH_BASE", str(tmp_path / "end-launch"))
    base.mkdir()
    (tmp_path / "end-launch").mkdir()
    root = str(base / "end-received" / "127x03" / "end-127x03-r00-l00")
    proof = V.prepare(si, root)
    ok(proof["created_empty"] and sorted(os.listdir(root)) == ["PREPARED.json"])
    ok(os.stat(root).st_mode & 0o777 == 0o700)
    raises(si.Refusal, V.prepare, si, root)
    raises(ValueError, V.prepare, si, str(base / "end-received" / "127x03" / "end-127x04-r00-l00"))
    elsewhere = tmp_path / "foreign"
    elsewhere.mkdir()
    os.rename(base / "end-received" / "127x03", tmp_path / "moved")
    os.symlink(elsewhere, base / "end-received" / "127x03")
    raises(si.Refusal, V.prepare, si, str(base / "end-received" / "127x03" / "end-127x03-r00-l01"))
    ok(os.listdir(elsewhere) == [])
