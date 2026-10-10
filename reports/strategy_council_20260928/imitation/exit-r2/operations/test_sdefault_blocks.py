"""Reject unmatched-load admission and require all-six gate selection."""
import json
from unittest.mock import patch
import pytest
import stage3_sdefault_admission as a

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))

def gates(job):
    for i in range(1,7):
        arm=f'X{i}'
        write(job/'offline'/f'{arm}.json',dict(survives=True,teacher={'metrics':{'hard_action_agreement':{'value':.8}}}))
        write(job/'stage2'/f'{arm}.json',dict(survives=True,loss=.4))

def test_selection_waits_for_every_arm_and_caps_three(tmp_path):
    gates(tmp_path);(tmp_path/'stage2/X6.json').unlink()
    with patch.object(a,'load_experiment',return_value={'arms':{f'X{i}':{} for i in range(1,7)}}):
        with pytest.raises(FileNotFoundError):a.selection(tmp_path)
        write(tmp_path/'stage2/X6.json',dict(survives=True,loss=.4))
        assert a.selection(tmp_path)==['X1','X2','X3']
        write(tmp_path/'stage2/X6.json',dict(survives=True,loss=.3))
        assert a.selection(tmp_path)==['X6','X1','X2']

def test_k_release_marker_does_not_admit_active_timing_processes(tmp_path):
    with patch.object(a,'K_ROOT',tmp_path),patch.object(a.subprocess,'check_output',return_value=''):
        assert not a.timing_released()
        (tmp_path/'REPORTING-R3-DONE').touch()
        assert a.timing_released()
        with patch.object(a.subprocess,'check_output',return_value='python reports/explore/k-v2/run.py --out reporting'):
            assert not a.timing_released()

def test_stop_and_memory_pressure_override_k_release(tmp_path):
    with patch.object(a,'context'),patch.object(a,'timing_released',return_value=True),patch.object(a,'load_receipt',return_value={'mem_available_bytes':25*2**30}),patch.object(a.time,'time',return_value=0):
        assert a.allowed(tmp_path)
        (tmp_path/'REPORTING.STOP').touch();assert not a.allowed(tmp_path)
        (tmp_path/'REPORTING.STOP').unlink()
        with patch.object(a,'load_receipt',return_value={'mem_available_bytes':23*2**30}):assert not a.allowed(tmp_path)

def test_gate_failure_excludes_arm_without_stage2(tmp_path):
    gates(tmp_path)
    write(tmp_path/'offline/X1.json',dict(survives=False))
    (tmp_path/'stage2/X1.json').unlink()
    with patch.object(a,'load_experiment',return_value={'arms':{f'X{i}':{} for i in range(1,7)}}):
        assert a.selection(tmp_path)==['X2','X3','X4']

@pytest.mark.parametrize('play_gate,expected',[(-2.,2304),(-.1,1)])
def test_default_argmax_joint_gate_and_legal_mask(play_gate,expected):
    import numpy as np
    import torch
    from types import SimpleNamespace
    from sdefault import student_choice
    mask=np.zeros(2306,dtype=bool);mask[[1,2,2304]]=True
    tiles=torch.zeros((1,4,576));tiles[0,0,9]=100 # Highest unmasked score is illegal.
    policy=SimpleNamespace(costs={},model=SimpleNamespace(log_policy=lambda _:{
        'gate':torch.tensor([[-.4,play_gate]]),'card':torch.zeros((1,4)),'tile':tiles}))
    with patch('sdefault.single_features',return_value=None),patch('sdefault.model_packet',return_value=None):
        action,order=student_choice(policy,None,mask,{})
    assert action==expected and order==(1,2)

def test_interrupted_block_reaps_game_and_never_completes(tmp_path):
    import stage3_block_worker as block
    from types import SimpleNamespace
    child=SimpleNamespace(returncode=None,poll=lambda:None,terminate=lambda:setattr(child,'terminated',True),
        wait=lambda timeout:setattr(child,'reaped',True))
    argv=['stage3_block_worker.py','--job',str(tmp_path),'--index','0','--arms','C-v1','X1','K0']
    (tmp_path/'stage3-sdefault-addendum.json').write_text('{}')
    with patch.object(block.sys,'argv',argv),patch.object(block,'frozen'),patch.object(block,'context',return_value={
        'host':'127x03','affinity':[0],'scheduler':'SCHED_IDLE','nice':19,'torch_threads':1}),patch.object(block,'allowed',side_effect=[True,True,False]),patch.object(block,'load_receipt',return_value={}),patch.object(block.subprocess,'Popen',return_value=child),patch.object(block.signal,'signal'):
        with pytest.raises(InterruptedError):block.main()
    assert child.terminated and child.reaped
    assert not (tmp_path/'stage3-sdefault/blocks/0000.json').exists()
