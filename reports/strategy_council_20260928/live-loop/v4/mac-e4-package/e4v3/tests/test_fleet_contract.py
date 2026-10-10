"""Public corpus admission, reporting masks and mechanical raw pooling."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import shutil
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
from fleet_end import evidence,host_reporting
from fleet_validity import GUARD_RULES


def guard_rows():
    ssh=dict(cpu_ticks=0,cpu_seconds=0.,core_fraction=0.,interfered=False,stop=False,processes=[])
    guard=dict(passes=True,rules=GUARD_RULES,ssh_family_sample=dict(stop=False,core_fraction=0.))
    identities=["warm-0-K0c-0"]
    identities.extend(f"speed-{repeat}-{tier}-{offset}" for repeat in range(3) for tier in TIERS for offset in range(0,300,50))
    identities.extend(f"deadline-{repeat}-{tier}-{cell}-{offset}" for repeat in range(3) for tier in TIERS for cell in ("1.0","0.8") for offset in range(0,300,50))
    return [dict(id=identity,event=event,reporting_guard=dict(guard,**({"completed_block":dict(id=identity,seconds=10.,ssh_family=ssh)} if event=="end" else {})))
            for identity in identities for event in ("begin","end")]


def end_fixture(base, hosts=("a","b")):
    """Synthetic committed health-only objects; proves bindings, never qualification."""
    repo=base/"source-repo";repo.mkdir();bundle=base/"context";bundle.mkdir()
    compute=dict(hosts={h:dict(physical_cpus=list(range(10)),census_cpu=10) for h in hosts},
        nice=10,scheduler="SCHED_OTHER",slots=2,console_slots=2,slot_width=5,smt=False)
    plan=dict(compute=compute)
    (bundle/"plan.json").write_text(json.dumps(plan))
    completion=dict(reporting_complete=True,outcomes_sealed=True,counted_primary_blocks=2400,counted_guard_blocks=600,
        completed_at_utc="2026-10-10T01:00:00Z",counted_host_phases={h:["reporting"] for h in hosts})
    counted=[]
    for pop,count in (("primary",2400),("guard",600)):
        for i in range(count):
            host=hosts[i%len(hosts)]
            counted.append(dict(host=host,phase="reporting",descriptor=dict(id=f"{pop}-{i:04d}",population=pop,host=host)))
    sources={"blind-ledger.json":dict(sealed=True,events=[]),
        "counted-inventory.json":dict(schema="clasher.t1.counted-blocks.v1",outcomes_sealed=True,blocks=counted)};phases=[]
    for host in hosts:
        values=dict(launch=dict(host=host,phase="reporting",slots=2),
            supervisor_exit=dict(host=host,reason=None,completed=[r["descriptor"] for r in counted if r["host"]==host],failed=[],unstarted=[],utc="2026-10-10T00:59:00Z"),
            mhz=[dict(utc=str(i),slots=2,physical_core_mhz=[dict(cpu=c,mhz=2000.) for c in range(10)]) for i in range(2)],
            census=[dict(host=host,utc=str(i),inflight=2,reason=None) for i in range(2)])
        phase=dict(host=host,phase="reporting")
        for key,value in values.items():
            name=host+"-"+key+(".jsonl" if isinstance(value,list) else ".json")
            sources[name]=value;phase[key]=dict(path=name,repository_path=name)
        phases.append(phase)
    completion.update(blind_ledger_sha256=__import__("hashlib").sha256(json.dumps(sources["blind-ledger.json"]).encode()).hexdigest(),
        counted_inventory_sha256=__import__("hashlib").sha256(json.dumps(sources["counted-inventory.json"]).encode()).hexdigest())
    sources["completion.json"]=completion
    for name,value in sources.items():
        raw=("\n".join(json.dumps(v) for v in value)+"\n") if isinstance(value,list) else json.dumps(value)
        (repo/name).write_text(raw);(bundle/name).write_text(raw)
    def git(*args):
        return subprocess.check_output(["git","-C",str(repo),*args],stderr=subprocess.DEVNULL,text=True).strip()
    git("init");git("add","--",*sources)
    git("-c","user.name=E4 unit fixture","-c","user.email=e4-fixture@example.invalid","commit","-m","Synthetic END evidence fixture")
    commit=git("rev-parse","HEAD")
    for phase in phases:
        for key in ("launch","supervisor_exit","mhz","census"):
            phase[key].update(commit=commit,sha256=sha(bundle/phase[key]["path"]))
    inv=dict(schema="clasher.e4v3.end-evidence.v1",kind="counted-reporting",repository=str(repo),
        completion=dict(path="completion.json",repository_path="completion.json",commit=commit,sha256=sha(bundle/"completion.json")),phases=phases,
        blind_ledger=dict(path="blind-ledger.json",repository_path="blind-ledger.json",commit=commit,sha256=sha(bundle/"blind-ledger.json")),
        counted_inventory=dict(path="counted-inventory.json",repository_path="counted-inventory.json",commit=commit,sha256=sha(bundle/"counted-inventory.json")))
    (bundle/"end.json").write_text(json.dumps(inv))
    folder=Path(__file__).resolve().parents[1]
    amendment=folder.parent.parent/"PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md"
    (bundle/"amendment.md").write_bytes(amendment.read_bytes())
    (bundle/"states.pkl").write_bytes(b"synthetic pool corpus identity")
    profile=dict(plan="plan.json",end_evidence="end.json",amendment="amendment.md",host=hosts[0],
        slot_count=2,console_rule=False,reference_slot=0,warmup_seconds=300,perception="none")
    manifest=dict(files={p.name:sha(p) for p in bundle.iterdir()},reference_load_profile=profile)
    (bundle/"tiers-pins.json").write_text(json.dumps(manifest))
    return bundle,manifest,plan,evidence(bundle,manifest,plan)


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
        reporting=[dict(slots=11,inflight=11,physical_core_mhz=[dict(cpu=i,mhz=2000.) for i in range(55)]) for _ in range(2)]
        reference=[dict(phase="reference-speed",cpu_clock_mhz_by_processor={str(c):2020. for c in range(64)},per_cpu_idle={str(c):.1 for c in range(64)}) for _ in range(2)]
        result=compare_mhz(reporting,reference,list(range(55)),11)
        self.assertTrue(result["passes"]);self.assertAlmostEqual(result["reference_to_reporting_mean"],1.01)
        reference[0]["cpu_clock_mhz_by_processor"]={str(c):2300. for c in range(64)}
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
        with self.assertRaisesRegex(ValueError,"counted hosts cannot be excluded"):
            pool_rows({"a":host_rows([1.]*3),"b":host_rows([1.02]*3),"slow":host_rows([1.2]*3)},min_states=1,end_mode=True)

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
            bundle,context,plan,end=end_fixture(base)
            for name in ("a","b"):
                data=host_rows([1.]*3,states=300)
                store=ReceiptStore(base/name,"FLEET-REFERENCE")
                sets={t:[str(i) for i in range(300)] for t in TIERS}
                folder=Path(__file__).resolve().parents[1]
                files={p.name:sha(p) for p in folder.iterdir() if p.suffix in (".py",".sh") or p.name=="spec-pins.json"}
                store.write("fleet-identity.json",dict(host=name,sets=dict(speed=sets),specification=json.loads((folder/"spec-pins.json").read_text()),
                    input_files={"states.pkl":context["files"]["states.pkl"],"v1.pt":V1_SHA,"R3a.pt":STUDENT_SHA,"R3a-calibration.json":CALIBRATION_SHA},native_sha256=NATIVE_SHA,runtime_files={},measurement_files=files,
                    load_profile=dict(context["reference_load_profile"],host=name),search_cpus=list(range(5)),background_masks=[list(range(5,10))],utc=1.,
                    end_kind="counted-reporting",end_evidence_sha256=end["sha256"],counted_hosts=["a","b"],
                    deadline_replay_semantics="committed-copy",nice=10,reporting_plan_sha256=sha(bundle/"plan.json"),corpus_receipt_sha256="c"*64))
                store.write("fleet-complete.json",dict(repeats=3,completed=True,reporting_load_profile=True,outcome_access=False,live_actions=False,poolable=True,exactness_class="EXACT"))
                store.write("reference-warmup.json",dict(seconds=300.,all_slots_active=True,all_background_slots=1,reference_slot_work={t:300 for t in TIERS}))
                store.write("exactness-tiers.json",dict(passes=True,states=125,records=[dict(id=str(i),workers_equal=True,zero_budget_immutable=True,max_relative_difference={t:0. for t in ("K0c","K1","K2","K4")}) for i in range(125)]))
                store.write("belief-exactness.json",dict(passes=True,histories=125,posterior_weights_cumulative_ledger_samples_rng_exact=True,records=[dict(id=str(i),deadline_on=on,exact=True,max_relative_difference=0.) for i in range(125) for on in (False,True)]))
                census=[dict(phase="reference-speed",cpu_clock_mhz_by_processor={str(c):2000. for c in range(10)},per_cpu_idle={str(c):.1 for c in range(10)},reporting_guard=dict(passes=True,rules=GUARD_RULES,ssh_family_sample=dict(stop=False))) for _ in range(2)]
                for row in census:store.append("capacity.jsonl",row)
                store.write("guard-admission.json",dict(reporting_guard=dict(passes=True,rules=GUARD_RULES,
                    console=dict(positive=False),memavailable_bytes=30*2**30,foreign_compute=[],foreign_active=[],ssh_family_sample=dict(stop=False))))
                for row in guard_rows():store.append("guard-blocks.jsonl",row)
                store.write("reporting-mhz-comparison.json",compare_mhz(host_reporting(end,dict(context["reference_load_profile"],host=name),plan),census,list(range(10)),2))
                drift=1e-7 if name=="b" else 0.
                forwards={"S":dict(gate=.6+drift,legal=[1],ranks={"1":1.+drift}),
                    "K0c":dict(sample=1,top8=[1],probabilities=[.5+drift],log_probabilities=[-.7+drift]),"K2":None,"K4":None}
                refs={t:{i:dict(result=dict(action=1,candidates=[1],scores=[1.]),forward=forwards[t],wall_seconds=1.) for i in ids} for t,ids in sets.items()}
                refs["S"]["0"]["forward"]=dict(gate=THRESHOLD+(-1e-5 if name=="b" else 1e-5),legal=[1],ranks={"1":1.})
                store.write("speed-reference.json",refs)
                for row in data["speed"]:store.append("speed-reference-raw.jsonl",row)
                for row in data["deadlines"]:store.append("deadline-reference-raw.jsonl",row)
                store.seal("complete")
                entries.append(dict(host=name,attempts=[dict(directory=str(base/name),manifest_sha256=sha(base/name/"receipt-manifest.json"))]))
            descriptor=dict(schema="clasher.e4v3.fleet-pool.v2",context=dict(bundle=str(bundle),manifest_sha256=sha(bundle/"tiers-pins.json")),hosts=entries)
            request=base/"pool.json";request.write_text(json.dumps(descriptor))
            args=["--pool-fleet-references","--pool-input",str(request),"--pool-input-sha256",sha(request),"--output",str(base/"pool")]
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                self.assertEqual(main(args),0)
            receipt=json.loads((base/"pool/receipt-manifest.json").read_text());verify_files(base/"pool",receipt["files"])
            rates=json.loads((base/"pool/deadline-reference.json").read_text())["S"]["1.0"]
            self.assertEqual(rates["n"],1800);self.assertEqual(rates["counts"]["cutoff"],600)
            policies=json.loads((base/"pool/fleet-policy-agreement.json").read_text())
            self.assertEqual(policies["conditional_exemptions"]["b"]["S"],["0"])
            self.assertTrue(policies["native_common_scores_exact"])
            # A hand-picked passing host cannot hide another counted host.
            descriptor["hosts"]=entries[:1];request.write_text(json.dumps(descriptor))
            args[4]=sha(request);args[-1]=str(base/"missing-counted-host")
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                with self.assertRaisesRegex(ValueError,"ALL counted"):main(args)
            descriptor["hosts"]=entries
            # Every failed attempt is source-sealed, typed and ordered. Use the
            # first passing attempt; a repeat after success is rejected.
            failed=base/"a-attempt0";shutil.copytree(base/"a",failed)
            identity_path=failed/"fleet-identity.json";identity=json.loads(identity_path.read_text());identity["utc"]=.5;identity_path.write_text(json.dumps(identity))
            failure_path=failed/"failure.json";failure_path.write_text(json.dumps(dict(error="MHz gate",fleet_technical_cause="mhz_gate")))
            clock_path=failed/"reporting-mhz-comparison.json";clock=json.loads(clock_path.read_text());clock["passes"]=False;clock_path.write_text(json.dumps(clock))
            seal_path=failed/"receipt-manifest.json";attempt=json.loads(seal_path.read_text());attempt["status"]="failed"
            for p in (identity_path,failure_path,clock_path):attempt["files"][p.name]=sha(p)
            seal_path.write_text(json.dumps(attempt))
            first=dict(directory=str(failed),manifest_sha256=sha(seal_path))
            entries[0]["attempts"].insert(0,first);request.write_text(json.dumps(descriptor));args[4]=sha(request);args[-1]=str(base/"technical-repeat-pool")
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                self.assertEqual(main(args),0)
            pooled=json.loads((base/"technical-repeat-pool/pooling.json").read_text())
            self.assertTrue(pooled["attempts"]["a"][0]["technical_repeat_candidate"])
            entries[0]["attempts"].reverse();request.write_text(json.dumps(descriptor));args[4]=sha(request);args[-1]=str(base/"repeat-after-pass")
            with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                with self.assertRaisesRegex(ValueError,"passing first"):main(args)
            entries[0]["attempts"]=[entries[0]["attempts"][0]]
            # Cross-host nice, fixed slot, warmup, and bit-exact score tolerances
            # are checked by the real CLI after resealing the changed fixture.
            good_identity=base/"b/fleet-identity.json";saved_identity=good_identity.read_bytes()
            good_native=base/"b/exactness-tiers.json";saved_native=good_native.read_bytes()
            good_seal=base/"b/receipt-manifest.json";saved_seal=json.loads(good_seal.read_text())
            cases=("nice","slot","warmup","native-near")
            for case in cases:
                identity=json.loads(saved_identity);native=json.loads(saved_native)
                if case=="nice":identity["nice"]=12
                elif case=="slot":identity["load_profile"]["reference_slot"]=1
                elif case=="warmup":identity["load_profile"]["warmup_seconds"]=299
                else:native["records"][0]["max_relative_difference"]["K4"]=5e-13
                good_identity.write_text(json.dumps(identity));good_native.write_text(json.dumps(native))
                host_receipt=copy.deepcopy(saved_seal);host_receipt["files"][good_identity.name]=sha(good_identity);host_receipt["files"][good_native.name]=sha(good_native)
                good_seal.write_text(json.dumps(host_receipt));entries[1]["attempts"][0]["manifest_sha256"]=sha(good_seal)
                request.write_text(json.dumps(descriptor));args[4]=sha(request);args[-1]=str(base/("fails-"+case))
                with patch.dict("os.environ",{k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}):
                    with self.assertRaises(ValueError):main(args)
            good_identity.write_bytes(saved_identity);good_native.write_bytes(saved_native);good_seal.write_text(json.dumps(saved_seal))
            entries[1]["attempts"][0]["manifest_sha256"]=sha(good_seal)
            # A policy near-threshold exemption cannot excuse ANY common native score drift.
            speed_path=base/"b/speed-reference.json"
            changed=json.loads(speed_path.read_text());changed["S"]["0"]["result"]["scores"]=[1.000001]
            speed_path.write_text(json.dumps(changed))
            host_seal=base/"b/receipt-manifest.json";host_receipt=json.loads(host_seal.read_text())
            host_receipt["files"]["speed-reference.json"]=sha(speed_path)
            host_seal.write_text(json.dumps(host_receipt))
            entries[1]["attempts"][0]["manifest_sha256"]=sha(host_seal)
            request.write_text(json.dumps(descriptor))
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
