"""CPU fixtures only: no engine/bootstrap, GPU, remote workload or training actor."""
import copy
from dataclasses import asdict, replace
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch

from bot.players.base import MatchContext
from bot.pretrain_v1 import actor_worker as W
from bot.pretrain_v1 import stream_actor as A
from bot.pretrain_v1.model import PolicyV1
from bot.pretrain_v1.tests.test_sim_ours import battle, DECK


def model():
    torch.set_num_threads(1)
    torch.manual_seed(21)
    return PolicyV1(d=24, layers=1, heads=3, ffn=48).eval()


def callback(c, boundary):
    if boundary.reason == 'quota':
        return A.PolicyUpdate(c.version+1, c.policy_sha256, copy.deepcopy(MODEL_STATE), 5)
    return A.PolicyUpdate(c.version, c.policy_sha256)


MODEL_STATE = None


def actor():
    global MODEL_STATE
    m = model()
    MODEL_STATE = m.state_dict()
    return A.StreamingPolicyOursPlayer(m, callback, actor_id='fixture', seed=12,
        anchor_sha256='a'*64, provenance_sha256='b'*64, opponent_id='fixture-opponent',
        budget_steps=100, quota_steps=2, chunk_rows=2)


def cursor(a):
    return dict(publication_sequence=a.completed_games+1, next_game_sequence=a.completed_games,
                seed=a.seed, actor_id=a.actor_id, schedule_sha256='c'*64,
                runtime_provenance_sha256=a.provenance_sha256)


def game(a, monkeypatch, seed=101, ticks=(90, 95, 100, 105)):
    h = hashlib.sha256()
    underlying = a.publish
    def traced_publish(c, boundary):
        for key, array in sorted(c.features.items()):
            h.update(W.encoded([key, str(array.dtype), array.shape]))
            h.update(array.tobytes())
        for key in A._VECTORS:
            h.update(getattr(c, key).tobytes())
        h.update(W.encoded([c.bootstrap, c.version, c.policy_sha256, asdict(boundary)]))
        return underlying(c, boundary)
    a.publish = traced_publish
    b, _ = battle(monkeypatch)
    b.game_over, b.winner = False, None
    a.bind_ours(b)
    a.start(MatchContext(0, seed, tuple(DECK)))
    for tick in ticks:
        b.tick = tick
        d = a.act(NS(tick=tick, seat=0, can_act=True))
        h.update(W.encoded([d.action, d.stats]))
        from bot.pretrain_v1.featurize import feature_bytes
        h.update(feature_bytes(a.session.last_feat).encode())
    b.tick += 2
    b.game_over, b.winner = True, 0
    a.close()
    a.publish = underlying
    h.update(W.encoded([a.generated_steps, a.published_steps, a.version, a.remaining_quota, a.counts]))
    return h.hexdigest()


def test_terminal_object_recycle_preserves_next_session_and_lifetime_budget(monkeypatch, tmp_path):
    a = actor()
    game(a, monkeypatch)
    assert a.version == 1 and a.remaining_quota == 3
    checkpoint = W.ActorCheckpoint.capture(a, cursor(a))
    twin = W.ActorCheckpoint.capture(a, cursor(a))
    checkpoint.write(tmp_path/'checkpoint.json')
    assert json.loads((tmp_path/'checkpoint.json').read_text())['sha256'] == checkpoint.sha256
    # Persistent actor is an independent oracle, with identical previous games.
    baseline = actor()
    game(baseline, monkeypatch)
    replacement = checkpoint.restore(model(), callback, driver_state=cursor(a))
    assert replacement.generated_steps == 4 and replacement.budget_steps == 100
    assert replacement.remaining_quota == 3 and replacement.version == 1
    with pytest.raises(W.WorkerError, match='completed games'):
        W.ActorCheckpoint.capture(replacement, cursor(replacement))
    assert game(replacement, monkeypatch, seed=102) == game(baseline, monkeypatch, seed=102)
    with pytest.raises(W.WorkerError, match='consumed'):
        checkpoint.restore(model(), callback, driver_state=cursor(a))
    with pytest.raises(W.WorkerError, match='retired'):
        twin.restore(model(), callback, driver_state=cursor(a))
    with pytest.raises(A.StreamError, match='stopped'):
        a.bind_ours(NS())


def test_active_quota_boundary_is_not_safe_checkpoint(monkeypatch):
    a = actor()
    b, _ = battle(monkeypatch)
    b.game_over, b.winner = False, None
    a.bind_ours(b); a.start(MatchContext(0, 101, tuple(DECK)))
    for tick in (90, 95, 100):
        b.tick = tick; a.act(NS(tick=tick, seat=0, can_act=True))
    assert a.version == 1  # real synchronous callback continuation, still same game
    with pytest.raises(W.WorkerError, match='closed game'):
        W.ActorCheckpoint.capture(a, cursor(a))
    a.close()
    with pytest.raises(W.WorkerError, match='failed'):
        W.ActorCheckpoint.capture(a, cursor(a))


@pytest.mark.parametrize('mutation', ['cursor', 'policy', 'counter', 'unpublished', 'unfinished'])
def test_capture_and_restore_fail_closed(monkeypatch, mutation):
    a = actor(); game(a, monkeypatch)
    checkpoint = W.ActorCheckpoint.capture(a, cursor(a))
    c, m = cursor(a), model()
    if mutation == 'cursor': c['publication_sequence'] += 1
    elif mutation == 'policy':
        with torch.no_grad(): next(m.parameters()).add_(1)
    elif mutation == 'counter': a.generated_steps += 1
    elif mutation == 'unpublished': a.published_steps -= 1
    elif mutation == 'unfinished': a.unfinished_games += 1
    with pytest.raises((W.WorkerError, A.StreamError)):
        checkpoint.restore(m, callback, driver_state=c)
    assert not getattr(a, '_lifecycle_retired', False)



def test_new_version_requires_exact_updated_policy_snapshot(monkeypatch):
    a = actor()
    def changing(c, b):
        if b.reason == 'quota':
            weights = copy.deepcopy(a.model.original.state_dict())
            weights['value.2.bias'][0].add_(0.05)
            reference = model(); reference.load_state_dict(weights)
            return A.PolicyUpdate(c.version+1, A.policy_sha256(reference), weights, 5)
        return A.PolicyUpdate(c.version, c.policy_sha256)
    a.publish = changing
    game(a, monkeypatch)
    assert a.version == 1
    cp = W.ActorCheckpoint.capture(a, cursor(a))
    with pytest.raises(A.StreamError, match='policy digest'):
        cp.restore(model(), changing, driver_state=cursor(a))
    successor = cp.restore(copy.deepcopy(a.model.original), changing, driver_state=cursor(a))
    assert successor.version == a.version == 1
    assert successor.policy_sha256 == a.policy_sha256 != A.policy_sha256(model())


def _checkpoint_child(connection):
    with pytest.MonkeyPatch.context() as patch:
        a = actor()
        game(a, patch)
        cp = W.ActorCheckpoint.capture(a, cursor(a))
        # Counterfactual persistent-worker continuation provides the oracle hash.
        expected = game(a, patch, seed=102)
        connection.send((cp.record, cp.sha256, cp.record['driver_state'], expected))
    connection.close()


def _restorer_child(connection, record, digest, driver_state, claims):
    global MODEL_STATE
    m = model(); MODEL_STATE = m.state_dict()
    try:
        a = W.ActorCheckpoint.restore_record(record, m, callback, expected_sha256=digest,
                driver_state=driver_state, claim_directory=claims)
        with pytest.MonkeyPatch.context() as patch:
            connection.send(('ok', game(a, patch, seed=102), a.generated_steps, a.budget_steps))
    except BaseException as ex:
        connection.send(('error', type(ex).__name__, str(ex)))
    connection.close()


def test_real_spawned_process_retirement_single_claim_and_exact_next_game(tmp_path):
    ctx = mp.get_context('spawn')
    receive, send = ctx.Pipe(duplex=False)
    old = ctx.Process(target=_checkpoint_child, args=(send,))
    old.start(); send.close()
    try:
        assert receive.poll(30), 'fixture worker did not return checkpoint'
        record, digest, driver, expected = receive.recv()
        old.join(30)
        assert old.exitcode == 0
    finally:
        if old.is_alive(): old.kill(); old.join(10)
        receive.close()
    claims = tmp_path/'claims'; claims.mkdir()
    outputs = []
    # Two simultaneous successors race on the exact same persistent claim.
    successors = []
    for _ in range(2):
        receive, send = ctx.Pipe(duplex=False)
        child = ctx.Process(target=_restorer_child, args=(send, record, digest, driver, claims))
        child.start(); send.close(); successors.append((child, receive))
    try:
        for child, receive in successors:
            assert receive.poll(30)
            outputs.append(receive.recv()); child.join(30)
            assert child.exitcode == 0
    finally:
        for child, receive in successors:
            if child.is_alive(): child.kill(); child.join(10)
            receive.close()
    assert sum(row[0] == 'ok' for row in outputs) == 1
    assert next(row for row in outputs if row[0] == 'ok') == ('ok', expected, 8, 100)
    assert 'already claimed' in next(row for row in outputs if row[0] == 'error')[2]
    assert len(list(claims.iterdir())) == 1


def test_live_source_and_cross_boot_and_bad_digest_refused(monkeypatch, tmp_path):
    a = actor(); game(a, monkeypatch)
    cp = W.ActorCheckpoint.capture(a, cursor(a))
    kw = dict(expected_sha256=cp.sha256, driver_state=cursor(a), claim_directory=tmp_path)
    with pytest.raises(W.WorkerError, match='still live'):
        W.ActorCheckpoint.restore_record(cp.record, model(), callback, **kw)
    record = cp.record; record['source_process']['boot'] = 'wrong-boot'
    kw['expected_sha256'] = hashlib.sha256(W.encoded(record)).hexdigest()
    with pytest.raises(W.WorkerError, match='cross-host or cross-boot'):
        W.ActorCheckpoint.restore_record(record, model(), callback, **kw)
    with pytest.raises(W.WorkerError, match='digest'):
        W.ActorCheckpoint.restore_record(record, model(), callback, **dict(kw, expected_sha256='a'*64))
    assert not list(tmp_path.iterdir())


def boundary(event='game_start', **kw):
    data = dict(event=event, actor_id='a', game_id='g0', game_sequence=0, seed=1,
        policy_version=0, policy_sha256='a'*64, generated_steps=0, published_steps=0,
        discarded_steps=0, engine_tick=90, terminal=False, pending_rows=0,
        publication_sequence=0, remaining_quota=8, remaining_budget=100)
    data.update(kw)
    return W.WorkerBoundary(**data)


def test_retirement_requests_wait_for_terminal_ack_and_survive_object_recycle():
    clock = [0.]
    lifecycle = W.ActorLifecycle(actor_id='a', monotonic=lambda: clock[0], read_rss=lambda: 1024)
    assert lifecycle.on_boundary(boundary()).action == 'continue'
    clock[0] = 1200.
    quota = boundary('publication', generated_steps=8, published_steps=4, pending_rows=0,
                     remaining_budget=92, remaining_quota=0, publication_sequence=1, engine_tick=130)
    decision = lifecycle.on_boundary(quota)
    assert decision.action == 'recycle_due' and not decision.safe_boundary
    done = replace(quota, event='game_complete', published_steps=8, terminal=True,
                   policy_version=1, remaining_quota=8)
    assert lifecycle.on_boundary(done).safe_boundary
    new_game = replace(done, event='game_start', game_id='g1', game_sequence=1, terminal=False, engine_tick=90)
    with pytest.raises(W.WorkerError, match='retirement'):
        lifecycle.on_boundary(new_game)


def test_game_count_bound_and_rss_stop_and_lease_drain():
    life = W.ActorLifecycle(actor_id='a', read_rss=lambda: 100, recycle_games=2)
    life.on_boundary(boundary())
    assert life.on_boundary(boundary('game_complete', terminal=True, generated_steps=1, published_steps=1, remaining_budget=99)).action == 'continue'
    life.on_boundary(boundary(game_id='g1', game_sequence=1, generated_steps=1, published_steps=1, remaining_budget=99))
    assert life.on_boundary(boundary('game_complete', terminal=True, game_id='g1', game_sequence=1, generated_steps=2, published_steps=2, remaining_budget=98)).action == 'recycle_due'
    with pytest.raises(W.WorkerError, match='RSS'):
        W.ActorLifecycle(actor_id='a', read_rss=lambda: (2 << 30)+1).on_boundary(boundary())
    life = W.ActorLifecycle(actor_id='a', read_rss=lambda: 100)
    life.on_boundary(boundary())
    life.lease = NS(poll=lambda: 'reclaim')
    assert life.on_boundary(boundary('publication')).action == 'drain'
    life.lease = None
    assert life.on_boundary(boundary('publication')).action == 'drain'


@pytest.mark.parametrize('bad', [dict(discarded_steps=1), dict(terminal=True), dict(engine_resume_qualified=True),
                              dict(published_steps=1), dict(remaining_budget=-1)])
def test_bad_boundary_fails_closed(bad):
    with pytest.raises(W.WorkerError):
        W.ActorLifecycle(actor_id='a', read_rss=lambda: 100).on_boundary(boundary(**bad))
