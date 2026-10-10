# Review: T1 harness delta and reducer against the frozen PREREG (round 1)

Independent verifier/reviewer for coordinator `0523ae6f`, 2026-10-10 ~13:50 UTC. I am not the T1 worker, and I have
not edited any T1 file. Binding text: `PREREG-SEARCH-TIERS-r3-DRAFT.md` (sha `ef0db97a…`) and
`E4-V3-ADDENDUM-r3-DRAFT.md`, per `PREREG-SEARCH-TIERS-FREEZE-20261010.json` (commit `cc6410b2`); "r2" in them reads as r3.

## Verdict: **APPROVE_WITH_CONDITIONS**

- **Scope approved:** the runner, schedule, seed and barrier delta as it stands.
- **Not reviewed: the reducer.** The tiers reducer and `measure_tiers.py` do not exist yet. The freeze needs a
  round-2 review of the reducer. Its requirements are in §4 below.
- **Blocking before the freeze:** B1–B6.
- **Required, non-blocking:** N1–N6.

## Reviewed bytes (T1 tree, untracked, as of 06:45 local / 13:45 UTC)

`run.py c3d92adf`, `schedule.py 2c6dcf85`, `barrier.py ce41a98d`, `supervise.py 0d6d228c`, `pin.py 4b6b48aa`,
`stage.py 7a2a753d`, `host_audit.py fdce4819`, `audit_seeds.py 49578789`, `select_guard_decks.py 32002f7d`,
`qualify.py ef7162e4`, `common.py 36e5eec3`, `plan.json e9ff6fff`, `test_schedule.py 9485d2e3`, `test_barrier.py 9ae0aba6`.
These are 16-hex prefixes of the SHA-256. If any of these change, the corresponding verdict lapses.

## 1. Verified conformant

- **Provenance.**
  - The overlay files are byte-identical to the S1 R2 freeze. I recomputed `anchor`, `belief`, `cached_policy`,
    `gc_window`, `latency`, `planner`, `proposals`, `reference_timed_policy` and `qualify_belief`.
  - The K2 anchor (`anchor.py` `75a1b7d7…`) is byte-equal to `k2/planner.py` at the K2 freeze `3cf8919e`.
  - `inherited/k2/*` is byte-equal to `k2/*`.
- **The `run.py` diff against S1 is minimal and on-scope.** It changes:
  - the case tuple, which now carries seat, population and cell;
  - the C17 fields (`unpruned_candidate_count`, `own_elixir`, `fallback_action`, `threads`, `coarse_horizon`,
    `default_source`);
  - the calibration SHA assertion;
  - the game id `{population}-{index:04d}-d27-{arm}`;
  - the multi-host `main()`, with the `127x01` assertion removed (§3.1 items 1–3, 7).

  It also removes the `loss` print. The kernel, lateness, GC, timer and cache code is unchanged.
- **Arms (§2).** There are 8 arm-cells: {K0c, S, K2, K4} × {200, 160} ms, with an 8 ms reserve.
  - Threads are 1/1/2/4, and core widths are 1/1/3/5 (`threads+1` for the anytime collector).
  - K0c and S use the coarse-first kernel with v1-cached and R3a-cached respectively.
  - K2 and K4 use the K2-anytime kernel with v1-unmodified.
  - The R3a (`37509a43…`), calibration (`e3003533…`), threshold `0.5005528330802917`, v1 (`d77005d5…`) and native
    (`44874fd6…`) hashes are all checked at load.
- **Seeds (§3).** All seven ranges, including both replacement banks, match the PREREG table exactly.
  `seed-audit.json` is DRAFT-PASS: 56 range×offset checks against 109 historical intervals, over all 8 helper offsets
  on both sides.
- **Cells and dispatch (§3).**
  - The 4:1 primary:guard interleave and descriptive-last order are correct.
  - Primary uses 50 cells (48 seeds each). Guard uses 18 cells, 6 of size 34 and 12 of size 33. Descriptive uses 18
    cells of 4.
  - The cell → (seat, own, opponent) maps are bijective, and the primary map reproduces S1's
    `(i%2, i%5, (i//5)%5)`.
- **Replacement (§3.2).**
  - The k-th lost block in cell c gets index N + C·k + c, in the lost block's cell, including the guard case where
    600 mod 18 = 6.
  - Chains of lost replacements resolve to the logical original.
  - The caps of 240/60 replacements and k ≤ 8/5 are inclusive-correct.
  - Descriptive blocks are never replaced.
- **Stops.** The supervisor implements:
  - the console rule: more than one core for more than 60 s;
  - 8 slots if the console check is positive at launch;
  - the 24 GiB memory floor;
  - owned STOP files;
  - immediate stop on foreign compute;
  - no automatic relaunch;
  - pin verification on entry and exit.
- **Tests.** T1's `test_schedule.py` and `test_barrier.py` pass 7/7. I ran them read-only (`-B`, no cache, on 127x05).

## 2. Blocking conditions (fix before the freeze)

- **B1. The reducer, `measure_tiers.py`, the copy job and the replacement-dispatch CLI are missing.**
  `barrier.reporting_release` already requires `independent_reducer_review`. That flag must refer to a round-2
  review of the actual reducer bytes, not to this document.
- **B2. Static round-robin host assignment confounds the guard and descriptive cells with hosts, and strands work.**
  `schedule.main` assigns `host = hosts[n % len(hosts)]`, and `supervise.py` runs only its own rows. I checked this
  numerically with T1's own `blocks()`:
  - With 2 hosts, **all 18 guard cells sit on one host each, and guard seat ≡ host** (seat 0 → host 0, seat 1 → host 1).
  - With 3 hosts, all 18 guard cells still sit on a single host each. The descriptive cells behave the same way.
  - Primary is unaffected.

  Paired contrasts stay unbiased, but a per-host timing difference (cutoff and fallback rates differ by host; that
  is why the ±5% rule exists) is then aliased onto seat and deck cells in the guard. That defeats §3's purpose:
  "host loss and drift spread over both".

  Static queues also leave **no rule for unstarted blocks on a stopped or lost host**:
  - If they are treated as lost, one lost host consumes about 1,500 blocks, far beyond the 10% cap, which stops the
    study.
  - If they are silently dropped, cells are left incomplete.

  **Fix:** dispatch from one global queue in dispatch order, pulled by free slots on any admitted host, or use a
  block-hash host assignment. State in writing that **never-started blocks are re-dispatched under their own seed
  and are not losses**. Only in-flight blocks, and completed blocks not yet on the hub, are lost (§3.2).
- **B3. Completed blocks can be marked failed, which risks double counting.**
  In `supervise.py`, `good = rc==0 and complete.json exists and not reason`. A block whose child exits cleanly in the
  same poll in which a stop reason is first set is recorded `complete=False`. It then gets a replacement, while
  `complete.json` is still on disk. A reducer that globs `*/complete.json` would count both blocks, giving 49 in
  that cell.

  **Fix:**
  - Decide completion only from `rc==0` and `complete.json` (§3.2 loses *in-flight* blocks only).
  - Make a single authoritative ledger (exits plus hub-ack plus the replacement ledger) the reducer's only source of
    counted blocks.
  - Assert exact per-cell counts.
- **B4. The off-host copy rule is incomplete.**
  - The 30-minute unacked check globs `j/'reporting'` only, so replacement-phase blocks are never checked.
  - The copier and the `hub-ack.json` protocol are not written.
  - "Counts only when on the hub" therefore cannot be evaluated yet.
- **B5. The 98.33% level is rounded.**
  `plan.json` has `confidences: [0.9833, …]`. §1 defines V1/V2 as Bonferroni over 3 tiers, and §5 says "full float
  precision with no rounding". So the level is **1 − 0.05/3**, which gives two-sided percentiles 0.8333… and
  99.1666…, not 0.835 and 99.165.

  **Fix:** use the exact value, or have the coordinator rule otherwise in writing. My verifier computes both and
  flags any gate whose decision differs between them.
- **B6. The outcome barrier has a path the PREREG doesn't.**
  In `barrier.outcome_release`, `reason=='explicit_coordinator_release'` returns without any check. §6.6(b) allows
  exactly two paths:
  - a committed `tiers-summary.json`;
  - the 14-day escape, counted from the completion of reporting.

  **Fix:** replace the bare release with `fourteen_day_escape`, which requires a committed reporting-completion
  receipt and `authorized_at_utc ≥ completion + 14 d`. Any other release is a PREREG amendment, not a barrier reason.

## 3. Required, non-blocking

- **N1. Host set.**
  - `plan.json` names 127x01 and 127x03, with 08 optional and 04/05 forbidden. With two hosts, losing one is a §3.2
    "fewer than two hosts" stop-and-amend.
  - Name 08 at the freeze if it qualifies, and disclose the exclusion of 04 (it is the hub mirror).
  - Wall time is about 2× the §0 estimate on 22 slots.
- **N2. Stale plan text.** `ordering.blocks` still says "all five arms … same three-core slot". It should say eight
  arm-cells on a five-core slot. `compute.game_physical_cores`, which S1's reducer used, is gone; the reducer must
  derive core widths from `threads`.
- **N3. Sealing leak.** `run.py` prints `ticks` (game length) per game into the supervisor logs. Game length is
  outcome-correlated, and §11 step 6 allows only completion, timing and pin receipts to be read. Drop `ticks` from
  stdout; it stays in the sealed game JSON. Per-game wall and CPU time are timing receipts and are fine.
- **N4. Guard decks (E1).**
  - `select_guard_decks.py` re-types the R1 L2 decks instead of binding to `imitation/exit_r1/emitter.py`
    `decks()`. The list is byte-equal today, so add an equality assertion against the emitter.
  - `guard-decks.json` is not produced yet. Before the freeze it must equal the PREREG §3 list (Hog EQ; Goblinstein
    Royal Hogs; ArcherQueen Royal Delivery) **unless** the support filter skips a deck. Goblinstein and ArcherQueen
    are champions, so they are the likeliest skips. Any skip must be listed in `skipped_unsupported`, and the
    re-check of later picks must be visible in the output.
- **N5. C17 detail.** `unpruned_candidate_count` is `None` on belief-preparation cutoffs, and it counts candidates
  after removing 2305. Document this in the report's field table.
- **N6. Smoke admission.** `SMOKE-PASS` is a bare marker file with no producer yet. It should be written by a
  script that checks smoke timing and metadata only, never smoke outcomes.

## 4. Requirements for the reducer (round-2 review checks these)

1. **Inputs.** Only blocks counted by the authoritative ledger (B3), on the hub, with all 8 game SHAs matching
   `complete.json`. Never smoke or corpus seeds. Descriptive blocks are never in a gate.
2. **Counted outcomes.**
   - Loss = `winner is not None and winner != seat`. A draw is a non-loss.
   - Report wins, losses, draws and n per arm-cell and population, as integers.
   - **A non-terminal game is a validity failure (assert). It is never dropped and never counted as a non-loss.**
3. **Bootstrap.**
   - 10,000 resamples from `numpy.default_rng(2026101040)`, with one index set shared across all contrasts.
   - Stratified: within each cell, draw n_c with replacement from that cell's counted seeds. A replacement seed sits
     in its lost block's cell.
   - **Document the exact draw order and export each population's index matrices (`.npz` plus SHA-256).** The
     verifier's default order is a single generator, primary cells 0–49 and then guard cells 0–17, each drawing
     `integers(0, n_c, size=(10000, n_c))` with seeds sorted by index. Matching that order gives bit-exact agreement.
4. **Intervals.**
   - Use the `numpy.percentile` default (linear) percentile on integer count differences, scaled after the
     percentile.
   - The two-sided levels are 1 − 0.05/3 (V1, V2), 0.975 (NI) and 0.95 (G1, G2).
5. **Gates, exactly as written.**
   - V1: upper bound ≤ −10.
   - V2: upper bound ≤ 40.
   - NI: upper bound ≤ +5.
   - G2: upper bound ≤ +10.
   - **G1: upper bound < 0 (strict, as written in §1, notwithstanding §5's "inclusive" sentence).**
   - Validity: K0c@200 loss in [36%, 54%], inclusive.
6. **All cell combinations.** Compute V1 and G1 for every tier cell against both control cells, and NI and G2 for
   every pair of tier cells, so that §6.5 re-application after formal E4 needs no new reduction.
7. **Selection.** Selection is a pure function of the Mac cell map and the gate table, implementing §6.5 including
   F0, "cheapest with NI ∧ G2 against every costlier member of A", and "else most cores".
8. **Output.** Emit no outcome number before release (B6). The verifier needs to match on these keys:
   - for arms: `{population, arm, n, wins, losses, draws}`;
   - for contrasts: `{population, left, right, point_count_diff, lo/hi at each level}`.

## 5. Independent verifier

`reports/explore/t1/verifier/verify_t1.py` is under construction. It is my own code and imports nothing from T1. It
will recompute everything in §4 from raw game JSON using integer counts and exact `Fraction` threshold tests. It
flags:
- mismatches with T1's reduction;
- exact boundary hits;
- bounds within one count step (100/n pp) of a threshold;
- float-versus-exact disagreements;
- 0.9833-versus-exact-Bonferroni decision flips.

It has been tested on synthetic data only.
