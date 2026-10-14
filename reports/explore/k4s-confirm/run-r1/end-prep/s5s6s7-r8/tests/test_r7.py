"""r7 (ruling PF-4, COORDINATOR c14b40e8): the S5 checks that were stricter than the frozen END.

- background_ready: the frozen END only RECORDS slot-evidence.json (end_reference.py:371-374); the frozen backends
  narrow each background worker to search_cpus[:width] per tier (tier_backend.py:238, k4s_backend.py:100). The
  readbacks observed on 127x04 l00 (preflight-result.json slot_evidence, metadata only) must pass; each readback must
  be a non-empty subset of its pinned mask and the masks pairwise disjoint.
- mhz_comparison: END compares only rows after its frozen warmup_seconds (end_reference.py:375-390); so does S5.
- an error raised while no check row is open fails the run (END: end_reference.py:225-230).
Class table: CLASS-TABLE-PF4.md."""
import ast
import hashlib
import json
import os
from pathlib import Path

import pytest

import k4s_end_preflight as S
import s5_fixture as X
from helpers import ok

RUNNER = "/mpac/sdicks02/k4s-runner/run-r1"
FROZEN_END = RUNNER + "/end-staging/runtime-98566c032d0b/runtime/reports/explore/k4s-confirm/end_reference.py"
EVIDENCE_04 = RUNNER + "/preflight-received/127x04/preflight-127x04-l00/preflight/preflight-result.json"
END_REFERENCE_PIN = dict(S.FROZEN_CLOSURE)["reports/explore/k4s-confirm/end_reference.py"]

# 127x04 l00 (r6 S5, failed at background_ready): the recorded slot evidence. Pinned masks: reference [0..4], then
# ten disjoint five-CPU masks 5-9 .. 50-54 (11 slots).
SEARCH_04 = [0, 1, 2, 3, 4]
MASKS_04 = [list(range(5 + 5 * i, 10 + 5 * i)) for i in range(10)]
OBSERVED_04 = dict(reference_affinity=SEARCH_04, reference_nice=10,
                   background_affinity=[[5], [10], [15, 16, 17], [20, 21, 22, 23, 24], [25], [30], [35, 36, 37],
                                        [40, 41, 42, 43, 44], [45], [50]],
                   background_nice=[10] * 10)
WORKER0 = 900001                                       # fake_frozen.Background worker pids


@pytest.fixture(autouse=True)
def host_os(monkeypatch):
    saved = dict(os.environ)
    state = dict(readbacks=[[2, 3], [4, 5]], nice={})        # fake_frozen default layout; 04 tests set their own
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: None)
    monkeypatch.setattr(os, "sched_getaffinity",
                        lambda pid: set(state["readbacks"][pid - WORKER0]) if pid >= WORKER0 else set(SEARCH_04))
    monkeypatch.setattr(os, "getpriority", lambda which, pid: state["nice"].get(pid, 10))
    yield state
    os.environ.clear()
    os.environ.update(saved)


def by_name(result):
    return {c["name"]: c for c in result["checks"]}


def run_04(tmp_path, monkeypatch, masks=MASKS_04, slot_count=11, **fake):
    env = X.build(tmp_path, monkeypatch, host="127x04", slot_count=slot_count,
                  fake=dict(fake, layout=[SEARCH_04, masks, 63]))
    return X.go(env)


# ---------------------------------------------------------------- background_ready: affinity subset (PF-4 item 1)

@pytest.mark.skipif(not os.path.isfile(EVIDENCE_04), reason="04 l00 preflight evidence not on this machine")
def test_pf4_regression_data_is_the_recorded_04_slot_evidence():
    """The literal below is exactly what 04 l00 recorded (read-only, preflight metadata)."""
    ok(json.loads(Path(EVIDENCE_04).read_text())["slot_evidence"] == OBSERVED_04)


def test_pf4_observed_04_readbacks_pass(tmp_path, monkeypatch, host_os):
    """The readbacks that failed r6's equality check pass; the evidence is recorded with END's four fields."""
    host_os["readbacks"] = OBSERVED_04["background_affinity"]
    ok(OBSERVED_04["background_affinity"] != MASKS_04)          # an equality-only rule refuses this run
    code, result, seal = run_04(tmp_path, monkeypatch)
    rows = by_name(result)
    ok(code == 0 and result["passed"] and seal["status"] == "passed", result.get("error"))
    ok(rows["background_ready"]["passed"] is True and rows["background_ready"]["workers"] == 10)
    ok(result["slot_evidence"] == OBSERVED_04)
    ok(result["load"]["background_slots_ready"] == result["load"]["background_slots_expected"] == 10)
    ok(result["mode"] == "binding" and result["qualifying"] is True)


def test_pf4_full_mask_readbacks_still_pass(tmp_path, monkeypatch, host_os):
    """A K4-width worker reads back its whole mask (tier_backend.py:238 width 5): equality is a subset too."""
    host_os["readbacks"] = MASKS_04
    code, result, _ = run_04(tmp_path, monkeypatch)
    ok(code == 0 and by_name(result)["background_ready"]["passed"] is True, result.get("error"))


def _cross(readbacks):
    return [list(r) for r in readbacks]


NEGATIVES = {
    "cpu-of-the-next-mask": (MASKS_04, 11, lambda r: r[:3] + [[20, 25]] + r[4:]),
    "reference-cpu": (MASKS_04, 11, lambda r: [[0]] + r[1:]),
    "empty-readback": (MASKS_04, 11, lambda r: r[:5] + [[]] + r[6:]),
    "overlapping-masks": ([[5, 6, 7], [7, 8, 9]], 3, lambda r: [[5], [8]]),
    "fewer-workers-than-masks": ([[5, 6], [7, 8], [9, 10]], 3, lambda r: [[5], [7]]),
}


@pytest.mark.parametrize("case", sorted(NEGATIVES))
def test_pf4_non_subset_or_overlapping_masks_refused(tmp_path, monkeypatch, host_os, case):
    masks, slots, make = NEGATIVES[case]
    host_os["readbacks"] = make(_cross(OBSERVED_04["background_affinity"]))
    code, result, seal = run_04(tmp_path, monkeypatch, masks=masks, slot_count=slots)
    row = by_name(result)["background_ready"]
    ok(code == 1 and seal["status"] == "failed" and row["passed"] is False, row)
    ok("not a non-empty subset of its pinned (disjoint) mask" in row["error"], row["error"])
    ok(result["slot_evidence"]["background_affinity"] == [sorted(x) for x in host_os["readbacks"][:slots - 1]])
    ok("loaded_hold" not in by_name(result) and by_name(result)["cleanup"]["passed"] is True)


@pytest.mark.parametrize("who", ["reference", "background"])
def test_pf4_priority_readback_still_required(tmp_path, monkeypatch, host_os, who):
    """Kept: nice 10 is the pinned reporting priority END itself enforces (fleet_profile.py:13 via
    end_background.py:84-85,113; every worker re-checks it); a renice after start is refused."""
    host_os["readbacks"] = OBSERVED_04["background_affinity"]
    host_os["nice"] = {0: 0} if who == "reference" else {WORKER0 + 4: 5}
    code, result, _ = run_04(tmp_path, monkeypatch)
    row = by_name(result)["background_ready"]
    ok(code == 1 and row["passed"] is False and "nice 10" in row["error"], row)


def _slot_dict_in(tree, match):
    for node in ast.walk(tree):
        if match(node):
            return node
    raise AssertionError("slot evidence expression not found")


def test_pf4_slot_evidence_is_recorded_exactly_as_the_frozen_end():
    """The S5 slot record is the frozen END's slot-evidence.json expression, field for field (AST-equal)."""
    data = Path(FROZEN_END).read_bytes() if os.path.isfile(FROZEN_END) else None
    if data is None:
        pytest.skip("frozen runtime not on this machine")
    ok(hashlib.sha256(data).hexdigest() == END_REFERENCE_PIN)       # the closure-pinned end_reference.py
    end = _slot_dict_in(ast.parse(data), lambda n: isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "write"
                        and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "slot-evidence.json")
    ours = _slot_dict_in(ast.parse(Path(S.__file__).read_text()),
                         lambda n: isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "slots")
    ok(ast.dump(end.args[1]) == ast.dump(ours.value))
    ok(sorted(k.arg for k in ours.value.keywords) == sorted(OBSERVED_04))


# ---------------------------------------------------------------- mhz_comparison: END's warm-up exclusion

def _hold_rows(result_dir):
    rows = [json.loads(s) for s in (Path(result_dir) / "capacity.jsonl").read_text().splitlines()]
    return [r for r in rows if r["phase"] == S.HOLD_PHASE]


def test_pf4_mhz_window_leaves_out_the_frozen_warmup(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(warmup_seconds=0.4))
    code, result, _ = X.go(env)
    ok(code == 0 and result["passed"], result.get("error"))
    held = _hold_rows(env.a.out)
    settled = held[0]["timestamp"] + 0.4
    compared = [r for r in held if r["timestamp"] >= settled]
    m = result["mhz_comparison"]
    ok(2 <= len(compared) < len(held), (len(compared), len(held)))
    ok(m["window"] == dict(warmup_seconds=0.4, hold_rows=len(held), compared_rows=len(compared)), m["window"])
    ok(m["reference_rows"] == len(compared) and m["first_reference_timestamp"] >= settled)
    ok(by_name(result)["mhz_comparison"]["gate"] is True and m["passes"] is True)


def test_pf4_mhz_gate_still_applies_after_the_warmup(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(warmup_seconds=0.4, mhz_fails=True))
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["mhz_comparison"]["passed"] is False and result["passed"] is False)


def test_pf4r8_binding_hold_with_a_starved_sampler_fails_closed(tmp_path, monkeypatch):
    """Sol PF4-r1 F1: a binding (reference-work) hold that leaves fewer than 2 rows after the frozen warmup_seconds
    (here: every sampled row falls inside the warm-up, while total samples and the loaded span are adequate) must fail
    closed, as the frozen END refuses fewer than 2 measured MHz rows (fleet_profile.py:59-62)."""
    env = X.build(tmp_path, monkeypatch, fake=dict(warmup_seconds=60))
    code, result, seal = X.go(env)
    row = by_name(result)["mhz_comparison"]
    m = result["mhz_comparison"]
    ok(m["passes"] is None and m["window"]["compared_rows"] < 2 and m["window"]["hold_rows"] >= 2 and m["unavailable"])
    ok(row["passed"] is False and row["gate"] is True and "binding hold" in row["error"], row)
    ok(code == 1 and result["passed"] is False and result["qualifying"] is False and seal["status"] == "failed")


def test_pf4r8_short_diagnostic_hold_records_unavailable_and_is_non_qualifying(tmp_path, monkeypatch):
    """Only a deliberately diagnostic hold (--no-reference-work) may record the MHz window as unavailable."""
    env = X.build(tmp_path, monkeypatch, fake=dict(warmup_seconds=60, mhz_fails=True), reference_work=False)
    code, result, _ = X.go(env)
    row = by_name(result)["mhz_comparison"]
    m = result["mhz_comparison"]
    ok(m["passes"] is None and m["unavailable"] and row["passed"] is True and row["gate"] is False, row)
    ok(code == 0 and result["passed"] and result["mode"] == "diagnostic" and result["qualifying"] is False)


class _AllPassed:
    def all_passed(self):
        return True


def test_pf4r8_binding_mode_requires_a_passing_mhz_comparison():
    """verdict(): with every other binding condition met, missing or unavailable MHz evidence is never
    binding/qualifying (Sol PF4-r1 F1)."""
    snap = dict(attempt_parent=[], registry=dict(claims={}))
    base = dict(mode_requested="binding", hold_seconds=1200.0, before=snap, after=dict(snap), guard_sources={},
                load=dict(reference_slot_work=True, reference_slot_states_worked=5, background_slots_ready=10,
                          background_slots_expected=10, slot_count=11),
                summaries=dict(bus=dict(cumulative_loaded=dict(seconds=1000.0), loaded_band="proceed"),
                               sshd=dict(sshd_count_growth_during_hold=False)))
    for mhz, mode, qualifying in ((dict(passes=True), "binding", True), (dict(passes=None), "diagnostic", False),
                                  (None, "diagnostic", False)):
        result = dict(base, **({} if mhz is None else dict(mhz_comparison=mhz)))
        v = S.verdict(_AllPassed(), result, "127x04")
        ok(v["passed"] is True and v["mode"] == mode and v["qualifying"] is qualifying, (mhz, v))


# ---------------------------------------------------------------- an error outside every check row

def test_pf4_error_outside_any_check_fails_the_run(tmp_path, monkeypatch):
    """The frozen background __exit__ (check + close) raising after loaded_hold ended: no row is open, every recorded
    row passed, and the run must still fail (r6 sealed it passed)."""
    env = X.build(tmp_path, monkeypatch, fake=dict(exit_fails=True))
    code, result, seal = X.go(env)
    ok(code == 1 and result["passed"] is False and seal["status"] == "failed" and result["qualifying"] is False)
    ok("Fleet background failure at exit" in result["error"])
    ok(all(c["passed"] is True or c.get("skipped") for c in result["checks"]))
    ok("loaded_hold" in by_name(result) and "monitor_stop" not in by_name(result))
