"""P0 capture → P1 perception → P2 belief → P3 search → P4 input; parent is P5.

All queues are bounded. Data queues overwrite oldest; control queue saturation
fails closed. Spawn is used on Linux too, exercising the Mac process boundary.
"""
from dataclasses import asdict, replace
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
from queue import Empty, Full
from multiprocessing.connection import wait as wait_connections
import time
import traceback
from .transport import FrameRing, ObservationWindow, put_latest, drain_latest, should_drop

BUDGETS = {'capture': (3, 10), 'decode': (4, 8), 'backbone_hud': (15, 25),
           'temporal_fusion': (5, 10), 'belief': (3, 10), 'search': (110, 200), 'taps': (45, 80)}


def wait_queues(queues, timeout=.05):
    """Wait on multiprocessing queue readers, including control wakeups.

    Queue's reader is the same pipe used by get(); waiting for readability
    avoids producer/feeder notification races and consumes no messages.
    """
    return wait_connections([queue._reader for queue in queues], timeout)


class Reporter:
    def __init__(self, queue, drops, stage):
        self.queue, self.drops, self.stage = queue, drops, stage

    def __call__(self, metric, milliseconds=None, **data):
        row = dict(stage=self.stage, metric=metric, emitted_at=time.monotonic(), pid=os.getpid(), **data)
        if milliseconds is not None:
            row['ms'] = milliseconds
        try:
            self.queue.put_nowait(row)
        except Full:
            with self.drops.get_lock():
                self.drops.value += 1


def limits():
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    try:
        os.nice(max(0, 10-os.getpriority(os.PRIO_PROCESS, 0)))
    except (AttributeError, PermissionError):
        pass


def p0(config, ipc, log):
    from .capture import replay_frames, grpc_frames
    import cv2
    cv2.setNumThreads(1)
    ipc['ready'][0].set()
    if not await_start(ipc, 0):
        return
    source = config['source']
    if source['kind'] == 'synthetic':
        import numpy as np
        from .contracts import Frame
        def synthetic():
            origin = time.monotonic()+.05
            for seq in range(config.get('frames', 100)):
                produced = origin+seq/config.get('fps', 20)
                if ipc['stop'].wait(max(0, produced-time.monotonic())):
                    break
                yield Frame(source['episode'], seq, produced, time.monotonic(),
                            seq*1000/config.get('fps', 20), np.zeros((1140, 540, 3), dtype=np.uint8))
        frames = synthetic()
    elif source['kind'] == 'replay':
        frames = replay_frames(source, ipc['stop'], log, config.get('frames', 0))
    else:
        frames = grpc_frames(source, ipc['stop'], log)
    for frame in frames:
        ipc['heartbeat'][0] = time.monotonic()
        ok = ipc['ring'].write(frame)
        log('captured', sequence=frame.sequence, produced_at=frame.produced_at, ring_written=ok)
    ipc['capture_done'].set()


def await_start(ipc, index):
    while not ipc['start'].wait(.05):
        ipc['heartbeat'][index] = time.monotonic()
        if ipc['stop'].is_set():
            return False
    return True


def controls(ipc, belief, log):
    terminal = False
    while True:
        try:
            feedback = ipc['feedback'].get_nowait()
        except Empty:
            break
        if belief.own.feedback(feedback):
            ipc['revision'].value = belief.own.revision
            terminal |= feedback.state in ('accepted', 'failed', 'blocked')
            log('ledger', revision=feedback.revision, state=feedback.state,
                command_id=feedback.command_id, pending=feedback.pending)
    if terminal:
        with ipc['busy'].get_lock():
            ipc['busy'].value = False
    return terminal


def p1(config, ipc, log):
    import torch
    torch.set_num_threads(1)
    from .loading import actuator_module
    from .perception import make_perception
    api = actuator_module()  # also establishes HUD's pickle identity
    sensor = make_perception(config['perception'])
    import cv2
    cv2.setNumThreads(1)
    # Pre-capture model warmup; never include it in latency measurements/history.
    if config.get('warmup', True) and config['perception']['kind'] != 'synthetic':
        import numpy as np
        from .contracts import Frame
        now = time.monotonic()
        sensor.step(Frame('__warmup__', 0, now, now, 0., np.zeros((1140, 540, 3), dtype=np.uint8)))
    # Legacy YOLO setup changes Torch's thread count; restore the stage budget.
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    ipc['ready'][1].set()
    if not await_start(ipc, 1):
        return
    last = -1
    event_window = ObservationWindow()
    unpublished = None
    fault_done = False
    while not ipc['stop'].is_set():
        ipc['heartbeat'][1] = time.monotonic()
        frame, last, missed = ipc['ring'].read(last, config['source']['episode'])
        if missed:
            log('dropped', count=missed, reason='ring overwrite/contention')
        if frame is None:
            if ipc['capture_done'].is_set() and last >= ipc['ring'].latest.value:
                # A feeder race can reject put_latest. Retry the final public
                # message before marking EOF, preserving its unacknowledged cues.
                if unpublished is not None:
                    if put_latest(ipc['observations'], unpublished):
                        ipc['perception_last'].value = unpublished.frame.sequence
                        unpublished = None
                if unpublished is None:
                    ipc['perception_done'].set()
            if config.get('blocking_queues', False):
                ipc['ring'].wait(last)
            else:
                ipc['stop'].wait(.002)
            continue
        age = time.monotonic()-frame.produced_at
        log('capture_queue_age', age*1000, sequence=frame.sequence)
        if should_drop(frame.sequence, age):
            log('dropped', count=1, sequence=frame.sequence, reason='age/alternate', age_ms=age*1000)
            continue
        fault = config.get('fault', {})
        if fault.get('stage') == 'P1' and not fault_done and frame.sequence >= fault.get('after', 10):
            fault_done = True
            log('injected_stall', seconds=fault['seconds'])
            ipc['stop'].wait(fault['seconds'])
            # Recheck after stall: never infer or act on an expired frame.
            if should_drop(frame.sequence, time.monotonic()-frame.produced_at):
                log('dropped', count=1, sequence=frame.sequence, reason='fault-expired')
                continue
        start = time.monotonic()
        observation = sensor.step(frame)
        for key, ms in observation.timings.items():
            log(key, ms, sequence=frame.sequence)
        log('perception', (time.monotonic()-start)*1000, sequence=frame.sequence)
        hud = api.Hud(frame.produced_at, observation.public.own_hand,
                      observation.public.own_elixir or 0., observation.public.own_next_card)
        # HUD bypasses the more expensive opponent belief update for the <=60ms
        # pre-tap check. Actuation sees RAW pixels-derived HUD, never optimistic HUD.
        put_latest(ipc['hud'], (frame.episode, frame.sequence, hud, time.monotonic()))
        # Latest body/HUD values are droppable; one-shot event candidates stay
        # in successive messages until P2 acknowledges consuming them.
        message = event_window.message(observation, ipc['observation_ack'].value)
        if put_latest(ipc['observations'], message):
            ipc['perception_last'].value = frame.sequence
            unpublished = None
        else:
            unpublished = message
            log('observation_publish_dropped', sequence=frame.sequence)
        log('perceived', sequence=frame.sequence, produced_at=frame.produced_at)


def p2(config, ipc, log):
    from .loading import actuator_module
    from .belief import Belief
    actuator_module()  # Feedback HUD pickle identity in this separate process.
    belief = Belief(config['belief'])
    ipc['ready'][2].set()
    if not await_start(ipc, 2):
        return
    last = -1
    fault_done = False
    while not ipc['stop'].is_set():
        ipc['heartbeat'][2] = time.monotonic()
        if config.get('blocking_queues', False):
            wait_queues([ipc['observations'], ipc['feedback']])
        controls(ipc, belief, log)
        observation = drain_latest(ipc['observations'])
        if observation is None:
            if ipc['perception_done'].is_set() and last >= ipc['perception_last'].value:
                ipc['belief_done'].set()
            if not config.get('blocking_queues', False):
                ipc['stop'].wait(.002)
            continue
        frame = observation.frame
        if frame.sequence <= last:
            raise ValueError('Noncausal perception sequence')
        log('perception_queue_age', (time.monotonic()-observation.completed_at)*1000,
            sequence=frame.sequence)
        fault = config.get('fault', {})
        if fault.get('stage') == 'P2' and not fault_done and frame.sequence >= fault.get('after', 10):
            fault_done = True
            log('injected_stall', seconds=fault['seconds'])
            ipc['stop'].wait(fault['seconds'])
        start = time.monotonic()
        latest = belief.update(observation)
        log('belief', (time.monotonic()-start)*1000, sequence=frame.sequence)
        if last >= 0 and frame.sequence > last+1:
            log('belief_frames_skipped', count=frame.sequence-last-1)
        last = frame.sequence
        ipc['observation_ack'].value = last
        put_latest(ipc['snapshots'], latest)
        log('processed', sequence=frame.sequence, produced_at=frame.produced_at,
            events=len(observation.events), history_resets=0,
            own_cycle_exact=latest.own['cycle_exact'], tick=latest.tick, public=asdict(latest.public),
            event_candidates=observation.events, own=latest.own, opponent=latest.opponent,
            roots=latest.roots, revision=latest.revision, pending=latest.pending,
            timestamp_ms=frame.timestamp_ms, phase=observation.phase)


def p3(config, ipc, log):
    import torch
    torch.set_num_threads(1)
    from .decision import RustPlanner, SyntheticPlanner, Triggers, command_for
    planner = (SyntheticPlanner if config['planner']['kind'] == 'synthetic' else RustPlanner)(config['planner'])
    triggers = Triggers()
    ipc['ready'][3].set()
    if not await_start(ipc, 3):
        planner.close()
        return
    sequence = -1
    command_id = 0
    fault_done = False
    try:
        while not ipc['stop'].is_set():
            ipc['heartbeat'][3] = time.monotonic()
            snapshot = drain_latest(ipc['snapshots'],
                                    timeout=.05 if config.get('blocking_queues', False) else None)
            if snapshot is None or snapshot.sequence <= sequence:
                if not config.get('blocking_queues', False):
                    ipc['stop'].wait(.003)
                continue
            sequence = snapshot.sequence
            now = time.monotonic()
            log('belief_queue_age', (now-snapshot.emitted_at)*1000, sequence=snapshot.sequence)
            if snapshot.revision != ipc['revision'].value:
                continue
            if now-snapshot.produced_at >= .4:
                log('stale_snapshot', age_ms=(now-snapshot.produced_at)*1000)
                continue
            if ipc['busy'].value:
                log('pending_blocked_frame', sequence=sequence,
                    affordable=any(c in config['belief']['costs'] and config['belief']['costs'][c] <= snapshot.own['elixir']
                                   for c in snapshot.own['hand']))
                continue
            reason = triggers.reason(snapshot, now)
            if reason is None:
                continue
            start = time.monotonic()
            action, diagnostic = planner.decide(snapshot, start+.2)
            fault = config.get('fault', {})
            if fault.get('stage') == 'P3' and not fault_done and sequence >= fault.get('after', 10):
                fault_done = True
                ipc['stop'].wait(fault['seconds'])
            finished = time.monotonic()
            log('search', (finished-start)*1000, sequence=sequence, trigger=reason,
                deadline_overrun=finished-start > .2, diagnostic=diagnostic)
            command_id += 1
            command = command_for(action, snapshot, command_id, config['belief']['costs'], finished)
            if command is None:
                continue
            if finished > command.expires_at:
                log('expired_decision', command_id=command_id)
                continue
            with ipc['busy'].get_lock():
                if ipc['busy'].value:
                    continue
                ipc['busy'].value = True
            try:
                ipc['commands'].put_nowait(command)
            except Full:
                # Impossible under the outstanding-command token: fail closed.
                raise RuntimeError('Command queue full while token was free')
            log('command', command_id=command_id, sequence=sequence, revision=command.revision)
    finally:
        planner.close()


def p4(config, ipc, log):
    from .actuation import Actuation, input_channel
    actor = Actuation(input_channel(config['actuator']),
                      backend=config['actuator']['backend'], timing_path=config['actuator']['timing_path'])
    hud_reader = None
    if config['perception']['kind'] == 'v3':
        # The legacy placeholder has a separate lightweight HUD reader. P4's
        # pre-tap check reads the latest capture while P1 processes bodies.
        # V4 uses the shared-backbone HUD published by P1.
        import cv2
        from clasher.vision.l1_hud_v3 import StreamHudReader
        cv2.setNumThreads(1)
        hud_reader = StreamHudReader(config['perception']['hud'])
    hud_sequence = -1
    direct_hud = None
    ipc['ready'][4].set()
    if not await_start(ipc, 4):
        actor.channel.close()
        return
    latest = None
    waiting = None
    def publish(feedback):
        # A lost reservation/result is a safety fault, never a droppable message.
        ipc['feedback'].put(feedback, timeout=.2)
        log('actuator_state', command_id=feedback.command_id, state=feedback.state,
            revision=feedback.revision, pending=feedback.pending, detail=feedback.detail)
    def execute(result):
        if result and result['state'] == 'tap':
            transport = actor.execute(result)
            completed = time.monotonic()
            log('taps', transport['transport_ms'], command_id=actor.command.command_id,
                attempt=result['attempt'], **{k: v for k, v in transport.items() if k != 'transport_ms'})
            if result['attempt'] == 1 and not transport['ambiguous']:
                log('frame_to_tap', (completed-actor.command.produced_at)*1000,
                    command_id=actor.command.command_id, frame_sequence=actor.command.frame_sequence,
                    submitted_at=completed, ambiguous=transport['ambiguous'])
    try:
        while not ipc['stop'].is_set():
            ipc['heartbeat'][4] = time.monotonic()
            latest = drain_latest(ipc['hud'], latest)
            hud = latest[2] if latest else None
            if hud_reader and ipc['ring'].latest.value > hud_sequence:
                frame, seq, _ = ipc['ring'].read(ipc['ring'].latest.value-1, config['source']['episode'])
                if frame is not None:
                    hud_sequence = seq
                    begin = time.monotonic()
                    raw = hud_reader.read(frame.pixels)
                    direct_hud = actor.api.Hud(frame.produced_at, tuple(raw['hand']), raw['elixir'], raw['next_card'])
                    log('actuator_hud', (time.monotonic()-begin)*1000, sequence=seq)
            if direct_hud and (hud is None or direct_hud.produced_at > hud.produced_at):
                hud = direct_hud
            now = time.monotonic()
            feedback, result = actor.observe(hud, now)
            if feedback:
                publish(feedback)
                execute(result)
            if waiting is None:
                try:
                    waiting = ipc['commands'].get_nowait()
                except Empty:
                    pass
            if waiting is not None:
                # Wait for the next fresh HUD rather than rejecting merely
                # because search consumed time. Command's original expiry stays.
                fresh = hud is not None and 0 <= now-hud.produced_at <= .060
                if fresh or now > waiting.expires_at:
                    if latest and latest[0] != waiting.episode:
                        raise ValueError('Cross-episode command')
                    feedback, result = actor.submit(waiting, hud, now)
                    if feedback:
                        publish(feedback)
                    else:
                        log('duplicate_blocked', command_id=waiting.command_id, detail=result)
                    execute(result)
                    waiting = None
            if config.get('blocking_queues', False):
                # Active verification retains its bounded timer checks. Idle
                # commands/HUD wake immediately on either queue's pipe.
                # A direct v3 HUD reader also needs periodic ring refreshes.
                timeout = .002 if actor.machine.pending or waiting is not None else .05
                if hud_reader:
                    timeout = min(timeout, .01)
                wait_queues([ipc['hud'], ipc['commands']], timeout)
            else:
                ipc['stop'].wait(.002)
    finally:
        if actor.machine.pending:
            log('shutdown_pending', pending=actor.pending())
        actor.channel.close()


def worker(index, config, ipc):
    limits()
    stage = f'P{index}'
    log = Reporter(ipc['logs'], ipc['log_drops'], stage)
    try:
        (p0, p1, p2, p3, p4)[index](config, ipc, log)
    except BaseException as error:
        log('fatal', error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
        ipc['stop'].set()
        raise
    finally:
        ipc['finished'][index].set()


def quantiles(values):
    if not values:
        return {'count': 0, 'p50': None, 'p95': None, 'p99': None}
    values = sorted(values)
    def percentile(p):
        index = (len(values)-1)*p
        lo = int(index)
        hi = min(len(values)-1, lo+1)
        return values[lo]+(values[hi]-values[lo])*(index-lo)
    return dict(count=len(values), p50=percentile(.5), p95=percentile(.95), p99=percentile(.99))


def summarize(rows, config, failures, log_drops):
    from collections import Counter, defaultdict
    metrics = defaultdict(list)
    counts = Counter()
    for row in rows:
        counts[row['metric']] += 1
        if 'ms' in row:
            metrics[row['metric']].append(row['ms'])
    timing = {name: quantiles(values) for name, values in metrics.items()}
    e2e = timing.get('frame_to_tap', quantiles([]))
    verdict = bool(e2e['count'] and e2e['p50'] <= 200 and e2e['p99'] <= 400)
    captured = counts['captured']
    processed = [r for r in rows if r['metric'] == 'processed']
    elapsed = (max(r['produced_at'] for r in processed)-min(r['produced_at'] for r in processed)
               if len(processed) > 1 else 0.)
    return dict(schema='clasher.live-v4.runtime.v1', host=os.uname().nodename,
                source=config['source']['kind'], perception=config['perception']['kind'],
                planner=config['planner']['kind'], actuator=config['actuator']['kind'],
                perception_variant=('v3-body-hud-only' if config['perception']['kind'] == 'v3' and not config['perception'].get('events') else config['perception']['kind']),
                timing_ms=timing, counts=dict(counts), captured=captured, processed=len(processed),
                processed_fraction=len(processed)/max(1, captured),
                processed_fps=(len(processed)-1)/elapsed if elapsed else 0.,
                dropped_frames=sum(r.get('count', 0) for r in rows if r['metric'] == 'dropped'),
                history_resets=sum(r.get('history_resets', 0) for r in processed),
                search_overruns=sum(r.get('deadline_overrun', False) for r in rows if r['metric'] == 'search'),
                stage_budget_pass={name: stats['p50'] <= BUDGETS[name][0] and stats['p95'] <= BUDGETS[name][1]
                                   for name, stats in timing.items() if name in BUDGETS},
                end_to_end_budget_pass=verdict, failures=failures, log_drops=log_drops,
                production_qualified=False,
                limitations=['mock taps do not influence recorded video',
                             'T2 verifier sensitivity failed; v4 formal weights and runtime latency qualification pending'])


def provenance(config):
    from importlib.metadata import version, PackageNotFoundError
    from .capture import sha256
    from .loading import COUNCIL, ROOT, V4
    files = list(Path(__file__).parent.glob('*.py'))
    files += list(Path(__file__).parent.glob('*.rs'))
    from .lattice import LIBRARY, _kernel
    if _kernel is not None:
        files.append(LIBRARY)
    files += [V4/'actuator.py', V4/'input_channel.py', V4/'actuation/backend-timing.json',
              ROOT/'src/clasher/vision/l1_v4.py', Path(config['belief']['prior'])]
    files += [COUNCIL/'search-noise-s4'/name for name in
              ('tracker_v3.py', 'tracker_v2.py', 'derived_d1.py', 'elt.py', 'noise-model.json', 'calibration.json')]
    files += [COUNCIL/'search-noise-s6'/name for name in ('delay.py', 'own_state.py')]
    if config['planner'].get('timing_path'):
        files.append(Path(config['planner']['timing_path']))
    if config['perception'].get('vectorized_decoder'):
        files += [V4/'l1'/name for name in ('decoder_records_v4.py', 'vectorized_decoder_v4.py',
                                          'vectorized_runtime_adapter_v4.py')]
    files += [Path(config['perception'][key]) for key in
              ('body', 'hud', 'events', 'selection', 'geometry', 'checkpoint', 'calibration')
              if config['perception'].get(key)]
    native = list((ROOT/'engine-rs').glob('clasher_core*.so'))
    files += native
    versions = {}
    for name in ('torch', 'numpy', 'opencv-python', 'ultralytics'):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            pass
    return dict(host=os.uname().nodename, cpu=os.uname().machine, nice=os.getpriority(os.PRIO_PROCESS, 0),
                packages=versions, hashes={str(p): sha256(p) for p in files},
                source_split=config['source'].get('split'), captured_at_epoch=time.time(),
                backend=config['source'].get('render_backend'), heldout_opened=False)


def configure_timing(config):
    """Reject conflicting selectors before any worker starts."""
    from .timing import backend_timing
    selected = {}
    for key in ('backend', 'timing_path'):
        values = {str(part[key]) for part in (config, config['planner'], config['actuator'])
                  if part.get(key) is not None}
        if len(values) > 1:
            raise ValueError(f'P3/P4 disagree on {key}')
        if values:
            selected[key] = values.pop()
    backend, path, _, _ = backend_timing(selected)
    shared = dict(backend=backend, timing_path=str(path))
    return dict(config, planner=dict(config['planner'], **shared),
                actuator=dict(config['actuator'], **shared))


def run(config, output):
    """P5 owns children, bounded logging, stall detection, and shutdown."""
    config = configure_timing(config)
    limits()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    (output/'provenance.json').write_text(json.dumps(provenance(config), indent=2)+'\n')
    ctx = mp.get_context('spawn')
    ipc = dict(ring=FrameRing(ctx, config.get('ring_capacity', 64)),
               observations=ctx.Queue(2), observation_ack=ctx.RawValue('q', -1),
               perception_last=ctx.RawValue('q', -1), snapshots=ctx.Queue(2), hud=ctx.Queue(2), commands=ctx.Queue(1), feedback=ctx.Queue(8),
               logs=ctx.Queue(2048), log_drops=ctx.Value('q', 0), busy=ctx.Value('b', False), revision=ctx.Value('q', 0),
               stop=ctx.Event(), start=ctx.Event(), capture_done=ctx.Event(), perception_done=ctx.Event(), belief_done=ctx.Event(),
               ready=[ctx.Event() for _ in range(5)], finished=[ctx.Event() for _ in range(5)],
               heartbeat=ctx.RawArray('d', [time.monotonic()]*5))
    import signal
    previous_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in previous_handlers:
        signal.signal(sig, lambda signum, frame: ipc['stop'].set())
    children = [ctx.Process(target=worker, args=(i, config, ipc), name=f'clasher-P{i}') for i in range(5)]
    rows, failures = [], []
    drain_start = None
    started = False
    deadline = time.monotonic()+config.get('startup_timeout', 180)
    wall_deadline = deadline+config.get('max_seconds', 900)
    with gzip.open(output/'latency.jsonl.gz', 'wt') as stream:
        def record(row):
            rows.append(row)
            stream.write(json.dumps(row, default=str)+'\n')
        def drain():
            while True:
                try:
                    record(ipc['logs'].get_nowait())
                except Empty:
                    break
        for child in children:
            child.start()
        (output/'pids.json').write_text(json.dumps({p.name: p.pid for p in children}, indent=2)+'\n')
        try:
            while True:
                drain()
                now = time.monotonic()
                if not started and all(event.is_set() for event in ipc['ready']):
                    started = True
                    # The last initializer can set ready before its first idle
                    # heartbeat. Runtime stall clocks start at this barrier.
                    for i in range(5):
                        ipc['heartbeat'][i] = now
                    ipc['start'].set()
                    record(dict(stage='P5', metric='ready', emitted_at=now))
                if not started and now > deadline:
                    failures.append('startup timeout')
                    break
                bad = [p for p in children if p.exitcode not in (None, 0)]
                if bad:
                    failures.extend(f'{p.name} exited {p.exitcode}' for p in bad)
                    break
                if started:
                    stalls = [f'P{i}' for i in range(5) if not ipc['finished'][i].is_set()
                              and now-ipc['heartbeat'][i] > config.get('stall_timeout', 5.)]
                    if stalls:
                        failures.append('stage stall: '+', '.join(stalls))
                        break
                if ipc['belief_done'].is_set():
                    drain_start = now if drain_start is None else drain_start
                    if (not ipc['busy'].value and now-drain_start > .5) or now-drain_start > 5:
                        break
                if now > wall_deadline:
                    failures.append('run time limit')
                    break
                if ipc['stop'].is_set():
                    failures.append('worker requested stop')
                    break
                time.sleep(.01)
        finally:
            ipc['stop'].set()
            until = time.monotonic()+6
            while any(p.is_alive() for p in children) and time.monotonic() < until:
                drain()
                for p in children:
                    p.join(timeout=.01)
            for p in children:
                if p.is_alive():
                    failures.append(f'terminated owned {p.name} pid {p.pid}')
                    p.terminate()
                    p.join(timeout=2)
                    if p.is_alive():
                        p.kill()
                        p.join(timeout=2)
            drain()
            for name in ('observations', 'snapshots', 'hud', 'commands', 'feedback', 'logs'):
                ipc[name].cancel_join_thread()
                ipc[name].close()
    for sig, handler in previous_handlers.items():
        signal.signal(sig, handler)
    result = summarize(rows, config, failures, ipc['log_drops'].value)
    (output/'metrics.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
