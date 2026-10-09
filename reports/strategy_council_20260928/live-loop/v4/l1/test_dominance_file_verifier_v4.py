import json,math,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from test_clock_free_records_v4 import records
from dominance_file_verifier_v4 import verify_d4,sha,VoidRecord,RecordFidelityFailure

class FileVerifierTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.pins={};self.messages=[]
  def put(name,value,jsonl=False):
   p=self.root/name;p.write_text(('\n'.join(json.dumps(x) for x in value)+'\n') if jsonl else json.dumps(value));self.pins[str(p)]=sha(p);return p
  self.put=put
  seal=put('body.json',{'schema':'clasher.v4.clock-free-body-seal.v1','epochs':{str(e):{'body_threshold':.5} for e in range(1,25)}})
  truth=[dict(episode='v',card='Knight',side=0,kind='troop',execution_timestamp_ms=0.)]
  bt=put('truth-bound.json',truth);mt=put('truth-measured.json',truth);mapping=put('mapping.json',{'source':'synthetic'})
  b=put('bound.json',dict(epoch=1,threshold=.1,body_threshold=.5,body_seal_sha256=sha(seal),truth_rows_sha256=sha(bt),opponent=dict(truth=1,predictions=1,matched=1)))
  frames=put('frames.jsonl',[dict(seq=0,produced_at=0.),dict(seq=1,produced_at=.1)],True)
  rec=put('records.jsonl',records(),True)
  peak=deepcopy(records()[0]['event_peaks'][0]);peak['available_timestamp_ms']=1.
  out=[dict(source_seq=i,payload=dict(episode_id='v',timestamp_ms=float(i*100),event_candidates=[peak] if i==0 else [])) for i in range(2)]
  outputs=put('outputs.jsonl',out,True)
  clocks=[dict(episode_id='v',source_seq=i,timestamp_ms=float(i*100),service_ms=1.,available_timestamp_ms=float(i*100+1)) for i in range(2)]
  completions=put('clocks.jsonl',clocks,True)
  self.kw=dict(bound_path=b,body_seal_path=seal,body_seal_sha256=sha(seal),episodes={'v':dict(frames=frames,records=rec,outputs=outputs,completions=completions)},bound_truth_path=bt,measured_truth_path=mt,truth_mapping_source=mapping,files_sha256=self.pins,spells=[],incident_path=self.root/'suspension.json',notify_coordinator=lambda p,r:self.messages.append((p,r)))
 def run_check(self):return verify_d4(**self.kw)
 def change_bound(self,**changes):
  p=self.kw['bound_path'];v=json.loads(p.read_text());v.update(changes);self.put(p.name,v)
 def test_actual_files_pass(self):
  r=self.run_check();self.assertTrue(r['available_at_least_frame_exact']);self.assertEqual(r['predictions'],1);self.assertFalse(r['selection_authorized'])
 def test_missing_seal_hash(self):
  self.change_bound(body_seal_sha256=None)
  with self.assertRaises(VoidRecord):self.run_check()
 def test_wrong_sealed_body(self):
  self.change_bound(body_threshold=.4)
  with self.assertRaises(VoidRecord):self.run_check()
 def test_equal_count_different_prediction_suspends_and_notifies(self):
  p=self.kw['episodes']['v']['outputs'];v=[json.loads(x) for x in p.read_text().splitlines()];v[0]['payload']['event_candidates'][0]['card']='Other';self.put(p.name,v,True)
  with self.assertRaises(RecordFidelityFailure):self.run_check()
  self.assertEqual(len(self.messages),1);self.assertTrue(self.messages[0][1]['elimination_suspended']);self.assertFalse(self.messages[0][1]['selection_allowed'])
 def test_identical_truth_values_different_bytes_fail(self):
  p=self.kw['measured_truth_path'];p.write_text(p.read_text()+'\n');self.pins[str(p)]=sha(p)
  with self.assertRaises(RecordFidelityFailure):self.run_check()
  self.assertEqual(len(self.messages),1)
 def test_available_one_ulp_below_stamp_rejected(self):
  p=self.kw['episodes']['v']['completions'];v=[json.loads(x) for x in p.read_text().splitlines()];v[1]['available_timestamp_ms']=math.nextafter(100.,-math.inf);self.put(p.name,v,True)
  with self.assertRaises(VoidRecord):self.run_check()
  self.assertFalse(self.messages)
 def test_bound_count_tamper(self):
  self.change_bound(opponent=dict(truth=1,predictions=1,matched=0))
  with self.assertRaises(VoidRecord):self.run_check()
 def test_truth_mapping_pin_required(self):
  del self.pins[str(self.kw['truth_mapping_source'])]
  with self.assertRaises(VoidRecord):self.run_check()
 def test_notifier_failure_cannot_continue(self):
  p=self.kw['measured_truth_path'];p.write_text('[]');self.pins[str(p)]=sha(p)
  def fail(*a):raise RuntimeError('notification failed')
  self.kw['notify_coordinator']=fail
  with self.assertRaises(RuntimeError):self.run_check()
  self.assertTrue(self.kw['incident_path'].exists())
if __name__=='__main__':unittest.main()
