"""Reject post-review checkpoint replacement and unauthorized diagnostic access."""

import json

import pytest
from phase_eval_chain import audit_phase_fold
from value_contract import sha


def fixture_fold(path):
    path.mkdir()
    for name in ('manifest.json', 'phase0.pkl', 'phase1.pkl', 'phase2.pkl', 'predictions.npz', 'report.json'):
        (path / name).write_bytes(name.encode())
    result = {'status': 'complete-phase-margin-fold', 'seed': 1279501, 'fold': 0, 'plan_sha256': 'plan',
              'artifacts': {p.name: sha(p) for p in path.iterdir()}}
    (path / 'complete.json').write_text(json.dumps(result))
    return sha(path / 'complete.json')


def test_reject_changed_checkpoint_after_review(tmp_path):
    path = tmp_path / 'fold'
    digest = fixture_fold(path)
    kwargs = {'completion_sha256': digest, 'seed': 1279501, 'fold': 0, 'plan_sha256': 'plan'}
    assert len(audit_phase_fold(path, **kwargs)) == 7
    (path / 'phase1.pkl').write_bytes(b'replaced checkpoint')
    with pytest.raises(ValueError, match='checkpoint or report changed'):
        audit_phase_fold(path, **kwargs)


def test_reject_altered_completion_or_scope(tmp_path):
    path = tmp_path / 'fold'
    digest = fixture_fold(path)
    with pytest.raises(ValueError, match='identity or inventory'):
        audit_phase_fold(path, completion_sha256=digest, seed=1279502, fold=0, plan_sha256='plan')
    (path / 'unexpected.pkl').write_bytes(b'unreviewed')
    with pytest.raises(ValueError, match='identity or inventory'):
        audit_phase_fold(path, completion_sha256=digest, seed=1279501, fold=0, plan_sha256='plan')


def test_unpublished_or_fitting_authority_cannot_open_data(tmp_path, monkeypatch):
    import phase_eval_contract as contract

    path = tmp_path / 'pin.json'
    monkeypatch.setattr(contract, 'PIN', path)
    with pytest.raises(ValueError, match='published phase diagnostic authority'):
        contract.validate_pin()
    path.write_text(json.dumps({'schema': 'clasher.hog26.phase-value-diagnostic.v1', 'sources': contract.sources(),
                               'fits': 8, 'seeds': list(contract.SEEDS), 'folds': 4, 'all_fits_reviewed': True,
                               'fitting': True, 'selection': False, 'calibration': False, 'acceptance': False}))
    with pytest.raises(ValueError, match='phase diagnostic authority differs'):
        contract.validate_pin()
