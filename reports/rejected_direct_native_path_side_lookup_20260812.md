# Rejected direct native path-side lookup

The immutable standard path map is an exact horizontal two-lane mirror. An
exhaustive candidate proved that the no-other-object nearest path ID is lane 1
for every source half-cell left of the center split and lane 2 otherwise. It
retained the full reference scan for other-object center-crossing ties and
matched the reference for every standard cell plus a two-cell perimeter.

The current bounded LRU still incurred 146 cold cell misses and 46 ms in an
initial three-label profile, but the production-shaped alternating benchmark
correctly retained the process-global cache across repetitions. Once warm, the
direct formula did not improve exact oracle throughput:

- cached: 0.879035 s median, 3.41283 labels/s;
- direct: 0.879688 s median, 3.41030 labels/s;
- paired median: +0.0153%, 6/11 positive;
- paired-mean 95% bootstrap interval: -0.1208% to +0.3334%;
- ratio of median rates: -0.0743%;
- exact digest for every row:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.

The candidate was rejected before rollout timing because it only moves cold
startup work and adds a second engine path without a steady-state gain. Source,
tests, and benchmark-driver changes were removed and verified byte-identical to
`ec7a652`. Raw output: `/tmp/direct_native_path_side_oracle.json`.
