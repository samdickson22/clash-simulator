"""Metadata-only qualification of descriptive selection, guards, interleaving and labels."""
import ast
import json
from pathlib import Path
import pytest
import postkill_admission as a

def records():
    return {'X'+str(i):{'survives':False,'teacher':{'metrics':{'play_recall':{'value':i/100}}}} for i in range(1,8)}

def test_selection_ignores_frozen_kills():assert a.chosen_from_results(records())==['X1','X2','X7']
def test_selection_waits_all_seven():
    r=records();r.pop('X5')
    with pytest.raises(AssertionError):a.chosen_from_results(r)
def test_selection_numeric_tie():
    r=records()
    for value in r.values():value['teacher']['metrics']['play_recall']['value']=.25
    assert a.chosen_from_results(r)==['X1','X2','X3']
def test_family_cap_not_applied_to_descriptive():assert a.chosen_from_results(records())==['X1','X2','X7']
def test_rotated_whole_block():
    arms=['C-v1','X1','X2','X7','K0']
    for i in range(10):assert a.arm_order(arms,i)==arms[i%5:]+arms[:i%5]
def test_labels_always_nonadoptable():
    for value in ({},{'adoption_eligible':True,'never_adoptable':False}):
        r=a.labelled(value);assert r['never_adoptable'] and not r['adoption_eligible'] and r['lane']=='exploration; never adoptable'
def test_context_requires_host01(monkeypatch):
    monkeypatch.setattr(a.socket,'gethostname',lambda:'127x03')
    with pytest.raises(AssertionError):a.context()
def test_context_other_nice10(monkeypatch):
    monkeypatch.setattr(a.socket,'gethostname',lambda:'127x01');monkeypatch.setattr(a.os,'getpriority',lambda *_:10)
    monkeypatch.setattr(a.os,'sched_getscheduler',lambda *_:a.os.SCHED_IDLE)
    with pytest.raises(AssertionError):a.context()
    monkeypatch.setattr(a.os,'sched_getscheduler',lambda *_:a.os.SCHED_OTHER)
    assert a.context()['scheduler']=='SCHED_OTHER'
def test_reserved_banks_expanded_disjoint():
    ours=[(a.BASE,600),(a.SMOKE_BASE,32)];reserved=[(4503601507370496,256),(4503601517370496,600),(4503601527370496,32),(4503601607370496,1000000),(4503601707370496,32768),(4503601807370496,2400),(4503601907370496,600),(4503601917370496,8),(4503601927370496,65536),(4503602307370496,600),(4503602317370496,32)]
    offsets=(0,13,100000,100001,100002,100003,271828,271829)
    for base,count in ours:
        for other,n in reserved:
            for o in offsets:
                for q in offsets:assert base+o+count<=other+q or other+q+n<=base+o
def test_adapter_has_unmodified_default_layer():
    source=Path(__file__).with_name('k_postkill_sdefault.py').read_text()
    assert 'select_default(p.core,action,defaults.get(actor,fallback),default_source,deadline)' in source
    assert 'poll_before_search(self,tick,packet,public_events,' in source and 'original_candidates(packet,list(p.core.refine_proposals))' in source
    assert 'human.write=labelled_write' in source and 'scheduler=\'SCHED_OTHER\'' in source

def test_interrupted_block_reaps_child_excludes_whole_block(tmp_path,monkeypatch):
    import postkill_block_worker as block
    from types import SimpleNamespace
    child=SimpleNamespace(returncode=None,poll=lambda:None,terminate=lambda:setattr(child,'terminated',True),wait=lambda timeout:setattr(child,'reaped',True))
    monkeypatch.setattr(block.sys,'argv',['postkill_block_worker.py','--job',str(tmp_path),'--index','0','--arms','C-v1','X1','X2','X7','K0'])
    (tmp_path/'postkill-sdefault-addendum.json').write_text('{}')
    monkeypatch.setattr(block,'frozen',lambda *_:None)
    monkeypatch.setattr(block,'context',lambda:dict(host='127x01',affinity=[0],scheduler='SCHED_OTHER',nice=10,torch_threads=1))
    states=iter([True,True,False]);monkeypatch.setattr(block,'allowed',lambda *_:next(states))
    monkeypatch.setattr(block,'load_receipt',lambda:{})
    monkeypatch.setattr(block.subprocess,'Popen',lambda *_args,**_kwargs:child)
    monkeypatch.setattr(block.signal,'signal',lambda *_:None)
    with pytest.raises(InterruptedError):block.main()
    assert child.terminated and child.reaped
    assert not (tmp_path/'postkill-sdefault/blocks/0000.json').exists()

def test_reducer_has_no_gate():
    tree=ast.parse(Path(__file__).with_name('reduce_postkill.py').read_text())
    constants=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
    assert not any(s in constants for s in ('survives','kill_reasons'))
