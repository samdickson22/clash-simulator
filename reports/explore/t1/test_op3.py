"""OP-3 ownership proof remains valid across a worker's exit, never a stranger's."""
import host_audit as H
import owned_supervisor as O
from common import write

def root():
    return dict(pid=20,pgid=20,ppid=1,start_ticks=2000,uid=3822945,
                cmdline_sha256='root',exe='/usr/bin/python3')

def worker(j,**changes):
    r=dict(pid=21,ppid=20,pgid=21,start_ticks=2100,uid=3822945,
           cmd=f'python reports/explore/t1/run.py --out {j}/block',cmdline_sha256='worker',exe='/usr/bin/python3')
    return dict(r,**changes)

def admit(j,monkeypatch,groups=()):
    write(j/'owned-supervisor-admission.json',dict(job=str(j),supervisor=O.identity(root()),worker_groups=list(groups)))
    monkeypatch.setattr(O,'live_identity',lambda pid:root() if pid==20 else None)

def gone(monkeypatch):
    def resolve(*args,**kw):raise ProcessLookupError('worker exited before cwd lookup')
    monkeypatch.setattr(H.Path,'resolve',resolve)

def test_exited_owned_command_and_authenticated_parent_allow(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    assert H.own_process(tmp_path,worker(tmp_path))

def test_exited_unowned_command_denies(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    assert not H.own_process(tmp_path,worker(tmp_path,cmd='python /foreign.py'))

def test_matching_command_foreign_parent_and_pgid_denies(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    assert not H.own_process(tmp_path,worker(tmp_path,pid=99,ppid=98,pgid=99))

def test_exited_command_and_authenticated_supervisor_pgid_allow(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    assert H.own_process(tmp_path,worker(tmp_path,ppid=99,pgid=20))

def test_reused_supervisor_identity_denies(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    monkeypatch.setattr(O,'live_identity',lambda pid:dict(root(),start_ticks=2001))
    assert not H.own_process(tmp_path,worker(tmp_path))

def test_registered_worker_group_requires_exact_leader_generation(tmp_path,monkeypatch):
    w=worker(tmp_path);group=O.identity(w,O.GROUP_KEYS)
    admit(tmp_path,monkeypatch,groups=[group]);gone(monkeypatch)
    # A captured group leader is sufficient even after that leader has exited.
    assert H.own_process(tmp_path,dict(w,ppid=99))
    descendant=worker(tmp_path,pid=22,ppid=21)
    assert not H.own_process(tmp_path,descendant)
    monkeypatch.setattr(O,'live_identity',lambda pid:root() if pid==20 else dict(w))
    assert H.own_process(tmp_path,descendant)
    monkeypatch.setattr(O,'live_identity',lambda pid:root() if pid==20 else dict(w,start_ticks=2101))
    assert not H.own_process(tmp_path,descendant)

def test_foreign_guard_preserves_owned_exit_and_rejects_stranger(tmp_path,monkeypatch):
    admit(tmp_path,monkeypatch);gone(monkeypatch)
    monkeypatch.setattr(H,'perception_reader',lambda *args:False)
    monkeypatch.setattr('idle_services.member',lambda *args:False)
    owned=worker(tmp_path);stranger=worker(tmp_path,pid=99,ppid=98,pgid=99)
    assert H.foreign_compute(tmp_path,[owned,stranger])==[stranger]
