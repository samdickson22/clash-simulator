"""OP-5 08: committed reversed TCP and exact generation/source join."""
import copy,json,subprocess
from pathlib import Path
import pytest
import parent_source_seed as S
import ssh_budget as B
from common import ROOT,read,write,sha
from test_op4 import parent,child

@pytest.fixture
def joined(tmp_path,monkeypatch):
 j=tmp_path/'job';repo=j/'repo';repo.mkdir(parents=True)
 def git(*args):return subprocess.check_output(['git','-C',str(repo),*args]).decode().strip()
 git('init','-q');git('config','user.name','Synthetic Test');git('config','user.email','test@example.invalid')
 receipt=read(ROOT/'reports/explore/t1/receipts/op5-parent-source-127x08.json');dependencies={}
 for key in ('server','client'):
  binding=receipt['source_join'][key];name=binding['path'];data=read(ROOT/name);write(repo/name,data);dependencies[key]=data
 git('add','--',*[receipt['source_join'][k]['path'] for k in ('server','client')]);git('commit','-qm','Synthetic committed join dependencies')
 commit=git('rev-parse','HEAD')
 for key,b in receipt['source_join'].items():b.update(commit=commit,sha256=sha(repo/b['path']))
 name='reports/explore/t1/receipts/synthetic-08-seed.json';write(repo/name,receipt);git('add','--',name);git('commit','-qm','Synthetic joined seed')
 binding=dict(path=name,commit=git('rev-parse','HEAD'),sha256=sha(repo/name))
 files={name:binding['sha256'],**{b['path']:b['sha256'] for b in receipt['source_join'].values()}}
 write(j/'FROZEN-T1.json',dict(files=files,parent_source_seeds=[binding]));monkeypatch.setattr(S.socket,'gethostname',lambda:'127x08')
 row=dict(parent(),**receipt['parent']);return j,row,receipt,dependencies['server'],dependencies['client'],binding

def test_exact_08_committed_join_seeds_childless_parent(joined):
 j,p,r,s,c,binding=joined;f=B.Families();assert S.joined_08(r,s,c)
 assert len(S.admit(j,[p],f))==1;f.apply([p],j);assert p['ssh_budget']['source']==r['ssh_connection']
 assert read(j/'parent-source-seed-admission.json')['accepted'][0]['binding']==binding

@pytest.mark.parametrize('field',S.FIELDS)
def test_08_new_parent_generation_does_not_seed(joined,field):
 j,p,r,s,c,_=joined;p[field]=p[field]+'x' if isinstance(p[field],str) else p[field]+1
 f=B.Families();assert not S.admit(j,[p],f) and not f.sources

@pytest.mark.parametrize('field',S.FIELDS)
def test_08_server_generation_join_mismatch(joined,field):
 _,p,r,s,c,_=joined
 if field=='cmdline_sha256':s[field]='0'*64
 else:s['parent'][field]+=1
 assert not S.matching(p,r,s,c)

@pytest.mark.parametrize('field',('pid','starttime','uid','cmdline_sha256','ppid','pgid'))
def test_04_client_identity_join_mismatch(joined,field):
 _,p,r,s,c,_=joined;v=r['client_identity'][field];r['client_identity'][field]=v+'x' if isinstance(v,str) else v+1
 assert not S.matching(p,r,s,c)

@pytest.mark.parametrize('which',('local_ip','local_port','remote_ip','remote_port','inode','controlpath','owner_pid','recheck_start','server_socket','source_ip','connection'))
def test_04_socket_controlpath_and_source_mismatch(joined,which):
 _,p,r,s,c,_=joined
 if which.startswith('local_') or which.startswith('remote_'):
  side,key=which.split('_');v=c['socket_identity'][side][key];c['socket_identity'][side][key]=v+'x' if isinstance(v,str) else v+1
 elif which=='inode':c['socket_identity']['inode']+=1
 elif which=='controlpath':c['control_path']+='-other'
 elif which=='owner_pid':c['socket_fd_owners'][0]['pid']+=1
 elif which=='recheck_start':c['observation']['owners'][0]['identity_recheck']['starttime']+=1
 elif which=='server_socket':s['socket_inode']+=1
 elif which=='source_ip':r['source_ip']='129.65.221.11'
 else:r['ssh_connection']='129.65.221.14 55839 129.65.221.18 22'
 assert not S.matching(p,r,s,c)

def test_08_uncommitted_dependency_is_denied(joined):
 j,p,r,s,c,_=joined;name=r['source_join']['client']['path'];c['client_starttime']+=1;write(j/'repo'/name,c)
 with pytest.raises(AssertionError):S.admit(j,[p],B.Families())

def test_08_join_still_budgets_nonreader_children_and_stops(joined):
 j,p,r,s,c,_=joined;f=B.Families();S.admit(j,[p],f)
 kid=child(p,ssh_connection_snapshot=None,cmd='python /nonreader.py',cpu_ticks=0,child_cpu_ticks=0)
 before=f.apply([p,kid],j);assert kid.get('ssh_budget');m=B.begin(before,hz=100)
 after=f.apply([dict(p),dict(kid,cpu_ticks=46)],j);B.update(m,after)
 assert B.finish(m,60)['interfered'] and not B.finish(m,60)['stop']
 assert B.sample(before,after,1,hz=100)['stop']
 after=f.apply([dict(p),dict(kid,cpu_ticks=121)],j);B.update(m,after);assert B.finish(m,60)['stop']

def test_08_conflicting_live_source_is_not_overwritten(joined):
 j,p,r,s,c,_=joined;f=B.Families();f.sources[str(j),B.identity(p)]=None
 assert not S.admit(j,[p],f) and f.sources[str(j),B.identity(p)] is None

def test_08_receipt_cannot_seed_01(joined,monkeypatch):
 j,p,*_=joined;monkeypatch.setattr(S.socket,'gethostname',lambda:'127x01')
 f=B.Families();assert not S.admit(j,[p],f) and not f.sources
