<!-- Saved verbatim by the design worker from delegated review task prereg-k4s-review-r1-20261011
     (Claude Opus 5.5, effort high, independent of the draft author). Saved 2026-10-11T09:10Z. -->

# PREREG-K4S-REVIEW-r1

- **Reviewer:** independent reviewer, Claude Opus 5.5 (1M context), high effort. Review only: no files edited, no compute run, no ssh, no heldout data opened. Run on 127x05.
- **Time:** 2026-10-11T09:05Z.
- **Document:** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r1.md`, commit `68a15c6a`, sha256 `caa52ad087017df117c88ffc3021b62cb4156b56412b749857e0135a0fe2bcf3` (verified).

## Verdict: **REVISE** (the next round only needs a conformance check)

The experiment itself is sound and freezable:
- arms, cells, populations, seed bank, n = 3,000/900, the poll charge, T1 machinery reuse and sealing;
- the fixed-sequence procedure, which validly gives strong FWER control;
- the power arithmetic, which I reproduced to ±0.01.

What fails is the **decision layer**, the text that turns admitted cells into a Mac deployment:
- it contradicts itself (§1.5 vs Q10; §1.3's "equivalently");
- it rests on a false premise that TIERS has nothing feasible below 0.8× (that is true only for K4);
- it lets SD1-only gates push a full-speed Mac off plain K4;
- its r* = 0.9 branch can never in practice admit anything;
- its release rule can leak TIERS-relevant K4 outcomes before the TIERS Mac summary exists.

All of these are fixable in the text without changing the games.

## Findings

**F1 — MAJOR — §1.5 table, §0, Q6/Q10: deployment assumes TIERS has no feasible tier when c_M ≤ 0.7, which is false.**
- **Problem.**
  - c_M is derived from r_K4S, a 5-core measurement.
  - TIERS feasibility is per tier. S uses r_S (1 core) and K2 uses r_3 (`PREREG-SEARCH-TIERS-r3-DRAFT.md:350-357, 364-365`).
  - A Mac whose 5-core ratio is 0.7 (for example, E-core spillover) can still have S or K2 feasible at their own 1.0/0.8 cells.
  - Row 4 ("c_M ≤ 0.7, where TIERS has no feasible tier → select K4S") would then override a valid TIERS selection of S/K2 with no paired comparison between K4S@c and S/K2.
  - The same false premise appears at §0 l.14 ("TIERS has nothing feasible below 0.8×"), l.86 (H2 rationale) and Q10.
- **Fix.**
  - Key the deployment table on the **TIERS outcome** (K4 / K2 / S / F0 / not available), not on c_M.
  - Add an explicit rule for "TIERS selected S or K2 and c_M ≤ 0.9". Default: **TIERS stands unless TIERS selected F0**. Alternatively, allow K4S at **level A only** to replace S/K2, on the stated, disclosed but untested argument that A means within 5 pp of K4@1.0.
  - Make this choice a numbered Q with that default.

**F2 — MAJOR — §1.5 row 2 vs Q10: level-B deployment is contradictory.**
- **Problem.**
  - Row 2 deploys D(c_e) whenever c_e ∈ 𝒜, which includes level B, for c_M ∈ {0.9, 0.8}.
  - Q10 (l.635) says level B is deployable "only where TIERS has no feasible tier (c_M ≤ 0.7)".
  - Row 2 also lets K4S@0.9 replace a TIERS K4 pick even though A(0.9) only requires K4S@0.9 ≤ K4@0.9 + 5 pp. That allows a downgrade of up to 5 pp against plain K4 on the Mac's own cell.
- **Fix.** Pick one rule and state it in both places.
  - **Recommended:** at c_M ∈ {0.9, 0.8} with TIERS = K4, K4S replaces K4 only if c_e = 0.8 is admitted at A or B. Level B is acceptable here because B(0.8) includes SUP over K4@0.8, which is exactly TIERS's evidence cell for that Mac.
  - For c_e = 0.9, require level A, and disclose the ≤ +5 pp allowance against K4@0.9.

**F3 — MAJOR — §1.4 cell mapping vs §1.5 row 1: SD1-only gates can push a full-speed Mac off plain K4.**
- **Problem.**
  - At c = 1.0, D(1.0) = K4, and K4 runs no SD1.
  - Yet c_M = 1.0 requires r_inf ≥ 1.0 (gate 2), forward p99 ≤ 20 ms (gate 3) and p10_K4S ≥ 0.90 (gate 1). The p10 condition is stricter than TIERS's p10 ≥ 0.70 (TIERS l.365); the draft calls it "exactly as in TIERS".
  - The result: a Mac with r_5 ≥ 1.0 and slightly slow inference gets c_M = 0.9, and TIERS's K4@1.0 is replaced by K4S@0.9 evidence, which is a downgrade.
- **Fix.**
  - The 1.0 cell should be TIERS's K4 cell (TIERS r_K4 and TIERS gates). Apply SD1-specific gates (2, 3, and the K4S deadline-equivalence check) only for c ≤ 0.9.
  - State the p10 rule as a deliberate generalisation (c − 0.10), not "exactly as in TIERS".

**F4 — MAJOR — §1.3: the r* rule and the gate definition.**
- **(a) The "equivalently" claim is false.** "ON iff c_e < threshold cell. Equivalently, ON iff r_K4S < r*" (l.108–109) does not hold.
  - c_M can sit below r_K4S because of gates 2–6.
  - c_e can sit below c_M when a cell is not admitted.
  - Fix: define the switch by c_e only, and delete the r-based phrasing.
- **(b) The r* = 0.9 branch is vacuous.**
  - It moves H3′ (NI5 K4@0.9 vs K4@1.0) to after H7.
  - H6 has power ≈0.15 and H7 ≈0, so H3′ is effectively never tested, and a 0.9 Mac falls to c_e = 0.8 with S ON. That contradicts the purpose of setting r* = 0.9.
  - K4 at 0.9 is also already TIERS's domain.
  - Fix: under r* = 0.9, drop H3 and let 0.9 Macs follow TIERS (plain K4). Alternatively, keep H3′ in H3's slot.
- **(c) The rule must be locked before phase E is reduced.**
  - At 09:05Z, phase E had not been reduced (x4s2 PROGRESS l.103 shows E starting after 09:15Z on 08).
  - r2 must not change the §1.3 rule text after phase E is reduced.
  - State this in r2 and record the phase E reduction time in the r* record.

**F5 — MAJOR — §4.5/Q3: release can leak TIERS-relevant K4 outcomes before the TIERS Mac summary is committed.**
- **Problem.**
  - K4S plays K4@1.0 and K4@0.8 on TIERS's primary population (same five decks, same v1 opponent; TIERS l.146) and on the same guard decks.
  - Releasing K4S before TIERS `tiers-summary.json` exists gives a 3,000-seed, confirmatory-grade estimate of T1's K4@200/160 cells.
  - TIERS §6.6/D6 and the freeze record ("fleet outcomes sealed until Mac summary committed") exist to close exactly this steering path.
  - Q5 then proposes running K4S's Mac cell in that same session.
  - X4S already published noisy versions of these contrasts, so the leak is incremental, not categorical. It is still a new steering input.
- **Fix.**
  - Add release condition 6: TIERS `tiers-summary.json` committed, or TIERS outcomes already released (including via its 14-day escape).
  - Also: if the K4S Mac session runs after K4S release (the standalone path), an independent reviewer confirms the mechanical session classification before it runs, mirroring TIERS §6.6(b).
  - The decoupling from K4S's *own* Mac summary is otherwise valid (see "Checked and correct").

**F6 — MINOR — §1.2: H3's ordering and gate-check coupling.**
- **(a) Remove the gate check from the testing chain.**
  - H3 bundles the gate check (K4S@0.9 − K4@0.9 ≤ +5) into the α chain. A failure there, which is a K4-vs-K4S choice at 0.9, halts A(0.8) and B(0.6).
  - Fix: make the gate check a **deployment veto** on D(0.9) that does not stop the sequence. This is still FWER-valid, because a veto only removes admissions.
- **(b) Put the ordering of B(0.6) to the coordinator.**
  - B(0.6) is the "rescue" value the draft emphasises, but it sits behind two A-level upgrades.
  - Moving B(0.6) to H3 changes cumulative power as follows:

    | Claim | Pessimistic: current → moved | Central: current → moved |
    |---|---|---|
    | B(0.6) | 0.24 → 0.67 | 0.86 → 0.96 |
    | A(0.9) | 0.69 → 0.51 | 0.97 → 0.93 |
    | A(0.8) | 0.33 → 0.24 | 0.89 → 0.86 |

  - Fix: add this as a Q with the trade-off table.
- **(c) The nesting claim is wrong at 0.9.** "A's parts imply B's" (l.93) is false at c = 0.9: A(0.9) has no SUP part, and B(0.9) is never tested. Fix: restrict the claim to c ≤ 0.8.

**F7 — MINOR — §3.5: planning centrals mix the uncharged and charged designs.**
- **Problem.** The confirmatory K4S arms are charged (K4Sh-like), but the central values average X4S K4S (uncharged) with K4Sh.
  - At 0.8, the only direct estimate for the charged design is K4Sh-160 − K4-200 = +3.2 [−0.7, 7.0] (`results-phaseA.md:35`). That is the "pessimistic" column.
  - The headline "most likely: full parity to 0.8×" (l.40) rests on the averaged +2.0.
  - Averaging is defensible, because the charge cost is ≈0 at 140/120 (+1.0, −2.0) and the +3.5 at 160 looks like noise. The justification must be stated, though.
- **Fix.**
  - Say explicitly that the design equals the K4Sh configuration and justify the shrinkage.
  - Soften l.40 to "A(0.8) ≈ 0.9 if the charge cost is ≈0; ≈0.33 at the direct charged estimate".
- **Note.** The cumulative products count the shared SUP(0.8) event twice (H1 and H4), so pessimistic A(0.8) is ≈0.36, not 0.33. Disclose this, or compute the joint probability.

**F8 — MINOR — §1.4 gate 2 / §2.4: r_inf is defined on a different quantity from the charge.**
- **Problem.**
  - The charge scales the **poll wall time**: about 10–11 ms, including packet and policy wrapper (`results-phaseA.md` poll column; `x4s2/run.py:206-211`).
  - r_inf is defined on the **forward p50** (about 6.4 ms per X4S RESULTS l.79).
  - The coverage derivation W/c + poll/c² requires both to be the same quantity.
  - No fleet source for "fleet loaded SD1 forward p50" is named; the END items (a)/(b) don't produce it.
- **Fix.**
  - Define r_inf on the same timed span as the charge, and name its fleet reference (END item (c), or pooled reporting `poll_seconds`).
  - Correct "≤ 192" to the exact emulated bound 200 − 8/c, which is conservative.
  - Disclose that fleet overrun lateness is under-penalised by the factor c (x4s2 PLAN l.63).

**F9 — MINOR — §1.5: undefined and unmodelled cases.**
- **Problem 1.** c_e = max{…} is undefined when no admitted cell is ≤ c_M (for example, c_M = 0.9 with 𝒜 = ∅ apart from 1.0).
- **Problem 2.** The monotonicity assumption is contradicted at the point estimate: K4S-160 (18.2%) < K4S-200 (20.7%) (`x4s/RESULTS.md:27-28`).
- **Fix.**
  - Define the empty case (→ TIERS/F0).
  - Disclose the non-monotonicity, and add a descriptive K4S@0.9 − K4S@0.8 check to §5.3.

**F10 — MINOR — §2.1: SD1 adoption needs an explicit supersession.**
- **Problem.**
  - R3 labels these bytes "ALWAYS NEVER-ADOPTABLE … regardless of its paired benefit" (`exit-r3/RESULTS.md:85, 97, 125`).
  - Renaming them SD1 does not remove that label. TIERS needed an explicit, coordinator-issued, outcome-informed supersession (TIERS l.89–95).
  - The draft says R3a "remains … NEVER-ADOPTABLE under R3" and also adopts the same bytes.
- **Fix.**
  - Add a TIERS-style supersession sentence scoped to the K4S cutoff-default role, issued by coordinator `0523ae6f` under owner delegation, with the outcome-informed disclosure (X4S/X4S-2).
  - Recipe omissions from `exit-r3/PLAN.md:22-23, 43-45`: the existing R2 gate/card/tile loss terms, and the threshold midpoint/tie rule. Add both.

**F11 — MINOR — §3.1/§3.4: subsample replacement, dispatch and rotation are unspecified.**
- **(a) Subsample replacement.** A lost subsample block (i < 600 primary, i < 300 guard) is replaced by an index ≥ 3,000 (or ≥ 900). The draft doesn't say whether the replacement plays 10 or 8 arm-cells, so the subsample can shrink silently. Fix: replacements inherit the lost block's arm set.
- **(b) Dispatch interleave.** No primary:guard interleave is given. TIERS used 4:1. Fix: specify 10:3 so host loss and drift spread over both populations.
- **(c) Rotation confounding.** Rotation i mod 8 with cell i mod 50 (or 18) means each cell sees only 4 of 8 rotations, since 50 ≡ 18 ≡ 2 (mod 8), and seat parity is tied to rotation parity. Fix: rotate by ⌊i/50⌋ mod 8 (guard ⌊i/18⌋ mod 8), or use a balanced Latin square.

**F12 — MINOR — §4.5: END reference failure path.**
- **Problem.** If the pooled END reference fails closed after its one repeat, the outcome is not stated. Release item 2 would then block release forever.
- **Fix.** Adopt TIERS A1.1's wording: re-run until it conforms, or declare the Mac speed ratio unavailable (tier Mac-infeasible) with outcomes then releasable.

**F13 — MINOR — §4.1: two qualification gaps.**
- **(a) K4@1.0 vs T1 equivalence is not tested.** "K4@1.0 byte-identical in behaviour to T1's K4@200" has no direct test. Fix: add command-hash and injected-clock equality of K4@1.0 under the delta runtime against the frozen T1 runtime (`ef4c073a`) on the qualification seeds.
- **(b) Guard deck pin.** Pin `guard-decks.json` by its own SHA (`6d51628b…`), not only by the selector (`21125180…`).

**F14 — NIT.**
- **§1.3 l.112: mixed baselines.** "+29 pp at 0.7×" is K4-140 − K4-200. The cost of missing S at 0.7 is the K4S-vs-K4 rescue, −25.2 pp, which is the baseline used for "+9 at 0.8×". Use one baseline.
- **§5.3 item 5:** this is a disclosure, not an analysis. Move it to the limits.
- **§3.6 per-decision fields:** add SD1 P(play) and a hash of the coarse_order list (useful for mechanism analysis and for linking Mac agreement).
- **§1.4 corpus:** the corpus is K4's, not K4S's own (TIERS used each tier's own corpus). Disclose; the effect is negligible at 1.0, where S triggers on 0.76% of decisions.
- **§3.5:** the n = 2,400, Δ = +5 cell should read .025, not .02.

## Checked and correct

**Statistics**
- Fixed-sequence over H1–H7 with intersection–union hypotheses gives valid strong FWER ≤ 0.025 for any prespecified order. Within each cell, levels are tested in a consistent order (B before A).
- "No adjustment across the Mac cell" is valid even with decoupled release. The claim "the deployed cell is falsely admitted" is a subset of "any false admission", and the min-across-sessions rule blocks raising r by repeating sessions. The TIERS leak in F5 is a separate issue.

**Power and σ**
- Every σ reproduces from the cited CIs with σ = half-width/1.96·√n: 0.43, 0.48–0.52, 0.51, 0.47–0.56, guard 0.56–0.62, 0.31.
- SE values (0.96/0.86/0.78; guard 1.87), the marginal NI power table, guard NI10/NI15 power and every sequential product (central and pessimistic) reproduce to ±0.01.

**S-default rule**
- §2.3 matches `x4s2/run.py:206-308` and `sdefault.py:15-30`:
  - SD1 seat poll;
  - coarse_order for scheduling only, with an empty candidate augmentation;
  - SD1 default on preparation cutoffs (belief, pre-scan, sample);
  - scoring-cutoff play override only when no play has a complete score;
  - SD1 WAIT keeps the frozen choice;
  - K4S ≡ K4 with no deadline.
- X4S-2 left K4's v1 poll uncharged (PLAN l.70). Charging both arms is the consistent model of one Mac.
- §2.4's restatement of "budget equivalence already charges inference" is faithful to x4s2 PLAN l.46–57.

**Artifacts and recipe**
- SD1 checkpoint `37509a43…`, calibration `e3003533…` and threshold 0.5005528330802917 match.
- Recipe facts match `exit-r3/PLAN.md`: 2,500 × 8,192 rows, seed 2026101013, corpora 1c8e1f49/4e8faf7e, 6,222,223 roots, teacher_root/wait_kind 0, T = 0.003, optimiser, 34.6%, heldout64 `0ecce0f0`.
- R3d −0.036 pp matches.

**Seeds and caps**
- Bank arithmetic (2^52 + 6.18e9 …) and window bounds are correct. `git grep` finds no seed literal in 2^52 + [5.87e9, 7.37e9) outside this draft.
- Replacement row limits (k ≤ 11 / ≤ 9) and caps are consistent.

**Compute**
- Game counts (25,200 + 7,800 = 33,000), throughput (X4S: 5,400 games / 24 slots / 2.46 h ≈ 92 games per slot-hour), ≈359 slot-hours, ≈1,800 reserved core-hours, ≈460 CPU-h (from 37.4 CPU-h per 2,700 games), and 8.2/11/16 h wall all check.

**Reuse of T1, OP lessons and END**
- OP-7 apt stop at 21:03Z (PROGRESS-T1 l.87), PC1–PC4 content (RELEASE-PRODUCTION-CHECKS l.5–8) and A1.1–A1.3 are cited correctly.
- The END rejection of SSH- and DBus-flagged work (END-CONTRACT-COMPATIBILITY) supports preferring transport-free hosts.
- Host conflicts match COORDINATOR l.1958–1962.

**Brief conformance**
- All seven brief items are present.
- §6 states that nothing from exploration is adoptable, and the only allowed phase E use is the single, prespecified r* rule.
- Q1–Q11 each have a default.
- No TIERS or T1 file was modified: commit 68a15c6a touches only this file.
