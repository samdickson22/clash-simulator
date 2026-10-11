# PREREG-K4S (DRAFT r1, not frozen): speed-gated K4 + student-default Mac tier

Draft r1, 2026-10-11T09:05Z, design worker (Opus, 127x05) for coordinator `0523ae6f`
(task `clasher-prereg-k4s-draft-20261011-r1`). This is design only: no game, compute job or Mac access was run, and
nothing is frozen. Freezing is the coordinator's decision. This study is **separate from, and runs after,**
PREREG-SEARCH-TIERS (r3 `ef0db97a`, freeze record `47aba25e`/`cc6410b2`, Amendment 1 `a149a474`) and the sealed T1
run. It edits no TIERS or T1 file. Paths are relative to `reports/`.

## 0. Summary

- **Question.** Plain 4-thread anytime W (K4) falls off a cliff on slower cores: its loss vs v1 was 18.5 / 27.8 /
  47.3 / 89.0% at 200 / 160 / 140 / 120 ms in X4S. It does so because of the WAIT spiral. Does K4 with the frozen
  R3a student as the cutoff default ("K4S") give a Mac tier that keeps fleet-K4 strength at 0.8–0.9× speed, and a
  usable rescue tier at 0.6–0.7×? TIERS has nothing feasible below 0.8×.
- **Tier.** The tier is **speed-gated**. With the default gate, the student default is ON iff the Mac's measured
  5-core speed ratio for this tier is below 1.0 (§1.3). At or above 1.0 the tier is plain K4, which TIERS already
  covers.
- **Design.**
  - Eight arm-cells on every block: K4 and K4S at 1.0 / 0.9 / 0.8×, plus K4S at 0.7 and 0.6×. Plain K4 at 0.7 and
    0.6× runs on a 600 + 300-seed subsample.
  - Speed is emulated by budget (200 / 180 / 160 / 140 / 120 ms), and the search seat's network poll is
    additionally charged at **1/s inside the timer**.
  - Opponent: the plain v1 policy.
  - Populations: **3,000 primary paired seeds** (the X4S five decks) and **900 guard seeds** (L2-v4 own decks against
    the three held-out human opponent decks), all fresh.
- **Decision.** A fixed-sequence test of seven hypotheses at one-sided α = 0.025 (§1.2) admits each speed cell at
  level **A** (non-inferior to fleet-speed K4 within 5 pp) or level **B** (within 10 pp, and superior to plain K4 at
  the same speed). A Mac runs the configuration of the highest admitted cell at or below its own measured cell (§1.5).
- **Expected outcome (planning, not a claim).** Probability of passing, at central planning values (pessimistic in
  parentheses):

  | Claim | Probability |
  |---|---|
  | B at 0.8 and 0.7 | ≈1.00 (0.91) |
  | A at 0.9 | 0.97 (0.69) |
  | A at 0.8 | 0.89 (0.33) |
  | B at 0.6 | 0.86 (0.24) |
  | A at 0.7 | ~0.13 |

  The most likely result is: full K4 parity down to 0.8×, and a "degraded but rescued" tier at 0.7–0.6×.
- **Cost.**
  - 33,000 games ≈ 360 five-core slot-hours, i.e. ≈1,800 reserved physical-core-hours (≈460 CPU-h actually used).
  - Wall time: ≈11 h on three hosts at 11 slots each; ≈16 h on two.
  - Plus an END fleet reference of ≈2–3 h, and one Mac measurement (§1.4) that can share the TIERS E4-v3 session.
- **Earliest start.** After T1 reporting and T1's END references, and after perception A2's 03/08 transports are
  retired (§4.2). Realistically 2026-10-12.

## 1. Hypotheses and decision rule

### 1.1 Notation

- **Cells.** c ∈ {1.0, 0.9, 0.8, 0.7, 0.6} with budget b(c) = 200c ms (200/180/160/140/120), an 8 ms return reserve,
  and the search seat's poll charged at 1/c (§2.4).
- **Loss.** L(X@c) is the opponent-win rate of arm X in cell c. Draws are non-losses and are reported separately.
  Every contrast is paired on seed.
- **Arms.**
  - **K4** is the frozen T1 K4 arm (§2.2).
  - **K4S** is K4 plus the SD1 student default (§2.3).
  - **D(c)** is the configuration deployed at cell c. With the default gate, D(1.0) = K4 and D(c) = K4S for c ≤ 0.9.
- **Primary contrasts.**
  - Δ_ref(c) = L(D(c)@c) − L(K4@1.0): against fleet-speed K4 in the same study.
  - Δ_same(c) = L(K4S@c) − L(K4@c): against plain K4 at the same speed.
  - Superscript G marks the guard population.

### 1.2 Hypotheses and fixed testing sequence (primary FWER ≤ 0.025, strong control)

Every bound below is from the two-sided **95%** paired interval, i.e. one-sided 0.025.

**Level A at cell c**, an intersection–union test (all parts must hold):
1. upper Δ_ref(c) ≤ **+5 pp**;
2. for c ≤ 0.8, upper Δ_same(c) < 0;
3. for c = 0.9, the gate check: upper [L(K4S@0.9) − L(K4@0.9)] ≤ +5 pp;
4. on the guard, upper Δ_ref^G(c) ≤ **+10 pp**.

**Level B at cell c**, also intersection–union:
1. upper Δ_ref(c) ≤ **+10 pp**;
2. upper Δ_same(c) < 0;
3. on the guard, upper Δ_ref^G(c) ≤ **+15 pp**.

Hypotheses are tested **in this fixed order**, and testing stops at the first failure. Every hypothesis after a
failure is "not tested", which is equivalent to not admitted:

| Step | Hypothesis | Why it sits here |
|---|---|---|
| H1 | B(0.8) | Core rescue claim. K4@0.8 lost +9.3 pp vs K4@1.0 in X4S. Highest prior. |
| H2 | B(0.7) | The tier's unique value: TIERS has no feasible tier below 0.8×. |
| H3 | A(0.9) | Full parity near the gate. It only matters if A(0.8) would fail, so it must precede A(0.8). |
| H4 | A(0.8) | Headline: full fleet-K4 parity at 0.8×. |
| H5 | B(0.6) | Rescue at the slowest plausible all-E-core Mac. |
| H6 | A(0.7) | Upgrade. Planned power is about 0.15, so it is included only for completeness. |
| H7 | A(0.6) | Upgrade. Expected to fail. |

Level A and level B at the same cell are nested, because A's parts imply B's. A cell's admitted level is the
strongest level whose hypothesis was tested and rejected. This is a pure fixed-sequence procedure, so no α is split
and the FWER over H1–H7 is ≤ 0.025. Each hypothesis is an intersection–union of its parts, so its parts need no
further adjustment.

**Why the margins.**
- **5 pp (level A)** is the TIERS NI margin and S1's margin, half the TIERS V1 margin. "Level A" means "as good as
  fleet K4 for deployment purposes", the same standard TIERS applies when choosing between tiers.
- **10 pp (level B)** equals the TIERS V1 and G2 margins. L(K4@1.0) is about 18–24%, so +10 pp puts a level-B tier
  at or below the observed K2 and S range (25–32%), while it still beats the collapsing plain K4 at the same speed.
- **Guard margins are primary + 5 pp,** because n = 900 is less precise. TIERS uses 10 pp on 600.
- **Draws** count as non-losses, as in TIERS.

### 1.3 The gate: where S-default switches on

- **Static per-session switch** (TIERS D4: no in-match switching). S-default is ON iff the Mac's *evidence cell*
  c_e (§1.5) is below the threshold cell. Equivalently, it is ON iff the measured r_K4S < r*.
- **Default r* = 1.0**, so S is on in every cell below 1.0. The reasons:
  1. The gate risk is asymmetric. In exploration, S's cost at full speed was small and not significant (+2.2 pp
     [−0.3, 4.7] on X; +0.4 [−2.4, 3.1] on G). Missing S when it is needed costs +9 pp at 0.8× and +29 pp at 0.7×.
  2. Live speed drifts with thermal state and perception bursts, so the gate should fail safe.
- **Prespecified rule from X4S-2 phase E**, applied once by the coordinator before the freeze and recorded in the
  freeze record:
  - Let d180 = L(K4S-180) − L(K4-180) on the X population, with phase E's paired 95% CI.
  - **If the lower bound of d180 > 0** (S significantly hurts at 0.9×), set **r* = 0.9**. Then D(0.9) = K4, H3
    becomes "NI5(K4@0.9 vs K4@1.0) ∧ guard NI10", and it moves to the end of the sequence (after H7), because it is
    no longer a claim about the S tier.
  - **Otherwise r* = 1.0**, including when phase E is not complete at the freeze.
  - No other exploration outcome may move r*.
- **No S-lite.** The X4S-2 "S-lite" rule (phase C) is not adopted. Under the gate, S is off at full speed, which is
  the only place S-lite was meant to help. See Q2 (§8).

### 1.4 Threshold measurement on the Mac (E4-style; needs Sam's authorisation)

**Work unit and corpus.**
- The work unit is TIERS §6.1's complete no-deadline decision: belief, candidates, root, exact screen8 scoring with 4
  workers, reduction, **plus the SD1 forward and top-8 ranking**.
- It runs on the **frozen T1 K4 speed corpus** (300 states, SHA-pinned in T1's corpus inventory `81f2483e`), so no
  new corpus seeds are needed.
- Exactness is checked against Linux receipts using TIERS §7.2 (ARM64-NEAR-EXACT) and §7.3 (student agreement
  ≥ 99.5%).

**Statistics measured under replay perception load,** with the same priority and configuration as live:
- **r_K4S** = min(median per-state ratio, Σ-ratio, p90 ratio), exactly as in TIERS §6.2, with p10_K4S as the 10th
  percentile of per-state ratios.
- **r_inf** = (fleet loaded SD1 forward p50) / (Mac loaded forward p50) on the chosen backend (TIERS §7.3: CPU by
  default); and the forward p99.
- **Deadline-mode check:** the K4S corpus run at **200 ms** on the Mac, giving the cutoff rate and the
  no-complete-play rate.

**Cell mapping.** c_M is the largest c ∈ {1.0, 0.9, 0.8, 0.7, 0.6} that passes all of the following:
1. r_K4S ≥ c and p10_K4S ≥ c − 0.10;
2. **inference coverage: r_inf ≥ c²**. The arms charge the poll at 1/c inside a budget already scaled by c, so they
   emulate inference down to c² × fleet speed (derivation in §2.4);
3. forward p99 ≤ 20 ms;
4. perception keeps ≥ 18 processed FPS and ≥ 95% processed while K4S runs;
5. GC/poll gate 4 of TIERS §6.3;
6. **deadline equivalence:** the Mac's 200 ms cutoff and no-complete-play rates are each ≤ the fleet END
   deadline-mode rate for K4S at b(c) (with the 1/c charge) **+ 2 pp**. If this fails, move down one cell and
   re-check.

r ≥ 1.0 gets no extra credit. If no cell passes, the tier is Mac-infeasible.

**Session rules.**
- **Integrity:** the TIERS §6.5 measurement-integrity rules apply unchanged. There is one valid session; repeats are
  allowed only for pre-listed technical failures, classified mechanically; and the minimum r and worst gate inputs
  across valid sessions are used.
- **Provisional status:** a replay-only (emulator-off) measurement is **PROVISIONAL** until formal E4/T9 re-measures
  every input, as in TIERS §6.5 item 5.
- **Implementation:** a K4S configuration is added to E4's `measure_tiers.py` by a reviewed addendum. By default the
  same session as TIERS is used (Q5).

### 1.5 Deployment rule and interaction with TIERS

The **admitted set** 𝒜 is the set of cells with level A or B after §1.2. Given the Mac cell c_M, the evidence cell is
**c_e = max{c ∈ 𝒜 ∪ {1.0} : c ≤ c_M}**. This is the TIERS convention: a faster Mac uses the evidence of the cell
below it, which relies on loss being non-increasing in speed.

| Case | Rule |
|---|---|
| c_M = 1.0 | K4S plays no role; the TIERS selection stands. |
| c_M ∈ {0.9, 0.8} and TIERS selected K4 | Deploy **D(c_e)**, i.e. K4 with the S-default on, provided c_e ∈ 𝒜. Otherwise TIERS stands. |
| c_M ∈ {0.9, 0.8} and TIERS selected a cheaper tier | TIERS stands. That tier was already shown NI to K4. |
| c_M ≤ 0.7, where TIERS has no feasible tier | Select K4S at c_e if c_e ∈ 𝒜, labelled with its level ("full" for A, "degraded" for B). Otherwise F0. |
| TIERS selection not yet available | K4S is held. It never pre-empts TIERS. |

General rules:
- **The live deadline stays 200 ms** (TIERS D3). The cell only says which evidence applies.
- Activation also needs the TIERS D2 one-root L2-v4 amendment, formal E4/T9 and coordinator review. **Nothing here
  authorises live play.**

## 2. Artifacts

### 2.1 SD1: R3a re-frozen as a new artifact

- **Name.** `SD1` (full ID `clasher-sd1-k4s-default-20261011`): "student default 1". These are the **exact R3a
  bytes** under a new artifact identity, with no refit (Q8).

| Component | SHA-256 |
|---|---|
| EMA checkpoint | `37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85` |
| Calibration | `e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414` |

- **Threshold** = 0.5005528330802917.
- **Manifest.** `SD1-MANIFEST.json` binds the checkpoint, the calibration, the threshold, the SHA of every inference
  source file (cached policy, `proposals.py` ranking, `model_packet`), the Torch version and the inference mode (CPU
  float32, 1 Torch thread). Its own SHA-256 is **the SD1 hash**, computed at the freeze. The runner refuses to start
  on any mismatch.
- **Training recipe**, fixed for disclosure and for any future refit, from `imitation/exit-r3/PLAN.md`:
  - **Initialisation and data:**
    - initialised from released v1 step 22552 EMA at width 192 (`d77005d5…`);
    - 2,500 AdamW steps × 8,192 root rows sampled uniformly with replacement, train seed 2026101013;
    - R1 corpus `1c8e1f49…` (6,009,681 eligible roots), plus five G shards (pause manifest `4e8faf7e…`, 212,542
      roots), 6,222,223 in total;
    - only rows with teacher_root true and wait_kind 0.
  - **Objective:** listwise softmax over valid completed candidates at T = 0.003; play weight 1; value weight 0.
  - **Optimiser:**
    - learning rate 3e-4, weight decay 0.05, warm-up 2,000, cosine schedule over 2,500 steps;
    - gradient clip 1, EMA 0.999, bf16 autocast;
    - final EMA only.
  - **Gate calibration:** nearest 34.6% deterministic play prevalence on the R1 heldout64 slice (`0ecce0f0…`),
    with no action labels.
  - **Replication:** R3d, a new-seed refit of this recipe, differed by −0.036 pp in play recall.
- **Status.**
  - R3a **remains KILLED** under R3 Stage 1 and NEVER-ADOPTABLE under R3. R3 files are not edited.
  - Claims here attach **only to the SD1 bytes in the K4S cutoff-default role**, never to the R3 recipe and never to
    tier S.
  - TIERS §2.1's supersession, which covers the same bytes in tier S, is separate and unaffected.
  - An additive pointer goes into `exit-r3/`, as for TIERS C1.
- **Disclosures** (repeated in the final report):
  - TIERS §2.2's full R3 chain;
  - R3a trained on all eight R1 deck slots, which include the L2 Hog 2.6 and X-Bow decks, against a mix that
    includes v1. So the primary population is in distribution for SD1, which favours K4S. The guard removes only
    the opponent-deck overlap.
  - The threshold was calibrated on the heldout64 slice. That slice is not reopened here; only the frozen value is
    used.

### 2.2 K4: frozen configuration

K4 is exactly T1's K4 arm, from the T1 reporting runtime (freeze `ef4c073a`, OP-7 manifest; the bytes are pinned by
SHA at the freeze):
- K2's WAIT-first anytime collector with **threads = 4** scorer workers plus the main thread, on **5 physical
  cores** with no SMT siblings;
- **coarse_horizon = 160**, complete-score horizon 160, three rollout styles, top-8 refinement;
- one sampled public belief root per decision; exact resumable, cancellable belief;
- search interval 10 ticks, policy interval 5, d = 27, capacity 1;
- native `44874fd6…`;
- fallback is the v1 policy poll, used only when no complete score exists;
- in-decision GC deferral, metered.

K4@1.0 is byte-identical in behaviour to T1's K4@200. The only runtime delta is the budget parameter and the poll
charge at c < 1 (§2.4).

### 2.3 K4S: the S-default rule (frozen)

K4S is K4 with three changes on the **search seat only**. The opponent is untouched.
1. **Seat poll.** The seat's policy poll is SD1 instead of v1. This is one cached forward per poll, giving the
   calibrated deterministic default: WAIT if P(play) < threshold or no legal play exists; otherwise the
   highest-ranked legal play.
2. **Coarse order.** SD1's top-8 ranked legal plays are scored first in the coarse scan. This is *scheduling only*:
   the candidate set is unchanged, with no augmentation and no refinement proposals.
3. **Cutoff default.**
   - If preparation (belief update, sample or pre-scoring) cuts off, return the SD1 default.
   - If the scoring deadline is hit and **no legal play has a complete score**, and the SD1 default is a play, return
     that play and set selected_wait_ticks = 0. An SD1 WAIT keeps the frozen choice.
   - Whenever any play has a complete score, the frozen best-complete-score rule stands.

With no deadline, K4S ≡ K4. Qualification requires identical actions, scores and command hashes (§4.1). The
reference implementation is `explore/x4s2/sdefault.py` (full rule) together with the K4S branch of its `run.py`. It
is **ported into the T1 runner and reviewed**, not imported (§6).

### 2.4 Honest inference charge

- **Budget equivalence already charges inference.** Under budget equivalence, all work inside the timer, inference
  included, already runs at 1/c relative to the budget. X4S-2 PLAN showed W ≤ 192c fleet-ms either way, up to an
  ≤ 4 ms reserve difference.
- **The additional charge.** As the assignment requires, each arm additionally sleeps (1/c − 1) × the measured wall
  time of the search seat's **network poll** in every search decision, **inside the timer**. This is X4S-2's
  "inference" mode, generalised to every arm:
  - K4S's SD1 poll and K4's own v1 poll are both charged, so SUP is fair. X4S-2 left K4's v1 poll uncharged.
  - At c = 1 there is no charge.
  - The sleep idles a dedicated core, so it shifts only the deadline.
- **What it covers.** The emulated constraint is W_search/c + poll/c² ≤ 192 real ms. On a Mac at r_K4S = c, the real
  constraint is W_search/c + poll/r_inf ≤ 192. The arms therefore cover any Mac with **r_inf ≥ c²**, which is gate 2
  of §1.4.
- **Interpretation.** This is conservative for a uniform slowdown, and is disclosed as such.
- **Not scaled:** the opponent, which has no deadline; and the uncharged polls at off-search ticks.

## 3. Design

### 3.1 Arms and blocks

| Arm-cell | Budget | Every block | Role |
|---|---:|---|---|
| K4@1.0 | 200 | yes | Reference for every Δ_ref; D(1.0) |
| K4S@1.0 | 200 | yes | Secondary F1: the full-speed cost of S (fail-safe "always on") |
| K4@0.9 | 180 | yes | Gate check in A(0.9); D(0.9) if r* = 0.9 |
| K4S@0.9 | 180 | yes | A(0.9) |
| K4@0.8 | 160 | yes | SUP comparator for B(0.8) and A(0.8) |
| K4S@0.8 | 160 | yes | B(0.8), A(0.8) |
| K4S@0.7 | 140 | yes | B(0.7), A(0.7) |
| K4S@0.6 | 120 | yes | B(0.6), A(0.6) |
| K4@0.7, K4@0.6 | 140, 120 | primary i < 600; guard i < 300 | SUP comparators. Expected effects are −24 and −60 pp, so power ≈ 1 at n = 600. |

- A **block** is one seed's 8 or 10 arm-cells, run back-to-back on one slot.
- The arm order is rotated cyclically by seed index (rotation i mod 8 over the eight core arms; the two subsample
  arms are inserted after positions 3 and 6).
- **One belief root** throughout (TIERS D2).

### 3.2 Opponent

The opponent is the sealed plain **v1 policy at T = 1 with no search**, the same as T1, X4S and S1. **There is no
second opponent** (Q4):
- A v1+W opponent would roughly double the cost, and TIERS D5 already declares it out of scope.
- A temperature-shifted v1 is no less in-distribution for SD1, which trained against a mix that includes v1.

Opponent-side transfer is instead checked by the guard decks. This limitation is disclosed.

### 3.3 Populations and decks

- **Primary.** The K2/S1/X4S harness's five archetype decks (bridge_wincon, siege, beatdown, bait, chip): 25
  matchups × 2 seats = 50 cells; seed index i goes to cell i mod 50. That gives **3,000 seeds**, 60 per cell.
- **Guard.**
  - Own decks: the three L2-v4 decks (Hog 2.6, X-Bow cycle, Royal Hogs spawners).
  - Opponent decks: the three held-out human decks selected by TIERS' rule (Hog EQ, Goblinstein Royal Hogs,
    ArcherQueen Royal Delivery), taken **byte-identical from T1's `guard-decks.json`** (selector `21125180…`;
    catalogue `80de4afb…`).
  - 18 cells; i goes to cell i mod 18. That gives **900 seeds**, 50 per cell.
- **Heldout data.** These are deck lists already in use; no heldout game data is opened.
- **No descriptive in-distribution cells.** T1 already plays L2-vs-L2 cells.

### 3.4 Seeds (fresh bank; audit before the freeze)

- **Bank:** 2^52 + [6.18e9, 6.28e9). As of origin/main `bc2e4e5b`, the tracked tree has no seed literal between
  4503605500000000 and 4503606999999999 (2^52 + [5.87e9, 7.37e9)).

| Use | Range |
|---|---|
| Primary reporting | `4503605807370496+[0,3000)` |
| Primary replacement | `4503605807370496+[3000,3600)` |
| Guard reporting | `4503605817370496+[0,900)` |
| Guard replacement | `4503605817370496+[900,1080)` |
| Excluded smoke | `4503605827370496+[0,8)` |
| Qualification | `4503605837370496+[0,8)` |
| Reserve (unused unless amended) | `4503605847370496+[0,64)` |

- **Audit.** The audit (T1 `audit_seeds.py`, extended) must show these ranges disjoint, at helper offsets {0, 13,
  100000–100003, 271828–271829}, from every declared prior range: K, K-v2, K2, S1 (both banks), R3, R1/G, X, X4S,
  X4S-2 (including phases E and F), T1 (all banks), DAgger, noise-ceiling and L2-v4. It must also show no repo seed
  literal inside the window.
- **Seats** alternate through the cell assignment. **Replacement** follows T1 §3.2 mechanics: the k-th lost block in
  cell c is replaced by seed 3000 + 50k + c (primary) or 900 + 18k + c (guard), stratified by the *lost* block's
  cell, in blind loss order.
- **Caps:** 10% per population (300 primary, 90 guard), with bank-row limits of k ≤ 11 (primary) and k ≤ 9 (guard).
  Exceeding a cap means stop and amend before any outcome opens.

### 3.5 Power and sample size

- **Planning σ** (per-pair SD of loss differences, from X4S/X4S-2 CIs, σ = half-width/1.96·√n):

  | Contrast | Observed σ | Planning σ |
  |---|---|---|
  | NI, within-run (X4S) | 0.43 | **0.47** |
  | NI, cross-run (X4S-2 K4Sh) | 0.48–0.52 | 0.47 |
  | NI at 0.6 | 0.51 | 0.51 |
  | SUP | 0.47–0.56 | 0.50 |
  | Guard | 0.56–0.62 | **0.56** |
  | K4S@1.0 − K4@1.0 | 0.31 | — |

- **Planning effects for Δ_ref:**

  | Cell | Central | Pessimistic | Basis |
  |---|---:|---:|---|
  | 0.9 | +1.5 | +2.5 | interpolated |
  | 0.8 | +2.0 | +3.2 | X4S K4S-160 −0.3; X4S-2 K4Sh-160 +3.2 |
  | 0.7 | +4.2 | +4.7 | K4S-140 +3.7; K4Sh-140 +4.7 |
  | 0.6 | +6.5 | +7.5 | K4S-120 +7.5; K4Sh-120 +5.5 |

  - SUP at 0.8: −6.2 central, −3.0 pessimistic.
  - Guard Δ_ref^G: +2 to +3.5 at 0.9–0.7, and +5 (+8) at 0.6. Phase F is pending.
  - These effects were selected after the fact, so they are likely optimistic. The pessimistic column exists for that
    reason.

- **Marginal power of NI at 5 pp** (one-sided 0.025, σ = 0.47), by true Δ:

  | n (primary) | SE pp | 0 | +1 | +2 | +3 | +4 | +5 |
  |---:|---:|---:|---:|---:|---:|---:|---:|
  | 2,400 | 0.96 | 1.00 | 1.00 | .88 | .55 | .18 | .02 |
  | **3,000** | **0.86** | 1.00 | 1.00 | **.94** | .64 | .21 | .025 |
  | 3,600 | 0.78 | 1.00 | 1.00 | .97 | .72 | .25 | .025 |

  At 10 pp, every column shifts by 5 pp. For example, at n = 3,000 NI10 has power 0.94 at a true +7.

- **Guard** (σ = 0.56, n = 900, SE 1.87): NI10 has power 0.99 / 0.76 at +2 / +5; NI15 has power 1.00 / 0.96 at
  +5 / +8.

- **Sequential power** (product of marginals, which is conservative because the components are positively
  correlated), n = 3,000 / 900:

  | Step | Central: marginal / cumulative | Pessimistic: marginal / cumulative |
  |---|---|---|
  | H1 B(0.8) | 1.00 / 1.00 | .91 / .91 |
  | H2 B(0.7) | 1.00 / 1.00 | 1.00 / .91 |
  | H3 A(0.9) | .97 / .97 | .76 / .69 |
  | H4 A(0.8) | .92 / .89 | .47 / .33 |
  | H5 B(0.6) | .96 / .86 | .74 / .24 |
  | H6 A(0.7) | .15 / .13 | .05 / .01 |
  | H7 A(0.6) | .00 / .00 | .00 / .00 |

- **Choice: n = 3,000 primary and 900 guard.** For comparison, n = 2,400 / 600 gives A(0.8) cumulative power 0.71
  central and 0.15 pessimistic. Going to 3,600 adds only ≈0.04 at about 20% more cost.
- **Type I error.** The FWER for any falsely admitted cell-level is ≤ 0.025. In particular, a K4S that is truly
  +5 pp worse is admitted at level A with probability ≤ 0.025.
- **No interim looks,** no optional stopping and no re-estimation.

### 3.6 Per-game record (sealed game JSON; C17-compatible)

| Group | Fields |
|---|---|
| Identity | study `PREREG-K4S`, freeze SHA, arm, cell, budget_ms, reserve_ms, inference_scale (= 1/c), scale_mode `poll`, kernel, threads, coarse_horizon, default_source (`v1`/`SD1`), s_default_rule (`full`/none), SD1 manifest SHA, checkpoint/calibration SHAs, threshold, opponent SHA, native SHA, runtime manifest SHA |
| Placement | population, seed, seed index, cell index (matchup, seat), rotation, block ID, replacement k, host, slot, core mask, nice, attempt directory |
| Outcome (sealed) | winner, loss, draw, crowns, ticks, command-sequence SHA |
| Per decision | tick, wall ms, CPU ms, deadline hit, preparation_cutoff kind, completed/coarse_scored/coarse_complete/plays, unpruned_candidate_count, own elixir, frozen_action, student_default flag, SD1 default action, chosen action, fallback used, selected_wait_ticks, poll_seconds, scale_sleep_seconds, prep_seconds, positive overrun ms, charged extra ticks |
| GC | count and pauses, deferred-in-decision flag |

- **Per block:** the T1 census and interference meters (OP-1 DBus, OP-4/6 SSH, OP-7 apt, idle services), proof
  SHAs and the hub acknowledgement.
- **Stdout** carries identity and terminal health only (T1 C1).

## 4. Execution and validity

### 4.1 Runner: reuse T1, review the deltas, re-qualify

The runner is T1's frozen reporting runtime plus reviewed deltas only:
1. a cell table with 180/140/120 ms budgets;
2. the poll-charge hook (§2.4), ported from X4S-2 `test_charge.py` semantics;
3. the K4S kernel (§2.3);
4. a 10-arm schedule and the subsample rule;
5. the new populations and seeds;
6. the reducer for §5, including the fixed sequence;
7. the per-decision fields;
8. the END reference cells.

Each delta gets an independent diff review whose reviewer is not the author. **Qualification on every named host,
before the freeze:**
- T1's full batteries: 125-state 1/4-worker exactness, belief ON/OFF (125 histories, 250 variants), injected-clock,
  lateness and GC;
- **K4 ≡ K4S with no deadline:** 125/125 frozen action and score equality, and identical command hashes on two
  qualification seeds;
- injected-clock S-default cases: pre-scan cutoff gives the SD1 play; an SD1 WAIT keeps the frozen choice; a
  completed play keeps the frozen rule; zero budget gives the SD1 default;
- charge tests: the sleep share equals (1/c − 1)/(1/c) ± 0.02 on every exit path in smoke;
- the SD1 manifest check;
- guard-card support.

Then an **excluded smoke** on the smoke range, all hosts, ≥ 8 blocks per host. Smoke reads no outcomes.

### 4.2 Hosts, exclusivity and the OP lessons

- **Candidates:** {127x01, 03, 04, 08}, named at the freeze; ≥ 2 required. 11 five-core slots per host on physical
  cores 0–54 (8 if a console user is present at launch); supervisor on 61, copier on 62, census on 63; scientific
  work at nice 10 / SCHED_OTHER; no SMT. 05 is command only, 06 is unreachable, 02 and 07 are down, and roader hosts
  are never used.
- **Conflicts (as of 2026-10-11T08:46Z):**
  - T1 is reporting on 01, with 08 held (1,764/3,072 durable), then needs its END clean window on 01/08.
  - Perception A2 stage 2 runs on 04 (allocated until 2026-10-12T12Z), with ssh transports into 03/08 until about
    13–14Z.
  - X4S-2 has 03 until 13:30Z and 08 until 12:30Z.
  - **No K4S reporting may overlap T1 reporting or T1 END references on the same host.**
- **Lessons inherited from T1's OP-1..OP-7** (guard code unchanged, at the final reviewed OP-7 bytes):
  1. **Perception transports** (OP-2/4/5/6): unprovable sshd generations from 04 stopped T1 on 03 and on 08
     repeatedly. **Prefer hosts with no perception transport for the whole window.** The coordinator records a
     *transport-retirement declaration* per host before admission. Only if a transport must stay does the OP-6
     LAN-SSH budget apply, with exact source seeds. Unknown-source sessions always stop.
  2. **apt** (OP-7): `unattended-upgrade --download-only` running as root stopped T1 01 at 21:03Z. The OP-7 apt
     budget and static `_apt` witness are inherited. We have no root, so we cannot disable the timer; a stop is an
     availability cost, not a validity risk.
  3. **System DBus pin** (OP-1), **owned-supervisor membership** (OP-3) and **one copier phase at a time**.
  4. **Console users** stop the host; **foreign compute** stops the host; memory floor 24 GiB.
  5. **No cross-host pollers or mirrors** on timing hosts; pause them by stop files before admission (S1 attempt 1).
     Health comes from one bounded hub connection per check.
- **OP-6-style flags.** Interference flags are recorded per block and disclosed. The primary analysis includes
  flagged blocks, and a sensitivity analysis excludes them (§5.3).

### 4.3 Timing and honest lateness (inherited unchanged)

- The full timer starts before observation.
- Every positive overrun is charged ceil(overrun × 20) ticks to the command due time, own availability and timed
  waits.
- Partial and late scores never count.
- The scoring cutoff is the budget minus 8 ms.
- GC is deferred only inside decisions, and metered.
- The poll-charge sleep is inside the timer, so it can itself cause overruns, which are charged.
- 1 Hz per-core MHz is recorded during reporting and during END.

### 4.4 Lost blocks

T1 §3.2 mechanics apply:
- a block counts only when all its arm-cells are complete **and** it is hash-verified on hub 01, with a 30-minute
  copy-lag stop;
- started-but-incomplete blocks are lost and replaced (§3.4); never-started blocks are re-dispatched with unchanged
  seeds;
- losses are classified mechanically from receipts;
- if fewer than two named hosts remain, stop and amend. No host may be added without an amendment plus its own
  qualification and END reference.

### 4.5 Seal, END reference and release barrier

- **Sealed.** No outcome field is read before release. The reducer fails closed before it opens any game bytes.
- **END reference.** After the committed reporting-completion receipt, on **every host with counted blocks**,
  reference slot 0 measures the following under the reporting load profile (all other slots running the corpus
  loop), with 1 Hz MHz:
  - (a) no-deadline K4S and K4 on the T1 K4 corpus, 3 repeats;
  - (b) deadline mode at all five cells with the 1/c charge, 3 repeats, producing the per-state cutoff,
    no-complete-play and fallback rates.

  Each host's ratio to the pool must lie in **[0.95, 1.05] (inclusive)**; otherwise the pool **fails closed** (T1
  Amendment 1 A1.1, with no host exclusion after counting). One mechanically classified repeat is allowed. MHz is
  compared only against full-occupancy reporting rows, and the signed ratio is disclosed (A1.2). Committed-posterior
  replay applies (A1.3).
- **Release requires all of the following committed:**
  1. the completion receipt;
  2. the pooled END reference and its independent re-check (T1 `check_reference.py` pattern);
  3. production checks **PC1–PC4** adapted from T1: all original attempt roots; reviewed E4 source inventory; one
     pinned interpreter; the interference-sensitivity sidecar over the final counted inventory and blind ledger;
  4. the **independent integer-count verifier**, whose author is not the reducer's author;
  5. the frozen K4S Mac measurement procedure (§1.4 scripts, the load-selection rule and the failure classifier).

  Release is **not** gated on the Mac *summary* (Q3, default). Cell-wise admission does not depend on the Mac, and
  the Mac mapping is frozen, mechanical and minimum-across-sessions, so knowledge of the outcomes cannot raise r.
  This is the deliberate difference from TIERS §6.6, made because TIERS had to choose among cells and here every
  cell is tested.
- **No automatic release.** The coordinator signs a release receipt that binds all of the SHAs above.

### 4.6 Compute and time

- **Games:** primary 3,000 × 8 + 600 × 2 = 25,200; guard 900 × 8 + 300 × 2 = 7,800; **33,000 in total.**
- **Throughput:** X4S/X4S-2 measured ≈ 92 games per five-core slot-hour (12 slots, nice 19). That gives ≈ 360
  slot-hours, ≈ 1,800 reserved physical-core-hours and ≈ 460 CPU-h actually used.
- **Wall time:** ≈ 8.2 h on 4 hosts (44 slots), **≈ 11 h on 3 hosts (33 slots)**, ≈ 16 h on 2. Plan for 12–17 h
  including copy and initialisation overhead.
- **Preparation and qualification:** ≈ 0.5 day of agent time plus ≈ 2 h of host time. **END:** ≈ 2–3 h.
- **Mac:** about +30–45 min if added to the TIERS E4-v3 session, or about 1.5 h as a standalone session.

## 5. Analysis

### 5.1 Statistics

- **Bootstrap:** paired-seed percentile bootstrap with **10,000 resamples**, `numpy.default_rng(2026101170)`,
  shared across all contrasts within a population. Resampling is stratified by cell: 50 primary cells and 18 guard
  cells.
- **Subsample contrasts** (K4@0.7, K4@0.6) resample only the subsample seeds, stratified the same way.
- **Precision:** exact rational percentile indices and integer loss counts (T1 reducer convention). Bounds are
  inclusive as written, except SUP, which is strict (< 0).
- **Rates:** cutoff, student-default, fallback, overrun and play rates are reported with per-game numerator and
  denominator resampling.

### 5.2 Multiplicity

- The fixed sequence H1–H7 (§1.2) gives strong FWER control at 0.025 over all admission claims.
- Intersection–union holds within each hypothesis.
- **No adjustment across the Mac cell.** The cell is chosen by a frozen physical measurement, and every cell's claim
  is already inside the controlled family.
- **Everything else is secondary or descriptive, unadjusted, and labelled as such.** It never changes admission.

### 5.3 Secondary and sensitivity analyses (prespecified; descriptive only)

1. **F1, the full-speed cost:** L(K4S@1.0) − L(K4@1.0) with its 95% CI, primary and guard. If the upper bound is
   ≤ +2.5 pp on both, the report notes that an "always on" gate (r* = ∞) is supported for a future amendment. It
   changes nothing here.
2. **Interference:** exclude blocks with any OP-6/OP-7 interference flag (sidecar ledger; separate RNG stream).
3. **Matchup-cluster bootstrap,** resampling the 25 matchups and 9 guard pairs, for every primary contrast.
4. **Per host** and **per seat** contrasts, plus a host × arm heterogeneity table.
5. **Uniform-charge read:** none is possible without arms. Disclose that the charge is conservative (§2.4).
6. **Mechanism by cell:** cutoff, student-default, coarse-complete-at-cutoff, play rate, candidate-set median and
   WAIT-spiral indicators.
7. **Latency:** latency and overrun tables, cut returns > budget + 8 ms, and GC tables in the K-v2/S1 format.
8. **Drift anchors** (unpaired, after T1 opens): K4@1.0 here vs T1 K4@200 and vs X4S K4-200.
9. **Draws** counted as half-losses.

### 5.4 What kills the tier, a cell or the study

- **Tier killed** (S-default leaves the Mac programme) if **H1 fails**: no cell ≤ 0.8 is admitted even at level B.
  Macs at 0.8–1.0 then rely on TIERS alone.
- **Cell not admitted** if its hypothesis fails or is not reached. A Mac in that cell maps down to the next admitted
  cell, or gets F0 or the TIERS selection (§1.5).
- **Mac-side kills:**
  - SD1 cross-platform agreement < 99.5%, or forward p99 > 20 ms, kills the tier on that Mac.
  - r_inf < c² or a deadline-equivalence failure lowers the cell, or makes the tier infeasible.
  - Any arm64 single-thread exactness failure (TIERS §7.2) kills every tier.
- **Validity suspension:** if L(K4@1.0, primary) lies outside **[10%, 30%]** (prior studies: 16–24%), selection is
  suspended pending an independent receipts-only code review (the TIERS §8 rule). A harness defect voids the study:
  new PREREG, new seeds.
- **Before reporting:** any qualification, exactness, pin, seed-audit, smoke or card-support failure means fix,
  re-qualify and use a new smoke range. The replacement cap means stop and amend.

## 6. What may be adopted from exploration (X4S, X4S-2): **nothing**

| Source | Allowed use | Not allowed |
|---|---|---|
| X4S RESULTS (600 seeds × 9 arms) | Planning effects and σ (§3.5) | Evidence, pooling, any gate input, citation as support |
| X4S-2 phases A–D (K4Sh, K4Sf, guard B/D) | Planning effects and σ; the shape of the charge (§2.4) | Same |
| X4S-2 phase E (180 ms) | Its *receipt* feeds only the frozen r* rule (§1.3), once, before the freeze | Any other use; it cannot move a margin, n or the sequence |
| X4S-2 phase F (guard at 120 ms) | Guard planning at 0.6 only | Same |
| X4S / X4S-2 code (`sdefault.py`, `run.py` charge, `anchor_x.py`) | Reference implementation for reviewed ports | Running as confirmatory bytes |
| X4S / X4S-2 seeds and games | — | Reuse. The new bank is audited disjoint. |
| K-anytime, S1, R3 r1(b) | Context and disclosures | Evidence |

All exploration remains **NEVER ADOPTABLE**. The confirmatory evidence is only the fresh-seed games of this PREREG,
read through §5.

## 7. Run order

1. Independent review of r1, then r2. **Coordinator decision on Q1–Q11**, and the coordinator applies the r* rule to
   the phase E receipt.
2. Author and review the runner deltas, reducer, verifier (different author), SD1 manifest, END scripts and the
   `measure_tiers.py` K4S addendum.
3. Seed audit and qualification on the named hosts.
4. **Freeze:** commit the PREREG, plan, SD1 manifest, source manifest, seed audit and r* record; secret-scan and
   push.
5. Excluded smoke.
6. Reporting, sealed, starting when the hosts are clear of T1 and perception (§4.2).
7. END reference.
8. PC1–PC4 and the verifier, then the release receipt.
9. Open outcomes and apply §1.2.
10. Mac measurement whenever Sam authorises it; apply §1.4–1.5. The result is PROVISIONAL until formal E4/T9.

Steps 6 and 10 are independent.

## 8. Open questions for the coordinator (none blocks the draft; defaults are applied above)

| # | Question | Default chosen |
|---|---|---|
| Q1 | Inference charge: the extra 1/c on the poll (conservative; the brief's "honest") or budget equivalence only? | **Extra 1/c on every arm's poll.** It costs power at 0.8 if the honest-scaled effect is real; it covers r_inf ≥ c². |
| Q2 | Gate threshold r*, and whether to use S-lite | **r* = 1.0**, unless phase E's lower CI for d180 > 0, then 0.9. **No S-lite.** |
| Q3 | Release gated on the Mac summary (as in TIERS) or decoupled? | **Decoupled**, provided the Mac procedure is frozen before release (§4.5). |
| Q4 | A second opponent? | **None.** Transfer is checked by the guard decks; disclosed. |
| Q5 | Mac: add a K4S cell to the TIERS E4-v3 session, or run a separate session? | **Add it to the same session** via a reviewed addendum, if that session has not yet run. |
| Q6 | Interaction with TIERS when TIERS picks K4 at 0.8 ≤ r < 1.0 | **K4S replaces plain K4.** Cheaper TIERS picks stand. Below 0.8, K4S fills TIERS' gap. |
| Q7 | Hosts and timing | Any ≥ 2 of {01, 03, 04, 08}, each clean of T1 (including END) and of perception transports, with written retirement declarations. 04 not before 2026-10-12T12Z. |
| Q8 | SD1: the same bytes, or a fresh-seed refit? | **The same bytes.** A refit invalidates the planning inputs and adds a GPU fit plus qualification. |
| Q9 | Size: 3,000 / 900 vs 2,400 / 600 | **3,000 / 900** (A(0.8) cumulative power 0.89 vs 0.71). |
| Q10 | Is level B (degraded) deployable? | **Yes, labelled, only where TIERS has no feasible tier (c_M ≤ 0.7).** |
| Q11 | One root (TIERS D2) | **Yes.** Activation needs the same L2-v4 one-root amendment. |
