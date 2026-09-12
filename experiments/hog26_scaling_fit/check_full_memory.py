"""Memory preflight on complete audited data; never trains an outcome candidate."""
import argparse
import hashlib
import json
import resource
import sys
import time
from dataclasses import fields
from pathlib import Path

import numpy as np
import torch
from scalar_dataset import Game
from scaling_dataset import load_combined_training
from scaling_training import fit_entity
from test_scalar_models import synthetic
from tree_storage import fitting_features

LIMIT = 18*1024**3


def peak_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == 'darwin' else peak*1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data','plan','preflight','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',choices=('neural','tree'),required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing existing memory report')
    torch.set_num_threads(1)
    started = time.monotonic()
    games,vocabulary,audit = load_combined_training(args.data,
        extension_plan=args.plan,extension_preflight=args.preflight)
    if peak_bytes() > LIMIT:
        raise MemoryError('combined audit exceeded memory limit')
    retained_bytes = sum(v.nbytes for g in games for v in g.public.values())
    details = {}
    if args.phase == 'neural':
        # Real games remain resident but are never passed to the synthetic fit.
        batch = synthetic(batch=2,time=750,entities=128)
        probe_games = [Game({f.name:getattr(batch,f.name)[i].numpy() for f in fields(batch)},
            2,.3,'synthetic','synthetic',i,'synthetic','','') for i in range(2)]
        tokens = [f'synthetic:{i}' for i in range(498)]
        tokens[10],tokens[11] = 'tower:Tower','tower:KingTower'
        weights = [np.full(750,1/1500) for _ in probe_games]
        model = fit_entity(probe_games,[0,1],weights,weights,vocabulary=tokens,
                           seed=1279501,epochs=1,batch_games=2)
        if not all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
            raise ValueError('synthetic gradients invalid')
        details = {'batch':[2,750,128],'full_backpropagation':True,'optimizer_steps':1,
                   'target_source':'synthetic fixture only','outcome_model_saved':False}
    else:
        sys.path.insert(0,str(Path.home()/'.cache/clasher-margin-tree-diagnostic'))
        import sklearn
        from sklearn.ensemble import HistGradientBoostingRegressor
        if sklearn.__version__ != '1.7.2':
            raise ValueError('tree runtime differs')
        folds = [[i for i,g in enumerate(games) if int(g.family[-3:])//2 != fold] for fold in range(4)]
        fold = max(range(4),key=lambda f:sum(len(games[i].public['global_features']) for i in folds[f]))
        matrix = fitting_features(games,folds[fold],len(vocabulary))
        if peak_bytes() > LIMIT:
            raise MemoryError('tree feature allocation exceeded limit')
        # Probe preprocessing, binning and one histogram iteration with deterministic
        # artificial targets. No terminal labels influence these targets or a saved fit.
        target = (np.arange(len(matrix),dtype=np.float64)%17)/16
        model = HistGradientBoostingRegressor(loss='absolute_error',learning_rate=.05,
            max_iter=1,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1.,
            max_bins=255,early_stopping=False,random_state=1279501+fold)
        model.fit(matrix,target,sample_weight=np.ones(len(matrix),dtype=np.float64))
        details = {'largest_row_fold':fold,'fitting_rows':len(matrix),'columns':matrix.shape[1],
                   'matrix_bytes':matrix.nbytes,'histogram_iterations':1,
                   'target_source':'row-index synthetic sequence, not game outcomes',
                   'outcome_model_saved':False,'sklearn':sklearn.__version__,
                   'limit':'Measures full matrix, binning and one iteration; not a100-iteration outcome fit.'}
    peak = peak_bytes()
    if peak > LIMIT:
        raise MemoryError(f'memory preflight peak {peak} exceeds {LIMIT}')
    sources = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(Path(__file__).parent.glob('*.py'))}
    result = {'status':'passed','phase':args.phase,'data_audit':audit,
              'implementation':sources,'collection_plan_sha256':hashlib.sha256(args.plan.read_bytes()).hexdigest(),
              'retained_public_bytes':retained_bytes,'peak_rss_bytes':peak,'limit_bytes':LIMIT,
              'seconds':time.monotonic()-started,'details':details,
              'runtime':{'torch':torch.__version__,'threads':1,'device':'cpu'},
              'outcome_training':False}
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('implementation','data_audit')}),flush=True)


if __name__ == '__main__':
    main()
