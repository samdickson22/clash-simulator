"""No games: K timing occupancy/quiet-gap refusal and unchanged G handoff."""
from unittest.mock import patch
import evaluation_k_yield as gate

def setup(tmp_path):
    return (patch.object(gate.socket,'gethostname',return_value='127x03'),
            patch.object(gate.os,'getpriority',return_value=19),
            patch.object(gate.os,'sched_getscheduler',return_value=gate.os.SCHED_IDLE),
            patch.object(gate.time,'time',return_value=0))

def test_live_k_pgid_blocks_even_with_completion_marker(tmp_path):
    (tmp_path/'REPORTING-R3-DONE').touch()
    with patch.object(gate,'K_ROOT',tmp_path),patch.object(gate.subprocess,'check_output',return_value='123 120 python reports/explore/k-v2/run.py --out reporting'):
        s=gate.k_status();assert not s['released'] and s['live_pgids']==[120]

def test_quiet_gap_without_k_release_is_not_admission(tmp_path):
    with patch.object(gate,'K_ROOT',tmp_path),patch.object(gate.subprocess,'check_output',return_value=''):
        assert not gate.k_status()['released']

def test_successful_k_release_and_empty_pgid_pass(tmp_path):
    (tmp_path/'REPORTING-R3-DONE').touch()
    with patch.object(gate,'K_ROOT',tmp_path),patch.object(gate.subprocess,'check_output',return_value=''):
        assert gate.k_status()['released']

def test_blocked_k_never_requests_g_stop(tmp_path):
    a,b,c,d=setup(tmp_path)
    with a,b,c,d,patch.object(gate,'k_status',return_value={'released':False}),patch.object(gate,'g_admission') as g,patch.object(gate,'write_json'),patch.object(gate.subprocess,'check_output',return_value='UTC'):
        assert not gate.admission(tmp_path,['offline','X1'],{})
        g.assert_not_called()

def test_k_release_still_requires_g_admission(tmp_path):
    a,b,c,d=setup(tmp_path)
    with a,b,c,d,patch.object(gate,'k_status',return_value={'released':True}),patch.object(gate,'g_admission',return_value=False) as g,patch.object(gate,'write_json'),patch.object(gate.subprocess,'check_output',return_value='UTC'):
        assert not gate.admission(tmp_path,['stage2','X1'],{})
        g.assert_called_once()

def test_home01_uses_g_handoff_without_k03_check(tmp_path):
    a,b,c,d=setup(tmp_path)
    with a,b,c,d,patch.object(gate.socket,'gethostname',return_value='127x01'),patch.object(gate,'home01_fit_finished',return_value=True),patch.object(gate,'k_status') as k,patch.object(gate,'g_admission',return_value=True):
        assert gate.admission(tmp_path,['stage2','X1'],{})
        k.assert_not_called()

def test_home01_refuses_evaluation_during_x4_fit(tmp_path):
    a,b,c,d=setup(tmp_path)
    with a,b,c,d,patch.object(gate.socket,'gethostname',return_value='127x01'),patch.object(gate,'home01_fit_finished',return_value=False),patch.object(gate,'g_admission') as g:
        assert not gate.admission(tmp_path,['stage2','X1'],{})
        g.assert_not_called()

def test_home01_completion_requires_final_step_and_absent_fit_pids(tmp_path):
    import json
    import os
    out=tmp_path/'fits/X4';out.mkdir(parents=True)
    complete=out/'complete.json';complete.write_text(json.dumps({'stopped':False,'step':4883}))
    (tmp_path/'X4-exit.json').write_text('{}')
    launch=tmp_path/'X4-launch.json';launch.write_text(json.dumps({'supervisor_pid':99999999,'trainer_pid':99999998}))
    assert gate.home01_fit_finished(tmp_path)
    launch.write_text(json.dumps({'supervisor_pid':99999999,'trainer_pid':os.getpid()}))
    assert not gate.home01_fit_finished(tmp_path)
