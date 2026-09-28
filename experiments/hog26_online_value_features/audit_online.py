"""Match a bounded public encoder and independent clones to audited cache bytes."""

import hashlib
import json
import resource
import time

import numpy as np
import torch
from cache_reader import read_complete_cache
from health_features import augment
from online_features import PUBLIC_FIELDS, PublicFeatureState
from stream_contract import PIN, RESULT, configuration, validate
from value_contract import CACHE, publish, sha


def exact(actual, expected):
    return actual.shape == expected.shape and actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes()


def frame(public, index):
    return {key: value[index].copy() for key, value in public.items()}


def main():
    torch.set_num_threads(1)
    pin = validate()
    mapped, evaluation, complete, _ = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    del evaluation
    if complete['cache']['sha256'] != pin['base_cache_sha256']:
        raise ValueError('online reference cache changed')
    with np.load(CACHE / 'rows.npz', allow_pickle=False) as saved:
        offsets = saved['offsets']
    layout, table, health = configuration()
    state = PublicFeatureState(layout, table)
    cases, total_rows = [], 0
    for game in pin['games']:
        with np.load(game['path'], allow_pickle=False) as saved:
            public = {key: saved[key].copy() for key in PUBLIC_FIELDS}
        n = len(public['global_features'])
        if n != game['rows']:
            raise ValueError('online raw game row count differs')
        begin, end = offsets[game['index']:game['index'] + 2]
        mapped = np.memmap(CACHE / 'features.f32', mode='r', dtype='<f4', shape=shape)
        expected = augment(np.array(mapped[begin:end], copy=True), health)
        mapped._mmap.close()
        state.reset()
        cutoff = max(1, n // 2)
        rows, clone = [], None
        started = time.perf_counter()
        for index in range(n):
            if index == cutoff:
                clone = state.clone()
                divergent = state.clone()
                changed = frame(public, index)
                changed['global_features'][2] = np.float32(1) - changed['global_features'][2]
                divergent.step(changed)
                if state.seen != index:
                    raise ValueError('branch update mutated parent feature history')
            rows.append(state.step(frame(public, index)))
        actual = np.stack(rows)
        if not exact(actual, expected):
            difference = np.argwhere(actual != expected)[0].tolist()
            raise ValueError(f'online cache bytes differ at game{game["index"]}, row/column{difference}')
        if clone is not None:
            replay = np.stack([clone.step(frame(public, index)) for index in range(cutoff, n)])
            if not exact(replay, expected[cutoff:]):
                raise ValueError('cloned public prefix does not reproduce the original future')
        if state.history_frames != min(n, 20):
            raise ValueError('public history memory is not bounded')
        cases.append({'game_index': game['index'], 'rows': n, 'streaming_cache_bytes_exact': True,
                      'cloned_future_bytes_exact': clone is not None, 'divergent_clone_isolated': clone is not None,
                      'maximum_history_frames': state.history_frames, 'feature_sha256': hashlib.sha256(actual.tobytes()).hexdigest(),
                      'elapsed_seconds': time.perf_counter() - started})
        total_rows += n
        print(json.dumps(cases[-1]), flush=True)
    validate()
    publish(RESULT, {'status': 'complete-online-value-feature-parity-audit', 'pin_sha256': sha(PIN),
                     'games': len(cases), 'rows': total_rows, 'cases': cases,
                     'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     'scope': pin['scope'], 'outcome_targets_used': False, 'model_fitting': False, 'policy_changes': False,
                     'acceptance': False})


if __name__ == '__main__':
    main()
