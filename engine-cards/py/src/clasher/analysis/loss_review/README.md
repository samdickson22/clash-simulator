# Loss-review ledger

Exploratory diagnostics only. No training, gate evidence, registration edits, or
heldout/eval access. `human.py` opens only explicitly selected `train` or `dev`
role manifests and named read-only NPY columns. It never opens the root store
plan, intent targets, or evaluation specifications. Both perspectives of a human
match share one bootstrap cluster.

Run on the home CPU fleet, with `fleet_run.sh` (nice 10), thread-library limits
from that launcher, and CPU affinity that preserves the assigned reserves. The
2026-10-08 run used 01 CPUs 0–95 for simulation and 08 CPUs 0–111 at peak for
human processing. Copy only task-owned files with `rsync -c`.

```bash
# Prefix each command below with:
# bash reports/strategy_council_20260928/fleet/fleet_run.sh UNIQUE-LABEL taskset -c 0-95
.venv/bin/python -m clasher.analysis.loss_review.human \
  --store reports/strategy_council_20260928/imitation/data/c56-store-v1 \
  --role train --workers 96 --out reports/explore/loss-review/human-train-NEW

# Repeat human extraction with --role dev and another destination.
.venv/bin/python -m clasher.analysis.loss_review.simulate \
  --exclusions reports/explore/loss-review/seeds.json \
  --workers 96 --pairs 150 --delays 0 27 --trace \
  --out reports/explore/loss-review/sim-NEW

.venv/bin/python -m clasher.analysis.loss_review.reduce_traces \
  --source reports/explore/loss-review/sim-NEW \
  --out reports/explore/loss-review/reduced-NEW/games --workers 64

.venv/bin/python -m clasher.analysis.loss_review.summarize \
  --inputs reports/explore/loss-review/human-train-NEW/games.jsonl \
  reports/explore/loss-review/human-dev-NEW/games.jsonl \
  reports/explore/loss-review/reduced-NEW/games \
  --out reports/explore/loss-review/results-NEW.json --workers 64 --bootstrap 1000

.venv/bin/python -m pytest -q tests/analysis/test_loss_review.py
```

The simulator imports the existing Stage 5 public reconstruction, S6
`DelayAwarePlanner`, and `CommandChannel` without editing them. Candidate and
rollout budgets use the existing `C56SearchConfig` defaults, fixed budget and
one thread, with 10-tick decisions. This is a diagnostic fair-search arm, **not**
a claim to reproduce the full live player or its 200 ms deadline. Both physical
players disable champion ability actions. Own commands execute after the chosen
delay; the opponent script has immediate actuation. d=0/d=27 share game seeds,
decks, seat and opponent style. No live opponent hand, cycle or RNG is imported
into search roots. The prior catalog contains train-role human decks.

`Game` is the adapter interface. Frames are pre-action, 20 ticks/second,
canonical own side at y<16, with global features in public-observation order and
17 compact entity columns. Offsets delimit ragged entities. Plays are accepted
execution events with pre-spend elixir and canonical coordinates. Raw trace
telemetry is analysis-only and never becomes a player input. Future sim runs
also save own queues; the initial run's traces did not save queues, so its
numeric queue-distance metric is unavailable for simulator games. Hand-absence
and affordability metrics remain measurable.

Each reduced game has `stats[scope][metric] = [numerator, denominator]`, identity,
original-game cluster ID, cohort, role and metadata. Scopes include aggregate,
single/double/triple phase, own-versus-enemy archetype, and their intersections.
Zero opportunities are missing, not zero-valued observations. Per-card rates
include zero-use games with that card in the deck. The summarizer rejects
forbidden roles and duplicate perspectives.

## Metric definitions and limits

- **Arrival:** first enemy troop presence in a lane at y<=16 after >=2 seconds
  of absence, excluding ticks before 90. Includes direct deployments in our
  half; does not claim to track individual bridge crossings. Record the
  pre-action elixir, under-4 share and integer-bin distribution. Compact
  replays lack persistent unit identities.
- **Defense:** first accepted same-lane own-half deployment or spell in the
  next 8 seconds; latency is capped at 8 for nonresponses, which are separately
  counted. Entire 8-second window required, including at truncated human ends.
  A separate 2-second preemptive-play proxy prevents interpreting every long
  post-arrival delay as a late defense. This is geometry, not tactical intent.
- **Commitment:** total same-lane own-half deployment/spell cost in that
  8-second window; >=7 share. Not automatically a mistake. Reinforcing pushes
  without a 2-second clearance belong to one incursion.
- **Elixir cap:** time-weighted sampled occupancy of elixir>=9.999. Leaked
  elixir is a conservative full-cap interval estimate, excluding intervals
  containing an accepted play; partial approach-to-cap and Collector overflow
  are omitted. Sampling is 0.25 seconds; unobserved gaps >0.5 seconds contribute
  no exposure. Time-at-cap is a sampled estimate, not exact subframe duration.
- **Counterpush:** after a >=2-second lane clearance, a rise in friendly troop
  count across the bridge within 10 seconds. Needs the complete follow-up.
  Measures new pressure, not verified surviving-defender identity.
- **Spell value:** pre-cast radial geometry for Fireball/Zap/Snowball/Rocket,
  enemy units/towers in nominal radius and HP-weighted exposed static unit
  elixir divided by spell cost. Excludes rolling and other unsupported spells.
  Geometry omits hitboxes, travel, air targeting and actual damage attribution;
  **actual hits and elixir traded are unavailable**, never zero-filled.
- **Cycle:** fraction of arrivals without a non-spell, non-win-condition card
  in the own hand; separate fraction without an affordable one; minimum queue
  position when recorded. Availability proxies, not oracle-labeled errors.
- **Lane:** left-lane share of accepted plays. No universal preferred lane or
  optimal-lane label is assumed. Archetypes use an explicit priority list in
  `metrics.py` and are descriptive, coarse deck categories.
- **Win-condition timing:** elapsed seconds at play, post-play reserve<4, and
  presence of an active enemy incursion. These do not establish tactical error.
- **Per-card use:** accepted plays per minute of observed exposure in decks
  containing that card, with zero-use games retained.

Human states are reconstructed from command streams, not native visual truth.
The reader drops projected trajectories and clips before first tower clamping.
Real outcomes can describe matches longer than the retained prefix. C56 card-name
and C56 base-form human subsets are provided as sensitivity comparisons; skill, level,
match-length and matchup differences remain. No pro qualification is assumed.

Estimates are pooled ratios. CIs are percentile 95% intervals from 1,000
original-game multinomial bootstrap draws, shared across metrics in a scope.
Human-vs-search contrasts are independent; delay contrasts resample paired
seeds. Sparse scopes can have wide or absent CIs. CIs are pointwise and do not
correct for exploratory selection/multiple comparisons. The under-4/tower-damage
risk contrast is an association, not a causal win-rate estimate.
