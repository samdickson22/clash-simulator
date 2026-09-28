"""A post-review checkpoint replacement must not become newly authorized evidence."""

import json

import pytest
from fitting_chain import audit_fold
from value_contract import sha


def test_changed_checkpoint_is_rejected_against_completed_review(tmp_path):
    checkpoint = tmp_path / 'model.pkl'
    checkpoint.write_bytes(b'reviewed-checkpoint')
    complete = tmp_path / 'complete.json'
    complete.write_text(json.dumps({'status': 'complete-expanded-value-fold', 'kind': 'trees', 'seed': 1279501,
                                    'fold': 0, 'plan_sha256': 'a' * 64, 'artifacts': {'model.pkl': sha(checkpoint)}}))
    kwargs = {'completion_sha256': sha(complete), 'kind': 'trees', 'seed': 1279501, 'fold': 0, 'model_plan_sha256': 'a' * 64}
    audit_fold(tmp_path, **kwargs)
    checkpoint.write_bytes(b'unreviewed-replacement')
    with pytest.raises(ValueError, match='checkpoint or report changed'):
        audit_fold(tmp_path, **kwargs)
