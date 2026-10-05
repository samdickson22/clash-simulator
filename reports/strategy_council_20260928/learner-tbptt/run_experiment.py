"""Bounded real-environment PPO comparison using the human checkpoint and public scripts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import time
import tomllib

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
import torch
import clasher

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.parallel_rollout import ActorWorkerConfig, EnvSlot, LocalSlotBackend, BatchedInferenceCollector, OpponentSpec, build_actor_environment
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.train_recurrent import compute_gae, ppo_update, maybe_silence_stdio

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CHECKPOINT = REPO/'reports/strategy_council_20260928/human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'
DECKS = REPO/'reports/strategy_council_20260928/m0/data/roles_v2/training.json'

class Experiment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    label: str
    mode: str = 'full-prefix'
    chunk: int = Field(default=64, ge=1)
    burn_in: int = Field(default=16, ge=0)
    minibatch: int = Field(default=2, ge=1)
    envs: int = Field(default=8, ge=1, le=64)
    rollout_steps: int = Field(default=128, ge=1)
    decisions: int = Field(default=4096, ge=1)
    max_seconds: int = Field(default=570, ge=1)
    seed: int = 2903
    threads: int = Field(default=1, ge=1, le=4)
    critic_warmup: int = Field(default=0, ge=0)
    epochs: int = Field(default=2, ge=1)

class ScriptAdapter:
    def __init__(self, builder, style):
        self.builder = builder
        self.script = PublicScriptedOpponent(builder, style=style)
    def select_action(self, env, player_id, *, action_mask):
        packet = project_council_public_observation(self.builder.build_actor(env.battle, player_id))
        action = self.script.select_action(packet)
        if not action_mask[action]: raise ValueError('public script produced illegal action')
        return action


def run(config_path):
    config = Experiment.model_validate(tomllib.loads(config_path.read_text()))
    from clasher.rl.tbptt import validate_mode
    validate_mode(config.mode,config.chunk,config.burn_in)
    out = ROOT/'runs'/config.label
    out.mkdir(parents=True,exist_ok=False)
    (out/'config.toml').write_bytes(config_path.read_bytes())
    torch.set_num_threads(config.threads)
    torch.manual_seed(config.seed); np.random.seed(config.seed); random.seed(config.seed)
    loaded = load_policy_checkpoint(CHECKPOINT, device=torch.device('cpu'), decks_path=DECKS)
    model, builder = loaded.model, loaded.builder
    optimizer = torch.optim.AdamW(model.parameters(),lr=1e-4,eps=1e-5,weight_decay=1e-5)
    worker = ActorWorkerConfig(decks_path=str(DECKS), token_names=tuple(builder.token_names),
        model_config=model.config.to_dict(),decision_interval=5,max_ticks=6001,mirror_match=False,
        opponent_mode='strategy',opponent_pool=(OpponentSpec(kind='strategy',strategy='balanced'),),
        engine_fast_path='off',quiet_engine=True,base_seed=config.seed,torch_threads=config.threads,
        reward_potential_scale=.05,reward_shaping_gamma=1.,elixir_leak_penalty_scale=0.,
        sampling_decks_path=str(DECKS),learner_sampling_decks_path=str(DECKS),opponent_sampling_decks_path=str(DECKS))
    with maybe_silence_stdio(True):
        envs = [build_actor_environment(worker,i,model.config,builder) for i in range(config.envs)]
    styles = ('balanced','pressure','defense')
    slots = [EnvSlot(env_index=i,env=env,learner_player=i%2,opponent_kind='bot',
                    opponent=ScriptAdapter(builder,styles[i%3])) for i,env in enumerate(envs)]
    backend = LocalSlotBackend(slots, actor_observation_domain=model.config.actor_observation_domain,truncation_bootstrap=True)
    collector = BatchedInferenceCollector(backend,builder=builder,recurrent_update_mode=config.mode,tbptt_burn_in=config.burn_in)
    provenance = dict(pid=os.getpid(), config=config.model_dump(),torch=torch.__version__,
        checkpoint=str(CHECKPOINT),checkpoint_sha256=hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
        source_root=str(Path(clasher.__file__).resolve().parent),
        source_sha256={str(Path('src/clasher')/p.relative_to(Path(clasher.__file__).resolve().parent)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(clasher.__file__).resolve().parent.rglob('*.py')},
        architecture=model.config.to_dict(),opponents=styles,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2))
    started=time.perf_counter(); decisions=0; update=0; wins=losses=draws=0; records=[]
    try:
        with (out/'monitor.jsonl').open('w',buffering=1) as stream:
            while decisions < config.decisions and time.perf_counter()-started < config.max_seconds:
                steps = min(config.rollout_steps, (config.decisions-decisions+config.envs-1)//config.envs)
                t=time.perf_counter()
                rollout=collector.collect(model=model,rollout_steps=steps,policy_version=update,learner_decisions=decisions)
                collect_s=time.perf_counter()-t
                adv,returns=compute_gae(rollout,gamma=1.,gae_lambda=.95)
                t=time.perf_counter()
                stats=ppo_update(model=model,optimizer=optimizer,rollout=rollout,advantages=adv,returns=returns,
                    device=torch.device('cpu'),epochs=config.epochs,sequence_batch_size=config.minibatch,
                    clip_ratio=.2,value_coef=.5,entropy_coef=0.,action_type_entropy_coef=0.,
                    location_entropy_coef=0.,conditional_slot_entropy_coef=.003,hand_aux_coef=.02,
                    elixir_aux_coef=.05,target_kl=.02,critic_only=update<config.critic_warmup,
                    recurrent_update_mode=config.mode,tbptt_chunk=config.chunk,tbptt_burn_in=config.burn_in)
                update_s=time.perf_counter()-t; update+=1; decisions+=rollout.transitions
                wins+=rollout.wins; losses+=rollout.losses; draws+=rollout.draws
                row=dict(update=update,decisions=decisions,transitions=rollout.transitions,
                    collect_seconds=collect_s,update_seconds=update_s,elapsed_seconds=time.perf_counter()-started,
                    update_ms_per_decision=1000*update_s/rollout.transitions,
                    decisions_per_second=rollout.transitions/(collect_s+update_s),
                    wins=rollout.wins,losses=rollout.losses,draws=rollout.draws,
                    cumulative_win_rate=wins/max(1,wins+losses+draws),
                    mean_reward=float(rollout.rewards.mean()),**stats)
                records.append(row); stream.write(json.dumps(row)+'\n'); print(json.dumps(row),flush=True)
        torch.save(dict(format_version=2,model_config=model.config.to_dict(),token_names=builder.token_names,
            model_state_dict=model.state_dict(),optimizer_state_dict=optimizer.state_dict(),
            config=config.model_dump(),total_transitions=decisions),out/'final.pt')
        receipt=dict(completed=decisions>=config.decisions,decisions=decisions,
            elapsed_seconds=time.perf_counter()-started,wins=wins,losses=losses,draws=draws,
            update_ms_per_decision=1000*sum(r['update_seconds'] for r in records)/decisions,
            decisions_per_second=decisions/sum(r['collect_seconds']+r['update_seconds'] for r in records),
            updates=len(records))
        (out/'completion.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt),flush=True)
    finally: collector.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('config',type=Path)
    run(parser.parse_args().config)
