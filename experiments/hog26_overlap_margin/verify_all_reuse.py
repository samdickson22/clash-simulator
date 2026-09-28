"""Require exact statistic identity in every reviewed training slice and seed."""

import json

import numpy as np
import torch
from fixed_wdl_statistics import reuse_wdl_bootstrap
from phase_contract import OUTPUT as HARD
from phase_contract import SEEDS, training_data, validate
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from value_contract import ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    validate(memory=True)
    evaluation, _, _, _, _ = training_data()
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    index = EvaluationIndex(ids, progress)
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f'family/{family}': families == family for family in np.unique(families)})
    resources, cases = {}, []
    for seed in SEEDS:
        path = HARD / f'seed{seed}-review.json'
        review = json.loads(path.read_text())
        oof_path = HARD / f'seed{seed}-oof.npz'
        if sha(oof_path) != review['oof_sha256']:
            raise ValueError('reviewed full OOF changed')
        resources[str(path.relative_to(ROOT))], resources[str(oof_path.relative_to(ROOT))] = sha(path), sha(oof_path)
        with np.load(oof_path, allow_pickle=False) as saved:
            probability, margin, prior = saved['probabilities'], saved['margin'], saved['prior']
        for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
            for name, mask in masks.items():
                weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
                reference = review['summary'][distribution][name]
                if not weights.any():
                    if reference['status'] != 'inconclusive-empty':
                        raise ValueError('reference empty slice differs')
                    cases.append({'seed': seed, 'distribution': distribution, 'slice': name, 'status': 'exact-empty'})
                    continue
                actual = reuse_wdl_bootstrap(probability, probability, labels, margin, target, current, weights, prior, clusters, reference['intervals'])
                if actual != reference['intervals']:
                    raise ValueError('complete reference statistic identity differs: ' + name)
                cases.append({'seed': seed, 'distribution': distribution, 'slice': name, 'status': 'exact-complete-dictionary'})
        print(json.dumps({'seed': seed, 'all_reference_slices_exact': True}), flush=True)
    helper = ROOT / 'experiments/hog26_overlap_margin/fixed_wdl_statistics.py'
    resources[str(helper.relative_to(ROOT))] = sha(helper)
    publish(ROOT / 'reports/hog26_overlap_all_statistics_identity_20260913.json',
            {'status': 'complete-all-slice-statistic-identity-proof', 'source_sha256': sha(__file__),
             'resources': resources, 'cases': cases, 'case_count': len(cases), 'seeds': list(SEEDS),
             'scope': 'Every full original bootstrap dictionary is reproduced on the actual reviewed training predictions. This does not establish model improvement.',
             'model_fitting': False, 'acceptance': False})


if __name__ == '__main__':
    main()
