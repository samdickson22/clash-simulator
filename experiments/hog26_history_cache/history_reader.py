"""Read-only history features tied to their public base and complete audit."""

import json

import numpy as np
from feature_store import file_sha
from history_contract import OUTPUT, PLAN, validate
from value_contract import CACHE, sha


def open_history_cache():
    plan = validate()
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if (complete['status'] != 'complete-audited-public-history-cache' or complete['plan_sha256'] != sha(PLAN)
            or complete['sources'] != plan['sources'] or complete['games'] != 6144 or complete['rows'] != 2465152
            or complete['columns'] != 97 or complete['prefix_checks'] != 6144 or not complete['random_reads_exact']
            or complete['feature_names'] != plan['names'] or complete['base_feature_sha256'] != plan['base_feature_sha256']
            or complete['base_complete_sha256'] != sha(CACHE / 'complete.json')
            or complete['base_rows_sha256'] != sha(CACHE / 'rows.npz')
            or [row['game_index'] for row in complete['streaming_audits']] != plan['streaming_audit_games']
            or not all(row['streaming_exact'] and row['future_perturbation_exact'] for row in complete['streaming_audits'])
            or complete['fitting'] is not False or complete['acceptance'] is not False):
        raise ValueError('complete public history audit required')
    path = OUTPUT / 'history.f32'
    if (complete['cache']['shape'] != [2465152, 97] or complete['cache']['dtype'] != '<f4'
            or path.stat().st_size != complete['cache']['bytes'] or file_sha(path) != complete['cache']['sha256']):
        raise ValueError('history cache bytes differ')
    return np.memmap(path, mode='r', dtype='<f4', shape=(2465152, 97)), complete
