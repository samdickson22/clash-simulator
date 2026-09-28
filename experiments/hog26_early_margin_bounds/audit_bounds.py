"""Read-only feasibility check of completed early-margin predictions."""

import json
import resource

import numpy as np
import torch
from health_features import make_layout
from margin_contract import OUTPUT as FOCUSED
from margin_contract import validate
from margin_data import load_data
from value_contract import CACHE, ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    validate(memory=True)
    data = load_data()
    complete = json.loads((CACHE / 'complete.json').read_text())
    layout = make_layout(complete['feature_names'])
    hp = data.matrices['base_public'][:, layout.hp].astype(np.float64)
    lower, upper = -hp[:, 3:].mean(1), hp[:, :3].mean(1)
    reference = ROOT / 'reports/hog26_early_margin_probe_review_20260913.json'
    review = json.loads(reference.read_text())
    path = FOCUSED / 'reviewed-oof.npz'
    if sha(path) != review['oof_sha256']:
        raise ValueError('reviewed early-margin OOF differs')
    with np.load(path, allow_pickle=False) as saved:
        predictions = {'current': data.current, **data.full_references,
                       'focused_base': saved['base_public'], 'focused_history': saved['entity_history']}
    results = {}
    for name, mask in (('all_early', np.ones(6144, bool)), ('early_bridge', data.styles == 'bridge-pressure')):
        result = {'games': int(mask.sum()), 'clusters': len(np.unique(data.clusters[mask])),
                  'target_violations_over_tolerance': int(((data.target < lower - 1e-6) | (data.target > upper + 1e-6))[mask].sum()),
                  'predictions': {}}
        for label, values in predictions.items():
            violation = np.maximum(np.maximum(lower - values, values - upper), 0)
            result['predictions'][label] = {'violations_over_tolerance': int((violation[mask] > 1e-6).sum()),
                                            'maximum_violation': float(violation[mask].max())}
        results[name] = result
    paths = [ROOT / 'src/clasher/entities.py', ROOT / 'src/clasher/battle.py',
             ROOT / 'scripts/hog26_scalar_reference_episode.py',
             ROOT / 'scripts/probe_hog26_scalar_complete_replay_20260909.py', reference, path]
    publish(ROOT / 'reports/hog26_early_margin_feasibility_audit_20260913.json',
            {'status': 'complete-exploratory-early-margin-feasibility-audit', 'source_sha256': sha(__file__),
             'resources': {str(p.relative_to(ROOT)): sha(p) for p in paths}, 'data_audit': data.audit,
             'formula': 'If tower health cannot increase, terminal margin is between negative current enemy mean health fraction and current own mean health fraction.',
             'source_basis': 'ScalarReferenceEpisode uses BattleState; Entity.take_damage rejects nonpositive damage and subtracts positive damage; terminal label is difference of mean tower fractions.',
             'floating_tolerance': 1e-6, 'results': results, 'prediction_changes': False,
             'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'scope': 'Exploratory training-only early representatives. A feasibility check, not a proof of full simulator invariants or model accuracy. No clipping or model change applied.',
             'acceptance': False})
    print(json.dumps(results), flush=True)


if __name__ == '__main__':
    main()
