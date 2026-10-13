"""A synthetic 127x03/127x04 host layout for S5 preflight tests (all under tmp_path): k4s-end-r1 base, runtime with
a SYNTHETIC frozen closure + K4S manifest, preflight and attempt bundles (pinned tiers-pins.json, sidecar, production
assembly receipt), git clones (repository; guard job repo/ with two commits), attempt/preflight parents, inputs.

Test-only route (explicitly marked): K4S_MANIFEST_SHA256, FROZEN_CLOSURE, SEED_COMMITS, the minimum hold/sample
constants and si.END_BASES/Q4_GUARD_PARENTS are monkeypatched to these synthetic values; production constants are
covered separately (test_s5_preflight: production anchors)."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import fake_frozen
import helpers as H

import k4s_end_preflight as S

RUNTIME_NAME = "runtime-0123456789ab"
CLOSURE_RELS = S.END_SOURCES + ("reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts.py",
                                "reports/explore/k4s-confirm/sdefault.py", "reports/explore/k4s-confirm/SD1-MANIFEST.json")


def synthetic_manifest(closure):
    end = {r: closure[r] for r in closure if r.startswith("reports/explore/k4s-confirm/end_")}
    k4s = {r: closure[r] for r in closure if "/mac/" in r}
    return dict(schema="clasher.k4s.mac-manifest.v1", frozen=True, status="FROZEN", end_files=end, k4s_files=k4s,
                reused_readonly={r: closure[r] for r in closure if "/e4v3/" in r},
                k4s_kernel=dict(files={"reports/explore/k4s-confirm/sdefault.py":
                                       closure["reports/explore/k4s-confirm/sdefault.py"]}),
                sd1_manifest=dict(path="reports/explore/k4s-confirm/SD1-MANIFEST.json",
                                  sha256=closure["reports/explore/k4s-confirm/SD1-MANIFEST.json"]),
                corpus=dict(inventory=S.CORPUS_INVENTORY_REL))


def bundle(path, manifest, receipt_over=None):
    data = (H.canonical(manifest) + "\n").encode()
    digest = H.sha_bytes(data)
    H.write(path / "tiers-pins.json", data)
    H.write(path / "tiers-pins.sha256", digest + "  tiers-pins.json\n")
    receipt = dict(schema=S.ASSEMBLY_SCHEMA, production_pins=True, status="CANDIDATE", manifest_sha256=digest,
                   guard_job=manifest["reference_load_profile"]["guard"]["job"])
    receipt.update(receipt_over or {})
    H.write(path / "assembly-receipt.json", H.canonical(receipt) + "\n")
    H.write(path / "end-evidence.json", b'{"synthetic": true}\n')
    return digest


def build(tmp, monkeypatch, host="127x03", fake=None, slot_count=3, attempt="preflight-%s-l00", contents=None,
          **over):
    tmp = Path(tmp)
    si, tool = H.load_layers()
    fs = tmp / "hostfs"
    base, q4 = fs / "k4s-end-r1", fs / "q4"
    monkeypatch.setitem(si.END_BASES, host, str(base))
    monkeypatch.setitem(si.Q4_GUARD_PARENTS, host, str(q4))
    monkeypatch.setattr(os, "uname", H.fake_uname(host))
    monkeypatch.setenv("HOME", str(tmp / "home"))
    (tmp / "home").mkdir(parents=True, exist_ok=True)
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
    runtime = base / RUNTIME_NAME
    closure = {}
    for rel in CLOSURE_RELS:
        data = (contents or {}).get(rel, "# synthetic stand-in for %s\n" % rel)
        closure[rel] = H.sha(H.write(runtime / rel, data))
    manifest_bytes = (json.dumps(synthetic_manifest(closure), sort_keys=True) + "\n").encode()
    H.write(runtime / S.MANIFEST_REL, manifest_bytes)
    inventory = H.write(runtime / S.CORPUS_INVENTORY_REL, b'{"synthetic": "corpus inventory"}\n')
    monkeypatch.setattr(S, "K4S_MANIFEST_SHA256", H.sha_bytes(manifest_bytes))
    monkeypatch.setattr(S, "FROZEN_CLOSURE", closure)
    monkeypatch.setattr(S, "MIN_HOLD_SECONDS", {"127x03": 0.4, "127x04": 0.4})
    monkeypatch.setattr(S, "MIN_LOADED_SECONDS", {"127x03": 0.2, "127x04": 0.2})
    monkeypatch.setattr(S, "MIN_SAMPLES", 3)
    monkeypatch.setattr(S, "BLOCK_SECONDS_RANGE", (0.1, 300))
    pf_job, at_job = q4 / "k4s-end-guard-r1-pf00", q4 / "k4s-end-guard-r1-rd00-a00"
    seeds = H.shallow_guard_repo(pf_job / "repo", tmp / "seed-source")
    monkeypatch.setattr(S, "SEED_COMMITS", seeds)
    F = fake_frozen.make(pf_job, fake, host=host, slot_count=slot_count)
    pf_bundle, at_bundle = base / "bundles" / "pf00", base / "bundles" / "a00"
    pf_sha = bundle(pf_bundle, F.manifest)
    attempt_manifest = json.loads(json.dumps(F.manifest))
    attempt_manifest["reference_load_profile"]["guard"]["job"] = str(at_job)
    at_sha = bundle(at_bundle, attempt_manifest)
    H.git_repo(base / "repository", files={"reports/explore/k4s-confirm/README": b"study\n"})
    (base / "attempts").mkdir(parents=True)
    name = attempt % host
    job = base / "preflight" / name
    job.mkdir(parents=True)
    native = H.write(base / "inputs" / "native.so", b"synthetic native\n")
    corpus = H.write(base / "inputs" / "k4-states.pkl", b"synthetic corpus\n")
    # test-only: the synthetic native/corpus/inventory identities replace the production K4S END identities
    monkeypatch.setattr(S, "NATIVE_SHA256", H.sha(native))
    monkeypatch.setattr(S, "CORPUS_SHA256", F.ER.K4_CORPUS_SHA256)
    monkeypatch.setattr(S, "CORPUS_INVENTORY_SHA256", H.sha(inventory))
    a = SimpleNamespace(bundle=str(pf_bundle), bundle_pins_sha256=pf_sha, runtime_root=str(runtime),
                        native=str(native), corpus=str(corpus), corpus_inventory=str(inventory),
                        corpus_inventory_sha256=H.sha(inventory), k4s_manifest_sha256=H.sha_bytes(manifest_bytes),
                        sd1_manifest_sha256="5" * 64, end_evidence=str(pf_bundle / "end-evidence.json"),
                        end_evidence_sha256="e" * 64, repository=str(base / "repository"),
                        attempt_parent=str(base / "attempts"), out=str(job / name), compare_bundle=str(at_bundle),
                        compare_bundle_pins_sha256=at_sha, end_job_sha256=None, hold_seconds=0.8,
                        block_seconds=0.3, min_samples=3, reference_work=True)
    for k, v in over.items():
        setattr(a, k, v)
    monkeypatch.setenv("GIT_DIR", "/inherited/evil")                # must be scrubbed by frozen_git_env
    return SimpleNamespace(si=si, tool=tool, a=a, F=F, base=base, q4=q4, pf_job=pf_job, at_job=at_job, job=job,
                           runtime=runtime, host=host, pf_bundle=pf_bundle, at_bundle=at_bundle)


HOSTINFO = dict(nice=10, sched_other=True, optimized=False)


def go(env, frozen_factory=None):
    code = S.run(env.a, frozen_factory=frozen_factory or (lambda root: env.F),
                 hostinfo=dict(HOSTINFO, host=env.host), layers=(env.si, env.tool))
    out = Path(env.a.out)
    result = json.loads((out / "preflight-result.json").read_text())
    seal = json.loads((out / "receipt-manifest.json").read_text())
    return code, result, seal
