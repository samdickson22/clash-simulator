import os
from pathlib import Path
from common import write
import ssh_transport as T
from system_bus import identity,member,finish,update

def bus():return dict(pid=10,start_ticks=100,exe='/usr/bin/dbus-daemon',cmdline_sha256='fixed',uid=103,cpu_ticks=100)
def test_pinned_system_bus_allows_exact_and_denies_new_pid_start_exe_cmd(tmp_path):
 r=bus();write(tmp_path/'system-bus-admission.json',dict(identity=identity(r)))
 assert member(r,tmp_path)
 for key,value in [('pid',11),('start_ticks',101),('exe','/tmp/dbus-daemon'),('cmdline_sha256','new'),('uid',104)]:
  assert not member(dict(r,**{key:value}),tmp_path)

def test_bus_cpu_exact_threshold_flags_only_above(monkeypatch):
 monkeypatch.setattr('system_bus.os.sysconf',lambda _:100)
 m=dict(identity=identity(bus()),start_cpu_ticks=100,last_cpu_ticks=110,retired=False)
 assert not finish(m,10)['interfered']
 update(m,[dict(bus(),cpu_ticks=111)]);assert finish(m,10)['interfered']

def session():return dict(pid=20,ppid=1,cmd=f'sshd: {os.environ.get("USER","sdicks02")}@notty',uid=os.getuid())
def test_authenticated_parent_transport_requires_every_child_attributable():
 s=session();a=dict(pid=21,ppid=20,cmd='cat /approved/evidence',uid=os.getuid());unknown=dict(pid=22,ppid=20,cmd='sleep 10',uid=os.getuid())
 approved=lambda r:r['pid']==21
 assert T.sshd_title(s) and T.approved_parent(s,[s,a],approved)
 assert not T.approved_parent(s,[s,a,unknown],approved)
 assert not T.approved_parent(s,[s,unknown],approved)
 assert not T.approved_parent(s,[s],approved)
 assert not T.approved_parent(dict(s,uid=0),[s,a],approved)
 assert not T.approved_parent(dict(s,cmd='sshd: unknown [preauth]'),[s,a],approved)
 # A permitted shell intermediary cannot hide another unapproved leaf.
 sh=dict(pid=23,ppid=20,cmd='sh -c cat',uid=os.getuid());a['ppid']=23
 assert T.approved_parent(s,[s,sh,a],approved)
 unknown['ppid']=23;assert not T.approved_parent(s,[s,sh,a,unknown],approved)

def test_owned_copier_requires_registered_pid_pgid_origin_and_scoped_work(tmp_path,monkeypatch):
 write(tmp_path/'owned-copier-admission.json',dict(active=True,job=str(tmp_path),host='127x01',source_ip='129.65.221.11',identity=dict(pid=30,pgid=30)))
 monkeypatch.setattr(T.socket,'gethostname',lambda:'127x03')
 row=dict(pid=40,cmd=f'rsync --server --sender -logDt . {tmp_path}/reporting/block/')
 env=dict(T1_COPIER_PID='30',T1_COPIER_PGID='30',SSH_CONNECTION='129.65.221.11 12345 129.65.221.13 22')
 assert T.copier_activity(row,[],tmp_path,lambda _:dict(env))
 for key,value in [('T1_COPIER_PID','31'),('T1_COPIER_PGID','31'),('SSH_CONNECTION','129.65.221.12 12345 129.65.221.13 22')]:
  assert not T.copier_activity(row,[],tmp_path,lambda _:dict(env,**{key:value}))
 assert not T.copier_activity(dict(row,cmd=row['cmd']+' /etc'),[],tmp_path,lambda _:dict(env))
 assert not T.copier_activity(dict(row,cmd='python /unapproved/job.py'),[],tmp_path,lambda _:dict(env))


def test_guard_rejects_unpinned_system_bus_and_unknown_child_ssh(monkeypatch,tmp_path):
 import host_audit as H
 r=dict(bus(),ppid=1,pgid=10,cmd='/usr/bin/dbus-daemon --system')
 monkeypatch.setattr(H,'own_process',lambda *args:False)
 monkeypatch.setattr(H,'perception_reader',lambda *args:False)
 monkeypatch.setattr('idle_services.member',lambda *args:False)
 assert H.foreign_compute(tmp_path,[r])==[r]
 known=dict(r,allowlist_kind='system_dbus');assert H.foreign_compute(tmp_path,[known])==[]
 session_row=session();unknown=dict(pid=21,ppid=20,pgid=20,uid=os.getuid(),cmd='sleep 10')
 assert session_row in H.foreign_compute(tmp_path,[session_row,unknown])
 known_session=dict(session_row,allowlist_kind='approved_sshd_transport')
 assert H.foreign_compute(tmp_path,[known_session,unknown])==[]
