"""Independent reviewer data mutants for A16 (reviewer-only, /tmp)."""
import copy,json,unittest
from unittest.mock import patch
import test_producer_contract_a16_v4 as tp
import test_vectorized_queue_audit_a16_v4 as ta
import test_queue_source_a16_v4 as tq
import test_assembly_entries_a16_v4 as te
import epoch_assembly_a16_v4 as a
import vectorized_producer_contract_a16_v4 as c
from match_queue_v4 import durable,sha

class Qual(tp.QualificationTests):
 def test_R1_one_byte_vectorized_record(self):
  cell=self.cells[1];name=sorted(cell['proof']['files'])[4];k=cell['output']+'/'+name
  row=self.rows[k][0];i=row.index(b'"bodies": [')+len(b'"bodies": [');row=row[:i]+bytes([row[i]^1])+row[i+1:];self.rows[k]=[row]
  with self.assertRaisesRegex(ValueError,'raw record'):self.run_check()
 def test_R1b_one_byte_whitespace_only(self):
  cell=self.cells[0];name=sorted(cell['proof']['files'])[0];k=cell['output']+'/'+name
  self.rows[k]=[self.rows[k][0].replace(b', ',b',',1)]
  with self.assertRaisesRegex(ValueError,'raw record'):self.run_check()
 def test_R2_identical_availability_in_both(self):
  cell=self.cells[0];name=sorted(cell['proof']['files'])[0]
  for side in (cell['reference'],cell['output']):
   k=side+'/'+name;v=json.loads(self.rows[k][0]);v['available_timestamp_ms']=1;self.rows[k]=[(json.dumps(v)+'\n').encode()]
  with self.assertRaises(ValueError):self.run_check()
 def test_R5_worker_pin_swap(self):
  self.contract['worker_sha256']='w'*64;self.contract['source_sha256']={'vec.py':'w'*64}
  with self.assertRaisesRegex(ValueError,'worker differs'):self.run_check()
 def test_R5b_source_closure_swap(self):
  self.contract['source_sha256']['vectorized_decoder_v4.py']='d'*64
  with self.assertRaisesRegex(ValueError,'source pin differs'):self.run_check()
 def test_R6_drop_qualification_receipt(self):
  self.contract['qualification_receipts']=[]
  with self.assertRaisesRegex(ValueError,'All three'):self.run_check()
 def test_R6b_drop_cell_708(self):
  self.report['cells']=[x for x in self.report['cells'] if x['episode']!='v4-phase-a-1975100708']
  self.plan['cells']=[x for x in self.plan['cells'] if x['episode']!='v4-phase-a-1975100708']
  with self.assertRaisesRegex(ValueError,'All three'):self.run_check()

class Audit(ta.VectorAuditTests):
 def test_R3_selfconsistent_divergent_production_record_IS_ADMITTED(self):
  # By design: a fresh production match has no original reference. A vectorized
  # record that differs from the original producer's bytes but is internally
  # consistent passes the per-match audit. Equivalence rests on A14 + 3 cells.
  self.row['bodies']=[{'divergent':True}];r=self.run_audit();self.assertEqual(r['producer_type'],'vectorized')
 def test_R5c_unqualified_host_worker(self):
  self.plan['source_sha256'][self.plan['worker']]='w'*64
  with self.assertRaises(ValueError):
   self.contract['source_sha256'][self.contract['worker_name']]='v'*64;self.plan['source_sha256'][self.plan['worker'].rsplit('/',1)[0]+'/'+self.contract['worker_name']]='w'*64;self.run_audit()
 def test_R5d_complete_written_by_other_worker(self):
  self.complete['capture_worker_sha256']='w'*64
  with self.assertRaises(ValueError):self.run_audit()
 def test_R5e_task_worker_original(self):
  self.task['worker_sha256']=ta.audit.WORKER
  with self.assertRaises(ValueError):self.run_audit()

class Source(tq.QueueSourceTests):
 def test_R7_vectorized_output_relabelled_original(self):
  self.prepare_source();del self.claim['task']['producer_type']
  with self.assertRaises(ValueError):self.check_source()
 def test_R7b_overlay_qualification_not_in_contract(self):
  self.prepare_source();self.overlay['qualification']={'sha256':'other'}
  with self.assertRaisesRegex(ValueError,'qualification binding'):self.check_source()

class Entries(te.AssemblyEntryTests):
 def test_R4_original_retained_dup_in_two_inventories(self):
  ep=self.entries[0]['episode']
  for n in ('i1','i2'):
   f=self.root/(n+'.json');durable(f,dict(matches=[dict(epoch=7,episode=ep)],tag=n));self.auth['inventories'][sha(f)]={'path':str(f)}
  self.state['tasks'].pop('e07-'+ep);self.entries[0].update(kind='retained',producer_type='original',inventory_sha256=next(iter(self.auth['inventories'])))
  with self.assertRaisesRegex(ValueError,'Exactly one'):self.call()
 def test_R4b_retained_plus_vectorized_queue(self):
  f=self.root/'inv.json';ep=self.entries[1]['episode'];durable(f,dict(matches=[dict(epoch=7,episode=ep)]));self.auth['inventories'][sha(f)]={'path':str(f)}
  self.assertEqual(self.entries[1]['producer_type'],'vectorized')
  with self.assertRaisesRegex(ValueError,'Exactly one'):self.call()
 def test_R4c_duplicate_entry_same_match(self):
  self.entries[1]=dict(self.entries[0],producer_type='vectorized')
  with self.assertRaises(ValueError):self.call()

class Closure(unittest.TestCase):
 def test_R8_live_state_differs_from_pinned_closure(self):
  snap={'plan_sha256':'b','suspended':False,'tasks':{}};live=dict(snap,generation=2)
  def pin(p,d):return live if str(p).endswith('state.json') and 'live' in str(p) else snap
  with patch.object(a,'pinned',side_effect=pin):
   with self.assertRaisesRegex(ValueError,'Live queue differs'):a.verify_queue_closure(dict(queue_state='/snap',queue_state_sha256='s',live_queue_root='/live',queue_plan='/p',queue_plan_sha256='b'))
if __name__=='__main__':unittest.main()
