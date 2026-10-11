"""OP-2 tests exercise the production matcher and confirmation, without /proc."""
import hashlib
import pytest
import host_audit as H
from perception_confirmation import Confirmation,UID
from ssh_transport import approved_parent

SOURCE='129.65.221.14 35798 129.65.221.13 22'
PATH='/mpac/sdicks02/v4-archive/verified-capture-20261009-r1/body/test.gz'

def row(pid,cmd,ppid=1,start=None,source=None):
    return dict(pid=pid,ppid=ppid,pgid=pid,start_ticks=start or pid*100,uid=UID,
                cmd=cmd,cmdline_sha256=hashlib.sha256(cmd.encode()).hexdigest(),
                ssh_connection_snapshot=source,cpu_ticks=0,exe=None)

def parent(**kw):return row(20,'sshd: sdicks02@notty',**kw)
def child(cmd=None,**kw):
    r=row(21,cmd if cmd is not None else 'cat -- '+PATH,ppid=20,**kw)
    p=parent();r['ssh_parent_snapshot']=[p[k] for k in ('pid','start_ticks','uid','cmdline_sha256')]
    return r

class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,n):self.now+=n

@pytest.fixture(autouse=True)
def host(monkeypatch):
    monkeypatch.setattr(H.socket,'gethostname',lambda:'127x03')
    monkeypatch.setenv('USER','sdicks02')
    monkeypatch.setattr('ssh_transport.os.getuid',lambda:UID)

def accepted(rows):
    return not rows[0].get('op2_denied') and approved_parent(rows[0],rows,lambda r:r.get('allowlist_kind')=='perception_reader')

def test_positive_snapshot_source_bound_to_exact_parent(tmp_path):
    rows=[parent(),child(source=SOURCE)];c=Confirmation()
    c.apply(rows,tmp_path,lambda:pytest.fail('resolved readers never wait'),H.perception_reader,block_ids=['smoke-1'])
    assert accepted(rows)
    proof=rows[0]['op2_confirmation']['source']
    assert proof['parent_identity']==[20,2000,UID,rows[0]['cmdline_sha256']]
    assert proof['connection']==SOURCE
    assert rows[0]['op2_confirmation']['block_ids']==['smoke-1']

def test_race_exited_before_environment_lookup_snapshot_command_resolves(tmp_path,monkeypatch):
    c=Confirmation();first=[parent(),child(source=SOURCE)]
    c.apply(first,tmp_path,lambda:[],H.perception_reader)
    # Next child exits after cmdline capture, so there is no later env to read.
    gone=child();gone['pid']=22;gone['start_ticks']=2200
    rows=[parent(),gone]
    monkeypatch.setattr(H.Path,'read_bytes',lambda _:pytest.fail('no late /proc/environment lookup'))
    c.apply(rows,tmp_path,lambda:[],H.perception_reader)
    assert accepted(rows) and rows[0]['op2_confirmation']['accepted']

def proven(clock):
    c=Confirmation(clock,clock.sleep)
    return c

def test_fork_exec_resolves_within_two_seconds(tmp_path):
    clock=Clock();c=proven(clock);p=parent(source=SOURCE)
    rows=[p,child(cmd=p['cmd'])]
    def collect():return [parent(source=SOURCE),child(cmd=p['cmd'] if clock()<1.9 else None)]
    c.apply(rows,tmp_path,collect,H.perception_reader)
    assert accepted(rows) and 1.9<=clock()<=2

def test_two_second_limit_denies_late_exec(tmp_path):
    clock=Clock();c=proven(clock);p=parent(source=SOURCE);rows=[p,child(cmd=p['cmd'])]
    c.apply(rows,tmp_path,lambda:[parent(source=SOURCE),child(cmd=p['cmd'] if clock()<=2 else None)],H.perception_reader)
    assert not accepted(rows) and rows[0]['op2_denied']=='confirmation limit'
    assert clock()<=2

def test_exited_unresolved_child_stays_foreign(tmp_path):
    clock=Clock();c=proven(clock);p=parent(source=SOURCE);rows=[p,child(cmd=p['cmd'])]
    c.apply(rows,tmp_path,lambda:[parent(source=SOURCE)],H.perception_reader)
    assert rows[0]['op2_denied']=='exited unresolved child'
    assert not accepted(rows)

def test_wrong_source_never_gets_confirmation_window(tmp_path):
    clock=Clock();c=proven(clock)
    rows=[parent(),child(source=SOURCE.replace('129.65.221.14','129.65.221.11'))]
    c.apply(rows,tmp_path,lambda:pytest.fail('wrong source cannot wait'),H.perception_reader)
    assert not accepted(rows) and clock()==0

def test_non_reader_child_denied_even_for_proven_source(tmp_path):
    clock=Clock();c=proven(clock)
    rows=[parent(source=SOURCE),child(cmd='sleep 100',source=SOURCE)]
    c.apply(rows,tmp_path,lambda:pytest.fail('non-reader cannot wait'),H.perception_reader)
    assert not accepted(rows) and rows[0]['op2_denied']=='non-reader child'
    assert clock()==0

@pytest.mark.parametrize('change',[{'start_ticks':2001},{'uid':UID+1},{'cmdline_sha256':'new'}])
def test_source_cache_never_reused_for_changed_parent(tmp_path,change):
    c=Confirmation();c.apply([parent(),child(source=SOURCE)],tmp_path,lambda:[],H.perception_reader)
    p=dict(parent(),**change);rows=[p,child()]
    c.apply(rows,tmp_path,lambda:pytest.fail('changed parent cannot wait'),H.perception_reader)
    assert not accepted(rows)

def test_every_observed_child_must_resolve(tmp_path):
    clock=Clock();c=proven(clock);p=parent(source=SOURCE)
    rows=[p,child(cmd=p['cmd'])]
    unknown=row(22,'sleep 10',ppid=20,source=SOURCE)
    c.apply(rows,tmp_path,lambda:[parent(source=SOURCE),child(),unknown],H.perception_reader)
    assert not accepted(rows) and rows[0]['op2_denied']=='non-reader child'

def test_wrong_source_cannot_be_overridden_by_cached_parent(tmp_path):
    c=Confirmation();c.apply([parent(),child(source=SOURCE)],tmp_path,lambda:[],H.perception_reader)
    rows=[parent(),child(source=SOURCE.replace('129.65.221.14','129.65.221.11'))]
    c.apply(rows,tmp_path,lambda:pytest.fail('wrong source cannot wait'),H.perception_reader)
    assert not accepted(rows) and rows[0]['op2_denied']=='wrong child UID/source'

def test_exit_failure_cannot_disappear_from_foreign_guard(tmp_path,monkeypatch):
    p=dict(parent(),op2_denied='exited unresolved child')
    monkeypatch.setattr(H,'own_process',lambda *args:False)
    assert H.foreign_compute(tmp_path,[p])==[p]


def test_collected_source_requires_matching_parent_identity(tmp_path):
    c=Confirmation();r=child(source=SOURCE);r['ssh_parent_snapshot'][1]+=1
    rows=[parent(),r]
    c.apply(rows,tmp_path,lambda:pytest.fail('unbound source cannot wait'),H.perception_reader)
    assert not accepted(rows)
