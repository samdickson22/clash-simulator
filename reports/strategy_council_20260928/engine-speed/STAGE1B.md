# Stage 1b: gate passed for the four-card slice

2026-10-03. Knight, Archers, Giant, Musketeer and towers only. Python remains
authoritative and unchanged. No commits were made.

The final build passes all three requested gates. Admit Stage 2 implementation.
This does not register the prototype as a training or evaluation backend.

## Final evidence

- Original twelve scenarios: zero mismatches / 21,674 tick boundaries.
- Expanded 24 scenarios: zero mismatches / 42,734 tick boundaries,
  zero command-acceptance differences and zero full-RNG differences.
- One-core stepping: Python 1,262.922 versus Rust
  83,470.550 ticks/core-second, **66.093x** on identical trajectories.
- Native clone: 1.353 microseconds on the imported 16-body root;
  1.067-1.854 microseconds on four independently evolved tick-600 roots.
- Thirteen differential tests pass: eleven root-cause regressions, the King
  projectile outcome follow-up, and debug-phase equivalence.
- Primitives: 4,600 MT19937 comparisons and 2,000 A* routes, zero differences.

Receipts: `results/stage1b_final12.json`, `results/stage1b_24.json`,
`results/stage1b_convergence.json`, and `logs/stage1b_final.log`.

Cases 0-11 keep the original actions and seeds. Cases 12-23 use seeds 9712-9723,
lanes shifted one tile outward, and the same three legal deployment depths.
Every scenario contains accepted deployments and combat. Each runs until the
Python outcome or the original 2,200-tick horizon. These are 24 scripted game
trajectories, not a claim that all 24 reach a terminal state.

| Card | Compared ticks | Mismatching boundaries |
|---|---:|---:|
| Knight | 12,641 | 0 |
| Archers | 11,743 | 0 |
| Giant | 5,150 | 0 |
| Musketeer | 13,200 | 0 |

Stepping is synchronous and single-threaded. Process CPU timers surround only
`step`; action generation, digest/RNG comparison, snapshots and cloning are
outside the timers. The shared ARM64 Mac can migrate processes between cores.
The immediately preceding final twelve-case run measured 73.218x;
this variation is why both raw receipts remain available.

Each clone mean covers 1,000 calls. Live roots contain 8, 12, 14 and 16 objects
with evolved timers, routes and combat state. Each cloned pair also runs twenty
more identical ticks, and the parents retain their original digests.

## Diagnostics and replay

`engine-rs/diagnostics.py` records full mutable Python entity fields, battle
clocks, player refill timers, projectiles, and all 624 RNG words plus index.
Rust snapshots expose its complete independent state. The first divergent tick
contains a field-level diff and both snapshots. Immutable card definitions are
omitted from the Python raw entity dump; the adapter imports them separately.
Different internal representations, such as a projectile's unused inherited
fields or normalized direction vectors, remain visible for diagnosis.

The admission digest retains the original `es_common.battle_digest` byte format.
It is not a full internal-state digest. Full RNG state is additionally compared
after every tick; diagnostic internal fields are not silently treated as equal.

`--case C --bisect-tick N` replays through N-1 and captures before, start, combat,
movement, objects, cleanup and complete states for tick N. Python uses a temporary
read-only trace hook. Rust `debug_step` captures the same implementation used by
ordinary `step`. A regression checks that tracing does not change the result.

## Root causes fixed

1. **Pending homing damage and retained-hit removal.** Track the target-owned maximum duration and live damage aggregate. Register new shots after character object timers. Pending-lethal removal bypasses finish work and resumes an in-range hit. Duration uses the inclusive 600 ms gate and a 1000 ms cap.

   Python reference: `src/clasher/entities.py:2281-2357,1672-1697`, `src/clasher/battle.py:949-960`.
   Regression: `test_pending_lethal_removal_reacquires_without_finish`.

2. **Resident depleted targets and Crown navigation.** Keep eligible depleted locks and resident Crown fallback objectives until cleanup. Rust previously selected the King during combat, changing movement in the same tick.

   Python reference: `src/clasher/entities.py:2359-2396,2507-2560`.
   Regression: `test_depleted_crown_remains_navigation_goal_until_cleanup`.

3. **Collision pressure averaging and cap.** Average every queued integer collision contribution, including tangent contacts, then cap the averaged vector at 150 logic units. Rust previously summed uncapped vectors.

   Python reference: `src/clasher/entities.py:351-379`, `src/clasher/battle.py:2841-2923`.
   Regression: `test_multiple_body_pressure_is_averaged`.

4. **Spawn stagger target eligibility.** Exclude a waiting second Archer until its stagger expires. Ordinary deployment delay after that boundary remains targetable.

   Python reference: `src/clasher/entities.py:703-717`.
   Regression: `test_staggered_archer_is_not_a_combat_candidate`.

5. **Phase-dependent keep-target range.** Use 25 units for mobile characters, zero for buildings, and 500 only for a started projectile hit whose phase exceeds 50 ms. Rust previously gave everyone 500.

   Python reference: `src/clasher/entities.py:2097-2156`.
   Regression: `test_melee_keep_range_does_not_use_projectile_extension`.

6. **Retained attack-clock reach and windup.** Track windup separately from an earlier completed hit. Continue an ordinary committed hit beyond initial engagement range when its phase exceeds 50 ms; clear windup on a shot or distant retarget.

   Python reference: `src/clasher/entities.py:2158-2179,1750-1813,3955-3969`.
   Regression: `test_started_melee_hit_continues_outside_engagement`.

7. **Crown fallback eligibility and no-King branch.** Apply pending-damage rejection to live fallback Crowns. When no eligible King remains, consider all Princesses before nearest selection, without applying the King-versus-Princess lane guard.

   Python reference: `src/clasher/entities.py:2535,2591-2594`.
   Regression: `test_crown_fallback_skips_live_pending_lethal_king`.

8. **Live projectiles from depleted eligible shooters.** A shooter killed earlier in combat can still fire under start-of-phase eligibility. Its new projectile starts alive; it must not inherit the depleted shooter flag.

   Python reference: `src/clasher/battle.py:818-840`, `src/clasher/entities.py:2993-2998,4075-4171`.
   Regression: `test_depleted_eligible_archer_emits_live_projectile`.

9. **Simultaneous King outcome resolution.** Resolve both Kings together after cleanup and declare a draw when both die. Count only King Building objects; source markers on their surviving projectiles do not keep a King alive.

   Python reference: `src/clasher/battle.py:2506-2522`.
   Regression: `test_simultaneous_king_deaths_draw; test_king_projectiles_do_not_keep_destroyed_kings_alive`.

10. **Tower acquisition load and pending-hit resume.** A fresh in-range acquisition advances passive load before active work. A resumed pending hit sets windup first and suppresses that extra load. The hidden cooldown drift began ten ticks before the missing shot.

   Python reference: `src/clasher/entities.py:1579-1597,1766-1770,4912-4938`.
   Regression: `test_tower_acquisition_consumes_passive_and_active_load`.

11. **Live Crown deployment footprint rejection.** Reject inclusive Princess 1.5-tile and King 2-tile square footprints before payment or spawning. Test all four cards and both seats, including unchanged state on rejection.

   Python reference: `src/clasher/arena.py:175-190,252-282`.
   Regression: `test_live_crown_footprint_rejects_without_payment`.

## Convergence and failed intermediate runs

Each semantic edit was followed by the full original twelve-case replay before
the next root cause. No commits were made; pre-edit sources and intermediate
versions remain in `engine-rs/evidence-stage1b/`. Corrections to the same root
were replayed separately too.

| Completed correction | Mismatching boundaries in original twelve |
|---|---:|
| Baseline | 15,763 |
| 1 | 9,188 |
| 2 | 8,864 |
| 3 | 7,087 |
| 4 | 6,973 |
| 5 | 5,023 |
| 6 | 401 |
| 7, including no-King branch | 381 |
| 8 | 78 |
| 9 | 77 |
| 10, including resumed-hit branch | 0 |
| 11 and final outcome type guard | 0 |

The first root moved Knight case 0's first failure from 438 to 1176. After nine
roots, eleven games were exact; after ten, all original games were exact. The
non-convergence stop condition was not reached.

The first correction-7 attempt rejected the King but returned no Princess; the
second implemented the no-King branch. The first correction-10 attempt produced
1,693 mismatches because it advanced load twice for resumed pending hits; setting
windup at the Python transition fixed that interaction. Both failed receipts
remain available.

The first 24-case expansion incorrectly placed all added anchors on Princess
footprints. Its failed receipt is `stage1b_24_invalid_anchors.json`. This exposed
root 11, but twelve idle games would not provide useful acceptance evidence, so
the final added cases use valid depths and shifted lanes. The next expansion had
one terminal mismatch: the new outcome scan counted King projectiles as Kings.
The type guard refines correction 9, rather than adding another original root.
That receipt is `stage1b_24_before_king_type.json`.

A correction-6 build's import child received SIGKILL while another test had
loaded the preceding extension. Fresh import passed and the completed replay
was relaunched after the prior driver exited. The final serial build/test/replay
sequence avoids concurrent extension replacement.

## Stage 2 decision and limits

**Go for Stage 2 implementation. Revised remaining estimate: 20-30 engineer-days**
for the sixteen pilot cards, including per-card differential fixtures and final
performance validation. Stage 1b is now complete, so the prior additional 8-12
Stage 1 days are no longer part of the remaining estimate. This is a planning
estimate, not a speed or completion guarantee for the larger engine.

No known mismatch remains in these 24 trajectories. Arbitrary placement, general
mid-game Python snapshot import, longer match horizons and the other twelve pilot
cards are unvalidated. The fresh-state adapter is not a general restore API.
The existing digest omits some internal clocks; the diagnostic snapshots help
reduce failures but do not prove universal internal equivalence. Python remains
the production reference, with no learner/backend integration in this task.

## Reproduction

From `/Users/sam/Desktop/code/clasher`:

```sh
bash engine-rs/build.sh
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/test_parity.py
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/differential.py --games 24 --output reports/strategy_council_20260928/engine-speed/results/stage1b_24.json
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/differential.py --case 0 --bisect-tick 438 --skip-primitives --output /tmp/clasher-stage1b-tick438.json
```

The completed detached sequence is `engine-rs/evidence-stage1b/validate_final.sh`.
Source/binary hashes and preservation checks are recorded in
`results/stage1b_manifest.json`. All 32 hashed Python engine source files remain
unchanged. No protected directories, unrelated processes or Git history were
modified. Cargo intermediates are removed after validation; the local extension
and small reproducible evidence remain. Total task output stays below 1 GiB.
