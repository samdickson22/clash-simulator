"""Bind completed scaled models and their original training-label authority."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin_fits(root):
    root=Path(root)
    resources={}
    authority=None
    for model in ('globals','tree','entity'):
        directory=root/f'reports/hog26_scaling_{model}_comparison_20260912'
        complete_path=directory/'complete.json'
        if not complete_path.is_file():
            raise ValueError('all scaled fits must complete before diagnostic access')
        complete=json.loads(complete_path.read_text())
        seeds=[1279501] if model=='tree' else [1279501,1279502]
        if (complete.get('status')!='diagnostic-comparison-complete'
                or complete.get('model')!=model or complete.get('seeds')!=seeds
                or complete.get('acceptance') is not False):
            raise ValueError('scaled fitting completion differs')
        manifest_path=directory/'fitting_manifest.json'
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('model')!=model or manifest.get('data_audit',{}).get('games')!=1536:
            raise ValueError('scaled fitting manifest differs')
        shared={key:manifest[key] for key in ('data_audit','collection_plan_sha256','comparison_sha256','outcome_token_names','input_games')}
        if authority is not None and shared!=authority:
            raise ValueError('scaled models use different data or vocabulary')
        authority=shared
        for name,expected in manifest['implementation'].items():
            if sha(root/'experiments/hog26_scaling_fit'/name)!=expected:
                raise ValueError('scaled fitting implementation changed')
        paths=[complete_path,manifest_path]
        for seed in seeds:
            for fold in range(4):
                paths.append(directory/f'seed{seed}-fold{fold}.{ "pkl" if model=="tree" else "pt"}')
        for path in paths:
            resources[str(path.relative_to(root))]={'path':str(path.resolve()),'sha256':sha(path)}
    return resources,authority


def original_training_records(root, authority):
    records=[]
    for part,path in (
        ('original','datasets/derived/hog26_scalar_birthfixed_pilot_seed1279261_20260911/complete.json'),
        ('extension','datasets/derived/hog26_scaling_train_seed1279701_20260912/complete.json')):
        path=Path(root)/path
        if sha(path)!=authority['data_audit'][part]['complete_manifest_sha256']:
            raise ValueError('training prior labels differ from scaled model authority')
        records.extend(json.loads(path.read_text())['games'])
    if len(records)!=1536:
        raise ValueError('scaled training inventory differs')
    return records
