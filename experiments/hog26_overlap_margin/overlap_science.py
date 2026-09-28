"""Close all overlapping fits against current, full-tree and hard-phase margins."""

import json

import numpy as np
import torch
from overlap_contract import OUTPUT, PLAN, SEEDS, training_data, validate
from paired_errors import paired_error_intervals
from phase_contract import OUTPUT as HARD
from phase_contract import REFERENCES
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    validate(memory=True)
    destination = OUTPUT / 'scientific-review.json'
    if destination.exists():
        raise ValueError('preserve completed phase scientific review')
    reviews, resources = {}, {}
    for seed in SEEDS:
        path = OUTPUT / f'seed{seed}-review.json'
        review = json.loads(path.read_text())
        if review['status'] != 'complete-exact-overlap-margin-review' or review['seed'] != seed or review['plan_sha256'] != sha(PLAN):
            raise ValueError('complete phase exact review required')
        for fold, digest in review['audited_folds'].items():
            completion_path = OUTPUT / f'seed{seed}-fold{fold}' / 'complete.json'
            if sha(completion_path) != digest:
                raise ValueError('phase reviewed fold changed')
            for name, expected in json.loads(completion_path.read_text())['artifacts'].items():
                if sha(completion_path.parent / name) != expected:
                    raise ValueError('phase reviewed artifact changed')
        oof = OUTPUT / f'seed{seed}-oof.npz'
        if sha(oof) != review['oof_sha256']:
            raise ValueError('phase reviewed OOF changed')
        resources[path.name], resources[oof.name] = sha(path), sha(oof)
        reviews[str(seed)] = review['summary']
    evaluation, _, _, _, _ = training_data()
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    index = EvaluationIndex(ids, progress)
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    paired = {}
    for seed in SEEDS:
        with np.load(OUTPUT / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            probability, margin, prior = saved['probabilities'], saved['margin'], saved['prior']
        with np.load(REFERENCES / 'globals' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            if not np.array_equal(probability, saved['probabilities']) or not np.array_equal(prior, saved['prior']):
                raise ValueError('unchanged globals OOF identity differs')
        with np.load(REFERENCES / 'trees' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            reference_margin = saved['margin']
        with np.load(HARD / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            hard_margin = saved['margin']
            if not np.array_equal(probability, saved['probabilities']) or not np.array_equal(prior, saved['prior']):
                raise ValueError('hard-phase WDL or prior identity differs')
        paired[str(seed)] = {}
        for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
            group = {}
            for name, mask in slices.items():
                weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
                contrasts = {}
                for label, before in (('current_margin', current), ('full_training_tree_margin', reference_margin), ('hard_phase_margin', hard_margin)):
                    value = paired_error_intervals(probability, probability, before, margin, labels, target, weights, clusters)
                    value['scope'] = 'Training-only same held-family rows and paired scenario bootstrap; positive means overlapping-expert margin improvement. WDL is exactly unchanged globals. Unadjusted diagnostic intervals.'
                    contrasts[label] = value
                group[name] = contrasts
                print(json.dumps({'seed': seed, 'distribution': distribution, 'slice': name}), flush=True)
            paired[str(seed)][distribution] = group
    validate(memory=True)
    publish(destination, {'status': 'complete-overlap-margin-scientific-review', 'plan_sha256': sha(PLAN),
                          'resources': resources, 'all_slices': reviews, 'paired': paired, 'acceptance': False,
                          'limitations': ['No natural draws or reserved data are introduced.',
                                          'The public gate is continuous for fixed head values; tree predictions can still jump, and counterfactual ranking is not established.',
                                          'Overlap changes fitting support, weight scale and binning; it does not isolate a cause.',
                                          'Every original slice and both distributions are retained, including insufficient-support cells.']})


if __name__ == '__main__':
    main()
