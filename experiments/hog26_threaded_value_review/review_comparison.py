"""Scientific closeout of every expanded fit; no acceptance or diagnostic access."""

import json

import numpy as np
import torch
from cache_reader import read_complete_cache
from continuation_contract import OUTPUT, validate
from continuation_contract import PLAN as EXECUTION_PLAN
from paired_errors import paired_error_intervals
from review_completed import summarize_slices
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from value_contract import CACHE, PLAN, ROOT, load_plan, publish, sha

PIN = ROOT / 'reports/hog26_threaded_value_scientific_review_pin_20260913.json'


def main():
    torch.set_num_threads(1)
    validate()
    plan = load_plan()
    pin = json.loads(PIN.read_text())
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('scientific review resource changed')
    if pin['source_sha256'] != sha(__file__):
        raise ValueError('scientific review source changed')
    completion = json.loads((OUTPUT / 'complete.json').read_text())
    if (completion['status'] != 'complete-threaded-value-fitting-and-exact-review'
            or completion['execution_plan_sha256'] != sha(EXECUTION_PLAN) or completion['plan_sha256'] != sha(PLAN) or completion['fold_bundles'] != 16 or completion['estimator_models'] != 24):
        raise ValueError('all fixed fits and exact reviews must finish first')
    resources = {str((OUTPUT / 'complete.json').relative_to(ROOT)): sha(OUTPUT / 'complete.json')}
    reviews = {}
    for kind in ('globals', 'trees'):
        reviews[kind] = {}
        for seed in plan.seeds:
            relative = f'{kind}/seed{seed}-review.json'
            path = OUTPUT / relative
            if completion['reviews'].get(relative) != sha(path):
                raise ValueError('exact review hash differs')
            review = json.loads(path.read_text())
            if (review['status'] != 'complete-exact-expanded-fitting-review' or review['kind'] != kind
                    or review['seed'] != seed or review['plan_sha256'] != sha(PLAN) or review['execution_plan_sha256'] != sha(EXECUTION_PLAN)):
                raise ValueError('exact review identity differs')
            for fold, expected in review['audited_folds'].items():
                fold_path = OUTPUT / kind / f'seed{seed}-fold{fold}' / 'complete.json'
                if sha(fold_path) != expected:
                    raise ValueError('audited fold completion changed')
                record = json.loads(fold_path.read_text())
                for name, digest in record['artifacts'].items():
                    if sha(fold_path.parent / name) != digest:
                        raise ValueError('audited fitting artifact changed')
            oof_path = OUTPUT / kind / f'seed{seed}-oof.npz'
            if sha(oof_path) != review['oof_sha256']:
                raise ValueError('reviewed OOF predictions changed')
            resources[str(path.relative_to(ROOT))] = sha(path)
            resources[str(oof_path.relative_to(ROOT))] = sha(oof_path)
            reviews[kind][str(seed)] = {name: summarize_slices(slices) for name, slices in review['summary'].items()}
    mapped, evaluation, _, _ = read_complete_cache(CACHE)
    mapped._mmap.close()
    ids, progress, labels, target, _, seats, styles, folds, clusters, families = evaluation
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    paired = {}
    for seed in plan.seeds:
        with np.load(OUTPUT / 'globals' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            old_p, old_m, prior = saved['probabilities'], saved['margin'], saved['prior']
        with np.load(OUTPUT / 'trees' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            new_p, new_m = saved['probabilities'], saved['margin']
            if not np.array_equal(prior, saved['prior']):
                raise ValueError('paired fitting-only priors differ')
        paired[str(seed)] = {}
        for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
            group = {}
            for name, mask in slices.items():
                weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
                value = paired_error_intervals(old_p, new_p, old_m, new_m, labels, target, weights, clusters)
                value['scope'] = 'Whole-scenario paired bootstrap on the same held-family OOF training rows; positive means tree improvement over expanded globals. Diagnostic evidence only.'
                group[name] = value
            paired[str(seed)][distribution] = group
    report = {'status': 'complete-threaded-value-scientific-review', 'plan_sha256': sha(PLAN), 'execution_plan_sha256': sha(EXECUTION_PLAN),
              'pin_sha256': sha(PIN), 'resources': resources, 'all_slices': reviews, 'paired_tree_vs_globals': paired,
              'acceptance': False, 'policy_updates_allowed': False, 'reserved_collection_allowed': False,
              'interpretation': ['Every fixed fit and exact review is retained, including empty and poorly supported slices.',
                                 'There are no natural draws in the training corpus; natural-draw calibration remains unmeasured.',
                                 'This is fitting-corpus held-family evidence. It does not establish held-seed transfer or counterfactual ranking.',
                                 'Opened diagnostic evaluation requires its own frozen plan after this report.']}
    validate()
    publish(ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json', report)
    print(json.dumps({'status': report['status'], 'accepted': False}), flush=True)


if __name__ == '__main__':
    main()
