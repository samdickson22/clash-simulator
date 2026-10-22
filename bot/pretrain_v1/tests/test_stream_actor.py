"""CPU actor/queue checks. No engine jobs, GPU, network, or remote games."""
import copy
from dataclasses import replace
import gc
import json
from types import SimpleNamespace as NS
import weakref

import numpy as np
import pytest
import torch

from bot.players.base import MatchContext
from bot.pretrain_v1 import featurize as F
from bot.pretrain_v1 import sim_ours as S
from bot.pretrain_v1 import stream_actor as A
from bot.pretrain_v1.model import PolicyV1, collate
from bot.pretrain_v1.policy import Session
from bot.pretrain_v1.policy_trace import PolicyTrace
from bot.pretrain_v1.tests.test_featurize import rec
from bot.pretrain_v1.tests.test_sim_ours import DECK, battle

SEED = 2026102101
PINS = dict(native='358cf506', gamedata='ccd2a5f1', source='unit-fixture-only')
PROVENANCE = A.manifest_sha256(PINS)
ANCHOR = 'a'*64


@pytest.fixture
def model():
    torch.set_num_threads(1)
    torch.manual_seed(1)
    return PolicyV1(d=24, layers=1, heads=3, ffn=48).eval()


def make_actor(model, callback, **kw):
    args = dict(actor_id='worker-0', seed=SEED, anchor_sha256=ANCHOR, provenance_sha256=PROVENANCE,
                opponent_id='fixture', budget_steps=100, quota_steps=100, chunk_rows=4)
    args.update(kw)
    return A.StreamingPolicyOursPlayer(model, callback, **args)


def acknowledge(c, boundary):
    return A.PolicyUpdate(c.version, c.policy_sha256)


def start(a, monkeypatch, seed=11):
    b, own = battle(monkeypatch)
    b.game_over, b.winner = False, None
    a.bind_ours(b)
    a.start(MatchContext(0, seed, tuple(DECK)))
    return b, own


def view(tick, can_act=True):
    return NS(tick=tick, seat=0, can_act=can_act)


def test_exact_session_features_rng_logp_actions_and_budget_across_chunks(model, monkeypatch):
    chunks, boundaries, chunk_refs = [], [], []
    gates, tiles, trunks = [], [], []
    original_gate, original_tile, original_trunk = model.gate_logits, model.tile_logits, model.trunk
    def gate(*args):
        gates.append(1)
        return original_gate(*args)
    def tile(*args):
        tiles.append(1)
        return original_tile(*args)
    def trunk(*args):
        trunks.append(1)
        return original_trunk(*args)
    monkeypatch.setattr(model, 'gate_logits', gate)
    monkeypatch.setattr(model, 'tile_logits', tile)
    monkeypatch.setattr(model, 'trunk', trunk)
    def publish(c, boundary):
        # Callback can persist without retaining original chunk arrays.
        chunks.append(copy.deepcopy(c)); boundaries.append(boundary)
        chunk_refs.append(weakref.ref(c.action))
        assert a.session.hist.polls == a.generated_steps
        assert a.session.hist.last_tick == 90+(a.generated_steps-1)*5
        assert a.pending is None and not a.rows
        if boundary.reason == 'quota':
            return A.PolicyUpdate(c.version+1, c.policy_sha256, copy.deepcopy(model.state_dict()), 7)
        return acknowledge(c, boundary)
    a = make_actor(model, publish, budget_steps=93, quota_steps=7, chunk_rows=3)
    b, own = start(a, monkeypatch)
    # Use a separate plain production Session and live producer as the oracle.
    baseline_model = copy.deepcopy(model)
    # Remove patched instance callables, whose closures point at actor model.
    for name in ('gate_logits', 'tile_logits', 'trunk'):
        delattr(baseline_model, name)
    trace = PolicyTrace(baseline_model)
    baseline = Session(trace, (11 ^ 0x9E3779B97F4A7C15) % (1 << 63))
    frames = S.OursFrames(b, 0, DECK, 11)
    feats, decisions, logps = [], [], []
    for i in range(93):
        b.tick = 90+5*i
        own.elixir = 0. if i < 3 else 7.
        (record, extras), _ = frames.record()
        trace.clear()
        expected = baseline.step(record, extras)
        lp = trace.log_probability(expected)
        if expected.status == 'play':
            baseline.accepted(expected)
        actual = a.act(view(b.tick, can_act=expected.status != 'forced'))
        assert (actual.action, actual.stats['status'], actual.stats['value'], actual.stats['p_wait'],
                actual.stats['p_wait5'], actual.stats['logp']) == (
                    expected.action, expected.status, expected.value, expected.p_wait, expected.p_wait5, lp)
        assert F.feature_bytes(a.session.last_feat) == F.feature_bytes(baseline.last_feat)
        assert a.session.rng.bit_generator.state == baseline.rng.bit_generator.state
        feats.append(copy.deepcopy(baseline.last_feat)); decisions.append(expected); logps.append(lp)
    gate_count, tile_count, state = len(gates), len(tiles), copy.deepcopy(a.session.rng.bit_generator.state)
    b.tick += 5
    with pytest.raises(A.BudgetComplete) as caught:
        a.act(view(b.tick))
    assert caught.value.generated_steps == 93 and caught.value.unfinished
    assert len(gates) == gate_count == 93 and len(tiles) == tile_count
    assert a.session.hist.polls == 93 and a.session.rng.bit_generator.state == state
    assert len(trunks) == 93+sum(not z.terminal for z in boundaries)
    assert sum(len(c.action) for c in chunks) == a.generated_steps == 93
    assert max(len(c.action) for c in chunks) <= 3
    assert {'forced', 'wait', 'play'} <= {d.status for d in decisions}
    assert any(not d.actor.all() for d in chunks)
    offset = 0
    for c in chunks:
        n = len(c.action)
        expected = collate(feats[offset:offset+n])
        for key in expected:
            np.testing.assert_array_equal(c.features[key], expected[key].numpy())
            assert c.features[key].dtype == expected[key].numpy().dtype
        np.testing.assert_array_equal(c.action, [d.action for d in decisions[offset:offset+n]])
        np.testing.assert_array_equal(c.old_logp, logps[offset:offset+n])
        if offset+n < 93:
            assert c.bootstrap == decisions[offset+n].value
        assert not c.terminated.any() and not c.reward.any()
        offset += n
    a.close(); gc.collect()
    assert all(r() is None for r in chunk_refs)
    assert a.session is a.frames is a.battle is None and a.pending is None and not a.rows
    assert a.unfinished_games == 1 and a.discarded_steps == 0


@pytest.mark.parametrize('winner, expected', [(0, 1.), (1, -1.), (None, 0.)])
def test_true_terminal_close_finalizes_pending_partial_chunk(model, monkeypatch, winner, expected):
    chunks = []
    def callback(c, b):
        chunks.append((c, b))
        return acknowledge(c, b)
    a = make_actor(model, callback)
    b, _ = start(a, monkeypatch)
    for tick in (90, 95):
        b.tick = tick; a.act(view(tick))
    assert not chunks and len(a.rows) == 1 and a.pending is not None
    # The real engine may terminate between grid polls. close is called by the
    # existing play_match finally, before it computes its returned result.
    b.tick, b.game_over, b.winner = 97, True, winner
    a.close(); a.close()
    c, boundary = chunks[0]
    assert boundary.terminal and not boundary.unfinished and boundary.reason == 'terminal'
    np.testing.assert_array_equal(c.terminated, [False, True])
    np.testing.assert_array_equal(c.reward, [0., expected])
    assert c.bootstrap == 0 and a.completed_games == 1 and a.generated_steps == 2


def test_exact_quota_on_terminal_and_cross_game_budget(model, monkeypatch):
    chunks = []
    def callback(c, b):
        chunks.append((c, b))
        if b.reason == 'quota':
            return A.PolicyUpdate(c.version+1, c.policy_sha256, copy.deepcopy(model.state_dict()), 2)
        return acknowledge(c, b)
    a = make_actor(model, callback, budget_steps=5, quota_steps=2)
    b, _ = start(a, monkeypatch)
    for tick in (90, 95):
        b.tick = tick; a.act(view(tick))
    b.tick, b.game_over, b.winner = 96, True, 0
    a.close()
    assert a.version == 1 and chunks[0][1].reason == 'quota' and chunks[0][1].terminal
    b, _ = start(a, monkeypatch, seed=19)
    for tick in (90, 95, 100):
        b.tick = tick; a.act(view(tick))
    b.tick = 105
    with pytest.raises(A.BudgetComplete):
        a.act(view(105))
    a.close()
    assert [len(c.action) for c, _ in chunks] == [2, 2, 1]
    assert [c.version for c, _ in chunks] == [0, 1, 2]
    assert a.generated_steps == 5 and a.completed_games == 1 and a.unfinished_games == 1


def test_new_weights_apply_before_next_action_with_history_preserved(model, monkeypatch):
    def callback(c, b):
        assert b.reason == 'quota'
        assert a.session.hist.polls == 1 and a.session.hist.last_tick == 90
        newer = copy.deepcopy(model)
        newer.gate_bias.fill_(100.)
        return A.PolicyUpdate(1, A.policy_sha256(newer), newer.state_dict(), 9)
    a = make_actor(model, callback, budget_steps=3, quota_steps=1)
    b, _ = start(a, monkeypatch)
    a.act(view(90))
    rng = copy.deepcopy(a.session.rng.bit_generator.state)
    b.tick = 95
    a.act(view(95))
    assert a.version == 1 and a.session.hist.polls == 2
    # If first step played, second is forced. In either case no second gate
    # draw happened on the old policy; busy histories still carry the pending.
    assert float(model.gate_bias) == 100
    assert a.pending.old_logp <= 0
    assert a.session.rng.bit_generator.state == rng or a.pending.action == F.NOOP


def test_nonterminal_close_no_fictitious_draw_no_retry(model, monkeypatch):
    chunks = []
    a = make_actor(model, lambda c, b: chunks.append((c, b)))
    b, _ = start(a, monkeypatch)
    a.act(view(90)); b.tick = 95; a.act(view(95))
    pending_value = a.pending.old_value
    b.tick = 98
    a.close()
    c, boundary = chunks[0]
    assert len(c.action) == 1 and not c.terminated.any() and not c.reward.any()
    assert c.bootstrap == pending_value and boundary.reason == 'unfinished'
    assert a.generated_steps == 2 and a.discarded_steps == 1 and a.unfinished_games == 1
    with pytest.raises(A.StreamError, match='stopped'):
        a.bind_ours(b)


@pytest.mark.parametrize('bad', ['none', 'same', 'digest'])
def test_barrier_failure_poisoned_no_extra_action(model, monkeypatch, bad):
    def callback(c, boundary):
        if bad == 'none': return None
        if bad == 'same': return acknowledge(c, boundary)
        return A.PolicyUpdate(1, 'b'*64, model.state_dict(), 3)
    a = make_actor(model, callback, quota_steps=1)
    b, _ = start(a, monkeypatch)
    a.act(view(90)); b.tick = 95
    with pytest.raises(A.StreamError):
        a.act(view(95))
    assert a.generated_steps == 1 and a.failed
    with pytest.raises(A.StreamError, match='stopped'):
        a.act(view(95))
    a.close()


def test_failed_generation_is_charged_and_never_topup(model, monkeypatch):
    a = make_actor(model, acknowledge)
    b, _ = start(a, monkeypatch)
    monkeypatch.setattr(a.session, 'step', lambda *args: (_ for _ in ()).throw(RuntimeError('inference failed')))
    with pytest.raises(RuntimeError, match='inference failed'):
        a.act(view(90))
    assert a.generated_steps == 1 and a.failed
    a.close()
    assert a.discarded_steps == 1
    with pytest.raises(A.StreamError, match='stopped'):
        a.bind_ours(b)


def test_grid_and_public_extras_rejected(model, monkeypatch):
    a = make_actor(model, acknowledge)
    b, _ = start(a, monkeypatch)
    b.tick = 95
    with pytest.raises(A.StreamError, match='start at 90'):
        a.act(view(95))
    assert a.generated_steps == 0 and a.failed
    a.close()
    a = make_actor(model, acknowledge)
    start(a, monkeypatch)
    original = a.frames.record
    def private_extra():
        (r, e), line = original()
        return (r, dict(e, opp_hand=['Zap'])), line
    monkeypatch.setattr(a.frames, 'record', private_extra)
    with pytest.raises(F.FeatureError):
        a.act(view(90))
    assert a.generated_steps == 1 and a.failed
    a.close()


def fixture_chunk():
    feats = [F.observe(rec(90+5*i), None, h) for h in [F.History()] for i in range(3)]
    return A.Chunk({k: t.numpy() for k, t in collate(feats).items()},
                   np.full(3, F.NOOP, np.int64), np.full(3, -.5, np.float64), np.zeros(3), np.zeros(3),
                   np.zeros(3, bool), np.ones(3, bool), np.full(3, 5, np.int16),
                   .25, 0, 'fixture', SEED, ANCHOR, 'b'*64, 3, PROVENANCE, 'opponent')


def queue(tmp_path, **kw):
    args = dict(max_bytes=10**7, max_chunks=2, runtime_manifest=PINS)
    args.update(kw)
    return A.AtomicChunkQueue(tmp_path, **args)


def test_atomic_queue_mmaps_digest_capacity_receipt_and_ack(tmp_path):
    q, c = queue(tmp_path), fixture_chunk()
    receipt = q.write(c)
    d = q.load(receipt, expected_version=0, expected_policy_sha256=c.policy_sha256)
    assert all(isinstance(a, np.memmap) and not a.flags.writeable for a in d.features.values())
    for k in c.features:
        np.testing.assert_array_equal(c.features[k], d.features[k])
    assert receipt.bytes == sum(p.stat().st_size for p in (tmp_path/receipt.name).iterdir())
    with pytest.raises(A.StreamError, match='version'):
        q.load(receipt, expected_version=1)
    with pytest.raises(A.StreamError, match='policy digest'):
        q.load(receipt, expected_version=0, expected_policy_sha256='c'*64)
    q.write(c)
    with pytest.raises(A.QueueFull): q.write(c)
    del d
    q.acknowledge(receipt)
    assert not (tmp_path/receipt.name).exists()
    q.write(c)


def test_byte_cap_exact_and_abandoned_partial_counts(tmp_path):
    c = fixture_chunk()
    sizing = queue(tmp_path/'sizing')
    receipt = sizing.write(c)
    q = queue(tmp_path/'exact', max_bytes=receipt.bytes, max_chunks=5)
    r = q.write(c)
    assert r.bytes == receipt.bytes
    with pytest.raises(A.QueueFull): q.write(c)
    q = queue(tmp_path/'small', max_bytes=receipt.bytes-1)
    with pytest.raises(A.QueueFull): q.write(c)
    assert list(q.root.iterdir()) == [q.root/'.writer.lock']
    q = queue(tmp_path/'partial', max_chunks=1)
    (q.root/'.partial-crashed-writer').mkdir()
    (q.root/'.partial-crashed-writer'/'incomplete.npy').write_bytes(b'partial')
    with pytest.raises(A.QueueFull): q.write(c)


def test_partial_write_failure_never_publishes(tmp_path, monkeypatch):
    q = queue(tmp_path)
    def fail(_): raise OSError('fsync interrupted')
    monkeypatch.setattr(A.os, 'fsync', fail)
    with pytest.raises(OSError, match='interrupted'):
        q.write(fixture_chunk())
    assert not list(tmp_path.glob('chunk-*')) and not list(tmp_path.glob('.partial-*'))


@pytest.mark.parametrize('target', ['array', 'manifest', 'receipt'])
def test_tampering_fails_closed(tmp_path, target):
    q = queue(tmp_path)
    r = q.write(fixture_chunk())
    if target == 'array':
        p = tmp_path/r.name/'action.npy'
        with open(p, 'r+b') as out:
            out.seek(-1, 2); out.write(b'!')
    elif target == 'manifest':
        p = tmp_path/r.name/'manifest.json'
        m = json.loads(p.read_text()); m['chunk']['version'] = 99
        p.write_text(json.dumps(m))
    else:
        r = replace(r, rows=4)
    with pytest.raises(A.StreamError): q.load(r, expected_version=0)
    with pytest.raises(A.StreamError): q.acknowledge(r)
    assert (tmp_path/r.name).exists()


def test_schema_runtime_and_no_object_pickle(tmp_path):
    q = queue(tmp_path)
    c = fixture_chunk()
    with pytest.raises(A.StreamError, match='runtime manifest'):
        q.write(replace(c, provenance_sha256='d'*64))
    features = dict(c.features); features['ent'] = features['ent'].astype(object)
    with pytest.raises(A.StreamError, match='dtype'):
        q.write(replace(c, features=features))
    r = q.write(c)
    other = queue(tmp_path, runtime_manifest=dict(native='other'))
    with pytest.raises(A.StreamError, match='runtime'):
        other.load(r, expected_version=0)
    with pytest.raises(A.StreamError, match='receipt path'):
        q.load(replace(r, name='../escape'), expected_version=0)


def test_old_critic_bootstrap_on_existing_live_record_sample(model, monkeypatch):
    # Exact records from local mem-c1/m01, longest existing five-tick segment
    # 1940..2030. No retiming or synthetic extras. This is a critic/history replay,
    # not an engine actor game, whose first public poll must be tick 90.
    from pathlib import Path
    records = [json.loads(line) for line in
               (Path(__file__).parent/'fixtures/stream_actor_live_records.jsonl').read_text().splitlines()]
    a = make_actor(model, acknowledge)
    start(a, monkeypatch)
    oracle = Session(model, 77)
    for r, following in zip(records, records[1:]):
        d = a.session.step(r)
        o = oracle.step(r)
        if d.status == 'play': a.session.accepted(d)
        if o.status == 'play': oracle.accepted(o)
        # Synchronize sampled channel history for the critic oracle, while
        # preserving the actor RNG independently throughout lookahead.
        oracle.hist = copy.deepcopy(a.session.hist)
        before = copy.deepcopy(a.session.hist)
        rng = copy.deepcopy(a.session.rng.bit_generator.state)
        f = F.observe(following, None, copy.deepcopy(oracle.hist))
        with torch.inference_mode():
            cls, _ = model.trunk(collate([f]))
            p = model.value(cls)[0].softmax(-1)
        assert a._bootstrap(following, None) == float(p[2]-p[0])
        assert a.session.hist.polls == before.polls and a.session.hist.last_tick == before.last_tick
        assert a.session.hist.pending == before.pending
        assert a.session.rng.bit_generator.state == rng
    # Test-only direct Session replay has no actor-generated rows to close.
    a.close()


def test_releases_published_arrays_and_every_transient_record(model, monkeypatch):
    record_refs, array_refs, chunk_refs = [], [], []
    class WeakRecord(dict):
        pass
    original_observe = F.observe
    def observe(*args):
        feat = original_observe(*args)
        array_refs.extend(weakref.ref(a) for a in feat.values())
        return feat
    monkeypatch.setattr(F, 'observe', observe)
    def callback(c, boundary):
        chunk_refs.extend(weakref.ref(a) for a in [*c.features.values(), c.action, c.old_value])
        assert not a.rows and a.pending is None
        return acknowledge(c, boundary)
    a = make_actor(model, callback, chunk_rows=5, budget_steps=1000, quota_steps=1000)
    b, _ = start(a, monkeypatch)
    original_record = a.frames.record
    def record():
        (r, extras), line = original_record()
        wrapped = WeakRecord(r)
        record_refs.append(weakref.ref(wrapped))
        return (wrapped, extras), line
    monkeypatch.setattr(a.frames, 'record', record)
    for i in range(1000):
        b.tick = 90+5*i
        a.act(view(b.tick))
        if i % 100 == 0:
            gc.collect()
            assert not any(r() is not None for r in record_refs)
            # Five buffered rows plus at most Session's most recent feature.
            assert sum(r() is not None for r in array_refs) <= 6*len(a.session.last_feat)
            assert not any(r() is not None for r in chunk_refs)
    b.tick += 5
    with pytest.raises(A.BudgetComplete): a.act(view(b.tick))
    a.close(); gc.collect()
    assert not any(r() is not None for r in [*record_refs, *array_refs, *chunk_refs])
    assert a.generated_steps == a.published_steps == 1000 and a.discarded_steps == 0


def test_concurrent_writers_obey_single_capacity_reservation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    q = queue(tmp_path, max_chunks=2)
    barrier = threading.Barrier(4)
    def write(_):
        barrier.wait()
        try:
            return q.write(fixture_chunk())
        except A.QueueFull:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(write, range(4)))
    assert sum(r is not None for r in receipts) == 2
    assert len(list(tmp_path.glob('chunk-*'))) == 2
    for r in filter(None, receipts):
        assert q.load(r, expected_version=0).generated_steps == 3


@pytest.mark.parametrize('deadline', [3600, 6000])
@pytest.mark.parametrize('limit', ['none', 'budget_before', 'budget_on', 'quota_before', 'quota_on'])
def test_frontend_deadline_value_only_row_true_terminal_and_exact_limits(model, monkeypatch, deadline, limit):
    chunks = []
    def callback(c, boundary):
        chunks.append((c, boundary))
        if boundary.reason == 'quota':
            return A.PolicyUpdate(c.version+1, c.policy_sha256, copy.deepcopy(model.state_dict()), 2000)
        return acknowledge(c, boundary)
    sampled = (deadline-90)//5
    budget = sampled if limit == 'budget_before' else sampled+1 if limit == 'budget_on' else 2000
    quota = sampled if limit == 'quota_before' else sampled+1 if limit == 'quota_on' else 2000
    a = make_actor(model, callback, chunk_rows=128, budget_steps=budget, quota_steps=quota)
    b, own = start(a, monkeypatch)
    own.elixir = 0.
    if deadline == 3600:
        b.entities[4].hitpoints = 0
    for i in range(sampled):
        b.tick = 90+i*5
        a.act(view(b.tick))
    hist = copy.deepcopy(a.session.hist)
    rng = copy.deepcopy(a.session.rng.bit_generator.state)
    production_last_feat = a.session.last_feat
    own.elixir = 7.
    b.tick = deadline
    if limit == 'budget_before':
        with pytest.raises(A.BudgetComplete) as caught:
            a.act(view(deadline))
        assert caught.value.unfinished and chunks[-1][1].reason == 'budget'
        assert not chunks[-1][0].terminated.any()
        assert b.tick == deadline and not b.game_over
        a.close()
        assert a.unfinished_games == 1 and a.completed_games == 0
        assert a.boundary_declined_steps == 0
    else:
        # No Session.step, gate/tile logits, sampling, or accepted command on
        # the production-declined poll. Critic sees the real public record only.
        def forbidden(*args): raise AssertionError('boundary advanced production policy')
        monkeypatch.setattr(a.session, 'step', forbidden)
        monkeypatch.setattr(a.session, 'accepted', forbidden)
        monkeypatch.setattr(model, 'gate_logits', forbidden)
        monkeypatch.setattr(model, 'tile_logits', forbidden)
        d = a.act(view(deadline))
        assert d.action == F.NOOP and d.stats['status'] == 'boundary_declined'
        assert a.pending.boundary_declined and not a.pending.actor and a.pending.old_logp == 0
        assert a.pending.features['glob'][F.G_TICK] == deadline
        assert a.pending.features['slot_ok'].any()  # Value-only even with legal public plays.
        assert a.session.last_feat is production_last_feat
        assert a.session.hist.last_tick == hist.last_tick == deadline-5
        assert a.session.hist.polls == hist.polls and a.session.hist.pending == hist.pending
        assert a.session.rng.bit_generator.state == rng
        assert not a.pending.terminated and a.pending.reward == 0
        # Engine resolves its final interval after the original declined WAIT.
        b.tick, b.game_over, b.winner = deadline+1, True, 0
        a.close()
        assert chunks[-1][1].terminal and chunks[-1][1].boundary_declined_steps == 1
        assert chunks[-1][0].boundary_declined_steps == 1
        assert chunks[-1][0].terminated[-1] and chunks[-1][0].reward[-1] == 1
        assert chunks[-1][0].bootstrap == 0
        assert a.completed_games == 1 and a.unfinished_games == 0
        assert a.boundary_declined_steps == 1
        assert a.exhausted == (limit == 'budget_on')
        assert a.version == int(limit.startswith('quota_'))
    expected = sampled+int(limit != 'budget_before')
    assert a.generated_steps == a.published_steps == expected and a.discarded_steps == 0
    assert sum(c.terminated.sum() for c, _ in chunks) == int(limit != 'budget_before')
    assert max(len(c.action) for c, _ in chunks) <= 128


def test_second_poll_after_boundary_decline_fails_closed(model, monkeypatch):
    a = make_actor(model, acknowledge, budget_steps=2000, quota_steps=2000, chunk_rows=128)
    b, _ = start(a, monkeypatch)
    for tick in range(90, 6001, 5):
        b.tick = tick; a.act(view(tick))
    consumed = a.generated_steps
    b.tick = 6005
    with pytest.raises(A.StreamError, match='actual terminal before another'):
        a.act(view(6005))
    assert a.failed and a.generated_steps == consumed
    a.close()


def test_manifest_version_mismatch_even_with_valid_manifest_digest(tmp_path):
    q = queue(tmp_path)
    r = q.write(fixture_chunk())
    p = tmp_path/r.name/'manifest.json'
    m = json.loads(p.read_text())
    m['chunk']['version'] = 99
    encoded = A._json(m)
    p.write_bytes(encoded)
    r = replace(r, manifest_sha256=A.hashlib.sha256(encoded).hexdigest())
    with pytest.raises(A.StreamError, match='version'):
        q.load(r, expected_version=0)
