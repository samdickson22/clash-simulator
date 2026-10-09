import copy,unittest
import evidence_recovery_a17_v4 as r
from test_evidence_recovery_a17_v4 import RecoveryTests as R,StressTests as S
class ReviewerRecovery(R):
 def test_old_receipt_on_reachable_host_refused(self):
  self.rec['replacement_qualifications'][0]['sha256']=r.OLD_QUAL
  with self.assertRaisesRegex(ValueError,'Fresh'):self.check()
 def test_approval_other_contract(self):
  self.approval['producer_contract_sha256']='other'
  with self.assertRaisesRegex(ValueError,'Owner'):self.check()
 def test_extra_out_of_scope_cell(self):
  self.new['cells'].append(dict(epoch=20,episode='v4-phase-a-1975100778',frames=1,reference_origin={}))
  with self.assertRaisesRegex(ValueError,'extra'):self.check()
 def test_view_changes_only_qualifications(self):
  rec=self.check();v=r.qualification_view(self.c,rec)
  a={k:x for k,x in v.items() if k!='qualification_receipts'};b={k:x for k,x in self.c.items() if k!='qualification_receipts'}
  self.assertEqual(a,b)
class ReviewerStress(S):
 def test_other_e1_cell_refused(self):
  ep='v4-phase-a-1975100799';self.cell['episode']=ep;self.plan['cells'][0]['episode']=ep
  self.originals[(1,ep)]=self.originals[(1,'v4-phase-a-1975100708')]
  with self.assertRaisesRegex(ValueError,'fixed cold-start'):self.run_stress()
 def test_stress_other_host_refused(self):
  self.spec['host']='127x02'
  with self.assertRaisesRegex(ValueError,'host08'):self.run_stress()
 def test_stress_plan_worker(self):
  self.stress['worker_sha256']='other'
  with self.assertRaisesRegex(ValueError,'worker'):self.run_stress()
if __name__=='__main__':unittest.main()
