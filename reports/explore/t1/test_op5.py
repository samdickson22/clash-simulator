"""OP-5 data-only identity/source seed; OP-4 budgets remain authoritative."""
import copy,json,subprocess
from pathlib import Path
import pytest
import parent_source_seed as S
import ssh_budget as B
from common import sha,write
from test_op4 import parent,child

@pytest.fixture
def admission(tmp_path,monkeypatch):
 j=tmp_path/'job';repo=j/'repo';repo.mkdir(parents=True)
 def git(*args):return subprocess.check_output(['git','-C',str(repo),*args]).decode().strip()
 git('init','-q');git('config','user.name','Synthetic Test');git('config','user.email','test@example.invalid')
 p=parent();connection='129.65.221.14 12345 129.65.221.13 22'
 receipt=dict(schema='clasher.t1.parent-source-seed.v1',host='127x03',parent={k:p[k] for k in S.FIELDS},source_ip=S.SOURCE,ssh_connection=connection)
 name='reports/explore/t1/receipts/synthetic-source.json';write(repo/name,receipt)
 git('add','--',name);git('commit','-qm','Synthetic source proof')
 binding=dict(path=name,commit=git('rev-parse','HEAD'),sha256=sha(repo/name))
 write(j/'FROZEN-T1.json',dict(files={name:binding['sha256']},parent_source_seeds=[binding]))
 monkeypatch.setattr(S.socket,'gethostname',lambda:'127x03')
 return j,p,receipt,binding

def test_exact_committed_generation_seeds_childless_parent(admission):
 j,p,receipt,binding=admission;f=B.Families()
 assert len(S.admit(j,[p],f))==1
 f.apply([p],j);assert p['ssh_budget']['source']==receipt['ssh_connection']
 assert json.loads((j/'parent-source-seed-admission.json').read_text())['accepted'][0]['binding']==binding

@pytest.mark.parametrize('field',S.FIELDS)
def test_each_mismatched_parent_field_gets_no_seed(admission,field):
 j,p,receipt,_=admission;p[field]=p[field]+'-different' if isinstance(p[field],str) else p[field]+1
 f=B.Families();assert not S.admit(j,[p],f)
 assert not p.get('ssh_budget') and not f.sources

def test_wrong_source_ip_never_matches(admission):
 _,p,r,_=admission;r['source_ip']='129.65.221.11';assert not S.matching(p,r)
 r['source_ip']=S.SOURCE;r['ssh_connection']='192.0.2.1 12345 129.65.221.13 22';assert not S.matching(p,r)

def test_seeded_non_reader_child_is_budgeted_and_over_budget_stops(admission):
 j,p,r,_=admission;f=B.Families();S.admit(j,[p],f)
 c=child(p,ssh_connection_snapshot=None,cmd='python /non-reader.py',cpu_ticks=0,child_cpu_ticks=0)
 before=f.apply([p,c],j);assert c.get('ssh_budget')
 m=B.begin(before,hz=100);after=f.apply([parent(),dict(c,cpu_ticks=46)],j);B.update(m,after)
 assert B.finish(m,1)['interfered'] and not B.sample(before,after,1,hz=100)['stop']
 assert B.finish(m,60)['interfered'] and B.finish(m,60)['stop'] is False
 after=f.apply([parent(),dict(c,cpu_ticks=601)],j);B.update(m,after)
 assert B.finish(m,60)['stop']

def test_wrong_host_never_seeds(admission,monkeypatch):
 j,p,_,_=admission;monkeypatch.setattr(S.socket,'gethostname',lambda:'127x08')
 f=B.Families();assert S.admit(j,[p],f)==[] and not f.sources

def test_uncommitted_or_unpinned_seed_is_denied(admission):
 j,p,r,binding=admission;r['source_ip']='129.65.221.11';write(j/'repo'/binding['path'],r)
 with pytest.raises(AssertionError):S.admit(j,[p],B.Families())

def test_conflicting_current_source_is_never_overwritten_by_seed(admission):
 j,p,r,_=admission;f=B.Families();f.sources[(str(j),B.identity(p))]=None
 assert not S.admit(j,[p],f) and f.sources[(str(j),B.identity(p))] is None
