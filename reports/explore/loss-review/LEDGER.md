# Clasher loss-review ledger — 2026-10-08

**Exploration lane. Not gate evidence. No training, pre-registration, frozen-registration edits, or eval/heldout access.**

The clearest measured loss sensitivity is the **d=27 command-delay setting**: 22/150 losses versus 11/150 at d=0, **+7.3 percentage points (95% game-bootstrap CI +2.0 to +13.3)**. The largest human-behavior difference is depleted reserves: **91.0%** of d=27 lane incursions arrive below 4 elixir versus **18.6%** for the C56-compatible human baseline, **+72.4 pp [71.2, 73.7]**. These are different findings: **d=0 is even more depleted (99.5%) yet loses fewer games**. This run does not establish reserve depletion as the cause of our losses.

[Compact summary](summary.json), [all estimates, distributions, slices and CIs](results.json), [tool and metric definitions](../../../src/clasher/analysis/loss_review/README.md), [execution receipt](receipts/run.json), [tests](receipts/tests.txt).

## Evidence and comparability

- Human: **55,657 train/dev perspectives from 52,240 original games**, 37,212,701 reconstructed frames. Train 52,951; dev 2,706. Projected trajectories were excluded, and retained prefixes stop before first tower clamping. No outcome-based selection.
- Main narrower comparator: **3,529 perspectives / 2,310 games** with both decks inside the C56 card-name scope. Evolutions, heroes and different levels still occur. Requiring base forms on both sides leaves only **6 perspectives / 4 games**; that sensitivity sample cannot validate strong conclusions.
- The broad human baseline has **512,831** complete-window incursion events and **15.9%** under-4 arrivals. The C56 subset has **41,526** events and **18.6%** under-4 arrivals. These players are **not individually pro-qualified**. The reported human baseline is not a substitute for ClashAI's pro baseline.
- Simulator: **150 paired seeds, 300 terminal games**, five own and opponent archetypes (25 matchups), three scripts and both seats. Each matchup has six seeds. No learned model or new training. Existing Stage 5 fair public reconstruction and S6 delay-aware rollout/channel code; 10-tick decisions, default fixed rollout budget, horizon 160 ticks, one search thread. Abilities disabled on both physical sides. Opponent scripts act without added command delay.
- d=0 versus d=27 changes physical command delay and the corresponding rollout model together. This is a diagnostic fair-search arm, **not the exact deployed live player, pixel path, 200 ms deadline arm, or an imitation-prior arm**.
- Estimates are pooled event/exposure ratios. **1,000 bootstrap draws resample original games**, clustering both human perspectives; delay contrasts resample paired seeds. CIs are pointwise, exploratory and uncorrected for multiple comparisons. Human-vs-simulator gaps remain confounded by opponent behavior, deck frequencies, levels, forms and replay-prefix censoring.

A “push arrival” here is a **lane incursion onset**: enemy troop presence in our half after at least two seconds without such presence in that lane, including direct deployments. It is not an identity-tracked count of every unit crossing a bridge. Thus the percentages must not be equated directly with ClashAI's 70%/24% result in [lesson L2](../../clashai_deepdive_20261008.md).

## Top five candidate loss mechanisms, ranked by research priority / estimated impact

Ranks are non-additive research hypotheses. Only rank 1 has a measured paired game-loss difference; ranks 2–5 have measured behavioral burdens, **not estimated causal win-rate uplift**.

1. **Delay-sensitive command commitment — high priority; strongest loss evidence.**
   d=27 loses **14.7% [9.3, 20.0]** versus **7.3% [3.3, 12.0]** at d=0; paired difference **+7.3 pp [2.0, 13.3]**, or 11 additional losses in these 150 seeds. Delay-aware search has not eliminated the cost of waiting 27 ticks for an accepted command. Post-arrival response latency changes only **+0.10 s [-0.13, 0.33]**, so “simply reacts more slowly after the crossing” is not established as the explanation.
   **Try:** keep physical d=27, instrument pending-command exposure and root scores, and compare earlier threat anticipation and delay-matched candidate placement/timing. Check that the imitation timing prior is evaluated at the same command horizon. Do not infer that reducing the real client's fixed delay is available, or that this isolated fixed-budget arm represents live latency.

2. **Spending away defensive options — high behavioral burden; causal impact unresolved.**
   Under-4 arrivals are **91.0% [89.8, 92.2]**, C56 humans **18.6% [18.1, 19.1]**; gap **+72.4 pp [71.2, 73.7]**. At arrival, there is no affordable generic defender in hand **65.3%** of the time versus **3.9%**, gap **+61.5 pp [58.8, 64.0]**. Actual defender absence from the hand is only about **0.10%** versus **0.17%**: this proxy points to affordability, not a missing generic card. **97.5%** of win-condition plays leave less than 4 elixir, versus **54.5%** for C56 humans; gap **+43.0 pp [41.7, 44.3]**.
   **Try:** inspect WAIT versus immediate-play candidate scores, leaf board-value/elixir scaling, and repeated cheap-card choices. Supply the existing imitation prior's wait/play and card proposals to the planner when that prior is available, without training in this lane. Use this ledger as a diagnostic, not a reward or a hard “always keep 4” rule.
   **Contradiction to retain:** d=27 improves under-4 frequency by **8.5 pp** versus d=0 while losing more. In d=27 games, low-elixir incursions have **−6.6 pp [-14.6, +1.2]** different subsequent tower-damage risk than other incursions; the interval includes zero. The broad human association is **+2.47 pp [2.10, 2.85]**, which cannot be transported as causal simulator impact.

3. **Expensive / long-horizon win conditions starved by the search choices — medium-high hypothesis.**
   X-Bow is played **0.124 per deck-minute** versus **1.010** for C56 humans; gap **−0.887 [-0.957, −0.811]**. Against the broad baseline, Giant is **0.057** versus **0.731**, gap **−0.674 [-0.796, −0.550]**; the narrower C56 Giant comparator has only three games and should not drive a conclusion. Cheap cycling is higher: Skeletons **3.267** versus C56 **1.856** plays/deck-minute, gap **+1.411 [1.304, 1.510]**. These rates include zero-use games containing the card, so they are not conditioned on already choosing it.
   **Try:** log whether expensive cards ever survive masking, candidate generation and reduction; guarantee representative legal proposals for each affordable hand card, including imitation-prior proposals. Compare the current eight-second leaf horizon with a longer strategically relevant horizon at the same physical delay. Audit long-deployment payoff before interpreting the low play rate as strategic restraint. Estimated win impact remains unknown.

4. **Spell selection favors cycling over expensive spell opportunities — medium hypothesis; value unproven.**
   Fireball is **0.112** versus C56 **0.836** plays/deck-minute, gap **−0.724 [-0.769, −0.674]**. Rocket is **0** versus **0.664**, gap **−0.664 [-0.701, −0.626]**. Log is **3.001** versus **1.502**, gap **+1.499 [1.364, 1.626]**. This is selection imbalance, not proof of bad spell aim: only **24** supported radial spells were played by d=27, and exposed-elixir-per-cost geometry differs from the C56 baseline by **+0.138 [-0.017, 0.289]**, a null result.
   **Try:** audit expensive spell candidates and public lethal-tower opportunities, then record damage-source attribution and targets at impact. Include imitation spell/card proposals. Do not optimize the geometry proxy, or claim measured elixir trades from it. A zero Rocket play count does not prove a lethal spell window was missed.

5. **Win-condition commitment while a threat is already present — medium-low hypothesis, overlapping delay/economy.**
   **34.1%** of d=27 win-condition executions occur during an enemy incursion, versus C56 humans **24.0%**; gap **+10.1 pp [6.3, 14.0]**. Relative to d=0, the paired change is **+7.1 pp [2.8, 11.0]**. The accepted command may be executing into a changed board, or this may be intentional opposite-lane pressure; geometry alone cannot decide.
   **Try:** log threat state at both submission and execution, distinguish same-lane defense from opposite-lane pressure, and inspect selected roots under the d=27 rollout. Compare delay-matched imitation timing proposals. Avoid labeling every offensive play during a threat as an error. No independent causal loss estimate is available.

## Slices, nulls and unavailable measurements

The under-4 gap appears in all 25 sampled matchup archetypes: d=27 ranges from **84.6% to 98.3%**, with only six games per matchup. Full game-bootstrap CIs and phase-by-matchup intersections are in `results.json`.

For single/double/triple elixir respectively, d=27 under-4 frequency is **90.6% [89.0, 92.1] / 93.1% [91.2, 95.0] / 79.0% [70.7, 85.6]**. Broad human values are **15.4% / 16.6% / 18.4%**. Triple-elixir simulator support is only **26 games / 100 incursions**. All phases have their own exposure and event denominators.

- **Large defensive commitments are not elevated:** >=7 elixir within the eight-second defense window occurs **2.8%** versus C56 humans **15.7%**. This contradicts large reactive dumps as the dominant overspending mechanism in this sample.
- **No observed max-elixir leakage in either search arm:** sampled time at 10 and the conservative full-cap leakage estimate are both zero. The broad human baseline spends **4.04%** of observed time at cap. The bootstrap [0,0] describes this sample; it does not establish a population upper bound of zero.
- **Counter-push pressure conversion is not weak:** d=27 **65.2%** versus C56 humans **50.1%**; paired d=27–d=0 **+1.1 pp [-2.5, 4.2]**. This counts new friendly pressure after a clearance, not identity-confirmed surviving defenders.
- **Response latency is measured, but mechanism attribution is weak:** capped-at-eight-second latency is **4.56 s** versus C56 **3.74 s**, gap **+0.81 s [0.63, 1.00]**. Preemptive plays, existing defenders, spell reach and opponent composition complicate the tactical interpretation. Delay's paired latency change is null as noted above.
- **Lane bias is null against the broad baseline:** left-lane share differs by **+0.95 pp [-1.10, 3.19]**. This does not assess whether the correct tower/lane was targeted.
- **Cycle position:** human queue distance and both cohorts' hand-absence/affordability proxies are available. Oracle-labeled strategic cycle errors are unavailable. Initial simulator traces omitted own queues; the reusable simulator now records them, but no simulator queue-distance values were invented for this run.
- **Actual spell hit counts and elixir traded are unavailable** in the common data. Recorded values are explicitly pre-cast radial geometry / exposed-value proxies; rolling spells and unsupported spell geometries are excluded. Damage-source/impact attribution is the remaining instrumentation requirement.
- **Strong-human qualification is unavailable.** The C56 base-form sensitivity has only four original games. This limits claims of human parity or deficit even where descriptive CIs are narrow.

## Reproduction and compute audit

The tool is under `src/clasher/analysis/loss_review/`; **12 tests pass**. Tests cover role guards, duplicate inputs, game clustering, bootstrap denominators, censoring, lane assignment, 7-elixir boundaries, phase exposure, card aliases, and separating cycle availability from affordability. The final d=0/d=27 queue-telemetry smoke preserves identical actions and public states versus the earlier deterministic smoke; [telemetry check](receipts/telemetry-check.json). No commits were made.

All substantial work ran detached with `fleet_run.sh`, nice **10**, on **127x01 and 127x08**. No work was run on 02/03, leased hosts or roader paths; 05 only authored code and read compact results. No GPU, tailscale, crontab or process-wide kill operations.

- **01 simulation:** 96 workers, CPUs 0–95, **300/300 terminal**, **240.8 s** program wall, **16,111.1 worker CPU seconds** (about 66.9 cores averaged over startup/tail). `/usr/bin/time` including setup records 16,324.4 CPU seconds / 243.2 wall seconds. **32 CPUs outside affinity**, exceeding the required 24 reserve.
- **08 final train extraction:** 96 workers, **44.8 s wall / 716.4 worker CPU seconds**. Concurrent dev extraction: 16 workers on CPUs 96–111, **2.7 s wall / 14.1 worker CPU seconds**. **At least 16 CPUs outside affinity**. These reductions are short, I/O/serialization-limited jobs; worker count is not claimed as sustained utilization.
- **08 final reduction/bootstrap:** 64-worker pools, CPUs 0–95; launcher receipt records **263.5 CPU seconds / 68.6 wall seconds**, including the bounded wait for extraction. Explicit receipts and input/code hashes are in `receipts/`.
- Earlier smoke and reducer iterations are retained remotely under distinct `loss-review-*` labels; they are not pooled as extra games. Final results use only `human-{train,dev}-v4` and `sim-reduced-v2` from `sim-production-v1`.

**Seed exclusion:** the requested `audit-proposed-seeds.json` path was absent on allowed hosts. The read-only home-host seed inventories supplied identical **4,356 proposed gate/helper seeds**, plus **19,294 distinct historical seed values** across 01/08. Fresh games use `2**48 + [0..149]`; game and player-helper seeds have **zero intersections**. See [seed audit](seed-audit.json) and [rerunnable exclusion list](seeds.json). No gate outcome, evaluation split or frozen registration was opened or modified.

Full per-game reductions and compressed public telemetry stay on the home hosts under `/mpac/sdicks02/repos/clasher/reports/explore/loss-review/`. Exact commands, source hashes, role-manifest hashes, seed schedule, utilization and test output accompany this ledger. The next research step is a small d=27-only diagnostic of pending-command exposure and candidate/WAIT scores—not a claimed gate result or a new training run.
