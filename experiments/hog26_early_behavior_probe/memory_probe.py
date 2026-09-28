"""Full auxiliary matrix and learner steps, with synthetic labels only."""

import resource

import numpy as np
import torch
from probe_contract import MEMORY, PLAN, validate
from probe_data import load_data
from probe_model import make_model, probability
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate()
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('auxiliary public data changed')
    x = np.asfortranarray(data.matrices['entity_history'], dtype=np.float64)
    model = make_model(1280400, memory_probe=True)
    model.fit(x, np.arange(len(x)) % 2)
    probability(model, x)
    publish(MEMORY, {'status': 'complete-early-behavior-synthetic-memory', 'plan_sha256': sha(PLAN),
                     'shape': list(x.shape), 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     'real_labels_used': False, 'checkpoint_saved': False, 'outcome_fitting': False})


if __name__ == '__main__':
    main()
