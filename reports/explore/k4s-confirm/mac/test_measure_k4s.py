"""Offline tests for the K4S Mac measurement logic (no torch, no native, no Mac, no network)."""
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_manifest as B  # noqa: E402
import classify_k4s_failure as C  # noqa: E402
import k4s_logic as L  # noqa: E402
import measure_k4s as M  # noqa: E402

GOLDEN = 125


# ---------------------------------------------------------------- fixtures

def rates(n, cutoff, ncp, fallback=0):
    return dict(n=n, cutoff_count=cutoff, cutoff=cutoff / n, no_complete_play_count=ncp,
                no_complete_play=ncp / n, fallback_count=fallback, fallback=fallback / n)


FLEET = {"1.0": rates(900, 9, 9), "0.9": rates(900, 18, 18), "0.8": rates(900, 45, 45),
         "0.7": rates(900, 90, 90), "0.6": rates(900, 180, 180)}


def inputs(**over):
    base = dict(gate0=dict(passes=True, parts=dict(tiers_exactness_and_worker_equality=True)),
                r_k4s=1.0, p10_k4s=.95, r_inf=1.0, poll_p99_seconds=.010,
                perception=dict(fps=20., processed_fraction=1.), gc=dict(passes=True),
                mac_deadline=rates(300, 3, 3), fleet_deadline=FLEET)
    base.update(over)
    return base


def tiers(k4_full=False, kind=None, gate0=True):
    return dict(gate0=dict(passes=gate0, parts=dict(tiers_exactness_and_worker_equality=gate0)),
                exactness_failure_kind=kind, k4_cell_1_0=k4_full, sessions=[])


def tree_state(root):
    root = Path(root)
    return {str(p.relative_to(root)): (L.sha(p), p.stat().st_mtime_ns) for p in sorted(root.rglob("*")) if p.is_file()}


COMMITS = {}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit_receipts(directory):
    """Commit a TIERS receipt directory in its parent git repository (r3 N2: committed receipts)."""
    directory = Path(directory)
    repo = directory.parent
    if not (repo / ".git").exists():
        git(repo, "init", "-q")
    git(repo, "add", "--", directory.name)
    git(repo, "-c", "user.name=K4S fixture", "-c", "user.email=k4s-fixture@example.invalid", "commit", "-q", "-m", "fixture")
    COMMITS[str(directory)] = git(repo, "rev-parse", "HEAD")
    return COMMITS[str(directory)]


def committed(directory):
    directory = Path(directory)
    return dict(repository=directory.parent, commit=COMMITS[str(directory)], repository_path=directory.name)


def read_session(directory, digest, **kwargs):
    return L.read_tiers_session(directory, digest, committed=committed(directory), **kwargs)


def tiers_args(directory, digest):
    directory = Path(directory)
    return ["--tiers-receipts", str(directory), "--tiers-receipt-sha256", digest, "--tiers-receipt-commit",
            COMMITS[str(directory)], "--tiers-receipt-repo-path", directory.name, "--repository", str(directory.parent)]


def make_tiers_session(directory, *, state="complete", scope="LINUX-DRY-RUN:PROVISIONAL-LOAD", r=1.05, p10=.9,
                       cell=1.0, feasible=True, measured_cut=.01, lock_path=None, utc=None, error=None,
                       manifest_sha="b" * 64, native_sha=L.NATIVE_PROVENANCE_SHA):
    store = L.K4SStore(directory, scope)
    store.write("tiers-identity.json", dict(manifest_sha256=manifest_sha, load_label="PROVISIONAL-LOAD", host="mac",
                                            machine="arm64", platform="Darwin"))
    if lock_path is not None:
        store.write("coordinator-lock.json", dict(path=str(lock_path), held_exclusively=True, receipt=""))
    store.write("build-tiers.json", dict(native_sha256=native_sha, source_manifest_sha256=manifest_sha,
                                         target="aarch64-apple-darwin", locked=True, rustflags=""))
    if state == "complete":
        store.write("exactness-tiers.json", dict(passes=True, states=GOLDEN, records=[
            dict(id=str(i), workers_equal=True, zero_budget_immutable=True) for i in range(GOLDEN)]))
        store.write("belief-exactness.json", dict(passes=True, histories=GOLDEN,
                                                  posterior_weights_cumulative_ledger_samples_rng_exact=True))
        store.write("student-agreement.json", dict(backends=dict(cpu=dict(passes=True, fraction=1., n=2000))))
        store.write("tiers-summary.json", dict(
            exactness_class="EXACT", speed=dict(K4=dict(r=r, p10=p10)),
            feasibility=dict(K4=dict(feasible=feasible, cell=cell, gates={"3_exactness": True})),
            deadline_equivalence=dict(K4=dict(cell=cell, checks=[dict(cell=1.0, passes=True,
                reference=dict(cutoff=.02, no_complete_play=.02), measured=dict(cutoff=measured_cut, no_complete_play=.01))]))))
        store.write("tiers-complete.json", dict(completed=True, utc=time.time() if utc is None else utc, final=False))
        store.seal("complete")
    elif state == "exactness":
        store.write("failure.json", dict(error=error or "Traceback (most recent call last):\nValueError: Exactness mismatch: g7/1=4\n"))
        store.seal("failed")
    else:
        store.write("failure.json", dict(error="Traceback (most recent call last):\nRuntimeError: Replay worker failed\n"))
        store.seal("failed")
    commit_receipts(directory)
    return Path(directory), L.sha(Path(directory) / "receipt-manifest.json")


def no_classify(directory):
    return dict(technical_repeat_candidate=False, reasons=[])


# ---------------------------------------------------------------- cell mapping

def test_all_gates_pass_maps_to_0_9():
    mapping = L.map_cell(inputs())
    assert mapping["c_M_k4s"] == "0.9" and mapping["provisional_cell"] == "0.9"
    assert mapping["gate6_trail"] == [dict(cell="0.9", passes=True, gate6=True)]


@pytest.mark.parametrize("r,p10,expected", [(.95, .9, "0.9"), (.85, .8, "0.8"), (.75, .65, "0.7"),
                                            (.65, .55, "0.6"), (.59, .55, None), (1.0, .69, "0.7")])
def test_speed_gate_selects_cell(r, p10, expected):
    assert L.map_cell(inputs(r_k4s=r, p10_k4s=p10))["c_M_k4s"] == expected


def test_p10_and_r_edges_are_inclusive_as_written():
    assert L.map_cell(inputs(r_k4s=.8, p10_k4s=.7))["c_M_k4s"] == "0.8"
    assert L.map_cell(inputs(r_k4s=.8, p10_k4s=.6999999))["c_M_k4s"] == "0.7"
    assert L.map_cell(inputs(r_k4s=.9, p10_k4s=.8))["c_M_k4s"] == "0.9"


def test_inference_coverage_gate_is_c_squared():
    assert L.map_cell(inputs(r_inf=.81))["c_M_k4s"] == "0.9"
    assert L.map_cell(inputs(r_inf=.8))["c_M_k4s"] == "0.8"
    assert L.map_cell(inputs(r_inf=.49))["c_M_k4s"] == "0.7"
    assert L.map_cell(inputs(r_inf=.35))["c_M_k4s"] is None


def test_gate6_failure_moves_down_one_cell_and_rechecks():
    # 0.9 limit = 18/900 + 2/100 = 0.04; 0.8 limit = 0.05 + 0.02 = 0.07.
    mapping = L.map_cell(inputs(mac_deadline=rates(300, 18, 3)))   # 0.06
    assert mapping["provisional_cell"] == "0.9" and mapping["c_M_k4s"] == "0.8"
    assert [t["cell"] for t in mapping["gate6_trail"]] == ["0.9", "0.8"]
    assert mapping["gate6_trail"][0]["gate6"] is False


def test_gate6_exact_margin_edge_passes_and_multiple_steps():
    assert L.map_cell(inputs(mac_deadline=rates(300, 12, 3)))["c_M_k4s"] == "0.9"   # 0.04 == 0.02 + 0.02
    assert L.map_cell(inputs(mac_deadline=rates(300, 13, 3)))["c_M_k4s"] == "0.8"
    deep = L.map_cell(inputs(mac_deadline=rates(300, 3, 66)))                       # 0.22: only 0.6 (0.22)
    assert deep["c_M_k4s"] == "0.6" and [t["cell"] for t in deep["gate6_trail"]] == ["0.9", "0.8", "0.7", "0.6"]
    none = L.map_cell(inputs(mac_deadline=rates(300, 67, 3)))
    assert none["c_M_k4s"] is None and none["mac_infeasible"] and len(none["gate6_trail"]) == 4


def test_gate6_does_not_rescue_a_speed_failure():
    mapping = L.map_cell(inputs(r_k4s=.85, p10_k4s=.8, mac_deadline=rates(300, 3, 60)))   # 0.2 > 0.07
    assert mapping["provisional_cell"] == "0.8" and mapping["c_M_k4s"] == "0.6"


def test_gate0_failure_kills_even_with_perfect_speed():
    i = inputs(gate0=dict(passes=False, parts=dict(sd1_agreement_k4s=False)))
    mapping = L.map_cell(i)
    assert mapping["c_M_k4s"] is None and mapping["provisional_cell"] is None
    kill = L.kill_flags(i, tiers())
    assert kill["k4s_killed_on_mac"] and "gate 0 part failed: sd1_agreement_k4s" in kill["reasons"]


@pytest.mark.parametrize("p99,expected", [(.020, "0.9"), (.0201, None)])
def test_poll_p99_limit_is_inclusive_and_kills(p99, expected):
    i = inputs(poll_p99_seconds=p99)
    assert L.map_cell(i)["c_M_k4s"] == expected
    assert L.kill_flags(i, tiers())["k4s_killed_on_mac"] is (expected is None)


@pytest.mark.parametrize("over", [dict(perception=dict(fps=17.99, processed_fraction=1.)),
                                  dict(perception=dict(fps=20., processed_fraction=.949)),
                                  dict(gc=dict(passes=False))])
def test_cell_independent_gates_make_tier_infeasible(over):
    assert L.map_cell(inputs(**over))["c_M_k4s"] is None


def test_nonfinite_gate_input_fails_closed():
    with pytest.raises(L.GateInputError):
        L.map_cell(inputs(r_k4s=float("nan")))
    with pytest.raises(L.GateInputError):
        L.map_cell(inputs(r_inf=True))


def test_final_cell_uses_tiers_for_1_0_and_c_star_eligibility():
    mapping = L.map_cell(inputs())
    assert L.final_cell(tiers(k4_full=True), mapping, "0.9")["c_M"] == "1.0"
    assert L.final_cell(tiers(k4_full=True), mapping, "0.9")["k4s_eligible_c_M_le_c_star"] is False
    assert L.final_cell(tiers(), mapping, "0.9")["k4s_eligible_c_M_le_c_star"] is True
    assert L.final_cell(tiers(), mapping, "0.8")["k4s_eligible_c_M_le_c_star"] is False
    low = L.map_cell(inputs(r_k4s=.85, p10_k4s=.8))
    assert L.final_cell(tiers(), low, "0.8")["k4s_eligible_c_M_le_c_star"] is True
    assert L.final_cell(tiers(k4_full=True, kind="all-tiers"), mapping, "0.9")["c_M"] is None
    assert L.final_cell(tiers(), None, "0.9")["c_M"] is None
    with pytest.raises(L.GateInputError):
        L.final_cell(tiers(), mapping, "0.7")


def test_kill_flags_for_tiers_exactness_kinds():
    assert L.kill_flags(None, tiers(kind="all-tiers", gate0=False))["all_tiers_infeasible"]
    workers = L.kill_flags(None, tiers(kind="workers-only", gate0=False))
    assert workers["k4s_killed_on_mac"] and not workers["all_tiers_infeasible"]


# ---------------------------------------------------------------- statistics

def test_speed_summary_is_tiers_statistic_with_repeat_medians():
    rows = []
    for i in range(10):
        fleet = .1 + .01 * i
        for wall in (fleet / .9, fleet / 1.1, fleet / 1.0):     # median ratio 1.0 per state
            rows.append(dict(id=str(i), fleet_wall_seconds=fleet, wall_seconds=wall))
    s = L.k4s_speed_summary(rows, [str(i) for i in range(10)])
    assert s["states"] == 10 and s["p50"] == pytest.approx(1.0) and s["p10"] == pytest.approx(1.0)
    assert s["r"] == min(s["p50"], s["sum_ratio"], s["p90_wall_ratio"])
    slow_tail = rows + [dict(id="9", fleet_wall_seconds=.19, wall_seconds=.5)] * 4
    assert L.k4s_speed_summary(slow_tail)["r"] < 1.0
    with pytest.raises(L.GateInputError):
        L.k4s_speed_summary(rows, [str(i) for i in range(11)])


def test_speed_summary_min_of_three_components():
    rows = [dict(id=str(i), fleet_wall_seconds=.1, wall_seconds=.1) for i in range(9)]
    rows.append(dict(id="9", fleet_wall_seconds=1.0, wall_seconds=2.0))      # heavy slow state
    s = L.k4s_speed_summary(rows)
    assert s["p50"] == 1.0 and s["sum_ratio"] == pytest.approx(1.9 / 2.9)
    assert s["r"] == pytest.approx(min(s["sum_ratio"], s["p90_wall_ratio"]))


def test_poll_summary_r_inf_p99_and_cold_exclusion():
    fleet = {str(i): dict(sd1_poll_seconds=.004) for i in range(5)}
    rows = [dict(id="0", poll_seconds=.5, cold=True)]
    rows += [dict(id=str(i), poll_seconds=.005, cold=False) for i in range(5) for _ in range(3)]
    p = L.poll_summary(rows, fleet, [str(i) for i in range(5)])
    assert p["r_inf"] == pytest.approx(.8) and p["p99_seconds"] == pytest.approx(.005) and p["observations"] == 15
    with pytest.raises(L.GateInputError):
        L.poll_summary(rows, {"0": dict(sd1_poll_seconds=.004)})


def test_perception_aggregate_and_agreement_gate():
    agg = L.perception_aggregate([dict(processed=360, expected=400), dict(processed=380, expected=400)], 40.)
    assert agg["fps"] == 18.5 and agg["processed_fraction"] == .925 and agg["passes"] is False
    ok = [dict(equal=True, allowed=True)] * 995 + [dict(equal=False, allowed=True)] * 5
    assert L.sd1_agreement_gate(ok)["passes"] is True
    low = [dict(equal=True, allowed=True)] * 994 + [dict(equal=False, allowed=True)] * 6
    assert L.sd1_agreement_gate(low)["passes"] is False
    bad = [dict(equal=True, allowed=True)] * 999 + [dict(equal=False, allowed=False)]
    assert L.sd1_agreement_gate(bad)["passes"] is False
    assert L.sd1_agreement_gate([])["passes"] is False


def test_deadline_rates_counts():
    rows = [dict(cutoff=i < 3, no_complete_play=i < 2, fallback=False, wall_seconds=.1, over_200_ms=False,
                 cut_return_over_208_ms=False) for i in range(10)]
    r = L.k4s_deadline_rates(rows)
    assert (r["n"], r["cutoff_count"], r["no_complete_play_count"]) == (10, 3, 2)


def test_combine_sessions_takes_minimum_r_and_worst_inputs():
    a = inputs(r_k4s=.95, poll_p99_seconds=.01, mac_deadline=rates(300, 3, 15))
    b = inputs(r_k4s=.86, p10_k4s=.9, poll_p99_seconds=.015, mac_deadline=rates(200, 10, 2))
    worst = L.combine_k4s_sessions([a, b])
    assert worst["r_k4s"] == .86 and worst["poll_p99_seconds"] == .015
    assert (worst["mac_deadline"]["cutoff_count"], worst["mac_deadline"]["cutoff_n"]) == (10, 200)
    assert (worst["mac_deadline"]["no_complete_play_count"], worst["mac_deadline"]["no_complete_play_n"]) == (15, 300)
    assert L.map_cell(worst)["c_M_k4s"] == "0.8"
    with pytest.raises(L.GateInputError):
        L.combine_k4s_sessions([a, inputs(fleet_deadline=dict(FLEET, **{"0.9": rates(900, 1, 1)}))])
    assert L.combine_k4s_sessions([a, inputs(gate0=dict(passes=False, parts={}))])["gate0"]["passes"] is False


# ---------------------------------------------------------------- TIERS receipts (read only)

@pytest.mark.parametrize("error,kind", [
    ("ValueError: Exactness mismatch: g1/1=4", "workers-only"),
    ("ValueError: Exactness mismatch: g1/1=2", "workers-only"),
    ("ValueError: Exactness mismatch: g1/K4/scores", "all-tiers"),
    ("ValueError: Exactness mismatch: belief/posterior/ledger/sampling/RNG/g1/posterior", "all-tiers"),
    ("ValueError: Zero-budget root mutated", "all-tiers"),
    ("RuntimeError: Replay worker failed", None), ("", None)])
def test_tiers_exactness_failure_kind(error, kind):
    assert L.exactness_failure_kind(error) == kind


def test_read_complete_tiers_session_and_reuse_inputs(tmp_path):
    d, digest = make_tiers_session(tmp_path / "tiers")
    s = read_session(d, digest, require_mac=False, classify=no_classify)
    assert s["state"] == "complete"
    t = L.tiers_inputs([s], GOLDEN)
    assert t["gate0"]["passes"] is True and t["k4_cell_1_0"] is True and t["exactness_failure_kind"] is None
    d2, digest2 = make_tiers_session(tmp_path / "tiers08", cell=.8)
    assert L.tiers_inputs([read_session(d2, digest2, require_mac=False)], GOLDEN)["k4_cell_1_0"] is False


def test_tiers_session_refusals(tmp_path):
    d, digest = make_tiers_session(tmp_path / "tiers")
    with pytest.raises(L.PreconditionRefusal, match="SHA mismatch"):
        read_session(d, "0" * 64, require_mac=False)
    with pytest.raises(L.PreconditionRefusal, match="not an authorized Mac session"):
        read_session(d, digest, require_mac=True)
    with pytest.raises(L.PreconditionRefusal, match="technically invalid"):
        read_session(d, digest, require_mac=False, classify=lambda _: dict(technical_repeat_candidate=True))
    h, hd = make_tiers_session(tmp_path / "harness", state="harness")
    with pytest.raises(L.PreconditionRefusal, match="not complete"):
        read_session(h, hd, require_mac=False)
    (d / "tiers-summary.json").write_text("{}\n")
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch"):
        read_session(d, digest, require_mac=False)


def test_tiers_exactness_termination_is_gate0_failure(tmp_path):
    d, digest = make_tiers_session(tmp_path / "t", state="exactness")
    t = L.tiers_inputs([read_session(d, digest, require_mac=False)], GOLDEN)
    assert t["gate0"]["passes"] is False and t["exactness_failure_kind"] == "workers-only" and not t["k4_cell_1_0"]


def test_tiers_multi_session_uses_worst_inputs(tmp_path):
    a = read_session(*make_tiers_session(tmp_path / "a", measured_cut=.03), require_mac=False)
    b = read_session(*make_tiers_session(tmp_path / "b", measured_cut=.041, r=1.2), require_mac=False)
    assert L.tiers_inputs([a], GOLDEN)["k4_cell_1_0"] is True
    assert L.tiers_inputs([a, b], GOLDEN)["k4_cell_1_0"] is False      # worst cutoff .041 > .02 + .02
    c = read_session(*make_tiers_session(tmp_path / "c", r=.99, cell=.8), require_mac=False)
    assert L.tiers_inputs([a, c], GOLDEN)["k4_cell_1_0"] is False


def test_in_session_ordering_lock_and_gap(tmp_path):
    lock = tmp_path / "lock"
    s = read_session(*make_tiers_session(tmp_path / "t", lock_path=lock, utc=1000.), require_mac=False)
    assert L.check_in_session(s, lock, 1000. + 600)["passes"]
    with pytest.raises(L.PreconditionRefusal, match="2 h"):
        L.check_in_session(s, lock, 1000. + 3 * 3600)
    with pytest.raises(L.PreconditionRefusal, match="not before"):
        L.check_in_session(s, lock, 999.)
    with pytest.raises(L.PreconditionRefusal, match="same coordinator lock"):
        L.check_in_session(s, tmp_path / "other", 1000. + 600)


def test_same_mac_identity():
    ident = dict(host="m", machine="arm64", platform="Darwin", sysctl=dict(stdout="\n".join(
        "%s: %s" % (k, v) for k, v in (("hw.model", "Mac14,3"), ("machdep.cpu.brand_string", "Apple M2"),
                                       ("hw.memsize", "17179869184"), ("hw.perflevel0.physicalcpu", "4"),
                                       ("hw.perflevel1.physicalcpu", "4"), ("hw.perflevel0.logicalcpu", "4"),
                                       ("hw.perflevel1.logicalcpu", "4")))))
    assert L.same_mac(ident, ident)["passes"]
    other = dict(ident, sysctl=dict(stdout=ident["sysctl"]["stdout"].replace("Mac14,3", "Mac15,1")))
    assert L.same_mac(ident, other)["mismatches"] == ["hw.model"]


# ---------------------------------------------------------------- binding, pins, load

def test_scorer_binding_accepts_declared_anchor_x_derivative_only(tmp_path):
    root = L.REPO_ROOT
    pins = {L.TIERS_SCORER_REL: L.sha(root / L.TIERS_SCORER_REL),
            L.TIERS_SCORER_BASE_REL: L.sha(root / L.TIERS_SCORER_BASE_REL)}
    build = dict(native_sha256="n" * 64, source_manifest_sha256="m" * 64, target="aarch64-apple-darwin", locked=True)
    common = dict(tiers_runtime_files=pins, runtime_root=root, native_sha256="n" * 64, tiers_build=build,
                  tiers_pins_sha256="m" * 64, dry_run=False)
    assert L.bind_scorer_and_native(k4s_scorer_rel="reports/explore/k4s-confirm/anchor_x.py", **common)["passes"]
    assert L.bind_scorer_and_native(k4s_scorer_rel=L.TIERS_SCORER_REL, **common)["passes"]
    assert not L.bind_scorer_and_native(k4s_scorer_rel="reports/explore/k4s-confirm/anchor_x.py",
                                        **dict(common, native_sha256="x" * 64))["passes"]
    assert not L.bind_scorer_and_native(k4s_scorer_rel="reports/explore/k4s-confirm/anchor_x.py",
                                        **dict(common, tiers_pins_sha256="z" * 64))["passes"]
    tampered = (root / "reports/explore/k4s-confirm/anchor_x.py").read_bytes().replace(b"score += value", b"score -= value")
    assert L.sha_bytes(L.scorer_normal_form(tampered)) != pins[L.TIERS_SCORER_REL]
    nested = L.bind_scorer_and_native(k4s_scorer_rel="reports/explore/k4s-confirm/mac/k4s_logic.py", **common)
    assert not nested["passes"] and "reports/explore/<dir>/" in nested["reasons"][0]


def test_select_load_is_tiers_bundle_profile():
    bundle = dict(load=dict(kind="v3-body-hud-only", label="PROVISIONAL-LOAD", target_fps=20,
                            config=dict(device="mps"), matches=["m"], split="s"))
    load = L.select_load(bundle, dict(load_label="PROVISIONAL-LOAD"), dry_run=False)
    assert load["nice"] == 10 and load["qos"] == "inherited" and "PROVISIONAL-LOAD" in load["labels"]
    with pytest.raises(L.PreconditionRefusal):
        L.select_load(bundle, dict(load_label="OTHER"), dry_run=False)
    cpu = dict(load=dict(bundle["load"], config=dict(device="cpu")))
    with pytest.raises(L.PreconditionRefusal, match="MPS"):
        L.select_load(cpu, dict(load_label="PROVISIONAL-LOAD"), dry_run=False)
    assert L.select_load(cpu, dict(load_label="PROVISIONAL-LOAD"), dry_run=True)["nice"] == 19
    with pytest.raises(L.PreconditionRefusal):
        L.check_priority_and_threads(0, dict(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1"),
                                     dry_run=False)


def test_corpus_and_fleet_reference_checks():
    root = L.REPO_ROOT / "reports/explore/t1/corpora/corpus-03-a51ea64c"
    inventory = json.loads((root / "corpora.json").read_text())
    publication = json.loads((root / "publication.json").read_text())
    ids = L.check_corpus(L.T1_K4_CORPUS_SHA, L.T1_K4_CORPUS_SHA, inventory, publication, None)
    assert len(ids) == 300 and ids[0].startswith("K4-200/")
    with pytest.raises(L.PreconditionRefusal):
        L.check_corpus("0" * 64, L.T1_K4_CORPUS_SHA, inventory, publication, None)
    with pytest.raises(L.PreconditionRefusal):
        L.check_corpus("0" * 64, "0" * 64, inventory, publication, None)
    with pytest.raises(L.PreconditionRefusal):
        L.check_corpus(L.T1_K4_CORPUS_SHA, L.T1_K4_CORPUS_SHA, inventory, publication, ids[:-1] + ["x"])
    states = {i: dict(k4s_wall_seconds=.1, sd1_poll_seconds=.004, result=dict(action=1, candidates=[1], scores=[0.]))
              for i in ids}
    deadline = {c: dict(FLEET[c], budget_ms=L.BUDGET_MS[c], charge_scale=L.charge_scale_text(c)) for c in FLEET}
    ref = dict(schema=L.FLEET_REFERENCE_SCHEMA, corpus_sha256=L.T1_K4_CORPUS_SHA, repeats=3, hosts=["127x01"],
               reporting_load_profile=True, pool_conforms=True, states=states, deadline=deadline)
    assert L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, ids, dry_run=True)["states"] == 300
    # Mac mode never accepts a reference without pooled provenance and its re-check (full chain: test_end_reference).
    with pytest.raises(L.PreconditionRefusal, match="provenance"):
        L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, ids, dry_run=False, reference_sha256="e" * 64,
                                recheck=dict(passes=True), expected_pins={}, end_pool_sha256="f" * 64)
    bad = json.loads(json.dumps(ref))
    bad["deadline"]["0.8"]["cutoff"] = .5
    with pytest.raises(L.PreconditionRefusal, match="disagrees"):
        L.check_fleet_reference(bad, L.T1_K4_CORPUS_SHA, ids, dry_run=True)
    old_names = json.loads(json.dumps(ref))
    for cell in old_names["deadline"].values():
        cell["cutoff_rate"] = cell.pop("cutoff")
    with pytest.raises(L.PreconditionRefusal, match="disagrees"):
        L.check_fleet_reference(old_names, L.T1_K4_CORPUS_SHA, ids, dry_run=True)


# ---------------------------------------------------------------- SD1 manifest (finding 1)

SD1_PATH = L.REPO_ROOT / "reports/explore/k4s-confirm/SD1-MANIFEST.json"


def sd1_runtime(tmp_path, network=b"synthetic network bytes\n"):
    """A runtime root holding the shipped SD1 inference sources (network.py is not in this worktree)."""
    root = tmp_path / "runtime"
    for rel in L.SD1_SOURCES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        source = L.REPO_ROOT / rel
        target.write_bytes(source.read_bytes() if source.is_file() else network)
    return root


def test_sd1_validator_reads_the_shipped_manifest_schema(tmp_path):
    shipped = json.loads(SD1_PATH.read_text())
    assert shipped["schema"] == L.SD1_SCHEMA and set(shipped["inference_sources"]) == set(L.SD1_SOURCES)
    root = sd1_runtime(tmp_path)
    # Every shipped source but network.py verifies; the complete map is checked, so the fake network fails.
    with pytest.raises(L.PreconditionRefusal, match="student-source/exit_r3/network.py"):
        L.check_sd1_manifest(SD1_PATH, L.sha(SD1_PATH), root, L.SD1_CHECKPOINT_SHA, L.SD1_CALIBRATION_SHA)
    # The same shipped manifest with only network.py's hash matching this runtime passes every other field.
    copy = dict(shipped, inference_sources=dict(shipped["inference_sources"], **{
        "student-source/exit_r3/network.py": L.sha(root / "student-source/exit_r3/network.py")}))
    path = tmp_path / "SD1.json"
    path.write_text(json.dumps(copy, indent=2) + "\n")
    assert L.check_sd1_manifest(path, L.sha(path), root, L.SD1_CHECKPOINT_SHA, L.SD1_CALIBRATION_SHA)["threshold"] == L.SD1_THRESHOLD
    for mutate, message in (
            (lambda m: m["checkpoint"].update(sha256="0" * 64), "R3a bytes"),
            (lambda m: m["calibration"].update(job_path="inputs/other.json"), "R3a bytes"),
            (lambda m: m.update(threshold=0.5), "threshold"),
            (lambda m: m["inference_sources"].pop("imitation/model/inference.py"), "inference_sources"),
            (lambda m: m["inference_sources"].update({"reports/explore/e1/policy.py": "0" * 64}), "Pin mismatch"),
            (lambda m: m["inference_mode"].update(torch_threads=2), "inference mode"),
            (lambda m: m.update(schema="other"), "schema")):
        forged = json.loads(json.dumps(copy))
        mutate(forged)
        other = tmp_path / "forged.json"
        other.write_text(json.dumps(forged))
        with pytest.raises(L.PreconditionRefusal, match=message):
            L.check_sd1_manifest(other, L.sha(other), root, L.SD1_CHECKPOINT_SHA, L.SD1_CALIBRATION_SHA)
    with pytest.raises(L.PreconditionRefusal, match="SD1's bytes"):
        L.check_sd1_manifest(path, L.sha(path), root, "0" * 64, L.SD1_CALIBRATION_SHA)
    with pytest.raises(L.PreconditionRefusal, match="SHA mismatch"):
        L.check_sd1_manifest(path, L.sha(SD1_PATH), root, L.SD1_CHECKPOINT_SHA, L.SD1_CALIBRATION_SHA)


def test_sd1_frozen_identity_matches_sd1_manifest_module():
    sys.path.insert(0, str(L.REPO_ROOT / "reports/explore/k4s-confirm"))
    import sd1_manifest
    assert tuple(sd1_manifest.SOURCES) == L.SD1_SOURCES and sd1_manifest.MODE == L.SD1_INFERENCE_MODE
    shipped = json.loads(SD1_PATH.read_text())
    assert shipped["checkpoint"]["sha256"] == L.SD1_CHECKPOINT_SHA and shipped["threshold"] == L.SD1_THRESHOLD


# ---------------------------------------------------------------- committed TIERS receipts (finding 7)

def test_tiers_receipts_must_be_committed_ancestors_with_equal_blobs(tmp_path):
    d, digest = make_tiers_session(tmp_path / "tiers")
    assert read_session(d, digest, require_mac=False)["committed"]["files"] == len(json.loads(
        (d / "receipt-manifest.json").read_text())["files"]) + 2
    with pytest.raises(L.PreconditionRefusal, match="from a commit"):
        L.read_tiers_session(d, digest, require_mac=False)
    with pytest.raises(L.PreconditionRefusal, match="full 40-hex"):
        L.read_tiers_session(d, digest, require_mac=False, committed=dict(committed(d), commit="abc"))
    # A commit on a side branch is not admissible.
    git(tmp_path, "checkout", "-q", "-b", "side")
    (tmp_path / "note").write_text("x")
    git(tmp_path, "add", "note")
    git(tmp_path, "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-q", "-m", "side")
    side = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "-q", "-")
    with pytest.raises(L.PreconditionRefusal, match="ancestor"):
        L.read_tiers_session(d, digest, require_mac=False, committed=dict(committed(d), commit=side))
    # A locally revised, re-sealed verdict does not match the committed blobs.
    revised = tmp_path / "revised"
    store = L.K4SStore(revised / "tiers", "LINUX-DRY-RUN:PROVISIONAL-LOAD")
    for name in json.loads((d / "receipt-manifest.json").read_text())["files"]:
        value = json.loads((d / name).read_text())
        value.pop("scope")
        if name == "tiers-summary.json":
            value["feasibility"]["K4"]["cell"] = 1.0
            value["exactness_class"] = "ARM64-NEAR-EXACT"
        store.write(name, value)
    store.seal("complete")
    resealed = L.sha(revised / "tiers" / "receipt-manifest.json")
    with pytest.raises(L.PreconditionRefusal, match="committed blob|inventory"):
        L.read_tiers_session(revised / "tiers", resealed, require_mac=False,
                             committed=dict(committed(d)))
    # An extra committed file means the committed inventory is not the sealed one.
    (d / "extra.json").write_text("{}\n")
    git(tmp_path, "add", "--", "tiers/extra.json")
    git(tmp_path, "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-q", "-m", "extra")
    with pytest.raises(L.PreconditionRefusal, match="inventory"):
        L.read_tiers_session(d, digest, require_mac=False, committed=dict(committed(d), commit=git(tmp_path, "rev-parse", "HEAD")))


def test_cli_refuses_uncommitted_tiers_receipts(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers", state="exactness")
    out = tmp_path / "k"
    assert M.main(dry_argv(out, "--tiers-receipts", str(tiers_dir), "--tiers-receipt-sha256", digest), **offline) == 3
    assert "commit" in json.loads((out / "refusal.json").read_text())["error"]


def test_output_isolation_from_tiers_paths(tmp_path):
    tiers_dir = tmp_path / "tiers"
    tiers_dir.mkdir()
    forbidden = L.forbidden_roots(L.REPO_ROOT, [tiers_dir], None)
    for bad in (L.REPO_ROOT / L.E4V3_REL / "k4s-out", tiers_dir, tiers_dir / "k4s", tmp_path,
                L.REPO_ROOT / "reports/explore/t1/k4s"):
        with pytest.raises(L.PreconditionRefusal):
            L.check_output_isolated(bad, forbidden)
    assert L.check_output_isolated(tmp_path / "k4s-out", forbidden)


def test_repeat_admission_rules():
    tech = dict(technical_repeat_candidate=True, counts_toward_repeat_allowance=True, receipt_sha256="a" * 64)
    tiers_invalid = dict(technical_repeat_candidate=True, counts_toward_repeat_allowance=False, receipt_sha256="b" * 64)
    assert L.check_repeat_admission([], released=False, review=None)["attempt"] == 1
    assert L.check_repeat_admission([tech, tiers_invalid], released=False, review=None)["counted_repeats"] == 1
    with pytest.raises(L.PreconditionRefusal, match="exhausted"):
        L.check_repeat_admission([tech, dict(tech, receipt_sha256="c" * 64)], released=False, review=None)
    with pytest.raises(L.PreconditionRefusal, match="not a pre-listed"):
        L.check_repeat_admission([dict(technical_repeat_candidate=False, receipt_sha256="d" * 64)], released=False, review=None)
    with pytest.raises(L.PreconditionRefusal, match="independent"):
        L.check_repeat_admission([tech], released=True, review=None)
    review = dict(schema="clasher.k4s.mac-classification-review.v1", independent_of_author=True,
                  confirmed_classification_sha256=["a" * 64], confirms_session_validity_rule=True)
    assert L.check_repeat_admission([tech], released=True, review=review)["released"]
    with pytest.raises(L.PreconditionRefusal, match="every prior"):
        L.check_repeat_admission([tech], released=True, review=dict(review, confirmed_classification_sha256=[]))


def test_standalone_authorization(tmp_path):
    with pytest.raises(L.PreconditionRefusal):
        L.check_standalone_authorization(None, None, [])
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps(dict(schema="clasher.k4s.mac-standalone-authorization.v1", coordinator="0523ae6f",
                                    sam_authorized_session=True, utc="2026-10-12T00:00Z",
                                    tiers_receipt_manifest_sha256=["a" * 64])))
    assert L.check_standalone_authorization(auth, L.sha(auth), ["a" * 64])["descriptive_only"] is False
    with pytest.raises(L.PreconditionRefusal, match="different TIERS"):
        L.check_standalone_authorization(auth, L.sha(auth), ["b" * 64])
    with pytest.raises(L.PreconditionRefusal):
        L.check_standalone_authorization(auth, "0" * 64, ["a" * 64])


def test_provisional_labels():
    assert L.provisional_status(False, False, False) == dict(provisional=True, label="PROVISIONAL (emulator-off)")
    assert L.provisional_status(True, True, False)["provisional"] is True
    assert L.provisional_status(True, True, True)["provisional"] is False
    assert L.emulator_present("  1 /sbin/launchd\n 99 /opt/sdk/qemu-system-aarch64\n")
    assert not L.emulator_present("  1 /sbin/launchd\n")


# ---------------------------------------------------------------- manifest

def test_manifest_is_current_and_measure_tiers_unmodified():
    on_disk = json.loads((L.MAC_DIR / L.MANIFEST_NAME).read_text())
    assert on_disk == B.build(L.REPO_ROOT, list(on_disk["k4s_kernel"]["files"]), on_disk["frozen"])
    path = on_disk["measure_tiers_unmodified"]["path"]
    committed = subprocess.run(["git", "-C", str(L.REPO_ROOT), "show", "HEAD:" + path], capture_output=True, check=True).stdout
    assert L.sha_bytes(committed) == on_disk["measure_tiers_unmodified"]["sha256"] == L.sha(L.REPO_ROOT / path)
    for rel, digest in on_disk["reused_readonly"].items():
        blob = subprocess.run(["git", "-C", str(L.REPO_ROOT), "show", "HEAD:" + rel], capture_output=True, check=True).stdout
        assert L.sha_bytes(blob) == digest, rel
    assert on_disk["native"]["provenance_linux_sha256"] == L.NATIVE_PROVENANCE_SHA
    assert all(p.startswith(L.MAC_REL + "/") for p in on_disk["k4s_files"])


def test_manifest_loader_rejects_draft_for_mac_and_tamper(tmp_path):
    path = L.MAC_DIR / L.MANIFEST_NAME
    manifest = L.load_k4s_manifest(path, L.sha(path), L.REPO_ROOT, require_frozen=False)
    assert manifest["frozen"] is False
    with pytest.raises(L.PreconditionRefusal, match="frozen"):
        L.load_k4s_manifest(path, L.sha(path), L.REPO_ROOT, require_frozen=True)
    with pytest.raises(L.PreconditionRefusal, match="SHA mismatch"):
        L.load_k4s_manifest(path, "0" * 64, L.REPO_ROOT, require_frozen=False)
    forged = json.loads(path.read_text())
    forged["reused_readonly"][L.E4V3_REL + "/measure_tiers.py"] = "0" * 64
    other = tmp_path / "m.json"
    other.write_text(json.dumps(forged))
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch"):
        L.load_k4s_manifest(other, L.sha(other), L.REPO_ROOT, require_frozen=False)


# ---------------------------------------------------------------- CLI preconditions (no Mac, no TIERS writes)

def dry_argv(out, *extra):
    path = L.MAC_DIR / L.MANIFEST_NAME
    return ["--output", str(out), "--linux-dry-run", "--k4s-manifest", str(path),
            "--k4s-manifest-sha256", L.sha(path), *extra]


ENV = dict(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(M, "admit_platform", lambda args: None)
    return dict(environ=ENV, nice=19, classify=no_classify)


def sealed(out):
    manifest = json.loads((out / "receipt-manifest.json").read_text())
    return manifest["status"], manifest["files"]


def test_cli_refuses_without_tiers_completion_receipt(tmp_path, offline):
    before = tree_state(L.REPO_ROOT / L.TIERS_PACKAGE_REL)
    out = tmp_path / "k4s"
    assert M.main(dry_argv(out), **offline) == 3
    status, files = sealed(out)
    refusal = json.loads((out / "refusal.json").read_text())
    assert status == "refused" and "refusal.json" in files and "TIERS session-completion receipt" in refusal["error"]
    assert refusal["repeat_consumed"] is False and "k4s-mac-summary.json" not in files
    assert tree_state(L.REPO_ROOT / L.TIERS_PACKAGE_REL) == before


def test_cli_refuses_output_inside_tiers_paths(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers")
    before = tree_state(tiers_dir)
    for out in (tiers_dir / "k4s", L.REPO_ROOT / L.E4V3_REL / "receipts" / "k4s-test-never"):
        assert M.main(dry_argv(out, *tiers_args(tiers_dir, digest)), **offline) == 3
        assert not out.exists()
    assert tree_state(tiers_dir) == before


def test_cli_refuses_bad_tiers_sha_and_standalone_without_authorization(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers")
    assert M.main(dry_argv(tmp_path / "a", *tiers_args(tiers_dir, "0" * 64)),
                  **offline) == 3
    assert "SHA mismatch" in json.loads((tmp_path / "a" / "refusal.json").read_text())["error"]
    assert M.main(dry_argv(tmp_path / "b", "--standalone"), **offline) == 3
    assert "authorization" in json.loads((tmp_path / "b" / "refusal.json").read_text())["error"]
    assert M.main(dry_argv(tmp_path / "c", "--tiers-receipts", str(tiers_dir)), **offline) == 3


def test_cli_refuses_incomplete_tiers_session(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers", state="harness")
    assert M.main(dry_argv(tmp_path / "k", *tiers_args(tiers_dir, digest)),
                  **offline) == 3
    assert "not complete" in json.loads((tmp_path / "k" / "refusal.json").read_text())["error"]


def test_cli_refuses_technically_invalid_tiers_session(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers")
    hooks = dict(offline, classify=lambda _: dict(technical_repeat_candidate=True, reasons=["x"]))
    assert M.main(dry_argv(tmp_path / "k", *tiers_args(tiers_dir, digest)),
                  **hooks) == 3


def test_cli_tiers_exactness_failure_writes_no_measurement_summary(tmp_path, offline):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers", state="exactness")
    before = tree_state(tiers_dir)
    out = tmp_path / "k4s"
    assert M.main(dry_argv(out, *tiers_args(tiers_dir, digest)), **offline) == 0
    status, files = sealed(out)
    summary = json.loads((out / "k4s-mac-summary.json").read_text())
    assert status == "complete" and summary["c_M"] is None and summary["measurements"] == dict(measured=False)
    assert summary["kill"]["k4s_killed_on_mac"] and summary["tiers_inputs"]["exactness_failure_kind"] == "workers-only"
    assert summary["dry_run"] is True and summary["provisional"] is True
    assert tree_state(tiers_dir) == before
    classification = C.classify(out, tiers_dir, digest, tiers_classify=no_classify)
    # The committed TIERS §7.2 failure is a recorded gate-0 failure: a valid, no-repeat gate-failure session.
    assert classification["category"] == "gate-failure" and classification["valid"] is True
    assert classification["technical_repeat_candidate"] is False and classification["tiers_classification_untouched"]
    assert classification["gate0_evidence"] == [
        "k4s-mac-summary.json gate 0: tiers_exactness_and_worker_equality",
        "k4s-preconditions.json committed TIERS gate 0: tiers_exactness_and_worker_equality"]


def test_cli_rejects_mac_authorization_with_dry_run(tmp_path, offline):
    assert M.main(dry_argv(tmp_path / "k", "--sam-authorized-replay"), **offline) == 3


def test_admit_platform_restrictions():
    mac = SimpleNamespace(linux_dry_run=False, sam_authorized_replay=True)
    M.admit_platform(mac, system="Darwin", machine="arm64", host="mini")
    with pytest.raises(L.PreconditionRefusal):
        M.admit_platform(SimpleNamespace(linux_dry_run=False, sam_authorized_replay=False),
                         system="Darwin", machine="arm64", host="mini")
    with pytest.raises(L.PreconditionRefusal):
        M.admit_platform(mac, system="Linux", machine="x86_64", host="127x03")
    with pytest.raises(L.PreconditionRefusal):
        M.admit_platform(SimpleNamespace(linux_dry_run=True, sam_authorized_replay=False),
                         system="Linux", machine="x86_64", host="127x09")


def test_measure_module_imports_without_torch():
    code = ("import sys; sys.path.insert(0, %r); import measure_k4s, classify_k4s_failure; "
            "assert 'torch' not in sys.modules and 'tier_backend' not in sys.modules") % str(L.MAC_DIR)
    subprocess.run([sys.executable, "-B", "-c", code], check=True)


# ---------------------------------------------------------------- measurement loops with a fake backend

class FakeBackend:
    def __init__(self, ids, wall=.1, poll=.005, mismatch=None):
        self.k4s_rows = {i: dict(id=i) for i in ids}
        self.wall, self.poll, self.mismatch, self.calls = wall, poll, mismatch, 0
        self.prepared = []

    def k4s_work(self, row, deadline=None, packet_entry=None):
        self.calls += 1
        action = 9 if row["id"] == self.mismatch else 1
        timing = dict(wall_seconds=self.wall, poll_seconds=self.poll, cold_poll=self.calls == 1,
                      cutoff=deadline is not None and row["id"] < "2", fallback=False,
                      no_complete_play=deadline is not None and row["id"] < "1", over_200_ms=False,
                      cut_return_over_208_ms=False, coarse_order=[1])
        return dict(action=action, candidates=[1], scores=[0.]), timing

    def prepare_work(self, row):
        self.prepared.append(row["id"])

    def infer(self, identity, device):
        return dict(gate=.9, legal=[1], ranks={1: 1.}), .001


class ListStore:
    def __init__(self):
        self.rows = {}

    def append(self, name, value):
        self.rows.setdefault(name, []).append(value)

    def write(self, name, value):
        self.rows[name] = value


def exact(actual, expected, label):
    if actual != expected:
        raise ValueError("Exactness mismatch: " + label)
    return 0.


def test_measurement_loops_with_fake_backend():
    ids = [str(i) for i in range(5)]
    fleet = {i: dict(k4s_wall_seconds=.09, sd1_poll_seconds=.004, result=dict(action=1, candidates=[1], scores=[0.]))
             for i in ids}
    limits = dict(L.DRY_LIMITS, speed=5, speed_seconds=0, agreement=3)
    store = ListStore()
    m = M.Measurements(FakeBackend(ids), store, limits, ids, fleet, window=lambda a, b: dict(processed=20, expected=20))
    assert m.corpus_exactness(exact) == dict(passes=True, states=5, exactness_class="EXACT")
    m.loaded_speed()
    speed = L.k4s_speed_summary(m.speed_rows, ids)
    assert speed["r"] == pytest.approx(.9) and len(m.spans) == 1
    poll = L.poll_summary(m.poll_rows, fleet, ids)
    assert poll["r_inf"] == pytest.approx(.8)
    r = m.deadline_corpus()
    assert (r["n"], r["cutoff_count"], r["no_complete_play_count"]) == (5, 2, 1)
    refs = {i: dict(gate=.9, legal=[1], ranks={"1": 1.}) for i in ids}
    agree = m.sd1_agreement(ids, refs, L.SD1_THRESHOLD,
                            lambda ref, act, thr: dict(equal=ref["ranks"] == act["ranks"], allowed=True))
    assert agree["passes"] and agree["n"] == 3
    bad = M.Measurements(FakeBackend(ids, mismatch="3"), ListStore(), limits, ids, fleet)
    result = bad.corpus_exactness(exact)
    assert result["passes"] is False and result["failed_state"] == "3"

    class RootMismatch(FakeBackend):
        def k4s_work(self, row, deadline=None, packet_entry=None):
            if row["id"] == "2":
                raise ValueError("Exactness mismatch: complete decision public root")
            return super().k4s_work(row, deadline, packet_entry)
    assert M.Measurements(RootMismatch(ids), ListStore(), limits, ids, fleet).corpus_exactness(exact)["failed_state"] == "2"

    class Crash(FakeBackend):
        def k4s_work(self, row, deadline=None, packet_entry=None):
            raise ValueError("Native module crashed")
    with pytest.raises(ValueError, match="crashed"):
        M.Measurements(Crash(ids), ListStore(), limits, ids, fleet).corpus_exactness(exact)


def test_summarize_records_every_gate_input():
    ctx = dict(tiers=tiers(), c_star="0.9", dry_run=True, mode="in-session", k4s_manifest_sha256="a" * 64)
    i = inputs()
    body = M.summarize(ctx, inputs=i, mapping=L.map_cell(i), extra={}, provisional=L.provisional_status(False, False, False))
    for key in ("gate0", "r_k4s", "p10_k4s", "r_inf", "poll_p99_seconds", "perception", "gc", "mac_deadline", "fleet_deadline"):
        assert key in body["gate_inputs"]
    assert body["c_M"] == "0.9" and body["dry_run"] is True and body["provisional_label"] == "PROVISIONAL (emulator-off)"
    assert body["mac_qualified"] is False and body["live_actions"] is False


# ---------------------------------------------------------------- classifier

@pytest.mark.parametrize("kwargs,category", [
    (dict(refusal=dict(error="no receipt"), status="refused"), "precondition-refusal"),
    (dict(refusal=dict(error="no receipt"), status="complete"), "technical-failure"),
    (dict(complete=dict(completed=True), status="failed"), "technical-failure"),
    (dict(complete=dict(completed=True), cleanup_error="Traceback (most recent call last):\nRuntimeError: x"),
     "technical-failure"),
    (dict(failure_error="Traceback (most recent call last):\nValueError: Exactness mismatch: x"), "gate-failure"),
    (dict(failure_error="Traceback (most recent call last):\nRuntimeError: Replay worker failed"), "technical-failure"),
    (dict(failure_error="ValueError: Pin mismatch (x): y"), "technical-failure"),
    (dict(complete=dict(completed=True), capacity_rows=[dict(phase="K3", processes=[dict(foreign_over_one_core_seconds=61)])]),
     "technical-failure"),
    (dict(complete=dict(completed=True), capacity_rows=[dict(phase="K1", processes=[],
                                                              thermal=dict(stdout="CPU_Speed_Limit = 80"))]), "technical-failure"),
    (dict(complete=dict(completed=True), capacity_rows=[dict(phase="K3", processes=[],
                                                              thermal=dict(stdout="CPU_Speed_Limit = 80"))]), "valid"),
    (dict(complete=dict(completed=True), capacity_rows=[dict(phase="K3", processes=[], boottime=dict(stdout="a")),
                                                        dict(phase="K3", processes=[], boottime=dict(stdout="b"))]),
     "technical-failure"),
    (dict(complete=dict(completed=True)), "valid"),
    (dict(), "technical-failure"),
    (dict(complete=dict(completed=True), tiers_classification=dict(technical_repeat_candidate=True, reasons=["r"])),
     "invalid-tiers-session"),
])
def test_classifier_categories(kwargs, category):
    result = C.classify_records(**kwargs)
    assert result["category"] == category
    assert result["technical_repeat_candidate"] is (category in ("technical-failure", "invalid-tiers-session"))
    assert result["counts_toward_repeat_allowance"] is (category == "technical-failure")


def test_classifier_cli_reads_only_and_writes_fresh_dir(tmp_path):
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers")
    session = L.K4SStore(tmp_path / "k4s", "K4S-LINUX-DRY-RUN")
    session.write("k4s-preconditions.json", dict(tiers=dict(sessions=[dict(receipt_manifest_sha256=digest)])))
    session.write("k4s-complete.json", dict(completed=True))
    session.seal("complete")
    before = tree_state(tiers_dir), tree_state(tmp_path / "k4s")
    assert C.classify(tmp_path / "k4s")["category"] == "valid"
    invalid = C.classify(tmp_path / "k4s", tiers_dir, digest,
                         tiers_classify=lambda _: dict(technical_repeat_candidate=True, reasons=["foreign"]))
    assert invalid["category"] == "invalid-tiers-session" and invalid["valid"] is False
    with pytest.raises(L.PreconditionRefusal):
        C.classify(tmp_path / "k4s", tiers_dir, "0" * 64, tiers_classify=no_classify)
    with pytest.raises(L.PreconditionRefusal):
        C.main(["classify", "--receipts", str(tmp_path / "k4s"), "--output", str(tmp_path / "k4s" / "c")])
    with pytest.raises(L.PreconditionRefusal):
        C.main(["classify", "--receipts", str(tmp_path / "k4s"), "--output", str(tiers_dir / "c"),
                "--tiers-receipts", str(tiers_dir), "--tiers-receipt-sha256", digest])
    assert C.main(["classify", "--receipts", str(tmp_path / "k4s"), "--output", str(tmp_path / "cls")]) == 0
    assert (tree_state(tiers_dir), tree_state(tmp_path / "k4s")) == before


def test_reduce_sessions_minimum_across_valid_sessions_only():
    t = tiers()
    valid = dict(category="valid", valid=True)
    s1 = dict(tiers_inputs=t, gate_inputs=inputs(r_k4s=.95), provisional=True)
    s2 = dict(tiers_inputs=t, gate_inputs=inputs(r_k4s=.84, p10_k4s=.8), provisional=True)
    s3 = dict(tiers_inputs=t, gate_inputs=inputs(r_k4s=.5), provisional=True)
    final = C.reduce_sessions([(s1, valid), (s2, valid), (s3, dict(category="technical-failure", valid=False))], "0.9")
    assert final["valid_sessions"] == 2 and final["gate_inputs"]["r_k4s"] == .84 and final["c_M"] == "0.8"
    gate_fail = dict(tiers_inputs=t, gate_inputs=dict(gate0=dict(passes=False, parts=dict(k4s_corpus_exactness=False)),
                                                      r_k4s=None), provisional=True)
    assert C.reduce_sessions([(s1, valid), (gate_fail, dict(category="gate-failure", valid=True))], "0.9")["c_M"] is None
    stopped = C.gate_failure_summary(t)
    assert C.reduce_sessions([(s1, valid), (stopped, dict(category="gate-failure", valid=True))], "0.9")["c_M"] is None
    with pytest.raises(L.GateInputError):
        C.reduce_sessions([(s3, dict(valid=False))], "0.9")
    with pytest.raises(L.GateInputError):
        C.reduce_sessions([(s1, valid), (dict(s2, tiers_inputs=tiers(k4_full=True)), valid)], "0.9")


# ---------------------------------------------------------------- sealed reduction inputs (finding 8)

def sealed_session(directory, summary=None, *, complete=True, status="complete", scope="K4S-LINUX-DRY-RUN"):
    store = L.K4SStore(directory, scope)
    store.write("k4s-preconditions.json", dict(tiers=tiers()))
    if summary is not None:
        store.write("k4s-mac-summary.json", summary)
    if complete:
        store.write("k4s-complete.json", dict(completed=True))
    store.seal(status)
    return Path(directory), L.sha(Path(directory) / "receipt-manifest.json")


def classified(session, output):
    assert C.main(["classify", "--receipts", str(session), "--output", str(output)]) == 0
    return Path(output), L.sha(Path(output) / "receipt-manifest.json")


def reduce_argv(pairs, output):
    argv = ["reduce", "--output", str(output)]
    for (s, sd), (c, cd) in pairs:
        argv += ["--session", str(s), "--session-sha256", sd, "--classification", str(c), "--classification-sha256", cd]
    return argv


def test_reduce_verifies_classification_bytes_against_their_seal(tmp_path):
    good = dict(tiers_inputs=tiers(), gate_inputs=inputs(r_k4s=.84, p10_k4s=.8), provisional=True)
    s1 = sealed_session(tmp_path / "s1", good)
    c1 = classified(s1[0], tmp_path / "c1")
    assert C.main(reduce_argv([(s1, c1)], tmp_path / "final")) == 0
    final = json.loads((tmp_path / "final" / "k4s-mac-final.json").read_text())
    assert final["c_M"] == "0.8" and final["valid_sessions"] == 1
    # A technically invalid session: mutate classification.json to "valid", keep the original seal.
    s2 = sealed_session(tmp_path / "s2", dict(good, gate_inputs=inputs(r_k4s=.5)), complete=False, status="failed")
    c2 = classified(s2[0], tmp_path / "c2")
    assert json.loads((c2[0] / "classification.json").read_text())["valid"] is False
    forged = json.loads((c2[0] / "classification.json").read_text())
    forged.update(valid=True, category="valid", technical_repeat_candidate=False)
    (c2[0] / "classification.json").write_text(L.canonical(forged) + "\n")
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch"):
        C.main(reduce_argv([(s1, c1), (s2, c2)], tmp_path / "final2"))
    # A seal that omits classification.json is refused (no unsealed classification is ever read).
    c3 = tmp_path / "c3"
    store = L.K4SStore(c3, C.CLASSIFICATION_SCOPE)
    store.seal("complete")
    (c3 / "classification.json").write_text(L.canonical(dict(valid=True, category="valid",
                                                              source_manifest_sha256=s1[1], status="complete")) + "\n")
    with pytest.raises(L.PreconditionRefusal, match="does not include"):
        C.main(reduce_argv([(s1, (c3, L.sha(c3 / "receipt-manifest.json")))], tmp_path / "final3"))
    # A failed classification seal is not admissible.
    with pytest.raises(L.PreconditionRefusal):
        C.read_entry(s1[0], s1[1], s2[0], "0" * 64)


def test_reduce_reads_session_summary_only_from_its_own_inventory(tmp_path):
    s, sd = sealed_session(tmp_path / "s", None)
    c = classified(s, tmp_path / "c")
    (s / "k4s-mac-summary.json").write_text(L.canonical(dict(tiers_inputs=tiers(), gate_inputs=inputs(),
                                                             provisional=True)) + "\n")
    with pytest.raises(L.PreconditionRefusal, match="not in its own sealed inventory"):
        C.main(reduce_argv([((s, sd), c)], tmp_path / "final"))
    with pytest.raises(L.PreconditionRefusal, match="different session"):
        other = sealed_session(tmp_path / "o", dict(tiers_inputs=tiers(), gate_inputs=inputs(), provisional=True))
        C.read_entry(other[0], other[1], *c)


# ---------------------------------------------------------------- cleanup failures (finding 9)

def test_cleanup_failure_after_completion_is_classified_technical_and_excluded(tmp_path, offline, monkeypatch):
    class CompletedThenCleanupFails:
        def __init__(self, args, store, ctx):
            self.store = store

        def run(self):
            self.store.write("k4s-mac-summary.json", dict(tiers_inputs=tiers(), gate_inputs=inputs(), provisional=True))
            self.store.write("k4s-complete.json", dict(completed=True, utc=time.time()))

        def close(self):
            raise RuntimeError("Telemetry did not stop cleanly")
    ctx = dict(measure=True, dry_run=True, tiers=tiers(), sessions=[])
    monkeypatch.setattr(M, "preconditions", lambda args, store, **hooks: ctx)
    monkeypatch.setattr(M, "stage_inputs", lambda args, ctx, store: ctx)
    monkeypatch.setattr(M, "Session", CompletedThenCleanupFails)
    out = tmp_path / "k4s"
    with pytest.raises(RuntimeError, match="did not stop cleanly"):
        M.main(dry_argv(out), **offline)
    status, files = sealed(out)
    assert status == "failed" and {"cleanup-failure.json", "k4s-complete.json", "k4s-mac-summary.json"} <= set(files)
    result = C.classify(out)
    assert result["category"] == "technical-failure" and result["valid"] is False
    assert any("cleanup" in r for r in result["reasons"]) and result["counts_toward_repeat_allowance"] is True
    c = classified(out, tmp_path / "c")
    with pytest.raises(L.GateInputError, match="No valid"):
        C.main(reduce_argv([((out, L.sha(out / "receipt-manifest.json")), c)], tmp_path / "final"))
    good = sealed_session(tmp_path / "good", dict(tiers_inputs=tiers(), gate_inputs=inputs(r_k4s=.95), provisional=True))
    assert C.main(reduce_argv([((out, L.sha(out / "receipt-manifest.json")), c),
                               (good, classified(good[0], tmp_path / "cg"))], tmp_path / "final2")) == 0
    final = json.loads((tmp_path / "final2" / "k4s-mac-final.json").read_text())
    assert final["valid_sessions"] == 1 and final["excluded_sessions"] == 1


def test_complete_seal_without_completion_or_with_failure_is_not_valid(tmp_path):
    s, _ = sealed_session(tmp_path / "s", None, complete=False)
    assert C.classify(s)["category"] == "technical-failure"
    store = L.K4SStore(tmp_path / "t", "K4S-LINUX-DRY-RUN")
    store.write("k4s-complete.json", dict(completed=True))
    store.write("failure.json", dict(error="Traceback (most recent call last):\nRuntimeError: Replay worker failed"))
    store.seal("complete")
    assert C.classify(tmp_path / "t")["category"] == "technical-failure"


# ---------------------------------------------------------------- post-summary gate failure (r2 finding 17)

def summary_then(tmp_path, monkeypatch, offline, *, error, close_error=None, name="k4s"):
    """Session.run writes a PASSING summary, then the post-run bundle re-validation fails (as validate_bundle /
    assert_exact would on a changed specification); close() may fail too."""
    class SummaryThenFailure:
        def __init__(self, args, store, ctx):
            self.store = store

        def run(self):
            self.store.write("k4s-mac-summary.json", dict(tiers_inputs=tiers(), gate_inputs=inputs(), provisional=True))
            raise ValueError(error)

        def close(self):
            if close_error:
                raise RuntimeError(close_error)
    ctx = dict(measure=True, dry_run=True, tiers=tiers(), sessions=[])
    monkeypatch.setattr(M, "preconditions", lambda args, store, **hooks: ctx)
    monkeypatch.setattr(M, "stage_inputs", lambda args, ctx, store: ctx)
    monkeypatch.setattr(M, "Session", SummaryThenFailure)
    out = tmp_path / name
    with pytest.raises(ValueError, match="Exactness mismatch"):
        M.main(dry_argv(out), **offline)
    return out


def test_post_summary_exactness_failure_classifies_and_reduces_to_gate0_false(tmp_path, offline, monkeypatch):
    out = summary_then(tmp_path, monkeypatch, offline, error="Exactness mismatch: frozen r3 specification")
    status, files = sealed(out)
    summary = json.loads((out / "k4s-mac-summary.json").read_text())
    assert status == "failed" and "failure.json" in files and summary["gate_inputs"]["gate0"]["passes"] is True
    result = C.classify(out)
    assert result["category"] == "gate-failure" and result["valid"] is True and result["gate0_failed"] is True
    assert result["technical_repeat_candidate"] is False and result["counts_toward_repeat_allowance"] is False
    c = classified(out, tmp_path / "c")
    session = (out, L.sha(out / "receipt-manifest.json"))
    entry, _ = C.read_entry(*session, *c)
    assert entry["gate_inputs"]["gate0"]["passes"] is False and entry["gate_inputs"]["r_k4s"] is None
    assert entry["gate_inputs"]["gate0"]["parts"]["k4s_exactness_gate_failure"] is False
    assert C.main(reduce_argv([(session, c)], tmp_path / "final")) == 0
    final = json.loads((tmp_path / "final" / "k4s-mac-final.json").read_text())
    assert final["c_M"] is None and final["gate_inputs"]["gate0"]["passes"] is False and final["valid_sessions"] == 1
    good = sealed_session(tmp_path / "good", dict(tiers_inputs=tiers(), gate_inputs=inputs(r_k4s=.95), provisional=True))
    assert C.main(reduce_argv([(session, c), (good, classified(good[0], tmp_path / "cg"))], tmp_path / "final2")) == 0
    final = json.loads((tmp_path / "final2" / "k4s-mac-final.json").read_text())
    assert final["valid_sessions"] == 2 and final["c_M"] is None and final["kill"]["k4s_killed_on_mac"] is True


def test_exactness_failure_with_cleanup_failure_stays_a_no_repeat_gate_failure(tmp_path, offline, monkeypatch):
    out = summary_then(tmp_path, monkeypatch, offline, error="Exactness mismatch: frozen r3 specification",
                       close_error="Telemetry did not stop cleanly")
    status, files = sealed(out)
    assert status == "failed" and {"failure.json", "cleanup-failure.json"} <= set(files)
    result = C.classify(out)
    assert result["category"] == "gate-failure" and result["technical_repeat_candidate"] is False
    assert any("cleanup" in r for r in result["reasons"])
    c = classified(out, tmp_path / "c")
    assert C.main(reduce_argv([((out, L.sha(out / "receipt-manifest.json")), c)], tmp_path / "final")) == 0
    assert json.loads((tmp_path / "final" / "k4s-mac-final.json").read_text())["gate_inputs"]["gate0"]["passes"] is False


def test_gate_failure_classification_status_mismatch_is_recorded_and_still_fails_gate0():
    result = C.classify_records(failure_error="Exactness mismatch: x", complete=dict(completed=True), status="complete")
    assert result["category"] == "gate-failure" and result["gate0_failed"] is True
    assert any("disagrees" in r for r in result["reasons"]) and any("superseded" in r for r in result["reasons"])


def test_reducer_rejects_a_contradictory_valid_or_gate_failure_entry(tmp_path):
    passing = dict(tiers_inputs=tiers(), gate_inputs=inputs(), provisional=True)
    with pytest.raises(L.GateInputError, match="contradicts a passing gate 0"):
        C.reduce_sessions([(passing, dict(category="gate-failure", valid=True, gate0_failed=True))], "0.9")
    # A sealed "valid" classification for a session whose own seal holds failure evidence is refused.
    store = L.K4SStore(tmp_path / "s", "K4S-LINUX-DRY-RUN")
    store.write("k4s-mac-summary.json", passing)
    store.write("k4s-complete.json", dict(completed=True))
    store.write("cleanup-failure.json", dict(error="close failed"))
    store.seal("complete")
    digest = L.sha(tmp_path / "s" / "receipt-manifest.json")
    cstore = L.K4SStore(tmp_path / "c", C.CLASSIFICATION_SCOPE)
    cstore.write("classification.json", dict(category="valid", valid=True, source_manifest_sha256=digest, status="complete"))
    cstore.seal("complete")
    with pytest.raises(L.PreconditionRefusal, match="contradicts the session"):
        C.read_entry(tmp_path / "s", digest, tmp_path / "c", L.sha(tmp_path / "c" / "receipt-manifest.json"))
    # A gate-failure classification without a sealed exactness trace is refused.
    store = L.K4SStore(tmp_path / "s2", "K4S-LINUX-DRY-RUN")
    store.write("k4s-mac-summary.json", passing)
    store.seal("failed")
    digest = L.sha(tmp_path / "s2" / "receipt-manifest.json")
    cstore = L.K4SStore(tmp_path / "c2", C.CLASSIFICATION_SCOPE)
    cstore.write("classification.json", dict(category="gate-failure", valid=True, gate0_failed=True,
                                              source_manifest_sha256=digest, status="failed"))
    cstore.seal("complete")
    with pytest.raises(L.PreconditionRefusal, match="without a sealed exactness failure trace"):
        C.read_entry(tmp_path / "s2", digest, tmp_path / "c2", L.sha(tmp_path / "c2" / "receipt-manifest.json"))


def test_end_frozen_pins_cover_every_end_measurement_source():
    manifest = B.build(L.REPO_ROOT, ["reports/explore/k4s-confirm/sdefault.py", "reports/explore/k4s-confirm/anchor_x.py"], True)
    assert set(L.END_MEASUREMENT_FILES) <= set(manifest["end_files"]) | set(manifest["k4s_files"])
    pins = L.end_frozen_pins(manifest, "a" * 64, "reports/explore/k4s-confirm/sdefault.py",
                             "reports/explore/k4s-confirm/anchor_x.py")
    assert set(pins) == set(L.END_FROZEN_PIN_KEYS) and pins["k4s_manifest_sha256"] == "a" * 64
    with pytest.raises(L.PreconditionRefusal, match="END-source pin"):
        L.end_frozen_pins(dict(manifest, end_files={}), "a" * 64, "reports/explore/k4s-confirm/sdefault.py",
                          "reports/explore/k4s-confirm/anchor_x.py")


# ---------------------------------------------------------------- recorded gate-0 failure + cleanup (r3 finding 18)

def recorded_gate_failure(tmp_path, monkeypatch, offline, *, kind, close_error="Telemetry did not stop cleanly",
                          name="k4s"):
    """Through the real measure_k4s.main: the real K1/SD1 loops (fake backend) record a gate-0 failure normally,
    the session writes its failing summary and completion receipt, then close() fails (if ``close_error``)."""
    ids = [str(i) for i in range(5)]
    fleet = {i: dict(k4s_wall_seconds=.09, sd1_poll_seconds=.004, result=dict(action=1, candidates=[1], scores=[0.]))
             for i in ids}
    limits = dict(L.DRY_LIMITS, speed=5, speed_seconds=0, agreement=3)

    class RecordedGateFailure:
        def __init__(self, args, store, ctx):
            self.store, self.ctx = store, ctx

        def run(self):
            m = M.Measurements(FakeBackend(ids, mismatch="3" if kind == "corpus" else None), self.store, limits,
                               ids, fleet)
            corpus = m.corpus_exactness(exact)                           # a caught K1 mismatch, not an exception
            refs = {i: dict(gate=.9, legal=[1], ranks={"1": 1.}) for i in ids}
            agree = m.sd1_agreement(ids, refs, L.SD1_THRESHOLD, lambda ref, act, thr: dict(
                equal=kind != "agreement", allowed=kind != "agreement"))
            gate0 = dict(self.ctx["tiers"]["gate0"])
            gate0["parts"] = dict(gate0["parts"], k4s_corpus_exactness=corpus["passes"], sd1_agreement_k4s=agree["passes"],
                                  sd1_agreement_tiers_cpu=True, r5_binding=True)
            gate0["passes"] = all(v is True for v in gate0["parts"].values())
            assert gate0["passes"] is False
            inputs_ = dict(gate0=gate0, r_k4s=None, p10_k4s=None, r_inf=None, poll_p99_seconds=None, perception=None,
                           gc=None, mac_deadline=None, fleet_deadline=FLEET)
            mapping = dict(cells=None, provisional_cell=None, gate6_trail=[], c_M_k4s=None, mac_infeasible=True,
                           reason="gate 0 failed; no K4S cell can pass")
            self.store.write("k4s-mac-summary.json", M.summarize(self.ctx, inputs=inputs_, mapping=mapping,
                             extra=dict(corpus_exactness=corpus, sd1_agreement=agree),
                             provisional=L.provisional_status(False, False, False)))
            self.store.write("k4s-complete.json", dict(completed=True, utc=time.time()))

        def close(self):
            if close_error:
                raise RuntimeError(close_error)
    ctx = dict(measure=True, dry_run=True, tiers=tiers(), sessions=[], c_star="0.9", mode="in-session",
               k4s_manifest_sha256="a" * 64)

    def preconditions(args, store, **hooks):
        store.write("k4s-preconditions.json", dict(mode="in-session", tiers=ctx["tiers"], measure=True))
        return ctx
    monkeypatch.setattr(M, "preconditions", preconditions)
    monkeypatch.setattr(M, "stage_inputs", lambda args, ctx, store: ctx)
    monkeypatch.setattr(M, "Session", RecordedGateFailure)
    out = tmp_path / name
    if close_error:
        with pytest.raises(RuntimeError, match=close_error):
            M.main(dry_argv(out), **offline)
    else:
        assert M.main(dry_argv(out), **offline) == 0
    return out, L.sha(out / "receipt-manifest.json")


EVIDENCE = {"corpus": ["k4s-corpus-exactness.jsonl: recorded exactness mismatch on state 3",
                       "k4s-mac-summary.json gate 0: k4s_corpus_exactness"],
            "agreement": ["k4s-mac-summary.json gate 0: sd1_agreement_k4s",
                          "k4s-sd1-agreement.jsonl: unexplained SD1 disagreement (TIERS §7.3)"]}


@pytest.mark.parametrize("kind", ["corpus", "agreement"])
def test_recorded_gate0_failure_survives_a_later_cleanup_failure(tmp_path, offline, monkeypatch, kind):
    """The reviewer's r3 scenario: main -> classify -> reduce, alone and alongside a good session."""
    session = recorded_gate_failure(tmp_path, monkeypatch, offline, kind=kind)
    status, files = sealed(session[0])
    summary = json.loads((session[0] / "k4s-mac-summary.json").read_text())
    assert status == "failed" and {"cleanup-failure.json", "k4s-complete.json", "k4s-mac-summary.json"} <= set(files)
    assert "failure.json" not in files and summary["gate_inputs"]["gate0"]["passes"] is False
    result = C.classify(session[0])
    assert result["category"] == "gate-failure" and result["valid"] is True and result["gate0_failed"] is True
    assert result["technical_repeat_candidate"] is False and result["counts_toward_repeat_allowance"] is False
    assert result["gate0_thrown"] is False and result["gate0_evidence"] == EVIDENCE[kind]
    assert any("cleanup" in r for r in result["technical_diagnostics"])                  # diagnostics kept
    assert any("survives the later failure" in r for r in result["reasons"])
    with pytest.raises(L.PreconditionRefusal, match="not a pre-listed technical failure"):
        L.check_repeat_admission([dict(result, receipt_sha256="0" * 64)], released=False, review=None)
    c = classified(session[0], tmp_path / "c")
    entry, _ = C.read_entry(*session, *c)
    part = "k4s_corpus_exactness" if kind == "corpus" else "sd1_agreement_k4s"
    assert entry["gate_inputs"]["gate0"]["passes"] is False and entry["gate_inputs"]["gate0"]["parts"][part] is False
    assert "k4s_exactness_gate_failure" not in entry["gate_inputs"]["gate0"]["parts"]
    assert C.main(reduce_argv([(session, c)], tmp_path / "final")) == 0
    final = json.loads((tmp_path / "final" / "k4s-mac-final.json").read_text())
    assert final["valid_sessions"] == 1 and final["c_M"] is None and final["kill"]["k4s_killed_on_mac"] is True
    good = sealed_session(tmp_path / "good", dict(tiers_inputs=tiers(), gate_inputs=inputs(r_k4s=.95), provisional=True))
    assert C.main(reduce_argv([(session, c), (good, classified(good[0], tmp_path / "cg"))], tmp_path / "final2")) == 0
    final = json.loads((tmp_path / "final2" / "k4s-mac-final.json").read_text())
    assert final["valid_sessions"] == 2 and final["excluded_sessions"] == 0
    assert final["c_M"] is None and final["gate_inputs"]["gate0"]["passes"] is False
    assert final["kill"]["k4s_killed_on_mac"] is True and final["gate_inputs"]["gate0"]["parts"][part] is False


def test_recorded_gate0_failure_without_cleanup_failure_is_the_same_gate_failure(tmp_path, offline, monkeypatch):
    session = recorded_gate_failure(tmp_path, monkeypatch, offline, kind="corpus", close_error=None)
    assert sealed(session[0])[0] == "complete"
    result = C.classify(session[0])
    assert result["category"] == "gate-failure" and result["gate0_evidence"] == EVIDENCE["corpus"]
    assert result["technical_diagnostics"] == []
    c = classified(session[0], tmp_path / "c")
    assert C.main(reduce_argv([(session, c)], tmp_path / "final")) == 0
    assert json.loads((tmp_path / "final" / "k4s-mac-final.json").read_text())["c_M"] is None


def test_admission_refuses_a_classification_that_discards_a_recorded_gate0_failure(tmp_path, offline, monkeypatch):
    session = recorded_gate_failure(tmp_path, monkeypatch, offline, kind="agreement")
    for forged in (dict(category="technical-failure", valid=False, technical_repeat_candidate=True),
                   dict(category="valid", valid=True, technical_repeat_candidate=False),
                   dict(category="gate-failure", valid=True, gate0_failed=True, gate0_evidence=EVIDENCE["corpus"])):
        name = "c-" + forged["category"] + str(len(forged))
        store = L.K4SStore(tmp_path / name, C.CLASSIFICATION_SCOPE)
        store.write("classification.json", dict(forged, source_manifest_sha256=session[1], status="failed"))
        store.seal("complete")
        with pytest.raises(L.PreconditionRefusal, match="discards the session|differs from the session"):
            C.read_entry(*session, tmp_path / name, L.sha(tmp_path / name / "receipt-manifest.json"))


def test_recorded_gate0_contradictions_are_refused_and_partial_traces_establish_failures(tmp_path):
    def session(name, *, summary=None, agreement=(), corpus=(), failure=None, status="failed"):
        store = L.K4SStore(tmp_path / name, "K4S-LINUX-DRY-RUN")
        store.write("k4s-preconditions.json", dict(tiers=tiers()))
        for row in corpus:
            store.append("k4s-corpus-exactness.jsonl", row)
        for row in agreement:
            store.append("k4s-sd1-agreement.jsonl", row)
        if summary is not None:
            store.write("k4s-mac-summary.json", summary)
        if failure:
            store.write("failure.json", dict(error=failure))
        store.seal(status)
        return tmp_path / name
    # Crash mid-agreement after an unexplained disagreement: the recorded verdict already fails TIERS §7.3.
    crash = "Traceback (most recent call last):\nRuntimeError: Replay worker failed"
    out = session("partial", agreement=[dict(id="0", equal=False, allowed=False)], failure=crash)
    result = C.classify(out)
    assert result["category"] == "gate-failure" and result["gate0_evidence"] == EVIDENCE["agreement"][1:]
    assert "harness/load exception" in result["technical_diagnostics"]
    # A caught K1 mismatch before a crash (no summary yet).
    out = session("k1", corpus=[dict(id="0", exact=False, error="Exactness mismatch: k4s-corpus/0")], failure=crash)
    assert C.classify(out)["gate0_evidence"] == ["k4s-corpus-exactness.jsonl: recorded exactness mismatch on state 0"]
    # An allowed (tolerated) disagreement alone is not a recorded failure: technical.
    out = session("allowed", agreement=[dict(id="0", equal=False, allowed=True)], failure=crash)
    assert C.classify(out)["category"] == "technical-failure"
    # A summary that contradicts the traces it summarises is refused, never resolved as a pass.
    passing = dict(tiers_inputs=tiers(), gate_inputs=inputs(gate0=dict(passes=True, parts=dict(
        tiers_exactness_and_worker_equality=True, k4s_corpus_exactness=True))), provisional=True)
    out = session("contra", summary=passing, corpus=[dict(id="0", exact=False, error="Exactness mismatch: x")],
                  status="complete")
    with pytest.raises(L.PreconditionRefusal, match="K1 corpus-exactness trace"):
        C.classify(out)
    lying = dict(passing, gate_inputs=inputs(gate0=dict(passes=True, parts=dict(tiers_exactness_and_worker_equality=False))))
    with pytest.raises(L.PreconditionRefusal, match="passes differs"):
        C.classify(session("lying", summary=lying, status="complete"))
    other = dict(passing, tiers_inputs=tiers(gate0=False))
    with pytest.raises(L.PreconditionRefusal, match="committed TIERS inputs"):
        C.classify(session("tiers", summary=other, status="complete"))


def test_tiers_invalid_session_rule_still_precedes_a_recorded_gate0_failure(tmp_path, offline, monkeypatch):
    session = recorded_gate_failure(tmp_path, monkeypatch, offline, kind="corpus")
    tiers_dir, digest = make_tiers_session(tmp_path / "tiers")
    result = C.classify(session[0], tiers_dir, digest,
                        tiers_classify=lambda _: dict(technical_repeat_candidate=True, reasons=["foreign"]))
    assert result["category"] == "invalid-tiers-session" and result["valid"] is False
    assert result["counts_toward_repeat_allowance"] is False
