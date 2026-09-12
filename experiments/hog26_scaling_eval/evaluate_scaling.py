"""Evaluate every previously frozen fit on complete fresh-seed diagnostic games."""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from fit_authority import original_training_records, pin_fits
from run_comparison import publish, report_predictions
from scalar_features import build_game_features
from scalar_models import EntityHistoryOutcome, GlobalWDL
from scalar_training import predict_entity, predict_globals, release_fit
from transfer_dataset import load_complete_pilot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'plan', 'preflight', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing existing evaluation output')
    scaled_resources,scaled_authority=pin_fits(Path.cwd())
    for source in Path(__file__).parent.glob('*.py'):
        scaled_resources[str(source.resolve())]={'path':str(source.resolve()),
            'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    torch.set_num_threads(1)
    games, vocabulary, audit = load_complete_pilot(args.data, plan_path=args.plan,
                                                  preflight_path=args.preflight)
    plan = json.loads(args.plan.read_text())
    resources = {**plan['source_authority']['resources'], **scaled_resources}
    if list(vocabulary)!=scaled_authority['outcome_token_names']:
        raise ValueError('scaled model vocabulary differs from diagnostic data')
    def check_resources():
        for item in resources.values():
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('frozen diagnostic resource changed: ' + item['path'])
    check_resources()
    original = {'games': original_training_records(Path.cwd(), scaled_authority)}
    lengths = [len(g.public['global_features']) for g in games]
    ids = np.repeat(np.arange(len(games)), lengths)
    progress = np.concatenate([g.public['global_features'][:, 0] for g in games])
    labels = np.repeat([g.target_class for g in games], lengths)
    target = np.repeat([g.target_margin for g in games], lengths)
    current = np.concatenate([(g.public['global_features'][:,8:11].sum(1) -
                               g.public['global_features'][:,11:14].sum(1))/3 for g in games])
    seats = np.repeat([g.seat for g in games], lengths)
    styles = np.repeat([g.style for g in games], lengths)
    families = np.repeat([g.family for g in games], lengths)
    clusters = np.repeat([g.cluster for g in games], lengths)
    folds = np.array([int(f[-3:])//2 for f in families])
    public = (ids, progress, labels, target, current, seats, styles, folds, clusters, families)
    args.output.mkdir()
    publish(args.output/'evaluation_manifest.json', {'data_audit': audit,
            'plan_sha256': hashlib.sha256(args.plan.read_bytes()).hexdigest(),
            'fitting': False, 'acceptance': False, 'model_resources': resources,
            'scaled_model_authority': scaled_authority,
            'evaluation_sources': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}})
    sys.path.insert(0, str(Path.home()/'.cache/clasher-margin-tree-diagnostic'))
    import sklearn
    if sklearn.__version__ != '1.7.2':
        raise ValueError('tree runtime changed')
    tree_features = None
    for model_name in ('globals', 'tree', 'entity'):
        if model_name == 'tree':
            tree_features = np.concatenate([build_game_features(**g.public, vocabulary_size=len(vocabulary)) for g in games])
        for seed in ((1279501,) if model_name == 'tree' else (1279501, 1279502)):
            for fold in range(4):
                check_resources()
                directory = Path(f'reports/hog26_scaling_{model_name}_comparison_20260912')
                stem = f'seed{seed}-fold{fold}'
                selected = [g for g in original['games'] if int(g['family_id'][-3:])//2 != fold]
                if len(selected) != 1152:
                    raise ValueError('original fitting-family prior count changed')
                prior = np.mean([g['outcome_wdl'][::-1] for g in selected], axis=0)
                if model_name == 'globals':
                    model = GlobalWDL()
                    model.load_state_dict(torch.load(directory/(stem+'.pt'), weights_only=True, map_location='cpu'))
                    model.eval()
                    probabilities = np.concatenate(predict_globals(model, games))
                    margins = current.copy()
                elif model_name == 'entity':
                    model = EntityHistoryOutcome(len(vocabulary), princess_tower_token=vocabulary.index('tower:Tower'), king_tower_token=vocabulary.index('tower:KingTower'))
                    model.load_state_dict(torch.load(directory/(stem+'.pt'), weights_only=True, map_location='cpu'))
                    model.eval()
                    probs, values = predict_entity(model, games)
                    probabilities, margins = np.concatenate(probs), np.concatenate(values)
                else:
                    # Trusted local model bytes have been verified against the frozen plan.
                    with (directory/(stem+'.pkl')).open('rb') as stream:
                        model = pickle.load(stream)
                    margins = np.clip(current + model.predict(tree_features), -1, 1)
                    with np.load(args.output/('globals-'+stem+'-predictions.npz'), allow_pickle=False) as saved:
                        probabilities = saved['probabilities'].copy()
                np.savez_compressed(args.output/(model_name+'-'+stem+'-predictions.npz'), probabilities=probabilities, margin=margins)
                report = {name: report_predictions(public, probabilities, margins, prior, fit_mask=mask, bootstrap=True)
                          for name, mask in (('fresh_seen_families', folds != fold), ('fresh_excluded_families', folds == fold))}
                publish(args.output/(model_name+'-'+stem+'-report.json'), report)
                print(json.dumps({'model': model_name, 'seed': seed, 'fold': fold, 'status': 'evaluated'}), flush=True)
                del model
                release_fit()
        if model_name == 'tree':
            tree_features = None
            release_fit()
    check_resources()
    publish(args.output/'complete.json', {'status': 'frozen-model-diagnostic-complete', 'fits_evaluated': 20, 'fitting': False, 'acceptance': False})


if __name__ == '__main__':
    main()
