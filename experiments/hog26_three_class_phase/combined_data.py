"""Join fitting indices while keeping natural and controlled provenance separate."""

import json

import numpy as np
from controls_cache_contract import OUTPUT as CONTROLS
from controls_cache_contract import PIN as CONTROL_PIN
from controls_cache_contract import validate as validate_controls
from phase_contract import training_data
from scalar_evaluation import phase_ids
from value_contract import sha


def load_data():
    validate_controls()
    control = json.loads((CONTROLS / 'complete.json').read_text())
    if (control['status'] != 'complete-audited-mirror-training-features' or control['pin_sha256'] != sha(CONTROL_PIN)
            or not control['all_streaming_batch_bytes_exact'] or control['label_order'] != 'LDW'
            or control['cache_sha256'] != sha(CONTROLS / 'features.f32')
            or control['rows_sha256'] != sha(CONTROLS / 'rows.npz')):
        raise ValueError('complete exact control feature authority required')
    natural, complete, clusters, shape, health = training_data()
    records = control['game_records']
    lengths = np.asarray([r['rows'] for r in records], dtype=np.int64)
    with np.load(CONTROLS / 'rows.npz', allow_pickle=False) as saved:
        progress, current, offsets = saved['progress'], saved['current_margin'], saved['offsets']
    if not np.array_equal(offsets, np.r_[0, lengths.cumsum()]) or control['shape'] != [int(lengths.sum()), 814]:
        raise ValueError('control cache boundaries differ')
    if len(records) != 512 or len({r['cluster'] for r in records}) != 256:
        raise ValueError('512views from256physical controls required')
    for first, second in zip(records[::2], records[1::2], strict=True):
        if (first['cluster'] != second['cluster'] or first['physical_game'] != second['physical_game']
                or first['seat'] != 0 or second['seat'] != 1 or first['rows'] != second['rows']
                or first['label_ldw'] != 2 - second['label_ldw']):
            raise ValueError('control pair provenance differs')
    ids = np.concatenate((natural[0], np.repeat(np.arange(6144, 6656), lengths)))
    combined_progress = np.concatenate((natural[1], progress))
    labels = np.concatenate((natural[2], np.repeat([r['label_ldw'] for r in records], lengths)))
    folds = np.concatenate((natural[7], np.full(int(lengths.sum()), -1, dtype=np.int8)))
    return {'natural': natural, 'natural_complete': complete, 'natural_clusters': clusters, 'natural_shape': shape,
            'control': control, 'control_lengths': lengths, 'control_progress': progress, 'control_current': current,
            'health': health, 'ids': ids, 'progress': combined_progress, 'labels': labels,
            'folds': folds, 'phases': phase_ids(combined_progress), 'natural_rows': shape[0], 'rows': len(ids)}
