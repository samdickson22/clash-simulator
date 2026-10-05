# Divergence sweep over opened Tier A evidence (v4, v5, v6), 2026-09-30

**Development evidence only.** This changes no attempt verdict. No ledger, attempt artifact or runtime snapshot was written. Native per-tick checks were read-only replays of recorded reference branches (recorded prefix plus the recorded `replay-schedule-card` stream; no controllers) on probe ports 26791–26796 (emulator-5584…5594). Those devices were left ready and paused. Emulators 5580 and 5582 were not used.

## Summary

- **Pairs:** 1534 scalar/reference pairs, keyed by (family, condition, role): 512 in v4, 510 in v5 and 512 in v6. Two v5 reference branches never completed.
- **Divergent pairs** (final HP differs or the decision streams differ):
  - 129 in the recorded runs;
  - 112 when current main is replayed (it already has the King first-target lock, the knockback stale navigation target fix and the ep24 frozen-stop route-resume fix, "H12");
  - **92 after this sweep's four fixes.**
- **Score (win/loss) differences:** recorded 8 → current main 5 → 3.
- **Frame-exact branches** (every 5-tick native frame matches in position and HP to the logic unit): 1187 → **1248** of 1534. By attempt: v4 419→434, v5 391→417, v6 377→397.
- **Four real rule bugs were fixed in main.** Each has clear native evidence, and each was validated alone and in combination on every branch its gate could affect.
  - Every fix moves branches toward native and **none moves any branch away**.
  - Combined: 69 branches toward, 0 away, 19 changed only between native samples; 722 of the 810 gate-flagged branches are byte-identical.
- **Remaining 92 divergent branches (42 trajectories):**
  - 12 branches (6 trajectories) have an identified native rule difference whose correct rule is not yet pinned down. None was landed, because every candidate moved some branch away or failed a native fixture.
  - 2 branches are the v4 ep04 case that an earlier review classed as chaotic amplification.
  - **78 branches (35 trajectories) remain unexplained.** Their first divergence is 750–5265 ticks after the root, and they were not investigated.

## Method

1. **Replay tool.** `artifacts/replay.py` replays a scalar branch closed-loop through `run_readiness_v2._execute_job_body` against the attempt's frozen `branch-plan.json`, using a copy of current main's `src`. It dumps every body every 5 ticks and compares against the reference `native_frame`.
   - `artifacts/exact.py` finds the first material divergence: the first 5-tick native frame in which any body differs by at least 1 logic unit or 1 HP, or a body is missing.
   - The earlier reviews used a 0.001-tile threshold. That threshold hides the 1-unit spawn errors fixed below.
2. **Baseline "pre".** All 1534 scalar branches were replayed on current main with behaviour-neutral gate detectors (`artifacts/detect_gates.py`). Each detector records the first tick at which a candidate rule would change behaviour.
   - A branch whose gate never fires is provably unchanged by that rule, so validation only replays gate-flagged branches.
   - 810 branches were flagged: T 121, K 162, B 619, S 401.
3. **Per-tick native checks.** For each first divergence, a per-tick native replay (`artifacts/native_probe.py`) was compared with a per-tick scalar trace.
   - Every probe reproduced all recorded 5-tick frames with 0 mismatches.
   - Candidate rules were written as monkeypatches first.
4. **Validation.**
   - **Combined run:** the four candidates were run as instrumented monkeypatches (`patch_combo2_logged.py`) on all 810 flagged branches. The instrumentation logs the exact tick at which each rule actually changed behaviour.
   - **Single-rule runs:** each rule was replayed alone wherever another rule also applied (T 18, K 20, B 121, S2 101 branches).
   - **Landed code:** it was replayed on 128 branches (every changed branch plus 40 random unchanged ones) and is byte-identical to the patched results.
5. **Direction.** A branch counts as *toward* native if its first exact divergence moves later, and *away* if it moves earlier.
   - *Neutral* means the decisions changed but the first exact divergence did not. In 17 such branches the change falls entirely between two 5-tick native samples.
   - Per-tick native checks of 4 neutral branches: v6 ep27 878, v5 ep16 520 and v5 ep22 716 are toward native at every tick. v5 ep15 488 is the same as before on every tick.

## Clusters, verdicts and fixes

| # | mechanism signature | example (first divergence) | verdict | action | toward / away (alone) |
|---|---|---|---|---|---|
| T | **Crown Tower retarget mid-windup resets its hit.** A Princess Tower's lock leaves reach during windup and it retargets an in-range unit | v6 ep12 displaced b/b, job 398: tick 320, Knight HP 109 (tower arrow one tick late) | **real bug** | fixed | **14 / 0** (+19 neutral: 17 between native samples, 2 after an earlier unrelated divergence) |
| K | **A push under stun stops the hit.** A Log/Fireball push starts while the unit is Frozen or Zapped | v4 ep03 displaced b/b, job 110: tick 550, Skeleton alive only in scalar; outcome reversed (score 0 vs native 1) | **real bug** | fixed (deferred stop) | **12 / 0**; 2 outcome reversals now equal native |
| B | **A building killed by this tick's combat stops counting as an avoidance obstacle** in the same tick | v4 ep28 wait b/p, job 898: tick 612, Goblin step (−21,−118) vs native (−4,−120) | **real bug** | fixed | **8 / 0** |
| S2 | **Symmetric one-unit deploy nudge uses the searched anchor's side** when the placement search relocates across the centre line | v6 ep10 immediate b/p, job 320: Ice Golem at 8499 vs native 8500 (also Ice Spirits in v4 ep16 and v5 ep06) | **real bug** | fixed | **35 / 0** (+2 neutral) |
| Z | Avoidance accumulator of a unit stunned while deploying (Zap), then pushed | v6 ep12 displaced b/p 390/406 (+55 ticks, Goblin 0.84 tiles); v6 ep03 wait b/b 106 (+115) | real rule difference, rule not identified | not landed | Retaining the accumulator under stun makes 390 frame-exact, but moves v4 ep18 590 away and fails 4 native fixtures. The "no scan" and "no scan, no decay" variants also fail |
| N | Walking retarget to a new target with the same goal cell keeps the old route | v4 ep14 alternate b/b 460/476 (+200): native walks toward (28,30), scalar keeps [(27,30)] | real rule difference, condition not identified | not landed | Rebuilding always fixes 460 but moves v6 390, v6 398 and v4 898 away |
| C | King Tower first-shot timeline after re-acquisition during reload (native timeline starts at 400, so the shot comes 550 ms after acquisition; scalar fires 450 ms after) | v6 ep21 alternate b/p 676 (+3315, Musketeer HP 109) | real rule difference | not landed | Putting Crown Towers on the ordinary two-clock model fixes it but fails `test_native_crown_clock_carry::test_king_slow_expiry_preserves_native_firing_phase` |
| H | Tesla hide timer under IceWizardSlowDown vs a Log | v5 ep29 928/930/934 (+3085): scalar Tesla hides at 3372 and the Log misses; native Tesla is destroyed | unresolved | none | |
| L | Crown fallback for a child nudged to x=8.999 at the centre column | v4 ep09 alternate b/p 292/308 (+1400): native Archer walks to the left tower, scalar to the right | unresolved (the body-position lane probe had no effect) | none | |
| A | Sub-tile drift at a Goblin retarget | v4 ep04 138/142 (+885) | classed as chaotic amplification by `tier-a-fresh-v4/review/episodes-04-14-mechanism.md` | none | |
| U | Not investigated | 35 trajectories, 78 branches, first divergence +750…+5265 ticks (Goblin, Ice Golemite, Skeleton and Hog bodies at 0.003–0.5 tiles; three HP-first) | unexplained | none | |

Combined (T + K + B + S2) over the 810 flagged branches: **69 toward, 0 away**, 19 neutral, 722 identical.
- Frame-exact: +61 / −0.
- HP-exact: +14 / −0.
- Score-equal: +2 / −0 (v4 ep03 displaced_placement under both balanced/balanced and defense/balanced).

By attempt: v4 19 toward, v5 27 toward and 18 neutral, v6 23 toward and 1 neutral.

## Fix evidence

All five native values below come from the recorded reference `native_frame` and per-tick native probes.

### T — `Entity._note_combat_target` (entities.py ~1789)

The native f5c92c rule keeps ordinary hit work when the replacement target is already in engagement reach. Scalar applied it only to entities on the ordinary clock, and Crown Towers are excluded from that clock.

**Native evidence (v6 job 399):**
- At 290 the right Princess Tower targets Skeleton 5000008 with timeline 50. The Skeleton leaves reach at 291, 0.034 tiles out.
- The tower retargets the Knight. Its timeline runs on unbroken (300 at 295, 800 at 305).
- The arrow spawns at 305 and hits the Knight at 320. Scalar spawned it at 306 and hit at 321.

**Change:** a Crown Tower on the legacy clock with an in-reach replacement also preserves its hit. With this change job 398 is frame-exact (923/923).

### K — `Troop._update_knockback_movement` (entities.py ~3449)

**Native evidence:**
- **Frozen case (v4 job 111):** the Knight is Frozen at 520 with timeline 800 and pushed by a Log at about 527. Its timeline stays at 800 through the push. After the thaw it resumes (950 at 545) and kills Skeleton 5000020 at 550.
- **Zap case (v6 job 157):** the Knight is Zapped at about 2529 and pushed by a Fireball that outlasts the 300 ms stun. Native does stop the hit.

**Why the rule is deferral, not cancellation:** simply cancelling the stop under stun moved v6 156 away from native.

**Change:** while the unit is stunned the stop is deferred to the first push frame after the thaw, and it lapses if the push ends first.

### B — `Troop._update_native_avoidance` (entities.py ~3315)

**Native evidence (v4 job 899):**
- Owner 0's Knight kills owner 1's Tesla in combat at 612.
- Goblin 5000024's native step at 612 is (−4,−120). Of the candidate nodes and avoidance values, only route node (28,33) with avoidance −90 → −110 → −100 reproduces it. That is the static-obstacle +20 bump, with the geometric side taken from the Tesla.
- Scalar dropped the dead Tesla and stepped (−21,−118).

**Change:** a building killed this tick is still in the pre-combat grid and still counts as a static obstacle, just as it already counts as a routing obstacle. This does not apply to direct calls made without the per-tick grid.

### S2 — `BattleState._apply_symmetric_deploy_snap` and `deploy_card` (battle.py ~1223, ~1411)

**Native evidence (v6 job 321):**
- The Ice Golem is requested at (9.5, 11.5), which the Cannon occupies. The placement search moves it to (8.5, 11.5).
- Native places it at x = 8500. Scalar gives 8499, because it decides the x side from the searched anchor.

**The alternative rule is contradicted.** Skipping the nudge entirely after any relocation (S1) moved v4 110, v4 898 and v6 398 away. A combined test run that included S1 also failed the `test_native_troop_overlap` anchor fixture.

**Change:** the x side is taken from the requested anchor. The rule is also supported by displaced Ice Spirits that become exact (v5 ep06 and v4 ep16).

## Tests

- **New:** `tests/test_native_tier_a_divergence_sweep.py` with fixture `tests/fixtures/native_tier_a_divergence_sweep_15_535_86.json`. It has five closed-loop branch cases checked against native frames.
  - Each rule case fails when its own rule is reverted and passes otherwise (verified for all four).
  - The fifth case, `zap_push_outlasting_stun_stops_hit`, fails under the naive "cancel under stun" version of K.
- **Suites:** the movement, route, native, match, interaction, deploy, building, target-switching and inferno suites were run on final main: 127 files, **2683 passed and 7 failed**.
  - All 7 failures also fail on current main without these changes: `test_inferno_ramp` resets-on-retarget, 3 × `test_hog26_scalar_deployment_ability`, 2 × `test_rl_oracle_direct_path`, and `test_rl_deployment_blocker_guard`.
  - `test_native_frozen_stop_route.py` and `test_native_knockback_navigation_target.py` pass.
- **Torch tests:** `tests/test_torch*.py` gives 475 passed and 6 failed, identical with and without the changes.

## Notes and open items

- **Torch simulator.** The torch sim has its own tower clock, avoidance and deploy-snap code. None of the four rules is mirrored there yet, and no parity test covers these cases.
- **Z (stun while deploying).** This most needs a constructed native probe: Goblins Zapped mid-deploy and pushed, with and without a pre-stun avoidance hit. Two v6 families depend on it.
- **N (same-goal retarget).** The three counter-cases all have multi-node retained routes. The one native rebuild had a single-node route whose node was the goal cell. A narrower rule may be possible, but it was not tested.
- **Artifacts.** `artifacts/` holds the replay, compare and probe scripts, every candidate patch (landed and rejected), the per-fix comparison lists (`cmp3_*.txt`, `*.json`), the per-branch pre/final summaries (`branch_summaries.json`), the exact first-divergence index (`exact_all.json`) and the remaining-trajectory list (`remaining_traj.json`). Per-tick dumps and native tick files are in `/tmp/dsweep/`, which is not persistent.
