"""Old (b04d201d, whole states.pkl) vs new (Amendment 3) TierBackend on the same END fixture, offline.

Proves, on real rows and the real native kernel: identical ordered states, openings and policy
inputs; identical golden/belief/decision outputs for sampled decisions; and that no call mutates
a row (so reloading a state per lookup cannot change what a later decision sees).
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
prepare(NEW)
import tier_backend as new_module
old_module = load_module("tier_backend_original", OLD / "tier_backend.py")
from convert_states import canonical_digest, deep_equal
from receipts import TIERS, assert_exact
started = time.monotonic()
old = old_module.TierBackend(BUNDLE, RT, NATIVE)
import torch  # second backend in one process: interop threads are already 1 and cannot be re-set
assert torch.get_num_interop_threads() == 1 and torch.get_num_threads() == 1
torch.set_num_interop_threads = lambda n: None
new = new_module.TierBackend(BUNDLE, RT, NATIVE)
index = json.loads((BUNDLE / "states-rows.json").read_text())
canonical = {e["id"]: e["canonical_sha256"] for e in index["rows"]}
report = dict(construct_seconds=time.monotonic() - started)
ids = [str(r["id"]) for r in old.rows]
assert ids == new.state_rows.ids == [e["id"] for e in index["rows"]], "order"
assert all(canonical_digest(old.by_id[i]) == canonical[i] for i in ids), "states.pkl rows vs index"
report["ordered_states_equal"] = len(ids)
assert old.openings == new.openings, "openings"
report["openings_equal"] = len(old.openings)
assert set(old.inputs) - set(new.inputs) == set(old.inputs) and not new.inputs  # fleet-reference: no agreement set
checked = 0
for identity in old.inputs:
    assert canonical_digest(old.inputs[identity]) == canonical_digest(new.policy_input(new.by_id[identity])), identity
    checked += 1
report["policy_inputs_equal"] = checked
manifest = old.manifest
decisions, mutation_checks = [], 0
def unchanged(row):
    global mutation_checks
    assert canonical_digest(row) == canonical[str(row["id"])], "row mutated: " + str(row["id"])
    mutation_checks += 1
for identity in manifest["sets"]["golden"][:3]:
    for tier in ("K0c", "K1", "K2", "K4"):
        a, b = old.golden(old.by_id[identity], tier), new.golden(new.by_id[identity], tier)
        assert_exact(a, b, "golden/" + tier); unchanged(old.by_id[identity]); unchanged(new.by_id[identity])
    for deadline_on in (False, True):
        assert_exact(old.belief_result(old.by_id[identity], deadline_on), new.belief_result(new.by_id[identity], deadline_on), "belief")
    old.zero_budget(old.by_id[identity]); new.zero_budget(new.by_id[identity])
    unchanged(old.by_id[identity]); unchanged(new.by_id[identity])
    decisions.append(("golden", identity))
for tier in TIERS:
    for identity in manifest["sets"]["speed"][tier][::100]:
        for backend in (old, new):
            backend.activate(tier)
        ra, ta = old.work(old.by_id[identity], tier)
        rb, tb = new.work(new.by_id[identity], tier)
        assert_exact(ra, rb, "decision/" + tier); assert_exact(ta["forward"], tb["forward"], "forward/" + tier)
        assert ta["root_digest"] == tb["root_digest"]
        # The same decision under the 200 ms budget path: admission before entry, as measure_tiers does.
        for backend in (old, new):
            backend.prepare_work(backend.by_id[identity])
        unchanged(old.by_id[identity]); unchanged(new.by_id[identity])
        old.prepared_work = new.prepared_work = None
        decisions.append((tier, identity))
report.update(decisions=len(decisions), decision_ids=decisions, mutation_checks=mutation_checks,
              suspended_sum_equal=sum(r.get("belief_had_suspended_transaction", False) for r in old.rows) ==
                                  sum(r.get("belief_had_suspended_transaction", False) for r in new.rows),
              seconds=time.monotonic() - started, outcomes_read=False, timing=False,
              old_tier_backend="b04d201d", new_tier_backend=__import__("hashlib").sha256((NEW / "tier_backend.py").read_bytes()).hexdigest())
old.close(); new.close()
print(json.dumps(report, sort_keys=True), flush=True)
(W / ("equivalence-" + os.environ.get("A3_RUN", "r3") + ".json" if os.environ.get("A3_R3") else "equivalence-r1.json")).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
