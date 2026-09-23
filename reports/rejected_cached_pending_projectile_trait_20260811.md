# Rejected cached pending-projectile trait

Date: 2026-08-11

The candidate cached the immutable normalized `projectile_data` presence on
each `Entity` and reused it in pending-projectile target rejection. Twelve
focused ranged/melee and fixed-seed off/shadow/on tests passed.

A bounded nine-repetition alternating oracle A/B ran at low process priority
while shared Clasher CPU/MPS and RoadForge CPU work was active:

```bash
nice -n 10 env PYTHONPATH=src:scripts/perf:. uv run python \
  scripts/perf/benchmark_oracle_cached_pending_projectile_trait.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 9 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Runtime resolution measured a 1.346471-second median and the cached candidate
measured 1.355665 seconds, a **-0.68%** result. All 18 rows produced identical
action, state, battle-RNG, and planner-RNG digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

Because the loaded result was negative and the candidate added a hot switch
branch for a small attribution, it was rejected without further shared-compute
timing. No candidate source or benchmark scaffolding remains.
