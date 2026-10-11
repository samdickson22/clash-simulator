# PREREG-K4S (DRAFT r2, not frozen): speed-gated K4 + student-default Mac tier

- **What this is.** Draft r2, 2026-10-11T09:20Z, by the design worker (Opus, 127x05) for coordinator `0523ae6f`.
  It revises r1 (`68a15c6a`, sha256 `caa52ad0…`) after the independent review `PREREG-K4S-REVIEW-r1.md` (verdict
  REVISE: 5 MAJOR, 8 MINOR, 1 NIT). Each finding's disposition is in `PREREG-K4S-RESPONSE-r1.md`.
- **What changed.** The games, arms, seeds and n are unchanged. The decision layer (§1.3–1.5), the release rule
  (§4.5) and several specifications were rewritten.
- **What has not happened.** This is design only: no game, compute job or Mac access, and nothing is frozen.
  Freezing is the coordinator's decision.
- **Relation to TIERS and T1.** The study is separate from, and runs after, PREREG-SEARCH-TIERS (r3 `ef0db97a`,
  freeze record `47aba25e`/`cc6410b2`, Amendment 1 `a149a474`) and the sealed T1 run. It edits no TIERS or T1 file.
- Paths are relative to `reports/`.

## 0. Summary

**Question.** Plain 4-thread anytime W (K4) collapses on slower cores through the WAIT spiral. In X4S its loss vs v1
was 18.5 / 27.8 / 47.3 / 89.0% at 200 / 160 / 140 / 120 ms. Does K4 with the frozen R3a student as its cutoff default
("K4S") give a Mac tier that:
- keeps fleet-K4 strength at 0.8–0.9× per-core speed, and
- is a usable rescue at 0.6–0.7×?

At 0.6–0.7×, K4 itself is TIERS-infeasible (TIERS needs r ≥ 0.8). Whether S or K2 remain feasible depends on their
own 1-core and 3-core ratios.

**Tier.** The tier is **speed-gated**. The student default is ON only when the Mac's evidence cell c_e (§1.5) is
below the full-speed cell 1.0. At full speed the tier is plain K4, which TIERS governs.

**Design.**

| Element | Choice |
|---|---|
| Arm-cells on every block (8) | K4 and K4S at 1.0 / 0.9 / 0.8×, plus K4S at 0.7 and 0.6× |
| Subsample arm-cells | Plain K4 at 0.7 and 0.6×, on the first 600 primary and 300 guard seeds |
| Speed emulation | By budget: 200 / 180 / 160 / 140 / 120 ms |
| Inference charge | The search seat's network poll is additionally charged at **1/s inside the timer** in every arm |
| Opponent | Plain v1 |
| Seeds | **3,000 primary** (X4S five decks) and **900 guard** (L2-v4 own decks vs the three held-out human decks), all fresh |

**Decision.**
- A fixed-sequence test of seven hypotheses at one-sided α = 0.025 (§1.2) admits each speed cell at one of two
  levels:
  - **A:** within 5 pp of fleet-speed K4;
  - **B:** within 10 pp of fleet-speed K4, *and* superior to plain K4 at the same speed.
- Deployment (§1.5) is keyed on the TIERS selection. K4S replaces a TIERS K4 pick on a 0.8–0.9× Mac, and fills in
  only where TIERS selects F0.

**Expected outcome (planning, not a claim).** Cumulative probability of passing, at central planning values
(pessimistic in parentheses; see §3.5 for the central/pessimistic basis):

| Claim | Probability |
|---|---|
| B at 0.8 and 0.7 | 1.00 (0.91) |
| B at 0.6 | 0.96 (0.67) |
| A at 0.9 | 0.94 (0.52) |
| A at 0.8 | 0.86 (0.27) |
| A at 0.7 | ≈0.13 |

At the only direct estimate for the charged design at 0.8× (+3.2 pp), level A at 0.8 is about a coin flip. Level B
at 0.8–0.7 is near-certain.

**Cost.**
- 33,000 games ≈ 360 five-core slot-hours ≈ 1,800 reserved physical-core-hours (≈ 460 CPU-h used).
- Wall time: ≈ 11 h on three hosts at 11 slots, ≈ 16 h on two.
- END reference: ≈ 2–3 h.
- One Mac measurement (§1.4).

**Earliest start.** After T1 reporting and T1 END references, and after perception A2's 03/08 transports are retired
(§4.2). Realistically 2026-10-12.

## 1. Hypotheses and decision rule

### 1.1 Notation

- **Cells:** c ∈ {1.0, 0.9, 0.8, 0.7, 0.6}.
  - Budget b(c) = 200c ms, with an 8 ms return reserve.
  - The search seat's poll is charged at 1/c (§2.4).
- **Loss:** L(X@c) is arm X's opponent-win rate in cell c. Draws are non-losses and reported separately. Every
  contrast is paired on the seed.
- **Arms:**
  - **K4** is the frozen T1 K4 arm (§2.2).
  - **K4S** is K4 plus the SD1 student default (§2.3).
- **Contrasts** (superscript G = guard population):
  - Δ_ref(c) = L(K4S@c) − L(K4@1.0), against fleet-speed K4 in this study;
  - Δ_same(c) = L(K4S@c) − L(K4@c).

### 1.2 Hypotheses and the fixed testing sequence (primary FWER ≤ 0.025, strong control)

Every bound below is taken from the two-sided **95%** paired interval (one-sided 0.025). Each hypothesis is an
intersection–union: all of its parts must hold.

| Level, cell | Part 1: upper Δ_ref(c) | Part 2: upper Δ_same(c) | Part 3: upper Δ_ref^G(c) |
|---|---|---|---|
| **A(c)**, c ≤ 0.8 | ≤ **+5 pp** | < 0 | ≤ **+10 pp** |
| **A(0.9)** | ≤ +5 pp | — | ≤ +10 pp |
| **B(c)**, c ≤ 0.8 only | ≤ **+10 pp** | < 0 | ≤ **+15 pp** |

**Nesting.** For c ≤ 0.8, A(c)'s parts imply B(c)'s. The admitted level is the strongest one tested and rejected.
B(0.9) is not defined.

**Testing order.** Hypotheses are tested **in this fixed order**, and testing stops at the first failure. Anything
after a failure counts as not admitted.

| Step | Hypothesis | Why it sits here |
|---|---|---|
| H1 | B(0.8) | Core rescue claim at TIERS's own K4 evidence cell. K4@0.8 lost +9.3 pp vs K4@1.0 in X4S. |
| H2 | B(0.7) | The first cell below K4's TIERS feasibility floor. |
| H3 | B(0.6) | The slowest plausible (E-core) Mac. |
| H4 | A(0.9) | Full parity near the gate. Only used for c_e = 0.9 (§1.5); a 0.9× Mac otherwise uses 0.8 evidence. |
| H5 | A(0.8) | "Full" label at 0.8×. |
| H6 | A(0.7) | Upgrade; planned power ≈ 0.15. |
| H7 | A(0.6) | Upgrade; expected to fail. |

- **Why B before A.** Under §1.5, B(0.8) already licenses replacing K4 on 0.8–0.9× Macs. So the rescue claims carry
  the decision value; the A-levels are labels and upgrades. The trade-off is in Q13 (§8).
- **Error control.** This is a pure fixed-sequence procedure, so α is not split and FWER over H1–H7 is ≤ 0.025 for
  this prespecified order. Within each hypothesis, the intersection–union parts need no further adjustment.
- **The 0.9 gate check is not in the chain.** Upper [L(K4S@0.9) − L(K4@0.9)] ≤ +5 pp is a **deployment veto** on
  using c_e = 0.9 (§1.5). It never stops the sequence. A veto can only remove admissions, so FWER is unaffected.

**Why these margins.**
- **5 pp (level A)** is the TIERS NI margin and S1's margin. "A" means as good as fleet K4 for deployment, the same
  standard TIERS uses between tiers.
- **10 pp (level B)** is the TIERS V1 and G2 margin. L(K4@1.0) ≈ 18–24%, so B caps the tier at about the observed
  K2/S range (25–32%), while requiring that it beat plain K4 at the same speed.
- **Guard margins are primary + 5 pp,** because n = 900 is less precise. TIERS used 10 pp on 600.
- **Draws** count as non-losses, as in TIERS.

### 1.3 The gate: where S-default switches on

- **Definition.** The gate is a static per-session switch (TIERS D4: no in-match switching). S-default is ON iff the
  evidence cell c_e (§1.5) is ≤ the threshold cell c*. It is defined by c_e alone.
- **Default c\* = 0.9:** S is ON in every K4S evidence cell. The risk is asymmetric:
  - S's exploratory cost at full speed was small and not significant: +2.2 pp [−0.3, 4.7] on X; +0.4 [−2.4, 3.1]
    on G.
  - Leaving S off when it is needed forgoes K4S's rescue: −9.7 pp at 0.8× and −25.2 pp at 0.7× (X4S, K4S − K4,
    same budget).
  - Live speed also drifts with thermal state and perception bursts, so the switch should fail safe.
- **The prespecified X4S-2 phase E rule.** The coordinator applies it once, before the freeze, and records it in the
  freeze record with phase E's reduction UTC.
  - Let d180 = L(K4S-180) − L(K4-180) on the X population, with phase E's paired 95% CI.
  - **If the lower bound of d180 > 0** (S significantly hurts at 0.9×), set **c\* = 0.8**:
    - H4 is dropped from the sequence (the order becomes H1, H2, H3, H5, H6, H7);
    - K4@0.9 and K4S@0.9 become descriptive;
    - a 0.9× Mac follows TIERS (plain K4).
  - **Otherwise c\* = 0.9.** This includes the case where phase E is not complete at the freeze.
  - No other exploration outcome may move c\*.
  - **Locking.** This rule text is final as of r2. At r2's writing (09:07Z), phase E had not been reduced
    (X4S-2 PROGRESS ends at phase B). Any later change to it would be outcome-informed and would void the rule; c\*
    would then default to 0.9.
- **No S-lite.** The X4S-2 "S-lite" rule (phase C) is not adopted. Under the gate, S is never on at full speed, which
  is the only place S-lite was meant to help.

### 1.4 Threshold measurement on the Mac (E4-style; needs Sam's authorisation)

**Cell 1.0 is TIERS's K4 cell.** c_M = 1.0 iff TIERS finds K4 Mac-feasible in its 1.0 cell, by TIERS's own r_5,
p10 ≥ 0.70 and gates 2–6 (TIERS §6.3–6.4). No SD1-specific gate applies at 1.0, because K4 runs no SD1.

**Cells c ≤ 0.9 are K4S cells.**

*Work unit.* It is TIERS §6.1's complete no-deadline decision (belief, candidates, root, 4-worker exact screen8,
reduction), **plus the charged SD1 poll span and top-8 ranking**.

*Corpus.*
- It runs on the **frozen T1 K4 speed corpus** (300 states, SHA-pinned in T1's inventory `81f2483e`).
- This is K4's corpus, not one from K4S's own games. That is disclosed: S changes the trajectory only through
  cutoffs, so the state distribution is close at fast cells and less representative at 0.6–0.7×.
- Exactness follows TIERS §7.2 (ARM64-NEAR-EXACT) and §7.3 (student agreement ≥ 99.5%).

*Measured under replay perception load,* with the live configuration and priority:
- **r_K4S** = min(median per-state ratio, Σ-ratio, p90 ratio), the TIERS §6.2 statistic, and **p10_K4S**, the 10th
  percentile of the per-state ratios.
- **r_inf** = (fleet END median poll span) / (Mac median poll span). The poll span is the same timed span the charge
  scales: `poll_seconds`, from the call to the policy poll until its return (packet → forward → ranking). It is
  taken over the corpus states on the chosen backend (TIERS §7.3: CPU by default). The fleet value comes from END
  item (c) (§4.5).
- **Forward p99** of the poll span.
- **Deadline mode:** the K4S corpus at **200 ms** on the Mac (cutoff rate and no-complete-play rate).

*Cell mapping.* For c ≤ 0.9, c_M is the largest c that passes all of:
1. r_K4S ≥ c and p10_K4S ≥ c − 0.10. This deliberately generalises TIERS's p10 ≥ 0.70 at 0.8 to every cell.
2. **Inference coverage: r_inf ≥ c²** (§2.4).
3. Poll-span p99 ≤ 20 ms.
4. Perception keeps ≥ 18 processed FPS and ≥ 95% processed while K4S runs.
5. TIERS §6.3 gate 4 (GC/poll).
6. **Deadline equivalence:** the Mac's 200 ms cutoff and no-complete-play rates are each ≤ the fleet END deadline-mode
   rates for K4S at b(c) with the 1/c charge, **+ 2 pp**. If this fails, move down one cell and re-check.

If nothing passes, the tier is Mac-infeasible.

**Integrity and status.**
- TIERS §6.5 measurement integrity applies: one valid session; repeats only for pre-listed technical failures,
  classified mechanically; the minimum r and worst gate inputs across valid sessions are used.
- A replay-only (emulator-off) result is **PROVISIONAL** until formal E4/T9 re-measures every input (TIERS §6.5
  item 5).
- **Implementation:** a reviewed addendum adds a K4S configuration to E4's `measure_tiers.py`. Using the same session
  as TIERS is the default (Q5).
- If the session runs **after** K4S outcomes are released, an independent reviewer confirms the mechanical
  session-validity classification before it runs (TIERS §6.6(b)).

### 1.5 Deployment rule and interaction with TIERS

- **Admitted set.** 𝒜 is the set of cells admitted at level A or B under §1.2.
- **Usable evidence cells.** A cell c is usable when:
  - c = 0.8 and it is admitted at A or B; or
  - c = 0.9, admitted at A, **and** the §1.2 gate-check veto passes; or
  - c ∈ {0.7, 0.6} and it is admitted at A or B.
- **Evidence cell.** c_e = max{usable c ≤ c_M}. If there is none, c_e is *undefined*.
- **Convention.** Using a slower cell's evidence for a faster Mac is the TIERS convention, and assumes loss is
  non-increasing in speed. That assumption is untested. X4S's point estimates violate it within noise (K4S-160
  18.2% < K4S-200 20.7%), and §5.3 item 9 checks it descriptively.

| TIERS selection | Rule |
|---|---|
| not yet available | K4S is held; it never pre-empts TIERS. |
| **K4** | If c_M = 1.0: plain K4 (S off). If c_M ≤ 0.9 and c_e ∈ {0.9, 0.8} with c_e ≤ c\*: **K4S (S-default on)**. Otherwise: plain K4 as TIERS selected. |
| **K2 or S** | **TIERS stands** (Q12). There is no paired evidence for K4S against K2 or S. |
| **F0** | If c_e is defined and ≤ c\*: K4S at c_e, labelled by its level ("full" for A, "degraded" for B). Otherwise F0. |

General rules:
- **The live deadline stays 200 ms** (TIERS D3). The cell only says which evidence applies.
- Activation also needs:
  - the TIERS D2 one-root L2-v4 amendment;
  - formal E4/T9;
  - the coordinator's review.
- **Nothing here authorises live play.**

## 2. Artifacts

### 2.1 SD1: R3a re-frozen as a new artifact

**Name.** `SD1`, full ID `clasher-sd1-k4s-default-20261011`. These are the **exact R3a bytes** under a new artifact
identity, with no refit (Q8).

| Item | Value |
|---|---|
| EMA checkpoint (sha256) | `37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85` |
| Calibration (sha256) | `e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414` |
| Threshold | 0.5005528330802917 |

**Manifest.**
- `SD1-MANIFEST.json` binds the checkpoint, the calibration and the threshold.
- It also binds the SHA of every inference source file (cached policy, `proposals.py` ranking, `model_packet`), the
  Torch version and the inference mode (CPU float32, one Torch thread).
- Its own SHA-256 is **the SD1 hash**, computed at the freeze. The runner refuses to start on any mismatch.

**Training recipe.** Fixed for disclosure and for any future refit, from `imitation/exit-r3/PLAN.md`:
- **Initialisation:** released v1 step 22552 EMA, width 192 (`d77005d5…`).
- **Steps and sampling:** 2,500 AdamW steps × 8,192 root rows, sampled uniformly with replacement; train seed
  2026101013.
- **Data:**
  - R1 corpus `1c8e1f49…`: 6,009,681 eligible roots;
  - plus five G shards (pause manifest `4e8faf7e…`): 212,542 roots;
  - total 6,222,223 roots;
  - only teacher_root = true and wait_kind = 0.
- **Loss:**
  - listwise softmax over valid completed candidates at T = 0.003;
  - plus the existing R2 gate/card/tile loss terms, with conditional full-8,192 denominators;
  - play weight 1, value weight 0.
- **Optimiser:**
  - learning rate 3e-4, weight decay 0.05, warm-up 2,000, cosine over 2,500 steps;
  - gradient clip 1; EMA 0.999; bf16 autocast;
  - final EMA only.
- **Gate calibration** on the R1 heldout64 slice (`0ecce0f0…`), with no action labels:
  - choose the scalar P(play) threshold, requiring a legal play, that gives the deterministic play prevalence
    nearest to 34.6%;
  - use the midpoint between sorted adjacent probabilities;
  - on exact distance ties, take the smaller threshold.
- **Recipe variance:** R3d, a new-seed refit of this recipe, differed by −0.036 pp in play recall.

**Status and supersession** (text proposed for the coordinator to issue at the freeze):
- R3a **remains KILLED** under R3 Stage 1. R3's files are not edited.
- "This PREREG, issued by coordinator `0523ae6f` under the owner's delegation, supersedes R3's 'ALWAYS
  NEVER-ADOPTABLE … regardless of its paired benefit' clause (`exit-r3/RESULTS.md` l.85, 97, 125) **for these exact
  bytes in the K4S cutoff-default role only**."
- The supersession is **outcome-informed**: it follows X4S and X4S-2 (and, for tier S, r1(b) and S1), and the report
  says so.
- Claims attach only to SD1 in this role. They never attach to the R3 recipe or to tier S. TIERS §2.1's separate
  supersession for tier S is unaffected.
- An additive pointer is placed in `exit-r3/`.

**Disclosures** (repeated in the final report):
- the full R3 chain from TIERS §2.2;
- R3a trained on all eight R1 deck slots, which include the L2 Hog 2.6 and X-Bow decks, against an opponent mix
  that includes v1. The primary population is therefore in distribution for SD1, which favours K4S. The guard
  removes only the opponent-deck overlap.
- The threshold was calibrated on the heldout64 slice. That slice is not reopened; only the frozen value is used.

### 2.2 K4: frozen configuration

K4 is exactly T1's K4 arm. It comes from the T1 reporting runtime (freeze `ef4c073a`, OP-7 manifest), with bytes
pinned by SHA at the freeze:
- **Collector:** K2's WAIT-first anytime collector.
- **Threads:** **threads = 4** scorer workers plus the main thread, on **5 physical cores** with no SMT siblings.
- **Horizons and refinement:** **coarse_horizon = 160**; complete-score horizon 160; three rollout styles; top-8
  refinement.
- **Belief:** one sampled public belief root; exact resumable, cancellable belief.
- **Timing:** search interval 10 ticks, policy interval 5; d = 27, capacity 1.
- **Native:** `44874fd6…`.
- **Fallback:** the v1 policy poll, used only when no complete score exists.
- **GC:** in-decision GC deferral, metered.

K4@1.0 must equal T1's K4@200 behaviourally. This is qualified directly (§4.1).

### 2.3 K4S: the S-default rule (frozen)

K4S is K4 with three changes, all on the **search seat only**. The opponent is untouched.

1. **Seat poll.** The seat's poll is SD1 instead of v1, using one cached forward per poll. It gives the calibrated
   deterministic default: WAIT if P(play) < threshold or there is no legal play; otherwise the highest-ranked legal
   play.
2. **Coarse order.** SD1's top-8 ranked legal plays are coarse-scanned first.
   - This is *scheduling only*. The candidate set is unchanged: no augmentation and no refinement proposals.
3. **Cutoff default.**
   - If preparation cuts off (belief update, sample or pre-scoring), return the SD1 default.
   - If the scoring deadline hits and **no legal play has a complete score**, and the SD1 default is a play, return
     that play with selected_wait_ticks = 0.
   - An SD1 WAIT keeps the frozen choice.
   - Whenever any play has a complete score, the frozen best-complete-score rule stands.

**With no deadline, K4S ≡ K4** (qualified, §4.1).

The reference implementation is `explore/x4s2/sdefault.py` (full rule) together with the K4S branch of
`explore/x4s2/run.py`. It is **ported into the T1 runner and reviewed**, not imported (§6).

### 2.4 Honest inference charge

**What budget equivalence already does.** Budget equivalence already scales all in-timer work, inference included,
by 1/c relative to the budget (X4S-2 PLAN).

**The additional charge.** As the assignment requires, every arm sleeps an extra (1/c − 1) × the measured
`poll_seconds` of the search seat's network poll in each search decision, **inside the timer**.
- This is X4S-2's "inference" mode, extended to every arm. K4S's SD1 poll and K4's own v1 poll are both charged,
  which models one Mac consistently and keeps SUP fair. X4S-2 had left K4's poll uncharged.
- At c = 1 the charge is zero.
- The sleep idles a dedicated core and so only shifts the deadline.

**What it emulates.** In fleet-ms, the emulated constraint is W_search + poll/c ≤ 200c − 8. In real Mac ms at
per-core speed c, that is W_search/c + poll/c² ≤ 200 − 8/c, which is ≤ 192 for c ≤ 1. On a Mac with r_K4S = c, the
real constraint is W_search/c + poll/r_inf ≤ 192. So the arms cover any Mac with **r_inf ≥ c²** (gate 2 of §1.4),
with a further 8/c − 8 ms of slack. This is conservative for a uniform slowdown.

**Disclosed limits:**
- Positive overruns are charged in fleet milliseconds, so overrun lateness is under-penalised by the factor c. Such
  overruns were about 0.1% of decisions in X4S/X4S-2.
- The opponent (it has no deadline) and polls at off-search ticks are not scaled.
- Return and tick conversion run at fleet speed (TIERS §10).

## 3. Design

### 3.1 Arms and blocks

| Arm-cell | Budget (ms) | Seeds | Role |
|---|---:|---|---|
| K4@1.0 | 200 | every block | reference for every Δ_ref |
| K4S@1.0 | 200 | every block | secondary F1: the full-speed cost of S |
| K4@0.9 | 180 | every block | 0.9 gate-check veto |
| K4S@0.9 | 180 | every block | A(0.9) |
| K4@0.8 | 160 | every block | SUP comparator at 0.8 |
| K4S@0.8 | 160 | every block | B(0.8), A(0.8) |
| K4S@0.7 | 140 | every block | B(0.7), A(0.7) |
| K4S@0.6 | 120 | every block | B(0.6), A(0.6) |
| K4@0.7, K4@0.6 | 140, 120 | primary i < 600; guard i < 300 | SUP comparators. Expected effects −24 / −60 pp give power ≈ 1 at n = 600. |

**Blocks.** A block is one seed's 8 or 10 arm-cells, run back-to-back on one slot.

**Rotation.**
- The eight core arms run in the table order, cyclically rotated by **ρ = ⌊i/50⌋ mod 8** (primary) or
  **⌊i/18⌋ mod 8** (guard). Each cell then sees all eight rotations (60 or 50 seeds per cell), and rotation is not
  tied to seat.
- The two subsample arms are inserted after rotated positions 3 and 6.
- **Replacement blocks inherit the lost block's arm set,** so the subsample never shrinks.

**Dispatch.**
- Blocks are dispatched in seed-index order, interleaving primary and guard **10:3** (3,000 : 900).
- The initial assignment is balanced across hosts by population, cell and seat (the T1 B2 balancer).

**One belief root** throughout (TIERS D2).

### 3.2 Opponent

- The opponent is the sealed plain **v1 policy, T = 1, no search**, as in T1, X4S and S1.
- **There is no second opponent** (Q4):
  - v1+W would roughly double the cost and is out of scope (TIERS D5);
  - a temperature-shifted v1 is no less in-distribution for SD1.
- The guard decks check opponent-side transfer. This limitation is disclosed.

### 3.3 Populations and decks

**Primary.**
- The five archetype decks of the K2/S1/X4S harness: bridge_wincon, siege, beatdown, bait, chip.
- 25 matchups × 2 seats = 50 cells; seed index i goes to cell i mod 50.
- **3,000 seeds,** 60 per cell.

**Guard.**
- Own decks: the three L2-v4 decks (Hog 2.6, X-Bow cycle, Royal Hogs spawners).
- Opponent decks: the three held-out human decks (Hog EQ, Goblinstein Royal Hogs, ArcherQueen Royal Delivery).
- These are **byte-identical to T1's `guard-decks.json`**, pinned by sha256
  `6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef` (selector `21125180…`, catalogue `80de4afb…`).
- 18 cells; i goes to cell i mod 18.
- **900 seeds,** 50 per cell.

These are deck lists already in use; no heldout game data is opened. No descriptive in-distribution cells are run,
because T1 plays them.

### 3.4 Seeds (fresh bank; audited before the freeze)

**Bank.** 2^52 + [6.18e9, 6.28e9). As of origin/main `bc2e4e5b`, the tracked tree contains no seed literal between
4503605500000000 and 4503606999999999, the reviewer independently confirmed.

| Use | Range |
|---|---|
| Primary reporting | `4503605807370496+[0,3000)` |
| Primary replacement | `4503605807370496+[3000,3600)` |
| Guard reporting | `4503605817370496+[0,900)` |
| Guard replacement | `4503605817370496+[900,1080)` |
| Excluded smoke | `4503605827370496+[0,8)` |
| Qualification | `4503605837370496+[0,8)` |
| Reserve (unused unless amended) | `4503605847370496+[0,64)` |

**Audit.**
- The seed audit (T1 `audit_seeds.py`, extended) must show the ranges disjoint, at helper offsets {0, 13,
  100000–100003, 271828–271829}, from every declared prior range:
  - K, K-v2, K2;
  - S1 (both banks);
  - R3, R1/G;
  - X, X4S, X4S-2 (including E/F);
  - T1 (all banks);
  - DAgger, noise-ceiling, L2-v4.
- It must also find no repo seed literal inside the window.

**Seats** alternate through the cell assignment.

**Replacement.** T1 §3.2 mechanics apply:
- the k-th lost block in cell c is replaced by seed 3000 + 50k + c (primary) or 900 + 18k + c (guard);
- replacements are stratified by the *lost* block's cell and assigned in blind loss order;
- each replacement keeps the lost block's arm set.

**Caps.** Replacement may not exceed 10% per population (300 primary, 90 guard) or the bank rows (k ≤ 11 primary,
k ≤ 9 guard). Beyond that: stop and amend before any outcome opens.

### 3.5 Power and sample size

**Planning σ** is the per-pair SD of loss differences, computed from X4S/X4S-2 CIs as σ = half-width/1.96·√n. The
reviewer reproduced all of these.

| Contrast type | Source values | Planning σ |
|---|---|---:|
| NI | 0.43 within-run; 0.48–0.52 cross-run | **0.47** |
| NI at 0.6 | 0.51 | 0.51 |
| SUP | 0.47–0.56 | 0.50 |
| Guard | 0.56–0.62 | **0.56** |

**Planning effects for Δ_ref.** The confirmatory K4S arms equal X4S-2's charged configuration (K4Sh).

| Cell | Central (pp) | Pessimistic (pp) |
|---|---:|---:|
| 0.9 | +1.5 | +2.5 |
| 0.8 | +2.0 | **+3.2** |
| 0.7 | +4.2 | +4.7 |
| 0.6 | +6.5 | +7.5 |

- **Pessimistic column.** At 0.8 the only direct estimate for this design is K4Sh-160 − K4-200 = +3.2 [−0.7, 7.0],
  and that is what the pessimistic column uses.
- **Central column.** It shrinks toward the uncharged X4S K4S estimates (−0.3 / +3.7 / +7.5 at 160/140/120), because:
  - the charge's own cost is about zero at 140/120 (K4Sh − K4S: +1.0, −2.0);
  - its +3.5 [0.0, 6.8] at 160 is non-monotone in budget and is most plausibly noise.
- **Other planning values:**
  - SUP at 0.8: −6.2 central, −3.0 pessimistic.
  - Guard Δ_ref^G: +2 to +3.5 at 0.9–0.7, and +5 (pessimistic +8) at 0.6 (phase F pending).
- **Selection.** These effects were selected after the fact and are likely optimistic.

**Marginal NI power at a 5 pp margin** (one-sided 0.025, σ = 0.47), by true Δ:

| n | SE (pp) | Δ = 0 | +1 | +2 | +3 | +4 | +5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,400 | 0.96 | 1.00 | 1.00 | .88 | .55 | .18 | .025 |
| **3,000** | **0.86** | 1.00 | 1.00 | **.94** | .64 | .21 | .025 |
| 3,600 | 0.78 | 1.00 | 1.00 | .97 | .72 | .25 | .025 |

- At a 10 pp margin, shift the columns by 5 pp.
- **Guard** (σ = 0.56, n = 900, SE 1.87): NI10 has power .99 / .76 at +2 / +5; NI15 has power 1.00 / .96 at +5 / +8.

**Sequential power** at n = 3,000 / 900.
- Each value is a cumulative product of marginals. The shared SUP(0.8) event is counted once.
- The products are conservative, because the parts are positively correlated.

| Step | Central | Pessimistic |
|---|---:|---:|
| H1 B(0.8) | 1.00 | .91 |
| H2 B(0.7) | 1.00 | .91 |
| H3 B(0.6) | .96 | .67 |
| H4 A(0.9) | .94 | .52 |
| H5 A(0.8) | .86 | .27 |
| H6 A(0.7) | .13 | .01 |
| H7 A(0.6) | .00 | .00 |

**Choice: n = 3,000 primary, 900 guard.**
- At 2,400 / 600, A(0.8) falls to 0.71 central.
- 3,600 adds ≈ 0.04 for about 20% more cost.

**Error control.** The FWER for any falsely admitted cell-level is ≤ 0.025. For example, a K4S that is truly +10 pp
worse at 0.8 is admitted at B with probability ≤ 0.025.

There are **no interim looks,** no optional stopping and no re-estimation.

### 3.6 Per-game record (sealed game JSON; compatible with C17)

| Group | Fields |
|---|---|
| Identity | study `PREREG-K4S`, freeze SHA, arm, cell, budget_ms, reserve_ms, inference_scale (= 1/c), scale_mode `poll`, kernel, threads, coarse_horizon, default_source (`v1` / `SD1`), s_default_rule (`full` / none), c\*; SD1 manifest SHA, checkpoint/calibration SHAs, threshold; opponent SHA, native SHA, runtime manifest SHA |
| Placement | population, seed, seed index, cell (matchup, seat), rotation ρ, block ID, replacement k, host, slot, core mask, nice, attempt directory |
| Outcome (sealed) | winner, loss, draw, crowns, ticks, command-sequence SHA |
| Per decision | tick, wall ms, CPU ms, deadline hit, preparation_cutoff kind; completed / coarse_scored / coarse_complete / plays; unpruned_candidate_count, own elixir; frozen_action, student_default flag, SD1 default action, **SD1 P(play)**, **coarse_order hash**, chosen action, fallback used, selected_wait_ticks; poll_seconds, scale_sleep_seconds, prep_seconds; positive overrun ms, charged extra ticks |
| GC | count, pauses, deferred-in-decision flag |

- **Per block:** T1 census and interference meters (OP-1 DBus, OP-4/6 SSH, OP-7 apt, idle services), proof SHAs and
  the hub acknowledgement.
- **Stdout:** identity and terminal health only (T1 C1).

## 4. Execution and validity

### 4.1 Runner: reuse T1, review deltas, re-qualify

**The runner** is T1's frozen reporting runtime plus reviewed deltas only:
1. a cell table with 180 / 140 / 120 ms budgets;
2. the poll-charge hook (§2.4), ported with X4S-2 `test_charge.py` semantics;
3. the K4S kernel (§2.3);
4. the 10-arm schedule, rotation ρ, subsample rule and 10:3 dispatch;
5. the new populations and seeds;
6. the reducer for §5, including the fixed sequence and the veto;
7. the per-decision fields;
8. the END reference cells, including poll-span timing.

Each delta gets an independent diff review whose reviewer is not the author.

**Qualification**, on every named host, before the freeze:
- **T1's full batteries:** 125-state 1-worker and 4-worker exactness; belief ON/OFF (125 histories, 250 variants);
  injected clock; lateness; GC.
- **K4@1.0 ≡ T1 K4@200:** command hashes and injected-clock decisions on the qualification seeds, under the delta
  runtime and under the frozen T1 runtime `ef4c073a`, must match.
- **K4 ≡ K4S with no deadline:** 125/125 frozen action and score equality, and identical command hashes on two
  qualification seeds.
- **Injected-clock S-default cases:**
  - a pre-scan cutoff returns the SD1 play;
  - an SD1 WAIT keeps the frozen choice;
  - a completed play keeps the frozen rule;
  - a zero budget returns the SD1 default.
- **Charge tests:** on every exit path in smoke, sleep share = (1/c − 1)/(1/c) ± 0.02.
- **Pins and cards:** the SD1 manifest check; the `guard-decks.json` SHA; guard-card support.

**Smoke.** An **excluded smoke** then runs on the smoke range, all hosts, ≥ 8 blocks per host. It reads no outcomes.

### 4.2 Hosts, exclusivity and the OP lessons

**Host set.**
- **Candidates:** {127x01, 03, 04, 08}, named at the freeze; at least two are required.
- **Not used:** 05 (command host only), 06 (unreachable), 02 and 07 (down), and roader hosts.
- **Slots:** 11 five-core slots per host on physical cores 0–54, or 8 if a console user is present at launch.
- **Reserved cores:** supervisor on 61, copier on 62, census on 63.
- **Priority:** nice 10 / SCHED_OTHER, no SMT.

**Conflicts as of 2026-10-11T09:04Z:**
- **T1** is reporting on 01, with 08 held (1,799/3,072 durable at 09:04Z). It then needs its END clean window on 01/08.
- **Perception A2** stage 2 runs on 04, which is allocated until 2026-10-12T12Z. Its ssh transports into 03/08 run
  until about 13–14Z.
- **X4S-2** holds 03 until 13:30Z and 08 until 12:30Z.
- **No K4S reporting or END may overlap T1 reporting or T1 END on the same host.**

**Lessons inherited from T1 OP-1..OP-7** (guard code unchanged, at the final reviewed OP-7 bytes):
1. **Perception transports (OP-2/4/5/6).** Unprovable sshd generations from 04 repeatedly stopped T1 on 03 and 08.
   - Use hosts with **no perception transport for the whole window**.
   - The coordinator records a *transport-retirement declaration* per host before admission.
   - The OP-6 LAN-SSH budget, with exact source seeds, applies only if a transport must remain.
   - Unknown-source sessions always stop the host.
   - T1's END contract also rejects SSH- and DBus-flagged reference work, which is another reason to avoid
     transports.
2. **apt (OP-7).** A root `unattended-upgrade --download-only` stopped T1 on 01 at 21:03Z. The OP-7 apt budget and
   the static `_apt` witness are inherited. We have no root and cannot disable the timer, so a stop is an
   availability cost, not a validity one.
3. **Pins and ownership.** The OP-1 system DBus pin, OP-3 owned-supervisor membership, and one copier phase at a
   time.
4. **Stop conditions.** Console users stop the host; foreign compute stops the host; the memory floor is 24 GiB.
5. **No cross-host pollers or mirrors** on timing hosts; they are paused by stop files before admission (S1
   attempt 1). Health comes from one bounded hub connection per check.

**Interference flags.** OP-6-style flags are recorded per block and disclosed. The primary analysis includes flagged
blocks; a sensitivity analysis excludes them (§5.3).

### 4.3 Timing and honest lateness (inherited unchanged)

- The full timer starts before observation.
- Every positive overrun is charged ceil(overrun × 20) ticks to command due time, own availability and timed waits.
- Partial and late scores never count.
- The scoring cutoff is the budget minus 8 ms.
- GC is deferred only inside decisions, and metered.
- The poll-charge sleep is inside the timer, so overruns it causes are charged too.
- Per-core MHz is recorded at 1 Hz in reporting and in END.

### 4.4 Lost blocks

T1 §3.2 mechanics apply:
- A block counts only when all of its arm-cells are complete **and** it is hash-verified on hub 01.
- A copy lag of 30 minutes stops the host.
- Started but incomplete blocks are lost and replaced (§3.4).
- Never-started blocks are re-dispatched with unchanged seeds.
- Losses are classified mechanically from receipts.
- If fewer than two named hosts remain, stop and amend.
- No host may be added without an amendment, its own qualification and its own END reference.

### 4.5 Seal, END reference and release barrier

**Sealed.** No outcome field is read before release. The reducer fails closed before it opens any game bytes.

**END reference.** It runs after the committed reporting-completion receipt, on **every host with counted blocks**,
in reference slot 0, under the reporting load profile (all other slots run the corpus loop), with 1 Hz MHz. It
measures:
- **(a)** no-deadline K4S and K4 on the T1 K4 corpus, 3 repeats;
- **(b)** deadline mode at all five cells with the 1/c charge, 3 repeats (per-state cutoff, no-complete-play and
  fallback rates);
- **(c)** the SD1 and v1 poll span on the corpus states (the fleet reference for r_inf).

**Pooling rules.**
- Each host's ratio to the pool must lie in **[0.95, 1.05] inclusive**. Otherwise the pool fails closed; hosts
  cannot be excluded after counting (T1 A1.1).
- One mechanically classified repeat is allowed.
- MHz is compared only against full-occupancy reporting rows, and the signed ratio is disclosed (A1.2).
- Committed-posterior replay is used (A1.3).
- **If the pool still fails,** it is re-run until it conforms, or the coordinator declares the K4S Mac speed ratio
  unavailable. In that case the tier is Mac-infeasible for deployment, and outcomes may still be released for the
  fleet claims (TIERS A1.1 wording).

**Release requires all of the following to be committed:**
1. the completion receipt;
2. the pooled END reference and its independent re-check (T1 `check_reference.py` pattern), or the
   "ratio unavailable" declaration above;
3. **PC1–PC4** adapted from T1: all original attempt roots; the reviewed E4 source inventory; one pinned
   interpreter; and the interference-sensitivity sidecar over the final counted inventory and blind ledger;
4. the **independent integer-count verifier**, whose author is not the reducer's author;
5. the frozen K4S Mac measurement procedure: the §1.4 scripts, the load-selection rule and the failure classifier;
6. **TIERS `tiers-summary.json`, or a released TIERS outcome barrier** (including via its 14-day escape). K4S plays
   TIERS's K4@200/160 cells on TIERS's populations, so opening earlier would give a confirmatory-grade steering
   input to the TIERS Mac session.

**What release does not wait for.** Release is **not** gated on the K4S Mac summary itself (Q3):
- every cell is tested inside the FWER family;
- the K4S mapping is frozen, mechanical and takes the minimum across sessions;
- any post-release K4S Mac session needs an independent classification review (§1.4).

**No automatic release.** The coordinator signs a release receipt that binds every SHA above.

### 4.6 Compute and time

- **Games:**
  - primary 3,000 × 8 + 600 × 2 = 25,200;
  - guard 900 × 8 + 300 × 2 = 7,800;
  - **33,000** in total.
- **Throughput:** about 92 games per five-core slot-hour (X4S/X4S-2). That gives about 360 slot-hours, about 1,800
  reserved physical-core-hours and about 460 CPU-hours used.
- **Wall time:**
  - about 8.2 h on 4 hosts (44 slots);
  - **about 11 h on 3 hosts (33 slots);**
  - about 16 h on 2 hosts.
  - Plan for 12–17 h including overhead.
- **Preparation and qualification:** about half a day of agent time and about 2 h of host time.
- **END:** about 2–3 h.
- **Mac:** about +30–45 min inside the TIERS E4-v3 session, or about 1.5 h standalone.

## 5. Analysis

### 5.1 Statistics

- **Bootstrap:**
  - paired-seed percentile bootstrap with **10,000 resamples**, `numpy.default_rng(2026101170)`;
  - shared across all contrasts within a population;
  - stratified by cell (50 primary cells, 18 guard cells).
- **Subsample contrasts** (K4@0.7, K4@0.6) resample the subsample seeds only, with the same stratification.
- **Arithmetic:**
  - exact rational percentile indices and integer loss counts (T1 reducer convention);
  - bounds are inclusive as written, except SUP, which is strict (< 0).
- **Rates** (cutoff, student default, fallback, overrun and play) use per-game numerator and denominator
  resampling.

### 5.2 Multiplicity

- The fixed sequence H1–H7 (§1.2) gives strong FWER control at 0.025 over every admission claim.
- Each hypothesis's parts combine by intersection–union.
- The 0.9 gate check acts as a veto only.
- **There is no adjustment across the Mac cell:** the cell is chosen by a frozen physical measurement, and every
  cell's claim is already inside the controlled family.
- Everything else is secondary or descriptive, unadjusted and labelled, and it never changes admission.

### 5.3 Secondary and sensitivity analyses (prespecified; descriptive only)

1. **F1, the full-speed cost:** L(K4S@1.0) − L(K4@1.0) with its 95% CI, on the primary and guard populations. If the
   upper bound is ≤ +2.5 pp on both, the report notes support for an "always on" gate in a future amendment.
2. **Interference:** exclude blocks with any OP-6/OP-7 interference flag (sidecar ledger, separate RNG stream).
3. **Matchup-cluster bootstrap** over the 25 matchups and the 9 guard pairs, for every primary contrast.
4. **Per host and per seat** contrasts, and a host × arm heterogeneity table.
5. **Mechanism by cell:**
   - cutoff, student-default and coarse-complete-at-cutoff rates;
   - play rate;
   - median candidate-set size;
   - WAIT-spiral indicators;
   - SD1 P(play) distribution.
6. **Latency:** overrun tables, cut returns > budget + 8 ms, and GC tables (K-v2/S1 format).
7. **Drift anchors** (unpaired, after T1 opens): K4@1.0 here vs T1 K4@200 and vs X4S K4-200.
8. **Draws** counted as half-losses.
9. **Monotonicity:** L(K4S@0.9) − L(K4S@0.8) and L(K4S@1.0) − L(K4S@0.9), checking the §1.5 convention.

### 5.4 What kills the tier, a cell or the study

- **Tier killed** (S-default leaves the Mac programme) if **H1 fails**: no K4S cell is usable even at level B at
  0.8×. The 0.8–0.9× Macs then keep TIERS's plain-K4 or cheaper selection.
- **A cell is not admitted** if its hypothesis fails or is not reached. Mapping then falls through per §1.5.
- **Mac side:**
  - SD1 cross-platform agreement below 99.5%, or poll-span p99 above 20 ms, kills the tier on that Mac.
  - r_inf < c², or a deadline-equivalence failure, lowers the cell or makes the tier infeasible.
  - An arm64 single-thread exactness failure (TIERS §7.2) kills every tier.
- **Validity suspension:** if L(K4@1.0, primary) falls outside **[10%, 30%]** (prior studies: 16–24%), selection is
  suspended pending an independent receipts-only code review (as in TIERS §8). A harness defect voids the study:
  a new PREREG with new seeds is required.
- **Before reporting:** any failure of qualification, exactness, pins, seed audit, smoke or card support means fix,
  re-qualify, and use a new smoke range. Reaching the replacement cap means stop and amend.

## 6. What may be adopted from exploration (X4S, X4S-2): **nothing**

| Source | Allowed use | Not allowed |
|---|---|---|
| X4S RESULTS (600 seeds × 9 arms) | Planning effects and σ (§3.5) | Evidence, pooling, any gate input, citation as support |
| X4S-2 phases A–D (K4Sh, K4Sf, guard B/D) | Planning effects and σ; the shape of the charge (§2.4) | Same |
| X4S-2 phase E (180 ms) | Its receipt feeds the frozen c\* rule (§1.3) once, before the freeze | Anything else, including moving a margin, n or the sequence |
| X4S-2 phase F (guard at 120 ms) | Guard planning at 0.6 | Same |
| X4S / X4S-2 code (`sdefault.py`, the `run.py` charge, `anchor_x.py`) | Reference implementation for reviewed ports | Running as confirmatory bytes |
| X4S / X4S-2 seeds and games | — | Reuse (the new bank is audited disjoint) |
| K-anytime, S1, R3 r1(b) | Context and disclosure | Evidence |

All exploration remains **NEVER ADOPTABLE**. The confirmatory evidence is only this PREREG's fresh-seed games, read
through §5.

## 7. Run order

1. Conformance check of r2 against REVIEW-r1, run by a reviewer independent of the author.
2. Coordinator decisions on Q1–Q13.
3. The coordinator applies the c\* rule to the phase E receipt.
4. Author and review the runner deltas, reducer, verifier (a different author), SD1 manifest, END scripts and the
   `measure_tiers.py` K4S addendum.
5. Seed audit and qualification on the named hosts.
6. **Freeze:** PREREG, plan, SD1 manifest with the supersession text, source manifest, seed audit and c\* record.
   Secret-scan, commit, push.
7. Excluded smoke.
8. Sealed reporting, once the hosts are clear (§4.2).
9. END reference.
10. PC1–PC4, the verifier, and the TIERS barrier condition; then the release receipt.
11. Open outcomes and apply §1.2.
12. The Mac measurement, whenever Sam authorises it. Apply §1.4–1.5 against the TIERS selection. The result is
    PROVISIONAL until formal E4/T9.

## 8. Open questions for the coordinator (none blocks; the defaults are applied above)

| # | Question | Default |
|---|---|---|
| Q1 | Inference charge: an extra 1/c on the poll, or budget equivalence only? | **The extra 1/c on every arm's poll.** It covers r_inf ≥ c², at the cost of A(0.8) power if the charge's cost is real. |
| Q2 | Gate threshold c\*; S-lite? | **c\* = 0.9,** unless phase E's d180 has a lower CI bound > 0, then c\* = 0.8. **No S-lite.** |
| Q3 | Release gated on the K4S Mac summary? | **No.** It is gated on the TIERS summary or TIERS release (§4.5 item 6). A post-release K4S Mac session needs an independent classification review. |
| Q4 | A second opponent? | **None.** The guard decks cover transfer; disclosed. |
| Q5 | K4S Mac cell inside the TIERS E4-v3 session, or a separate session? | **The same session,** via a reviewed addendum, if it has not yet run. |
| Q6 | Replace a TIERS K4 pick at 0.8–0.9×? | **Yes,** when c_e ∈ {0.9 (A with veto passing), 0.8 (A or B)}. |
| Q7 | Hosts and timing | Any ≥ 2 of {01, 03, 04, 08} that are clear of T1 (including END) and of perception transports, with written retirement declarations. 04 not before 2026-10-12T12Z. |
| Q8 | SD1: same bytes or a refit? | **Same bytes,** with an explicit role-scoped supersession (§2.1). |
| Q9 | Size | **3,000 / 900** (A(0.8) power 0.86 vs 0.71 at 2,400 / 600). |
| Q10 | Level B deployable? | **Yes:** to replace TIERS K4 at c_e = 0.8, or where TIERS selects F0; always labelled. |
| Q11 | One root (TIERS D2)? | **Yes.** Activation needs the same L2-v4 one-root amendment. |
| Q12 | May K4S replace a TIERS **S or K2** selection? | **No (TIERS stands).** Alternative: level-A K4S may replace S/K2, on the untested argument that A means within 5 pp of K4@1.0. |
| Q13 | Position of B(0.6) in the sequence | **H3** (before the A-levels). Moving it to H5 (r1's order) changes cumulative power as shown below. |

Q13 trade-off, cumulative power at the central (pessimistic) planning values:

| Claim | B(0.6) at H3 (default) | B(0.6) at H5 (r1 order) |
|---|---|---|
| B(0.6) | .96 (.67) | .86 (.24) |
| A(0.9) | .94 (.52) | .97 (.69) |
| A(0.8) | .86 (.27) | .89 (≈.35; r1 printed .33 with SUP(0.8) double-counted) |
