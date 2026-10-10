"""Metadata-only completion/cleanup races: never read or evaluate a policy."""
import json
from fit_collection_ready import snapshot


def setup(tmp_path):
    fit = tmp_path / 'fits/X1'
    fit.mkdir(parents=True)
    values = {
        fit / 'complete.json': dict(step=4883, stopped=False, pins={'input': 'frozen'}),
        fit / 'segment.json': dict(status='returned', cursor_start=0, optimizer_steps=4883),
        fit / 'inputs.json': dict(pins={'input': 'frozen'}),
        fit / 'runtime.json': {},
        tmp_path / 'X1-exit.json': dict(exit_code=0, reason=None),
        tmp_path / 'X1-launch.json': dict(supervisor_pgid=123, trainer_pgid=456),
    }
    for path, value in values.items():
        path.write_text(json.dumps(value))
    (fit / 'step-00004883.pt').write_bytes(b'fixture only, never loaded')
    return fit


def probe(tmp_path, live=()):
    return snapshot(tmp_path, 'X1', 4883, alive=lambda group: group in live)


def test_completion_before_loader_cleanup_is_queued(tmp_path):
    fit = setup(tmp_path)
    (fit / 'segment.json').unlink()
    (tmp_path / 'X1-exit.json').unlink()
    state = probe(tmp_path)
    assert not state['ready'] and set(state['missing']) == {'segment', 'exit'}


def test_segment_before_supervisor_exit_is_queued(tmp_path):
    setup(tmp_path)
    (tmp_path / 'X1-exit.json').unlink()
    assert not probe(tmp_path)['ready']


def test_live_supervisor_or_trainer_group_is_queued(tmp_path):
    setup(tmp_path)
    for group in (123, 456):
        assert probe(tmp_path, (group,))['live_owned_pgids'] == [group]
        assert not probe(tmp_path, (group,))['ready']


def test_complete_segment_clean_exit_and_absent_groups_admit(tmp_path):
    setup(tmp_path)
    assert probe(tmp_path)['ready']


def test_resource_yield_is_not_final_completion(tmp_path):
    fit = setup(tmp_path)
    (fit / 'complete.json').write_text(json.dumps(dict(step=4750, stopped=True, pins={})))
    assert not probe(tmp_path)['ready']


def test_nonzero_exit_is_never_admitted(tmp_path):
    setup(tmp_path)
    (tmp_path / 'X1-exit.json').write_text(json.dumps(dict(exit_code=1, reason=None)))
    assert not probe(tmp_path)['ready']


def test_guard_stop_even_at_final_step_is_not_clean_exit(tmp_path):
    setup(tmp_path)
    (tmp_path / 'X1-exit.json').write_text(json.dumps(dict(exit_code=0, reason='owned STOP')))
    assert not probe(tmp_path)['ready']


def test_final_segment_cursor_includes_exact_resume(tmp_path):
    fit = setup(tmp_path)
    (fit / 'segment.json').write_text(json.dumps(dict(status='returned', cursor_start=4500, optimizer_steps=383)))
    assert probe(tmp_path)['ready']
    (fit / 'segment.json').write_text(json.dumps(dict(status='returned', cursor_start=4500, optimizer_steps=382)))
    assert not probe(tmp_path)['ready']


def test_missing_checkpoint_or_changed_input_pins_is_refused(tmp_path):
    fit = setup(tmp_path)
    (fit / 'inputs.json').write_text(json.dumps(dict(pins={'input': 'changed'})))
    assert not probe(tmp_path)['ready']
    (fit / 'step-00004883.pt').unlink()
    assert not probe(tmp_path)['ready']


def test_partial_json_is_retried_without_crashing_controller(tmp_path):
    fit = setup(tmp_path)
    (fit / 'segment.json').write_text('{')
    assert not probe(tmp_path)['ready']
