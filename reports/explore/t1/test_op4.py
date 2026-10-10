"""OP-4 budget boundaries and source/foreign/console fallback paths."""
import os
from copy import deepcopy
from pathlib import Path
import host_audit as H
import ssh_budget as B
from common import write

def parent(**kw):return dict(pid=20,ppid=1,pgid=20,start_ticks=1,uid=3822945,cmd=f'sshd: {os.environ.get("USER","sdicks02")}@notty',cmdline_sha256='parent',cpu_ticks=100,**kw)
def child(p,**kw):
 r=dict(pid=21,ppid=p['pid'],pgid=21,start_ticks=2,uid=3822945,cmd='python /arbitrary-child.py',cmdline_sha256='child',cpu_ticks=50,ssh_connection_snapshot='129.65.221.14 35798 129.65.221.13 22',ssh_family_parent_snapshot=list(B.identity(p)))
 r.update(kw);return r

def meter(ticks):return dict(hz=100,cpu_ticks=ticks,processes={})
def test_below_budget_and_inclusive_boundaries_pass():
 assert not B.finish(meter(5),10)['interfered']
 assert not B.finish(meter(120),60)['stop']
 assert not B.sample([parent()],[dict(parent(),cpu_ticks=125,ssh_budget={'source':'LAN'})],1,hz=100)['stop']

def test_average_flags_above_half_percent_but_below_two_percent():
 r=B.finish(meter(6),10);assert r['interfered'] and not r['stop']

def test_average_and_single_sample_stop():
 assert B.finish(meter(121),60)['stop']
 r=parent();a=dict(r,cpu_ticks=126,ssh_budget={'source':'LAN'})
 assert B.sample([r],[a],1,hz=100)['stop']
 assert B.stop_reason({'positive':False},[],[],{'stop':False},[B.finish(meter(121),60)])=='ssh_family_average_budget'
 assert B.stop_reason({'positive':False},[],[],{'stop':True},[])=='ssh_family_sample_budget'

def test_proven_lan_family_includes_arbitrary_descendants_and_childless_gap(tmp_path):
 p=parent();c=child(p);grand=dict(c,pid=22,ppid=21,cmd='cargo build',cmdline_sha256='grand',ssh_connection_snapshot=None)
 f=B.Families();rows=f.apply([p,c,grand],tmp_path)
 assert all(r.get('ssh_budget') for r in rows)
 p2=parent();f.apply([p2],tmp_path);assert p2.get('ssh_budget')
 # A reused authenticated PID does not inherit its predecessor's source proof.
 newer=dict(parent(),start_ticks=3);f.apply([newer],tmp_path);assert not newer.get('ssh_budget')

def test_non_lan_and_unknown_fall_back_to_identity_guard(tmp_path,monkeypatch):
 monkeypatch.setattr(H,'own_process',lambda *args:False);monkeypatch.setattr(H,'perception_reader',lambda *args:False)
 for conn in (None,'192.0.2.4 123 129.65.221.13 22','129.65.222.14 123 129.65.221.13 22'):
  p=parent();c=child(p,ssh_connection_snapshot=conn)
  rows=B.Families().apply([p,c],tmp_path)
  assert not any(r.get('ssh_budget') for r in rows)
  assert p in H.foreign_compute(tmp_path,rows) and c in H.foreign_compute(tmp_path,rows)

def test_bad_parent_binding_never_proves_lan(tmp_path):
 p=parent();c=child(p,ssh_family_parent_snapshot=[20,99,3822945,'parent'])
 B.Families().apply([p,c],tmp_path);assert not p.get('ssh_budget')

def test_non_ssh_foreign_stops_even_with_lan_ssh_family(tmp_path,monkeypatch):
 p=parent();c=child(p);stranger=dict(c,pid=99,ppid=1,cmd='python /foreign.py',cmdline_sha256='foreign',ssh_connection_snapshot=None)
 rows=B.Families().apply([p,c,stranger],tmp_path)
 monkeypatch.setattr(H,'own_process',lambda *args:False);monkeypatch.setattr(H,'perception_reader',lambda *args:False)
 foreign=H.foreign_compute(tmp_path,rows);assert foreign==[stranger]
 assert B.stop_reason({'positive':False},foreign,[],{'stop':False},[])=='foreign_compute'

def test_console_stop_has_no_low_load_exception():
 assert B.stop_reason({'positive':True},[],[],{'stop':False},[])=='console_user'

def test_cpu_totals_include_children_exits_newborns_and_readable_commands(tmp_path,monkeypatch):
 monkeypatch.setattr(B.time,'clock_gettime',lambda _:10.)
 p=parent();c=child(p);rows=B.Families().apply([p,c],tmp_path)
 m=B.begin(rows,clock=lambda:10.,hz=100)
 p1=dict(p,cpu_ticks=101);c1=dict(c,cpu_ticks=52);rows=B.Families().apply([p1,c1],tmp_path);B.update(m,rows)
 assert B.finish(m,10)['cpu_ticks']==3
 new=dict(c,pid=23,start_ticks=1001,cpu_ticks=2);rows=B.Families().apply([dict(p1,cpu_ticks=102),new],tmp_path);B.update(m,rows)
 r=B.finish(m,10);assert r['cpu_ticks']==6 and len(r['processes'])==3
 assert any(v['child_commands'] for v in r['processes'])
 assert B.sample([p,c],[dict(p1,cpu_ticks=102),dict(new,ssh_budget={'source':'LAN'})],1,hz=100)['cpu_ticks']==4

def test_conflicting_source_and_captured_non_lan_revoke_budget(tmp_path):
 f=B.Families();p=parent();c=child(p);f.apply([p,c],tmp_path);assert p.get('ssh_budget')
 fresh=parent();wrong=child(fresh,ssh_connection_snapshot='192.0.2.1 123 129.65.221.13 22');f.apply([fresh,wrong],tmp_path);assert not fresh.get('ssh_budget')
 p=parent();good=child(p);bad=dict(wrong,pid=22);f=B.Families();f.apply([p,good,bad],tmp_path);assert not p.get('ssh_budget')

def test_approved_idle_service_is_counted_in_host_budget(tmp_path):
 import idle_services as I
 p=dict(parent(),cmd='python /approved/cache.py',cmdline_sha256='cache')
 write(tmp_path/'idle-services.json',dict(services=[dict(service=I.identity(p),wrapper_trio=[I.identity(p)])]))
 B.Families().apply([p],tmp_path);assert p['ssh_budget']['approved_idle_service']

def test_copier_captured_identity_survives_exit(tmp_path,monkeypatch):
 import ssh_transport as T
 write(tmp_path/'owned-copier-admission.json',dict(active=True,job=str(tmp_path),host='127x01',source_ip='129.65.221.11',identity=dict(pid=30,pgid=30)))
 monkeypatch.setattr(T.socket,'gethostname',lambda:'127x08')
 row=dict(pid=40,cmd=f'rsync --server --sender -logDt . {tmp_path}/reporting/block/',ssh_connection_snapshot='129.65.221.11 12345 129.65.221.18 22',copier_identity_snapshot=dict(T1_COPIER_PID='30',T1_COPIER_PGID='30'))
 assert T.copier_activity(row,[],tmp_path,lambda _: {})
 assert not T.copier_activity(dict(row,copier_identity_snapshot=dict(T1_COPIER_PID='99',T1_COPIER_PGID='30')),[],tmp_path,lambda _: {})

def test_census_applies_budget_family_and_keeps_foreign_stop(tmp_path,monkeypatch):
 import socket
 p=parent();c=child(p);stranger=dict(c,pid=99,ppid=1,cmd='python /foreign.py',ssh_connection_snapshot=None)
 monkeypatch.setattr(H.socket,'gethostname',lambda:'127x08')
 monkeypatch.setattr(H,'processes',lambda:deepcopy([p,c,stranger]))
 monkeypatch.setattr(H,'own_process',lambda *args:False)
 monkeypatch.setattr(B,'FAMILIES',B.Families())
 after,foreign,active,cpu=H.census(tmp_path,block_ids=['b1'])
 assert [x['pid'] for x in foreign]==[99]
 assert next(r for r in after if r['pid']==20)['allowlist_kind']=='ssh_family_budget'
 import json
 occurrence=json.loads((tmp_path/'ssh-family-occurrences.jsonl').read_text())
 assert occurrence['block_ids']==['b1'] and {r['pid'] for r in occurrence['processes']}=={20,21}

def test_console_admission_denies_even_idle(tmp_path,monkeypatch):
 monkeypatch.setattr(H.socket,'gethostname',lambda:'127x08')
 monkeypatch.setattr(H,'physical_cpus',lambda:list(range(64)))
 monkeypatch.setattr(H,'console',lambda:dict(positive=True,who='sdicks02 tty1',console_count=1))
 monkeypatch.setattr(H,'processes',lambda:[])
 monkeypatch.setattr(H,'memory',lambda:128*2**30)
 monkeypatch.setattr(H,'census',lambda *args:([],[],[],0))
 monkeypatch.setattr('system_bus.pin',lambda *args:None)
 monkeypatch.setattr(H.time,'sleep',lambda _:None)
 assert H.admission(tmp_path)['admitted'] is False

def test_source_revocation_on_reused_dictionary_removes_budget_tag(tmp_path):
 p=parent();c=child(p);f=B.Families();f.apply([p,c],tmp_path);assert p.get('ssh_budget')
 c['ssh_connection_snapshot']='192.0.2.1 123 129.65.221.13 22'
 f.apply([p,c],tmp_path);assert not p.get('ssh_budget') and not p.get('allowlist_kind')


def test_conflicting_source_cannot_be_restored_with_later_lan_child(tmp_path):
 f=B.Families();p=parent();f.apply([p,child(p)],tmp_path)
 bad=child(p,ssh_connection_snapshot='192.0.2.1 123 129.65.221.13 22')
 f.apply([parent(),bad],tmp_path)
 fresh=parent();f.apply([fresh,child(fresh)],tmp_path)
 assert not fresh.get('ssh_budget')
 newer=dict(parent(),start_ticks=3);f.apply([newer,child(newer)],tmp_path)
 assert newer.get('ssh_budget')


def test_reaped_short_children_trigger_sample_cap_with_constant_parent_self_cpu(tmp_path,monkeypatch):
 # Reviewer probe: ~47ms children all exit between one-second censuses.
 # Their CPU is visible only in the persistent shell's cutime+cstime.
 p=parent();shell=child(p,child_cpu_ticks=100)
 before=B.Families().apply([p,shell],tmp_path)
 m=B.begin(before,hz=100)
 after=B.Families().apply([parent(),dict(shell,child_cpu_ticks=146)],tmp_path)
 B.update(m,after)
 assert B.finish(m,1)['cpu_ticks']==46
 assert B.finish(m,1)['interfered'] and not B.finish(m,1)['stop']
 assert B.sample(before,after,1,hz=100)['cpu_ticks']==46
 assert not B.sample(before,after,1,hz=100)['stop'] # OP-6 proven SSH cap is150%
 assert any(r['observed_reaped_child_cpu_ticks']==146 for r in B.finish(m,1)['processes'])


def test_reaped_cpu_of_authenticated_parent_and_every_budgeted_descendant(tmp_path):
 p=parent(child_cpu_ticks=10);c=child(p,child_cpu_ticks=20)
 before=B.Families().apply([p,c],tmp_path);m=B.begin(before,hz=100)
 after=B.Families().apply([dict(p,child_cpu_ticks=13),dict(c,child_cpu_ticks=25)],tmp_path)
 B.update(m,after)
 assert B.finish(m,60)['cpu_ticks']==8
 assert B.sample(before,after,1,hz=100)['cpu_ticks']==8
 # A second identical census never charges the same reaped delta again.
 B.update(m,after);assert B.finish(m,60)['cpu_ticks']==8


def test_early_block_uses_sample_cap_then_average_stop_at_sixty_seconds():
 assert not B.finish(meter(121),59.999)['stop']
 assert B.finish(meter(121),60)['stop']
 assert not B.finish(meter(120),60)['stop'] # exactly2% remains inclusive
 before=[parent()];after=[dict(parent(),cpu_ticks=126,ssh_budget={'source':'LAN'})]
 assert B.sample(before,after,1,hz=100)['stop'] # never delayed by the block floor


def test_live_proc_reaped_children_are_measured(tmp_path):
 import signal,subprocess,time
 # Real /proc probe with a synthetic authenticated root; no SSH/network activity.
 core=min(set(H.physical_cpus()) & os.sched_getaffinity(0))
 loop="while :; do sh -c 'i=0; while [ $i -lt 30000 ]; do i=$((i+1)); done'; done"
 process=subprocess.Popen(['nice','-n','19','taskset','-c',str(core),'bash','-c',loop],start_new_session=True)
 fake=dict(parent(),pid=10**8,pgid=10**8,cpu_ticks=0,child_cpu_ticks=0)
 families=B.Families()
 def capture():
  allrows=H.processes();selected={process.pid}
  for _ in range(8):
   selected.update(r['pid'] for r in allrows if r['ppid'] in selected)
  rows=[r for r in allrows if r['pid'] in selected]
  shell=next(r for r in rows if r['pid']==process.pid)
  shell['ppid']=fake['pid'];shell['ssh_connection_snapshot']='129.65.221.11 12345 129.65.221.15 22'
  shell['ssh_family_parent_snapshot']=list(B.identity(fake))
  rows.append(dict(fake));families.apply(rows,tmp_path)
  return rows,shell
 try:
  before,shell=capture();baseline=shell['child_cpu_ticks'];m=B.begin(before)
  for _ in range(4):
   time.sleep(.5);after,shell=capture();B.update(m,after)
  reaped=shell['child_cpu_ticks']-baseline
  assert reaped>0,'Probe must actually reap busy children'
  assert m['cpu_ticks']>=reaped,'All reaped CPU must be included even when no child is sampled'
 finally:
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  process.wait(timeout=5)
