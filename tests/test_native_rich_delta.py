"""Phase B delta rich telemetry: host reconstruction and cached compaction.

A Python model of the probe's seven cumulative rings emits the full
(``observe-rich``) and delta (``observe-rich-since``) envelopes for the same
frame, including ring overflow, telemetry epoch resets (snapshot restores) and
identity-mismatch frames. The reconstructed rich object must serialize to the
same bytes as the full one, and cached compaction must produce the identical
storage record. No emulator or adb is used.
"""
import copy
import importlib
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from clasher.rl import native_frame_storage as storage
from clasher.rl.native_rich_delta import (
    TRACE_ORDER,
    TRANSMIT_FIELD_TRACES,
    NativeRichTraceAccumulator,
    RichTraceDeltaError,
)

CAPACITY = {'combatEvents': 64, 'phaseRuntime': 32, 'specialMovementRuntime': 8,
            'actionMovementRuntime': 16, 'characterStateRuntime': 8,
            'visibilityRuntime': 4, 'remainingRuntime': 24}


class RingModel:
    """Process-global sequences; an epoch reset only moves the first sequence."""

    def __init__(self, field, rng):
        self.field, self.rng, self.capacity = field, rng, CAPACITY[field]
        self.next, self.first = 1, 1
        self.identity = (1, 1)
        self.pending = None
        self.records = {}

    def begin(self, generation, epoch):
        self.identity, self.first, self.pending = (generation, epoch), self.next, None

    def begin_lazily(self, generation, epoch):
        # Like the visibility/remaining rings: re-begin on the next publish.
        self.pending = (generation, epoch)

    def publish(self, count, tick):
        if count and self.pending is not None:
            self.begin(*self.pending)
        for _ in range(count):
            sequence = self.next
            self.next += 1
            self.records[sequence] = {
                'sequence': sequence, 'tick': tick, 'kind': self.rng.choice(['damage', 'spawn', 'remove', 'é-edge']),
                'subject': {'nativeObjectId': 5000000 + self.rng.randrange(40), 'owner': self.rng.randrange(2),
                            'x': self.rng.randrange(18000) / 1000, 'hp': None if self.rng.random() < .2 else 17},
                'amount': self.rng.randrange(-5, 900), 'ratio': self.rng.random(),
                'tags': [self.rng.randrange(9) for _ in range(self.rng.randrange(3))],
            }

    def envelope(self, generation, epoch, tick, since=None):
        identity = self.identity == (generation, epoch)
        first = self.first if identity else self.next
        oldest = self.next - self.capacity if self.next > first + self.capacity else first
        transmit = oldest
        if since is not None and oldest <= since <= self.next:
            transmit = since
        env = {'ok': True, 'schema': f'{self.field}.v1', 'generation': generation, 'stateEpoch': epoch,
               'observationTick': tick, 'capacity': self.capacity, 'hookSetAttested': True,
               'hookSetInstalled': True,
               'capability': {'status': 'derived' if identity else 'unavailable', 'failClosed': True},
               'epochFirstSequence': first, 'oldestRetainedSequence': oldest}
        if self.field in TRANSMIT_FIELD_TRACES:
            env['transmitFromSequence'] = transmit
        env.update({'nextSequence': self.next, 'overflowCount': max(0, self.next - first - self.capacity),
                    'rejectedCount': 0, 'sequenceGapBeforeOldest': oldest > first, 'complete': identity})
        if since is not None:
            env['deltaSinceSequence'] = since
            env['deltaTransmitFromSequence'] = transmit
        env['events'] = [copy.deepcopy(self.records[s]) for s in range(transmit, self.next)] if identity else []
        return env


class ProbeModel:
    def __init__(self, seed=7):
        self.rng = random.Random(seed)
        self.rings = {field: RingModel(field, self.rng) for field in TRACE_ORDER}
        self.generation, self.epoch, self.tick = 1, 1, 0

    def advance(self, ticks=5, burst=False):
        self.tick += ticks
        for field, ring in self.rings.items():
            count = self.rng.randrange(0, 3 * ring.capacity if burst else 4)
            ring.publish(count, self.tick)

    def restore(self):
        # stateEpoch only increases; some rings begin at once, others lazily,
        # so frames right after a restore can show ring identity mismatches.
        self.epoch += 1
        for ring in self.rings.values():
            if self.rng.random() < .5:
                ring.begin(self.generation, self.epoch)
            else:
                ring.begin_lazily(self.generation, self.epoch)

    def rich(self, cursors=None):
        """What json.loads returns for the probe's response bytes."""
        body = {'ok': True, 'schema': 'native-rich-telemetry.v3', 'generation': self.generation,
                'stateEpoch': self.epoch, 'tick': self.tick,
                'objects': [{'nativeObjectId': 5000006, 'phaseRuntime': {'lastStep': self.tick}}]}
        for index, field in enumerate(TRACE_ORDER):
            body[field] = self.rings[field].envelope(
                self.generation, self.epoch, self.tick, None if cursors is None else cursors[index])
        body['visibilityTail'] = {'ok': True, 'note': 'non-trace channel'}
        return json.loads(json.dumps(body))


def frame_of(rich, tick):
    return {'ordinary': {'tick': tick, 'objects': []}, 'rich': rich,
            'level_source': {'levels': {5000006: 11, 5000008: 3}, 'transport': 'fixture'}}


def run_stream(model, frames, *, schedule):
    accumulator = NativeRichTraceAccumulator()
    transmitted = full_events = 0
    for index in range(frames):
        action = schedule(index)
        if action == 'restore':
            model.restore()
        elif action == 'burst':
            model.advance(burst=True)
        elif action == 'quiet_restore':
            # Restore with no new events before the next observation: lazily
            # beginning rings report an identity mismatch (no events).
            model.restore()
            model.tick += 5
        else:
            model.advance()
        full = model.rich()
        command = accumulator.command()
        assert command.startswith('observe-rich-since ')
        delta = model.rich([int(c) for c in command.split()[1:]])
        rebuilt = accumulator.apply(delta)
        assert rebuilt == full
        assert storage._json_bytes(rebuilt) == storage._json_bytes(full)
        cached = storage.compact_native_frame(frame_of(rebuilt, model.tick),
                                              event_cache=accumulator.event_cache(rebuilt))
        reference = storage.compact_native_frame(frame_of(full, model.tick))
        assert storage._json_bytes(cached) == storage._json_bytes(reference)
        storage.validate_native_frame_storage(cached)
        transmitted += sum(len(delta[f]['events']) for f in TRACE_ORDER)
        full_events += sum(len(full[f]['events']) for f in TRACE_ORDER)
    return accumulator, transmitted, full_events


@pytest.mark.parametrize('seed', range(6))
def test_reconstruction_is_byte_identical_across_overflow_restore_and_identity_loss(seed):
    rng = random.Random(seed)
    actions = ['step'] * 6 + ['burst', 'restore', 'quiet_restore']

    def schedule(index):
        return 'step' if index < 3 else rng.choice(actions)

    accumulator, transmitted, full_events = run_stream(ProbeModel(seed), 80, schedule=schedule)
    assert accumulator.state == 'open'
    assert accumulator.receipt['frames'] == 80
    assert transmitted < full_events


def test_steady_state_transmits_only_new_events():
    model = ProbeModel(3)
    accumulator, transmitted, full_events = run_stream(model, 200, schedule=lambda i: 'step')
    new_events = sum(ring.next - 1 for ring in model.rings.values())
    assert transmitted == new_events
    assert full_events > 5 * transmitted


def test_first_command_requests_full_retransmit_and_cursor_advances():
    model = ProbeModel()
    model.advance()
    accumulator = NativeRichTraceAccumulator()
    assert accumulator.command() == 'observe-rich-since ' + ' '.join(['0'] * 7)
    assert accumulator.command('observe-atomic-levels').startswith('observe-atomic-levels 0 ')
    accumulator.apply(model.rich([0] * 7))
    assert accumulator.cursors() == [ring.next for ring in model.rings.values()]
    with pytest.raises(ValueError):
        accumulator.command('observe-rich')


def _primed():
    model = ProbeModel(11)
    accumulator = NativeRichTraceAccumulator()
    for ring in model.rings.values():
        ring.publish(ring.capacity + 5, model.tick)  # overflow every ring once
    for _ in range(3):
        model.advance()
        accumulator.apply(model.rich(accumulator.cursors()))
    assert all(ring.next > ring.capacity + 1 for ring in model.rings.values())
    model.advance()
    for ring in model.rings.values():
        ring.publish(3, model.tick)
    return model, accumulator


DELTA_FAULTS = {
    'gap': lambda d: d['combatEvents']['events'].pop(1),
    'reorder': lambda d: d['phaseRuntime']['events'].reverse(),
    'duplicate': lambda d: d['combatEvents']['events'].__setitem__(1, d['combatEvents']['events'][0]),
    'missing_delta_keys': lambda d: [d['actionMovementRuntime'].pop(k)
                                     for k in ('deltaSinceSequence', 'deltaTransmitFromSequence')],
    'cursor_not_echoed': lambda d: d['remainingRuntime'].__setitem__('deltaSinceSequence', 0),
    'transmit_rule': lambda d: d['characterStateRuntime'].__setitem__(
        'deltaTransmitFromSequence', d['characterStateRuntime']['deltaTransmitFromSequence'] - 1),
    'transmit_field': lambda d: d['visibilityRuntime'].__setitem__('transmitFromSequence', 0),
    'unexpected_transmit_field': lambda d: d['specialMovementRuntime'].__setitem__('transmitFromSequence', 1),
    'delta_keys_misplaced': lambda d: d.__setitem__('combatEvents', {
        'deltaSinceSequence': d['combatEvents']['deltaSinceSequence'],
        **{k: v for k, v in d['combatEvents'].items() if k != 'deltaSinceSequence'}}),
    'epoch_change_without_full': lambda d: d['phaseRuntime'].__setitem__('stateEpoch', 99),
    'regression': lambda d: d['combatEvents'].__setitem__('nextSequence', 1),
    # Bounds stay self-consistent but the ring's next falls below our cursor.
    'regression_consistent': lambda d: d['combatEvents'].update(
        nextSequence=d['combatEvents']['deltaSinceSequence'] - 1,
        oldestRetainedSequence=d['combatEvents']['epochFirstSequence'], events=[]),
    # Claims retained history older than anything the host holds.
    'claims_unseen_history': lambda d: d['phaseRuntime'].__setitem__(
        'oldestRetainedSequence', d['phaseRuntime']['epochFirstSequence']),
    'bounds_inverted': lambda d: d['phaseRuntime'].__setitem__('epochFirstSequence', 10 ** 6),
    'events_not_list': lambda d: d['phaseRuntime'].__setitem__('events', None),
    'event_not_object': lambda d: d['combatEvents']['events'].__setitem__(0, 5),
    'negative_cursor': lambda d: d['combatEvents'].__setitem__('deltaSinceSequence', -1),
    'bool_cursor': lambda d: d['combatEvents'].__setitem__('deltaTransmitFromSequence', True),
    'trace_missing': lambda d: d.pop('remainingRuntime'),
    'delta_keys_elsewhere': lambda d: d.__setitem__('visibilityTail', {'deltaSinceSequence': 1}),
    'not_ok': lambda d: d.__setitem__('ok', False),
    'schema': lambda d: d.__setitem__('schema', 'native-rich-telemetry.v2'),
}


@pytest.mark.parametrize('fault', sorted(DELTA_FAULTS))
def test_delta_faults_invalidate_the_accumulator(fault):
    model, accumulator = _primed()
    before = accumulator.cursors()
    delta = model.rich(before)
    DELTA_FAULTS[fault](delta)
    with pytest.raises(RichTraceDeltaError):
        accumulator.apply(delta)
    assert accumulator.state == 'failed'
    assert accumulator.receipt['failure']
    # Nothing was committed and no later frame can be accepted.
    assert accumulator.cursors() == before
    with pytest.raises(RichTraceDeltaError):
        accumulator.command()
    with pytest.raises(RichTraceDeltaError):
        accumulator.apply(model.rich(before))


def test_full_cumulative_response_is_not_accepted_as_a_delta():
    model = ProbeModel()
    model.advance()
    with pytest.raises(RichTraceDeltaError, match='not a delta'):
        NativeRichTraceAccumulator().apply(model.rich())


def test_event_cache_is_bound_to_the_latest_reconstructed_frame():
    model = ProbeModel()
    accumulator = NativeRichTraceAccumulator()
    model.advance()
    first = accumulator.apply(model.rich(accumulator.cursors()))
    model.advance()
    second = accumulator.apply(model.rich(accumulator.cursors()))
    accumulator.event_cache(second)
    with pytest.raises(RichTraceDeltaError):
        accumulator.event_cache(first)
    with pytest.raises(RichTraceDeltaError):
        accumulator.event_cache(copy.deepcopy(second))


# ------------------------------------------------------ cached compaction

def _cached_frame():
    model = ProbeModel(5)
    accumulator = NativeRichTraceAccumulator()
    for _ in range(4):
        model.advance(burst=True)
        rich = accumulator.apply(model.rich(accumulator.cursors()))
    return frame_of(rich, model.tick), accumulator.event_cache(rich)


def test_cached_compaction_matches_uncached_and_leaves_frame_intact():
    frame, cache = _cached_frame()
    original = copy.deepcopy(frame)
    assert storage.compact_native_frame(frame, event_cache=cache) == storage.compact_native_frame(frame)
    assert frame == original
    partial = {'combatEvents': cache['combatEvents']}
    assert storage.compact_native_frame(frame, event_cache=partial) == storage.compact_native_frame(frame)


@pytest.mark.parametrize('fault', ['other_list', 'count', 'digest', 'not_bytes'])
def test_cached_compaction_rejects_a_cache_for_another_frame(fault):
    frame, cache = _cached_frame()
    cache = {k: dict(v) for k, v in cache.items()}
    entry = cache['phaseRuntime']
    if fault == 'other_list':
        entry['events'] = list(entry['events'])
    elif fault == 'count':
        entry['event_bytes'] = entry['event_bytes'][:-1]
    elif fault == 'digest':
        entry['json_sha256'] = '0' * 64
    else:
        entry['event_bytes'] = [piece.decode() for piece in entry['event_bytes']]
    with pytest.raises(ValueError):
        storage.compact_native_frame(frame, event_cache=cache)


def test_cached_compaction_detects_a_colliding_sentinel(monkeypatch):
    frame, cache = _cached_frame()
    fixed = SimpleNamespace(hex='fixednonce')
    monkeypatch.setattr(storage.uuid, 'uuid4', lambda: fixed)
    frame['ordinary']['note'] = '\x00clasher-events-fixednonce-combatEvents\x00'
    with pytest.raises(ValueError, match='sentinel'):
        storage.compact_native_frame(frame, event_cache=cache)


# ---------------------------------------------------- readiness runner wiring

@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    return importlib.import_module('run_readiness_v2')


def test_runner_read_options_default_to_current_behavior(runner, monkeypatch):
    assert runner.native_read_options(SimpleNamespace()) == runner.DEFAULT_NATIVE_READ_OPTIONS
    assert runner.DEFAULT_NATIVE_READ_OPTIONS == {
        'level_reader': 'legacy', 'rich_transfer': 'full', 'probe_build': 'pinned',
        'probe_process_identity': False}
    captured = {}
    monkeypatch.setattr('sys.argv', ['run_readiness_v2.py', 'execute', '--plan', 'p', '--output', 'o',
                                     '--native-lock', 'l'])
    monkeypatch.setattr(runner, 'execute', lambda args: captured.setdefault('args', args))
    runner.main()
    assert runner.native_read_options(captured['args']) == runner.DEFAULT_NATIVE_READ_OPTIONS


@pytest.mark.parametrize('options,message', [
    ({'native_level_reader': 'probe'}, 'phaseb'),
    ({'native_rich_transfer': 'delta'}, 'phaseb'),
    ({'native_level_reader': 'batched', 'native_probe_process_identity': True}, 'probe level reader'),
    ({'native_level_reader': 'dd'}, 'unknown'),
    ({'native_rich_transfer': 'zip'}, 'unknown'),
    ({'native_probe_build': 'latest'}, 'unknown'),
])
def test_runner_read_option_guards(runner, options, message):
    with pytest.raises(ValueError, match=message):
        runner.native_read_options(SimpleNamespace(**options))


def test_runner_accepts_phase_b_combinations(runner):
    options = runner.native_read_options(SimpleNamespace(
        native_level_reader='probe', native_rich_transfer='delta', native_probe_build='phaseb',
        native_probe_process_identity=True))
    assert options['probe_build'] == 'phaseb'
    assert runner.NATIVE_PROBE_BUILDS['phaseb']['probe_sha256'].startswith('76953b60')
    batched = runner.native_read_options(SimpleNamespace(native_level_reader='batched'))
    assert batched['probe_build'] == 'pinned'


def test_runner_rich_reader_full_and_delta(runner):
    model = ProbeModel(9)
    commands = []

    def call(command):
        commands.append(command)
        if command == 'observe-rich':
            return model.rich()
        return model.rich([int(c) for c in command.split()[1:]])

    full_reader = runner.NativeRichReader(call, 'full')
    delta_reader = runner.NativeRichReader(call, 'delta')
    assert full_reader.receipt is None
    for _ in range(5):
        model.advance()
        full = full_reader.read()
        rebuilt = delta_reader.read()
        assert rebuilt == full
        assert delta_reader.compact(frame_of(rebuilt, model.tick)) == full_reader.compact(frame_of(full, model.tick))
    assert commands.count('observe-rich') == 5
    assert sum(c.startswith('observe-rich-since ') for c in commands) == 5
    assert delta_reader.receipt['frames'] == 5 and delta_reader.receipt['status'] == 'open'
    with pytest.raises(ValueError):
        runner.NativeRichReader(call, 'partial')
