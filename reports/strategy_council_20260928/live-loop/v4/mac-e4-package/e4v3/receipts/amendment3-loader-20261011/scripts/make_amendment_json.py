"""Regenerate the Amendment 3 JSON record from the worktree files and receipts (run from the worktree root)."""
import json, hashlib, sys
from pathlib import Path
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
V = "reports/strategy_council_20260928/live-loop/v4"; P = V + "/mac-e4-package/e4v3"; R = P + "/receipts/amendment3-loader-20261011"
review = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None
before = {"tier_backend.py": "b04d201de7a95a36669e5c11898a297ba8f324d1a658f2987ec5ba244671add7", "prepare_bundle.py": "ad36c2020ab59ccafd91b3dbb03329a3fe1c2bb3b79d8b3d94b557d3daa6138e",
          "README.md": "bb1471641598237915c17b8b4c0cc09027c34c9b56f52adc6912594a4a59ebfc", "FLEET-INPUT-SCHEMA.md": "1579ae2551bc54ace12ab6cd3b5c414ab6e84b46f84f6426a2bdec16725b1e5c"}
changes = {P + "/" + f: dict(before_sha256=before.get(f), after_sha256=sha(P + "/" + f)) for f in
           ["tier_backend.py", "prepare_bundle.py", "state_rows.py", "convert_states.py", "tests/test_state_rows.py", "README.md", "FLEET-INPUT-SCHEMA.md"]}
unchanged = {P + "/" + f: sha(P + "/" + f) for f in ["measure_tiers.py", "fleet_reference.py", "replay_load.py", "corpus_contract.py", "receipts.py", "telemetry.py",
             "spec-pins.json", "fleet_pool.py", "fleet_end.py", "fleet_validity.py", "fleet_profile.py", "classify_failure.py"]}
assert unchanged[P + "/measure_tiers.py"].startswith("6066228b")
rec = json.load(open(R + "/conversion-05-reconstruction-r4.json")); ver = json.load(open(R + "/conversion-05-verified-states-r4s.json"))
rb = json.load(open(R + "/rss-one-backend-before-b04d201d.json")); ra = json.load(open(R + "/rss-one-backend-after.json")); eq = json.load(open(R + "/equivalence-old-vs-new.json"))
for receipt in (rec, ver):
    assert receipt["converter_sha256"] == sha(P + "/convert_states.py") and receipt["state_rows_sha256"] == sha(P + "/state_rows.py"), "stale conversion receipt"
assert ra["tier_backend_sha256"] == sha(P + "/tier_backend.py") == eq["new_tier_backend"], "stale backend receipt"
receipts = {str(p): sha(p) for p in sorted(Path(R).rglob("*")) if p.is_file()}
import re
def counts(name):
    text = Path(R + "/" + name).read_text()
    ran = int(re.search(r"^Ran (\d+) tests", text, re.M).group(1))
    skipped = re.search(r"^OK \(skipped=(\d+)\)", text, re.M)
    assert re.search(r"^OK", text, re.M) and text.rstrip().endswith("exit=0"), name
    return dict(log=R + "/" + name, ran=ran, skipped=int(skipped.group(1)) if skipped else 0, passed=True)
new_tests = len(re.findall(r"^    def test_", Path(P + "/tests/test_state_rows.py").read_text(), re.M))
tests = dict(py38=dict(python="3.8.10", **counts("unit-tests-py38.log")), py312=dict(python="3.12.12", torch="2.10.0+cpu", numpy="2.2.6", **counts("unit-tests-py312.log")),
             new_test_state_rows=new_tests, before_count=counts("unit-tests-py38.log")["ran"] - new_tests)
doc = dict(schema="clasher.tiers.amendment3-candidate.v1", status="CANDIDATE_PENDING_ADOPTION", study="PREREG-SEARCH-TIERS",
  title="Outcome-blind E4-v3 state-loading repair (memory)", prepared_host="127x05", branch="worker/e4-amendment3-loader-20261011",
  parent_commit="3cd0e58bd7ed1416e393f3d85ccfc4c653f86bad", coordinator_thread="0523ae6f-baa3-4d4e-b233-b392671670db",
  outcome_blind=True, outcomes_read=False, outcomes_sealed=True, timing_runs=False, ssh_to_01_03_04_08=False, mac_access=False,
  independent_review=review,
  note=dict(path=V + "/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.md", sha256=sha(V + "/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.md")),
  original_freeze=dict(path=V + "/PREREG-SEARCH-TIERS-FREEZE-20261010.json", sha256=sha(V + "/PREREG-SEARCH-TIERS-FREEZE-20261010.json"), unchanged=True),
  amendment_2=dict(path=V + "/PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json", sha256=sha(V + "/PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json"), unchanged=True),
  unchanged_semantics=dict(slots=11, warmup_seconds=300, op6_guard=True, memory_floor_gib=24, budgets=True, per_decision_timing=True,
      measure_tiers_sha256=unchanged[P + "/measure_tiers.py"], kernels_and_scorers=True,
      timed_methods_unchanged=["work", "_work", "prepare_work", "configure", "policy_input", "golden", "belief_result", "zero_budget", "infer", "activate", "core"]),
  cause=dict(t1_receipt="reports/explore/t1/receipts/END-offline-backend-memory-01-20261011T2033Z.json", one_backend_rss_anon_bytes_01=12305870848,
      estimated_11_anon_bytes=135364579328, host_mem_total_bytes=134897418240, required_with_floor_bytes=161134383104, shortfall_bytes=26236964864),
  measurements_05=dict(before=dict(tier_backend="b04d201d", **{k: rb[k] for k in ("after_construction", "after_probe", "construct_seconds")}),
      after=dict(tier_backend=ra["tier_backend_sha256"], **{k: ra[k] for k in ("after_construction", "after_probe", "construct_seconds")}),
      lookup_seconds_after=ra["probe"]["lookup_seconds"], admission_seconds=ra["probe"]["admission_seconds"], lookup_seconds_before=rb["probe"]["lookup_seconds"]),
  fixture_identity=dict(assembled_states_sha256="0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1",
      byte_redump_reproducible=False, reason="torch legacy storage pickle keys storages by str(storage._cdata), a memory address",
      reviewed_ordered_canonical_fingerprint=rec["fixture_canonical_fingerprint"],
      reconstruction_05=dict(receipt=R + "/conversion-05-reconstruction-r4.json", inputs={i["role"]: i["sha256"] for i in rec["inputs"]},
                             verification=rec["verification"], corpus_inventory=rec["corpus_inventory"]),
      verified_states_05=dict(receipt=R + "/conversion-05-verified-states-r4s.json", states_sha256=ver["inputs"][0]["sha256"],
                              fingerprint_equal=ver["fixture_canonical_fingerprint"] == rec["fixture_canonical_fingerprint"]),
      equivalence_old_vs_new={k: eq[k] for k in ("ordered_states_equal", "openings_equal", "policy_inputs_equal", "decisions", "mutation_checks", "suspended_sum_equal")},
      authoritative_binding="T1 converts the actual 01 states.pkl with --states --expect-fingerprint <reviewed>; that states-rows set is copied byte-identically wherever that fixture is used"),
  source_changes=changes, unchanged_files=unchanged, receipts=receipts,
  re_pins_required=dict(tiers=["this amendment record", "every bundle tiers-pins.json (files + measurement_files)", "END 01/08 bundles and both C3 preflights repeated",
                               "Mac bundle via prepare_bundle --state-rows", "Mac runtime re-staged from the Amendment 3 commit; arm64 build rebinds automatically"],
      k4s_mac_manifest=dict(path="reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json", sha256=sha("reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json"),
                            entry="reused_readonly tier_backend.py b04d201d -> Amendment 3 SHA; add state_rows.py", owner="coordinator", requires_independent_Sol_review=True),
      frozen_k4s=dict(path="reports/explore/k4s-confirm/run-r1/oa1/FROZEN-K4S.json", sha256=sha("reports/explore/k4s-confirm/run-r1/oa1/FROZEN-K4S.json"), e4v3_files_pinned=False),
      k4s_own_corpus_memory="k4s_backend.py still pickle.loads its 300-state K4 corpus (about 3 GiB resident); not changed here"),
  proposed_conditions=["same Amendment 3 bytes everywhere; b04d201d references/smokes void and unpoolable",
      "END: convert actual 01 states.pkl with --expect-fingerprint, copy one container set to 08, regenerate manifests, repeat C3 and one-backend memory check",
      "A3-P supplementary all-cause late-poll check (>25 ms rate <=1%, max <=50 ms) from existing Mac receipts, no code change",
      "Mac fixture converted on Linux under its own reviewed fingerprint; Mac never converts", "K4S companion re-pin (coordinator)"],
  tests=tests)
Path(V + "/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json").write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
print(sha(V + "/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.md"), sha(V + "/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json"))
