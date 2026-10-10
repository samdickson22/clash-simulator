"""Amendment 1 refuses hand selection, idle clocks and fleet near-exactness."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_end import evidence,host_reporting,pool_context
from fleet_validity import ReportingGuard,owned_tree,validity_reason,classify_attempt,validate_census,FleetTechnicalError
from fleet_profile import compare_mhz
from receipts import ReceiptStore,sha,verify_files
from measure_tiers import Session
from test_fleet_contract import end_fixture


class FleetEndTests(unittest.TestCase):
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
    def test_guard_loads_frozen_t1_op1_code_and_rejects_a_foreign_child_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/"t1-guard";root.mkdir();job=base/"job";job.mkdir()
            repository=Path(__file__).resolve().parents[7]
            t1=repository/"reports/explore/t1"
            names=("common.py","host_audit.py","idle_services.py","system_bus.py","ssh_transport.py")
            files={};frozen={}
            for name in names:
                (root/name).write_bytes((t1/name).read_bytes())
                files["t1-guard/"+name]=sha(root/name);frozen["reports/explore/t1/"+name]=sha(root/name)
            (base/"freeze.json").write_text(json.dumps(dict(files=frozen)))
            (base/"plan.json").write_text(json.dumps(dict(compute={})))
            command="/usr/bin/dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only"
            bus=dict(pid=200,ppid=0,pgid=200,start_ticks=99,cpu_ticks=0,uid=103,tty=0,exe="/usr/bin/dbus-daemon",exe_evidence="argv0 (proc/exe unreadable, unprivileged)",cmdline_sha256="d"*64,cmd=command,affinity=[0])
            admission=dict(identity={k:bus[k] for k in ("pid","start_ticks","exe","cmdline_sha256","uid")})
            for path in (job/"system-bus-admission.json",base/"bus.json"):path.write_text(json.dumps(admission))
            for name in ("freeze.json","plan.json","bus.json"):files[name]=sha(base/name)
            manifest=dict(files=files,reference_load_profile=dict(plan="plan.json",guard=dict(root="t1-guard",job=str(job),freeze="freeze.json",admissions={"system-bus-admission.json":"bus.json"})))
            own=dict(bus,pid=100,ppid=0,start_ticks=10,uid=1000,exe="/usr/bin/python3",cmd="python measure_tiers.py")
            child=dict(own,pid=101,ppid=100,start_ticks=11)
            foreign=dict(own,pid=300,ppid=0,start_ticks=12,cmd="python foreign.py")
            modules=("common","host_audit","system_bus","idle_services","ssh_transport")
            with patch.dict(sys.modules),patch.object(sys,"path",list(sys.path)):
                for name in modules:sys.modules.pop(name,None)
                guard=ReportingGuard(base,manifest,[100])
                guard.audit.processes=lambda:[dict(bus),dict(own),dict(child)]
                guard.audit.console=lambda:dict(positive=False)
                guard.audit.memory=lambda:30*2**30
                row={};self.assertIsNone(guard(row));self.assertTrue(row["reporting_guard"]["passes"])
                self.assertEqual(set(map(int,row["reporting_guard"]["owned_pid_start_ticks"])),{100,101})
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
        self.assertEqual(validity_reason([dict(tty=1)],[],dict(positive=True),2,1,60,30*2**30)[0],"console_over_one_core_60s")
        self.assertEqual(validity_reason([],[],good,0,1,0,30*2**30,True)[0],"op1_interference")
        with self.assertRaises(FleetTechnicalError):validate_census([dict(reporting_guard=dict(passes=False,reason="foreign_compute"))]*2)

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
