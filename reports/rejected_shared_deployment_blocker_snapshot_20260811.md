# Rejected request-local deployment-blocker snapshot

Date: 2026-08-11

## Candidate

The candidate built the exact live `blocks_deployment` tuple once when two
player masks were requested from one unchanged battle, then supplied that
tuple to both fast mask builds. It used no persistent cache, card names, or
deck-specific behavior. Oracle sampling order, shadow RNG consumption, legal
actions, and action application were unchanged.

The source candidate was removed after attribution because its production
gain was not statistically distinguishable from noise.

## Correctness gates

- 56 focused action-mask, DAgger behavior, structured-policy, observation
  buffer, direct-oracle, planner-exactness, and gather tests passed.
- Pairwise tests proved two reference blocker snapshots versus one candidate
  snapshot while masks were bit-identical, both with no live blocker and with
  a live blocker.
- Fixed-seed environment off/shadow/on masks, NumPy RNG state, and shadow
  metrics matched; shadow mismatches remained zero.
- Fixed-seed oracle actions, battle state, battle RNG, complete planner RNG,
  and pinned default/stable-root traces matched.
- Ruff, isolated mypy, Python compilation, and `git diff --check` passed.

## Production-shaped attribution

Machine: Apple M4 Pro, macOS 26.5.2 arm64, Python 3.12.13. Each screen used
seven alternating-order pairs at niceness 15. An unrelated MPS imitation fit
and one RoadForge CPU solver were active, so paired results and confidence
intervals are authoritative for rejection only and must not be compared with
clean historical throughput.

### Random stationary rollout

Command:

```text
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py --comparison shared-snapshot --workload random --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 7 --warmup-steps 8 --torch-threads 2 --engine-fast-path on --reward-profile defense-v2
```

- Separate median: 179.200 decisions/s, 1.428572 s
- Shared median: 179.713 decisions/s, 1.424496 s
- Paired median: +0.270%; paired mean: +0.945%
- Mean bootstrap 95% CI: -0.506% to +3.191%; 4/7 positive pairs
- Both hashes: `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a`

### Balanced strategy stationary rollout

Command was the random command above with `--workload strategy --strategy balanced`.

- Separate median: 181.479 decisions/s, 1.410632 s
- Shared median: 184.164 decisions/s, 1.390063 s
- Paired median: +1.407%; paired mean: +0.944%
- Mean bootstrap 95% CI: -1.426% to +3.487%; 5/7 positive pairs
- Both hashes: `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d`

### Stable-root oracle

```text
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_oracle.py --comparison shared-snapshot --seed 2301 --planner-seed 901 --states 3 --state-stride 4 --repetitions 7 --decision-interval 8 --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 --engine-fast-path on
```

- Separate median: 2.378 decisions/s, 1.261581 s
- Shared median: 2.377 decisions/s, 1.262260 s
- Paired median: +0.044%; paired mean: +0.023%
- Mean bootstrap 95% CI: -1.088% to +1.088%; 4/7 positive pairs
- Both hashes: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Decision

Reject. The candidate adds a batch-mask API and several call-site branches for
an oracle result centered at zero and rollout confidence intervals crossing
zero. The exact request-local design remains a safe option if future profiling
shows entity snapshot construction becoming material, but it is not justified
in the current production stack.
