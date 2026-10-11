# SOL independent core review r1

**Verdict: APPROVE_WITH_FIXES.** Findings 1–4 are MAJOR and must be resolved before freezing/admitting this runtime. This is approval of the core approach conditional on the fixes, not approval to begin reporting.

Reviewed read-only in `/mpac/sdicks02/repos/clasher-k4s-prep`, based on HEAD `38c195b86b636dd0f05e7f85345ac8720ba62985` plus the working-tree changes observed during review. The preregistration SHA is `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. Paths below are relative to `reports/explore/k4s-confirm/` unless stated otherwise. No network, SSH, commit/push, game outcome data, or `reports/explore/x4s2/receipts` was accessed. The only file written by this reviewer is this review.

## Findings

1. **MAJOR — Qualification always fails on the regenerated guard receipt's timestamp.**
   **Location:** `qualify.sh:20`; supporting implementation `select_guard_decks.py:60` and frozen `guard-decks.json:2`.

   The new `cmp` compares the entire freshly generated support receipt with the frozen guard file. The generator inserts `utc=utc()`, whereas the frozen file contains `2026-10-10T14:29:50Z`. Thus a correct regeneration on any qualification host today fails byte comparison, and `set -e` exits before either 125-state qualification or the belief battery. The newly added receipt assembler also compares these entire receipt hashes, so merely bypassing the shell comparison does not repair admission.

   **Suggested fix:** Keep checking the exact SHA of the frozen `guard-decks.json`. Compare the regenerated receipt's deterministic deck/catalogue/selector/support/native-execution projection to the frozen projection, excluding its generation timestamp. Bind the fresh receipt separately in the qualification evidence. Do not rewrite the frozen guard file or replace its original timestamp in the fresh receipt to manufacture byte equality.

2. **MAJOR — The game checker accepts missing qualification groups and exits successfully on explicit failures.**
   **Location:** `check_games.py:55`, `check_games.py:79`, `check_games.py:90`, `check_games.py:99`.

   Only the no-deadline groups have a required inventory. If both charged directories and the zero-budget directory are absent, their loops run zero times: `charged_all_within_tolerance` remains true, `zero` is empty, and `passed` is true. Missing individual arms or an empty decision list can similarly evade the charged checks. Conversely, a measured charge failure appends an error and writes `passed=false`, but `main()` then returns normally, so a shell running the checker under `set -e` sees success. The new separate `qualify_games.sh` does not inspect the JSON after invoking it. The new receipt assembler checks `games['passed']`, but its empty-group `all(...)` checks cannot detect the first case.

   **Reproduction:** With entirely in-memory qualification projections, valid no-deadline hashes plus no charged/zero fixtures produced `passed=true`, `charged={}`, `zero={}`. Supplying a K4-160 decision with a 10 ms poll and zero charge produced `passed=false` and `charge share outside tolerance`, but `main()` still returned normally.

   **Suggested fix:** Require the exact expected seeds, arms, populations and game counts for every group, nonempty decision records, and required path coverage. Validate all required metadata even on the zero-budget group. Write the diagnostic receipt, then exit nonzero on any failure. Apply the charge/field checks to the excluded smoke as required by r3 §4.1; `health.py:30` currently checks only inherited lateness/C17 fields.

3. **MAJOR — Descriptor validation trusts supplied rotation/index fields, permitting wrong rotations and duplicate seeds into a sealed run.**
   **Location:** `schedule.py:42`, `run.py:348`, `reduce.py:116`, `reduce.py:121`, `reduce.py:123`.

   `expected_order(d)` reconstructs the order from the descriptor's own `rotation` and `subsample`, rather than computing them from the logical original. Therefore `primary-0050` with rotation 0 and the matching rotation-0 order passes the runner even though r3 requires rotation 1. In the reducer, logical uniqueness derives from `id`, while the seed check uses the independent supplied `index`: an original descriptor with `id=primary-0000`, `index=1`, and `seed=base+1` is accepted and reuses primary-0001's seed. Replacement validation compares only cell/replaces/order with the ledger; it does not rederive the bank index, k, caps or inherited rotation. The reducer also no longer enforces T1's across-arm equality of decks/seat, and does not validate the expected deck mapping.

   **Reproduction:** The actual `load_blocks()` accepted an entirely virtual 3000-primary/900-guard fixture containing both the wrong primary-0050 rotation and the primary-0000 index/seed mismatch. No game files were created or opened.

   **Suggested fix:** Add canonical descriptor validation before the runner opens an attempt: id/population/index relationship, index range, seed, cell, seat/deck mapping, logical-original rotation/subsample, and exact arm order. Revalidate in the reducer; independently derive replacement k/index/caps and compare the whole descriptor to the ledger. Check identical expected decks across the paired arms and reject duplicate reporting seeds. The independent verifier has stronger checks and should detect these examples if run on the exact inventory; that would protect admission but would only discover a wasted/invalid sealed run after collection.

4. **MAJOR — Required injected-clock equivalence of the complete K4 runner to frozen T1 is not qualified.**
   **Location:** `qualify_k4s.py:104`; `qualify_games.py:45`; `check_games.py:43`.

   The injected-clock comparison calls `core.score_candidates()` on already prepared roots and candidates. The whole-game comparisons disable deadlines. No qualification mode compares injected-clock decisions through the complete T1 and K4S `run_game()` paths on the qualification seeds, as explicitly required by r3 §4.1. A regression in observation/poll/preparation timing, belief cancellation, submission or lateness can therefore pass every current equivalence check. This matters here because the runner adds clock reads and preparation bookkeeping outside the collector being compared. The newly added game script still runs only no-deadline, charged and zero-budget modes.

   **Suggested fix:** Add a shared deterministic clock/work-duration harness around both complete runtimes, with deadline-enabled K4-200 qualification games. Compare decisions, candidate/RNG states, cancellation points, submitted commands and lateness under boundary cases covering belief, prescan, sample, scoring and overrun. Keep instrumentation clock reads from advancing simulated work merely because the new runner records more fields. Bind this evidence for every named host. The supplied collector-only injected-clock and no-deadline game evidence is useful, but does not satisfy this additional runner check.

5. **MINOR — Prespecified rate inference is omitted.**
   **Location:** `reduce.py:181`.

   Mechanism output flattens all decisions and emits pooled point percentages. There are no bootstrap intervals for cutoff, student-default, fallback, overrun or play rates, and no per-game numerator/denominator resampling. r3 §5.1 explicitly specifies that method for these rates. For example, games with 20 and 200 decisions contribute very different denominators; resampling their individual decisions would give a different uncertainty estimate from resampling their paired game-level counts. The current output cannot report the prespecified rate uncertainty at all. It also drops GC records from the loaded timing projection, preventing the r3 §5.3 GC tables, and does not produce the WAIT-spiral indicators.

   **Suggested fix:** Retain the necessary search/GC records, form per-game numerators and denominators, and stratify/resample those together on a disclosed secondary RNG stream. Emit rate CIs and the required mechanism/GC tables without changing the four primary bootstrap analyses or their RNG consumption.

6. **MINOR — Interference sensitivity uses the wrong exclusion flag and loses the inherited sidecar input contract.**
   **Location:** `reduce.py:125`, `reduce.py:159`.

   The sensitivity excludes `interference.interfered`, which the inherited supervisor sets for idle-service and DBus interference as well as SSH/apt. r3 §5.3 specifies OP-6/OP-7 exclusions from the sidecar ledger. A block with only a DBus flag is therefore excluded from the advertised sensitivity even when its SSH and apt flags are false. The comment on `population_stats()` says it supports the unchanged sensitivity sidecar, but `load_blocks()` no longer includes `complete_sha256`; the unchanged `ssh_sensitivity.analyze()` requires that field and raises `KeyError` when given these rows.

   **Suggested fix:** Preserve the complete-proof SHA, construct/verify the inherited final-inventory sidecar ledger, and use its source-proven SSH-or-apt flag for the prespecified sensitivity. If a broader any-interference sensitivity is useful, publish it separately with an explicit label. Retain the same subsample contrasts in the prespecified sensitivity rather than limiting it to the eight core arms.

7. **MINOR — Required decision and game audit fields are missing or misleading.**
   **Location:** `run.py:271`, `run.py:296`, `run.py:313`.

   For every scored plain-K4 decision, `anchor_x` supplies no `student_default` key, so the new common bookkeeping sets `frozen_action=None`. There is a known frozen action on this path: it is the K4 action just returned by the collector. A null is appropriate for preparation without a frozen scoring decision, not for every scored K4 record. The per-game output also lacks the requested slot and attempt-directory fields; `search_ab` provides host/affinity/nice but not those identities. The reused `extract()` output does not retain explicit final ticks/crowns/draw fields, despite the r3 §3.6 outcome-record table. These omissions do not alter the primary loss arithmetic, but reduce the promised auditability of the sealed study.

   **Suggested fix:** Record the returned K4 action as `frozen_action` on scored K4 paths; keep null semantics explicit on unscored paths. Supply slot and attempt identity from dispatch/runner placement and record terminal ticks/crowns/draw in the sealed game output. Extend the field checks to validate values/nullability and placement, not just key presence.

## Conformance evidence and limits

- Read the governing r3 clauses and implementation contract, all named scoped source/tests, the premade T1 diffs, and the specified X4S-2 reference code. The supplied qualification evidence was treated as context, not independently rerun against real game outputs.
- Independently verified **all 75 identical/rebound manifest entries** against `ef4c073a4c69e85aea0b6f9af9c1118ca8888a59`. The OP guard copies conform to their declared transformations. `rebind.py` proves equality/pure substitution for listed entries; it does not itself prove manifest inventory completeness. Rebuild and recheck the manifest after the concurrent edits/new helpers are finalized.
- Verified that `anchor_x.py` is byte-identical to X4S-2 and its AST equals frozen T1 `anchor.py` after removing the docstring and the three declared statistics fields. No other scoring/control-flow change was found. Static inspection found no additional RNG-consuming operation in the K4 path and preserves belief/candidate/root order, empty proposals, cutoff/reserve and lateness logic. Added timing/reporting calls remain a reason to complete finding 4.
- The K4S deterministic seat poll repeats the frozen cached threshold branch; cached proposals reorder coarse scheduling only. Candidate generation gets an empty proposal list, refinement proposals remain empty, and preparation cutoffs return the seat default. The full S-default rule is a faithful port.
- Executed **13 authored S-default tests**, **4 charge tests**, and **4 fixed-sequence/margin tests** in memory. The S-default tests used the real collector function loaded by AST to avoid unavailable external runtime dependencies, with its authored synthetic evaluators. The decision tests exercised the real reducer functions. No pytest temporary trees, commits, generated game files, or cache files were created. NumPy and pytest are unavailable locally, so the full staged-runtime suite and bootstrap end-to-end tests were not rerun.
- Independently checked 3900 scheduled blocks / 33000 games and inspected rotation, subsample insertion, 10:3 dispatch and chained replacement formulas/caps. Correct descriptors produced by `schedule.block()` conform to I-1/I-2/I-5; finding 3 concerns validation of their inputs/outputs.
- The poll charge is `(1/c-1)*poll_seconds`, within the existing observation-started timer and GC window, for every proceeding search-seat decision; c=1 never sleeps. The availability/wait checks implement I-3. Its lack of blocked-tick charge matches that declared interpretation.
- The primary reducer uses the declared four analysis order, shared stratified integer draws per analysis, rational linear percentiles, inclusive NI/veto/validity boundaries, strict SUP, fixed-sequence stopping, and strongest admitted levels. The veto only removes 0.9 usability. The concurrent change to `passed=null` for unreached steps was reread and is consistent with the revised comparison contract.
- The release check precedes block loading/game access. An in-memory denied-release probe confirmed the game loader is never called. The six prerequisite branches are SHA-bound to committed and working-tree bytes; no automatic K4S release or Mac-summary gate was introduced. Health/check projections do not access winner/loss/crowns fields. This is an ordering/schema review, not an authentication audit of external coordinator evidence.
- Concurrent changes to `qualify_games.py` now allow all four hosts and nice 10/19; the earlier host-03-only restriction is **not** a finding. The new separate game/receipt helpers were inspected only to understand whether they resolve the qualification findings above. Other new helper files remain outside this core review's requested scope.

## Reviewed source identity

Final checked SHA-256 values for files most directly implicated in the findings:

```text
run.py          684be9336b87f7545bf5139a6c270bb603b69e6414e2395de1c644dbd4125bc5
schedule.py     c805fcd39d3d776ebc1b3e49baa7ad987f51be67b0ba72f61144d96bbebae156
reduce.py       79985929946c980256ec2c1ab4ea50ed33af55feb1a7a4c23899e81f498ffc11
qualify.sh      510bbba20d985ab7d6cbecbe2ce6dcac630f637510adc09d4f19254915ff84a2
qualify_k4s.py  12bb640f5cf7343e6e98e750517c4428f47588f5f6442068280f4b9242518de4
qualify_games.py d63ccba15cf1ce0415195642520e744fbd56682c5672212aa45ec09475732fc3
check_games.py  cda257ccff35f15e8fb22cfe9507267a36f3f52f46979a86941255c833d93281
barrier.py      01a58c66573ad6f7bf116fdf03bd075f4f81991f67a8aa5d8ddf47343ad0b063
K4S-SPEC.md     d1bfb11c73f744ace219008632db54d38e0a5ddb4a80a3257af51c3e91f3e2ec
```
