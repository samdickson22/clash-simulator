"""Synthetic FIFO/loading/output timing tests; no real pixels or model weights."""
from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import patch
import validation_replay_v4 as replay


def main():
    checks = 0
    def check(value):
        nonlocal checks
        assert value
        checks += 1
    def rejects(call):
        nonlocal checks
        try:
            call()
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Expected refusal')
    frames = [dict(seq=i, produced_at=t) for i, t in enumerate((100., 100.05, 101.))]
    clock = SimpleNamespace(now=0.)
    reads, calls, outputs, journal = [], [], [], []
    class Cache:
        index = {'ep': {'block_size': 2}}
        def get(self, episode, indices, raw):
            check(episode == 'ep' and raw is True)
            reads.append(indices)
            clock.now += .020
            return indices
    class Runtime:
        def step(self, image, episode, stamp):
            calls.append((image, episode, stamp))
            clock.now += .060
            return {'inner_timestamp_is_not_authoritative': -999}
    def emit(row):
        outputs.append(row)
        clock.now += .010
    def complete(row):
        journal.append(row)
        clock.now += .005
    result = replay.replay_episode(Runtime(), Cache(), 'ep', frames, emit, complete, clock=lambda:clock.now)
    check(reads == [[0, 1], [2]])
    check([r[0] for r in calls] == [0, 1, 2])
    check(abs(calls[1][2]-50) < 1e-8 and calls[2][2] == 1000)
    check([r['source_seq'] for r in outputs] == [0, 1, 2])
    check(all(abs(a['available_timestamp_ms']-b) < 1e-8 for a, b in zip(journal, (90, 165, 1095))))
    check(all(abs(a['service_ms']-b) < 1e-8 for a, b in zip(journal, (90, 75, 95))))
    check(result['frames'] == 3 and abs(result['final_available_timestamp_ms']-1095) < 1e-8)
    rejects(lambda: replay.frame_times([]))
    for bad in ([dict(seq=1, produced_at=1.)], [dict(seq=0, produced_at=float('nan'))],
                [dict(seq=0, produced_at=True)], [dict(seq=0, produced_at=1.), dict(seq=1, produced_at=1.)],
                [dict(seq=0, produced_at=2.), dict(seq=1, produced_at=1.)]):
        rejects(lambda: replay.frame_times(bad))
    # A failed write must not produce a completed-frame receipt.
    def fail_write(row):
        raise ValueError('Synthetic write failure')
    before = len(journal)
    rejects(lambda: replay.replay_episode(Runtime(), Cache(), 'ep', frames, fail_write, complete, clock=lambda:clock.now))
    check(len(journal) == before)
    # Formal admission precedes all checkpoint/pixel/output arguments.
    original = replay.validate_run
    def reject_admission(*args):
        raise ValueError('Synthetic incomplete formal fit')
    replay.validate_run = reject_admission
    try:
        rejects(lambda: replay.run(SimpleNamespace(run=None, source=None, split=None, phase_state=None, phase_exit=None)))
    finally:
        replay.validate_run = original
    # Bridge to scoring ignores inner/backdated availability and preserves scores.
    candidate = dict(card='Skeletons', side=0, x_tiles=3.5, y_tiles=13.5,
                     existence_q=.7, execution_timestamp_ms=-10., available_timestamp_ms=-999.)
    payloads = [dict(source_seq=i, payload=dict(episode_id='ep', timestamp_ms=row['timestamp_ms'],
                event_candidates=[dict(candidate, execution_timestamp_ms=row['timestamp_ms']-10)]))
                for i, row in enumerate(journal)]
    def join(p=payloads, c=journal, calibration=None):
        return replay.completed_predictions(p, c, episode='ep', expected_frames=3,
                                            calibration={} if calibration is None else calibration)
    predicted = join()
    check([p['available_timestamp_ms'] for p in predicted] == [r['available_timestamp_ms'] for r in journal])
    check(all(p['score'] == .7 and p['episode_id'] == 'ep' for p in predicted))
    rejects(lambda: join(payloads[:-1]))
    rejects(lambda: join(c=journal[:-1]))
    rejects(lambda: join(calibration={'default': [[0., 0.], [1., 1.]]}))
    for target, key, value in (('completion', 'source_seq', 0), ('completion', 'available_timestamp_ms', 1.),
                               ('completion', 'service_ms', float('nan')), ('completion', 'episode_id', 'other'),
                               ('payload', 'timestamp_ms', -1.), ('candidate', 'side', True),
                               ('candidate', 'execution_timestamp_ms', 10000.), ('candidate', 'existence_q', 1.1)):
        p, c = deepcopy(payloads), deepcopy(journal)
        row = c[1] if target == 'completion' else p[1]['payload']
        if target == 'candidate':
            row = row['event_candidates'][0]
        row[key] = value
        rejects(lambda: join(p, c))
    empty = deepcopy(payloads)
    for row in empty:
        row['payload']['event_candidates'] = []
    check(join(empty) == [])
    check(replay.threshold_options(.5)=={'default':.5})
    mapping={'default':.5,'Knight':.7}
    check(replay.threshold_options(.5,mapping)==mapping)
    check(replay.threshold_options(.5,mapping) is not mapping)
    for bad in ({},{'Knight':.7},{'default':.4},{'default':True},{'default':.5,'Knight':.55},
                {'default':.5,'':.7},{'default':.5,' Knight':.7},[],{'default':.5,'Knight':float('nan')}):
        rejects(lambda:replay.threshold_options(.5,bad))
    for bad in (True,None,.55,float('inf')):rejects(lambda:replay.threshold_options(bad))
    with patch.object(replay,'validate_run',return_value={}),patch.object(replay,'sha',return_value='a'*64),patch.object(replay,'read',return_value=None):
        rejects(lambda:replay.run(SimpleNamespace(run=None,source=None,split=None,phase_state=None,
            phase_exit=None,epoch=1,threshold=.5,body_threshold=.5,threshold_map='fixture-null.json')))
    print({'checks': checks, 'passed': True, 'scope': 'synthetic only; no GPU replay or formal gate'}, flush=True)


if __name__ == '__main__':
    main()
