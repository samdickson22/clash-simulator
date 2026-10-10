import json,os,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
import admission

class Tests(unittest.TestCase):
    def test_release_receipt_and_evidence_required(self):
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1/tmp') as directory:
            j=Path(directory);fake=dict(host='127x03',affinity=[0],nice=10,scheduler=os.SCHED_OTHER)
            with patch('admission.context',return_value=fake),patch('admission.active_conflicts',return_value=[]):
                self.assertFalse(admission.allowed(j))
                evidence=j/'CPU-RELEASE-EVIDENCE.json';evidence.write_text('{"explicit":true}')
                receipt=j/'CPU-RELEASE-ADMITTED.json';r=dict(explicit_release=True,host='127x03',release_evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),vacated_pgids=[]);receipt.write_text(json.dumps(r))
                admission._conflict_cache_time=0;self.assertTrue(admission.allowed(j))
                evidence.write_text('{"changed":true}');self.assertFalse(admission.allowed(j))
    def test_nice_scheduler_host_affinity_stop_and_conflicts(self):
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1/tmp') as directory:
            j=Path(directory);evidence=j/'CPU-RELEASE-EVIDENCE.json';evidence.write_text('{}');r=dict(explicit_release=True,host='127x03',release_evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),vacated_pgids=[]);(j/'CPU-RELEASE-ADMITTED.json').write_text(json.dumps(r))
            fake=dict(host='127x03',affinity=[0],nice=10,scheduler=os.SCHED_OTHER)
            with patch('admission.context',return_value=fake),patch('admission.active_conflicts',return_value=[{'pid':1}]):
                admission._conflict_cache_time=0;self.assertFalse(admission.allowed(j))
                for change in ({'nice':19},{'host':'127x09'},{'affinity':[60]},{'scheduler':os.SCHED_IDLE}):
                    with patch('admission.context',return_value={**fake,**change}):self.assertFalse(admission.allowed(j))
                (j/'REPORTING.STOP').touch();self.assertFalse(admission.allowed(j))
if __name__=='__main__':unittest.main()
