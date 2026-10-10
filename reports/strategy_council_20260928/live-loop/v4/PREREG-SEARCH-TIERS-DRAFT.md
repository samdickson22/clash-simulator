# PREREG (DRAFT, not frozen): live search tier selected from measured Mac capacity

Draft 2026-10-10, research planner (Opus) for coordinator `0523ae6f`. This is a draft only: nothing has been
launched, committed or run on the Mac. The coordinator commissions an **independent review** (a Codex or Opus
reviewer on high effort that took no part in K/K2/K-v2/S1/R3), then amends, freezes, secret-scans, commits and
pushes it **before the first reporting game**. "Frozen" means listed in the TIERS content manifest (SHA-256).
Paths are relative to `reports/`.

## 0. Summary

- **Question.** Which search tier should the live player run, given the CPU the Mac actually has left over while
  perception runs?
- **Design.** It has two decoupled parts, so the fleet does not wait for the Mac:
  1. **Fleet confirmatory study (C).** Four arms × two budget-equivalent speed cells (1.0× = 200 ms, 0.8× = 160 ms)
     are played on 2,400 fresh paired seeds, plus a 600-seed transfer guard on the L2-v4 live decks.
  2. **One Mac measurement session (M).** It is replay-only, and it measures each tier's loaded speed ratio r_T
     against the fleet on a fixed, frozen work corpus.
- **Decision.** A frozen rule maps r_T to a speed cell, and C's results in that cell pick the tier: the **cheapest
  admissible tier non-inferior (+5 pp) to the most capable admissible tier**.
- **Expected outcome (prior, not a claim).** K4 is chosen if the Mac sustains five fast cores under load. Otherwise S
  (1 core plus the student) is chosen over K2 if it stays within 5 pp of K2, which S1 suggests it will (−0.83 pp).
  If nothing qualifies, the live configuration stays as the frozen L2-v4 one.
- **Cost.** About 500 reserved fleet physical-core-hours (about 4–6 h wall on about 100 cores), plus one Mac
  session of about 1.5–2.5 h.

## 1. Hypotheses and primary contrasts

Notation: loss(T@s) is the opponent-win rate of tier T in speed cell s. Draws are kept separate and count as
non-losses. Every contrast is paired on the seed.

| ID | Hypothesis (per tier T ∈ {K4, K2, S}, at its Mac-mapped cell s_T) | Test |
|---|---|---|
| **V1** | T beats the 1-core control by a meaningful margin: loss(T@s_T) − loss(K0c@s_1) < −10 pp | upper **98.33%** CI ≤ −10 pp (Bonferroni over 3 tiers) |
| **V2** | T beats plain v1 clearly in absolute terms: loss(T@s_T) < 40% | upper 98.33% CI ≤ 40% |
| **G** | Transfer guard: T beats the control on the live L2-v4 decks: loss − loss(K0c) < 0 | upper 95% CI < 0, guard population |
| **NI** | Selection: a cheaper tier is non-inferior to the most capable admissible tier T_max: loss(T) − loss(T_max) < +5 pp | upper 95% CI ≤ +5 pp |

- **Why these margins.** V1 keeps the −10 pp advance margin that K, K-v2, K2 and S1 used. V2 rules out "beats a
  collapsed control": K0c-160 lost 79%, which is worse than not searching. NI keeps S1's +5 pp margin, which is
  half the V1 margin, so a selected cheaper tier always keeps most of the benefit.
- **Descriptive only.** All 8 arm-cells' loss rates, every pairwise contrast in both cells, the speed degradation
  (T@0.8 − T@1.0), and the timing, cutoff, fallback, overrun and GC tables in the K-v2/S1 format.

## 2. Arms (all one-core-or-more, same harness, same opponent)

| Arm | Definition (frozen bytes from the cited study) | Cores |
|---|---|---:|
| **K0c** (control) | S1's K0c: coarse-first W-screen8, one cached v1 forward for both the stochastic T=1 fallback and the exact top-8 proposals | 1 |
| **S** | S1's S: coarse-first W-screen8; R3a EMA `37509a43…` top-8 proposer; calibrated deterministic fallback, calibration `e3003533…`, threshold `0.5005528330802917`; one cached forward | 1 |
| **K2** | K2's two-worker WAIT-first anytime collector (freeze `3cf8919e`), including K-v2 preparation and GC amendments (`75e2513d`, `83a7faea`); v1 fallback only when no complete score exists | 2 workers + main = 3 |
| **K4** | The same collector with four workers, i.e. K-v2's V-arm | 4 + main = 5 |

Every arm runs in two cells, **s = 1.0 (200 ms deadline)** and **s = 0.8 (160 ms)**, each with an 8 ms return
reserve. That gives 8 arm-cells, all on the same seeds.

Common rules, all inherited unchanged from K2/S1:
- Opponent: the sealed plain v1 policy, T=1, no search.
- Symmetric d=27, capacity 1, search interval 10, policy interval 5, horizon 160 with three styles.
- **Honest lateness:** the full timer starts before observation; every positive overrun is charged as
  ceil(overrun×20) ticks; partial and late scores never count.
- GC is deferred only inside decisions and metered.
- Native `44874fd6`.
- **One sampled public belief root per decision** (see §9, decision D2).

### 2.1 Student decision: re-freeze R3a's bytes, do not retrain (decision D1)

R3a is tested as **"S1-student", a new registered artifact whose bytes are identical to R3a** (SHA above). R3's
Stage 1 KILL / NEVER-ADOPTABLE verdict is unchanged in R3's record. Adoption authority, if any, comes only from
this PREREG's gates on fresh seeds. Why not retrain:

1. **A confirmatory test of fixed bytes on fresh seeds is unbiased for those bytes.** The selection concern
   (winner's curse after r1(b) and S1) applies to claims about the *recipe*, not to the exact artifact deployed.
   A retrained student would make S1's effect and variance estimates, and so this power calculation, inapplicable.
   It would also add a GPU fit plus a qualification cycle before anything else could run.
2. **R3's Stage 1 gates were imitation proxies, not strength.** Play recall missed 0.6375 by 0.008 (0.6297);
   agreement missed all-WAIT+0.10 by 0.010; W regret *passed* (0.0088 ≤ 0.010). Game outcome is the deployment
   endpoint, and §1 tests it directly.
3. **The audit's legitimate concerns are designed in, not retrained away:**
   - inference is equalised (K0c caches one v1 forward, the S1 fix);
   - lateness is charged;
   - the opponent and kernel are common across arms;
   - the speed sweep is in the design;
   - generalisation beyond the five training archetypes is gated by the **G transfer guard** on the L2-v4 live
     decks, which the student never trained on.

A fresh-seed refit is **not** a candidate here. If S fails G, a refit becomes a separate exploration item.

## 3. Populations, seeds and schedule

- **Primary population:** the K2/S1 harness, with five archetype decks (bridge_wincon, siege, beatdown, bait,
  chip). That gives 25 matchups × 2 seats = 50 cells × 48 seeds = **2,400 paired seeds**.
- **Guard population:** the three L2-v4 families against their L2-v4 opponents (`L2-V4-PREREG.md` §3 rotation;
  styles off, since the opponent is the v1 policy), alternating seats: **600 paired seeds**.
- **Seeds (fresh; the seed audit must prove them disjoint from every frozen K/K-v2/K2/S1/R3/X/G/DAgger range and
  helper offset before the freeze):**

  | Use | Range |
  |---|---|
  | Primary reporting | `4503603107370496+[0,2400)` |
  | Guard reporting | `4503603207370496+[0,600)` |
  | Excluded smoke (8 seeds × 8 arm-cells) | `4503603307370496+[0,8)` |
  | Speed-corpus generation (§6.1; no outcomes used) | `4503603407370496+[0,64)` |

- **Schedule:**
  - Each seed's 8 arm-cells run back-to-back on one host and slot, in cyclic rotated order.
  - Slots are 5 physical cores, with no SMT siblings, at nice 10 / SCHED_OTHER. Each arm narrows to its own core
    count, as in K2.
  - Only complete blocks count. An interrupted block is preserved, excluded and never re-seeded.
  - Hosts are the clasher allocation (01–04, 07, 08; never 05, 06 or leased hosts for timing). The coordinator
    assigns them, with the exclusive-host guard from S1.

## 4. Power and sample size

- **Variance inputs.** Per-pair SDs of loss differences come from today's 600-seed CIs (σ = half-width/1.96·√600):
  - S−K0c 0.61;
  - S−K2 0.55;
  - K2−K4 0.48;
  - K4−K0 0.55;
  - K2−K0 0.63.
- **Planning values.** The design uses σ = **0.63** for V1 and **0.56** for NI. Effect planning values:
  - S−K0c −16, observed in S1;
  - K2−K0c ≈ −15, implied by S1;
  - K4−K0c ≈ −27;
  - S−K2 ≈ −1;
  - K2−K4 ≈ +8.5.

**V1 power** (one-sided α = 0.025/3, z = 2.394), by true effect:

| n | SE pp | −13 | −14 | −15 | −16 | −20 |
|---:|---:|---:|---:|---:|---:|---:|
| 600 | 2.57 | .11 | .20 | .33 | .48 | .93 |
| 1,800 | 1.48 | .35 | .62 | .83 | .95 | 1.00 |
| **2,400** | **1.29** | .48 | **.76** | **.93** | **.99** | 1.00 |
| 3,000 | 1.15 | .58 | .86 | .97 | 1.00 | 1.00 |

**NI power** (+5 pp margin, one-sided 0.025), by true S−K2:

| n | SE pp | −0.83 | 0 | +1 | +2 | +3 |
|---:|---:|---:|---:|---:|---:|---:|
| 1,800 | 1.32 | .99 | .97 | .86 | .62 | .33 |
| **2,400** | **1.14** | 1.00 | **.99** | **.94** | .75 | .42 |

- **Choice: n = 2,400.** It gives ≥0.93 power for K2/S V1 at the observed effects, and still 0.76 if the true
  effect has regressed 2 pp toward the margin. S1's own n = 600 had only about 0.48 power at its point estimate,
  and passed by 1.17 pp.
- **K4 in the 1.0 cell.** V1 power is essentially 1. A false NI of K2 against K4, with true +8.5, has
  probability <10⁻⁷.
- **0.8 cell.** The control collapses there (K0c-160 79%), so V1 and V2 are not binding. NI between tiers is the
  operative test, at the same precision.
- **Guard, n = 600.** Superiority power is 1.00 if the effect transfers fully (−16 pp), 0.88 at half (−8), and
  0.49 at −5.
- **No interim looks**, no optional stopping, no re-estimation.

## 5. Statistics

- Paired-seed percentile bootstrap, **10,000 resamples**, `numpy.default_rng(2026101040)`, shared across all
  contrasts. Resampling is stratified by deck-matchup × seat cell.
- Upper bounds for V1/V2 come from the 98.33% two-sided interval; for G and NI from the 95% interval.
- Bonferroni covers the three tier-viability claims. NI and G are selection gates applied only to tiers that
  already passed V1/V2, so they get no further adjustment.
- The speed cell is chosen by a physical Mac measurement, under a rule frozen here (§6), so there is no
  adjustment across cells.
- Cutoff, fallback and overrun rates are reported with per-game numerator/denominator resampling, as in S1.
- An **independent integer-count verification script** is authored and committed before outcomes open, following
  the S1 precedent.

## 6. Mac measurement and the decision rule

### 6.1 Speed corpora (built on the fleet before the freeze)

- **The corpus.** 300 nonterminal decision states per tier come from smoke-range K0c games (seeds
  `…3407370496+[0,64)`), with stratified sampling by elixir and legal-play count. They are sealed as root bytes
  plus public history.
- **The work unit.** It is **no-deadline** full work for that tier: exact screen8 scoring with the tier's worker
  count, plus, for S/K0c, the cached forward and top-8 proposal.
- **Exactness.** Identical work is enforced by exact score/action equality.
- **The fleet reference.** Per-state wall time on 127x01, physical cores, nice 10, measured 3 times; the median is
  frozen into the manifest.

### 6.2 The speed ratio

r_T = **median over the corpus of (fleet wall / Mac loaded wall)** per state, for T's thread configuration:
- r_1 for S and K0c (the S corpus includes the student forward);
- r_3 for K2;
- r_5 for K4.

It is measured by the E4-v3 addendum (`mac-e4-package/E4-V3-ADDENDUM-DRAFT.md`) with replay perception load
running and the configuration and priority the live runtime will use.

### 6.3 Feasibility on the Mac

Tier T is **Mac-feasible** iff all of the following hold:
1. r_T ≥ 0.80, and the 10th percentile of the per-state ratio is ≥ 0.60, which keeps it clear of K-v2's
   0.6× cliff;
2. while T runs, the replay perception load keeps **≥18 processed FPS and ≥95% processed**;
3. the arm64 exactness checks pass (§7);
4. the timestamped GC/poll check passes: maintenance-delayed polls ≤1% of opportunities, and no pause >150 ms
   during an opportunity, with either default GC or the registered `gc.freeze()` variant;
5. for S only, the loaded student forward p99 is ≤20 ms on the chosen backend.

### 6.4 Speed cell

- s_T = 1.0 if r_T ≥ 1.00, and 0.8 if 0.80 ≤ r_T < 1.00. Faster Macs get no credit beyond 1.0.
- The control cell is s_1 = cell(r_1).

### 6.5 Rule (frozen)

1. A = {T ∈ {K4, K2, S} : Mac-feasible ∧ V1 ∧ V2 at (s_T, s_1) ∧ G at the same cells}.
2. If A = ∅, select **F0**: no tier change. The frozen L2-v4 search configuration stays, and the report says
   "no supported tier".
3. Otherwise, T_max = the tier in A with the most cores. **Select the cheapest T ∈ A whose NI against T_max holds**
   (T_max qualifies trivially).
4. Selection fixes the tier, its cell and its deadline. Live uses the **200 ms** deadline whatever the cell; the
   cell only says which fleet evidence applies.

**Measurement integrity:**
- There is exactly one valid Mac session. Repeats are allowed only for the technical failures pre-listed in the
  addendum (§F), and then the **minimum r_T across valid sessions** is used.
- The later formal E4 / T9 emulator-on smoke must re-measure r_T on the same corpora. If any r_T falls to a lower
  cell or below 0.80, the rule is re-applied with the lower value. The rule is monotone, so no new outcomes are
  needed.
- r_T can never be raised after the outcomes are seen.

## 7. Mac must-measure-first list (blocking, in this order)

1. **Identity:** chip, P/E core counts (`hw.perflevel0/1.physicalcpu`), RAM, macOS, thermal state; the arm64
   Python, Torch and Rust toolchain.
2. **arm64 native build** from the frozen tier source, with no Linux binary, and exactness:
   - 125-state exact screen8 actions, candidates and scores against the Linux receipts;
   - 1/2/4-worker equality;
   - zero-budget root immutability.
3. **Student cross-platform agreement** on 2,000 frozen states:
   - Mac CPU (1 Torch thread) and MPS each against fleet CPU;
   - the gate decision and top-8 ordered list must agree on **≥99.5%** of states;
   - every disagreement must be within 1e-4 of the threshold or an exact logit tie.

   **Backend: CPU by default.** MPS is used only if its loaded p99 is ≥2 ms lower **and** perception p95 rises
   ≤2 ms while it runs (MPS is shared with perception).
4. **Free capacity** with replay perception running and no search: per-core idle at 1 Hz, mapped to P/E clusters,
   reported as free P / free E (p10, p50). This is descriptive; feasibility is decided by item 5.
5. **Loaded r_1, r_3, r_5** (§6.2), each ≥300 states and ≥5 min after a 5-minute thermal warm-up. Unloaded ratios
   are also measured, to separate contention from raw speed.
6. **Deadline-mode tier cells:** 1,000 replay packets × {K0c, S, K2, K4} at 200 ms / 8 ms reserve under load.
   Record:
   - p50/p95/p99/max;
   - cutoff, fallback and no-complete-play rates;
   - overruns >200 ms and cut returns >208 ms;
   - **timestamped GC pauses against scheduled poll deadlines**, with default GC and with the `gc.freeze()`
     variant.

## 8. Kill criteria

- **Before reporting** (no outcomes are opened): any qualification, exactness or pin failure; a seed-audit
  overlap; foreign compute on a timing slot; a smoke timing/metadata failure. Fix, re-qualify, and use a new
  smoke range if code changed.
- **Validity:** if K0c@1.0 loss falls outside [36%, 54%] (the prior studies ran 44–48%), the result is reported
  but the selection is **suspended** pending an independent harness-drift review. No re-run on the same seeds.
- **Tier kills:** a tier is killed for this program if it is not Mac-feasible, or fails V1, V2 or G in its cell.
  S is also killed by a student-agreement failure (§7.3) or a loaded forward p99 >20 ms.
- **Program kill:** if A = ∅ even though every r_T ≥ 1.0, the failure is strength, not speed. The tier program
  stops, and research returns to the fleet.

## 9. Recorded design decisions

- **D1, student:** re-freeze, no retrain (§2.1).
- **D2, one belief root.** Every result behind these tiers (K, K-v2, K2, S1) used one sampled public root per
  decision. The live S6 pipeline uses four, which is roughly 4× the scoring work: on any plausible Mac that puts
  every tier past the K-v2 cliff. There is no strength evidence for four roots under W.
  **The selected tier is therefore registered as one-root**, and activating it needs an L2-v4 amendment replacing
  K=4 roots. Four-root timing remains a descriptive E4 cell (the existing package), not a candidate.
- **D3, fixed live deadline.** Live keeps a 200 ms deadline. Slower hardware maps to the 0.8 cell's *evidence*;
  the deadline is never shortened.
- **D4, static tier per session.** No in-match tier switching. A watchdog downgrade is a separate engineering
  amendment and is not covered by this evidence.
- **D5, opponent.** The plain v1 policy (human proxy), as in every input study. A v1+W opponent is out of scope.

## 10. Limits (stated up front)

- Fleet cells emulate speed by budget, not by underclocking. Preparation, return and tick conversion run at fleet
  speed.
- The simulator has perfect public observation. Perception noise is L2-v4's question, not this one's.
- Mac timing is replay-only. Formal E4 (emulator-on, real gRPC, P4 acceptance, eight matches) is still required
  before live play.
- Live play happens only under Sam's authorisation, on the Mac emulator with a throwaway account, with no
  detection evasion, and under the fair-information rule. Nothing in this PREREG authorises live play.

## 11. Run order

1. Independent review.
2. Freeze: source, plan, seed audit, speed corpora and fleet reference.
3. Qualification and smoke on the fleet.
4. Fleet reporting: 2,400 + 600 seeds × 8 arm-cells, about 4–6 h.
5. Verification and reduction.
6. The Mac session, whenever Sam authorises it; it can come before, during or after steps 4–5.
7. Apply §6.5.
8. Draft the L2-v4 amendment for the selected tier.

Steps 4 and 6 are independent by design.
