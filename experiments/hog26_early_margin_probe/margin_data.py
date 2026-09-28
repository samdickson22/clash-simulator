"""The same fixed early public points, with actual training margin targets."""

import json
from dataclasses import dataclass

import numpy as np
from continuation_contract import OUTPUT as FULL_MODELS
from probe_data import array_sha
from probe_data import load_data as load_public_probe_data
from scalar_evaluation import EvaluationIndex
from value_contract import CACHE, ROOT, sha


@dataclass(frozen=True)
class MarginData:
    matrices: dict[str, np.ndarray]
    target: np.ndarray
    current: np.ndarray
    families: np.ndarray
    folds: np.ndarray
    seats: np.ndarray
    styles: np.ndarray
    clusters: np.ndarray
    full_references: dict[str, np.ndarray]
    audit: dict


def load_data():
    public = load_public_probe_data()
    cache = json.loads((CACHE / 'complete.json').read_text())
    records = cache['game_records']
    with np.load(CACHE / 'rows.npz', allow_pickle=False) as saved:
        progress, offsets = saved['progress'], saved['offsets']
    ids = np.repeat(np.arange(6144), np.diff(offsets))
    index = EvaluationIndex(ids, progress)
    rows = np.flatnonzero(index.representative_mask & (index.phases == 0))
    if array_sha(rows) != public.audit['rows_sha256'] or not np.array_equal(ids[rows], np.arange(6144)):
        raise ValueError('early point alignment differs')
    target = np.asarray([row['terminal_margin'] for row in records], dtype=np.float64)
    current = public.matrices['base_public'][:, -1].copy()
    styles = np.asarray([row['style'] for row in records])
    if not np.array_equal(styles == 'bridge-pressure', public.labels):
        raise ValueError('training metadata alignment differs')
    references = {}
    science_path = ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json'
    science = json.loads(science_path.read_text())
    complete_path = FULL_MODELS / 'complete.json'
    if sha(complete_path) != science['resources'][str(complete_path.relative_to(ROOT))]:
        raise ValueError('full-training completion differs from scientific review')
    completion = json.loads(complete_path.read_text())
    resource_hashes = {}
    for seed in (1279501, 1279502):
        directory = FULL_MODELS / 'trees'
        review_path = directory / f'seed{seed}-review.json'
        if (sha(review_path) != completion['reviews'][str(review_path.relative_to(FULL_MODELS))]
                or sha(review_path) != science['resources'][str(review_path.relative_to(ROOT))]):
            raise ValueError('full-training exact review authority changed')
        review = json.loads(review_path.read_text())
        resource_hashes[str(review_path.relative_to(ROOT))] = sha(review_path)
        path = directory / f'seed{seed}-oof.npz'
        if sha(path) != review['oof_sha256'] or sha(path) != science['resources'][str(path.relative_to(ROOT))]:
            raise ValueError('reviewed full-training reference changed')
        with np.load(path, allow_pickle=False) as saved:
            references[f'full_seed{seed}'] = saved['margin'][rows]
        resource_hashes[str(path.relative_to(ROOT))] = sha(path)
        for seat in (0, 1):
            selected = (styles == 'bridge-pressure') & (public.seats == seat)
            expected = review['summary']['representatives'][f'phase/early/seat/{seat}/style/bridge-pressure']['metrics']['margin_mae']
            if not np.isclose(np.abs(references[f'full_seed{seed}'][selected] - target[selected]).mean(), expected, rtol=1e-12, atol=1e-12):
                raise ValueError('full-model early reference score differs')
    audit = {'public_audit': public.audit, 'target_sha256': array_sha(target), 'current_sha256': array_sha(current),
             'reference_resources': resource_hashes, 'games': 6144, 'scope': 'Training-only fixed early representative assay. No full-phase or acceptance claim.'}
    return MarginData(public.matrices, target, current, public.families, public.folds, public.seats,
                      styles, public.clusters, references, audit)
