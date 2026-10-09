# Independent review: proposed clock-recovery amendment (option B), 2026-10-09

The reviewer worked read-only on 127x05. No jobs were run, and no validation or heldout outcomes were opened or computed. Inputs read:

- `CLOCK-OPTIONS.md` and `amendments/11-capture-clock-attribution-20261009.md`.
- `PREREG.md`, amendments 04–10, `BODY-SELECTION.md`, `BRANCH-CLOCK-QUALIFICATION.md`, and the runbook tail.
- DESIGN §5.1 and the newest sections of `PROGRESS-T6T7.md`.
- Receipts: `clock-attribution-incident-0045.json`, `branch-clock-probe-15r1.json`, `branch-clock-isolated-15r2.json`, `standalone-cost-plan-r1.json` and `timing-sample-cost-proposal.json`.
- Code: `scoring_v4.py` (`match_events`, `score_events`, `select_threshold`, `select_epoch`) and `validation_replay_v4.py` (the measured FIFO driver and its validator).

## Verdict

**APPROVE WITH REQUIRED CHANGES.** I approve a prospective, validation-only *selection-procedure* amendment. **I do not approve B's modeled availability as a selection score.** Modeled clocks must not decide, or appear to decide, any T7 epoch, global event threshold, per-card threshold or isotonic calibration.

The required replacement, B′ ("measured dominance selection"), is defined below. It uses no modeled clocks. It reproduces exactly the selection that full A would produce from the same measured runs, and its expected cost is close to the coordinator's 10–15 GPU-hour preference. B's sampled service model survives only as an optional, separately gated Tier 2 pruning aid (§4). It never scores a finalist.

Full A is not needed as currently costed: its body-stage clocks are irrelevant to selection (Finding 1). A remains the automatic fallback only in the sense that B′ degrades to "measure every event cell in bound order", which is the clock-relevant part of A.

## Findings that drive the verdict

### F1. The body stage needs no clocks, so A and B are both scoped on the wrong factor.

Body thresholds are selected by source-frame body F1 (`BODY-SELECTION.md`): "source-frame body diagnostics, not event availability". The scorer header says the same ("not availability or Mac gate"). Selecting one body threshold per epoch is therefore clock-free. It can proceed now from the record-only captures, provided their non-clock records are admitted under amendments 04/07.

The only clock-dependent decisions are:

1. Global event threshold within each epoch, and epoch choice. Both use opponent F1 at 500 ms, then precision, then higher threshold or earlier epoch (`scoring_v4.select_threshold` / `select_epoch`).
2. Per-card event thresholds in the selected epoch.
3. Isotonic calibration on the combined per-card replay, whose TP/FP labels depend on 500 ms availability.

`validation_replay_v4` passes the event threshold into the runtime. Each (epoch, event threshold, selected body) cell is therefore its own runtime configuration with its own clock. The 24 × 9 × 64 body-branch passes priced as "A's body stage" (~195–198 GPU-h) buy nothing for selection.

B's 8 + 8 sample is drawn over the same irrelevant factor: 24 epochs × 9 body branches at event 0.5. It never samples the event-threshold axis, which is the axis that actually gets ranked with clocks. As proposed, B would calibrate a model on configurations that are not the ones it must predict.

### F2. A rigorous, model-free optimistic bound exists, so most cells never need a clock.

From the code:

- `validation_replay_v4` enforces `available = max(ready, stamp) + service` with `service >= 0`. Hence `available >= stamp` (the production time of the emitting frame) for every possible measured run.
- `scoring_v4.match_events` is maximum-cardinality, then minimum-latency. The blocked cost `(min+1)*501` exceeds every combination of valid edges. An edge is valid iff `exec <= available <= exec + 500` (point mode).
- `score_events` counts every prediction and every truth event regardless of availability. P and T are therefore clock-independent, and opponent F1 = 2·TP/(P+T) and precision = TP/P are both increasing in TP.

Define the **superset edge rule**: edge (p, t) is bound-valid iff `stamp(p) <= exec(t) + 500`, with the same card/side/kind key and no lower end. Any edge valid under any measured clock is bound-valid. The lower end is dropped deliberately: a prediction produced before the true execution can become valid when its availability is delayed, so simply setting `available := stamp` is not a valid bound. The maximum matching on the superset, TP_ub, therefore satisfies TP_ub ≥ TP_measured for every realization, and so does the rank key (F1_ub, precision_ub).

Every input is in the bit-exact non-clock records: frame timestamps, candidates and truth. Computing the bound needs no GPU.

### F3. Fleet clocks are host- and contention-dependent by a factor of about 6.

The fleet clocks are measured, but they vary widely between hosts:

- On host 09, epoch 1 single-branch runs had median service 5.29–5.32 ms (warm p95 40–54 ms).
- In the cost pilot on host 15 (contended), epoch 20 ran at about 30.9 ms mean per frame (74.7 s / 2416 frames).
- With service near the inter-frame interval, FIFO backlog is highly non-linear.

Any measured cells compared against each other in a selection must be measured under controlled, recorded conditions, or host noise decides the selection. This applies equally to A. It is a further reason to reject a service model calibrated in one contention regime and applied as truth.

### F4. The process-lifecycle policy is not yet frozen, and B assumes the wrong one.

The admitted single-branch reference ran one process per cell, with matches in order:

- `1975100708`, the first match, had lag max 2312 ms (the cold start).
- `0718` and `0728` had lag max 92–95 ms (warm).

The cost pilot and B's plan instead use a fresh CUDA process per match, which adds one ~2.4 s cold-start backlog per match. Cold start dominates the 500 ms eligibility of early-match events. The validation policy therefore has to be frozen and kept identical in the later heldout replay.

### F5. B's timing-test list is contaminated.

`v4-phase-a-1975100708` is listed as a timing-test match. It is also the match used for:

- the incident comparison,
- both prefix probes (15r1 and 15r2),
- the cost pilot, whose standalone clocks have already been inspected and have shaped the proposed cold-start term.

It cannot serve as a held-out test of a model designed after seeing it.

### F6. With 8 test matches, any error claim is underpowered.

The 8 proposed test matches carry 338 accepted events across both sides (about 169 opponent events) and give only 8 independent clusters. Even with zero observed eligibility flips:

- The rule-of-three upper bound is 0.89% (both sides) or about 1.8% (opponent).
- Any match-clustered interval has 7 degrees of freedom.

One opponent TP is about 0.06 pp of validation F1 (P+T ≈ 3,300). The sample cannot certify an error small enough to decide close selections, and close selections are exactly where the clock matters.

## 1. Admissibility

**B as proposed is a change of measurement, not an implementation detail.** PREREG defines availability as "output completion, including FIFO backlog" and selects "by opponent validation F1 at 500ms" on that definition. Replacing measured completion with `available_hat` changes the measured quantity used for selection. It would be admissible only as a dated, prospective, disclosed deviation. Every validation number derived from it would have to be labelled "modeled", and any decision near a tie would be uninterpretable (F6). I do not approve it as the decision score.

**B′ is compatible with the frozen requirement.** In B′:

- Every cell whose validation F1 decides the outcome (the winner, and any cell not strictly dominated) is scored only from measured completion plus FIFO.
- Every unmeasured cell is excluded by a bound that holds for **every** measured realization (F2).

The selected configuration is therefore exactly what A would select given the same measured runs for the measured cells. It still needs a dated prospective amendment, because it changes the procedure and tooling (`select_epoch` currently demands 24 complete measured rows). It also needs this disclosure in RESULTS, the seal and any L2-v4 entry evidence:

> "T7 validation selection used Amendment 12 measured-dominance selection: N of 216 event cells were measured standalone with measured completion+FIFO; the remainder were excluded by a zero-service optimistic bound that cannot exceed any measured outcome. No modeled availability entered selection, per-card thresholds or calibration."

**Heldout is unaffected.** It stays measured in the actual selected runtime:

- Fleet heldout replay remains diagnostic.
- The Mac primary endpoint and the Mac p95 ≤ 40 ms row remain BLOCKED until genuinely measured.
- The 95/95 (LB 92) gates and the separately reported S5 90/90 (LB 87) L2-entry gates are unchanged.
- `noise-measured.json` takes heldout measurements only. It contains no bounds, no modeled values and no validation clocks.

**C is not admissible** for selection or for any gate.

- This task is barred from Mac work.
- No per-frame Mac measurements on validation frames exist.
- The Mac runtime is pipelined on different hardware, so a Mac latency distribution grafted onto fleet frames is itself a modeled clock from another device.
- C may later serve only as a labelled sensitivity analysis, after genuine Mac E4 measurement.

## 2. Required procedure (B′) and model specification

### 2a. B′ procedure (Tier 1, mandatory)

0. **Preconditions.** Non-clock records for every (epoch e, event threshold τ, body b*(e)) cell come from a path admitted bit-exact under amendments 04/07/08. Quarantined clock fields from the shared, packed or vectorized drivers, the epoch 1/2 CPU grids, and any clock copied from the event-0.5 run to another τ are never read.
1. **Body.** Select b*(e) for all 24 epochs with the existing clock-free body selector. Record it and seal it as an intermediate receipt before any bound is computed.
2. **Bounds.** For each of the 216 cells, compute (TP_ub, P, T), then F1_ub and precision_ub, for opponent events in point mode, using the superset edge rule and maximum-cardinality matching. Use the unchanged scorer otherwise. Write all 216 bound records with SHAs.
3. **Order.** Sort cells by the selection key (F1_ub, precision_ub, −epoch, threshold), descending. Within-epoch ties prefer the higher threshold and cross-epoch ties the earlier epoch, which is equivalent to the hierarchical rule in `scoring_v4`.
4. **Measure.**
   - Measure the next unmeasured cell in that order, standalone, with the unchanged admitted `validation_replay_v4` single-runtime driver, at its actual τ and b*(e), over all 64 matches.
   - Score it with the unchanged scorer. Keep the incumbent: the measured cell with the highest measured selection key.
   - Remove every unmeasured cell whose bound key is **strictly below** the incumbent's measured key, compared lexicographically on (F1, precision, then tie-break). Equal keys are not eliminated; they are measured.
   - Repeat until no unmeasured cell remains.
5. **Winner.** The incumbent at termination is the selected (epoch, global τ).
6. **Selected epoch.** Measure all 9 τ cells of the selected epoch (some may already be measured in step 4). Fit per-card thresholds from measured clocks only, using the registered ≥10-event rule.
7. **Combined configuration.** Measure the combined per-card configuration standalone (64 matches). Fit isotonic calibration on its measured TP/FP labels, using the registered ≥20-prediction and pooled rule. Seal.

Expected cost at the contended observed rate (32.3–32.9 fps) is about 106,744 / 32.6 ≈ 3,270 s ≈ **0.91 GPU-h per full 64-match cell**:

- Minimum: 10 cells (the selected epoch's 9 plus the combined configuration), about 9 GPU-h.
- Every extra finalist from step 4 adds about 0.9 GPU-h.
- The worst case is all 216 cells, i.e. the clock-relevant part of A (~197 GPU-h). It never exceeds A, and its result is identical to A's.

If two GPUs and the frozen host policy are available, finalists can run in parallel only under the matched-condition rule in §2c.

### 2b. Tier 2 (optional; only if Tier 1 is not closed after a frozen budget)

Freeze a Tier 1 budget of **30 measured cells**. If unmeasured, undominated cells remain after 30 measured cells, the owner may either:

- (i) keep measuring, which is the default and always admissible; or
- (ii) invoke Tier 2, which uses a modeled clock only to **eliminate** cells, never to select or score one.

Under Tier 2:

- Eliminate an unmeasured cell c only if `F1_hat(c) + Δ < F1_meas(incumbent)`, where Δ is the frozen error margin from §4.
- Precision is used only as an exact-tie tiebreak among measured cells.
- The winner and every non-eliminated cell remain measured.
- The disclosure must then say "modeled pruning with tested margin Δ". That is weaker than Tier 1 and must be reported as such.

If Tier 2 is ever invoked, the model must be specified and frozen exactly as follows **before** any Tier 2 fit.

- **Unit and recursion.** Per frame i of each match, `available_hat[i] = max(stamp[i], available_hat[i-1]) + service_hat[i]`. Reset per match exactly as the driver does: `ready = times[0]`, and service of frame 0 includes the first block fetch.
- **Process lifecycle.** The process-lifecycle policy of §2c applies: cold start falls on the first match of the cell's frozen order only.
- **Additive terms.**
  - **Cold term.** The cold first-frame cost is the median of measured process-first frames on the frozen host. It is applied only where the frozen lifecycle puts a process start.
  - **Block-fetch term.** One coefficient for frames with `i % block_size == 0`.
  - **Warm service.** Linear in per-frame counts taken from the non-clock records of *that* cell: body detections and tracks under b*, births, event candidates above τ (peaks decoded), emitted events after fusion/NMS, and publication payload bytes.
  - No epoch, match, threshold or body dummies. Configuration enters only through these observable counts.
  - No truth, correctness or label-derived feature. No heldout data.
- **Fit.** Median (L1) regression on measured warm frames from the measured Tier 1 cells only, with a fixed solver, tolerance and deterministic tie order.
- **Residual tails.** Residuals are reproduced by a moving-block bootstrap: block length 64 frames, R = 50 replicates, seed `clasher-v4-tier2-20261009`.
- **Cell score.** For each replicate, run the FIFO recursion and score. F1_hat(c) is the **maximum** over replicates, which is optimistic and therefore conservative for elimination. A point-mean service is forbidden: E[max] ≥ max E, so mean service understates backlog.
- **No trimming.** No winsorizing, dropping cold starts, dropping stalls, or tuning on test cells.

### 2c. Measurement conditions (frozen for Tier 1, Tier 2 and the later heldout fleet replay)

- **Driver.** The unchanged admitted `validation_replay_v4` single-runtime measured-completion driver, pinned by SHA. Not the attributable shared candidate, which FAILED 15r1/15r2, and not the vectorized quarantine.
- **Lifecycle.** One fresh CUDA process per cell. All 64 matches run in lexicographic episode order with per-match runtime state reset, and the cold start is retained on the first match. This is the admitted reference behaviour (F4). The heldout fleet replay must use the identical lifecycle.
- **Host.** One frozen host class with recorded GPU model and driver. No other GPU process on the measuring GPU during a cell. Sample `nvidia-smi` and load at least every 30 s into the cell receipt. If foreign GPU work or MemAvailable below 24 GB is observed during a cell, the attempt is void-but-retained and is rerun with an identical seed and input.
- **Paired finalists.** Any two cells whose measured keys decide the winner must be measured on the same host under the same policy.
- **Reproducibility check.** Measure the winner and the runner-up a second time, after selection is fixed. Report whether their order flips. A flip is disclosed as clock-noise sensitivity and is **not** grounds for reselection. The first scheduled measurement is the selection measurement.

## 3. Sample size and representativeness

- **Is B's 8 + 8 necessary?** No, because it samples the wrong axis (F1). Under B′ the relevant configurations are measured in full, and B's calibration sample becomes unnecessary.
- **Is 8 + 8 sufficient?** No, for a decisional modeled clock (F6). The proposal also has the lifecycle error (F4) and test contamination (F5).
- **Can a 10–15 GPU-h frame-stratified sample work?** Not as frame sampling. Both FIFO backlog and the causal runtime state (T = 16 ring, tracker, births, fusion) depend on the full history since match start, and the cold start depends on the process history. Scattered frames or mid-match segments cannot be measured faithfully, so the smallest valid unit is a whole match in the frozen lifecycle order. Since a full 64-match cell costs only about 0.91 GPU-h, the budget is spent best on whole configurations. Tier 1 meets the 10–15 GPU-h preference whenever ≤ 5 extra finalists are needed beyond the mandatory 10 cells. That is likely but not guaranteed; there is no error bound to state, because Tier 1 is exact.
- **Concrete minimum if Tier 2 is invoked.**
  - Calibration must cover at least 8 measured full cells across ≥ 3 epochs, including ≥ 2 of epochs 15–24, and τ ∈ {0.1, 0.5, 0.9}. That spans the heaviest decode load (τ = 0.1, dense late epochs) and the lightest.
  - Add the missing extreme cells if Tier 1 did not measure them: at most 4 cells, about 3.6 GPU-h.
  - Reasoning: Tier 2 must predict other configurations on the **same 64 matches**, so the generalization needed is across configurations, not across matches. Each held-out full cell supplies about 3,300 events (about 1,650 opponent events). With zero observed flips that gives a rule-of-three flip bound of about 0.18% opponent per cell, which is sufficient to resolve differences of about 0.2 pp in F1. By contrast, 8 matches give 1.8%.

## 4. Error test and fallback (Tier 2 only)

The Tier 2 test is **leave-one-cell-out** over the measured Tier 1 cells, and must be frozen before any fit. For each held-out measured cell k, fit on the others and predict cell k on all 64 matches. Report:

- signed and absolute per-frame availability error (median, p95, p99, max), split into cold-start, block-fetch and warm frames;
- final per-match lag error;
- the count of opponent truth events whose 500 ms matched status differs between measured and modeled scoring (flips), with direction;
- |ΔTP_opponent|, |ΔF1_opponent| and |Δrecall_opponent|, with 10,000 match-cluster bootstrap intervals (seed 6110).

**Acceptance** requires all of the following on every held-out cell:

- (a) Opponent flips ≤ 0.5% of opponent truth events.
- (b) Upper 95% match-cluster bound on |Δrecall_opponent| ≤ 0.5 pp, and the same for |ΔF1_opponent|.
- (c) Across held-out cells, the modeled F1 is not lower than the measured F1 on more than one cell. The model must be optimistic or neutral, because it is used only for elimination.
- (d) Zero modeled availabilities below the frame stamp, and the recursion is verified exactly.

Then set **Δ = 2 × max over held-out cells of the upper 95% bound on |ΔF1_opponent|**, floored at 0.3 pp.

**On failure,** Tier 2 is unavailable and Tier 1 measurement continues to closure, which is the clock-relevant part of A. A failed model may not be refitted, re-featured or re-tested on the same cells. A new model needs a new reviewed amendment.

## 5. Interactions

- **Selection over 24 epochs × body/event grids.** Body selection is clock-free and comes first. Event and epoch selection proceed by B′. The global lexicographic key is equivalent to the hierarchical rule. The new selector and verifier must:
  - accept 216 bound records plus measured cells;
  - recompute every bound from the non-clock records;
  - recompute every measured score from its clocks;
  - verify that each unmeasured cell is strictly dominated by the incumbent's measured key;
  - verify termination.

  Synthetic tests must include equal-key bounds, which must be measured and not eliminated, early-epoch ties, a premature prediction (stamp < truth exec) to prove the superset rule, and tampered bounds.
- **Event thresholds.** Every measured cell runs at its actual τ. CPU-grid reuse of the τ = 0.5 runtime's clock for another τ is forbidden for anything that decides selection.
- **Per-card thresholds and calibration.** Use measured clocks only (B′ steps 6–7). Isotonic calibration fitted on modeled labels would carry modeled time into the sealed configuration.
- **Validation reporting.** Unmeasured cells are reported as "zero-service upper bound", never as validation F1. Any per-epoch winner table for unmeasured epochs is a bound table.
- **Heldout.** One single-use opening, with the identical driver, lifecycle and host policy as §2c. Heldout fleet event metrics are diagnostic, the Mac primary is BLOCKED, and the gates are unchanged.
- **L2-v4 entry.** The S5 90/90 (LB 87) entry report, `L2-V4-PREREG` evidence and the live wrapper's sealed `body_threshold` must cite this amendment's SHA and the selection method. The in-loop "within 2 pp of offline L1" gate refers to measured heldout only.
- **T6.** The amendment must state whether T6 epoch-24 threshold selection, via the unchanged v3 evaluator, read any affected clock. If it did, the same B′ procedure applies to T6's 9 τ cells. If it did not, cite the evidence.

## 6. Other issues that would make selection or gates uninterpretable

- **Order of freezing.** Some validation outcomes have already been seen: the quarantined epoch 1/2 grids and the incident/probe matches. B′'s result is invariant to that knowledge, because it is exact. B's free modelling choices are not, which is another reason to reject B as a decision score. Freeze and seal the amendment, the driver SHA, the host policy, the lifecycle and the Tier 1 budget before computing any bound or measuring any cell.
- **Retention.** Retain every failed or void cell attempt, as PREREG requires for infrastructure reruns.
- **No modeled correction of old captures.** Never divide by nine, never copy reference clocks, and never infer offsets.
- **B's timing list.** If any B-style sample is ever used, move `1975100708` out of any test role (F5) and replace it by the next hash-ranked match in its stratum.

## 7. Items the amendment text must freeze exactly

1. **Scope.** T7 validation selection only (state T6 per §5). Heldout, gates, split, fits, PREREG selection keys and `noise-measured.json` contents are unchanged. Mac and C are excluded.
2. **Clock-free body step.** Selector SHA, inputs, and the sealed b*(e) receipt before any bound.
3. **Bound definition.**
   - Superset edge rule `stamp(p) <= exec(t) + 500` within the same card/side/kind key.
   - Maximum-cardinality matching.
   - Opponent point-mode counts and the rank key (F1_ub, precision_ub, −epoch, threshold).
   - Bound-tool SHA.
   - The invariants it relies on: `available >= stamp`, the max-cardinality scorer, and clock-independent P and T, cited to `validation_replay_v4.py` and `scoring_v4.py` by SHA.
4. **Measurement order, elimination and stopping.** Strictly-below elimination, equal-key measurement, termination, the Tier 1 budget of 30 cells, and the default of continued measurement.
5. **Driver, lifecycle and host policy.** Exactly as in §2c, including the void-and-rerun rule, telemetry, same-host finalists and the post-selection replication rule. The heldout fleet replay is bound to the same lifecycle.
6. **Selected-epoch follow-up.** All 9 τ cells measured, per-card fitting on measured clocks, combined configuration measured, isotonic calibration on measured labels.
7. **Tier 2 contract.** The full model specification of §2b, the leave-one-cell-out test, acceptance (a)–(d), the Δ formula and floor, the no-refit-on-failure rule, and its weaker disclosure wording.
8. **Disclosure.** The disclosure sentence in §1, verbatim, in RESULTS, the seal (`selection_method`, amendment SHA, per-cell measured/bounded status with SHAs) and the L2 entry evidence.
9. **Forbidden inputs.** Quarantined or misattributed clocks, epoch 1/2 grids, shared/packed/vectorized clock fields, τ-borrowed clocks, Mac distributions (C), and divided, averaged or copied clocks.

## 8. Required changes, with wording

**RC1.** Replace the recommendation paragraph of CLOCK-OPTIONS (Preliminary recommendation) for the amendment with:

> "Amendment 12 adopts measured-dominance selection (B′). Body thresholds are selected clock-free. All 216 event cells receive a zero-service optimistic bound computed from admitted non-clock records; cells are measured standalone in bound order until every unmeasured cell is strictly dominated by the best measured cell. Modeled availability is never used to score, select, fit per-card thresholds or calibrate."

**RC2.** Strike "available_hat … calibrated on a fixed stratified sample" as the selection metric. Retain it only as:

> "Tier 2 elimination aid, invocable only after 30 measured cells without closure, under the frozen leave-one-cell-out test and margin Δ; never scores a finalist."

**RC3.** Replace the 8 + 8 body-branch sample with:

> "No pre-selection timing sample is required. Tier 2, if invoked, calibrates only on measured full cells spanning ≥3 epochs (≥2 in 15–24) and τ∈{0.1,0.5,0.9}."

**RC4.** Add:

> "Process lifecycle: one fresh CUDA process per cell; 64 matches in lexicographic order; per-match state reset; cold start retained on the first match. The heldout fleet replay uses the identical lifecycle, driver SHA and host policy."

**RC5.** Add:

> "A's body-stage clock cost is withdrawn: body selection is clock-free per BODY-SELECTION.md. The clock-relevant upper bound is 216 event cells (~197 GPU-h at the contended observed rate)."

**RC6.** Add:

> "C is not admissible for validation selection or any gate."

**RC7.** Add the matched-condition and replication rule of §2c, and the void-but-retained rerun rule.

**RC8.** Add:

> "Tooling: new selector/verifier/seal fields per §5 with synthetic tests (equal-key bounds, premature prediction, tamper, termination) passing before any bound is computed on real data."

**Verdict:** APPROVE WITH REQUIRED CHANGES. Approve a prospective validation-selection amendment implemented as measured-dominance selection (B′). B's modeled clock is not approved as a selection score. A is needed only as B′'s worst case (continued measurement), and C is inadmissible.

File: `reports/strategy_council_20260928/live-loop/v4/l1/reviews/CLOCK-AMENDMENT-REVIEW-20261009.md`
