"""Capture before editing; tests compare these numerical and serialization receipts."""
from pathlib import Path
import copy, hashlib, io, json, runpy, sys
import numpy as np
import torch
from clasher.rl.train_recurrent import compute_gae, ppo_update, parse_args
ROOT = Path(__file__).resolve().parent

def tiny_update():
    torch.set_num_threads(1)
    np.random.seed(711)
    module = runpy.run_path('tests/test_council_ppo_contract.py')
    model, rollout, *_ = module['collected'].__wrapped__()
    # The second window has a nonempty full prefix.
    from clasher.rl.train_recurrent import collect_rollout
    _, _, state, env, builder = model, rollout, *_[0:3]
    rollout, *_ = collect_rollout(envs=[env], builder=builder, model=model,
        device=torch.device('cpu'), rollout_steps=4, recurrent_state=state,
        previous_actions=rollout.actions[:,-1], previous_rewards=np.zeros(2,dtype=np.float32),
        episode_starts=np.zeros(2,dtype=bool), quiet_engine=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, eps=1e-5)
    adv, returns = compute_gae(rollout, gamma=1., gae_lambda=.95)
    stats = ppo_update(model=model, optimizer=optimizer, rollout=rollout,
        advantages=adv, returns=returns, device=torch.device('cpu'), epochs=2,
        sequence_batch_size=1, clip_ratio=.2, value_coef=.5, entropy_coef=.01,
        hand_aux_coef=.02, elixir_aux_coef=.05, target_kl=0.)
    old = sys.argv; sys.argv = ['trainer']
    try: args = vars(parse_args())
    finally: sys.argv = old
    payload = dict(model=model.state_dict(), optimizer=optimizer.state_dict(), stats=stats,
                   torch_rng=torch.get_rng_state(), numpy_rng=np.random.get_state(), args=args)
    return payload

if __name__ == '__main__':
    target = ROOT/'results/default-reference.pt'
    if target.exists(): raise SystemExit('reference already exists')
    result = tiny_update()
    torch.save(result, target)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'before').glob('*.py')}
    (ROOT/'results/reference-provenance.json').write_text(json.dumps(dict(source_sha256=files,
        torch=torch.__version__, numpy=np.__version__, reference_sha256=hashlib.sha256(target.read_bytes()).hexdigest()), indent=2))
    print(result['stats'])


def tiny_bc(imitation, output_dir, **options):
    from dataclasses import fields
    import tempfile
    module = runpy.run_path('tests/test_council_ppo_contract.py')
    model, rollout, _, _, builder = module['collected'].__wrapped__()
    arrays = {f.name: getattr(rollout, f.name).reshape((12, *getattr(rollout, f.name).shape[2:])).copy()
              for f in fields(rollout) if isinstance(getattr(rollout, f.name), np.ndarray)
              and getattr(rollout, f.name).shape[:2] == (2,6)}
    arrays['episode_ids'] = np.repeat(np.arange(2), 6)
    arrays['expert_actions'] = np.full(12, 2304, dtype=np.int64)
    arrays['action_masks'][:, 2305] = True  # two choices even at match opening
    arrays['expert_action_supervision_valid'] = np.ones(12,dtype=bool)
    arrays['expert_action_supervision_valid'][[5,11]] = False
    arrays['terminal_status'] = np.zeros(12,dtype=np.int64)
    arrays['terminal_status'][[5,11]] = 1
    metadata = imitation.CorpusMetadata(schema_version=imitation.CORPUS_SCHEMA_VERSION,
        created_at='reference', seed=289, decisions=12, samples=12, decision_interval=5,
        max_ticks=100, planner_depth=0, planner_simulations=0, planner_action_samples=0,
        max_entities=32, token_names=builder.token_names, public_contract_version=4,
        provenance='{"role":"training"}')
    old_load = imitation.load_corpus
    imitation.load_corpus = lambda _: (metadata, arrays)
    try:
        manifest = imitation.fit_imitation_corpus(corpus_path=Path('synthetic-reference.npz'),
            output_checkpoint=output_dir/'bc.pt', control_checkpoint=output_dir/'control.pt',
            decks_path=Path('decks.json'), seed=711, epochs=1, batch_size=4,
            learning_rate=1e-4, validation_fraction=.5, device=torch.device('cpu'),
            d_model=32, num_heads=4, actor_layers=1, critic_layers=1, memory_size=48,
            sequence_length=options.pop('sequence_length',3), model_config_override=model.config, **options)
    finally: imitation.load_corpus = old_load
    return dict(checkpoint=torch.load(output_dir/'bc.pt',weights_only=False),
                control=torch.load(output_dir/'control.pt',weights_only=False),
                torch_rng=torch.get_rng_state(), numpy_rng=np.random.get_state())
