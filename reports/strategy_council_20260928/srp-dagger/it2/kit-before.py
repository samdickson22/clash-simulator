"""One bounded SRP DAgger iteration; all engine/learner imports use the workspace."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import tomllib

HERE = Path(__file__).resolve().parent
COUNCIL = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'engine-rs'))
os.environ.update(CLASHER_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field
from clasher.rl import eval as ev
from clasher.rl.dagger_behavior import actor_policy_action
from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.imitation import CorpusMetadata, CORPUS_SCHEMA_VERSION, load_corpus
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import project_council_public_observation as project
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner
from clasher.rl.scripted_demonstrations import ScriptedGameDemonstration
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.train_recurrent import maybe_silence_stdio

TRAINING = COUNCIL / 'm0/data/roles_v2/training.json'
HOG = COUNCIL / 'pilot/hog26-deployment.json'
INITIAL = COUNCIL / 'pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt'
FINAL = HERE / 'student.pt'
DEVICE = torch.device('cpu')

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    games: int = Field(ge=2, le=40)
    beta: float = Field(ge=0, le=1)
    collection_seed: int
    split_seed: int
    fit_seed: int
    epochs: int = Field(ge=1, le=3)
    learning_rate: float = Field(gt=0, le=0.0001)
    anchor_kl: float = Field(gt=0)
    chunk: int = Field(ge=2)


def config():
    return Config.model_validate(tomllib.loads((HERE / 'pilot.toml').read_text()))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    tmp.replace(path)


def log(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def source_hashes():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src/clasher').rglob('*.py'))}


def sources_match(reference):
    current = source_hashes()
    # Exact reviewed changes outside this collection/fit/evaluation path.
    reviewed = (
        ('src/clasher/cards/c56_champions.py',
         'bf58d5c450b70abe7b6a50c5273f48b9243c97920af4e0daa294f36fdc13a74e',
         'd7d82e91fd8da4f2f1e71dd6a7e79d7cf3ef0e470206dfeb555c2060f015bc95'),
        ('src/clasher/rl/script_rollout_planner.py',
         '69f15a118197a9812debde1d8756644d6c5d2908ba4633988383370d3a90d8e3',
         'd624bb24d16be0d3f324500dfdf5c64dbc06a08f3cdeab974aab06c3bf090c59'),
        ('src/clasher/rl/council_pilot.py',
         '0bae206e8b36a05392d0e32a1e21f62f14630973986dae360a263153326e6c52',
         'a7edb4eec6ef19ef756f98e7c23749ed94ed53e8f6878514dc7742ab4c5c7a53'),
    )
    for key, before, after in reviewed:
        if reference.get(key) == before and current.get(key) == after:
            current[key] = reference[key]
    return current == reference


def check_data_pins(pins):
    if not (COUNCIL/'GAMEDATA_CANONICAL_READY').is_file():
        raise RuntimeError('canonical gamedata marker is missing')
    for path, key in ((TRAINING, 'training_sha256'), (HOG, 'hog_sha256')):
        if sha(path) != pins[key]:
            raise RuntimeError(f'deck data drift: {path}')
    expected = json.loads((HERE/'data-provenance.json').read_text())['gamedata_sha256']
    if sha(ROOT/'gamedata.json') != expected:
        raise RuntimeError('gamedata drift')
    canonical = json.loads((HERE/'canonical-data.json').read_text())
    if expected != canonical['gamedata_sha256']:
        raise RuntimeError('preflight data is not the verified canonical data')


def check_native_pins():
    receipt = json.loads((HERE/'native-runtime.json').read_text())
    for name, expected in receipt['verified_hashes'].items():
        if sha(ROOT/name) != expected:
            raise RuntimeError(f'native runtime drift: {name}')


def budget():
    total = sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    for p in (COUNCIL / 'human-prior-p16/evaluation').glob('srp-dagger-*/*'):
        if p.is_file():
            total += p.stat().st_size
    if total >= 2 * 1024**3:
        raise RuntimeError('2 GiB artifact budget exceeded')
    return total


class RecordedPlanner(ScriptRolloutPlanner):
    """Record existing leaf returns, preserving search order and RNG consumption."""
    def select_action(self, battle, player_id, legal):
        self.root_values = []
        return super().select_action(battle, player_id, legal)

    def _rollout(self, battle, player_id, action, other_action):
        value = super()._rollout(battle, player_id, action, other_action)
        self.root_values.append((int(action), float(value)))
        return value


def setup(loaded, deck_path, seed, seat):
    env = ev._make_evaluation_envs(candidate=loaded, decks_path=TRAINING,
        sampling_decks_path=None, candidate_sampling_decks_path=deck_path,
        opponent_sampling_decks_path=TRAINING, decision_interval=5, max_ticks=6001,
        seed=seed, mirror_match=False, reward_profile='objective-v1')[seat]
    env._structured_obs_builder = loaded.builder
    env._public_action_mask_builder = None
    env.public_contract_version = loaded.model.config.public_contract_version
    decks = ev._sample_paired_ordered_decks(load_deck_pool(deck_path),
        load_deck_pool(TRAINING), matchup_seed=seed)
    with maybe_silence_stdio(True):
        env.reset(seed=seed, ordered_decks=decks if seat == 0 else decks[::-1])
    return env


@torch.no_grad()
def collect_game(game, loaded, cfg, *, backend='native', output_dir=None):
    started, cpu_started = time.perf_counter(), time.process_time()
    pins = json.loads((HERE/'preflight.json').read_text())
    check_data_pins(pins)
    if not sources_match(pins['sources']):
        raise RuntimeError('workspace source drift before game')
    if backend == 'native':
        check_native_pins()
    seed = cfg.collection_seed + (game // 2) * 1009
    seat = game % 2
    # Seven of twenty seat pairs explicitly use Hog 2.6.
    role = 'hog26' if (game // 2) % 3 == 0 else 'training'
    # Avoid confounding all Hog games with one opponent style.
    style = ('balanced', 'pressure', 'defense')[((game // 2) + (game // 6)) % 3]
    env = setup(loaded, HOG if role == 'hog26' else TRAINING, seed, seat)
    builder, model = loaded.builder, loaded.model
    masks_builder = PublicActionMaskBuilder(builder)
    planner = RecordedPlanner(env, PublicScriptedOpponent(builder, style='balanced'),
        seed=seed * 2 + seat + 7919, opponent_model=StrategyBot('balanced'), backend=backend)
    opponent = PublicScriptedOpponent(builder, style=style)
    rng = np.random.default_rng(seed * 2 + seat + 19001)
    torch.manual_seed(seed + 271828)
    state = model.initial_state(1, device=DEVICE)
    noop = env.action_space.no_op_action
    prior = noop
    observations, masks, labels, previous, queried = [], [], [], [], []
    executed, ticks, accepted, student_actions, mixed = [], [], [], [], []
    candidate_ids, candidate_values, candidate_rows = [], [], []
    planner_cpu = planner_wall = 0.0
    for decision in range(1300):
        packets = [project(builder.build_actor(env.battle, s)) for s in (0, 1)]
        public_masks = {s: masks_builder.build(PublicActionMaskInput.from_confidence_observation(packets[s])) for s in (0, 1)}
        action, state = actor_policy_action(model, packets[seat], public_masks[seat],
            state=state, previous_action=prior, previous_reward=0.0,
            episode_start=decision == 0, deterministic=False, device=DEVICE,
            observation_builder=builder)
        legal = np.flatnonzero(public_masks[seat] & env.action_space.legal_action_mask(env.battle, seat))
        playable = bool(np.any(legal != noop))
        teacher = noop
        if playable:
            wall0, cpu0 = time.perf_counter(), time.process_time()
            with maybe_silence_stdio(True):
                teacher = planner.select_action(env.battle, seat, legal)
            planner_cpu += time.process_time() - cpu0
            planner_wall += time.perf_counter() - wall0
            for aid, value in planner.root_values:
                candidate_ids.append(aid); candidate_values.append(value); candidate_rows.append(decision)
        use_teacher = bool(rng.random() < cfg.beta)
        chosen = teacher if use_teacher else action
        if not public_masks[seat][teacher] or not public_masks[seat][chosen]:
            raise ValueError('illegal label or executed action')
        observations.append(packets[seat]); masks.append(public_masks[seat])
        labels.append(teacher); queried.append(playable); previous.append(prior)
        executed.append(chosen); student_actions.append(action); mixed.append(use_teacher)
        ticks.append(env.battle.tick)
        decisions = {seat: chosen, 1-seat: int(opponent.select_action(packets[1-seat]))}
        with maybe_silence_stdio(True):
            _, done, info = env.step(decisions, pre_action_masks=public_masks)
        accepted.append(bool(info.action_success[seat]))
        prior = chosen
        if decision % 100 == 0:
            log(dict(event='collection', game=game, decisions=decision+1,
                     labels=sum(queried), planner_cpu_s=planner_cpu, pid=os.getpid()))
        if done:
            if not env.battle.game_over:
                raise ValueError('truncated game')
            break
    else:
        raise ValueError('decision bound reached')
    observations.append(project(builder.build_actor(env.battle, seat)))
    masks.append(masks_builder.build(PublicActionMaskInput.from_confidence_observation(observations[-1])))
    previous.append(prior); labels.append(noop); queried.append(False)
    n = len(labels)
    starts = np.zeros(n, bool); starts[0] = True
    public = PublicPolicySequence.from_observations(builder, observations)
    controls = dict(action_masks=np.asarray(masks, bool), expert_actions=np.asarray(labels, np.int64),
        previous_actions=np.asarray(previous, np.int64), previous_rewards=np.zeros(n, np.float32),
        episode_starts=starts, episode_ids=np.full(n, game, np.int64),
        expert_action_supervision_valid=np.asarray(queried, bool))
    provenance = dict(role='training', family_id=role, seed=seed, seat=seat,
        opponent_style=style, teacher='privileged-srp-xm', complete_game=True,
        query_every=1, qualified_player_plan_every=2, beta=cfg.beta, backend=backend,
        gamedata_sha256=sha(ROOT/'gamedata.json'))
    metadata = CorpusMetadata(schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(), seed=seed, decisions=n-1, samples=n,
        decision_interval=5, max_ticks=6001, planner_depth=1, planner_simulations=1,
        planner_action_samples=16, max_entities=builder.max_entities, token_names=builder.token_names,
        reward_profile=env.reward_profile, behavior_checkpoint=str(INITIAL), expert_probability=cfg.beta,
        label_source='oracle', label_strategy='privileged-srp-xm', public_contract_version=4,
        public_history_slots=4, public_seen_card_slots=8, provenance=json.dumps(provenance))
    execution = dict(submitted_actions=np.asarray(executed, np.int64), submitted_ticks=np.asarray(ticks, np.int64),
        accepted_commands=np.asarray(accepted, bool), student_actions=np.asarray(student_actions, np.int64),
        teacher_executed=np.asarray(mixed, bool), root_candidate_ids=np.asarray(candidate_ids, np.int64),
        root_candidate_values=np.asarray(candidate_values, np.float64), root_candidate_rows=np.asarray(candidate_rows, np.int64))
    path = (Path(output_dir) if output_dir is not None else HERE/'games') / f'game-{game:03d}.npz'
    check_data_pins(pins)
    if not sources_match(pins['sources']):
        raise RuntimeError('workspace source drift during game; refusing publication')
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix('.partial.npz')
    ScriptedGameDemonstration(public, controls, metadata, execution).save(tmp)
    load_corpus(tmp)
    tmp.replace(path)
    result = dict(game=game, seed=seed, seat=seat, role=role, style=style, decisions=n-1, backend=backend,
        gamedata_sha256=provenance['gamedata_sha256'],
        labels=sum(queried), teacher_waits=sum(q and a == noop for q,a in zip(queried,labels)),
        teacher_executions=sum(mixed), playable_teacher_executions=sum(m and q for m,q in zip(mixed,queried)),
        rejected_executions=sum(not a for a in accepted),
        outcome='draw' if env.battle.winner is None else 'win' if env.battle.winner == seat else 'loss',
        planner_cpu_s=planner_cpu, planner_wall_s=planner_wall,
        total_cpu_s=time.process_time()-cpu_started, wall_s=time.perf_counter()-started,
        npz_sha256=sha(path), bytes=path.stat().st_size, end_tick=env.battle.tick)
    write_json(path.with_suffix('.json'), result)
    log(dict(event='game_done', **result))
    return result


def collect(start, stop):
    cfg = config()
    torch.set_num_threads(1)
    loaded = ev.load_policy_checkpoint(INITIAL, device=DEVICE, decks_path=TRAINING)
    pins = json.loads((HERE / 'preflight.json').read_text())
    if any(pins['config'][key] != value for key, value in cfg.model_dump().items()):
        raise RuntimeError('pilot configuration drift')
    check_data_pins(pins)
    if not sources_match(pins['sources']) or sha(INITIAL) != pins['initial_sha256']:
        raise RuntimeError('workspace/checkpoint source drift since preflight')
    for game in range(start, min(stop, cfg.games)):
        budget()
        path = HERE / 'games' / f'game-{game:03d}.npz'
        if path.exists():
            receipt = json.loads(path.with_suffix('.json').read_text())
            if receipt.get('gamedata_sha256') != pins['gamedata_sha256'] or receipt.get('backend') != 'native':
                raise ValueError('refusing a noncanonical or non-native collection receipt')
            if sha(path) != receipt['npz_sha256']:
                raise ValueError('corpus hash mismatch')
            load_corpus(path)
            continue
        collect_game(game, loaded, cfg)


def preflight():
    if not (COUNCIL/'GAMEDATA_CANONICAL_READY').is_file():
        raise RuntimeError('wait for canonical gamedata marker before preflight')
    canonical = json.loads((HERE/'canonical-data.json').read_text())
    if sha(ROOT/'gamedata.json') != canonical['gamedata_sha256']:
        raise RuntimeError('canonical data receipt mismatch')
    check_native_pins()
    cfg = config()
    torch.set_num_threads(1)
    loaded = ev.load_policy_checkpoint(INITIAL, device=DEVICE, decks_path=TRAINING)
    engine = json.loads((COUNCIL / 'engine-speed/results/stage0_engine_sources.json').read_text())
    matches = {name: sha(ROOT/'src'/name) == value['after'] for name,value in engine.items()}
    if not all(matches.values()):
        raise RuntimeError(f'Stage 0 source mismatch: {matches}')
    if loaded.model.config.public_contract_version != 4 or loaded.model.config.dropout != 0:
        raise ValueError('expected public-v4 zero-dropout student')
    env = setup(loaded, TRAINING, cfg.collection_seed, 0)
    with torch.no_grad():
        state = loaded.model.initial_state(1, device=DEVICE)
        torch.manual_seed(18)
        action, next_state, mask, _ = ev._policy_step(loaded, env, 0, state=state,
            previous_action=env.action_space.no_op_action, previous_reward=0.,
            episode_start=True, deterministic=False, device=DEVICE)
        packet = project(loaded.builder.build_actor(env.battle, 0))
        public_mask = PublicActionMaskBuilder(loaded.builder).build(PublicActionMaskInput.from_confidence_observation(packet))
        torch.manual_seed(18)
        action2, next2 = actor_policy_action(loaded.model, packet, public_mask,
            state=state, previous_action=env.action_space.no_op_action, previous_reward=0.,
            episode_start=True, deterministic=False, device=DEVICE, observation_builder=loaded.builder)
    assert np.array_equal(mask, public_mask) and action == action2
    assert all(torch.equal(a,b) for a,b in zip(next_state,next2))
    receipt = dict(config=cfg.model_dump(), initial_sha256=sha(INITIAL), sources=source_hashes(),
        stage0_source_matches=matches, actor_eval_parity=True, torch_version=torch.__version__,
        runtime=str(ROOT), python=sys.executable, engine='workspace-python',
        planner_backend='native', gamedata_sha256=canonical['gamedata_sha256'],
        training_sha256=sha(TRAINING), hog_sha256=sha(HOG), pid=os.getpid())
    gamedata = ROOT/'gamedata.json'
    write_json(HERE/'data-provenance.json', dict(gamedata_sha256=sha(gamedata),
        gamedata_mtime_ns=gamedata.stat().st_mtime_ns,
        gamedata_predates_preflight=gamedata.stat().st_mtime_ns < time.time_ns()))
    write_json(HERE/'preflight.json', receipt)
    log({k:v for k,v in receipt.items() if k != 'sources'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['preflight', 'collect'])
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--stop', type=int, default=40)
    args = parser.parse_args()
    if args.command == 'preflight': preflight()
    else: collect(args.start, args.stop)
