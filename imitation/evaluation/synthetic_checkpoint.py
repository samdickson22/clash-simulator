"""Create an explicitly random, full-size plumbing checkpoint with real assets."""
import argparse
from dataclasses import asdict
from pathlib import Path
import torch
from .paths import setup
setup()
from imitation.model.network import ModelConfig, SetPolicy
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.structured_obs import build_canonical_tile_features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    torch.set_num_threads(1)
    torch.manual_seed(68174001)
    b = ContractV5ObservationBuilder()
    c = ModelConfig()
    m = SetPolicy(c, torch.from_numpy(b.card_stat_features),
                  torch.from_numpy(build_canonical_tile_features()),
                  torch.from_numpy(b.card_stat_features[:, 0]*10))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(dict(config=asdict(c), model=m.state_dict(), ema=m.state_dict(),
                    plumbing_only=True, hashes={'token_sha256': b.pinned_tokens.sha256},
                    provenance='RANDOM INITIALIZATION: PLUMBING ONLY; NO OUTCOME CLAIMS'), args.output)


if __name__ == '__main__':
    main()
