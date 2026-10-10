"""OP-7 provenance denial, exact budgets, reaping and sealed sensitivity proofs."""
import copy, hashlib, os, time
import numpy as np
import pytest
import apt_budget as A
import ssh_sensitivity as S
import host_audit as H
from common import write, sha
from reduce import population_stats
from schedule import ARMS

def root(**overrides):
    row=dict(pid=542173,ppid=541277,pgid=541271,start_ticks=145613425,
             uid=0,cmd='/usr/bin/python3 /usr/bin/unattended-upgrade --download-only',
             cmdline_sha256='apt-cmd',cpu_ticks=0,child_cpu_ticks=0,
             apt_cgroup_snapshot='/system.slice/apt-daily.service')
    row.update(overrides)
    return row

def child(parent, **overrides):
    values=dict(pid=parent['pid']+1,ppid=parent['pid'],cmd='/usr/bin/python3 /apt/child.py',
                cmdline_sha256='child-cmd')
    values.update(overrides)
    return root(**values)

def measured(ticks):
    before=A.apply([root()]);meter=A.begin(before,hz=100)
    after=A.apply([root(cpu_ticks=ticks)]);A.update(meter,after)
    return before,after,meter

@pytest.mark.parametrize('line',[
    '0::/system.slice/apt-daily.service',
    '1:name=systemd:/system.slice/apt-daily-upgrade.service'])
def test_kernel_cgroup_parser(tmp_path,line):
    (tmp_path/'cgroup').write_text(line+'\n')
    assert A.capture_cgroup(tmp_path) in A.CGROUPS

@pytest.mark.parametrize('line',[
    '0::/system.slice/apt-daily.service.evil',
    '0::/evil/system.slice/apt-daily.service',
    '1:cpu:/system.slice/apt-daily.service',
    '0::/system.slice/apt-daily.service\n1:name=systemd:/other',
    'malformed'])
def test_missing_wrong_ambiguous_cgroup_does_not_prove_source(tmp_path,line):
    assert A.capture_cgroup(tmp_path) is None
    (tmp_path/'cgroup').write_text(line+'\n')
    assert A.capture_cgroup(tmp_path) not in A.CGROUPS

@pytest.mark.parametrize('cmd',sorted(A.DIRECT)+[
    '/bin/sh /usr/lib/apt/apt.systemd.daily update',
    '/usr/bin/python3 /usr/lib/update-notifier/apt-check',
    '/usr/bin/python3 /usr/bin/unattended-upgrade --download-only'])
def test_pinned_service_and_exact_apt_command_admitted(cmd,tmp_path):
    rows=A.apply([root(cmd=cmd)]);assert rows[0]['apt_budget']
    assert not H.foreign_compute(tmp_path,rows)

@pytest.mark.parametrize('override',[
    {'uid':3822945},{'apt_cgroup_snapshot':None},
    {'apt_cgroup_snapshot':'/system.slice/other.service'},
    {'apt_cgroup_snapshot':'/system.slice/apt-daily.service/child'},
    {'cmd':'/usr/bin/python3 /unrelated.py'},
    {'cmd':'/tmp/apt-get'},{'cmd':'python3 /usr/bin/unattended-upgrade'},
    {'cmd':'/usr/bin/python3 /tmp/unattended-upgrade'},
])
def test_lookalike_or_unproven_root_remains_foreign(override,tmp_path):
    rows=A.apply([root(**override)]);assert not rows[0].get('apt_budget')
    if rows[0]['cmd'].split()[0].split('/')[-1].startswith('python'):
        assert H.foreign_compute(tmp_path,rows)

@pytest.mark.parametrize('cmd',['/usr/bin/apt-get update','/usr/bin/dpkg --configure -a','/tmp/apt-get update','/bin/sh /usr/lib/apt/apt.systemd.daily update'])
def test_nonpython_apt_with_wrong_cgroup_stops(cmd,tmp_path):
    rows=A.apply([root(cmd=cmd,apt_cgroup_snapshot='/system.slice/unrelated.service')])
    assert H.foreign_compute(tmp_path,rows)

def test_descendants_require_same_uid_cgroup_and_observed_root(tmp_path):
    parent=root();c=child(parent);grandchild=child(c,pid=parent['pid']+2)
    rows=A.apply([parent,c,grandchild]);assert all(r.get('apt_budget') for r in rows)
    assert not H.foreign_compute(tmp_path,rows)
    assert rows[-1]['apt_budget']['root_identity']['pid']==parent['pid']
    for changed in [dict(c,uid=3822945),dict(c,apt_cgroup_snapshot='/other'),dict(c,ppid=1)]:
        rows=A.apply([root(),changed]);assert not rows[-1].get('apt_budget')
        assert H.foreign_compute(tmp_path,rows)
    assert not A.apply([c])[0].get('apt_budget')

@pytest.mark.parametrize('ticks,flag,stop',[(30,False,False),(31,True,False),(600,True,False),(601,True,True)])
def test_exact_average_and_flag_boundaries(ticks,flag,stop):
    _,_,meter=measured(ticks);result=A.finish(meter,60)
    assert result['apt_flagged'] is flag and result['stop'] is stop
    assert S.apt_flagged({'ubuntu_apt':result,'apt_flagged':flag}) is flag

@pytest.mark.parametrize('ticks,stop',[(25,False),(150,False),(151,True)])
def test_exact_sample_caps(ticks,stop):
    before,after,_=measured(ticks);assert A.sample(before,after,1,hz=100)['stop'] is stop

def test_average_floor_and_reaped_children():
    before=A.apply([root(child_cpu_ticks=10)]);meter=A.begin(before,hz=100)
    after=A.apply([root(child_cpu_ticks=611)]);A.update(meter,after)
    assert A.finish(meter,60)['cpu_ticks']==601
    assert not A.finish(meter,59.999)['stop'] and A.finish(meter,60)['stop']
    assert A.sample(before,after,1,hz=100)['stop']

def test_stop_reasons_and_unrelated_foreign_still_win(tmp_path):
    import ssh_budget as B
    before,after,meter=measured(601)
    assert A.stop_reason(A.sample(before,after,1,hz=100),[])=='ubuntu_apt_sample_budget'
    assert A.stop_reason({'stop':False},[A.finish(meter,60)])=='ubuntu_apt_average_budget'
    assert A.stop_reason({'stop':False},[A.finish(meter,59)]) is None
    rows=A.apply([root(),root(pid=8,ppid=1,uid=3822945,cmd='/usr/bin/python3 /foreign.py',apt_cgroup_snapshot=None)])
    foreign=H.foreign_compute(tmp_path,rows)
    assert len(foreign)==1 and foreign[0]['pid']==8
    assert B.stop_reason({'positive':False},foreign,[],{'stop':False},[])=='foreign_compute'
    assert B.stop_reason({'positive':True},[],[],{'stop':False},[])=='console_user'

def test_stale_allowlist_is_removed_when_provenance_changes():
    rows=A.apply([root()]);assert rows[0].get('apt_budget')
    rows[0]['apt_cgroup_snapshot']='/system.slice/unrelated.service'
    A.apply(rows);assert not rows[0].get('apt_budget') and not rows[0].get('allowlist_kind')

def test_multiple_children_share_one_sample_cap():
    r=root();a=child(r);b=child(r,pid=r['pid']+2)
    before=A.apply([r,a,b]);after=A.apply([root(),dict(a,cpu_ticks=80),dict(b,cpu_ticks=71)])
    assert A.sample(before,after,1,hz=100)['cpu_ticks']==151
    assert A.sample(before,after,1,hz=100)['stop']

def test_new_generation_cpu_is_not_subtracted_from_previous_generation(monkeypatch):
    monkeypatch.setattr(A.time,'clock_gettime',lambda _:100)
    before=A.apply([root(start_ticks=9900,cpu_ticks=500)])
    after=A.apply([root(start_ticks=10000,cpu_ticks=151)])
    assert A.sample(before,after,1,hz=100)['cpu_ticks']==151

def test_meter_flags_and_occurrences_are_bound_to_block(tmp_path):
    _,rows,meter=measured(31);A.record(tmp_path,rows,['primary-0000'])
    text=(tmp_path/'ubuntu-apt-occurrences.jsonl').read_text()
    assert 'primary-0000' in text and 'apt-daily.service' in text and 'root_identity' in text
    health={'ubuntu_apt':A.finish(meter,60),'apt_flagged':True}
    folder=tmp_path/'hub'/'primary-0000';write(folder/'interference.json',health)
    write(folder/'complete.json',dict(host='127x01',descriptor=dict(id='primary-0000',population='primary',cell=0,replaces=None),interference=health,interference_sha256=sha(folder/'interference.json'),games={'unreadable.json':'sealed'}))
    ledger=S.health_ledger(folder.parent,[],'blind-sha');assert ledger['blocks'][0]['apt_flagged']
    assert not ledger['blocks'][0]['ssh_flagged'] and 'games' not in str(ledger)
    health['ubuntu_apt']['processes'][0]['cpu_ticks']=0
    with pytest.raises(AssertionError):S.apt_flagged(health)
    with pytest.raises(AssertionError):S.apt_flagged({'apt_flagged':True})

def test_apt_sensitivity_is_separate_and_primary_rng_unchanged():
    _,_,meter=measured(31)
    rows={'primary':[dict(id='a',cell=0,complete_sha256='a',interference={'ubuntu_apt':A.finish(meter,60)},loss={a:1 for a in ARMS},draw={a:False for a in ARMS},win={a:False for a in ARMS}),dict(id='b',cell=1,complete_sha256='b',interference={},loss={a:0 for a in ARMS},draw={a:False for a in ARMS},win={a:True for a in ARMS})]}
    original=copy.deepcopy(rows);ledger={'blocks':[dict(id=r['id'],complete_sha256=r['complete_sha256'],ssh_flagged=False,apt_flagged=S.apt_flagged(r['interference'])) for r in rows['primary']]}
    rng=np.random.default_rng(2026101040);primary=population_stats(rows['primary'],rng,100);state=copy.deepcopy(rng.bit_generator.state)
    apt=S.analyze_apt(rows,ledger,100,2026101040,population_stats,np.random.default_rng)
    ssh=S.analyze(rows,ledger,100,2026101040,population_stats,np.random.default_rng)
    assert rows==original and rng.bit_generator.state==state and primary['n']==2
    assert apt['populations']['primary']['retained']==1 and not apt['selection_eligible']
    assert ssh['populations']['primary']['retained']==2
    only={'primary':rows['primary'][:1]};one={'blocks':ledger['blocks'][:1]}
    result=S.analyze_apt(only,one,100,2026101040,population_stats,np.random.default_rng)['populations']['primary']
    assert result['status']=='NO_UNFLAGGED_BLOCKS' and result['statistics'] is None

from test_op4 import test_non_lan_and_unknown_fall_back_to_identity_guard, test_non_ssh_foreign_stops_even_with_lan_ssh_family, test_console_stop_has_no_low_load_exception
