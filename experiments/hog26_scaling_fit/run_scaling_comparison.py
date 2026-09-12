"""Execute only the predeclared comparison after complete-pilot audit."""
import argparse
import hashlib
import json
import pickle
import platform
import sys
import time
from itertools import pairwise
from pathlib import Path

import numpy as np
import torch
from scalar_evaluation import (
    EvaluationIndex,
    cluster_bootstrap,
    coverage,
    empirical_prior,
    evaluation_weights,
    fitting_weights,
    fold_masks,
    metrics,
    slice_masks,
)
from scalar_features import feature_names
from scaling_dataset import load_combined_training
from scaling_training import (
    fit_entity,
    fit_globals,
    predict_entity,
    predict_globals,
    release_fit,
)
from tree_storage import fitting_features, predict_margin


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def source_pin():
    return {p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def report_predictions(public,probabilities,margin,prior,*,fit_mask=None,bootstrap=False):
    ids,progress,labels,target,current,seats,styles,folds,clusters,families=public
    slices=slice_masks(progress,seats,styles,folds)
    slices.update({f'family/{family}':families==family for family in np.unique(families)})
    results={}
    index=EvaluationIndex(ids,progress)
    for representative in (False,True):
        group={}
        for name,mask in slices.items():
            if fit_mask is not None:mask=mask&fit_mask
            weights=evaluation_weights(ids,progress,mask,representative=representative,index=index)
            if not weights.any():
                group[name]={'status':'inconclusive-empty'};continue
            args=(probabilities,labels,margin,target,current,weights,prior)
            value={'coverage':coverage(ids,labels,clusters,weights),'metrics':metrics(*args)}
            if bootstrap:value['intervals']=cluster_bootstrap(*args,clusters,replicates=2000,seed=1279511)
            group[name]=value
        results['representatives' if representative else 'all_states']=group
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--preflight',type=Path,required=True);p.add_argument('--comparison',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--model',choices=('globals','tree','entity'),required=True)
    p.add_argument('--globals-output',type=Path)
    p.add_argument('--readiness',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise ValueError('refusing to overwrite fitting output')
    comparison=json.loads(args.comparison.read_text())
    preflight=json.loads(args.preflight.read_text())
    pinned_comparison=next((value for key,value in preflight['evidence'].items() if Path(key).resolve()==args.comparison.resolve()),None)
    if pinned_comparison!=sha(args.comparison):raise ValueError('comparison was not pinned before collection')
    if args.model=='tree' and args.globals_output is None:raise ValueError('tree needs paired global WDL predictions')
    torch.set_num_threads(1)
    original_directory=Path(__file__).resolve().parents[1]/'hog26_scalar_pilot'
    benchmark=json.loads((original_directory/'synthetic_fullgame_benchmark_verified.json').read_text())
    readiness=json.loads(args.readiness.read_text())
    if (readiness.get('status')!='passed' or readiness.get('implementation')!=source_pin()
            or readiness.get('collection_plan_sha256')!=sha(args.plan)
            or readiness.get('combined_games')!=1536
            or readiness.get('memory_verified') is not True):
        raise ValueError('scaling readiness does not match complete data, implementation and memory checks')
    if (not benchmark['finite_gradients'] or benchmark['torch']!=torch.__version__
            or any(sha(original_directory/name)!=h for name,h in benchmark['source_sha256'].items())):
        raise ValueError('memory prerequisite does not match current model implementation')
    games,vocabulary,data_audit=load_combined_training(args.data,extension_plan=args.plan,extension_preflight=args.preflight)
    if readiness.get('data_audit')!=data_audit:
        raise ValueError('readiness audit differs from full combined corpus')
    # No outcome is inspected until the complete data inventory has passed audit.
    tree_version=None
    if args.model=='tree':
        sys.path.insert(0,str(Path.home()/'.cache/clasher-margin-tree-diagnostic'))
        import sklearn
        tree_version=sklearn.__version__
        if tree_version!='1.7.2':raise ValueError('tree library differs from reference version')
    implementation=source_pin()
    args.output.mkdir(parents=True)
    manifest={'comparison_sha256':sha(args.comparison),'collection_plan_sha256':sha(args.plan),
              'implementation':implementation,'data_audit':data_audit,'model':args.model,
              'memory_prerequisite':benchmark,'scaling_readiness':readiness,'readiness_sha256':sha(args.readiness),
              'outcome_token_names':list(vocabulary),
              'vocabulary_sha256':hashlib.sha256(json.dumps(list(vocabulary),separators=(',',':')).encode()).hexdigest(),
              'runtime':{'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__,'device':'cpu','threads':torch.get_num_threads(),'sklearn':tree_version},
              'parameter_counts':{'globals':benchmark['global_parameters'],'entity':benchmark['entity_parameters']},
              'tree_weight_scale':'mean-one fitting-row weights; relative phase/representative mass unchanged; matches reference fitting_phase_weights',
              'input_games':[{'path':g.path,'sha256':g.sha256} for g in games]}
    publish(args.output/'fitting_manifest.json',manifest)
    lengths=[len(g.public['global_features']) for g in games];offsets=np.r_[0,np.cumsum(lengths)];n=int(offsets[-1])
    ids=np.repeat(np.arange(len(games)),lengths);progress=np.concatenate([g.public['global_features'][:,0] for g in games])
    labels=np.repeat([g.target_class for g in games],lengths);target=np.repeat([g.target_margin for g in games],lengths)
    current=np.concatenate([(g.public['global_features'][:,8:11].sum(1)-g.public['global_features'][:,11:14].sum(1))/3 for g in games])
    seats=np.repeat([g.seat for g in games],lengths);styles=np.repeat([g.style for g in games],lengths)
    families=np.repeat([g.family for g in games],lengths);clusters=np.repeat([g.cluster for g in games],lengths)
    folds=np.array([int(f[-3:])//2 for f in families])
    public=(ids,progress,labels,target,current,seats,styles,folds,clusters,families)
    seeds=comparison['training']['tree_seeds' if args.model=='tree' else 'neural_seeds']
    if args.model=='tree':
        paired_manifest=json.loads((args.globals_output/'fitting_manifest.json').read_text())
        if (not (args.globals_output/'complete.json').is_file()
                or paired_manifest['model']!='globals' or paired_manifest['data_audit']!=data_audit
                or paired_manifest['comparison_sha256']!=sha(args.comparison)
                or paired_manifest['collection_plan_sha256']!=sha(args.plan)
                or paired_manifest['input_games']!=manifest['input_games']):
            raise ValueError('paired globals are incomplete or from different data/plan')
        sys.path.insert(0,str(Path.home()/'.cache/clasher-margin-tree-diagnostic'))
        from sklearn.ensemble import HistGradientBoostingRegressor
        # Only fitting-family features are materialized, directly in float64.
        publish(args.output/'feature_names.json',list(feature_names(len(vocabulary))))
    for base_seed in seeds:
        oof_p=np.full((n,3),np.nan);oof_m=np.full(n,np.nan);oof_prior=np.full((n,3),np.nan)
        fitting_reports=[]
        for fold in range(4):
            if source_pin()!=implementation:raise RuntimeError('fitting source changed')
            fit,excluded=fold_masks(ids,families,fold);fit_indices=np.unique(ids[fit]).tolist()
            if len(fit_indices)!=1152 or len(np.unique(ids[excluded]))!=384:raise ValueError('fold counts differ')
            wdl,mw=fitting_weights(ids,progress,fit)
            per_w=[wdl[a:b] for a,b in pairwise(offsets)]
            per_m=[mw[a:b] for a,b in pairwise(offsets)]
            prior=empirical_prior(ids,labels,fit);seed=int(base_seed)+fold
            log=lambda row, base_seed=base_seed, fold=fold:print(json.dumps({'base_seed':base_seed,'fold':fold,**row}),flush=True)
            began=time.monotonic()
            if args.model=='globals':
                model=fit_globals(games,fit_indices,per_w,seed=seed,epochs=30,batch_rows=512,log=log)
                probabilities=np.concatenate(predict_globals(model,games));predicted=current.copy()
                torch.save(model.state_dict(),args.output/f'seed{base_seed}-fold{fold}.pt')
            elif args.model=='entity':
                model=fit_entity(games,fit_indices,per_w,per_m,vocabulary=vocabulary,seed=seed,epochs=30,batch_games=2,log=log)
                probs,margins=predict_entity(model,games);probabilities=np.concatenate(probs);predicted=np.concatenate(margins)
                torch.save(model.state_dict(),args.output/f'seed{base_seed}-fold{fold}.pt')
            else:
                model=HistGradientBoostingRegressor(loss='absolute_error',learning_rate=.05,max_iter=100,max_leaf_nodes=15,
                    min_samples_leaf=20,l2_regularization=1.,max_bins=255,early_stopping=False,random_state=seed)
                tree_x=fitting_features(games,fit_indices,len(vocabulary))
                model.fit(tree_x,(target-current)[fit],sample_weight=mw[fit]*int(fit.sum()))
                del tree_x
                release_fit()
                predicted=predict_margin(model,games,len(vocabulary))
                paired=args.globals_output/f'seed{base_seed}-fold{fold}-predictions.npz'
                with np.load(paired,allow_pickle=False) as prior_fit:probabilities=prior_fit['probabilities']
                with (args.output/f'seed{base_seed}-fold{fold}.pkl').open('xb') as stream:pickle.dump(model,stream)
            np.savez_compressed(args.output/f'seed{base_seed}-fold{fold}-predictions.npz',probabilities=probabilities,margin=predicted)
            fitting_reports.append({'fold':fold,'elapsed_seconds':time.monotonic()-began,
                                    'fitting':report_predictions(public,probabilities,predicted,prior,fit_mask=fit),
                                    'excluded':report_predictions(public,probabilities,predicted,prior,fit_mask=excluded)})
            oof_p[excluded]=probabilities[excluded];oof_m[excluded]=predicted[excluded];oof_prior[excluded]=prior
            del model;release_fit()
            publish(args.output/f'seed{base_seed}-fold{fold}-report.json',fitting_reports[-1])
            log({'status':'fit_complete','elapsed_seconds':time.monotonic()-began})
        if not np.isfinite(oof_p).all() or not np.isfinite(oof_m).all():raise AssertionError('incomplete OOF predictions')
        np.savez_compressed(args.output/f'seed{base_seed}-oof.npz',probabilities=oof_p,margin=oof_m,prior=oof_prior)
        publish(args.output/f'seed{base_seed}-summary.json',report_predictions(public,oof_p,oof_m,oof_prior,bootstrap=True))
    if source_pin()!=implementation:raise RuntimeError('fitting source changed')
    publish(args.output/'complete.json',{'status':'diagnostic-comparison-complete','model':args.model,'seeds':seeds,
                                       'draw_games':sum(g.target_class==1 for g in games),'acceptance':False})

if __name__=='__main__':main()
