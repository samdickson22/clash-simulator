"""Coordinator04:35 selection addendum; original e8c82b10 remains immutable."""
import json
from pathlib import Path
from imitation.exit_r1.rows import sha
import postkill_admission as original

JOB = Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1')
RECORDS = ('X1', 'X2', 'X3', 'X4', 'X6')

def labelled(value, job=JOB):
    original.labelled(value)
    value['selection_amendment_sha256'] = sha(Path(job)/'postkill-selection-amendment.json')
    return value

def chosen_from_results(results):
    assert set(results) == set(RECORDS), 'All five completed recipe records required; X5/X7 excluded'
    best = min(('X3', 'X4', 'X6'), key=lambda arm: (
        -results[arm]['teacher']['metrics']['play_recall']['value'], int(arm[1:])))
    return ['X1', 'X2', best]

def frozen(job):
    job = Path(job)
    harness = original.frozen(job)
    amendment = json.loads((job/'postkill-selection-amendment.json').read_text())
    prelaunch = json.loads((job/'postkill-selection-amendment-prelaunch.json').read_text())
    assert amendment['kind'] == 'postkill selection amendment; exploration; never adoptable'
    assert amendment['base_addendum_sha256'] == sha(job/'postkill-sdefault-addendum.json')
    assert prelaunch['pushed'] and prelaunch['amendment_sha256'] == sha(job/'postkill-selection-amendment.json')
    assert amendment['reporting_games_before_amendment'] == 0
    assert amendment['never_adoptable'] and not amendment['adoption_eligible']
    for relative, expected in amendment['files'].items():
        assert sha(job/relative) == expected, relative
    qualified = json.loads((job/'postkill-selection-code-qualification.json').read_text())
    assert qualified['passed']
    assert sha(job/'postkill-selection-code-qualification.json') == amendment['code_qualification_sha256']
    return harness

def selection(job):
    job = Path(job)
    results = {arm: json.loads((job/'offline'/f'{arm}.json').read_text()) for arm in RECORDS}
    selected = chosen_from_results(results)
    seal = json.loads((job/'postkill-selection.json').read_text())
    receipt = json.loads((job/'postkill-selection-prelaunch.json').read_text())
    assert receipt['pushed'] and receipt['selection_sha256'] == sha(job/'postkill-selection.json')
    assert seal['selected'] == selected == ['X1', 'X2', 'X4']
    assert seal['harness_sha256'] == sha(job/'postkill-sdefault-addendum.json')
    assert seal['selection_amendment_sha256'] == sha(job/'postkill-selection-amendment.json')
    for arm, value in results.items():
        assert seal['offline_sha256'][arm] == sha(job/'offline'/f'{arm}.json')
        assert seal['checkpoint_sha256'][arm] == value['checkpoint_sha256']
    return selected
