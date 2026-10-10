# ExIt r2: teacher noise ceiling, passivity cause, next distillation design

Research analyst (Opus) for coordinator 0523ae6f, 2026-10-10. Read-only on all frozen files and running jobs; not
committed. Exploration lane; no gate, kill or recipe is changed by this note. Job prefix:
`127x04:/mpac/sdicks02/jobs/clasher/exit-noise-ceiling-20261010/` (`src/`, `analytic.json`, `full/`, `final.json`).

## 0. Bottom line

1. **W's tile choice is essentially non-reproducible, but its timing is stable.** Fresh W-screen8 instances on the same
   corpus roots agree with the recorded teacher on play-vs-WAIT 0.901 [0.888, 0.912] and play recall 0.852 [0.833, 0.869], but on the exact play
   only 0.255 [0.223, 0.284]. The cause is not near-tied scores. The scorer is deterministic: rescoring the *recorded* candidate list
   with a fresh belief gives the same action 96.7% of the time. The cause is that W ranks **16 randomly sampled
   tiles** plus 5 scripted proposals. A fresh teacher even *proposes* the recorded play only 31.7% of the time.
2. **Stage-1 gates against teacher self-agreement (W as its own student):**

   | Gate | Threshold | Fresh-W ceiling, 95% CI | Best of 3 fresh W | Reachable? |
   |---|---|---|---|---|
   | top-8 recall | ≥0.50 | 0.314 [0.283, 0.348] | pooled 0.353 [0.317, 0.387] | **No.** Above the teacher's own ceiling |
   | root hard agreement | ≥0.704 | 0.706 [0.686, 0.725] | majority 0.740 [0.720, 0.758] | Only for a near-perfect clone; W itself clears it by 0.002 |
   | play recall (gate prob) | ≥0.60 | 0.852 [0.833, 0.869] | — | Yes, in principle |
   | WAIT ≤1.5× teacher | ≤0.98 | 0.671 [0.654, 0.690] | — | Yes |

   **No student can pass stage 1 as frozen.** X3–X8 will be killed by top-8 regardless of quality. Treat r2 stage 1 as
   descriptive; R2 DAgger cannot trigger.
3. **Sharpening did not make the students passive per poll. They are calibrated to the wrong population.** Per poll,
   X1 plays at 1.10× and X2 at 0.97× the teacher's rate (0.081/0.072 vs 0.074). r1 S-teacher played at 2.28×. Only
   **21%** of supervised training rows are teacher roots. The other 79% are timed-wait/poll-wait continuation rows,
   which carry hard WAIT labels because the teacher had *committed* to a wait, not because WAIT was best in that state.
   Nothing in the state reveals that commitment. Stage 1 scores only roots, where the teacher plays 34.6%.
4. **Next design (decisive):** stop target sweeps. Run one **root-only** student evaluated directly in the 1-core
   S-default harness (~4 GPU-h, ~40 CPU-h). In parallel, measure **2-thread anytime W (K2)** (~20 CPU-h). If K2 is at
   least as good as the student, retire distillation.

## 1. Noise ceiling (Q1)

**Method.** I replayed 64 sealed r1 generation games: 16 per opponent (W, v1, baseline, script), drawn with fixed
seeds. Command-exact replay was asserted at every executed command. In each game I took up to 32 teacher roots
(2,048 roots in total) and rebuilt the public `observe()` info, then ran:

- 3 fully fresh frozen W-screen8 instances (fresh belief, candidate and root RNG);
- 2 fresh-belief rescorings of the recorded candidate list.

Seeds are 4503609917370496+[0, 2^18), disjoint from every plan range. The run used 8 processes on 04 physical cores
0–7, nice 19/SCHED_IDLE, no touch of 52/116/118–126. Memory PSI full stayed at 0.00 throughout. Cost:
0.39 CPU-h of scoring (≤5 CPU-h whole run, 8 cores × ~38 min wall, including replay) CPU-h, plus 0.1 CPU-h for the analytic pass.

Intervals are game-cluster bootstraps.

**Analytic, from 400k sampled corpus roots (1c8e1f49, read-only):**
- The median "top-2 gap of 0.003" is mostly an artifact: **18% of roots have an exact 0 gap**, from WAIT/WAIT10 alias
  ties.
- **25% of roots have no valid play** (4 WAIT aliases only).
- A typical root has 8 refined plays plus 4 waits.
- The decision-relevant margin, |best play − best WAIT|, has median 0.007; 19% of roots are below 0.003 and 48% below
  0.01.
- The rescoring shows these small margins are **deterministic, not noise**. With fixed candidates, the scores are
  bit-identical in 84.7% of roots, and the action agrees 96.7% of the time. Belief sampling matters only early, when
  the opponent's hand is unrevealed.

Analytic SE estimates are therefore the wrong model: there is no per-score rollout SE. The randomness is in
*which* actions get scored.

**Per-opponent and per-margin breakdowns** are in `final.json`. Timing agreement is 0.78–0.81 when the recorded play–WAIT
margin is below 3e-3 (393 roots), and 0.91–0.94 above 1e-2. All four opponent types are within ±0.02 on timing.
On exact tiles, the top-8 ceiling ranges from 0.23 (script) to 0.39 (W).

## 2. Why sharpening raised WAIT (Q2)

Four mechanisms, in order of size:

1. **Root aliasing (dominant).** The teacher re-decides only at roots. Between roots, every 5-tick poll is labeled hard
   WAIT. Plays occur on roots only: row play rate 0.0717 = 0.341 × 0.210. A student queried every poll learns the
   *hazard* (≈7%), not the root decision (34%). X1/X2 match that hazard almost exactly. Their root play rate is
   0.15–0.17 vs a non-root rate of ≈0.057, so they only partly recover the "root-ness" from features.
2. **The T=0.1 targets in r1 hid this.** Near-uniform root targets put about 50% mass on plays at *every* root
   (computed: 0.497 at T=0.1, 0.391 at T=.003, 0.349 at T=1e-4, 0.380 for z-score τ=.5). Sharpening removed about 15 pp
   of free play mass from each root row.
3. **Play weight 4→1.** The gate's effective play fraction over training rows fell from ≈0.19 (r1: T=.1, pw4) to
   ≈0.073–0.082 (X2/X1, pw1). r1's ×4 offset the aliasing by accident, which is why r1 *over*-played per poll (2.28×).
4. **Ties toward WAIT:** minor. WAIT aliases win exact ties by candidate order, but only ~5% of roots have a
   play–WAIT margin below 1e-4.

Capacity or features are not the binding limit. The play/WAIT signal the students miss is mostly *unobservable
commitment*, not hard-to-learn state.

## 3. Do stage-1 metrics predict strength? (Q3)

Not usefully. In r1, the arm with the best teacher recall (S-teacher, 0.403) was the **worst standalone policy**:
69.1% loss h2h vs v1, against 45.7% for S-human (recall 0.028). Yet S-teacher was the only arm that helped as a
fallback/proposer: −7.5 pp [−12.7, −2.2]. Stage-1 exact-tile metrics are capped below the gates by W's own sampling.
Stage-2 (h2h vs v1, free-running every poll) measures a job the student no longer has.

**Recommendation: yes, run descriptive post-kill games, but in the deployment harness, not h2h.** For X1, X2 and the
best of X3–X8 (by play recall), run S-default 1-core vs C-v1 on 600 fresh paired seeds, outside every frozen range. K1
cost 8.6 CPU-h per 600 games, so this is about 9 CPU-h per arm plus one shared C-v1/K0 anchor (≈17 CPU-h). Optionally
add the 256 h2h vs v1 (≈3 CPU-h per arm) for the correlation record. Label everything exploration and
never-adoptable. With r1's three points, this gives 6–7 (offline metric → deployment value) pairs to calibrate future
gates.

## 4. Next distillation design (Q4)

**In the S-default 1-core harness, the student is a *proposer*, not a decider.** W fully scores the student's argmax
and top-8 first, then keeps the best *complete* score against WAIT/WAIT10, which it always completes. False-positive
plays are cheap, because W mostly vetoes them (the argmax is scored first, so it usually completes). Passivity is fatal: K1, whose cutoffs left only WAITs, lost 96.5%. The
relevant targets are therefore (a) a high play recall at W's decision points and (b) *value* of proposals, not
exact-tile identity.

**R3 (one arm, not a sweep):**
- **Training rows:** train on **teacher-root rows only** (6.01 M in 1c8e1f49, plus G top-up). Drop wait kinds 1/2.
- **Targets:** listwise softmax over valid candidates at T=.003, play weight 1.
- **Value head:** add an auxiliary per-candidate **advantage regression**, (score − WAIT score) on the ~12 scored
  candidates, using Huber loss. It learns tile *value* from deterministic scores rather than the random argmax. Use it
  to rank top-k proposals.
- **Gate:** calibrate the gate threshold on held-out roots to the teacher's 34.6% root play rate.
- **Cost:** about 2,500 steps × 8,192 (≈3.4 epochs) ≈ **1.5–2 GPU-h**. Use 2 arms (root-only with and without the
  advantage head) ≈ **4 GPU-h**.
- **New stage-1 gates (ceiling-relative):**
  - play recall ≥0.75 × the fresh-W ceiling;
  - play/WAIT agreement ≥ all-WAIT + 10 pp;
  - **W-score regret** of the best of the student's top-8 vs W's argmax, computed with the frozen scorer on the 64
    held-out games (≈0.5 CPU-h per arm).
- **Stage 2:** S-default 1-core 600 paired seeds directly (≈9 CPU-h per arm + 17 shared). Drop the h2h gate.
- **Total:** ≈4 GPU-h and ≈40 CPU-h, about 6 h of wall time.

**Do in parallel: K2 (2-thread anytime W at 200 ms).** It needs no GPU: 600 paired seeds × K2/K0 ≈ 20 CPU-h on 01/03.
K4 already equals KU, and 1-thread K1 fails only because the coarse scan is too slow. If K2's retention is ≥80% of
K4's, the Mac needs only 2 free cores and the student becomes a contingency. In that case, stop distillation after R3's
S-default readout.

**Rejected candidates:**
- **Margin-aware loss alone:** the ties are deterministic, so ignoring them doesn't fix aliasing.
- **Coarse action space:** this would help exact-tile metrics, but W must still pick tiles. Revisit only if R3's
  regret is poor.
- **More X arms / R2 DAgger:** the gates are unreachable, and DAgger relabels the same aliasing.

**Data hygiene for future generation:** have the emitter also record the teacher's would-be root decision at a sparse
random 10% of continuation polls (score-only, not executed). That removes aliasing at its source, for ≈+10% teacher
CPU.
