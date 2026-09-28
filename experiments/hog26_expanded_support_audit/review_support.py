"""Retrospective support and endpoint-position accounting; never model inputs."""

import json

import numpy as np
import torch
from cache_reader import read_complete_cache
from scalar_evaluation import EvaluationIndex, evaluation_weights
from value_contract import CACHE, ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    output = ROOT / 'reports/hog26_expanded_training_support_20260913.json'
    if output.exists():
        raise ValueError('preserve existing support audit')
    mapped, evaluation, complete, _ = read_complete_cache(CACHE)
    mapped._mmap.close()
    ids, progress, _, target, current, _, _, _, _, _ = evaluation
    index = EvaluationIndex(ids, progress)
    lengths = np.array([game['rows'] for game in complete['game_records']])
    offsets = np.r_[0, lengths.cumsum()]
    final_rows = np.zeros(len(ids), dtype=bool)
    final_rows[offsets[1:] - 1] = True
    late = index.phases == 2
    representatives = late & index.representative_mask
    coverage_path = ROOT / 'reports/hog26_expanded_cache_review_20260913.json'
    coverage = json.loads(coverage_path.read_text())['coverage']['representatives']
    late_slices = {key: value for key, value in coverage.items() if key.startswith('phase/late/seat/')}
    inadequate = {key: value for key, value in late_slices.items()
                  if value['scenario_clusters'] < 8 or min(value['clusters_containing_loss'], value['clusters_containing_win']) < 2}
    cohorts = np.repeat([game['cohort'] for game in complete['game_records']], lengths)
    results = {}
    for cohort, mask in (('combined', np.ones(len(ids), dtype=bool)), ('original_plus_extension', cohorts != 'expanded'), ('expanded', cohorts == 'expanded')):
        selected = representatives & mask
        weights = evaluation_weights(ids, progress, late & mask, index=index)
        points = {}
        for name, endpoint in (('final_decision', final_rows), ('earlier_decision', ~final_rows)):
            subset = selected & endpoint
            points[name] = {'representative_games': int(subset.sum()),
                            'baseline_margin_mae': float(np.abs(current[subset] - target[subset]).mean()) if subset.any() else None}
        results[cohort] = {'late_representative_games': int(selected.sum()),
                           'final_decision_representatives': int((selected & final_rows).sum()),
                           'final_decision_representative_fraction': float(final_rows[selected].mean()),
                           'final_decision_all_state_weight': float(weights[final_rows].sum()), 'baseline_subgroups': points}
    publish(output, {'status': 'complete-expanded-training-support-audit', 'cache_complete_sha256': sha(CACHE / 'complete.json'),
                     'coverage_review_sha256': sha(coverage_path), 'source_sha256': sha(__file__),
                     'late_joint_slices': len(late_slices), 'below_existing_decisive_cluster_floors': inadequate,
                     'endpoint_accounting': results, 'acceptance': False, 'changes_to_frozen_experiment': False,
                     'scope': 'Retrospective training-only analysis. Actual endpoint position is forbidden as model input. This does not authorize selective top-ups or alter any evaluation weights.'})
    print(json.dumps({'inadequate_late_joint_slices': len(inadequate), 'endpoint_accounting': results}), flush=True)


if __name__ == '__main__':
    main()
