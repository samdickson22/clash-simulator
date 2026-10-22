"""Offline maximum-shape GPU allocation probe. No games, rollout or saved policy.

The input is synthetic and has all capped token axes present. Two optimizer
steps include allocated AdamW moments. This measures one live microbatch and
the frozen anchor, not whole-rollout host memory or actor resource admission.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

ANCHORS = {
    'S100': '74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f',
    'M': '947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4',
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def guard():
    available = int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                         if s.startswith('MemAvailable:')))*1024
    require(os.getpriority(os.PRIO_PROCESS, 0) >= 10 and available >= 32*2**30
            and os.getloadavg()[0] <= 90, 'host admission requires nice10, 32GiB available and load <=90')


def synthetic(batch, device):
    import numpy as np
    import torch
    from bot.pretrain_v1 import featurize as F, rl_learner as L
    from bot.pretrain_v1.model import tiles_ok_np
    arrays = {}
    for key, (dtype, shape) in L._FEATURES.items():
        base = key.removesuffix('_mask')
        width = (L._CAPS[base], *shape[1:]) if base in L._CAPS else shape
        arrays[key] = np.zeros((batch, *width), dtype=dtype)
    for key in L._CAPS:
        arrays[key+'_mask'][:] = True
    arrays['ent'][..., F.E_CARD] = 2
    arrays['ev'][..., F.V_CARD] = 2
    arrays['ev'][..., F.V_PRESENT] = 1
    arrays['rev'][..., F.R_CARD] = 2
    arrays['rev'][..., F.R_PRESENT] = 1
    hand = arrays['hand']
    hand[..., F.H_CARD] = 2
    hand[..., F.H_PLACE] = 1
    hand[..., F.H_AFFORD] = 1
    hand[:, :4, F.H_LEGAL] = 1
    arrays['slot_ok'][:] = True
    arrays['alive'][:] = True
    arrays['glob'][:, F.G_TICK] = 90
    legal = tiles_ok_np(hand, arrays['slot_ok'], arrays['alive'])
    return {k: torch.from_numpy(v).to(device) for k, v in arrays.items()}, torch.from_numpy(legal).to(device)


def run(a, result):
    guard()
    import torch
    from bot.pretrain_v1 import rl_learner as L, rl_math
    require(torch.__version__.startswith('2.7.1'), 'require pinned Torch2.7.1')
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1, 'expose exactly one CUDA device')
    torch.set_num_threads(1)
    budget = 43.5*2**30
    total = torch.cuda.get_device_properties(0).total_memory
    free, _ = torch.cuda.mem_get_info()
    require(total >= budget and free >= budget, 'GPU requires full43.5GiB free admission budget')
    torch.cuda.set_per_process_memory_fraction(budget/total)
    require(hashlib.sha256(a.anchor.read_bytes()).hexdigest() == ANCHORS[a.size], 'selected BC file SHA mismatch')
    checkpoint = torch.load(a.anchor, map_location='cpu', weights_only=False)
    cfg = checkpoint['cfg']
    expected = {'S100': (192, 4, 6, 576), 'M': (320, 6, 8, 1280)}[a.size]
    require(tuple(cfg[k] for k in ('d', 'layers', 'heads', 'ffn')) == expected
            and cfg.get('drop', 0.) == 0. and (cfg['n_cards'], cfg['n_bodies']) == (124, 183),
            'exact selected model shape required')
    source = hashlib.sha256()
    for p in sorted((ROOT/'bot/pretrain_v1').rglob('*.py')):
        source.update(str(p.relative_to(ROOT)).encode()+b'\0'+p.read_bytes())
    manifest = dict(scope='synthetic-maxshape-allocation-only', source_sha256=source.hexdigest(),
                    native_sha256='358cf506031bde59519fbb7ec59f07d3823112311b8d3192dbebd7a8871ef144',
                    gamedata_sha256='ccd2a5f18f49e23ad316d8ffecd32278fe9994fcdc74936c7410223b2faef756',
                    actor_source_sha256='43c20b2df9880af8634e1cd3efefb8ae369e3dad615af7f75bc830b59a9c6583')
    config = L.LearnerConfig(seed=L.SEEDS[0], size=a.size, microbatch=a.microbatch,
                            test_only=True, precision='float64')
    learner = L.Learner(a.anchor, anchor_sha256=ANCHORS[a.size], model_cfg=cfg,
                        runtime_manifest=manifest, config=config, device='cuda:0')
    learner.update_index = 3  # Local synthetic probe only. No update or checkpoint is admitted.
    learner._set_trainable()
    del checkpoint
    b, legal = synthetic(a.microbatch, learner.device)
    action = torch.full((a.microbatch,), 2304, dtype=torch.int64, device=learner.device)
    dt = torch.full_like(action, 5)
    actor = torch.ones_like(action, dtype=torch.bool)
    advantages = torch.linspace(-1, 1, a.microbatch, device=learner.device, dtype=torch.float64)
    torch.cuda.reset_peak_memory_stats()
    result.update(source=manifest, model_cfg=cfg, torch=str(torch.__version__), device=torch.cuda.get_device_name(),
                  dtype='float64', synthetic=True, generated_environment_steps=0, optimizer_steps=[])
    for step in range(2):
        guard()
        start = time.monotonic()
        learner.optimizer.zero_grad(set_to_none=True)
        g, t, value = learner._forward(b, legal)
        with torch.no_grad():
            ag, at, _ = learner._forward(b, legal, anchor=True)
        logp, entropy = rl_math.joint_terms(g, t, action, dt)
        kl = rl_math.joint_kl(g, t, ag, at)
        sums = rl_math.ppo_sums(logp, logp.detach(), advantages, value,
                               torch.zeros_like(value), entropy, kl, actor)
        loss = (.5*sums['value']+sums['policy']-.001*sums['entropy']+.05*sums['kl'])/2048
        require(bool(torch.isfinite(loss)), 'nonfinite synthetic loss')
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(learner.model.parameters(), 1., error_if_nonfinite=True)
        learner.optimizer.step()
        torch.cuda.synchronize()
        reserved = torch.cuda.max_memory_reserved()
        require(reserved <= budget, 'reserved memory exceeds admission budget')
        result['optimizer_steps'].append(dict(step=step+1, seconds=time.monotonic()-start,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=reserved,
            loss=float(loss.detach()), gradient_norm=float(norm)))
        del g, t, value, ag, at, logp, entropy, kl, sums, loss, norm
    result.update(status='pass', cpu_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  capped_axes=L._CAPS, anchor_sha256=ANCHORS[a.size])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--size', choices=tuple(ANCHORS), required=True)
    ap.add_argument('--anchor', type=Path, required=True)
    ap.add_argument('--microbatch', type=int, choices=(128, 256), required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--test-only', action='store_true', required=True)
    a = ap.parse_args()
    require(not a.out.exists(), 'fresh output required; preserve earlier failures')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='failed', size=a.size, microbatch=a.microbatch, scope='offline-synthetic-memory-only')
    spec = importlib.util.spec_from_file_location('maxshape_backend', Path(__file__).with_name('qualify_fp64.py'))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    import torch
    try:
        with helper.math_backend(torch):
            run(a, result)
    except BaseException as ex:
        result['error'] = repr(ex)
        raise
    finally:
        with a.out.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')


if __name__ == '__main__':
    main()
