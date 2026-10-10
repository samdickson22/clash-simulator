"""Public corpus admission, reporting masks and mechanical raw pooling."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corpus_contract import REQUIRED_ROW,validate_row,validate_capture_receipt
from fleet_profile import slot_layout,compare_mhz
from fleet_pool import pool_rows
from tier_backend import NATIVE_SHA,V1_SHA,STUDENT_SHA,CALIBRATION_SHA,THRESHOLD
from receipts import TIERS,ReceiptStore,sha,verify_files
from measure_tiers import main


def corpus_row():
    row=dict.fromkeys(REQUIRED_ROW)
    row.update(id="a",tier="K2",seed=1,d1_before={},belief_before=SimpleNamespace(_pending=None),
        belief_had_suspended_transaction=False,opponent_elixir=5.,strata=dict(elixir=5.,legal_play_count=3,bins=[1,1]))
    return row


def host_rows(walls,states=1):
    speed=[];deadlines=[]
    for tier in TIERS:
        for i in range(states):
            for repeat,wall in enumerate(walls):
                speed.append(dict(tier=tier,id=str(i),repeat=repeat,wall_seconds=wall))
                for cell,budget in (("1.0",.2),("0.8",.16)):
                    deadlines.append(dict(tier=tier,id=str(i),repeat=repeat,cell=cell,deadline_seconds=budget,
                        wall_seconds=.1,cutoff=repeat==0,fallback=repeat==0,no_complete_play=repeat==1,
                        over_200_ms=False,cut_return_over_208_ms=False))
    return dict(speed=speed,deadlines=deadlines)


class CorpusContractTests(unittest.TestCase):
    def test_contract_matches_t1_exact_twenty_fields(self):
        root=Path(__file__).resolve().parents[7]
        # The external draft can advance independently; required row names stay explicit here.
        self.assertEqual(len(REQUIRED_ROW),20)
        validate_row(corpus_row(),"K2")
        for key in ("belief_resume","elixir","legal_play_count","tick","replay_timestamp_seconds","true_opponent_deck"):
            with self.subTest(key=key),self.assertRaises(ValueError):validate_row(dict(corpus_row(),**{key:None}))
        for key in REQUIRED_ROW:
            row=corpus_row();del row[key]
            with self.subTest(missing=key),self.assertRaises(ValueError):validate_row(row)
        row=corpus_row();row["strata"]["extra"]=1
        with self.assertRaises(ValueError):validate_row(row)

    def test_only_committed_public_belief_is_admitted(self):
        row=corpus_row();row["belief_before"]._pending=object()
        with self.assertRaises(ValueError):validate_row(row)
        row=corpus_row();row["belief_had_suspended_transaction"]=1
        with self.assertRaises(ValueError):validate_row(row)

    def test_policy_history_required_outside_linux_smoke(self):
        from tier_backend import TierBackend
        backend=object.__new__(TierBackend);backend.manifest=dict(profile="fleet-reference")
        # Admission rejects this before inference/native work can be invoked.
        row=corpus_row();del row["d1_before"]
        with self.assertRaises(ValueError):validate_row(row)
    def test_capture_health_and_inventory_remain_bound_to_fixed_selected_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected={t:[t+str(i) for i in range(300)] for t in TIERS}
            tiers={t:dict(states=300,state_inventory=[dict(id=i,sha256="a"*64) for i in ids],
                capture_health=dict(eligible_search_opportunities=400,deadline_cut=40,suspended_transaction=100),
                selected_suspended_transaction_states=0) for t,ids in selected.items()}
            receipt=dict(outcomes_read=False,tiers=tiers)
            path=Path(tmp)/"corpora.json";path.write_text(json.dumps(receipt))
            manifest=dict(corpus_receipt="corpora.json",files={"corpora.json":sha(path)},sets=dict(speed=selected))
            backend=SimpleNamespace(by_id={i:dict(belief_had_suspended_transaction=False) for ids in selected.values() for i in ids})
            validate_capture_receipt(tmp,manifest,backend)
            tiers["K4"]["state_inventory"][0]["id"]="wrong"
            path.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):validate_capture_receipt(tmp,manifest,backend)



class FleetProfileTests(unittest.TestCase):
    def setUp(self):
        self.plan=dict(compute=dict(hosts={"test-host":dict(physical_cpus=list(range(55)),census_cpu=63)},
            nice=12,scheduler="SCHED_OTHER",slots=11,console_slots=8,slot_width=5,smt=False))
        self.profile=dict(host="test-host",slot_count=11,console_rule=False,reference_slot=2,
            warmup_seconds=300,perception="none")

    def test_all_slots_follow_pinned_host_and_priority_without_host_hardcoding(self):
        own,other,census=slot_layout(self.profile,self.plan,"test-host",12)
        self.assertEqual(own,list(range(10,15)))
        self.assertEqual(len(other),10)
        self.assertEqual(set(own+sum(other,[])),set(range(55)))
        self.assertEqual(census,63)
        self.profile.update(console_rule=True,slot_count=8)
        self.assertEqual(len(slot_layout(self.profile,self.plan,"test-host",12)[1]),7)

    def test_profile_rejects_priority_partial_slots_and_perception(self):
        for change in (dict(slot_count=2),dict(reference_slot=11),dict(warmup_seconds=299),dict(warmup_seconds=float("nan")),dict(console_rule="false"),dict(perception="v3")):
            with self.subTest(change=change),self.assertRaises(ValueError):slot_layout(dict(self.profile,**change),self.plan,"test-host",12)
        with self.assertRaises(ValueError):slot_layout(self.profile,self.plan,"test-host",10)
        with self.assertRaises(ValueError):slot_layout(self.profile,self.plan,"other-host",12)

    def test_background_worker_runs_every_tier_and_full_corpus_on_its_pinned_mask(self):
        from replay_load import fleet_corpus_worker,FleetBackground
        manifest=dict(sets=dict(speed={t:[str(i) for i in range(300)] for t in TIERS}))
        calls=[];stop=MagicMock();stop.is_set.side_effect=lambda:len(calls)>=1200
        backend=MagicMock();backend.by_id={str(i):dict(id=str(i)) for i in range(300)}
        backend.work.side_effect=lambda row,tier:calls.append((tier,row["id"]))
        ready=MagicMock();mask=list(range(5,10))
        with patch("replay_load.validate_bundle",return_value=manifest),patch("fleet_profile.pinned_profile",return_value=(None,None,([], [mask],63))),patch("tier_backend.TierBackend",return_value=backend),patch("os.sched_setaffinity") as affinity:
            fleet_corpus_worker(None,None,None,ready,stop,mask,1)
        affinity.assert_called_once_with(0,set(mask))
        self.assertEqual({t:sum(tier==t for tier,_ in calls) for t in TIERS},{t:300 for t in TIERS})
        backend.close.assert_called_once()
        load=FleetBackground(None,None,None,[list(range(i,i+5)) for i in range(5,55,5)])
        self.assertEqual(len(load.workers),10)
        self.assertTrue(all(p._target is fleet_corpus_worker for p in load.workers))

    def test_reporting_mhz_comparison_checks_every_busy_physical_core(self):
        reporting=[dict(slots=11,physical_core_mhz=[dict(cpu=i,mhz=2000.) for i in range(55)]) for _ in range(2)]
        reference=[dict(phase="reference-speed",cpu_clock_mhz=[2020.]*64) for _ in range(2)]
        result=compare_mhz(reporting,reference,list(range(55)),11)
        self.assertTrue(result["passes"]);self.assertAlmostEqual(result["reference_to_reporting_mean"],1.01)
        reference[0]["cpu_clock_mhz"]=[2300.]*64
        self.assertFalse(compare_mhz(reporting,reference,list(range(55)),11)["passes"])
        reporting[0]["physical_core_mhz"].pop()
        with self.assertRaises(ValueError):compare_mhz(reporting,reference,list(range(55)),11)


class FleetPoolTests(unittest.TestCase):
    def test_raw_observations_are_pooled_not_host_medians(self):
        result=pool_rows({"a":host_rows([.96,.97,1.04]),"b":host_rows([.98,1.02,1.03])},min_states=1)
        self.assertEqual(result["walls"]["K4"]["0"],1.)
        self.assertNotEqual(result["walls"]["K4"]["0"],(.97+1.02)/2)
        self.assertEqual(result["deadlines"]["S"]["1.0"]["n"],6)
        self.assertEqual(result["deadlines"]["S"]["1.0"]["counts"]["cutoff"],2)

    def test_host_outside_five_percent_is_excluded_before_repooling(self):
        result=pool_rows({"a":host_rows([1.]*3),"b":host_rows([1.02]*3),"slow":host_rows([1.2]*3)},min_states=1)
        self.assertEqual(result["excluded"],["slow"])
        self.assertAlmostEqual(result["walls"]["K2"]["0"],1.01)
        self.assertEqual(result["deadlines"]["K2"]["1.0"]["n"],6)

    def test_missing_duplicate_raw_repeat_or_deadline_cell_fails_closed(self):
        good={"a":host_rows([1.]*3)}
        for key in ("speed","deadlines"):
            for duplicate in (False,True):
                value=copy.deepcopy(good)
                if duplicate:value["a"][key].append(value["a"][key][0])
                else:value["a"][key].pop()
                with self.subTest(key=key,duplicate=duplicate),self.assertRaises(ValueError):pool_rows(value,min_states=1)

    def test_full_pool_cli_verifies_seals_and_outputs_counted_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);entries=[]
            for name in ("a","b"):
                data=host_rows([1.]*3,states=300)
                store=ReceiptStore(base/name,"FLEET-REFERENCE")
                sets={t:[str(i) for i in range(300)] for t in TIERS}
                folder=Path(__file__).resolve().parents[1]
                files={p.name:sha(p) for p in folder.iterdir() if p.suffix in (".py",".sh") or p.name=="spec-pins.json"}
                store.write("fleet-identity.json",dict(host=name,sets=dict(speed=sets),specification=json.loads((folder/"spec-pins.json").read_text()),
                    input_files={"states.pkl":"s"*64,"v1.pt":V1_SHA,"R3a.pt":STUDENT_SHA,"R3a-calibration.json":CALIBRATION_SHA},native_sha256=NATIVE_SHA,runtime_files={},measurement_files=files,
                    deadline_replay_semantics="committed-copy",nice=12,reporting_plan_sha256="p"*64,corpus_receipt_sha256="c"*64))
                store.write("fleet-complete.json",dict(repeats=3,completed=True,reporting_load_profile=True,outcome_access=False,live_actions=False))
                store.write("exactness-tiers.json",dict(passes=True,states=125,records=[dict(id=str(i),workers_equal=True,zero_budget_immutable=True,max_relative_difference={t:0. for t in ("K0c","K1","K2","K4")}) for i in range(125)]))
                store.write("belief-exactness.json",dict(passes=True,histories=125,posterior_weights_cumulative_ledger_samples_rng_exact=True,records=[dict(id=str(i),deadline_on=on,exact=True) for i in range(125) for on in (False,True)]))
                store.write("reporting-mhz-comparison.json",dict(passes=True))
                drift=1e-7 if name=="b" else 0.
                forwards={"S":dict(gate=.6+drift,legal=[1],ranks={"1":1.+drift}),
                    "K0c":dict(sample=1,top8=[1],probabilities=[.5+drift],log_probabilities=[-.7+drift]),"K2":None,"K4":None}
                refs={t:{i:dict(result=dict(action=1,candidates=[1],scores=[1.]),forward=forwards[t],wall_seconds=1.) for i in ids} for t,ids in sets.items()}
                refs["S"]["0"]["forward"]=dict(gate=THRESHOLD+(-1e-5 if name=="b" else 1e-5),legal=[1],ranks={"1":1.})
                store.write("speed-reference.json",refs)
                for row in data["speed"]:store.append("speed-reference-raw.jsonl",row)
                for row in data["deadlines"]:store.append("deadline-reference-raw.jsonl",row)
                store.seal("complete")
                entries.append(dict(directory=str(base/name),manifest_sha256=sha(base/name/"receipt-manifest.json")))
            request=base/"pool.json";request.write_text(json.dumps(dict(schema="clasher.e4v3.fleet-pool.v1",hosts=entries)))
            args=["--pool-fleet-references","--pool-input",str(request),"--pool-input-sha256",sha(request),"--output",str(base/"pool")]
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                self.assertEqual(main(args),0)
            receipt=json.loads((base/"pool/receipt-manifest.json").read_text());verify_files(base/"pool",receipt["files"])
            rates=json.loads((base/"pool/deadline-reference.json").read_text())["S"]["1.0"]
            self.assertEqual(rates["n"],1800);self.assertEqual(rates["counts"]["cutoff"],600)
            policies=json.loads((base/"pool/fleet-policy-agreement.json").read_text())
            self.assertEqual(policies["conditional_exemptions"]["b"]["S"],["0"])
            self.assertTrue(policies["native_common_scores_exact"])
            # A policy near-threshold exemption cannot excuse ANY common native score drift.
            speed_path=base/"b/speed-reference.json"
            changed=json.loads(speed_path.read_text());changed["S"]["0"]["result"]["scores"]=[1.000001]
            speed_path.write_text(json.dumps(changed))
            host_seal=base/"b/receipt-manifest.json";host_receipt=json.loads(host_seal.read_text())
            host_receipt["files"]["speed-reference.json"]=sha(speed_path)
            host_seal.write_text(json.dumps(host_receipt))
            entries[1]["manifest_sha256"]=sha(host_seal)
            request.write_text(json.dumps(dict(schema="clasher.e4v3.fleet-pool.v1",hosts=entries)))
            args[4]=sha(request);args[-1]=str(base/"native-mismatch-pool")
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                with self.assertRaisesRegex(ValueError,"ALL tiers fail"):main(args)
            self.assertEqual(json.loads((base/"native-mismatch-pool/receipt-manifest.json").read_text())["status"],"failed")
            (base/"a/speed-reference-raw.jsonl").write_text("tampered")
            args[-1]=str(base/"failed-pool")
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                with self.assertRaisesRegex(ValueError,"Pin mismatch"):main(args)
            self.assertEqual(json.loads((base/"failed-pool/receipt-manifest.json").read_text())["status"],"failed")

if __name__=="__main__":unittest.main()
