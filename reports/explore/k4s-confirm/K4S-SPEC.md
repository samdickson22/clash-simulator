# K4S harness specification (PREREG-K4S r3 implementation contract)

Implementation contract for the PREREG-K4S runner, reducer and independent verifier.
- **Source:** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` (sha256 `9650972d…`), cited as
  "r3 §x". Where this file and r3 differ, r3 governs and this file is a bug.
- **Interpretation choices** that r3 leaves open are marked **[I-n]** and listed in §9 for the coordinator.
- **Author:** K4S prep worker (Opus), 2026-10-11. The independent verifier is written from this file and r3 only,
  without reading `reduce.py`.

## 1. Arms and cells (r3 §1.1, §2.2–2.4, §3.1)

Cell c maps to a budget of 200c ms, an inference_scale of 1/c and a charge sleep factor of (1/c − 1). Each arm is
named by its budget.

| Arm | Cell c | Budget (deadline_seconds) | Kernel | Seat policy | Seat default source | Block membership |
|---|---:|---:|---|---|---|---|
| `K4-200` | 1.0 | 0.200 | `K4-anytime` | `v1-unmodified` | v1 | core |
| `K4S-200` | 1.0 | 0.200 | `K4-anytime-sdefault` | `SD1-cached` | SD1 | core |
| `K4-180` | 0.9 | 0.180 | `K4-anytime` | `v1-unmodified` | v1 | core |
| `K4S-180` | 0.9 | 0.180 | `K4-anytime-sdefault` | `SD1-cached` | SD1 | core |
| `K4-160` | 0.8 | 0.160 | `K4-anytime` | `v1-unmodified` | v1 | core |
| `K4S-160` | 0.8 | 0.160 | `K4-anytime-sdefault` | `SD1-cached` | SD1 | core |
| `K4S-140` | 0.7 | 0.140 | `K4-anytime-sdefault` | `SD1-cached` | SD1 | core |
| `K4S-120` | 0.6 | 0.120 | `K4-anytime-sdefault` | `SD1-cached` | SD1 | core |
| `K4-140` | 0.7 | 0.140 | `K4-anytime` | `v1-unmodified` | v1 | subsample |
| `K4-120` | 0.6 | 0.120 | `K4-anytime` | `v1-unmodified` | v1 | subsample |

Settings shared by every arm:
- 4 scorer threads plus the main thread on a 5-physical-core slot;
- coarse_horizon 160, W-screen8;
- opponent: sealed v1 policy at T = 1, no search;
- d = 27, capacity 1, search interval 10 ticks, policy interval 5;
- return reserve 8 ms;
- honest lateness (§4).

**CORE order** (r3 §3.1 table order): `K4-200, K4S-200, K4-180, K4S-180, K4-160, K4S-160, K4S-140, K4S-120`.

## 2. Populations, cells, seeds (r3 §3.3–3.4)

**Cells.**

| Population | Cells | Cell of index i | Seat | Own deck | Opponent deck |
|---|---:|---|---|---|---|
| `primary` | 50 | i mod 50 | cell mod 2 | `guard-decks.json:primary[cell mod 5]` | `primary[(cell div 5) mod 5]` |
| `guard` | 18 | i mod 18 | cell mod 2 | `l2[(cell div 2) mod 3]` | `guard[cell div 6].cards` |
| `smoke` (excluded) | 50 | i mod 50 | as primary | as primary | as primary |
| `qualification` (excluded) | — | qualification only | — | — | — |

- These mappings are byte-identical to T1's `schedule.block()`.
- `guard-decks.json` is T1's file, pinned at sha256 `6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef`.

**Seeds.** For index i in range, seed = base + i.

| Range | Base | Indices |
|---|---|---|
| primary reporting | 4503605807370496 | [0, 3000) |
| primary replacement | 4503605807370496 | [3000, 3600) |
| guard reporting | 4503605817370496 | [0, 900) |
| guard replacement | 4503605817370496 | [900, 1080) |
| smoke | 4503605827370496 | [0, 8) |
| qualification | 4503605837370496 | [0, 8) |
| reserve | 4503605847370496 | [0, 64), unused |

The helper offsets used inside a game are inherited from T1 and are unchanged:
- own planner seed + 100000 (candidate RNG at +100001);
- opponent planner + 100002;
- policies seed + 271828 + seat.

## 3. Blocks, rotation, dispatch, replacement (r3 §3.1, §3.4)

**Logical index.** For a reporting block it is i. For a replacement block it is the logical index of the block it
ultimately replaces, following the `replaces` chain to its original. This is **[I-1]**: the replacement inherits its
original's rotation, arm set and cell.

**Rotation.** ρ = ⌊L/50⌋ mod 8 for primary and ⌊L/18⌋ mod 8 for guard, where L is the logical index.
- Rotated core: R = CORE[ρ:] + CORE[:ρ].
- Smoke uses ρ = i mod 8.

**Subsample.** The subsample is primary L < 600 and guard L < 300. Smoke blocks always carry all 10 arms.
- A subsample block's order is R[0:3] + [`K4-140`] + R[3:6] + [`K4-120`] + R[6:8]. Each subsample arm goes
  "after rotated positions 3 and 6", counting the 8-arm rotated core from 1. This is **[I-2]**.
- Any other block's order is R, 8 arms.

**Descriptor fields.** These are T1's fields, plus `rotation` and `subsample`:
- `id`: `{pop}-{index:04d}`;
- `population`, `index`, `seed`, `cell`, `seat`, `own_index`, `opponent_index`;
- `order` (list of arms);
- `replaces`: the logical original id, or null;
- `rotation` (ρ) and `subsample` (bool).

**Dispatch order.** Group g = 0..299 holds primary indices 10g..10g+9 followed by guard 3g..3g+2, which gives the
10:3 interleave. Hosts are assigned with T1's `assign_hosts` (B2 balancer), unchanged.

**Replacement** (r3 §3.4).
- k is 0-based. `replaces` is always the **logical original** id, not the immediately lost replacement.
- The k-th lost block in (population, cell c) is replaced by index 3000 + 50k + c (primary) or 900 + 18k + c (guard).
- Bank caps: k ≤ 11 primary and k ≤ 9 guard.
- Population caps: at most 300 primary and 90 guard replacements in total. Beyond any cap: stop and amend.
- Never-started blocks are re-dispatched unchanged.

## 4. Decision timing, charge and the S-default (r3 §2.3, §2.4, §4.3)

The decision timer starts at `wall0`, before observation. It is T1's `run_game` unchanged, except for the following.

**(a) Poll timing.** For the search seat, at search ticks (tick ≥ 90, tick % 10 == 0, own channel available and
not waiting), `poll_seconds` is measured as the monotonic span of `policies[seat].poll(...)`. Every arm does this.

**(b) Charge.**
- Immediately after the availability, waiting and tick%10 checks, and before the belief update, the seat sleeps
  `(1/c − 1) × poll_seconds` of wall time inside the timer: `make_charger(1/c)`, ported from X4S-2.
- At c = 1 it never sleeps.
- `scale_sleep_seconds` records the slept wall time. Blocked ticks are not charged. This is **[I-3]**; X4S-2 also
  charged on blocked search ticks, which had no game effect.

**(c) K4S seat poll.** `CachedPolicy(SD1, threshold)` with one forward per poll.
- The deterministic default is WAIT (2304) if P(play) < threshold or there is no legal play; otherwise it is the
  top-ranked legal play.
- `SD1 P(play)` is recorded from the same forward.

**(d) K4S coarse order.** `core.coarse_order` = SD1's top-8 ranked legal plays (proposals of the same forward). The
candidate generator gets no proposals, so the candidate set is unchanged.

**(e) K4S cutoff default** (`sdefault.apply_default`, the full rule from X4S-2).
- A preparation cutoff (belief, pre-scan, sample) returns the seat poll result, which is the SD1 default.
- At the scoring deadline, if no legal play has a complete score and the SD1 default is a play, return it with
  selected_wait_ticks = 0.
- Otherwise the frozen choice stands.

**(f) Kernel.** `K4-anytime` is `anchor_x.planner_class`, which is T1's `anchor.py` plus deadline_stats fields
`coarse_complete`, `coarse_scored` and `plays`.
- Its actions, candidates and scores equal T1's anchor. Qualification checks this on 125 fixed states, with no
  deadline and under the injected clock.

**(g) Lateness.** T1's `apply_lateness` is unchanged. A positive overrun is charged ceil(overrun × 20) ticks.

## 5. Per-game record (r3 §3.6)

Each game file is `games/{pop}-{index:04d}-d27-{arm}.json`. It is T1's `extract()` output plus the following.

**`cohort`** is the arm.

**`metadata`** contains T1's fields:
- `terminal`, `winner`, `seat`, `seed`, `cell` (the population cell), `population`, `seed_index`;
- `own_deck`, `opponent_deck`, `threads`, `coarse_horizon`, `kernel`, `deadline_seconds`, `opponent`, `arm`.

It also contains these fields:

| Group | Fields |
|---|---|
| Study and freeze | `study`=`PREREG-K4S` (with "SEALED"); `freeze_manifest_sha256` (sha256 of `FROZEN-K4S.json`, or null in qualification and smoke); `runtime_pin_sha256` |
| Arm settings | `speed_cell` (c); `budget_ms`; `reserve_ms` = 8; `inference_scale` = 1/c; `scale_mode` = `poll` |
| Defaults | `default_source` ∈ {`v1`, `SD1`}; `s_default_rule` ∈ {`full`, null}; `c_star` |
| SD1 | `sd1_manifest_sha256`, `sd1_checkpoint_sha256`, `sd1_calibration_sha256`, `sd1_threshold` |
| Pins | `opponent_checkpoint_sha256`, `native_sha256` |
| Placement | `rotation`, `block_id`, `replacement_k` |
| Charge totals | `scale_sleep_seconds` (game total), `scale_sleeps` |

**`search_ab.deadline_stats`** has one row per seat search decision. Each row holds T1's fields:
- `hit`, `fallback`, `completed`, `candidates`, optional `preparation_cutoff`;
- `unpruned_candidate_count`, `own_elixir`, `fallback_action`;
- `threads`, `coarse_horizon`, `default_source`;
- `wall_overrun`, `overrun_seconds`, `delayed_ticks`;
- `decision_tick`, `action`, `wall_seconds`.

It adds these fields:

| Group | Fields |
|---|---|
| Timing | `cpu_seconds` |
| Scan | `coarse_complete`, `coarse_scored`, `plays` (null on preparation cutoffs) |
| Actions | `frozen_action`; `student_default` (bool); `sd1_default_action`; `sd1_p_play`; `coarse_order_sha256` (the last three null for K4); `chosen_action` (= `action`) |
| Fallback | `fallback_used` (= `fallback`); `selected_wait_ticks` |
| Charge | `poll_seconds`, `scale_sleep_seconds`, `prep_seconds` (wall from `wall0` to the scoring call, or the whole decision when unscored), `scored` |
| Lateness | `positive_overrun_ms`, `charged_extra_ticks` (= `delayed_ticks`) |

- `search_ab` also keeps T1's other keys: `gc_maintenance`, `latency_seconds`, `cpu_latency_seconds`,
  `policy_cache_counts` and `command_sha256`.
- Block `complete.json` is T1's format: `descriptor`, `host`, `slot_cores`, `games{name: sha256}`, `interference`.
  `games` has 8 or 10 entries, as the descriptor's `order` requires.

## 6. Reduction (r3 §5.1–5.2, §1.2, §1.5)

### 6.1 Inputs and seal

The inputs are:
- the counted block tree (a directory of `<id>/complete.json`, hub-acknowledged when the host is not 127x01);
- the replacement ledger (`{"events":[{"lost":desc,"replacement":desc|null,...}]}`);
- the coordinator's release receipt.

The reducer verifies the release (§7) **before** opening any game file, or else runs only on a tree marked
`SYNTHETIC` (a `SYNTHETIC` file at the tree root) with `--synthetic`.

### 6.2 Counting

- A block counts if `complete.json` exists, every listed game SHA matches, its arm set equals its descriptor's
  `order` set, and its id is not a lost id in the ledger.
- Logical ids must be unique.
- The expected totals are exactly 3000 primary and 900 guard logical blocks, and exactly 600 / 300 of them in the
  subsample. Anything else is an error.
- Per game:
  - loss = 1 iff `winner` is not null and `winner != seat`;
  - draw iff `winner` is null;
  - a non-terminal game is an error;
  - `metadata.seed`, `cell` and `seat` must match the descriptor.

### 6.3 Bootstrap

- R = 10,000, from `rng = numpy.random.default_rng(2026101170)`, consumed in this exact order:
  1. primary full (3000 rows);
  2. guard full (900);
  3. primary subsample (600);
  4. guard subsample (300).
- **In each analysis:** rows are the logical blocks sorted by logical index. For each cell c in increasing order:
  - let the cell's rows be idx_c (ascending logical index), with n_c = |idx_c|;
  - draw = `rng.integers(0, n_c, size=(R, n_c))`;
  - resampled loss counts per arm += `M[idx_c[draw]].sum(axis=1)`, where M is the integer rows × arms loss matrix.
- One index draw is shared by every arm, and so by every contrast, within an analysis. This is **[I-4]**.
- The contrast X − Y in pp for resample r is 100 × (count_X[r] − count_Y[r]) / n.

**Percentile bounds.** These are exact rational linear percentiles, with the T1 convention:
- sort the R values;
- position = (R − 1) × q, with q = 1/40 (lower) and 39/40 (upper);
- interpolate linearly between the floor and ceiling order statistics with a rational weight;
- multiply by 100 / n.

The float value is for display only. **Rational values govern every gate.**

**Point estimate** in pp: 100 × (losses_X − losses_Y) / n.

### 6.4 Contrasts used by the decision

All use primary full unless marked otherwise.

| Contrast | Definition | Analysis |
|---|---|---|
| Δ_ref(c) | `K4S-b(c)` − `K4-200` | primary full |
| Δ_ref^G(c) | the same | guard full |
| Δ_same(0.8) | `K4S-160` − `K4-160` | primary full |
| Δ_same(0.7) | `K4S-140` − `K4-140` | primary subsample |
| Δ_same(0.6) | `K4S-120` − `K4-120` | primary subsample |
| veto(0.9) | `K4S-180` − `K4-180` | primary full |

### 6.5 Hypotheses and the fixed sequence

All bounds are upper 97.5th-percentile bounds. Margins are inclusive (≤), and SUP is strict (< 0).

| Hypothesis | Conditions |
|---|---|
| B(c), c ∈ {0.8, 0.7, 0.6} | Δ_ref(c) ≤ 10, Δ_same(c) < 0 and Δ_ref^G(c) ≤ 15 |
| A(c), c ∈ {0.8, 0.7, 0.6} | Δ_ref(c) ≤ 5, Δ_same(c) < 0 and Δ_ref^G(c) ≤ 10 |
| A(0.9) | Δ_ref(0.9) ≤ 5 and Δ_ref^G(0.9) ≤ 10 |

**Sequence.**
- With c\* = 0.9: H1 B(0.8), H2 B(0.7), H3 B(0.6), H4 A(0.9), H5 A(0.8), H6 A(0.7), H7 A(0.6).
- With c\* = 0.8: H4 is removed.
- Test in order and stop at the first failure. Everything after it is "not reached" and is not admitted.

**Admitted level.**
- For 0.8, 0.7 and 0.6: A if its A step passed, else B if its B step passed, else none.
- For 0.9: A if H4 passed, else none.

**Veto and usable cells.**
- veto_pass = upper(veto(0.9)) ≤ 5.
- Usable cells (r3 §1.5): 0.9 if A(0.9) and veto_pass; 0.8, 0.7 and 0.6 if admitted at A or B.

**Validity.** It passes iff 10n ≤ 100 × losses(`K4-200`, primary full) ≤ 30n. Otherwise the result's status is
`SUSPENDED` and admissions are reported but marked suspended.

**Output.** The output carries the `verifier_view` block of §6.7, plus:
- per-arm losses, draws, wins and n for each analysis;
- every contrast above, with its point, float CI and exact CI;
- the H-sequence record (each step: tested, passed, parts);
- admitted levels, usable cells, veto and validity;
- the plan and input SHAs.

### 6.6 Secondary and descriptive outputs (r3 §5.3)

These never change admission:
1. F1 in both populations.
2. The flagged-block sensitivity, on its own RNG stream `default_rng(2026101171)`.
3. The matchup-cluster bootstrap (`default_rng(2026101172)`).
4. Per host and per seat.
5. Mechanism rates.
6. Latency.
7. Draws as half-losses.
8. Monotonicity.

Rates use per-game numerator and denominator resampling.

### 6.7 Fixed comparison block (`verifier_view`)

The reducer output has a top-level `verifier_view`, and the verifier's `--compare` checks it key by key.

| Key | Content |
|---|---|
| `schema` | `clasher.k4s.verifier-view.v1` |
| `counts` | `counts[A][arm] = {losses, draws, n}` for A ∈ {`P_full`, `G_full`, `P_sub`, `G_sub`}: the 8 core arms in full analyses, all 10 in subsamples |
| `contrasts` | `contrasts[key] = {lower: [num, den], upper: [num, den]}`, the exact rational 2.5th/97.5th percentile bounds in pp |
| `sequence` | `[{step, hypothesis, tested, passed}]` in test order |
| `admitted` | `{"0.9", "0.8", "0.7", "0.6"} → "A" \| "B" \| null` |
| `veto_pass` | bool |
| `usable_cells` | list of strings, e.g. `["0.9", "0.8"]` |
| `validity_inside` | bool |

The `contrasts` keys are:
- `P_full:dref@c` and `G_full:drefg@c` for c ∈ {0.9, 0.8, 0.7, 0.6};
- `P_full:dsame@0.8`, `P_sub:dsame@0.7`, `P_sub:dsame@0.6`;
- `P_full:veto@0.9`.

## 7. Release barrier (r3 §4.5)

`outcome_release(repo, receipt)` asserts:
- `coordinator_thread` = `0523ae6f-baa3-4d4e-b233-b392671670db`;
- a non-empty `authorization_message_id` and `authorized_at_utc`;
- `commit` is an ancestor of HEAD.

The receipt shape is `{coordinator_thread, authorized_at_utc, authorization_message_id, study: "PREREG-K4S", commit,
items: {name: {path, sha256}}}`, with repo-relative paths. At that commit, `git show commit:path` must hash to the
declared sha256 for each of the six items, and the working-tree bytes must equal it:
1. `completion`: the completion receipt, a JSON object with `reporting_complete: true`, `outcomes_sealed: true`,
   `counted_primary_blocks: 3000` and `counted_guard_blocks: 900`.
2. `end_reference` plus `end_recheck`, or `ratio_unavailable_declaration`.
3. `production_checks` (PC1–PC4).
4. `verifier_receipt`.
5. `mac_procedure_manifest`.
6. `tiers_summary` or `tiers_release`.

Only then may game bytes be opened.

## 8. END reference cells (r3 §4.5 (a)–(c))

On the frozen T1 K4 speed corpus (300 states, inventory `81f2483e`):
- **(a)** No-deadline K4 and K4S work units, 3 repeats.
- **(b)** Deadline mode at 200 / 180 / 160 / 140 / 120 ms with the 1/c charge, 3 repeats: per-state cutoff,
  no-complete-play and fallback rates.
- **(c)** The SD1 and v1 poll span (`poll_seconds`) on every corpus state.

This runs in reference slot 0 while the other slots run the corpus loop (reporting load profile), with 1 Hz MHz
logging. Pooling follows r3 §4.5.

## 9. Interpretation choices for the coordinator

| Id | Choice | Why |
|---|---|---|
| I-1 | A replacement inherits its logical original's rotation, arm set and cell. | r3 §3.1 says "inherit the lost block's arm set". Rotation follows T1. |
| I-2 | Subsample arms go after rotated core positions 3 and 6 (1-based): `K4-140` after the 3rd, `K4-120` after the 6th. | r3 §3.1 text. |
| I-3 | The poll charge applies only at search decisions that proceed past the availability, waiting and tick checks. | r3 §2.4 says "in each search decision". X4S-2 also slept on blocked search ticks, which never affects play. |
| I-4 | One RNG; analyses in the order primary full, guard full, primary subsample, guard subsample; one draw per cell shared by all arms. | r3 §5.1 "shared across all contrasts within a population". |
| I-5 | Smoke blocks carry all 10 arms with ρ = i mod 8, and run 8 blocks per host on the same 8 smoke seeds. | Exercises every arm and charge path. r3 §4.1 needs ≥ 8 blocks per host and gives 8 smoke seeds. |
