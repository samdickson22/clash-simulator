"""Copy completed references into the continuation without mutating their sources."""

import json
import shutil
from pathlib import Path

from continuation_contract import OUTPUT, PLAN, REPLAY, SERIAL, validate
from value_contract import PLAN as ORIGINAL_PLAN
from value_contract import publish, sha


def copy_exact(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('preserve existing imported artifact')
    expected = sha(source)
    shutil.copy2(source, destination)
    if sha(destination) != expected or sha(source) != expected:
        raise ValueError('imported artifact bytes differ')


def import_completed():
    plan = validate()
    if not OUTPUT.is_dir() or any((OUTPUT / kind).exists() for kind in ('globals', 'trees')):
        raise ValueError('new empty continuation model directories required')
    copied = {}
    for seed in plan['seeds']:
        for fold in range(4):
            stem = f'seed{seed}-fold{fold}'
            source = SERIAL / 'globals' / stem
            destination = OUTPUT / 'globals' / stem
            destination.mkdir(parents=True)
            complete = json.loads((source / 'complete.json').read_text())
            if complete['status'] != 'complete-expanded-value-fold' or complete['plan_sha256'] != sha(ORIGINAL_PLAN):
                raise ValueError('complete original globals required')
            for name, expected in complete['artifacts'].items():
                if sha(source / name) != expected:
                    raise ValueError('original globals artifact changed')
            for path in sorted(source.iterdir()):
                copy_exact(path, destination / path.name)
            copied[f'globals/{stem}'] = {'source_complete_sha256': sha(source / 'complete.json'),
                                         'copied_complete_sha256': sha(destination / 'complete.json')}
    reference = SERIAL / 'trees/seed1279501-fold0'
    destination = OUTPUT / 'trees/seed1279501-fold0'
    destination.mkdir(parents=True)
    replay = json.loads((REPLAY / 'complete.json').read_text())
    manifest = json.loads((reference / 'manifest.json').read_text())
    manifest.update(execution_plan_sha256=sha(PLAN), execution_implementation=plan['sources'], tree_fit_openmp_threads=8,
                    imported_exact_replay_complete_sha256=sha(REPLAY / 'complete.json'))
    publish(destination / 'manifest.json', manifest)
    copy_exact(REPLAY / 'model.pkl', destination / 'model.pkl')
    copy_exact(REPLAY / 'predictions.npz', destination / 'predictions.npz')
    report = json.loads((reference / 'report.json').read_text())
    report.update(serial_reference_elapsed_seconds=report['elapsed_seconds'], elapsed_seconds=replay['elapsed_seconds'],
                  statistics_reused_from_exact_serial_predictions=True, serial_report_sha256=sha(reference / 'report.json'))
    publish(destination / 'report.json', report)
    publish(destination / 'complete.json', {'status': 'complete-expanded-value-fold', 'kind': 'trees', 'seed': 1279501,
            'fold': 0, 'plan_sha256': sha(ORIGINAL_PLAN), 'execution_plan_sha256': sha(PLAN),
            'artifacts': {path.name: sha(path) for path in destination.iterdir() if path.is_file()}, 'acceptance': False})
    copied['trees/seed1279501-fold0'] = {'replay_complete_sha256': sha(REPLAY / 'complete.json'),
                                       'serial_statistics_sha256': sha(reference / 'report.json')}
    validate()
    publish(OUTPUT / 'import_manifest.json', {'execution_plan_sha256': sha(PLAN), 'imports': copied, 'source_files_unchanged': True})
