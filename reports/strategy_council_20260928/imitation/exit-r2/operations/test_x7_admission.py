"""Metadata and stub-shell qualification; no policy inference or games."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest
import experiment_x7 as experiment
import stage3_sdefault_admission_x7 as admission


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(job):
    write(job/'freeze.json', {'original': True})
    write(job/'x6-addendum.json', {'original': True})
    write(job/'x7-seed-audit.json', {'passed': True})
    write(job/'x7-addendum.json', dict(committed_before_launch=True,
        base_freeze_sha256=experiment.sha(job/'freeze.json'),
        x6_addendum_sha256=experiment.sha(job/'x6-addendum.json'),
        seed_audit_sha256=experiment.sha(job/'x7-seed-audit.json'), files={},
        arm=dict(train_seed=2026101007, temperature=.003, teacher_fraction=1., steps=4883)))


def test_composes_seven_preserving_original_six(tmp_path):
    fixture(tmp_path)
    original={'arms':{f'X{i}':{'frozen':i} for i in range(1,7)},'seed':2026101001}
    with patch.object(experiment,'original',side_effect=lambda _:copy.deepcopy(original)):
        result=experiment.load_experiment(tmp_path)
    assert {key:result['arms'][key] for key in original['arms']}==original['arms']
    assert result['seed']==2026101001 and result['arms']['X7']['train_seed']==2026101007
    assert len(original['arms'])==6 and len(result['arms'])==7


def test_refuses_unqualified_seed_audit(tmp_path):
    fixture(tmp_path)
    write(tmp_path/'x7-seed-audit.json',{'passed':False})
    with patch.object(experiment,'original',return_value={'arms':{}}),pytest.raises(AssertionError):
        experiment.load_experiment(tmp_path)


def test_refuses_changed_original_freeze(tmp_path):
    fixture(tmp_path)
    write(tmp_path/'freeze.json',{'changed':True})
    with patch.object(experiment,'original',return_value={'arms':{}}),pytest.raises(AssertionError):
        experiment.load_experiment(tmp_path)


def gates(job):
    for i in range(1,8):
        write(job/'offline'/f'X{i}.json',dict(survives=True,teacher={'metrics':{'hard_action_agreement':{'value':.8}}}))
        write(job/'stage2'/f'X{i}.json',dict(survives=True,loss=.4))


def selected(job):
    with patch.object(admission,'load_experiment',return_value={'arms':{f'X{i}':{} for i in range(1,8)}}):
        return admission.selection(job)


def test_all_seven_gate_results_required(tmp_path):
    gates(tmp_path)
    (tmp_path/'stage2/X7.json').unlink()
    with pytest.raises(FileNotFoundError):selected(tmp_path)


def test_family_tie_selects_x1_only(tmp_path):
    gates(tmp_path)
    assert selected(tmp_path)==['X1','X2','X3']


def test_x7_family_winner_competes_equally_not_only_overall_first(tmp_path):
    gates(tmp_path)
    write(tmp_path/'stage2/X2.json',dict(survives=True,loss=.2))
    write(tmp_path/'stage2/X7.json',dict(survives=True,loss=.3))
    assert selected(tmp_path)==['X2','X7','X3']


def test_family_agreement_breaks_loss_tie(tmp_path):
    gates(tmp_path)
    write(tmp_path/'offline/X7.json',dict(survives=True,teacher={'metrics':{'hard_action_agreement':{'value':.9}}}))
    assert selected(tmp_path)==['X7','X2','X3']


def test_failed_x1_does_not_exclude_surviving_x7(tmp_path):
    gates(tmp_path)
    write(tmp_path/'offline/X1.json',dict(survives=False))
    (tmp_path/'stage2/X1.json').unlink()
    write(tmp_path/'stage2/X7.json',dict(survives=True,loss=.3))
    assert selected(tmp_path)==['X7','X2','X3']


def test_no_family_survivor_still_selects_other_arms(tmp_path):
    gates(tmp_path)
    for arm in ('X1','X7'):write(tmp_path/'stage2'/f'{arm}.json',dict(survives=False,loss=.7))
    assert selected(tmp_path)==['X2','X3','X4']


def test_real_shell_arguments_match_x1_except_seed_output_stop(tmp_path):
    (tmp_path/'source').mkdir()
    (tmp_path/'venv/bin').mkdir(parents=True)
    (tmp_path/'loader6.json').write_text('{}')
    stub=tmp_path/'venv/bin/python'
    stub.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    stub.chmod(0o755)
    directory=Path(__file__).parent
    env=dict(os.environ,EXIT_R2_JOB=str(tmp_path))
    base=json.loads(subprocess.check_output(['bash',str(directory/'run_fit.sh'),'X1'],env=env,text=True))
    replicate=json.loads(subprocess.check_output(['bash',str(directory/'run_fit_x7.sh'),'X7'],env=env,text=True))
    assert base[base.index('--seed')+1]=='2026101001'
    assert replicate[replicate.index('--seed')+1]=='2026101007'
    assert replicate[replicate.index('--stop')+1]==str(tmp_path/'X7.STOP')
    def normalize(args):
        out=args.copy()
        for key in ('--seed','--output','--stop'):out[out.index(key)+1]='MATCH'
        return out
    assert normalize(base)==normalize(replicate)
