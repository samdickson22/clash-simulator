"""Offline qualification only. No registered training budget or precision admission.

Capture exactly one engine game, then check its actual Session samples on a chosen
learner device. All outputs are fresh, source-gated, and local to this worktree.
"""
from contextlib import contextmanager
from dataclasses import asdict
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT/'bot/pretrain_v1'


def source_digest():
    h = hashlib.sha256()
    for p in sorted(PACKAGE.rglob('*.py')):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def guard():
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:')))*1024
    if os.getpriority(os.PRIO_PROCESS, 0) < 10 or available < 29*2**30 or os.getloadavg()[0] > 90:
        raise RuntimeError('require nice >= 10, MemAvailable >= 29 GiB and load1 <= 90')


@contextmanager
def math_backend(torch):
    """Explicit qualification settings; restore caller policy on exit."""
    old = (torch.backends.mha.get_fastpath_enabled(), torch.backends.cuda.flash_sdp_enabled(),
           torch.backends.cuda.mem_efficient_sdp_enabled(), torch.backends.cuda.math_sdp_enabled())
    torch.backends.mha.set_fastpath_enabled(False)
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    try:
        yield
    finally:
        torch.backends.mha.set_fastpath_enabled(old[0])
        torch.backends.cuda.enable_flash_sdp(old[1])
        torch.backends.cuda.enable_mem_efficient_sdp(old[2])
        torch.backends.cuda.enable_math_sdp(old[3])


def origins():
    result = {n: str(Path(m.__file__).resolve()) for n, m in sys.modules.items()
              if n.startswith('bot.pretrain_v1') and getattr(m, '__file__', None)}
    assert result and all(PACKAGE in Path(p).parents for p in result.values()), result
    return result


def close_maps(chunk):
    for a in [*chunk.features.values(), *(getattr(chunk, k) for k in
               ('action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt'))]:
        if getattr(a, '_mmap', None) is not None:
            a._mmap.close()


def capture(a, out):
    # Use the candidate bootstrap: its package root is derived from __file__.
    # Loading the old immutable bootstrap would override the candidate package.
    spec = importlib.util.spec_from_file_location('fp64_bootstrap', PACKAGE/'checks/check_ours_producer.py')
    q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q)
    rt, lineage = q.bootstrap(a.runtime.resolve(), a.actor_source.resolve(), a.manifest.resolve())
    import numpy as np
    import torch
    from bot.pretrain_v1 import stream_actor as A, rl_learner as L
    from bot.pretrain_v1.sim_ours import bind_matches
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    torch.set_num_threads(a.threads)
    ck = torch.load(a.anchor, map_location='cpu', weights_only=False)
    manifest = dict(native_sha256=rt.pins['native_sha256'], gamedata_sha256=rt.pins['gamedata_sha256'],
                    actor_source_sha256=lineage['actor_manifest_sha256'],
                    runtime_source_sha256=lineage['runtime_manifest_sha256'],
                    candidate_source_sha256=a.source_sha256, precision='float64', scope='offline-qualification-only',
                    torch_version=str(torch.__version__), numpy_version=np.__version__,
                    attention='mha_fastpath=False,flash=False,mem_efficient=False,math=True',
                    actor_threads=str(a.threads))
    # Keep the registered budget in the constructor; this capture never calls update.
    config = L.LearnerConfig(seed=L.SEEDS[0], size=a.size, test_only=True, precision='float64')
    learner = L.Learner(a.anchor, anchor_sha256=a.anchor_sha256, model_cfg=ck['cfg'],
                        runtime_manifest=manifest, config=config)
    queue = A.AtomicChunkQueue(out/'queue', max_bytes=256*2**20, max_chunks=32, runtime_manifest=manifest)
    receipts, chunks = [], []

    def publish(c, boundary):
        guard()
        receipt = queue.write(c)
        mapped = queue.load(receipt, expected_version=c.version, expected_policy_sha256=learner.policy_sha256)
        try:
            L.validate_chunk(L.Chunk(**vars(mapped)), config=config, version=c.version,
                             anchor_sha256=learner.anchor_sha256, policy_sha256=learner.policy_sha256,
                             provenance_sha256=learner.provenance_sha256, model_cfg=learner.model.cfg)
        finally:
            close_maps(mapped)
        receipts.append(asdict(receipt))
        (out/'receipts.json').write_text(json.dumps(receipts, indent=2)+'\n')
        chunks.append(dict(rows=c.generated_steps, boundary=boundary.reason, terminal=bool(c.terminated[-1]),
                           reward=float(c.reward.sum()), bootstrap=c.bootstrap,
                           boundary_declined=c.boundary_declined_steps))
        return A.PolicyUpdate(c.version, c.policy_sha256)

    own = A.StreamingPolicyOursPlayer(learner.model, publish, actor_id='fp64-qualification-'+a.size,
             seed=config.seed, anchor_sha256=learner.anchor_sha256, provenance_sha256=learner.provenance_sha256,
             opponent_id='R3a-readiness', budget_steps=4000, quota_steps=4000, chunk_rows=128)
    levels = dict(Skeletons=8, Musketeer=7, IceGolem=7, Cannon=9, Fireball=8, Zap=9, IceSpirit=8, HogRider=10)
    players = {0: own, 1: make_player(rt, 'R3a')}
    with math_backend(torch), bind_matches(players):
        game = play_match(rt, players, seed=a.game_seed, decks=[list(levels), list(levels)],
                          levels=dict(cards={0: levels, 1: levels}, towers={0: 9, 1: 9}, planner='l11'), verbose=True)
    assert game['terminal'] and own.completed_games == 1
    assert own.discarded_steps == 0 and own.published_steps == own.generated_steps
    assert game['channels'][0]['rejected'] == 0
    # No fixed FP32 trajectory, row count, outcome, or number of nominal deadlines.
    assert chunks[-1]['terminal'] and chunks[-1]['bootstrap'] == 0.
    q.check_origins(a.runtime.resolve(), a.actor_source.resolve())
    return dict(game=game, generated=own.generated_steps, published=own.published_steps,
                discarded=own.discarded_steps, boundary_declined=own.boundary_declined_steps, chunks=chunks,
                provenance=manifest, config=config.record(), model_cfg=ck['cfg'], policy_sha256=learner.policy_sha256,
                anchor_sha256=learner.anchor_sha256, origins=origins())


def check(a, out):
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import torch
    from bot.pretrain_v1 import stream_actor as A, rl_learner as L, rl_math
    torch.set_num_threads(a.threads)
    captured = json.loads((a.capture/'result.json').read_text())
    assert captured['status'] == 'pass' and captured['source_sha256'] == a.source_sha256
    assert captured['anchor_sha256'] == a.anchor_sha256
    assert captured['config']['size'] == a.size and captured['config']['dtype'] == 'float64'
    assert captured['provenance']['torch_version'] == str(torch.__version__), 'match actor/learner torch'
    queue = A.AtomicChunkQueue(a.capture/'queue', max_bytes=256*2**20, max_chunks=32,
                              runtime_manifest=captured['provenance'])
    ck = torch.load(a.anchor, map_location='cpu', weights_only=False)
    config = L.LearnerConfig(seed=L.SEEDS[0], size=a.size, test_only=True, precision='float64')
    learner = L.Learner(a.anchor, anchor_sha256=a.anchor_sha256, model_cfg=ck['cfg'],
                        runtime_manifest=captured['provenance'], config=config, device=a.device)
    chunks = [L.Chunk(**vars(queue.load(A.Receipt(**r), expected_version=0,
                          expected_policy_sha256=learner.policy_sha256)))
              for r in json.loads((a.capture/'receipts.json').read_text())]
    try:
        checked = [L.validate_chunk(c, config=config, version=0, anchor_sha256=learner.anchor_sha256,
                    policy_sha256=learner.policy_sha256, provenance_sha256=learner.provenance_sha256,
                    model_cfg=learner.model.cfg) for c in chunks]
        arrays = [b for b, _ in checked]
        vectors = {k: np.concatenate([v[k] for _, v in checked]) for k in checked[0][1]}
        vectors['action'] = vectors['action'].astype(np.int64, copy=False)
        offsets = np.r_[0, np.cumsum([c.generated_steps for c in chunks])]
        results = {}
        with math_backend(torch), torch.no_grad():
            for batch in (128, 256):
                guard()
                le = ve = 0.
                for start in range(0, int(offsets[-1]), batch):
                    ix = np.arange(start, min(int(offsets[-1]), start+batch))
                    b, legal = learner._batch(arrays, offsets, ix)
                    g, t, value = learner._forward(b, legal, declined=learner._tensor(vectors['boundary_declined'], ix))
                    logp, _ = rl_math.joint_terms(g, t, learner._tensor(vectors['action'], ix), learner._tensor(vectors['dt'], ix))
                    le = max(le, float((logp.double()-learner._tensor(vectors['old_logp'], ix)).abs().max()))
                    ve = max(ve, float((value.double()-learner._tensor(vectors['old_value'], ix)).abs().max()))
                results[str(batch)] = dict(rows=int(offsets[-1]), max_logp_error=le, max_value_error=ve,
                                           pass_gate=le <= 2e-6 and ve <= 2e-6)
        assert all(r['pass_gate'] for r in results.values()), results
        update = None
        if a.update_fixture:
            # Explicit 256-row fixture, never the registered 262144 x 32 run.
            # Whole original chunks retain authentic bootstraps and chronology.
            fixture = chunks[:2]
            assert [c.generated_steps for c in fixture] == [128, 128]
            cfg = L.LearnerConfig(seed=config.seed, size=a.size, microbatch=128, steps_per_update=256,
                                  updates=1, batch_size=256, test_only=True, precision='float64')
            small = L.Learner(a.anchor, anchor_sha256=a.anchor_sha256, model_cfg=ck['cfg'],
                              runtime_manifest=captured['provenance'], config=cfg, device=a.device)
            guard()
            with math_backend(torch):
                update = small.update(fixture)
            assert update['warmup'] and update['optimizer_steps'] == 2
            assert L.policy_sha256(small.anchor, small.feature_hash) == small._anchor_state_sha256
            small.save_checkpoint(out/'fixture-checkpoint.pt')
            restored = L.Learner(a.anchor, anchor_sha256=a.anchor_sha256, model_cfg=ck['cfg'],
                                  runtime_manifest=captured['provenance'], config=cfg, device=a.device)
            restored.load_checkpoint(out/'fixture-checkpoint.pt')
            assert restored.policy_sha256 == small.policy_sha256
        return dict(batches=results, fixture_update=update, config=config.record(), origins=origins(),
                    device=a.device, torch_version=str(torch.__version__), threads=a.threads,
                    anchor_sha256=learner.anchor_sha256, policy_sha256=learner.policy_sha256,
                    peak_reserved_bytes=torch.cuda.max_memory_reserved() if a.device == 'cuda' else None)
    finally:
        for c in chunks:
            close_maps(c)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    sub.add_parser('source-digest')
    for mode in ('capture', 'check'):
        cmd = sub.add_parser(mode)
        cmd.add_argument('--source-sha256', required=True)
        cmd.add_argument('--anchor', type=Path, required=True)
        cmd.add_argument('--anchor-sha256', required=True)
        cmd.add_argument('--size', choices=['S100', 'M'], required=True)
        cmd.add_argument('--threads', type=int, choices=[1, 4], default=1)
        cmd.add_argument('--out', type=Path, required=True)
        if mode == 'capture':
            cmd.add_argument('--runtime', type=Path, required=True)
            cmd.add_argument('--actor-source', type=Path, required=True)
            cmd.add_argument('--manifest', type=Path, required=True)
            cmd.add_argument('--game-seed', type=int, required=True)
        else:
            cmd.add_argument('--capture', type=Path, required=True)
            cmd.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
            cmd.add_argument('--update-fixture', action='store_true')
    a = p.parse_args()
    if a.mode == 'source-digest':
        print(source_digest())
        return
    guard()
    assert a.source_sha256 == source_digest(), 'candidate source changed'
    assert hashlib.sha256(a.anchor.read_bytes()).hexdigest() == a.anchor_sha256, 'selected anchor changed'
    out = a.out.resolve()
    assert ROOT/'qualification-artifacts' in out.parents and a.source_sha256 in out.parts
    out.mkdir(parents=True, exist_ok=False)
    os.environ['NUMBA_CACHE_DIR'] = str(out/'numba-cache')
    start = time.monotonic()
    result = dict(status='failed', source_sha256=a.source_sha256, mode=a.mode)
    try:
        result.update((capture if a.mode == 'capture' else check)(a, out))
        assert a.source_sha256 == source_digest(), 'candidate source changed during run'
        assert hashlib.sha256(a.anchor.read_bytes()).hexdigest() == a.anchor_sha256, 'source anchor changed during run'
        result['status'] = 'pass'
    except BaseException as ex:
        result['error'] = repr(ex)
        raise
    finally:
        result['seconds'] = time.monotonic()-start
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
