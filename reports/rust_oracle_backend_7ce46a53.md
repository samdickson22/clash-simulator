# Resident Rust oracle backend attribution

Date: 2026-08-13

Baseline provenance: optimized Python simulator in this isolated worktree at
`7ce46a53`, with the accepted reward profiles ported in `96cc8605`. The Rust
candidate includes `a8c817cb` state keys, `ae0c4bdf` leaf projections, and the
resident action/tick primitives through `2b27f4f3`.

Command:

```text
PYTHONPATH=src:. uv run python scripts/perf/benchmark_rust_oracle_backend.py \
  --repetitions 10 --warmups 2
```

The workload is one fixed-depth oracle label with 32 simulations, depth 6,
96 sampled actions, and 8 logic ticks per decision. Runs alternated Python and
Rust order. Both arms used the same fixed battle/planner seeds and a deck whose
complete reachable hand/cycle closure passes the resident fail-closed gate.
The timed Rust arm includes resident construction at label entry. No workers,
MPS, GPU, training, or corpus process ran.

Results:

- Python mean: 1.1728475543 seconds per label
- Resident Rust mean: 0.0438189709 seconds per label
- Paired mean speedup: 26.7657x
- Paired bootstrap 95% CI: 26.2985x to 27.2611x
- Selected actions: player 0 = 124, player 1 = 37
- Backup trace SHA-256: `11d8234a6cf5c24ad1e492fe9537c4727c440f9cba7cd006c632d62802fc9bc7`
- Action/backup mismatches: 0

This clears the 20% evidence gate for the declared supported resident closure.
It is not yet a general production-deck acceptance claim: unsupported cards
still fall back before planner RNG consumption, and mixed-deck coverage plus
12-worker end-to-end corpus attribution remain required.
