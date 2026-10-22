"""New-data offline FP64 fixture: 3 critic warmups, 1 PPO, fresh Session parity.

Run as a file, before importing bot. No registered launch, engine resume or
precision admission. Every invocation requires a new output directory.
"""
import argparse
import copy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT/'bot/pretrain_v1'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load_helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKAGE/'checks'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Q = load_helper('ppo_fp64_contract', 'qualify_fp64.py')


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def bootstrap(a):
    """Restore the caller's visibility before the first CUDA query, or fail closed.

    Runtime imports torch and creates CPU resources. The reviewed bootstrap stays
    untouched. No CUDA availability query belongs between hiding and restoring.
    """
    visibility = os.environ.get('CUDA_VISIBLE_DEVICES')
    helper = load_helper('ppo_engine_bootstrap', 'check_ours_producer.py')
    rt, lineage = helper.bootstrap(a.runtime.resolve(), a.actor_source.resolve(), a.manifest.resolve())
    require(len(lineage['files']) == 9409 and len(lineage['source_files']) == 17010,
            'full pinned runtime and actor manifest required')
    import torch
    require(not torch.cuda.is_initialized() and getattr(torch.cuda, '_cached_device_count', None) is None,
            'bootstrap touched CUDA; visibility cannot safely change')
    if visibility is None:
        os.environ.pop('CUDA_VISIBLE_DEVICES', None)
    else:
        os.environ['CUDA_VISIBLE_DEVICES'] = visibility
    return rt, lineage, helper, dict(cuda_initialized=False, cuda_device_count_cached=False,
                                    restored_cuda_visible_devices=visibility)


def parity(learner, chunks, *, batches=(128, 256), padded=False):
    """Compare immutable actual Session labels; optionally add masked padding only."""
    import numpy as np
    import torch
    from bot.pretrain_v1 import rl_learner as L, rl_math
    checked = [L.validate_chunk(c, config=learner.config, version=learner.version,
               anchor_sha256=learner.anchor_sha256, policy_sha256=learner.policy_sha256,
               provenance_sha256=learner.provenance_sha256, model_cfg=learner.model.cfg) for c in chunks]
    arrays = [b for b, _ in checked]
    if padded:
        # Separate invariance probe, never passed to update or counted as new data.
        arrays = [{k: v for k, v in b.items()} for b in arrays]
        for b in arrays:
            for key, cap in L._CAPS.items():
                width = min(cap, b[key].shape[1]+7)
                for name in (key, key+'_mask'):
                    source = b[name]
                    b[name] = np.pad(source, [(0, 0), (0, width-source.shape[1])]+[(0, 0)]*(source.ndim-2))
    vectors = {k: np.concatenate([v[k] for _, v in checked]) for k in checked[0][1]}
    vectors['action'] = vectors['action'].astype(np.int64, copy=False)
    offsets = np.r_[0, np.cumsum([c.generated_steps for c in chunks])]
    result = {}
    with torch.no_grad():
        for batch in batches:
            Q.guard()
            le = ve = 0.
            for start in range(0, int(offsets[-1]), batch):
                ix = np.arange(start, min(int(offsets[-1]), start+batch))
                b, legal = learner._batch(arrays, offsets, ix)
                g, t, value = learner._forward(b, legal, declined=learner._tensor(vectors['boundary_declined'], ix))
                logp, _ = rl_math.joint_terms(g, t, learner._tensor(vectors['action'], ix), learner._tensor(vectors['dt'], ix))
                require(bool(torch.isfinite(logp).all() and torch.isfinite(value).all()), 'nonfinite parity')
                le = max(le, float((logp.double()-learner._tensor(vectors['old_logp'], ix)).abs().max()))
                ve = max(ve, float((value.double()-learner._tensor(vectors['old_value'], ix)).abs().max()))
            require(le <= 2e-6 and ve <= 2e-6, f'strict parity failed: {le}, {ve}')
            result[str(batch)] = dict(rows=int(offsets[-1]), max_logp_error=le, max_value_error=ve)
    return result


def memory(torch, device):
    return dict(cpu_process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == 'cuda' else None,
                gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved() if device == 'cuda' else None,
                scope='process RSS high-water; GPU peaks since preceding reset; observed shapes only')


def update_proof(learner, chunks):
    """Use the real learner unchanged and audit gradients, heads and Adam state."""
    import torch
    from bot.pretrain_v1 import rl_learner as L
    warmup = learner.version < 3
    before = {n: p.detach().cpu().clone() for n, p in learner.model.named_parameters()
              if n.startswith(('value.', 'noop.', 'ptr.', 'tile.'))}
    old_policy = learner.policy_sha256
    if learner.device.type == 'cuda':
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    Q.guard()
    start = time.monotonic()
    metrics = learner.update(chunks)
    if learner.device.type == 'cuda':
        torch.cuda.synchronize()
    elapsed = time.monotonic()-start
    heads = {}
    gradients = {}
    for prefix in ('value.', 'noop.', 'ptr.', 'tile.'):
        params = [(n, p) for n, p in learner.model.named_parameters() if n.startswith(prefix)]
        heads[prefix] = any(not torch.equal(before[n], p.detach().cpu()) for n, p in params)
        gradients[prefix] = any(p.grad is not None and bool(p.grad.abs().sum() > 0) for _, p in params)
    require(all(p.grad is None or (p.grad.dtype == torch.float64 and bool(torch.isfinite(p.grad).all()))
                for p in learner.model.parameters()), 'nonfinite or wrong-dtype gradient')
    require(heads['value.'] and gradients['value.'], 'critic did not train')
    require(all(not heads[k] for k in ('noop.', 'ptr.', 'tile.')) if warmup else
            all(heads[k] and gradients[k] for k in ('noop.', 'ptr.', 'tile.')), 'policy-head update proof failed')
    require(old_policy != learner.policy_sha256, 'policy state did not change')
    require(L.policy_sha256(learner.anchor, learner.feature_hash) == learner._anchor_state_sha256,
            'frozen anchor changed')
    states = {}
    for name, p in learner.model.named_parameters():
        s = learner.optimizer.state.get(p)
        expected = 2*learner.version if name.startswith('value.') else 2*max(0, learner.version-3)
        require((s is not None) == bool(expected), 'unexpected optimizer state coverage')
        if s:
            require(all(s[k].dtype == torch.float64 and bool(torch.isfinite(s[k]).all())
                        for k in ('exp_avg', 'exp_avg_sq')), 'Adam moments must be finite FP64')
            require(s['step'].numel() == 1 and float(s['step']) == expected, 'Adam step mismatch')
            states[name] = dict(step=float(s['step']), step_dtype=str(s['step'].dtype),
                               exp_avg_dtype=str(s['exp_avg'].dtype), exp_avg_sq_dtype=str(s['exp_avg_sq'].dtype))
    require(metrics['warmup'] == warmup and metrics['optimizer_steps'] == 2*learner.version,
            'expected exactly two effective-batch optimizer steps per update')
    return dict(metrics=metrics, seconds=elapsed, head_changed=heads, head_nonzero_gradient=gradients,
                gradients_finite=True, anchor_unchanged=True, optimizer=states,
                before_policy_sha256=old_policy, memory=memory(torch, learner.device.type))


class Ledger:
    """One actor's exact rows and game/version continuity, including quota edges."""
    def __init__(self, steps, updates, post_rows):
        self.steps, self.updates, self.post_rows = steps, updates, post_rows
        self.total = 0
        self.rows = [0]*(updates+1)
        self.last = None
        self.games = set()
        self.entries = []
        self.declined = 0

    def accept(self, c, boundary, game, engine_tick):
        from bot.pretrain_v1 import featurize as F
        n, v = c.generated_steps, c.version
        require(0 <= v <= self.updates, 'unexpected version')
        target = self.post_rows if v == self.updates else self.steps
        require(v == min(self.total//self.steps, self.updates), 'version barrier skipped')
        require(0 < n and self.rows[v]+n <= target, 'quota overshoot')
        first, last = map(int, c.features['glob'][[0, -1], F.G_TICK])
        terminal = bool(c.terminated[-1])
        if self.last and not self.last['terminal']:
            require(game == self.last['game'] and first == self.last['last_tick']+F.POLL,
                    'engine game changed or polls lost across barrier')
            if self.last['version'] == v:
                require(abs(self.last['bootstrap']-float(c.old_value[0])) <= 2e-6, 'bootstrap continuity')
        else:
            require(game not in self.games and first == 90, 'replayed or truncated game')
            self.games.add(game)
        self.rows[v] += n
        self.total += n
        self.declined += c.boundary_declined_steps
        budget = self.steps*self.updates+self.post_rows
        quota = target-self.rows[v]
        reason = 'budget' if self.total == budget else 'quota' if quota == 0 else 'terminal' if terminal else 'chunk'
        require(boundary.reason == reason and boundary.generated_steps == self.total
                and boundary.remaining_budget == budget-self.total and boundary.remaining_quota == quota,
                'actor counters differ from exact publication ledger')
        require(boundary.boundary_declined_steps == self.declined, 'boundary-declined counter mismatch')
        require(boundary.terminal == terminal and boundary.unfinished == (reason == 'budget' and not terminal),
                'unfinished budget must have no invented outcome')
        require((last <= engine_tick <= last+F.POLL) if terminal else engine_tick == last+F.POLL,
                'engine tick differs from next-state/terminal tick')
        entry = dict(sequence=len(self.entries), game=game, engine_tick=engine_tick,
                     version=v, policy_sha256=c.policy_sha256, rows=n, first_tick=first, last_tick=last,
                     terminal=terminal, reward=float(c.reward.sum()), bootstrap=float(c.bootstrap),
                     actor_rows=int(c.actor.sum()), forced_rows=n-int(c.actor.sum()),
                     boundary_declined=c.boundary_declined_steps, boundary=asdict(boundary))
        self.entries.append(entry)
        self.last = entry
        return quota == 0


def run(a, out, result):
    rt, lineage, helper, visibility = bootstrap(a)
    Q.guard()
    import numpy as np
    import torch
    from bot.pretrain_v1 import rl_learner as L, stream_actor as A
    from bot.pretrain_v1.model import PolicyV1
    from bot.pretrain_v1.sim_ours import bind_matches
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    torch.set_num_threads(a.threads)
    cfg = json.loads(a.model_cfg.read_text())
    shape = dict(S100=(192, 4, 6, 576), M=(320, 6, 8, 1280))[a.size]
    require(tuple(cfg[k] for k in ('d', 'layers', 'heads', 'ffn')) == shape
            and cfg['drop'] == 0. and (cfg['n_cards'], cfg['n_bodies']) == (124, 183), 'real admitted model shape required')
    manifest = dict(native_sha256=rt.pins['native_sha256'], gamedata_sha256=rt.pins['gamedata_sha256'],
                    actor_source_sha256=lineage['actor_manifest_sha256'],
                    runtime_source_sha256=lineage['runtime_manifest_sha256'], candidate_source_sha256=a.source_sha256,
                    precision='float64', scope='offline-8192-poll-fixture-one-R3a-readiness-only',
                    torch_version=str(torch.__version__), numpy_version=np.__version__,
                    attention='mha_fastpath=False,flash=False,mem_efficient=False,math=True')
    config = L.LearnerConfig(seed=L.SEEDS[0], size=a.size, microbatch=a.microbatch,
                            steps_per_update=2048, updates=4, batch_size=2048, test_only=True, precision='float64')
    learner = L.Learner(a.anchor, anchor_sha256=a.anchor_sha256, model_cfg=cfg,
                        runtime_manifest=manifest, config=config, device=a.device)
    require(learner.policy_sha256 == a.policy_sha256, 'explicit initial FP64 policy SHA mismatch')
    actor_model = PolicyV1(**cfg).double().eval()
    actor_model.load_state_dict({k: v.detach().cpu() for k, v in learner.model.state_dict().items()})
    require(A.policy_sha256(actor_model) == a.policy_sha256, 'actor weights differ')
    ledger = Ledger(2048, 4, 256)
    queue = A.AtomicChunkQueue(out/'queue', max_bytes=512*2**20, max_chunks=2048, runtime_manifest=manifest)
    result.update(config=config.record(), model_cfg=cfg, initial_policy_sha256=a.policy_sha256,
                  model_cfg_sha256=L.manifest_sha256(cfg), source_anchor_dtype='float32', actor_dtype='float64',
                  provenance=manifest, bootstrap_visibility=visibility, updates=[], games=[],
                  publications=ledger.entries, engine_resume_qualified=False)
    pending = []
    game_id = None
    barrier_seconds = 0.
    version_start = time.monotonic()

    def publish(c, boundary):
        nonlocal barrier_seconds, version_start
        Q.guard()
        require(c.policy_sha256 == learner.policy_sha256 and c.version == learner.version, 'stale actor policy')
        require(bool(c.terminated[-1]) == bool(own.battle.game_over), 'terminal differs from actual engine')
        if c.terminated[-1]:
            winner = own.battle.winner
            reward = 0. if winner is None else (1. if winner == own.seat else -1.)
            require(float(c.reward[-1]) == reward, 'reward differs from actual winner')
        complete = ledger.accept(c, boundary, game_id, own.battle.tick)
        receipt = queue.write(c)
        ledger.entries[-1]['receipt'] = asdict(receipt)
        pending.append(receipt)
        write_json(out/'progress.json', result)
        if not complete:
            return A.PolicyUpdate(c.version, c.policy_sha256)
        start = time.monotonic()
        mapped = []
        try:
            mapped = [queue.load(r, expected_version=c.version, expected_policy_sha256=c.policy_sha256) for r in pending]
            chunks = [L.Chunk(**vars(m)) for m in mapped]
            check = parity(learner, chunks)
            if c.version < 4:
                proof = update_proof(learner, chunks)
                proof.update(input_parity=check, observed_widths={k: max(m.features[k].shape[1] for m in mapped)
                              for k in ('ent', 'ev', 'rev')}, rows=ledger.rows[c.version])
                proof['collection_seconds'] = start-version_start
                learner.save_checkpoint(out/f'update-{learner.version}.pt')
                proof['checkpoint_sha256'] = L.file_sha256(out/f'update-{learner.version}.pt')
                result['updates'].append(proof)
            else:
                # Both devices read precisely the same post-PPO Session samples.
                cpu = copy.copy(learner)
                cpu.device = torch.device('cpu')
                cpu.model = actor_model
                require(L.policy_sha256(cpu.model, learner.feature_hash) == learner.policy_sha256, 'post-update CPU weights differ')
                result['post_update'] = dict(rows=256, version=4, policy_sha256=learner.policy_sha256,
                    learner_device=a.device, learner_parity=check, cpu_parity=parity(cpu, chunks),
                    masked_wider_padding_parity=parity(learner, chunks, padded=True),
                    observed_widths={k: max(m.features[k].shape[1] for m in mapped) for k in ('ent', 'ev', 'rev')})
        finally:
            for m in mapped:
                Q.close_maps(m)
            barrier_seconds += time.monotonic()-start
        pending.clear()  # Retain queue artifacts and receipt hashes for independent inspection.
        write_json(out/'progress.json', result)
        Q.guard()
        version_start = time.monotonic()
        return A.PolicyUpdate(learner.version, learner.policy_sha256,
                {k: v.detach().cpu().clone() for k, v in learner.model.state_dict().items()},
                256 if learner.version == 4 else 2048)

    own = A.StreamingPolicyOursPlayer(actor_model, publish, actor_id='offline-ppo-'+a.size,
        seed=config.seed, anchor_sha256=learner.anchor_sha256, provenance_sha256=learner.provenance_sha256,
        opponent_id='R3a-readiness', budget_steps=8448, quota_steps=2048, chunk_rows=128,
        expected_policy_sha256=a.policy_sha256)
    levels = dict(Skeletons=8, Musketeer=7, IceGolem=7, Cannon=9, Fireball=8, Zap=9, IceSpirit=8, HogRider=10)
    start = time.monotonic()
    try:
        with Q.math_backend(torch):
            for sequence in range(a.max_games):
                Q.guard()
                game_id = f'{a.game_seed+sequence}'
                players = {0: own, 1: make_player(rt, 'R3a')}
                # A fresh constructor binding per game; the actor and learner persist.
                with bind_matches(players):
                    try:
                        game = play_match(rt, players, seed=a.game_seed+sequence, decks=[list(levels), list(levels)],
                            levels=dict(cards={0: levels, 1: levels}, towers={0: 9, 1: 9}, planner='l11'), verbose=True)
                    except A.BudgetComplete as ex:
                        require(own.exhausted and ex.generated_steps == 8448, 'unexpected partial budget')
                        result['budget_stop'] = dict(game_id=game_id, generated=ex.generated_steps,
                                                   unfinished=ex.unfinished, terminal_outcome=None)
                        break
                require(game['terminal'], 'nonterminal engine limit cannot be topped up')
                require(game['channels'][0]['rejected'] == 0, 'engine rejected a sampled action')
                rate = 300*game['accepted'][0]/(game['ticks']/20.)
                require(15 <= rate <= 80, 'completed-game play-rate collapse')
                game['accepted_plays_per_300s'] = rate
                result['games'].append(dict(game_id=game_id, **game))
                if own.exhausted:
                    break
    finally:
        result.update(actor=dict(generated=own.generated_steps, published=own.published_steps, discarded=own.discarded_steps,
            completed_games=own.completed_games, unfinished_games=own.unfinished_games, version=own.version,
            boundary_declined=own.boundary_declined_steps, counts=own.counts),
            learner=dict(generated=learner.generated_steps, trained=learner.trained_steps, version=learner.version,
                         optimizer_steps=learner.optimizer_steps), rows_by_version=ledger.rows,
            capture_seconds=time.monotonic()-start-barrier_seconds, barrier_seconds=barrier_seconds,
            memory=memory(torch, a.device), origins=Q.origins())
    require(ledger.rows == [2048]*4+[256] and not pending and 'post_update' in result, 'incomplete fixture')
    require(own.generated_steps == own.published_steps == ledger.total == 8448 and own.discarded_steps == 0,
            'discarded or missing transitions; no replacement permitted')
    require(learner.generated_steps == learner.trained_steps == 8192 and learner.version == 4,
            'learner exact fixture ledger mismatch')
    require(own.completed_games == len(result['games']) and own.completed_games > 0, 'completed-game ledger mismatch')
    result['capture_games_per_hour'] = own.completed_games*3600/result['capture_seconds']
    result['throughput_scope'] = 'one R3a readiness opponent only; excludes barriers; not full registered league'
    helper.check_origins(a.runtime.resolve(), a.actor_source.resolve())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-digest', action='store_true')
    p.add_argument('--test-only', action='store_true')
    for flag in ('source-sha256', 'anchor-sha256', 'policy-sha256'):
        p.add_argument('--'+flag)
    for flag in ('anchor', 'model-cfg', 'runtime', 'actor-source', 'manifest', 'out'):
        p.add_argument('--'+flag, type=Path)
    p.add_argument('--size', choices=('S100', 'M'))
    p.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    p.add_argument('--dtype', choices=('float64',))
    p.add_argument('--threads', type=int, choices=(1, 4), default=1)
    p.add_argument('--microbatch', type=int, choices=(128, 256), default=128)
    p.add_argument('--game-seed', type=int)
    p.add_argument('--max-games', type=int, default=64)
    a = p.parse_args()
    if a.source_digest:
        print(Q.source_digest())
        return
    require(a.test_only and all(getattr(a, k) is not None for k in
            ('source_sha256', 'anchor_sha256', 'policy_sha256', 'anchor', 'model_cfg', 'runtime',
             'actor_source', 'manifest', 'out', 'size', 'game_seed', 'dtype')), 'all explicit pins and --test-only required')
    require(1 <= a.max_games <= 64, 'finite game bound must be 1..64')
    Q.guard()
    require(a.source_sha256 == Q.source_digest(), 'candidate source changed')
    require(hashlib.sha256(a.anchor.read_bytes()).hexdigest() == a.anchor_sha256, 'selected anchor changed')
    out = a.out.resolve()
    require(ROOT/'qualification-artifacts' in out.parents and a.source_sha256 in out.parts
            and a.anchor_sha256 in out.parts, 'output must be new and source/anchor SHA gated inside candidate')
    out.mkdir(parents=True, exist_ok=False)
    os.environ.update(NUMBA_CACHE_DIR=str(out/'numba-cache'), PYTHONDONTWRITEBYTECODE='1')
    result = dict(status='failed', source_sha256=a.source_sha256, anchor_sha256=a.anchor_sha256,
                  scope='test_only 8192 training polls plus 256 post-update polls; no precision admission')
    start = time.monotonic()
    try:
        run(a, out, result)
        require(a.source_sha256 == Q.source_digest(), 'source changed during qualification')
        require(hashlib.sha256(a.anchor.read_bytes()).hexdigest() == a.anchor_sha256, 'anchor file changed during run')
        result['status'] = 'pass'
    except BaseException as ex:
        result['error'] = repr(ex)
        raise
    finally:
        result['seconds'] = time.monotonic()-start
        write_json(out/'result.json', result)


if __name__ == '__main__':
    main()
