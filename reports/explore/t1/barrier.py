"""Deny outcome access before reading any game bytes. Coordinator owns release."""
import subprocess
from datetime import datetime,timedelta
from pathlib import Path
from common import read,sha
COORDINATOR='0523ae6f-baa3-4d4e-b233-b392671670db'
def outcome_release(repo,receipt):
 repo=Path(repo);r=read(receipt)
 assert r['coordinator_thread']==COORDINATOR and r['authorized_at_utc']
 assert r['authorization_message_id'],'explicit coordinator evidence required'
 assert r['reason'] in ('fourteen_day_escape','committed_mac_summary')
 from release_reference import prerequisites
 completion=prerequisites(repo,r)
 if r['reason']=='fourteen_day_escape':
  bound=r['amendment_1_prerelease']['completion']
  assert bound==dict(path=r['reporting_completion_path'],commit=r['completion_commit'],sha256=r['reporting_completion_sha256']),'escape completion differs from checked END'
  name=r['reporting_completion_path'];assert not Path(name).is_absolute() and '..' not in Path(name).parts
  raw=subprocess.check_output(['git','-C',str(repo),'show',r['completion_commit']+':'+name])
  import hashlib,json
  assert hashlib.sha256(raw).hexdigest()==r['reporting_completion_sha256']
  assert subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',r['completion_commit'],'HEAD']).returncode==0
  assert sha(repo/name)==r['reporting_completion_sha256']
  completion=json.loads(raw);assert completion['reporting_complete'] is True and completion['outcomes_sealed'] is True
  assert completion['counted_primary_blocks']==2400 and completion['counted_guard_blocks']==600
  completed=datetime.fromisoformat(completion['completed_at_utc'].replace('Z','+00:00'))
  authorized=datetime.fromisoformat(r['authorized_at_utc'].replace('Z','+00:00'))
  assert completed.utcoffset() is not None and authorized.utcoffset() is not None
  assert authorized>=completed+timedelta(days=14),'escape clock starts at reporting completion'
  return r
 assert r['reason']=='committed_mac_summary'
 name=r['mac_summary_path'];assert not Path(name).is_absolute() and '..' not in Path(name).parts
 raw=subprocess.check_output(['git','-C',str(repo),'show',r['commit']+':'+name])
 import hashlib
 assert hashlib.sha256(raw).hexdigest()==r['mac_summary_sha256']
 assert subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',r['commit'],'HEAD']).returncode==0
 assert sha(repo/name)==r['mac_summary_sha256']
 return r

def reporting_release(repo,manifest,authorization):
 repo=Path(repo);m=read(manifest);a=read(authorization)
 commit_repo=repo if (repo/'.git').exists() else Path('/mpac/sdicks02/repos/clasher')
 assert a['coordinator_thread']==COORDINATOR and a['r3_explicitly_frozen']
 assert a['authorization_message_id'] and a['manifest_sha256']==sha(manifest)
 assert m['status']=='FROZEN' and m['independent_diff_review'] and m['independent_reducer_review']
 assert m['verifier_author']!=m['reducer_author']
 for name,h in m['files'].items():assert sha(repo/name)==h,name
 for key in ('prereg','plan','seed_audit','guard_decks','runner','reducer','independent_verifier'):
  names=m[key] if isinstance(m[key],list) else [m[key]]
  assert names and all(n in m['files'] for n in names),key
 assert m['seed_audit_disjoint'] and m['guard_support_pass'] and len(m['qualified_hosts'])>=2
 assert m['reporting_delta_review']['verdict']=='APPROVE' and m['reporting_delta_review']['round']>=3
 assert m['reporting_delta_review']['path'] in m['files']
 # Frozen bytes must already be in a commit. No uncommitted freeze is sufficient.
 for name,h in m['files'].items():
  import hashlib
  raw=subprocess.check_output(['git','-C',str(commit_repo),'show',a['freeze_commit']+':'+name]);assert hashlib.sha256(raw).hexdigest()==h,name
 return m
