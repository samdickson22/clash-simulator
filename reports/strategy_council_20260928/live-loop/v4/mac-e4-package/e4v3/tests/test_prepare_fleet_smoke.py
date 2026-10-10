"""Offline A6 staging: retain approved bytes, no timing, unpoolable output."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_fleet_contract import end_fixture
from prepare_fleet_smoke import prepare
from fleet_end import evidence,pool_context
from receipts import TIERS,sha,verify_files


def source_fixture(base):
    bundle,manifest,plan,end=end_fixture(base,hosts=("127x01","127x03"))
    folder=Path(__file__).resolve().parents[1]
    manifest.update(profile="fleet-reference",sets=dict(golden=["g"+str(i) for i in range(125)],
        speed={tier:[tier+str(i) for i in range(300)] for tier in TIERS}),
        measurement_files={p.name:sha(p) for p in folder.iterdir() if p.suffix in (".py",".sh") or p.name=="spec-pins.json"})
    (bundle/"tiers-pins.json").write_text(json.dumps(manifest))
    return bundle,manifest,plan


class PrepareFleetSmokeTests(unittest.TestCase):
    def test_stage_preserves_all_original_input_bytes_and_rejects_production_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source,original,plan=source_fixture(base)
            source_sha=sha(source/"tiers-pins.json")
            output=base/"staged"
            result=prepare(source,source_sha,output)
            self.assertEqual(sha(source/"tiers-pins.json"),source_sha)
            verify_files(source,original["files"])
            verify_files(output/"bundle",original["files"])
            manifest=json.loads((output/"bundle/tiers-pins.json").read_text())
            self.assertEqual(result,sha(output/"bundle/tiers-pins.json"))
            self.assertNotEqual(result,source_sha)
            smoke_plan=json.loads((output/"bundle/_a6/plan.json").read_text())
            self.assertEqual(smoke_plan["profile"],"e4v3-unpoolable-smoke")
            self.assertEqual(manifest["sets"],original["sets"])
            self.assertEqual(manifest["reference_load_profile"]["slot_count"],original["reference_load_profile"]["slot_count"])
            self.assertEqual(manifest["measurement_files"],original["measurement_files"])
            self.assertEqual(evidence(output/"bundle",manifest,smoke_plan)["kind"],"unpoolable-smoke")
            report=[json.loads(s) for s in (output/"bundle/_a6/reporting-mhz.jsonl").read_text().splitlines()]
            self.assertEqual(report[0]["source_utc"],"0")
            self.assertTrue(all(row["synthetic"] for row in report))
            self.assertTrue(all(v["mhz"]==2000. for row in report for v in row["physical_core_mhz"]))
            receipt=json.loads((output/"receipt-manifest.json").read_text());verify_files(output,receipt["files"])
            self.assertEqual(receipt["status"],"complete")
            self.assertFalse(json.loads((output/"staging.json").read_text())["measurement_started"])
            with self.assertRaisesRegex(ValueError,"cannot be pooled"):
                pool_context(dict(context=dict(bundle=str(output/"bundle"),manifest_sha256=result),hosts=[dict(host="127x01")]))

    def test_stage_refuses_wrong_sha_host_missing_tier_and_tamper_with_failure_receipt(self):
        for failure in ("sha","host","missing-tier-state","tamper"):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);source,manifest,_=source_fixture(base)
                if failure=="host":manifest["reference_load_profile"]["host"]="127x03"
                elif failure=="missing-tier-state":manifest["sets"]["speed"]["K4"].pop()
                (source/"tiers-pins.json").write_text(json.dumps(manifest))
                expected=sha(source/"tiers-pins.json")
                if failure=="sha":expected="0"*64
                elif failure=="tamper":(source/"states.pkl").write_bytes(b"altered")
                output=base/"failed"
                with self.assertRaises(ValueError):prepare(source,expected,output)
                receipt=json.loads((output/"receipt-manifest.json").read_text());verify_files(output,receipt["files"])
                self.assertEqual(receipt["status"],"failed")
                self.assertFalse(json.loads((output/"failure.json").read_text())["measurement_started"])


if __name__=="__main__":unittest.main()
