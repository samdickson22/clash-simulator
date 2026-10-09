"""Allocator hygiene only: preserve math/RNG while releasing unused CUDA pages."""
import sys
from pathlib import Path


def main():
    source = Path(sys.argv[sys.argv.index('--source')+1])
    sys.path.insert(0, str(source))
    from imitation.model import train
    import torch
    step = train.optimizer_step
    def bounded_step(*args, **kwargs):
        torch.cuda.empty_cache()
        result = step(*args, **kwargs)
        torch.cuda.empty_cache()
        return result
    train.optimizer_step = bounded_step
    from train_scan import main as scan
    scan()


if __name__ == '__main__':
    main()
