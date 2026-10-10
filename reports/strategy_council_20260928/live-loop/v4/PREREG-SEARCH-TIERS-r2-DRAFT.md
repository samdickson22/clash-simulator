# PREREG r2 (DRAFT, not frozen): live search tier selected from measured Mac capacity

Draft r2 2026-10-10, PREREG revision author (Opus) for coordinator `0523ae6f`. It revises
`PREREG-SEARCH-TIERS-DRAFT.md` (r1, ab816c31) by applying conditions C1–C14 of the independent review
`REVIEW-PREREG-SEARCH-TIERS-20261010.md` (APPROVE_WITH_CONDITIONS). The condition-by-condition map is
`C1-C14-RESPONSE.md`. Nothing has been launched, committed or run on the Mac. Before the freeze, a **conformance
check** of this text against C1–C14 is required; its reviewer must not have taken part in S1 or R3. The coordinator
then freezes, secret-scans, commits and pushes it **before the first reporting game**. "Frozen" means listed in the
TIERS content manifest (SHA-256). Paths are relative to `reports/`.

## 0. Summary

- **Question.** Which search tier should the live player run, given the CPU the Mac actually has left over while
  perception runs?
- **Design.** It has two decoupled parts, so the fleet does not wait for the Mac to *play*:
  1. **Fleet confirmatory study (C).** Four arms × two budget-equivalent speed cells (1.0× = 200 ms, 0.8× = 160 ms)
     are played on 2,400 fresh paired seeds, plus a 600-seed transfer guard in which the L2-v4 own decks face
     **held-out human opponent decks** that are in no R1 training matchup.
  2. **One Mac measurement session (M).** It is replay-only, and it measures each tier's loaded speed ratio r_T
     against a loaded fleet reference on a fixed, frozen corpus of complete decisions, plus a direct 200 ms
     deadline-mode check against the fleet.
- **Order.** Fleet outcomes stay **sealed until the Mac `tiers-summary.json` is committed** (§11; one 14-day escape,
  §6.6). Any Mac selection from a replay-only session is **PROVISIONAL (emulator-off)** until formal E4/T9 (§6.5).
- **Decision.** A frozen rule maps each tier's Mac measurements to a speed cell. C's results in those cells pick the
  tier: the **cheapest admissible tier shown, at 97.5% confidence, to be no more than 5 pp worse than every costlier
  admissible tier**, and no more than 10 pp worse on the transfer guard (§6.5).
- **Expected outcome (prior, not a claim).**
  - If the Mac sustains five fast cores under load (r_5 ≥ 1.0), K4 is chosen unless a cheaper tier is shown NI to it.
  - **If r_5 lands in [0.8, 1.0), K4 is still the likely pick:** K4@160 (K-v2: 26.5%) is likely to beat S@160
    (S1: 32.2%) by more than 5 pp, so S would fail NI against K4 and K4 would be selected. A K4 pick in that case is
    expected, not a surprise.
  - If K4 is infeasible, S (1 core plus R3a) is chosen over K2 if it stays within 5 pp of K2. The single exploratory
    S1 estimate (−0.83 pp) suggests it may, but S1 is planning input only, not evidence.
  - If nothing qualifies, select F0 (no tier change; §6.5, §10).
- **Cost.** About **1,500 reserved physical-core-hours** for the 3,000 confirmatory blocks (about 400–450 CPU-hours
  actually used); about 1,560 including the 72 descriptive in-distribution blocks (§3). That is about **7 h on four
  exclusive hosts** (01, 03, 04, 08 at 11 slots), about 9.5 h if one host is lost, or about 15 h on 100 cores. Plus
  one Mac session of about 2–2.5 h alone, or 3–3.5 h with the E4 package.

## 1. Hypotheses and primary contrasts

Notation: loss(T@s) is the opponent-win rate of tier T in speed cell s. Draws are kept separate and count as
non-losses. Every contrast is paired on the seed.

| ID | Hypothesis (per tier T ∈ {K4, K2, S}, at its Mac-mapped cell s_T) | Test |
|---|---|---|
| **V1** | T beats the 1-core control by a meaningful margin: loss(T@s_T) − loss(K0c@s_1) < −10 pp | upper **98.33%** CI ≤ −10 pp (Bonferroni over 3 tiers), primary population |
| **V2** | T beats plain v1 clearly in absolute terms: loss(T@s_T) < 40% | upper 98.33% CI ≤ 40%, primary population |
| **G1** | Transfer guard, superiority: loss(T@s_T) − loss(K0c@s_1) < 0 on the guard population | upper **95%** CI < 0, guard population |
| **G2** | Transfer guard, cheaper vs costlier: for a candidate T cheaper than an admissible U, loss(T@s_T) − loss(U@s_U) ≤ +10 pp on the guard population | upper **95%** CI ≤ +10 pp, guard population |
| **NI** | Selection: a cheaper tier T is non-inferior to a costlier admissible tier U: loss(T@s_T) − loss(U@s_U) ≤ +5 pp | upper bound of the two-sided **97.5%** CI ≤ +5 pp, primary population |

- **Why these margins.** V1 keeps the −10 pp advance margin that K, K-v2, K2 and S1 used. V2 rules out "beats a
  collapsed control": K0c-160 lost 79%, which is worse than not searching. NI keeps S1's +5 pp margin, which is
  half the V1 margin, so a selected cheaper tier always keeps most of the benefit. G2's wider +10 pp margin reflects
  the guard's n = 600 (C16's 1,200-seed guard was not adopted; see `C1-C14-RESPONSE.md`).
- **Why NI is at 97.5%.** Up to two cheaper candidates (S, then K2) can be tested in sequence; one-sided 0.0125 per
  candidate keeps the probability of falsely selecting an inferior cheaper tier ≤ 0.025 overall.
- **Descriptive only.** All 8 arm-cells' loss rates in every population, every pairwise contrast in both cells, the
  speed degradation (T@0.8 − T@1.0), the in-distribution L2-own vs L2-opponent cells (§3), and the timing, cutoff,
  fallback, overrun and GC tables in the K-v2/S1 format.

## 2. Arms (all one-core-or-more, same harness, same opponent)

| Arm | Definition (frozen bytes from the cited study) | Cores |
|---|---|---:|
| **K0c** (control) | S1's K0c: coarse-first W-screen8, one cached v1 forward for both the stochastic T=1 fallback and the exact top-8 proposals | 1 |
| **S** | S1's S: coarse-first W-screen8; **R3a** EMA `37509a43…` top-8 proposer; calibrated deterministic fallback, calibration `e3003533…`, threshold `0.5005528330802917`; one cached forward | 1 |
| **K2** | K2's two-worker WAIT-first anytime collector (freeze `3cf8919e`), including K-v2 preparation and GC amendments (`75e2513d`, `83a7faea`); v1 fallback only when no complete score exists | 2 workers + main = 3 |
| **K4** | The same collector with four workers, i.e. K-v2's V-arm | 4 + main = 5 |

Every arm runs in two cells, **s = 1.0 (200 ms deadline)** and **s = 0.8 (160 ms)**, each with an 8 ms return
reserve. That gives 8 arm-cells, all on the same seeds. K2@160 has never been run and K4 has never run inside the
S1 harness; both are covered by the qualification in §3.1.

Common rules, all inherited unchanged from K2/S1:
- Opponent: the sealed plain v1 policy, T=1, no search.
- Symmetric d=27, capacity 1, search interval 10, policy interval 5, horizon 160 with three styles.
- **Honest lateness:** the full timer starts before observation; every positive overrun is charged as
  ceil(overrun×20) ticks; partial and late scores never count.
- GC is deferred only inside decisions and metered.
- Native `44874fd6`.
- **One sampled public belief root per decision** (see §9, decision D2).
- **Per-decision logging (C17, adopted; costs nothing):** unpruned candidate count, own elixir, the fallback action
  taken, `threads`, `coarse_horizon` and `default_source`.

### 2.1 Student decision: test R3a's bytes under its own name, do not retrain (decision D1)

R3a (EMA `37509a43…`, calibration `e3003533…`, threshold 0.5005528330802917) is tested under its own name. R3
recorded it as Stage 1 KILLED and 'ALWAYS NEVER-ADOPTABLE … regardless of its paired benefit'. **This PREREG,
issued by coordinator `0523ae6f` under the owner's delegation, supersedes the NEVER-ADOPTABLE clause for these
exact bytes only.** The supersession is outcome-informed: it follows the r1(b) descriptive game result and the
S1 exploration. R3's Stage 1 KILL on its imitation gates is not re-litigated, and R3's files are not edited; an
additive pointer is placed in `exit-r3/`. Claims concern these bytes in tier S only, never the R3 recipe. S1 and
r1(b) data are used for planning only: they are never pooled or cited as evidence.

Why test the frozen bytes rather than retrain:

1. **A confirmatory test of fixed bytes on fresh seeds is unbiased for those bytes.** The selection concern
   (winner's curse after r1(b) and S1) applies to claims about the *recipe*, not to the exact artifact deployed.
   A retrained student would make S1's effect and variance estimates, and so this power calculation, inapplicable.
   It would also add a GPU fit plus a qualification cycle before anything else could run. S1 was itself selected
   (this study exists because S1 passed, by 1.17 pp), so its −16 pp is expected to be optimistic; §4 reports power
   at −14 and −13 for that reason.
2. **Post-hoc rationale, stated after the gates were missed:** R3's Stage 1 gates were imitation proxies, not
   strength. Play recall missed 0.6375 by 0.008 (0.6297); agreement missed all-WAIT+0.10 by 0.010; W regret
   *passed* (0.0088 ≤ 0.010). Game outcome is the deployment endpoint, and §1 tests it directly.
3. **The audit's legitimate concerns are designed in, not retrained away:**
   - inference is equalised (K0c caches one v1 forward, the S1 fix);
   - lateness is charged;
   - the opponent and kernel are common across arms;
   - the speed sweep is in the design;
   - opponent-deck shift is gated by the **G1/G2 transfer guard**, whose opponent decks are held out of every R1
     training matchup (§3). The guard's *own* decks are the L2 decks, which **are** in R3a's training corpus.

A fresh-seed refit is **not** a candidate here. If S fails G1 or G2, a refit becomes a separate exploration item, as
does the audit's factorial ablation (C18).

### 2.2 Disclosures about R3a (required in the final report)

- **The full chain.** R3 Stage 1 KILL of R3a (calibrated play recall 0.6297 vs 0.6375; binary agreement 0.7438 vs
  0.7541); the kills of siblings **R3b–R3e** (R3d is a new-seed refit of R3a's recipe); the r1 S-teacher result
  (−7.5 pp); the outcome-informed r1(b) descriptive game test (−28.67 pp against an init-W mirror) and R3's
  "ALWAYS NEVER-ADOPTABLE" label (`exit-r3/RESULTS.md` l.85, 97, 125); the independent audit (effect confirmed with
  caveats, fresh fit recommended); S1 (−16.00 pp vs K0c, −0.83 pp vs K2, designed after r1(b)); then this PREREG.
- **R3a was the only student whose game outcome was measured.**
- **The fallback threshold was calibrated on the R1 heldout64 slice.**
- **Equalised and not equalised.** S1/K0c equalised the cached forward. They did not equalise the deterministic
  calibrated fallback against v1 T=1 sampling. That fallback is part of tier S by design, which is fine for a tier
  claim, but the effect cannot be attributed to proposal quality.
- **Training-distribution overlap.** R3a trained on the R1 corpus: 8 own decks (the five archetype decks **and** the
  three L2 decks; `exit-r1/PLAN.md` l.12–14, `exit_r1/emitter.py` `decks()`), all 64 matchups, against an opponent
  mix that **includes the released v1 stochastic policy**, which is this study's opponent. The primary population is
  in distribution for S and not for K2/K4, which have no training. That asymmetry favours S in every primary
  contrast. The guard population removes the opponent-deck overlap but not the own-deck or opponent-policy overlap.

### 2.3 Independence

- The independent integer-count verification script is authored and committed before outcomes open (§5). **Its
  author must differ from the reducer's author.**
- The conformance reviewer of this r2 text must not have taken part in S1 or R3.

## 3. Populations, seeds and schedule

- **Primary population:** the K2/S1 harness, with five archetype decks (bridge_wincon, siege, beatdown, bait,
  chip). That gives 25 matchups × 2 seats = 50 cells × 48 seeds = **2,400 paired seeds**. Seed index i is assigned
  to cell i mod 50.
- **Guard population (held-out opponent decks):**
  - Own deck ∈ the three L2-v4 families (Hog 2.6, X-Bow cycle, Royal Hogs spawners, as transcribed in
    `exit_r1/emitter.py` `decks()` from L2 `register.py`).
  - Opponent deck: the **three most frequent decks in the frozen C56 human deck catalogue
    (`c56/engine/root-v3/human_deck_catalog.json`) that are not among the eight R1 training decks** and whose cards
    are all supported by native 44874fd6 and by the v1/R3a vocabularies. They are selected by a hashed script,
    `select_guard_decks.py`, committed with its output in the TIERS manifest before the freeze.
  - Styles off, since the opponent is the v1 policy. Alternating seats.
  - **600 paired seeds**, stratified 3 own × 3 opponent × 2 seats = 18 cells; seed index i goes to cell i mod 18
    (so 6 cells hold 34 seeds and 12 hold 33). The guard bootstrap is stratified by these 18 cells.
  - **Qualification:** every guard card is supported by the native, the v1 vocabulary and the R3a vocabulary, with
    no fallback for unknown cards; any unknown-card fallback in qualification fails the freeze. A deck with an
    unsupported card is skipped by the script's frequency order, never by a human choice.
- **Descriptive in-distribution cells (not selection evidence):** L2-own vs L2-opponent decks (3 × 3 × 2 = 18
  cells × 4 seeds = **72 seeds**), in distribution for S. Played last; they never enter any gate.
- **Seeds (fresh; the seed audit must prove them disjoint from every frozen K/K-v2/K2/S1 (R1/R2 and the abandoned
  S1 attempt-1 bank)/R3 and round 2/R1/G generation (`4503599727370496…`, G `4503601607370496+[0,3e6)`)/X/DAgger/
  noise-ceiling/L2-v4 range and from helper offsets 0/13/100000..100003/271828..271829 before the freeze):**

  | Use | Range |
  |---|---|
  | Primary reporting | `4503603107370496+[0,2400)` |
  | Primary replacement bank (§3.2) | `4503603107370496+[2400,2880)` |
  | Guard reporting | `4503603207370496+[0,600)` |
  | Guard replacement bank (§3.2) | `4503603207370496+[600,720)` |
  | Excluded smoke (8 seeds × 8 arm-cells) | `4503603307370496+[0,8)` |
  | Speed-corpus generation (§6.1; no outcomes read) | `4503603407370496+[0,64)` |
  | Descriptive in-distribution cells | `4503603507370496+[0,72)` |

- **Schedule:**
  - Each seed's 8 arm-cells run back-to-back on one host and slot, in cyclic rotated order. A **block** is one seed's
    8 arm-cells.
  - Slots are 5 physical cores, with no SMT siblings, at nice 10 / SCHED_OTHER. Each arm narrows to its own core
    count, as in K2. The 1-core cells leave four reserved cores idle; that is in the cost (§0).
  - Hosts are named at the freeze from **{127x01, 127x03, 127x04, 127x08}**: 02 and 07 are down, 05 is command only,
    06 is unreachable, and leased or roader hosts are never used for timing. 11 slots per host; **8 slots** on a host
    whose `~/.local/bin/fleet-console-users` check is positive at launch. The coordinator assigns hosts with S1's
    exclusive-host guard.
  - Blocks are dispatched in seed-index order within each population, interleaving the primary and guard queues
    5:1 (the population ratio), so that host loss and drift spread over both.

### 3.1 Harness deltas and qualification

Harness reuse is not byte reuse. The S1 `run.py` asserts `hostname == '127x01'`, ≤13 workers and width 3; K2's
harness was 03-only. The code deltas from the S1 (R2) and K2 freezes are:

1. 5-core slots (S1 used 3-core width) and the per-host slot count (11 or 8);
2. 8 arm-cells per block, including K2 and K4 inside the S1 harness and the never-run **K2@160** and K4-in-S1 cells;
3. multi-host dispatch, removal of the `127x01` hostname assertion, per-host pin receipts;
4. the guard population (new deck pairs, 18-cell assignment) and the descriptive in-distribution cells;
5. the replacement-bank logic (§3.2) and the 30-minute off-host copy;
6. the stratified 10,000-resample bootstrap and the new gates (G1, G2, NI at 97.5%, the §6.5 rule);
7. C17 per-decision logging fields;
8. the corpus-generation, fleet-reference and deadline-mode reference scripts (§6.1).

Each delta is listed with its diff in the TIERS manifest and diff-reviewed by someone other than its author. Then
the full **S1 + K2 + K-v2 qualification batteries** are re-run under the new harness on every named host:
125-state 1/2/4-worker equality, belief ON/OFF, injected-clock, lateness and GC. Every host must pin identical
runtime and native SHAs; per-host pin receipts are kept.

### 3.2 Lost hosts, foreign compute and replacement blocks

- **Off-host copy.** Completed blocks are copied to the hub (127x01; mirror 127x04) at least every 30 minutes. A
  block counts only when all 8 arm-cells are complete **and** it is on the hub. A block completed on a host that is
  lost before the copy is a lost block.
- **What is lost.** A block is lost if its host is powered off or unreachable, if foreign compute hits its slot, or
  if reporting on its host is stopped by the console rule below. Lost and interrupted blocks are preserved and
  excluded; their seed is never re-run.
- **Console rule.** Reporting on a host stops if a console user's load exceeds one core for more than 60 s (read
  from `fleet-console-users` plus the 1 Hz census). Its in-flight blocks go to the replacement bank.
- **Before admission on each timing host:** pause the hub mirror and any cross-host pollers using their stop files
  (a cross-host T11 poller voided S1's first attempt).
- **Replacement.** The k-th lost block (k = 0, 1, …) in primary cell c = i mod 50 is replaced by seed index
  **2400 + 50·k + c**, which keeps its matchup and seat. The guard is analogous: **600 + 18·k + (i mod 18)**.
  Assignment is in loss order and blind to outcomes (no outcome is opened before §11 step 8). Replacements are
  dispatched to the remaining hosts.
- **Caps.** If more than **10%** of blocks in either population need replacement (240 primary or 60 guard), or any
  cell's bank row is exhausted (k > 8 primary or k > 5 guard), stop and amend before any outcome opens.
- **Lost host.** The study continues on the remaining named hosts (about 9.5 h wall on three). If fewer than two
  named hosts remain, or a host fails §6.1's ±5% reference rule, stop and amend; no host is added after the freeze
  without an amendment and its own qualification and reference.
- **Disclosure.** Replaced blocks are counted by population, cell and host. Long games are more likely to be cut,
  so loss may be informative; the report gives the lost blocks' cell distribution (but never their outcomes).

## 4. Power and sample size

- **Variance inputs.** Per-pair SDs of loss differences come from today's 600-seed CIs (σ = half-width/1.96·√600):
  - S−K0c 0.61;
  - S−K2 0.55;
  - K2−K4 0.48;
  - K4−K0 0.55;
  - K2−K0 0.63.

  K2−K0c and K4−K0c were never measured as paired contrasts; the K0c anchor exists only in S1. Their σ values are
  borrowed from the K0 contrasts.
- **Planning values.** The design uses σ = **0.63** for V1 and **0.56** for NI and G2. Effect planning values:
  - S−K0c −16, observed in S1 (selected, so likely optimistic);
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

**NI power** (+5 pp margin, one-sided 0.0125, i.e. two-sided 97.5%, z = 2.241), by true S−K2:

| n | SE pp | −0.83 | 0 | +1 | +2 | +3 |
|---:|---:|---:|---:|---:|---:|---:|
| 1,800 | 1.32 | .99 | .94 | .79 | .51 | .23 |
| **2,400** | **1.14** | 1.00 | **.98** | **.90** | .65 | .31 |

- **Choice: n = 2,400.** It gives ≥0.93 power for K2/S V1 at the planning effects, and still 0.76 if the true
  effect has regressed 2 pp toward the margin. **S1's own n = 600 had about 0.67 power at its own α (0.48 at this
  study's Bonferroni α)** at its point estimate, and passed by 1.17 pp.
- **K4 in the 1.0 cell.** V1 power is essentially 1. **A false NI of K2 against K4, with true +8.5 pp, has
  probability about 6×10⁻⁸ at the planning σ = 0.56 under the 97.5% NI interval** (about 3×10⁻⁹ with K2−K4's own
  σ = 0.48). r1's "<10⁻⁷" was stated at 95%, where it held only for σ = 0.48 (1.6×10⁻⁸; 2.6×10⁻⁷ at σ = 0.56).
- **0.8 cell.** The control collapses there (K0c-160 79%), so V1 and V2 are not binding. NI between tiers is the
  operative test, at the same precision.
- **Guard, n = 600.** G1 (σ = 0.63, SE 2.57 pp) has power 1.00 if the effect transfers fully (−16 pp), 0.88 at half
  (−8), and 0.49 at −5. G2 (+10 pp margin, σ = 0.56, SE 2.29 pp) has power 0.99 at a true 0, 0.86 at +3 and 0.59 at
  +5.
- **No interim looks**, no optional stopping, no re-estimation.

## 5. Statistics

- Paired-seed percentile bootstrap, **10,000 resamples**, `numpy.default_rng(2026101040)`, shared across all
  contrasts. Resampling is stratified by deck-matchup × seat cell (50 primary cells; 18 guard cells).
- Upper bounds: V1/V2 from the two-sided **98.33%** interval; **NI from the two-sided 97.5% interval**; G1 and G2
  from the two-sided 95% interval.
- Bonferroni covers the three tier-viability claims. V1 ∧ V2 ∧ G1 is an intersection–union, so the conjunction needs
  no further adjustment. NI is at 97.5% to cover up to two sequential cheaper candidates (§1); NI ∧ G2 against every
  costlier admissible tier is again an intersection–union within a candidate.
- The speed cell is chosen by a physical Mac measurement, under a rule frozen here (§6), with its scripts and
  reducer frozen before any reporting game and its summary committed before outcomes open (§6.6), so there is no
  adjustment across cells.
- **r_T and all gates are computed in full float precision with no rounding.** All stated boundaries are inclusive
  as written.
- Cutoff, fallback and overrun rates are reported with per-game numerator/denominator resampling, as in S1.
- An **independent integer-count verification script** is authored and committed before outcomes open, following
  the S1 precedent; its author is not the reducer's author (§2.3).

## 6. Mac measurement and the decision rule

### 6.1 Speed corpora and fleet references (built on the fleet before the freeze)

- **The corpus.** For each tier T, 300 nonterminal decision states come from **T's own** excluded games on the
  corpus range (seeds `…3407370496+[0,64)`; each tier plays them in its 1.0 cell; outcomes are never read), with
  stratified sampling by elixir and legal-play count. They are sealed as public history plus root bytes.
- **The work unit** is the **complete no-deadline decision** from sealed public history:
  - belief preparation (posterior, sampling, the one public root);
  - candidate generation and root construction;
  - exact screen8 scoring with the tier's worker count;
  - Python reduction and action selection;
  - for S and K0c, the cached forward and top-8 proposal.
- **Exactness.** Identical work is enforced by exact equality of the final action and the scores against the Linux
  receipts (with the ARM64-NEAR-EXACT rule of §7.2).
- **Fleet reference (no-deadline), under the reporting load profile.**
  - Measured on **every named reporting host**, 3 repeats per state per tier configuration (1, 3 and 5 cores).
  - While the reference runs on one slot, **every other slot on that host runs the same frozen corpus loop**, which
    holds the CPU at all-core clocks as in reporting.
  - `/proc/cpuinfo` MHz is sampled at 1 Hz during the reference and during reporting, and both are reported.
  - A host whose per-state median wall (pooled over tiers, as a geometric mean of per-state ratios to the pooled
    median) lies outside **±5% of the pooled all-host median** is excluded from reporting before the freeze.
  - The frozen reference wall for each state is the **pooled per-state median** over the remaining hosts and repeats.
- **Fleet reference (deadline mode, for gate 6).** On the same hosts and load profile, each tier's corpus is run in
  deadline mode at **200 ms and 160 ms** (8 ms reserve, honest timer), 3 repeats. The per-state cutoff, fallback and
  no-complete-play rates are frozen into the manifest, pooled over hosts and repeats.
- These references cost a few core-hours and are included in the freeze, not in reporting.

### 6.2 The speed ratio

For each tier T and its thread configuration (1 core for S and K0c, each on its own corpus; 3 cores for K2;
5 cores for K4), with per-state Mac wall taken as the median over the session's repeats of that state:

**r_T = min( median over states of (fleet wall / Mac loaded wall), Σ fleet wall / Σ Mac loaded wall,
fleet p90 wall / Mac p90 wall ).**

Notation: r_S and r_K0c (together "r_1"), r_3 = r_K2, r_5 = r_K4. S's cell uses r_S (its work includes the student
forward); the control cell s_1 uses r_K0c, so a slow student never weakens the control. The minimum of the three statistics keeps a heavy slow tail from
hiding behind a median at the cliff edge (K-v2: +8 pp for 200→160 ms, +56 pp for 160→120 ms). r_T is measured by
the E4-v3 addendum r2 (`mac-e4-package/E4-V3-ADDENDUM-r2-DRAFT.md`) with replay perception load running and the
configuration and priority the live runtime will use.

### 6.3 Feasibility on the Mac

Tier T is **Mac-feasible** in cell s iff all of the following hold:
1. r_T ≥ 0.80, and the 10th percentile of the per-state ratio is **≥ 0.70**;
2. while T runs, the replay perception load keeps **≥18 processed FPS and ≥95% processed**;
3. the arm64 exactness checks pass (§7.2), including belief/RNG exactness;
4. the timestamped GC/poll check passes, with either default GC or the registered `gc.freeze()` variant (called
   once after warm-up, default thresholds):
   - an **opportunity** is a scheduled poll at the live search/policy cadence, computed from replay packet
     timestamps;
   - a **maintenance-delayed poll** starts more than 25 ms after its schedule;
   - delayed polls ≤ 1% of opportunities, **and** no in-window pause that would add a charged tick (a poll start
     more than 50 ms past its schedule);
5. for S only, the loaded student forward p99 is ≤ 20 ms on the chosen backend;
6. **deadline-mode equivalence:** on the Mac, under load, T's corpus run at **200 ms** (8 ms reserve) has cutoff and
   no-complete-play rates each ≤ the fleet's deadline-mode rate at cell s's deadline (200 ms for s = 1.0, 160 ms for
   s = 0.8) **+ 2 pp absolute**.

### 6.4 Speed cell

- Provisional cell from speed: s_T = 1.0 if r_T ≥ 1.00, and 0.8 if 0.80 ≤ r_T < 1.00. Faster Macs get no credit
  beyond 1.0.
- **Gate 6 then applies:** if T fails gate 6 in its provisional cell, it moves down one cell and gate 6 is
  re-checked against the 160 ms fleet reference. Below 0.8, T is infeasible.
- The control cell is s_1 = the cell of K0c (r_K0c and K0c's gate 6). K0c need not be Mac-feasible on gates 4–5;
  it is only the control.

### 6.5 Rule (frozen)

1. A = {T ∈ {K4, K2, S} : Mac-feasible in s_T ∧ V1 ∧ V2 at (s_T, s_1) ∧ G1 at the same cells}.
2. If A = ∅, select **F0**: no tier change. The frozen L2-v4 search configuration stays, and the report says
   "no supported tier". F0's own Mac feasibility is unmeasured (§10).
3. Otherwise, select the cheapest T ∈ A (fewest cores) such that NI(T, U) holds for **every** U ∈ A with more cores,
   where NI(T, U) is: the upper bound of the two-sided **97.5%** paired interval of loss(T@s_T) − loss(U@s_U) is
   ≤ +5 pp. If none holds, select the tier with the most cores in A.
   - **G2 is part of each candidate check:** a cheaper T qualifies only if, in addition, G2(T, U) holds on the guard
     for every U ∈ A with more cores (upper 95% bound of loss(T@s_T) − loss(U@s_U) ≤ +10 pp). The tier with the most
     cores in A has no costlier U and qualifies trivially.
4. Selection fixes the tier, its cell and its deadline. Live uses the **200 ms** deadline whatever the cell; the
   cell only says which fleet evidence applies.
5. **Provisional status.** A selection made from a replay-only session is **PROVISIONAL (emulator-off)**. It cannot
   be activated until formal E4/T9, with the emulator running, re-measures r_T, gate 6, FPS/processed, GC and the
   student p99 on the same corpora with the same frozen scripts. Every §6.3 gate is re-applied, using the worst
   value of each across all valid sessions. Formal E4 must be amended to include these measurements before it runs.

**Measurement integrity:**
- There is exactly one valid Mac session. Repeats are allowed only for the technical failures pre-listed in the
  addendum (§F), classified mechanically by a frozen script from receipts, and the **minimum r_T across valid
  sessions** (and the worst value of every other gate input) is used.
- Re-application after formal E4: **all cells are pre-played, so re-application needs no new games. The selected
  tier may become cheaper or costlier.** (For example, K4 dropping to the 0.8 cell can make S NI against it; S
  becoming infeasible can move the pick to K2.)
- r_T can never be raised after the outcomes are seen.

### 6.6 Outcome barrier

- **(a)** `measure_tiers.py` and the tiers reducer are written, independently reviewed and **frozen in the TIERS
  manifest before any fleet reporting game**.
- **(b)** **The fleet outcome barrier stays closed until `tiers-summary.json` is committed.** If Sam has not
  authorised the Mac session within 14 days of reporting completing, outcomes may open. In that case any later Mac
  repeat session needs an independent reviewer to confirm the mechanical failure classification before it runs.
- Scheduling the Mac session before fleet reporting ends (C15) is preferred; it removes every residual steering
  path.

## 7. Mac must-measure-first list (blocking, in this order)

1. **Identity:** chip, P/E core counts (`hw.perflevel0/1.physicalcpu`), RAM, macOS, thermal state; the arm64
   Python, Torch and Rust toolchain.
2. **arm64 native build** from the frozen tier source, with no Linux binary, and exactness:
   - 125-state exact screen8 actions, candidates and scores against the Linux receipts;
   - 1/2/4-worker equality;
   - zero-budget root immutability;
   - **belief/RNG exactness:** 125 histories with exact posterior, weights, cumulative order, resource ledger,
     samples and RNG state, with the deadline ON and OFF, as in the K-v2 belief qualification.

   **Outcomes:**
   - A single-thread action, candidate, score, root or belief/sample/RNG mismatch ⇒ **all** tiers infeasible.
   - A mismatch only in 2/4-worker equality ⇒ K2/K4 infeasible.
   - If actions and candidates match 125/125 and every score differs by ≤ 1e-12 relative, the result is
     **ARM64-NEAR-EXACT**: it passes, with disclosure. The same applies to belief floats (posterior, weights) when
     every discrete output (cumulative order, ledger, samples, RNG state) matches exactly. Anything else fails.
3. **Student cross-platform agreement** on 2,000 frozen states:
   - Mac CPU (1 Torch thread) and MPS each against fleet CPU;
   - the gate decision and top-8 ordered list must agree on **≥99.5%** of states;
   - every gate disagreement must be within 1e-4 of the threshold or an exact logit tie; a top-8 order
     disagreement is allowed iff the swapped entries' fleet logits differ by ≤ 1e-4.

   **Backend: CPU by default.** MPS is used only if its loaded p99 is ≥2 ms lower **and** perception p95 rises
   ≤2 ms while it runs (MPS is shared with perception).
4. **Free capacity** with replay perception running and no search: per-core idle at 1 Hz, mapped to P/E clusters,
   reported as free P / free E (p10, p50). This is descriptive; feasibility is decided by items 5–6.
5. **Loaded r_1, r_3, r_5** (§6.2), each ≥300 states and ≥5 min after a 5-minute thermal warm-up, in rotated tier
   blocks of 50 states. Unloaded ratios are also measured, to separate contention from raw speed.
6. **Deadline-mode corpus check (gate 6):** each tier's corpus at 200 ms / 8 ms reserve under load.
7. **Deadline-mode tier cells:** 1,000 replay packets × {K0c, S, K2, K4} at 200 ms / 8 ms reserve under load.
   Record:
   - p50/p95/p99/max;
   - cutoff, fallback and no-complete-play rates;
   - overruns >200 ms and cut returns >208 ms;
   - **timestamped GC pauses against scheduled poll deadlines** (§6.3 gate 4), with default GC and, for every tier
     passing gates 1–3 and 5, with the `gc.freeze()` variant.

## 8. Kill criteria

- **Before reporting** (no outcomes are opened): any qualification, exactness or pin failure; a seed-audit
  overlap; foreign compute on a timing slot; a smoke timing/metadata failure; a guard-card support failure. Fix,
  re-qualify, and use a new smoke range if code changed.
- **Validity:** if K0c@1.0 loss falls outside [36%, 54%] (the prior studies ran 44–48%), the result is reported
  and the selection is **suspended. An independent reviewer inspects code and receipts, not outcomes by arm. A
  harness defect voids the study: a new PREREG with new seeds is required. No defect means the selection proceeds
  unchanged. The review's conclusion is committed before the selection is applied.**
- **Tier kills:** a tier is killed for this program if it is not Mac-feasible, or fails V1, V2 or G1 in its cell.
  S is also killed by a student-agreement failure (§7.3) or a loaded forward p99 >20 ms. A cheaper tier that fails
  NI or G2 is not selected but is not killed.
- **Replacement cap:** §3.2 (stop and amend before opening outcomes).
- **Program kill:** if A = ∅ even though every r_T ≥ 1.0 and every tier passes gate 6 at 1.0, the failure is
  strength, not speed. The tier program stops, and research returns to the fleet.

## 9. Recorded design decisions

- **D1, student:** R3a under its own name, with R3's NEVER-ADOPTABLE clause superseded for these bytes only by this
  PREREG (outcome-informed, disclosed); no retrain (§2.1–2.2).
- **D2, one belief root.** Every result behind these tiers (K, K-v2, K2, S1) used one sampled public root per
  decision. The live S6 pipeline uses four, which is roughly 4× the scoring work: on any plausible Mac that puts
  every tier past the K-v2 cliff. There is no strength evidence for four roots under W.
  **The selected tier is therefore registered as one-root**, and activating it needs an L2-v4 amendment replacing
  K=4 roots (§10). Four-root timing remains a descriptive E4 cell (the existing package), not a candidate.
- **D3, fixed live deadline.** Live keeps a 200 ms deadline. Slower hardware maps to the 0.8 cell's *evidence*;
  the deadline is never shortened.
- **D4, static tier per session.** No in-match tier switching. A watchdog downgrade is a separate engineering
  amendment and is not covered by this evidence.
- **D5, opponent.** The plain v1 policy (human proxy), as in every input study. A v1+W opponent is out of scope.
- **D6, outcome barrier.** Fleet outcomes open only after the Mac summary is committed (§6.6), except via the
  14-day escape.

## 10. Limits and disclosures (stated up front)

- Fleet cells emulate speed by budget, not by underclocking. The r2 work unit now covers belief preparation and
  Python reduction, and gate 6 checks deadline behaviour directly, but return and tick conversion still run at
  fleet speed.
- The simulator has perfect public observation. Perception noise is L2-v4's question, not this one's.
- **Opponent.** The plain v1 opponent is the student's training opponent, and the tier ranking against humans is
  untested. "V2 < 40%" is relative to v1, not to humans.
- **In-distribution asymmetry favours S** (§2.2): R3a trained on all eight R1 decks including the L2 decks, against
  a mix that includes v1. The guard removes only the opponent-deck overlap.
- **F0's own Mac feasibility is unmeasured.** If A = ∅, the L2-v4 four-root configuration stays, and it is likely
  *less* Mac-feasible than any tier (D2's own argument).
- **One-root activation needs an L2-v4 amendment before any L2-v4 confirmatory game.** L2-v4's P/O/S-d arms all use
  the K=4 P3 scorer. If L2-v4 reporting has already started with K = 4, the tier waits for L2-v4 to finish.
- **GC pauses between decisions are uncharged on the fleet** (only in-decision deferral is metered). Gen-2 pauses
  of about 145–155 ms occur about 0.15 times per game.
- Mac timing is replay-only, so r_T is an **upper bound** on the live value: the live load includes the Android
  emulator. The selection is PROVISIONAL (emulator-off) until formal E4/T9 re-measures every §6.3 input (§6.5
  item 5). Formal E4 (emulator-on, real gRPC, P4 acceptance, eight matches) is still required before live play.
- Live play happens only under Sam's authorisation, on the Mac emulator with a throwaway account, with no
  detection evasion, and under the fair-information rule. Nothing in this PREREG authorises live play.

## 11. Run order

1. Independent review (done: APPROVE_WITH_CONDITIONS), r2 edits, and the **conformance check** of r2.
2. Build and diff-review the harness deltas (§3.1); write and independently review `measure_tiers.py`, the tiers
   reducer, `select_guard_decks.py`, the verifier (author ≠ reducer author) and the reference scripts.
3. Corpus generation (§6.1), qualification batteries on every named host, fleet references (no-deadline and
   deadline mode) under load, the ±5% host rule, and the seed audit.
4. **Freeze:** source, plan, seed audit, guard decks, speed corpora, fleet references, `measure_tiers.py` and the
   tiers reducer. Secret-scan, commit, push.
5. Smoke on the fleet (excluded range).
6. Fleet reporting: 2,400 + 600 seeds × 8 arm-cells (plus 72 descriptive), about 7 h on four hosts, with §3.2
   replacement. Outcomes stay **sealed**; only completion, timing and pin receipts are read.
7. The Mac session (addendum r2), whenever Sam authorises it, preferably before step 6 ends. Commit
   `tiers-summary.json`.
8. **Open fleet outcomes** (or after the 14-day escape, §6.6). Verification and reduction.
9. Apply §6.5 → a **PROVISIONAL (emulator-off)** selection.
10. Amend formal E4/T9 with the §6.5 item 5 measurements; the selection activates only after they pass, together
    with the L2-v4 one-root amendment and coordinator review.

Steps 6 and 7 are independent in execution; only step 8 waits for both.
