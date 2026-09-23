# Rejected: rebuilding derived caches during BattleState clone

The candidate deep-copied only core mutable battle state and rebuilt entity
buckets, alive-building membership, tower masks, and target arrays in the
clone. It preserved exact oracle actions/state digest and passed 29 focused
clone/cache evolution and isolation tests, but the performance evidence was
flat and did not justify the substantially larger manual snapshot path.

Machine and controls matched the accepted optimizer benchmarks: Apple M4 Pro,
single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread, fixed seeds and
alternating order.

- Tower-only 51-pair clone microprobe: +0.323% paired median; copied median
  0.3481 ms, rebuilt median 0.3495 ms.
- Production-shaped oracle screen, 3 labels, 5 pairs: +0.372% paired median,
  +0.217% paired mean, only 3/5 positive, mean bootstrap CI
  -0.275% to +0.723%.
- Reference and candidate digest:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.

Raw screen: `/tmp/rebuilt_clone_caches_oracle_screen.json`.

All candidate changes to `battle.py` and the oracle benchmark driver were
removed. The accepted `62e49a2` stack remains unchanged.
