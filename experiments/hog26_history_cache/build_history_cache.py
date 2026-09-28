"""Stream all public histories with exact prefix, reset and online/offline audits."""

import hashlib
import json
import resource
import shutil

import numpy as np
import torch
from cache_reader import read_complete_cache
from feature_store import FeatureStore
from history_contract import OUTPUT, PLAN, validate
from history_features import (
    HistoryState,
    build_game_history,
    history_names,
    make_layout,
)
from value_contract import CACHE, publish, sha


def exact(first, second):
    return first.dtype == second.dtype and first.shape == second.shape and first.tobytes() == second.tobytes()


def main():
    torch.set_num_threads(1)
    plan = validate()
    mapped, evaluation, complete, _ = read_complete_cache(CACHE)
    mapped._mmap.close()
    del evaluation
    if complete['cache']['sha256'] != plan['base_feature_sha256']:
        raise ValueError('base cache bytes differ from history authority')
    if shutil.disk_usage(OUTPUT.parent).free < 2465152 * 97 * 4 + 2 * 1024**3:
        raise ValueError('insufficient room for the exact history cache')
    OUTPUT.mkdir(exist_ok=False)
    layout = make_layout(complete['feature_names'])
    store = FeatureStore(OUTPUT / 'history.f32', 2465152, 97)
    chosen = np.random.default_rng(plan['random_read_seed']).integers(0, 2465152, size=512)
    expected = np.empty((512, 97), dtype=np.float32)
    base_digest = hashlib.sha256()
    minimum, maximum = np.full(97, np.inf), np.full(97, -np.inf)
    nonzero = np.zeros(97, dtype=np.int64)
    audits, offsets = [], [0]
    for game_index, record in enumerate(complete['game_records']):
        start, end = offsets[-1], offsets[-1] + record['rows']
        mapped = np.memmap(CACHE / 'features.f32', mode='r', dtype='<f4', shape=(2465152, 809))
        base = np.array(mapped[start:end], copy=True)
        mapped._mmap.close()
        features = build_game_history(base, layout)
        cutoff = max(1, len(base) // 2)
        if not exact(build_game_history(base[:cutoff], layout), features[:cutoff]):
            raise ValueError('prefix truncation changed public history')
        if game_index in plan['streaming_audit_games']:
            state = HistoryState(layout)
            online = np.stack([state.step(row) for row in base])
            if not exact(online, features):
                raise ValueError('streamed and batch public history bytes differ')
            changed = base.copy()
            changed[cutoff:, list(layout.columns)] *= np.float32(.75)
            if not exact(build_game_history(changed, layout)[:cutoff], features[:cutoff]):
                raise ValueError('future public changes altered earlier features')
            audits.append({'game_index': game_index, 'rows': len(base), 'prefix_rows': cutoff,
                           'streaming_exact': True, 'future_perturbation_exact': True})
        base_digest.update(memoryview(base).cast('B'))
        selected = (chosen >= start) & (chosen < end)
        expected[selected] = features[chosen[selected] - start]
        minimum = np.minimum(minimum, features.min(axis=0))
        maximum = np.maximum(maximum, features.max(axis=0))
        nonzero += np.count_nonzero(features, axis=0)
        store.append(features)
        offsets.append(end)
        if (game_index + 1) % 128 == 0:
            store.release_pages()
            print(json.dumps({'audited_games': game_index + 1, 'rows': end}), flush=True)
    if len(offsets) != 6145 or offsets[-1] != 2465152 or base_digest.hexdigest() != plan['base_feature_sha256']:
        raise ValueError('base feature bytes or full game inventory changed')
    cache = store.finish()
    mapped = np.memmap(OUTPUT / 'history.f32', mode='r', dtype='<f4', shape=(2465152, 97))
    if not exact(np.array(mapped[chosen], copy=True), expected):
        raise ValueError('history random-access reads differ')
    mapped._mmap.close()
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-audited-public-history-cache', 'plan_sha256': sha(PLAN),
            'sources': plan['sources'], 'cache': cache, 'base_feature_sha256': base_digest.hexdigest(),
            'base_complete_sha256': sha(CACHE / 'complete.json'), 'base_rows_sha256': sha(CACHE / 'rows.npz'),
            'games': 6144, 'rows': 2465152, 'columns': 97, 'feature_names': list(history_names()),
            'prefix_checks': 6144, 'streaming_audits': audits, 'random_reads_exact': True,
            'minimum': minimum.tolist(), 'maximum': maximum.tolist(), 'nonzero_rows': nonzero.tolist(),
            'constant_columns': int(np.count_nonzero(minimum == maximum)),
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'fitting': False, 'acceptance': False,
            'scope': 'Only public feature values enter the transform. Cache metadata supplies game boundaries for reset. No outcome target or private opponent style enters a feature.'})
    print(json.dumps({'status': 'complete-audited-public-history-cache', 'games': 6144, 'rows': 2465152}), flush=True)


if __name__ == '__main__':
    main()
