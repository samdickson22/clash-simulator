# Rejected: unused avoidance unit-mass import

Date: 2026-08-12

Line profiling found an unused per-call local import of `unit_mass` in native
avoidance; the function consumes `Entity.get_unit_mass()` instead. Removing
the import was semantically inert and all fixed hashes matched, but it failed
production-shaped rollout attribution.

Oracle: seed 9103, planner 2103, two states, depth 6, 32 simulations, 64 action
samples, 8-tick steps, 11 alternating pairs, one process/thread, `nice -n 10`.

- imported: 0.868684 seconds, 2.30233 labels/s
- skipped: 0.865050 seconds, 2.31201 labels/s
- ratio gain +0.420%; paired median +0.392%; 11/11 positive
- paired mean 95% CI +0.232% to +0.615%
- digest `8f995c8b54e22b99bf793b6ca5fe46fc0898c3228ff895e81adf84882eefb328`

Stationary screens used four environments x 24 decisions, four warmup
decisions, 15 alternating pairs, defense-v2, optimized/on, one Torch thread.

| workload | imported decisions/s | skipped decisions/s | ratio gain | paired median | positive | paired mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| random | 194.4647 | 194.6885 | +0.115% | +0.093% | 8/15 | -0.398% to +1.769% | `cae070e827037e73d68d925c23686fed9cc4d0ab18f8191ab3a24e05d983e542` |
| balanced strategy | 180.5647 | 180.5248 | -0.022% | +0.222% | 8/15 | -0.773% to +1.982% | `6211780bd186466f59f08c9d2bbe9f4871687dce945b6144f782dd6b8f50db0d` |

Because strategy medians regressed and neither rollout confidence interval
excluded zero, all source and benchmark-driver hunks were removed. No commit
was created.
