"""Mac-only replay measurement. No actuator, emulator controller or network API.

The decision timer covers RustPlanner.decide + command_for + an in-memory sink.
A separate paced replay process supplies real capture/decode/perception load.
Full frame-service timings are separate; neither is formal T9/E4 acceptance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from receipt_logic import (canonical, complete_reduction, perception_gate, quantiles, sha,
    summarize_decisions, verify_pins, without_availability, write_new)

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[4]
CONFIG = PACKAGE / 'configs'
COUNCIL = ROOT / 'reports/strategy_council_20260928'


def mac_only():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('Mac measurements require macOS/arm64; Linux logic tests are separate')


def verify_sources():
    pins = json.loads((CONFIG / 'source-pins.json').read_text())
    verify_pins(ROOT, pins['files'])
    verify_pins(PACKAGE, json.loads((CONFIG / 'package-pins.json').read_text())['files'])
    return pins


def environment():
    import importlib.metadata
    import torch
    import cv2
    return dict(host=platform.node(), platform=sys.platform, architecture=platform.machine(),
        python=sys.version, python_executable=sys.executable, torch=str(torch.__version__),
        packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions() if d.metadata['Name']},
        opencv=cv2.__version__, mps_available=torch.backends.mps.is_available(),
        nice=os.getpriority(os.PRIO_PROCESS, 0),
        threads={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
            'VECLIB_MAXIMUM_THREADS', 'RAYON_NUM_THREADS')})


def setup(native_dir):
    os.environ['CLASHER_ROOT'] = str(ROOT)
    os.environ['CLASHER_EVAL_RUNTIME_ROOT'] = str(ROOT)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS', 'RAYON_NUM_THREADS'):
        os.environ[key] = '1'
    # Import the versioned binary first: research imports may prepend engine-rs.
    sys.path[:0] = [str(native_dir), str(ROOT / 'src'), str(ROOT), str(ROOT / 'engine-rs'),
        str(COUNCIL / 'engine-speed/stage5'), str(COUNCIL / 'engine-speed'),
        str(COUNCIL / 'c56/engine/root-v3'), str(COUNCIL / 'imitation')]
    import clasher_core
    if Path(clasher_core.__file__).resolve().parent != Path(native_dir).resolve():
        raise ValueError('Wrong native library imported')
    if not hasattr(clasher_core.NativeScripts, 'score_wait_screen8'):
        raise ValueError('W-screen8 native entrypoint missing')
    import torch
    import cv2
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    cv2.setNumThreads(1)
    return clasher_core


def selection(args):
    # Launcher pin comes from Sam's independent deployment review, not the seal.
    if sha(args.owner_launcher) != args.owner_launcher_sha256:
        raise ValueError('Independent owner launcher SHA mismatch')
    spec = importlib.util.spec_from_file_location('mac_e4_trusted_owner_launcher', args.owner_launcher)
    launcher = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = launcher
    spec.loader.exec_module(launcher)
    value = launcher.load_selection(Path(args.selection))
    from clasher.live.selection import AuthenticatedSelection
    if type(value) is not AuthenticatedSelection:
        raise ValueError('Owner launcher must return authenticated final joint selection')
    value.check_sources()
    if sha(args.owner_launcher) != args.owner_launcher_sha256:
        raise ValueError('Owner launcher changed during authentication')
    return value


def sensor_config(args, authenticated, vectorized=False):
    return dict(checkpoint=str(args.checkpoint), authenticated_selection=authenticated,
        device=args.device, vectorized_decoder=vectorized, decoder_diagnostic=True)


def timed(device, fn):
    import torch
    if device == 'mps':
        torch.mps.synchronize()
    start = time.perf_counter_ns()
    value = fn()
    if device == 'mps':
        torch.mps.synchronize()
    return value, (time.perf_counter_ns() - start) / 1e6


def frames_unpaced(source, limit):
    """Decode chronological sanitized pixels; recorded spacing is model time only.

    Foreground service time starts at actual video.read, not old capture clocks.
    Paced capture-age/load evidence comes from the independent load process.
    """
    import cv2
    from clasher.live.capture import sanitize
    from clasher.live.contracts import Frame
    video = cv2.VideoCapture(source['video'])
    if not video.isOpened():
        raise ValueError('Cannot open admitted recording')
    if hasattr(cv2, 'CAP_PROP_N_THREADS'):
        video.set(cv2.CAP_PROP_N_THREADS, 1)
    rows = source['rows'][:limit]
    first = rows[0]['produced_mono']
    try:
        for row in rows:
            produced = time.monotonic()
            ok, image = video.read()
            if not ok:
                raise ValueError('Video shorter than admitted timing ledger')
            pixels = sanitize(image)
            yield Frame(source['episode'], row['seq'], produced, time.monotonic(),
                (row['produced_mono'] - first) * 1000, pixels)
    finally:
        video.release()


def capture_outputs(sensor):
    model = sensor.sensor.model
    encode, forward = model.encode, model.temporal.forward
    def encoded(*a, **kw):
        value = encode(*a, **kw)
        sensor.raw_body = value
        return value
    def temporal(*a, **kw):
        value = forward(*a, **kw)
        sensor.raw_event = value
        return value
    model.encode, model.temporal.forward = encoded, temporal


def comparable(sensor, observation):
    from clasher.vision.l1_v4 import decode_bodies
    from clasher.live.loading import module
    records = module('mac_e4_decoder_records', COUNCIL / 'live-loop/v4/l1/decoder_records_v4.py')
    if sensor.decoder_adapter is None:
        bodies = decode_bodies(sensor.raw_body, sensor.sensor.bodies, .1)
        events = records.extract_event_records(sensor.raw_event, sensor.sensor.cards, observation.frame.timestamp_ms)
    else:
        bodies = sensor.decoder_adapter.bodies(sensor.raw_body, sensor.sensor.bodies, .1)
        events = sensor.decoder_adapter.events(sensor.raw_event, sensor.sensor.cards, observation.frame.timestamp_ms)
    return canonical(without_availability(dict(public=asdict(observation.public),
        phase=observation.phase, events=list(observation.events), decoder_bodies=bodies,
        decoder_events=events)))


def fallback_d1(snapshot, builder, own_deck, history=()):
    """Observed public-event histories, unknown cycle, labelled elixir prior.

    These are serving latency inputs, not exact gate-(b)/(c) oracle sidecars.
    Never mark inferred elixir/cycle as observed exact or read an opponent deck.
    """
    import numpy as np
    token = lambda name: 0 if not name else builder.token_id(name, namespace='card_action')
    z = lambda n: np.zeros(n, np.int16)
    observed = {}
    for label, side in (('opp', 0), ('own', 1)):
        ids, features = z(8), np.zeros((8, 3), np.float32)
        for i, event in enumerate([e for e in history if e['side'] == side][-8:][::-1]):
            ids[i] = token(event['card'])
            features[i] = [min(1., max(0, snapshot.tick-event['tick'])/1200),
                (18-event['x'])/18, (32-event['y'])/32]
        observed[label] = ids, features
    return dict(own_deck=np.array([token(c) for c in own_deck], np.int16),
        own_queue=np.array([token(c) for c in snapshot.own['cycle']], np.int16),
        own_refill_remaining=np.int16(snapshot.own['refill']),
        opp_elixir=np.float32(snapshot.roots[0]['elixir']), elixir_exact=np.bool_(False),
        opp_refill_remaining=np.int16(0), opp_hand_known=z(4), opp_next_card=np.int16(0),
        opp_queue=z(4), opp_cards_revealed=np.int8(len({e['card'] for e in history if e['side'] == 0})),
        own_recent_play_ids=observed['own'][0], own_recent_play_features=observed['own'][1],
        opp_recent_play_ids=observed['opp'][0], opp_recent_play_features=observed['opp'][1],
        opp_ability_ids=z(8), opp_ability_ages=np.zeros(8, np.float32))


def load_worker(args, sources, ready, stop, output):
    try:
        setup(args.native_dir)
        from clasher.live.capture import replay_frames
        from clasher.live.perception import V4Perception
        sensor = V4Perception(sensor_config(args, selection(args)))
        count = 0
        with Path(output).open('x') as stream:
            lap = 0
            while not stop.is_set():
                for source in sources:
                    def log(metric, ms=None, **kw):
                        stream.write(canonical(dict(metric=metric, ms=ms, **kw)) + '\n')
                    for frame in replay_frames(source, stop, log, args.frames_per_match):
                        frame = replace(frame, episode=frame.episode + '-load-' + str(lap))
                        _, ms = timed(args.device, lambda: sensor.step(frame))
                        stream.write(canonical(dict(metric='perception', ms=ms,
                            wall=time.monotonic(), episode=frame.episode, sequence=frame.sequence)) + '\n')
                        count += 1
                        if count >= 16:
                            stream.flush()
                            ready.set()
                lap += 1
    except BaseException:
        Path(str(output) + '.error.txt').write_text(traceback.format_exc())
        raise
    finally:
        stop.set()


def row_snapshot(row):
    from clasher.live.contracts import Snapshot
    from clasher.rl.live_inference_contract import parse_public_vision_frame, LIVE_VISION_SCHEMA_VERSION
    public = dict(row['public'])
    outer = {k: public.pop(k) for k in ('episode_id', 'frame_id', 'timestamp_ms')}
    frame = parse_public_vision_frame(dict(outer, schema_version=LIVE_VISION_SCHEMA_VERSION, public=public))
    now = time.monotonic()
    return Snapshot(row['episode'], row['sequence'], now, now, now, row['tick'], frame,
        row['own'], tuple(row['roots']), row['opponent'], row['revision'], None, 0, 0)


def new_planner(arm, args):
    from clasher.live.decision import RustPlanner
    config = dict(arm['planner'], timing_path=str(CONFIG / 'timing.json'),
        wait_screen8_native_dir=str(args.native_dir))
    start = time.perf_counter()
    planner = RustPlanner(config)
    planner.pool.shutdown(wait=True)
    planner.pool = ThreadPoolExecutor(max_workers=arm['root_threads'], thread_name_prefix='mac-e4-root')
    original_score = planner.score
    planner.measurement_root_scores = [None] * 4
    def recorded_score(core, *a, **kw):
        if getattr(planner, 'measurement_no_deadline', False) and planner.wait_screen8:
            # The W native API rejects infinite budgets. None is its actual
            # no-deadline path; retain the same candidate/scorer semantics.
            root, info, candidates, _deadline = a
            core.info, core.costs = info, planner.resources.costs
            core.wait_own_elixir = float(info.packet.observation.global_features[5]) * 10
            core.score_candidates(root, info.seat, candidates, deadline=None)
            values = core.last['scores']
        else:
            values = original_score(core, *a, **kw)
        planner.measurement_root_scores[next(i for i, c in enumerate(planner.cores) if c is core)] = list(values)
        return values
    planner.score = recorded_score
    return planner, (time.perf_counter() - start) * 1000


def belief_config(args, source):
    from clasher.live.__main__ import public_metadata
    costs, bodies = public_metadata(args.prior)
    return dict(own_deck=source['own_deck'], costs=costs, body_cards=bodies,
        prior=str(args.prior), seed=6108, recall=.90, precision=.90,
        resource_calibration=.11040000000000028)


def prepare(args, sources, authenticated):
    import numpy as np
    import torch
    from clasher.live.perception import V4Perception
    from clasher.live.tower_channel import TowerChannel
    from clasher.live.belief import Belief
    from clasher.live.decision import DecisionInfo
    from imitation.model import load_policy
    from imitation.evaluation.d1 import model_packet
    arm = json.loads((CONFIG / 'w0-t4.json').read_text())
    planner, planner_init = new_planner(arm, args)
    init = {}
    sensors = {}
    for label in ('scalar', 'vectorized'):
        start = time.perf_counter()
        sensors[label] = V4Perception(sensor_config(args, authenticated, label == 'vectorized'))
        init[label] = (time.perf_counter() - start) * 1000
        capture_outputs(sensors[label])
    policy_start = time.perf_counter()
    policy = load_policy(args.fallback)
    policy.model.temperatures.fill_(1.)
    init['v1_policy'] = (time.perf_counter() - policy_start) * 1000
    generator = torch.Generator(device='cpu').manual_seed(6108)
    tower = TowerChannel()
    cohort, perception, towers, fallback, mismatches, exclusions = [], [], [], [], [], []
    try:
        with (args.output / 'perception.jsonl').open('x') as pfile, (args.output / 'fallback.jsonl').open('x') as ffile:
            for source in sources:
                belief = Belief(belief_config(args, source))
                history, seen_events = [], set()
                for index, frame in enumerate(frames_unpaced(source, args.frames_per_match)):
                    observations, payloads = {}, {}
                    # AB/BA alternation: model outputs also synchronize before timers end.
                    order = ('scalar', 'vectorized') if index % 2 == 0 else ('vectorized', 'scalar')
                    for label in order:
                        observation, ms = timed(args.device, lambda: sensors[label].step(frame))
                        observations[label] = observation
                        record = dict(arm=label, episode=frame.episode, sequence=frame.sequence,
                            cold=index < 16, perception_ms=ms, tower_ms=observation.timings['tower_channel'],
                            parts=observation.timings)
                        perception.append(record)
                        pfile.write(canonical(record) + '\n')
                        payloads[label] = comparable(sensors[label], observation)
                    if payloads['scalar'] != payloads['vectorized']:
                        mismatches.append(dict(episode=frame.episode, sequence=frame.sequence,
                            scalar=payloads['scalar'], vectorized=payloads['vectorized']))
                    _, tower_ms = timed('cpu', lambda: tower.step(frame.pixels, frame.episode, frame.timestamp_ms))
                    towers.append(dict(episode=frame.episode, sequence=frame.sequence, cold=index < 16, ms=tower_ms))
                    snapshot, belief_ms = timed('cpu', lambda: belief.update(observations['scalar']))
                    for event in observations['scalar'].events:
                        event_id = canonical(event.get('event_id', [event['card'], event['side'], event['execution_timestamp_ms']]))
                        if event_id in seen_events or event['card'] not in belief.costs:
                            continue
                        seen_events.add(event_id)
                        history.append(dict(card=event['card'], side=event['side'],
                            tick=max(0, snapshot.tick-max(0, round((frame.timestamp_ms-event['execution_timestamp_ms'])/50))),
                            x=event['x_tiles'], y=event['y_tiles']))
                    packet, _ = planner.packets.build(snapshot.public, snapshot.tick)
                    packet = planner.model_hypothesis(packet)
                    planner.cores[0].rng = np.random.default_rng(6108 + frame.sequence)
                    candidates, mask = planner.cores[0].candidates(packet)
                    if packet.observation.terminal or len(candidates) < 2:
                        exclusions.append(dict(episode=frame.episode, sequence=frame.sequence,
                            reason='terminal' if packet.observation.terminal else 'no_search'))
                        continue
                    info = DecisionInfo(snapshot.tick, 1, packet,
                        {k: snapshot.own[k] for k in ('hand', 'cycle', 'refill', 'elixir')})
                    terminal = []
                    for hypothesis in snapshot.roots:
                        root = planner.resources.root(info, hypothesis, np.random.default_rng(6108))
                        root.step(1)
                        terminal.append(json.loads(root.snapshot())['game_over'])
                    if any(terminal):
                        exclusions.append(dict(episode=frame.episode, sequence=frame.sequence,
                            reason='one_tick_terminal', terminal_roots=terminal))
                        continue
                    d1 = fallback_d1(snapshot, planner.resources.builder, source['own_deck'], history)
                    public_packet = model_packet(packet, mask)
                    proposals, proposal_ms = timed('cpu', lambda: policy.propose(public_packet, d1, k=8))
                    action, sample_ms = timed('cpu', lambda: policy.sample(public_packet, d1, generator))
                    if any(not mask[p['action']] for p in proposals) or not mask[action]:
                        raise ValueError('Illegal v1 output on public serving row')
                    frecord = dict(episode=frame.episode, sequence=frame.sequence, cold=index < 16,
                        proposal_ms=proposal_ms, sample_ms=sample_ms, proposals=proposals, action=action,
                        d1_scope='observed public history/unknown cycle/public-root-prior; elixir_exact=False; T=1; CPU-one-thread')
                    fallback.append(frecord)
                    ffile.write(canonical(frecord) + '\n')
                    cohort.append(dict(packet_id=frame.episode + ':' + str(frame.sequence),
                        episode=frame.episode, sequence=frame.sequence, tick=snapshot.tick,
                        public=asdict(snapshot.public), own=snapshot.own, roots=list(snapshot.roots),
                        opponent=snapshot.opponent, revision=snapshot.revision,
                        public_event_history=list(history),
                        frame_services=dict(decode_ms=(frame.received_at-frame.produced_at)*1000,
                            perception_ms=next(r['perception_ms'] for r in perception[-2:] if r['arm'] == 'scalar'),
                            belief_ms=belief_ms), nonterminal=True))
        write_new(args.output / 'cohort.json', dict(split='train', heldout_opened=False,
            packets=cohort, exclusions=exclusions))
        write_new(args.output / 'decoder-comparison.json', dict(formal_admitted=False,
            scope='Mac public-train replay; availability excluded; all non-clock raw/fused records compared',
            frames=len(perception)//2, mismatches=mismatches,
            exactness_gate='PASS' if not mismatches else 'FAIL', startup_ms=init,
            perception=perception_gate(perception),
            tower_six_slot_ms=quantiles([r['ms'] for r in towers if not r['cold']]),
            towers=towers, planner_startup_ms=planner_init,
            fallback_proposal_ms=quantiles([r['proposal_ms'] for r in fallback if not r['cold']]),
            fallback_sample_ms=quantiles([r['sample_ms'] for r in fallback if not r['cold']]),
            fallback_cold_proposal_ms=quantiles([r['proposal_ms'] for r in fallback if r['cold']]),
            fallback_p99_15ms_target=(quantiles([r['proposal_ms'] for r in fallback if not r['cold']])['p99'] or float('inf')) <= 15))
        return cohort
    finally:
        planner.close()


def decision_inputs(args, selected, sources, mode):
    if mode == 'exact':
        for row in selected:
            yield row, row_snapshot(row), None
        return
    from clasher.live.perception import V4Perception
    from clasher.live.belief import Belief
    sensor = V4Perception(sensor_config(args, selection(args)))
    by_id = {row['packet_id']: row for row in selected}
    for source in sources:
        belief = Belief(belief_config(args, source))
        for frame in frames_unpaced(source, args.frames_per_match):
            observation, _ = timed(args.device, lambda: sensor.step(frame))
            snapshot = belief.update(observation)
            row = by_id.get(frame.episode + ':' + str(frame.sequence))
            if row is not None:
                # Same public packets across all cells; no synthetic frame shortcut.
                if (canonical(without_availability(asdict(snapshot.public))) !=
                        canonical(without_availability(row['public'])) or
                        canonical(snapshot.own) != canonical(row['own']) or
                        canonical(snapshot.roots) != canonical(row['roots'])):
                    raise ValueError('Repeated scalar replay changed paired public input')
                yield row, snapshot, frame.produced_at


def loaded_fallback(args, cohort, sources):
    from imitation.model import load_policy
    from imitation.evaluation.d1 import model_packet
    from clasher.rl.public_action_mask import PublicActionMaskInput
    import torch
    policy = load_policy(args.fallback)
    policy.model.temperatures.fill_(1.)
    generator = torch.Generator(device='cpu').manual_seed(6108)
    planner, startup = new_planner(json.loads((CONFIG/'w0-t1.json').read_text()), args)
    decks = {s['episode']: s['own_deck'] for s in sources}
    rows = []
    try:
        with (args.output/'fallback-loaded.jsonl').open('x') as stream:
            for index, row in enumerate(cohort):
                snapshot = row_snapshot(row)
                packet, _ = planner.packets.build(snapshot.public, snapshot.tick)
                mask = planner.resources.bots['balanced'].mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(packet))
                packet = model_packet(planner.model_hypothesis(packet), mask)
                d1 = fallback_d1(snapshot, planner.resources.builder, decks[row['episode']], row['public_event_history'])
                proposals, proposal_ms = timed('cpu', lambda: policy.propose(packet, d1, k=8))
                action, sample_ms = timed('cpu', lambda: policy.sample(packet, d1, generator))
                if not mask[action] or any(not mask[p['action']] for p in proposals):
                    raise ValueError('Loaded fallback returned illegal public action')
                value = dict(packet_id=row['packet_id'], cold=index == 0,
                    proposal_ms=proposal_ms, sample_ms=sample_ms, action=action, proposals=proposals)
                rows.append(value)
                stream.write(canonical(value)+'\n')
        write_new(args.output/'fallback-loaded-summary.json', dict(
            cpu_threads=1, temperature=[1,1,1], proposer_k=8, startup_ms=startup,
            scope='real public packets/observed public-event histories/unknown cycle/elixir prior; capture/perception load concurrent',
            proposal_ms=quantiles([r['proposal_ms'] for r in rows]),
            sample_ms=quantiles([r['sample_ms'] for r in rows]),
            engineering_target_p99_ms=15,
            proposer_target='PASS' if quantiles([r['proposal_ms'] for r in rows])['p99'] <= 15 else 'FAIL'))
    finally:
        planner.close()


def cold_worker(args, arm, row, output):
    """One fresh-interpreter P3 sample; OS/file caches are uncontrolled."""
    mac_only()
    start = time.monotonic()
    setup(args.native_dir)
    planner, planner_ms = new_planner(arm, args)
    try:
        snapshot = row_snapshot(row)
        begin = time.monotonic()
        action, diagnostic = planner.decide(snapshot, begin+.2)
        ms = (time.monotonic()-begin)*1000
        write_new(output, dict(scope='fresh spawned interpreter/native/planner; OS caches uncontrolled; public recorded packet',
            packet_id=row['packet_id'], wait_screen8=arm['planner']['wait_screen8'],
            root_threads=arm['root_threads'], process_setup_ms=(begin-start)*1000,
            planner_initialization_ms=planner_ms, first_decision_ms=ms,
            action=action, diagnostic=diagnostic, root_scores=planner.measurement_root_scores,
            formal_E4_qualified=False))
    finally:
        planner.close()


def decisions(args, cohort, sources):
    import numpy as np
    from clasher.live.decision import command_for
    from clasher.rl.wait_screen8 import TIMED_WAITS
    if len(cohort) < 1000:
        raise ValueError('Need >=1000 unique eligible nonterminal public packets, not repeated 440 historical rows')
    # Round-robin the recordings before cutting the fixed paired cohort.
    groups = {s['episode']: [r for r in cohort if r['episode'] == s['episode']] for s in sources}
    cohort = []
    while any(groups.values()) and len(cohort) < 1000:
        for rows in groups.values():
            if rows and len(cohort) < 1000:
                cohort.append(rows.pop(0))
    write_new(args.output / 'paired-cohort.json', cohort)
    context = mp.get_context('spawn')
    ready, stop = context.Event(), context.Event()
    worker = context.Process(target=load_worker,
        args=(args, sources, ready, stop, args.output / 'loaded-replay.jsonl'))
    worker.start()
    measurements, startup = [], []
    try:
        if not ready.wait(120) or not worker.is_alive() or stop.is_set():
            raise ValueError('Real paced scalar perception/capture load did not start; preserve worker error')
        (args.output/'cold').mkdir()
        for path in sorted(CONFIG.glob('w*-t*.json')):
            child = context.Process(target=cold_worker,
                args=(args, json.loads(path.read_text()), cohort[0], args.output/'cold'/path.name))
            child.start()
            child.join(120)
            if child.is_alive():
                child.terminate()
                child.join(5)
            if child.exitcode != 0:
                raise ValueError('Fresh-process cold planner sample failed: '+path.stem)
        loaded_fallback(args, cohort, sources)
        with (args.output / 'decisions.jsonl').open('x') as stream:
            for mode in ('exact', 'deadline'):
                selected = cohort[:32] if mode == 'exact' else cohort
                # Reverse cell order between phases; run twice with reversed list
                # only if investigating drift, retaining both receipt directories.
                paths = sorted(CONFIG.glob('w*-t*.json'), reverse=mode == 'deadline')
                for path in paths:
                    arm = json.loads(path.read_text())
                    planner, init = new_planner(arm, args)
                    planner.measurement_no_deadline = mode == 'exact'
                    startup.append(dict(mode=mode, arm=path.stem, ms=init))
                    try:
                        for index, (row, snapshot, produced) in enumerate(decision_inputs(args, selected, sources, mode)):
                            if not worker.is_alive() or stop.is_set():
                                raise ValueError('Concurrent perception load failed during decision measurement')
                            # Independent public packets: suppress prior W cadence skip.
                            # Never change candidate lists, scorer, reducer or production source.
                            planner.wait_until_tick, planner.wait_episode = 0, None
                            seed = 6108 + index
                            planner.rng = np.random.default_rng(seed)
                            for core_index, core in enumerate(planner.cores):
                                core.rng = np.random.default_rng(seed + core_index)
                            planner.measurement_root_scores = [None] * 4
                            begin = time.monotonic()
                            action, diagnostic = planner.decide(snapshot,
                                begin + .2 if mode == 'deadline' else float('inf'))
                            command = command_for(action, snapshot, index, planner.resources.costs, time.monotonic())
                            # In-memory serialization is the only submission boundary.
                            sink = canonical(asdict(command)) if command is not None else None
                            ms = (time.monotonic() - begin) * 1000
                            ids = diagnostic.get('candidate_ids', [])
                            complete = diagnostic.get('completed', 0)
                            count = diagnostic.get('candidates', 0)
                            valid = (0 <= complete <= count and len(diagnostic.get('scores', [])) == complete
                                and (action in ids if complete else action == 2304))
                            matrix = planner.measurement_root_scores
                            if count > 1:
                                checked_action, checked_scores = complete_reduction(ids, matrix)
                                valid = valid and checked_action == action and checked_scores == diagnostic.get('scores', [])
                            record = dict(packet_id=row['packet_id'], mode=mode,
                                wait_screen8=arm['planner']['wait_screen8'], threads=arm['root_threads'],
                                decision_ms=ms, frame_to_mock_ms=(time.monotonic()-produced)*1000 if produced is not None else ms,
                                frame_service_scope='actual contiguous video decode/P1/P2/P3/mock service; paced replay load concurrent; no IPC/emulator transport',
                                cold=index == 0, nonterminal=row['nonterminal'], searched=count > 1,
                                cold_scope='first decision of fresh planner; shared process already warmed by preparation',
                                exact_full_budget=mode == 'exact',
                                action=action, candidates=count, completed=complete,
                                candidate_ids=ids, scores=diagnostic.get('scores', []), admission_valid=valid,
                                root_scores=matrix,
                                selected_wait_ticks=TIMED_WAITS.get(action, 0),
                                fallback_needed=complete == 0, fallback_policy_applied=False,
                                mock_submission=sink is not None, diagnostic=diagnostic)
                            measurements.append(record)
                            stream.write(canonical(record) + '\n')
                            stream.flush()
                    finally:
                        planner.close()
    finally:
        stop.set()
        worker.join(15)
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
        write_new(args.output / 'decision-partial-summary.json', dict(
            startup_ms=startup, load_exitcode=worker.exitcode,
            decisions=summarize_decisions(measurements)))
    if worker.exitcode != 0:
        raise ValueError('Capture/perception load worker failed')
    rows = [json.loads(line) for line in (args.output / 'loaded-replay.jsonl').read_text().splitlines()]
    load = [r for r in rows if r['metric'] == 'perception']
    elapsed = load[-1]['wall'] - load[0]['wall'] if len(load) > 1 else 0
    write_new(args.output / 'decision-summary.json', dict(
        startup_ms=startup, load_exitcode=worker.exitcode,
        load_processed=len(load), load_processed_fps=(len(load)-1)/elapsed if elapsed > 0 else 0,
        load_perception_ms=quantiles([r['ms'] for r in load]),
        loaded_capture_age_ms=quantiles([r['ms'] for r in rows if r['metric'] == 'capture']),
        decisions=summarize_decisions(measurements)))


def session(args):
    mac_only()
    if not args.sam_authorized_replay:
        raise ValueError('Future session requires Sam authorization for replay on the Mac')
    pins = verify_sources()
    inputs = {}
    for name in ('checkpoint', 'fallback', 'selection', 'owner_launcher', 'prior', 'split'):
        path, expected = getattr(args, name), getattr(args, name + '_sha256')
        if sha(path) != expected:
            raise ValueError('Input SHA mismatch: ' + name)
        inputs[name] = dict(path=str(Path(path).resolve()), sha256=expected)
    if args.fallback_sha256 != json.loads((CONFIG / 'measurement.json').read_text())['v1_checkpoint_sha256']:
        raise ValueError('Wrong released v1 fallback checkpoint')
    native = setup(args.native_dir)
    build = json.loads((args.native_dir / 'build.json').read_text())
    if (build['binary_sha256'] != sha(native.__file__) or build['target'] != 'aarch64-apple-darwin'
            or build['features'] != ['extension-module', 'gil-release']
            or build['source_pins_sha256'] != sha(CONFIG / 'source-pins.json')):
        raise ValueError('Build receipt/native source identity mismatch')
    from clasher.live.capture import admit_replay
    # Reject validation/heldout and mismatched media before sensor creation.
    sources = [admit_replay(path, args.split) for path in args.match]
    if len(sources) < 2 or len({s['episode'] for s in sources}) != len(sources):
        raise ValueError('At least two distinct admitted train recordings required')
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / 'session.json', dict(schema='clasher.mac-e4.measurement.v1',
        environment=environment(), inputs=inputs, source_revision=pins['source_revision'],
        source_pins_sha256=sha(CONFIG / 'source-pins.json'), package_pins_sha256=sha(CONFIG / 'package-pins.json'),
        native_sha256=sha(native.__file__), build_receipt_sha256=sha(args.native_dir / 'build.json'),
        device=args.device, sources=[{k: s[k] for k in ('episode', 'hashes', 'split_sha256', 'split')} for s in sources],
        frames_per_match=args.frames_per_match, formal_selection_changed=False, formal_decoder_admitted=False,
        live_taps=False, ladder=False, hidden_state_read=False, emulator_control=False))
    try:
        authenticated = selection(args)
        write_new(args.output / 'selection-provenance.json', authenticated.provenance())
        cohort = prepare(args, sources, authenticated)
        decisions(args, cohort, sources)
        # Bind final receipts to unchanged executable/config bytes too.
        verify_sources()
        for name, pin in inputs.items():
            if sha(pin['path']) != pin['sha256']:
                raise ValueError('Input changed during measurement: ' + name)
        decoder = json.loads((args.output / 'decoder-comparison.json').read_text())
        decision = json.loads((args.output / 'decision-summary.json').read_text())
        write_new(args.output / 'complete.json', dict(experiment_complete=True,
            formal_E4_qualified=False, formal_decoder_admitted=False,
            decision=decision['decisions']['package_decision_gate'], decoder_nonclock=decoder['exactness_gate'],
            perception_budget={k: v['budget_status'] for k, v in decoder['perception'].items()},
            all_receipt_sha256={str(p.relative_to(args.output)): sha(p)
                for p in sorted(args.output.rglob('*')) if p.is_file()}))
    except BaseException:
        write_new(args.output / 'failure.json', dict(experiment_complete=False, traceback=traceback.format_exc()))
        raise


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('verify-sources')
    build = sub.add_parser('build-receipt')
    build.add_argument('--native-dir', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('session')
    run.add_argument('--native-dir', type=Path, required=True)
    run.add_argument('--match', type=Path, action='append', required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--device', choices=('mps', 'cpu'), default='mps')
    run.add_argument('--frames-per-match', type=int, default=1500)
    run.add_argument('--sam-authorized-replay', action='store_true')
    for name in ('checkpoint', 'fallback', 'selection', 'owner-launcher', 'prior', 'split'):
        run.add_argument('--' + name, type=Path, required=True)
        run.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args()
    if args.operation == 'verify-sources':
        pins = verify_sources()
        print(canonical(dict(verified=True, source_revision=pins['source_revision'])))
    elif args.operation == 'build-receipt':
        mac_only()
        verify_sources()
        native = setup(args.native_dir)
        write_new(args.output, dict(target='aarch64-apple-darwin',
            features=['extension-module', 'gil-release'], binary_path=str(native.__file__),
            binary_sha256=sha(native.__file__), source_pins_sha256=sha(CONFIG / 'source-pins.json'),
            environment=environment(), rustc_sha256=sha(args.native_dir / 'rustc.txt'),
            cargo_log_sha256=sha(args.native_dir / 'cargo.log'),
            file_output=(args.native_dir / 'file.txt').read_text(),
            otool_output=(args.native_dir / 'otool.txt').read_text()))
    else:
        session(args)


if __name__ == '__main__':
    main()
