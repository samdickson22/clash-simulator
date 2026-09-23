# Rejected specialized `Position` deepcopy

Date: 2026-08-12

Candidate: add a memo-aware `Position.__deepcopy__` that preserves subclasses,
dynamic attributes, mutable extension isolation, and repeated-reference aliasing.

The direct clone microbenchmark used three fixed snapshots, 300 clones per row,
15 alternating pairs, seed 2301, and the exact optimized clone stack at
`7c01854`. It improved the paired median by 4.2235% (15/15 positive; bootstrap
mean 95% CI +4.1289% to +10.0234%). Median clone throughput changed from
2890.03 to 3016.39 clones/s.

The production-shaped fixed-depth oracle rejected the candidate:

```text
PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison position-deepcopy --states 3 --repetitions 11 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 2301 --planner-seed 901 \
  --engine-fast-path on
```

Median oracle throughput changed from 3.61889 to 3.60047 labels/s. The paired
median was -0.5330%, only 1/11 pairs improved, and the bootstrap mean 95% CI was
-0.8043% to -0.2961%. Both modes produced the identical digest
`72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.

Conclusion: the direct clone gain does not survive production planner work.
The source, test, and benchmark switch were removed; this report is retained to
avoid repeating the rejected allocation tradeoff.
