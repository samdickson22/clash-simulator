"""Small CPU contracts only. Mock game records never qualify real engine data."""
import copy
from dataclasses import replace

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import rl_learner as L, stream_actor as A
from bot.pretrain_v1.checks import qualify_ppo_session as Q
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads, chunk, learner
from bot.pretrain_v1.tests.test_stream_actor import make_actor, start, view


@pytest.fixture(autouse=True)
def guards():
    Q.Q.guard()


def test_real_toy_gradient_path_and_fresh_post_update_labels(admitted):
    l = learner(admitted, precision='float64', batch_size=8, updates=4)
    initial_anchor = L.policy_sha256(l.anchor, l.feature_hash)
    with Q.Q.math_backend(torch):
        for version in range(4):
            c = chunk(l, mixed=True, ragged=True)
            labels = c.old_value.tobytes(), c.old_logp.tobytes()
            proof = Q.update_proof(l, [c])
            assert proof['metrics']['optimizer_steps'] == 2*(version+1)
            assert proof['metrics']['warmup'] == (version < 3)
            assert labels == (c.old_value.tobytes(), c.old_logp.tobytes())
        fresh = chunk(l, ragged=True)
        assert fresh.version == 4 and fresh.policy_sha256 == l.policy_sha256
        Q.parity(l, [fresh], batches=(2, 4))
        Q.parity(l, [fresh], batches=(2, 4), padded=True)
        stale = replace(fresh, old_value=c.old_value)
        with pytest.raises(RuntimeError, match='strict parity'):
            Q.parity(l, [stale], batches=(4,))
        assert L.policy_sha256(l.anchor, l.feature_hash) == initial_anchor


def test_inprocess_barriers_keep_pending_poll_fresh_and_exact(admitted, monkeypatch):
    """Real StreamingPolicy actor + toy real gradient; only engine is mocked."""
    l = learner(admitted, precision='float64', steps_per_update=2, batch_size=2, updates=4)
    actor_model = copy.deepcopy(l.model)
    ledger = Q.Ledger(2, 4, 2)
    seen_values = []

    def publish(c, boundary):
        done = ledger.accept(c, boundary, 'same-engine-game', b.tick)
        if done and c.version < 4:
            # Each version uses new Session inference, including changed critic.
            assert c.policy_sha256 == l.policy_sha256
            seen_values.append(c.old_value.copy())
            l.update([L.Chunk(**vars(c))])
            return A.PolicyUpdate(l.version, l.policy_sha256,
                    {k: v.clone() for k, v in l.model.state_dict().items()}, 2)
        if done:
            Q.parity(l, [L.Chunk(**vars(c))], batches=(2,))
        return A.PolicyUpdate(c.version, c.policy_sha256)

    a = make_actor(actor_model, publish, budget_steps=10, quota_steps=2, chunk_rows=2,
                   anchor_sha256=l.anchor_sha256, provenance_sha256=l.provenance_sha256)
    b, _ = start(a, monkeypatch)
    with Q.Q.math_backend(torch):
        for i in range(10):
            b.tick = 90+5*i
            a.act(view(b.tick))
        b.tick = 140
        with pytest.raises(A.BudgetComplete):
            a.act(view(b.tick))
        a.close()
    assert ledger.rows == [2]*5
    assert a.generated_steps == a.published_steps == 10 and a.discarded_steps == 0
    assert a.unfinished_games == 1 and a.completed_games == 0
    assert l.generated_steps == l.trained_steps == 8 and l.version == a.version == 4
    assert not np.array_equal(seen_values[0], seen_values[1])
    assert len(ledger.games) == 1


@pytest.mark.parametrize('corruption', ['version', 'game', 'budget', 'engine_tick'])
def test_ledger_rejects_cross_barrier_relabel_replay_and_counter_errors(admitted, corruption):
    l = learner(admitted, precision='float64')
    c = chunk(l, n=2, terminal_tail=False)
    ledger = Q.Ledger(2, 4, 2)
    boundary = A.Boundary('quota', 2, 8, 0, False, False)
    ledger.accept(c, boundary, 'game0', 100)
    c = replace(c, version=1, features={k: v.copy() for k, v in c.features.items()})
    from bot.pretrain_v1 import featurize as F
    c.features['glob'][:, F.G_TICK] += 10
    game, tick = 'game0', 110
    boundary = A.Boundary('quota', 4, 6, 0, False, False)
    if corruption == 'version':
        c = replace(c, version=0)
    elif corruption == 'game':
        game = 'restarted-game'
    elif corruption == 'budget':
        boundary = replace(boundary, generated_steps=3)
    else:
        tick = 111
    with pytest.raises(RuntimeError):
        ledger.accept(c, boundary, game, tick)
