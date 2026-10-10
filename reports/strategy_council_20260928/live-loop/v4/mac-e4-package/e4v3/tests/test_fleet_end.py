"""Amendment 1 refuses hand selection, idle clocks and fleet near-exactness."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_end import evidence,host_reporting,pool_context,counting
from fleet_validity import ReportingGuard,owned_tree,validity_reason,classify_attempt,validate_census,validate_blocks,FleetTechnicalError,GUARD_MODULES
from fleet_profile import compare_mhz
from receipts import ReceiptStore,sha,verify_files
from measure_tiers import Session
from test_fleet_contract import end_fixture,guard_rows


class FleetEndTests(unittest.TestCase):
    def test_stopped_counted_phase_raw_exits_and_blind_redispatch_remain_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,manifest,plan,end=end_fixture(Path(tmp),hosts=("127x01","127x03","127x08"))
            inv=copy.deepcopy(end["inventory"]);completion=copy.deepcopy(end["completion"])
            phase=end["phases"][("127x08","reporting")]
            exit_=phase["supervisor_exit"]
            lost=exit_["completed"].pop(0);lost["cell"]=2
            queued=exit_["completed"].pop(0)
            exit_.update(reason="owned_STOP",failed=[lost],unstarted=[queued])
            phase["census"][-1]["reason"]="owned_STOP"
            replacement=dict(lost,id="primary-2402",replaces=lost["id"])
            ledger=dict(sealed=True,events=[dict(lost=lost,replacement={k:v for k,v in replacement.items() if k!="host"},evidence_sha256="pending")])
            counted=copy.deepcopy(end["counted_inventory"])
            for row in counted["blocks"]:
                if row["descriptor"]["id"] in (lost["id"],queued["id"]):
                    row.update(phase="replacement-r1")
                    if row["descriptor"]["id"]==lost["id"]:row["descriptor"]=replacement
            fresh=dict(host="127x08",phase="replacement-r1")
            values=dict(launch=dict(host="127x08",phase="replacement",slots=2),
                supervisor_exit=dict(host="127x08",reason=None,completed=[replacement,queued],failed=[],unstarted=[],utc="2026-10-10T00:59:30Z"),
                mhz=copy.deepcopy(phase["mhz"]),census=[dict(r,reason=None) for r in phase["census"]])
            inv["phases"].append(fresh);completion["counted_host_phases"]["127x08"].append("replacement-r1")
            repo=Path(inv["repository"])
            def write(name,value,lines=False):
                raw="\n".join(json.dumps(r) for r in value)+"\n" if lines else json.dumps(value)
                (bundle/name).write_text(raw);(repo/name).write_text(raw);manifest["files"][name]=sha(bundle/name)
            for entry in inv["phases"]:
                source=values if entry is fresh else end["phases"][(entry["host"],entry["phase"])]
                for field in ("launch","supervisor_exit","mhz","census"):
                    if entry is fresh:
                        name="08-replacement-"+field+(".jsonl" if field in ("mhz","census") else ".json")
                        entry[field]=dict(path=name,repository_path=name)
                    write(entry[field]["path"],source[field],field in ("mhz","census"))
            ledger["events"][0]["evidence_sha256"]=sha(bundle/"127x08-supervisor_exit.json")
            for field,value in (("blind_ledger",ledger),("counted_inventory",counted)):
                write(inv[field]["path"],value);completion[field+"_sha256"]=sha(bundle/inv[field]["path"])
            write("completion.json",completion)
            paths=[x["path"] for entry in inv["phases"] for x in (entry[f] for f in ("launch","supervisor_exit","mhz","census"))]
            paths.extend(inv[f]["path"] for f in ("completion","blind_ledger","counted_inventory"))
            subprocess.run(["git","-C",str(repo),"add","--",*paths],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(["git","-C",str(repo),"-c","user.name=E4 unit fixture","-c","user.email=e4-fixture@example.invalid","commit","-m","Synthetic stopped END fixture"],check=True,stdout=subprocess.DEVNULL)
            commit=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
            for item in [inv[f] for f in ("completion","blind_ledger","counted_inventory")]+[entry[f] for entry in inv["phases"] for f in ("launch","supervisor_exit","mhz","census")]:
                item.update(commit=commit,sha256=sha(bundle/item["path"]))
            (bundle/"end.json").write_text(json.dumps(inv));manifest["files"]["end.json"]=sha(bundle/"end.json")
            checked=evidence(bundle,manifest,plan)
            self.assertEqual(checked["counted_hosts"],["127x01","127x03","127x08"])
            self.assertEqual(checked["phases"][("127x08","reporting")]["supervisor_exit"],exit_)
            self.assertEqual(len(host_reporting(checked,dict(manifest["reference_load_profile"],host="127x08"),plan)),4)
            for case in ("lost-counted","no-ledger","missing-block","wrong-phase","wrong-exit-hash","unknown-field"):
                counts={f:copy.deepcopy(checked[f]) for f in ("blind_ledger","counted_inventory")}
                if case=="lost-counted":counts["counted_inventory"]["blocks"][2]["descriptor"]=lost
                elif case=="no-ledger":counts["blind_ledger"]["events"]=[]
                elif case=="missing-block":counts["counted_inventory"]["blocks"].pop()
                elif case=="wrong-phase":counts["counted_inventory"]["blocks"][2]["phase"]="reporting"
                elif case=="wrong-exit-hash":counts["blind_ledger"]["events"][0]["evidence_sha256"]="0"*64
                else:counts["counted_inventory"]["blocks"][0]["descriptor"]["outcome"]=0
                with self.subTest(case=case),self.assertRaises(ValueError):counting(counts,completion,checked["phases"])

    def test_committed_bytes_not_only_self_declared_sha_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,manifest,plan,end=end_fixture(Path(tmp))
            path=bundle/"completion.json"
            completion=json.loads(path.read_text());completion["counted_primary_blocks"]=2399
            path.write_text(json.dumps(completion));manifest["files"][path.name]=sha(path)
            obj=copy.deepcopy(end["inventory"]);obj["completion"]["sha256"]=sha(path)
            (bundle/"end.json").write_text(json.dumps(obj));manifest["files"]["end.json"]=sha(bundle/"end.json")
            with self.assertRaisesRegex(ValueError,"committed T1 bytes"):
                evidence(bundle,manifest,plan)

    def test_missing_counted_host_phase_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,manifest,plan,end=end_fixture(Path(tmp))
            obj=copy.deepcopy(end["inventory"]);obj["phases"].pop()
            (bundle/"end.json").write_text(json.dumps(obj));manifest["files"]["end.json"]=sha(bundle/"end.json")
            with self.assertRaisesRegex(ValueError,"Missing counted"):
                evidence(bundle,manifest,plan)

    def test_full_occupancy_join_excludes_ramp_and_drain_and_rejects_missing_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,manifest,plan,end=end_fixture(Path(tmp))
            profile=manifest["reference_load_profile"]
            phase=end["phases"][("a","reporting")]
            idle_clock=dict(phase["mhz"][0],utc="idle",physical_core_mhz=[dict(cpu=c,mhz=4000.) for c in range(10)])
            phase["mhz"].append(idle_clock)
            phase["census"].append(dict(host="a",utc="idle",inflight=1,reason=None))
            report=host_reporting(end,profile,plan)
            self.assertEqual(len(report),2)
            self.assertTrue(all(r["inflight"]==2 for r in report))
            phase["census"].pop()
            with self.assertRaisesRegex(ValueError,"join"):
                host_reporting(end,profile,plan)

    def test_registered_slot_and_launch_slots_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,manifest,plan,end=end_fixture(Path(tmp))
            profile=manifest["reference_load_profile"]
            with self.assertRaisesRegex(ValueError,"slot zero"):
                host_reporting(end,dict(profile,reference_slot=1),plan)
            with self.assertRaisesRegex(ValueError,"slot count"):
                host_reporting(end,dict(profile,slot_count=3),plan)

    def test_pool_context_requires_all_counted_hosts_and_refuses_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,manifest,plan,end=end_fixture(Path(tmp))
            request=dict(context=dict(bundle=str(bundle),manifest_sha256=sha(bundle/"tiers-pins.json")),hosts=[dict(host="a")])
            with self.assertRaisesRegex(ValueError,"ALL counted"):
                pool_context(request)
            request["hosts"].append(dict(host="b"));pool_context(request)
            obj=end["inventory"];obj["kind"]="unpoolable-smoke"
            (bundle/"end.json").write_text(json.dumps(obj))
            plan["profile"]="e4v3-unpoolable-smoke";(bundle/"plan.json").write_text(json.dumps(plan))
            for key in ("end.json","plan.json"):manifest["files"][key]=sha(bundle/key)
            (bundle/"tiers-pins.json").write_text(json.dumps(manifest));request["context"]["manifest_sha256"]=sha(bundle/"tiers-pins.json")
            with self.assertRaisesRegex(ValueError,"cannot be pooled"):
                pool_context(request)

    def test_processor_id_clock_mapping_ignores_list_order(self):
        report=[dict(slots=2,inflight=2,physical_core_mhz=[dict(cpu=c,mhz=2000.) for c in (3,7)])]*2
        reference=[dict(phase="reference-speed",cpu_clock_mhz_by_processor={"7":2020.,"3":2020.,"0":9000.},per_cpu_idle={"7":.1,"3":.1})]*2
        self.assertAlmostEqual(compare_mhz(report,reference,[7,3],2)["reference_to_reporting_mean"],1.01)
        with self.assertRaisesRegex(ValueError,"full-occupancy"):
            compare_mhz([dict(report[0],inflight=1)]*2,reference,[7,3],2)


class FleetValidityTests(unittest.TestCase):
    def test_guard_loads_frozen_final_t1_code_and_enforces_op4_and_foreign_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/"t1-guard";root.mkdir();job=base/"job";job.mkdir()
            repository=Path(__file__).resolve().parents[7]
            names=tuple(m+".py" for m in GUARD_MODULES)
            files={};frozen={}
            for name in names:
                # The shared checkout can contain another worker's unfinished
                # guard delta. Exercise the coordinator-named OP-4 candidate,
                # not WIP; actual measurement requires its final frozen pins.
                raw=subprocess.check_output(["git","-C",str(repository),"show",
                    "cb1b9f128d0dc9aeda2f357c425e71ba9c0e7980:reports/explore/t1/"+name])
                (root/name).write_bytes(raw)
                files["t1-guard/"+name]=sha(root/name);frozen["reports/explore/t1/"+name]=sha(root/name)
            (base/"freeze.json").write_text(json.dumps(dict(files=frozen)))
            (base/"plan.json").write_text(json.dumps(dict(compute=dict(perception_io_exception=dict(host="127x03")))))
            command="/usr/bin/dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only"
            bus=dict(pid=200,ppid=0,pgid=200,start_ticks=99,cpu_ticks=0,uid=103,tty=0,exe="/usr/bin/dbus-daemon",exe_evidence="argv0 (proc/exe unreadable, unprivileged)",cmdline_sha256="d"*64,cmd=command,affinity=[0])
            admission=dict(identity={k:bus[k] for k in ("pid","start_ticks","exe","cmdline_sha256","uid")})
            for path in (job/"system-bus-admission.json",base/"bus.json"):path.write_text(json.dumps(admission))
            for name in ("freeze.json","plan.json","bus.json"):files[name]=sha(base/name)
            manifest=dict(files=files,reference_load_profile=dict(plan="plan.json",guard=dict(root="t1-guard",job=str(job),freeze="freeze.json",admissions={"system-bus-admission.json":"bus.json"})))
            own=dict(bus,pid=100,ppid=0,start_ticks=10,uid=1000,exe="/usr/bin/python3",cmd="python measure_tiers.py")
            child=dict(own,pid=101,ppid=100,start_ticks=11)
            foreign=dict(own,pid=300,ppid=0,start_ticks=12,cmd="python foreign.py")
            modules=GUARD_MODULES
            with patch.dict(sys.modules),patch.object(sys,"path",list(sys.path)):
                for name in modules:sys.modules.pop(name,None)
                for name in ("perception_confirmation.py","owned_supervisor.py","ssh_budget.py"):
                    raw=(root/name).read_bytes();(root/name).write_bytes(raw+b"\n# unpinned change\n")
                    with self.subTest(module=name),self.assertRaisesRegex(ValueError,"frozen final T1 source"):
                        ReportingGuard(base,manifest,[100])
                    (root/name).write_bytes(raw)
                guard=ReportingGuard(base,manifest,[100])
                guard.audit.processes=lambda:[dict(bus),dict(own),dict(child)]
                guard.audit.console=lambda:dict(positive=False)
                guard.audit.memory=lambda:30*2**30
                row={};self.assertIsNone(guard(row));self.assertTrue(row["reporting_guard"]["passes"])
                self.assertEqual(set(map(int,row["reporting_guard"]["owned_pid_start_ticks"])),{100,101})
                self.assertFalse(guard.audit.own_process(job,dict(child,start_ticks=999)))
                # Frozen Families proves the source-bound LAN tree. Its CPU is
                # measured by the real frozen per-block meters, not exempted.
                parent=dict(own,pid=20,ppid=1,pgid=20,start_ticks=20,uid=3822945,
                    cmd="sshd: "+__import__("os").environ.get("USER","sdicks02")+"@notty",cpu_ticks=0)
                lan=dict(parent,pid=21,ppid=20,start_ticks=21,cmd="python /arbitrary-child.py",
                    ssh_connection_snapshot="129.65.221.14 30000 129.65.221.13 22",
                    ssh_family_parent_snapshot=[parent[k] for k in ("pid","start_ticks","uid","cmdline_sha256")])
                guard.audit.processes=lambda:[dict(bus),dict(own),dict(child),dict(parent),dict(lan)]
                clock=[100.]
                with patch("fleet_validity.time.monotonic",lambda:clock[0]):
                    self.assertIsNone(guard.begin_block("inclusive"))
                    parent["cpu_ticks"]=5;clock[0]=110.
                    self.assertIsNone(guard.end_block("inclusive"))
                    self.assertFalse(guard.latest["completed_block"]["ssh_family"]["interfered"])
                    self.assertIsNone(guard.begin_block("flagged"))
                    parent["cpu_ticks"]=11;clock[0]=120.
                    self.assertEqual(guard.end_block("flagged"),"ssh_family_interference")
                    self.assertFalse(guard.latest["passes"])
                    self.assertIsNone(guard.begin_block("average-stop"))
                    parent["cpu_ticks"]=32;clock[0]=130.
                    self.assertEqual(guard.end_block("average-stop"),"ssh_family_average_budget")
                    self.assertIsNone(guard.begin_block("sample-stop"))
                    guard.sample_previous=guard.previous;guard.sample_last=130.
                    parent["cpu_ticks"]=58;clock[0]=131.
                    self.assertEqual(guard({}),"ssh_family_sample_budget")
                    self.assertEqual(guard.end_block("sample-stop"),"ssh_family_sample_budget")
                    guard.ssh_sample=dict(cpu_ticks=0,seconds=1.,core_fraction=0.,stop=False)
                guard.audit.console=lambda:dict(positive=True)
                self.assertEqual(guard({}),"console_user")
                guard.audit.console=lambda:dict(positive=False)
                guard.audit.processes=lambda:[dict(bus),dict(own),dict(child),dict(foreign)]
                row={};self.assertEqual(guard(row),"foreign_compute")
                self.assertFalse(row["reporting_guard"]["passes"])
                # A silently refreshed system-bus identity is refused even if
                # the source allowlist would admit the new process.
                (job/"system-bus-admission.json").write_text("changed")
                with self.assertRaisesRegex(ValueError,"identity changed"):guard({})

    def test_background_exactness_survives_cleanup_errors(self):
        from replay_load import FleetBackground
        import queue
        load=object.__new__(FleetBackground)
        load.errors=queue.Queue();load.errors.put(dict(error="Exactness mismatch: public sampled opponent"))
        load.stop=MagicMock();load.stop.is_set.return_value=False
        worker=MagicMock();worker.pid=100;worker.is_alive.return_value=False;worker.exitcode=1
        load.workers=[worker]
        with self.assertRaisesRegex(RuntimeError,"Exactness mismatch"):
            try:load.check()
            except RuntimeError:
                load.close()  # Suppresses secondary exitcode failure only.
                raise
        worker.join.assert_called_once()

    def test_pid_start_identity_and_descendants_own_spawn_helpers(self):
        known={}
        rows=[dict(pid=1,ppid=0,start_ticks=10),dict(pid=2,ppid=1,start_ticks=11),dict(pid=3,ppid=2,start_ticks=12),dict(pid=4,ppid=0,start_ticks=13)]
        self.assertEqual(owned_tree(rows,{1},known),{1,2,3})
        rows[0]["start_ticks"]=99;rows[1]["ppid"]=0
        self.assertNotIn(1,owned_tree(rows,{1},known))

    def test_reporting_stop_rules_memory_foreign_console_and_op1(self):
        good=dict(positive=False)
        self.assertEqual(validity_reason([],[],good,0,1,0,24*2**30)[0],None)
        self.assertEqual(validity_reason([],[],good,0,1,0,24*2**30-1)[0],"memory_floor")
        self.assertEqual(validity_reason([dict(tty=0)],[],good,0,1,0,30*2**30)[0],"foreign_compute")
        self.assertEqual(validity_reason([], [dict(tty=0)],good,0,1,0,30*2**30)[0],"foreign_active")
        self.assertEqual(validity_reason([],[],dict(positive=True),0,1,0,30*2**30)[0],"console_user")
        self.assertEqual(validity_reason([],[],good,0,1,0,30*2**30,True)[0],"op1_interference")
        with self.assertRaises(FleetTechnicalError):validate_census([dict(reporting_guard=dict(passes=False,reason="foreign_compute"))]*2)

    def test_pool_requires_complete_unflagged_work_block_budgets(self):
        rows=guard_rows();self.assertEqual(validate_blocks(rows)["blocks"],217)
        for case in ("flagged","incomplete","missing-speed","missing-warmup","old-census"):
            with self.subTest(case=case):
                changed=copy.deepcopy(rows)
                if case=="flagged":changed[1]["reporting_guard"]["completed_block"]["ssh_family"]["interfered"]=True
                elif case=="incomplete":changed.pop()
                elif case=="missing-speed":del changed[2:4]
                elif case=="missing-warmup":del changed[:2]
                else:
                    with self.assertRaisesRegex(FleetTechnicalError,"OP-4"):validate_census([dict(reporting_guard=dict(passes=True))]*2)
                    continue
                with self.assertRaises(FleetTechnicalError):validate_blocks(changed)

    def test_pool_refuses_passing_label_with_console_or_budget_stop(self):
        from fleet_validity import GUARD_RULES
        for case in ("console","sample","average"):
            g=dict(passes=True,rules=GUARD_RULES,ssh_family_sample=dict(stop=False))
            if case=="console":g["console"]=dict(positive=True)
            elif case=="sample":g["ssh_family_sample"]["stop"]=True
            else:g["ssh_family_blocks"]={"b":dict(stop=True)}
            with self.subTest(case=case),self.assertRaisesRegex(FleetTechnicalError,"Contradictory"):
                validate_census([dict(reporting_guard=g)]*2)

    def test_fleet_classifier_requires_evidence_and_never_repeats_exactness(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            for name,error,cause,evidence_,expected in (
                ("mhz","MHz gate","mhz_gate",{"passes":False},True),
                ("unsupported","a traceback","mhz_gate",{"passes":True},False),
                ("exact","Exactness mismatch in background","crash",None,False),
                ("untyped","generic traceback",None,None,False)):
                store=ReceiptStore(base/name,"FLEET-REFERENCE")
                store.write("failure.json",dict(error=error,fleet_technical_cause=cause))
                if evidence_ is not None:store.write("reporting-mhz-comparison.json",evidence_)
                store.seal("failed")
                receipt=json.loads((base/name/"receipt-manifest.json").read_text());verify_files(base/name,receipt["files"])
                self.assertEqual(classify_attempt(base/name,receipt)["technical_repeat_candidate"],expected)

    def test_fleet_native_near_exact_is_rejected_before_any_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle=Path(tmp);reference=dict(action=1,candidates=[1],scores=[1.])
            (bundle/"golden.json").write_text(json.dumps({"a":reference}))
            backend=MagicMock();backend.by_id={"a":{}}
            backend.golden.return_value=dict(reference,scores=[1.+5e-13])
            session=SimpleNamespace(args=SimpleNamespace(bundle=bundle,fleet_reference=True),manifest=dict(sets=dict(golden=["a"])),backend=backend,store=MagicMock(),exactness_class="EXACT")
            with self.assertRaisesRegex(ValueError,"fleet bit-exact"):
                Session.exactness(session)
            backend.zero_budget.assert_not_called();session.store.write.assert_not_called()

    def test_fleet_posterior_near_exact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle=Path(tmp);score=dict(action=1,candidates=[1],scores=[1.])
            ref=dict(arrays={},ledger={},events=[],samples=[],rng={},derived=dict(weight=1.))
            (bundle/"golden.json").write_text(json.dumps({"a":score}))
            (bundle/"belief-reference.json").write_text(json.dumps({"a":ref}))
            backend=MagicMock();backend.by_id={"a":dict(info=SimpleNamespace(events=[]))};backend.golden.return_value=score
            backend.belief_result.return_value=dict(ref,derived=dict(weight=1.+5e-13))
            session=SimpleNamespace(args=SimpleNamespace(bundle=bundle,fleet_reference=True),manifest=dict(sets=dict(golden=["a"])),backend=backend,store=MagicMock(),exactness_class="EXACT")
            with self.assertRaisesRegex(ValueError,"fleet bit-exact belief"):
                Session.exactness(session)


if __name__=="__main__":unittest.main()
