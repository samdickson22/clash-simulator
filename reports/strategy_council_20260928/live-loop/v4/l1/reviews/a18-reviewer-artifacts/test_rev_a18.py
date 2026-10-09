"""Reviewer A18 probes (adversarial scenarios). Synthetic + real local IO under /tmp only."""
import copy,gzip,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import evidence_transport_a18_v4 as routes
import epoch_assembly_a18_v4 as asm
import production_audit_admission_a18_v4 as audits
import queue_audit_io_v4 as qio
H='a'*64
def h(b):return hashlib.sha256(b).hexdigest()

# ---------- P1: retired 02 unadmittable ----------
class Retired02(unittest.TestCase):
 def test_retained_source_refuses_02(self):
  inv=dict(schema='clasher.v4.closed-match-inventory.v1',timing_admitted=False,matches=[dict(epoch=6,episode='E',host='127x02',source='/mpac/sdicks02/jobs/clasher/x',frames=1,checkpoint_sha256='c')])
  a=dict(inventories={'I':dict(path='inv')},retained_producers={})
  with patch.object(asm,'pinned',return_value=inv):
   with self.assertRaisesRegex(ValueError,'retired'):asm.retained_source(dict(inventory_sha256='I',episode='E',frames=1),a,6,'c','b','/b')
 def _world(self):
  retired_inv=dict(matches=[dict(epoch=6,episode='E',host='127x02')])
  other_inv=dict(matches=[dict(epoch=6,episode='F',host='127x09')])
  a=dict(inventories={'R':dict(path='R'),'O':dict(path='O')})
  def pinned(path,pin):return {'R':retired_inv,'O':other_inv}[pin]
  state=dict(tasks={'e06-E':dict(status='verified_record_only')})
  return a,pinned,state
 def test_recovery_is_single_source_for_retired(self):
  a,pinned,state=self._world()
  with patch.object(asm,'pinned',side_effect=pinned),patch('retained_recovery_a18_v4.retirement',return_value=({}, {'e06-E'})):
   asm.unique_source(dict(kind='queue',episode='E'),a,6,state)  # exactly one: recovery queue
   with self.assertRaises(ValueError):asm.unique_source(dict(kind='retained',episode='E',inventory_sha256='R'),a,6,state)
 def test_routes_refuse_02_source_even_with_receipt(self):
  src='/mpac/sdicks02/jobs/clasher/late.json'
  rec=dict(schema='clasher.v4.owned-evidence-member-copy.v1',source_host='127x02',destination_host='127x03',destination_directory=routes.DEST+'m/127x02',files_sha256={src:H},checksum_verified=True,fsync_complete=True,source_deletion=False,timing_admitted=False)
  man=dict(schema='clasher.v4.owned-evidence-routes.a18-v1',timing_admitted=False,copy_receipts={H:dict(path='c')},members=[dict(source_host='127x02',source_path=src,destination_host='127x03',destination_path=routes.DEST+'m/127x02'+src,sha256=H,copy_receipt_sha256=H)])
  with patch.object(routes,'pinned',side_effect=[man,rec]):
   with self.assertRaises(ValueError):routes.Routes(dict(path='m',sha256=H))

# ---------- P2: no first-wins ----------
class FirstWins(unittest.TestCase):
 def test_two_retained_candidates(self):
  inv=dict(matches=[dict(epoch=3,episode='E',host='127x09')])
  a=dict(inventories={'A':dict(path='A'),'B':dict(path='B')})
  with patch.object(asm,'pinned',return_value=inv),patch('retained_recovery_a18_v4.retirement',return_value=({},set())):
   with self.assertRaises(ValueError):asm.unique_source(dict(kind='retained',episode='E',inventory_sha256='A'),a,3,dict(tasks={}))
 def test_retained_plus_queue(self):
  inv=dict(matches=[dict(epoch=3,episode='E',host='127x09')])
  a=dict(inventories={'A':dict(path='A')})
  with patch.object(asm,'pinned',return_value=inv),patch('retained_recovery_a18_v4.retirement',return_value=({},set())):
   with self.assertRaises(ValueError):asm.unique_source(dict(kind='queue',episode='E'),a,3,dict(tasks={'e03-E':dict(status='verified_record_only')}))
 def test_population_duplicate(self):
  eps={'e%d'%i:1 for i in range(64)}
  ent=[dict(episode='e%d'%i,kind='queue',producer_type='original',frames=1) for i in range(64)];ent[1]=dict(ent[0])
  with self.assertRaises(ValueError):asm.population(ent,eps)
 def test_duplicate_destination_collapse(self):
  """Two source members routed to one destination: is it refused, and does hashes() verify both pins?"""
  A='/mpac/sdicks02/repos/clasher-lease/jobs/a.py';B='/mpac/sdicks02/repos/clasher-lease/jobs/b.py';D=routes.DEST+'m/same.py'
  X='1'*64;Y='2'*64
  rec=dict(schema='clasher.v4.retained-original-archive-copy.v1',checksum_verified=True,fsync_complete=True,source_deletion=False,timing_admitted=False,source_host='127x09',destination_host='127x03',source_directory='/mpac/sdicks02/repos/clasher-lease/jobs',destination_directory=routes.DEST+'m',files_sha256={'a.py':X})
  rec2=dict(rec,source_directory='/mpac/sdicks02/repos/clasher-lease/jobs',files_sha256={'b.py':Y})
  # route both to D via two receipts with distinct relative names is impossible; use same relative name in different source dirs
  rec=dict(rec,source_directory='/mpac/sdicks02/repos/clasher-lease/jobs/s1',files_sha256={'same.py':X})
  rec2=dict(rec,source_directory='/mpac/sdicks02/repos/clasher-lease/jobs/s2',files_sha256={'same.py':Y})
  A='/mpac/sdicks02/repos/clasher-lease/jobs/s1/same.py';B='/mpac/sdicks02/repos/clasher-lease/jobs/s2/same.py'
  man=dict(schema='clasher.v4.owned-evidence-routes.a18-v1',timing_admitted=False,copy_receipts={'r1':dict(path='1'),'r2':dict(path='2')},
   members=[dict(source_host='127x09',source_path=A,destination_host='127x03',destination_path=D,sha256=X,copy_receipt_sha256='r1'),
            dict(source_host='127x09',source_path=B,destination_host='127x03',destination_path=D,sha256=Y,copy_receipt_sha256='r2')])
  def pinned(spec):return {'m':man,'1':rec,'2':rec2}[spec['path']]
  calls=[]
  with patch.object(routes,'pinned',side_effect=pinned),patch.object(qio,'hashes',side_effect=lambda host,pins:calls.append((host,dict(pins)))):
   try:
    with routes.routed(dict(path='m',sha256=H)):qio.hashes('127x09',{A:X,B:Y})
   except ValueError:return  # refused: fine
  verified={p for _,d in calls for p in d.values()}
  self.assertEqual(verified,{X,Y},'routed hashes() silently dropped a pin (last-wins): %r'%calls)

# ---------- P3: relocated member with one byte changed (real local IO) ----------
class ByteChange(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.mkdtemp(prefix='a18rev-',dir='/tmp/sdicks02-a18rev');root=self.d+'/'
  self.json_src='/mpac/sdicks02/repos/clasher-lease/jobs/c/controller.json';self.gz_src='/mpac/sdicks02/repos/clasher-lease/jobs/c/body-1/E-decoder.jsonl.gz';self.code_src='/mpac/sdicks02/repos/clasher-lease/jobs/c/w.py'
  self.blob=json.dumps({'owner':'x'}).encode();self.gz=gzip.compress(b'{"a":1}\n',mtime=0);self.code=b'print(1)\n'
  self.files={self.json_src:self.blob,self.gz_src:self.gz,self.code_src:self.code}
  self.dest={s:root+'127x09'+s for s in self.files}
  for s,b in self.files.items():
   p=Path(self.dest[s]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  rec=dict(schema='clasher.v4.owned-evidence-member-copy.v1',source_host='127x09',destination_host='127x03',destination_directory=root+'127x09',files_sha256={s:h(b) for s,b in self.files.items()},checksum_verified=True,fsync_complete=True,source_deletion=False,timing_admitted=False)
  man=dict(schema='clasher.v4.owned-evidence-routes.a18-v1',timing_admitted=False,copy_receipts={'r':dict(path='r')},members=[dict(source_host='127x09',source_path=s,destination_host='127x03',destination_path=self.dest[s],sha256=h(b),copy_receipt_sha256='r') for s,b in self.files.items()])
  self.p=[patch.object(routes,'pinned',side_effect=lambda spec:{'m':man,'r':rec}[spec['path']]),patch.object(routes,'DEST',root),patch.object(qio,'ROOTS',qio.ROOTS+(root,)),patch.object(qio,'local',lambda host:True)]
  for x in self.p:x.start()
 def tearDown(self):
  for x in self.p:x.stop()
  import shutil;shutil.rmtree(self.d)
 def flip(self,s):
  p=Path(self.dest[s]);b=bytearray(p.read_bytes());b[len(b)//2]^=1;p.write_bytes(bytes(b))
 def test_unchanged_passes(self):
  with routes.routed(dict(path='m',sha256=H)):
   self.assertEqual(qio.read('127x09',self.json_src,h(self.blob))[0],{'owner':'x'})
   qio.hashes('127x09',{self.code_src:h(self.code)})
   with qio.records('127x09',self.gz_src,h(self.gz)) as f:f.read()
 def test_json_byte_change_pinned(self):
  self.flip(self.json_src)
  with routes.routed(dict(path='m',sha256=H)):
   with self.assertRaises(Exception):qio.read('127x09',self.json_src,h(self.blob))
 def test_json_byte_change_unpinned_caller(self):
  """queue_output_audit reads controller/launch/outcome with expected=None."""
  p=Path(self.dest[self.json_src]);p.write_bytes(p.read_bytes().replace(b'"x"',b'"y"'))  # one byte, still valid JSON
  with routes.routed(dict(path='m',sha256=H)):
   with self.assertRaises(ValueError):qio.read('127x09',self.json_src)
 def test_code_byte_change(self):
  self.flip(self.code_src)
  with routes.routed(dict(path='m',sha256=H)):
   with self.assertRaises(Exception):qio.hashes('127x09',{self.code_src:h(self.code)})
 def test_record_byte_change(self):
  self.flip(self.gz_src)
  with routes.routed(dict(path='m',sha256=H)):
   with self.assertRaises(Exception):
    with qio.records('127x09',self.gz_src,h(self.gz)) as f:f.read()
 def test_leased_unrouted_control_file(self):
  with routes.routed(dict(path='m',sha256=H)):
   with self.assertRaisesRegex(ValueError,'lacks owned route'):qio.read('127x13','/mpac/sdicks02/repos/clasher-lease/jobs/c/controller.json')
 def test_io_restored(self):
  saved=(qio.read,qio.hashes,qio.records)
  with routes.routed(dict(path='m',sha256=H)):pass
  self.assertEqual(saved,(qio.read,qio.hashes,qio.records))

# ---------- P4: R16 enforcement ----------
class R16(unittest.TestCase):
 HOSTS=['127x09','127x13','127x14','127x15']
 def setUp(self):
  self.reports=[];self.files={};self.selected=[];self.tasks={};self.proofs={}
  for i,host in enumerate(self.HOSTS):
   cid='c%d'%i;tid='e%02d-E%d'%(i+1,i);ps='p%d'%i
   cell=dict(claim_id=cid,task_id=tid,proof_sha256=ps,epoch=i+1,episode='E%d'%i,frames=2,checkpoint_sha256='k%d'%i,reference='/r%d'%i,output='/o%d'%i,complete_sha256='cs',
     reference_copy_receipt=dict(host=host,path='/cp%d'%i,sha256='x'),reference_origin=dict(host='127x08',directory='/d%d'%i,claim_id=cid,proof_sha256=ps),proof=dict(files={}))
   self.selected.append(dict(claim_id=cid,task_id=tid,epoch=i+1))
   self.files[(host,'/rep%d'%i)]=dict(pass_nonclock=True,timing_admitted=False,selection_admitted=False,cells=[cell],plan_sha256='pl')
   self.files[(host,'/plan%d'%i)]=dict(pins={'/w':audits.ORIGINAL},worker='/w',cells=[dict(claim_id=cid)])
   self.files[(host,'/cp%d'%i)]=dict(schema='clasher.v4.r16-selected-reference-copy.v1',claim_id=cid,source_host='127x08',source_directory='/d%d'%i,destination_host=host,destination_directory='/r%d'%i,independent_proof_sha256=ps,records_sha256={},fsynced=True)
   self.files[(host,'/o%d/complete.json'%i)]=dict(capture_worker_sha256=audits.ORIGINAL,clock_status='INVALID_RECORD_ONLY',episodes={'E%d'%i:2},files_sha256={'manifest.json':'m'})
   self.files[(host,'/o%d/manifest.json'%i)]=dict(epoch=i+1,checkpoint_sha256='k%d'%i)
   self.reports.append(dict(host=host,report='/rep%d'%i,report_sha256='rs',plan='/plan%d'%i))
   self.tasks[tid]=dict(status='verified_record_only',current=dict(claim_id=cid),independent_verification=dict(path='proof%d'%i,sha256=ps))
   self.proofs['proof%d'%i]=dict(worker_sha256=audits.VECTOR,host='127x08',directory='/d%d'%i,records_sha256={})
  self.dense=[]
 def run_gate(self):
  spec=dict(schema='clasher.v4.r16-admission-evidence.a18-v1',timing_admitted=False,original_audits=self.reports,fixed_dense={})
  state=dict(tasks=self.tasks)
  def pinned(s):return spec if s.get('path')=='r16' else state if s.get('path')=='state' else self.proofs[s['path']]
  def read(host,name,expected=None):return copy.deepcopy(self.files[(host,name)]),'x'
  with patch.object(audits,'pinned',side_effect=pinned),patch.object(audits,'exact_selection',return_value=self.selected),patch.object(audits.io,'read',side_effect=read),patch.object(audits.io,'hashes'),patch.object(audits,'check_branches'),patch.object(audits,'verify_dense',side_effect=lambda *a:self.dense.append(1)):
   audits.verify_r16(dict(r16_audits=dict(path='r16'),queue_state='state',queue_state_sha256='s'))
 def test_valid_world(self):self.run_gate();self.assertEqual(self.dense,[1])
 def test_missing_pass(self):
  self.files[('127x14','/rep2')]['pass_nonclock']=False
  with self.assertRaises(ValueError):self.run_gate()
 def test_missing_report(self):
  del self.reports[3]
  with self.assertRaises(ValueError):self.run_gate()
 def test_duplicate_report_for_one_claim(self):
  self.files[('127x15','/rep3')]=copy.deepcopy(self.files[('127x09','/rep0')]);self.files[('127x15','/plan3')]=copy.deepcopy(self.files[('127x09','/plan0')])
  with self.assertRaises(Exception):self.run_gate()
 def test_stress_failure_blocks(self):
  spec_err=ValueError('stress')
  with patch.object(audits,'verify_dense',side_effect=spec_err):
   with self.assertRaises(ValueError):
    spec=dict(schema='clasher.v4.r16-admission-evidence.a18-v1',timing_admitted=False,original_audits=self.reports,fixed_dense={})
    state=dict(tasks=self.tasks)
    def pinned(s):return spec if s.get('path')=='r16' else state if s.get('path')=='state' else self.proofs[s['path']]
    with patch.object(audits,'pinned',side_effect=pinned),patch.object(audits,'exact_selection',return_value=self.selected),patch.object(audits.io,'read',side_effect=lambda h,n,e=None:(copy.deepcopy(self.files[(h,n)]),'x')),patch.object(audits.io,'hashes'),patch.object(audits,'check_branches'):
     audits.verify_r16(dict(r16_audits=dict(path='r16'),queue_state='state',queue_state_sha256='s'))
 def test_original_worker_required(self):
  self.files[('127x09','/o0/complete.json')]['capture_worker_sha256']=audits.VECTOR
  with self.assertRaises(ValueError):self.run_gate()

if __name__=='__main__':unittest.main()
