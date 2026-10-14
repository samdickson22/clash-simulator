"""Train rext-rlppo with RoyaleLearn's own trainer (Learner -> LearningCoordinator, PPO, ladder).

Runs in the learnvenv on 127x08 (torch 2.7.1+cu118 for driver 470), from the clasher-bot root:

    /mpac/sdicks02/repos/clasher-bot-rsim/learnvenv/bin/python -m bot.players.rext_train \
        --save-dir /mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r1 --total-steps 30000000

Learner's documented settings (quickstart/training-an-agent pages, opponent="self": mirror
battles, past selves from its pool, and its scripted bots), with one change: the rollout source.
Learner fixes `inline` (all battles in the learner process); this sets RoyaleLearn's own
process farm (RolloutConfig's default source, `workers` processes x `games_per_worker`
battles), so the battles use more than one core. Environment: bot.players.rext_envs.build_env.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--save-dir', required=True)
    ap.add_argument('--total-steps', type=int, default=30_000_000)
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--games-per-worker', type=int, default=32)
    ap.add_argument('--inline', action='store_true', help="Learner's own single-process rollouts")
    ap.add_argument('--overlap', action='store_true', help='RolloutConfig.overlap: collect the next batch under the update')
    ap.add_argument('--device', default='auto')
    ap.add_argument('--threads', type=int, default=8)
    ap.add_argument('--steps-per-update', type=int, default=16_384)
    ap.add_argument('--checkpoint-every', type=int, default=500_000)
    ap.add_argument('--batch-size', type=int, default=4096, help='decisions per optimizer step')
    ap.add_argument('--epochs', type=int, default=2)
    ap.add_argument('--channels', type=int, default=64)
    ap.add_argument('--blocks', type=int, default=4)
    ap.add_argument('--policy-lr', type=float, default=2e-4)
    ap.add_argument('--critic-lr', type=float, default=2e-4)
    ap.add_argument('--ent-coef', type=float, default=0.01, help='<0: RoyaleLearn default schedule 0.01 -> 0.003')
    ap.add_argument('--seed', type=int, default=20261014)
    ap.add_argument('--eval-workers', type=int, default=2, help='RolloutConfig.eval_workers (gate games)')
    ap.add_argument('--candidate-every', type=int, default=0, help='>0: LadderConfig.candidate_every_env_steps')
    ap.add_argument('--gate-games', type=int, default=0, help='>0: GateConfig.champion_games (eval_seed_count = half)')
    ap.add_argument('--all-scripted', action='store_true', help="league's scripted share: all six RoyaleGym rungs")
    ap.add_argument('--vram-fraction', type=float, default=None, help='cap on the GPU share (shared cards)')
    ap.add_argument('--ram-budget-mb', type=int, default=24_000)
    a = ap.parse_args()
    from royalelearn import Learner
    from royalelearn import config as cfg
    from bot.players.rext_envs import build_env
    learner = Learner(
        build_env,
        n_envs=a.games_per_worker,
        opponent='self',
        device=a.device,
        threads=a.threads,
        **({} if a.vram_fraction is None else {'vram_fraction': a.vram_fraction}),
        trunk_channels=a.channels,
        trunk_blocks=a.blocks,
        steps_per_update=a.steps_per_update,
        ppo_batch_size=a.batch_size,
        ppo_minibatch_size=min(4096, a.batch_size),
        ppo_epochs=a.epochs,
        policy_lr=a.policy_lr,
        critic_lr=a.critic_lr,
        ppo_ent_coef=None if a.ent_coef < 0 else a.ent_coef,
        checkpoint_every=a.checkpoint_every,
        n_checkpoints_to_keep=50,
        timestep_limit=a.total_steps,
        seed=a.seed,
        save_dir=a.save_dir,
    )
    if not a.inline:
        learner._settings['rollout'] = cfg.RolloutConfig(
            source='process', workers=a.workers, games_per_worker=a.games_per_worker, shards_per_worker=2,
            overlap=a.overlap, eval_workers=a.eval_workers)
    import msgspec
    ladder = learner._settings['ladder']
    if a.candidate_every > 0:
        ladder = msgspec.structs.replace(ladder, candidate_every_env_steps=a.candidate_every)
    if a.gate_games > 0:
        ladder = msgspec.structs.replace(ladder, eval_seed_count=a.gate_games // 2,
                                         gate=msgspec.structs.replace(ladder.gate, champion_games=a.gate_games))
    if a.all_scripted:
        from royalelearn.rollout.scripted import SCRIPTED_NAMES
        ladder = msgspec.structs.replace(ladder, scripted_opponents=tuple(f'scripted:{n}' for n in SCRIPTED_NAMES))
    learner._settings['ladder'] = ladder
    # The start-up RAM gate defaults to 6.5 GB (a laptop); 127x08 has 125 GB, ~78 GB available.
    learner._settings['doctor'] = cfg.DoctorConfig(ram_budget_mb=a.ram_budget_mb)
    Path(a.save_dir).mkdir(parents=True, exist_ok=True)
    (Path(a.save_dir) / 'rext_train_args.json').write_text(json.dumps(dict(vars(a), pid=os.getpid()), indent=1))
    learner.learn()
    learner.save(str(Path(a.save_dir) / 'bot'))


if __name__ == '__main__':
    main()
