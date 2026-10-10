# Independent review: PREREG search tiers (draft ab816c31) + E4-v3 addendum + Mac tiers memo

Reviewer: Opus (independent, high effort; no part in K/K-v2/K2/S1/R3/X), 2026-10-10, for coordinator `0523ae6f`.
Scope: `live-loop/v4/PREREG-SEARCH-TIERS-DRAFT.md`, `mac-e4-package/E4-V3-ADDENDUM-DRAFT.md`,
`DECISION-MAC-TIERS-20261010.md`, checked against `explore/{k-anytime,k-v2,k2,s1}` and `imitation/exit-r3`, plus
`imitation/exit-r1/PLAN.md`, `imitation/exit_r1/emitter.py`, `L2-V4-PREREG.md` and the fleet memory notes.
I only read files. I ran no games and launched nothing, and nothing is committed. Paths are relative to `reports/`.

## Verdict: **APPROVE_WITH_CONDITIONS**

The design is sound in outline:
- two decoupled parts (fleet outcomes and a physical Mac measurement);
- fresh paired seeds, frozen arms, honest lateness and an integer-count verifier;
- Bonferroni-controlled viability gates and a rule written before any Mac number exists.

The power arithmetic checks out. But one premise is factually false, and the rule and the Mac measurement have
several gaps that matter. **C1–C14 below must be edited into the draft before the freeze.** A short conformance
check of the edited text is also required before the freeze; any reviewer may do it, including this one. C15–C18
are strongly recommended.

### Summary (under 200 words)

- **Blocking 1: the G guard's premise is false.** R3a trained on the R1 corpus, whose emitter played all 64
  matchups of **8 decks, including the three L2 decks** (`exit-r1/PLAN.md` l.12–14; `emitter.py` `decks()`). So G
  is not a generalisation test. It should use held-out *opponent* decks and include non-inferiority against the
  costlier tier.
- **Blocking 2: re-freezing R3a is legitimate, but the relabelling is not.** "S1-student" must be called R3a, and
  the draft must say explicitly that it supersedes R3's "ALWAYS NEVER-ADOPTABLE" clause, with the outcome-informed
  history disclosed.
- **Blocking 3: T_max is defined as "most cores", not "strongest".** Across speed cells this can select a tier
  that is more than 5 pp worse than a stronger cheaper tier. NI should be tested against every costlier admissible
  tier.
- **Blocking 4: r_T is weak in three ways.** It omits Python pipeline work, it uses a median at the cliff edge, and
  its fleet reference is measured on an idle, boosting 3990X. Add a deadline-mode equivalence check.
- **Other conditions:**
  - the addendum's D1 kill rule is wrong;
  - belief/RNG exactness is missing on arm64;
  - the cost is about 3× understated, and hosts 02 and 07 are down;
  - host-loss and replacement handling, the drift-suspension outcome, and the ordering of the Mac session against
    outcome opening are undefined.
- The addendum is safe: replay only, no taps, no client, no ladder.

---

## 1. Re-freezing R3a after its frozen kill (question 1)

**What actually happened, in order:**
1. **R3 Stage 1 KILL.** Calibrated play recall was 0.6297 against a gate of 0.6375, and binary agreement was
   0.7438 against 0.7541.
2. **Siblings R3b–R3e were also killed.** R3d is a new-seed refit of R3a's recipe.
3. **An outcome-informed descriptive game test** (r1(b), −28.67 pp against an init-W mirror) was labelled
   "R3a descriptive is ALWAYS NEVER-ADOPTABLE … ineligible regardless of its paired benefit"
   (`exit-r3/RESULTS.md` l.85, 97, 125).
4. **An independent audit** confirmed the effect with caveats and recommended a fresh fit.
5. **S1 exploration** found −16.00 pp against K0c and −0.83 pp against K2. S1 was designed after step 3.
6. **This PREREG** follows from S1.

**Is it legitimate?** Yes, as a test of fixed bytes. A confirmatory test of a fixed artefact on fresh, audited
seeds, with frozen arms and a frozen reducer, gives an unbiased estimate *for that artefact*, however the artefact
was arrived at. Exploration that selects a candidate followed by a fresh-seed confirmation is the normal pipeline,
not forking paths, provided that:
- (a) the estimand is restricted to these bytes in this configuration;
- (b) no exploration data are pooled with the confirmatory data or used as evidence;
- (c) every analytic choice is frozen before outcomes.

The draft meets (a) and (c). For (b), S1 is used only for planning (power), which is correct: S1 is **not**
evidence. It is also selected evidence, since this study exists because S1 passed (by 1.17 pp), so its −16 pp is
expected to be optimistic. The draft's power column at −14 (0.76) and −13 (0.48) partly covers this.

**What is not acceptable is the governance framing.**
- The draft creates "a new registered artefact whose bytes are identical to R3a" and states that R3's verdict is
  "unchanged in R3's record", while granting adoption authority. R3's record explicitly forbids adoption
  "regardless of its paired benefit". Renaming the bytes to step around a frozen clause is exactly the kind of
  relabelling that frozen commitments exist to prevent.
- The honest framing: the coordinator, under the owner delegation, **supersedes** R3's NEVER-ADOPTABLE clause for
  SHA `37509a43…`. The supersession is **outcome-informed**, motivated by r1(b) and S1. R3's Stage 1 KILL on its own
  imitation gates stands. → **C1.**
- The §2.1 argument that "Stage 1 gates were proxies" was written after the gates were missed. That is acceptable
  as a stated reason for superseding them, but it must be labelled as post-hoc. → C1.

**Required disclosures in the final report (C1):**
- the full chain above, including the kills of R3b–R3e and the r1 S-teacher (−7.5 pp);
- that R3a was the only student whose game outcome was measured;
- that the threshold was calibrated on the R1 heldout64 slice;
- the student-favouring factors that S1/K0c equalised (cached forward) and those it did not:
  - **the deterministic calibrated fallback against v1 T=1 sampling.** This is part of tier S by design, which is
    fine for a tier claim, but it means the effect cannot be attributed to proposal quality;
- **training-distribution overlap.** R3a trained on the five archetype decks **and** the three L2 decks, against an
  opponent mix that **includes the released v1 stochastic policy**, which is this study's opponent. The primary and
  guard populations are both in-distribution for S and not for K2/K4, which have no training. That asymmetry favours
  S in every contrast and must be stated.

**Independence:**
- The verification script must be authored and committed before outcomes open (already in §5).
- Its author must not be the author of the reducer.
- The conformance reviewer must not have taken part in S1/R3. → C1.

## 2. Contrasts, multiplicity, alpha, power, and the decision rule (question 2)

### 2.1 Arithmetic check (all reproduced)

σ is computed as the 95% half-width / 1.96 · √600:

| Contrast | Source CI | σ (draft) | σ (mine) |
|---|---|---:|---:|
| S−K0c | S1 [−21.00, −11.17] | 0.61 | 0.614 |
| S−K2 | S1 [−5.33, 3.50] | 0.55 | 0.552 |
| K2−K4 | K2 [4.67, 12.33] | 0.48 | 0.479 |
| K4−K0 | K2 [−33.67, −24.83] | 0.55 | 0.552 |
| K2−K0 | K2 [−25.83, −15.83] | 0.63 | 0.625 |

**V1 power** (z = 2.394, SE = 0.63/√2400 = 1.286 pp): 0.476 / 0.763 / 0.932 / 0.988 at −13 / −14 / −15 / −16.
**NI power** (SE 1.143): 0.999 / 0.992 / 0.938 / 0.747 / 0.417 at −0.83 / 0 / +1 / +2 / +3. Both tables match.

Two small corrections:
- **"S1's own n = 600 had only about 0.48 power"** holds only at the Bonferroni α. At S1's own α (one-sided 0.025)
  the power at −16 was about **0.67**. → C13.
- **False NI of K2 against K4.** This is about 1.6e-8 with K2−K4's own σ = 0.48, but about 2.6e-7 with the
  planning σ = 0.56. "<10⁻⁷" holds only for the former. Cosmetic.

**One planning caveat.** K2−K0c and K4−K0c were never measured as paired contrasts; the K0c anchor exists only in
S1. Their σ values are borrowed from K0, which is reasonable but should be said.

### 2.2 Multiplicity

- **V1/V2.** Bonferroni over three tiers (98.33%) is correct. V1 ∧ V2 ∧ G is an intersection–union, so no further
  adjustment is needed for the conjunction.
- **Speed cell.** The cell is chosen by an external physical measurement, so no adjustment is needed *provided* the
  measurement cannot be steered by outcomes (§5, C10).
- **NI.** Up to two candidate selections are tested in sequence (S, then K2). Each is at one-sided 0.025, so the
  probability of falsely selecting an inferior cheaper tier is bounded by **0.05**, not 0.025. Use one-sided 0.0125
  (two-sided 97.5% intervals) for NI. Power at a true 0 remains 0.983, and 0.896 at +1. → C3.

### 2.3 Decision rule: is "cheapest within 5 pp of the strongest" well defined?

**Partly.** The NI test is CI-based (upper 95% ≤ +5), core counts 1/3/5 cannot tie, and A = ∅ maps to F0. But:

1. **T_max is "most cores", not "strongest".** Cells differ by tier, because r_1, r_3 and r_5 differ under load,
   so the tier with the most cores need not be the strongest.
   - Example: K4@0.8 = 30%, K2@1.0 = 22%, S@1.0 = 33%. S is NI against K4 (+3), so S is selected while being 11 pp
     worse than admissible K2.
   - **Fix (C3):** select the cheapest T ∈ A whose NI holds against **every** admissible tier with more cores. This
     is an intersection–union, so there is no extra α within a candidate. It is CI-based, needs no point-estimate
     choice of "strongest", and matches the memo's intent.
2. **The memo describes a point rule** ("within 5 points"). Rewrite it as "shown, with 95% confidence, to be no more
   than 5 points worse". → C13.
3. **The claim "the rule is monotone, so no new outcomes are needed" (§6.5) is wrong as stated.** Lowering r_T can
   move the selection toward a cheaper tier (K4 drops to the 0.8 cell, so S becomes NI against it) or toward a
   costlier one (S becomes infeasible, so K2 is chosen). What is true is that every cell is already played, so
   re-application needs no new games. → C3.
4. **Boundary and rounding.** Compute r_T and the gates in full float precision with no rounding; the boundaries
   are inclusive as written. → C3.
5. **The drift suspension (§8) has no defined exit.** "Suspended pending review" is a forking path. → C9.

## 3. Validity threats (question 3): blocking or disclosure

| Threat | Assessment | Class |
|---|---|---|
| **Deck shift onto the L2 decks** | **The premise is false:** the L2 decks are in R3a's training corpus (exit-r1 PLAN l.12–14, `emitter.py` uses 8 decks, `index%8`). G therefore tests nothing out of distribution. Live, the bot's own deck is an L2 deck, but **human opponents' decks are arbitrary**, so opponent-deck shift is the real risk, and G does not touch it. G is also nearly vacuous in the 0.8 cell (K0c@160 lost 79%), and it tests only against K0c, not the student-versus-search selection. | **Blocking → C2** |
| Re-labelled student | See §1. | **Blocking → C1** |
| **160 ms as a stand-in for slower cores** | Budget equivalence is conservative *if* every part of the decision slows by the same r. With fixed overhead f and r = 0.8, the Mac scoring budget is 192·0.8 − f = 153.6 − f, against the fleet's 152 − f. **But** (i) the r_T work unit omits belief preparation and Python reduction (§6.1 is screen8 plus the forward only); (ii) r_T is a **median**, while loss is sharply convex at the cliff (K-v2: +8 pp for 200→160 ms, +56 pp for 160→120 ms), so a median of 0.80 with a heavy slow tail sits beyond the evidence; (iii) p10 ≥ 0.60 *is* the cliff (V120 lost 82%). | **Blocking → C4** |
| **Fleet reference speed** | The reference is 127x01 alone, measured 3×. An idle 3990X boosts to about 4.3 GHz on one core, while 11 busy slots run near the all-core clock (about 3 GHz). The reference is then too fast, which **under-states** r_T (conservative) and can wrongly demote a tier. Reporting also spans several hosts with different cooling and clocks. | **Blocking → C5** |
| **One belief root vs live four roots** | All the evidence is one-root and internally consistent, and D2 registers one-root as the activated configuration. Its strength under perception noise is L2-v4's question. Activating it needs an L2-v4 amendment, which interacts with the frozen L2-v4 (P/O/S-d all use the K=4 P3 scorer). | Disclosure + C12 |
| **Plain v1 opponent as a human proxy** | It is the training opponent (in distribution for S). "V2 < 40%" is relative to v1, not to humans. The tier ranking against humans may differ, especially for a distilled student. | Disclosure (C12) |
| **GC and poll delays not charged** | Gen-2 pauses of about 145–155 ms occur about 0.15 times per game (S1: 84–108 per 600 games), so the expected strength effect is small. Mac gate 4 covers it, but "opportunity" is undefined in replay, and 150 ms sits exactly at the fleet's observed maximum. | Disclosure + C7 |
| **arm64** | Native exactness is covered. **Missing:** belief posterior, sampling and RNG equality (required by S1 MAC-TIER and k-v2 MAC-E4-V2). macOS libm can differ from glibc in the last ulp, so pre-register what happens. There is no core pinning on macOS: scheduling between P and E cores is by QoS, which the loaded measurement captures. | **Blocking (part) → C6** |
| **Emulator not running in the session** | The live load includes the Android emulator, a large CPU consumer, so replay-only r_T is an **upper bound**. The draft relies on formal E4 re-measurement, which is right, but the selection must be labelled provisional and formal E4 must re-check *every* gate. | Condition C8 |
| **F0 is unqualified** | If A = ∅, the L2-v4 four-root configuration "stays", and it is likely *less* Mac-feasible than any tier (D2's own argument). | Disclosure (C12) |

## 4. Seeds, harness, cores and host exclusivity (question 4)

- **Seeds.**
  - The proposed bases `45036031…`–`45036034…` appear nowhere else in the repo (grep).
  - They are spaced 1e8 apart, so helper offsets up to +271,829 cannot collide.
  - The seed audit must still bind every frozen range: K, K-v2, K2, S1 R1/R2 including the abandoned S1 attempt-1
    bank, R3 and round 2, R1/G generation (`4503599727370496…`, G `4503601607370496+[0,3e6)`), X/DAgger, noise
    ceiling, L2-v4 and helper offsets 0/13/100000..100003/271828..271829. Already required.
  - **Wording bug:** §6.1 says "smoke-range K0c games (seeds …3407…)", but …3407… is the corpus range and smoke is
    …3307…. → C13.
- **Harness reuse is not byte-reuse.**
  - S1 `run.py` asserts `hostname == '127x01'`, ≤13 workers and width 3; K2's harness was 03-only.
  - The draft needs new code: 5-core slots, 8 arm-cells, K4 and the 160 ms K2/K4 cells inside the S1 harness,
    multi-host, the guard population, and stratified 10k bootstrap. **K2-160 has never been run**, and K4 has never
    run inside the S1 harness.
  - → **C11:** enumerate the deltas, diff-review them, re-run the full S1 + K2 + K-v2 qualification batteries under
    the new harness (125-state 1/2/4-worker equality, belief ON/OFF, injected-clock, lateness, GC), and pin
    identical runtime and native SHAs per host.
- **Core allocations** K0c = S = 1, K2 = 3, K4 = 5 match K2/S1, with one exclusive 5-core slot per seed and no SMT.
  This is correct for timing, but 1-core cells leave four reserved cores idle. That cost belongs in the estimate.
- **Hosts.** As of 2026-10-10, **02 and 07 are down**; clasher runs on 01, 03, 04 and 08 only. The draft lists
  01–04, 07 and 08. Other points:
  - 04 runs the 30-minute hub mirror.
  - A cross-host T11 poller already voided S1's first attempt.
  - Plain `who` lists our own ssh sessions; use `~/.local/bin/fleet-console-users`.
  - Lab hosts are manually powered off without warning. → **C10, C11.**
- **Cost is understated about 3×.**
  - From measured walls, an S1 5-arm block took 266 s (13 slots, 3.41 h, 600 blocks) and a K2 3-arm block took
    115 s.
  - An 8-arm-cell block is therefore about 366 s, so 3,000 blocks ≈ **305 slot-hours ≈ 1,525 reserved
    physical-core-hours**. About 400–450 CPU-hours are actually consumed, which is probably where "500" came from.
  - Wall time is about **15 h on 100 cores**, or about **7 h on four exclusive hosts** with 11 slots each. → C13.
- **Missing blocks.** "An interrupted block is excluded and never re-seeded" fails the program in a fleet where
  hosts vanish. Losses can also be informative, since long games are more likely to be cut. → **C10:** pre-register
  a replacement bank and a cap.

## 5. E4-v3 addendum (question 5)

**Safety: pass.**
- The session replays train recordings only.
- It inherits every RUNBOOK restriction: no actuator, taps, login, client memory, client networking, ladder or
  heldout.
- The script refuses to run without `--sam-authorized-replay`, Darwin/arm64 and matching pins, and has no CLI for
  any live input or emulator address.
- Nothing touches an account, so the throwaway-account and detection-evasion rules are not engaged.
- **One tightening (C7):** "if the reference emulator is idle-running, its state is recorded" must mean the process
  table only (`ps`), with no adb, gRPC, window capture or socket connection.

**Does one session measure everything the rule needs?** It measures r_1/r_3/r_5 with p10, FPS and processed share
per tier, exactness, the student backend and p99, and GC overlap. Those are all of §6.3–6.4's inputs. **Gaps:**
1. **D1's stop rule is wrong.** "Any mismatch ⇒ K2/K4 infeasible; continue with S/K0c". But S and K0c use the same
   native coarse-first screen8 scorer. A single-thread score or action mismatch must make **every** tier infeasible.
   Only a 2/4-worker equality failure is K2/K4-specific. → C6.
2. **Belief/posterior/RNG exactness is missing.** → C6.
3. **D2 top-8 tolerance is unworkable.** For order disagreements it allows only "an exact logit tie", but MPS, and
   possibly Accelerate on CPU, will reorder *near* ties. Allow |Δlogit| ≤ 1e-4 between swapped entries on the
   fleet. → C6.
4. **D8 is circular.** It runs `gc.freeze()` only for "the feasible tier with the most cores", but gate 4 itself
   decides feasibility. Run D8 for every tier that passes gates 1–3 and 5 (about 15 min). The `gc.freeze()` variant
   must also be specified (when it is called, and whether thresholds change). → C7.
5. **Gate 4's "opportunity" is undefined in replay.** Define scheduled polls from packet timestamps at the live
   cadence, a delayed poll as a start more than 25 ms late, and the pause criterion as "would add ≥1 charged tick".
   → C7.
6. **Inconsistencies.**
   - B.1 says "packet list for §D5", but the packets are used in D7.
   - B.2 allows only stdlib, NumPy and Torch, while D4 uses psutil.
   - D5 runs "≥300 states and ≥5 min" but does not say how repeats are aggregated: take the per-state median over
     repeats, then the corpus median. → C7.
7. **No emulator load.** The result is provisional (C8).
8. **Exclusive Mac.** Other agent threads use the Mac mini. The session needs a pre-session quiescence census and
   a coordinator lock, not only the in-session 1 Hz detector. → C7.
9. **The reducer must be frozen before fleet outcomes open.** `measure_tiers.py` and the tiers reducer do not exist
   yet. If either is written after fleet outcomes open, choices in how r_T is computed become outcome-steerable.
   → C10.

---

## Conditions (exact edits, before the freeze)

**C1: R3a governance (PREREG §2.1, §9 D1, §0; memo "One caveat").** Replace the first paragraph of §2.1 with:
> "R3a (EMA `37509a43…`, calibration `e3003533…`, threshold 0.5005528330802917) is tested under its own name. R3
> recorded it as Stage 1 KILLED and 'ALWAYS NEVER-ADOPTABLE … regardless of its paired benefit'. **This PREREG,
> issued by coordinator `0523ae6f` under the owner's delegation, supersedes the NEVER-ADOPTABLE clause for these
> exact bytes only.** The supersession is outcome-informed: it follows the r1(b) descriptive game result and the
> S1 exploration. R3's Stage 1 KILL on its imitation gates is not re-litigated, and R3's files are not edited; an
> additive pointer is placed in `exit-r3/`. Claims concern these bytes in tier S only, never the R3 recipe. S1 and
> r1(b) data are used for planning only: they are never pooled or cited as evidence."

Also:
- Mark §2.1 reason 2 as "post-hoc rationale, stated after the gates were missed".
- Add a disclosure paragraph listing the R3b–R3e kills, r1 S-teacher, and the training overlap (8 decks, including
  L2; v1 opponent in the mix).
- Require the verifier's author to differ from the reducer's author.

**C2: Guard redesign (§1 G, §2.1 point 3, §3, §6.5).**
- **Delete** "which the student never trained on".
- **Guard population:** own deck ∈ the three L2-v4 families; opponent deck from the **three most frequent decks in
  the frozen C56 human deck catalogue that are not among the eight R1 training decks** and whose cards are all
  supported by native 44874fd6 and by the v1/R3a vocabularies. Select them by a hashed script before the freeze.
  Use alternating seats, 600 paired seeds, stratified 3 × 3 × 2. Add a qualification that every guard card is
  supported, with no fallback for unknown cards.
- **G becomes two parts:**
  - (G1) loss(T@s_T) − loss(K0c@s_1) has upper 95% CI < 0;
  - (G2) for any selected T that is cheaper than an admissible U: loss(T) − loss(U) on the guard has upper 95%
    CI ≤ **+10 pp**. Power at n = 600 with σ = 0.56 is 0.99 at a true 0 and 0.86 at +3.
- **Descriptive only:** the L2-own versus L2-opponent cells (in distribution for S).

**C3: Rule (§6.5 items 3–4, §5).** Replace item 3 with:
> "Otherwise, select the cheapest T ∈ A (fewest cores) such that NI(T, U) holds for **every** U ∈ A with more cores,
> where NI(T, U) is: the upper bound of the two-sided **97.5%** paired interval of loss(T@s_T) − loss(U@s_U) is
> ≤ +5 pp. If none holds, select the tier with the most cores in A."

Also:
- Replace "The rule is monotone, so no new outcomes are needed" with "All cells are pre-played, so re-application
  needs no new games. The selected tier may become cheaper or costlier."
- Add "r_T and all gates are computed in full float precision with no rounding."
- In §5, change NI to 97.5%.

**C4: r_T and budget equivalence (§6.1–6.4; addendum D3/D5).**
- **Work unit:** the complete no-deadline decision from sealed public history: belief preparation, candidate
  generation, root, scoring (with the tier's workers), reduction, and for S/K0c the forward and proposals. Exactness
  covers the final action and scores.
- **Speed:** r_T = **min**(median per-state ratio, Σ fleet wall / Σ Mac wall, fleet p90 wall / Mac p90 wall).
  Feasibility also requires per-state p10 ≥ **0.70** (raised from 0.60).
- **New feasibility gate 6 (deadline-mode equivalence).**
  - Before the freeze, run each tier's corpus on the fleet in deadline mode at 200 and 160 ms (8 ms reserve). Use
    the C5 host and load profile and 3 repeats. Record the cutoff, fallback and no-complete-play rates per state.
  - On the Mac, under load, run the same corpus at **200 ms** (a new step D5b, about 10 min).
  - T is feasible in cell s only if, on the Mac, cutoff and no-complete-play rates are ≤ the fleet's at the cell's
    deadline + 2 pp absolute.
  - Otherwise T moves down one cell. Below 0.8, T is infeasible.
- **Corpus states** are drawn from each tier's own excluded smoke games, not only from K0c's starved state
  distribution.

**C5: Fleet reference (§6.1).**
- Measure the reference **under the reporting load profile**: every other slot on the host runs the same frozen
  corpus loop, to put the CPU at all-core clocks.
- Measure on **every reporting host**. Hosts outside ±5% of the pooled median are excluded from reporting before
  the freeze.
- The frozen reference is the pooled per-state median.
- Record the clock (`/proc/cpuinfo` MHz sampled) during reference and reporting.

**C6: arm64 exactness (§7.2–7.3, addendum D1/D2).**
- Add: 125 histories with exact posterior, weights, cumulative order, resource ledger, samples and RNG (deadline ON
  and OFF), as in the K-v2 belief qualification.
- Replace D1's bracket with: "[A single-thread action, candidate, score or root mismatch ⇒ **all** tiers
  infeasible. A mismatch only in 2/4-worker equality ⇒ K2/K4 infeasible.]"
- Pre-register: "If actions and candidates match 125/125 and every score differs by ≤ 1e-12 relative, the result is
  **ARM64-NEAR-EXACT**: it passes, with disclosure. Anything else fails."
- D2: a top-8 order disagreement is allowed iff the swapped entries' fleet logits differ by ≤ 1e-4. Keep the gate
  rule as written.

**C7: Addendum fixes (B, D4, D7, D8, §F).**
- B.1: change "§D5" to "§D7".
- B.2: allow pinned `psutil`, or read per-CPU ticks via `host_processor_info` with ctypes.
- D5: aggregate repeats as a per-state median, rotating tier blocks of 50 states.
- **Define "opportunity"** as a scheduled poll at the live search/policy cadence, from packet timestamps. A
  maintenance-delayed poll starts >25 ms after its schedule. Gate 4 becomes: delayed polls ≤ 1%, and no in-window
  pause that would add a charged tick (>50 ms past schedule).
- **D8** runs for every tier passing gates 1–3 and 5. Register `gc.freeze()` as "called once after warm-up,
  default thresholds".
- **Emulator state** is read from the process table only: no adb, gRPC, socket or screen capture.
- **Exclusive Mac:** a coordinator lock plus a 5-minute pre-session census showing no foreign process above 0.2 core,
  in addition to §F's in-session detector.
- **Technical-failure classification** (§F) is mechanical. A frozen script reads it from receipts (exception trace,
  `pmset`/uptime, census). A human cannot declare it.

**C8: Provisional selection (§6.5 item 4, §10, addendum G).** Add:
> "A selection made from a replay-only session is **PROVISIONAL (emulator-off)**. It cannot be activated until
> formal E4/T9, with the emulator running, re-measures r_T, gate 6, FPS/processed, GC and the student p99 on the
> same corpora with the same frozen scripts. Every §6.3 gate is re-applied, using the worst value of each across all
> valid sessions."

Formal E4 must also be amended to include these measurements before it runs.

**C9: Drift suspension (§8 Validity).** Replace "suspended pending an independent harness-drift review" with:
> "Suspended. An independent reviewer inspects code and receipts, not outcomes by arm. A harness defect voids the
> study: a new PREREG with new seeds is required. No defect means the selection proceeds unchanged. The review's
> conclusion is committed before the selection is applied."

**C10: Integrity of outcome opening and missing blocks (§3, §6.5, §11).**
- (a) **Freeze `measure_tiers.py` and the tiers reducer** (independently reviewed) in the TIERS manifest before any
  fleet reporting game.
- (b) **The fleet outcome barrier stays closed until `tiers-summary.json` is committed.** If Sam has not authorised
  the Mac session within 14 days of reporting completing, outcomes may open. In that case any later Mac repeat
  session needs an independent reviewer to confirm the mechanical failure classification before it runs.
- (c) **Replacement bank** `4503603107370496+[2400, 2880)`. A block lost to host loss or foreign compute is replaced
  by index 2400 + 50·k + (i mod 50), which keeps its matchup and seat. Assignment is in order and is blind to
  outcomes. The guard is analogous, from +[600, 720).
- (d) If more than 10% of blocks need replacement, stop and amend before opening outcomes.
- (e) Copy completed blocks off-host to the hub at least every 30 minutes.

**C11: Harness and hosts (§3, §8).**
- List the code deltas from the S1/K2 freezes, and qualify per C6 and §4 above.
- **Hosts:** name them at the freeze from {01, 03, 04, 08} (02 and 07 are down; 05 is command only).
- On each timing host, before admission, pause the hub mirror and any cross-host pollers, using the stop files.
- The console check uses `fleet-console-users`. Slots are reduced to 8 if that check is positive at launch.
- Reporting on a host stops if a console user's load exceeds one core for more than 60 s. The in-flight blocks go to
  the replacement bank.
- Keep per-host native/runtime pin receipts.

**C12: Limits and disclosures (§10).** Add:
- the plain v1 opponent is the student's training opponent, and the tier ranking against humans is untested;
- in-distribution asymmetry favours S (C1);
- F0's own Mac feasibility is unmeasured;
- one-root activation needs an L2-v4 amendment before any L2-v4 confirmatory game (if L2-v4 reporting has already
  started with K = 4, the tier waits for L2-v4 to finish);
- GC pauses between decisions are uncharged on the fleet.

**C13: Corrections (PREREG §0, §4, §6.1; memo).**
- Cost: "≈ 1,500 reserved physical-core-hours (≈ 400–450 CPU-hours used); ≈ 7 h on four exclusive hosts, ≈ 15 h on
  100 cores".
- "S1's own n = 600 had about 0.67 power at its own α (0.48 at this study's Bonferroni α)".
- §6.1 "smoke-range" → "corpus-range".
- Memo: replace "matches two-thread search … statistical tie" with "within the 5-point margin in one exploratory
  study". Replace the rule wording with the CI version (C3). State the fleet cost correctly. Say that the Mac answer
  is provisional until the emulator-on test (C8).

**C14: Expected outcome (§0).** It omits the most likely 0.8-cell case. If r_5 ∈ [0.8, 1.0), K4@160 (K-v2: 26.5%)
is likely to beat S@160 (S1: 32.2%) by more than 5 pp, so **K4 would be selected over S**. Say so, so that a K4 pick
is not read as a surprise.

## Strong recommendations (not conditions)

- **C15. Mac before outcomes.** Schedule the Mac session before fleet outcomes open. It removes every residual
  steering path.
- **C16. Guard size.** Consider raising the guard to 1,200 seeds if the budget allows. Then G2 at +5 pp becomes
  feasible (power about 0.87 at a true 0).
- **C17. Logging.** Log per decision: unpruned candidate count, own elixir, the fallback action taken, `threads`,
  `coarse_horizon` and `default_source`, as REVIEW-K and the R3a audit recommended. This costs nothing and makes the
  elixir-leak mechanism testable descriptively.
- **C18. Factorial ablation.** The audit's ablation (student proposer + v1 fallback, and so on) is not needed for
  tier selection. Leave it as a separate exploration item rather than adding arms here.

## What is fine as drafted

- Fresh audited seed banks; complete-block pairing; rotated cell order on one slot.
- Honest lateness inherited unchanged; the 8 ms reserve; partial and late scores never count.
- The V1 margin (−10 pp) and V2 (<40%) as a guard against a collapsed control.
- NI's +5 pp, half the V1 margin.
- No interim looks; an integer-count verifier authored before outcomes.
- The 200 ms live deadline kept regardless of cell (D3); static tier per session (D4).
- r_T may only decrease after outcomes; the minimum across sessions is used.
- The student backend defaults to CPU, with MPS admitted only on a pre-stated benefit.
- The addendum's safety scope.
