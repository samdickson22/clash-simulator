"""Compose X7 seed replicate while retaining the immutable five/X6 freezes."""
import json
from experiment_x6 import load_experiment as original, sha

def load_experiment(job):
    frozen = original(job)
    addendum = json.loads((job/'x7-addendum.json').read_text())
    assert addendum['committed_before_launch']
    assert addendum['base_freeze_sha256'] == sha(job/'freeze.json')
    assert addendum['x6_addendum_sha256'] == sha(job/'x6-addendum.json')
    assert addendum['seed_audit_sha256'] == sha(job/'x7-seed-audit.json')
    assert json.loads((job/'x7-seed-audit.json').read_text())['passed']
    for relative, expected in addendum['files'].items():
        assert sha(job/relative) == expected, relative
    assert 'X7' not in frozen['arms']
    frozen['arms']['X7'] = addendum['arm']
    return frozen
