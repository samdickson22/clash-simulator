"""Full CPU feature-building + top-k latency; synthetic inputs clearly labelled."""
import argparse
import json
import os
import platform
import time
from pathlib import Path
import numpy as np
import torch
from .inference import Policy, load_policy
from .network import ModelConfig
from .synthetic import model, packet


def bench(policy, iterations=1000, entities=25):
    p, d = packet(entities)
    for _ in range(30):
        policy.propose(p, d)
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        proposals = policy.propose(p, d)
        times.append((time.perf_counter_ns()-start)/1e6)
    return {"entities": entities, "iterations": iterations, "p50_ms": float(np.median(times)),
            "p99_ms": float(np.percentile(times, 99)), "max_ms": max(times), "k": len(proposals)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint"); p.add_argument("--tile-width", type=int, default=128)
    p.add_argument("--iterations", type=int, default=1000); p.add_argument("--output", required=True)
    args = p.parse_args()
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    torch.manual_seed(1)
    policy = load_policy(args.checkpoint) if args.checkpoint else Policy(model(ModelConfig(tile_width=args.tile_width)))
    result = {"host": platform.node(), "torch": torch.__version__, "threads": 1,
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "synthetic_inputs": True,
              "random_weights": not bool(args.checkpoint),
              "parameters": sum(p.numel() for p in policy.model.parameters()),
              "measurements": [bench(policy, args.iterations, n) for n in (10, 25, 64)]}
    Path(args.output).write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
