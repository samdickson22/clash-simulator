"""Controller transitions preserve closed scores and cannot launch stage2."""
import json
from unittest.mock import patch
import pytest
import controller_offline_record as c

def fixture(job):
    (job/'offline').mkdir()
    return {'arms':{arm:{'steps':4883} for arm in c.HOSTS}}, {'offline':{},'stage2':{}}

def test_closed_scores_are_never_repeated(tmp_path):
    frozen,launched=fixture(tmp_path)
    for arm in c.HOSTS:(tmp_path/'offline'/f'{arm}.json').write_text(json.dumps({'survives':False}))
    with patch.object(c,'remote') as remote:
        assert len(c.tick_offline(tmp_path,frozen,launched))==7
        remote.assert_not_called()

def test_active_attempt_is_adopted_without_new_launch(tmp_path):
    frozen,launched=fixture(tmp_path)
    with patch.object(c,'remote',return_value={'status':'active'}) as remote:
        assert c.tick_offline(tmp_path,frozen,launched)=={}
        assert len(remote.call_args_list)==7
        assert all(call.args[2:4]==('status',1) for call in remote.call_args_list)

def test_missing_fit_waits_for_clean_seal(tmp_path):
    frozen,launched=fixture(tmp_path)
    with patch.object(c,'remote',return_value={'status':'not-started'}) as remote,patch.object(c,'collection_ready',return_value=False):
        assert c.tick_offline(tmp_path,frozen,launched)=={}
        assert all(call.args[2:4]==('status',1) for call in remote.call_args_list)

def test_only_stage1_can_start(tmp_path):
    frozen,launched=fixture(tmp_path)
    def remote(job,host,operation,stage,arm):
        assert stage==1
        return {'status':'not-started'} if operation=='status' else {'status':'launched','pid':123,'pgid':123}
    with patch.object(c,'remote',side_effect=remote),patch.object(c,'collection_ready',return_value=True):
        assert c.tick_offline(tmp_path,frozen,launched)=={}
        assert len(launched['offline'])==7 and launched['stage2']=={}

def test_closed_remote_results_and_whole_meters_collected_once(tmp_path):
    frozen,launched=fixture(tmp_path)
    with patch.object(c,'remote',return_value={'status':'done','result':{'survives':False},'meter':{'children_cpu_seconds':2}}) as remote:
        assert len(c.tick_offline(tmp_path,frozen,launched))==7
        c.tick_offline(tmp_path,frozen,launched)
        assert len(remote.call_args_list)==7
        assert json.loads((tmp_path/'offline/X6-remote-meter.json').read_text())['children_cpu_seconds']==2

def test_failed_attempt_is_not_silently_relaunched(tmp_path):
    frozen,launched=fixture(tmp_path)
    with patch.object(c,'remote',return_value={'status':'failed'}):
        with pytest.raises(RuntimeError):c.tick_offline(tmp_path,frozen,launched)
    assert launched=={'offline':{},'stage2':{}}
