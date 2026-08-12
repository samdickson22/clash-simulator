# Query-local dense bucket bindings

## Change

The exact dense spatial scan repeatedly resolved
`self._entity_bucket_grid` and `out.extend` inside its row/column loop.
`iter_entities_in_radius()` now binds the stable grid and list method once per
query. Bounds, row-major bucket order, returned list ownership, and the final
native object-ID sort are unchanged. The change is shared by targeting,
collision, and avoidance and contains no card/deck special case.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process at `nice -n 15`; BLAS/OpenMP/VecLib limited to one thread
- fixed seed 9015; planner seed 2015; alternating reference/candidate order

| workload | repeated attributes | local bindings | ratio of medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Exact Oracle, depth 6 / 32 sims / 64 samples, 3 labels, 11 pairs | 1.038376 s / 2.88913 labels/s | 1.033027 s / 2.90409 labels/s | +0.5178% | +0.5142% | 9/11 | +0.1425% to +0.5755% | `19c7358db1063eac95c329c9b1100d92e7bae07411a344e7b7608cc711a09232` |
| Random stationary, 4 envs x 32 steps, 15 pairs | 0.686963 s / 186.327 d/s | 0.684112 s / 187.104 d/s | +0.4167% | +0.4679% | 11/15 | +0.1642% to +1.5382% | `199b5152f2ac6e1f97ba393ac741d7251c8b1cd11ba932a9d7f1d187592eef5b` |
| Balanced strategy, 4 envs x 32 steps, 15 pairs | 0.684521 s / 186.992 d/s | 0.683746 s / 187.204 d/s | +0.1132% | +0.1258% | 10/15 | -0.0047% to +0.2241% | `087fb5355b0bbf1cbca392bb8492997912266f19cab248c5118989b640b0f0a4` |

The strategy result is exact and non-negative but its confidence interval
crosses zero; no strategy-throughput gain is claimed.

Commands:

```bash
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison local-dense-bucket-bindings --states 3 --repetitions 11 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 9015 --planner-seed 2015 \
  --engine-fast-path on

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison local-dense-bucket-bindings --workload random --seed 9015 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

The strategy command replaces `--workload random` with `--workload strategy
--strategy balanced`.

## Exactness

- Unit coverage compares the complete returned object lists and identity order
  across arena edges, populated cells, empty cells, narrow scans, and whole-map
  radii.
- Attribute/local Oracle action/state/planner-RNG digests match exactly.
- Seed 9015, 64-decision attribute/local scalar/off, shadow, and optimized/on
  hashes all equal
  `83c0a2309c6f997dac11f93ee2eb279275c873c91a673fc9c23284691ec11ada`.
- The pinned seed-8831 shadow hash remains
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`
  in both modes, with one comparison and zero mismatches each.

Raw outputs:

- `/tmp/local_dense_bucket_bindings_oracle.json`
- `/tmp/local_dense_bucket_bindings_random.json`
- `/tmp/local_dense_bucket_bindings_strategy.json`
