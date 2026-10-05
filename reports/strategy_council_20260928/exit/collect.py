"""Collect complete public histories from the acting policy-assisted search player."""
import argparse
from datetime import datetime, timezone
import json
import os
import time
from common import *
from clasher.rl.imitation import CorpusMetadata, CORPUS_SCHEMA_VERSION, load_corpus
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_action_mask import PublicActionMaskInput
from clasher.rl.scripted_demonstrations import ScriptedGameDemonstration

@torch.no_grad()
def game(ctx, resources, iteration, number, output):
    started = time.perf_counter(); cfg = config()
    seed = cfg.collection_seed + iteration*100000000 + (number//2)*1009
    seat = number % 2; role = 'hog26' if (number//2)%3 == 0 else 'training'
    style = STYLES[int(np.random.default_rng(seed+17).integers(3))]
    env, decks = reset(ctx, role, seed, seat)
    planner = PublicPlanner(resources, json.loads(TRAIN_DECKS.read_text()), k=1, seed=seed*2+seat+7919, policy=True)
    observations, masks, labels, prev, queried = [], [], [], [], []
    executed, ticks, accepted, ids, scores, rows = [], [], [], [], [], []
    prior = resources.no_op; max_wall = 0.; search_cpu = 0.
    for decision in range(1300):
        info = observe(env, seat); calls = planner.calls
        t = time.perf_counter(); cpu = time.process_time()
        action, mask = planner.decide(info, decision)
        max_wall = max(max_wall, time.perf_counter()-t)
        searched = planner.calls != calls
        if searched:
            search_cpu += time.process_time()-cpu
            ids.extend(planner.last['candidates']); scores.extend(planner.last['scores'])
            rows.extend([decision]*len(planner.last['candidates']))
            assert action in planner.last['candidates']
        assert mask[action]
        observations.append(info.packet); masks.append(mask); labels.append(action)
        prev.append(prior); queried.append(searched); executed.append(action); ticks.append(info.tick)
        other = observe(env, 1-seat).packet
        omask = resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(other))
        other_action = int(ctx.bot(style).select_action(other))
        with maybe_silence_stdio(True):
            _, done, step = env.step({seat:action, 1-seat:other_action}, pre_action_masks={seat:mask, 1-seat:omask})
        accepted.append(bool(step.action_success[seat])); prior = action
        if done: break
    else: raise RuntimeError('incomplete game')
    assert env.battle.game_over
    packet = observe(env, seat).packet
    observations.append(packet); masks.append(resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet)))
    labels.append(resources.no_op); prev.append(prior); queried.append(False)
    n = len(labels); starts = np.zeros(n, bool); starts[0] = True
    public = PublicPolicySequence.from_observations(ctx.loaded.builder, observations)
    controls = dict(action_masks=np.asarray(masks, bool), expert_actions=np.asarray(labels, np.int64),
        previous_actions=np.asarray(prev, np.int64), previous_rewards=np.zeros(n, np.float32),
        episode_starts=starts, episode_ids=np.full(n, number, np.int64), expert_action_supervision_valid=np.asarray(queried, bool))
    provenance = dict(role='training', family_id=role, complete_game=True, teacher='srp-pub-pol',
        backend='native', iteration=iteration, seed=seed, seat=seat, opponent_style=style, k=1, plan_every=2)
    metadata = CorpusMetadata(schema_version=CORPUS_SCHEMA_VERSION, created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed, decisions=n-1, samples=n, decision_interval=5, max_ticks=6001, planner_depth=1,
        planner_simulations=1, planner_action_samples=8, max_entities=ctx.loaded.builder.max_entities,
        token_names=ctx.loaded.builder.token_names, reward_profile=env.reward_profile,
        behavior_checkpoint=str(previous(iteration)), expert_probability=1., label_source='public-script',
        label_strategy='srp-pub-pol', public_contract_version=4, public_history_slots=4, public_seen_card_slots=8,
        provenance=json.dumps(provenance))
    execution = dict(submitted_actions=np.asarray(executed, np.int64), submitted_ticks=np.asarray(ticks, np.int64),
        accepted_commands=np.asarray(accepted, bool), root_candidate_ids=np.asarray(ids, np.int64),
        root_candidate_values=np.asarray(scores, np.float64), root_candidate_rows=np.asarray(rows, np.int64))
    verify(); output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix('.partial.npz')
    if tmp.exists(): tmp.unlink()  # Only this worker's unpublished interrupted game.
    ScriptedGameDemonstration(public, controls, metadata, execution).save(tmp)
    _, a = load_corpus(tmp)
    assert a['terminal_status'][-1] == 1 and np.array_equal(a['previous_actions'][1:], execution['submitted_actions'])
    tmp.replace(output)
    outcome = 'draw' if env.battle.winner is None else 'win' if env.battle.winner == seat else 'loss'
    rec = dict(**provenance, game=number, decisions=n-1, labels=sum(queried), outcome=outcome,
        score={'win':1.,'draw':.5,'loss':0.}[outcome], rejected_plays=sum(not ok and a != resources.no_op for ok,a in zip(accepted,executed)),
        checkpoint_sha256=sha(previous(iteration)), manifest_sha256=sha(HERE/'manifest.json'), npz_sha256=sha(output),
        wall_s=time.perf_counter()-started, search_cpu_s=search_cpu, decision_wall_max=max_wall, pid=os.getpid())
    write_json(output.with_suffix('.json'), rec); log(rec)
    return rec

def main():
    p = argparse.ArgumentParser(); p.add_argument('--iteration', type=int, required=True)
    p.add_argument('--worker', type=int, default=0); p.add_argument('--workers', type=int, default=3)
    p.add_argument('--smoke', action='store_true'); args = p.parse_args()
    verify(); ctx = Context(previous(args.iteration)); resources = Resources(ctx)
    out = HERE/'smoke' if args.smoke else folder(args.iteration)/'games'
    for number in range(args.worker, 2 if args.smoke else config().games, args.workers):
        path = out/f'game-{number:03d}.npz'
        if path.exists() and path.with_suffix('.json').exists():
            rec = json.loads(path.with_suffix('.json').read_text())
            assert sha(path) == rec['npz_sha256'] and rec['checkpoint_sha256'] == sha(previous(args.iteration))
            continue
        game(ctx, resources, args.iteration, number, path)
if __name__ == '__main__': main()
