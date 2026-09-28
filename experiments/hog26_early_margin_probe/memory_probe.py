"""Exercise full assay inputs with synthetic regression targets only."""

import resource

import numpy as np
import torch
from margin_contract import MEMORY, PLAN, validate
from margin_data import load_data
from margin_model import make_model, predict
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate()
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('focused assay data changed')
    x = np.asfortranarray(data.matrices['entity_history'], dtype=np.float64)
    model = make_model(1280500, memory=True)
    model.fit(x, np.sin(np.arange(len(x))))
    if not np.isfinite(predict(model, x, data.current)).all():
        raise ValueError('nonfinite synthetic prediction')
    publish(MEMORY, {'status': 'complete-focused-margin-synthetic-memory', 'plan_sha256': sha(PLAN),
                     'shape': list(x.shape), 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     'real_targets_used': False, 'checkpoint_saved': False})


if __name__ == '__main__':
    main()
