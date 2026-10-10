"""Use reviewed T1 seed/join admission, including exact committed 08 proof."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_validity import GUARD_MODULES,ReportingGuard,validate_blocks,validate_census,FleetTechnicalError
from receipts import sha
from test_fleet_contract import guard_rows

REVIEWED_FREEZE = "aeeb3003d2a877bd7ff538a1977cbbc37adb404f"


def stage_guard(base):
    """Actual committed guard/seed bytes; synthetic local processes/admissions."""
    repository=Path(__file__).resolve().parents[7]
    def raw(commit,name):
        return subprocess.check_output(["git","-C",str(repository),"show",commit+":"+name])
    freeze_raw=raw(REVIEWED_FREEZE,"reports/explore/t1/FROZEN-T1.json")
    freeze=json.loads(freeze_raw);root=base/"t1-guard";root.mkdir();job=base/"job";job.mkdir()
    files={}
    for module in GUARD_MODULES:
        name=module+".py";(root/name).write_bytes(raw(REVIEWED_FREEZE,"reports/explore/t1/"+name))
        files["t1-guard/"+name]=sha(root/name)
    (base/"freeze.json").write_bytes(freeze_raw);(job/"FROZEN-T1.json").write_bytes(freeze_raw)
    seed_inputs={};receipts={}
    def stage(binding):
        name=binding["path"];data=raw(binding["commit"],name)
        source="seed-inputs/"+name
        for path in (base/source,job/"repo"/name):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        seed_inputs[name]=source;files[source]=sha(base/source)
        return json.loads(data)
    for binding in freeze["parent_source_seeds"]:
        receipt=stage(binding);receipts[receipt["host"]]=receipt
        for joined in receipt.get("source_join",{}).values():stage(joined)
    (base/"plan.json").write_text(json.dumps(dict(compute=dict(perception_io_exception=dict(host="127x03")))))
    command="/usr/bin/dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only"
    bus=dict(pid=200,ppid=0,pgid=200,start_ticks=99,cpu_ticks=0,uid=103,tty=0,exe="/usr/bin/dbus-daemon",exe_evidence="argv0 (proc/exe unreadable, unprivileged)",cmdline_sha256="d"*64,cmd=command,affinity=[0])
    admission=dict(identity={k:bus[k] for k in ("pid","start_ticks","exe","cmdline_sha256","uid")})
    for path in (job/"system-bus-admission.json",base/"bus.json"):path.write_text(json.dumps(admission))
    for name in ("freeze.json","plan.json","bus.json"):files[name]=sha(base/name)
    manifest=dict(files=files,reference_load_profile=dict(plan="plan.json",guard=dict(root="t1-guard",job=str(job),freeze="freeze.json",
        admissions={"system-bus-admission.json":"bus.json"},seed_inputs=seed_inputs)))
    return manifest,bus,job,receipts


@contextmanager
def fresh_modules():
    with patch.dict(sys.modules),patch.object(sys,"path",list(sys.path)):
        for name in GUARD_MODULES:sys.modules.pop(name,None)
        yield


def process_rows(bus,receipt):
    own=dict(bus,pid=100,ppid=0,start_ticks=10,uid=1000,exe="/usr/bin/python3",cmd="python measure_tiers.py")
    parent=dict(own,**receipt["parent"]);parent["cmd"]="sshd: "+os.environ.get("USER","sdicks02")+"@notty"
    return own,parent


class GuardSeedTests(unittest.TestCase):
    def test_seeded_childless_parent_is_admitted_before_census_once_on_03_and_08(self):
        for host in ("127x03","127x08"):
            with self.subTest(host=host),tempfile.TemporaryDirectory() as tmp,fresh_modules():
                base=Path(tmp);manifest,bus,job,receipts=stage_guard(base)
                guard=ReportingGuard(base,manifest,[100]);own,parent=process_rows(bus,receipts[host])
                guard.audit.processes=lambda:copy.deepcopy([bus,own,parent])
                guard.audit.console=lambda:dict(positive=False);guard.audit.memory=lambda:30*2**30
                original=guard.audit.census
                def census(*args,**kwargs):
                    self.assertEqual(guard.ssh.FAMILIES.sources[(str(job),guard.ssh.identity(parent))],receipts[host]["ssh_connection"])
                    return original(*args,**kwargs)
                guard.audit.census=census
                with patch.object(guard.seed.socket,"gethostname",return_value=host),patch.object(guard.seed,"admit",wraps=guard.seed.admit) as admit,patch.object(guard.seed,"joined_08",wraps=guard.seed.joined_08) as joined:
                    self.assertIsNone(guard({}));self.assertIsNone(guard({}));self.assertEqual(admit.call_count,1)
                    if host=="127x08":self.assertTrue(joined.called)
                accepted=json.loads((job/"parent-source-seed-admission.json").read_text())["accepted"]
                self.assertEqual(len(accepted),1);self.assertEqual(accepted[0]["parent"],receipts[host]["parent"])
                self.assertEqual(guard.latest["parent_source_seed_admission"],accepted)
                self.assertTrue(next(r for r in guard.previous if r["pid"]==parent["pid"])["ssh_budget"])

    def test_seed_does_not_refresh_changed_parent_generation_or_overwrite_conflict(self):
        for field in ("pid","start_ticks","uid","cmdline_sha256","ppid","pgid","conflict"):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp,fresh_modules():
                base=Path(tmp);manifest,bus,job,receipts=stage_guard(base)
                guard=ReportingGuard(base,manifest,[100]);own,parent=process_rows(bus,receipts["127x08"])
                if field=="conflict":guard.ssh.FAMILIES.sources[(str(job),guard.ssh.identity(parent))]=None
                else:parent[field]=parent[field]+"x" if isinstance(parent[field],str) else parent[field]+1
                guard.audit.processes=lambda:copy.deepcopy([bus,own,parent])
                guard.audit.console=lambda:dict(positive=False);guard.audit.memory=lambda:30*2**30
                with patch.object(guard.seed.socket,"gethostname",return_value="127x08"):guard({})
                self.assertFalse(guard.seed_accepted)
                self.assertFalse(next(r for r in guard.previous if r["pid"]==parent["pid"]).get("ssh_budget"))

    def test_pinned_freeze_and_seed_join_inputs_cannot_change(self):
        for case in ("freeze","bundle-seed","live-join","missing-join","unreviewed-op6"):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp,fresh_modules():
                base=Path(tmp);manifest,bus,job,receipts=stage_guard(base)
                cfg=manifest["reference_load_profile"]["guard"]
                client=receipts["127x08"]["source_join"]["client"]["path"]
                if case=="freeze":(job/"FROZEN-T1.json").write_text("changed")
                elif case=="bundle-seed":(base/next(iter(cfg["seed_inputs"].values()))).write_text("changed")
                elif case=="live-join":(job/"repo"/client).write_text("changed")
                elif case=="missing-join":del cfg["seed_inputs"][client]
                else:
                    p=base/"freeze.json";f=json.loads(p.read_text());f["operational_delta_op6"]["verdict"]="pending"
                    p.write_text(json.dumps(f));manifest["files"]["freeze.json"]=sha(p)
                with self.assertRaises(ValueError):ReportingGuard(base,manifest,[100])

    def test_self_repinned_08_join_still_requires_committed_t1_bytes(self):
        with tempfile.TemporaryDirectory() as tmp,fresh_modules():
            base=Path(tmp);manifest,bus,job,receipts=stage_guard(base)
            cfg=manifest["reference_load_profile"]["guard"];join=receipts["127x08"]["source_join"]["client"]
            source=base/cfg["seed_inputs"][join["path"]];obj=json.loads(source.read_text());obj["client_starttime"]+=1
            source.write_text(json.dumps(obj));(job/"repo"/join["path"]).write_bytes(source.read_bytes())
            changed=sha(source);manifest["files"][cfg["seed_inputs"][join["path"]]]=changed
            seed_name=next(n for n in cfg["seed_inputs"] if n.endswith("op5-parent-source-127x08.json"))
            p=base/cfg["seed_inputs"][seed_name];seed=json.loads(p.read_text());seed["source_join"]["client"]["sha256"]=changed
            p.write_text(json.dumps(seed));(job/"repo"/seed_name).write_bytes(p.read_bytes());seed_sha=sha(p)
            manifest["files"][cfg["seed_inputs"][seed_name]]=seed_sha
            f=json.loads((base/"freeze.json").read_text());f["files"][join["path"]]=changed;f["files"][seed_name]=seed_sha
            for binding in f["parent_source_seeds"]:
                if binding["path"]==seed_name:binding["sha256"]=seed_sha
            (base/"freeze.json").write_text(json.dumps(f));(job/"FROZEN-T1.json").write_bytes((base/"freeze.json").read_bytes())
            manifest["files"]["freeze.json"]=sha(base/"freeze.json")
            guard=ReportingGuard(base,manifest,[100]);own,parent=process_rows(bus,receipts["127x08"])
            guard.audit.processes=lambda:copy.deepcopy([bus,own,parent]);guard.audit.console=lambda:dict(positive=False);guard.audit.memory=lambda:30*2**30
            with patch.object(guard.seed.socket,"gethostname",return_value="127x08"),self.assertRaisesRegex(AssertionError,"committed bytes"):
                guard({})
            self.assertFalse(guard.seed_admitted);self.assertFalse(guard.ssh.FAMILIES.sources)

    def test_reference_stays_strict_for_dbus_flags_even_with_passing_label(self):
        rows=guard_rows();rows[1]["reporting_guard"]["completed_block"]["system_bus"]=dict(interfered=True)
        with self.assertRaisesRegex(FleetTechnicalError,"dbus"):validate_blocks(rows)
        g=dict(rows[0]["reporting_guard"],system_bus=dict(interfered=True))
        with self.assertRaisesRegex(FleetTechnicalError,"dbus"):validate_census([dict(reporting_guard=g)]*2)


if __name__=="__main__":unittest.main()
