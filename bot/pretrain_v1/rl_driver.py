"""Registered rollout/league driver and bounded local-process transport.

The operational owner supplies frozen populations, banks and GO evidence. This
module never discovers a replacement checkpoint or resumes a stopped seed.
"""
from __future__ import annotations

from dataclasses import asdict
from contextlib import contextmanager
import json
import fcntl
import os
from pathlib import Path
import shutil
import resource
import subprocess
import signal
import struct
import sys
import threading
import time

from . import rl_schedule as S

GATES = ('producer_parity', 'hidden_state_mutation', 'real_levels', 'session_likelihood_kl',
         'cpu_gpu_parity', 'full_rollout_memory_queue', 'six_hour_32_actor_soak',
         'terminal_process_recycle', 'fresh_banks', 'independent_sol_high')
ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT/'bot/pretrain_v1/run_registered_rl.py'
GPU_CAP_BYTES = int(43.5*2**30)
QUALIFICATION_SECONDS = 6*60*60
QUALIFICATION_UPDATES = 128


class QualificationStop(RuntimeError):
    pass


def guard():
    memory = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines()
                      if l.startswith('MemAvailable:')))*1024
    S.require(os.getpriority(os.PRIO_PROCESS, 0) >= 10 and memory >= 32*2**30
              and os.getloadavg()[0] <= 90, 'own-host guard: nice>=10, MemAvailable>=32GiB, load<=90')
    S.require(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')),
              'all math thread environments must equal 1')
    return dict(mem_available_bytes=memory, load1=os.getloadavg()[0], nice=os.getpriority(os.PRIO_PROCESS, 0))


def source_digest():
    return S.digest({str(p.relative_to(ROOT)): S.file_sha(p)
                     for p in sorted((ROOT/'bot/pretrain_v1').rglob('*.py'))})


def module_origins(config):
    from .checks.check_ours_producer import check_origins
    check_origins(Path(config['runtime']).resolve(), Path(config['actor_source']).resolve())
    return {name: str(Path(module.__file__).resolve()) for name, module in list(sys.modules.items())
            if (name == 'bot' or name.startswith('bot.') or name == 'clasher' or name.startswith('clasher.'))
            and getattr(module, '__file__', None)}


def read_config(path):
    config = json.loads(Path(path).read_text())
    S.require(config['schema'] == 'pv1-rl-launch-v1', 'launch schema')
    S.require(config['size'] in S.ANCHORS and config['seed'] in S.SEEDS, 'unregistered arm')
    S.require(config['anchor']['sha256'] == S.ANCHORS[config['size']], 'selected next anchor required')
    S.require(config['precision'] in ('float32', 'float64'), 'explicit precision required')
    S.require(config['workers'] == 32 and config['chunk_rows'] == 128, 'registered topology is 32 processes, 128-row chunks')
    S.require(config['steps_per_update'] == 262144 and config['updates'] == 32
              and config['minibatch'] == 2048 and config['microbatch'] == 128, 'registered optimizer/budget')
    S.require(config['actor_threads'] == 1 and config['learner_threads'] == 1, 'math threads must equal 1')
    own = {'M': '127x01', 'S100': '127x02'}[config['size']]
    fallback = {'M': '127x09', 'S100': '127x12'}[config['size']]
    S.require(config['host'] == (fallback if config.get('qualification_only', False) else own),
              'registered M01/S02; explicit qualification-only fallback M09/S12')
    S.require(type(config['wait_seconds']) in (int, float) and 0 < config['wait_seconds'] <= 86400,
              'bounded operational timeout required')
    return config


def input_manifest(config):
    """Validate every frozen input, without constructing an engine or a model."""
    S.require(set(config['registration_documents']) == {'RL-DUAL-PREREG', 'RL-DESIGN',
              'RL-COORDINATOR-CONTRACT', 'RL-LEARNER-CONTRACT'}, 'complete scientific registration documents required')
    for ref in config['registration_documents'].values():
        S.pinned(ref)
    paths = {key: S.pinned(config[key]) for key in
             ('anchor', 'model_cfg', 'populations', 'evaluation_populations', 'banks', 'runtime_manifest', 'hp1_checkpoint')}
    S.require(config['hp1_checkpoint']['sha256'] == S.HP1_SHA, 'exact HP1 recovery04 v330 required')
    populations = S.validate_populations(json.loads(paths['populations'].read_text()))
    evaluation_populations = S.validate_populations(json.loads(paths['evaluation_populations'].read_text()))
    S.require(populations['role'] == 'training-only' and evaluation_populations['role'] == 'evaluation-only'
              and not set(populations['physical_source_ids']) & set(evaluation_populations['physical_source_ids']),
              'train/evaluation physical source overlap')
    for ref in populations['sources']:
        S.pinned(ref)
    banks = S.validate_banks(json.loads(paths['banks'].read_text()), config['seed'])
    S.require(banks['evaluation_populations'] == config['evaluation_populations'], 'evaluation population identity mismatch')
    profiles = {r['source_id']: r for rows in evaluation_populations['opponents'].values() for r in rows}
    for row in banks['primary']+banks['dev']['0']:
        profile = profiles[row['profile_source_id']]
        seat = 1-row['seat']
        S.require(set(row['decks'][seat]) == set(profile['deck'])
                  and row['levels']['cards'][str(seat)] == profile['cards']
                  and row['levels']['towers'][seat] == profile['tower'], 'bank profile/source mismatch')
    from .probe_roots import input_paths
    audit_files = json.loads(S.pinned(banks['audit_input_manifest']).read_text())
    S.require({str(S.pinned(ref)) for ref in audit_files} == {str(p.resolve()) for p in input_paths()},
              'audit manifest must cover exactly all actual root-evaluator input files')
    manifest = json.loads(paths['runtime_manifest'].read_text())
    S.require(len(manifest['files']) == 9409 and len(manifest['source_files']) == 17010,
              'complete frozen runtime/actor manifest required')
    for key, root_key in (('files', 'runtime'), ('source_files', 'actor_source')):
        S.require(S.digest(manifest[key]) == {'files': '380c8141ab1c3cc26ea9490869b0023be9e37481532cdbeda75817462410bd30',
                  'source_files': '43c20b2df9880af8634e1cd3efefb8ae369e3dad615af7f75bc830b59a9c6583'}[key],
                  'unapproved runtime/actor manifest')
        for name, sha in manifest[key].items():
            S.require(S.file_sha(Path(config[root_key])/name) == sha, f'mixed runtime: {name}')
    live = config['live']
    S.require(live['factory'] == 'make_opponent' and live['planner'] == 'l11'
              and live['spec'] == 'livesearch:LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-pt5-wint'
              and live['belief_spec'] == 'fullpool:11433651:freq=b53b02a1fde4',
              'exact frozen deployed LIVE identity required')
    S.require(live['fast_checkpoint']['sha256'] == '0c03f79ffe5aa19e2310f9a959c96c98eb98678fe4c1f10352f9eb9566b58736'
              and live['fast_calibration']['sha256'] == 'e805d498ae693c7d66ecbf5ae0d4749fc817e7abd7a1cb92effec6dcca6a4145'
              and live['fast_threshold'] == 0.6444047689437866, 'exact frozen LIVE fast tier required')
    S.pinned(config['live']['fast_checkpoint'])
    calibration = json.loads(S.pinned(live['fast_calibration']).read_text())
    S.require(calibration['threshold'] == live['fast_threshold'], 'LIVE fast calibration mismatch')
    for ref in config['live']['artifacts']:
        S.pinned(ref)
    S.require(not any(k in config['live']['environment'] for k in
              ('CLASHER_ROOT', 'CLASHER_BOT_RUNTIME', 'CLASHER_EVAL_RUNTIME_ROOT', 'CUDA_VISIBLE_DEVICES',
               'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'PYTHONPATH')),
              'live environment may not override runtime/device/thread pins')
    S.require(bool(config['live']['environment']) and bool(config['live']['artifacts']), 'complete live env/artifacts required')
    S.require(config['hp1_threshold'] == 0.019753086419753086, 'frozen v330 calibrated threshold required')
    model_cfg = json.loads(paths['model_cfg'].read_text())
    shape = {'M': (320, 6, 8, 1280), 'S100': (192, 4, 6, 576)}[config['size']]
    S.require(tuple(model_cfg[k] for k in ('d', 'layers', 'heads', 'ffn')) == shape
              and model_cfg['drop'] == 0. and (model_cfg['n_cards'], model_cfg['n_bodies']) == (124, 183),
              'exact selected model configuration required')
    catalog = json.loads((Path(__file__).parent/'catalog/catalog.json').read_text())
    S.require(set(populations['vocabulary']) <= {c['name'] for c in catalog['cards']}, 'private/unqualified card identity')
    S.require(config['scripts'] == ['scripted-pressure', 'scripted-defense'], 'registered simple scripts')
    return paths, populations, banks, manifest


def registration_identity(config):
    # Evidence references cannot hash themselves. Everything that controls a run
    # remains in this identity, including populations, banks, devices and dtype.
    return S.digest({k: v for k, v in config.items() if k not in
                     ('gate_receipt', 'qualification_gate_receipt', 'precision_registration', 'league_schedule_registration')})


def audit(config, *, verify_inputs=True, qualification=False):
    failures = []
    source, identity = source_digest(), registration_identity(config)
    if config.get('qualification_only', False) and not qualification:
        failures.append('placement: leased fallback admits qualification only')
    if not qualification:
        try:
            league = json.loads(S.pinned(config['league_schedule_registration']).read_text())
            S.require(league['status'] == 'GO' and league['source_sha256'] == source
                      and league['config_sha256'] == identity
                      and league['protocol'] == 'paired-case-draws-game-start-version-v1'
                      and league['amends_exact_cross_size_snapshot_indices'] is True,
                      'game-start snapshot versions need an explicit prereg amendment; exact matching is not implemented')
        except Exception as ex:
            failures.append('paired league registration: '+str(ex))
    if verify_inputs:
        try:
            input_manifest(config)
        except Exception as ex:
            failures.append('inputs: '+str(ex))
    try:
        evidence = json.loads(S.pinned(config['qualification_gate_receipt' if qualification else 'gate_receipt']).read_text())
        S.require(evidence['scope'] == ('separate-six-hour-qualification' if qualification else 'registered-experiment'),
                  'qualification GO cannot authorize registered training')
        S.require(evidence['source_sha256'] == source and evidence['config_sha256'] == identity,
                  'GO receipt must bind exact source and complete config')
        required = set(GATES)-({'six_hour_32_actor_soak'} if qualification else set())
        S.require(set(evidence['gates']) == required, 'complete gate inventory required')
        for name in required:
            gate = evidence['gates'][name]
            S.require(gate['status'] == 'GO', 'gate is not GO: '+name)
            S.pinned(gate['evidence'])
        review = evidence['gates']['independent_sol_high']
        S.require(review['model'] == 'gpt-6.1-sol' and review['effort'] == 'high', 'independent Sol high required')
    except Exception as ex:
        failures.append('launch review: '+str(ex))
    try:
        precision = json.loads(S.pinned(config['precision_registration']).read_text())
        S.require(precision['schema'] == 'pv1-rl-precision-v1' and precision['status'] == 'GO'
                  and precision['training_precision'] == config['precision']
                  and precision['sizes'] == ['M', 'S100'] and precision['absolute_tolerance'] == 2e-6
                  and precision['source_sha256'] == source and precision['deployment'] is False,
                  'explicit both-size training precision registration required; strict 2e-6 unchanged')
        S.require(precision['registration_id'] == config['precision_registration_id']
                  and precision['amendment_sha256'] == config['precision_amendment']['sha256'],
                  'training precision amendment/ID differs from reviewed receipt')
        S.pinned(config['precision_amendment'])
        for size in S.ANCHORS:
            S.require(precision['anchors'][size] == S.ANCHORS[size], 'precision anchor identity')
            S.pinned(precision['parity_evidence'][size])
        from .rl_learner import LearnerConfig
        admitted = LearnerConfig(seed=config['seed'], size=config['size'], microbatch=128,
                                 precision=config['precision'], precision_registration=config['precision_registration_id'])
        S.require(not admitted.test_only, 'registered precision must be admitted by production learner guard')
    except Exception as ex:
        failures.append('precision: '+str(ex))
    return dict(status='GO' if not failures else 'NO-GO', source_sha256=source,
                config_sha256=identity, failures=failures, engine_resume_qualified=False)


def send(connection, message):
    data = S.encoded(message)
    S.require(len(data) <= 2**20, 'control message exceeds 1 MiB')
    connection.send_bytes(data)


def receive(connection, timeout):
    S.require(connection.poll(timeout), 'worker control timeout')
    message = json.loads(connection.recv_bytes(maxlength=2**20))
    S.encoded(message)  # reject nonfinite control JSON before using any field
    return message


_FD_LOCK = threading.Lock()


def ensure_fd_capacity(required):
    """Raise only this process's soft limit; preserve the hard limit exactly."""
    S.require(type(required) is int and required > 0, 'bounded positive descriptor requirement')
    with _FD_LOCK:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        S.require(hard == resource.RLIM_INFINITY or required <= hard,
                  f'{required} descriptors required but hard limit is {hard}')
        if soft != resource.RLIM_INFINITY and soft < required:
            resource.setrlimit(resource.RLIMIT_NOFILE, (required, hard))
        after = resource.getrlimit(resource.RLIMIT_NOFILE)
        S.require(after[1] == hard, 'hard descriptor limit changed')
        return dict(required=required, before_soft=soft, hard=hard, after_soft=after[0])


def guarded_queue_type():
    from . import stream_actor as A
    class GuardedQueue(A.AtomicChunkQueue):
        def load(self, *args, **kwargs):
            # Short games may produce more shards than the initial 128-row
            # estimate. Admit actual live mappings before opening another shard.
            ensure_fd_capacity(len(list(Path('/proc/self/fd').iterdir()))+
                               len(A._FEATURES)+len(A._VECTORS)+64)
            return super().load(*args, **kwargs)
    return GuardedQueue


class GenerationCounter:
    """A parent-readable process counter charged before policy inference.

    A kernel-owned file lock serializes eight-byte reads/writes. A killed writer
    releases its lock. Host crash recovery is deliberately outside this API.
    """
    def __init__(self, path, *, create=False):
        self.fd = os.open(path, os.O_RDWR | (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
        if create:
            os.write(self.fd, struct.pack('<Q', 0))
            os.fsync(self.fd)

    def read(self):
        self._lock(fcntl.LOCK_SH)
        try:
            raw = os.pread(self.fd, 8, 0)
            S.require(len(raw) == 8, 'unreadable authoritative generation counter')
            return struct.unpack('<Q', raw)[0]
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)

    def write(self, value):
        self._lock(fcntl.LOCK_EX)
        try:
            raw = os.pread(self.fd, 8, 0)
            S.require(len(raw) == 8 and type(value) is int and value >= struct.unpack('<Q', raw)[0],
                      'authoritative generation counter regressed/corrupt')
            S.require(os.pwrite(self.fd, struct.pack('<Q', value), 0) == 8, 'generation counter short write')
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)

    def close(self):
        os.close(self.fd)

    def _lock(self, mode):
        deadline = time.monotonic()+.25
        while True:
            try:
                fcntl.flock(self.fd, mode | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                S.require(time.monotonic() < deadline, 'authoritative generation counter lock timeout')
                time.sleep(.005)


def attach_counter(actor, counter, stop_check=None):
    from .stream_actor import StreamingPolicyOursPlayer
    S.require(counter.read() == actor.generated_steps, 'new process differs from lifetime generation counter')
    class CountedActor(StreamingPolicyOursPlayer):
        def __setattr__(self, name, value):
            if name == 'generated_steps':
                if stop_check is not None:
                    stop_check()
                counter.write(value)
            super().__setattr__(name, value)
    # Only counter assignment changes. Sampling/history/model code is inherited
    # unchanged; the existing charge-before-inference statement calls this hook.
    actor.__class__ = CountedActor
    return actor


def public_evidence(play_match, actor):
    """Observe the actual match's command diagnostics, as in the reviewed fixture.

    close() publishes before play_match returns. Find that exact live frame,
    check battle identity, and copy only public command/timing diagnostics.
    """
    frame = sys._getframe(1)
    try:
        while frame is not None and frame.f_code is not play_match.__code__:
            frame = frame.f_back
        S.require(frame is not None, 'publication outside actual match')
        state = frame.f_locals
        battle = state['b']
        S.require(battle is actor.battle, 'publication battle identity mismatch')
        channels, plays = state['channels'], state['plays']
        return dict(terminal=bool(battle.game_over), winner=battle.winner if battle.game_over else None,
                    ticks=int(battle.tick), channels={s: c.diagnostics() for s, c in channels.items()},
                    play_log={s: list(rows) for s, rows in plays.items()},
                    accepted={s: sum(r[3] for r in rows) for s, rows in plays.items()})
    finally:
        del frame


def execution_ok(stats):
    """All failure marks propagated by LivePlayer remain fatal to training."""
    for name, value in stats.items():
        if value and (any(mark in name for mark in ('fail', 'error', 'panic', 'broken', 'dead'))
                      or name in ('own_state_break', 'own_state_breaks', 'opp_state_break', 'opp_state_breaks',
                                  'root_state_breaks')
                      or name == 'source' and value in ('fast-error', 'fast-disabled')):
            raise RuntimeError(f'opponent execution failure: {name}={value!r}')


def bounded_policy_player(model, name='registered-policy'):
    from .sim_ours import PolicyOursPlayer
    class BoundedPolicyPlayer(PolicyOursPlayer):
        def act(self, view):
            try:
                return super().act(view)
            finally:
                # The reviewed sampled Session/parity path stays intact. Its
                # readiness-only whole-game debug log is unnecessary here.
                self.rows.clear()

        def close(self):
            self.rows.clear()
            self.model.clear()
            self.battle = self.session = self.frames = None
            self.shadow_builder = self.shadow_hist = None
    return BoundedPolicyPlayer(model, name=name)


class Opponents:
    def __init__(self, rt, learner_model, config, checkpoints):
        self.rt, self.config, self.checkpoints = rt, config, Path(checkpoints)
        self.cfg = dict(learner_model.cfg)
        self.dtype = next(learner_model.parameters()).dtype
        self.bc = {k: v.detach().cpu().clone() for k, v in learner_model.state_dict().items()}

    def model(self, state):
        from .model import PolicyV1
        model = PolicyV1(**self.cfg).to(dtype=self.dtype).eval()
        expected = model.state_dict()
        S.require(set(state) == set(expected) and all(state[k].shape == v.shape and state[k].dtype == v.dtype
                                                    for k, v in expected.items()), 'opponent state dtype/shape mismatch')
        model.load_state_dict(state, strict=True)
        return model

    def snapshot(self, version):
        import torch
        path = self.checkpoints/f'update-{version:02d}.pt'
        ledger = json.loads(path.with_suffix('.json').read_text())
        S.require(S.file_sha(path) == ledger['learner_checkpoint']['sha256'], 'opponent snapshot SHA')
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        S.require(checkpoint['policy_sha256'] == ledger['policy_sha256'], 'opponent policy identity')
        from .stream_actor import policy_sha256
        model = self.model(checkpoint['model'])
        S.require(policy_sha256(model) == ledger['policy_sha256'], 'opponent model policy SHA mismatch')
        return model

    def make(self, case, version):
        from bot.eval.headline import make_player
        kind = case['league']
        if kind in ('current', 'reservoir', 'bc'):
            chosen = version
            if kind == 'bc':
                return bounded_policy_player(self.model(self.bc), name='frozen-own-bc'), dict(family=kind, version=0)
            if kind == 'reservoir':
                # Fixed milestone rule, <=16 entries, with BC version zero as
                # the explicitly recorded initial reservoir member.
                pool = list(range(0, version+1, 10))[-16:]
                chosen = pool[min(int(case['reservoir_u']*len(pool)), len(pool)-1)]
            return bounded_policy_player(self.snapshot(chosen), name=f'{kind}-v{chosen}'), dict(family=kind, version=chosen)
        if kind == 'hp1_v330':
            path = S.pinned(self.config['hp1_checkpoint'])
            spec = f"student:{path}@{self.config['hp1_threshold']}"
            return make_player(self.rt, spec), dict(family=kind, sha256=S.HP1_SHA)
        if kind == 'live':
            live = self.config['live']
            path = S.pinned(live['fast_checkpoint'])
            fast = f"student:{path}@{live['fast_threshold']}"
            os.environ['BOT_RL_K4CW_FAST'] = fast
            from bot.rl import actor as old_actor
            S.require(old_actor.K4CW_FAST == fast, 'LIVE factory imported with another fast tier')
            opponent = old_actor.make_opponent(self.rt, live['spec'])
            S.require(opponent.deadline_seconds is None, 'LIVE training must use frozen serial no-wall mode')
            inner = opponent.live
            S.require((inner.search.native_threads, inner.search.pool_size, inner.search.chunks) == (1, 0, 4)
                      and inner.deadline_seconds is None and inner.search.deadline_seconds is None,
                      'frozen serial LIVE execution parameters differ')
            return opponent, dict(family=kind, spec=live)
        S.require(kind == 'script', 'unknown league family')
        spec = self.config['scripts'][case['index'] % 2]
        return make_player(self.rt, spec), dict(family=kind, spec=spec)


def boundary_record(actor, event, game, game_sequence, publication_sequence, *, engine_tick, terminal):
    from .actor_worker import WorkerBoundary
    return WorkerBoundary(event=event, actor_id=actor.actor_id, game_id=game,
        game_sequence=game_sequence, seed=actor.seed, policy_version=actor.version,
        policy_sha256=actor.policy_sha256, generated_steps=actor.generated_steps,
        published_steps=actor.published_steps, discarded_steps=actor.discarded_steps,
        engine_tick=engine_tick, terminal=terminal, pending_rows=len(actor.rows)+(actor.pending is not None),
        publication_sequence=publication_sequence, remaining_quota=actor.remaining_quota,
        remaining_budget=actor.budget_steps-actor.generated_steps, engine_resume_qualified=False)


def worker(config, spec, connection, rt, manifest):
    """One CPU process owns one live engine, producer, Session and opponent."""
    import torch
    from . import stream_actor as A, rl_coordinator as C, operational_rejections as O
    from .actor_worker import ActorCheckpoint, ActorLifecycle
    from .lease_adapter import LeaseStopAdapter
    from .sim_ours import bind_matches
    from bot.players.ours import play_match
    from .checks.qualify_ppo_session import audited_match
    from .model import PolicyV1
    from . import featurize as F
    torch.set_num_threads(1)
    config = dict(config)
    S.require(source_digest() == manifest['candidate_source_sha256']
              and registration_identity(config) == manifest['config_sha256'], 'worker source/config changed since admission')
    for key, value in config['live']['environment'].items():
        os.environ[key] = value
    # The full-pool helper is part of the pinned actor source, never a fallback.
    from bot.fullpool.models import install_from_env
    from bot.fullpool.banks import select
    install_from_env(rt)
    select(rt, config['live']['belief_spec'])
    cfg = json.loads(S.pinned(config['model_cfg']).read_text())
    model = PolicyV1(**cfg).to(dtype={'float32': torch.float32, 'float64': torch.float64}[config['precision']]).eval()

    def weights(permit):
        path = Path(permit['checkpoint']['path'])
        S.require(S.file_sha(path) == permit['checkpoint']['sha256'], 'permit checkpoint SHA mismatch')
        ck = torch.load(path, map_location='cpu', weights_only=False)
        S.require(ck['policy_sha256'] == permit['policy_sha256'], 'permit checkpoint policy mismatch')
        return ck['model']

    initial = spec['initial']
    model.load_state_dict(weights(initial), strict=True)
    schedule = S.Schedule(json.loads(S.pinned(config['populations']).read_text()), config['seed'])
    opponent_factory = Opponents(rt, model, config, spec['checkpoints'])
    # BC is always the original selected model, even after process recycling.
    bc_checkpoint = torch.load(Path(spec['checkpoints'])/'update-00.pt', map_location='cpu', weights_only=False)
    opponent_factory.bc = bc_checkpoint['model']
    spool = A.AtomicChunkQueue(spec['spool'], max_bytes=spec['spool_bytes'], max_chunks=spec['spool_chunks'],
                               runtime_manifest=manifest)
    cursor = spec.get('cursor', dict(publication_sequence=0, next_game_sequence=0,
        seed=config['seed'], actor_id=spec['actor_id'], schedule_sha256=schedule.sha256,
        runtime_provenance_sha256=A.manifest_sha256(manifest)))
    sequence, game_sequence = cursor['publication_sequence'], cursor['next_game_sequence']
    game_id, commands, case = None, [], None
    lease = LeaseStopAdapter.from_environment()
    lifecycle = ActorLifecycle(actor_id=spec['actor_id'], lease=lease)
    retirement_reported = False

    def check_stop():
        if Path(spec['qualification_stop_file']).exists():
            actor.failed = True  # close records discarded tail; it cannot publish replacement rows
            raise QualificationStop('separate six-hour qualification exposure complete')
        S.require(not Path(spec['stop_file']).exists(), 'parent stopped the seed')

    def check_lifecycle():
        nonlocal retirement_reported
        decision = lifecycle.check()
        check_stop()
        if lifecycle.retirement_request is not None and not retirement_reported:
            send(connection, dict(kind='retirement_request', generated=actor.generated_steps,
                                  request=lifecycle.retirement_request))
            retirement_reported = True
        S.require(decision.action != 'drain', 'lifecycle drain: '+str(decision.reason))
        return decision

    def observe(event, *, tick, terminal):
        guard()
        decision = lifecycle.on_boundary(boundary_record(actor, event, game_id, game_sequence,
                                        sequence, engine_tick=tick, terminal=terminal))
        if decision.action == 'drain':
            raise RuntimeError('lifecycle drain: '+str(decision.reason))
        return decision

    def publish(chunk, boundary):
        nonlocal sequence
        evidence = public_evidence(play_match, actor)
        for i, action in enumerate(chunk.action):
            if action < F.NOOP:
                card = F.catalog().cards[int(chunk.features['hand'][i, int(action)//576, F.H_CARD])-2]['name']
                commands.append(dict(tick=int(chunk.features['glob'][i, F.G_TICK]), action=int(action), card=card,
                                     version=chunk.version, policy_sha256=chunk.policy_sha256))
        terminal = evidence['terminal']
        S.require(terminal == bool(chunk.terminated[-1]), 'actual terminal/publication mismatch')
        completed = None
        if terminal:
            counts = O.game_counts(evidence, actor.seat, submissions=commands)
            completed = dict(game_id=game_id, accepted_plays=counts['counts']['accepted'], seconds=evidence['ticks']/20.)
        publication = C.Publication(sequence, game_id, game_sequence, evidence['ticks'], terminal,
                                    None if completed is None else C.L.PlayRate(**completed))
        observe('publication', tick=evidence['ticks'], terminal=terminal)
        receipt = spool.write(chunk)
        send(connection, dict(kind='publish', receipt=asdict(receipt), boundary=asdict(boundary),
                              publication=asdict(publication), generated=actor.generated_steps))
        try:
            permit = receive(connection, config['wait_seconds'])
        except EOFError:
            check_stop()
            raise
        if permit['kind'] == 'stop':
            check_stop()
        S.require(permit['kind'] == 'permit', 'coordinator stopped: '+str(permit))
        spool.acknowledge(receipt)
        sequence += 1
        check_lifecycle()
        if lease is not None:
            reason = lease.poll()
            S.require(reason is None, 'lease stop after acknowledgement: '+str(reason))
        state = weights(permit) if permit['version'] != chunk.version else None
        return A.PolicyUpdate(permit['version'], permit['policy_sha256'], state,
                              permit.get('quota_steps'))

    actor = A.StreamingPolicyOursPlayer(model, publish, actor_id=spec['actor_id'], seed=config['seed'],
        anchor_sha256=config['anchor']['sha256'], provenance_sha256=A.manifest_sha256(manifest),
        opponent_id='not-yet-started', budget_steps=spec['quota']*spec['updates'], quota_steps=spec['quota'],
        chunk_rows=config['chunk_rows'], expected_policy_sha256=initial['policy_sha256'])
    if 'restore' in spec:
        actor = ActorCheckpoint.restore_record(spec['restore']['record'], model, publish,
            expected_sha256=spec['restore']['sha256'], driver_state=cursor, claim_directory=spec['claims'])
    generation_counter = GenerationCounter(spec['generation_counter'])
    actor = attach_counter(actor, generation_counter, check_stop)

    def poll(view, decision):
        if view.seat == actor.seat:
            guard()
            check_lifecycle()
            if lease is not None:
                S.require(lease.poll() is None, 'lease interrupted active game; no replay qualified')
            check_stop()
        execution_ok(decision.stats or {})

    try:
        send(connection, dict(kind='ready', generated=actor.generated_steps, pid=os.getpid()))
        while not actor.exhausted:
            guard()
            check_lifecycle()
            case = schedule.case(spec['worker_index']+game_sequence*config['workers'])
            game_id = f"{config['seed']}/{spec['actor_id']}/{game_sequence}"
            commands = []
            opponent, opponent_pin = opponent_factory.make(case, actor.version)
            actor.opponent_id = case['league']
            observe('game_start', tick=0, terminal=False)
            players = {case['seat']: actor, 1-case['seat']: opponent}
            started, cpu = time.monotonic(), time.process_time()
            with bind_matches(players):
                game = audited_match(play_match, rt, players, seed=case['seed'], decks=case['decks'],
                                     levels=case['levels'], verbose=True, observer=poll)
            module_origins(config)
            counts = O.game_counts(game, case['seat'], submissions=commands)
            send(connection, dict(kind='game', game_id=game_id, game_sequence=game_sequence, case=case,
                opponent=opponent_pin, result=game, operational_rejections=counts,
                generated=actor.generated_steps, cpu_seconds=time.process_time()-cpu,
                wall_seconds=time.monotonic()-started))
            if not game['terminal']:
                S.require(actor.exhausted and 'budget_stop' in game, 'unfinished game cannot be replaced')
                observe('budget_complete', tick=game['ticks'], terminal=False)
                break
            decision = observe('game_complete', tick=game['ticks'], terminal=True)
            game_sequence += 1
            if actor.exhausted:
                observe('budget_complete', tick=game['ticks'], terminal=True)
                break
            if decision.action == 'recycle_due':
                cursor = dict(publication_sequence=sequence, next_game_sequence=game_sequence, seed=config['seed'],
                    actor_id=spec['actor_id'], schedule_sha256=schedule.sha256,
                    runtime_provenance_sha256=A.manifest_sha256(manifest))
                snapshot = ActorCheckpoint.capture(actor, cursor)
                send(connection, dict(kind='recycle', record=snapshot.record, sha256=snapshot.sha256,
                                      cursor=cursor, generated=actor.generated_steps))
                return
        send(connection, dict(kind='done', generated=actor.generated_steps, published=actor.published_steps,
                              discarded=actor.discarded_steps))
    except QualificationStop:
        try:
            send(connection, dict(kind='qualification_stopped', generated=actor.generated_steps,
                                  published=actor.published_steps, discarded=actor.discarded_steps))
        except (BrokenPipeError, EOFError):
            pass
    except BaseException as ex:
        C.durable_json(Path(spec['error_directory'])/f'{spec["actor_id"]}-{os.getpid()}.json',
                       dict(error=repr(ex), generated=actor.generated_steps))
        try:
            send(connection, dict(kind='failed', error=repr(ex), generated=actor.generated_steps,
                                  published=actor.published_steps, discarded=actor.discarded_steps))
        except (BrokenPipeError, EOFError):
            pass
        raise
    finally:
        generation_counter.close()


def make_manifest(config):
    import numpy as np
    import torch
    from . import rl_learner as L
    lineage = json.loads(S.pinned(config['runtime_manifest']).read_text())
    return dict(native_sha256=L.NATIVE_SHA256, gamedata_sha256=L.GAMEDATA_SHA256,
        actor_source_sha256=lineage['actor_manifest_sha256'],
        runtime_source_sha256=lineage['runtime_manifest_sha256'], candidate_source_sha256=source_digest(),
        config_sha256=registration_identity(config), precision=config['precision'],
        precision_registration_sha256=config['precision_registration']['sha256'],
        precision_registration_id=config['precision_registration_id'],
        precision_amendment_sha256=config['precision_amendment']['sha256'],
        populations_sha256=config['populations']['sha256'], banks_sha256=config['banks']['sha256'],
        evaluation_populations_sha256=config['evaluation_populations']['sha256'],
        torch_version=str(torch.__version__), numpy_version=np.__version__,
        attention='mha_fastpath=False,flash=False,mem_efficient=False,math=True', actor_threads='1')


def checkpoint_permit(checkpoints, version, policy, quota=None):
    path = Path(checkpoints)/f'update-{version:02d}.pt'
    ledger = json.loads(path.with_suffix('.json').read_text())
    S.require(ledger['policy_sha256'] == policy, 'checkpoint/permit identity mismatch')
    return dict(kind='permit', version=version, policy_sha256=policy, quota_steps=quota,
                checkpoint=dict(path=str(path), sha256=ledger['learner_checkpoint']['sha256']))


def relay_publication(coordinator, transport, actor_id, message):
    """One bounded spool mapping; only canonical coordinator files reach update."""
    from . import rl_coordinator as C, rl_learner as L, stream_actor as A
    data = dict(message['publication'])
    if data['completed'] is not None:
        data['completed'] = L.PlayRate(**data['completed'])
    receipt = A.Receipt(**message['receipt'])
    mapped = transport.load(receipt, expected_version=coordinator.version,
                            expected_policy_sha256=coordinator.policy)
    try:
        return coordinator.publish(actor_id, mapped, A.Boundary(**message['boundary']), C.Publication(**data))
    finally:
        C.close_maps(mapped)


@contextmanager
def learner_lock(directory):
    """One owning driver per own-host GPU; the lock survives actor replacement."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/(os.uname().nodename.split('.')[0]+'-gpu.lock')
    with path.open('a+b') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as ex:
            raise RuntimeError('another learner owns this host/GPU lock') from ex
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def adopt_worker_descendants():
    """Keep orphaned search descendants attached to this driver for exact reap."""
    import ctypes
    S.require(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0,
              'Linux child-subreaper admission failed')


def finish_worker_session(session):
    """A terminal worker must leave no live search process behind."""
    live = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            raw = (path/'stat').read_text()
            fields = raw[raw.rfind(')')+2:].split()
            if int(fields[3]) != session:
                continue
            pid = int(path.name)
            if fields[0] == 'Z' and int(fields[1]) == os.getpid():
                os.waitpid(pid, os.WNOHANG)
            else:
                live.append(pid)
        except (FileNotFoundError, ProcessLookupError, ChildProcessError):
            continue
    if live:
        os.killpg(session, signal.SIGKILL)
        raise RuntimeError(f'worker left search descendants; no successor allowed: {live}')


def training_rejections(path):
    from . import operational_rejections as O
    records, snapshots = [], {}
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            row = json.loads(line)['operational_rejections']
            records.append(row)
            for version, snapshot in row['by_snapshot'].items():
                snapshots.setdefault(version, []).append(snapshot)
    by_version = {}
    for version, rows in snapshots.items():
        identities = {row['policy_sha256'] for row in rows}
        S.require(len(identities) == 1, 'one snapshot version has multiple policy hashes')
        by_version[version] = dict(policy_sha256=identities.pop(),
            **O.aggregate([dict(counts=r['counts'], by_card=r['by_card']) for r in rows]))
    return dict(overall=O.aggregate(records), by_version=by_version,
                comparison_scope='training exposure counts; matched BC alerts are evaluation-only')


def run(config, config_path, out, *, qualification=False):
    guard()
    S.require(qualification or not config.get('qualification_only', False), 'leased placement is qualification only')
    report = audit(config, qualification=qualification)
    S.require(report['status'] == 'GO', 'launch gates remain closed: '+repr(report['failures']))
    with learner_lock('/mpac/sdicks02/jobs/clasher/pretrain-v1/rl-locks'):
        import torch
        S.require(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'one visible own-host GPU required')
        free, total = torch.cuda.mem_get_info(0)
        gpu = config['gpu_admission']
        evidence = json.loads(S.pinned(gpu['measurement']).read_text())
        S.require(evidence['status'] == 'pass' and evidence['size'] == config['size']
                  and evidence['dtype'] == config['precision'] and evidence['microbatch'] == 128
                  and evidence['anchor_sha256'] == config['anchor']['sha256']
                  and evidence['capped_axes'] == {'ent': 256, 'ev': 32, 'rev': 16}
                  and len(evidence['optimizer_steps']) >= 2
                  and gpu['peak_reserved_bytes'] == max(s['peak_reserved_bytes'] for s in evidence['optimizer_steps']),
                  'GPU max-shape/resident-Adam evidence mismatch')
        process_evidence = json.loads(S.pinned(gpu['process_measurement']).read_text())
        S.require(process_evidence['status'] == 'pass' and process_evidence['scope'] == 'full-cuda-process'
                  and process_evidence['size'] == config['size'] and process_evidence['dtype'] == config['precision']
                  and process_evidence['anchor_sha256'] == config['anchor']['sha256']
                  and process_evidence['peak_process_bytes'] == gpu['peak_process_bytes'] >= gpu['peak_reserved_bytes'],
                  'full CUDA process peak is required; allocator-only evidence cannot admit sharing')
        required_free = gpu['peak_process_bytes']+8*2**30
        S.require(total >= GPU_CAP_BYTES and free >= required_free, 'measured RL peak plus 8 GiB headroom does not fit')
        S.require(torch.cuda.memory_allocated(0) == 0, 'fresh learner allocator required')
        torch.cuda.set_per_process_memory_fraction(GPU_CAP_BYTES/total, device=0)
        admission = dict(free_bytes=free, total_bytes=total, allocator_cap_bytes=GPU_CAP_BYTES,
                         allocator_fraction=GPU_CAP_BYTES/total, singleton_lock=True,
                         required_free_bytes=required_free, measured_peak_reserved_bytes=gpu['peak_reserved_bytes'])
        admission['measured_peak_process_bytes'] = gpu['peak_process_bytes']
        return _run(config, config_path, out, gpu_admission=admission, qualification=qualification)


def _run(config, config_path, out, *, gpu_admission, qualification=False):
    """Keep the learner/coordinator live while terminal actor processes recycle."""
    from multiprocessing import Pipe
    import torch
    from . import rl_learner as L, rl_coordinator as C, stream_actor as A
    from .lease_adapter import LeaseStopAdapter
    guard()
    adopt_worker_descendants()
    lease = LeaseStopAdapter.from_environment()
    S.require((lease is not None) == bool(config.get('qualification_only', False)),
              'leased qualification requires R37 generation environment; own run must not inherit it')
    S.require(lease is None or lease.poll() is None, 'lease already stopped before learner allocation')
    S.require(os.uname().nodename.split('.')[0] == config['host'], 'wrong registered host')
    report = audit(config, qualification=qualification)
    S.require(report['status'] == 'GO', 'launch gates remain closed: '+repr(report['failures']))
    S.require(not Path(out).exists(), 'fresh run directory required; run resume is not qualified')
    out = Path(out).resolve()
    out.mkdir(parents=True)
    C.durable_json(out/'config.json', config)
    config_path = out/'config.json'
    C.durable_json(out/'admission.json', report)
    C.durable_json(out/'gpu-admission.json', gpu_admission)
    updates = QUALIFICATION_UPDATES if qualification else 32
    C.durable_json(out/'scope.json', dict(scope='separate-six-hour-qualification' if qualification else 'registered-experiment',
        counted_registered_prefix=False if qualification else True, maximum_updates=updates,
        minimum_qualification_seconds=QUALIFICATION_SECONDS if qualification else None,
        checkpoint_or_data_promotion_allowed=False, test_only=qualification))
    torch.set_num_threads(1)
    S.require(str(torch.__version__) == '2.7.1+cu118', 'exact qualified Torch required')
    S.require(torch.cuda.is_available(), 'CUDA learner required')
    free, _ = torch.cuda.mem_get_info()
    S.require(free >= 8*2**30, 'at least 8 GiB GPU free required')
    manifest = make_manifest(config)
    manifest['scope'] = 'separate-six-hour-qualification' if qualification else 'registered-experiment'
    C.durable_json(out/'runtime.json', manifest)
    cfg = json.loads(S.pinned(config['model_cfg']).read_text())
    learner_config = L.LearnerConfig(seed=config['seed'], size=config['size'], precision=config['precision'],
        microbatch=128, updates=updates, test_only=qualification,
        precision_registration='' if qualification else config['precision_registration_id'])
    learner_stop = threading.Event()
    class StoppingLearner(L.Learner):
        def _batch(self, *args, **kwargs):
            S.require(not learner_stop.is_set(), 'driver stop before learner microbatch')
            return super()._batch(*args, **kwargs)

        def _forward(self, *args, **kwargs):
            S.require(not learner_stop.is_set(), 'driver stop before learner forward')
            return super()._forward(*args, **kwargs)
    learner = StoppingLearner(S.pinned(config['anchor']), anchor_sha256=config['anchor']['sha256'], model_cfg=cfg,
                        runtime_manifest=manifest, config=learner_config, device='cuda')
    names = [f'actor-{i:02d}' for i in range(config['workers'])]
    quotas = {name: 262144//len(names) for name in names}
    chunks, size = C.queue_capacity(262144)
    spool_chunks, spool_bytes = C.queue_capacity(config['chunk_rows']*2)
    S.require(shutil.disk_usage(out).free > size+len(names)*spool_bytes+10*2**30,
              'insufficient reserved queue/spool disk capacity')
    descriptors = ensure_fd_capacity((262144//config['chunk_rows'])*(len(A._FEATURES)+len(A._VECTORS))+512)
    C.durable_json(out/'descriptor-admission.json', descriptors)
    queue = guarded_queue_type()(out/'queue', max_bytes=size, max_chunks=chunks, runtime_manifest=manifest)
    stop = out/'STOP'
    def notify(reason):
        # Only this run's cooperative notification; never a remote signal.
        stop.touch(exist_ok=True)
        learner_stop.set()
    coordinator = C.Coordinator(learner, queue, quotas=quotas, checkpoint_dir=out/'checkpoints',
        config=C.CoordinatorConfig(wait_seconds=config['wait_seconds'], test_only=qualification), stop_notifier=notify)
    counters = {name: 0 for name in names}
    generation_counters = {name: GenerationCounter(out/f'{name}-generated.u64', create=True) for name in names}
    counter_lock, files_lock = threading.Lock(), threading.Lock()
    failures = []
    counter_failures = {}
    process_lock = threading.Lock()
    processes = {}
    monitoring_done = threading.Event()
    qualification_stopping = threading.Event()
    qualification_start = []
    ready = set()
    qualification_stop = out/'QUALIFICATION-EXPOSURE-COMPLETE'
    (out/'worker-errors').mkdir()

    def account(name, value):
        S.require(type(value) is int and value >= 0, 'invalid worker generation report')
        with counter_lock:
            S.require(value >= counters[name], 'worker counter regressed')
            counters[name] = value

    def all_counters():
        with counter_lock:
            result = {}
            for name, counter in generation_counters.items():
                try:
                    value = counter.read()
                    S.require(counters[name] <= value <= quotas[name]*updates, 'invalid authoritative generation frontier')
                    result[name] = value
                    counter_failures.pop(name, None)
                except BaseException as ex:
                    counter_failures[name] = repr(ex)
                    raise
            return result

    def abort(reason):
        # A stopped writer can hold flock. Abort generation even when the
        # authoritative count cannot yet be read; re-read it after exact reap.
        try:
            counts = all_counters()
        except BaseException:
            counts = None
        coordinator.abort(reason, generated_counts=counts)

    def identity(pid):
        # Parent and monitor compare Linux starttime as well as PID.
        text = Path(f'/proc/{pid}/stat').read_text()
        return text[text.rfind(')')+2:].split()[19]

    def stop_processes():
        with process_lock:
            live = list(processes.values())
        for process, started in live:
            if process.poll() is None:
                try:
                    if identity(process.pid) == started:
                        os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def monitor():
        last_recorded = 0.
        while not monitoring_done.wait(1.):
            try:
                host = guard()
                if lease is not None:
                    S.require(lease.poll() is None, 'lease reclaimed; qualification stops without resume/top-up')
                S.require(torch.cuda.memory_reserved(0) <= GPU_CAP_BYTES, 'learner allocator cap breached')
                with process_lock:
                    live = list(processes.values())
                observations = []
                for process, started in live:
                    if process.poll() is not None:
                        continue
                    try:
                        before = identity(process.pid)
                        status = Path(f'/proc/{process.pid}/status').read_text()
                        rss = int(next(l.split()[1] for l in status.splitlines() if l.startswith('VmRSS:')))*1024
                        after = identity(process.pid)
                    except FileNotFoundError:
                        S.require(process.poll() is not None, 'worker /proc identity disappeared while live')
                        continue
                    S.require(before == after == started and 0 < rss <= 2*2**30,
                              f'worker PID/start/RSS violation: {process.pid}, {rss}')
                    anon = int(next(l.split()[1] for l in status.splitlines() if l.startswith('RssAnon:')))*1024
                    observations.append(dict(pid=process.pid, start=started, rss_bytes=rss, rss_anon_bytes=anon))
                now = time.monotonic()
                if qualification and qualification_start and now-qualification_start[0] >= QUALIFICATION_SECONDS:
                    qualification_stopping.set()
                    qualification_stop.touch(exist_ok=False)
                    abort('separate six-hour qualification exposure complete')
                    return
                if now-last_recorded >= 10:
                    with files_lock:
                        with open(out/'resource-samples.jsonl', 'ab') as samples:
                            samples.write(S.encoded(dict(monotonic=now, host=host, workers=observations,
                                learner_reserved_bytes=torch.cuda.memory_reserved(0)))+b'\n')
                    last_recorded = now
                if coordinator.stop_event.is_set() and not qualification_stopping.is_set():
                    stop_processes()
            except BaseException as ex:
                with files_lock:
                    failures.append(dict(actor_id='resource-monitor', error=repr(ex)))
                abort(repr(ex))
                stop_processes()
                return

    def gpu_monitor():
        while not monitoring_done.wait(1.):
            try:
                query = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                                       check=True, capture_output=True, text=True, timeout=2)
                rows = query.stdout.strip().splitlines()
                S.require(len(rows) == 1, 'one physical GPU required for memory monitor')
                free = int(rows[0].strip())*2**20
                S.require(free >= 8*2**30, 'physical GPU headroom fell below 8 GiB')
            except BaseException as ex:
                with files_lock:
                    failures.append(dict(actor_id='physical-gpu-monitor', error=repr(ex)))
                abort(repr(ex))
                stop_processes()  # only this runner's tracked worker sessions
                return

    def supervisor(name, index):
        process = connection = None
        spec = dict(actor_id=name, worker_index=index, quota=quotas[name],
            updates=updates, qualification_stop_file=str(qualification_stop), error_directory=str(out/'worker-errors'),
            checkpoints=str(out/'checkpoints'), spool=str(out/'transport'/name),
            spool_chunks=spool_chunks, spool_bytes=spool_bytes, claims=str(out/'claims'),
            stop_file=str(stop), initial=checkpoint_permit(out/'checkpoints', 0, coordinator.policy))
        spec['generation_counter'] = str(out/f'{name}-generated.u64')
        transport = A.AtomicChunkQueue(spec['spool'], max_bytes=spool_bytes, max_chunks=spool_chunks,
                                        runtime_manifest=manifest)
        try:
            while True:
                guard()
                S.require(not coordinator.stop_event.is_set(), 'seed stopped before process start')
                parent_connection, child_connection = Pipe(duplex=True)
                connection = parent_connection
                spec_path = out/f'{name}-start.json'
                C.durable_json(spec_path, spec)
                log = open(out/f'{name}.log', 'ab', buffering=0)
                try:
                    process = subprocess.Popen([sys.executable, str(ENTRY), 'worker', '--config', str(config_path),
                        '--out', str(out), '--worker-spec', str(spec_path), '--fd', str(child_connection.fileno())],
                        pass_fds=(child_connection.fileno(),), stdout=log, stderr=subprocess.STDOUT,
                        cwd=ROOT, env=dict(os.environ, CUDA_VISIBLE_DEVICES=''), start_new_session=True)
                    with process_lock:
                        processes[name] = (process, identity(process.pid))
                finally:
                    log.close()
                    child_connection.close()
                recycle = None
                while True:
                    message = receive(connection, config['wait_seconds'])
                    account(name, message['generated'])
                    kind = message['kind']
                    if kind == 'publish':
                        update = relay_publication(coordinator, transport, name, message)
                        permit = dict(kind='permit', version=update.version, policy_sha256=update.policy_sha256,
                                      quota_steps=update.quota_steps)
                        if update.state_dict is not None:
                            permit = checkpoint_permit(out/'checkpoints', update.version,
                                                        update.policy_sha256, update.quota_steps)
                        spec['initial'] = checkpoint_permit(out/'checkpoints', update.version, update.policy_sha256)
                        send(connection, permit)
                    elif kind == 'game':
                        with files_lock:
                            with open(out/'games.jsonl', 'ab') as rows:
                                rows.write(S.encoded(dict(actor_id=name, **message))+b'\n')
                                rows.flush()
                                os.fsync(rows.fileno())
                    elif kind == 'retirement_request':
                        pid = message['request']['source_process']['pid']
                        C.durable_json(out/f'{name}-retirement-request-{pid}.json', message)
                    elif kind == 'recycle':
                        record, cursor = message['record'], message['cursor']
                        S.require(S.digest(record) == message['sha256'], 'recycle checkpoint SHA mismatch')
                        state = coordinator.actors[name]
                        S.require(record['actor_id'] == name and record['seed'] == config['seed']
                                  and record['budget_steps'] == quotas[name]*updates
                                  and record['source_process']['pid'] == process.pid
                                  and str(record['source_process']['start']) == processes[name][1]
                                  and record['policy_sha256'] == spec['initial']['policy_sha256']
                                  and record['version'] == spec['initial']['version']
                                  and record['counters']['generated_steps'] == state['generated'] == state['accepted']
                                  and record['counters']['published_steps'] == state['accepted']
                                  and record['remaining_quota'] == quotas[name]-state['update_rows']
                                  and cursor['publication_sequence'] == state['sequence']
                                  and cursor['next_game_sequence'] == state['completed']
                                  and cursor['actor_id'] == name and cursor['seed'] == config['seed']
                                  and cursor['runtime_provenance_sha256'] == learner.provenance_sha256
                                  and cursor['schedule_sha256'] == S.Schedule(
                                      json.loads(S.pinned(config['populations']).read_text()), config['seed']).sha256
                                  and state['last']['terminal'], 'recycle witness differs from live coordinator')
                        S.require(not any(p.is_dir() for p in transport.root.iterdir()), 'transport not drained before recycle')
                        C.durable_json(out/f'{name}-recycle-{cursor["next_game_sequence"]}.json', message)
                        recycle = message
                        break
                    elif kind == 'done':
                        S.require(message['discarded'] == 0 and message['generated'] == message['published']
                                  == quotas[name]*updates, 'worker completion budget mismatch')
                        break
                    elif kind == 'ready':
                        with process_lock:
                            ready.add(name)
                            if len(ready) == len(names) and not qualification_start:
                                qualification_start.append(time.monotonic())
                    elif kind == 'qualification_stopped':
                        S.require(qualification_stopping.is_set(), 'unexpected qualification stop')
                        break
                    else:
                        raise RuntimeError('worker failed: '+str(message))
                code = process.wait(timeout=60)
                S.require(code == 0, f'worker {name} exited {code}')
                finish_worker_session(process.pid)
                connection.close()
                connection = None
                with process_lock:
                    processes.pop(name, None)
                if recycle is None:
                    return
                spec.update(restore=dict(record=recycle['record'], sha256=recycle['sha256']), cursor=recycle['cursor'])
        except BaseException as ex:
            expected = qualification_stopping.is_set() and isinstance(ex, (C.CoordinatorError, EOFError, BrokenPipeError))
            if not expected:
                with files_lock:
                    failures.append(dict(actor_id=name, error=repr(ex)))
                abort(f'{name}: {ex}')
            if connection is not None:
                try:
                    send(connection, dict(kind='stop', reason=repr(ex)))
                except (OSError, ValueError):
                    pass
        finally:
            if connection is not None:
                connection.close()
            if process is not None:
                try:
                    process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    stop_processes()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        if identity(process.pid) == processes[name][1]:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
                    failures.append(dict(actor_id=name, error='worker required forced stop', pid=process.pid))
                finally:
                    try:
                        finish_worker_session(process.pid)
                    except RuntimeError as ex:
                        failures.append(dict(actor_id=name, error=repr(ex)))
                    with process_lock:
                        processes.pop(name, None)

    threads = [threading.Thread(target=supervisor, args=(name, i), name=name) for i, name in enumerate(names)]
    monitor_thread = threading.Thread(target=monitor, name='registered-resource-monitor')
    gpu_monitor_thread = threading.Thread(target=gpu_monitor, name='registered-physical-gpu-monitor')
    try:
        monitor_thread.start()
        gpu_monitor_thread.start()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        S.require(not failures, 'actor failures: '+repr(failures))
        C.durable_json(out/'training-rejections.json', training_rejections(out/'games.jsonl'))
        if qualification:
            S.require(qualification_stopping.is_set() and qualification_start
                      and time.monotonic()-qualification_start[0] >= QUALIFICATION_SECONDS,
                      'qualification budget exhausted before six hours; no extension/replacement permitted')
            S.require(coordinator.join(timeout=120), 'in-flight qualification optimizer did not stop')
            counts = all_counters()
            coordinator.abort('separate six-hour qualification exposure complete', generated_counts=counts)
            S.require(not any((out/'worker-errors').iterdir()), 'qualification has worker execution failures')
            result = dict(status='completed-exposure-pending-review', scope='separate-six-hour-qualification',
                source_sha256=source_digest(), wall_seconds=time.monotonic()-qualification_start[0],
                generated_counts=counts, generated=sum(counts.values()), trained_steps=learner.trained_steps,
                accepted=sum(a['accepted'] for a in coordinator.actors.values()),
                unpublished_or_discarded_tail=sum(counts.values())-sum(a['accepted'] for a in coordinator.actors.values()),
                updates=learner.version, test_only=True, counted_registered_prefix=False,
                checkpoint_or_data_promotion_allowed=False, engine_resume_qualified=False)
            C.durable_json(out/'qualification.json', result)
            return result
        final = coordinator.finalize()
        # The existing loader proves the complete Adam participation/counters at
        # a completed-update boundary. This is validation, never run resume.
        proof = L.Learner(S.pinned(config['anchor']), anchor_sha256=config['anchor']['sha256'], model_cfg=cfg,
            runtime_manifest=manifest, config=learner_config, device='cpu')
        proof.load_checkpoint(out/'checkpoints/update-32.pt')
        C.durable_json(out/'completed.json', dict(status='training_complete', final=final,
            generated_counts=all_counters(), optimizer_resume_proof=True, engine_resume_qualified=False))
        return final
    except BaseException as ex:
        abort(repr(ex))
        stopped = coordinator.join(timeout=120)
        diagnostic = None
        if stopped:
            learner.save_checkpoint(out/'stopped-diagnostic.pt')
            diagnostic = dict(path='stopped-diagnostic.pt', sha256=S.file_sha(out/'stopped-diagnostic.pt'),
                              resume_eligible=False)
        try:
            final_counts = all_counters()
        except BaseException:
            final_counts = dict(counters)
        C.durable_json(out/'stopped.json', dict(status='stopped', error=repr(ex), failures=failures,
            generated_counts=final_counts, unknown_generation_counters=dict(counter_failures), trained_steps=learner.trained_steps,
            version=learner.version, engine_resume_qualified=False, diagnostic_checkpoint=diagnostic))
        raise
    finally:
        monitoring_done.set()
        monitor_thread.join(timeout=5)
        gpu_monitor_thread.join(timeout=5)
        coordinator.join(timeout=60)
        for counter in generation_counters.values():
            counter.close()
