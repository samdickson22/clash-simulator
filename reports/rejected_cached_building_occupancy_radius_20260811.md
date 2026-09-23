# Rejected cached building occupancy radius

Date: 2026-08-11

## Candidate

Store the data-driven building collision radius on each entity at spawn and
reuse it in exact point-occupancy and troop-placement-mask queries instead of
reading the card compatibility wrapper repeatedly. The candidate preserved
the query's distinct `collision_radius or 1.0` fallback, including `None` and
zero values, and did not alter fixed-point geometry.

## Machine and protocol

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `d6a117f`
- one process, `nice -n 15`, one Torch/BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no Clasher training, evaluation, or MPS
  process was active during timing
- fixed seeds and alternating paired order, 11 repetitions

Oracle command:

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison building-occupancy-radius --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --engine-fast-path on
```

Stationary rollout command, once for `strategy` and once for `random`:

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison building-occupancy-radius --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

## Evidence

| Workload | Reference median | Candidate median | Paired median | Mean 95% bootstrap CI | Positive pairs | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| oracle, labels/s | 2.888 | 2.891 | -0.036% | -0.514% to +0.188% | 5/11 | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| balanced strategy, decisions/s | 186.466 | 186.680 | +0.272% | +0.041% to +0.974% | 8/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random, decisions/s | 171.084 | 171.656 | +0.192% | -0.449% to +0.918% | 7/11 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The candidate passed seven focused fallback and off/shadow/on fixed-seed
digest checks, and every timed pair produced identical hashes with zero
shadow mismatches. It was nevertheless rejected: the oracle point estimate
was negative, the random confidence interval crossed zero, and the only
positive screen was too small to justify another entity field and duplicated
fallback invariant. Source, test, and benchmark-driver changes were removed.
