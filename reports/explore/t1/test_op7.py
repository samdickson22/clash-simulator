"""OP-7 provenance denial, exact budgets, reaping and sealed sensitivity proofs."""
import copy, hashlib, os, time
from pathlib import Path
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
             uid=0,apt_uid_snapshot=(0,0),apt_helper_uid_snapshot=105,cmd='/usr/bin/python3 /usr/bin/unattended-upgrade --download-only',
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
    {'uid':3822945,'apt_uid_snapshot':(3822945,3822945)},{'apt_cgroup_snapshot':None},
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
    for changed in [dict(c,uid=3822945,apt_uid_snapshot=(3822945,3822945)),dict(c,apt_cgroup_snapshot='/other'),dict(c,ppid=1)]:
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
    rows=A.apply([root(),root(pid=8,ppid=1,uid=3822945,apt_uid_snapshot=(3822945,3822945),cmd='/usr/bin/python3 /foreign.py',apt_cgroup_snapshot=None)])
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


@pytest.mark.parametrize('module,budget_key',[(A,'apt_budget'),(__import__('ssh_budget'),'ssh_budget')])
def test_observed_five_second_child_reaping_is_not_charged_twice(module,budget_key):
    p=root();c=child(p)
    for r in (p,c):r[budget_key]={'source':'129.65.221.14 123 129.65.221.18 22'}
    meter=module.begin([p,c],hz=100)
    for ticks in range(100,501,100):
        module.update(meter,[p,dict(c,cpu_ticks=ticks)])
    assert module.finish(meter,60)['cpu_ticks']==500
    before=[p,dict(c,cpu_ticks=500)];after=[dict(p,child_cpu_ticks=500)]
    sample=module.sample(before,after,1,hz=100)
    assert sample['cpu_ticks']==0 and not sample['stop']
    module.update(meter,after)
    assert module.finish(meter,60)['cpu_ticks']==500

@pytest.mark.parametrize('module,budget_key',[(A,'apt_budget'),(__import__('ssh_budget'),'ssh_budget')])
def test_nested_reaping_each_tick_once_and_unobserved_child_still_counts(module,budget_key):
    p=root();c=child(p);g=child(c,pid=p['pid']+2);leaf=child(g,pid=p['pid']+3)
    for r in (p,c,g,leaf):r[budget_key]={'source':'129.65.221.14 123 129.65.221.18 22'}
    meter=module.begin([p,c,g,leaf],hz=100)
    rows=[p,c,g,dict(leaf,cpu_ticks=100)];module.update(meter,rows)
    rows=[p,c,dict(g,child_cpu_ticks=100)];module.update(meter,rows)
    rows=[p,dict(c,child_cpu_ticks=100)];module.update(meter,rows)
    rows=[dict(p,child_cpu_ticks=100)];module.update(meter,rows)
    assert module.finish(meter,60)['cpu_ticks']==100
    module.update(meter,[dict(p,child_cpu_ticks=147)])
    assert module.finish(meter,60)['cpu_ticks']==147

@pytest.mark.parametrize('module,budget_key',[(A,'apt_budget'),(__import__('ssh_budget'),'ssh_budget')])
def test_simultaneous_nested_reaping_and_delayed_wait_credit(module,budget_key):
    p=root();c=child(p);g=child(c,pid=p['pid']+2)
    for r in (p,c,g):r[budget_key]={'source':'129.65.221.14 123 129.65.221.18 22'}
    meter=module.begin([p,c,g],hz=100)
    module.update(meter,[p,dict(c,cpu_ticks=100),dict(g,cpu_ticks=100)])
    module.update(meter,[p])  # parent was scanned before wait() reflected the reaping
    module.update(meter,[dict(p,child_cpu_ticks=200)])
    assert module.finish(meter,60)['cpu_ticks']==200

@pytest.mark.parametrize('module,budget_key',[(A,'apt_budget'),(__import__('ssh_budget'),'ssh_budget')])
def test_reaped_preblock_cpu_is_charged_without_recharging_observed_delta(module,budget_key):
    p=root();c=child(p,cpu_ticks=500)
    for r in (p,c):r[budget_key]={'source':'129.65.221.14 123 129.65.221.18 22'}
    meter=module.begin([p,c],hz=100)
    module.update(meter,[p,dict(c,cpu_ticks=600)])
    module.update(meter,[dict(p,child_cpu_ticks=600)])
    assert module.finish(meter,60)['cpu_ticks']==600


def test_full_hybrid_cgroup_and_uid_status_evidence(tmp_path):
    lines=['12:blkio:/system.slice/apt-daily.service','11:cpu,cpuacct:/system.slice/apt-daily.service','1:name=systemd:/system.slice/apt-daily.service','0::/system.slice/apt-daily.service']
    (tmp_path/'cgroup').write_text('\n'.join(lines)+'\n')
    assert A.capture_cgroup(tmp_path)=='/system.slice/apt-daily.service'
    (tmp_path/'status').write_text('Name: http\nUid:\t105\t105\t105\t105\n')
    assert A.capture_uids(tmp_path)==(105,105)
    (tmp_path/'status').write_text('Uid: 105 0 0 0\n')
    assert A.capture_uids(tmp_path)==(105,0)
    (tmp_path/'passwd').write_text('_apt:x:105:65534::/nonexistent:/usr/sbin/nologin\n')
    assert A.apt_uid(tmp_path/'passwd')==105
    (tmp_path/'passwd').write_text('_apt:x:0:65534::/:/bin/sh\n')
    assert A.apt_uid(tmp_path/'passwd') is None


def method(parent,**changes):
    return child(parent,uid=105,apt_uid_snapshot=(105,105),cmd='/usr/lib/apt/methods/http',exe='/usr/lib/apt/methods/http',exe_evidence='proc/exe',apt_helper_exe_snapshot={'path':'/usr/lib/apt/methods/http','evidence':'proc/exe'},**changes)


def test_apt_method_requires_real_effective_uid_exe_cgroup_and_root(tmp_path):
    parent=root();m=method(parent);rows=A.apply([parent,m]);assert rows[1]['apt_budget']['member_kind']=='_apt_method'
    assert not H.foreign_compute(tmp_path,rows)
    meter=A.begin(rows,hz=100);A.update(meter,A.apply([root(),dict(m,cpu_ticks=31)]))
    assert S.apt_flagged({'ubuntu_apt':A.finish(meter,60)})
    for fields in [dict(apt_helper_uid_snapshot=None),dict(apt_uid_snapshot=(105,0)),dict(apt_uid_snapshot=None),dict(apt_helper_exe_snapshot={'path':'/tmp/http','evidence':'proc/exe'}),dict(apt_helper_exe_snapshot=None),dict(apt_helper_exe_snapshot={'path':'/usr/lib/apt/methods/http','evidence':'argv0'}),dict(apt_cgroup_snapshot='/other'),dict(ppid=1)]:
        denied=A.apply([root(),dict(m,**fields)])[-1]
        assert not denied.get('apt_budget') and H.foreign_compute(tmp_path,[denied])
    # A non-dumpable user's root-owned /proc directory is not UID-0 evidence.
    impostor=A.apply([root(apt_uid_snapshot=(3822945,3822945))])[0]
    assert not impostor.get('apt_budget') and H.foreign_compute(tmp_path,[impostor])


def test_unbalanced_apt_lookalike_quote_stops(tmp_path):
    r=root(cmd="/tmp/apt-get 'x",apt_cgroup_snapshot=None)
    assert A.apt_command(r) and H.foreign_compute(tmp_path,[r])


def test_missing_sensitivity_flag_fails_closed():
    rows={'primary':[dict(id='a',complete_sha256='a',cell=0,interference={})]}
    ledger={'blocks':[dict(id='a',complete_sha256='a')]}
    with pytest.raises(KeyError):S.analyze(rows,ledger,1,2026101040,lambda *args:None,np.random.default_rng)


def test_union_sensitivity_and_both_flag_counts_never_change_primary_rng():
    _,_,m=measured(31);apt={'ubuntu_apt':A.finish(m,60)}
    ssh={'ssh_family':dict(source_proven_cpu_ticks=31,block_seconds=60,clock_ticks_per_second=100,processes=[dict(source_proven_cpu_ticks=31)],ssh_flagged=True)}
    interference=[{},apt,ssh,{**apt,**ssh}]
    rows={'primary':[dict(id=str(i),cell=i%2,complete_sha256=str(i),interference=proof,loss={a:i%2 for a in ARMS},draw={a:False for a in ARMS},win={a:i%2==0 for a in ARMS}) for i,proof in enumerate(interference)]}
    ledger={'blocks':[dict(id=r['id'],complete_sha256=r['complete_sha256'],population='primary',cell=r['cell'],ssh_flagged=S.flagged(r['interference']),apt_flagged=S.apt_flagged(r['interference']),ssh_or_apt_flagged=S.union_flagged(r['interference']),apt_meter_stop=False,ssh_meter_stop=False) for r in rows['primary']]}
    original=copy.deepcopy(rows);rng=np.random.default_rng(2026101040)
    primary=population_stats(rows['primary'],rng,100);state=copy.deepcopy(rng.bit_generator.state)
    union=S.analyze_union(rows,ledger,100,2026101040,population_stats,np.random.default_rng)
    assert union['populations']['primary']['excluded']==3 and union['populations']['primary']['retained']==1
    counts=S.flag_counts(ledger['blocks'])['primary'];assert counts['both']==1 and counts['either']==3
    assert rows==original and rng.bit_generator.state==state and primary['n']==4


@pytest.mark.parametrize('approved_overwrite',[False,True])
def test_census_apt_allowlist_order_and_supervisor_stop_payload(tmp_path,monkeypatch,approved_overwrite):
    import supervise as V
    import ssh_budget as B
    r=root();r['tty']=0
    monkeypatch.setattr(H,'processes',lambda:[dict(r)])
    monkeypatch.setattr('system_bus.member',lambda *args:False)
    monkeypatch.setattr('idle_services.member',lambda *args:False)
    monkeypatch.setattr(H,'perception_reader',lambda *args:False)
    monkeypatch.setattr('ssh_transport.copier_activity',lambda *args:False)
    monkeypatch.setattr('ssh_transport.approved_parent',lambda *args:approved_overwrite)
    monkeypatch.setattr(B.FAMILIES,'apply',lambda rows,j:rows)
    monkeypatch.setattr(B,'record',lambda *args:None)
    monkeypatch.setattr('perception_confirmation.CONFIRMATION.apply',lambda *args,**kwargs:None)
    rows,foreign,active,_=H.census(tmp_path,[root()],['primary-0000'])
    assert rows[0]['allowlist_kind']==('approved_sshd_transport' if approved_overwrite else 'ubuntu_apt_budget')
    assert rows[0]['apt_budget'] and not foreign and not active
    meter=A.begin(rows,hz=100);A.update(meter,[dict(rows[0],cpu_ticks=151)])
    assert A.finish(meter,60)['cpu_ticks']==151
    assert 'primary-0000' in (tmp_path/'ubuntu-apt-occurrences.jsonl').read_text()
    false={'stop':False};true={'stop':True};c={'positive':False}
    assert V.guard_reason(c,[r],[],true,[],true,[])=='foreign_compute'
    assert V.guard_reason(c,[],[],true,[],true,[])=='ssh_family_sample_budget'
    assert V.guard_reason(c,[],[],false,[],true,[])=='ubuntu_apt_sample_budget'
    payload=V.stop_receipt('ubuntu_apt_sample_budget',[],[],c,false,dict(true,cpu_ticks=151))
    write(tmp_path/'stop-reason.json',payload)
    from common import read
    assert read(tmp_path/'stop-reason.json')['ubuntu_apt_sample']['cpu_ticks']==151


@pytest.mark.parametrize('error',[2,1,None])
def test_helper_non_eacces_errors_no_fallback(error):
    assert A.helper_exe(None,error,'/usr/lib/apt/methods/http') is None

@pytest.mark.parametrize('path',['http','/usr/lib/apt/methods/../methods/http','/tmp/http'])
def test_helper_relative_escape_or_wrong_path_no_fallback(path):
    import errno
    assert A.helper_exe(None,errno.EACCES,path) is None


def test_helper_eacces_root_owned_nonwritable_file_only(monkeypatch,tmp_path):
    import errno
    methods=tmp_path/'methods';methods.mkdir();file=methods/'http';file.write_text('synthetic method');file.chmod(0o755)
    monkeypatch.setattr(A,'METHODS',methods)
    # This test runs as sdicks02; substitute only file owner for the synthetic fixture.
    original=Path.stat
    def stat_override(path,*args,**kwargs):
        value=original(path,*args,**kwargs)
        if path==file:
            values=list(value);values[4]=0;return os.stat_result(values)
        return value
    monkeypatch.setattr(Path,'stat',stat_override)
    proof=A.helper_exe(None,errno.EACCES,str(file))
    assert proof['evidence']=='argv0 (proc/exe EACCES, unprivileged)' and proof['file_uid']==0
    r=method(root());r['apt_helper_exe_snapshot']=proof
    assert A.apply([root(),r])[-1].get('apt_budget')
    for mode in (0o775,0o757):
        file.chmod(mode);assert A.helper_exe(None,errno.EACCES,str(file)) is None
    file.chmod(0o755);monkeypatch.setattr(Path,'stat',original)
    assert A.helper_exe(None,errno.EACCES,str(file)) is None  # not root-owned



def test_union_still_validates_apt_proof_when_ssh_is_flagged():
    ssh={'ssh_family':dict(source_proven_cpu_ticks=31,block_seconds=60,clock_ticks_per_second=100,processes=[dict(source_proven_cpu_ticks=31)],ssh_flagged=True),'apt_flagged':True}
    with pytest.raises(AssertionError):S.union_flagged(ssh)



def test_process_collector_captures_status_cgroup_and_raw_argv0_before_identity_recheck(tmp_path,monkeypatch):
    proc=tmp_path/'proc';proc.mkdir();folder=proc/'542173';folder.mkdir()
    values=['0']*24;values[0]='S';values[1]='1';values[2]='542173';values[19]='100'
    (folder/'stat').write_text('542173 (http) '+' '.join(values))
    (folder/'cmdline').write_bytes(b'/usr/lib/apt/methods/http\x00')
    (folder/'status').write_text('Uid: 105 105 105 105\n')
    (folder/'cgroup').write_text('1:name=systemd:/system.slice/apt-daily.service\n0::/system.slice/apt-daily.service\n')
    (folder/'environ').write_bytes(b'')
    original=Path
    monkeypatch.setattr(H,'Path',lambda path:proc if str(path)=='/proc' else original(path))
    monkeypatch.setattr(A,'apt_uid',lambda:105)
    monkeypatch.setattr(H.os,'sched_getaffinity',lambda _:set())
    # Missing exe is ENOENT, so no argv0 fallback despite the helper-shaped name.
    rows=H.processes();assert len(rows)==1
    row=rows[0];assert row['apt_uid_snapshot']==(105,105) and row['apt_helper_uid_snapshot']==105
    assert row['apt_cgroup_snapshot']=='/system.slice/apt-daily.service'
    assert row['apt_helper_exe_snapshot'] is None and row['exe_evidence']=='unavailable'
    assert A.apply(rows)[0].get('apt_budget') is None
