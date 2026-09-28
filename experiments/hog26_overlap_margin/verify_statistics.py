"""Verify reuse against full original bootstraps on audited real training rows."""

import json

import numpy as np
import torch
from fixed_wdl_statistics import reuse_wdl_bootstrap
from phase_contract import OUTPUT as HARD
from phase_contract import training_data, validate
from scalar_evaluation import EvaluationIndex, cluster_bootstrap, evaluation_weights
from value_contract import ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    validate(memory=True)
    evaluation, _, _, _, _ = training_data()
    ids, progress, labels, target, current, _, _, _, clusters, _ = evaluation
    review_path = HARD / 'seed1279501-review.json'
    review = json.loads(review_path.read_text())
    oof_path = HARD / 'seed1279501-oof.npz'
    if sha(oof_path) != review['oof_sha256']:
        raise ValueError('reviewed hard-phase OOF changed')
    with np.load(oof_path, allow_pickle=False) as saved:
        probability, margin, prior = saved['probabilities'], saved['margin'], saved['prior']
    index = EvaluationIndex(ids, progress)
    cases = []
    for representative, name in ((False, 'all_states'), (True, 'representatives')):
        weights = evaluation_weights(ids, progress, index.phases == 2, representative=representative, index=index)
        reference = review['summary'][name]['phase/late']['intervals']
        identity = reuse_wdl_bootstrap(probability, probability.copy(), labels, margin, target, current, weights, prior, clusters, reference)
        if identity != reference:
            raise ValueError('real unchanged-margin bootstrap identity differs')
        recomputed = cluster_bootstrap(probability, labels, current, target, current, weights, prior, clusters)
        reused = reuse_wdl_bootstrap(probability, probability.copy(), labels, current, target, current, weights, prior, clusters, reference)
        if reused != recomputed:
            raise ValueError('real full-bootstrap and reuse results differ')
        cases.append({'distribution': name, 'active_rows': int((weights > 0).sum()), 'identity_exact': True, 'changed_margin_complete_bootstrap_exact': True})
    paths = [review_path, oof_path, ROOT / 'experiments/hog26_overlap_margin/fixed_wdl_statistics.py',
             ROOT / 'experiments/hog26_scalar_pilot/scalar_evaluation.py']
    publish(ROOT / 'reports/hog26_overlap_statistics_equivalence_20260913.json',
            {'status': 'complete-exact-WDL-statistic-reuse-proof', 'source_sha256': sha(__file__),
             'resources': {str(path.relative_to(ROOT)): sha(path) for path in paths}, 'cases': cases,
             'scope': 'Training-only numerical equivalence control. Real outcome labels are used for metric verification, never new fitting. Both complete dictionaries, including tied-score AUC and undefined-replicate metadata, match.',
             'model_fitting': False, 'acceptance': False})
    print(json.dumps(cases), flush=True)


if __name__ == '__main__':
    main()
