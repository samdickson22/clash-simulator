# Delta review: Amendment 12 (measured-dominance selection), 2026-10-09

The independent reviewer worked read-only on 127x05; the only file written is this review. No bound, body score, measurement or selection was computed on real records, and no validation or heldout outcome was opened.

## Inputs reviewed

| Input | SHA256 |
|---|---|
| `amendments/12-measured-dominance-20261009.md` (draft) | `9e575ba1bcd67e8069a022d952cf873b957ea80a410f30c1e1376422b608dc23` |
| `amendments/12-measured-dominance-draft-pins.json` | `2669f8142efa42dfb993dd5a5ee61f612040ec6ae1334dbaa0a393c84bbab6e1` |
| `reviews/CLOCK-AMENDMENT-REVIEW-20261009.md` (base review) | `43ed20a05fd0f436d20cd75a2dcaa3f13225ee20dfcd617b34e3f4f4e0693dc4` |

The reviewer also read `CLOCK-OPTIONS.md`, `PREREG.md`, amendment 11, `BODY-SELECTION.md`, and these source files:

- `measured_dominance_v4.py` and `test_measured_dominance_v4.py`;
- `clock_free_records_v4.py`, `test_clock_free_records_v4.py`, `clock_free_body_score_v4.py`, `clock_free_body_ranking_v4.py` and `record_capture_admission_v4.py`;
- `decoder_records_v4.py`, `scoring_v4.py` and `validation_replay_v4.py`;
- `PixelPerception.step` and `EventFusion.update` in `src/clasher/vision/l1_v4.py`.

All 17 source pins in the pins file match the files on disk byte for byte.

### Independent checks

- **Dominance tests.** On 127x05 with system python3, run with `-B` so nothing was written, all 10 `test_measured_dominance_v4` tests pass.
- **Clock-free tests.** Of the 4 `test_clock_free_records_v4` tests, 2 pass here. The other 2 need `torch` and `clasher`, which 127x05 does not have. For those 2 the reviewer relies on receipt `clock-free-tests-15r1.exit.json` (exit 0, "Ran 4 tests … OK"). Neither 15r1 receipt pins the SHA of the test file it executed (non-blocking; see N2).
- **Host inventory.** At 2026-10-09 01:30:50Z, a read-only `nvidia-smi` query on 127x08 returned `NVIDIA RTX A6000, 470.256.02, GPU-6cb558a5-e557-239c-60ed-be7ddb4de59c`. This matches the pins.

## Verdict summary

The substance is sound. The bound is a valid ceiling, the selector is exact, the body seal comes first, modeled clocks cannot decide anything, and the gates are unchanged.

The draft still needs six required changes before it can be frozen:

- three that the coordinator flagged (D1–D3);
- one bound-soundness condition the file verifier must enforce, because the pure primitives check only counts (D4);
- two editorial items: adoption wording and repair of the word spacing (D5–D6).

Each change has exact wording below. **APPROVE WITH REQUIRED CHANGES.**

## A. The coordinator's three flagged issues

### A1. Disclosure-sentence direction: agreed, the sentence must be corrected

The base review's sentence says the bound "cannot exceed any measured outcome". That is backwards relative to F2 and to the code:

- For every cell and every measured realization, TP_ub ≥ TP_measured, and P and T are identical, so the bound key is ≥ the measured key.
- The stopping rule eliminates a cell only when its bound key is strictly below the incumbent's measured key, compared on the complete lexicographic key. This is the strict `<` in `next_step`.

The base review's error is in that one sentence; the procedure in §2a is correct. The owner's proposal, "each unmeasured upper bound was strictly below the measured winner", is correct in direction. The final wording should also name the full key, because elimination can rest on the tie-break (equal F1 and precision, but a later epoch or lower threshold). **Required final sentence (D1):**

> "T7 validation selection used Amendment 12 measured-dominance selection: N of 216 event cells were measured standalone with measured completion+FIFO; each of the remaining 216−N cells was excluded because its zero-service optimistic upper bound, which is at least any outcome that cell could have measured, ranked strictly below the measured winner's selection key (opponent F1 at 500 ms, then precision, then earlier epoch, then higher threshold). No modeled availability entered selection, per-card thresholds or calibration."

This sentence supersedes §1 and §7 item 8 of the base review. RESULTS, the selection seal and the L2 entry evidence use it verbatim, with N filled in.

### A2. The 30-cell "budget" is a checkpoint, never a closure: confirmed

This matches the base review. §2b(i) makes continued measurement "the default and always admissible", and nothing in §2a terminates on a count. The code agrees:

- `next_step` sets `budget_checkpoint` only as a flag.
- `next_step` keeps returning `next_cell` after 30 cells.
- `closed` depends only on dominance.
- `verify_certificate` refuses an unclosed state, as `test_unclosed_and_budget_not_a_winner` exercises.

One sentence in the draft (line 54) is ambiguous: "No automatic budget increase … is implied". It could be read as stopping measurement at 30 until someone re-authorizes. **Required replacement for the draft's 30-cell paragraph (D2):**

> "Tier 1 checkpoint. The 30-cell figure is a reporting checkpoint, never a closure, stopping or selection rule. It counts first valid scheduled selection measurements only; void-but-retained attempts, replication runs and selected-epoch/combined follow-up runs do not count. If the 30th counted measurement completes without closure, the controller, in the same step: (1) writes `tier1-checkpoint-030.json` and reports it to the coordinator, listing every measured cell with its measured counts and SHAs, the current incumbent labelled 'provisional incumbent — not a selection', the number of pending (not strictly dominated) cells with their bound keys, the measured mean and maximum 127x08 GPU-hours per cell, a cost re-estimate equal to pending cells × measured mean cell hours plus the 10 follow-up cells, and the host-telemetry/void summary; (2) makes no selection: no winner, epoch, per-card threshold, calibration, T7 seal, RESULTS validation-F1 claim or heldout step; (3) continues standalone measurement in the frozen bound order on the same host, driver and lifecycle without waiting for a decision. The same report is repeated after every further 30 counted measurements. No checkpoint may change the order, elimination rule, host, lifecycle, driver or population. A pause is permitted only for an infrastructure reason, is logged, and resumes the identical queue. Tier 2 remains disabled; measurement continues while any Tier 2 addendum is reviewed. Selection occurs only when `next_step` reports `closed=true` and the file verifier recomputes the certificate."

### A3. Tier 2 leave-one-cell-out "all 64" against the excluded match: Tier 2 stays disabled

The conflict is real. Match `v4-phase-a-1975100708` is lexicographically the first validation match. Under the frozen lifecycle, it therefore carries the only process start, the cold start, in every cell. Its clocks have already been inspected and shaped the cold term. It cannot sit in a test denominator.

It needs no modeled role at all, because the per-match zero-service bound can stand in for it optimistically. Matching is per episode, so a per-match TP_ub is a valid per-match ceiling. Tier 1 is unaffected: it keeps all 64 formal validation matches in every bound, every measured cell and every selection score, and it fits no model.

**Required resolution text (D3).** It replaces the draft's "Additional coordinator restriction" paragraph. It must also appear verbatim in any future Tier 2 enabling addendum, and is binding there:

> "Tier 2 is disabled. It may be enabled only by a separately reviewed and frozen addendum that pins the implementation, solver, tolerances and tie order and adopts this resolution verbatim. Match v4-phase-a-1975100708 stays in every Tier 1 bound, measured cell and selection score over all 64 validation matches. In Tier 2 it has no fitting or testing role: (i) its frames are excluded from the service-model fit; (ii) all leave-one-cell-out statistics — per-frame availability errors, final-lag errors, flip counts, |ΔTP|, |ΔF1| and |Δrecall| with their 10,000-resample match-cluster bootstrap intervals (seed 6110) — are computed over the other 63 validation matches, whose opponent truth events are the denominators of acceptance (a) and (b), and acceptance (c) compares 63-match modeled and measured F1; (iii) in any Tier 2 elimination score this match contributes its zero-service optimistic bound, never a modeled count: F1_hat(c) = 2·(TP_hat_63(c) + TP_ub_1975100708(c)) / (P(c) + T), with P and T the full 64-match clock-independent counts; (iv) because the frozen lifecycle places the only process start on this match, the §2b cold term has no Tier 2 role and is not fitted, and cold-start frames are reported descriptively only; (v) Δ is computed from the 63-match intervals. The addendum must verify that 1975100708 is first in the frozen lexicographic order; if the order or lifecycle ever places a process start elsewhere, or any of (i)–(v) cannot be implemented exactly, Tier 2 stays disabled."

## B. Other required checks

**RC1–RC8 copied verbatim.** Yes. The reviewer checked programmatically that the base review's §8 block, the whole §2b, the whole §4 and the original disclosure quotation each occur byte for byte in the draft. The RCs are implemented as follows:

- **RC1:** in CLOCK-OPTIONS line 35, the exact sentence.
- **RC2 and RC3:** Tier 2 is only an elimination aid, and is disabled; there is no pre-selection sample.
- **RC4:** in the lifecycle section.
- **RC5:** the body-stage costs are withdrawn in CLOCK-OPTIONS line 37.
- **RC6:** C appears in the forbidden list.
- **RC7:** the void-but-retained rule, the same-host rule for finalists, and replication without reselection, plus a defined runner-up.
- **RC8:** the pure tests pass. The draft goes beyond RC8 by making the file-backed orchestration a freeze blocker.

One weakness remains: the RCs appear only as a quoted review block. D5 makes their adoption normative.

**The clock-free body seal precedes any bound.** Yes, in text (lines 7 and 48). The body view (`clock_free_records_v4.checked_records`/`body_frames`) rejects clock fields and never takes journals. `record_capture_admission_v4` hashes the decoder files but deliberately never opens `*-completion.jsonl`. Body ranking keeps the registered rule: F1, then precision, then the higher threshold. The pure bound primitive cannot prove the ordering. D4(a) makes the ordering verifiable: each bound record must embed the seal hash.

**The bound is a mathematically valid ceiling.** Yes. The chain of reasoning:

1. `replay_episode` sets `ready = max(ready, stamp) + service`, with `service ≥ 0` enforced, so available ≥ the frame stamp exactly in IEEE arithmetic.
2. The scorer's point edge is `exec ≤ available ≤ exec+500`, which implies `stamp ≤ exec+500`. Every measured edge is therefore a bound edge.
3. Keys match `match_events`: (episode, card, side, card_play/champion). Opponent P and T are selected the same way, `side==0`, with champion abilities excluded.
4. `match_events` is maximum-cardinality. The blocked cost `(min+1)·501` exceeds any sum of valid costs, so TP_measured ≤ maxmatch(superset) = TP_ub.
5. Within a key, the bound's neighbourhoods are nested ({p : stamp ≤ deadline}). Processing deadlines in ascending order and assigning the earliest unmatched feasible stamp is therefore maximum. The exhaustive test confirms this, and the edge-subset test covers delayed predictions, including premature ones.
6. Rank: the same P and T with a TP that is ≤ gives an F1 that is ≤. If F1 is equal, TP is equal, so precision is equal. The tie-break fields are identical. So measured key ≤ bound key, and strict elimination is exact.
7. The global key (F1, precision, −epoch, τ) is equivalent to `select_threshold` followed by `select_epoch`.
8. Because each (epoch, τ) cell is unique, two different cells can never have equal complete keys. "Equal keys are measured" therefore operates on equal (F1, precision): a cell whose tie-break is better stays pending, and a cell whose tie-break is worse is correctly eliminated.
9. P is clock-independent. In `PixelPerception.step` and `EventFusion.update`, availability only populates an output field. Thresholding, NMS and tracking use the frame stamp alone. `RecordedEventFusion` mirrors this logic, and the decoder keeps every peak with score ≥ 0.1, so every τ on the grid can be reconstructed.

The validity condition the code does not yet enforce is that the records equal what the runtime emits. The pure `next_step` compares only the P, T and TP counts. D4 closes this gap.

**Measurement host policy.** This passes. The policy specifies:

- 127x08 only, no earlier than 05:00Z and after the GRU job has actually exited and released the host.
- The A6000, driver 470.256.02 and GPU UUID pinned and re-verified at admission, and recorded in every attempt and in the seal.
- Single-tenant use, with no foreign compute on CPU or GPU.
- Telemetry every 30 s or more often, through flush and exit.
- MemAvailable below 24 GB, missing telemetry or changed hardware makes an attempt void but retained, followed by an identical rerun.
- One fresh CUDA process per cell, with 64 matches in lexicographic order. `validation_replay_v4.run` loops every episode in one process, `PixelPerception` resets on each episode change, and `replay_episode` resets `ready` on each match.
- Cold start retained on the first match only.
- The heldout fleet replay uses the identical lifecycle, driver and host policy.
- 04 is not a deciding host, and finalists are measured on the same host.

The launcher and telemetry tooling are still unbuilt. The draft correctly lists them as freeze blockers that must be pinned before any measurement, and they stay that way.

**Forbidden inputs.** Line 134 covers every item in §7.9 of the base review: misattributed, quarantined or shared/packed/vectorized clocks; epoch 1/2 grids; τ-borrowed clocks; divided, averaged or copied clocks; inferred offsets; and Mac distributions (C). It adds heldout data, changed fits, splits, grids or gates, and reconstructed arrival clocks. The contended host-15 probes and pilots cannot decide anything ("No leased/contended timing probe decides any cell").

**Gates and noise.** Unchanged:

- L1 95/95, bootstrap lower bound 92.
- S5/L2-v4 entry 90/90, lower bound 87.
- The Mac primary endpoint and the Mac p95 ≤ 40 ms row stay BLOCKED.
- `noise-measured.json` holds genuine heldout measurements only.
- The in-loop 2 pp comparison refers to measured heldout.
- T6 is unaffected, and verifier 15r4's evidence is cited.

**Nothing lets modeled clocks decide.** Correct:

- `tier2_enabled` is `false` both in the pins and as a hard-coded output of `next_step`.
- Per-card thresholds and isotonic calibration use measured cells and labels only.
- Unmeasured cells are reported only as "zero-service upper bound".

## C. Required changes, with exact wording

**D1.** Replace the "Required disclosure" quotation and the "Delta-review issue" paragraph with the following. The heading must read "Required disclosure (corrected by delta review)".

> "T7 validation selection used Amendment 12 measured-dominance selection: N of 216 event cells were measured standalone with measured completion+FIFO; each of the remaining 216−N cells was excluded because its zero-service optimistic upper bound, which is at least any outcome that cell could have measured, ranked strictly below the measured winner's selection key (opponent F1 at 500 ms, then precision, then earlier epoch, then higher threshold). No modeled availability entered selection, per-card thresholds or calibration."

Add one line after it: "The base review's sentence 'cannot exceed any measured outcome' was reversed and is superseded by this sentence, per delta review `AMENDMENT-12-DELTA-REVIEW-20261009.md`."

**D2.** Replace the draft's paragraph that begins "The30-cell Tier1 budget is the frozen review checkpoint" with the A2 checkpoint text above, verbatim.

**D3.** Replace the paragraph that begins "Additional coordinator restriction" with the A3 resolution text above, verbatim.

**D4.** Add the following under the Tier 1 procedure, after the paragraph about the pure selector/verifier:

> "Bound-validity preconditions, enforced by the file verifier in addition to the pure checks: (a) every bound record embeds `body_seal_sha256` and the b*(e) recorded in that seal; a bound without the seal hash, or with a different body threshold, is rejected. (b) For every measured cell, the multiset of opponent card-play predictions keyed by (episode_id, source_seq, card, side) recomputed from the measured outputs equals the multiset recomputed from the admitted clock-free records for the same (epoch, τ, b*(e)); equal counts alone are insufficient. Bound and measured scoring consume one byte-identical truth row list (episode, card, side, kind, execution_timestamp_ms) from one pinned truth-mapping source, recorded by SHA. (c) Every measured prediction satisfies available_timestamp_ms ≥ its frame timestamp_ms exactly, with no tolerance, and each bound uses that same frame timestamp_ms as production_timestamp_ms. A failure of (a) or (c) voids and retains the affected record. A failure of (b) is a record-fidelity failure: elimination is suspended, no selection is made, the coordinator is notified, and the only admissible continuation is measuring every remaining cell without elimination."

**D5.** Insert the following at the top of the "Required review wording" section, and append the delta review's SHA to the pins file as `delta_review`:

> "The quoted RC1–RC8 sentences are adopted as normative text of this amendment. RC7 is implemented by the section 'Controlled measurement host and lifecycle'. Where the base review and the delta review differ (the disclosure sentence, the 30-cell checkpoint, the Tier 2 test role), the delta review governs."

**D6.** Restore normal word spacing throughout the draft (and in CLOCK-OPTIONS lines 37–43). Many words are fused, for example "Dated2026-10-09", "excludes noformalvalidationmatch" and "Macp95<=40ms". Normative text has to be readable without guessing.

The change must be whitespace-only outside D1–D5. A comparison with all whitespace removed (`re.sub(r'\s','',…)`) must show no other change from SHA `9e575ba1…dc23`.

## D. Non-blocking notes

- **N1.** Add a synthetic test where an unmeasured cell has the same bound (F1, precision) as the incumbent but a worse tie-break. It is correctly eliminated. Also add a per-match bound test for D3(iii) if Tier 2 is ever built.
- **N2.** Future test receipts should pin the SHA of the test file executed and the PYTHONPATH tree.
- **N3.** The heldout replay driver must import `replay_episode` from the pinned `validation_replay_v4.py`, unchanged, so "identical driver" can be checked by hash.
- **N4.** The cost tables in CLOCK-OPTIONS (lines 39–68) should carry a "WITHDRAWN (engineering history)" label in their headings.

## E. Freeze conditions

The coordinator may freeze without another review round if both of the following hold:

1. D1–D5 are inserted verbatim.
2. The whitespace-normalized comparison required by D6 shows no other change.

The freeze must record the new draft SHA and the new pins SHA. The draft's own blockers stay in force before any real computation:

- the file-backed clock-free body/non-clock admission;
- the persisted bound/selector/seal orchestration, including the D4 checks and their tests;
- the controlled 127x08 launcher and telemetry, pinned;
- then the intermediate body seal, which must come before any bound.

**Verdict: APPROVE WITH REQUIRED CHANGES** (D1–D6 above). This applies to draft `9e575ba1bcd67e8069a022d952cf873b957ea80a410f30c1e1376422b608dc23` and pins `2669f8142efa42dfb993dd5a5ee61f612040ec6ae1334dbaa0a393c84bbab6e1`. It is not approved for freeze at these SHAs.

File: `reports/strategy_council_20260928/live-loop/v4/l1/reviews/AMENDMENT-12-DELTA-REVIEW-20261009.md`
