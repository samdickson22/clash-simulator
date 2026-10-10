"""Dependency-free tests; the native integration receipt is a separate test."""
import copy
import gc
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receipts import (TIERS, ReceiptStore, agreement, agreement_gate, assert_exact,
    choose_backend, deadline_equivalence, feasible, gc_summary, perception_window,
    quantiles, sha, speed_summary, verify_files, score_exactness, belief_exactness,
    census_average, forward_exception)
from measure_tiers import GCTrace, admit_platform, main, validate_counts, DRY_LIMITS, Session
from telemetry import idle_delta, validate_topology
from classify_failure import classify
from tier_backend import dry_opening_orders
from fleet_reference import validate_row, REQUIRED_ROW
from replay_load import LinuxBackground, admit_background


class ReceiptTests(unittest.TestCase):
    def test_r3_near_exact_scores_keep_discrete_outputs_exact(self):
        ref=dict(action=1,candidates=[1,2],scores=[1.,0.])
        self.assertGreater(score_exactness(dict(ref,scores=[1.+5e-13,0.]),ref,"near"),0.)
        for value in (dict(ref,scores=[1.+2e-12,0.]),dict(ref,scores=[1.,1e-30]),dict(ref,action=2)):
            with self.assertRaises(ValueError):
                score_exactness(value,ref,"fail")

    def test_belief_near_exact_preserves_support_and_rng(self):
        ref=dict(ledger={},events=[],samples=[],rng={"state":1},derived={},
                 arrays={"weights":dict(dtype="float64",shape=[2],sha256="reference",values=[.4,.6])})
        actual=copy.deepcopy(ref);actual["arrays"]["weights"]["values"][0]+=.4*5e-13
        self.assertGreater(belief_exactness(actual,ref,"near"),0.)
        actual["rng"]["state"]=2
        with self.assertRaises(ValueError):
            belief_exactness(actual,ref,"rng")
    def test_background_cleanup_joins_every_worker_after_first_failure(self):
        load = object.__new__(LinuxBackground)
        load.stop = MagicMock()
        load.workers = [MagicMock(pid=1,exitcode=1),MagicMock(pid=2,exitcode=0)]
        for worker in load.workers:worker.is_alive.return_value=False
        with self.assertRaises(RuntimeError):load.close()
        for worker in load.workers:worker.join.assert_called_once_with(10)

    def test_native_mismatch_stops_all_tier_checks_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ref=dict(action=1,candidates=[1],scores=[1.])
            (root/"golden.json").write_text(json.dumps({"a":ref}))
            backend=MagicMock()
            backend.by_id={"a":{}}
            backend.golden.return_value=dict(ref,scores=[1.+2e-12])
            session=SimpleNamespace(args=SimpleNamespace(bundle=root),backend=backend,
                manifest=dict(sets=dict(golden=["a"])),exactness_class="EXACT",store=MagicMock())
            with self.assertRaisesRegex(ValueError,"Exactness mismatch"):
                Session.exactness(session)
            backend.golden.assert_called_once()
            backend.zero_budget.assert_not_called()
            session.store.write.assert_not_called()

    def test_partial_failure_sealed_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            store = ReceiptStore(out, "test")
            (out/"nested").mkdir()
            (out/"nested/settings.json").write_text('{"offline":true}')
            store.append("raw.jsonl", dict(value=2))
            store.write("failure.json", dict(error="stopped", fail_closed=True))
            with self.assertRaises(FileExistsError):
                store.write("failure.json", {})
            store.seal("failed")
            manifest = json.loads((out / "receipt-manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertIn("nested/settings.json",manifest["files"])
            verify_files(out, manifest["files"])
            self.assertTrue((out / "receipt-manifest.sha256").read_text().startswith(sha(out / "receipt-manifest.json")))
            (out / "raw.jsonl").write_text("altered")
            with self.assertRaisesRegex(ValueError, "Pin mismatch"):
                verify_files(out, manifest["files"])
            with self.assertRaises(FileExistsError):
                ReceiptStore(out, "test")

    def test_pin_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "outside").write_text("data")
            (base / "root").mkdir()
            (base / "root/link").symlink_to(base / "outside")
            for name in ("../outside", "link"):
                with self.assertRaises(ValueError):
                    verify_files(base / "root", {name: sha(base / "outside")})

    def test_exactness_covers_actions_candidates_and_scores(self):
        ref = dict(action=2304, candidates=[1, 2304], scores=[.1, .2])
        assert_exact(ref, copy.deepcopy(ref), "same")
        for key, value in (("action", 1), ("candidates", [2304, 1]), ("scores", [.1, .200000000000001])):
            actual = dict(ref, **{key: value})
            with self.assertRaisesRegex(ValueError, "Exactness mismatch"):
                assert_exact(actual, ref, key)
        with self.assertRaises(ValueError):
            assert_exact(dict(ref, scores=[float("nan"), .2]), ref, "NaN")

    def test_refusal_itself_leaves_sha_failure_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"run"
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}), patch("measure_tiers.admit_platform", side_effect=ValueError("Unauthorized Mac")):
                with self.assertRaisesRegex(ValueError, "Unauthorized Mac"):
                    main(["--bundle", tmp, "--runtime-root", tmp, "--native", tmp,
                          "--output", str(out), "--manifest-sha256", "0"*64])
            manifest = json.loads((out/"receipt-manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            verify_files(out, manifest["files"])
            self.assertTrue(json.loads((out/"failure.json").read_text())["fail_closed"])


class SpeedTests(unittest.TestCase):
    def test_distribution_and_conservative_ratio_with_per_state_repeats(self):
        rows = []
        for tier in TIERS:
            for identity, reference, walls in (("a", 1., [1., 3., 2.]), ("b", 4., [2.])):
                for wall in walls:
                    rows.append(dict(tier=tier, id=identity, fleet_wall_seconds=reference, wall_seconds=wall))
        result = speed_summary(rows)["S"]
        # State medians are 2 and 2: per-state ratios .5 and 2.
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["p50"], 1.25)
        self.assertAlmostEqual(result["p10"], .65)
        self.assertAlmostEqual(result["p25"], .875)
        self.assertEqual(result["sum_ratio"], 1.25)
        self.assertEqual(result["r"], 1.25)
        self.assertEqual(result["per_state_ratios"], [.5, 2.])

    def test_tail_ratio_can_demote_median_at_cliff(self):
        rows = [dict(tier=t, id=str(i), fleet_wall_seconds=1., wall_seconds=w)
                for t in TIERS for i,w in enumerate([1.,1.,1.,4.])]
        result = speed_summary(rows)["K4"]
        self.assertEqual(result["p50"], 1.)
        self.assertLess(result["r"], .8)

    def test_reference_mutation_and_invalid_timings_rejected(self):
        rows = [dict(tier="S", id="a", fleet_wall_seconds=f, wall_seconds=1.) for f in (1.,2.)]
        with self.assertRaises(ValueError):
            speed_summary(rows)
        with self.assertRaises(ValueError):
            quantiles([0, float("inf")])
        with self.assertRaises(ValueError):
            quantiles([])

    def test_deadline_equivalence_demotes_one_cell(self):
        fleet = {"1.0": dict(cutoff=.1,no_complete_play=.05), "0.8": dict(cutoff=.4,no_complete_play=.15)}
        result = deadline_equivalence(dict(r=1.05), dict(cutoff=.2,fallback=.1,no_complete_play=.10), fleet)
        self.assertEqual(result["cell"], .8)
        self.assertEqual(len(result["checks"]), 2)
        killed = deadline_equivalence(dict(r=.9), dict(cutoff=.5,no_complete_play=.2), fleet)
        self.assertIsNone(killed["cell"])

    def test_feasibility_boundaries_without_rounding(self):
        speed = dict(r=.8, p10=.7)
        result = feasible(speed, {"passes": True}, True, {"passes": True}, deadline_cell=.8)
        self.assertTrue(result["feasible"])
        for field in ("r", "p10"):
            below = dict(speed, **{field: speed[field]-1e-12})
            self.assertFalse(feasible(below,{"passes":True},True,{"passes":True},deadline_cell=.8)["feasible"])
        self.assertIn("deadline equivalence", feasible(speed,{"passes":True},True,{"passes":True})["reasons"])


class AgreementTests(unittest.TestCase):
    def row(self, gate=.6):
        return dict(gate=gate, legal=list(range(9)), ranks={i: 10.-i for i in range(9)})

    def test_far_gate_disagreement_fails(self):
        result = agreement(self.row(.8), self.row(.2), .5)
        self.assertFalse(result["equal"])
        self.assertFalse(result["allowed"])

    def test_gate_threshold_disagreement_is_registered_tolerance(self):
        self.assertTrue(agreement(self.row(.50005), self.row(.49995), .5)["allowed"])

    def test_near_rank_ties_only_at_swapped_entries(self):
        old, new = self.row(), self.row()
        old["ranks"][1] = old["ranks"][0]-5e-5
        new["ranks"][1] = new["ranks"][0]+5e-5
        result = agreement(old,new,.5)
        self.assertFalse(result["equal"])
        self.assertTrue(result["allowed"])
        old, new = self.row(), self.row()
        old["ranks"][7] = old["ranks"][8]  # Unrelated exact tie.
        new["ranks"][1] = 11.
        self.assertFalse(agreement(old,new,.5)["allowed"])

    def test_ordered_top8_boundary_replacement_is_checked(self):
        old, new = self.row(), self.row()
        new["ranks"][8] = 20.
        self.assertFalse(agreement(old,new,.5)["allowed"])

    def test_joint_agreement_rate_and_explanation(self):
        passed = [dict(equal=True, allowed=True)]*1990 + [dict(equal=False,allowed=True)]*10
        self.assertTrue(agreement_gate(passed)["passes"])
        self.assertFalse(agreement_gate(passed+[dict(equal=False,allowed=True)])["passes"])
        failed = passed[:-1]+[dict(equal=False,allowed=False)]
        self.assertFalse(agreement_gate(failed)["passes"])

    def test_backend_rule_uses_latency_and_perception_contention(self):
        gates = {d: {"passes":True} for d in ("cpu","mps")}
        latency = {"cpu": {"p99":10}, "mps":{"p99":8}}
        self.assertEqual(choose_backend(gates,latency,{"cpu":10,"mps":12}),"mps")
        self.assertEqual(choose_backend(gates,latency,{"cpu":10,"mps":12.001}),"cpu")
        gates["mps"]["passes"] = False
        self.assertEqual(choose_backend(gates,latency,{"cpu":10,"mps":10}),"cpu")
        gates["cpu"]["passes"] = False
        self.assertIsNone(choose_backend(gates,latency,{"cpu":10,"mps":10}))


class TelemetryTests(unittest.TestCase):
    def test_census_uses_whole_window_average_not_peak(self):
        rows=[dict(interval_seconds=1.,processes=[dict(pid=1,owned=False,cpu_cores=1.)])]
        rows += [dict(interval_seconds=1.,processes=[]) for _ in range(9)]
        self.assertAlmostEqual(census_average(rows)["1"],.1)

    def test_gc_charges_actual_dispatch_after_collection(self):
        poll=dict(poll_id="a",opportunity=True,scheduled=1.,entered=1.06)
        result=gc_summary([dict(start=.99,end=1.01)],[poll])
        self.assertAlmostEqual(result["max_in_opportunity_poll_delay_ms"],60.)
        self.assertFalse(result["passes"])
    def test_perception_counts_expected_deliveries_not_only_captured(self):
        rows=[dict(finished=i/20,service_ms=10.) for i in range(200)]
        self.assertTrue(perception_window(rows,0,10)["passes"])
        dropped=perception_window(rows[:180],0,10)
        self.assertEqual(dropped["fps"],18.)
        self.assertFalse(dropped["passes"])  # 90% processed despite 18 FPS.

    def test_per_cpu_idle_maps_clusters(self):
        result=idle_delta({0:(100,50),1:(100,60)}, {0:(200,130),1:(200,80)}, {"P":[0],"E":[1]})
        self.assertAlmostEqual(result["free_P"],.8)
        self.assertAlmostEqual(result["free_E"],.2)
        with self.assertRaises(ValueError):
            validate_topology({"P":[0],"E":[0,1]}, {0:(),1:()},darwin=False)

    def test_gc_rate_deduplicates_events_and_requires_25ms_lateness(self):
        polls=[dict(poll_id=str(i),opportunity=True,scheduled=float(i),entered=float(i)) for i in range(100)]
        polls[1]["entered"] = 1.03
        events=[dict(start=.99,end=1.03),dict(start=1.,end=1.02)]
        result=gc_summary(events,polls)
        self.assertEqual(result["delayed_poll_rate"],.01)
        self.assertTrue(result["passes"])
        polls[1]["entered"] = 1.02
        self.assertEqual(gc_summary(events,polls)["delayed_polls"],0)

    def test_gc_charged_tick_gate_and_unavailable_opportunities(self):
        poll=dict(poll_id="a",opportunity=True,scheduled=1.,entered=1.051)
        self.assertFalse(gc_summary([dict(start=.9,end=1.051)],[poll])["passes"])
        self.assertFalse(gc_summary([],[])["passes"])

    def test_timestamped_gc_callback_captures_context_and_generation(self):
        with GCTrace() as trace:
            trace.context.update(tier="K4",scheduled_poll_deadline=1.,opportunity=True)
            gc.collect(0)
        self.assertTrue(trace.events)
        self.assertEqual(trace.events[-1]["generation"],0)
        self.assertEqual(trace.events[-1]["tier"],"K4")
        self.assertLessEqual(trace.events[-1]["start"],trace.events[-1]["end"])


class AdmissionTests(unittest.TestCase):
    def test_fleet_capture_contract_rejects_live_progress_or_missing_reservation(self):
        row = {key:None for key in REQUIRED_ROW}
        row.update(tier="K2",d1_before={},belief_before=SimpleNamespace(_pending=None),strata=dict(elixir=5.,legal_play_count=3))
        validate_row(row,"K2")
        row.pop("reserved_packet")
        with self.assertRaises(ValueError):validate_row(row,"K2")
        row["reserved_packet"]=None
        row["belief_before"]._pending=object()
        with self.assertRaises(ValueError):validate_row(row,"K2")

    def test_legacy_packet_refill_gap_preserves_public_eight_card_order(self):
        rows = [dict(seed=1,info=SimpleNamespace(own=dict(hand=list("ABCD"),cycle=list("EFGH")))),
                dict(seed=1,info=SimpleNamespace(own=dict(hand=list("ABCD"),cycle=list("EFG"))))]
        self.assertEqual(dry_opening_orders(rows)[1],list("ABCDEFGH"))
        with self.assertRaises(ValueError):
            dry_opening_orders(rows[1:])
    def test_background_admission_distinguishes_t1_reference_from_dry_run(self):
        admit_background("Linux","127x05",19,False)
        admit_background("Linux","127x03",10,True)
        admit_background("Linux","127x01",10,True)
        admit_background("Linux","127x08",10,True)
        for params in (("Linux","127x01",19,False),("Linux","127x04",10,True),("Linux","127x05",10,True)):
            with self.assertRaises(ValueError):admit_background(*params)

    def test_platform_and_host_guards(self):
        admit_platform(True,False,"Linux","x86_64","127x03",19)
        admit_platform(True,False,"Linux","x86_64","127x05",19)
        admit_platform(False,True,"Darwin","arm64","mac",10)
        for params in ((True,False,"Linux","x86_64","127x01",19),
                       (True,False,"Linux","x86_64","127x04",19),
                       (True,False,"Linux","x86_64","127x03",10),
                       (False,False,"Darwin","arm64","mac",10),
                       (False,True,"Darwin","x86_64","mac",10),
                       (False,True,"Linux","arm64","mac",10)):
            with self.assertRaises(ValueError):
                admit_platform(*params)

    def test_counts_reject_repeated_state_padding(self):
        manifest=dict(sets={"golden":[str(i) for i in range(125)], "agreement":[str(i) for i in range(32)],
            "packets":[str(i) for i in range(32)],"speed":{t:[str(i) for i in range(32)] for t in TIERS}},
            packet_schedule=[dict(id=str(i),offset_seconds=i*.5) for i in range(32)])
        validate_counts(manifest,DRY_LIMITS,True)
        manifest["sets"]["speed"]["K4"]=["a"]*300
        with self.assertRaisesRegex(ValueError,"duplicate"):
            validate_counts(manifest,DRY_LIMITS,True)

    def test_failure_classifier_never_grants_repeat_for_exactness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"failure"
            store=ReceiptStore(out,"test")
            store.write("failure.json",dict(error="ValueError: Exactness mismatch: scores"))
            store.seal("failed")
            result=classify(out)
            self.assertFalse(result["technical_repeat_candidate"])
            self.assertTrue(result["exactness_failure"])


if __name__ == "__main__":
    unittest.main()
