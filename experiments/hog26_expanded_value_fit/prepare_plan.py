"""Publish fitting authority only after complete data, memory, and source evidence."""

import json

import torch
from value_contract import CACHE, PLAN, ROOT, ValuePlan, publish, runtime, sha, sources
from value_models import TREE_SETTINGS


def main():
    torch.set_num_threads(1)
    if PLAN.exists():
        raise ValueError('preserve frozen fitting authority')
    review_path = ROOT / 'reports/hog26_expanded_cache_review_20260913.json'
    review = json.loads(review_path.read_text())
    if (review['status'] != 'complete-expanded-cache-review' or review['games'] != 6144
            or not review['label_and_game_metadata_exact'] or not review['public_progress_and_baseline_exact']
            or review['cache_complete_sha256'] != sha(CACHE / 'complete.json')):
        raise ValueError('complete independent cache review required')
    prefix = ROOT / 'reports/hog26_expanded_value_actual_memory_20260913'
    memory = json.loads(prefix.with_suffix('.json').read_text())
    receipt = json.loads(prefix.with_suffix('.receipt.json').read_text())
    if (memory['status'] != 'complete-actual-loss-synthetic-memory' or memory['regressor_loss'] != 'absolute_error'
            or memory['classifier_classes'] != [0, 1, 2] or memory['fitting_rows'] != 1897300
            or memory['full_inference_rows'] != 2465152 or memory['outcome_labels_used'] or memory['checkpoint_saved']
            or receipt['status'] != 'passed' or receipt['memory_limit_terminated'] or not receipt['source_unchanged']
            or max(memory['peak_rss_bytes'], receipt['peak_rss_bytes']) + 2 * 1024**3 > 18 * 1024**3):
        raise ValueError('actual-loss full-size memory gate failed')
    memory_sources = json.loads(prefix.with_suffix('.pin.json').read_text())
    for name, expected in memory_sources.items():
        if sha(ROOT / name) != expected:
            raise ValueError('memory-tested source changed')
    globals_memory = ROOT / 'reports/hog26_expanded_tree_value_memory_20260913/globals.json'
    globals_receipt = ROOT / 'reports/hog26_expanded_tree_value_memory_20260913/globals-receipt.json'
    global_check = json.loads(globals_memory.read_text())
    global_guard = json.loads(globals_receipt.read_text())
    if (global_check['status'] != 'complete-synthetic-memory-probe' or global_check['matrix_shape'] != [2465152, 36]
            or global_guard['exit_code'] != 0 or not global_guard['source_unchanged'] or global_guard['memory_limit_terminated']):
        raise ValueError('globals memory gate failed')
    paths = [review_path, CACHE / 'complete.json', ROOT / 'reports/hog26_expanded_feature_plan_20260913.json',
             prefix.with_suffix('.json'), prefix.with_suffix('.receipt.json'), prefix.with_suffix('.pin.json'),
             globals_memory, globals_receipt, ROOT / 'reports/hog26_expanded_tree_value_memory_20260913/source_pin.json',
             ROOT / 'reports/hog26_grouped_weight_parity_20260913.json',
             ROOT / 'reports/hog26_cached_model_inference_bridge_20260913.json',
             ROOT / 'reports/hog26_expanded_tree_value_draft_20260913.json']
    paths += list((ROOT / 'experiments/hog26_expanded_tree_value').glob('*.py'))
    paths += list((ROOT / 'experiments/hog26_expanded_corpus').glob('*.py'))
    paths += [ROOT / 'experiments/hog26_scalar_pilot/scalar_models.py', ROOT / 'experiments/hog26_scalar_pilot/scalar_evaluation.py',
              ROOT / 'experiments/hog26_expanded_cache_review/review_cache.py']
    resources = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    resources.update(memory_sources)
    plan = ValuePlan(schema_id='clasher.hog26.expanded-value.v1', games=6144, rows=2465152, features=814,
                     seeds=(1279501, 1279502), folds=4, globals_epochs=30, batch_rows=512, tree_iterations=100,
                     implementation=sources(), resources=resources, runtime=runtime(), fitting_allowed=True,
                     opened_diagnostic_allowed=False, reserved_collection_allowed=False, policy_updates_allowed=False,
                     acceptance=False, interpretation=[
                         'Same whole-family folds and fitting objectives; data, candidate representation, and architecture change together.',
                         'Trees use log loss for canonical L/D/W and absolute residual error for terminal margin; absent draw class remains explicit.',
                         'Current public health features contain no future endpoint, remaining duration, or auxiliary termination prediction.',
                         'GlobalWDL keeps the original uniform sampler, importance weights, architecture, initialization and optimizer.',
                         'All 16 fold bundles and four exact OOF reviews must complete before a separate opened-diagnostic plan.',
                         'Reserved data roles and public calibration/counterfactual-ranking gates remain unchanged.',
                         'Memory readiness reserves an additional 2 GiB above the full-size synthetic peak for retained evaluation metadata, real targets and the remaining boosting iterations; every production process remains guarded at 18 GiB.',
                         'Tree settings: ' + json.dumps(TREE_SETTINGS, sort_keys=True)])
    publish(PLAN, plan.model_dump(mode='json'))
    print(json.dumps({'status': 'frozen-expanded-value-plan', 'sha256': sha(PLAN)}), flush=True)


if __name__ == '__main__':
    main()
