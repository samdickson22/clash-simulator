"""rext-bc: RoyaleImitate behaviour cloning of IL_Replay human play (royaleimitate.clone).

Runs in the learnvenv from the clasher-bot root, on shards from rext_imitate_replays (merged).
The network is rext_imitate_ppo.make_learner's (RoyaleLearn default 32ch x 2, as rext-rlppo r4),
so the clone is the PPO fine-tune's warm_start.init. `clone` itself is RoyaleImitate's plain
behaviour cloning: masked cross-entropy weighted by the rows' weights, AdamW, cosine schedule,
early stopping on the by-battle validation split; it writes an actor artifact with probe rows
plus policy.json/environment.json, so Learner.load_policy and rext_policy.load_actor read it.

    learnvenv/bin/python -m bot.players.rext_imitate_clone --shards O/merged/<key> --out CLONE
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shards', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--epochs', type=int, default=20)
    ap.add_argument('--batch-size', type=int, default=256)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--patience', type=int, default=3)
    ap.add_argument('--cache', default='auto')
    ap.add_argument('--vram-fraction', type=float, default=0.45)
    ap.add_argument('--threads', type=int, default=8)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(a.threads)
    from royaleimitate import clone
    from bot.players.rext_imitate_ppo import make_learner
    with tempfile.TemporaryDirectory() as scratch:
        learner = make_learner(scratch, vram_fraction=a.vram_fraction, threads=a.threads)
        cache = {'false': False, 'none': None}.get(a.cache.lower(), a.cache)
        digest = clone(learner, a.shards, a.out, epochs=a.epochs, batch_size=a.batch_size,
                       learning_rate=a.lr, patience=a.patience, cache=cache)
    (Path(a.out).parent / (Path(a.out).name + '.digest.json')).write_text(json.dumps({'sha256': digest, **vars(a)}))
    print('DIGEST', digest, flush=True)


if __name__ == '__main__':
    main()
