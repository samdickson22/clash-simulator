"""S6 verifier (k4s_end_verify_push.py) on directories produced by the real wrapper copy + fake producer.

Only ``BASE`` is monkeypatched to a temporary 05 runner root. Under ``python -O`` the verifier refuses at import
(T1 R3-1); then only that refusal is tested.
"""
import datetime
import importlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from helpers import ROOT, sha
from test_s6_wrapper import Harness

if not __debug__:
    def test_verifier_refuses_optimized_python():
        with pytest.raises(SystemExit, match="refuses optimized"):
            importlib.import_module("k4s_end_verify_push")
else:
    V = importlib.import_module("k4s_end_verify_push")


def utc(offset=0):
    return datetime.datetime.fromtimestamp(time.time() + offset, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def flow(tmp_path, monkeypatch):
    if not __debug__:
        pytest.skip("verifier refuses -O at import")
    monkeypatch.setattr(V, "BASE", tmp_path / "recv")
    h = Harness(tmp_path, "k4s_end_exit_push.sh")

    def go(mode="complete", name="end-127x03-r00-l00", prepare=True):
        job = h.job(name)
        root = tmp_path / "recv" / "end-received" / h.host / job.name
        if prepare:
            V.prepare(root)
            proof = json.loads((root / "PREPARED.json").read_text())
            proof["utc"] = utc(-20)
            (root / "PREPARED.json").write_text(json.dumps(proof, sort_keys=True) + "\n")
        else:
            proof = {}
        argv = h.end_argv(job)
        launch = dict(host=h.host, job=str(job), utc=utc(-10), wrapper_sha256=sha(ROOT / "k4s_end_exit_push.sh"),
                      measurement_argv=argv)
        result = h.run(job, argv, mode=mode)
        return root, launch, proof, result
    return go


def test_wrapper_pin_is_the_delivered_wrapper():
    text = (ROOT / "k4s_end_verify_push.py").read_text()
    assert sha(ROOT / "k4s_end_exit_push.sh") in text


def test_complete_is_sealed_and_claim_bound(flow):
    root, launch, proof, result = flow()
    assert result.returncode == 0, result.stderr
    out = V.verify(root, launch, proof)
    assert out["classification"] == "SEALED" and out["status"] == "complete" and out["ack_allowed"] is True
    assert out["claim_bound"] is True and out["claim_without_receipt"] is False
    assert [c["name"] for c in out["registry_claims"]] == ["attempt-00.json"]


def test_failed_seal_is_ackable_as_failed(flow):
    root, launch, proof, result = flow(mode="failed")
    assert result.returncode == 1
    out = V.verify(root, launch, proof)
    assert out["status"] == "failed" and out["ack_allowed"] is True


def test_claim_without_receipt_is_recorded(flow):
    root, launch, proof, result = flow(mode="claim-only")
    out = V.verify(root, launch, proof)
    assert out["classification"] == "UNSEALED" and out["ack_allowed"] is False
    assert out["claim_without_receipt"] is True and out["registry_claims"][0]["receipt_directory"] == root.name


def test_preclaim_refusal_records_no_claim(flow):
    root, launch, proof, result = flow(mode="preclaim")
    out = V.verify(root, launch, proof)
    assert out["classification"] == "UNSEALED" and out["claim_without_receipt"] is False
    assert out["registry_claims"] == []


def test_earlier_claim_listed_but_not_this_attempt(flow):
    flow(mode="claim-only", name="end-127x03-r00-l00")
    root, launch, proof, result = flow(mode="preclaim", name="end-127x03-r00-l01")
    out = V.verify(root, launch, proof)
    assert [c["receipt_directory"] for c in out["registry_claims"]] == ["end-127x03-r00-l00"]
    assert out["claim_without_receipt"] is False


def refuse(root, launch, proof, match):
    with pytest.raises((ValueError, KeyError, FileNotFoundError), match=match):
        V.verify(root, launch, proof)


def test_refusals(flow, tmp_path):
    root, launch, proof, _ = flow()
    refuse(root, dict(launch, wrapper_sha256="0" * 64), proof, "Unapproved")
    refuse(root, dict(launch, measurement_argv=launch["measurement_argv"][:-1]), proof, "argv")
    refuse(root, launch, dict(proof, nonce="f" * 32), "proof changed")
    refuse(root, dict(launch, utc=utc(+3600)), proof, "precede")
    # registry tampering
    claim = root / "registry" / "attempt-00.json"
    original = claim.read_bytes()
    data = json.loads(original)
    claim.write_text(json.dumps(dict(data, host="127x04")))
    refuse(root, launch, proof, "namespace")
    claim.write_text(json.dumps(dict(data, launched_utc=1.0)))
    refuse(root, launch, proof, "lacks its registry claim")
    claim.write_bytes(original)
    (root / "registry" / "attempt-02.json").write_bytes(original)
    refuse(root, launch, proof, "contiguous")
    (root / "registry" / "attempt-02.json").unlink()
    (root / "registry" / "attempt-01.json").write_bytes(original)
    refuse(root, launch, proof, "namespace")                     # a copied claim keeps attempt 0
    (root / "registry" / "attempt-01.json").write_text(json.dumps(dict(data, attempt=1)))
    refuse(root, launch, proof, "Several")
    (root / "registry" / "attempt-01.json").unlink()
    V.verify(root, launch, proof)


def test_refuses_sealed_receipt_without_pushed_registry(flow):
    root, launch, proof, _ = flow()
    exit_ = json.loads((root / "exit.json").read_text())
    import shutil
    shutil.rmtree(root / "registry")
    refuse(root, launch, proof, "Registry/exit")
    (root / "exit.json").write_text(json.dumps(dict(exit_, registry_exists=False)))
    refuse(root, launch, proof, "lacks its registry claim")


def test_refuses_seal_tampering_and_scope(flow):
    root, launch, proof, _ = flow()
    data = root / "durable-measurement"
    (data / "extra.json").write_text("{}")
    refuse(root, launch, proof, "Extra")
    (data / "extra.json").unlink()
    seal = json.loads((data / "receipt-manifest.json").read_text())
    (data / "receipt-manifest.json").write_text(json.dumps(dict(seal, scope="K4S-END-PREFLIGHT")))
    (data / "receipt-manifest.sha256").write_text(sha(data / "receipt-manifest.json") + "  receipt-manifest.json\n")
    refuse(root, launch, proof, "scope")


def test_refuses_push_failed_and_wrong_namespace(flow, tmp_path):
    root, launch, proof, _ = flow()
    (root / "PUSH-FAILED.json").write_text("{}")
    refuse(root, launch, proof, "PUSH-FAILED")
    (root / "PUSH-FAILED.json").unlink()
    with pytest.raises(ValueError, match="host namespace"):
        V.namespace(tmp_path / "recv" / "end-received" / "127x01" / "a")
    with pytest.raises(ValueError, match="receive namespace"):
        V.namespace(tmp_path / "elsewhere" / "127x03" / "a")


def test_exit_registry_flag_must_be_boolean(flow):
    root, launch, proof, _ = flow()
    exit_ = json.loads((root / "exit.json").read_text())
    exit_.pop("registry_exists")
    (root / "exit.json").write_text(json.dumps(exit_))
    refuse(root, launch, proof, "registry_exists")


def test_main_requires_05_nice19_cpu63(monkeypatch, tmp_path):
    if not __debug__:
        pytest.skip("verifier refuses -O at import")
    monkeypatch.setattr(sys, "argv", ["v", "--receive", str(tmp_path / "x"), "--prepare"])
    monkeypatch.setattr(socket, "gethostname", lambda: "127x03")
    with pytest.raises(ValueError):
        V.main()


def test_optimized_import_refusal_subprocess():
    done = subprocess.run([sys.executable, "-O", "-c", "import k4s_end_verify_push"], cwd=ROOT,
                          capture_output=True, text=True)
    assert done.returncode != 0 and "refuses optimized" in done.stderr
