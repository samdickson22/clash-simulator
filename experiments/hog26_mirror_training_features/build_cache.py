"""Encode every audited control frame, checking offline/online identity."""

import json

import numpy as np
import torch
from body_features import body_features
from controls_cache_contract import OUTPUT, PIN, validate
from health_features import EXTRA_NAMES, augment
from online_features import PUBLIC_FIELDS, PublicFeatureState
from residual_features import numeric_features
from stream_contract import configuration
from value_contract import CACHE, publish, sha


def canonical_label(wdl):
    value = np.asarray(wdl)
    if value.shape != (3,) or not np.isin(value, (0, 1)).all() or value.sum() != 1:
        raise ValueError('one-hot raw WDL required')
    return int(np.argmax(value[::-1]))


def main():
    torch.set_num_threads(1)
    pin = validate()
    layout, table, health = configuration()
    if OUTPUT.exists():
        raise ValueError('preserve previous cache')
    OUTPUT.mkdir()
    records, progress, current, offsets = [], [], [], [0]
    with (OUTPUT / 'features.f32').open('xb') as stream:
        for index, record in enumerate(pin['games']):
            with np.load(record['path'], allow_pickle=False) as data:
                public = {key: data[key].copy() for key in PUBLIC_FIELDS}
                # Metadata and terminal labels never enter either encoder.
                batch_public = dict(public)
                batch_public['hand_ids'] = public['hand_ids'][:, :4]
                batch_public['hand_id_confidence'] = public['hand_id_confidence'][:, :4]
                base = np.concatenate((numeric_features(batch_public, layout), body_features(batch_public, table)), axis=1)
                batch = augment(base, health)
                if batch.shape != (record['rows'], 814) or batch.dtype != np.float32:
                    raise ValueError('complete fixed public feature shape required')
                state = PublicFeatureState(layout, table)
                for row in range(len(batch)):
                    online = state.step({key: value[row] for key, value in public.items()})
                    if online.dtype != batch.dtype or online.tobytes() != batch[row].tobytes():
                        raise ValueError('control streaming/batch feature bytes differ')
                if not np.array_equal(batch[:, health.globals[0]], public['global_features'][:, 0]):
                    raise ValueError('public clock identity differs')
                label = canonical_label(data['outcome_wdl'])
                winner = int(data['winner'])
                expected = 1 if winner == -1 else (2 if winner == record['seat'] else 0)
                if label != expected:
                    raise ValueError('canonical LDW label contradicts actual winner')
                target = float(data['terminal_tower_margin'])
            stream.write(np.ascontiguousarray(batch, dtype='<f4').tobytes())
            progress.append(batch[:, health.globals[0]].copy())
            current.append(batch[:, -1].copy())
            offsets.append(offsets[-1] + len(batch))
            records.append({**record, 'label_ldw': label, 'terminal_margin': target})
            if (index + 1) % 32 == 0:
                print(json.dumps({'views_encoded': index + 1, 'rows': offsets[-1]}), flush=True)
    if offsets[-1] != pin['rows']:
        raise ValueError('cache row count differs')
    with (OUTPUT / 'rows.npz').open('xb') as stream:
        np.savez_compressed(stream, offsets=np.asarray(offsets, dtype=np.int64), progress=np.concatenate(progress), current_margin=np.concatenate(current))
    names = json.loads((CACHE / 'complete.json').read_text())['feature_names'] + list(EXTRA_NAMES)
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-audited-mirror-training-features', 'pin_sha256': sha(PIN),
            'shape': [pin['rows'], 814], 'dtype': '<f4', 'feature_names': names, 'game_records': records,
            'cache_sha256': sha(OUTPUT / 'features.f32'), 'cache_bytes': (OUTPUT / 'features.f32').stat().st_size,
            'rows_sha256': sha(OUTPUT / 'rows.npz'), 'all_streaming_batch_bytes_exact': True,
            'label_order': 'LDW', 'raw_label_order': 'WDL', 'physical_clusters': 256, 'actor_views': 512,
            'fitting_performed': False, 'natural_frequency_evidence': False, 'acceptance': False})


if __name__ == '__main__':
    main()
