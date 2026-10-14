"""rext-bcppo: RoyaleLearn PPO fine-tuned from the RoyaleImitate human clone (rext-bc).

Runs in the learnvenv from the clasher-bot root. The Learner is rext_train.py's r4 setup (the
best from-scratch run: RoyaleLearn default net 32ch x 2, 65536 steps/update, batch 2048 x 3
epochs, lr 5e-4, default entropy schedule, opponent "self" league with all six scripted rungs,
gate every 4M env steps, 200 games), on rext_envs.build_env, plus RoyaleImitate's two sections:

- warm_start.init: the actor starts from the clone (artifact digest checked, probe self-test);
  warm_start.actor_lr_scale: the actor is held still (scale 0) for the first --freeze env steps
  while the fresh critic learns the clone's values, then trains at full rate;
- imitation: a reference_kl regulariser KL(clone || policy) on the choice rows, held to
  --kl-budget nats by RoyaleImitate's adaptive coefficient (start --kl-coef, max 10).

`make_learner` is also what rext_imitate_clone uses, so the clone's network is this run's.

    learnvenv/bin/python -m bot.players.rext_imitate_ppo --save-dir J --init CLONE_DIR \
        --total-steps 60000000 --workers 23 --overlap
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

R4 = dict(channels=32, blocks=2, steps_per_update=65536, batch_size=2048, epochs=3, policy_lr=5e-4,
          critic_lr=5e-4, ent_coef=-1.0, games_per_worker=32, checkpoint_every=2_000_000, seed=20261014)


def make_learner(save_dir, *, channels=R4['channels'], blocks=R4['blocks'], games_per_worker=32,
                 steps_per_update=R4['steps_per_update'], batch_size=R4['batch_size'], epochs=R4['epochs'],
                 policy_lr=R4['policy_lr'], critic_lr=R4['critic_lr'], ent_coef=R4['ent_coef'],
                 checkpoint_every=R4['checkpoint_every'], total_steps=None, seed=R4['seed'], device='auto',
                 threads=4, vram_fraction=None, extensions=None, head_float32=False, autocast=None):
    import msgspec
    from royalelearn import Learner
    from bot.players.rext_envs import build_env
    learner = Learner(
        build_env,
        n_envs=games_per_worker,
        opponent='self',
        device=device,
        threads=threads,
        **({} if vram_fraction is None else {'vram_fraction': vram_fraction}),
        trunk_channels=channels,
        trunk_blocks=blocks,
        steps_per_update=steps_per_update,
        ppo_batch_size=batch_size,
        ppo_minibatch_size=min(4096, batch_size),
        ppo_epochs=epochs,
        policy_lr=policy_lr,
        critic_lr=critic_lr,
        ppo_ent_coef=None if ent_coef < 0 else ent_coef,
        checkpoint_every=checkpoint_every,
        n_checkpoints_to_keep=50,
        timestep_limit=total_steps,
        seed=seed,
        save_dir=save_dir,
        extensions=extensions,
    )
    # A cloned actor is far more peaked than a seeded one, and under the bf16 policy head the
    # rollout's and the update's logits round apart by more than ppo.ratio_atol (bcppo-r1 died
    # at update 5: ratio deviation 0.0056 > 0.005). The head in float32 is RoyaleLearn's own
    # remedy; both fields are actor-neutral (nets.ACTOR_NEUTRAL_FIELDS), so the clone still loads.
    net = learner._settings['net']
    if head_float32:
        net = msgspec.structs.replace(net, policy_head_float32=True)
    if autocast:
        net = msgspec.structs.replace(net, autocast_dtype=autocast)
    learner._settings['net'] = net
    return learner


def league(learner, *, workers, games_per_worker, overlap, eval_workers, candidate_every, gate_games,
           ram_budget_mb):
    """rext_train.py's r4 league and rollout settings."""
    import msgspec
    from royalelearn import config as cfg
    from royalelearn.rollout.scripted import SCRIPTED_NAMES
    learner._settings['rollout'] = cfg.RolloutConfig(
        source='process', workers=workers, games_per_worker=games_per_worker, shards_per_worker=2,
        overlap=overlap, eval_workers=eval_workers)
    ladder = learner._settings['ladder']
    ladder = msgspec.structs.replace(ladder, candidate_every_env_steps=candidate_every,
                                     eval_seed_count=gate_games // 2,
                                     gate=msgspec.structs.replace(ladder.gate, champion_games=gate_games),
                                     scripted_opponents=tuple(f'scripted:{n}' for n in SCRIPTED_NAMES))
    learner._settings['ladder'] = ladder
    learner._settings['doctor'] = cfg.DoctorConfig(ram_budget_mb=ram_budget_mb)


def imitation_extensions(init, *, freeze, kl_budget, kl_coef, anchor=True, self_test_atol=None):
    """`self_test_atol`: the clone's probe rows were recorded on the GPU under TF32; a run in
    plain float32 (--no-tf32) reproduces them to ~3e-5, not the default 1e-5, and says so here."""
    from royaleimitate.artifacts import artifact_digest
    art = {'path': str(init), 'sha256': artifact_digest(init)}
    atol = {} if self_test_atol is None else {'self_test_atol': float(self_test_atol)}
    ext = {'warm_start': {'init': {**art, **atol}}}
    if freeze > 0:
        ext['warm_start']['actor_lr_scale'] = {'kind': 'piecewise', 'points': [[0, 0.0], [int(freeze), 1.0]]}
    if anchor:
        ext['imitation'] = {
            'references': {'clone': {'kind': 'snapshot', **art, **atol}},
            'regularisers': [{'kind': 'reference_kl', 'name': 'clone', 'reference': 'clone',
                              'budget': {'kind': 'constant', 'value': float(kl_budget)},
                              'coef': {'start': float(kl_coef)}}],
        }
    return ext


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--save-dir', required=True)
    ap.add_argument('--init', required=True, help='the clone folder (rext_imitate_clone --out)')
    ap.add_argument('--total-steps', type=int, default=60_000_000)
    ap.add_argument('--workers', type=int, default=23)
    ap.add_argument('--games-per-worker', type=int, default=32)
    ap.add_argument('--overlap', action='store_true')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--eval-workers', type=int, default=10)
    ap.add_argument('--candidate-every', type=int, default=4_000_000)
    ap.add_argument('--gate-games', type=int, default=200)
    ap.add_argument('--vram-fraction', type=float, default=0.45)
    ap.add_argument('--ram-budget-mb', type=int, default=40_000)
    ap.add_argument('--freeze', type=int, default=1_000_000, help='env steps with the actor held still')
    ap.add_argument('--kl-budget', type=float, default=0.1, help='nats per choice row (RoyaleImitate default 0.1)')
    ap.add_argument('--kl-coef', type=float, default=1.0)
    ap.add_argument('--no-anchor', action='store_true')
    ap.add_argument('--policy-lr', type=float, default=R4['policy_lr'])
    ap.add_argument('--ent-coef', type=float, default=R4['ent_coef'])
    ap.add_argument('--head-float32', action='store_true', help='net.policy_head_float32 (see make_learner)')
    ap.add_argument('--autocast', default=None, help='net.autocast_dtype override, e.g. float32')
    ap.add_argument('--self-test-atol', type=float, default=None, help='warm_start/reference probe self-test tolerance')
    ap.add_argument('--no-tf32', action='store_true',
                    help='plain float32 on the GPU: under TF32 a cloned (peaked) actor broke the 0.005 tf32 ratio '
                         'tolerance (bcppo-r2: 0.0059); without it RoyaleLearn asserts the float32 1e-4')
    a = ap.parse_args()
    if a.no_tf32:
        import torch
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
    ext = imitation_extensions(a.init, freeze=a.freeze, kl_budget=a.kl_budget, kl_coef=a.kl_coef,
                               anchor=not a.no_anchor, self_test_atol=a.self_test_atol)
    learner = make_learner(a.save_dir, games_per_worker=a.games_per_worker, total_steps=a.total_steps,
                           threads=a.threads, vram_fraction=a.vram_fraction, policy_lr=a.policy_lr,
                           ent_coef=a.ent_coef, extensions=ext, head_float32=a.head_float32,
                           autocast=a.autocast)
    league(learner, workers=a.workers, games_per_worker=a.games_per_worker, overlap=a.overlap,
           eval_workers=a.eval_workers, candidate_every=a.candidate_every, gate_games=a.gate_games,
           ram_budget_mb=a.ram_budget_mb)
    Path(a.save_dir).mkdir(parents=True, exist_ok=True)
    (Path(a.save_dir) / 'rext_imitate_ppo_args.json').write_text(
        json.dumps(dict(vars(a), pid=os.getpid(), extensions=ext), indent=1))
    learner.learn()
    learner.save(str(Path(a.save_dir) / 'bot'))


if __name__ == '__main__':
    main()
