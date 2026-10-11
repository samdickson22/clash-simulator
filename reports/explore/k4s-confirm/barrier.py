"""Deny outcome access before reading any game bytes. Coordinator owns release.

K4S delta vs T1: outcome_release implements the six r3 §4.5 release items (no Mac-summary gate; Q3);
reporting_release additionally requires the SD1 manifest among the frozen files.
"""
import subprocess
from datetime import datetime,timedelta
from pathlib import Path
from common import read,sha
COORDINATOR='0523ae6f-baa3-4d4e-b233-b392671670db'
RELEASE_ITEMS=('completion','production_checks','verifier_receipt','mac_procedure_manifest')
def _committed(repo,commit,name,h):
 import hashlib
 assert not Path(name).is_absolute() and '..' not in Path(name).parts
 raw=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+name])
 assert hashlib.sha256(raw).hexdigest()==h,name
 assert sha(repo/name)==h,name
 return raw

def outcome_release(repo,receipt):
 """r3 §4.5: every release item committed and SHA-bound in one coordinator-signed receipt. No automatic release."""
 import json
 repo=Path(repo);r=read(receipt)
 assert r['coordinator_thread']==COORDINATOR and r['authorized_at_utc']
 assert r['authorization_message_id'],'explicit coordinator evidence required'
 assert r['study']=='PREREG-K4S'
 commit=r['commit']
 assert subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',commit,'HEAD']).returncode==0
 items=r['items']
 for key in RELEASE_ITEMS:_committed(repo,commit,items[key]['path'],items[key]['sha256'])
 completion=json.loads(_committed(repo,commit,items['completion']['path'],items['completion']['sha256']))
 assert completion['reporting_complete'] is True and completion['outcomes_sealed'] is True
 assert completion['counted_primary_blocks']==3000 and completion['counted_guard_blocks']==900
 # Item 2: pooled END reference and its independent re-check, or the coordinator's ratio-unavailable declaration.
 if 'ratio_unavailable_declaration' in items:
  _committed(repo,commit,items['ratio_unavailable_declaration']['path'],items['ratio_unavailable_declaration']['sha256'])
 else:
  for key in ('end_reference','end_recheck'):_committed(repo,commit,items[key]['path'],items[key]['sha256'])
 # Item 6: the TIERS summary or a released TIERS outcome barrier (including its 14-day escape).
 tiers=[k for k in ('tiers_summary','tiers_release') if k in items];assert len(tiers)>=1
 for key in tiers:_committed(repo,commit,items[key]['path'],items[key]['sha256'])
 return r

def reporting_release(repo,manifest,authorization):
 repo=Path(repo);m=read(manifest);a=read(authorization)
 commit_repo=repo if (repo/'.git').exists() else Path('/mpac/sdicks02/repos/clasher')
 assert a['coordinator_thread']==COORDINATOR and a['r3_explicitly_frozen']
 assert a['authorization_message_id'] and a['manifest_sha256']==sha(manifest)
 assert m['status']=='FROZEN' and m['independent_diff_review'] and m['independent_reducer_review']
 assert m['verifier_author']!=m['reducer_author']
 for name,h in m['files'].items():assert sha(repo/name)==h,name
 for key in ('prereg','plan','seed_audit','guard_decks','runner','reducer','independent_verifier','sd1_manifest'):
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
