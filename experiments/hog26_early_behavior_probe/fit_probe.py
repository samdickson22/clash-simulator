"""Fixed paired information probes; no outcome targets or policy updates."""

import gc
import json
import pickle

import numpy as np
import torch
from binary_metrics import scores
from probe_contract import OUTPUT, PLAN, validate
from probe_data import load_data
from probe_model import make_model, probability
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate(require_memory=True)
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('audited auxiliary data changed')
    OUTPUT.mkdir(exist_ok=False)
    publish(OUTPUT / 'manifest.json', {'plan_sha256': sha(PLAN), 'data_audit': data.audit, 'outcome_fitting': False})
    for representation in plan['representations']:
        directory = OUTPUT / representation
        directory.mkdir()
        x = np.asfortranarray(data.matrices[representation], dtype=np.float64)
        for seed in plan['seeds']:
            for fold in range(4):
                validate(require_memory=True)
                fit = data.folds != fold
                prior = float(data.labels[fit].mean())
                model = make_model(seed + fold)
                model.fit(np.asfortranarray(x[fit]), data.labels[fit])
                predicted = probability(model, x)
                stem = f'seed{seed}-fold{fold}'
                with (directory / f'{stem}.pkl').open('xb') as stream:
                    pickle.dump(model, stream)
                np.savez_compressed(directory / f'{stem}-predictions.npz', bridge_probability=predicted)
                report = {'representation': representation, 'seed': seed, 'fold': fold, 'prior': prior,
                          'fit_games': int(fit.sum()), 'excluded_games': int((~fit).sum()),
                          'fitting': scores(data.labels[fit], predicted[fit], prior),
                          'excluded': scores(data.labels[~fit], predicted[~fit], prior)}
                publish(directory / f'{stem}-report.json', report)
                del model
                gc.collect()
                print(json.dumps({'representation': representation, 'seed': seed, 'fold': fold, 'status': 'auxiliary-fit-complete'}), flush=True)
        del x
    validate(require_memory=True)
    publish(OUTPUT / 'complete.json', {'status': 'complete-fixed-early-behavior-fits', 'plan_sha256': sha(PLAN), 'fits': 16,
            'artifacts': {str(path.relative_to(OUTPUT)): sha(path) for path in sorted(OUTPUT.rglob('*')) if path.is_file()},
            'outcome_fitting': False, 'acceptance': False})


if __name__ == '__main__':
    main()
