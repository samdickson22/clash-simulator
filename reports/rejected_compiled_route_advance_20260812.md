# Rejected: compiled route-node advancement

Date: 2026-08-12. Current verified stack: `16a1125`.

The candidate moved only the pure integer normalization/projection inside
`advance_native_ground_route` to the existing optional Numba layer. Python
retained the established coordinate-to-logic-unit quantization, and the exact
Python helper remained the no-Numba fallback. There were no card or deck
branches.

Twenty thousand randomized fixed-point comparisons per seed across five seeds,
the fallback test, and 45 route/path tests passed. The fixed scalar/off,
shadow, and optimized/on rollout hashes matched, with zero shadow mismatches.
On 200,000 direct inputs, the compiled helper took 0.01935 seconds versus
0.10416 seconds for Python (5.38x faster).

The production workloads did not justify the added compiled boundary:

- exact depth-6/32-simulation oracle, seed/planner 9057/2057, 2 states and 11
  alternating pairs: +0.431% paired median, 9/11 positive, bootstrap mean 95%
  CI -0.876% to +0.705%, identical complete digest
  `99da3a3c24136401d8f625d9a81a09b44dad81dd94dcdb2444a654539efa83b2`;
- stationary-random rollout, 4 environments x 32 decisions, 24 warmup,
  21 alternating pairs: +0.081% paired median, 12/21 positive, ratio of medians
  -0.067%, CI -2.757% to +0.138%, identical rollout digest
  `3b56f9367cc8fa8de7cccf935cfbdd5332363f10b84c50e09b51fe473f4ebabc`.

All candidate source, tests, and benchmark-driver changes were removed. No
commit was made.
