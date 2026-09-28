"""Fit eight fixed early-margin regressors on training-family points."""

import gc
import json
import pickle

import numpy as np
import torch
from assay_metrics import report
from margin_contract import OUTPUT, PLAN, validate
from margin_data import load_data
from margin_model import make_model, predict
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate(memory=True)
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('focused margin data changed')
    OUTPUT.mkdir(exist_ok=False)
    publish(OUTPUT / 'manifest.json', {'plan_sha256': sha(PLAN), 'data_audit': data.audit, 'full_phase_candidate': False})
    for representation in plan['representations']:
        directory = OUTPUT / representation
        directory.mkdir()
        x = np.asfortranarray(data.matrices[representation], dtype=np.float64)
        for fold in range(4):
            validate(memory=True)
            fit = data.folds != fold
            model = make_model(plan['seed'] + fold)
            model.fit(np.asfortranarray(x[fit]), (data.target - data.current)[fit])
            prediction = predict(model, x, data.current)
            stem = f"seed{plan['seed']}-fold{fold}"
            with (directory / f'{stem}.pkl').open('xb') as stream:
                pickle.dump(model, stream)
            with (directory / f'{stem}-predictions.npz').open('xb') as stream:
                np.savez_compressed(stream, margin=prediction)
            result = {'representation': representation, 'seed': plan['seed'], 'fold': fold,
                      'fit_games': int(fit.sum()), 'excluded_games': int((~fit).sum()),
                      'fitting': report(data, prediction, fit), 'excluded': report(data, prediction, ~fit)}
            publish(directory / f'{stem}-report.json', result)
            del model
            gc.collect()
            print(json.dumps({'representation': representation, 'fold': fold, 'status': 'focused-margin-fit-complete'}), flush=True)
        del x
    validate(memory=True)
    publish(OUTPUT / 'complete.json', {'status': 'complete-fixed-early-margin-fits', 'plan_sha256': sha(PLAN), 'fits': 8,
            'artifacts': {str(path.relative_to(OUTPUT)): sha(path) for path in sorted(OUTPUT.rglob('*')) if path.is_file()},
            'full_phase_candidate': False, 'acceptance': False})


if __name__ == '__main__':
    main()
