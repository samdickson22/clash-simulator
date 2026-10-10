from pathlib import Path
import pytest
from barrier import outcome_release,reporting_release,COORDINATOR
from common import write

def test_uncommitted_summary_cannot_open_outcomes(tmp_path):
 r=tmp_path/'release.json';write(r,dict(coordinator_thread=COORDINATOR,authorized_at_utc='2026-10-10T00:00:00Z',authorization_message_id='test-only',reason='committed_mac_summary',mac_summary_path='summary.json',commit='missing',mac_summary_sha256='fake'))
 with pytest.raises(Exception):outcome_release(tmp_path,r)

def test_missing_explicit_freeze_denies_reporting(tmp_path):
 m=tmp_path/'manifest.json';a=tmp_path/'authorization.json';write(m,dict(status='FROZEN'));write(a,dict(coordinator_thread=COORDINATOR,r3_explicitly_frozen=False))
 with pytest.raises(AssertionError):reporting_release(tmp_path,m,a)

def test_escape_is_never_automatic(tmp_path):
 r=tmp_path/'release.json';write(r,dict(coordinator_thread=COORDINATOR,authorized_at_utc='2026-10-10T00:00:00Z',authorization_message_id='test-only',reason='14_days_elapsed'))
 with pytest.raises(AssertionError):outcome_release(tmp_path,r)

def test_escape_requires_committed_completion_and_fourteen_days(tmp_path,monkeypatch):
 import subprocess
 from common import sha
 def git(*args):return subprocess.check_output(['git','-C',str(tmp_path),*args]).decode().strip()
 git('init','-q');git('config','user.name','Synthetic Test');git('config','user.email','test@example.invalid')
 completion=tmp_path/'completion.json';write(completion,dict(reporting_complete=True,outcomes_sealed=True,counted_primary_blocks=2400,counted_guard_blocks=600,completed_at_utc='2026-10-10T12:00:00Z'))
 git('add','completion.json');git('commit','-qm','synthetic completion')
 receipt=dict(coordinator_thread=COORDINATOR,authorized_at_utc='2026-10-24T11:59:59Z',authorization_message_id='synthetic',reason='fourteen_day_escape',reporting_completion_path='completion.json',reporting_completion_sha256=sha(completion),completion_commit=git('rev-parse','HEAD'))
 # Isolate the existing escape clock; full prerequisite tests use committed bundles.
 import release_reference
 monkeypatch.setattr(release_reference,'prerequisites',lambda *args:{})
 receipt['amendment_1_prerelease']=dict(completion=dict(path='completion.json',sha256=sha(completion),commit=receipt['completion_commit']))
 release=tmp_path/'release.json';write(release,receipt)
 with pytest.raises(AssertionError,match='escape clock'):outcome_release(tmp_path,release)
 receipt['authorized_at_utc']='2026-10-24T12:00:00Z';write(release,receipt);assert outcome_release(tmp_path,release)==receipt
 receipt['reason']='explicit_coordinator_release';write(release,receipt)
 with pytest.raises(AssertionError):outcome_release(tmp_path,release)
