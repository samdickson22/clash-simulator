"""Checkpoint IPC stays outside decision timers and preserves raw failures."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fleet_reference import reference_monitor
from fleet_validity import GUARD_RULES,validate_blocks,validate_admission,classify_attempt
from receipts import ReceiptStore,verify_files


class ReferenceGuardControlTests(unittest.TestCase):
    def test_monitor_records_serial_begin_end_and_failure_before_ack(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);channel=MagicMock();channel.poll.return_value=True
                channel.recv.side_effect=[dict(event="admit",id="reference-admission",phase="reference-warmup"),
                                          dict(event="begin",id="speed-0-K0c-0",phase="reference-speed"),
                                          dict(event="end",id="speed-0-K0c-0",phase="reference-speed")]
                guard=MagicMock()
                def admission(row):
                    guard.latest=dict(passes=True,rules=GUARD_RULES,console=dict(positive=False),
                        memavailable_bytes=30*2**30,foreign_compute=[],foreign_active=[],ssh_family_sample=dict(stop=False))
                    return None
                def begin(identity):
                    guard.latest=dict(passes=True,rules=GUARD_RULES,ssh_family_sample=dict(stop=False))
                    return None
                def end(identity):
                    guard.latest=dict(passes=not fail,rules=GUARD_RULES,reason="ssh_family_interference" if fail else None,
                        completed_block=dict(id=identity,seconds=10.,ssh_family=dict(interfered=fail,stop=False)))
                    return guard.latest["reason"]
                guard.begin_block.side_effect=begin;guard.end_block.side_effect=end
                guard.side_effect=admission
                def monitor(*args):
                    control=args[-1]
                    control();control();control()
                with patch("fleet_reference.os.sched_setaffinity"),patch("fleet_validity.ReportingGuard",return_value=guard),patch("fleet_reference.monitor_worker",side_effect=monitor):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError,"checkpoint"):reference_monitor(None,None,[],{},folder/"capacity.jsonl",0,folder,{},channel)
                    else:reference_monitor(None,None,[],{},folder/"capacity.jsonl",0,folder,{},channel)
                rows=[json.loads(s) for s in (folder/"guard-blocks.jsonl").read_text().splitlines()]
                self.assertEqual([r["event"] for r in rows],["begin","end"])
                self.assertEqual(channel.send.call_count,3)
                self.assertTrue(validate_admission(json.loads((folder/"guard-admission.json").read_text()))["passes"])
                if fail:self.assertFalse(rows[-1]["reporting_guard"]["passes"])
                else:self.assertEqual(validate_blocks(rows,require_measurement=False)["blocks"],1)

    def test_failed_admission_is_recorded_and_classified_without_starting_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ReceiptStore(Path(tmp)/"attempt","FLEET-REFERENCE");folder=store.directory
            channel=MagicMock();channel.poll.return_value=True
            channel.recv.return_value=dict(event="admit",id="reference-admission",phase="reference-warmup")
            guard=MagicMock();guard.return_value="console_user"
            guard.latest=dict(passes=False,rules=GUARD_RULES,reason="console_user")
            with patch("fleet_reference.os.sched_setaffinity"),patch("fleet_validity.ReportingGuard",return_value=guard),patch("fleet_reference.monitor_worker",side_effect=lambda *args:args[-1]()):
                with self.assertRaisesRegex(RuntimeError,"console_user"):
                    reference_monitor(None,None,[],{},folder/"capacity.jsonl",0,folder,{},channel)
            guard.begin_block.assert_not_called()
            self.assertFalse(json.loads((folder/"guard-admission.json").read_text())["reporting_guard"]["passes"])
            store.write("failure.json",dict(error="Reference host admission failed",fleet_technical_cause="validity_census"));store.seal("failed")
            manifest=json.loads((folder/"receipt-manifest.json").read_text());verify_files(folder,manifest["files"])
            self.assertTrue(classify_attempt(folder,manifest)["technical_repeat_candidate"])


if __name__=="__main__":unittest.main()
