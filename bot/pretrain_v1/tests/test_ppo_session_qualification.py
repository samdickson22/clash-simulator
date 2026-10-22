"""Small CPU contracts only. Mock game records never qualify real engine data."""
import copy
from contextlib import nullcontext
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace as NS

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


@pytest.mark.parametrize('rejected', [0, 1])
def test_run_retains_and_checks_actual_unfinished_match_diagnostics(admitted, monkeypatch, tmp_path, rejected):
    """Exercise run's budget branch without real engine/model-size work."""
    from bot.pretrain_v1 import model, sim_ours
    from bot.players import ours
    from bot.eval import headline
    l = learner(admitted, precision='float64')
    cfg = tmp_path/'cfg.json'
    cfg.write_text(json.dumps(dict(d=192, layers=4, heads=6, ffn=576, drop=0., n_cards=124, n_bodies=183)))
    monkeypatch.setattr(Q, 'bootstrap', lambda a: (NS(pins=admitted['runtime_manifest']),
        dict(actor_manifest_sha256='a'*64, runtime_manifest_sha256='b'*64), None, {}))
    monkeypatch.setattr(L, 'Learner', lambda *args, **kwargs: l)
    monkeypatch.setattr(model, 'PolicyV1', lambda **kwargs: copy.deepcopy(l.model))
    monkeypatch.setattr(sim_ours, 'bind_matches', lambda players: nullcontext())
    monkeypatch.setattr(headline, 'make_player', lambda *args: None)
    actor = NS(exhausted=True, generated_steps=8448, published_steps=8448, discarded_steps=0,
               completed_games=0, unfinished_games=1, version=4, boundary_declined_steps=0, counts={})
    monkeypatch.setattr(A, 'StreamingPolicyOursPlayer', lambda *args, **kwargs: actor)

    def mock_match(*args, **kwargs):
        # Names are the pinned match frame contract read by audited_match.
        b = NS(game_over=False, tick=145)
        channels = {0: NS(diagnostics=lambda: dict(rejected=rejected, executed=1)),
                    1: NS(diagnostics=lambda: dict(rejected=0, executed=0))}
        plays = {0: [(140, 'Knight', 0, not rejected)], 1: []}
        command_hash = hashlib.sha256(b'real-mock-execution-log')
        raise A.BudgetComplete(8448, True)

    monkeypatch.setattr(ours, 'play_match', mock_match)
    a = NS(runtime=tmp_path, actor_source=tmp_path, manifest=tmp_path, model_cfg=cfg, size='S100',
           source_sha256='c'*64, threads=1, microbatch=128, anchor=admitted['anchor_path'],
           anchor_sha256=l.anchor_sha256, policy_sha256=l.policy_sha256, device='cpu', max_games=1, game_seed=100)
    result = {}
    with pytest.raises(RuntimeError, match='engine rejected' if rejected else 'incomplete fixture'):
        Q.run(a, tmp_path, result)
    audit = result['unfinished_game']
    assert audit['channels'][0]['rejected'] == rejected
    assert audit['play_log'][0] == [(140, 'Knight', 0, not rejected)]
    assert not audit['terminal'] and audit['winner'] is None
    assert result['budget_stop']['terminal_outcome'] is None
    assert result['actor']['unfinished_games'] == 1 and not result['games']
